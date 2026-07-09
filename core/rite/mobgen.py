"""Monster generation for The Rite of Convergence's 5 wing encounters.

Each wing copies its base-stat formula directly from the matching Uber boss
generator in core/combat/mobgen/gen_mob.py, then replaces the usual
signature + random modifier rolls with a fully deterministic, static T5
modifier list per RAID-DESIGN.md — no RNG in what a wing throws at the
player, only in the underlying stat roll (level_exponent jitter, same as
every other monster).
"""

import random

from core.combat.mobgen.gen_mob import (
    _apply_spawn_modifiers,
    apply_all_corrupted_modifiers,
    calculate_monster_stats,
    finalize_monster_spawn,
)
from core.combat.mobgen.modifier_data import make_modifier
from core.images import (
    MONSTER_APHRODITE,
    MONSTER_EVELYNN,
    MONSTER_EVELYNN_PRECURSOR,
    MONSTER_GEMINI,
    MONSTER_LUCIFER,
    MONSTER_NEET,
)
from core.models import Monster, MonsterModifier

# Nightmarish (3) / Delirious (4) overlays, reused for Wing 5 and (in Milestone 5)
# the Arbiter's final phase. Mirrors cogs/combat.py's difficulty-setting math
# exactly — additive bonus_pct stacking + flat DR + difficulty_level for the
# surplus/crit/hit-chance tables — applied directly to a specific encounter
# rather than through the player's difficulty setting.
_DIFFICULTY_ATK_MULT = {3: 3.0, 4: 4.0}
_DIFFICULTY_DR = {3: 0.10, 4: 0.25}


def apply_rite_difficulty_overlay(monster: "Monster", level: int) -> None:
    """Overlays Nightmarish (level=3) or Delirious (level=4) scaling onto an
    already-generated monster, on top of whatever bonus_*_pct it already has."""
    mult = _DIFFICULTY_ATK_MULT[level]
    monster.bonus_attack_pct += mult - 1.0
    monster.bonus_defence_pct += mult - 1.0
    monster.difficulty_level = level
    monster.difficulty_dr = _DIFFICULTY_DR[level]
    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))


def _static_mods(monster: "Monster", names: list[str]) -> list:
    return [make_modifier(name, monster.level, force_max_tier=True) for name in names]


def generate_wing_aphrodite(player, monster: "Monster") -> "Monster":
    """Wing 1 — Aphrodite Reborn (Defensive Test): Unbreakable stack clock."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.7))
    monster.base_max_hp = int(base_hp * 4.0)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Aphrodite Reborn"
    monster.image = MONSTER_APHRODITE
    monster.flavor = "radiates an unbreakable, converging aura"
    monster.species = "Celestial"
    monster.is_boss = True

    monster.base_attack += int(monster.level * 0.5)
    monster.base_defence += int(monster.level * 0.5)
    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    monster.modifiers = _static_mods(
        monster,
        [
            "Fortified",
            "Ironclad",
            "Stalwart",
            "Titanic",
            "Vampiric",
            "Mending",
            "Veiled",
            "Death Rattle",
            "Undying Resolve",
        ],
    )
    monster.modifiers.append(make_modifier("Unbreakable", monster.level))

    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    return monster


def generate_wing_lucifer(player, monster: "Monster") -> "Monster":
    """Wing 2 — Lucifer Reborn (Offensive Test): Judgment stack clock."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.7))
    monster.base_max_hp = int(base_hp * 2)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Lucifer Reborn"
    monster.image = MONSTER_LUCIFER
    monster.flavor = "exudes a judging, all-consuming killing intent"
    monster.species = "Demon"
    monster.is_boss = True

    monster.bonus_attack_pct += 0.30
    monster.bonus_defence_pct -= 0.70

    monster.base_attack += int(monster.level * 1.0)
    monster.base_defence += int(monster.level * 0.2)

    monster.modifiers = _static_mods(
        monster,
        [
            "Empowered",
            "Savage",
            "Devastating",
            "Lethal",
            "Keen",
            "Multistrike",
            "Crushing",
            "Searing",
            "Blinding",
            "Enraged",
        ],
    )
    monster.modifiers.append(make_modifier("Judgment", monster.level))

    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    return monster


def generate_wing_gemini(
    player, monster: "Monster", *, true_reckoning_pct: float = 0.80
) -> "Monster":
    """Wing 3 — Gemini Reborn (Sustain Test): True Reckoning damage split.

    true_reckoning_pct defaults to 80% per RAID-DESIGN.md; the Fracture of
    Balance writ (Milestone 4) overrides this to 90%.
    """
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.7))
    monster.base_max_hp = int(base_hp * 2)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Castor & Pollux Reborn"
    monster.image = MONSTER_GEMINI
    monster.flavor = "move in perfect, inescapable synchrony"
    monster.species = "Celestial"
    monster.is_boss = True

    monster.base_attack += int(monster.level * 0.65)
    monster.base_defence += int(monster.level * 0.65)
    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    monster.modifiers = _static_mods(
        monster,
        [
            "Vampiric",
            "Mending",
            "Titanic",
            "Stalwart",
            "Veiled",
            "Time Lord",
            "Death Rattle",
            "Undying Resolve",
            "Soul Siphon",
        ],
    )
    # make_modifier's "uber" pool branch always uses the modifier's default
    # tier-0 value regardless of force flags, so a non-default percentage
    # (Fracture of Balance) needs to be constructed directly.
    monster.modifiers.append(
        MonsterModifier(name="True Reckoning", tier=0, value=true_reckoning_pct, difficulty=0.0)
    )

    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    return monster


def generate_wing_neet(player, monster: "Monster", *, void_drain_rate: float = 0.015) -> "Monster":
    """Wing 4 — NEET Reborn (Void Drain): stat-pool attrition test.

    void_drain_rate defaults to 1.5%/round per RAID-DESIGN.md; the Hungering
    Void writ (Milestone 4) will override this to 3.0%.
    """
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.4))
    monster.base_max_hp = int(base_hp * 2)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "NEET Reborn"
    monster.image = MONSTER_NEET
    monster.flavor = "radiates an entropic, unraveling void"
    monster.species = "Void"
    monster.is_boss = True

    monster.base_attack += int(monster.level * 0.8)
    monster.base_defence += int(monster.level * 0.5)
    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    monster.modifiers = _static_mods(monster, ["Corrosion", "Dispelling", "Nullifying"])
    monster.modifiers.append(make_modifier("Void Aura", monster.level))
    monster.void_drain_rate = void_drain_rate

    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    return monster


def generate_wing_evelynn(player, monster: "Monster", *, delirious: bool = False) -> "Monster":
    """Wing 5 — Evelynn Reborn (All Modifiers): every common/rare mod at T5,
    scaled to Nightmarish difficulty (Delirious under the Abyssal Embrace writ,
    Milestone 4).
    """
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.65))
    monster.base_max_hp = int(base_hp * 2)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Evelynn Reborn"
    monster.image = MONSTER_EVELYNN_PRECURSOR
    monster.image2 = MONSTER_EVELYNN
    monster.flavor = "casts a writhing, converging black mass"
    monster.species = "Corrupted"
    monster.is_boss = True
    monster.is_corrupted = True

    monster.modifiers = []
    apply_all_corrupted_modifiers(monster, force_tier=5)
    monster.modifiers.extend(
        [
            make_modifier("Corrupted Protection", monster.level),
            make_modifier("Origin of Corruption", monster.level),
        ]
    )

    monster.bonus_attack_pct += 0.40
    monster.bonus_defence_pct -= 0.15
    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    _apply_spawn_modifiers(monster)
    apply_rite_difficulty_overlay(monster, level=4 if delirious else 3)
    finalize_monster_spawn(monster)
    return monster
