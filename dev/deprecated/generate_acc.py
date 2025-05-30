import random

# Assuming `generate_accessory` is defined within a class, let's create a mock class
class MockGame:
    def __init__(self):
        self.prefixes = ["Ancient", "Mystic", "Shiny", "Cursed"]
        self.accessory_types = ["Amulet", "Ring", "Bracelet", "Necklace"]
        self.suffixes = ["of Power", "of Wisdom", "of Agility", "of Protection"]

    async def generate_accessory(self, user_id: str, server_id: str, encounter_level: int) -> str:
        """Generate a unique accessory item."""
        prefix = random.choice(self.prefixes)
        accessory_type = random.choice(self.accessory_types)
        suffix = random.choice(self.suffixes)
        acc_name = f"{prefix} {accessory_type} {suffix}"

        modifiers = []
        attack_modifier = 0
        defence_modifier = 0
        rarity_modifier = 0
        randroll = random.randint(0, 100)

        if randroll <= 18:  # 18% chance for attack roll
            attack_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
            modifiers.append(f"+{attack_modifier} Attack")
        elif randroll > 18 and randroll <= 36:  # 18% chance for defense roll
            defence_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
            modifiers.append(f"+{defence_modifier} Defence")
        elif randroll > 36 and randroll <= 54:
            rarity_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5))) * 5
            modifiers.append(f"+{rarity_modifier}% Rarity")
        elif randroll > 54 and randroll <= 72:
            rarity_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5))) * 2
            modifiers.append(f"+{rarity_modifier}% Ward")
        elif randroll > 72 and randroll <= 90:
            rarity_modifier = max(1, random.randint(int(encounter_level // 10), int(encounter_level // 9)))
            modifiers.append(f"+{rarity_modifier}% Crit")

        loot_description = acc_name + f"\n"
        if modifiers:
            loot_description += f"\n".join(modifiers)
        else:
            # Award the Rune of Potential if there are no modifiers
            loot_description = "**Rune of Potential**!"
            acc_name = "rune"
            
        return acc_name, loot_description

# Main testing function
import asyncio

async def main():
    game = MockGame()
    user_id = "test_user"
    server_id = "test_server"
    encounter_level = 60  # Example level to use in testing

    results = []
    for _ in range(20):
        acc_name, loot_description = await game.generate_accessory(user_id, server_id, encounter_level)
        results.append((acc_name, loot_description))

    # Displaying results
    for index, (name, description) in enumerate(results):
        print(f"Loot #{index + 1}:\nName: {name}\nDescription:\n{description}\n")

# Run the main function to test the accessory generation
asyncio.run(main())
