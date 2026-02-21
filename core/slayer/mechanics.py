import random
import csv
import os
from collections import Counter
from typing import Tuple, Dict

class SlayerMechanics:
    PASSIVE_POOL = [
        "slayer_dmg", "boss_dmg", "combat_dmg", 
        "gold_find", "xp_find", "slayer_def", 
        "crit_dmg", "accuracy", "task_progress", "slayer_drops"
    ]

    @staticmethod
    def calculate_level_from_xp(xp: int) -> int:
        """1000 XP for Lvl 2, 3000 XP for Lvl 3, etc. (Level * 1000)"""
        lvl = 1
        while xp >= (lvl * 1000):
            xp -= (lvl * 1000)
            lvl += 1
        return lvl

    @staticmethod
    def generate_task(player_level: int) -> Tuple[str, int]:
        """Reads monsters.csv, weights species by frequency in bracket, returns (Species, Amount)"""
        csv_path = os.path.join(os.path.dirname(__file__), '../../assets/monsters.csv')
        bracket_min = max(1, player_level - 20)
        bracket_max = min(110, player_level + 10)
        
        species_pool = []
        try:
            with open(csv_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    m_lvl = int(row['level']) * 10
                    if bracket_min <= m_lvl <= bracket_max:
                        species_pool.append(row.get('species', 'Humanoid'))
        except Exception:
            species_pool = ['Humanoid'] # Fallback
            
        if not species_pool: species_pool = ['Humanoid']
        
        # Count frequency
        counts = Counter(species_pool)
        total_monsters = len(species_pool)
        
        # Pick a random unique species
        chosen_species = random.choice(list(counts.keys()))
        
        # Calculate amount based on frequency
        # If species is 50% of the pool, task size is 50% of 50 = 25. Min cap at 5, Max cap at 50.
        frequency_ratio = counts[chosen_species] / total_monsters
        amount = max(5, min(50, int(frequency_ratio * 50)))
        
        return chosen_species, amount

    @staticmethod
    def calculate_task_rewards(amount: int) -> Tuple[int, int]:
        """Returns (XP, Points). Linear scaling."""
        # Completion burst: 50 XP per monster in the task, +1 Point per monster.
        return (amount * 50), amount

    @staticmethod
    def roll_drops(monster_level: int) -> Tuple[int, int]:
        """Returns (ViolentEssenceFound, ImbuedHeartsFound)"""
        essence, hearts = 0, 0
        
        # Scales slightly with level. e.g., Lvl 100 = 20% essence, 2% heart
        e_chance = 0.10 + (monster_level * 0.001)
        h_chance = 0.01 + (monster_level * 0.0001)
        
        if random.random() < e_chance: essence = 1
        if random.random() < h_chance: hearts = 1
        return essence, hearts

    @staticmethod
    def roll_upgrade(current_tier: int) -> Tuple[bool, int]:
        """
        Returns (Success, NewTier).
        Implements the Korean MMO tiering logic requested.
        """
        if current_tier >= 5: return False, 5
        
        # Success Chances: T1(80%), T2(60%), T3(40%), T4(20%)
        success_chance = 1.0 - (current_tier * 0.20)
        
        if random.random() <= success_chance:
            return True, current_tier + 1
            
        # Failed - Calculate Downgrade
        # T1 (No downgrade), T2(20%), T3(40%), T4(60%)
        downgrade_chance = (current_tier - 1) * 0.20
        new_tier = current_tier
        if random.random() <= downgrade_chance and current_tier > 1:
            new_tier -= 1
            
        return False, new_tier

    @staticmethod
    def get_unlocked_slots(slayer_level: int) -> int:
        """1 slot every 20 levels. Max 5 at Lvl 80+"""
        if slayer_level >= 80: return 5
        if slayer_level >= 60: return 4
        if slayer_level >= 40: return 3
        if slayer_level >= 20: return 2
        return 1