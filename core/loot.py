import random
from core.util import load_list


async def generate_loot(level: int, drop_rune: bool) -> str:
    """Generate a unique loot item."""
    prefix = random.choice(load_list("assets/items/pref.txt"))
    weapon_type = random.choice(load_list("assets/items/wep.txt"))
    suffix = random.choice(load_list("assets/items/suff.txt"))
    item_name = f"{prefix} {weapon_type} {suffix}"

    modifiers = []
    attack_modifier = 0
    defence_modifier = 0
    rarity_modifier = 0
    if (drop_rune):
        if random.randint(0, 100) < 80:  # 80% chance for attack roll
            attack_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
            modifiers.append(f"+{attack_modifier} Attack")
    else:
        attack_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        modifiers.append(f"+{attack_modifier} Attack")

    if random.randint(0, 100) < 50:  # 50% chance for defense roll
        defence_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        modifiers.append(f"+{defence_modifier} Defence")

    if random.randint(0, 100) < 20:  # 20% chance for rarity roll
        rarity_modifier = max(1, random.randint(int(level // 7), int(level // 5))) * 5
        modifiers.append(f"+{rarity_modifier}% Rarity")

    loot_description = item_name + f"\n"
    if modifiers:
        loot_description += f"\n".join(modifiers)
    else:
        loot_description = "**Rune of Refinement**!"
        item_name = "rune"

    return item_name, attack_modifier, defence_modifier, rarity_modifier, loot_description

async def generate_accessory(level: int, drop_rune: bool) -> str:
    """Generate a unique accessory item."""
    prefix = random.choice(load_list("assets/items/pref.txt"))
    accessory_type = random.choice(load_list("assets/items/acc.txt"))
    suffix = random.choice(load_list("assets/items/suff.txt"))
    acc_name = f"{prefix} {accessory_type} {suffix}"

    modifiers = []
    attack_modifier = 0
    defence_modifier = 0
    rarity_modifier = 0
    if (drop_rune):
        randroll = random.randint(0, 100)
    else:
        randroll = random.randint(0, 90)

    if randroll <= 18:  # 18% chance for attack roll
        attack_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        modifiers.append(f"+{attack_modifier} Attack")
    elif randroll > 18 and randroll <= 36:  # 18% chance for defense roll
        defence_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        modifiers.append(f"+{defence_modifier} Defence")
    elif randroll > 36 and randroll <= 54:
        rarity_modifier = max(1, random.randint(int(level // 7), int(level // 5))) * 5
        modifiers.append(f"+{rarity_modifier}% Rarity")
    elif randroll > 54 and randroll <= 72:
        rarity_modifier = max(1, random.randint(int(level // 7), int(level // 5))) * 2
        modifiers.append(f"+{rarity_modifier}% Ward")
    elif randroll > 72 and randroll <= 90:
        rarity_modifier = max(1, random.randint(int(level // 10), int(level // 9)))
        modifiers.append(f"+{rarity_modifier}% Crit")

    loot_description = acc_name + f"\n"
    if modifiers:
        loot_description += f"\n".join(modifiers)
    else:
        loot_description = "**Rune of Potential**!"
        acc_name = "rune"
        
    return acc_name, loot_description

async def generate_armor(level: int, drop_rune: bool) -> str:
    """Generate a unique armor item."""
    prefix = random.choice(load_list("assets/items/pref.txt"))
    armor_type = random.choice(load_list('assets/items/armor.txt'))  # Load names from armor.txt
    suffix = random.choice(load_list("assets/items/suff.txt"))
    armor_name = f"{prefix} {armor_type} {suffix}"

    modifiers = []
    block_modifier = 0
    evasion_modifier = 0
    ward_modifier = 0

    if drop_rune:
        randroll = random.randint(0, 100)
    else:
        randroll = random.randint(0, 90)
    print(f"Armor attribute roll: {randroll}")
    if randroll <= 30:  # 30% chance for block roll
        block_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        modifiers.append(f"+{block_modifier} Block")
    elif randroll > 30 and randroll <= 60:  # 30% chance for evasion roll
        evasion_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        modifiers.append(f"+{evasion_modifier} Evasion")
    elif randroll > 60 and randroll <= 90:  # 30% chance for ward roll
        ward_modifier = max(1, random.randint(int(level // 7), int(level // 5))) * 2
        modifiers.append(f"+{ward_modifier}% Ward")
    else:
        armor_description = "**Rune of Imbuing**!"
        armor_name = "rune"
        return armor_name, armor_description

    if modifiers:
        armor_description = armor_name + f"\n" + f"\n".join(modifiers)
    else:
        armor_description = armor_name

    return armor_name, armor_description