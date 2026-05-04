# core/settlement/mechanics.py

import random
from typing import Dict, Optional

from core.settlement.constants import (
    ITEM_NAMES,
    SPECIAL_MAP,
    UBER_BUILDINGS,
)


class SettlementMechanics:

    # --- CONSTANTS ---
    MAX_TIER = 5

    # Building Definitions
    # 'type': generator (creates from thin air), converter (consumes input), passive (buff)
    BUILDINGS = {
        "logging_camp": {"type": "generator", "output": "timber", "base_rate": 1},
        "quarry": {"type": "generator", "output": "stone", "base_rate": 1},
        "market": {
            "type": "generator",
            "output": "market_gold",
            "base_rate": 50,
        },  # 50 gold (currency) per worker/hr
        "foundry": {
            "type": "converter",
            "map": [
                ("iron", "iron_bar"),
                ("coal", "steel_bar"),
                ("gold", "gold_bar"),
                ("platinum", "platinum_bar"),
                ("idea", "idea_bar"),
            ],
            "base_rate": 1,  # 5 conversions per worker/hr
        },
        "sawmill": {
            "type": "converter",
            "map": [
                ("oak_logs", "oak_plank"),
                ("willow_logs", "willow_plank"),
                ("mahogany_logs", "mahogany_plank"),
                ("magic_logs", "magic_plank"),
                ("idea_logs", "idea_plank"),
            ],
            "base_rate": 1,
        },
        "reliquary": {
            "type": "converter",
            "map": [
                ("desiccated_bones", "desiccated_essence"),
                ("regular_bones", "regular_essence"),
                ("sturdy_bones", "sturdy_essence"),
                ("reinforced_bones", "reinforced_essence"),
                ("titanium_bones", "titanium_essence"),
            ],
            "base_rate": 1,
        },
        "barracks": {"type": "passive", "effect": "combat_stats"},
        "temple": {"type": "passive", "effect": "propagate_bonus"},
        "town_hall": {"type": "core", "effect": "caps"},
        "apothecary": {"type": "passive", "effect": "potion_buff"},
        # Type 'special' means it has no passive production, handled via custom View
        "black_market": {"type": "special", "effect": "trading"},
        # Generates 'companion_cookie' which is auto-converted to XP on collect
        "companion_ranch": {
            "type": "generator",
            "output": "companion_cookie",
            "base_rate": 1,
        },  # 1 XP per worker/hr
        "celestial_shrine": {"type": "passive", "effect": "sigil_bonus"},
        "infernal_forge": {"type": "passive", "effect": "infernal_sigil_bonus"},
        "void_sanctum": {"type": "passive", "effect": "void_shard_bonus"},
        "twin_shrine": {"type": "passive", "effect": "gemini_sigil_bonus"},
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
        raw_inventory: Dict[str, int] = None,
    ) -> Dict[str, int]:
        """
        Calculates production for a specific building over time.
        Returns dict of changes: {'iron': -100, 'iron_bar': 100, 'timber': 50}
        """
        if workers <= 0 or hours_elapsed <= 0:
            return {}

        b_data = SettlementMechanics.BUILDINGS.get(building_type)
        if not b_data:
            return {}

        # Safely fetch base_rate. If 0 (passives/special), it produces nothing.
        base_rate = b_data.get("base_rate", 0)
        if base_rate == 0:
            return {}

        changes = {}

        # Rate = Base * Tier * Workers
        # Example: T1 Logging Camp w/ 100 workers = 1 * 1 * 100 = 100 Timber/hr
        production_capacity = int(base_rate * tier * workers * hours_elapsed)

        if b_data["type"] == "generator":
            changes[b_data["output"]] = production_capacity

        elif b_data["type"] == "converter" and raw_inventory:
            remaining_capacity = production_capacity

            # Iterate through tier mappings (Lowest to Highest)
            for raw_key, refined_key in b_data["map"]:
                if raw_key in raw_inventory:
                    available_raw = raw_inventory[raw_key]

                    # How much can we convert?
                    amount_to_convert = min(available_raw, remaining_capacity)

                    if amount_to_convert > 0:
                        changes[raw_key] = changes.get(raw_key, 0) - amount_to_convert
                        changes[refined_key] = (
                            changes.get(refined_key, 0) + amount_to_convert
                        )

                        remaining_capacity -= amount_to_convert

                    if remaining_capacity <= 0:
                        break

        return changes

    @staticmethod
    def roll_event(hours_elapsed: float) -> Optional[str]:
        """
        Checks if a random event occurred during the elapsed time.
        """
        if hours_elapsed < 1:
            return None

        # 1% chance per hour
        chance = 0.01 * hours_elapsed
        if random.random() < chance:
            events = [
                "Traveling Merchant visited! Gained 5,000 Gold.",
                "Minor earthquake! A few stones fell loose (+10 Stone).",
                "A worker slacked off. Production reduced slightly (Flavor).",
                "A wandering bard entertained your followers. Morale high!",
            ]
            return random.choice(events)
        return None

    @staticmethod
    def get_multiplier(tier: int) -> float:
        """Black Market tier bonus multiplier."""
        if tier == 1:
            return 1.0
        if tier == 2:
            return 1.2
        if tier == 3:
            return 1.3
        if tier == 4:
            return 1.4
        if tier == 5:
            return 1.5
        return 1.0

    @staticmethod
    def get_upgrade_cost(building_type: str, current_tier: int) -> dict:
        """Unified upgrade cost calculator for ALL building types."""
        target_tier = current_tier + 1

        def _round_to_thousand(n: int) -> int:
            """Round to nearest 1,000 (standard rounding)."""
            return round(n / 1000) * 1000

        # 1. Uber buildings (flat high cost)
        if building_type in UBER_BUILDINGS:
            cost = {
                "timber": _round_to_thousand(target_tier * 100_000),
                "stone": _round_to_thousand(target_tier * 100_000),
                "gold": _round_to_thousand(target_tier * 10_000_000),
            }
            special_col = SPECIAL_MAP.get(building_type)
            if special_col:
                cost.update(
                    {
                        "special_key": special_col,
                        "special_name": ITEM_NAMES.get(special_col, "Special Material"),
                        "special_qty": target_tier - 1,
                    }
                )
            return cost

        # 2. Black Market (original formula)
        if building_type == "black_market":
            base_wood = base_stone = 50_000
            base_gold = 1000000
            cost = {
                "timber": _round_to_thousand(int(base_wood * (target_tier**1.5))),
                "stone": _round_to_thousand(int(base_stone * (target_tier**1.5))),
                "gold": _round_to_thousand(int(base_gold * (target_tier**1.5))),
            }
            # NEW: Every upgrade requires ALL THREE special materials
            qty = target_tier - 1  # T2=1, T3=2, ...
            cost["specials"] = [
                {"key": "magma_core", "name": "Magma Core", "qty": qty},
                {"key": "life_root", "name": "Life Root", "qty": qty},
                {"key": "spirit_shard", "name": "Spirit Shard", "qty": qty},
            ]
            return cost

        # 3. Town Hall (now up to Tier 7 with all three specials)
        if building_type == "town_hall":
            base = 50_000
            base_gold = 500_000
            cost = {
                "timber": _round_to_thousand(int(base * (target_tier**1.5))),
                "stone": _round_to_thousand(int(base * (target_tier**1.5))),
                "gold": _round_to_thousand(int(base_gold * (target_tier**1.5))),
            }

            # Every Town Hall upgrade requires all three special materials
            qty = target_tier - 1  # T2=1, T3=2, ..., T7=6
            cost["specials"] = [
                {"key": "magma_core", "name": "Magma Core", "qty": qty},
                {"key": "life_root", "name": "Life Root", "qty": qty},
                {"key": "spirit_shard", "name": "Spirit Shard", "qty": qty},
            ]
            return cost

        # 4. Standard buildings
        base_wood = 200
        base_stone = 200
        base_gold = 50000
        cost = {
            "timber": _round_to_thousand(int(base_wood * (target_tier**1.5))),
            "stone": _round_to_thousand(int(base_stone * (target_tier**1.5))),
            "gold": _round_to_thousand(int(base_gold * (target_tier**2))),
        }

        if target_tier >= 3:
            special_col = SPECIAL_MAP.get(building_type, "magma_core")
            cost.update(
                {
                    "special_key": special_col,
                    "special_name": ITEM_NAMES.get(special_col, "Special Material"),
                    "special_qty": target_tier - 2,  # T3=1, T4=2, T5=3
                }
            )
        return cost
