import random
import logging
from typing import Tuple, Dict

from core.models import Player, Monster
from core.combat.calcs import (
    calculate_hit_chance, 
    calculate_monster_hit_chance, 
    calculate_damage_taken, 
    check_cull, 
    check_for_accuracy, 
    check_for_crit_bonus, 
    check_for_burn_bonus, 
    check_for_spark_bonus, 
    check_for_echo_bonus,
    check_for_poison_bonus
)

logger = logging.getLogger("discord_bot")

def apply_stat_effects(player: Player, monster: Monster) -> None:
    """Applies monster modifiers that alter player stats at the start of combat."""
    modifier_effects = {
        "Shield-breaker": lambda p, m: setattr(p, "combat_ward", 0),
        "Impenetrable": lambda p, m: setattr(p, "base_crit_chance_target", max(1, p.base_crit_chance_target - 5)), 
        "Enfeeble": lambda p, m: setattr(p, "base_attack", int(p.base_attack * 0.9)),
        "Overwhelm": lambda p, m: setattr(p, "combat_ward", 0), 
    }
    
    for modifier in monster.modifiers:
        if modifier in modifier_effects:
            modifier_effects[modifier](player, monster)

def apply_combat_start_passives(player: Player, monster: Monster) -> Dict[str, str]:
    """Applies player passives that trigger at the start of combat. Returns UI log strings."""
    logs = {}
    
    # 1. Reset transient states
    player.is_invulnerable_this_combat = False

    # 2. Armor Passives
    armor_passive = player.get_armor_passive()

    if armor_passive == "Invulnerable" and random.random() < 0.2:
        logs["Armor Passive"] = f"The **Invulnerable** armor imbues with power!\n{player.name} receives divine protection."
        player.is_invulnerable_this_combat = True

    if armor_passive == "Omnipotent" and random.random() < 0.5:
        total_atk = player.get_total_attack()
        total_def = player.get_total_defence()
        logs["Armor Passive"] = (f"The **Omnipotent** armor imbues with power!\nYou feel **empowered**.\n"
                                 f"⚔️ Attack boosted by **{total_atk}**\n"
                                 f"🛡️ Defence boosted by **{total_def}**\n"
                                 f"🔮 Gain **{player.max_hp}** ward")
        player.base_attack += total_atk
        player.base_defence += total_def
        player.combat_ward += player.max_hp

    # 3. Accessory Passives
    acc_passive = player.get_accessory_passive()
    if acc_passive == "Absorb" and player.equipped_accessory:
        absorb_chance = player.equipped_accessory.passive_lvl * 0.10
        if random.random() <= absorb_chance:
            monster_stats_total = monster.attack + monster.defence
            if monster_stats_total > 0:
                absorb_amount = max(1, int(monster_stats_total * 0.10))
                player.base_attack += absorb_amount
                player.base_defence += absorb_amount
                logs["Accessory Passive"] = (f"The accessory's 🌀 **Absorb ({player.equipped_accessory.passive_lvl})** activates!\n"
                                             f"⚔️ Attack boosted by **{absorb_amount}**\n"
                                             f"🛡️ Defence boosted by **{absorb_amount}**")

    # 4. Weapon Passives (Polished/Sturdy/Impenetrable)
    # Collect all active passives (Main, Pinnacle, Utmost)
    active_passives = [player.get_weapon_passive(), player.get_weapon_pinnacle(), player.get_weapon_utmost()]
    
    # Polished: Reduces Monster Defence
    polished_list = ["polished", "honed", "gleaming", "tempered", "flaring"]
    polished_indices = [polished_list.index(p) for p in active_passives if p in polished_list]
    
    if polished_indices:
        max_idx = max(polished_indices)
        pct_reduction = (max_idx + 1) * 0.08
        flat_reduction = int(monster.defence * pct_reduction)
        monster.defence = max(0, monster.defence - flat_reduction)
        logs["Weapon Passive"] = (f"The **{polished_list[max_idx]}** weapon 💫 shines!\n"
                                  f"Reduces {monster.name}'s defence by {flat_reduction} ({int(pct_reduction*100)}%).")

    # Sturdy / Impenetrable: Increases Player Defence
    # Note: 'impenetrable' is the final tier of the 'sturdy' line
    sturdy_list = ["sturdy", "reinforced", "thickened", "impregnable", "impenetrable"]
    sturdy_indices = [sturdy_list.index(p) for p in active_passives if p in sturdy_list]

    if sturdy_indices:
        max_idx = max(sturdy_indices)
        pct_bonus = (max_idx + 1) * 0.08
        current_def = player.get_total_defence()
        flat_bonus = int(current_def * pct_bonus)
        player.base_defence += flat_bonus
        
        passive_name = sturdy_list[max_idx]
        msg = (f"The **{passive_name}** weapon strengthens resolve!\n"
               f"🛡️ Player defence boosted by **{flat_bonus}**!")
        
        if "Weapon Passive" in logs:
            logs["Weapon Passive"] += f"\n{msg}"
        else:
            logs["Weapon Passive"] = msg

    return logs

def process_heal(player: Player) -> str:
    """Handles the logic of a player using a potion."""
    if player.potions <= 0:
        return f"{player.name} has no potions left to use!"

    if player.current_hp >= player.max_hp:
        return f"{player.name} is already full HP!"

    heal_percentage = 0.30 # Base 30%
    if player.equipped_boot and player.equipped_boot.passive == "cleric":
        heal_percentage += (player.equipped_boot.passive_lvl * 0.10)
        
    heal_amount = int((player.max_hp * heal_percentage) + random.randint(1, 6)) 
    healed_to_hp = min(player.max_hp, player.current_hp + heal_amount)
    actual_healed_amount = healed_to_hp - player.current_hp
    player.current_hp = healed_to_hp
    player.potions -= 1
    
    return (f"{player.name} uses a potion and heals for **{actual_healed_amount}** HP!\n"
            f"**{player.potions}** potions left.")

def process_player_turn(player: Player, monster: Monster) -> str:
    """Executes the player's turn, applying damage to the monster and returning the combat log."""
    attack_message = ""
    passive_message = ""
    attack_multiplier = 1.0

    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0
    armor_passive = player.get_armor_passive()

    # --- Pre-Attack Multipliers ---
    if glove_passive == "instability" and glove_lvl > 0:
        if random.random() < 0.5:
            attack_multiplier *= 0.5
        else:
            attack_multiplier *= 1.50 + (glove_lvl * 0.10) 
        passive_message += f"**Instability ({glove_lvl})** gives you {int(attack_multiplier * 100)}% damage.\n"

    if acc_passive == "Obliterate" and random.random() <= (acc_lvl * 0.02):
        passive_message += f"**Obliterate ({acc_lvl})** activates, doubling 💥 damage dealt!\n"
        attack_multiplier *= 2.0

    if armor_passive == "Mystical Might" and random.random() < 0.2:
        attack_multiplier *= 10.0
        passive_message += "The **Mystical Might** armor imbues with power, massively increasing damage!\n"

    # --- Hit Chance Calculation ---
    hit_chance = calculate_hit_chance(player, monster)
    if "Dodgy" in monster.modifiers:
        hit_chance = max(0.05, hit_chance - 0.10)
        passive_message += f"The monster's **Dodgy** nature makes it harder to hit!\n"

    attack_roll = random.randint(0, 100)
    
    acc_value_bonus, passive_message = check_for_accuracy(player, passive_message)

    if acc_passive == "Lucky Strikes" and random.random() <= (acc_lvl * 0.10):
        attack_roll = max(attack_roll, random.randint(0, 100))
        passive_message += f"**Lucky Strikes ({acc_lvl})** activates! Hit chance is now 🍀 lucky!\n"

    if "Suffocator" in monster.modifiers and random.random() < 0.2:
        passive_message += f"The {monster.name}'s **Suffocator** aura stifles your attack! Hit chance is now 💀 unlucky!\n"
        attack_roll = min(attack_roll, random.randint(0, 100))
        
    if "Shields-up" in monster.modifiers and random.random() < 0.1:
        attack_multiplier = 0
        passive_message += f"{monster.name} projects a magical barrier, nullifying the hit!\n"

    final_miss_threshold = 100 - int(hit_chance * 100)
    is_hit = False
    if attack_multiplier > 0: 
        effective_attack_roll = attack_roll + acc_value_bonus
        if effective_attack_roll >= final_miss_threshold:
            is_hit = True

    # --- Crit Check ---
    is_crit = False
    weapon_crit_bonus_chance = check_for_crit_bonus(player)
    crit_target = player.get_current_crit_target() - weapon_crit_bonus_chance
    
    if is_hit and attack_roll > crit_target and "Impenetrable" not in monster.modifiers:
        is_crit = True

    # --- Damage Calculation ---
    actual_hit_pre_ward_gen = 0
    echo_hit = False
    echo_damage = 0

    if is_crit:
        max_hit_calc = player.get_total_attack()
        crit_damage_floor_multiplier = 0.5
        if glove_passive == "deftness" and glove_lvl > 0:
            crit_damage_floor_multiplier = min(0.75, crit_damage_floor_multiplier + (glove_lvl * 0.05))
            passive_message += f"**Deftness ({glove_lvl})** increases your crit floor!\n"
        
        crit_min = max(1, int(max_hit_calc * crit_damage_floor_multiplier) + 1)
        # Ensure max >= min
        crit_max = max(crit_min, max_hit_calc)
        
        crit_base_damage = int(random.randint(crit_min, crit_max) * 2.0)
        
        if "Smothering" in monster.modifiers:
            crit_base_damage = int(crit_base_damage * 0.80)
            passive_message += f"The monster's **Smothering** aura dampens your critical hit!\n"

        actual_hit_pre_ward_gen = int(crit_base_damage * attack_multiplier)
        
        glimmer = "The weapon glimmers with power!\n" if weapon_crit_bonus_chance > 0 else ""
        attack_message = passive_message + glimmer + f"Critical Hit! Damage: 🗡️ **{actual_hit_pre_ward_gen}**"

    elif is_hit:
        base_damage_max = player.get_total_attack()
        base_damage_min = 1

        if glove_passive == "adroit" and glove_lvl > 0:
            base_damage_min = max(base_damage_min, int(base_damage_max * (glove_lvl * 0.02)))
            passive_message += f"**Adroit ({glove_lvl})** sharpens your technique!\n"

        base_damage_max, attack_message = check_for_burn_bonus(player, base_damage_max, attack_message)
        base_damage_min, attack_message = check_for_spark_bonus(player, base_damage_min, base_damage_max, attack_message)

        rolled_damage = random.randint(min(base_damage_min, base_damage_max), base_damage_max)
        actual_hit_pre_ward_gen = int(rolled_damage * attack_multiplier)

        actual_hit_pre_ward_gen, echo_hit, echo_damage = check_for_echo_bonus(player, actual_hit_pre_ward_gen)

        attack_message = passive_message + attack_message + f"Hit! Damage: 💥 **{actual_hit_pre_ward_gen - echo_damage}**"
        if echo_hit:
            attack_message += f"\nThe hit is 🎶 echoed!\nEcho damage: 💥 **{echo_damage}**"

    else: # Miss
        poison_damage_on_miss = check_for_poison_bonus(player, attack_multiplier)
        if poison_damage_on_miss > 0:
            attack_message = passive_message + f"Miss!\nHowever, the lingering poison 🐍 deals **{poison_damage_on_miss}** damage."
            actual_hit_pre_ward_gen = poison_damage_on_miss 
        else: 
            attack_message = passive_message + "Miss!"

    # --- Apply Damage Reductions ---
    actual_hit = actual_hit_pre_ward_gen
    if "Titanium" in monster.modifiers and actual_hit > 0:
        reduction = int(actual_hit * 0.10)
        actual_hit = max(0, actual_hit - reduction) 
        attack_message += f"\n{monster.name}'s **Titanium** plating reduces damage by {reduction}."

    # --- Glove Ward Passives ---
    if not is_crit and glove_passive == "ward-touched" and glove_lvl > 0 and actual_hit_pre_ward_gen > 0:
        ward_gained = int(actual_hit_pre_ward_gen * (glove_lvl * 0.01))
        if ward_gained > 0:
            player.combat_ward += ward_gained
            attack_message += f"\n**Ward-Touched ({glove_lvl})** generates 🔮 **{ward_gained}** ward!"
    
    if is_crit and glove_passive == "ward-fused" and glove_lvl > 0 and actual_hit_pre_ward_gen > 0:
        ward_gained = int(actual_hit_pre_ward_gen * (glove_lvl * 0.02))
        if ward_gained > 0:
            player.combat_ward += ward_gained
            attack_message += f"\n**Ward-Fused ({glove_lvl})** generates 🔮 **{ward_gained}** ward!"

    # --- Apply Final HP Deduction ---
    if actual_hit >= monster.hp: 
        if "Time Lord" in monster.modifiers and random.random() < 0.80 and monster.hp > 1: 
            actual_hit = monster.hp - 1 
            attack_message += f"\nA fatal blow was dealt, but **{monster.name}** cheated death via **Time Lord**!"
        else: 
            actual_hit = monster.hp 
    
    monster.hp -= actual_hit

    # --- Pending XP/Gold Tracking ---
    if actual_hit > 0:
        if glove_passive == "equilibrium" and glove_lvl > 0:
            player.equilibrium_bonus_xp_pending += int(actual_hit * (glove_lvl * 0.05))
        if glove_passive == "plundering" and glove_lvl > 0:
            player.plundering_bonus_gold_pending += int(actual_hit * (glove_lvl * 0.10))

    # --- Culling Check ---
    if monster.hp > 0 and check_cull(player, monster):
        cull_damage = monster.hp - 1
        if cull_damage > 0:
            monster.hp = 1
            attack_message += f"\n{player.name}'s weapon culls the weakened {monster.name}, dealing an additional 🪓 __**{cull_damage}**__ damage!"

    return attack_message


def process_monster_turn(player: Player, monster: Monster) -> str:
    """Executes the monster's turn, applies damage to player, and returns combat log."""
    if player.is_invulnerable_this_combat:
        return f"The **Invulnerable** armor protects {player.name}, absorbing all damage from {monster.name}!"

    # --- Hit Chance Calculation ---
    base_hit_chance = calculate_monster_hit_chance(player, monster)
    effective_hit_chance = max(0.05, base_hit_chance)

    monster_attack_roll = random.random()

    if "Prescient" in monster.modifiers:
        effective_hit_chance = min(0.95, effective_hit_chance + 0.10)
    if "Lucifer-touched" in monster.modifiers and random.random() < 0.5:
        monster_attack_roll = min(monster_attack_roll, random.random())
    if "All-seeing" in monster.modifiers:
        effective_hit_chance = min(0.95, effective_hit_chance * 1.10)
    if "Celestial Watcher" in monster.modifiers:
        effective_hit_chance = 1.0

    monster_message = ""
    
    if monster_attack_roll <= effective_hit_chance: # Monster Hits
        damage_taken_base = calculate_damage_taken(player, monster)

        if "Celestial Watcher" in monster.modifiers: damage_taken_base = int(damage_taken_base * 1.2)
        if "Hellborn" in monster.modifiers: damage_taken_base += 2
        if "Hell's Fury" in monster.modifiers: damage_taken_base += 5
        if "Mirror Image" in monster.modifiers and random.random() < 0.2: damage_taken_base *= 2
        if "Unlimited Blade Works" in monster.modifiers: damage_taken_base *= 2

        # PDR / FDR Mitigation
        effective_pdr = player.get_total_pdr()
        if "Penetrator" in monster.modifiers: effective_pdr = max(0, effective_pdr - 20)
        damage_taken_base = max(0, int(damage_taken_base * (1 - (effective_pdr / 100))))

        effective_fdr = player.get_total_fdr()
        if "Clobberer" in monster.modifiers: effective_fdr = max(0, effective_fdr - 5)
        damage_taken_base = max(0, damage_taken_base - effective_fdr)

        # Minions
        minion_damage = 0
        if "Summoner" in monster.modifiers: minion_damage += int(damage_taken_base * (1/3))
        if "Infernal Legion" in monster.modifiers: minion_damage += damage_taken_base
        
        # Apply FDR to minions as well (implied in original logic via separate calculation, but grouping helps)
        minion_damage = max(0, minion_damage - effective_fdr)

        total_damage = damage_taken_base + minion_damage

        # Multistrike
        multistrike_damage = 0
        if "Multistrike" in monster.modifiers and random.random() <= effective_hit_chance:
            multistrike_damage = max(0, int(calculate_damage_taken(player, monster) * 0.5) - effective_fdr)
            total_damage += multistrike_damage

        # Executioner
        is_executed = False
        if "Executioner" in monster.modifiers and random.random() < 0.01:
            total_damage = max(total_damage, int(player.current_hp * 0.90))
            is_executed = True

        # Block & Dodge
        is_blocked = False
        is_dodged = False
        
        if "Unblockable" not in monster.modifiers and "Overwhelm" not in monster.modifiers:
            equipped_armor = player.equipped_armor
            block_chance = equipped_armor.block / 100 if equipped_armor else 0
            if random.random() <= block_chance:
                is_blocked = True
                
        if "Unavoidable" not in monster.modifiers and "Overwhelm" not in monster.modifiers:
            equipped_armor = player.equipped_armor
            dodge_chance = equipped_armor.evasion / 100 if equipped_armor else 0
            if random.random() <= dodge_chance:
                is_dodged = True

        if is_blocked:
            monster_message = f"{monster.name} {monster.flavor}, but your armor 🛡️ blocks all damage!\n"
        elif is_dodged:
            monster_message = f"{monster.name} {monster.flavor}, but you 🏃 nimbly step aside!\n"
        else:
            # Apply to Ward then HP
            damage_dealt_this_turn = 0
            if player.combat_ward > 0 and total_damage > 0:
                if total_damage <= player.combat_ward:
                    damage_dealt_this_turn = total_damage
                    player.combat_ward -= total_damage
                    monster_message += f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {total_damage} damage!\n"
                    total_damage = 0
                else:
                    damage_dealt_this_turn = player.combat_ward
                    monster_message += f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {player.combat_ward} damage, but shatters!\n"
                    total_damage -= player.combat_ward
                    player.combat_ward = 0
            
            if total_damage > 0:
                damage_dealt_this_turn += total_damage
                player.current_hp -= total_damage
                monster_message += f"{monster.name} {monster.flavor}. You take 💔 **{total_damage}** damage!\n"

            if "Vampiric" in monster.modifiers and damage_dealt_this_turn > 0:
                heal_amount = damage_dealt_this_turn * 10
                monster.hp = min(monster.max_hp, monster.hp + heal_amount)
                monster_message += f"The monster's **Vampiric** essence siphons life, healing it for **{heal_amount}** HP!\n"

            # Flavor messages for procs
            if is_executed: monster_message += f"The {monster.name}'s **Executioner** ability cleaves through you!\n"
            if minion_damage > 0: monster_message += f"Their minions strike for an additional {minion_damage} damage!\n"
            if multistrike_damage > 0: monster_message += f"{monster.name} strikes again for {multistrike_damage} damage!\n"
            if not monster_message: monster_message = f"{monster.name} {monster.flavor}, but you mitigate all its damage."

    else: # Miss
        if "Venomous" in monster.modifiers:
            player.current_hp = max(1, player.current_hp - 1)
            monster_message = f"{monster.name} misses, but their **Venomous** aura deals **1** 🐍 damage!"
        else:
            monster_message = f"{monster.name} misses!"

    player.current_hp = max(0, player.current_hp)
    return monster_message