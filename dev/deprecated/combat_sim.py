# combat_simulator.py
import random
import math
import copy # For deep copying configurations if necessary

# --- Imports from your provided files ---
# Ensure these files are accessible (e.g., in the same directory or via PYTHONPATH)
from core.models import Player, Monster 
from core.combat_calcs import (
    calculate_hit_chance, calculate_monster_hit_chance,
    calculate_damage_taken, check_cull,
    check_for_polished, check_for_sturdy, check_for_accuracy,
    check_for_crit_bonus, check_for_burn_bonus, check_for_spark_bonus,
    check_for_echo_bonus, check_for_poison_bonus
)

# --- Helper class for simulation logging (optional) ---
class SimLogger:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def info(self, msg):
        if self.verbose:
            print(f"[SIM_INFO] {msg}")
    
    def warning(self, msg):
        # Always print warnings
        print(f"[SIM_WARNING] {msg}")

# --- Embed Substitute for Passive Checks ---
class LoggingEmbedSubstitute:
    """A substitute for discord.Embed to capture messages from passive checks."""
    def __init__(self, log_list, logger: SimLogger):
        self.log_list = log_list
        self.logger = logger

    def add_field(self, name, value, inline=False):
        msg = f"{name}: {value}"
        self.log_list.append(msg)
        self.logger.info(f"[PASSIVE_LOG] {msg}")


    def clear_fields(self):
        pass # Not needed for this use case

# --- Adapting/Replicating Combat Cog Logic ---

def apply_monster_stat_effects_to_player(player: Player, monster: Monster, logger: SimLogger):
    """Applies monster modifier effects that alter player stats at combat start."""
    modifier_effects = {
        "Shield-breaker": lambda p, m: setattr(p, "ward", 0),
        "Impenetrable": lambda p, m: setattr(p, "crit", min(100, p.crit + 5)), # Capped at 100
        "Unblockable": lambda p, m: setattr(p, "block", 0),
        "Unavoidable": lambda p, m: setattr(p, "evasion", 0),
        "Enfeeble": lambda p, m: setattr(p, "attack", max(0, int(p.attack * 0.9))),
        "Overwhelm": lambda p, m: (
            setattr(p, "ward", 0),
            setattr(p, "block", 0),
            setattr(p, "evasion", 0)
        )
    }
    for modifier in monster.modifiers:
        if modifier in modifier_effects:
            modifier_effects[modifier](player, monster)
            logger.info(f'Applied monster modifier "{modifier}" effect to player stats.')

def apply_player_combat_start_passives(player: Player, monster: Monster, logger: SimLogger, passive_log_list: list):
    """Applies player's combat start passives."""
    player.invulnerable = False # Reset invulnerability
    if player.armor_passive == "Invulnerable" and random.random() < 0.2:
        msg = "Armor Passive: Invulnerable activates. Player receives divine protection."
        passive_log_list.append(msg)
        logger.info(f"[PASSIVE] {msg}")
        player.invulnerable = True

    if player.armor_passive == "Omnipotent" and random.random() < 0.2:
        monster.attack = 0
        monster.defence = 0
        msg = "Armor Passive: Omnipotent activates. Monster attack and defense set to 0."
        passive_log_list.append(msg)
        logger.info(f"[PASSIVE] {msg}")
            
    if player.acc_passive == "Absorb":
        absorb_chance = player.acc_lvl * 0.10
        if random.random() <= absorb_chance:
            monster_stats_total = monster.attack + monster.defence
            if monster_stats_total > 0:
                absorb_amount = max(1, int(monster_stats_total * 0.10))
                player.attack += absorb_amount
                player.defence += absorb_amount
                msg = (f"Accessory Passive: Absorb (Lvl {player.acc_lvl}) activates! "
                       f"Player ATK +{absorb_amount}, DEF +{absorb_amount}")
                passive_log_list.append(msg)
                logger.info(f"[PASSIVE] {msg}")
    
    # Use LoggingEmbedSubstitute for passives that log via embed.add_field
    embed_sub = LoggingEmbedSubstitute(passive_log_list, logger)
    
    # check_for_polished and sturdy modify player/monster and log through embed_sub
    player, monster, _ = check_for_polished(player, monster, embed_sub)
    player, monster, _ = check_for_sturdy(player, monster, embed_sub)
    # No need to reassign player, monster as they are mutable objects modified in place.

def simulate_player_turn(player: Player, monster: Monster, logger: SimLogger):
    """Simulates a single player turn, returning the modified monster, damage dealt, and log messages."""
    turn_messages = []
    damage_dealt_this_turn = 0
    
    initial_monster_hp = monster.hp

    # Passive message accumulation (local to this turn, then added to turn_messages)
    current_turn_passive_msgs = []

    attack_multiplier = 1.0

    if player.acc_passive == "Obliterate":
        double_damage_chance = player.acc_lvl * 0.02
        if random.random() <= double_damage_chance:
            current_turn_passive_msgs.append(f"**Obliterate (Lvl {player.acc_lvl})** activates, doubling 💥 damage dealt!")
            attack_multiplier *= 2.0

    if player.armor_passive == "Mystical Might" and random.random() < 0.2:
        attack_multiplier *= 10.0
        current_turn_passive_msgs.append("The **Mystical Might** armor imbues with power, massively increasing damage!")

    hit_chance = calculate_hit_chance(player, monster)
    attack_roll = random.randint(0, 100)
    final_miss_threshold = 100 - int(hit_chance * 100)
    
    acc_value_bonus, accuracy_msg_text = check_for_accuracy(player, "")
    if accuracy_msg_text.strip(): current_turn_passive_msgs.append(accuracy_msg_text.strip())

    if player.acc_passive == "Lucky Strikes":
        lucky_strike_chance = player.acc_lvl * 0.10
        if random.random() <= lucky_strike_chance:
            attack_roll2 = random.randint(0, 100)
            attack_roll = max(attack_roll, attack_roll2)
            current_turn_passive_msgs.append(f"**Lucky Strikes (Lvl {player.acc_lvl})** activates! Hit chance is now 🍀 lucky!")

    if "Suffocator" in monster.modifiers and random.random() < 0.2:
        current_turn_passive_msgs.append(f"The {monster.name}'s **Suffocator** aura attempts to stifle your attack! Hit chance is now 💀 unlucky!")
        attack_roll2 = random.randint(0, 100)
        attack_roll = min(attack_roll, attack_roll2)
            
    weapon_crit_bonus_chance = check_for_crit_bonus(player)

    if "Shields-up" in monster.modifiers and random.random() < 0.1:
        attack_multiplier = 0
        current_turn_passive_msgs.append(f"{monster.name} projects a powerful magical barrier, nullifying the hit!")

    is_crit = False
    if attack_multiplier > 0:
        crit_target = player.crit - weapon_crit_bonus_chance 
        if attack_roll > crit_target:
            is_crit = True
    
    is_hit = False
    if attack_multiplier > 0:
        effective_attack_roll_for_hit = attack_roll + acc_value_bonus
        if effective_attack_roll_for_hit >= final_miss_threshold:
            is_hit = True

    # Combine passive messages now
    turn_messages.extend(current_turn_passive_msgs)
    
    current_hit_damage_value = 0 # Damage value of this hit action before reductions/Time Lord

    if is_crit:
        max_hit_calc = player.attack
        # Ensure max_hit_calc * 0.5 is an int for randint
        crit_base_min = int(max_hit_calc * 0.5) + 1
        crit_base_max = max_hit_calc
        if crit_base_min > crit_base_max: crit_base_min = crit_base_max # Handle edge case if attack is very low

        crit_roll_damage = random.randint(crit_base_min, crit_base_max) if crit_base_max >= crit_base_min else crit_base_min

        current_hit_damage_value = int(crit_roll_damage * 2.0 * attack_multiplier)
        
        crit_log_msg = "Critical Hit!"
        if weapon_crit_bonus_chance > 0: crit_log_msg = "The weapon glimmers with power! " + crit_log_msg
        turn_messages.append(f"{crit_log_msg} Damage: 🗡️ **{current_hit_damage_value}**")

    elif is_hit:
        base_damage_max = player.attack
        base_damage_min = 1
        
        burn_spark_hit_msgs = [] # Messages for burn/spark/echo specific to this hit
        _base_damage_max, burn_msg = check_for_burn_bonus(player, base_damage_max, "")
        if burn_msg.strip(): burn_spark_hit_msgs.append(burn_msg.strip())
        base_damage_max = _base_damage_max
        
        _base_damage_min, spark_msg = check_for_spark_bonus(player, base_damage_min, base_damage_max, "")
        if spark_msg.strip(): burn_spark_hit_msgs.append(spark_msg.strip())
        base_damage_min = _base_damage_min
        
        base_damage_min = max(0, base_damage_min)
        if base_damage_min >= base_damage_max : base_damage_min = max(0, base_damage_max -1)
        
        rolled_damage = 0
        if base_damage_max > base_damage_min :
            rolled_damage = random.randint(base_damage_min, base_damage_max)
        elif base_damage_max >=0 : # If max == min, or max is 0.
            rolled_damage = base_damage_max

        main_hit_component = int(rolled_damage * attack_multiplier)
        
        # check_for_echo_bonus returns (total_damage_with_echo, echo_occured_flag, echo_amount)
        total_damage_with_echo, echo_hit_flag, echo_damage_amount = check_for_echo_bonus(player, main_hit_component)
        current_hit_damage_value = total_damage_with_echo

        turn_messages.extend(burn_spark_hit_msgs) # Add burn/spark messages
        turn_messages.append(f"Hit! Damage: 💥 **{main_hit_component}**") # Log main hit part
        if echo_hit_flag:
            turn_messages.append(f"The hit is 🎶 echoed! Echo damage: 💥 **{echo_damage_amount}**")
    else: # Miss
        current_hit_damage_value = 0 
        poison_damage_on_miss = check_for_poison_bonus(player, attack_multiplier)
            
        if poison_damage_on_miss > 0:
            turn_messages.append(f"Miss! However, the lingering poison 🐍 deals **{poison_damage_on_miss}** damage.")
            current_hit_damage_value = poison_damage_on_miss
        else:
            turn_messages.append("Miss!")

    # Apply monster's damage reduction, Time Lord, Cull
    damage_to_apply_to_monster_hp = current_hit_damage_value
    if "Titanium" in monster.modifiers and damage_to_apply_to_monster_hp > 0:
        reduction = int(damage_to_apply_to_monster_hp * 0.10)
        damage_to_apply_to_monster_hp = max(0, damage_to_apply_to_monster_hp - reduction)
        turn_messages.append(f"{monster.name}'s **Titanium** plating reduces damage by {reduction}.")

    if damage_to_apply_to_monster_hp >= monster.hp:
        if "Time Lord" in monster.modifiers and random.random() < 0.80 and monster.hp > 1:
            damage_to_apply_to_monster_hp = monster.hp - 1
            turn_messages.append(f"A fatal blow! But **{monster.name}**'s **Time Lord** allows it to cheat death, surviving at 1 HP!")
        else:
            damage_to_apply_to_monster_hp = monster.hp # Exact kill
    
    monster.hp -= damage_to_apply_to_monster_hp
    damage_dealt_this_turn = damage_to_apply_to_monster_hp # This is the actual HP reduction from this hit
    
    if monster.hp > 0 and check_cull(player, monster):
        cull_damage_value = monster.hp -1 
        if cull_damage_value > 0:
            monster.hp = 1
            damage_dealt_this_turn += cull_damage_value # Add cull to total for turn
            turn_messages.append(f"{player.name}'s **{player.weapon_passive}** culls {monster.name} for an additional 🪓 __**{cull_damage_value}**__ damage, leaving it at 1 HP!")
            
    for msg_idx, msg_content in enumerate(turn_messages):
        logger.info(f"[P->M] {msg_content}")
        
    return monster, damage_dealt_this_turn, turn_messages


def simulate_monster_turn(player: Player, monster: Monster, logger: SimLogger):
    """Simulates a single monster turn, returning the modified player, damage taken by player, and log messages."""
    turn_messages = []
    damage_taken_by_player_hp_this_turn = 0

    if player.invulnerable:
        msg = f"The **Invulnerable** armor protects {player.name}, absorbing all damage from {monster.name}!"
        turn_messages.append(msg)
        logger.info(f"[M->P] {msg}")
        return player, 0, turn_messages
    
    base_monster_hit_chance = calculate_monster_hit_chance(player, monster)
    player_evasion_value = (0.01 + (player.evasion / 400.0)) if player.evasion > 0 else 0.0
    effective_hit_chance = max(0.05, base_monster_hit_chance - player_evasion_value)

    monster_attack_roll = random.random()

    if "Lucifer-touched" in monster.modifiers and random.random() < 0.5:
        monster_attack_roll = min(monster_attack_roll, random.random()) # Lucky for monster
    if "All-seeing" in monster.modifiers:
        effective_hit_chance = min(0.95, effective_hit_chance * 1.10)
    if "Celestial Watcher" in monster.modifiers:
        effective_hit_chance = 1.0

    if monster_attack_roll <= effective_hit_chance: # Monster hits
        damage_roll_base = calculate_damage_taken(player, monster)

        # Apply monster damage modifiers
        modified_damage = damage_roll_base
        if "Celestial Watcher" in monster.modifiers: modified_damage = int(modified_damage * 1.2)
        if "Hellborn" in monster.modifiers: modified_damage += 2
        if "Hell's Fury" in monster.modifiers: modified_damage += 5
        if "Mirror Image" in monster.modifiers and random.random() < 0.2: modified_damage *= 2
        if "Unlimited Blade Works" in monster.modifiers: modified_damage *= 2
        
        minion_damage_component = 0
        if "Summoner" in monster.modifiers: minion_damage_component = int(modified_damage * (1/3)) # Based on main hit after mods
        if "Infernal Legion" in monster.modifiers: minion_damage_component = modified_damage # Echoes main hit after mods
        
        total_potential_damage = modified_damage + minion_damage_component

        multistrike_component = 0
        if "Multistrike" in monster.modifiers and random.random() <= effective_hit_chance: # Check hit again for multistrike
            multistrike_new_roll = calculate_damage_taken(player, monster) # New base roll
            # Apply mods to multistrike? Original scales only by 0.5 after new roll
            multistrike_component = int(multistrike_new_roll * 0.5)
            total_potential_damage += multistrike_component

        is_executed_flag = False
        if "Executioner" in monster.modifiers and random.random() < 0.01:
            execution_damage = int(player.hp * 0.90)
            total_potential_damage = max(total_potential_damage, execution_damage)
            is_executed_flag = True
            logger.info(f"Executioner proc: {execution_damage} damage against player HP {player.hp}")

        damage_after_block = total_potential_damage
        block_chance = min(0.75, (player.block / 200.0) if player.block > 0 else 0.0)
        is_blocked_flag = False
        if random.random() <= block_chance:
            damage_after_block = 0
            is_blocked_flag = True
        
        damage_to_player_hp = 0
        if not is_blocked_flag:
            damage_after_ward = damage_after_block
            ward_absorption_msg = ""
            if player.ward > 0:
                if damage_after_ward <= player.ward:
                    ward_absorbed = damage_after_ward
                    player.ward -= ward_absorbed
                    ward_absorption_msg = f"Your ward absorbs 🔮 {ward_absorbed} damage!"
                    damage_after_ward = 0 
                else:
                    ward_absorbed = player.ward
                    ward_absorption_msg = f"Your ward absorbs 🔮 {ward_absorbed} damage, but shatters!"
                    damage_after_ward -= ward_absorbed
                    player.ward = 0
            
            if damage_after_ward > 0:
                player.hp -= damage_after_ward
                damage_to_player_hp = damage_after_ward
                turn_messages.append(f"{monster.name} {monster.flavor}. You take 💔 **{damage_to_player_hp}** damage!")
                if ward_absorption_msg: turn_messages.insert(0, ward_absorption_msg)
            elif ward_absorption_msg: # Fully absorbed by ward
                 turn_messages.append(f"{monster.name} {monster.flavor}. {ward_absorption_msg}")
            
            damage_taken_by_player_hp_this_turn = damage_to_player_hp

            # Post-damage messages if not blocked and damage occurred
            if damage_to_player_hp > 0 or (ward_absorption_msg and not damage_after_ward > 0) : # If HP took damage OR ward took all
                if is_executed_flag:
                    turn_messages.append(f"The {monster.name}'s **Executioner** ability cleaves you!")
                # These were part of total, so message explains composition
                if minion_damage_component > 0 and "Summoner" in monster.modifiers:
                    turn_messages.append(f"Their minions added {minion_damage_component} to the hit.")
                if minion_damage_component > 0 and "Infernal Legion" in monster.modifiers:
                    turn_messages.append(f"Their legion echoed {minion_damage_component} to the hit.")
                if multistrike_component > 0:
                    turn_messages.append(f"{monster.name} struck again for {multistrike_component}.")
        else: # Blocked
            turn_messages.append(f"{monster.name} {monster.flavor}, but your armor 🛡️ blocks all damage!")
            damage_taken_by_player_hp_this_turn = 0
        
        if not turn_messages and not is_blocked_flag : # Fallback if hit but no specific message
             turn_messages.append(f"{monster.name} {monster.flavor}, dealing its blow.")

    else: # Monster misses
        if "Venomous" in monster.modifiers:
            if player.hp > 1: # Venomous can't kill if player is at 1 HP
                player.hp -= 1
                damage_taken_by_player_hp_this_turn = 1
                turn_messages.append(f"{monster.name} misses, but their **Venomous** aura deals **1** 🐍 damage!")
            else:
                turn_messages.append(f"{monster.name} misses. Venomous aura tries to sting, but you're already at 1 HP.")
        else:
            turn_messages.append(f"{monster.name} misses!")
    
    player.hp = max(0, player.hp)
    for msg_idx, msg_content in enumerate(turn_messages):
        logger.info(f"[M->P] {msg_content}")

    return player, damage_taken_by_player_hp_this_turn, turn_messages


# --- Simulation Core ---
def simulate_encounter(player_config: dict, monster_config: dict, sim_logger: SimLogger):
    # Create fresh Player and Monster objects for this encounter from configs
    # This ensures each simulation run is independent
    player = Player(**copy.deepcopy(player_config))
    monster = Monster(**copy.deepcopy(monster_config))
    
    initial_player_hp_for_log = player.hp 
    initial_monster_hp_for_log = monster.hp

    combat_start_passive_log = []
    
    # Apply pre-combat effects (these modify player/monster objects in-place)
    apply_monster_stat_effects_to_player(player, monster, sim_logger)
    apply_player_combat_start_passives(player, monster, sim_logger, combat_start_passive_log)
    
    sim_logger.info(f"Starting Encounter: Player (HP:{player.hp}, ATK:{player.attack}, DEF:{player.defence}, WARD:{player.ward}) vs Monster (HP:{monster.hp}, ATK:{monster.attack}, DEF:{monster.defence})")

    turns = 0
    max_turns = 300 # Safety break
    total_player_damage_output = 0
    total_damage_to_player_hp = 0

    while player.hp > 0 and monster.hp > 0 and turns < max_turns:
        turns += 1
        sim_logger.info(f"\n--- Turn {turns} ---")

        # Player's turn
        if player.hp > 0:
            sim_logger.info(f"Player (HP:{player.hp}, WARD:{player.ward}) attacks Monster (HP:{monster.hp})")
            _, p_dmg_this_turn, _ = simulate_player_turn(player, monster, sim_logger)
            total_player_damage_output += p_dmg_this_turn
            if monster.hp <= 0:
                sim_logger.info(f"Monster defeated by player in turn {turns}.")
                break 

        # Monster's turn
        if monster.hp > 0:
            sim_logger.info(f"Monster (HP:{monster.hp}) attacks Player (HP:{player.hp}, WARD:{player.ward})")
            _, m_dmg_to_p_hp_this_turn, _ = simulate_monster_turn(player, monster, sim_logger)
            total_damage_to_player_hp += m_dmg_to_p_hp_this_turn
            if player.hp <= 0:
                sim_logger.info(f"Player defeated by monster in turn {turns}.")
                break
                
    winner = "draw (timeout)"
    if player.hp <= 0:
        winner = "monster"
    elif monster.hp <= 0:
        winner = "player"

    sim_logger.info(f"Encounter End: Winner: {winner}, Turns: {turns}\n")
    return {
        "winner": winner,
        "turns": turns,
        "player_hp_remaining": player.hp,
        "monster_hp_remaining": monster.hp,
        "player_total_damage_dealt": total_player_damage_output,
        "monster_total_damage_taken_by_player_hp": total_damage_to_player_hp,
        "initial_player_hp": initial_player_hp_for_log, # From config
        "initial_monster_hp": initial_monster_hp_for_log # From config
    }


def run_simulation_suite(player_config: dict, monster_config: dict, num_iterations: int, verbose_sim_logs: bool = False):
    sim_logger = SimLogger(verbose=verbose_sim_logs)
    all_results = []

    for i in range(num_iterations):
        # if (i + 1) % (num_iterations // 10 if num_iterations >=10 else 1) == 0 : # Progress update
        #      print(f"Running simulation {i+1}/{num_iterations}...")
        result = simulate_encounter(player_config, monster_config, sim_logger)
        all_results.append(result)

    # Aggregate results
    player_wins_count = sum(1 for r in all_results if r["winner"] == "player")
    monster_wins_count = sum(1 for r in all_results if r["winner"] == "monster")
    draws_count = sum(1 for r in all_results if r["winner"] == "draw (timeout)")

    sum_player_damage_output = sum(r["player_total_damage_dealt"] for r in all_results)
    sum_damage_to_player_hp = sum(r["monster_total_damage_taken_by_player_hp"] for r in all_results)
    sum_total_turns = sum(r["turns"] for r in all_results)
    
    player_win_fights_data = [r for r in all_results if r["winner"] == "player"]
    avg_ttk_player = sum(r["turns"] for r in player_win_fights_data) / len(player_win_fights_data) if player_win_fights_data else float('nan')

    monster_win_fights_data = [r for r in all_results if r["winner"] == "monster"]
    avg_ttk_monster = sum(r["turns"] for r in monster_win_fights_data) / len(monster_win_fights_data) if monster_win_fights_data else float('nan')

    # Average damage per round (across all rounds in all simulations)
    avg_player_dmg_per_round = sum_player_damage_output / sum_total_turns if sum_total_turns > 0 else float('nan')
    avg_monster_dmg_to_player_hp_per_round = sum_damage_to_player_hp / sum_total_turns if sum_total_turns > 0 else float('nan')
    
    print("\n--- Overall Simulation Results ---")
    print(f"Total Iterations: {num_iterations}")
    print(f"Player Wins: {player_wins_count} ({player_wins_count/num_iterations*100:.2f}%)")
    print(f"Monster Wins: {monster_wins_count} ({monster_wins_count/num_iterations*100:.2f}%)")
    print(f"Draws (Timeout): {draws_count} ({draws_count/num_iterations*100:.2f}%)")
    
    print(f"\nAverage Player Damage Dealt (per round active): {avg_player_dmg_per_round:.2f}")
    print(f"Average Damage Taken by Player HP (per round active): {avg_monster_dmg_to_player_hp_per_round:.2f}")

    print(f"\nAverage Turns for Player to Kill Monster (on player win): {avg_ttk_player:.2f}")
    print(f"Average Turns for Monster to Kill Player (on monster win): {avg_ttk_monster:.2f}")


if __name__ == "__main__":
    # --- Define Player Configuration ---
    # These are the player's stats *after* accounting for gear, ideology, etc.
    # but *before* combat-start passives like Sturdy/Polished or monster debuffs like Enfeeble.
    player_config_1 = {
        "id": "sim_player1", "name": "Crit", "level": 100, "ascension": 0, "exp": 0,
        "hp": 300, "max_hp": 300, "attack": 400, "defence": 380,
        "rarity": 100, "crit": 95, # 25% base crit
        "ward": 0, "block": 0, "evasion": 0,
        "potions": 0, "wep_id": 0,
        "weapon_passive": "flaring", 
        "pinnacle_passive": "none", 
        "utmost_passive": "none", 
        "acc_passive": "none", "acc_lvl": 0,
        "armor_passive": "none", 
        "invulnerable": False
    }

    # --- Define Monster Configuration ---
    monster_config_1 = {
        "name": "EvasiveSpiker", "level": 100, "hp": 10000, "max_hp": 10000, "xp": 0,
        "attack": 340, "defence": 600,
        "modifiers": [],
        "image": "", "flavor": "darts around", "is_boss": True # Boss flag for potential future logic
    }

    num_simulations_to_run = 100 # Baseline 100, increase for more accuracy

    print("--- Starting Simulation Set 1 ---")
    print(f"Player Config: {player_config_1['name']}")
    print(f"Monster Config: {monster_config_1['name']}")
    # Set verbose_sim_logs to True to see turn-by-turn details for each sim (can be very long!)
    run_simulation_suite(player_config_1, monster_config_1, num_simulations_to_run, verbose_sim_logs=False)


    # --- Example 2: Glass Cannon Player vs Evasive Monster ---
    player_config_2 = {
        "id": "sim_player2", "name": "Echoes", "level": 100, "ascension": 0, "exp": 0,
        "hp": 300, "max_hp": 300, "attack": 400, "defence": 380,
        "rarity": 100, "crit": 95, # 25% base crit
        "ward": 0, "block": 0, "evasion": 0,
        "potions": 0, "wep_id": 0,
        "weapon_passive": "none", 
        "pinnacle_passive": "none", 
        "utmost_passive": "none", 
        "acc_passive": "none", "acc_lvl": 0,
        "armor_passive": "none", 
        "invulnerable": False
    }
    monster_config_2 = {
        "name": "Level 100", "level": 100, "hp": 10000, "max_hp": 10000, "xp": 0,
        "attack": 340, "defence": 600,
        "modifiers": [],
        "image": "", "flavor": "darts around", "is_boss": True # Boss flag for potential future logic
    }
    print("\n\n--- Starting Simulation Set 2 ---")
    print(f"Player Config: {player_config_2['name']}")
    print(f"Monster Config: {monster_config_2['name']}")
    run_simulation_suite(player_config_2, monster_config_2, num_simulations_to_run, verbose_sim_logs=False)