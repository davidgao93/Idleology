# core/settlement/mechanics.py

from typing import Dict

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
        "logging_camp": {"type": "generator", "output": "timber", "base_rate": 0.2},
        "quarry": {"type": "generator", "output": "stone", "base_rate": 0.2},
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
            "base_rate": 0.01,
        },  # 0.01 XP per worker/hr
        "hatchery": {"type": "special", "effect": "egg_incubation"},
        "war_camp": {
            "type": "generator",
            "output": "war_camp_stamina",
            "base_rate": 0.01,
        },  # 0.01 stamina per worker/hr
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
        production_raw = base_rate * tier * workers * hours_elapsed
        production_capacity = int(production_raw)

        if b_data["type"] == "generator":
            output_key = b_data["output"]
            if output_key == "war_camp_stamina":
                # Keep float precision — stamina is collected in decimal increments
                changes[output_key] = round(production_raw, 4)
            else:
                changes[output_key] = production_capacity

        elif b_data["type"] == "converter" and raw_inventory:
            # Each building tier unlocks the corresponding material slot:
            #   T1 → slot 0 only, T2 → slots 0-1, T3 → slots 0-2, etc.
            # All unlocked slots are processed simultaneously from independent
            # capacity pools — higher-tier (rarer) materials receive a smaller
            # weighted fraction of the total capacity.
            #
            # Weights descend from `tier` down to 1 (slot 0 is heaviest):
            #   T1: [1]          → 100% to slot 0
            #   T2: [2, 1]       → 67% / 33%
            #   T3: [3, 2, 1]    → 50% / 33% / 17%
            #   T4: [4, 3, 2, 1] → 40% / 30% / 20% / 10%
            #   T5: [5,4,3,2,1]  → 33% / 27% / 20% / 13% / 7%
            active_map = b_data["map"][:tier]
            n = len(active_map)
            weights = list(range(n, 0, -1))  # [n, n-1, ..., 1]
            total_weight = n * (n + 1) // 2  # = sum(weights)

            for i, (raw_key, refined_key) in enumerate(active_map):
                if raw_key not in raw_inventory or raw_inventory[raw_key] <= 0:
                    continue
                slot_capacity = int(production_capacity * weights[i] / total_weight)
                amount_to_convert = min(raw_inventory[raw_key], slot_capacity)
                if amount_to_convert > 0:
                    changes[raw_key] = changes.get(raw_key, 0) - amount_to_convert
                    changes[refined_key] = (
                        changes.get(refined_key, 0) + amount_to_convert
                    )

        return changes

    @staticmethod
    def get_converter_rates(
        building_type: str, tier: int, workers: int
    ) -> list[tuple[str, str, int]]:
        """
        Returns the per-hour processing rate for each material slot that is active
        at the given building tier, as a list of (raw_key, refined_key, rate_per_hr).

        Used by the detail view to display live rates without duplicating the
        capacity-weighting logic from calculate_production.
        """
        b_data = SettlementMechanics.BUILDINGS.get(building_type)
        if not b_data or b_data.get("type") != "converter":
            return []

        base_rate = b_data.get("base_rate", 1)
        active_map = b_data["map"][:tier]
        n = len(active_map)
        if n == 0:
            return []

        total_per_hr = base_rate * tier * workers
        weights = list(range(n, 0, -1))
        total_weight = n * (n + 1) // 2

        return [
            (raw_key, refined_key, int(total_per_hr * weights[i] / total_weight))
            for i, (raw_key, refined_key) in enumerate(active_map)
        ]

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
                "timber": _round_to_thousand(target_tier * 20_000),
                "stone": _round_to_thousand(target_tier * 20_000),
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
            base_wood = base_stone = 20_000
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
            base = 20_000
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
        base_wood = 500
        base_stone = 500
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
