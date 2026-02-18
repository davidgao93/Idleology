import random
from typing import Dict, Any, List
from core.models import Player, Monster

def calculate_rewards(player: Player, monster: Monster) -> Dict[str, Any]:
    """
    Calculates XP and Gold rewards based on player stats, passives, and monster level.
    Returns a dict containing 'xp', 'gold', and a list of 'msgs' for logs.
    """
    results = {
        "xp": 0,
        "gold": 0,
        "msgs": [],
        "items": []
    }

    # --- XP Calculation ---
    base_xp = monster.xp
    
    # Scale XP for low levels (from original combat.py)
    if monster.level <= 20: 
        base_xp = int(base_xp * 2)
    else: 
        base_xp = int(base_xp * 1.3)

    # Accessory Passive: Infinite Wisdom
    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0
    
    if acc_passive == "Infinite Wisdom":
        double_exp_chance = acc_lvl * 0.05
        if random.random() <= double_exp_chance:
            base_xp *= 2
            results["msgs"].append(f"**Infinite Wisdom ({acc_lvl})** grants double XP!")

    # Glove Passive: Equilibrium (Pending XP)
    if player.equilibrium_bonus_xp_pending > 0:
        base_xp += player.equilibrium_bonus_xp_pending
        results["msgs"].append(f"**Equilibrium** siphons an extra {player.equilibrium_bonus_xp_pending:,} XP!")
        player.equilibrium_bonus_xp_pending = 0 # Reset

    results["xp"] = base_xp

    # --- Gold Calculation ---
    rare_monsters = ["Treasure Chest", "Random Korean Lady", "KPOP STAR", "Loot Goblin", "Yggdrasil", "Capybara Sauna"]
    
    reward_scale = 0
    if monster.name in rare_monsters:
        reward_scale = int(player.level / 10)
    else:
        reward_scale = max(0, (monster.level - player.level) / 10)

    gold_award = int((monster.level ** random.uniform(1.4, 1.6)) * (1 + (reward_scale ** 1.3)))
    
    # Rarity Bonus
    if player.rarity > 0:
        gold_award = int(gold_award * (1.5 + player.rarity / 100))
    
    gold_award += 20 # Base flat amount

    # Accessory Passive: Prosper
    if acc_passive == "Prosper":
        double_gold_chance = acc_lvl * 0.10
        if random.random() <= double_gold_chance:
            gold_award *= 2
            results["msgs"].append(f"**Prosper ({acc_lvl})** grants double Gold!")

    # Glove Passive: Plundering (Pending Gold)
    if player.plundering_bonus_gold_pending > 0:
        gold_award += player.plundering_bonus_gold_pending
        results["msgs"].append(f"**Plundering** snatches an extra {player.plundering_bonus_gold_pending:,} Gold!")
        player.plundering_bonus_gold_pending = 0 # Reset

    results["gold"] = gold_award
    
    return results

def check_special_drops(player: Player, monster: Monster) -> Dict[str, bool]:
    """
    Determines which special items (Keys, Runes, Curios) drop.
    Returns a dict of flags like {'draconic_key': True, 'refinement_rune': True}
    """
    drops = {}
    
    # --- BOSS DROPS (Aphrodite, Lucifer, NEET) ---
    if "Aphrodite" in monster.name:
        if random.random() < 0.33: drops['refinement_rune'] = True
        if random.random() < 0.33: drops['potential_rune'] = True
        if random.random() < 0.33: drops['imbue_rune'] = True
        drops['curio'] = True 
        return drops

    if "Lucifer" in monster.name:
        if random.random() < 0.66: drops['refinement_rune'] = True
        if random.random() < 0.33: drops['potential_rune'] = True
        return drops

    if "NEET" in monster.name:
        if random.random() < 0.33: drops['refinement_rune'] = True
        if random.random() < 0.66: drops['potential_rune'] = True
        return drops
    
    if "Gemini" in monster.name:
        if random.random() < 0.5: drops['partnership_rune'] = True
        return drops

    # --- STANDARD MOBS ---
    rare_monsters = ["Treasure Chest", "Random Korean Lady", "KPOP STAR", "Loot Goblin", "Yggdrasil", "Capybara Sauna"]
    
    special_drop_chance = len(monster.modifiers) / 100.0
    if monster.name in rare_monsters:
        special_drop_chance = 0.05
        drops['curio'] = True

    # Boot Passive: Thrill Seeker
    if player.equipped_boot and player.equipped_boot.passive == "thrill-seeker":
        special_drop_chance += (player.equipped_boot.passive_lvl * 0.01)
    

    if random.random() < 0.05: # 5% from Fire mobs
        drops['magma_core'] = True
    if random.random() < 0.05:
        drops['life_root'] = True
    if random.random() < 0.05:
        drops['spirit_shard'] = True

    # Level 20+ Drops
    if player.level > 20:
        if random.random() < (0.03 + special_drop_chance): drops['draconic_key'] = True
        if random.random() < (0.03 + special_drop_chance): drops['angelic_key'] = True
        if random.random() < (0.08 + special_drop_chance): drops['soul_core'] = True
        if random.random() < (0.05 + special_drop_chance): drops['void_frag'] = True
        if random.random() < (0.01 + special_drop_chance): drops['shatter_rune'] = True
        if random.random() < (0.05 + special_drop_chance): drops['balance_fragment'] = True

    return drops

def calculate_item_drop_chance(player: Player) -> int:
    """
    Calculates the percentage chance (0-100) for a gear item to drop.
    Base: 10%
    Max Cap: 30% (Asymptotic)
    Scaling: 100% Rarity = 20% Total Chance
    """
    base_chance = 10.0
    max_bonus_chance = 20.0 # The most you can possibly add to the base
    
    scaling_constant = 100.0 
    
    # Prevent negative rarity from breaking math (optional safety)
    rarity = max(0, player.rarity)

    # Formula: MaxBonus * ( R / (R + K) )
    # As R gets huge, the fraction approaches 1.0, giving the full MaxBonus.
    bonus_chance = max_bonus_chance * (rarity / (rarity + scaling_constant))
    
    total_chance = base_chance + bonus_chance
    
    return int(total_chance)