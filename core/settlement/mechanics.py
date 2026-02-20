# core/settlement/mechanics.py

import random
from datetime import datetime
from typing import Dict, Tuple, List, Optional

class SettlementMechanics:
    
    # --- CONSTANTS ---
    MAX_TIER = 5
    
    # Building Definitions
    # 'type': generator (creates from thin air), converter (consumes input), passive (buff)
    BUILDINGS = {
        "logging_camp": {"type": "generator", "output": "timber", "base_rate": 1},
        "quarry":       {"type": "generator", "output": "stone", "base_rate": 1},
        "market":       {"type": "generator", "output": "gold", "base_rate": 50}, # 50 gold per worker/hr
        
        "foundry": {
            "type": "converter", 
            "map": [
                ("iron", "iron_bar"), ("coal", "steel_bar"), 
                ("gold", "gold_bar"), ("platinum", "platinum_bar"), ("idea", "idea_bar")
            ],
            "base_rate": 1 # 5 conversions per worker/hr
        },
        "sawmill": {
            "type": "converter",
            "map": [
                ("oak_logs", "oak_plank"), ("willow_logs", "willow_plank"),
                ("mahogany_logs", "mahogany_plank"), ("magic_logs", "magic_plank"), ("idea_logs", "idea_plank")
            ],
            "base_rate": 1
        },
        "reliquary": {
            "type": "converter",
            "map": [
                ("desiccated_bones", "desiccated_essence"), ("regular_bones", "regular_essence"),
                ("sturdy_bones", "sturdy_essence"), ("reinforced_bones", "reinforced_essence"), ("titanium_bones", "titanium_essence")
            ],
            "base_rate": 1
        },
        
        "barracks": {"type": "passive", "effect": "combat_stats"},
        "temple":   {"type": "passive", "effect": "propagate_bonus"},
        "town_hall": {"type": "core", "effect": "caps"},
        "apothecary": {"type": "passive", "effect": "potion_buff"},
        # Type 'special' means it has no passive production, handled via custom View
        "black_market": {"type": "special", "effect": "trading"},
        # Generates 'companion_cookie' which is auto-converted to XP on collect
        "companion_ranch": {"type": "generator", "output": "companion_cookie", "base_rate": 5}, # 5 XP per worker/hr
    }

    @staticmethod
    def get_max_workers(tier: int) -> int:
        """Higher tier buildings can hold more workers."""
        return 100 * tier

    @staticmethod
    def calculate_production(
        building_type: str, 
        tier: int, 
        workers: int, 
        hours_elapsed: float, 
        raw_inventory: Dict[str, int] = None
    ) -> Dict[str, int]:
        """
        Calculates production for a specific building over time.
        Returns dict of changes: {'iron': -100, 'iron_bar': 100, 'timber': 50}
        """
        if workers <= 0 or hours_elapsed <= 0:
            return {}

        b_data = SettlementMechanics.BUILDINGS.get(building_type)
        if not b_data: return {}

        changes = {}
        
        # Rate = Base * Tier * Workers
        # Example: T1 Logging Camp w/ 100 workers = 100 / 10 * 1 = 10 Timber/hr
        # Example: T5 Foundry w/ 500 workers = 5 * 5 * (500 / 10) = 1250 Ingots/hr
        production_capacity = int(b_data["base_rate"] * tier * workers * hours_elapsed)

        if b_data["type"] == "generator":
            changes[b_data["output"]] = production_capacity

        elif b_data["type"] == "converter" and raw_inventory:
            remaining_capacity = production_capacity
            
            # Iterate through tier mappings (Lowest to Highest)
            # Tier 1 Building processes Index 0. Tier 5 processes up to Index 4.
            # However, for simplicity, let's say higher tiers process EVERYTHING faster, 
            # but we prioritize high-value or low-value? 
            # Standard logic: Process lowest tier mats first (clearing junk).
            
            for raw_key, refined_key in b_data["map"]:
                if raw_key in raw_inventory:
                    available_raw = raw_inventory[raw_key]
                    
                    # How much can we convert?
                    amount_to_convert = min(available_raw, remaining_capacity)
                    
                    if amount_to_convert > 0:
                        changes[raw_key] = changes.get(raw_key, 0) - amount_to_convert
                        changes[refined_key] = changes.get(refined_key, 0) + amount_to_convert
                        
                        remaining_capacity -= amount_to_convert
                        
                    if remaining_capacity <= 0:
                        break

        return changes

    @staticmethod
    def roll_event(hours_elapsed: float) -> Optional[str]:
        """
        Checks if a random event occurred during the elapsed time.
        """
        if hours_elapsed < 1: return None
        
        # 1% chance per hour
        chance = 0.01 * hours_elapsed
        if random.random() < chance:
            events = [
                "Traveling Merchant visited! Gained 5,000 Gold.",
                "Minor earthquake! A few stones fell loose (+10 Stone).",
                "A worker slacked off. Production reduced slightly (Flavor).",
                "A wandering bard entertained your followers. Morale high!"
            ]
            return random.choice(events)
        return None