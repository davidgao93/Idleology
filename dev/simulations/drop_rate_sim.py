import random

# Controlled Parameters
user_level = 20  # Change this value for the user's level
player_rar = 50  # Player rarity in percentage (0-100)
encounter_level = 30  # Level of the monster being encountered

# Simulation variables
num_iterations = 1000
drop_results = {
    "accessory": 0,
    "weapon": 0,
    "curio": 0,
    "none": 0
}

# Rare monster determination
def is_rare_monster():
    return random.random() < 0.01  # 1% chance

# Simulation
for _ in range(num_iterations):
    monster_name = "Monster"  # Placeholder, we can ignore specific monster names for this simulation
    rare_monster = is_rare_monster()

    if rare_monster:
        drop_chance = 0
    else:
        drop_chance = 90  # Normal drop chance

    # Simulate loot roll
    loot_roll = random.randint(1, 100)
    final_loot_roll = loot_roll + (10 * (player_rar / 100)) if player_rar > 0 else loot_roll
    
    if final_loot_roll >= drop_chance:  # Normal drop logic
        drop_results["weapon"] += 1
    else:
        if (random.randint(1, 100) >= 95): #5% chance for accessory
            drop_results["accessory"] += 1
        else:
            drop_results["none"] += 1
    if (drop_chance == 0):
        drop_results["curio"] += 1

# Display results
print(f"\nResults after {num_iterations} iterations:")
print(f"Accessory Drops: {drop_results['accessory']}")
print(f"Weapon Drops: {drop_results['weapon']}")
print(f"Curio Drops: {drop_results['curio']}")
print(f"Nothing Drops: {drop_results['none']}")
