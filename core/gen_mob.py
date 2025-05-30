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
    # print('Generating a monster')
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
    else:
        difficulty_multiplier = random.randint(3, 6)
    
    monster.level = random.randint(player.level, player.level + difficulty_multiplier)

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
    else:
        base_attack = monster.level ** random.uniform(1.29, 1.3)
        base_defence = monster.level ** random.uniform(1.29, 1.3)

    monster.attack = int(base_attack)
    monster.defence = int(base_defence)
    
    return monster

async def fetch_monster_image(level, monster_data):
    """Fetches a monster image from the monsters.csv file based on the encounter level."""
    csv_file_path = os.path.join(os.path.dirname(__file__), '../assets/monsters.csv')
    monsters = []
    try:
        with open(csv_file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                monster_name = row['name']
                monster_url = row['url']
                monster_level = int(row['level']) * 10
                flavor_txt = row['flavor']
                monsters.append((monster_name, monster_url, monster_level, flavor_txt))
    except Exception as e:
        print(f"Error reading monsters.csv: {e}")
        return "Commoner", "https://i.imgur.com/v1BrB1M.png", "stares pleadingly at"
    
    if 663 <= level <= 888:
        for monster in monsters:
            if (monster[2] == level * 10):
                print('Monster matched')
                monster_data.name = monster[0]
                monster_data.image = monster[1]
                monster_data.flavor = monster[3]
                return monster_data
    else:
        if level == 999:
            selected_monsters = [monster for monster in monsters if monster[2] == level * 10]
        else:
            min_level = max(1, level - 10)
            max_level = min(100, level + 10)
            selected_monsters = [monster for monster in monsters if min_level <= monster[2] <= max_level]

        if not selected_monsters:
            monster_data.name = "Commoner"
            monster_data.image = "https://i.imgur.com/v1BrB1M.png"
            monster_data.flavor = "says how did you find me???"
            return monster_data

        selected_monster = random.choice(selected_monsters)
        monster_data.name = selected_monster[0]
        monster_data.image = selected_monster[1]
        monster_data.flavor = selected_monster[3]
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
        "Shield-breaker": "Disables ward",
        "Impenetrable": "Crit immunity",
        "Unblockable": "Cannot be blocked",
        "Unavoidable": "Cannot be evaded",
        "Built-different": "+2 to level",
        "Multistrike": "Landing a hit rolls another (50% damage)",
        "Mighty": "10% boost to attack",
        "Shields-up": "Block 10% of all attacks",
        "Executioner": "1% chance to deal 90% of remaining HP",
        "Time Lord": "80% chance to not die",
        "Suffocator": "20% for player hits to be unlucky",
        "Celestial Watcher": "Never miss",
        "Unlimited Blade Works": "Double damage",
        "Hell's Fury": "+5 each successful hit",
        "Absolute": "+25 Attack, +25 defence",
        "Infernal Legion": "Has minions that echo hits",
        "Overwhelm" : "Disables ward, cannot be blocked, cannot be evaded",
        "Temporal Bubble": "Player's weapon passive is disabled"
    }
    return descriptions.get(modifier, "") 