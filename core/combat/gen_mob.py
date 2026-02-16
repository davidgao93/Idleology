import random
import os 
import csv 
from core.models import Monster
from core.util import load_list

def get_monster_mods():
    return load_list("assets/mobs/mods.txt")

def get_boss_mods():
    return load_list("assets/mobs/bossmods.txt")

async def generate_encounter(player, monster, is_treasure):
    """Generate an encounter with a monster based on the user's level."""
    print(f'Generating a monster based off {monster}')
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
        difficulty_multiplier = random.randint(4, 10)
    
    monster.level = random.randint(player.level + player.ascension, player.level + player.ascension + difficulty_multiplier)

    # print('Calculating monster stats')
    monster = calculate_monster_stats(monster)

    if is_treasure:
        monster = await fetch_monster_image(999, monster)
    else:
        monster = await fetch_monster_image(monster.level, monster)

    if player.level == 1:
        monster.hp = 10
    elif player.level > 1 and player.level <= 5:
        monster.hp = max(10, random.randint(1, 4) + int(7 * monster.level))
    else:
        monster.hp = random.randint(0, 9) + int(10 * (monster.level ** random.uniform(1.4, 1.45)))

    monster.max_hp = monster.hp
    monster.xp = monster.max_hp
    # Apply monster modifiers
    monster.modifiers = []
    if not is_treasure:
        modifier_checks = []
        if monster.level > 20:
            modifier_checks.append(10 + int(player.rarity / 10))
        if monster.level > 40:
            modifier_checks.append(15 + int(player.rarity / 10))
        if monster.level > 60:
            modifier_checks.append(20 + int(player.rarity / 10))
        if monster.level > 80:
            modifier_checks.append(25 + int(player.rarity / 10))
        if monster.level >= 100:
            modifier_checks.append(50 + int(player.rarity / 10))

        available_modifiers = get_monster_mods()
        
        for chance in modifier_checks:
            if random.randint(1, 100) <= chance and available_modifiers:
                modifier = random.choice(available_modifiers)
                monster.modifiers.append(modifier)
                available_modifiers.remove(modifier)  # Ensure no duplicate modifiers
                print(f"Added modifier: {modifier}")

        if "Built-different" in monster.modifiers:
            monster.level += 2
            monster = calculate_monster_stats(monster)

        if "Ascended" in monster.modifiers:
            monster.attack += 10
            monster.defence += 10
            print(f"Ascended modifier applied: m.atk/m.def +10")

        # Apply Steel-born modifier
        if "Steel-born" in monster.modifiers:
            monster.defence = int(monster.defence * 1.1)
            print(f"Steel-born modifier applied: Monster defence increased to {monster.defence}")
        
        if "Mighty" in monster.modifiers:
            monster.attack = int(monster.attack * 1.1)

        if "Glutton" in monster.modifiers:
            monster.hp *= 2
            print(f"Glutton modifier applied: Monster HP doubled to {monster.hp}")

    return monster


async def generate_boss(player, monster, phase, phase_index):
    """Generate a boss with a phase based on the user's level."""
    print(f'Generating a boss based on {phase}')
    difficulty_multiplier = int(player.level / 15)
    
    monster.level = player.level + player.ascension + difficulty_multiplier + phase_index

    monster = calculate_monster_stats(monster)
    monster = await fetch_monster_image(phase["level"], monster)

    monster.hp = random.randint(0, 9) + int(10 * (monster.level ** random.uniform(1.25, 1.35)))
    monster.hp = int(monster.hp * phase["hp_multiplier"])
    monster.max_hp = monster.hp
    monster.xp = monster.hp

    available_modifiers = get_monster_mods()
    available_modifiers.remove("Glutton")
    available_modifiers.remove("Built-different")
    monster.modifiers = []
    if ('Lucifer' in phase["name"]):
        boss_modifiers = get_boss_mods()
        boss_mod = random.choice(boss_modifiers)
        if (boss_mod == "Celestial Watcher"):
            available_modifiers.remove("All-seeing")
            available_modifiers.remove("Venomous")
        elif (boss_mod == "Unlimited Blade Works"):
            available_modifiers.remove("Mirror Image")
        elif (boss_mod == "Hell's Fury"):
            available_modifiers.remove("Strengthened")
        elif (boss_mod == "Hell's Precision"):
            available_modifiers.remove("Hellborn")
        elif (boss_mod == "Absolute"):
            available_modifiers.remove("Ascended")
        elif (boss_mod == "Infernal Legion"):
            available_modifiers.remove("Summoner")
        monster.modifiers.append(boss_mod)
        print(monster)

    if ('NEET' in phase["name"]):
        boss_modifiers = get_boss_mods()
        for _ in range(phase["modifiers_count"]):
            if available_modifiers:
                boss_mod = random.choice(boss_modifiers)
                monster.modifiers.append(boss_mod)
                boss_modifiers.remove(boss_mod)

    for _ in range(phase["modifiers_count"]):
        if available_modifiers:
            modifier = random.choice(available_modifiers)
            monster.modifiers.append(modifier)
            available_modifiers.remove(modifier)
    print(monster)
            
    if "Absolute" in monster.modifiers:
        monster.attack += 25
        monster.defence += 25

    if "Ascended" in monster.modifiers:
        monster.attack += 10
        monster.defence += 10

    if "Steel-born" in monster.modifiers:
        monster.defence = int(monster.defence * 1.1)

    if "Mighty" in monster.modifiers:
        monster.attack = int(monster.attack * 1.1)
    return monster


async def generate_ascent_monster(player, monster_instance, ascent_stage_level, num_normal_mods, num_boss_mods):
    """Generates a monster for the ascent mode."""
    monster = monster_instance
    monster.level = ascent_stage_level # This is the base level for the stage

    # Calculate initial stats based on the stage level
    # We use a temporary monster object for stat calculation to avoid altering monster.level if "Built-different" applies
    temp_monster_for_stats = Monster(name="", level=monster.level, hp=0,max_hp=0,xp=0,attack=0,defence=0,modifiers=[],image="",flavor="")
    temp_monster_for_stats = calculate_monster_stats(temp_monster_for_stats)
    monster.attack = temp_monster_for_stats.attack
    monster.defence = temp_monster_for_stats.defence

    # Fetch image, name, and flavor text using the stage level
    monster = await fetch_monster_image(random.randint(20,120), monster)

    # HP Calculation based on stage level
    monster.hp = random.randint(0, 9) + int(10 * (monster.level ** random.uniform(1.3, 1.4)))
    
    monster.max_hp = monster.hp
    monster.xp = int(monster.max_hp * (1 + ascent_stage_level / 50)) # XP scales with stage level

    monster.modifiers = []
    
    # Apply Normal Modifiers
    all_normal_mods = get_monster_mods()
    available_normal_mods = [m for m in all_normal_mods] # Create a mutable copy
    random.shuffle(available_normal_mods) 

    count_normal_applied = 0
    while count_normal_applied < num_normal_mods and available_normal_mods:
        modifier = available_normal_mods.pop(0)
        monster.modifiers.append(modifier)
        count_normal_applied += 1
        
    # Apply Boss Modifiers
    all_boss_mods = get_boss_mods()
    # Ensure boss mods are not already present if they can also be normal mods
    available_boss_mods = [m for m in all_boss_mods if m not in monster.modifiers] 
    random.shuffle(available_boss_mods)

    count_boss_applied = 0
    while count_boss_applied < num_boss_mods and available_boss_mods:
        modifier = available_boss_mods.pop(0)
        monster.modifiers.append(modifier) # Assumes boss mods are distinct enough or effects are additive
        count_boss_applied +=1

    # Apply effects of chosen modifiers
    # Handle "Built-different" first as it affects stat calculation level
    effective_stat_level = monster.level # Start with the base stage level
    if "Built-different" in monster.modifiers:
        effective_stat_level += 2
        # Recalculate attack/defense based on this effective level
        temp_monster_for_stats.level = effective_stat_level
        temp_monster_for_stats = calculate_monster_stats(temp_monster_for_stats)
        monster.attack = temp_monster_for_stats.attack
        monster.defence = temp_monster_for_stats.defence
        print(f"Built-different modifier applied: m.atk/m.def recalculated for effective level {effective_stat_level}")

    # Apply other stat-modifying effects on top of (potentially) recalculated stats
    if "Ascended" in monster.modifiers:
        monster.attack += 10
        monster.defence += 10
        print(f"Ascended modifier applied: m.atk/m.def +10")
    
    if "Absolute" in monster.modifiers: # Typically a boss mod
        monster.attack += 25
        monster.defence += 25
        print(f"Absolute modifier applied: m.atk/m.def +25")

    if "Steel-born" in monster.modifiers:
        monster.defence = int(monster.defence * 1.1)
        print(f"Steel-born modifier applied: Monster defence increased to {monster.defence}")
    
    if "Mighty" in monster.modifiers:
        monster.attack = int(monster.attack * 1.1)
        print(f"Mighty modifier applied: Monster attack increased to {monster.attack}")

    # Glutton applies to HP calculated from STAGE level, after other HP calculations
    if "Glutton" in monster.modifiers:
        monster.hp = int(monster.hp * 2) 
        monster.max_hp = monster.hp # Ensure max_hp matches
        print(f"Glutton modifier applied: Monster HP doubled to {monster.hp}")

    monster.is_boss = True # Ascent monsters are considered bosses
    return monster


def calculate_monster_stats(monster):
    if monster.level < 5:
        base_attack = monster.level
        base_defence = monster.level
    elif monster.level >= 5 and monster.level <= 20:
        base_attack = monster.level ** random.uniform(1.1, 1.2)
        base_defence = monster.level ** random.uniform(1.1, 1.2)
    elif monster.level > 20 and monster.level <= 40:
        base_attack = monster.level ** random.uniform(1.25, 1.26)
        base_defence = monster.level ** random.uniform(1.25, 1.26)
    elif monster.level > 40 and monster.level <= 50:
        base_attack = monster.level ** random.uniform(1.26, 1.27)
        base_defence = monster.level ** random.uniform(1.26, 1.27)
    elif monster.level > 50 and monster.level <= 60:
        base_attack = monster.level ** random.uniform(1.27, 1.28)
        base_defence = monster.level ** random.uniform(1.27, 1.28)
    elif monster.level > 60 and monster.level <= 70:
        base_attack = monster.level ** random.uniform(1.28, 1.29)
        base_defence = monster.level ** random.uniform(1.28, 1.29)
    elif monster.level > 70 and monster.level <= 80:
        base_attack = monster.level ** random.uniform(1.29, 1.3)
        base_defence = monster.level ** random.uniform(1.29, 1.3)
    elif monster.level > 80 and monster.level <= 90:
        base_attack = monster.level ** random.uniform(1.3, 1.31)
        base_defence = monster.level ** random.uniform(1.3, 1.31)
    elif monster.level > 90 and monster.level <= 100:
        base_attack = monster.level ** random.uniform(1.3, 1.31)
        base_defence = monster.level ** random.uniform(1.3, 1.31)
    elif monster.level > 100 and monster.level <= 110:
        base_attack = monster.level ** random.uniform(1.32, 1.33)
        base_defence = monster.level ** random.uniform(1.32, 1.33)
    else:
        base_attack = monster.level ** random.uniform(1.34, 1.35)
        base_defence = monster.level ** random.uniform(1.34, 1.35)

    monster.attack = int(base_attack)
    monster.defence = int(base_defence)
    
    return monster

async def fetch_monster_image(level, monster_data):
    """Fetches a monster image from the monsters.csv file based on the encounter level."""
    csv_file_path = os.path.join(os.path.dirname(__file__), '../../assets/monsters.csv')
    monsters = []
    try:
        with open(csv_file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                monster_name = row['name']
                monster_url = row['url']
                monster_level = int(row['level']) * 10
                flavor_txt = row['flavor']
                monster_species = row.get('species', monster_name) 
                monsters.append((monster_name, monster_url, monster_level, flavor_txt, monster_species))
    except Exception as e:
        print(f"Error reading monsters.csv: {e}")
        monster_data.name = "Commoner"
        monster_data.image = "https://i.imgur.com/v1BrB1M.png"
        monster_data.flavor = "stares pleadingly at"
        monster_data.species = "Humanoid"
        return monster_data
    
    if 444 <= level <= 888:
        for monster in monsters:
            if (monster[2] == level * 10):
                print('Monster matched')
                monster_data.name = monster[0]
                monster_data.image = monster[1]
                monster_data.flavor = monster[3]
                monster_data.species = monster[4]
                return monster_data
    else:
        if level == 999:
            selected_monsters = [monster for monster in monsters if monster[2] == level * 10]
        else:
            if level > 110:
                level = 100
            min_level = max(1, level - 20)
            max_level = min(110, level + 10)
            selected_monsters = [monster for monster in monsters if min_level <= monster[2] <= max_level]

        if not selected_monsters:
            monster_data.name = "Commoner"
            monster_data.image = "https://i.imgur.com/v1BrB1M.png"
            monster_data.flavor = "says how did you find me???"
            monster_data.species = "Humanoid"
            return monster_data

        selected_monster = random.choice(selected_monsters)
        monster_data.name = selected_monster[0]
        monster_data.image = selected_monster[1]
        monster_data.flavor = selected_monster[3]
        monster_data.species = selected_monster[4]
        return monster_data
        
    
def get_modifier_description(modifier):
    """Helper method to get modifier descriptions."""
    descriptions = {
        "Steel-born": "10% boost to defence",
        "All-seeing": "10% boost to accuracy",
        "Mirror Image": "20% to deal double damage",
        "Glutton": "2x HP",
        "Enfeeble": "Decrease player's attack by 10%",
        "Venomous": "Aura deals 1 damage on every miss",
        "Strengthened": "+3 max hit",
        "Hellborn": "+2 to all hits",
        "Lucifer-touched": "50% lucky attacks",
        "Titanium": "Reduce incoming damage by 10%",
        "Ascended": "+10 Attack, +10 Defence",
        "Summoner": "Has minions that deal 33% damage",
        "Shield-breaker": "Disables ward at start of combat",
        "Impenetrable": "Base crit immunity",
        "Unblockable": "Cannot be blocked",
        "Unavoidable": "Cannot be evaded",
        "Built-different": "+2 to level",
        "Multistrike": "Landing a hit rolls another (50% damage)",
        "Mighty": "10% boost to attack",
        "Shields-up": "Block 10% of all attacks",
        "Executioner": "1% chance to deal 90% of remaining HP",
        "Time Lord": "80% chance to not die",
        "Suffocator": "20% for player hits to be unlucky",
        "Penetrator": "Ignores 20% of Percentage Damage Reduction",
        "Clobberer": "Ignores 5 Flat Damage Reduction",
        "Smothering": "Critical hit damage is reduced by 20%",
        "Dodgy": "Evasion increased by 10%",
        "Prescient": "10% more likely to hit",
        "Vampiric": "Heals for 10 times damage dealt",
        "Celestial Watcher": "Never miss (boss)", # Start boss list here
        "Unlimited Blade Works": "Double damage (boss)",
        "Hell's Fury": "+5 each successful hit (boss)",
        "Absolute": "+25 Attack, +25 defence (boss)",
        "Infernal Legion": "Has minions that echo hits (boss)",
        }
    return descriptions.get(modifier, "") 