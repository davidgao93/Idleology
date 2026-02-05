import random

def get_player_passive_indices(player, target_passives):
    """
    Check if player has any passives from the target list.
    Returns a list of indices corresponding to the target_passives list.
    """
    indices = []
    
    # Get all player passives using the new dataclass methods
    player_passives = [
        player.get_weapon_passive(),
        player.get_weapon_pinnacle(),
        player.get_weapon_utmost(),
        # You can add other passive sources if needed:
        # player.get_armor_passive(),
        # player.get_accessory_passive(),
        # player.get_glove_passive(),
        # player.get_boot_passive(),
    ]
    
    # Check each player passive against target list
    for passive in player_passives:
        if passive in target_passives:
            indices.append(target_passives.index(passive))
    
    return indices

def calculate_hit_chance(player, monster):
    """Calculate the chance to hit based on the player's attack and monster's defence."""
    difference = player.get_total_attack() - monster.defence
    # print(f"p.atk {player.get_total_attack()} - m.def {monster.defence}: {difference}")
    if player.get_total_attack() <= 10:
        return 0.9
    elif player.get_total_attack() <= 20:
        return 0.8
    elif player.get_total_attack() <= 30:
        return 0.7
    hit_chance = min(max(0.6 + (difference / 100), 0.6), 0.8)
    return hit_chance


def calculate_monster_hit_chance(player, monster):
    """Calculate the player's chance to be hit based on stats."""
    difference = monster.attack - player.get_total_defence()
    if monster.attack <= 5:
        return 0.2
    elif monster.attack <= 10:
        return 0.3
    elif monster.attack <= 15:
        return 0.4

    hit_chance = min(max(0.5 + (difference / 100), 0.3), 0.8)
    return hit_chance
    
def calculate_damage_taken(player, monster):
    """Calculate damage taken based on monster's attack and player's defense."""
    difference = monster.attack - player.get_total_defence()

    if "Strengthened" in monster.modifiers:
        damage_ranges = [(1, 5), (1, 6), (1, 9)]
    else:
        damage_ranges = [(1, 2), (1, 3), (1, 6)]

    if monster.attack <= 3:
        damage = random.randint(*damage_ranges[0])
        difference = 0
    elif monster.attack <= 20:
        damage = random.randint(*damage_ranges[1])
        difference = 0
    else:
        damage = random.randint(*damage_ranges[2]) + int(monster.level // 10)

    additional_damage = 0
    if difference > 0:
        additional_damage = int(sum(random.randint(1, 3) for _ in range(int(difference / 10))))
        damage += additional_damage
    damage_taken = random.randint(1, damage)
    return max(0, damage_taken)

def check_cull(player, monster):
    overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
    indices = get_player_passive_indices(player, overwhelm_passives)
    if indices and monster.hp > 1:
        max_index = max(indices)
        culling_strike = (max_index + 1) * 0.08
        if monster.hp <= (monster.max_hp * culling_strike):
            return True
    return False


def check_for_polished(player, monster, embed_to_modify):
    polished_passives = ["polished", "honed", "gleaming", "tempered", "flaring"]
    indices = get_player_passive_indices(player, polished_passives)

    # If any passives were found, calculate the maximum value
    if indices:
        max_index = max(indices)
        defence_reduction_percentage = (max_index + 1) * 0.08  # 8% to 40%
        reduced_amount = int(monster.defence * defence_reduction_percentage)
        monster.defence = max(0, monster.defence - reduced_amount)  # Ensure defence doesn't go below 0
        embed_to_modify.add_field(
            name="Weapon Passive",
            value=f"The **{polished_passives[max_index]}** weapon 💫 shines!\n"
                  f"Reduces {monster.name}'s defence by {reduced_amount} ({defence_reduction_percentage * 100:.0f}%).",
            inline=False
        )
    
    return player, monster, embed_to_modify


def check_for_sturdy(player, monster, embed_to_modify):
    sturdy_passives = ["sturdy", "reinforced", "thickened", "impregnable", "impenetrable"]
    indices = get_player_passive_indices(player, sturdy_passives)

    # If any passives were found, calculate the maximum value
    if indices:
        max_index = max(indices)
        defence_bonus_percentage = (max_index + 1) * 0.08  # 8% to 40%
        defence_bonus_amount = int(player.get_total_defence() * defence_bonus_percentage)  # Bonus based on player's current defence
        player.base_defence += defence_bonus_amount
        embed_to_modify.add_field(
            name="Weapon Passive",
            value=f"The **{sturdy_passives[max_index]}** weapon strengthens resolve!\n"
                  f"🛡️ Player defence boosted by **{defence_bonus_amount}**!",
            inline=False
        )

    # Return the updated player, monster, and embed_to_modify objects
    return player, monster, embed_to_modify


def check_for_accuracy(player, passive_message):
    acc_value_bonus = 0
    accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
    indices = get_player_passive_indices(player, accuracy_passives)

    # If any passives were found, calculate the maximum bonus
    if indices:
        max_index = max(indices)
        acc_value_bonus = (1 + max_index) * 4  # This is a % bonus to the roll
        passive_message += f"The **{accuracy_passives[max_index]}** weapon boosts 🎯 accuracy roll by **{acc_value_bonus}**!\n"

    # Return the updated passive_message
    return acc_value_bonus, passive_message


def check_for_crit_bonus(player):
    crit_passives = ["piercing", "keen", "incisive", "puncturing", "penetrating"]
    weapon_crit_bonus_chance = 0  # This is a reduction to player's crit target for easier crits
    indices = get_player_passive_indices(player, crit_passives)

    # If any passives were found, calculate the highest bonus
    if indices:
        max_index = max(indices)
        weapon_crit_bonus_chance = (max_index + 1) * 5  # e.g., 5 to 25 reduction in crit target

    # Return the calculated weapon_crit_bonus_chance
    return weapon_crit_bonus_chance


def check_for_burn_bonus(player, base_damage_max, attack_message):
    burning_passives = ["burning", "flaming", "scorching", "incinerating", "carbonising"]
    burn_bonus_percentage = 0
    indices = get_player_passive_indices(player, burning_passives)

    # If any passives were found, calculate the highest bonus
    if indices:
        max_index = max(indices)
        burn_bonus_percentage = (max_index + 1) * 0.08
        bonus_burn_damage = int(player.get_total_attack() * burn_bonus_percentage)
        base_damage_max += bonus_burn_damage
        attack_message += (f"The **{burning_passives[max_index]}** weapon 🔥 burns bright!\n"
                           f"Attack damage potential boosted by **{bonus_burn_damage}**.\n")

    # Return the updated base_damage_max and attack_message
    return base_damage_max, attack_message


def check_for_spark_bonus(player, base_damage_min, base_damage_max, attack_message):
    sparking_passives = ["sparking", "shocking", "discharging", "electrocuting", "vapourising"]
    spark_min_percentage = 0
    indices = get_player_passive_indices(player, sparking_passives)

    # If any passives were found, calculate the highest bonus
    if indices:
        max_index = max(indices)
        spark_min_percentage = (max_index + 1) * 0.08
        base_damage_min = max(base_damage_min, int(base_damage_max * spark_min_percentage))
        attack_message += (f"The **{sparking_passives[max_index]}** weapon surges with ⚡ lightning, ensuring solid impact!\n")

    # Return the updated base_damage_min and attack_message
    return base_damage_min, attack_message


def check_for_echo_bonus(player, actual_hit):
    echo_hit = False
    echo_passives = ["echo", "echoo", "echooo", "echoooo", "echoes"]
    echo_multiplier = 0
    indices = get_player_passive_indices(player, echo_passives)

    # If any passives were found, calculate the highest bonus
    echo_damage = 0
    if indices:
        max_index = max(indices)
        echo_multiplier = (max_index + 1) * 0.10
        echo_damage = int(actual_hit * echo_multiplier)  # Echo is based on the already calculated hit
        actual_hit += echo_damage  # Total damage includes echo
        echo_hit = True  # Mark that echo hit occurred

    # Return the updated actual_hit and echo_hit flag
    return actual_hit, echo_hit, echo_damage


def check_for_poison_bonus(player, attack_multiplier):
    poison_damage_on_miss = 0
    poisonous_passives = ["poisonous", "noxious", "venomous", "toxic", "lethal"]
    indices = get_player_passive_indices(player, poisonous_passives)

    # If any passives were found, calculate the highest bonus
    if indices:
        max_index = max(indices)
        poison_miss_percentage = (max_index + 1) * 0.08
        # Poison damage on miss is a fraction of player's attack
        poison_damage_on_miss = int(random.randint(1, int(player.get_total_attack() * poison_miss_percentage)) * attack_multiplier)

    # Return the calculated poison_damage_on_miss
    return poison_damage_on_miss