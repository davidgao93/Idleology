"""
Pure logic for the Paradise Jewel system — no I/O, no Discord, no DB calls.
"""

import random
from typing import Optional

from .data import (
    SKILL_JEWELS,
    PASSIVES,
    REROLL_TYPE_POOL,
    PASSIVE_SLOT_THRESHOLDS,
    PASSIVE_SLOT_COSTS,
    DUST_REROLL_TYPE,
    DUST_REROLL_VALUE,
    DUST_FROM_JEWEL_BASE,
    SkillJewelDef,
    PassiveDef,
)


# ---------------------------------------------------------------------------
# Thresholds & levels
# ---------------------------------------------------------------------------

def get_threshold(skill_key: str, effective_level: int) -> int:
    """Return the charge threshold for a skill at a given effective level."""
    defn = SKILL_JEWELS[skill_key]
    if effective_level >= 30:
        base = defn.threshold_lv30
    elif effective_level >= 20:
        # Interpolate between lv20 and lv30
        t = (effective_level - 20) / 10
        base = round(defn.threshold_lv20 - t * (defn.threshold_lv20 - defn.threshold_lv30))
    else:
        # Interpolate between lv1 and lv20
        t = max(0, (effective_level - 1)) / 19
        base = round(defn.threshold_lv1 - t * (defn.threshold_lv1 - defn.threshold_lv20))
    return max(1, base)


def get_effective_level(skill_key: str, data: dict, passive_modifier: int = 0) -> int:
    """Return natural level + Mastery passive bonus (capped at 30)."""
    natural = data["skill_levels"].get(skill_key, 0)
    return min(30, natural + passive_modifier)


# ---------------------------------------------------------------------------
# Passive helpers
# ---------------------------------------------------------------------------

def _passive_modifier(value: float) -> float:
    """Scale a passive value to 0..1 range within its definition's min/max."""
    return value  # raw value is stored and used directly; helpers read it as-is


def get_passive_value(data: dict, passive_type: str) -> float:
    """Sum all stacked values for a given passive type across all slots."""
    return sum(
        slot["value"]
        for slot in data.get("passive_slots", [])
        if slot.get("type") == passive_type
    )


def get_passive_slot_count(data: dict) -> int:
    """Number of passive slots unlocked from total invested jewels."""
    invested = data.get("passive_jewels_invested", 0)
    count = 0
    for threshold in PASSIVE_SLOT_THRESHOLDS:
        if invested >= threshold:
            count += 1
    return count


def jewels_to_next_slot(data: dict) -> Optional[int]:
    """How many jewels must still be invested to unlock the next passive slot."""
    invested = data.get("passive_jewels_invested", 0)
    for threshold in PASSIVE_SLOT_THRESHOLDS:
        if invested < threshold:
            return threshold - invested
    return None  # all 5 slots unlocked


def mastery_bonus(data: dict) -> int:
    """Total Mastery passive level bonus (rounded down)."""
    return int(get_passive_value(data, "mastery"))


# ---------------------------------------------------------------------------
# Combat passive reading helpers
# ---------------------------------------------------------------------------

def get_compression_bonus(data: dict) -> int:
    """Total threshold reduction from Compression passives (floor 0 for the bonus)."""
    return int(get_passive_value(data, "compression"))


def get_rapid_pct(data: dict) -> float:
    """% chance to gain +1 extra charge from Rapid passives."""
    return get_passive_value(data, "rapid")


def get_force_pct(data: dict) -> float:
    """% unleash strength bonus from Force passives."""
    return get_passive_value(data, "force")


def get_mirage_pct(data: dict) -> float:
    """% double-proc chance from Mirage passives."""
    return get_passive_value(data, "mirage")


def get_lingering_pct(data: dict) -> float:
    """% chance to retain charges after unleash from Lingering passives."""
    return get_passive_value(data, "lingering")


def get_fury_pct(data: dict) -> float:
    """% damage bonus on damage unleashes from Fury passives."""
    return get_passive_value(data, "fury")


def get_arcane_pct(data: dict) -> float:
    """% ward bonus on ward-generating unleashes."""
    return get_passive_value(data, "arcane")


def get_sustenance_pct(data: dict) -> float:
    """% healing bonus on healing unleashes."""
    return get_passive_value(data, "sustenance")


def get_spec_pct(data: dict, skill_key: str) -> float:
    """% specialization bonus for a specific skill."""
    return get_passive_value(data, f"spec_{skill_key}")


def get_fortune_pct(data: dict) -> float:
    """% chance to duplicate a found Paradise Jewel."""
    return get_passive_value(data, "fortune")


# ---------------------------------------------------------------------------
# Charge system
# ---------------------------------------------------------------------------

def add_charge(data: dict, skill_key: str, amount: int = 1) -> tuple[bool, int]:
    """
    Adds charge(s) to the equipped skill.  Applies Rapid passive for extra charges.
    Returns (unleashed, charges_after) where unleashed is True if threshold was hit.
    Modifies data in-place.
    """
    if data.get("equipped_skill") != skill_key:
        return False, data["skill_charges"].get(skill_key, 0)

    rapid_pct = get_rapid_pct(data)
    extra = 0
    for _ in range(amount):
        if rapid_pct > 0 and random.random() < rapid_pct / 100:
            extra += 1

    total_gain = amount + extra
    current = data["skill_charges"].get(skill_key, 0) + total_gain
    data["skill_charges"][skill_key] = current

    mastery_lvl = mastery_bonus(data)
    eff_level = get_effective_level(skill_key, data, mastery_lvl)
    compression = get_compression_bonus(data)
    threshold = max(1, get_threshold(skill_key, eff_level) - compression)

    if current >= threshold:
        return True, current
    return False, current


def consume_charges(data: dict, skill_key: str) -> int:
    """
    Resets charges after an unleash, applying Lingering passive.
    Returns the charges kept.
    """
    lingering_pct = get_lingering_pct(data)
    kept = 0
    if lingering_pct > 0 and random.random() < lingering_pct / 100:
        kept = random.randint(1, 5)

    data["skill_charges"][skill_key] = kept
    return kept


def should_double_proc(data: dict) -> bool:
    """Returns True if Mirage passive triggers a second unleash."""
    mirage_pct = get_mirage_pct(data)
    if mirage_pct <= 0:
        return False
    return random.random() < mirage_pct / 100


# ---------------------------------------------------------------------------
# Skill leveling
# ---------------------------------------------------------------------------

# Progress needed per level (levels 1-20 natural cap, passives can exceed 20)
_COMBATS_PER_LEVEL = 5  # 5 combat wins per level → 100 combats to reach level 20

def add_skill_progress(data: dict, skill_key: str) -> bool:
    """
    Called after a won combat when skill_key is equipped.
    Returns True if the skill leveled up.
    """
    levels = data.setdefault("skill_levels", {})
    current_level = levels.get(skill_key, 0)
    if current_level >= 20:
        return False  # natural cap

    savant_pct = get_passive_value(data, "savant")
    effective_chance = 1.0 + savant_pct / 100

    # Each combat: one progress roll per effective_chance (fractional = extra roll chance)
    full_rolls = int(effective_chance)
    extra_pct = effective_chance - full_rolls

    leveled = False
    for _ in range(full_rolls):
        if random.random() < 1 / _COMBATS_PER_LEVEL:
            levels[skill_key] = current_level + 1
            leveled = True
            break
    if not leveled and extra_pct > 0 and random.random() < extra_pct / _COMBATS_PER_LEVEL:
        levels[skill_key] = current_level + 1
        leveled = True

    return leveled


# ---------------------------------------------------------------------------
# Passive rolling
# ---------------------------------------------------------------------------

def _skewed_roll(min_val: float, max_val: float) -> float:
    """
    Weighted roll heavily skewed toward lower values.
    ~60% of rolls fall in the bottom 40% of the range.
    """
    r = random.random()
    # beta-like skew: cube root pushes values toward 0
    biased = r ** 3
    return round(min_val + biased * (max_val - min_val), 1)


def roll_passive_type() -> str:
    """Randomly pick a passive type from the weighted pool."""
    return random.choice(REROLL_TYPE_POOL)


def roll_passive_value(passive_key: str) -> float:
    """Roll a skewed value for a passive type."""
    defn = PASSIVES[passive_key]
    return _skewed_roll(defn.min_value, defn.max_value)


def roll_new_passive() -> dict:
    """Returns a new {'type': ..., 'value': ...} passive dict."""
    p_type = roll_passive_type()
    return {"type": p_type, "value": roll_passive_value(p_type)}


# ---------------------------------------------------------------------------
# Jewel consumption
# ---------------------------------------------------------------------------

def can_consume_jewel(data: dict) -> bool:
    """True if there is something useful the player can do with a jewel."""
    skills_unlocked = len(data.get("unlocked_skills", []))
    passive_count = get_passive_slot_count(data)
    # Can unlock more skills (up to 8 total), or invest in passive slots (up to 5)
    return skills_unlocked < len(SKILL_JEWELS) or passive_count < 5


def consume_jewel_unlock_skill(data: dict, skill_key: str) -> str | None:
    """
    Unlocks a skill using one Jewel of Paradise.
    Returns an error message string on failure, or None on success.
    Modifies data in-place; caller must update DB (decrement paradise_jewels, save data).
    """
    if skill_key not in SKILL_JEWELS:
        return "Unknown skill."
    if skill_key in data.get("unlocked_skills", []):
        return "That skill is already unlocked."
    data.setdefault("unlocked_skills", []).append(skill_key)
    data["total_jewels_consumed"] = data.get("total_jewels_consumed", 0) + 1
    # Auto-equip first skill
    if data.get("equipped_skill") is None:
        data["equipped_skill"] = skill_key
        data.setdefault("skill_charges", {})[skill_key] = 0
        data.setdefault("skill_levels", {})[skill_key] = 0
    elif skill_key not in data.get("skill_levels", {}):
        data.setdefault("skill_levels", {})[skill_key] = 0
        data.setdefault("skill_charges", {})[skill_key] = 0
    return None


def consume_jewel_invest_passive(data: dict) -> tuple[bool, str]:
    """
    Invests one Jewel of Paradise toward the next passive slot.
    Returns (slot_unlocked, message).
    Modifies data in-place.
    """
    passive_count = get_passive_slot_count(data)
    if passive_count >= 5:
        return False, "All passive slots are already unlocked."
    data["passive_jewels_invested"] = data.get("passive_jewels_invested", 0) + 1
    data["total_jewels_consumed"] = data.get("total_jewels_consumed", 0) + 1

    new_count = get_passive_slot_count(data)
    if new_count > passive_count:
        # A new slot opened — roll a random passive for it
        new_passive = roll_new_passive()
        data.setdefault("passive_slots", []).append(new_passive)
        return True, f"Passive slot {new_count} unlocked! Rolled **{PASSIVES[new_passive['type']].name}** ({_format_passive_value(new_passive)})."
    needed = jewels_to_next_slot(data)
    return False, f"Invested. {needed} more jewel(s) needed for the next slot."


def _format_passive_value(slot: dict) -> str:
    defn = PASSIVES.get(slot["type"])
    if defn is None:
        return str(slot["value"])
    val = slot["value"]
    return f"{val}%" if defn.is_percent else str(val)


# ---------------------------------------------------------------------------
# Cosmic Dust rerolls
# ---------------------------------------------------------------------------

def dust_from_jewel(alchemy_level: int = 1) -> int:
    """Cosmic Dust awarded for dusting a Jewel of Paradise."""
    bonus = 1 + (alchemy_level - 1) * 0.05
    return int(DUST_FROM_JEWEL_BASE * bonus)


def reroll_passive_type(data: dict, slot_index: int) -> tuple[bool, str, int]:
    """
    Reroll the TYPE of the passive in the given slot.
    Returns (success, message, dust_cost).
    """
    cost = DUST_REROLL_TYPE
    slots = data.get("passive_slots", [])
    if slot_index < 0 or slot_index >= len(slots):
        return False, "Invalid slot.", cost
    old_type = slots[slot_index]["type"]
    new_type = roll_passive_type()
    # Re-roll until different type (cap at 10 attempts)
    for _ in range(10):
        if new_type != old_type:
            break
        new_type = roll_passive_type()
    new_value = roll_passive_value(new_type)
    slots[slot_index] = {"type": new_type, "value": new_value}
    name = PASSIVES[new_type].name
    val_str = _format_passive_value(slots[slot_index])
    return True, f"Rerolled to **{name}** ({val_str}).", cost


def reroll_passive_value(data: dict, slot_index: int) -> tuple[bool, str, int]:
    """
    Reroll only the VALUE of the passive in the given slot.
    Returns (success, message, dust_cost).
    """
    cost = DUST_REROLL_VALUE
    slots = data.get("passive_slots", [])
    if slot_index < 0 or slot_index >= len(slots):
        return False, "Invalid slot.", cost
    p_type = slots[slot_index]["type"]
    new_value = roll_passive_value(p_type)
    slots[slot_index]["value"] = new_value
    val_str = _format_passive_value(slots[slot_index])
    return True, f"Rerolled value to **{val_str}**.", cost


# ---------------------------------------------------------------------------
# Unleash scale helpers
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


def _scale_t(level: int) -> float:
    """0..1 scale based on level (1→0, 20→~0.95, 30→1)."""
    if level <= 1:
        return 0.0
    if level >= 30:
        return 1.0
    if level <= 20:
        return (level - 1) / 29
    return 0.5 + (level - 20) / 20


def scale_damage_pct(skill_key: str, level: int, which: str = "high") -> float:
    """
    Returns scaled damage % for a skill at a given level.
    which = 'low' or 'high'.
    Curves are per-skill as defined in the design doc.
    """
    # Pre-defined per-skill low/high at lv1, lv20, lv30+
    _dmg_table = {
        #          (low_lv1, high_lv1, low_lv20, high_lv20, low_lv30, high_lv30)
        "surge":   (5, 8, 100, 180, 200, 380),
        "cataclysm": (50, 50, 150, 150, 250, 250),  # single value (bonus crit multi %)
        "acrimony": (40, 80, 150, 250, 300, 450),
        "bastion": (200, 400, 600, 1000, 1200, 1800),
        "onslaught": (60, 120, 200, 350, 400, 600),  # ATK multiplier %
    }
    _ward_table = {
        "wardforge": (80, 150, 400, 700, 800, 1200),
    }
    _heal_table = {
        "siphon": (30, 60, 40, 80, 50, 100),  # % of max HP
    }

    if skill_key in _dmg_table:
        row = _dmg_table[skill_key]
    elif skill_key in _ward_table:
        row = _ward_table[skill_key]
    elif skill_key in _heal_table:
        row = _heal_table[skill_key]
    else:
        return 0.0

    low_lv1, high_lv1, low_lv20, high_lv20, low_lv30, high_lv30 = row
    if level <= 1:
        low, high = low_lv1, high_lv1
    elif level >= 30:
        low, high = low_lv30, high_lv30
    elif level <= 20:
        t = (level - 1) / 19
        low = _lerp(low_lv1, low_lv20, t)
        high = _lerp(high_lv1, high_lv20, t)
    else:
        t = (level - 20) / 10
        low = _lerp(low_lv20, low_lv30, t)
        high = _lerp(high_lv20, high_lv30, t)

    return high if which == "high" else low


def roll_scale_pct(skill_key: str, level: int) -> float:
    """Roll a random value between low and high for the skill at this level."""
    low = scale_damage_pct(skill_key, level, "low")
    high = scale_damage_pct(skill_key, level, "high")
    return random.uniform(low, high)


# ---------------------------------------------------------------------------
# Draught: potion generation table
# ---------------------------------------------------------------------------

def draught_potion_range(level: int) -> tuple[int, int]:
    if level >= 30:
        return 0, 3
    elif level >= 20:
        return 0, 2
    else:
        return 0, 1


# ---------------------------------------------------------------------------
# Format helpers (for UI)
# ---------------------------------------------------------------------------

def format_passive_slot(slot: dict) -> str:
    """Returns a short string like 'Force (28.4%)'."""
    defn = PASSIVES.get(slot.get("type", ""))
    if defn is None:
        return "Unknown"
    return f"{defn.name} ({_format_passive_value(slot)})"


def format_passive_description(slot: dict) -> str:
    """Returns the full description with the rolled value substituted."""
    defn = PASSIVES.get(slot.get("type", ""))
    if defn is None:
        return "Unknown passive."
    val = slot["value"]
    display = f"{val:.1f}%" if defn.is_percent else f"{val:.0f}"
    return defn.description_template.replace("{value}", display)
