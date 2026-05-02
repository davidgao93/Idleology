import random

from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon
from core.util import load_list

# Soft caps for each stat per equipment type.
# get_scaled_stat approaches these asymptotically — they are never literally hit.
_WEAPON_CAPS = {"attack": 80, "defence": 80, "rarity": 200}
_ACC_CAPS = {"attack": 80, "defence": 80, "rarity": 200, "ward": 60, "crit": 20}
_ARMOR_CAPS = {"block": 50, "evasion": 50, "ward": 100, "pdr": 40, "fdr": 80, "main_stat": 60}
_GLOVE_CAPS = {"attack": 80, "defence": 80, "ward": 100, "pdr": 15, "fdr": 50}
_BOOT_CAPS = {"attack": 80, "defence": 80, "ward": 100, "pdr": 15, "fdr": 50}
_HELM_CAPS = {"defence": 40, "ward": 80, "pdr": 15, "fdr": 50}


def get_scaled_stat(
    level: int, cap: float, halfway_point: int = 100, variance: float = 0.2
) -> float:
    """
    Soft-capped stat roll using a hyperbolic curve.
    The expected value approaches `cap` asymptotically; at `halfway_point` levels it sits at 50% of cap.
    """
    expected = cap * (level / (level + halfway_point))
    return max(
        1.0, random.uniform(expected * (1 - variance), expected * (1 + variance))
    )


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
        u_passive="",
    )
    weapon.user = user_id
    weapon.name = item_name
    weapon.level = level
    # If a rune cannot be dropped, set attack mod to always be true (curio case)
    if drop_rune:
        if random.randint(0, 100) < 80:  # 80% chance for attack roll
            weapon.attack = int(get_scaled_stat(level, _WEAPON_CAPS["attack"]))
    else:
        weapon.attack = int(get_scaled_stat(level, _WEAPON_CAPS["attack"]))

    if random.randint(0, 100) < 50:  # 50% chance for defense roll
        weapon.defence = int(get_scaled_stat(level, _WEAPON_CAPS["defence"]))

    if random.randint(0, 100) < 20:  # 20% chance for rarity roll
        weapon.rarity = int(get_scaled_stat(level, _WEAPON_CAPS["rarity"]))

    if weapon.attack > 0 or weapon.defence > 0 or weapon.rarity > 0:
        weapon.passive = "none"
        weapon.description = (
            (f"**{weapon.name}**\n(Level {weapon.level})\n")
            + (f"+{weapon.attack} Attack\n" if weapon.attack > 0 else "")
            + (f"+{weapon.defence} Defence\n" if weapon.defence > 0 else "")
            + (f"+{weapon.rarity}% Rarity\n" if weapon.rarity > 0 else "")
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
    if drop_rune:
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
        passive_lvl=0,
        description=f"**{acc_name}**\n(Level {level})\n",
    )

    if randroll <= 18:  # 18% chance for attack roll
        acc.attack = int(get_scaled_stat(level, _ACC_CAPS["attack"]))
        acc.description += f"+{acc.attack} Attack"
    elif randroll > 18 and randroll <= 36:  # 18% chance for defense roll
        acc.defence = int(get_scaled_stat(level, _ACC_CAPS["defence"]))
        acc.description += f"+{acc.defence} Defence"
    elif randroll > 36 and randroll <= 54:
        acc.rarity = int(get_scaled_stat(level, _ACC_CAPS["rarity"]))
        acc.description += f"+{acc.rarity}% Rarity"
    elif randroll > 54 and randroll <= 72:
        acc.ward = int(get_scaled_stat(level, _ACC_CAPS["ward"]))
        acc.description += f"+{acc.ward}% Ward"
    elif randroll > 72 and randroll <= 90:
        acc.crit = int(get_scaled_stat(level, _ACC_CAPS["crit"]))
        acc.description += f"+{acc.crit}% Crit"
    else:
        acc.name = "Rune of Potential"
        acc.description = f"{acc.name}\n25% increased chance to succeed at increasing an accessory's potential level."

    return acc


async def generate_armor(user_id: str, level: int, drop_rune: bool) -> str:
    """Generate a unique armor item."""
    prefix = random.choice(load_list("assets/items/armor_pref.txt"))
    armor_type = random.choice(
        load_list("assets/items/armor.txt")
    )  # Load names from armor.txt
    suffix = random.choice(load_list("assets/items/armor_suff.txt"))
    armor_name = f"{prefix} {armor_type} {suffix}"

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
        description=f"**{armor_name}**\n(Level {level})\n",
    )

    if drop_rune:
        rune_roll = random.randint(0, 100)
    else:
        rune_roll = random.randint(0, 90)

    if rune_roll > 90:
        armor.name = "Rune of Imbuing"
        armor.description = (
            f"{armor.name}\nPotentially imbues a powerful passive onto your armor."
        )
        return armor

    # Main stat: ATK or DEF
    if random.random() < 0.5:
        armor.main_stat_type = "atk"
    else:
        armor.main_stat_type = "def"
    armor.main_stat = int(get_scaled_stat(level, _ARMOR_CAPS["main_stat"]))
    stat_label = "ATK" if armor.main_stat_type == "atk" else "DEF"
    armor.description += f"+{armor.main_stat} {stat_label}\n"

    # Secondary stat: Block or Evasion (immutable, determined on roll)
    if random.random() < 0.5:
        armor.block = int(get_scaled_stat(level, _ARMOR_CAPS["block"]))
        armor.description += f"+{armor.block}% Block\n"
    else:
        armor.evasion = int(get_scaled_stat(level, _ARMOR_CAPS["evasion"]))
        armor.description += f"+{armor.evasion}% Evasion\n"

    # Tertiary stat: PDR or FDR (Temper can increase)
    if random.random() < 0.5:
        armor.pdr = int(get_scaled_stat(level, _ARMOR_CAPS["pdr"]))
        armor.description += f"+{armor.pdr}% Percent Damage Reduction"
    else:
        armor.fdr = int(get_scaled_stat(level, _ARMOR_CAPS["fdr"]))
        armor.description += f"+{armor.fdr} Flat Damage Reduction"

    return armor


async def generate_glove(
    user_id: str, level: int
) -> Glove:  # drop_rune parameter removed
    """Generate a unique glove item. Gloves roll one primary stat (Atk, Def, or Ward)
    and one secondary stat (PDR or FDR). They do not drop runes."""
    try:
        prefix = random.choice(load_list("assets/items/armor_pref.txt"))
        glove_type_name = random.choice(
            load_list("assets/items/gloves.txt")
        )  # Renamed to avoid conflict
        suffix = random.choice(load_list("assets/items/armor_suff.txt"))
        glove_name = f"{prefix} {glove_type_name} {suffix}"
    except FileNotFoundError:
        glove_name = f"Training Gloves of Level {level}"

    glove = Glove(
        user=user_id,
        name=glove_name,
        level=level,
        description=f"**{glove_name}**\n(Level {level})\n",
    )

    # 1. Primary Stat Roll (Attack, Defence, or Ward)
    primary_stat_roll = random.randint(0, 2)

    if primary_stat_roll == 0:  # Attack
        glove.attack = int(get_scaled_stat(level, _GLOVE_CAPS["attack"]))
        glove.description += f"+{glove.attack} Attack\n"
    elif primary_stat_roll == 1:  # Defence
        glove.defence = int(get_scaled_stat(level, _GLOVE_CAPS["defence"]))
        glove.description += f"+{glove.defence} Defence\n"
    else:  # Ward
        glove.ward = int(get_scaled_stat(level, _GLOVE_CAPS["ward"]))
        glove.description += f"+{glove.ward}% Ward\n"

    # 2. Secondary Stat Roll (PDR or FDR)
    if random.random() < 0.5:
        glove.pdr = int(get_scaled_stat(level, _GLOVE_CAPS["pdr"]))
        glove.description += f"+{glove.pdr}% Percentage Damage Reduction\n"
    else:
        glove.fdr = int(get_scaled_stat(level, _GLOVE_CAPS["fdr"]))
        glove.description += f"+{glove.fdr} Flat Damage Reduction\n"

    return glove


async def generate_boot(user_id: str, level: int) -> Boot:
    """Generate a unique boot item. Boots roll one primary stat (Atk, Def, or Ward)
    and one secondary stat (PDR or FDR). They do not drop runes."""
    try:
        # Assuming asset files: assets/items/boot_pref.txt, assets/items/boots.txt, assets/items/boot_suff.txt
        prefix = random.choice(load_list("assets/items/armor_pref.txt"))
        boot_type_name = random.choice(load_list("assets/items/boots.txt"))
        suffix = random.choice(load_list("assets/items/armor_suff.txt"))
        boot_name = f"{prefix} {boot_type_name} {suffix}"
    except FileNotFoundError:
        boot_name = f"Sturdy Boots of Level {level}"  # Fallback name

    boot = Boot(
        user=user_id,
        name=boot_name,
        level=level,
        description=f"**{boot_name}**\n(Level {level})\n",
    )

    # 1. Primary Stat Roll (Attack, Defence, or Ward)
    primary_stat_roll = random.randint(0, 2)

    if primary_stat_roll == 0:  # Attack
        boot.attack = int(get_scaled_stat(level, _BOOT_CAPS["attack"]))
        boot.description += f"+{boot.attack} Attack\n"
    elif primary_stat_roll == 1:  # Defence
        boot.defence = int(get_scaled_stat(level, _BOOT_CAPS["defence"]))
        boot.description += f"+{boot.defence} Defence\n"
    else:  # Ward
        boot.ward = int(get_scaled_stat(level, _BOOT_CAPS["ward"]))
        boot.description += f"+{boot.ward}% Ward\n"

    # 2. Secondary Stat Roll (PDR or FDR)
    if random.random() < 0.5:
        boot.pdr = int(get_scaled_stat(level, _BOOT_CAPS["pdr"]))
        boot.description += f"+{boot.pdr}% Percentage Damage Reduction\n"
    else:
        boot.fdr = int(get_scaled_stat(level, _BOOT_CAPS["fdr"]))
        boot.description += f"+{boot.fdr} Flat Damage Reduction\n"

    return boot


async def generate_helmet(user_id: str, level: int) -> Helmet:
    try:
        prefix = random.choice(load_list("assets/items/armor_pref.txt"))
        helm_type = random.choice(
            ["Helm", "Coif", "Sallet", "Bascinet", "Armet", "Visor"]
        )
        suffix = random.choice(load_list("assets/items/armor_suff.txt"))
        name = f"{prefix} {helm_type} {suffix}"
    except:
        name = f"Sturdy Helm of Level {level}"

    helm = Helmet(
        user=user_id,
        name=name,
        level=level,
        description=f"**{name}**\n(Level {level})\n",
    )

    # 1. Primary Stat Roll (Defence OR Ward)
    if random.random() < 0.5:
        helm.defence = int(get_scaled_stat(level, _HELM_CAPS["defence"]))
        helm.description += f"+{helm.defence} Defence\n"
    else:
        helm.ward = int(get_scaled_stat(level, _HELM_CAPS["ward"]))
        helm.description += f"+{helm.ward}% Ward\n"

    # 2. Secondary Stat Roll (PDR OR FDR)
    if random.random() < 0.5:
        helm.pdr = int(get_scaled_stat(level, _HELM_CAPS["pdr"]))
        helm.description += f"+{helm.pdr}% PDR\n"
    else:
        helm.fdr = int(get_scaled_stat(level, _HELM_CAPS["fdr"]))
        helm.description += f"+{helm.fdr} FDR\n"

    return helm
