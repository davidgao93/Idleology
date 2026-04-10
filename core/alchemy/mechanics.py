import random
from typing import Optional, Tuple


class AlchemyMechanics:
    MAX_LEVEL = 10

    # Gold cost to advance from level N to N+1
    LEVEL_COSTS: dict[int, int] = {
        0: 500,
        1: 1_500,
        2: 3_000,
        3: 5_000,
        4: 8_000,
        5: 12_000,
        6: 18_000,
        7: 25_000,
        8: 35_000,
        9: 50_000,
    }

    # ------------------------------------------------------------------
    # Slot progression
    # ------------------------------------------------------------------

    @staticmethod
    def get_slot_count(level: int) -> int:
        """Number of active potion-passive slots unlocked at *level*."""
        if level >= 10: return 5
        if level >= 7:  return 4
        if level >= 5:  return 3
        if level >= 3:  return 2
        if level >= 1:  return 1
        return 0

    # ------------------------------------------------------------------
    # Potion Passives
    # ------------------------------------------------------------------

    # Keys mirror the passive_type stored in DB.
    # min_val / max_val are the FULL range at level 10.
    # At level 1 only 30 % of the range above min is accessible; each level
    # adds 7 percentage points, capping at 100 % at level 10.
    PASSIVES: dict[str, dict] = {
        "potent_concoction": {
            "name":    "Potent Concoction",
            "emoji":   "🧪",
            "desc":    "+{value:.0f}% base heal from potions",
            "min_val": 5.0,
            "max_val": 30.0,
            "unit":    "%",
        },
        "alchemical_frenzy": {
            "name":    "Alchemical Frenzy",
            "emoji":   "🌀",
            "desc":    "{value:.0f}% chance to double your heal",
            "min_val": 5.0,
            "max_val": 40.0,
            "unit":    "%",
        },
        "second_wind": {
            "name":    "Second Wind",
            "emoji":   "💨",
            "desc":    "{value:.0f}% chance potion is not consumed on use",
            "min_val": 5.0,
            "max_val": 40.0,
            "unit":    "%",
        },
        "overflowing_vigor": {
            "name":    "Overflowing Vigor",
            "emoji":   "💧",
            "desc":    "Gain {value:.0f}% of missing HP as bonus healing",
            "min_val": 5.0,
            "max_val": 25.0,
            "unit":    "%",
        },
        "ward_infusion": {
            "name":    "Ward Infusion",
            "emoji":   "🔮",
            "desc":    "Generate {value:.0f}% of max HP as Ward on heal",
            "min_val": 2.0,
            "max_val": 12.0,
            "unit":    "%",
        },
        "lingering_remedy": {
            "name":    "Lingering Remedy",
            "emoji":   "🌿",
            "desc":    "Heal {value:.0f} HP per turn for 3 turns",
            "min_val": 10.0,
            "max_val": 60.0,
            "unit":    "flat",
        },
        "bottled_courage": {
            "name":    "Bottled Courage",
            "emoji":   "⚔️",
            "desc":    "Your next attack cannot miss after using a potion",
            "min_val": 1.0,
            "max_val": 1.0,
            "unit":    "bool",
        },
        "warriors_draft": {
            "name":    "Warrior's Draft",
            "emoji":   "💪",
            "desc":    "+{value:.0f}% ATK for the rest of combat after using a potion",
            "min_val": 5.0,
            "max_val": 30.0,
            "unit":    "%",
        },
        "iron_skin": {
            "name":    "Iron Skin",
            "emoji":   "🛡️",
            "desc":    "-{value:.0f}% incoming damage for 3 turns after potion",
            "min_val": 5.0,
            "max_val": 30.0,
            "unit":    "%",
        },
        "venomous_tincture": {
            "name":    "Venomous Tincture",
            "emoji":   "🐍",
            "desc":    "Deal {value:.0f} damage to your foe when you use a potion",
            "min_val": 15.0,
            "max_val": 80.0,
            "unit":    "flat",
        },
    }

    # Gold cost to roll a passive into a given slot (1-indexed)
    ROLL_COSTS: dict[int, int] = {1: 500, 2: 1_000, 3: 2_000, 4: 4_000, 5: 8_000}

    # ------------------------------------------------------------------
    # Transmutation
    # ------------------------------------------------------------------

    # Ordered resource columns per skill
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

    # Source resources required per 1 destination resource (always 8:1)
    TRANSMUTE_RATIO: int = 8

    # Gold cost per single transmutation, indexed by source-tier index (0 = T1→T2)
    TRANSMUTE_GOLD: dict[int, int] = {0: 50, 1: 150, 2: 400, 3: 1_000}

    # Spirit-stone → resource rates  {tier_index: qty_per_stone}
    SPIRIT_STONE_RATES: dict[int, int] = {3: 5, 4: 2}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_level_up_cost(current_level: int) -> Optional[int]:
        """Gold cost to advance to the next level; None if already at max."""
        if current_level >= AlchemyMechanics.MAX_LEVEL:
            return None
        return AlchemyMechanics.LEVEL_COSTS.get(current_level)

    @staticmethod
    def roll_passive(alchemy_level: int) -> Tuple[str, float]:
        """
        Randomly selects a passive type and rolls a value appropriate for
        the current alchemy level.  Higher level = larger possible values.
        """
        passive_type = random.choice(list(AlchemyMechanics.PASSIVES.keys()))
        info = AlchemyMechanics.PASSIVES[passive_type]

        if info["unit"] == "bool":
            return passive_type, 1.0

        # Scale: level 1 → 30 % of range; level 10 → 100 % of range
        scale = min(1.0, 0.30 + 0.077 * (alchemy_level - 1))
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
