"""
Essence application logic — pure functions, no I/O.

Terminology:
  Regular slot  — one of the three numbered essence slots (essence_1/2/3)
  Corrupted slot — the single corrupted_essence column (different mechanics)
  Utility essence — cleansing / chaos / annulment; consumed immediately, never stored as a slot
"""

import random
from typing import List, Tuple, Optional

# ---------------------------------------------------------------------------
# Value ranges for regular essences — (min, max) stored as float
# ---------------------------------------------------------------------------
ESSENCE_VALUE_RANGES: dict[str, tuple[float, float]] = {
    "power":      (20.0, 100.0),  # % of item's main attribute
    "protection": (20.0, 80.0),   # % of item's existing PDR / FDR
    "insight":    (1.0,  10.0),   # flat crit-target reduction
    "evasion":    (1.0,  8.0),    # flat evasion added
    "warding":    (1.0,  8.0),    # flat block added
}

REGULAR_ESSENCE_TYPES  = set(ESSENCE_VALUE_RANGES.keys())
UTILITY_ESSENCE_TYPES  = {"cleansing", "chaos", "annulment"}
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
        return False, f"This item already has an essence of that type applied."

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
    """Rolls a random value in the defined range for the given essence type."""
    r = ESSENCE_VALUE_RANGES.get(essence_type)
    if not r:
        return 0.0
    # For integer-feeling stats (insight, evasion, warding) return a whole number
    if essence_type in ("insight", "evasion", "warding"):
        return float(random.randint(int(r[0]), int(r[1])))
    return round(random.uniform(r[0], r[1]), 1)


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
      attack   — flat attack bonus
      defence  — flat defence bonus
      ward     — additional ward percentage points (same unit as item.ward)
      pdr      — additional physical damage reduction %
      fdr      — additional flat damage reduction
      crit     — flat crit-target reduction (positive = crit threshold lowers)
      evasion  — flat evasion (same unit as armor.evasion)
      block    — flat block (same unit as armor.block)
    """
    from core.models import Helmet  # local to avoid circular import

    bonus = {
        "attack": 0, "defence": 0, "ward": 0,
        "pdr": 0, "fdr": 0, "crit": 0, "evasion": 0, "block": 0,
    }

    is_helmet = isinstance(item, Helmet)

    for _, essence_type, value in get_essence_slots(item):

        if essence_type == "power":
            if is_helmet:
                # Helmet has no attack — bonus applies to DEF and WARD %
                bonus["defence"] += int(item.defence * value / 100)
                bonus["ward"]    += int(item.ward    * value / 100)
            else:
                # Gloves / Boots — bonus applies to ATK
                bonus["attack"]  += int(item.attack  * value / 100)

        elif essence_type == "protection":
            # Amplifies existing PDR and FDR on the item
            bonus["pdr"] += int(item.pdr * value / 100)
            bonus["fdr"] += int(item.fdr * value / 100)

        elif essence_type == "insight":
            # Flat crit target reduction
            bonus["crit"] += int(value)

        elif essence_type == "evasion":
            bonus["evasion"] += int(value)

        elif essence_type == "warding":
            bonus["block"] += int(value)

    return bonus
