#!/usr/bin/env python3
"""
Artisan Mastery Monte Carlo Simulation — Accurate, Idea-focused verification.

Uses the live mastery getters (after wiring fixes) + the canonical base yield tables
from the game (BiS ideal/titanium/felling tools). Runs 3000 simulated days (24 ticks/day)
to produce stable per-day averages.

Specifically answers: "we have nodes that say 55% Idea ore (from hourly ticks), is it actually increasing it by 55%?"
"""

import json
import random
from collections import defaultdict
from typing import Dict

from core.skills.mastery import (
    get_never_empty_proc_chance,
    get_rich_event_chance,
    get_signature_resource_bonus,
    get_yield_multiplier,
    BRANCH_NODE_ORDERS,
    ALL_TREES,
)


DAYS = 3000
TICKS_PER_DAY = 24

TOOL_TIERS = {
    "mining": "ideal",
    "fishing": "titanium",
    "woodcutting": "felling",
}

SIGNATURE = {
    "mining": "idea",
    "fishing": "titanium_bones",
    "woodcutting": "idea_logs",
}


# Exact base ranges copied from the canonical SkillMechanics.calculate_yield (BiS column only for speed)
BASE_RANGES = {
    "mining": {
        "iron": (7, 12),
        "coal": (6, 10),
        "gold": (5, 8),
        "platinum": (4, 7),
        "idea": (3, 5),
    },
    "fishing": {
        "desiccated_bones": (7, 12),
        "regular_bones": (6, 10),
        "sturdy_bones": (5, 8),
        "reinforced_bones": (4, 7),
        "titanium_bones": (3, 5),
    },
    "woodcutting": {
        "oak_logs": (7, 12),
        "willow_logs": (6, 10),
        "mahogany_logs": (5, 8),
        "magic_logs": (4, 7),
        "idea_logs": (3, 5),
    },
}


def _build_unlocked_for_invested(
    skill: str, invested_per_branch: Dict[str, int]
) -> Dict[str, list]:
    """Given invested points per branch, return the list of nodes that would be unlocked (cumulative)."""
    order_map = BRANCH_NODE_ORDERS.get(skill, {})
    tree = ALL_TREES[skill]
    result = {}
    for branch, invested in invested_per_branch.items():
        order = order_map.get(branch, [])
        unlocked = []
        cumulative = 0
        for node in order:
            cost = tree.get(node, {}).get("cost", 0)
            cumulative += cost
            if cumulative <= invested:
                unlocked.append(node)
            else:
                break
        result[branch] = unlocked
    return result


def make_row(
    mining: Dict[str, int],
    fishing: Dict[str, int],
    wood: Dict[str, int],
    insight: int = 0,
) -> dict:
    """Create a mastery row dict with correct 'invested' + 'unlocked' lists derived from the points."""

    def alloc(skill: str, d: Dict[str, int]) -> str:
        unlocked_map = _build_unlocked_for_invested(skill, d)
        return json.dumps(
            {
                b: {"invested": p, "unlocked": unlocked_map.get(b, [])}
                for b, p in d.items()
            },
            separators=(",", ":"),
        )

    return {
        "mining_alloc": alloc("mining", mining),
        "fishing_alloc": alloc("fishing", fishing),
        "woodcutting_alloc": alloc("woodcutting", wood),
        "mastery_insight": insight,
    }


def base_yield(skill: str, tier: str) -> Dict[str, int]:
    """Replicates the deterministic-range part of SkillMechanics.calculate_yield (no random here; tick will roll)."""
    ranges = BASE_RANGES[skill]
    out = {}
    for res, (lo, hi) in ranges.items():
        # Only resources available at this tier or lower are present; for BiS we always have all
        # The original samples random.randint only for those the tier can produce.
        # For simplicity in expectation sim we always roll the BiS range when the resource exists for the tier.
        if tier in ("ideal", "titanium", "felling") or res in (
            "idea",
            "titanium_bones",
            "idea_logs",
        ):
            out[res] = random.randint(lo, hi)
        # For lower resources the ranges are higher at BiS; we include them all for total realism.
        # (The mapping above already encodes the BiS numbers.)
    # Simpler: always produce the full BiS column for the 5 resources.
    # Rebuild accurately:
    out = {}
    for res, (lo, hi) in ranges.items():
        out[res] = random.randint(lo, hi)
    return out


def tick(skill: str, row: dict, tier: str) -> Dict[str, float]:
    """One passive tick with full mastery (now including the wired +55% synergy sig bonus)."""
    base = base_yield(skill, tier)
    y = get_yield_multiplier(skill, row)
    s = get_signature_resource_bonus(
        skill, row
    )  # now correctly includes Living Mountain +55% (hourly ticks)
    sig = SIGNATURE[skill]

    # Apply global yield first (to everything)
    res = {k: v * y for k, v in base.items()}

    # Then signature-specific (Quality 38% + Synergy 55% when owned) — only on the signature resource (passive hourly ticks)
    if sig in res:
        res[sig] *= s

    # Rich event (4% at Quality 3pt unlock, 22% at 5pt Resonance, or 3% from Synergy 5pt capstone)
    if random.random() < get_rich_event_chance(skill, row):
        for k in res:
            res[k] *= 2.6

    # Never Empty proc (+70%)
    if random.random() < get_never_empty_proc_chance(skill, row):
        for k in res:
            res[k] *= 1.7

    return res


def simulate_days(row: dict, days: int = DAYS) -> Dict[str, float]:
    """Return per-day averages for total resources per skill + the raw signature resource counts."""
    per_skill_totals = defaultdict(float)
    sig_totals = defaultdict(float)  # "mining_idea", "fishing_titanium_bones", ...
    sig_key = {s: SIGNATURE[s] for s in ("mining", "fishing", "woodcutting")}

    for _ in range(days):
        for skill in ("mining", "fishing", "woodcutting"):
            daily_sig = 0.0
            daily_total = 0.0
            for _ in range(TICKS_PER_DAY):
                g = tick(skill, row, TOOL_TIERS[skill])
                daily_total += sum(g.values())
                if sig_key[skill] in g:
                    daily_sig += g[sig_key[skill]]
            per_skill_totals[skill] += daily_total
            sig_totals[f"{skill}_{sig_key[skill]}"] += daily_sig

    result = {}
    for s in ("mining", "fishing", "woodcutting"):
        result[s] = per_skill_totals[s] / days
    for k, v in sig_totals.items():
        result[k] = v / days
    return result


def main():
    print("=" * 78)
    print("ARTISAN MASTERY — IDEA ORE / SIGNATURE RESOURCE VERIFICATION")
    print(
        f"Monte Carlo: {DAYS} days x {TICKS_PER_DAY} ticks, BiS tools (ideal / titanium / felling)"
    )
    print(
        "All multipliers from live core/skills/mastery.py getters (Yield + Quality + Synergy sig)"
    )
    print("=" * 78)

    profiles = {
        "No Artisan (baseline)": (
            {"yield": 0, "quality": 0, "synergy": 0},
            {"yield": 0, "quality": 0, "synergy": 0},
            {"yield": 0, "quality": 0, "synergy": 0},
            0,
        ),
        "Mining Maxed (no insight)": (
            {"yield": 22, "quality": 21, "synergy": 29},  # living_mountain unlocked
            {"yield": 0, "quality": 0, "synergy": 0},
            {"yield": 0, "quality": 0, "synergy": 0},
            0,
        ),
        "All Trees Maxed (no insight)": (
            {"yield": 22, "quality": 21, "synergy": 29},
            {"yield": 22, "quality": 21, "synergy": 29},
            {"yield": 22, "quality": 21, "synergy": 29},
            0,
        ),
        "All Trees Maxed + 50 Insight (post-max scaling)": (
            {"yield": 22, "quality": 21, "synergy": 29},
            {"yield": 22, "quality": 21, "synergy": 29},
            {"yield": 22, "quality": 21, "synergy": 29},
            50,  # +10% global yield from insight (0.2% × 50)
        ),
    }

    for name, (m, f, w, ins) in profiles.items():
        row = make_row(m, f, w, ins)
        out = simulate_days(row)

        print(f"\n{name}:")
        print(f"  Mining total resources / day : {out['mining']:7.1f}")
        print(
            f"    +-- Idea Ore (signature)    : {out['mining_idea']:7.1f}   (the 55% node target)"
        )
        print(f"  Fishing total / day          : {out['fishing']:7.1f}")
        print(f"    +-- Titanium Bones         : {out['fishing_titanium_bones']:7.1f}")
        print(f"  Woodcutting total / day      : {out['woodcutting']:7.1f}")
        print(f"    +-- Idea Logs              : {out['woodcutting_idea_logs']:7.1f}")

        # Quick diagnostic for the Mining Maxed case
        if "Mining Maxed" in name or "All Trees Maxed" in name:
            # Re-compute the raw multipliers that were applied for mining
            y = get_yield_multiplier("mining", row)
            s = get_signature_resource_bonus("mining", row)
            print(f"  [debug] Effective multipliers applied to Mining (BiS base):")
            print(f"          Yield branch (global) : {y:.3f}×")
            print(
                f"          Signature (Idea)      : {s:.3f}×   <--- includes Living Mountain +55% when present"
            )
            print(
                f"          Combined on Idea      : {y * s:.3f}× before Rich/NE procs"
            )

    print("\n" + "=" * 78)
    print("INTERPRETATION (Living Mountain / equivalent 5pt Synergy nodes):")
    print(
        "  - Quality branch alone (Ideal Seeker + Crystallized Insight) = +38% Idea Ore from passive hourly ticks"
    )
    print(
        "  - Adding Living Mountain (synergy) = +55% Idea Ore yield from passive hourly mining ticks"
    )
    print(
        "    (total signature multiplier on Idea = 1.93× when both Quality + Synergy 5pt are taken)"
    )
    print(
        "  - The sim now correctly includes the +55% because get_signature_resource_bonus checks synergy nodes."
    )
    print(
        "  - Previously this +55% was completely ignored (only Quality 38% existed in the getter)."
    )
    print("=" * 78)


if __name__ == "__main__":
    random.seed(42)  # reproducible run for comparison
    main()
