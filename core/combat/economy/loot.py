import random

from core.combat.economy.config import (
    ACC_STAT_CAPS,
    ARMOR_STAT_CAPS,
    BOOT_STAT_CAPS,
    GLOVE_STAT_CAPS,
    HELM_STAT_CAPS,
    WEAPON_DEFENCE_ROLL_CHANCE,
    WEAPON_RARITY_ROLL_CHANCE,
    WEAPON_STAT_CAPS,
)
from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon
from core.util import load_list

# ---------------------------------------------------------------------------
# Weapon Base Templates
# Each entry: (hit_chance, crit_chance, crit_multi, base_rarity)
# base_rarity: 3 = Premium ★★★, 2 = Good ★★, 1 = Mediocre ★
# ---------------------------------------------------------------------------
_WEAPON_BASE_TEMPLATES = [
    # Premium (total weight 0.10)
    (0.60, 0.05, 2.0, 3),  # Balanced
    (0.65, 0.00, 2.0, 3),  # High Accuracy
    (0.55, 0.10, 2.0, 3),  # High Crit
    (0.55, 0.04, 2.5, 3),  # High Multi
    # Good (total weight 0.50)
    (0.58, 0.02, 2.0, 2),  # Balanced
    (0.60, 0.00, 2.0, 2),  # High Accuracy
    (0.52, 0.08, 2.0, 2),  # High Crit
    (0.52, 0.03, 2.5, 2),  # High Multi
    # Mediocre (total weight 0.40)
    (0.54, 0.01, 2.0, 1),  # Balanced
    (0.55, 0.00, 2.0, 1),  # High Accuracy
    (0.50, 0.05, 2.0, 1),  # High Crit
    (0.50, 0.01, 2.5, 1),  # High Multi
]

_TEMPLATE_WEIGHTS = [
    0.025,
    0.025,
    0.025,
    0.025,  # Premium  (4 × 0.025 = 0.10)
    0.125,
    0.125,
    0.125,
    0.125,  # Good     (4 × 0.125 = 0.50)
    0.10,
    0.10,
    0.10,
    0.10,  # Mediocre (4 × 0.10  = 0.40)
]

# Stat caps imported from config — edit core/combat/economy/config.py to tune.
_WEAPON_CAPS = WEAPON_STAT_CAPS
_ACC_CAPS = ACC_STAT_CAPS
_ARMOR_CAPS = ARMOR_STAT_CAPS
_GLOVE_CAPS = GLOVE_STAT_CAPS
_BOOT_CAPS = BOOT_STAT_CAPS
_HELM_CAPS = HELM_STAT_CAPS


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


async def generate_weapon(user_id: str, level: int) -> Weapon:
    """Generate a unique loot item."""
    prefix = random.choice(load_list("assets/items/pref.txt"))
    weapon_type = random.choice(load_list("assets/items/wep.txt"))
    suffix = random.choice(load_list("assets/items/suff.txt"))
    item_name = f"{prefix} {weapon_type} {suffix}"

    weapon = Weapon(
        user=user_id,
        name=item_name,
        level=level,
        attack=int(get_scaled_stat(level, _WEAPON_CAPS["attack"])),
        defence=0,
        rarity=0,
        passive="none",
        description="",
        p_passive="",
        u_passive="",
    )

    if random.randint(0, 100) < WEAPON_DEFENCE_ROLL_CHANCE:
        weapon.defence = int(get_scaled_stat(level, _WEAPON_CAPS["defence"]))

    if random.randint(0, 100) < WEAPON_RARITY_ROLL_CHANCE:
        weapon.rarity = int(get_scaled_stat(level, _WEAPON_CAPS["rarity"]))

    hit, crit, multi, base_rar = random.choices(
        _WEAPON_BASE_TEMPLATES, _TEMPLATE_WEIGHTS
    )[0]
    weapon.hit_chance = hit
    weapon.crit_chance = crit
    weapon.crit_multi = multi
    weapon.base_rarity = base_rar

    weapon.description = (
        (f"**{weapon.name}**\n(Level {weapon.level})\n")
        + f"+{weapon.attack} Attack\n"
        + (f"+{weapon.defence} Defence\n" if weapon.defence > 0 else "")
        + (f"+{weapon.rarity}% Rarity\n" if weapon.rarity > 0 else "")
    )

    return weapon


async def generate_accessory(user_id: str, level: int) -> Accessory:
    """Generate a unique accessory item."""
    prefix = random.choice(load_list("assets/items/pref.txt"))
    accessory_type = random.choice(load_list("assets/items/acc.txt"))
    suffix = random.choice(load_list("assets/items/suff.txt"))
    acc_name = f"{prefix} {accessory_type} {suffix}"

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

    stat = random.choices(["attack", "defence", "rarity", "ward", "crit"], k=1)[0]
    if stat == "attack":
        acc.attack = int(get_scaled_stat(level, _ACC_CAPS["attack"]))
        acc.description += f"+{acc.attack}% Attack"
    elif stat == "defence":
        acc.defence = int(get_scaled_stat(level, _ACC_CAPS["defence"]))
        acc.description += f"+{acc.defence}% Defence"
    elif stat == "rarity":
        acc.rarity = int(get_scaled_stat(level, _ACC_CAPS["rarity"]))
        acc.description += f"+{acc.rarity}% Rarity"
    elif stat == "ward":
        acc.ward = int(get_scaled_stat(level, _ACC_CAPS["ward"]))
        acc.description += f"+{acc.ward}% Ward"
    else:
        acc.crit = int(get_scaled_stat(level, _ACC_CAPS["crit"]))
        acc.description += f"+{acc.crit}% Crit"

    return acc


async def generate_armor(user_id: str, level: int) -> Armor:
    """Generate a unique armor item."""
    prefix = random.choice(load_list("assets/items/pref.txt"))
    armor_type = random.choice(load_list("assets/items/armor.txt"))
    suffix = random.choice(load_list("assets/items/suff.txt"))
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


async def generate_glove(user_id: str, level: int) -> Glove:
    """Generate a unique glove item. Gloves roll one primary stat (Atk, Def, or Ward)
    and one secondary stat (PDR or FDR). They do not drop runes."""
    try:
        prefix = random.choice(load_list("assets/items/pref.txt"))
        glove_type_name = random.choice(
            load_list("assets/items/gloves.txt")
        )  # Renamed to avoid conflict
        suffix = random.choice(load_list("assets/items/suff.txt"))
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
        prefix = random.choice(load_list("assets/items/pref.txt"))
        boot_type_name = random.choice(load_list("assets/items/boots.txt"))
        suffix = random.choice(load_list("assets/items/suff.txt"))
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
        prefix = random.choice(load_list("assets/items/pref.txt"))
        helm_type = random.choice(
            ["Helm", "Coif", "Sallet", "Bascinet", "Armet", "Visor"]
        )
        suffix = random.choice(load_list("assets/items/suff.txt"))
        name = f"{prefix} {helm_type} {suffix}"
    except Exception:
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
