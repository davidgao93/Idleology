import random
from typing import Dict, List, Optional, Tuple

from core.images import TOOL_AXE, TOOL_PICKAXE, TOOL_ROD

# Artisan Mastery integration
from core.skills import mastery as Mastery


class SkillMechanics:

    # --- Minigame Config ---

    # Fishing: (min_wait_seconds, max_wait_seconds) per rod tier
    FISHING_TIMINGS = {
        "desiccated": (270, 330),
        "regular": (210, 270),
        "sturdy": (150, 210),
        "reinforced": (90, 150),
        "titanium": (45, 75),
    }

    # Forestry: cooldown in seconds after a tree is felled, per axe tier
    FORESTRY_COOLDOWNS = {
        "flimsy": 300,
        "carved": 240,
        "chopping": 180,
        "magic": 120,
        "felling": 60,
    }

    # Gold cost to buy bait / forestry pass, per tool tier
    MINIGAME_ENTRY_COSTS = {
        "fishing": {
            "desiccated": 500,
            "regular": 1_500,
            "sturdy": 5_000,
            "reinforced": 10_000,
            "titanium": 30_000,
        },
        "forestry": {
            "flimsy": 500,
            "carved": 1_500,
            "chopping": 5_000,
            "magic": 10_000,
            "felling": 30_000,
        },
    }

    # Number of Swing clicks needed to fell a tree, per axe tier
    FORESTRY_SWINGS = {
        "flimsy": 8,
        "carved": 6,
        "chopping": 5,
        "magic": 4,
        "felling": 3,
    }

    # ─── Gathering Expansion: Familiarization Gates + Session Quality ────────────

    # Hours each tool upgrade gate lasts after purchasing that tier.
    # Key = the tier just purchased; gate controls when the NEXT upgrade is unlocked.
    # Only non-BiS tiers appear (BiS tiers don't gate another upgrade).
    FAMILIARIZATION_HOURS: dict = {
        "mining": {"steel": 4, "gold": 6, "platinum": 10},
        "woodcutting": {"carved": 4, "chopping": 6, "magic": 10},
        "fishing": {"regular": 4, "sturdy": 6, "reinforced": 10},
    }

    # Maximum momentum (minutes) a player can bank per skill across the whole path.
    # 25% of total gate hours → 25% * (4+6+10) * 60 = 300 min per skill.
    MAX_MOMENTUM_MINUTES: dict = {skill: 300 for skill in ("mining", "woodcutting", "fishing")}

    # Momentum (minutes toward next gate) earned per session quality tier.
    MOMENTUM_MINUTES: dict = {"none": 0, "good": 10, "great": 15, "masterful": 22}

    # Yield multiplier applied on top of base yield for quality sessions.
    QUALITY_YIELD_BONUS: dict = {"none": 1.0, "good": 1.05, "great": 1.10, "masterful": 1.15}

    # Forestry: max seconds between swings to count as "in rhythm".
    FORESTRY_RHYTHM_WINDOW: int = 45

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
        return SkillMechanics.MINIGAME_ENTRY_COSTS.get(activity, {}).get(
            tool_tier, 1_000
        )

    @staticmethod
    def get_swings_needed(axe_tier: str) -> int:
        """Returns the number of Swing clicks required to fell a tree."""
        return SkillMechanics.FORESTRY_SWINGS.get(axe_tier, 8)

    SKILL_CONFIG = {
        "mining": {
            "display_name": "Mining",
            "emoji": "⛏️",
            "tool_name": "Pickaxe",
            "image": TOOL_PICKAXE,
            "resources": [
                ("iron", "Iron Ore"),
                ("coal", "Coal"),
                ("gold", "Gold Ore"),
                ("platinum", "Platinum Ore"),
                ("idea", "Idea Ore"),
            ],
        },
        "woodcutting": {
            "display_name": "Woodcutting",
            "emoji": "🪓",
            "tool_name": "Axe",
            "image": TOOL_AXE,
            "resources": [
                ("oak_logs", "Oak Logs"),
                ("willow_logs", "Willow Logs"),
                ("mahogany_logs", "Mahogany Logs"),
                ("magic_logs", "Magic Logs"),
                ("idea_logs", "Idea Logs"),
            ],
        },
        "fishing": {
            "display_name": "Fishing",
            "emoji": "🎣",
            "tool_name": "Rod",
            "image": TOOL_ROD,
            "resources": [
                ("desiccated_bones", "Desiccated Bones"),
                ("regular_bones", "Regular Bones"),
                ("sturdy_bones", "Sturdy Bones"),
                ("reinforced_bones", "Reinforced Bones"),
                ("titanium_bones", "Titanium Bones"),
            ],
        },
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
        if not config or not row:
            return []

        mapped = []
        # DB Indices 3 to 7 correspond to the 5 resources in order
        for i, (db_col, display_name) in enumerate(config["resources"]):
            amount = row[i + 3]
            mapped.append((display_name, amount))

        return mapped

    @staticmethod
    def get_tool_tiers(skill: str) -> list[str]:
        if skill == "mining":
            return ["iron", "steel", "gold", "platinum", "ideal"]
        elif skill == "woodcutting":
            return ["flimsy", "carved", "chopping", "magic", "felling"]
        elif skill == "fishing":
            return ["desiccated", "regular", "sturdy", "reinforced", "titanium"]
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
                "iron": (100, 0, 0, 0, 1000),
                "steel": (200, 100, 0, 0, 5000),
                "gold": (300, 200, 100, 0, 10000),
                "platinum": (600, 400, 200, 100, 100000),
            }
        elif skill == "woodcutting":
            costs_map = {
                "flimsy": (100, 0, 0, 0, 1000),
                "carved": (200, 100, 0, 0, 5000),
                "chopping": (300, 200, 100, 0, 10000),
                "magic": (600, 400, 200, 100, 100000),
            }
        elif skill == "fishing":
            costs_map = {
                "desiccated": (100, 0, 0, 0, 1000),
                "regular": (200, 100, 0, 0, 5000),
                "sturdy": (300, 200, 100, 0, 10000),
                "reinforced": (600, 400, 200, 100, 50000),
            }

        cost_tuple = costs_map.get(current_tier)
        if not cost_tuple:
            return None

        return {
            "res_1": cost_tuple[0],
            "res_2": cost_tuple[1],
            "res_3": cost_tuple[2],
            "res_4": cost_tuple[3],
            "gold": cost_tuple[4],
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
                "iron": {
                    "iron": (3, 5),
                    "steel": (4, 7),
                    "gold": (5, 8),
                    "platinum": (6, 10),
                    "ideal": (7, 12),
                },
                "coal": {
                    "steel": (3, 5),
                    "gold": (4, 7),
                    "platinum": (5, 8),
                    "ideal": (6, 10),
                },
                "gold": {"gold": (3, 5), "platinum": (4, 7), "ideal": (5, 8)},
                "platinum": {"platinum": (3, 5), "ideal": (4, 7)},
                "idea": {"ideal": (3, 5)},
            }
        elif skill_type == "fishing":
            # Resources: desiccated_bones, regular_bones, sturdy_bones, reinforced_bones, titanium_bones
            # Note: DB columns usually have _bones suffix, mapping keys here for DB compatibility
            ranges = {
                "desiccated_bones": {
                    "desiccated": (3, 5),
                    "regular": (4, 7),
                    "sturdy": (5, 8),
                    "reinforced": (6, 10),
                    "titanium": (7, 12),
                },
                "regular_bones": {
                    "regular": (3, 5),
                    "sturdy": (4, 7),
                    "reinforced": (5, 8),
                    "titanium": (6, 10),
                },
                "sturdy_bones": {
                    "sturdy": (3, 5),
                    "reinforced": (4, 7),
                    "titanium": (5, 8),
                },
                "reinforced_bones": {"reinforced": (3, 5), "titanium": (4, 7)},
                "titanium_bones": {"titanium": (3, 5)},
            }
        elif skill_type == "woodcutting":
            # Resources: oak_logs, willow_logs, mahogany_logs, magic_logs, idea_logs
            ranges = {
                "oak_logs": {
                    "flimsy": (3, 5),
                    "carved": (4, 7),
                    "chopping": (5, 8),
                    "magic": (6, 10),
                    "felling": (7, 12),
                },
                "willow_logs": {
                    "carved": (3, 5),
                    "chopping": (4, 7),
                    "magic": (5, 8),
                    "felling": (6, 10),
                },
                "mahogany_logs": {
                    "chopping": (3, 5),
                    "magic": (4, 7),
                    "felling": (5, 8),
                },
                "magic_logs": {"magic": (3, 5), "felling": (4, 7)},
                "idea_logs": {"felling": (3, 5)},
            }

        result = {}
        for resource, tier_map in ranges.items():
            min_val, max_val = tier_map.get(tool_tier, (0, 0))
            if max_val > 0:
                result[resource] = random.randint(min_val, max_val)

        return result

    @staticmethod
    def calculate_yield_with_mastery(
        skill_type: str, tool_tier: str, mastery_row: dict | None
    ) -> Dict[str, int]:
        """
        Mastery-aware yield. Applies global Yield branch multipliers + Quality signature
        resource bonuses. Signature below-tier chance is handled by caller (passive only).
        Rich events and remnant generation are handled exclusively in the hourly task.
        """
        base = SkillMechanics.calculate_yield(skill_type, tool_tier)
        if not mastery_row:
            return base

        y_mult = Mastery.get_yield_multiplier(skill_type, mastery_row)
        sig_mult = Mastery.get_signature_resource_bonus(skill_type, mastery_row)

        # Map display/internal names for signature resources
        sig_map = {
            "mining": ("idea", "idea"),
            "fishing": ("titanium_bones", "titanium_bones"),
            "woodcutting": ("idea_logs", "idea_logs"),
        }
        sig_col = sig_map.get(skill_type, (None, None))[0]

        result = {}
        for res, amt in base.items():
            amt = int(amt * y_mult)
            if sig_col and res == sig_col:
                amt = int(amt * sig_mult)
            result[res] = max(0, amt)
        return result

    # ─── Gathering Expansion: Pure calculation helpers ────────────────────────────

    @staticmethod
    def get_familiarization_hours(skill: str, new_tier: str) -> int:
        """Gate hours after purchasing new_tier (0 = no gate, e.g. BiS tier)."""
        return SkillMechanics.FAMILIARIZATION_HOURS.get(skill, {}).get(new_tier, 0)

    @staticmethod
    def get_familiarization_remaining_seconds(
        end_iso: Optional[str], momentum_minutes: int = 0
    ) -> int:
        """Seconds remaining on the gate after applying banked momentum. 0 = gate lifted."""
        if not end_iso:
            return 0
        from datetime import datetime, timezone
        try:
            end = datetime.fromisoformat(end_iso)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            raw = max(0, int((end - datetime.now(timezone.utc)).total_seconds()))
            return max(0, raw - momentum_minutes * 60)
        except Exception:
            return 0

    @staticmethod
    def calculate_fishing_quality(focus_streak: int, approach: str) -> str:
        """Quality tier for a successful fishing reel."""
        if approach == "aggressive":
            if focus_streak >= 5:
                return "masterful"
            if focus_streak >= 3:
                return "great"
            if focus_streak >= 1:
                return "good"
        else:  # steady
            if focus_streak >= 7:
                return "masterful"
            if focus_streak >= 4:
                return "great"
            if focus_streak >= 2:
                return "good"
        return "none"

    @staticmethod
    def calculate_forestry_quality(rhythm_hits: int, total_swings: int) -> str:
        """Quality tier for a felled tree based on rhythm percentage."""
        if total_swings == 0:
            return "none"
        pct = rhythm_hits / total_swings
        if pct >= 0.90:
            return "masterful"
        if pct >= 0.70:
            return "great"
        if pct >= 0.50:
            return "good"
        return "none"

    @staticmethod
    def calculate_delve_quality(stability_remaining: int, depth_reached: int) -> str:
        """Quality tier for a delve extraction."""
        if depth_reached < 5:
            return "none"
        if stability_remaining >= 80 and depth_reached >= 20:
            return "masterful"
        if stability_remaining >= 55 and depth_reached >= 12:
            return "great"
        if stability_remaining >= 35 and depth_reached >= 6:
            return "good"
        return "none"

    @staticmethod
    def get_momentum_minutes(quality: str) -> int:
        """Momentum minutes earned for a given session quality tier."""
        return SkillMechanics.MOMENTUM_MINUTES.get(quality, 0)

    @staticmethod
    def apply_quality_to_yield(
        yield_dict: Dict[str, int], quality: str
    ) -> Dict[str, int]:
        """Apply quality yield multiplier; returns a new dict."""
        mult = SkillMechanics.QUALITY_YIELD_BONUS.get(quality, 1.0)
        if mult == 1.0:
            return dict(yield_dict)
        return {k: max(1, int(v * mult)) for k, v in yield_dict.items() if v > 0}

    @staticmethod
    def get_upgrade_cost(skill: str, current_tier: str, reduction: float = 0.0) -> dict | None:
        """Returns upgrade costs (dict with res_1..4 + gold) with optional reduction (0.0-0.12) from synergy 1pt nodes."""
        base_costs = {
            "mining": {
                "iron": (100, 0, 0, 0, 1000),
                "steel": (200, 100, 0, 0, 5000),
                "gold": (300, 200, 100, 0, 10000),
                "platinum": (600, 400, 200, 100, 100000),
            },
            "woodcutting": {
                "flimsy": (100, 0, 0, 0, 1000),
                "carved": (200, 100, 0, 0, 5000),
                "chopping": (300, 200, 100, 0, 10000),
                "magic": (600, 400, 200, 100, 100000),
            },
            "fishing": {
                "desiccated": (100, 0, 0, 0, 1000),
                "regular": (200, 100, 0, 0, 5000),
                "sturdy": (300, 200, 100, 0, 10000),
                "reinforced": (600, 400, 200, 100, 50000),
            },
        }
        costs = base_costs.get(skill, {}).get(current_tier)
        if not costs:
            return None
        red = max(0.0, min(0.5, float(reduction or 0.0)))
        factor = 1.0 - red
        return {
            "res_1": int(costs[0] * factor),
            "res_2": int(costs[1] * factor),
            "res_3": int(costs[2] * factor),
            "res_4": int(costs[3] * factor),
            "gold": int(costs[4] * factor),
        }
