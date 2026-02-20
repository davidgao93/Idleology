import random
from typing import Tuple, Dict, Optional, Literal, Any, List
from core.models import Weapon, Armor, Accessory, Glove, Boot

class EquipmentMechanics:
    """
    Handles the logic for upgrading, refining, and modifying equipment.
    Does NOT handle DB writes or Discord UI.
    """

    # --- WEAPON FORGING LOGIC ---
    @staticmethod
    def calculate_forge_cost(weapon: Weapon) -> Optional[Dict[str, int]]:
        """
        Returns the resource cost to forge a weapon based on level and remaining forges.
        Returns None if no forges remaining.
        Keys: 'ore_type', 'log_type', 'bone_type', 'ore_qty', 'log_qty', 'bone_qty', 'gold'
        """
        if weapon.forges_remaining < 1:
            return None

        # Determine Tier
        if weapon.level <= 40:
            tier_data = {
                3: {'ore': 'iron', 'log': 'oak', 'bone': 'desiccated', 'qty': 10, 'gold': 100},
                2: {'ore': 'coal', 'log': 'willow', 'bone': 'regular', 'qty': 10, 'gold': 400},
                1: {'ore': 'gold', 'log': 'mahogany', 'bone': 'sturdy', 'qty': 10, 'gold': 1000}
            }
        elif weapon.level <= 80:
            tier_data = {
                4: {'ore': 'iron', 'log': 'oak', 'bone': 'desiccated', 'qty': 25, 'gold': 250},
                3: {'ore': 'coal', 'log': 'willow', 'bone': 'regular', 'qty': 25, 'gold': 1000},
                2: {'ore': 'gold', 'log': 'mahogany', 'bone': 'sturdy', 'qty': 25, 'gold': 2500},
                1: {'ore': 'platinum', 'log': 'magic', 'bone': 'reinforced', 'qty': 25, 'gold': 5000}
            }
        else: # Level 80+
            tier_data = {
                5: {'ore': 'iron', 'log': 'oak', 'bone': 'desiccated', 'qty': 50, 'gold': 500},
                4: {'ore': 'coal', 'log': 'willow', 'bone': 'regular', 'qty': 50, 'gold': 2000},
                3: {'ore': 'gold', 'log': 'mahogany', 'bone': 'sturdy', 'qty': 50, 'gold': 5000},
                2: {'ore': 'platinum', 'log': 'magic', 'bone': 'reinforced', 'qty': 50, 'gold': 10000},
                1: {'ore': 'idea', 'log': 'idea', 'bone': 'titanium', 'qty': 50, 'gold': 20000}
            }

        cost = tier_data.get(weapon.forges_remaining)
        if not cost: return None

        return {
            'ore_type': cost['ore'],
            'log_type': cost['log'],
            'bone_type': cost['bone'],
            'ore_qty': cost['qty'],
            'log_qty': cost['qty'],
            'bone_qty': cost['qty'],
            'gold': cost['gold']
        }

    @staticmethod
    def roll_forge_outcome(weapon: Weapon) -> Tuple[bool, str]:
        """
        Determines if a forge succeeds and selects a passive.
        Returns (Success: bool, PassiveName: str)
        """
        # Calculate Success Rate
        base_rate = 0.8
        
        # Determine max forges for this tier to calculate decay
        max_forges = 3
        if weapon.level > 40: max_forges = 4
        if weapon.level > 80: max_forges = 5
        
        # Current forge step (e.g., if max is 3 and remaining is 3, step is 0)
        current_step = max_forges - weapon.forges_remaining
        success_rate = base_rate - (current_step * 0.05)

        if random.random() > success_rate:
            return False, weapon.passive # Fail, keep existing

        # Success - Pick Passive
        passives = ["burning", "poisonous", "polished", "sparking", "sturdy", "piercing", "strengthened", "accurate", "echo"]
        
        # Upgrade logic map
        upgrade_map = {
            "burning": "flaming", "flaming": "scorching", "scorching": "incinerating", "incinerating": "carbonising",
            "poisonous": "noxious", "noxious": "venomous", "venomous": "toxic", "toxic": "lethal",
            "polished": "honed", "honed": "gleaming", "gleaming": "tempered", "tempered": "flaring",
            "sparking": "shocking", "shocking": "discharging", "discharging": "electrocuting", "electrocuting": "vapourising",
            "sturdy": "reinforced", "reinforced": "thickened", "thickened": "impregnable", "impregnable": "impenetrable",
            "piercing": "keen", "keen": "incisive", "incisive": "puncturing", "puncturing": "penetrating",
            "strengthened": "forceful", "forceful": "overwhelming", "overwhelming": "devastating", "devastating": "catastrophic",
            "accurate": "precise", "precise": "sharpshooter", "sharpshooter": "deadeye", "deadeye": "bullseye",
            "echo": "echoo", "echoo": "echooo", "echooo": "echoooo", "echoooo": "echoes"
        }

        if weapon.passive == "none":
            return True, random.choice(passives)
        else:
            # Upgrade existing or keep maxed
            return True, upgrade_map.get(weapon.passive, weapon.passive)


# --- WEAPON REFINING LOGIC ---
    @staticmethod
    def calculate_refine_cost(weapon: Weapon) -> Dict[str, Any]:
        """
        Calculates Gold and Material costs for refining based on level and current refinement.
        Returns: {'gold': int, 'materials': List[Dict]}
        """
        rem = weapon.refines_remaining
        lvl = weapon.level
        ref_lvl = weapon.refinement_lvl
        
        # 1. Calculate Gold Cost (Existing Logic)
        gold_cost = 1000
        if lvl <= 40:
            costs = {3: 500, 2: 1000, 1: 5000}
            gold_cost = costs.get(rem, 1000)
        elif lvl <= 80:
            costs = {4: 5000, 3: 15000, 2: 25000, 1: 50000}
            gold_cost = costs.get(rem, 50000)
        else:
            costs = {5: 10000, 4: 30000, 3: 50000, 2: 100000, 1: 200000}
            gold_cost = costs.get(rem, 200000)

        # 2. Calculate Material Cost (New Logic > +100)
        materials = []
        
        if ref_lvl >= 100:
            qty = 0
            tier_idx = 0 # 0=Iron/Oak/Desiccated, 1=Steel/Willow/Reg, etc.
            
            # Logic Table
            if 100 <= ref_lvl <= 120:
                qty = 10
                tier_idx = 0
            elif 121 <= ref_lvl <= 140:
                qty = 20
                tier_idx = 1
            elif 141 <= ref_lvl <= 160:
                qty = 30
                tier_idx = 2
            elif 161 <= ref_lvl <= 180:
                qty = 40
                tier_idx = 3
            elif 181 <= ref_lvl <= 200:
                qty = 50
                tier_idx = 4
            else: # 201+
                qty = 50 + (ref_lvl - 200)
                tier_idx = 4 # Cap at Idea/Titanium tier

            res_defs = [
                ('iron_bar', 'oak_plank', 'desiccated_essence', 'Iron/Oak/Desiccated'),
                ('steel_bar', 'willow_plank', 'regular_essence', 'Steel/Willow/Regular'),
                ('gold_bar', 'mahogany_plank', 'sturdy_essence', 'Gold/Mahogany/Sturdy'),
                ('platinum_bar', 'magic_plank', 'reinforced_essence', 'Platinum/Magic/Reinforced'),
                ('idea_bar', 'idea_plank', 'titanium_essence', 'Idea/Titanium')
            ]
            
            def_t = res_defs[tier_idx]
            
            materials.append({'table': 'mining', 'column': def_t[0], 'qty': qty, 'name': def_t[0].replace('_', ' ').title()})
            materials.append({'table': 'woodcutting', 'column': def_t[1], 'qty': qty, 'name': def_t[1].replace('_', ' ').title()})
            materials.append({'table': 'fishing', 'column': def_t[2], 'qty': qty, 'name': def_t[2].replace('_', ' ').title()})

        return {
            'gold': gold_cost,
            'materials': materials
        }

    @staticmethod
    def roll_refine_outcome(weapon: Weapon) -> Dict[str, int]:
        """
        Calculates stat gains for a single refine action.
        Returns dict: {'attack': val, 'defence': val, 'rarity': val}
        """
        stats = {'attack': 0, 'defence': 0, 'rarity': 0}
        
        # Success chances
        atk_success = random.randint(0, 100) < 80 # 80%
        def_success = random.randint(0, 100) < 50 # 50%
        rar_success = random.randint(0, 100) < 20 # 20%
        
        # Range calculation: 1 to (Lvl/10 + 2)
        max_gain = int(weapon.level / 10) + 2
        
        if atk_success:
            stats['attack'] = random.randint(1, max_gain)
        
        if def_success:
            stats['defence'] = random.randint(1, max_gain)
            
        if rar_success:
            stats['rarity'] = random.randint(1, max_gain) * 5 # Rarity scales higher visually usually
            
        return stats

    # --- ARMOR TEMPERING LOGIC ---
    @staticmethod
    def calculate_temper_cost(armor: Armor) -> Optional[Dict[str, int]]:
        """
        Returns cost to temper armor. Identical logic structure to weapons but different values.
        """
        if armor.temper_remaining < 1:
            return None

        # Simplified mapping based on original armor.py
        if armor.level <= 40:
            tier_data = {
                3: {'ore': 'iron', 'log': 'oak', 'bone': 'desiccated', 'qty': 20, 'gold': 500},
                2: {'ore': 'coal', 'log': 'willow', 'bone': 'regular', 'qty': 20, 'gold': 100},
                1: {'ore': 'gold', 'log': 'mahogany', 'bone': 'sturdy', 'qty': 20, 'gold': 2000}
            }
        elif armor.level <= 80:
            tier_data = {
                4: {'ore': 'iron', 'log': 'oak', 'bone': 'desiccated', 'qty': 50, 'gold': 500},
                3: {'ore': 'coal', 'log': 'willow', 'bone': 'regular', 'qty': 50, 'gold': 1500},
                2: {'ore': 'gold', 'log': 'mahogany', 'bone': 'sturdy', 'qty': 50, 'gold': 3000},
                1: {'ore': 'platinum', 'log': 'magic', 'bone': 'reinforced', 'qty': 50, 'gold': 6000}
            }
        else:
            tier_data = {
                5: {'ore': 'iron', 'log': 'oak', 'bone': 'desiccated', 'qty': 100, 'gold': 500},
                4: {'ore': 'coal', 'log': 'willow', 'bone': 'regular', 'qty': 100, 'gold': 2000},
                3: {'ore': 'gold', 'log': 'mahogany', 'bone': 'sturdy', 'qty': 100, 'gold': 5000},
                2: {'ore': 'platinum', 'log': 'magic', 'bone': 'reinforced', 'qty': 100, 'gold': 10000},
                1: {'ore': 'idea', 'log': 'idea', 'bone': 'titanium', 'qty': 100, 'gold': 20000}
            }

        cost = tier_data.get(armor.temper_remaining)
        if not cost: return None

        return {
            'ore_type': cost['ore'],
            'log_type': cost['log'],
            'bone_type': cost['bone'],
            'ore_qty': cost['qty'],
            'log_qty': cost['qty'],
            'bone_qty': cost['qty'],
            'gold': cost['gold']
        }

    @staticmethod
    def roll_temper_outcome(armor: Armor, bonus_chance: int = 0) -> Tuple[bool, str, int]:
        """
        Returns (Success, StatIncreased, Amount).
        bonus_chance: Flat percentage added to success rate (e.g., 10).
        """
        base_rate = 0.8 # 80% base
        max_tempers = 3
        if armor.level > 40: max_tempers = 4
        if armor.level > 80: max_tempers = 5
        
        current_step = max_tempers - armor.temper_remaining
        success_rate = base_rate - (current_step * 0.05) + (bonus_chance / 100.0)

        if random.random() > success_rate:
            return False, "", 0

        stat = 'fdr'
        amount = 0
        if armor.pdr > 0:
            stat = 'pdr'
            amount = max(1, random.randint(int(armor.level // 33), int(armor.level // 16)))
        elif armor.fdr > 0:
            stat = 'fdr'
            amount = max(1, random.randint(int(armor.level // 100), int(armor.level // 25)))
        
        return True, stat, amount

    # --- POTENTIAL (Accessory) LOGIC ---
    @staticmethod
    def calculate_potential_cost(level: int) -> int:
        """Returns Gold cost based on current passive level (0-9)."""
        costs = [500, 1000, 2000, 3000, 4000, 5000, 10000, 25000, 50000, 100000]
        if level < len(costs):
            return costs[level]
        return 999999999

    # --- POTENTIAL (Glove/Boot/Helmet) LOGIC ---
    @staticmethod
    def calculate_ap_cost(level: int) -> int:
        """Returns Gold cost based on current passive level (0-9)."""
        costs = [1000, 5000, 25000, 50000, 100000, 200000]
        if level < len(costs):
            return costs[level]
        return 999999999

    @staticmethod
    def roll_potential_outcome(current_level: int, bonus_chance: int = 0) -> bool:
        """
        Calculates success based on level + bonus.
        bonus_chance: Flat percentage (e.g. 25 or 15).
        """
        base_chance = max(75 - (current_level * 5), 30)
        total_chance = base_chance + bonus_chance
        
        return random.randint(1, 100) <= total_chance

    @staticmethod
    def get_new_passive(item_type: Literal['accessory', 'glove', 'boot', 'helmet']) -> str:
        """Returns a random passive name for a fresh unlock."""
        if item_type == 'accessory':
            return random.choice(["Obliterate", "Absorb", "Prosper", "Infinite Wisdom", "Lucky Strikes"])
        elif item_type == 'glove':
            return random.choice(["ward-touched", "ward-fused", "instability", "deftness", "adroit", "equilibrium", "plundering"])
        elif item_type == 'boot':
            return random.choice(["speedster", "skiller", "treasure-tracker", "hearty", "cleric", "thrill-seeker"])
        elif item_type == 'helmet':
            return random.choice([
                "thorns", "ghosted", "juggernaut", "insight", 
                "volatile", "divine", "frenzy", "leeching"
            ])
        return "none"
    
    