import csv
import os
import random

from core.combat.mobgen.modifier_data import (
    BOSS_MOD_NAMES,
    COMMON_MOD_NAMES,
    MODIFIER_DEFINITIONS,
    RARE_TIERED_MOD_NAMES,
    make_modifier,
    omnipotent_label,
)
from core.images import (
    COMBAT_DUMMY,
    CORRUPTED_MONSTERS,
    MONSTER_APHRODITE,
    MONSTER_EVELYNN,
    MONSTER_EVELYNN_PRECURSOR,
    MONSTER_GEMINI,
    MONSTER_LUCIFER,
    MONSTER_NEET,
)
from core.inner_sanctum.mechanics import get_tree_bonuses
from core.models import Monster

# Module-level cache for monsters.csv rows — populated on first call, never re-read.
# Tuple layout: (name, url, level_scaled, flavor, species)
_MONSTER_ROWS: list[tuple] | None = None


def _load_monster_rows() -> list[tuple]:
    global _MONSTER_ROWS
    if _MONSTER_ROWS is not None:
        return _MONSTER_ROWS
    csv_path = os.path.join(os.path.dirname(__file__), "../../../assets/monsters.csv")
    rows: list[tuple] = []
    try:
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                rows.append(
                    (
                        row["name"],
                        row["url"],
                        int(row["level"]) * 10,
                        row["flavor"],
                        row.get("species", row["name"]),
                    )
                )
    except Exception as e:
        print(f"Error reading monsters.csv: {e}")
    _MONSTER_ROWS = rows
    return rows


async def generate_encounter(
    player, monster, is_treasure, task_species=None, slayer_tree_nodes=None
):
    """Generate an encounter with a monster based on the user's level."""
    if player.level < 5:
        difficulty_multiplier = random.randint(1, 2)
    elif player.level <= 20:
        difficulty_multiplier = random.randint(1, 3)
    elif player.level <= 40:
        difficulty_multiplier = random.randint(1, 4)
    elif player.level <= 50:
        difficulty_multiplier = random.randint(1, 5)
    elif player.level <= 60:
        difficulty_multiplier = random.randint(2, 5)
    elif player.level <= 70:
        difficulty_multiplier = random.randint(2, 6)
    elif player.level <= 80:
        difficulty_multiplier = random.randint(2, 7)
    elif player.level <= 90:
        difficulty_multiplier = random.randint(3, 8)
    else:
        difficulty_multiplier = random.randint(10, 15)

    monster.level = player.level + player.ascension + difficulty_multiplier

    monster = calculate_monster_stats(monster)

    if is_treasure:
        monster = await fetch_monster_image(999, monster, None)
    else:
        monster = await fetch_monster_image(monster.level, monster, task_species)

    # Phase 2+ style: set base_max_hp, let finalize_monster_spawn apply bonuses (Titanic etc.)
    if player.level == 1:
        base_hp = 10
    elif player.level > 1 and player.level <= 10:
        base_hp = max(10, random.randint(1, 4) + int(7 * monster.level))
    else:
        base_hp = random.randint(0, 9) + int(
            10 * (monster.level ** random.uniform(1.6, 1.7))
        )

    if is_treasure:
        # Treasure monsters are near-harmless pushovers by default — a trivial
        # kill that exists purely to hand out its guaranteed/boosted loot roll
        # (see rare_monsters handling in rewards.py). Inner Sanctum Vice's
        # Curio-sity nodes add back a % of what a normal same-level monster
        # would have, up to 90% at full investment across all three nodes.
        normal_attack, normal_defence, normal_hp = (
            monster.base_attack,
            monster.base_defence,
            base_hp,
        )
        stat_pct = get_tree_bonuses(getattr(player, "inner_sanctum_nodes", {}))[
            "treasure_stat_bonus_pct"
        ]
        monster.base_attack = 1 + int(normal_attack * stat_pct)
        monster.base_defence = 1 + int(normal_defence * stat_pct)
        monster.attack = monster.base_attack
        monster.defence = monster.base_defence
        base_hp = 10 + int(normal_hp * stat_pct)

    monster.base_max_hp = base_hp
    monster.hp = base_hp
    monster.max_hp = base_hp
    # Early-level XP is deliberately reduced so a single fight doesn't cause
    # multiple level-ups (the old level*100 formula gave 300+ XP at level 3).
    # At monster.level < 10: ~30 XP at level 1, ~105 XP at level 3, blending
    # smoothly back up to the full level*100 formula by level 10.
    if monster.level < 10:
        monster.xp = random.randint(1, 9) + monster.level * 30 + 15
    else:
        monster.xp = random.randint(1, 9) + monster.level * 100

    monster.modifiers = []
    if not is_treasure:
        modifier_checks = []
        if monster.level > 20:
            modifier_checks.append(10 + int(player.get_total_rarity() / 10))
        if monster.level > 40:
            modifier_checks.append(15 + int(player.get_total_rarity() / 10))
        if monster.level > 60:
            modifier_checks.append(20 + int(player.get_total_rarity() / 10))
        if monster.level > 80:
            modifier_checks.append(25 + int(player.get_total_rarity() / 10))
        if monster.level >= 100:
            modifier_checks.append(50 + int(player.get_total_rarity() / 10))
        if monster.level > 110:
            modifier_checks.append(55 + int(player.get_total_rarity() / 10))
        if monster.level > 120:
            modifier_checks.append(60 + int(player.get_total_rarity() / 10))
        if monster.level > 130:
            modifier_checks.append(65 + int(player.get_total_rarity() / 10))
        if monster.level > 140:
            modifier_checks.append(70 + int(player.get_total_rarity() / 10))
        if monster.level >= 150:
            modifier_checks.append(75 + int(player.get_total_rarity() / 10))

        num_mods = sum(
            1 for chance in modifier_checks if random.randint(1, 100) <= chance
        )
        if num_mods > 0:
            _assign_modifiers(monster, num_mods, is_boss=False)
            _apply_spawn_modifiers(monster)
        _roll_essence_spawn(monster, player.level)
        if not monster.is_essence:
            _roll_zenith_spawn(monster, player, slayer_tree_nodes or {})

        # Vice's Special Needs/Runefinder downside only applies to regular
        # (non-treasure) monsters — treasure monsters are governed entirely
        # by the Curio-sity stat scaling above.
        _apply_inner_sanctum_vice_downside(monster, player)

    finalize_monster_spawn(monster)
    return monster


async def generate_boss(player, monster, phase, phase_index):
    """Generate a boss with a phase based on the user's level."""
    # print(f"Generating a boss based on {phase}")
    difficulty_multiplier = int(player.level / 5)

    monster.level = (
        player.level + player.ascension + difficulty_multiplier + phase_index
    )

    monster = calculate_monster_stats(monster)
    monster = await fetch_monster_image(phase["level"], monster)

    # Phase 2+ style
    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )
    base_hp = int(base_hp * phase["hp_multiplier"])
    base_hp = int(base_hp * (monster.level / 100))
    monster.base_max_hp = base_hp
    monster.hp = base_hp
    monster.max_hp = base_hp
    monster.xp = random.randint(1, 9) + monster.level * 100

    monster.modifiers = []
    # Reset all modifier-driven combat stacks. These are tied to specific modifiers
    # that are being re-rolled for this phase — stale values from the previous phase
    # would cause doom to silently fizzle (modifier gone but stacks remain) or
    # instantly kill the player on the first hit of a new phase (stacks carried in).
    monster.doom_stacks = 0
    monster.wrathful_stacks = 0
    monster.corrode_stacks = 0
    monster.bleed_stacks = 0
    monster.spike_stacks = 0
    monster.onslaught_bonus_atk = 0.0
    monster.pressure_stacks = 0
    monster.pressure_player_critted = False
    monster.flashfire_charges = 0
    monster.death_rattle_triggered = False
    monster.death_rattle_countdown = -1
    monster.colossus_active = False
    monster.colossus_hit_negated = False
    monster.colossus_dr = 0.0
    monster.temporal_window_damage = 0
    monster.undying_resolve_triggered = False
    monster.undying_immune_turns = 0
    monster.undying_atk_boost_turns = 0
    monster.potion_uses_tracked = 0
    # Fix 3: reset percentage multipliers — _apply_spawn_modifiers uses +=, so stale
    # phase-1 values would stack additively into phase-2 modifier rolls.
    monster.bonus_attack_pct = 0.0
    monster.bonus_defence_pct = 0.0
    monster.bonus_max_hp_pct = 0.0
    _assign_modifiers(
        monster, phase["modifiers_count"], is_boss=True, force_max_eligible_tier=True
    )
    _apply_spawn_modifiers(monster)
    _apply_inner_sanctum_deicide_downside(monster, player)
    finalize_monster_spawn(monster)
    return monster


async def generate_ascent_monster(
    player, monster_instance, ascent_stage_level, num_normal_mods, num_boss_mods
):
    """Generates a monster for the ascent mode."""
    monster = monster_instance
    monster.level = ascent_stage_level

    temp_monster_for_stats = Monster(
        name="",
        level=monster.level,
        hp=0,
        max_hp=0,
        xp=0,
        attack=0,
        defence=0,
    )
    temp_monster_for_stats = calculate_monster_stats(temp_monster_for_stats)
    monster.attack = temp_monster_for_stats.attack
    monster.base_attack = temp_monster_for_stats.base_attack
    monster.defence = temp_monster_for_stats.defence
    monster.base_defence = temp_monster_for_stats.base_defence

    monster = await fetch_monster_image(random.randint(30, 120), monster)

    # Phase 2+ style
    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )
    monster.base_max_hp = base_hp
    monster.hp = base_hp
    monster.max_hp = base_hp
    monster.xp = int(monster.max_hp * (1 + ascent_stage_level / 50))

    monster.modifiers = []
    total_mods = num_normal_mods + num_boss_mods
    _assign_ascent_modifiers(monster, total_mods, num_boss_mods=num_boss_mods)
    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    monster.is_boss = True
    return monster


def _apply_inner_sanctum_vice_downside(monster, player) -> None:
    """Vice path trade-off: every rank invested in Special Needs/Runefinder
    makes regular monsters slightly tankier/harder-hitting, in exchange for
    Vice's rarity/loot bonuses (special rarity, rune chance, treasure chance).

    Crit/damage use plain assignment (spawn-established, like Empowered) —
    they're set once per generate_encounter call and never re-entered for a
    single monster, so there's no double-accumulation risk the way there
    would be re-applying a `+=` across boss phase transitions."""
    bonuses = get_tree_bonuses(getattr(player, "inner_sanctum_nodes", {}))
    if bonuses["vice_monster_atk_pct"]:
        monster.bonus_attack_pct += bonuses["vice_monster_atk_pct"]
    if bonuses["vice_monster_def_pct"]:
        monster.bonus_defence_pct += bonuses["vice_monster_def_pct"]
    if bonuses["vice_monster_hp_pct"]:
        monster.bonus_max_hp_pct += bonuses["vice_monster_hp_pct"]
    monster.is_bonus_crit_chance = bonuses["vice_monster_crit_pct"]
    monster.is_bonus_damage_pct = bonuses["vice_monster_dmg_pct"]


def _apply_inner_sanctum_deicide_downside(monster, player) -> None:
    """Deicide path trade-off: every point invested in Deicide makes phase-door
    bosses tougher, in exchange for its boss-chance/boss-loot bonuses.
    Never applied to Uber bosses — those are separately hand-tuned fights."""
    bonuses = get_tree_bonuses(getattr(player, "inner_sanctum_nodes", {}))
    if bonuses["deicide_boss_atk_pct"]:
        monster.bonus_attack_pct += bonuses["deicide_boss_atk_pct"]
    if bonuses["deicide_boss_def_pct"]:
        monster.bonus_defence_pct += bonuses["deicide_boss_def_pct"]
    if bonuses["deicide_boss_hp_pct"]:
        monster.bonus_max_hp_pct += bonuses["deicide_boss_hp_pct"]


def _pick_modifier_type(is_boss: bool) -> str:
    """Returns 'common', 'rare_tiered', or 'boss'."""
    if is_boss:
        weights = [55, 30, 15]  # common, rare_tiered, boss
    else:
        weights = [75, 25, 0]  # regular monsters never get boss mods
    return random.choices(["common", "rare_tiered", "boss"], weights=weights, k=1)[0]


def _assign_modifiers(
    monster,
    num_mods: int,
    is_boss: bool,
    force_max_tier: bool = False,
    force_max_eligible_tier: bool = False,
) -> None:
    """Fills monster.modifiers with num_mods unique MonsterModifier instances."""
    used_names: set = set()
    attempts = 0
    while len(monster.modifiers) < num_mods and attempts < num_mods * 10:
        attempts += 1
        pool_type = _pick_modifier_type(is_boss)
        if pool_type == "common":
            candidates = [n for n in COMMON_MOD_NAMES if n not in used_names]
        elif pool_type == "rare_tiered":
            candidates = [n for n in RARE_TIERED_MOD_NAMES if n not in used_names]
        else:
            candidates = [n for n in BOSS_MOD_NAMES if n not in used_names]
        if not candidates:
            continue
        name = random.choice(candidates)
        used_names.add(name)
        monster.modifiers.append(
            make_modifier(
                name,
                monster.level,
                force_max_tier=force_max_tier,
                force_max_eligible_tier=force_max_eligible_tier,
            )
        )


def _assign_ascent_modifiers(monster, num_mods: int, num_boss_mods: int = 0) -> None:
    """Ascent variant: guarantees the specified number of boss mods."""
    min_boss = min(num_boss_mods, len(BOSS_MOD_NAMES))
    boss_assigned = 0
    used_names: set = set()

    boss_candidates = list(BOSS_MOD_NAMES)
    random.shuffle(boss_candidates)
    for name in boss_candidates:
        if boss_assigned >= min_boss:
            break
        if name not in used_names:
            monster.modifiers.append(make_modifier(name, monster.level))
            used_names.add(name)
            boss_assigned += 1

    remaining = num_mods - boss_assigned
    attempts = 0
    while remaining > 0 and attempts < remaining * 10:
        attempts += 1
        pool_type = random.choices(["common", "rare_tiered"], weights=[72, 28], k=1)[0]
        candidates = {
            "common": COMMON_MOD_NAMES,
            "rare_tiered": RARE_TIERED_MOD_NAMES,
        }[pool_type]
        candidates = [n for n in candidates if n not in used_names]
        if candidates:
            name = random.choice(candidates)
            used_names.add(name)
            monster.modifiers.append(make_modifier(name, monster.level))
            remaining -= 1


def _apply_spawn_modifiers(monster) -> None:
    """Apply modifiers that affect monster stats at spawn time.
    Phase 2: % effects now accumulate into bonus_*_pct pools.
    """
    if monster.has_modifier("Ascended"):
        level_added = int(monster.get_modifier_value("Ascended"))
        monster.level += level_added
        monster = calculate_monster_stats(monster)

    if monster.has_modifier("Empowered"):
        monster.bonus_attack_pct += monster.get_modifier_value("Empowered")

    if monster.has_modifier("Fortified"):
        monster.bonus_defence_pct += monster.get_modifier_value("Fortified")

    if monster.has_modifier("Titanic"):
        monster.bonus_max_hp_pct += monster.get_modifier_value("Titanic") - 1.0

    if monster.has_modifier("Veiled"):
        monster.ward = int(monster.max_hp * monster.get_modifier_value("Veiled"))

    # Dual-write live fields during Phase 2 so existing code continues to work
    # (will be removed in Phase 3)
    if monster.bonus_attack_pct != 0 or monster.bonus_defence_pct != 0:
        monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
        monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    if monster.bonus_max_hp_pct != 0:
        monster.max_hp = int(monster.base_max_hp * (1 + monster.bonus_max_hp_pct))
        monster.hp = monster.max_hp


def _add_uber_random_modifiers(monster, count: int = 5) -> None:
    """Layers `count` additional random modifiers onto an Uber boss's
    already-built signature modifier list — same common/rare_tiered 72/28
    mix, deduplicated against names already on the monster, that Apex uses
    for its 5 extra random modifiers (see ApexMechanics.build_apex_monster).

    Must run before finalize_monster_spawn: applies any spawn-time stat
    effects (Empowered/Fortified/Titanic/Veiled) rolled among the new names.
    """
    used_names = {m.name for m in monster.modifiers}
    added = 0
    attempts = 0
    while added < count and attempts < 50:
        attempts += 1
        pool_type = random.choices(["common", "rare_tiered"], weights=[72, 28], k=1)[0]
        pool = COMMON_MOD_NAMES if pool_type == "common" else RARE_TIERED_MOD_NAMES
        candidates = [n for n in pool if n not in used_names]
        if not candidates:
            continue
        name = random.choice(candidates)
        monster.modifiers.append(make_modifier(name, monster.level))
        used_names.add(name)
        added += 1
    _apply_spawn_modifiers(monster)


def finalize_monster_spawn(monster: "Monster") -> "Monster":
    """Centralized final step for Phase 2+ spawn logic.

    - Ensures base_* fields are populated if they weren't set earlier.
    - Applies all accumulated bonus_*_pct and flat_*_bonus to produce final live stats.
    - This is the single place that should be called at the end of every
      monster generation path to keep things consistent.
    """
    # Fallback snapshot if bases were never explicitly set
    if monster.base_attack == 0:
        monster.base_attack = monster.attack
    if monster.base_defence == 0:
        monster.base_defence = monster.defence
    if monster.base_max_hp == 0:
        monster.base_max_hp = monster.max_hp

    # Apply current bonuses + flat bonuses to live fields
    monster.attack = monster.effective_attack
    monster.defence = monster.effective_defence

    if monster.bonus_max_hp_pct != 0:
        monster.max_hp = monster.effective_max_hp
        monster.hp = min(monster.hp, monster.max_hp)

    return monster


def level_exponent(level: int) -> float:
    if level < 5:
        return 1.0

    if level <= 20:
        return random.uniform(1.1, 1.2)
    elif level <= 40:
        return random.uniform(1.2, 1.25)
    elif level <= 50:
        return random.uniform(1.25, 1.3)
    elif level <= 60:
        return random.uniform(1.3, 1.35)
    elif level <= 70:
        return random.uniform(1.35, 1.4)
    elif level <= 80:
        return random.uniform(1.4, 1.45)
    elif level <= 100:
        return random.uniform(1.45, 1.5)
    elif level <= 110:
        return random.uniform(1.5, 1.51)
    elif level <= 120:
        return random.uniform(1.51, 1.52)
    elif level <= 130:
        return random.uniform(1.52, 1.53)
    elif level <= 140:
        return random.uniform(1.53, 1.54)
    elif level <= 150:
        return random.uniform(1.54, 1.55)
    elif level <= 160:
        return random.uniform(1.55, 1.56)
    elif level <= 170:
        return random.uniform(1.56, 1.57)
    elif level <= 180:
        return random.uniform(1.57, 1.58)
    elif level <= 190:
        return random.uniform(1.58, 1.59)
    elif level <= 200:
        return random.uniform(1.59, 1.60)
    elif level <= 210:
        return random.uniform(1.60, 1.61)
    else:
        return random.uniform(1.61, 1.62)


def calculate_monster_stats(monster):
    """Compute base stats for a monster and store them in base_* fields.
    Live .attack / .defence are kept in sync during Phase 2 transition.
    """
    if monster.level < 5:
        base_attack = base_defence = monster.level
    else:
        exp_a = level_exponent(monster.level)
        exp_b = level_exponent(monster.level)
        base_attack = monster.level**exp_a
        base_defence = (
            monster.level**exp_b * 1.3
        )  # player attack is typically 30% higher than player def

    monster.base_attack = int(base_attack)
    monster.base_defence = int(base_defence)

    # Dual-write for Phase 2 transition compatibility
    monster.attack = monster.base_attack
    monster.defence = monster.base_defence

    return monster


async def fetch_monster_image(level, monster_data, task_species=None):
    """Fetches a monster image from the monsters.csv file based on the encounter level."""
    monsters = _load_monster_rows()
    if not monsters:
        monster_data.name = "Commoner"
        monster_data.image = COMBAT_DUMMY
        monster_data.flavor = "stares pleadingly at"
        monster_data.species = "Humanoid"
        return monster_data

    if 444 <= level <= 888:
        for monster in monsters:
            if monster[2] == level * 10:
                monster_data.name = monster[0]
                monster_data.image = monster[1]
                monster_data.flavor = monster[3]
                monster_data.species = monster[4]
                return monster_data
    else:
        if level == 999:
            selected_monsters = [
                monster for monster in monsters if monster[2] == level * 10
            ]
        else:
            if level > 110:
                level = 100
            min_level = max(1, level - 30)
            max_level = min(110, level + 10)
            selected_monsters = [
                monster for monster in monsters if min_level <= monster[2] <= max_level
            ]

        if not selected_monsters:
            monster_data.name = "Commoner"
            monster_data.image = COMBAT_DUMMY
            monster_data.flavor = "says how did you find me???"
            monster_data.species = "Humanoid"
            return monster_data

        if task_species and random.random() < 0.50:
            task_specific_mobs = [m for m in selected_monsters if m[4] == task_species]
            if task_specific_mobs:
                selected_monsters = task_specific_mobs

        selected_monster = random.choice(selected_monsters)
        monster_data.name = selected_monster[0]
        monster_data.image = selected_monster[1]
        monster_data.flavor = selected_monster[3]
        monster_data.species = selected_monster[4]
        return monster_data


_ESSENCE_SPAWN_CHANCES = {0: 0.0, 1: 0.05, 2: 0.12, 3: 0.22}
_ESSENCE_SPAWN_CHANCE_MAX = 0.35  # 4+ modifiers


def _roll_zenith_spawn(monster, player, slayer_tree_nodes: dict) -> None:
    """5% chance to spawn a Zenith variant when player owns hu_4=zenith tree node.

    Zenith monsters mirror the Calcified pattern: mutated in-place, +100% ATK/DEF,
    flagged with is_zenith=True so victory.py can guarantee the Imbued Heart drop.
    Only triggers on the player's active task species; never on bosses or essence spawns.
    """
    if slayer_tree_nodes.get("hu_4") != "zenith":
        return
    if not getattr(player, "active_task_species", None):
        return
    if monster.species != player.active_task_species:
        return
    if random.random() >= 0.05:
        return
    monster.bonus_attack_pct += 1.0
    monster.bonus_defence_pct += 1.0
    monster.is_zenith = True
    monster.name = f"Zenith {monster.name}"


def _roll_essence_spawn(monster, player_level: int) -> None:
    """Mutates monster in-place if it becomes essence-infused (Calcified).
    Chance scales with modifier count. Requires player level 30+.
    """
    if player_level < 30:
        return
    num_mods = len(monster.modifiers)
    if num_mods == 0:
        return
    chance = _ESSENCE_SPAWN_CHANCES.get(num_mods, _ESSENCE_SPAWN_CHANCE_MAX)
    if random.random() < chance:
        monster.is_essence = True
        monster.name = f"Calcified {monster.name}"


def get_modifier_description(mod) -> str:
    """Returns a human-readable description of a modifier.

    Accepts either:
      - MonsterModifier object (has .name and .value)
      - str (just the modifier name — used by Dojo, etc.)
    """
    if isinstance(mod, str):
        mod_name = mod.strip()
        mod_value = 1.0
    else:
        mod_name = mod.name.strip()
        mod_value = mod.value

    if mod_name == "Ascended":
        return f"Level +{int(mod_value)}"

    defn = MODIFIER_DEFINITIONS.get(mod_name)
    if defn:
        return defn.description(mod_value)
    return ""


def apply_all_corrupted_modifiers(monster, force_tier: int = 2) -> None:
    """Apply every common and rare modifier at the given tier to a corrupted monster.

    Called once during generation — after HP/stats are set and before
    _apply_spawn_modifiers, which reads the modifier list to mutate stats.
    """
    all_names = COMMON_MOD_NAMES + RARE_TIERED_MOD_NAMES
    for name in all_names:
        monster.modifiers.append(
            make_modifier(name, monster.level, force_tier=force_tier)
        )
    # Collapse the wall of individual modifier names into one consolidated
    # display entry — the real MonsterModifier entries above still drive
    # the actual stat math untouched.
    monster.omnipotent_display = omnipotent_label(force_tier)
    monster.omnipotent_names = frozenset(all_names)


# Corrupted monster display names derived from CORRUPTED_MONSTERS keys.
_CORRUPTED_MONSTER_NAMES: list[tuple[str, str]] = [
    (key, "Corrupted " + key.replace("_", " ").title()) for key in CORRUPTED_MONSTERS
]


async def generate_incubated_monster(
    encounter: dict, player_level: int = 50
) -> "Monster":
    """Builds a Monster from a queued incubated encounter row.

    The monster's level, name, and species are taken from the stored egg data.
    Stats are scaled at +20% ATK/DEF. Modifiers scale with player_level
    (1 random mod at level 50, scaling up to 2 boss + 6 random at level 100).
    """
    monster = Monster(
        name=f"[Incubated] {encounter['monster_name']}",
        level=encounter["monster_level"],
        hp=0,
        max_hp=0,
        xp=0,
        attack=0,
        defence=0,
        modifiers=[],
        image="",
        flavor="radiates a feral, half-formed vitality",
        species="Incubated",
    )

    monster = calculate_monster_stats(monster)

    # Phase 2: 20% ATK/DEF amplification via bonus pools
    monster.bonus_attack_pct += 0.20
    monster.bonus_defence_pct += 0.20

    # HP formula mirrors the standard high-level calculation
    monster.base_max_hp = 10 + int(10 * (monster.level**1.65))
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp

    # Dual-write during Phase 2
    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    monster.xp = 1 + monster.level * 100

    # Fetch image from monsters.csv by matching the original name exactly
    monster = await _fetch_incubated_image(encounter["monster_name"], monster)

    monster.is_boss = True
    monster.is_incubated = True
    monster.incubated_encounter_id = encounter["id"]
    monster.incubated_egg_tier = encounter["egg_tier"]

    _assign_incubated_modifiers(monster, player_level)
    _apply_spawn_modifiers(monster)

    return monster


async def _fetch_incubated_image(original_name: str, monster: "Monster") -> "Monster":
    """Tries to match the original monster name in monsters.csv to grab its image."""
    for name, url, _, _, species in _load_monster_rows():
        if name == original_name:
            monster.image = url
            monster.species = species
            return monster
    return monster  # fallback: image stays empty, name already set


def _assign_incubated_modifiers(monster, player_level: int) -> None:
    """Assigns level-scaled boss + random mods at max tier.

    Modifier counts scale every 10 levels starting at 50:
      level 50 → 0 boss, 1 random
      level 60 → 0 boss, 2 random
      level 70 → 0 boss, 3 random
      level 80 → 1 boss, 4 random
      level 90 → 1 boss, 5 random
      level 100+ → 2 boss, 6 random
    """
    clamped = max(50, min(player_level, 100))
    random_count = (clamped - 40) // 10  # 1 at lvl50 … 6 at lvl100
    boss_count = 0
    if clamped >= 100:
        boss_count = 2
    elif clamped >= 80:
        boss_count = 1

    used: set = set()

    boss_candidates = list(BOSS_MOD_NAMES)
    random.shuffle(boss_candidates)
    for name in boss_candidates[:boss_count]:
        monster.modifiers.append(
            make_modifier(name, monster.level, force_max_tier=True)
        )
        used.add(name)

    remaining = random_count
    attempts = 0
    while remaining > 0 and attempts < 80:
        attempts += 1
        pool_type = random.choices(["common", "rare_tiered"], weights=[72, 28], k=1)[0]
        pool = {
            "common": COMMON_MOD_NAMES,
            "rare_tiered": RARE_TIERED_MOD_NAMES,
        }[pool_type]
        candidates = [n for n in pool if n not in used]
        if not candidates:
            continue
        name = random.choice(candidates)
        used.add(name)
        monster.modifiers.append(
            make_modifier(name, monster.level, force_max_tier=True)
        )
        remaining -= 1


def generate_corrupted_encounter(player, monster) -> "Monster":
    """Generate a Corrupted monster encounter.

    Corrupted monsters are post-level-70 elite variants carrying every common
    and rare modifier at max tier. Stats are fixed at player ceiling (no random
    difficulty roll) and HP/attack are heavily amplified.

    Sets monster.is_corrupted = True so downstream loot logic can branch on it.
    """
    key, display_name = random.choice(_CORRUPTED_MONSTER_NAMES)

    monster.level = player.level + player.ascension
    monster = calculate_monster_stats(monster)

    # HP: 2× a normal monster of equivalent level (using base for Phase 2)
    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )
    monster.base_max_hp = int(base_hp * 0.7)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp

    monster.xp = random.randint(1, 9) + monster.level * 100

    monster.name = display_name
    monster.image = CORRUPTED_MONSTERS[key]
    monster.flavor = "radiates a suffocating aura of corruption"
    monster.species = "Corrupted"
    monster.is_boss = False
    monster.is_corrupted = True

    monster.modifiers = []
    apply_all_corrupted_modifiers(monster)
    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)

    return monster


async def generate_uber_lucifer(player, monster):
    """Generate the single-phase Uber Lucifer boss fight. Heavy attack, minimal defence."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.7))
    monster.base_max_hp = int(base_hp * 2)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Lucifer, Infernal Sovereign"
    monster.image = MONSTER_LUCIFER
    monster.flavor = "exudes an overwhelming killing intent"
    monster.species = "Demon"
    monster.is_boss = True

    # Phase 2: Use bonus pools for % adjustments
    monster.bonus_attack_pct += 0.30
    monster.bonus_defence_pct -= 0.70  # 30% of original = -70%

    monster.modifiers = [
        make_modifier("Infernal Protection", monster.level),
        make_modifier("Hell's Fury", monster.level),
    ]

    # Flat additions — bake into base for now (Phase 2)
    monster.base_attack += int(monster.level * 1.0)
    monster.base_defence += int(monster.level * 0.2)

    boss_pool = [n for n in BOSS_MOD_NAMES]
    random.shuffle(boss_pool)
    monster.modifiers.append(make_modifier(boss_pool[0], monster.level))

    _add_uber_random_modifiers(monster)

    finalize_monster_spawn(monster)
    return monster


def generate_uber_neet(player, monster):
    """Generate the single-phase Uber NEET boss fight. High defence, attrition-focused."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.4))
    monster.base_max_hp = int(base_hp * 2)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "NEET, the Void Sovereign"
    monster.image = MONSTER_NEET
    monster.flavor = "radiates an entropic void"
    monster.species = "Void"
    monster.is_boss = True

    monster.modifiers = [
        make_modifier("Void Protection", monster.level),
        make_modifier("Void Aura", monster.level),
    ]

    # Flat additions baked into base (Phase 2)
    monster.base_attack += int(monster.level * 0.8)
    monster.base_defence += int(monster.level * 0.5)

    boss_pool = [n for n in BOSS_MOD_NAMES]
    random.shuffle(boss_pool)
    monster.modifiers.append(make_modifier(boss_pool[0], monster.level))

    _add_uber_random_modifiers(monster)

    finalize_monster_spawn(monster)
    return monster


def generate_uber_gemini(player, monster):
    """Generate the single-phase Uber Gemini Twins boss fight. Perfectly balanced — equal ATK and DEF."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.7))
    monster.base_max_hp = int(base_hp * 2)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Castor & Pollux, Bound Sovereigns"
    monster.image = MONSTER_GEMINI
    monster.flavor = "move in perfect synchrony"
    monster.species = "Celestial"
    monster.is_boss = True

    monster.modifiers = [
        make_modifier("Balanced Protection", monster.level),
        make_modifier("Balanced Strikes", monster.level),
    ]

    monster.base_attack += int(monster.level * 0.65)
    monster.base_defence += int(monster.level * 0.65)

    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    boss_pool = [n for n in BOSS_MOD_NAMES]
    random.shuffle(boss_pool)
    monster.modifiers.append(make_modifier(boss_pool[0], monster.level))

    _add_uber_random_modifiers(monster)

    finalize_monster_spawn(monster)
    return monster


def generate_uber_evelynn(player, monster):
    """Generate the single-phase Evelynn Uber boss fight. All corrupted modifiers + signature ward drain."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.65))
    monster.base_max_hp = int(base_hp * 2)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Evelynn, the Origin of Corruption"
    monster.image = MONSTER_EVELYNN_PRECURSOR
    monster.image2 = MONSTER_EVELYNN
    monster.flavor = "casts a writhing black mass"
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

    # Phase 2: % scaling via bonuses
    monster.bonus_attack_pct += 0.40
    monster.bonus_defence_pct -= 0.15  # results in 85% of base

    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    # No _add_uber_random_modifiers call here: apply_all_corrupted_modifiers
    # above already applies every COMMON_MOD_NAMES + RARE_TIERED_MOD_NAMES
    # entry (at forced tier 5), so there are no unused names left to draw —
    # Evelynn already exceeds the "+5 random" treatment the other bosses get.
    # She previously never ran _apply_spawn_modifiers/finalize_monster_spawn
    # though, so Empowered/Fortified/Titanic/Veiled among that full set were
    # silently inert; run them now so her modifiers actually take effect.
    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    return monster


async def generate_uber_aphrodite(player, monster):
    """Generate the single-phase Uber Aphrodite boss fight."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(10 * (monster.level**1.7))
    monster.base_max_hp = int(base_hp * 4.0)
    monster.hp = monster.base_max_hp
    monster.max_hp = monster.base_max_hp
    monster.xp = 75000

    monster.name = "Aphrodite, Celestial Apex"
    monster.image = MONSTER_APHRODITE
    monster.flavor = "radiates an overwhelming aura"
    monster.species = "Celestial"
    monster.is_boss = True

    monster.modifiers = [make_modifier("Radiant Protection", monster.level)]

    boss_pool = list(BOSS_MOD_NAMES)
    random.shuffle(boss_pool)
    for name in boss_pool[: random.randint(1, 2)]:
        monster.modifiers.append(make_modifier(name, monster.level))

    # Flat additions baked into base
    monster.base_attack += int(monster.level * 0.5)
    monster.base_defence += int(monster.level * 0.5)

    monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    monster.defence = int(monster.base_defence * (1 + monster.bonus_defence_pct))

    _add_uber_random_modifiers(monster)

    finalize_monster_spawn(monster)
    return monster


# =========================================================
# Prestige Gathering Boss Generation (Artisan Mastery Phase 2)
# Rare "treasure boss" encounters for the Synergy capstones.
# =========================================================


async def generate_prestige_golem(player, monster):
    """Meridian Golem — Mining prestige boss. High DR."""
    ref_level = player.level + player.ascension
    monster.level = ref_level
    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )
    monster.base_max_hp = base_hp
    monster.hp = base_hp
    monster.max_hp = base_hp
    monster.xp = random.randint(1, 9) + monster.level * 100

    # Override random monster data with proper boss identity
    monster.name = "Meridian Golem"
    monster.flavor = "stomps and bellows fiercely"
    monster.species = "Golem"
    from core.images import MERIDIAN_GOLEM_FIGHT

    monster.image = MERIDIAN_GOLEM_FIGHT

    monster.modifiers = []
    mod = make_modifier("Meridian Golem DR", monster.level)
    if mod:
        monster.modifiers.append(mod)

    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    monster.is_boss = True
    monster.prestige_boss_type = "golem"
    return monster


async def generate_prestige_leviathan(player, monster):
    """Drowned Leviathan — Fishing prestige boss. True damage bites."""
    ref_level = player.level + player.ascension
    monster.level = ref_level
    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )
    monster.base_max_hp = base_hp
    monster.hp = base_hp
    monster.max_hp = base_hp
    monster.xp = random.randint(1, 9) + monster.level * 100

    # Override random monster data with proper boss identity
    monster.name = "Drowned Leviathan"
    monster.flavor = "bites from impossible depths"
    monster.species = "Leviathan"
    from core.images import DROWNED_LEVIATHAN_FIGHT

    monster.image = DROWNED_LEVIATHAN_FIGHT

    monster.modifiers = []
    mod = make_modifier("Leviathan Bite", monster.level)
    if mod:
        monster.modifiers.append(mod)

    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    monster.is_boss = True
    monster.prestige_boss_type = "leviathan"
    return monster


async def generate_prestige_colossus(player, monster):
    """Verdant Colossus — Woodcutting prestige boss. Snare effect."""
    ref_level = player.level + player.ascension
    monster.level = ref_level
    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )
    monster.base_max_hp = base_hp
    monster.hp = base_hp
    monster.max_hp = base_hp
    monster.xp = random.randint(1, 9) + monster.level * 100

    # Override random monster data with proper boss identity
    monster.name = "Verdant Colossus"
    monster.flavor = "ensnares you with titanic roots"
    monster.species = "Colossus"
    from core.images import VERDANT_COLOSSUS_FIGHT

    monster.image = VERDANT_COLOSSUS_FIGHT

    monster.modifiers = []
    mod = make_modifier("Verdant Snare", monster.level)
    if mod:
        monster.modifiers.append(mod)

    _apply_spawn_modifiers(monster)
    finalize_monster_spawn(monster)
    monster.is_boss = True
    monster.prestige_boss_type = "colossus"
    return monster
