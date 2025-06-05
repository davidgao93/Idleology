import random
from core.util import load_list
from core.models import Player, Weapon, Accessory, Armor

async def generate_weapon(user_id: str, level: int, drop_rune: bool) -> str:
    """Generate a unique loot item."""
    prefix = random.choice(load_list("assets/items/pref.txt"))
    weapon_type = random.choice(load_list("assets/items/wep.txt"))
    suffix = random.choice(load_list("assets/items/suff.txt"))
    item_name = f"{prefix} {weapon_type} {suffix}"
    
    weapon = Weapon(
        user="",
        name="",
        level=0,
        attack=0,
        defence=0,
        rarity=0,
        passive="",
        description="",
        p_passive="",
        u_passive=""
    )
    weapon.user=user_id
    weapon.name=item_name
    weapon.level=level
    # If a rune cannot be dropped, set attack mod to always be true (curio case)
    if (drop_rune):
        if random.randint(0, 100) < 80:  # 80% chance for attack roll
            attack_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
            weapon.attack = attack_modifier
    else:
        attack_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        weapon.attack = attack_modifier

    if random.randint(0, 100) < 50:  # 50% chance for defense roll
        defence_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        weapon.defence = defence_modifier

    if random.randint(0, 100) < 20:  # 20% chance for rarity roll
        rarity_modifier = max(1, random.randint(int(level // 7), int(level // 5))) * 5
        weapon.rarity = rarity_modifier

    if weapon.attack > 0 or weapon.defence > 0 or weapon.rarity > 0:
        weapon.passive = "none"
        weapon.description = ((f"**{weapon.name}**\n(Level {weapon.level})\n") +
            (f"+{weapon.attack} Attack\n" if weapon.attack > 0 else "") +
            (f"+{weapon.defence} Defence\n" if weapon.defence > 0 else "") +
            (f"+{weapon.rarity}% Rarity\n" if weapon.rarity > 0 else "")
        )
    else:
        weapon.name = "Rune of Refinement"
        weapon.description = f"{weapon.name}\nAdds a refinement attempt if the weapon is no longer refinable."

    return weapon

async def generate_accessory(user_id: str, level: int, drop_rune: bool) -> str:
    """Generate a unique accessory item."""
    prefix = random.choice(load_list("assets/items/acc_pref.txt"))
    accessory_type = random.choice(load_list("assets/items/acc.txt"))
    suffix = random.choice(load_list("assets/items/acc_suff.txt"))
    acc_name = f"{prefix} {accessory_type} {suffix}"

    attack_modifier = 0
    defence_modifier = 0
    rarity_modifier = 0
    if (drop_rune):
        randroll = random.randint(0, 100)
    else:
        randroll = random.randint(0, 90)

    acc = Accessory(
        user=user_id,
        name=acc_name,
        level=level,
        attack=0,
        defence=0,
        rarity=0,
        ward=0,
        crit=0,
        passive="",
        description=f"**{acc_name}**\n(Level {level})\n"
    )
    
    if randroll <= 18:  # 18% chance for attack roll
        attack_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        acc.attack=attack_modifier
        acc.description += f"+{attack_modifier} Attack"
    elif randroll > 18 and randroll <= 36:  # 18% chance for defense roll
        defence_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        acc.defence=defence_modifier
        acc.description += f"+{defence_modifier} Defence"
    elif randroll > 36 and randroll <= 54:
        rarity_modifier = max(1, random.randint(int(level // 7), int(level // 5))) * 5
        acc.rarity=rarity_modifier
        acc.description += f"+{rarity_modifier}% Rarity"
    elif randroll > 54 and randroll <= 72:
        ward_modifier = max(1, random.randint(int(level // 7), int(level // 5))) * 2
        acc.ward=ward_modifier
        acc.description += f"+{ward_modifier}% Ward"
    elif randroll > 72 and randroll <= 90:
        crit_modifier = max(1, random.randint(int(level // 10), int(level // 9)))
        acc.crit=crit_modifier
        acc.description += f"+{crit_modifier}% Crit"
    else:
        acc.name = "Rune of Potential"
        acc.description = f"{acc.name}\n25% increased chance to succeed at increasing an accessory's potential level."
        
    return acc

async def generate_armor(user_id: str, level: int, drop_rune: bool) -> str:
    """Generate a unique armor item."""
    prefix = random.choice(load_list("assets/items/armor_pref.txt"))
    armor_type = random.choice(load_list('assets/items/armor.txt'))  # Load names from armor.txt
    suffix = random.choice(load_list("assets/items/armor_suff.txt"))
    armor_name = f"{prefix} {armor_type} {suffix}"

    block_modifier = 0
    evasion_modifier = 0
    ward_modifier = 0

    armor = Armor(
        user=user_id,
        name=armor_name,
        level=level,
        block=0,
        evasion=0,
        ward=0,
        pdr=0,
        fdr=0,
        passive="",
        description=f"**{armor_name}**\n(Level {level})\n"
    )

    if drop_rune:
        randroll = random.randint(0, 100)
    else:
        randroll = random.randint(0, 90)
    print(f"Armor attribute roll: {randroll}")
    if randroll <= 30:  # 30% chance for block roll
        block_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        armor.block = block_modifier
        armor.description += f"+{block_modifier} Block"
    elif randroll > 30 and randroll <= 60:  # 30% chance for evasion roll
        evasion_modifier = max(1, random.randint(int(level // 7), int(level // 5)))
        armor.evasion = evasion_modifier
        armor.description += f"+{evasion_modifier} Evasion"
    elif randroll > 60 and randroll <= 90:  # 30% chance for ward roll
        ward_modifier = max(1, random.randint(int(level // 7), int(level // 5))) * 2
        armor.ward = ward_modifier
        armor.description += f"+{ward_modifier}% Ward"
    else:
        armor.name = "Rune of Imbuing"
        armor.description = f"{armor.name}\nPotentially imbues a powerful passive onto your armor."

    # Roll for PDR or FDR
    if (random.random() < 0.5):
        pdr_mod = max(1, random.randint(int(level // 20), int(level // 10)))
        armor.pdr = pdr_mod
    else:
        fdr_mod = max(1, random.randint(int(level // 50), int(level // 20)))
        armor.fdr = fdr_mod


    return armor