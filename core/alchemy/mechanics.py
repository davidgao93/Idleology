import random
from typing import Optional, Tuple


class AlchemyMechanics:
    MAX_LEVEL = 5

    # Spirit Stone cost to advance from level N to N+1
    LEVEL_COSTS: dict[int, int] = {
        1: 10,
        2: 15,
        3: 25,
        4: 40,
    }

    # ------------------------------------------------------------------
    # Slot progression — 1 slot per level (level 1 = 1 slot, level 5 = 5 slots)
    # ------------------------------------------------------------------

    @staticmethod
    def get_slot_count(level: int) -> int:
        """Number of active potion-passive slots unlocked at *level*."""
        return max(0, min(level, AlchemyMechanics.MAX_LEVEL))

    # ------------------------------------------------------------------
    # Transmutation ratios (depends on alchemy level)
    # ------------------------------------------------------------------

    @staticmethod
    def get_upgrade_ratio(alchemy_level: int) -> int:
        """Number of lower-tier resources needed to produce 1 higher-tier resource."""
        if alchemy_level >= 5:
            return 2
        if alchemy_level >= 3:
            return 3
        return 4  # level 1-2

    @staticmethod
    def get_downgrade_ratio(alchemy_level: int) -> int:
        """Number of lower-tier resources received when breaking down 1 higher-tier resource."""
        if alchemy_level >= 5:
            return 4
        if alchemy_level >= 3:
            return 3
        return 2  # level 1-2

    # ------------------------------------------------------------------
    # Potion Passives
    # ------------------------------------------------------------------

    # Keys mirror the passive_type stored in DB.
    # min_val / max_val are the full range across levels 1–5.
    # At level 1: min_val; at level 5: up to max_val.
    PASSIVES: dict[str, dict] = {
        "fermented_brew": {
            "name":    "Fermented Brew",
            "emoji":   "🍺",
            "desc":    "+{value:.0f}% bonus to heal amount",
            "min_val": 15.0,
            "max_val": 45.0,
            "unit":    "%",
        },
        "venom_cure": {
            "name":    "Venom Cure",
            "emoji":   "🐍",
            "desc":    "Deal damage equal to {value:.1f}× the heal to the enemy",
            "min_val": 2.0,
            "max_val": 6.0,
            "unit":    "mult",
        },
        "warriors_draft": {
            "name":    "Warrior's Draft",
            "emoji":   "💪",
            "desc":    "+{value:.0f}% ATK on your next attack this combat",
            "min_val": 8.0,
            "max_val": 20.0,
            "unit":    "%",
        },
        "iron_skin": {
            "name":    "Iron Skin",
            "emoji":   "🛡️",
            "desc":    "+{value:.0f}% DEF for the next 2 monster turns",
            "min_val": 8.0,
            "max_val": 20.0,
            "unit":    "%",
        },
        "ward_infusion": {
            "name":    "Ward Infusion",
            "emoji":   "🔮",
            "desc":    "Restore Ward equal to {value:.0f}% of the heal amount",
            "min_val": 15.0,
            "max_val": 40.0,
            "unit":    "%",
        },
        "overcap_brew": {
            "name":    "Overcap Brew",
            "emoji":   "💥",
            "desc":    "Overheal stored as temp HP up to {value:.0f}% of max HP (lost on hit)",
            "min_val": 20.0,
            "max_val": 50.0,
            "unit":    "%",
        },
        "unstable_mixture": {
            "name":    "Unstable Mixture",
            "emoji":   "🌀",
            "desc":    "50% chance to double the heal — 50% chance to halve it",
            "min_val": 1.0,
            "max_val": 1.0,
            "unit":    "bool",
        },
        "dulled_pain": {
            "name":    "Dulled Pain",
            "emoji":   "🩹",
            "desc":    "Take {value:.0f}% less damage from the monster's next attack",
            "min_val": 25.0,
            "max_val": 50.0,
            "unit":    "%",
        },
        "lingering_remedy": {
            "name":    "Lingering Remedy",
            "emoji":   "🌿",
            "desc":    "Restore {value:.0f} HP at the start of each of your next 3 turns",
            "min_val": 5.0,
            "max_val": 20.0,
            "unit":    "flat",
        },
        "bottled_courage": {
            "name":    "Bottled Courage",
            "emoji":   "⚔️",
            "desc":    "After healing, your next hit cannot miss",
            "min_val": 1.0,
            "max_val": 1.0,
            "unit":    "bool",
        },
    }

    # Spirit Stone cost to reroll any slot (flat 1 per reroll)
    REROLL_COST: int = 1  # spirit stones

    # ------------------------------------------------------------------
    # Transmutation resource definitions
    # ------------------------------------------------------------------

    # Ordered resource columns per skill (index 0 = tier 1, index 4 = tier 5)
    SKILL_TIERS: dict[str, list[str]] = {
        "mining":      ["iron", "coal", "gold", "platinum", "idea"],
        "fishing":     ["desiccated_bones", "regular_bones", "sturdy_bones",
                        "reinforced_bones", "titanium_bones"],
        "woodcutting": ["oak_logs", "willow_logs", "mahogany_logs",
                        "magic_logs", "idea_logs"],
    }

    # Human-readable tier names matching the same order
    SKILL_TIER_NAMES: dict[str, list[str]] = {
        "mining":      ["Iron",    "Coal",    "Gold",     "Platinum",    "Idea Ore"],
        "fishing":     ["Desd.",   "Regular", "Sturdy",   "Reinforced",  "Titanium"],
        "woodcutting": ["Oak",     "Willow",  "Mahogany", "Magic",       "Idea Logs"],
    }

    # Gold cost per upgrade transmutation, keyed by destination tier index (1=T2 … 4=T5)
    TRANSMUTE_UPGRADE_GOLD: dict[int, int] = {1: 2_000, 2: 8_000, 3: 25_000, 4: 75_000}

    # Gold cost per downgrade transmutation, keyed by source tier index (1=T2 … 4=T5)
    TRANSMUTE_DOWNGRADE_GOLD: dict[int, int] = {1: 500, 2: 2_000, 3: 6_000, 4: 20_000}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_level_up_cost(current_level: int) -> Optional[int]:
        """Spirit Stone cost to advance to the next level; None if already at max."""
        if current_level >= AlchemyMechanics.MAX_LEVEL:
            return None
        return AlchemyMechanics.LEVEL_COSTS.get(current_level)

    @staticmethod
    def roll_passive(alchemy_level: int) -> Tuple[str, float]:
        """
        Randomly selects a passive type and rolls a value appropriate for
        the current alchemy level.  Level 1 = min value; level 5 = full range.
        """
        passive_type = random.choice(list(AlchemyMechanics.PASSIVES.keys()))
        info = AlchemyMechanics.PASSIVES[passive_type]

        if info["unit"] == "bool":
            return passive_type, 1.0

        # Scale: level 1 → min_val only; level 5 → full range
        scale = (alchemy_level - 1) / (AlchemyMechanics.MAX_LEVEL - 1)
        lo = info["min_val"]
        hi = lo + (info["max_val"] - lo) * scale
        value = round(random.uniform(lo, hi), 1)
        return passive_type, value

    @staticmethod
    def format_passive(passive_type: str, passive_value: float) -> str:
        """Returns a short human-readable description for a passive + value."""
        info = AlchemyMechanics.PASSIVES.get(passive_type)
        if not info:
            return f"{passive_type}: {passive_value}"
        if info["unit"] == "bool":
            return info["desc"]
        return info["desc"].format(value=passive_value)

    @staticmethod
    def format_passive_range(passive_type: str) -> str:
        """Returns the passive description showing the full min–max value range."""
        import re
        info = AlchemyMechanics.PASSIVES.get(passive_type)
        if not info:
            return passive_type
        if info["unit"] == "bool":
            return info["desc"]
        lo = info["min_val"]
        hi = info["max_val"]
        # Detect decimal places from the format spec in the desc, e.g. {value:.1f} → 1 dp
        match = re.search(r"\{value:\.(\d)f\}", info["desc"])
        dp = int(match.group(1)) if match else 0
        fmt = f".{dp}f"
        range_str = f"{lo:{fmt}}–{hi:{fmt}}"
        result = re.sub(r"\{value[^}]*\}", range_str, info["desc"])
        return result
