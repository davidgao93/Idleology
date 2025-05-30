import random

def calculate_hit_chance(player, monster):
    """Calculate the chance to hit based on the player's attack and monster's defence."""
    difference = player.attack - monster.defence

    if player.attack <= 10:
        return 0.9
    elif player.attack <= 20:
        return 0.8
    elif player.attack <= 30:
        return 0.7
    hit_chance = min(max(0.6 + (difference / 100), 0.6), 0.8)
    return hit_chance

def calculate_monster_hit_chance(player, monster):
    """Calculate the player's chance to be hit based on stats."""
    difference = monster.attack - player.defence

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
    difference = monster.attack - player.defence

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
        damage = random.randint(*damage_ranges[2])

    additional_damage = 0
    if difference > 0:
        additional_damage = int(sum(random.randint(1, 3) for _ in range(int(difference / 10))))
        damage += additional_damage
    damage_taken = random.randint(1, damage)
    return max(0, damage_taken)

def check_cull(player, monster):
    overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
    if player.weapon_passive in overwhelm_passives and monster.hp > 1:
        value = overwhelm_passives.index(player.weapon_passive)
        culling_strike = (value + 1) * 0.08
        if monster.hp <= (monster.max_hp * culling_strike):
            return True
    return False