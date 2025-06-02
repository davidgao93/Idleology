import random

class Player:
    def __init__(self, rarity, level):
        self.rarity = rarity
        self.level = level

async def generate_weapon(user_id, level, drop_rune=False):
    # Placeholder for weapon generation logic
    return Weapon("Sword of Power", "A powerful sword.")

async def generate_accessory(user_id, level, drop_rune=False):
    # Placeholder for accessory generation logic
    return Accessory("Ring of Strength", "A ring that boosts strength.")

async def generate_armor(user_id, level, drop_rune=False):
    # Placeholder for armor generation logic
    return Armor("Plate Armor", "A sturdy plate armor.")

class Weapon:
    def __init__(self, name, description):
        self.name = name
        self.description = description

class Accessory:
    def __init__(self, name, description):
        self.name = name
        self.description = description

class Armor:
    def __init__(self, name, description):
        self.name = name
        self.description = description

async def simulate_loot(player, iterations=1000):
    loot_results = {"Weapons": 0, "Accessories": 0, "Armors": 0, "None": 0}

    for _ in range(iterations):
        base_drop_chance = 10
        level_bonus = int(0.2 * (100 - player.level))
        drop_chance = base_drop_chance + (player.rarity / 10) + level_bonus
        drop_roll = random.randint(1, 100)
        # print(f"{drop_roll} vs {drop_chance}")
        # Decide if an item is dropped
        if drop_roll <= drop_chance:
            # Weighted item type selection
            item_type_roll = random.randint(1, 100)
            if item_type_roll <= 50:  # 50% chance for weapon
                loot_results['Weapons'] += 1
                weapon = await generate_weapon(user_id=1, level=player.level)
                # print(f"Dropped: Weapon - {weapon.description}")
            elif item_type_roll <= 75:  # 30% chance for accessory
                loot_results['Accessories'] += 1
                acc = await generate_accessory(user_id=1, level=player.level)
                # print(f"Dropped: Accessory - {acc.description}")
            else:  # 20% chance for armor
                loot_results['Armors'] += 1
                armor = await generate_armor(user_id=1, level=player.level)
                # print(f"Dropped: Armor - {armor.description}")
        else:
            loot_results['None'] += 1

    # Print the summary of the loot results
    print(f"\nLoot Simulation Results after {iterations} iterations:")
    for item_type, count in loot_results.items():
        print(f"{item_type}: {count} dropped")

# Example usage
if __name__ == "__main__":
    # Modify these numbers to test different player configurations
    player_rarity = 2500  # Change this value as needed
    player_level = 100   # Change this value as needed

    player = Player(rarity=player_rarity, level=player_level)
    
    import asyncio
    asyncio.run(simulate_loot(player, iterations=100))
