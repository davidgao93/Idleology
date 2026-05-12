"""
calcs.py — Passive detection utilities and re-exports for backward compatibility.

Pure calculation functions have been extracted to focused modules:
  hit_calc.py   — hit/crit chance math, resolve_hit, resolve_crit, build_attack_multiplier
  damage_calc.py — damage formulas (player phases, monster roll, HP/ward application)
  ward_system.py — add_ward, generate_player_ward_on_hit

The re-exports below keep all existing callers working unchanged.
"""

import random

# ---------------------------------------------------------------------------
# Re-exports from focused modules (keep all existing import paths working)
# ---------------------------------------------------------------------------

from core.combat.calc.damage_calc import calculate_damage_taken
from core.combat.calc.hit_calc import (
    calculate_crit_chance,
    calculate_hit_chance,
    calculate_monster_hit_chance,
)

# ---------------------------------------------------------------------------
# Weapon Passive Family Registry
#
# Passives are stored as 'family_tier' strings, e.g. 'burning_3' (1-indexed).
# Per-tier scale values (used by engine and player_turn):
#   burning, poison, debilitate, shocking, sturdy, cull  → 0.08 per tier
#   deadeye  → 4 flat hit chance per tier
#   piercing → 5 crit chance per tier
#   echo     → 0.10 per tier
#   arcane   → 25 ward on hit per tier
# Checked slots: weapon main passive, pinnacle, utmost.
# ---------------------------------------------------------------------------

WEAPON_PASSIVE_FAMILIES: frozenset[str] = frozenset(
    {
        "burning",
        "poison",
        "debilitate",
        "shocking",
        "sturdy",
        "piercing",
        "cull",
        "deadeye",
        "echo",
        "arcane",
    }
)

PASSIVE_SCALE: dict[str, float] = {
    "burning": 0.08,
    "poison": 0.08,
    "debilitate": 0.08,
    "shocking": 0.08,
    "sturdy": 0.08,
    "cull": 0.08,
    "deadeye": 4.0,
    "piercing": 5.0,
    "echo": 0.10,
    "arcane": 25.0,
}


_PASSIVE_ROMAN = ("I", "II", "III", "IV", "V")


def fmt_weapon_passive(passive_str: str) -> str:
    """Formats 'burning_3' → 'Burning III' for display in combat logs."""
    if not passive_str or passive_str == "none":
        return passive_str
    if "_" in passive_str:
        family, _, tier_str = passive_str.rpartition("_")
        try:
            return f"{family.title()} {_PASSIVE_ROMAN[int(tier_str) - 1]}"
        except (ValueError, IndexError):
            pass
    return passive_str.title()


def get_weapon_tier(player, key: str) -> tuple[int, str]:
    """
    Returns (tier_index 0–4, passive_string) for the highest active tier of the
    named weapon passive family, or (-1, '') if the player has none.
    Checks weapon main, pinnacle, and utmost slots.
    """
    prefix = f"{key}_"
    best: tuple[int, str] = (-1, "")
    for passive_str in (
        player.get_weapon_passive(),
        player.get_weapon_pinnacle(),
        player.get_weapon_utmost(),
    ):
        if passive_str and passive_str.startswith(prefix):
            try:
                tier_idx = int(passive_str[len(prefix):]) - 1
                if tier_idx > best[0]:
                    best = (tier_idx, passive_str)
            except ValueError:
                continue
    return best


def get_player_passive_indices(player, target_passives: list[str]) -> list[int]:
    """
    Returns indices into target_passives for each weapon-slot passive the player has.
    Checks weapon main, pinnacle, and utmost slots.
    Retained for dummy_engine.py compatibility.
    """
    active = [
        player.get_weapon_passive(),
        player.get_weapon_pinnacle(),
        player.get_weapon_utmost(),
    ]
    return [target_passives.index(p) for p in active if p in target_passives]


# ---------------------------------------------------------------------------
# Legacy wrappers — retained for dummy_engine.py compatibility
# ---------------------------------------------------------------------------


def check_for_echo_bonus(player, actual_hit: int) -> tuple[int, bool, int]:
    """Echo weapon passive: bonus damage on hit that mirrors the strike."""
    idx, _ = get_weapon_tier(player, "echo")
    if idx < 0:
        return actual_hit, False, 0
    echo_damage = int(actual_hit * (idx + 1) * 0.10)
    return actual_hit + echo_damage, True, echo_damage


def check_for_poison_bonus(player, attack_multiplier: float) -> int:
    """Poison weapon passive: guaranteed damage on miss."""
    idx, _ = get_weapon_tier(player, "poison")
    if idx < 0:
        return 0
    poison_pct = (idx + 1) * 0.08
    return int(
        random.randint(1, int(player.get_total_attack() * poison_pct))
        * attack_multiplier
    )
