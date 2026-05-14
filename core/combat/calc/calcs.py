"""
calcs.py — Passive detection utilities and re-exports for backward compatibility.

Pure calculation functions have been extracted to focused modules:
  hit_calc.py   — hit/crit chance math, resolve_hit, resolve_crit, build_attack_multiplier
  damage_calc.py — damage formulas (player phases, monster roll, HP/ward application)
  ward_system.py — add_ward, generate_player_ward_on_hit

The re-exports below keep all existing callers working unchanged.
"""

import random
from dataclasses import dataclass
from typing import Callable

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
# WEAPON_PASSIVE_DEFS is the canonical source for all weapon passive metadata.
# WEAPON_PASSIVE_FAMILIES and PASSIVE_SCALE are derived from it for backward compat.
# ---------------------------------------------------------------------------


@dataclass
class WeaponPassiveDef:
    key: str                               # internal DB key, e.g. "burning"
    display_name: str                      # e.g. "Burning (Atk Boost)"
    tier_labels: tuple                     # 5 display names for T1–T5
    scale: float                           # per-tier numeric scale (for engine)
    description: Callable[[int], str]      # 1-based tier index → effect string


WEAPON_PASSIVE_DEFS: dict[str, WeaponPassiveDef] = {
    "burning": WeaponPassiveDef(
        "burning", "Burning (Atk Boost)",
        ("burning", "flaming", "scorching", "incinerating", "carbonising"),
        0.08, lambda i: f"Atk +{int(i * 0.08 * 100)}%",
    ),
    "poison": WeaponPassiveDef(
        "poison", "Poisonous (Miss Dmg)",
        ("poisonous", "noxious", "venomous", "toxic", "lethal"),
        0.08, lambda i: f"Miss deals up to {int(i * 0.08 * 100)}% Atk",
    ),
    "debilitate": WeaponPassiveDef(
        "debilitate", "Polished (Def Shred)",
        ("polished", "honed", "gleaming", "tempered", "flaring"),
        0.08, lambda i: f"Enemy Def -{int(i * 0.08 * 100)}%",
    ),
    "shocking": WeaponPassiveDef(
        "shocking", "Sparking (Min Dmg)",
        ("sparking", "shocking", "discharging", "electrocuting", "vapourising"),
        0.08, lambda i: f"Min Dmg Floor raised to {int(i * 0.08 * 100)}% of Max",
    ),
    "sturdy": WeaponPassiveDef(
        "sturdy", "Sturdy (Def Boost)",
        ("sturdy", "reinforced", "thickened", "impregnable", "impenetrable"),
        0.08, lambda i: f"Player Def +{int(i * 0.08 * 100)}%",
    ),
    "piercing": WeaponPassiveDef(
        "piercing", "Piercing (Crit Rate)",
        ("piercing", "keen", "incisive", "puncturing", "penetrating"),
        5.0, lambda i: f"Crit Rolls increased by {i * 5} (Easier Crits)",
    ),
    "cull": WeaponPassiveDef(
        "cull", "Strengthened (Cull)",
        ("strengthened", "forceful", "overwhelming", "devastating", "catastrophic"),
        0.08, lambda i: f"Instantly kill if HP < {int(i * 0.08 * 100)}%",
    ),
    "deadeye": WeaponPassiveDef(
        "deadeye", "Accurate (Hit Bonus)",
        ("accurate", "precise", "sharpshooter", "deadeye", "bullseye"),
        4.0, lambda i: f"Flat Accuracy Roll +{i * 4}",
    ),
    "echo": WeaponPassiveDef(
        "echo", "Echo (Double Hit)",
        ("echo", "echoo", "echooo", "echoooo", "echoes"),
        0.10, lambda i: f"Extra hit dealing {int(i * 0.10 * 100)}% Dmg",
    ),
    "arcane": WeaponPassiveDef(
        "arcane", "Arcane (Ward on Hit)",
        ("arcane", "arcane II", "arcane III", "arcane IV", "arcane V"),
        25.0, lambda i: f"Gain {int(i * 25)} Ward on Hit",
    ),
}

# Backward-compatible constants derived from WEAPON_PASSIVE_DEFS
WEAPON_PASSIVE_FAMILIES: frozenset[str] = frozenset(WEAPON_PASSIVE_DEFS)
PASSIVE_SCALE: dict[str, float] = {k: v.scale for k, v in WEAPON_PASSIVE_DEFS.items()}

# ---------------------------------------------------------------------------
# Gear Passive Description Dicts
#
# Canonical source for display descriptions of tiered/levelled gear passives.
# Keys are lowercase passive names (matching DB storage); values are
# lambda(level: int) → str. Level is 1-based.
# ---------------------------------------------------------------------------

ACCESSORY_PASSIVE_DESCS: dict[str, Callable[[int], str]] = {
    "obliterate": lambda l: f"{l * 2}% chance to deal Double Damage",
    "absorb": lambda l: f"{l * 10}% chance to gain 10% of Monster's ATK and DEF",
    "prosper": lambda l: f"{l * 10}% chance to Double Gold gained",
    "infinite wisdom": lambda l: f"{l * 5}% chance to Double XP gained",
    "lucky strikes": lambda l: f"{l * 10}% chance for Lucky Hits",
}

GLOVE_PASSIVE_DESCS: dict[str, Callable[[int], str]] = {
    "ward-touched": lambda l: f"Gain {l * 25} Ward on Hits",
    "ward-fused": lambda l: f"Gain {l * 50} Ward on Crits",
    "instability": lambda l: f"Hits are 50% dmg OR {150 + (l * 10)}% dmg",
    "deftness": lambda l: f"Crit Floor raised by {l * 5}%",
    "adroit": lambda l: f"Normal Hit Floor raised by {l * 2}%",
    "equilibrium": lambda l: f"Gain {l * 5}% of Dmg Dealt as XP",
    "plundering": lambda l: f"Gain {l * 10}% of Dmg Dealt as Gold",
}

BOOT_PASSIVE_DESCS: dict[str, Callable[[int], str]] = {
    "speedster": lambda l: f"Cooldown reduced by {l}m",
    "skiller": lambda l: f"{l * 5}% chance for extra skill mats",
    "treasure-tracker": lambda l: f"Treasure Mob chance +{l * 0.5:.1f}%",
    "hearty": lambda l: f"Max HP +{l * 5}%",
    "cleric": lambda l: f"Potions heal +{l * 10}% extra",
    "thrill-seeker": lambda l: f"Special Drop Chance +{l}%",
}

HELMET_PASSIVE_DESCS: dict[str, Callable[[int], str]] = {
    "juggernaut": lambda l: f"Gain {l * 4}% of Def as Atk",
    "insight": lambda l: f"Crit Dmg Multiplier +{l * 0.1:.1f}x",
    "volatile": lambda l: f"Deal {l * 100}% of Max HP as Dmg on ward break",
    "divine": lambda l: f"Converts {l * 100}% of Potion Overheal to Ward",
    "frenzy": lambda l: f"{l * 0.5:.1f}% Inc Dmg per 1% Missing HP",
    "leeching": lambda l: f"Heal for {l * 2}% of base damage dealt",
    "thorns": lambda l: f"Reflect {l * 100}% of blocked damage",
    "ghosted": lambda l: f"Gain {l * 10} Ward on Evade",
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
