from __future__ import annotations

import random
from datetime import datetime, timezone
from math import floor
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import Partner

from core.partners.mechanics import (
    _FLORA_DOUBLE_CHANCE,
    _KAY_DISPATCH_BONUS_HOURS,
    _SIGMUND_EFFECTIVENESS,
)

# ---------------------------------------------------------------------------
# Loot tables
# ---------------------------------------------------------------------------

_COMBAT_LOOT_TYPES = ["gold", "boss_key", "refinement_rune", "potential_rune", "shatter_rune"]
_COMBAT_LOOT_WEIGHTS = [75, 10, 5, 5, 5]

_BOSS_SIGILS = ["blessed_bismuth", "sparkling_sprig", "capricious_carp"]

# Gold range per combat dispatch reward roll
_COMBAT_GOLD_MIN = 500
_COMBAT_GOLD_MAX = 2_000

# XP range per combat dispatch reward roll (granted to the player)
_COMBAT_EXP_MIN = 500
_COMBAT_EXP_MAX = 1_500

# ---------------------------------------------------------------------------
# Gathering material tables  (tool_name → materials list + quantity range)
# ---------------------------------------------------------------------------

_MINING_TIERS: Dict[str, dict] = {
    "iron":     {"materials": ["iron"],              "qty": (2, 5)},
    "steel":    {"materials": ["iron", "coal"],      "qty": (3, 6)},
    "gold":     {"materials": ["gold"],              "qty": (2, 5)},
    "platinum": {"materials": ["platinum"],          "qty": (2, 4)},
    "idea":     {"materials": ["idea"],              "qty": (1, 3)},
}

_FISHING_TIERS: Dict[str, dict] = {
    "desiccated": {"materials": ["desiccated_bones"],  "qty": (2, 5)},
    "regular":    {"materials": ["regular_bones"],     "qty": (3, 6)},
    "sturdy":     {"materials": ["sturdy_bones"],      "qty": (2, 5)},
    "reinforced": {"materials": ["reinforced_bones"],  "qty": (2, 4)},
    "titanium":   {"materials": ["titanium_bones"],    "qty": (1, 3)},
}

_WOODCUTTING_TIERS: Dict[str, dict] = {
    "flimsy":    {"materials": ["oak_logs"],                   "qty": (2, 5)},
    "oak":       {"materials": ["oak_logs", "willow_logs"],    "qty": (3, 6)},
    "willow":    {"materials": ["willow_logs"],                "qty": (2, 5)},
    "mahogany":  {"materials": ["mahogany_logs"],              "qty": (2, 4)},
    "magic":     {"materials": ["magic_logs"],                 "qty": (2, 4)},
    "idea":      {"materials": ["idea_logs"],                  "qty": (1, 3)},
}

_GATHERING_SKILL_MAP = {
    "mining":      _MINING_TIERS,
    "fishing":     _FISHING_TIERS,
    "woodcutting": _WOODCUTTING_TIERS,
}

_TOOL_COLUMN = {
    "mining":      "pickaxe_tier",
    "fishing":     "fishing_rod",
    "woodcutting": "axe_type",
}


# ===========================================================================
# Core helpers
# ===========================================================================

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_cap_hours(partner: Partner) -> float:
    """Max accumulation hours for this partner (48h + Kay sig bonus)."""
    cap = 48.0
    if partner.sig_dispatch_key == "sig_di_kay" and partner.sig_dispatch_lvl >= 1:
        cap += _KAY_DISPATCH_BONUS_HOURS.get(partner.sig_dispatch_lvl, 0)
    return cap


def elapsed_hours(start_time_str: Optional[str], now: Optional[datetime] = None) -> float:
    """Hours elapsed since start_time_str (ISO format). Returns 0 for missing input."""
    if not start_time_str:
        return 0.0
    if now is None:
        now = _now_utc()
    try:
        start = datetime.fromisoformat(start_time_str)
    except ValueError:
        return 0.0
    return max(0.0, (now - start).total_seconds() / 3600.0)


def reward_rolls(partner: Partner, start_time_str: str, now: Optional[datetime] = None) -> float:
    """
    Number of reward rolls accumulated.
    Each hour = 1 tick = 0.25 rolls. Capped by get_cap_hours().
    """
    cap = get_cap_hours(partner)
    hours = elapsed_hours(start_time_str, now)
    return min(hours, cap) * 0.25


# ===========================================================================
# Dispatch skill modifier extraction
# ===========================================================================

def _extract_skill_modifiers(partner: Partner) -> Dict[str, Any]:
    """
    Reads dispatch skill slots and returns a dict of active modifiers:
      exp_mult, gold_mult, skilling_mult,
      extra_reward_chance, settlement_mat_chance, boss_extra_chance,
      contract_chance, pinnacle_chance
    Plus sig-based rates.
    """
    mods: Dict[str, Any] = {
        "exp_mult": 1.0,
        "gold_mult": 1.0,
        "skilling_mult": 1.0,
        "extra_reward_chance": 0.05,
        "settlement_mat_chance": 0.0,
        "boss_extra_chance": 0.0,
        "contract_chance": 0.0,
        "pinnacle_chance": 0.0,
        "essence_chance": 0.0,
        "spirit_stone_chance": 0.0,
        "elemental_key_chance": 0.0,
        "slayer_drop_chance": 0.0,
        "flora_double_chance": 0.0,
    }

    for (key, lvl) in partner.dispatch_skills:
        if not key:
            continue
        if key == "di_exp_boost":
            mods["exp_mult"] = 1.0 + 0.10 * lvl
        elif key == "di_gold_boost":
            mods["gold_mult"] = 1.0 + 0.10 * lvl
        elif key == "di_skilling_boost":
            mods["skilling_mult"] = 1.0 + 0.10 * lvl
        elif key == "di_extra_reward":
            mods["extra_reward_chance"] = min(0.10, 0.05 + 0.01 * lvl)
        elif key == "di_settlement_mat":
            mods["settlement_mat_chance"] = min(0.10, 0.05 + 0.01 * lvl)
        elif key == "di_boss_reward":
            mods["boss_extra_chance"] = min(0.10, 0.05 + 0.01 * lvl)
        elif key == "di_contract_find":
            mods["contract_chance"] = min(0.10, 0.05 + 0.01 * lvl)
        elif key == "di_pinnacle_find":
            mods["pinnacle_chance"] = min(0.10, 0.05 + 0.01 * lvl)

    sig = partner.sig_dispatch_key
    slvl = partner.sig_dispatch_lvl
    if slvl >= 1:
        if sig == "sig_di_skol":
            mods["essence_chance"] = slvl / 100
        elif sig == "sig_di_eve":
            mods["spirit_stone_chance"] = slvl / 100
        elif sig == "sig_di_velour":
            mods["elemental_key_chance"] = slvl / 100
        elif sig == "sig_di_yvenn":
            mods["slayer_drop_chance"] = slvl / 100
        elif sig == "sig_di_flora":
            mods["flora_double_chance"] = _FLORA_DOUBLE_CHANCE.get(slvl, 0.0)

    return mods


# ===========================================================================
# Per-task reward rollers
# ===========================================================================

def _roll_combat(rolls: float, mods: Dict[str, Any]) -> Dict[str, Any]:
    """Rolls combat dispatch rewards for `rolls` reward rolls."""
    gold = 0
    exp = 0
    items: Dict[str, int] = {}

    for _ in range(int(rolls)):
        gold += int(random.randint(_COMBAT_GOLD_MIN, _COMBAT_GOLD_MAX) * mods["gold_mult"])
        exp += int(random.randint(_COMBAT_EXP_MIN, _COMBAT_EXP_MAX) * mods["exp_mult"])

        loot = random.choices(_COMBAT_LOOT_TYPES, weights=_COMBAT_LOOT_WEIGHTS, k=1)[0]
        if loot != "gold":
            items[loot] = items.get(loot, 0) + 1

        # di_extra_reward bonus item
        if random.random() < mods["extra_reward_chance"]:
            extra = random.choices(_COMBAT_LOOT_TYPES, weights=_COMBAT_LOOT_WEIGHTS, k=1)[0]
            if extra == "gold":
                gold += int(random.randint(_COMBAT_GOLD_MIN, _COMBAT_GOLD_MAX) * mods["gold_mult"])
            else:
                items[extra] = items.get(extra, 0) + 1

        if mods["settlement_mat_chance"] > 0 and random.random() < mods["settlement_mat_chance"]:
            mat = random.choice(["timber", "stone"])
            items[mat] = items.get(mat, 0) + 1

        if mods["contract_chance"] > 0 and random.random() < mods["contract_chance"]:
            items["guild_ticket"] = items.get("guild_ticket", 0) + 1

        if mods["pinnacle_chance"] > 0 and random.random() < mods["pinnacle_chance"]:
            drop = random.choice(["antique_tome", "pinnacle_key"])
            items[drop] = items.get(drop, 0) + 1

        if mods["essence_chance"] > 0 and random.random() < mods["essence_chance"]:
            items["essence"] = items.get("essence", 0) + 1

        if mods["spirit_stone_chance"] > 0 and random.random() < mods["spirit_stone_chance"]:
            items["spirit_stone"] = items.get("spirit_stone", 0) + 1

        if mods["elemental_key_chance"] > 0 and random.random() < mods["elemental_key_chance"]:
            ekey = random.choice(_BOSS_SIGILS)
            items[ekey] = items.get(ekey, 0) + 1

        if mods["slayer_drop_chance"] > 0 and random.random() < mods["slayer_drop_chance"]:
            items["slayer_drop"] = items.get("slayer_drop", 0) + 1

    return {"gold": gold, "exp": exp, "items": items}


def _roll_gathering(
    rolls: float,
    skill_tiers: Dict[str, str],
    mods: Dict[str, Any],
) -> Dict[str, Any]:
    """Rolls gathering dispatch rewards."""
    items: Dict[str, int] = {}

    for _ in range(int(rolls)):
        skill = random.choice(list(_GATHERING_SKILL_MAP.keys()))
        tier_table = _GATHERING_SKILL_MAP[skill]
        tool = skill_tiers.get(skill, list(tier_table.keys())[0])
        tier_data = tier_table.get(tool, list(tier_table.values())[0])

        material = random.choice(tier_data["materials"])
        qty_min, qty_max = tier_data["qty"]
        qty = int(random.randint(qty_min, qty_max) * mods["skilling_mult"])

        if mods["flora_double_chance"] > 0 and random.random() < mods["flora_double_chance"]:
            qty *= 2

        items[material] = items.get(material, 0) + qty

    return {"gold": 0, "exp": 0, "items": items}


def _roll_boss(rolls: float, mods: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rolls boss dispatch rewards.
    Each boss drop costs 4 full rolls (= 16 hours at standard rate).
    """
    boss_drops = floor(rolls / 4)
    items: Dict[str, int] = {}

    for _ in range(boss_drops):
        sigil = random.choice(_BOSS_SIGILS)
        items[sigil] = items.get(sigil, 0) + 1

        if mods["boss_extra_chance"] > 0 and random.random() < mods["boss_extra_chance"]:
            extra_sigil = random.choice(_BOSS_SIGILS)
            items[extra_sigil] = items.get(extra_sigil, 0) + 1

    return {"gold": 0, "exp": 0, "items": items}


# ===========================================================================
# Public API
# ===========================================================================

def calculate_rewards(
    partner: Partner,
    start_time_str: str,
    task_override: Optional[str] = None,
    skill_tiers: Optional[Dict[str, str]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Master dispatch reward calculator for a single task.

    Args:
        partner:         The dispatched Partner model.
        start_time_str:  ISO datetime string when dispatch began.
        task_override:   If provided, use this task type instead of partner.dispatch_task.
        skill_tiers:     {"mining": "iron", "fishing": "desiccated", "woodcutting": "flimsy"}.
                         Only needed for gathering tasks.
        now:             Override the current time (for testing).

    Returns dict with keys: gold, exp, items, rolls, hours_used.
    """
    if skill_tiers is None:
        skill_tiers = {}
    if now is None:
        now = _now_utc()

    task = task_override or partner.dispatch_task or "combat"
    rolls = reward_rolls(partner, start_time_str, now)
    cap = get_cap_hours(partner)
    hours_used = min(elapsed_hours(start_time_str, now), cap)
    mods = _extract_skill_modifiers(partner)

    if task == "combat":
        result = _roll_combat(rolls, mods)
    elif task == "gathering":
        result = _roll_gathering(rolls, skill_tiers, mods)
    elif task == "boss":
        result = _roll_boss(rolls, mods)
    else:
        result = {"gold": 0, "exp": 0, "items": {}}

    result["rolls"] = rolls
    result["hours_used"] = hours_used
    return result


def calculate_sigmund_rewards(
    partner: Partner,
    skill_tiers: Optional[Dict[str, str]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Calculates combined rewards for Sigmund's dual dispatch.
    Task 1 uses partner.dispatch_task / dispatch_start_time.
    Task 2 uses partner.dispatch_task_2 / dispatch_start_time_2, scaled by effectiveness.
    """
    if now is None:
        now = _now_utc()

    sig_lvl = partner.sig_dispatch_lvl
    effectiveness = _SIGMUND_EFFECTIVENESS.get(sig_lvl, 0.60)

    r1 = calculate_rewards(partner, partner.dispatch_start_time or "", None, skill_tiers, now)
    r2 = calculate_rewards(
        partner,
        partner.dispatch_start_time_2 or "",
        partner.dispatch_task_2,
        skill_tiers,
        now,
    )

    # Scale task 2 rewards by effectiveness
    r2_gold = int(r2["gold"] * effectiveness)
    r2_exp = int(r2["exp"] * effectiveness)
    r2_items = {
        k: max(1, int(v * effectiveness))
        for k, v in r2["items"].items()
        if int(v * effectiveness) >= 1
    }

    merged: Dict[str, int] = dict(r1["items"])
    for k, v in r2_items.items():
        merged[k] = merged.get(k, 0) + v

    return {
        "gold": r1["gold"] + r2_gold,
        "exp": r1["exp"] + r2_exp,
        "items": merged,
        "rolls": r1["rolls"] + r2["rolls"] * effectiveness,
        "hours_used": max(r1["hours_used"], r2["hours_used"]),
    }
