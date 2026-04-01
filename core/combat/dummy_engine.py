import random
from dataclasses import dataclass
from core.models import Player, Monster
from core.combat.calcs import (
    calculate_hit_chance, 
    check_for_echo_bonus,
    check_for_poison_bonus,
    get_player_passive_indices  # [NEW IMPORT]
)

@dataclass
class SimulationResult:
    total_damage: int
    hits: int
    misses: int
    crits: int
    max_hit: int
    min_hit: int
    average_damage: float
    turns: int

class DummyEngine:
    @staticmethod
    def run_simulation(player: Player, monster: Monster, turns: int = 100) -> SimulationResult:
        total_damage = 0
        hits = 0
        misses = 0
        crits = 0
        max_hit = 0
        min_hit = float('inf')

        # Cache passives
        glove_passive = player.get_glove_passive()
        glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
        acc_passive = player.get_accessory_passive()
        acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0
        armor_passive = player.get_armor_passive()
        helmet_passive = player.get_helmet_passive()
        helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0

        # Define lists for weapon logic lookup
        burning_passives = ["burning", "flaming", "scorching", "incinerating", "carbonising"]
        sparking_passives = ["sparking", "shocking", "discharging", "electrocuting", "vapourising"]

        for _ in range(turns):
            attack_multiplier = 1.0
            
            # --- Multipliers ---
            if glove_passive == "instability" and glove_lvl > 0:
                if random.random() < 0.5:
                    attack_multiplier *= 0.5
                else:
                    attack_multiplier *= 1.50 + (glove_lvl * 0.10)

            if acc_passive == "Obliterate" and random.random() <= (acc_lvl * 0.02):
                attack_multiplier *= 2.0

            if armor_passive == "Mystical Might" and random.random() < 0.2:
                attack_multiplier *= 10.0

            if helmet_passive == "frenzy" and helmet_lvl > 0:
                if player.max_hp > 0:
                    missing_hp_pct = (1 - (player.current_hp / player.max_hp)) * 100
                    multiplier_bonus = (missing_hp_pct * (0.005 * helmet_lvl))
                    attack_multiplier *= (1 + multiplier_bonus)

            # --- Hit Calc ---
            hit_chance = calculate_hit_chance(player, monster)
            if "Dodgy" in monster.modifiers:
                hit_chance = max(0.05, hit_chance - 0.10)

            if acc_passive == "Lucky Strikes" and random.random() <= (acc_lvl * 0.10):
                r1, r2 = random.randint(0, 100), random.randint(0, 100)
                attack_roll = max(r1, r2)
            else:
                attack_roll = random.randint(0, 100)

            if "Suffocator" in monster.modifiers and random.random() < 0.2:
                r1, r2 = random.randint(0, 100), random.randint(0, 100)
                attack_roll = min(r1, r2)

            is_hit = False
            final_miss_threshold = 100 - int(hit_chance * 100)
            
            if attack_roll >= final_miss_threshold:
                is_hit = True
            
            if "Shields-up" in monster.modifiers and random.random() < 0.1:
                attack_multiplier = 0 # Blocked

            damage = 0
            
            if is_hit and attack_multiplier > 0:
                # --- Crit Check ---
                crit_target = player.get_current_crit_target()
                
                if random.randint(0, 100) > crit_target and "Impenetrable" not in monster.modifiers:
                    # CRIT
                    crits += 1
                    hits += 1
                    
                    max_hit_calc = player.get_total_attack()
                    crit_floor = 0.5
                    if glove_passive == "deftness": crit_floor += (glove_lvl * 0.05)
                    
                    c_min = max(1, int(max_hit_calc * crit_floor))
                    c_max = max(c_min, max_hit_calc)
                    base_dmg = int(random.randint(c_min, c_max) * 2.0)
                    
                    if helmet_passive == "insight":
                        base_dmg = int(base_dmg * (1 + (helmet_lvl * 0.1)))
                        
                    if "Smothering" in monster.modifiers:
                        base_dmg = int(base_dmg * 0.80)
                        
                    damage = int(base_dmg * attack_multiplier)
                    
                else:
                    # NORMAL HIT
                    hits += 1
                    base_max = player.get_total_attack()
                    base_min = 1
                    
                    # 1. Adroit (Glove)
                    if glove_passive == "adroit":
                        base_min = max(base_min, int(base_max * (glove_lvl * 0.02)))
                    
                    # 2. Burn (Weapon) - Increases Max Damage
                    burn_indices = get_player_passive_indices(player, burning_passives)
                    if burn_indices:
                        max_idx = max(burn_indices)
                        # (Tier Index + 1) * 8%
                        burn_bonus = int(player.get_total_attack() * ((max_idx + 1) * 0.08))
                        base_max += burn_bonus

                    # 3. Spark (Weapon) - Increases Min Damage based on Max
                    spark_indices = get_player_passive_indices(player, sparking_passives)
                    if spark_indices:
                        max_idx = max(spark_indices)
                        # (Tier Index + 1) * 8%
                        spark_min_pct = (max_idx + 1) * 0.08
                        base_min = max(base_min, int(base_max * spark_min_pct))
                    
                    # Roll Logic
                    rolled = random.randint(base_min, base_max)
                    damage = int(rolled * attack_multiplier)
                    
                    # Echo
                    dmg_pre_echo = damage
                    damage, is_echo, echo_amt = check_for_echo_bonus(player, damage)
                    
            else:
                misses += 1
                damage = check_for_poison_bonus(player, attack_multiplier)

            # --- Mitigation ---
            if "Titanium" in monster.modifiers and damage > 0:
                damage = max(0, damage - int(damage * 0.10))

            if damage > 0:
                total_damage += damage
                if damage > max_hit: max_hit = damage
                if damage < min_hit: min_hit = damage

        if min_hit == float('inf'): min_hit = 0

        return SimulationResult(
            total_damage=total_damage,
            hits=hits,
            misses=misses,
            crits=crits,
            max_hit=max_hit,
            min_hit=min_hit,
            average_damage=total_damage / turns,
            turns=turns
        )

    @staticmethod
    def assess_readiness(player: Player, target: str) -> str:
        """Runs a fast simulation against a target proxy to gauge difficulty."""
        if target == "aphrodite_uber":
            # Approximate the Uber stats to test against
            ref_lvl = player.level + player.ascension + 20
            m_atk = int(ref_lvl * 1.5) + 25  # Level scaling + Absolute mod estimate
            m_def = int(ref_lvl * 1.5) + 25
            
            proxy_boss = Monster(
                name="Proxy", level=ref_lvl, hp=999999, max_hp=999999, xp=0,
                attack=m_atk, defence=m_def,
                modifiers=["Radiant Protection"], # Important for DPS reduction
                image="", flavor=""
            )
            
            # 1. Test Player DPS
            res = DummyEngine.run_simulation(player, proxy_boss, turns=50)
            dps = res.average_damage
            
            # 2. Test Player Survivability (Estimate incoming dmg)
            from core.combat.calcs import calculate_monster_hit_chance, calculate_damage_taken
            
            # Fast manual simulation of incoming damage over 10 turns
            total_inc_dmg = 0
            for _ in range(10):
                hit_chance = calculate_monster_hit_chance(player, proxy_boss)
                if random.random() <= hit_chance:
                    total_inc_dmg += calculate_damage_taken(player, proxy_boss)
            
            avg_inc_dmg = total_inc_dmg / 10.0
            
            # 3. Evaluate Results
            # Baseline assumptions:
            # Uber HP is ~ 10x (Level^1.4) 
            # If DPS is very low, or Incoming Dmg is high relative to max HP = Not Ready
            
            time_to_die = player.max_hp / avg_inc_dmg if avg_inc_dmg > 0 else 999
            
            if time_to_die < 5:
                return "You feel as if you are **not ready**. The aura alone crushes you."
            elif dps < (player.max_hp * 0.1) and time_to_die < 15:
                return "You feel this would be a **tough battle**. Survival is uncertain."
            else:
                return "You are **filled with determination**. Press onwards."

        if target == "lucifer_uber":
            ref_lvl = player.level + player.ascension + 20
            # Lucifer proxy: triple attack, minimal defence
            m_atk = int(ref_lvl ** 1.3 * 3.0) + 25 + int(ref_lvl * 1.0)
            m_def = int(ref_lvl ** 1.3 * 0.3) + 25 + int(ref_lvl * 0.2)

            proxy_boss = Monster(
                name="Proxy",
                level=ref_lvl,
                hp=999999,
                max_hp=999999,
                xp=0,
                attack=m_atk,
                defence=m_def,
                modifiers=["Hell's Fury"],
                image="",
                flavor="",
            )

            res = DummyEngine.run_simulation(player, proxy_boss, turns=50)
            dps = res.average_damage

            from core.combat.calcs import calculate_monster_hit_chance, calculate_damage_taken

            total_inc_dmg = 0
            for _ in range(10):
                hit_chance = calculate_monster_hit_chance(player, proxy_boss)
                if random.random() <= hit_chance:
                    total_inc_dmg += calculate_damage_taken(player, proxy_boss)

            avg_inc_dmg = total_inc_dmg / 10.0
            time_to_die = player.max_hp / avg_inc_dmg if avg_inc_dmg > 0 else 999

            if time_to_die < 3:
                return "You feel as if you are **not ready**. His strikes alone would end you."
            elif dps < (player.max_hp * 0.1) and time_to_die < 10:
                return "You feel this would be a **tough battle**. Survival is uncertain."
            else:
                return "You are **filled with determination**. Press onwards."

        if target == "neet_uber":
            ref_lvl = player.level + player.ascension + 20
            # NEET proxy: 1.5x attack, 2x defence — Void Drain not simulated but TTK threshold is tighter
            m_atk = int(ref_lvl ** 1.3 * 1.5) + 25 + int(ref_lvl * 0.8)
            m_def = int(ref_lvl ** 1.3 * 2.0) + 25 + int(ref_lvl * 0.5)

            proxy_boss = Monster(
                name="Proxy",
                level=ref_lvl,
                hp=999999,
                max_hp=999999,
                xp=0,
                attack=m_atk,
                defence=m_def,
                modifiers=[],
                image="",
                flavor="",
            )

            res = DummyEngine.run_simulation(player, proxy_boss, turns=50)
            dps = res.average_damage

            from core.combat.calcs import calculate_monster_hit_chance, calculate_damage_taken

            total_inc_dmg = 0
            for _ in range(10):
                hit_chance = calculate_monster_hit_chance(player, proxy_boss)
                if random.random() <= hit_chance:
                    total_inc_dmg += calculate_damage_taken(player, proxy_boss)

            avg_inc_dmg = total_inc_dmg / 10.0
            time_to_die = player.max_hp / avg_inc_dmg if avg_inc_dmg > 0 else 999

            # Void Drain compounds over rounds — warn if DPS is low (long fight = death)
            if dps < (player.max_hp * 0.05):
                return "You feel as if you are **not ready**. The void would consume you before you land a dent."
            elif time_to_die < 5:
                return "You feel as if you are **not ready**. Its strikes alone would end you."
            elif dps < (player.max_hp * 0.10) and time_to_die < 12:
                return "You feel this would be a **tough battle**. The void slowly drains everything."
            else:
                return "You are **filled with determination**. The void beckons."

        if target == "gemini_uber":
            ref_lvl = player.level + player.ascension + 20
            # Gemini proxy: perfectly balanced — equal ATK and DEF scaling
            m_atk = int(ref_lvl ** 1.3) + 25 + int(ref_lvl * 0.65)
            m_def = int(ref_lvl ** 1.3) + 25 + int(ref_lvl * 0.65)

            proxy_boss = Monster(
                name="Proxy",
                level=ref_lvl,
                hp=999999,
                max_hp=999999,
                xp=0,
                attack=m_atk,
                defence=m_def,
                modifiers=[],
                image="",
                flavor="",
            )

            res = DummyEngine.run_simulation(player, proxy_boss, turns=50)
            dps = res.average_damage

            from core.combat.calcs import calculate_monster_hit_chance, calculate_damage_taken

            total_inc_dmg = 0
            for _ in range(10):
                hit_chance = calculate_monster_hit_chance(player, proxy_boss)
                if random.random() <= hit_chance:
                    total_inc_dmg += calculate_damage_taken(player, proxy_boss)

            avg_inc_dmg = total_inc_dmg / 10.0
            time_to_die = player.max_hp / avg_inc_dmg if avg_inc_dmg > 0 else 999

            # Twin Strike doubles incoming damage every other round — factor this in
            if dps < (player.max_hp * 0.05):
                return "You feel as if you are **not ready**. The twins would outlast you entirely."
            elif time_to_die < 4:
                return "You feel as if you are **not ready**. Their Twin Strike would end you too quickly."
            elif dps < (player.max_hp * 0.10) and time_to_die < 10:
                return "You feel this would be a **tough battle**. The twins' rhythm is relentless."
            else:
                return "You are **filled with determination**. The constellation awaits."

        return "Unknown target."