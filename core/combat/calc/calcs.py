"""
calcs.py — Passive detection utilities and re-exports for backward compatibility.

Pure calculation functions have been extracted to focused modules:
  hit_calc.py   — hit/crit chance math, resolve_hit, resolve_crit, build_attack_multiplier
  damage_calc.py — damage formulas (player phases, monster roll, HP/ward application)
  ward_system.py — add_ward, generate_player_ward_on_hit

The re-exports below keep all existing callers working unchanged.
"""

from dataclasses import dataclass
from typing import Callable

# ---------------------------------------------------------------------------
# Re-exports from focused modules (keep all existing import paths working)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Weapon Passive Family Registry
#
# Passives are stored as 'family_tier' strings, e.g. 'burning_3' (1-indexed).
# WEAPON_PASSIVE_DEFS is the canonical source for all weapon passive metadata.
# WEAPON_PASSIVE_FAMILIES and PASSIVE_SCALE are derived from it for backward compat.
# ---------------------------------------------------------------------------


@dataclass
class WeaponPassiveDef:
    key: str  # internal DB key, e.g. "burning"
    display_name: str  # e.g. "Burning (Atk Boost)"
    tier_labels: tuple  # 5 display names for T1–T5
    scale: float  # per-tier numeric scale (for engine)
    description: Callable[[int], str]  # 1-based tier index → effect string


WEAPON_PASSIVE_DEFS: dict[str, WeaponPassiveDef] = {
    "burning": WeaponPassiveDef(
        "burning",
        "Burning (Atk Boost)",
        ("Burning I", "Burning II", "Burning III", "Burning IV", "Burning V"),
        0.08,
        lambda i: f"Atk +{int(i * 0.08 * 100)}%",
    ),
    "poison": WeaponPassiveDef(
        "poison",
        "Poisonous (Miss Dmg)",
        ("Poisonous I", "Poisonous II", "Poisonous III", "Poisonous IV", "Poisonous V"),
        0.08,
        lambda i: f"Miss deals up to {int(i * 0.08 * 100)}% Atk",
    ),
    "debilitate": WeaponPassiveDef(
        "debilitate",
        "Debilitate (Def Shred)",
        (
            "Debilitate I",
            "Debilitate II",
            "Debilitate III",
            "Debilitate IV",
            "Debilitate V",
        ),
        0.08,
        lambda i: f"Enemy Def -{int(i * 0.08 * 100)}%",
    ),
    "shocking": WeaponPassiveDef(
        "shocking",
        "Sparking (Min Dmg)",
        ("Sparking I", "Sparking II", "Sparking III", "Sparking IV", "Sparking V"),
        0.08,
        lambda i: f"Min Dmg Floor raised to {int(i * 0.08 * 100)}% of Max",
    ),
    "sturdy": WeaponPassiveDef(
        "sturdy",
        "Sturdy (Def Boost)",
        ("Sturdy I", "Sturdy II", "Sturdy III", "Sturdy IV", "Sturdy V"),
        0.08,
        lambda i: f"Player Def +{int(i * 0.08 * 100)}%",
    ),
    "piercing": WeaponPassiveDef(
        "piercing",
        "Piercing (Crit Rate)",
        ("Piercing I", "Piercing II", "Piercing III", "Piercing IV", "Piercing V"),
        5.0,
        lambda i: f"Critical strike chance increased by {i * 5}%",
    ),
    "cull": WeaponPassiveDef(
        "cull",
        "Strengthened (Cull)",
        (
            "Strengthened I",
            "Strengthened II",
            "Strengthened III",
            "Strengthened IV",
            "Strengthened V",
        ),
        0.08,
        lambda i: f"Instantly kill if HP < {int(i * 0.08 * 100)}%",
    ),
    "deadeye": WeaponPassiveDef(
        "deadeye",
        "Accurate (Hit Bonus)",
        ("Accurate I", "Accurate II", "Accurate III", "Accurate IV", "Accurate V"),
        4.0,
        lambda i: f"Flat Accuracy Roll +{i * 4}",
    ),
    "echo": WeaponPassiveDef(
        "echo",
        "Echo (Double Hit)",
        ("Echo I", "Echo II", "Echo III", "Echo IV", "Echo V"),
        0.10,
        lambda i: f"Extra hit dealing {int(i * 0.10 * 100)}% Dmg",
    ),
    "arcane": WeaponPassiveDef(
        "arcane",
        "Arcane (Ward on Hit)",
        ("Arcane I", "Arcane II", "Arcane III", "Arcane IV", "Arcane V"),
        25.0,
        lambda i: f"Gain {int(i * 25)} Ward on Hit",
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
    "obliterate": lambda lvl: f"{lvl * 4}% chance to deal Double Damage",
    "absorb": lambda lvl: f"{lvl * 10}% chance to gain 10% of Monster's ATK and DEF",
    "prosper": lambda lvl: f"{lvl * 10}% chance to Double Gold gained",
    "infinite wisdom": lambda lvl: f"{lvl * 5}% chance to Double XP gained",
    "lucky strikes": lambda lvl: f"{lvl * 10}% chance for Lucky Hits",
}

GLOVE_PASSIVE_DESCS: dict[str, Callable[[int], str]] = {
    "ward-touched": lambda lvl: f"Gain {lvl * 25} Ward on Hits",
    "ward-fused": lambda lvl: f"Gain {lvl * 50} Ward on Crits",
    "instability": lambda lvl: f"Hits are 50% dmg OR {150 + (lvl * 10)}% dmg",
    "deftness": lambda lvl: f"Crit roll floor raised by {lvl * 5}% of max",
    "adroit": lambda lvl: f"Normal Hit Floor raised by {lvl * 2}%",
    "equilibrium": lambda lvl: f"Gain {lvl * 5}% of Dmg Dealt as XP",
    "plundering": lambda lvl: f"Gain {lvl * 10}% of Dmg Dealt as Gold",
}

BOOT_PASSIVE_DESCS: dict[str, Callable[[int], str]] = {
    "speedster": lambda lvl: f"Cooldown reduced by {lvl}m",
    "skiller": lambda lvl: f"{lvl * 5}% chance for extra skill mats",
    "treasure-tracker": lambda lvl: f"Treasure Mob chance +{lvl * 0.5:.1f}%",
    "hearty": lambda lvl: f"Max HP +{lvl * 5}%",
    "cleric": lambda lvl: f"Potions heal +{lvl * 10}% extra",
    "thrill-seeker": lambda lvl: f"Special Rarity +{lvl * 0.5:.1f}%",
}

HELMET_PASSIVE_DESCS: dict[str, Callable[[int], str]] = {
    "juggernaut": lambda lvl: f"Gain {lvl * 4}% of Def as Atk",
    "insight": lambda lvl: f"Crit Dmg Multiplier +{lvl * 0.1:.1f}x",
    "volatile": lambda lvl: f"Deal {lvl * 100}% of Max HP as Dmg on ward break",
    "divine": lambda lvl: f"Converts {lvl * 100}% of Potion Overheal to Ward",
    "frenzy": lambda lvl: f"{lvl * 0.5:.1f}% Inc Dmg per 1% Missing HP",
    "leeching": lambda lvl: f"Heal {lvl * 0.2:.2f}% of dmg dealt",
    "thorns": lambda lvl: f"Reflect {lvl * 500}% of blocked damage",
    "ghosted": lambda lvl: f"Gain {lvl * 10} Ward on Evade",
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
    Checks weapon main, pinnacle, utmost slots, and the soul stone.
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
                tier_idx = int(passive_str[len(prefix) :]) - 1
                if tier_idx > best[0]:
                    best = (tier_idx, passive_str)
            except ValueError:
                continue

    # Also check soul stone for weapon-type passives
    if key in WEAPON_PASSIVE_FAMILIES:
        ss_tier = get_soul_stone_passive(player, key)
        if ss_tier is not None:
            tier_idx = ss_tier - 1  # 1-based tier → 0-based index
            if tier_idx > best[0]:
                best = (tier_idx, f"{key}_{ss_tier}")

    return best


def get_soul_stone_passive(player, key: str) -> int | None:
    """
    Returns the tier (1–5) of the given passive in the player's soul stone, or None.
    Thin wrapper around player.get_soul_stone_passive() so combat modules can call
    a standalone function without importing models directly.
    """
    return player.get_soul_stone_passive(key)
