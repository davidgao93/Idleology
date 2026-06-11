"""
Essence application logic — pure functions, no I/O.

Terminology:
  Regular slot  — one of the three numbered essence slots (essence_1/2/3)
  Corrupted slot — the single corrupted_essence column (different mechanics)
  Utility essence — cleansing / chaos / annulment; consumed immediately, never stored as a slot
"""

import random
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Value ranges for regular essences — (min, max) stored as float
# ---------------------------------------------------------------------------
ESSENCE_VALUE_RANGES: dict[str, tuple[float, float]] = {
    "power": (20.0, 100.0),  # % of item's main attribute
    "protection": (20.0, 80.0),  # % of item's existing PDR / FDR
    "insight": (1.0, 8.0),  # flat crit chance added
    "evasion": (1.0, 8.0),  # flat evasion added
    "blocking": (1.0, 8.0),  # flat block added
    "deftness": (0.1, 0.5),  # additive crit multiplier bonus
    "precision": (1.0, 8.0),  # flat hit chance % added
    "gluttony": (1.0, 8.0),  # % max HP bonus
}

REGULAR_ESSENCE_TYPES = set(ESSENCE_VALUE_RANGES.keys())
UTILITY_ESSENCE_TYPES = {"cleansing", "chaos", "annulment"}
CORRUPTED_ESSENCE_TYPES = {"aphrodite", "lucifer", "gemini", "neet"}


# ---------------------------------------------------------------------------
# Slot helpers
# ---------------------------------------------------------------------------


def get_essence_slots(item) -> List[Tuple[int, str, float]]:
    """
    Returns a list of occupied regular essence slots as (slot_index, type, value).
    slot_index is 1-based. Empty / 'none' slots are omitted.
    """
    slots = []
    for i in (1, 2, 3):
        t = getattr(item, f"essence_{i}", "none") or "none"
        v = getattr(item, f"essence_{i}_val", 0.0) or 0.0
        if t != "none":
            slots.append((i, t, float(v)))
    return slots


def next_open_slot(item) -> Optional[int]:
    """Returns the index (1-3) of the first empty regular slot, or None if full."""
    for i in (1, 2, 3):
        t = getattr(item, f"essence_{i}", "none") or "none"
        if t == "none":
            return i
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def can_apply_essence(item, essence_type: str) -> Tuple[bool, str]:
    """
    Determines whether an essence can be applied to the item.
    Returns (True, "") on success, or (False, reason_string) on failure.

    Corrupted and utility essences have distinct validation paths.
    """
    if essence_type in UTILITY_ESSENCE_TYPES:
        # Utility essences are consumed directly — they are never 'applied' as a slot.
        return False, "Utility essences are consumed directly, not applied to a slot."

    if essence_type in CORRUPTED_ESSENCE_TYPES:
        current = getattr(item, "corrupted_essence", "none") or "none"
        if current != "none":
            return False, "This item already has a Corrupted Essence applied."
        return True, ""

    # Regular essence
    if essence_type not in REGULAR_ESSENCE_TYPES:
        return False, f"Unknown essence type: '{essence_type}'."

    slots = get_essence_slots(item)
    if len(slots) >= 3:
        return False, "This item already has **3** essence slots filled."

    existing_types = {t for _, t, _ in slots}
    if essence_type in existing_types:
        return False, "This item already has an essence of that type applied."

    return True, ""


def can_apply_utility(item, utility_type: str) -> Tuple[bool, str]:
    """
    Validates a utility essence (cleansing / chaos / annulment) against the item.
    """
    if utility_type not in UTILITY_ESSENCE_TYPES:
        return False, f"'{utility_type}' is not a utility essence."

    slots = get_essence_slots(item)

    if utility_type == "cleansing":
        if not slots:
            return False, "This item has no essence slots to cleanse."
        return True, ""

    if utility_type == "chaos":
        if not slots:
            return False, "This item has no essence values to reroll."
        return True, ""

    if utility_type == "annulment":
        if not slots:
            return False, "This item has no essence slots to remove."
        return True, ""

    return True, ""


# ---------------------------------------------------------------------------
# Value rolling
# ---------------------------------------------------------------------------


def roll_essence_value(essence_type: str) -> float:
    """Rolls a value in the defined range, weighted toward the lower end.
    Squaring a uniform sample gives ~5% probability in the top 10% of the range."""
    r = ESSENCE_VALUE_RANGES.get(essence_type)
    if not r:
        return 0.0
    lo, hi = r
    t = random.random() ** 2
    raw = lo + t * (hi - lo)
    if essence_type in ("insight", "evasion", "blocking", "precision", "gluttony"):
        return float(round(raw))
    if essence_type == "deftness":
        return round(raw, 2)
    return round(raw, 1)


def reroll_all_values(slots: List[Tuple[int, str, float]]) -> List[float]:
    """
    Given a list of occupied slots, returns new rolled values in the same order.
    Used by Essence of Chaos.
    """
    return [roll_essence_value(essence_type) for _, essence_type, _ in slots]


# ---------------------------------------------------------------------------
# Stat bonus computation  (no I/O — reads item fields directly)
# ---------------------------------------------------------------------------


def compute_essence_stat_bonus(item) -> dict:
    """
    Returns a dict of flat stat bonuses contributed by all regular essence slots.

    Keys:
      attack     — flat attack bonus
      defence    — flat defence bonus
      ward       — additional ward percentage points (same unit as item.ward)
      pdr        — additional physical damage reduction %
      fdr        — additional flat damage reduction
      crit       — flat crit chance bonus
      evasion    — flat evasion (same unit as armor.evasion)
      block      — flat block (same unit as armor.block)
      crit_multi — additive crit multiplier bonus (Deftness)
      hit_pct    — flat hit chance bonus in % points (Precision)
      max_hp_pct — % bonus to max HP (Gluttony)
    """
    bonus = {
        "attack": 0,
        "defence": 0,
        "ward": 0,
        "pdr": 0,
        "fdr": 0,
        "crit": 0,
        "evasion": 0,
        "block": 0,
        "crit_multi": 0.0,
        "hit_pct": 0,
        "max_hp_pct": 0,
    }

    for _, essence_type, value in get_essence_slots(item):
        if essence_type == "power":
            if getattr(item, "attack", None) is not None:
                # Glove / Boot — exactly one of ATK/DEF/WARD is non-zero (the main stat)
                atk = item.attack or 0
                def_ = item.defence or 0
                ward = item.ward or 0
                if atk > 0:
                    bonus["attack"] += int(atk * value / 100)
                elif def_ > 0:
                    bonus["defence"] += int(def_ * value / 100)
                elif ward > 0:
                    bonus["ward"] += int(ward * value / 100)
            else:
                # Helmet — no attack field; boost all non-zero stats (DEF and/or WARD)
                def_ = getattr(item, "defence", 0) or 0
                ward = getattr(item, "ward", 0) or 0
                if def_ > 0:
                    bonus["defence"] += int(def_ * value / 100)
                if ward > 0:
                    bonus["ward"] += int(ward * value / 100)

        elif essence_type == "protection":
            # Amplifies existing PDR and FDR on the item
            bonus["pdr"] += int(item.pdr * value / 100)
            bonus["fdr"] += int(item.fdr * value / 100)

        elif essence_type == "insight":
            bonus["crit"] += int(value)

        elif essence_type == "evasion":
            bonus["evasion"] += int(value)

        elif essence_type == "blocking":
            bonus["block"] += int(value)

        elif essence_type == "deftness":
            bonus["crit_multi"] += value

        elif essence_type == "precision":
            bonus["hit_pct"] += int(value)

        elif essence_type == "gluttony":
            bonus["max_hp_pct"] += int(value)

    return bonus
