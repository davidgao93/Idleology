# core/companions/mechanics.py

import random
from datetime import datetime
from typing import Tuple, List, Dict, Any
from core.models import Companion, Weapon, Armor, Accessory, Glove, Boot, Helmet

class CompanionMechanics:
    
    # --- CONSTANTS ---
    PASSIVE_TYPES = ['atk', 'def', 'hit', 'crit', 'ward', 'rarity', 'fdr', 'pdr']
    RARE_PASSIVE_TYPES = ['s_rarity'] # Special Rarity is rarer
    
    MAX_LEVEL = 100
    COLLECTION_INTERVAL_SECONDS = 1800 # 30 Minutes
    MAX_COLLECTION_CYCLES = 48 # 24 Hours max accumulation

    # --- XP & LEVELING ---

    @staticmethod
    def calculate_next_level_xp(current_level: int) -> int:
        """XP needed to reach next level: Level * 100."""
        if current_level >= CompanionMechanics.MAX_LEVEL:
            return 999999999
        return current_level * 100

    @staticmethod
    def calculate_feed_xp(item: Any) -> int:
        """Determines XP value of an item based on its stats/type."""
        xp = 10 # Base for generic junk
        
        # Scale based on item level
        if hasattr(item, 'level'):
            xp += item.level // 2
            
        # Bonus for Rarity/Enchantments
        if isinstance(item, Weapon):
            if item.rarity > 0: xp += 10
            if item.refinement_lvl > 0: xp += (item.refinement_lvl * 50)
            if item.passive != 'none': xp += 50
            
        elif hasattr(item, 'passive_lvl') and item.passive_lvl > 0:
            xp += (item.passive_lvl * 50)
            
        return xp

    # --- PASSIVE GENERATION ---

    @staticmethod
    def roll_new_passive(is_capture: bool = True) -> Tuple[str, int]:
        """
        Generates a (Type, Tier) tuple.
        is_capture: Weighted heavily towards T1/T2.
        """
        # Roll Type
        if random.random() < 0.05: # 5% chance for Special Rarity
            p_type = 's_rarity'
        else:
            p_type = random.choice(CompanionMechanics.PASSIVE_TYPES)

        # Roll Tier
        roll = random.random()
        tier = 1
        
        if is_capture:
            # Capture Weights: T3(4%), T4(0.9%), T5(0.1%)
            if roll > 0.95: tier = 3
            elif roll > 0.80: tier = 2
        else:
            # Reroll/Generation Weights (Slightly better): T1(50%), T2(30%), T3(15%), T4(4%), T5(1%)
            if roll > 0.99: tier = 5
            elif roll > 0.95: tier = 4
            elif roll > 0.80: tier = 3
            elif roll > 0.50: tier = 2

        return p_type, tier

    @staticmethod
    def reroll_passive(current_tier: int, current_type: str = None) -> Tuple[str, int, bool]:
        """
        Rerolls passive using a Rune.
        Returns: (NewType, NewTier, DidTierUp)
        Logic:
        - 10% Chance to Upgrade Tier (Max 5).
        - 90% Chance to Keep Tier.
        - Type is ALWAYS different from current_type.
        """
        
        # 1. Determine New Type
        # Logic: 5% chance for s_rarity, 95% for standard.
        # Constraint: Must not be current_type.
        
        new_type = None
        
        # Helper to pick from standard list excluding current
        def pick_standard():
            pool = [p for p in CompanionMechanics.PASSIVE_TYPES if p != current_type]
            return random.choice(pool)

        if current_type == 's_rarity':
            # If we currently have Special Rarity, we FORCE a standard roll 
            # (since we can't be s_rarity again)
            new_type = pick_standard()
        else:
            # If standard, we roll for s_rarity or different standard
            if random.random() < 0.05:
                new_type = 's_rarity'
            else:
                new_type = pick_standard()

        # 2. Roll Tier Change
        new_tier = current_tier
        upgraded = False
        
        roll = random.random()
        if roll < 0.10 and current_tier < 5: # 10% upgrade chance
            new_tier += 1
            upgraded = True
        
        # Safety bounds
        new_tier = max(1, min(5, new_tier))
        
        return new_type, new_tier, upgraded

    # --- PASSIVE COLLECTION ---

    @staticmethod
    def calculate_collection_rewards(companions: List[Companion], last_collect_str: str) -> Dict[str, Any]:
        """
        Calculates passive rewards based on time elapsed and active companions.
        """
        if not last_collect_str or not companions:
            return {"items": [], "cycles": 0, "can_collect": False}

        try:
            last_time = datetime.fromisoformat(last_collect_str)
        except ValueError:
            return {"items": [], "cycles": 0, "can_collect": False}

        diff = (datetime.now() - last_time).total_seconds()
        cycles = int(diff // CompanionMechanics.COLLECTION_INTERVAL_SECONDS)
        
        if cycles <= 0:
            return {"items": [], "cycles": 0, "can_collect": False}

        # Cap cycles
        cycles = min(cycles, CompanionMechanics.MAX_COLLECTION_CYCLES)

        loot_bag = []

        # Loot Weights (Sum = 105, random.choices handles normalization)
        loot_types = [
            "Gold", "Boss Key", "Rune of Refinement", 
            "Rune of Potential", "Rune of Shattering", "Equipment"
        ]
        loot_weights = [50, 20, 5, 5, 10, 10]

        for comp in companions:
            # Chance to find *anything* this cycle: 1% per level
            find_chance = comp.level * 0.01
            
            # Optimization: If 100% chance (Lvl 100), just generate 'cycles' amount of loot
            # Otherwise, simulate checks
            successful_rolls = 0
            if find_chance >= 1.0:
                successful_rolls = cycles
            else:
                # Binomial simulation approx or simple loop
                for _ in range(cycles):
                    if random.random() < find_chance:
                        successful_rolls += 1
            
            if successful_rolls > 0:
                # Batch roll types
                results = random.choices(loot_types, weights=loot_weights, k=successful_rolls)
                
                for res in results:
                    if res == "Gold":
                        # Gold Amount: Level * 1000 (e.g. Lvl 50 = 50000g, Lvl 100 = 100000g)
                        amount = comp.level * 1000
                        loot_bag.append(("Gold", amount))
                    else:
                        loot_bag.append((res, 1))

        return {
            "items": loot_bag, # List of tuples: ("Type", Amount/1)
            "cycles": cycles,
            "can_collect": True
        }
    

    @staticmethod
    def calculate_cumulative_xp(level: int, current_exp: int) -> int:
        """
        Converts Level + CurrentXP into Total Cumulative XP.
        Formula: Sum of (i * 100) for i=1 to level-1.
        Arithmetic Series Sum: S = n/2 * (2a + (n-1)d) -> simplified: 50 * L * (L-1)
        """
        if level <= 1: return current_exp
        
        # XP required to reach current_level from level 1
        xp_to_reach_level = 50 * level * (level - 1)
        return xp_to_reach_level + current_exp

    @staticmethod
    def calculate_level_from_xp(total_xp: int) -> Tuple[int, int]:
        """
        Converts Total Cumulative XP back into (Level, CurrentXP).
        Max Level 100.
        """
        level = 1
        while level < CompanionMechanics.MAX_LEVEL:
            req_xp = level * 100
            if total_xp >= req_xp:
                total_xp -= req_xp
                level += 1
            else:
                break
        return level, total_xp

    @staticmethod
    def fuse_attributes(comp_a, comp_b) -> dict:
        """
        Picks random traits from parents.
        """
        # Coin flips for traits
        base_source = random.choice([comp_a, comp_b])
        
        return {
            "name": base_source.name,
            "species": base_source.species,
            "image_url": base_source.image_url,
            "passive_type": random.choice([comp_a.passive_type, comp_b.passive_type]),
            "passive_tier": random.choice([comp_a.passive_tier, comp_b.passive_tier])
        }
    
    @staticmethod
    def roll_boss_passive() -> Tuple[str, int]:
        """
        Generates a passive for a Boss Pet.
        Always Tier 3 (as per specification).
        """
        # 5% chance for Special Rarity, otherwise standard types
        if random.random() < 0.05:
            p_type = 's_rarity'
        else:
            p_type = random.choice(CompanionMechanics.PASSIVE_TYPES)
            
        # Fixed Tier 3
        return p_type, 3