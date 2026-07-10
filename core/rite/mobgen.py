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
from core.combat.mobgen.modifier_data import (
    BOSS_MOD_NAMES,
    COMMON_MOD_NAMES,
    RARE_TIERED_MOD_NAMES,
    make_modifier,
    omnipotent_label,
)
from core.images import (
    ARBITER_PHASE_1,
    ARBITER_PHASE_2,
    ARBITER_PHASE_3,
    ARBITER_PHASE_4,
    ARBITER_PHASE_5,
    ARBITER_PHASE_FINAL,
    MONSTER_APHRODITE_REBORN,
    MONSTER_EVELYNN_REBORN,
    MONSTER_GEMINI_REBORN,
    MONSTER_LUCIFER_REBORN,
    MONSTER_NEET_REBORN,
)
from core.models import Monster, MonsterModifier

# Extreme (2) / Nightmarish (3) / Delirious (4) overlays — Wings 2 and 4 use
# Extreme, Wing 5 and the Arbiter's final phase use Nightmarish/Delirious.
# Mirrors cogs/combat.py's difficulty-setting math
# exactly — additive bonus_pct stacking + flat DR + difficulty_level for the
# surplus/crit/hit-chance tables — applied directly to a specific encounter
# rather than through the player's difficulty setting.
_DIFFICULTY_ATK_MULT = {2: 2.5, 3: 3.0, 4: 4.0}
_DIFFICULTY_DR = {2: 0.0, 3: 0.10, 4: 0.25}


def apply_rite_difficulty_overlay(monster: "Monster", level: int) -> None:
    """Overlays Extreme (level=2), Nightmarish (level=3), or Delirious
    (level=4) scaling onto an already-generated monster, on top of whatever
    bonus_*_pct it already has."""
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
    monster.image = MONSTER_APHRODITE_REBORN
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

    # Balance pass: base 2x HP boosted by a further 300% (×4) — Lucifer was
    # dying too fast to matter. ×8 total.
    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.7))
    monster.base_max_hp = int(base_hp * 2 * 4.0)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Lucifer Reborn"
    monster.image = MONSTER_LUCIFER_REBORN
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
    # Balance pass: bumped to Extreme combat difficulty (×2.5 ATK/DEF).
    apply_rite_difficulty_overlay(monster, level=2)
    finalize_monster_spawn(monster)
    return monster


def generate_wing_gemini(
    player, monster: "Monster", *, true_reckoning_pct: float = 0.80
) -> "Monster":
    """Wing 3 — Gemini Reborn (Sustain Test): True Reckoning damage split.

    true_reckoning_pct defaults to 80% per RAID-DESIGN.md; the Fracture of
    Balance writ overrides this to 90%.
    """
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    # Balance pass: base 2x HP boosted by a further 200% (×3) — combat
    # difficulty is left untouched, this wing only needed more sustain time.
    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.7))
    monster.base_max_hp = int(base_hp * 2 * 3.0)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Castor & Pollux Reborn"
    monster.image = MONSTER_GEMINI_REBORN
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
        MonsterModifier(
            name="True Reckoning", tier=0, value=true_reckoning_pct, difficulty=0.0
        )
    )

    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    return monster


def generate_wing_neet(
    player, monster: "Monster", *, void_drain_rate: float = 0.015
) -> "Monster":
    """Wing 4 — NEET Reborn (Void Drain): stat-pool attrition test.

    void_drain_rate defaults to 1.5%/round per RAID-DESIGN.md; the Hungering
    Void writ overrides this to 3.0%.
    """
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    # Balance pass: base 2x HP boosted by a further 300% (×4) — NEET was
    # dying too fast to matter. ×8 total.
    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.4))
    monster.base_max_hp = int(base_hp * 2 * 4.0)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "NEET Reborn"
    monster.image = MONSTER_NEET_REBORN
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
    # Balance pass: bumped to Extreme combat difficulty (×2.5 ATK/DEF).
    apply_rite_difficulty_overlay(monster, level=2)
    finalize_monster_spawn(monster)
    return monster


def generate_wing_evelynn(
    player, monster: "Monster", *, delirious: bool = False
) -> "Monster":
    """Wing 5 — Evelynn Reborn (All Modifiers): every common/rare mod at T5,
    scaled to Nightmarish difficulty (Delirious under the Abyssal Embrace writ).
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
    # Only one dedicated asset provided for this wing (no separate precursor/
    # reveal pair like Uber Evelynn has) — used for both image slots.
    monster.image = MONSTER_EVELYNN_REBORN
    monster.image2 = MONSTER_EVELYNN_REBORN
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


# =========================================================
# The Arbiter — 6-phase finale
# =========================================================

ARBITER_PHASE_NAMES = [
    "Left Wing of the Heavens",
    "Right Wing of the Nine Hells",
    "Left Arm of Ultimate Balance",
    "Right Arm of the Infinite Void",
    "Amalgam of Flesh, Dreams, and Nightmares",
    "Arbiter, the Last Edict",
]

ARBITER_PHASE_IMAGES = [
    ARBITER_PHASE_1,
    ARBITER_PHASE_2,
    ARBITER_PHASE_3,
    ARBITER_PHASE_4,
    ARBITER_PHASE_5,
    ARBITER_PHASE_FINAL,
]


def arbiter_ref_level(player) -> int:
    return player.level + player.ascension + 20


def get_arbiter_phases(player) -> list[dict]:
    """Builds the 6-phase combat_phases list, matching the shape
    EncounterManager.get_boss_phases returns (a dict per phase) so it slots
    into CombatView's existing combat_phases plumbing untouched."""
    ref_level = arbiter_ref_level(player)
    return [
        {"name": name, "level": ref_level, "tier": i + 1}
        for i, name in enumerate(ARBITER_PHASE_NAMES)
    ]


def _arbiter_fixed_hp(ref_level: int) -> int:
    """Deterministic HP shared by all 6 Arbiter phases — no random jitter, so
    every phase call reproduces the identical value without needing to
    thread state between phase generations."""
    return int(10 * (ref_level**1.7) * 4.0)


def generate_arbiter_phase(player, phase_data: dict, phase_index: int) -> "Monster":
    """Generates the Monster for one Arbiter phase (0-indexed).

    Phases 1-5 (index 0-4): all common + rare-tiered modifiers at the phase's
    tier, no boss modifiers. Phase 6 (index 5): Delirious stat overlay + every
    modifier at Tier 5 + every boss modifier at Tier 5 — the hardest single
    encounter in the game.

    HP is pinned identically across all 6 phases (RAID-DESIGN.md: "equal HP
    pools across all phases"), overriding whatever the modifier list (e.g.
    Titanic) would otherwise produce.
    """
    ref_level = phase_data["level"]
    tier = phase_data["tier"]

    monster = Monster(
        name=phase_data["name"],
        level=ref_level,
        hp=0,
        max_hp=0,
        xp=150000,
        attack=0,
        defence=0,
        modifiers=[],
        # No image2 — each phase keeps its own art for the whole phase.
        # CombatView._apply_phase_image_transition swaps to image2 once HP
        # drops below 50%; leaving it set to ARBITER_PORTRAIT was replacing
        # the correct phase art with the generic portrait mid-fight.
        image=ARBITER_PHASE_IMAGES[phase_index],
        flavor="watches, unmoved by anything you can do",
        species="???",
        is_boss=True,
    )
    monster = calculate_monster_stats(monster)
    monster.base_attack += int(monster.level * 0.75)
    monster.base_defence += int(monster.level * 0.75)
    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    monster.modifiers = [
        make_modifier(name, monster.level, force_tier=tier)
        for name in (COMMON_MOD_NAMES + RARE_TIERED_MOD_NAMES)
    ]
    if phase_index == 5:
        monster.modifiers += [
            make_modifier(name, monster.level, force_max_tier=True)
            for name in BOSS_MOD_NAMES
        ]
        # The true Arbiter carries every common, rare, and boss modifier at
        # max tier — a wall of dozens of names. Collapse it into one bespoke
        # entry instead of the generic "Omnipotent V" every other omnipotent
        # monster gets.
        monster.omnipotent_display = "∞ The Mind's End ∞"
        monster.omnipotent_names = frozenset(
            COMMON_MOD_NAMES + RARE_TIERED_MOD_NAMES + BOSS_MOD_NAMES
        )
    else:
        monster.omnipotent_display = omnipotent_label(tier)
        monster.omnipotent_names = frozenset(COMMON_MOD_NAMES + RARE_TIERED_MOD_NAMES)

    _apply_spawn_modifiers(monster)

    if phase_index == 5:
        apply_rite_difficulty_overlay(monster, level=4)  # Delirious

    # Equal-HP override: applied AFTER _apply_spawn_modifiers (which may have
    # set bonus_max_hp_pct via Titanic) and again after finalize_monster_spawn
    # below (which would otherwise recompute max_hp from that bonus pool).
    fixed_hp = _arbiter_fixed_hp(ref_level)
    monster.base_max_hp = fixed_hp
    monster.hp = fixed_hp
    monster.max_hp = fixed_hp

    finalize_monster_spawn(monster)
    monster.hp = fixed_hp
    monster.max_hp = fixed_hp
    return monster
