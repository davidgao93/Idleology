import random
from typing import Dict, Tuple, Optional, List

class SkillMechanics:

    # --- Minigame Config ---

    # Fishing: (min_wait_seconds, max_wait_seconds) per rod tier
    FISHING_TIMINGS = {
        "desiccated": (270, 330),
        "regular":    (210, 270),
        "sturdy":     (150, 210),
        "reinforced": (90,  150),
        "titanium":   (45,  75),
    }

    # Forestry: cooldown in seconds after a tree is felled, per axe tier
    FORESTRY_COOLDOWNS = {
        "flimsy":    300,
        "carved":    240,
        "chopping":  180,
        "magic":     120,
        "felling":    60,
    }

    # Gold cost to buy bait / forestry pass, per tool tier
    MINIGAME_ENTRY_COSTS = {
        "fishing": {
            "desiccated": 1_000,
            "regular":    5_000,
            "sturdy":     15_000,
            "reinforced": 30_000,
            "titanium":   50_000,
        },
        "forestry": {
            "flimsy":    1_000,
            "carved":    5_000,
            "chopping":  15_000,
            "magic":     30_000,
            "felling":   50_000,
        },
    }

    # Number of Swing clicks needed to fell a tree, per axe tier
    FORESTRY_SWINGS = {
        "flimsy":   8,
        "carved":   6,
        "chopping": 5,
        "magic":    4,
        "felling":  3,
    }

    @staticmethod
    def get_fishing_wait(rod_tier: str) -> int:
        """Returns a randomised wait time in seconds for the given rod tier."""
        lo, hi = SkillMechanics.FISHING_TIMINGS.get(rod_tier, (270, 330))
        return random.randint(lo, hi)

    @staticmethod
    def get_forestry_cooldown(axe_tier: str) -> int:
        """Returns the post-fell cooldown in seconds for the given axe tier."""
        return SkillMechanics.FORESTRY_COOLDOWNS.get(axe_tier, 300)

    @staticmethod
    def get_entry_cost(activity: str, tool_tier: str) -> int:
        """Returns the gold entry cost for a single fishing cast or forestry session."""
        return SkillMechanics.MINIGAME_ENTRY_COSTS.get(activity, {}).get(tool_tier, 1_000)

    @staticmethod
    def get_swings_needed(axe_tier: str) -> int:
        """Returns the number of Swing clicks required to fell a tree."""
        return SkillMechanics.FORESTRY_SWINGS.get(axe_tier, 8)

    SKILL_CONFIG = {
    "mining": {
        "display_name": "Mining",
        "emoji": "⛏️",
        "tool_name": "Pickaxe",
        "image": "https://i.imgur.com/4OS6Blx.jpeg",
        "resources": [
            ("iron", "Iron Ore"),
            ("coal", "Coal"),
            ("gold", "Gold Ore"),
            ("platinum", "Platinum Ore"),
            ("idea", "Idea Ore")
        ]
    },
    "woodcutting": {
        "display_name": "Woodcutting",
        "emoji": "🪓",
        "tool_name": "Axe",
        "image": "https://i.imgur.com/X0JdvX8.jpeg",
        "resources": [
            ("oak_logs", "Oak Logs"),
            ("willow_logs", "Willow Logs"),
            ("mahogany_logs", "Mahogany Logs"),
            ("magic_logs", "Magic Logs"),
            ("idea_logs", "Idea Logs")
        ]
    },
    "fishing": {
        "display_name": "Fishing",
        "emoji": "🎣",
        "tool_name": "Rod",
        "image": "https://i.imgur.com/JpgyGlD.jpeg",
        "resources": [
            ("desiccated_bones", "Desiccated Bones"),
            ("regular_bones", "Regular Bones"),
            ("sturdy_bones", "Sturdy Bones"),
            ("reinforced_bones", "Reinforced Bones"),
            ("titanium_bones", "Titanium Bones")
        ]
        }
    }

    @staticmethod
    def get_skill_info(skill: str) -> dict:
        """Returns UI configuration for a specific skill."""
        return SkillMechanics.SKILL_CONFIG.get(skill, {})

    @staticmethod
    def map_db_row_to_resources(skill: str, row: tuple) -> List[Tuple[str, int]]:
        """
        Maps a raw DB tuple to a list of (DisplayName, Amount).
        Assumes DB row structure: [..., tool_tier, res1, res2, res3, res4, res5]
        Indices 3-7 are resources.
        """
        config = SkillMechanics.SKILL_CONFIG.get(skill)
        if not config or not row: return []
        
        mapped = []
        # DB Indices 3 to 7 correspond to the 5 resources in order
        for i, (db_col, display_name) in enumerate(config['resources']):
            amount = row[i + 3]
            mapped.append((display_name, amount))
            
        return mapped
        
    @staticmethod
    def get_tool_tiers(skill: str) -> list[str]:
        if skill == "mining":
            return ['iron', 'steel', 'gold', 'platinum', 'ideal']
        elif skill == "woodcutting":
            return ['flimsy', 'carved', 'chopping', 'magic', 'felling']
        elif skill == "fishing":
            return ['desiccated', 'regular', 'sturdy', 'reinforced', 'titanium']
        return []

    @staticmethod
    def get_next_tier(skill: str, current_tier: str) -> Optional[str]:
        tiers = SkillMechanics.get_tool_tiers(skill)
        try:
            idx = tiers.index(current_tier)
            if idx + 1 < len(tiers):
                return tiers[idx + 1]
        except ValueError:
            pass
        return None

    @staticmethod
    def get_upgrade_cost(skill: str, current_tier: str) -> Optional[Dict[str, int]]:
        """
        Returns a dictionary of costs.
        Keys: 'resource_1', 'resource_2', 'resource_3', 'resource_4', 'gold'
        """
        # Define costs tuple: (res1, res2, res3, res4, gold)
        # Mapping matches the DB columns index logic in the repository
        
        costs_map = {}
        
        if skill == "mining":
            costs_map = {
                'iron': (100, 0, 0, 0, 1000),
                'steel': (200, 100, 0, 0, 5000),
                'gold': (300, 200, 100, 0, 10000),
                'platinum': (600, 400, 200, 100, 100000),
            }
        elif skill == "woodcutting":
            costs_map = {
                'flimsy': (100, 0, 0, 0, 1000),
                'carved': (200, 100, 0, 0, 5000),
                'chopping': (300, 200, 100, 0, 10000),
                'magic': (600, 400, 200, 100, 100000),
            }
        elif skill == "fishing":
            costs_map = {
                'desiccated': (100, 0, 0, 0, 1000),
                'regular': (200, 100, 0, 0, 5000),
                'sturdy': (300, 200, 100, 0, 10000),
                'reinforced': (600, 400, 200, 100, 50000),
            }

        cost_tuple = costs_map.get(current_tier)
        if not cost_tuple:
            return None

        return {
            'res_1': cost_tuple[0],
            'res_2': cost_tuple[1],
            'res_3': cost_tuple[2],
            'res_4': cost_tuple[3],
            'gold': cost_tuple[4]
        }
    

    @staticmethod
    def calculate_yield(skill_type: str, tool_tier: str) -> Dict[str, int]:
        """
        Calculates resource yield based on skill type and tool tier.
        Returns a dictionary {resource_column_name: amount}.
        """
        ranges = {}
        
        if skill_type == "mining":
            # Resources: iron, coal, gold, platinum, idea
            ranges = {
                'iron': {'iron': (3,5), 'steel': (4,7), 'gold': (5,8), 'platinum': (6,10), 'ideal': (7,12)},
                'coal': {'steel': (3,5), 'gold': (4,7), 'platinum': (5,8), 'ideal': (6,10)},
                'gold': {'gold': (3,5), 'platinum': (4,7), 'ideal': (5,8)},
                'platinum': {'platinum': (3,5), 'ideal': (4,7)},
                'idea': {'ideal': (3,5)}
            }
        elif skill_type == "fishing":
            # Resources: desiccated_bones, regular_bones, sturdy_bones, reinforced_bones, titanium_bones
            # Note: DB columns usually have _bones suffix, mapping keys here for DB compatibility
            ranges = {
                'desiccated_bones': {'desiccated': (3,5), 'regular': (4,7), 'sturdy': (5,8), 'reinforced': (6,10), 'titanium': (7,12)},
                'regular_bones': {'regular': (3,5), 'sturdy': (4,7), 'reinforced': (5,8), 'titanium': (6,10)},
                'sturdy_bones': {'sturdy': (3,5), 'reinforced': (4,7), 'titanium': (5,8)},
                'reinforced_bones': {'reinforced': (3,5), 'titanium': (4,7)},
                'titanium_bones': {'titanium': (3,5)}
            }
        elif skill_type == "woodcutting":
            # Resources: oak_logs, willow_logs, mahogany_logs, magic_logs, idea_logs
            ranges = {
                'oak_logs': {'flimsy': (3,5), 'carved': (4,7), 'chopping': (5,8), 'magic': (6,10), 'felling': (7,12)},
                'willow_logs': {'carved': (3,5), 'chopping': (4,7), 'magic': (5,8), 'felling': (6,10)},
                'mahogany_logs': {'chopping': (3,5), 'magic': (4,7), 'felling': (5,8)},
                'magic_logs': {'magic': (3,5), 'felling': (4,7)},
                'idea_logs': {'felling': (3,5)}
            }

        result = {}
        for resource, tier_map in ranges.items():
            min_val, max_val = tier_map.get(tool_tier, (0, 0))
            if max_val > 0:
                result[resource] = random.randint(min_val, max_val)
        
        return result