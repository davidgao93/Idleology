import random

# ---------------------------------------------------------------------------
# Slot unlock costs (Primordial blood)
# ---------------------------------------------------------------------------

SLOT_UNLOCK_COSTS = {
    "head":      500,
    "torso":     500,
    "right_arm": 1_000,
    "left_arm":  1_000,
    "right_leg": 1_000,
    "left_leg":  1_000,
    "cheeks":    50_000,
    "organs":    50_000,
}

# ---------------------------------------------------------------------------
# Tier upgrade costs (Evolutionary blood) — index = target_tier - 2
# ---------------------------------------------------------------------------

UPGRADE_COSTS = {
    2: 200,
    3: 1_000,
    4: 2_000,
    5: 5_000,
}

MUTATIVE_COST = 1_000  # Mutative blood per attempt

# ---------------------------------------------------------------------------
# Transmutation ratio
# ---------------------------------------------------------------------------

TRANSMUTE_RATIO = 3  # 3 of source → 1 of target

# ---------------------------------------------------------------------------
# Main passive pool (15 passives)
# Placeholders — values will be replaced when passives are wired into combat.
# ---------------------------------------------------------------------------

PASSIVE_POOL: dict[str, dict] = {
    "vitality":     {"name": "Vitality",     "description": "Increases Max HP.",                    "stat": "max_hp"},
    "iron_skin":    {"name": "Iron Skin",    "description": "Increases Defence.",                   "stat": "defence"},
    "battle_fury":  {"name": "Battle Fury",  "description": "Increases Attack.",                    "stat": "attack"},
    "precision":    {"name": "Precision",    "description": "Increases Critical Hit Chance.",       "stat": "crit_chance"},
    "lethal_edge":  {"name": "Lethal Edge",  "description": "Increases Critical Hit Damage.",      "stat": "crit_damage"},
    "evasion":      {"name": "Evasion",      "description": "Reduces enemy Hit Chance.",            "stat": "evasion"},
    "ward_flow":    {"name": "Ward Flow",    "description": "Increases Ward generation.",           "stat": "ward"},
    "resilience":   {"name": "Resilience",   "description": "Increases Physical Damage Reduction.", "stat": "pdr"},
    "deflection":   {"name": "Deflection",   "description": "Increases Flat Damage Reduction.",    "stat": "fdr"},
    "hunters_eye":  {"name": "Hunter's Eye", "description": "Increases Hit Chance.",               "stat": "hit_chance"},
    "momentum":     {"name": "Momentum",     "description": "Grants bonus Attack on consecutive hits.", "stat": "momentum"},
    "fortitude":    {"name": "Fortitude",    "description": "Restores HP at the start of each round.", "stat": "regen"},
    "ferocity":     {"name": "Ferocity",     "description": "Grants flat bonus Attack.",            "stat": "flat_attack"},
    "rarity_sense": {"name": "Rarity Sense", "description": "Increases Item Rarity.",              "stat": "rarity"},
    "predator":     {"name": "Predator",     "description": "Increases damage dealt to bosses.",   "stat": "boss_damage"},
}

# ---------------------------------------------------------------------------
# Mutative passive pool (5 passives — only accessible via Mutative blood)
# ---------------------------------------------------------------------------

MUTATIVE_POOL: dict[str, dict] = {
    "blood_frenzy": {"name": "Blood Frenzy",   "description": "Increases Attack when below 50% HP.",           "stat": "low_hp_attack"},
    "void_touched":  {"name": "Void-Touched",   "description": "Chance to ignore incoming damage once per fight.", "stat": "damage_immunity"},
    "chimeric":      {"name": "Chimeric",        "description": "Grants a random stat bonus each combat round.", "stat": "chimeric"},
    "apex":          {"name": "Apex Predator",   "description": "Increases damage, scaling with consecutive kills.", "stat": "kill_scaling"},
    "undying":       {"name": "Undying",         "description": "Survive a lethal blow once per fight.",         "stat": "death_save"},
}

# ---------------------------------------------------------------------------
# Mutative outcome weights
# ---------------------------------------------------------------------------

_MUTATIVE_OUTCOMES = ["delete", "downgrade", "double", "new_passive"]
_MUTATIVE_WEIGHTS  = [50, 20, 15, 15]


class HematurgyMechanics:

    @staticmethod
    def roll_mutative_outcome() -> str:
        return random.choices(_MUTATIVE_OUTCOMES, weights=_MUTATIVE_WEIGHTS, k=1)[0]

    @staticmethod
    def get_random_main_passive(exclude: set[str]) -> str | None:
        """Returns a random passive_id from the main pool, excluding already-owned ones."""
        available = [pid for pid in PASSIVE_POOL if pid not in exclude]
        if not available:
            return None
        return random.choice(available)

    @staticmethod
    def get_random_mutative_passive(exclude: set[str]) -> str | None:
        """Returns a random passive_id from the mutative pool, excluding already-owned ones."""
        available = [pid for pid in MUTATIVE_POOL if pid not in exclude]
        if not available:
            return None
        return random.choice(available)

    @staticmethod
    def get_passive_def(passive_id: str) -> dict | None:
        return PASSIVE_POOL.get(passive_id) or MUTATIVE_POOL.get(passive_id)

    @staticmethod
    def passive_display_name(passive_id: str) -> str:
        defn = HematurgyMechanics.get_passive_def(passive_id)
        return defn["name"] if defn else passive_id

    @staticmethod
    def passive_description(passive_id: str) -> str:
        defn = HematurgyMechanics.get_passive_def(passive_id)
        return defn["description"] if defn else "Unknown passive."

    @staticmethod
    def upgrade_cost(target_tier: int) -> int:
        return UPGRADE_COSTS.get(target_tier, 0)

    @staticmethod
    def unlock_cost(slot_type: str) -> int:
        return SLOT_UNLOCK_COSTS.get(slot_type, 0)
