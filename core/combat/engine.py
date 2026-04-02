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

    celestial_passive = player.get_celestial_armor_passive()

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

    # Helmet Passive: Juggernaut (Def -> Atk)
    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0

    if helmet_passive == "juggernaut" and helmet_lvl > 0:
        defence = player.get_total_defence()
        # 4% per level conversion
        atk_bonus = int(defence * (helmet_lvl * 0.04))
        player.base_attack += atk_bonus
        logs["Helmet Passive"] = f"**Juggernaut ({helmet_lvl})** empowers your strikes!\n⚔️ Attack boosted by **{atk_bonus}**."

    # Infernal Weapon Passives (combat-start effects)
    infernal = player.get_weapon_infernal()

    if infernal == "inverted_edge" and player.equipped_weapon:
        wep_atk = player.equipped_weapon.attack
        wep_def = player.equipped_weapon.defence
        player.equipped_weapon.attack = wep_def
        player.equipped_weapon.defence = wep_atk
        logs["Infernal Passive"] = (
            f"🔥 **Inverted Edge** warps the blade!\n"
            f"Weapon attack and defence are swapped ({wep_atk} ↔ {wep_def})."
        )

    elif infernal == "gilded_hunger" and player.equipped_weapon:
        rarity_bonus = int(player.equipped_weapon.rarity * 0.5)
        if rarity_bonus > 0:
            player.base_attack += rarity_bonus
            logs["Infernal Passive"] = (
                f"🔥 **Gilded Hunger** devours the weapon's rarity!\n"
                f"⚔️ Attack boosted by **{rarity_bonus}**."
            )

    elif infernal == "diabolic_pact":
        hp_cost = int(player.current_hp * 0.5)
        player.current_hp = max(1, player.current_hp - hp_cost)
        player.base_attack *= 2
        logs["Infernal Passive"] = (
            f"🔥 **Diabolic Pact** sealed in blood!\n"
            f"💀 Lost **{hp_cost}** HP.\n"
            f"⚔️ Attack **doubled** for this combat!"
        )

    elif infernal == "cursed_precision":
        player.base_crit_chance_target = max(1, player.base_crit_chance_target - 20)
        player.cursed_precision_active = True
        logs["Infernal Passive"] = (
            f"🔥 **Cursed Precision** clouds your strikes!\n"
            f"🎯 Crit chance greatly increased, but crits roll for the lower result."
        )

    # Void Accessory Passives (combat-start effects)
    void_passive = player.get_accessory_void_passive()

    if void_passive == "entropy" and player.equipped_weapon:
        atk_transfer = int(player.equipped_weapon.attack * 0.20)
        def_transfer = int(player.equipped_weapon.defence * 0.20)
        player.equipped_weapon.attack = player.equipped_weapon.attack - atk_transfer + def_transfer
        player.equipped_weapon.defence = player.equipped_weapon.defence - def_transfer + atk_transfer
        logs["Void Passive"] = (
            f"⬛ **Entropy** warps the weapon!\n"
            f"20% ATK↔DEF transferred (±{atk_transfer} ATK / ±{def_transfer} DEF)."
        )

    elif void_passive == "void_echo" and player.equipped_accessory:
        echo_bonus = int(player.base_attack * 0.15)
        if echo_bonus > 0:
            player.equipped_accessory.attack += echo_bonus
            logs["Void Passive"] = (
                f"⬛ **Void Echo** resonates with your power!\n"
                f"Accessory ATK boosted by **{echo_bonus}**."
            )

    elif void_passive == "unravelling" and monster.defence > 0:
        strip = int(monster.defence * 0.20)
        monster.defence = max(0, monster.defence - strip)
        logs["Void Passive"] = (
            f"⬛ **Unravelling** tears at {monster.name}'s defenses!\n"
            f"🛡️ Monster defence reduced by **{strip}** (20%)."
        )

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

    if player.apothecary_workers > 0:
        flat_bonus = int(player.apothecary_workers * 0.2)
        heal_amount += flat_bonus

    # Apply Divine Logic from Helmet
    potential_hp = player.current_hp + heal_amount
    overheal = 0
    if potential_hp > player.max_hp:
        helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        overheal = (potential_hp - player.max_hp) * helmet_lvl
        player.current_hp = player.max_hp
    else:
        player.current_hp = potential_hp
    
    player.potions -= 1
    
    msg = f"{player.name} uses a potion and heals for **{heal_amount - overheal}** HP!"
    if player.apothecary_workers > 0:
        msg += f" (Apothecary: +{int(player.apothecary_workers * 0.2)})"
    
    if player.get_helmet_passive() == "divine" and overheal > 0:
        player.combat_ward += overheal
        msg += f"\n**Divine** converts **{overheal}** overheal into 🔮 Ward!"
        
    msg += f"\n**{player.potions}** potions left."
    return msg

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
    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0

    # --- Pre-Attack Multipliers ---
    # --- Emblem Multipliers ---
    # Base Damage (e.g. 2% per tier)
    if not monster.is_boss:
        combat_dmg_tiers = player.get_emblem_bonus("combat_dmg")
        if combat_dmg_tiers > 0:
            attack_multiplier *= (1 + (combat_dmg_tiers * 0.02))

    # Boss Damage (e.g. 5% per tier)
    if monster.is_boss:
        boss_dmg_tiers = player.get_emblem_bonus("boss_dmg")
        if boss_dmg_tiers > 0:
            attack_multiplier *= (1 + (boss_dmg_tiers * 0.05))
            
    # Slayer Task Damage (e.g. 5% per tier)
    if player.active_task_species == monster.species:
        slayer_dmg_tiers = player.get_emblem_bonus("slayer_dmg")
        if slayer_dmg_tiers > 0:
            attack_multiplier *= (1 + (slayer_dmg_tiers * 0.05))

    acc_value_bonus = 0
    # Accuracy (e.g. +2 flat hit roll per tier)
    emblem_acc = player.get_emblem_bonus("accuracy")
    if emblem_acc > 0:
        acc_value_bonus += (emblem_acc * 2)

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

    # Frenzy (Low HP Scaling)
    # Scale: 0.5% (L1) -> 2.5% (L5) per 1% HP missing
    if helmet_passive == "frenzy" and helmet_lvl > 0:
        missing_hp_pct = (1 - (player.current_hp / player.max_hp)) * 100
        scaling_factor = 0.005 * helmet_lvl 
        multiplier_bonus = (missing_hp_pct * scaling_factor)
        
        attack_multiplier *= (1 + multiplier_bonus)
        passive_message += f"**Frenzy ({helmet_lvl})** rage increases damage by {int(multiplier_bonus*100)}%!\n"
    
    # --- Hit Chance Calculation ---
    hit_chance = calculate_hit_chance(player, monster)
    if "Dodgy" in monster.modifiers:
        hit_chance = max(0.05, hit_chance - 0.10)
        passive_message += f"The monster's **Dodgy** nature makes it harder to hit!\n"

    attack_roll = random.randint(0, 100)
    wep_acc_passive_bonus, passive_message = check_for_accuracy(player, passive_message)
    acc_value_bonus += wep_acc_passive_bonus

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

    # Voracious: each round without a crit lowers crit target by 5 (stacking)
    infernal = player.get_weapon_infernal()
    if infernal == "voracious" and player.voracious_stacks > 0:
        crit_target = max(1, crit_target - (player.voracious_stacks * 5))

    crit_roll = random.randint(0, 100)
    if is_hit and crit_roll > crit_target and "Impenetrable" not in monster.modifiers:
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
            passive_message += f"**Deftness ({glove_lvl})** hones your crits!\n"
            
        
        crit_min = max(1, int(max_hit_calc * crit_damage_floor_multiplier) + 1)
        # Ensure max >= min
        crit_max = max(crit_min, max_hit_calc)
        
        crit_base_damage = int(random.randint(crit_min, crit_max) * 2.0)
        # Emblem crit bonus
        crit_dmg_tiers = player.get_emblem_bonus("crit_dmg")
        if crit_dmg_tiers > 0:
            crit_base_damage = crit_base_damage * (1 + (crit_dmg_tiers * 0.05))

        # Apply Insight
        if helmet_passive == "insight" and helmet_lvl > 0:
            # Add 0.1x multiplier per level
            extra_mult = helmet_lvl * 0.1
            crit_base_damage = int(crit_base_damage * (1 + extra_mult))
            passive_message += f"**Insight ({helmet_lvl})** exposes a weak point! (Crit Dmg +{int(extra_mult*100)}%)\n"

        if "Smothering" in monster.modifiers:
            crit_base_damage = int(crit_base_damage * 0.80)
            passive_message += f"The monster's **Smothering** aura dampens your critical hit!\n"

        # Cursed Precision: roll twice, take lower
        if player.cursed_precision_active:
            alt_base = int(random.randint(crit_min, crit_max) * 2.0)
            if alt_base < crit_base_damage:
                crit_base_damage = alt_base
            passive_message += f"**Cursed Precision** — the weaker roll applies!\n"

        actual_hit_pre_ward_gen = int(crit_base_damage * attack_multiplier)

        # Last Rites: bonus 10% of enemy current HP on crit
        if infernal == "last_rites" and monster.hp > 0:
            last_rites_bonus = int(monster.hp * 0.10)
            actual_hit_pre_ward_gen += last_rites_bonus
            passive_message += f"**Last Rites** seals {monster.name}'s fate! (+{last_rites_bonus})\n"

        # Voracious: reset stacks on crit
        if infernal == "voracious":
            if player.voracious_stacks > 0:
                passive_message += f"**Voracious** resets after a crit! ({player.voracious_stacks} stacks lost)\n"
            player.voracious_stacks = 0

        # Void Gaze: each crit reduces monster ATK by 1% (max 30 stacks)
        void_passive_crit = player.get_accessory_void_passive()
        if void_passive_crit == "void_gaze" and player.gaze_stacks < 30 and monster.attack > 0:
            player.gaze_stacks += 1
            atk_reduction = max(1, int(monster.attack * 0.01))
            monster.attack = max(0, monster.attack - atk_reduction)
            passive_message += f"⬛ **Void Gaze** ({player.gaze_stacks}/30) — {monster.name}'s ATK -{atk_reduction}!\n"

        # Fracture: 5% chance on crit to instantly kill (no uber bosses)
        if void_passive_crit == "fracture" and not getattr(monster, 'is_uber', False) and random.random() < 0.05:
            actual_hit_pre_ward_gen = monster.hp
            passive_message += "💀 **Fracture** tears open a void rift — **instant kill!**\n"

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

        # Voracious: increment stacks on non-crit hit
        if infernal == "voracious":
            player.voracious_stacks += 1
            passive_message += f"**Voracious** charges! ({player.voracious_stacks} stack{'s' if player.voracious_stacks != 1 else ''})\n"

        attack_message = passive_message + attack_message + f"Hit! Damage: 💥 **{actual_hit_pre_ward_gen - echo_damage}**"
        if echo_hit:
            attack_message += f"\nThe hit is 🎶 echoed!\nEcho damage: 💥 **{echo_damage}**"

    else:  # Miss
        poison_damage_on_miss = check_for_poison_bonus(player, attack_multiplier)
        void_passive_miss = player.get_accessory_void_passive()
        miss_dmg_parts = []

        # Perdition: misses deal 75% weapon attack
        if infernal == "perdition" and player.equipped_weapon:
            perdition_dmg = int(player.equipped_weapon.attack * 0.75)
            if perdition_dmg > 0:
                actual_hit_pre_ward_gen += perdition_dmg
                miss_dmg_parts.append(f"**Perdition** tears through for 🔥 **{perdition_dmg}**")

        # Poison on miss
        if poison_damage_on_miss > 0:
            actual_hit_pre_ward_gen += poison_damage_on_miss
            miss_dmg_parts.append(f"poison 🐍 deals **{poison_damage_on_miss}**")

        # Oblivion: converts miss into 50% of min damage, stacks with all miss sources
        if void_passive_miss == "oblivion":
            base_max = player.get_total_attack()
            glove_p = player.get_glove_passive()
            glove_l = player.equipped_glove.passive_lvl if player.equipped_glove else 0
            base_min = max(1, int(base_max * (glove_l * 0.02))) if glove_p == "adroit" and glove_l > 0 else 1
            oblivion_dmg = max(1, int(base_min * 0.5))
            actual_hit_pre_ward_gen += oblivion_dmg
            miss_dmg_parts.append(f"**Oblivion** phases through for ⬛ **{oblivion_dmg}**")

        if miss_dmg_parts:
            attack_message = passive_message + "Miss! But " + ", ".join(miss_dmg_parts) + " damage."
        else:
            attack_message = passive_message + "Miss!"

        # Voracious: increment stacks on miss too
        if infernal == "voracious":
            player.voracious_stacks += 1

    # --- Apply Damage Reductions ---
    actual_hit = actual_hit_pre_ward_gen

    if "Radiant Protection" in monster.modifiers and actual_hit > 0:
        reduction = int(actual_hit * 0.60)
        actual_hit = max(0, actual_hit - reduction)
        attack_message += f"\n✨ **Radiant Protection** mitigates {reduction} damage!"

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

    # Leeching (Helmet passive)
    if actual_hit > 0 and helmet_passive == "leeching" and helmet_lvl > 0:
        leech_pct = 0.02 * helmet_lvl # 2% to 10%
        heal_amt = int(actual_hit * leech_pct)
        if heal_amt > 0:
            player.current_hp = min(player.max_hp, player.current_hp + heal_amt)
            attack_message += f"\n**Leeching** drains life, healing you for **{heal_amt}** HP."

    # Ward-regen (Celestial armor passive)
    if player.get_celestial_armor_passive() == 'celestial_ghostreaver':
        regen_amount = random.randint(50, 200)
        if regen_amount > 0:
            player.combat_ward += regen_amount
            attack_message += f"\n✨ **Celestial Ghostreaver** restores **{regen_amount}** 🔮 Ward!"

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

    # Track combat round for Twin Strike
    monster.combat_round += 1
    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    
    # Store previous ward to check for break later
    previous_ward = player.combat_ward

    # --- Hit Chance Calculation ---
    base_hit_chance = calculate_monster_hit_chance(player, monster)
    effective_hit_chance = max(0.05, base_hit_chance)
    celestial_passive = player.get_celestial_armor_passive()
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

    # Void Drain: siphons player ATK/DEF every monster turn (regardless of hit)
    if "Void Aura" in monster.modifiers:
        drain_atk = max(1, int(player.base_attack * 0.05))
        drain_def = max(0, int(player.base_defence * 0.05))
        player.base_attack = max(1, player.base_attack - drain_atk)
        player.base_defence = max(0, player.base_defence - drain_def)
        monster_message += f"🌑 **Void Drain** siphons **{drain_atk}** ATK and **{drain_def}** DEF!\n"

    if monster_attack_roll <= effective_hit_chance: # Monster Hits
        
        # 1. PDR / FDR Setup & Celestial Fortress
        effective_pdr = player.get_total_pdr()
        if celestial_passive == 'celestial_fortress':
            missing_hp_pct = (1 - (player.current_hp / player.max_hp)) * 100
            effective_pdr += int(missing_hp_pct / 5.0) # +1% PDR per 5% missing HP

        effective_fdr = player.get_total_fdr()

        # 2. Damage Roll Helper
        def roll_monster_dmg():
            dmg = calculate_damage_taken(player, monster)
            if "Celestial Watcher" in monster.modifiers: dmg = int(dmg * 1.2)
            if "Hellborn" in monster.modifiers: dmg += 2
            if "Hell's Fury" in monster.modifiers: dmg += 5
            if "Mirror Image" in monster.modifiers and random.random() < 0.2: dmg *= 2
            if "Unlimited Blade Works" in monster.modifiers: dmg *= 2

            # Mitigation
            pdr = effective_pdr
            if "Penetrator" in monster.modifiers: pdr = max(0, pdr - 20)
            dmg = max(0, int(dmg * (1 - (pdr / 100))))
            
            fdr = effective_fdr
            if "Clobberer" in monster.modifiers: fdr = max(0, fdr - 5)
            dmg = max(0, dmg - fdr)

            # Minions
            minions = 0
            if "Summoner" in monster.modifiers: minions += int(dmg * (1/3))
            if "Infernal Legion" in monster.modifiers: minions += dmg
            minions = max(0, minions - fdr)

            return dmg + minions, dmg, minions

        # 3. Base Damage & Unlucky Enemy Logic
        total_damage, dmg_base, minion_dmg = roll_monster_dmg()
        
        if celestial_passive == 'celestial_sanctity':
            alt_total, alt_base, alt_minion = roll_monster_dmg()
            if alt_total < total_damage:
                total_damage, dmg_base, minion_dmg = alt_total, alt_base, alt_minion

        # 4. Multistrike & Executioner
        multistrike_damage = 0
        if "Multistrike" in monster.modifiers and random.random() <= effective_hit_chance:
            multistrike_damage = max(0, int(calculate_damage_taken(player, monster) * 0.5) - effective_fdr)
            total_damage += multistrike_damage

        is_executed = False
        if "Executioner" in monster.modifiers and random.random() < 0.01:
            total_damage = max(total_damage, int(player.current_hp * 0.90))
            is_executed = True

        # 5. Block & Dodge (With Celestial Overrides)
        is_blocked = False
        is_dodged = False
        
        if "Unblockable" not in monster.modifiers:
            equipped_armor = player.equipped_armor
            block_chance = equipped_armor.block / 100 if equipped_armor else 0
            if celestial_passive == 'celestial_glancing_blows':
                block_chance *= 2.0
            if random.random() <= block_chance:
                is_blocked = True
                
        if "Unavoidable" not in monster.modifiers:
            equipped_armor = player.equipped_armor
            dodge_chance = equipped_armor.evasion / 100 if equipped_armor else 0
            if celestial_passive == 'celestial_wind_dancer':
                dodge_chance *= 3.0
            if random.random() <= dodge_chance:
                is_dodged = True

        # 6. Resolve Mitigation States
        if is_dodged:
            monster_message = f"{monster.name} {monster.flavor}, but you 🏃 nimbly step aside!\n"
            total_damage = 0
            if helmet_passive == "ghosted" and helmet_lvl > 0:
                ward_gain = helmet_lvl * 10
                player.combat_ward += ward_gain
                monster_message += f"**Ghosted ({helmet_lvl})** manifests **{ward_gain}** 🔮 Ward from the movement!\n"
                
        elif is_blocked:
            if celestial_passive == 'celestial_glancing_blows':
                total_damage = int(total_damage * 0.5)
                monster_message = f"{monster.name} {monster.flavor}, but your armor 🛡️ partially blocks it (Bleedthrough: {total_damage})!\n"
            else:
                monster_message = f"{monster.name} {monster.flavor}, but your armor 🛡️ blocks all damage!\n"
                total_damage = 0
                
            if helmet_passive == "thorns" and helmet_lvl > 0:
                reflect_dmg = int(dmg_base * (helmet_lvl * 1.0))
                monster.hp -= reflect_dmg
                monster_message += f"**Thorns ({helmet_lvl})** reflects **{reflect_dmg}** damage back!\n"

        # 7. Apply Final Damage to Ward/HP
        if total_damage > 0 and not is_dodged:
            damage_dealt_this_turn = 0

            # Nullfield: 15% chance to absorb the hit entirely into the void
            void_passive_def = player.get_accessory_void_passive()
            if void_passive_def == "nullfield" and random.random() < 0.15:
                monster_message += f"⬛ **Nullfield** absorbs the strike into the void!\n"
                total_damage = 0

            if player.combat_ward > 0:
                if total_damage <= player.combat_ward:
                    damage_dealt_this_turn = total_damage
                    player.combat_ward -= total_damage
                    if not is_blocked:
                        monster_message += f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {total_damage} damage!\n"
                    total_damage = 0
                else:
                    damage_dealt_this_turn = player.combat_ward
                    if not is_blocked:
                        monster_message += f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {player.combat_ward} damage, but shatters!\n"
                    total_damage -= player.combat_ward
                    player.combat_ward = 0

            # Slayer Resilience
            if player.active_task_species == monster.species:
                slayer_def_tiers = player.get_emblem_bonus("slayer_def")
                if slayer_def_tiers > 0:
                    mitigation = min(0.50, slayer_def_tiers * 0.02)
                    total_damage = int(total_damage * (1 - mitigation))

            # HP Application & Celestial Vow
            if total_damage > 0:
                if celestial_passive == 'celestial_vow' and (player.current_hp - total_damage <= 0) and not getattr(player, 'celestial_vow_used', False):
                    player.current_hp = 1
                    ward_gain = int(player.max_hp * 0.5)
                    player.combat_ward += ward_gain
                    player.celestial_vow_used = True
                    monster_message += f"\n✨ **Celestial Vow** activates! You survive the fatal blow and gain {ward_gain} 🔮 Ward!"
                    damage_dealt_this_turn += (player.current_hp - 1)
                else:
                    damage_dealt_this_turn += total_damage
                    player.current_hp -= total_damage
                    if not is_blocked or celestial_passive != 'celestial_glancing_blows':
                        monster_message += f"{monster.name} {monster.flavor}. You take 💔 **{total_damage}** damage!\n"

            # Eternal Hunger: stacks per hit taken; at 10 stacks consume all and devour enemy HP
            if void_passive_def == "eternal_hunger" and damage_dealt_this_turn > 0:
                player.hunger_stacks += 1
                if player.hunger_stacks >= 10:
                    hunger_dmg = int(monster.max_hp * 0.10)
                    monster.hp = max(0, monster.hp - hunger_dmg)
                    player.current_hp = player.max_hp
                    player.hunger_stacks = 0
                    monster_message += (
                        f"⬛ **Eternal Hunger** consumes the pain!\n"
                        f"💀 Devoured **{hunger_dmg}** HP ({monster.name}'s max × 10%)!\n"
                        f"❤️ Wounds consumed — HP restored to full!\n"
                    )
                else:
                    monster_message += f"⬛ **Eternal Hunger** feeds ({player.hunger_stacks}/10 stacks).\n"

            # Volatile Explosion
            if helmet_passive == "volatile" and helmet_lvl > 0:
                if previous_ward > 0 and player.combat_ward == 0:
                    boom_dmg = int(player.max_hp * helmet_lvl)
                    monster.hp -= boom_dmg
                    monster_message += f"\n💥 **Volatile** Shield shatters, dealing **{boom_dmg}** damage to {monster.name}!\n"
                    
            # Vampiric Mod
            if "Vampiric" in monster.modifiers and damage_dealt_this_turn > 0:
                heal_amount = damage_dealt_this_turn * 10
                monster.hp = min(monster.max_hp, monster.hp + heal_amount)
                monster_message += f"The monster's **Vampiric** essence siphons life, healing it for **{heal_amount}** HP!\n"

            if is_executed: monster_message += f"The {monster.name}'s **Executioner** ability cleaves through you!\n"
            if minion_dmg > 0: monster_message += f"Their minions strike for an additional {minion_dmg} damage!\n"
            if multistrike_damage > 0: monster_message += f"{monster.name} strikes again for {multistrike_damage} damage!\n"

            # Twin Strike: every even round, a second coordinated blow lands at 50% damage
            if "Twin Strike" in monster.modifiers and monster.combat_round % 2 == 0:
                twin_raw, _, _ = roll_monster_dmg()
                twin_dmg = max(1, int(twin_raw * 0.5))
                player.current_hp = max(0, player.current_hp - twin_dmg)
                monster_message += f"⚡ **Twin Strike!** The bound sovereigns strike as one for **{twin_dmg}** damage!\n"

            if not monster_message: monster_message = f"{monster.name} {monster.flavor}, but you mitigate all its damage."

    else: # Miss
        if "Venomous" in monster.modifiers:
            player.current_hp = max(1, player.current_hp - 1)
            monster_message = f"{monster.name} misses, but their **Venomous** aura deals **1** 🐍 damage!"
        else:
            monster_message = f"{monster.name} misses!"

    player.current_hp = max(0, player.current_hp)
    return monster_message


def log_combat_debug(player: Player, monster: Monster, logger: logging.Logger) -> None:
    """Calculates and logs the final stats and theoretical maximum damage of both entities."""
    
    # --- PLAYER MAX CALCULATION ---
    p_atk = player.get_total_attack()
    p_def = player.get_total_defence()
    p_crit_chance = 100 - player.get_current_crit_target()
    
    # Base Crit multiplier logic
    crit_mult = 2.0
    helmet_passive = player.get_helmet_passive()
    if helmet_passive == "insight":
        lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        crit_mult += (lvl * 0.1)
    if "Smothering" in monster.modifiers:
        crit_mult *= 0.8
        
    p_max_dmg = int(p_atk * crit_mult)

    # Overwhelm/Instability/Mystical Might passives can make this jump wildly,
    # but we just want the standard mechanical max hit for debugging bounds.
    if player.get_glove_passive() == "instability":
        lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
        p_max_dmg = int(p_max_dmg * (1.50 + (lvl * 0.10)))

    # --- MONSTER MAX CALCULATION ---
    m_atk = monster.attack
    m_def = monster.defence
    
    diff = max(0, m_atk - p_def)
    
    if m_atk <= 3: base_m_dmg = 5
    elif m_atk <= 20: base_m_dmg = 6
    else: base_m_dmg = 9 + int(monster.level // 10)
    
    # 3 is the max randint roll per 10 diff points
    max_bonus_dmg = int(diff / 10) * 3 
    base_m_dmg += max_bonus_dmg
    
    if "Celestial Watcher" in monster.modifiers: base_m_dmg = int(base_m_dmg * 1.2)
    if "Hellborn" in monster.modifiers: base_m_dmg += 2
    if "Hell's Fury" in monster.modifiers: base_m_dmg += 5
    
    # Mitigation Check
    pdr = player.get_total_pdr()
    if "Penetrator" in monster.modifiers: pdr = max(0, pdr - 20)
    
    fdr = player.get_total_fdr()
    if "Clobberer" in monster.modifiers: fdr = max(0, fdr - 5)

    m_max_dmg = int(base_m_dmg * (1 - (pdr / 100))) - fdr
    m_max_dmg = max(0, m_max_dmg)
    
    if "Mirror Image" in monster.modifiers or "Unlimited Blade Works" in monster.modifiers:
        m_max_dmg *= 2
        
    # --- LOG OUTPUT ---
    logger.info(f"--- COMBAT DEBUG: {player.name} VS {monster.name} ---")
    logger.info(f"PLAYER : HP {player.current_hp}/{player.max_hp} | Atk {p_atk} | Def {p_def} | Ward {player.combat_ward} | Crit {p_crit_chance}% | PDR {player.get_total_pdr()}% | FDR {player.get_total_fdr()}")
    logger.info(f"MONSTER: HP {monster.hp}/{monster.max_hp} | Atk {m_atk} | Def {m_def} | Mods: {monster.modifiers}")
    logger.info(f"THEORETICAL MAX HIT -> Player: ~{p_max_dmg} | Monster: ~{m_max_dmg}")
    logger.info(f"--------------------------------------------------")