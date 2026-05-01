"""
Standalone dispatch simulation — no DB, no Discord.

Run with:  python -m tests.test_dispatch_sim
           (from the Idleology project root)

For each test partner, simulates 1000 48-hour dispatch windows and prints
aggregated per-window averages so we can sanity-check loot rates.
"""

from __future__ import annotations

import random
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Minimal Partner stub — mirrors only the fields dispatch.py reads
# ---------------------------------------------------------------------------

@dataclass
class FakePartner:
    name: str
    partner_id: int = 1
    level: int = 50
    exp: int = 0

    # dispatch skill slots: (key, level) tuples
    dispatch_slot_1: Optional[str] = None
    dispatch_slot_1_lvl: int = 0
    dispatch_slot_2: Optional[str] = None
    dispatch_slot_2_lvl: int = 0
    dispatch_slot_3: Optional[str] = None
    dispatch_slot_3_lvl: int = 0

    sig_dispatch_lvl: int = 0

    dispatch_task: Optional[str] = "combat"
    dispatch_start_time: Optional[str] = None
    dispatch_task_2: Optional[str] = None
    dispatch_start_time_2: Optional[str] = None
    is_dispatched: bool = True

    # Signature key determined by partner_id (mirrors _SIG_DISPATCH_KEYS)
    _SIG_KEYS = {
        1: "sig_di_skol",
        2: "sig_di_eve",
        3: "sig_di_kay",
        4: "sig_di_sigmund",
        5: "sig_di_velour",
        6: "sig_di_flora",
        7: "sig_di_yvenn",
    }

    @property
    def sig_dispatch_key(self) -> Optional[str]:
        return self._SIG_KEYS.get(self.partner_id)

    @property
    def sig_combat_key(self) -> Optional[str]:
        return None

    @property
    def dispatch_skills(self) -> List[Tuple[Optional[str], int]]:
        return [
            (self.dispatch_slot_1, self.dispatch_slot_1_lvl),
            (self.dispatch_slot_2, self.dispatch_slot_2_lvl),
            (self.dispatch_slot_3, self.dispatch_slot_3_lvl),
        ]


# ---------------------------------------------------------------------------
# Patch sys.path so we can import from the project root
# ---------------------------------------------------------------------------

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.partners.dispatch import calculate_rewards, calculate_sigmund_rewards

# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

_48H_AGO = (datetime.now(timezone.utc) - timedelta(hours=48)).replace(tzinfo=None).isoformat()
_96H_AGO = (datetime.now(timezone.utc) - timedelta(hours=96)).replace(tzinfo=None).isoformat()
_NOW = datetime.now(timezone.utc).replace(tzinfo=None)

RUNS = 1_000


def _run(partner: FakePartner, task: str = "combat", start: str = _48H_AGO) -> dict:
    partner.dispatch_task = task
    partner.dispatch_start_time = start
    return calculate_rewards(partner, start, task_override=task, now=_NOW)


def simulate(partner: FakePartner, task: str = "combat", runs: int = RUNS) -> dict:
    """Run `runs` independent 48h windows and aggregate."""
    totals: dict = {"gold": [], "exp": [], "rolls": []}
    item_totals: dict = {}

    for _ in range(runs):
        result = _run(partner, task=task)
        totals["gold"].append(result["gold"])
        totals["exp"].append(result["exp"])
        totals["rolls"].append(result["rolls"])
        for k, v in result["items"].items():
            item_totals.setdefault(k, []).append(v)

    # Pad item lists with 0s for windows where they didn't drop
    for k in item_totals:
        while len(item_totals[k]) < runs:
            item_totals[k].append(0)

    return {
        "gold_avg": statistics.mean(totals["gold"]),
        "exp_avg": statistics.mean(totals["exp"]),
        "rolls_avg": statistics.mean(totals["rolls"]),
        "items": {k: statistics.mean(v) for k, v in sorted(item_totals.items())},
    }


def _fmt_items(items: dict) -> str:
    if not items:
        return "  (none)"
    return "\n".join(f"  {k:<30} {v:.2f}/window" for k, v in items.items())


def report(label: str, result: dict, task: str = "combat") -> None:
    print(f"\n{'='*60}")
    print(f"  {label}  [{task}]")
    print(f"{'='*60}")
    if task == "combat":
        print(f"  Gold / window:    {result['gold_avg']:>10,.0f}")
        print(f"  Partner EXP / w:  {result['exp_avg']:>10,.0f}")
    print(f"  Rolls / window:   {result['rolls_avg']:>10.2f}")
    print(f"  Items:")
    print(_fmt_items(result["items"]))


# ---------------------------------------------------------------------------
# Test partners
# ---------------------------------------------------------------------------

def make_partners() -> list:
    partners = []

    # 1. Bare baseline — no skills
    p = FakePartner(name="Baseline (no skills)", partner_id=1, sig_dispatch_lvl=0)
    partners.append(("Baseline — no skills", p, "combat"))

    # 2. Full combat stack — gold + exp + extra reward at max
    p = FakePartner(
        name="Combat Specialist",
        partner_id=1, sig_dispatch_lvl=0,
        dispatch_slot_1="di_gold_boost", dispatch_slot_1_lvl=5,
        dispatch_slot_2="di_exp_boost",  dispatch_slot_2_lvl=5,
        dispatch_slot_3="di_extra_reward", dispatch_slot_3_lvl=5,
    )
    partners.append(("Combat: gold+exp+extra (all Lv.5)", p, "combat"))

    # 3. Settlement mat hunter
    p = FakePartner(
        name="Material Hunter",
        partner_id=1, sig_dispatch_lvl=0,
        dispatch_slot_1="di_gold_boost",       dispatch_slot_1_lvl=3,
        dispatch_slot_2="di_extra_reward",     dispatch_slot_2_lvl=5,
        dispatch_slot_3="di_settlement_mat",   dispatch_slot_3_lvl=5,
    )
    partners.append(("Combat: gold+extra+settlement_mat (Lv.5)", p, "combat"))

    # 4. Pinnacle / tome hunter
    p = FakePartner(
        name="Pinnacle Hunter",
        partner_id=1, sig_dispatch_lvl=0,
        dispatch_slot_1="di_gold_boost",    dispatch_slot_1_lvl=3,
        dispatch_slot_2="di_extra_reward",  dispatch_slot_2_lvl=5,
        dispatch_slot_3="di_pinnacle_find", dispatch_slot_3_lvl=5,
    )
    partners.append(("Combat: gold+extra+pinnacle_find (Lv.5)", p, "combat"))

    # 5. Contract (ticket) hunter
    p = FakePartner(
        name="Ticket Farmer",
        partner_id=1, sig_dispatch_lvl=0,
        dispatch_slot_1="di_gold_boost",     dispatch_slot_1_lvl=3,
        dispatch_slot_2="di_extra_reward",   dispatch_slot_2_lvl=5,
        dispatch_slot_3="di_contract_find",  dispatch_slot_3_lvl=5,
    )
    partners.append(("Combat: gold+extra+contract_find (Lv.5)", p, "combat"))

    # 6. Skol sig — essence finder at max (5%)
    p = FakePartner(
        name="Skol (essence sig)",
        partner_id=1, sig_dispatch_lvl=5,
        dispatch_slot_1="di_gold_boost",    dispatch_slot_1_lvl=5,
        dispatch_slot_2="di_exp_boost",     dispatch_slot_2_lvl=5,
        dispatch_slot_3="di_extra_reward",  dispatch_slot_3_lvl=5,
    )
    partners.append(("Skol Sig Lv.5 — essence chance 5%", p, "combat"))

    # 7. Eve sig — spirit stone finder at max (5%)
    p = FakePartner(
        name="Eve (spirit stone sig)",
        partner_id=2, sig_dispatch_lvl=5,
        dispatch_slot_1="di_gold_boost",    dispatch_slot_1_lvl=5,
        dispatch_slot_2="di_exp_boost",     dispatch_slot_2_lvl=5,
        dispatch_slot_3="di_extra_reward",  dispatch_slot_3_lvl=5,
    )
    partners.append(("Eve Sig Lv.5 — spirit_stone chance 5%", p, "combat"))

    # 8. Velour sig — elemental key at max (5%)
    p = FakePartner(
        name="Velour (elemental key sig)",
        partner_id=5, sig_dispatch_lvl=5,
        dispatch_slot_1="di_gold_boost",    dispatch_slot_1_lvl=5,
        dispatch_slot_2="di_exp_boost",     dispatch_slot_2_lvl=5,
        dispatch_slot_3="di_extra_reward",  dispatch_slot_3_lvl=5,
    )
    partners.append(("Velour Sig Lv.5 — elemental_key chance 5%", p, "combat"))

    # 9. Yvenn sig — slayer drop at max (5%)
    p = FakePartner(
        name="Yvenn (slayer sig)",
        partner_id=7, sig_dispatch_lvl=5,
        dispatch_slot_1="di_gold_boost",    dispatch_slot_1_lvl=5,
        dispatch_slot_2="di_exp_boost",     dispatch_slot_2_lvl=5,
        dispatch_slot_3="di_extra_reward",  dispatch_slot_3_lvl=5,
    )
    partners.append(("Yvenn Sig Lv.5 — slayer_drop chance 5%", p, "combat"))

    # 10. Boss dispatch — bare
    p = FakePartner(name="Boss Baseline", partner_id=1, sig_dispatch_lvl=0)
    partners.append(("Boss dispatch — no skills", p, "boss"))

    # 11. Boss dispatch — with extra reward skill
    p = FakePartner(
        name="Boss Specialist",
        partner_id=1, sig_dispatch_lvl=0,
        dispatch_slot_1="di_boss_reward",  dispatch_slot_1_lvl=5,
    )
    partners.append(("Boss dispatch — boss_reward Lv.5", p, "boss"))

    # 12. Gathering dispatch — skilling boost at max
    p = FakePartner(
        name="Gatherer",
        partner_id=6, sig_dispatch_lvl=5,   # Flora sig: 50% double chance
        dispatch_slot_1="di_skilling_boost", dispatch_slot_1_lvl=5,
        dispatch_slot_2="di_skilling_boost", dispatch_slot_2_lvl=5,  # same key dupe for test
    )
    partners.append(("Gathering: skilling Lv.5 + Flora sig Lv.5", p, "gathering"))

    # --- Level scaling checks ---
    for lv in (1, 25, 50, 75, 100):
        p = FakePartner(
            name=f"Level {lv} baseline",
            partner_id=1, level=lv, sig_dispatch_lvl=0,
        )
        partners.append((f"Combat baseline — Lv.{lv}", p, "combat"))

    return partners


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    random.seed(42)

    skill_tiers = {
        "mining": "idea",
        "fishing": "titanium",
        "woodcutting": "idea",
    }

    test_cases = make_partners()

    for label, partner, task in test_cases:
        kw = {"task": task}
        if task == "gathering":
            # patch calculate_rewards to pass skill_tiers
            result_list = []
            for _ in range(RUNS):
                partner.dispatch_task = task
                r = calculate_rewards(
                    partner,
                    _48H_AGO,
                    task_override=task,
                    skill_tiers=skill_tiers,
                    now=_NOW,
                )
                result_list.append(r)
            agg = {
                "gold_avg": statistics.mean(r["gold"] for r in result_list),
                "exp_avg": statistics.mean(r["exp"] for r in result_list),
                "rolls_avg": statistics.mean(r["rolls"] for r in result_list),
            }
            all_keys = set()
            for r in result_list:
                all_keys |= r["items"].keys()
            item_avgs = {}
            for k in sorted(all_keys):
                vals = [r["items"].get(k, 0) for r in result_list]
                item_avgs[k] = statistics.mean(vals)
            agg["items"] = item_avgs
            report(label, agg, task=task)
        else:
            agg = simulate(partner, task=task)
            report(label, agg, task=task)

    # --- Boss party simulation ---
    from core.partners.dispatch import calculate_boss_party_rewards

    print(f"\n{'='*60}")
    print(f"  Boss Party Dispatch (12h window, 1000 runs)")
    print(f"{'='*60}")

    for desc, a_lv, t_lv, h_lv in [
        ("All Lv.1",  1,   1,   1  ),
        ("All Lv.50", 50,  50,  50 ),
        ("All Lv.100",100, 100, 100),
        ("Mixed Lv.", 25,  75,  50 ),
    ]:
        golds, sigils, tickets, a_exps, t_exps, h_exps = [], [], [], [], [], []
        for _ in range(RUNS):
            a = FakePartner(name="A", level=a_lv)
            t = FakePartner(name="T", level=t_lv)
            h = FakePartner(name="H", level=h_lv)
            r = calculate_boss_party_rewards(a, t, h)
            golds.append(r["gold"])
            sigils.append(r["sigil_count"])
            tickets.append(1 if r["guild_ticket"] else 0)
            a_exps.append(r["partner_exps"]["attacker"])
            t_exps.append(r["partner_exps"]["tank"])
            h_exps.append(r["partner_exps"]["healer"])
        print(f"\n  Party {desc}  (ATK {a_lv} / TNK {t_lv} / HLR {h_lv})")
        print(f"  Gold avg:        {statistics.mean(golds):>10,.0f}")
        print(f"  Sigils avg:      {statistics.mean(sigils):>10.2f}")
        print(f"  Ticket rate:     {statistics.mean(tickets)*100:>9.1f}%")
        print(f"  ATK partner EXP: {statistics.mean(a_exps):>10,.0f}")
        print(f"  TNK partner EXP: {statistics.mean(t_exps):>10,.0f}")
        print(f"  HLR partner EXP: {statistics.mean(h_exps):>10,.0f}")

    print(f"\n{'='*60}")
    print(f"  Simulation complete — {RUNS} windows per partner")
    print(f"  All values are per dispatch window (combat=48h, boss party=12h)")
    print(f"{'='*60}\n")
