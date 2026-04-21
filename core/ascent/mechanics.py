BASE_LEVEL = 100
LEVEL_PER_FLOOR = 5
NORMAL_MOD_EVERY = 5
BOSS_MOD_EVERY = 10
STARTING_OFFSET = 5

# Pinnacle floor → stat bonuses granted as a one-time unlock.
# Keys: atk_pct, def_pct, crit, hit, pdr, fdr, hp
PINNACLE_REWARDS: dict[int, dict] = {
    25:  {"atk_pct": 5,  "def_pct": 5},
    50:  {"crit": 1, "hit": 1},
    75:  {"atk_pct": 5,  "def_pct": 5},
    100: {"hp": 50},
    125: {"crit": 1, "hit": 1},
    150: {"pdr": 1, "fdr": 10},
    175: {"atk_pct": 10, "def_pct": 10},
    200: {"hp": 50},
    225: {"crit": 1, "hit": 1},
    250: {"pdr": 1, "fdr": 10},
    275: {"atk_pct": 10, "def_pct": 10},
    300: {"hp": 50},
    350: {"hp": 50},
    400: {"hp": 50},
    500: {"crit": 1, "hit": 1},
    600: {"crit": 1, "hit": 1},
    666: {"atk_pct": 20, "def_pct": 20},
}


class AscentMechanics:

    @staticmethod
    def calculate_floor_monster_level(floor: int) -> int:
        return BASE_LEVEL + (floor - 1) * LEVEL_PER_FLOOR

    @staticmethod
    def get_floor_modifier_counts(floor: int) -> tuple[int, int]:
        """Returns (normal_mods, boss_mods) for the given floor."""
        return floor // NORMAL_MOD_EVERY, floor // BOSS_MOD_EVERY

    @staticmethod
    def calculate_starting_floor(best_floor: int) -> int:
        return max(1, best_floor - STARTING_OFFSET)

    @staticmethod
    def get_cumulative_pinnacle_bonuses(unlocked_floors: set) -> dict:
        """Sums all active pinnacle bonuses into one dict."""
        totals = {"atk_pct": 0, "def_pct": 0, "crit": 0, "hit": 0, "pdr": 0, "fdr": 0, "hp": 0}
        for floor in unlocked_floors:
            if floor in PINNACLE_REWARDS:
                for k, v in PINNACLE_REWARDS[floor].items():
                    totals[k] += v
        return totals

    @staticmethod
    def pinnacle_label(floor: int) -> str:
        """Human-readable description of the pinnacle reward for display."""
        reward = PINNACLE_REWARDS.get(floor, {})
        parts = []
        if reward.get("atk_pct"):
            parts.append(f"+{reward['atk_pct']}% ATK")
        if reward.get("def_pct"):
            parts.append(f"+{reward['def_pct']}% DEF")
        if reward.get("crit"):
            parts.append(f"+{reward['crit']} Crit Chance")
        if reward.get("hit"):
            parts.append(f"+{reward['hit']} Hit")
        if reward.get("pdr"):
            parts.append(f"+{reward['pdr']} PDR")
        if reward.get("fdr"):
            parts.append(f"+{reward['fdr']} FDR")
        if reward.get("hp"):
            parts.append(f"+{reward['hp']} Max HP")
        return " / ".join(parts)
