from __future__ import annotations

import json
import math
import os
import random
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Load exp table once at import time
# ---------------------------------------------------------------------------

_EXP_TABLE: dict = {}


def _load_exp() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "exp.json")
    with open(path, encoding="utf-8") as f:
        _EXP_TABLE.update(json.load(f)["levels"])


_load_exp()

# ---------------------------------------------------------------------------
# Skill key lists
# ---------------------------------------------------------------------------

COMMON_COMBAT_SKILLS: List[str] = [
    "co_joint_attack",
    "co_heal",
    "co_damage_reduction",
    "co_stat_transfer",
    "co_monster_debuff",
    "co_xp_boost",
    "co_gold_boost",
    "co_special_rarity",
    "co_atk_from_def",
    "co_def_from_atk",
    "co_curse_damage",
    "co_curse_taken",
]

RARE_COMBAT_SKILLS: List[str] = [
    "co_crit_rate",
    "co_crit_damage",
    "co_execute",
    "co_ward_regen",
    "co_ward_leech",
]

COMMON_DISPATCH_SKILLS: List[str] = [
    "di_exp_boost",
    "di_gold_boost",
    "di_extra_reward",
    "di_skilling_boost",
]

RARE_DISPATCH_SKILLS: List[str] = [
    "di_settlement_mat",
    "di_boss_reward",
    "di_contract_find",
    "di_pinnacle_find",
]

# Upgrade shard costs indexed by (current_level - 1)
COMBAT_UPGRADE_COSTS: List[int] = [3, 7, 10, 12, 15, 18, 20, 25, 30]  # lvl 1→2 … 9→10
DISPATCH_UPGRADE_COSTS: List[int] = [5, 10, 15, 30]  # lvl 1→2 … 4→5

REROLL_COMBAT_COST = 10
REROLL_DISPATCH_COST = 5

MAX_COMBAT_SKILL_LEVEL = 10
MAX_DISPATCH_SKILL_LEVEL = 5

# Affinity (encounter_threshold, story_index)
AFFINITY_THRESHOLDS: List[Tuple[int, int]] = [(25, 1), (50, 2), (75, 3), (100, 4)]

# Skol sig: corrupted essence buff counts per tier
_SKOL_SIG_BUFFS = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}

# Eve sig: potion cost per tier
_EVE_SIG_POTIONS = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}

# Kay sig dispatch: extra hours per tier
_KAY_DISPATCH_BONUS_HOURS = {1: 12, 2: 24, 3: 36, 4: 48, 5: 60}

# Flora sig dispatch: double chance per tier
_FLORA_DOUBLE_CHANCE = {1: 0.02, 2: 0.04, 3: 0.06, 4: 0.08, 5: 0.10}

# Sigmund sig dispatch: effectiveness per tier
_SIGMUND_EFFECTIVENESS = {1: 0.60, 2: 0.70, 3: 0.80, 4: 0.90, 5: 1.00}

# ---------------------------------------------------------------------------
# Partner class system
# ---------------------------------------------------------------------------

# Main classes (available at 4★)
ATTACKER_MAIN = frozenset({"Assault", "Caster", "Ranger"})
TANK_MAIN     = frozenset({"Frontline", "Warden", "Aegis"})
HEALER_MAIN   = frozenset({"Herbalist", "Druid", "Cleric"})

# Hybrid classes (available at 5★/6★) — fill two roles each
HYBRID_CLASSES = frozenset({"Vanguard", "Paladin", "Battlemage"})

# Full slot eligibility sets (main + compatible hybrids)
ATTACKER_CLASSES = ATTACKER_MAIN | {"Vanguard", "Battlemage"}
TANK_CLASSES     = TANK_MAIN     | {"Vanguard", "Paladin"}
HEALER_CLASSES   = HEALER_MAIN   | {"Paladin", "Battlemage"}

_SLOT_SETS = {
    "attacker": ATTACKER_CLASSES,
    "tank":     TANK_CLASSES,
    "healer":   HEALER_CLASSES,
}

# Human-readable slot labels
SLOT_LABELS = {
    "attacker": "⚔️ Attacker",
    "tank":     "🛡️ Tank",
    "healer":   "💚 Healer",
}

# Human-readable class labels with role hints
CLASS_ROLE_HINT = {
    "Assault":    "Attacker",
    "Caster":     "Attacker",
    "Ranger":     "Attacker",
    "Frontline":  "Tank",
    "Warden":     "Tank",
    "Aegis":      "Tank",
    "Herbalist":  "Healer",
    "Druid":      "Healer",
    "Cleric":     "Healer",
    "Vanguard":   "Attacker / Tank",
    "Paladin":    "Healer / Tank",
    "Battlemage": "Attacker / Healer",
}


def can_fill_slot(partner_class: str, slot: str) -> bool:
    """Returns True if the given partner class is eligible for the given slot."""
    return partner_class in _SLOT_SETS.get(slot, frozenset())


# ===========================================================================
# Gacha
# ===========================================================================

_BASE_RATE_6 = 0.01
_BASE_RATE_5 = 0.11
_SOFT_PITY_START = 60
_SOFT_PITY_INCREMENT = 0.001  # +0.1% per pull above threshold
_HARD_PITY = 100


def _rate_6(pity: int) -> float:
    if pity < _SOFT_PITY_START:
        return _BASE_RATE_6
    bonus = (pity - _SOFT_PITY_START) * _SOFT_PITY_INCREMENT
    return min(1.0, _BASE_RATE_6 + bonus)


def roll_single(pity: int) -> Tuple[int, int]:
    """Roll one pull. Returns (rarity, new_pity_counter)."""
    new_pity = pity + 1
    if new_pity >= _HARD_PITY:
        return 6, 0
    r6 = _rate_6(new_pity)
    roll = random.random()
    if roll < r6:
        return 6, 0
    if roll < r6 + _BASE_RATE_5:
        return 5, new_pity
    return 4, new_pity


def roll_ten(pity: int) -> Tuple[List[int], int]:
    """
    10-pull. Guarantees at least one 5★+.
    If none of the first 9 rolls yield 5★+, the 10th is forced to 5★
    (pity for 6★ is still checked independently on the forced roll).
    Returns (rarity_list, final_pity_counter).
    """
    results: List[int] = []
    current_pity = pity
    has_five_plus = False

    for i in range(10):
        rarity, current_pity = roll_single(current_pity)
        results.append(rarity)
        if rarity >= 5:
            has_five_plus = True

    if not has_five_plus:
        # Force the 10th pull to at least 5★; pity still checked for 6★
        forced = 6 if random.random() < _rate_6(current_pity) else 5
        if forced == 6:
            current_pity = 0
        results[-1] = forced

    return results, current_pity


# ===========================================================================
# Skill generation
# ===========================================================================


def _roll_skill_excluding(skill_type: str, rarity: int, excluded: List[str]) -> str:
    """Roll a single skill key while avoiding already-used skills on this partner."""
    if skill_type == "combat":
        common_pool = COMMON_COMBAT_SKILLS
        rare_pool = RARE_COMBAT_SKILLS
    else:  # dispatch
        common_pool = COMMON_DISPATCH_SKILLS
        rare_pool = RARE_DISPATCH_SKILLS

    # Filter out any skills already present on this partner
    available_common = [s for s in common_pool if s not in excluded]
    available_rare = [s for s in rare_pool if s not in excluded] if rarity >= 5 else []

    # Rare skills still have 20% chance (only if any are still available)
    if available_rare and random.random() < 0.20:
        return random.choice(available_rare)

    # Fall back to common skills
    if available_common:
        return random.choice(available_common)

    # Extremely rare fallback (should almost never happen)
    return random.choice(common_pool)


def generate_skill_slots(rarity: int, skill_type: str) -> List[Optional[str]]:
    """
    Returns a list of exactly 3 skill keys (with None padding for unused slots).
    4★ = 1 skill, 5★ = 2 skills, 6★ = 3 skills.
    Guarantees no duplicate skills within the same type.
    """
    num_slots = rarity - 3  # 1 for 4★, 2 for 5★, 3 for 6★
    slots: List[Optional[str]] = []
    used: set[str] = set()

    for _ in range(num_slots):
        skill = _roll_skill_excluding(skill_type, rarity, list(used))
        slots.append(skill)
        used.add(skill)

    # Pad to exactly 3 slots (the rest stay None)
    while len(slots) < 3:
        slots.append(None)

    return slots


def reroll_skill(
    skill_type: str, rarity: int, current_slots: List[Optional[str]]
) -> str:
    """
    Reroll a single skill slot while avoiding any skills already present
    in the other slots of the same type on this partner.
    """
    used = {s for s in current_slots if s is not None}
    return _roll_skill_excluding(skill_type, rarity, list(used))


# ===========================================================================
# Upgrade costs
# ===========================================================================


def get_combat_upgrade_cost(current_level: int) -> Optional[int]:
    """Shard cost to level a combat skill from current_level to current_level+1."""
    if current_level >= MAX_COMBAT_SKILL_LEVEL:
        return None
    return COMBAT_UPGRADE_COSTS[current_level - 1]


def get_dispatch_upgrade_cost(current_level: int) -> Optional[int]:
    if current_level >= MAX_DISPATCH_SKILL_LEVEL:
        return None
    return DISPATCH_UPGRADE_COSTS[current_level - 1]


# ===========================================================================
# Effect text
# ===========================================================================


def get_skill_effect_text(key: str, level: int) -> str:
    """Human-readable passive description at a given level (1–10 for combat, 1–5 for dispatch)."""
    L = level
    _texts = {
        # --- Common combat ---
        "co_joint_attack": f"{L * 10}% chance to attack alongside you",
        "co_heal": f"Heals you for {L}% max HP every 3 turns",
        "co_damage_reduction": f"{L * 5}% chance to halve damage taken",
        "co_stat_transfer": f"On combat start, add {L * 10}% of partner's stats to your base stats",
        "co_monster_debuff": f"On combat start, reduce monster ATK and DEF by {L * 2}%",
        "co_xp_boost": f"+{L * 5}% XP from combat",
        "co_gold_boost": f"+{L * 5}% gold from combat",
        "co_special_rarity": f"+{L * 0.1:.1f}% special rarity",
        "co_atk_from_def": f"Your base ATK gains {L * 25}% of partner DEF",
        "co_def_from_atk": f"Your base DEF gains {L * 20}% of partner ATK",
        "co_curse_damage": f"Curses the monster, it deals {L * 2}% less damage",
        "co_curse_taken": f"Curses the monster, it takes {L * 2}% more damage",
        # --- Rare combat ---
        "co_crit_rate": f"+{L}% critical strike chance",
        "co_crit_damage": f"+{L * 10}% critical strike multiplier",
        "co_execute": f"Culls the monster at {L}% HP",
        "co_ward_regen": f"Generate {L * 10} ward per turn to the player",
        "co_ward_leech": f"{L * 0.1:.1f}% of damage dealt by the player is restored as ward",
        # --- Common dispatch ---
        "di_exp_boost": f"+{L * 10}% EXP during combat dispatch",
        "di_gold_boost": f"+{L * 10}% gold during combat dispatch",
        "di_extra_reward": f"+{L}% bonus rewards from combat dispatch ({5 + L}% total)",
        "di_skilling_boost": f"+{L * 10}% materials from gathering dispatch",
        # --- Rare dispatch ---
        "di_settlement_mat": f"In combat dispatch, +{L}% chance to find a settlement material)",
        "di_boss_reward": f"In Boss dispatch, +{L}% chance for an extra reward)",
        "di_contract_find": f"In combat dispatch, +{L}% chance to find a Guild Ticket)",
        "di_pinnacle_find": f"In combat dispatch, +{L}% chance to find a pinnacle item)",
    }
    return _texts.get(key, f"{key} Lv.{L}")


def get_sig_combat_effect_text(partner_id: int, tier: int) -> str:
    if tier < 1 or tier > 5:
        return "???"
    T = tier
    if partner_id == 1:  # Skol
        n = _SKOL_SIG_BUFFS[T]
        return f"Gain {n} random corrupted essence buff(s) at combat start"
    if partner_id == 2:  # Eve
        p = _EVE_SIG_POTIONS[T]
        return f"Survive a fatal hit by consuming {p} potion(s)"
    if partner_id == 3:  # Kay
        return f"{T * 5}% chance to obtain an extra curio after combat"
    if partner_id == 4:  # Sigmund
        return f"{T * 2}% chance to double your damage on a hit"
    if partner_id == 5:  # Velour
        return f"{T * 2}% chance to double all special rarity drops"
    if partner_id == 6:  # Flora
        return f"Convert {T * 10}% of monster gold drops into skilling materials"
    if partner_id == 7:  # Yvenn
        return (
            f"All monsters count as task monsters; +{T} bonus slayer progress per kill"
        )
    return "???"


def get_sig_dispatch_effect_text(partner_id: int, tier: int) -> str:
    if tier < 1 or tier > 5:
        return "???"
    T = tier
    if partner_id == 1:  # Skol
        return f"In combat dispatch, +{T}% chance to find an essence"
    if partner_id == 2:  # Eve
        return f"In combat dispatch, +{T}% chance to find a spirit stone"
    if partner_id == 3:  # Kay
        bonus = _KAY_DISPATCH_BONUS_HOURS[T]
        return f"Accumulate up to {48 + bonus}h of rewards"
    if partner_id == 4:  # Sigmund
        pct = int(_SIGMUND_EFFECTIVENESS[T] * 100)
        return (
            f"Assignable to two dispatch tasks simultaneously at {pct}% effectiveness"
        )
    if partner_id == 5:  # Velour
        return f"In combat dispatch, +{T}% chance to find an elemental key"
    if partner_id == 6:  # Flora
        pct = int(_FLORA_DOUBLE_CHANCE[T] * 100)
        return f"{pct}% chance to double gathering dispatch materials earned"
    if partner_id == 7:  # Yvenn
        return f"In combat dispatch, +{T}% chance to find a slayer drop"
    return "???"


# ===========================================================================
# XP & leveling
# ===========================================================================

MAX_LEVEL = 100


def xp_threshold(level: int) -> int:
    """XP needed to advance from `level` to `level + 1`."""
    if level >= MAX_LEVEL:
        return 0
    return math.floor(int(_EXP_TABLE.get(str(level), 999_999)) * 0.1)


def grant_xp(
    current_level: int, current_exp: int, xp_gained: int
) -> Tuple[int, int, List[str]]:
    """
    Apply xp_gained to a partner.
    Returns (new_level, new_exp, level_up_messages).
    XP and level-ups are suppressed at MAX_LEVEL.
    """
    if current_level >= MAX_LEVEL:
        return current_level, 0, []

    msgs: List[str] = []
    level = current_level
    exp = current_exp + xp_gained

    while level < MAX_LEVEL:
        threshold = xp_threshold(level)
        if threshold <= 0 or exp < threshold:
            break
        exp -= threshold
        level += 1
        msgs.append(f"Partner reached level **{level}**!")

    if level >= MAX_LEVEL:
        exp = 0

    return level, exp, msgs


# ===========================================================================
# Affinity helpers
# ===========================================================================


def next_available_story(
    affinity_encounters: int, affinity_story_seen: int
) -> Optional[int]:
    """
    Returns the index of the next story the player can read, or None.
    Stories must be read in order.
    """
    for threshold, story_idx in AFFINITY_THRESHOLDS:
        if affinity_encounters >= threshold and affinity_story_seen < story_idx:
            return story_idx
    return None


def portrait_unlocked(affinity_encounters: int, affinity_story_seen: int) -> bool:
    return affinity_encounters >= 100 and affinity_story_seen >= 4
