import random

# Controlled Parameters
monster_name = "Goblin"  # Change this to simulate different monsters
rare_monsters = ["Dragon", "Phoenix"]  # List of rare monsters
user_level = 20  # Change this value for the user's level
award_xp = 100  # Base XP awarded for defeating the monster
player_rar = 50  # Player rarity in percentage (0-100)
encounter_level = 30  # Level of the monster being encountered
accessory_passive = "Prosper"  # Possible options: 'Prosper', 'Infinite Wisdom', or None
accessory_lvl = 3  # Level of the accessory

# Simulation Logic
if monster_name in rare_monsters:
    drop_chance = 0
    xp_award = 0
    reward_scale = int(user_level / 10)  # Bonus rewards based on level differential
else:
    drop_chance = 90  # Normal drop chance
    xp_award = int(award_xp * 1.4)
    reward_scale = (encounter_level - user_level) / 10  # Bonus rewards based on level differential

rarity = player_rar / 100  # Player rarity
loot_roll = random.randint(1, 100)
final_loot_roll = loot_roll
if player_rar > 0:
    final_loot_roll = int(loot_roll + (10 * rarity))
    print(f'User has {rarity:.2f}, multiplier on {loot_roll} to {final_loot_roll}')

print(f'User rolls {final_loot_roll}, beat {drop_chance} to get item')
gold_award = int((encounter_level ** random.uniform(1.4, 1.6)) * (1 + (reward_scale ** 1.3)))
if player_rar > 0:
    final_gold_award = int(gold_award * (1.5 + rarity))
else:
    final_gold_award = gold_award

# Apply accessory passives
if accessory_passive == "Prosper":
    double_gold_chance = (accessory_lvl * 5)
    if random.randint(1, 100) <= double_gold_chance:
        print(f'Original gold award: {final_gold_award}')
        final_gold_award *= 2
        print(f'New gold award: {final_gold_award}')
elif accessory_passive == "Infinite Wisdom":
    double_exp_chance = (accessory_lvl * 5)
    if random.randint(1, 100) <= double_exp_chance:
        print(f'Original xp award: {xp_award}')
        xp_award *= 2
        print(f'New xp award: {xp_award}')

# Final Results Display 
print(f'📚 Experience Earned: {xp_award:,} XP')
print(f'💰 Gold Earned: {final_gold_award:,} GP')

if final_loot_roll >= drop_chance:  # Normal drop logic
    print("✨ Loot: You received an item!")
    # You would generally put item generation logic here.
else:
    print("✨ Loot: None")
