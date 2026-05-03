import csv
import os
import random

from core.combat.modifier_data import (
    BOSS_MOD_NAMES,
    COMMON_MOD_NAMES,
    MODIFIER_DEFINITIONS,
    RARE_FLAT_MOD_NAMES,
    RARE_TIERED_MOD_NAMES,
    make_modifier,
)
from core.models import Monster, MonsterModifier


async def generate_encounter(player, monster, is_treasure, task_species=None):
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

    if player.level == 1:
        monster.hp = 10
    elif player.level > 1 and player.level <= 10:
        monster.hp = max(10, random.randint(1, 4) + int(7 * monster.level))
    else:
        monster.hp = random.randint(0, 9) + int(
            10 * (monster.level ** random.uniform(1.6, 1.7))
        )

    monster.max_hp = monster.hp
    monster.xp = random.randint(1,9) + monster.level * 100

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

        num_mods = sum(1 for chance in modifier_checks if random.randint(1, 100) <= chance)
        if num_mods > 0:
            _assign_modifiers(monster, num_mods, is_boss=False)
            _apply_spawn_modifiers(monster)
        _roll_essence_spawn(monster)

    print(monster)
    return monster


async def generate_boss(player, monster, phase, phase_index):
    """Generate a boss with a phase based on the user's level."""
    print(f"Generating a boss based on {phase}")
    difficulty_multiplier = int(player.level / 5)

    monster.level = (
        player.level + player.ascension + difficulty_multiplier + phase_index
    )

    monster = calculate_monster_stats(monster)
    monster = await fetch_monster_image(phase["level"], monster)

    monster.hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )
    monster.hp = int(monster.hp * phase["hp_multiplier"])
    monster.max_hp = monster.hp
    monster.xp = random.randint(1,9) + monster.level * 100

    monster.modifiers = []
    _assign_modifiers(monster, phase["modifiers_count"], is_boss=True, force_max_tier=True)
    _apply_spawn_modifiers(monster)
    print(monster)
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
    monster.defence = temp_monster_for_stats.defence

    monster = await fetch_monster_image(random.randint(30, 120), monster)

    monster.hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )

    monster.max_hp = monster.hp
    monster.xp = int(
        monster.max_hp * (1 + ascent_stage_level / 50)
    )

    monster.modifiers = []
    total_mods = num_normal_mods + num_boss_mods
    _assign_ascent_modifiers(monster, total_mods, floor=ascent_stage_level)
    _apply_spawn_modifiers(monster)
    monster.is_boss = True
    return monster


def _pick_modifier_type(is_boss: bool) -> str:
    """Returns 'common', 'rare_tiered', 'rare_flat', or 'boss'."""
    if is_boss:
        weights = [55, 20, 10, 15]  # common, rare_tiered, rare_flat, boss
    else:
        weights = [75, 15, 10, 0]   # regular monsters never get boss mods
    return random.choices(["common", "rare_tiered", "rare_flat", "boss"], weights=weights, k=1)[0]


def _assign_modifiers(monster, num_mods: int, is_boss: bool, force_max_tier: bool = False) -> None:
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
        elif pool_type == "rare_flat":
            candidates = [n for n in RARE_FLAT_MOD_NAMES if n not in used_names]
        else:
            candidates = [n for n in BOSS_MOD_NAMES if n not in used_names]
        if not candidates:
            continue
        name = random.choice(candidates)
        used_names.add(name)
        monster.modifiers.append(make_modifier(name, monster.level, force_max_tier=force_max_tier))


def _assign_ascent_modifiers(monster, num_mods: int, floor: int) -> None:
    """Ascent variant: guarantees at least floor//10 boss mods."""
    min_boss = min(floor // 10, len(BOSS_MOD_NAMES))
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
        pool_type = random.choices(
            ["common", "rare_tiered", "rare_flat"],
            weights=[65, 20, 15],
            k=1
        )[0]
        candidates = {
            "common": COMMON_MOD_NAMES,
            "rare_tiered": RARE_TIERED_MOD_NAMES,
            "rare_flat": RARE_FLAT_MOD_NAMES,
        }[pool_type]
        candidates = [n for n in candidates if n not in used_names]
        if candidates:
            name = random.choice(candidates)
            used_names.add(name)
            monster.modifiers.append(make_modifier(name, monster.level))
            remaining -= 1


def _apply_spawn_modifiers(monster) -> None:
    """Apply modifiers that mutate monster stats at spawn time."""
    if monster.has_modifier("Ascended"):
        level_added = int(monster.get_modifier_value("Ascended"))
        monster.level += level_added
        monster = calculate_monster_stats(monster)
    if monster.has_modifier("Empowered"):
        monster.attack = int(monster.attack * (1 + monster.get_modifier_value("Empowered")))
    if monster.has_modifier("Fortified"):
        monster.defence = int(monster.defence * (1 + monster.get_modifier_value("Fortified")))
    if monster.has_modifier("Titanic"):
        monster.hp = int(monster.hp * monster.get_modifier_value("Titanic"))
        monster.max_hp = monster.hp
    if monster.has_modifier("Veiled"):
        monster.ward = int(monster.max_hp * monster.get_modifier_value("Veiled"))


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
    if monster.level < 5:
        base_attack = base_defence = monster.level
    else:
        exp_a = level_exponent(monster.level)
        exp_b = level_exponent(monster.level)
        base_attack = monster.level**exp_a
        base_defence = monster.level**exp_b

    monster.attack = int(base_attack)
    monster.defence = int(base_defence)
    return monster


async def fetch_monster_image(level, monster_data, task_species=None):
    """Fetches a monster image from the monsters.csv file based on the encounter level."""
    csv_file_path = os.path.join(os.path.dirname(__file__), "../../assets/monsters.csv")
    monsters = []
    try:
        with open(csv_file_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                monster_name = row["name"]
                monster_url = row["url"]
                monster_level = int(row["level"]) * 10
                flavor_txt = row["flavor"]
                monster_species = row.get("species", monster_name)
                monsters.append(
                    (
                        monster_name,
                        monster_url,
                        monster_level,
                        flavor_txt,
                        monster_species,
                    )
                )
    except Exception as e:
        print(f"Error reading monsters.csv: {e}")
        monster_data.name = "Commoner"
        monster_data.image = "https://i.imgur.com/v1BrB1M.png"
        monster_data.flavor = "stares pleadingly at"
        monster_data.species = "Humanoid"
        return monster_data

    if 444 <= level <= 888:
        for monster in monsters:
            if monster[2] == level * 10:
                print("Monster matched")
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
            min_level = max(1, level - 20)
            max_level = min(110, level + 10)
            selected_monsters = [
                monster for monster in monsters if min_level <= monster[2] <= max_level
            ]

        if not selected_monsters:
            monster_data.name = "Commoner"
            monster_data.image = "https://i.imgur.com/v1BrB1M.png"
            monster_data.flavor = "says how did you find me???"
            monster_data.species = "Humanoid"
            return monster_data

        if task_species and random.random() < 0.50:
            task_specific_mobs = [
                m for m in selected_monsters if m[4] == task_species
            ]
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


def _roll_essence_spawn(monster) -> None:
    """Mutates monster in-place if it becomes essence-infused (Calcified).
    Chance scales with modifier count.
    """
    num_mods = len(monster.modifiers)
    if num_mods == 0:
        return
    chance = _ESSENCE_SPAWN_CHANCES.get(num_mods, _ESSENCE_SPAWN_CHANCE_MAX)
    if random.random() < chance:
        monster.is_essence = True
        monster.name = f"Calcified {monster.name}"


def get_modifier_description(mod: MonsterModifier) -> str:
    """Returns a human-readable description of a MonsterModifier."""
    descriptions = {
        "Empowered":    lambda v: f"+{int(v*100)}% attack",
        "Fortified":    lambda v: f"+{int(v*100)}% defence",
        "Titanic":      lambda v: f"{int(v*100)}% HP",
        "Savage":       lambda v: f"+{int(v*100)}% damage",
        "Lethal":       lambda v: f"+{int(v*100)}% crit chance",
        "Devastating":  lambda v: f"Crits deal {round(2.0+v, 1)}× damage",
        "Keen":         lambda v: f"+{int(v)} to hit rolls",
        "Blinding":     lambda v: f"−{int(v)} to your hit rolls",
        "Jinxed":       lambda v: f"{int(v*100)}% chance your hit rolls are unlucky",
        "Crushing":     lambda v: f"Ignores {int(v*100)}% of your PDR",
        "Searing":      lambda v: f"Ignores {int(v*100)}% of your FDR",
        "Stalwart":     lambda v: f"Nullifies {int(v*100)}% of incoming damage",
        "Ironclad":     lambda v: f"{int(v*100)}% less damage taken",
        "Vampiric":     lambda v: f"Heals {int(v*100)}% max HP per hit",
        "Mending":      lambda v: f"Heals {int(v*100)}% max HP every other turn",
        "Thorned":      lambda v: f"You take {int(v*100)}% of max HP on each hit",
        "Venomous":     lambda v: f"You take {int(v*100)}% of max HP on each miss",
        "Enraged":      lambda v: f"+{int(v*100)}% ATK per 25% HP lost",
        "Parching":     lambda v: f"Your potions heal {int(v*100)}% less",
        "Veiled":       lambda v: f"Starts with {int(v*100)}% max HP as ward",
        "Ascended":     lambda v: f"Level +{int(v)}",
        "Commanding":   lambda v: f"Minions echo {int(v*100)}% of each hit",
        "Dampening":    lambda v: f"Your crit chance −{int(v)}",
        "Nullifying":   lambda v: f"Your crits deal {int(v*100)}% less damage",
        "Unblockable":  lambda v: "Block chance 80% less effective",
        "Unavoidable":  lambda v: "Evasion chance 80% less effective",
        "Dispelling":   lambda v: "Reduces your ward by 80% at combat start",
        "Multistrike":  lambda v: "50% chance to strike twice",
        "Spectral":     lambda v: "20% chance to deal double damage",
        "Executioner":  lambda v: "1% chance to deal 90% of your HP as damage",
        "Time Lord":    lambda v: "80% chance to survive a killing blow",
        "Overwhelming": lambda v: "Double damage; −25 to accuracy",
        "Inevitable":   lambda v: "Always hits; 50% damage",
        "Sundering":    lambda v: "25% of damage bypasses your ward",
        "Unerring":     lambda v: "Hit rolls always take the highest of two",
        "Radiant Protection":  lambda v: "60% damage reduction",
        "Infernal Protection": lambda v: "60% damage reduction",
        "Balanced Protection": lambda v: "60% damage reduction",
        "Void Protection":     lambda v: "60% damage reduction",
        "Hell's Fury":         lambda v: "Deals triple damage",
        "Void Aura":           lambda v: "Drains 0.5% ATK and DEF per round",
        "Balanced Strikes":    lambda v: "Every other turn: 50% hit, bypasses ward",
    }
    fn = descriptions.get(mod.name)
    if fn:
        return fn(mod.value)
    return ""


async def generate_uber_lucifer(player, monster):
    """Generate the single-phase Uber Lucifer boss fight. Heavy attack, minimal defence."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** 1.7)
    )
    monster.hp = int(base_hp * 2)
    monster.max_hp = monster.hp
    monster.xp = 75000

    monster.name = "Lucifer, Infernal Sovereign"
    monster.image = "https://i.imgur.com/FsK30xp.jpeg"
    monster.flavor = "exudes an overwhelming killing intent"
    monster.species = "Demon"
    monster.is_boss = True

    monster.attack = int(monster.attack * 1.3)
    monster.defence = int(monster.defence * 0.3)

    monster.modifiers = [
        make_modifier("Infernal Protection", monster.level),
        make_modifier("Hell's Fury", monster.level),
    ]

    monster.attack += int(monster.level * 1.0)
    monster.defence += int(monster.level * 0.2)

    boss_pool = [n for n in BOSS_MOD_NAMES]
    random.shuffle(boss_pool)
    monster.modifiers.append(make_modifier(boss_pool[0], monster.level))

    return monster


def generate_uber_neet(player, monster):
    """Generate the single-phase Uber NEET boss fight. High defence, attrition-focused."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** 1.4)
    )
    monster.hp = int(base_hp * 2)
    monster.max_hp = monster.hp
    monster.xp = 75000

    monster.name = "NEET, the Void Sovereign"
    monster.image = "https://i.imgur.com/o8e56uN.jpeg"
    monster.flavor = "radiates an entropic void"
    monster.species = "Void"
    monster.is_boss = True

    monster.modifiers = [
        make_modifier("Void Protection", monster.level),
        make_modifier("Void Aura", monster.level),
    ]

    monster.attack += int(monster.level * 0.8)
    monster.defence += int(monster.level * 0.5)

    boss_pool = [n for n in BOSS_MOD_NAMES]
    random.shuffle(boss_pool)
    monster.modifiers.append(make_modifier(boss_pool[0], monster.level))

    return monster


def generate_uber_gemini(player, monster):
    """Generate the single-phase Uber Gemini Twins boss fight. Perfectly balanced — equal ATK and DEF."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** 1.7)
    )
    monster.hp = int(base_hp * 2)
    monster.max_hp = monster.hp
    monster.xp = 75000

    monster.name = "Castor & Pollux, Bound Sovereigns"
    monster.image = "https://i.imgur.com/tCvDbCn.jpeg"
    monster.flavor = "move in perfect synchrony"
    monster.species = "Celestial"
    monster.is_boss = True

    monster.modifiers = [
        make_modifier("Balanced Protection", monster.level),
        make_modifier("Balanced Strikes", monster.level),
    ]

    monster.attack += int(monster.level * 0.65)
    monster.defence += int(monster.level * 0.65)

    boss_pool = [n for n in BOSS_MOD_NAMES]
    random.shuffle(boss_pool)
    monster.modifiers.append(make_modifier(boss_pool[0], monster.level))

    return monster


async def generate_uber_aphrodite(player, monster):
    """Generate the single-phase Uber Aphrodite boss fight."""
    ref_level = player.level + player.ascension + 20
    monster.level = ref_level

    monster = calculate_monster_stats(monster)

    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** 1.7)
    )
    monster.hp = int(base_hp * 4.0)
    monster.max_hp = monster.hp
    monster.xp = 75000

    monster.name = "Aphrodite, Celestial Apex"
    monster.image = "https://i.imgur.com/je9CVKH.jpeg"
    monster.flavor = "radiates an overwhelming aura"
    monster.species = "Celestial"
    monster.is_boss = True

    monster.modifiers = [make_modifier("Radiant Protection", monster.level)]

    boss_pool = list(BOSS_MOD_NAMES)
    random.shuffle(boss_pool)
    for name in boss_pool[:random.randint(1, 2)]:
        monster.modifiers.append(make_modifier(name, monster.level))

    monster.attack += int(monster.level * 0.5)
    monster.defence += int(monster.level * 0.5)

    return monster
