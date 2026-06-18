import math
import random
from typing import Optional


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

    @staticmethod
    def get_effective_upgrade_ratio(
        alchemy_level: int, has_master_baiter: bool = False
    ) -> int:
        """Master Baiter (permanent) gives one-step better upgrade ratios."""
        effective = alchemy_level + 1 if has_master_baiter else alchemy_level
        return AlchemyMechanics.get_upgrade_ratio(effective)

    @staticmethod
    def get_effective_downgrade_ratio(
        alchemy_level: int, has_master_baiter: bool = False
    ) -> int:
        """Master Baiter (permanent) gives one-step better downgrade ratios."""
        effective = alchemy_level + 1 if has_master_baiter else alchemy_level
        return AlchemyMechanics.get_downgrade_ratio(effective)

    # Legacy simple passives and the old quick-roll system have been fully removed.
    # All potion passives now come exclusively from the Distillation system.
    # Any pre-existing legacy passives in a player's DB will show by key (no mechanical effect).

    # ------------------------------------------------------------------
    # Transmutation resource definitions
    # ------------------------------------------------------------------

    # Ordered resource columns per skill (index 0 = tier 1, index 4 = tier 5)
    SKILL_TIERS: dict[str, list[str]] = {
        "mining": ["iron", "coal", "gold", "platinum", "idea"],
        "fishing": [
            "desiccated_bones",
            "regular_bones",
            "sturdy_bones",
            "reinforced_bones",
            "titanium_bones",
        ],
        "woodcutting": [
            "oak_logs",
            "willow_logs",
            "mahogany_logs",
            "magic_logs",
            "idea_logs",
        ],
    }

    # Human-readable tier names matching the same order
    SKILL_TIER_NAMES: dict[str, list[str]] = {
        "mining": ["Iron", "Coal", "Gold", "Platinum", "Idea Ore"],
        "fishing": ["Desd.", "Regular", "Sturdy", "Reinforced", "Titanium"],
        "woodcutting": ["Oak", "Willow", "Mahogany", "Magic", "Idea Logs"],
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
    def format_passive(
        passive_type: str, passive_value: float, passive_duration: float = 2.0
    ) -> str:
        """Returns a short human-readable description for a passive + value + duration.
        Checks powerful distilled passives first (new system).
        """
        pinfo = DistillationMechanics.POWERFUL_PASSIVES.get(passive_type)
        if pinfo:
            return pinfo["desc"].format(value=passive_value, duration=passive_duration)

        # Fallback for any remaining legacy passives in DB
        return f"{passive_type.replace('_', ' ').title()}: {passive_value}"

    # ------------------------------------------------------------------
    # Synthesis — Boss Key Disenchanting & Crafting
    # ------------------------------------------------------------------

    # DB column → human-readable name (also defines display order)
    KEY_DISPLAY_NAMES: dict[str, str] = {
        "dragon_key": "Dragon Key",
        "angel_key": "Angel Key",
        "soul_cores": "Soul Core",
        "void_frags": "Void Fragment",
        "balance_fragment": "Fragment of Balance",
    }

    KEY_EMOJIS: dict[str, str] = {
        "dragon_key": "🐉",
        "angel_key": "👼",
        "soul_cores": "💀",
        "void_frags": "🌀",
        "balance_fragment": "⚖️",
    }

    # Cosmic Dust granted when disenchanting one key of each type.
    DUST_YIELD: dict[str, int] = {
        "dragon_key": 80,
        "angel_key": 80,
        "soul_cores": 35,
        "void_frags": 55,
        "balance_fragment": 65,
    }

    # ------------------------------------------------------------------
    # Elemental Keys (uber drops) — disenchant only, stored in uber_progress
    # ------------------------------------------------------------------

    ELEMENTAL_DISPLAY_NAMES: dict[str, str] = {
        "capricious_carp": "Capricious Carp",
        "blessed_bismuth": "Blessed Bismuth",
        "sparkling_sprig": "Sparkling Sprig",
    }

    ELEMENTAL_EMOJIS: dict[str, str] = {
        "capricious_carp": "🐟",
        "blessed_bismuth": "💎",
        "sparkling_sprig": "🌿",
    }

    ELEMENTAL_DUST_YIELD: dict[str, int] = {
        "capricious_carp": 80,
        "blessed_bismuth": 80,
        "sparkling_sprig": 80,
    }

    # ------------------------------------------------------------------
    # Essences — disenchant only, stored in player_essences
    # Dust scales inversely with drop weight (common = 30, corrupted = 150)
    # ------------------------------------------------------------------

    ESSENCE_DISPLAY_NAMES: dict[str, str] = {
        "power": "Power Essence",
        "protection": "Protection Essence",
        "insight": "Insight Essence",
        "evasion": "Evasion Essence",
        "blocking": "Blocking Essence",
        "deftness": "Deftness Essence",
        "precision": "Precision Essence",
        "gluttony": "Gluttony Essence",
        "cleansing": "Cleansing Essence",
        "chaos": "Chaos Essence",
        "annulment": "Annulment Essence",
        "aphrodite": "Aphrodite Essence",
        "lucifer": "Lucifer Essence",
        "gemini": "Gemini Essence",
        "neet": "Neet Essence",
    }

    ESSENCE_EMOJIS: dict[str, str] = {
        "power": "🔴",
        "protection": "🔵",
        "insight": "🟣",
        "evasion": "🟢",
        "blocking": "🟡",
        "deftness": "🟠",
        "precision": "⚪",
        "gluttony": "🩷",
        "cleansing": "💧",
        "chaos": "🌪️",
        "annulment": "❌",
        "aphrodite": "💗",
        "lucifer": "🔥",
        "gemini": "♊",
        "neet": "🌙",
    }

    # Common → 30, Rare → 60, Utility → 90, Corrupted → 150
    ESSENCE_DUST_YIELD: dict[str, int] = {
        "power": 30,
        "protection": 30,
        "insight": 60,
        "evasion": 60,
        "blocking": 60,
        "deftness": 60,
        "precision": 60,
        "gluttony": 60,
        "cleansing": 90,
        "chaos": 90,
        "annulment": 90,
        "aphrodite": 150,
        "lucifer": 150,
        "gemini": 150,
        "neet": 150,
    }

    # Base Cosmic Dust cost to synthesize one key (before alchemy discount).
    # Each synthesis also costs SYNTHESIS_GOLD_COST gold.
    # All costs are well above the corresponding DUST_YIELD even at max discount,
    # preventing any profitable disenchant → re-synthesize loop.
    SYNTHESIS_DUST_BASE: dict[str, int] = {
        "dragon_key": 130,
        "angel_key": 130,
        "soul_cores": 60,
        "void_frags": 90,
        "balance_fragment": 105,
    }

    SYNTHESIS_GOLD_COST: int = 100_000

    @staticmethod
    def get_disenchant_queue_slots(level: int) -> int:
        """Number of concurrent disenchant queue slots available at *level*.
        Level 1 = 1 slot, Level 2 = 2 slots, Level 3+ = 3 slots."""
        if level >= 3:
            return 3
        if level >= 2:
            return 2
        return 1

    @staticmethod
    def get_disenchant_minutes(level: int) -> int:
        """
        Minutes required to disenchant a single key at the given alchemy level.
        L1 = 50 min, L2 = 40, L3 = 30, L4 = 20, L5 = 10.
        """
        return (6 - level) * 10

    @staticmethod
    def get_synthesis_dust_cost(level: int, item_type: str) -> int:
        """
        Dust cost to synthesize one key, reduced by 1 % per alchemy level (max 5 %).
        Uses math.ceil so the cost is always a whole number and never drops below
        the corresponding DUST_YIELD (guaranteed by the base values chosen).
        """
        base = AlchemyMechanics.SYNTHESIS_DUST_BASE[item_type]
        discount = level * 0.01  # 0.01 … 0.05
        return math.ceil(base * (1.0 - discount))

    # ------------------------------------------------------------------

    @staticmethod
    def format_passive_range(passive_type: str) -> str:
        """Returns a display name for the possible list (legacy removed)."""
        info = DistillationMechanics.POWERFUL_PASSIVES.get(passive_type)
        if info:
            return f"{info['emoji']} **{info['name']}** (powerful distilled)"
        return passive_type.replace("_", " ").title()


# =============================================================================
# POTION DISTILLATION (new multi-step Sage Elixir style system)
# =============================================================================
# 9-step choice-driven crafting using Cosmic Dust + random events.
# Each step the player picks a reagent (green/blue/red) that biases the outcome.
# Outcomes modify duration power, value power, or apply special event state
# (free steps, lucky/unlucky, guaranteed duration/value rolls, etc.).
# At the end we produce a powerful "distilled" passive (much stronger than the
# legacy simple list above).
#
# Legacy simple passives and the old roll system have been completely removed.
# All potion passives are now obtained exclusively via the Distillation system.
# =============================================================================


class DistillationMechanics:
    """Pure mechanics for the 9-step distillation mini-game.

    All methods are static and side-effect free except that they mutate the
    caller's session dict (convenient for the view layer). The caller is
    responsible for persisting the session via the repository.
    """

    STEPS = 9

    # ------------------------------------------------------------------
    # Reagents (the 3 choices per step). Colors are for UI flavor.
    # base_cost is the "normal" dust cost before event modifiers.
    # ------------------------------------------------------------------
    REAGENTS = [
        {
            "key": "green",
            "name": "Verdant Reagent",
            "emoji": "🟢",
            "color": "green",
            "desc": "Stable growth. Favors consistent value increases with lower variance.",
            "base_cost": 8,
            "bias": "value",  # hint for future weighting
        },
        {
            "key": "blue",
            "name": "Astral Reagent",
            "emoji": "🔵",
            "color": "blue",
            "desc": "Balanced essence. Good mix of duration and value potential.",
            "base_cost": 10,
            "bias": "balanced",
        },
        {
            "key": "red",
            "name": "Crimson Reagent",
            "emoji": "🔴",
            "color": "red",
            "desc": "Volatile power. Higher risk/reward — bigger swings and more dramatic events.",
            "base_cost": 12,
            "bias": "duration",
        },
    ]

    # ------------------------------------------------------------------
    # Passives
    # ------------------------------------------------------------------
    POWERFUL_PASSIVES: dict[str, dict] = {
        # Core encounter-changing (original 6, worded consistently)
        "panacea": {
            "name": "Panacea",
            "emoji": "🌿",
            "desc": "On potion use: {value:.0f}% chance to cleanse all ailments and grants {duration:.0f} turns of ailment immunity.",
            "value_min": 25.0,
            "value_max": 65.0,
            "duration_min": 1.0,
            "duration_max": 4.0,
            "category": "defensive",
        },
        "eclipse_strike": {
            "name": "Eclipse Strike",
            "emoji": "🌑",
            "desc": "On potion use: Your next attack deals {value:.0f}% increased damage and is guaranteed to crit (for {duration:.0f} attacks).",
            "value_min": 40.0,
            "value_max": 120.0,
            "duration_min": 1.0,
            "duration_max": 3.0,
            "category": "offensive",
        },
        "astral_aegis": {
            "name": "Astral Aegis",
            "emoji": "🛡️",
            "desc": "On potion use: Gain a shield equal to {value:.0f}% of max HP for {duration:.0f} turns. While shielded, you are immune to the next lethal blow.",
            "value_min": 30.0,
            "value_max": 80.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "defensive",
        },
        "void_tide": {
            "name": "Void Tide",
            "emoji": "🌊",
            "desc": "On potion use: Monster suffers {value:.0f}% reduced ATK and DEF for the next {duration:.0f} of its turns.",
            "value_min": 15.0,
            "value_max": 40.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "control",
        },
        "blood_pact": {
            "name": "Blood Pact",
            "emoji": "🩸",
            "desc": "On potion use: Your attacks leech {value:.0f}% of damage dealt as HP for the next {duration:.0f} hits.",
            "value_min": 20.0,
            "value_max": 50.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "offensive",
        },
        "quickening_draught": {
            "name": "Quickening Draught",
            "emoji": "⚡",
            "desc": "On potion use: Your next hit cannot miss, and you gain +{value:.0f}% hit chance for {duration:.0f} turns.",
            "value_min": 15.0,
            "value_max": 35.0,
            "duration_min": 2.0,
            "duration_max": 4.0,
            "category": "utility",
        },
        "potent_brew": {
            "name": "Potent Brew",
            "emoji": "🍺",
            "desc": "On potion use: The heal amount is increased by an additional {value:.0f}% of your max HP.",
            "value_min": 30.0,
            "value_max": 100.0,
            "duration_min": 0.0,
            "duration_max": 0.0,
            "category": "healing",
        },
        "venomous_infusion": {
            "name": "Venomous Infusion",
            "emoji": "🐍",
            "desc": "On potion use: The heal also deals {value:.0f}% of the healed amount as damage to the monster.",
            "value_min": 100.0,
            "value_max": 300.0,
            "duration_min": 0.0,
            "duration_max": 0.0,
            "category": "offensive",
        },
        "battle_draft": {
            "name": "Battle Draft",
            "emoji": "💪",
            "desc": "On potion use: Gain {value:.0f}% ATK for your next {duration:.0f} attacks this combat.",
            "value_min": 25.0,
            "value_max": 75.0,
            "duration_min": 1.0,
            "duration_max": 3.0,
            "category": "offensive",
        },
        "ironclad_elixir": {
            "name": "Ironclad Elixir",
            "emoji": "⚔️",
            "desc": "On potion use: Gain {value:.0f}% DEF for the next {duration:.0f} monster turns.",
            "value_min": 25.0,
            "value_max": 75.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "defensive",
        },
        "ward_surge": {
            "name": "Ward Surge",
            "emoji": "🔮",
            "desc": "On potion use: Restore Ward equal to {value:.0f}% of the heal amount.",
            "value_min": 50.0,
            "value_max": 150.0,
            "duration_min": 0.0,
            "duration_max": 0.0,
            "category": "defensive",
        },
        "overflow_elixir": {
            "name": "Overflow Elixir",
            "emoji": "💥",
            "desc": "On potion use: Overheal up to {value:.0f}% of max HP is stored as temporary HP (lost on hit).",
            "value_min": 40.0,
            "value_max": 120.0,
            "duration_min": 0.0,
            "duration_max": 0.0,
            "category": "defensive",
        },
        "numbing_tonic": {
            "name": "Numbing Tonic",
            "emoji": "🩹",
            "desc": "On potion use: Reduce damage from the monster's next attack by {value:.0f}%.",
            "value_min": 30.0,
            "value_max": 80.0,
            "duration_min": 1.0,
            "duration_max": 1.0,
            "category": "defensive",
        },
        "sustained_remedy": {
            "name": "Sustained Remedy",
            "emoji": "🌱",
            "desc": "On potion use: Restore {value:.0f} HP at the start of each of your next {duration:.0f} turns.",
            "value_min": 8.0,
            "value_max": 30.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "healing",
        },
    }

    # ------------------------------------------------------------------
    # Event / Property table (wide pool).
    # Sampled per reagent step with weights biased toward "middle" outcomes.
    # Rare/very-rare powerful properties have low weights.
    # Each property is shown to the player for the 3 choices and affects
    # how the background (nothing / duration inc/dec / power inc/dec) is resolved.
    # ------------------------------------------------------------------
    EVENTS = [
        # ==================== COMMON / MIDDLE (high weight 10-18) ====================
        {
            "id": "no_cost",
            "name": "Stabilized Flow",
            "desc": "This step costs **no Cosmic Dust**.",
            "weight": 15,
            "effect": {"cost_mult": 0.0},
        },
        {
            "id": "this_lucky",
            "name": "Perfect Alignment",
            "desc": "This step's result is **lucky**.",
            "weight": 16,
            "effect": {"this_lucky": True},
        },
        {
            "id": "guaranteed_duration",
            "name": "Time-Infused",
            "desc": "This step is **guaranteed to affect duration**.",
            "weight": 12,
            "effect": {"force": "duration"},
        },
        {
            "id": "guaranteed_value",
            "name": "Potency-Infused",
            "desc": "This step is **guaranteed to affect power**.",
            "weight": 12,
            "effect": {"force": "value"},
        },
        {
            "id": "small_boost",
            "name": "Gentle Bloom",
            "desc": "Guarantees at least a **good** tier gain this step.",
            "weight": 10,
            "effect": {"min_tier": "good"},
        },
        {
            "id": "free_next",
            "name": "Lingering Essence",
            "desc": "The **next step costs no dust**.",
            "weight": 13,
            "effect": {"free_next_steps": 1},
        },
        {
            "id": "half_cost",
            "name": "Efficient Mixture",
            "desc": "This step costs **half the usual dust**.",
            "weight": 11,
            "effect": {"cost_mult": 0.5},
        },
        {
            "id": "guaranteed_improvement",
            "name": "Fated Catalyst",
            "desc": "This step is **guaranteed to improve** either duration or power.",
            "weight": 10,
            "effect": {"guarantee_improvement": True},
        },
        # ==================== UNCOMMON (weight 5-9) ====================
        {
            "id": "double_lucky",
            "name": "Volatile Surge",
            "desc": "Dust cost is **doubled** this step, but the result is **slightly lucky**.",
            "weight": 7,
            "effect": {"cost_mult": 2.0, "lucky": True},
        },
        {
            "id": "free_next_two",
            "name": "Resonant Echo",
            "desc": "The **next 2 steps cost no dust**.",
            "weight": 6,
            "effect": {"free_next_steps": 2},
        },
        {
            "id": "refund_on_gain",
            "name": "Fortunate Residue",
            "desc": "If this step produces any gain, the dust spent is refunded.",
            "weight": 8,
            "effect": {"refund_on_gain": True},
        },
        {
            "id": "unlucky",
            "name": "Misaligned Reagents",
            "desc": "This step is **unlucky** (worse outcomes).",
            "weight": 6,
            "effect": {"unlucky": True},
        },
        {
            "id": "double_cost",
            "name": "Demanding Essence",
            "desc": "This step costs **double dust**.",
            "weight": 7,
            "effect": {"cost_mult": 2.0},
        },
        {
            "id": "cheaper_future",
            "name": "Economies of Scale",
            "desc": "All **future steps cost 25% less** dust.",
            "weight": 5,
            "effect": {"future_cost_mult": 0.75},
        },
        # ==================== RARE / POWERFUL (weight 2-5) ====================
        {
            "id": "very_lucky",
            "name": "Astral Convergence",
            "desc": "This step will be **very lucky**.",
            "weight": 4,
            "effect": {"very_lucky": True},
        },
        {
            "id": "safe_step",
            "name": "Warded Catalyst",
            "desc": "This step will **not decrease** the passive's duration or power.",
            "weight": 5,
            "effect": {"safe": True},
        },
        {
            "id": "free_next_three",
            "name": "Harmonic Cascade",
            "desc": "The **next 3 steps cost no dust**.",
            "weight": 3,
            "effect": {"free_next_steps": 3},
        },
        {
            "id": "big_swing",
            "name": "Chaotic Catalyst",
            "desc": "Bigger swings: higher chance of large gains *or* noticeable losses.",
            "weight": 3,
            "effect": {"big_swing": True},
        },
        {
            "id": "next_free_lucky",
            "name": "Serendipitous Flow",
            "desc": "The next step is **free and lucky**.",
            "weight": 4,
            "effect": {"free_next_steps": 1, "next_lucky": True},
        },
        # ==================== VERY RARE / VERY POWERFUL (weight 1-2) ====================
        {
            "id": "all_future_free",
            "name": "Eternal Flow",
            "desc": "**All future steps have no dust cost.**",
            "weight": 1,
            "effect": {"all_future_free": True},
        },
        {
            "id": "double_gain",
            "name": "Amplified Resonance",
            "desc": "Any gain this step is **doubled** in magnitude.",
            "weight": 2,
            "effect": {"double_gain": True},
        },
        {
            "id": "nothing",
            "name": "Dud Reagent",
            "desc": "This step produces **no improvement**.",
            "weight": 4,
            "effect": {"force_nothing": True},
        },
    ]

    # Tier names for display
    TIER_NAMES = {0: "nothing", 1: "a little", 2: "good", 3: "a lot"}

    @staticmethod
    def start_distillation(
        alchemy_level: int, excluded_passive_types: list | None = None
    ) -> dict:
        """Create a fresh distillation session state (step 0 = choosing base)."""
        return {
            "step": 0,
            "base_type": None,
            "duration_mod": 0.0,
            "value_mod": 0.0,
            "active_modifiers": {},
            "history": [],
            "dust_spent": 0,
            "alchemy_level": alchemy_level,
            "excluded_passive_types": excluded_passive_types or [],
        }

    @staticmethod
    def get_base_choices(excluded_types: set | None = None) -> list[dict]:
        """Sample 3 core passive choices, excluding any types the player already owns."""
        all_keys = list(DistillationMechanics.POWERFUL_PASSIVES.keys())
        if excluded_types:
            pool = [k for k in all_keys if k not in excluded_types]
        else:
            pool = all_keys
        # Ensure we always get 3 options; fall back to full pool if needed
        if len(pool) < 3:
            pool = all_keys
        chosen_keys = random.sample(pool, min(3, len(pool)))
        choices = []
        for key in chosen_keys:
            info = DistillationMechanics.POWERFUL_PASSIVES[key]
            choices.append(
                {
                    "key": key,
                    "name": info["name"],
                    "emoji": info["emoji"],
                    "desc": get_passive_list_desc(key),
                }
            )
        return choices

    @staticmethod
    def prepare_core_choices(session: dict) -> list[dict]:
        """Lock in the 3 core choices for this run (idempotent — re-uses if already stored)."""
        if session.get("core_choices"):
            return session["core_choices"]
        excluded = set(session.get("excluded_passive_types", []))
        choices = DistillationMechanics.get_base_choices(excluded_types=excluded)
        session["core_choices"] = choices
        return choices

    @staticmethod
    def get_prepared_core_choices(session: dict) -> list[dict]:
        """Return the previously prepared core choices (or prepare now as fallback)."""
        if session.get("core_choices"):
            return session["core_choices"]
        return DistillationMechanics.prepare_core_choices(session)

    @staticmethod
    def get_reagent_choices(session: dict, step: int) -> list[dict]:
        """Return the 3 reagent options for the given step (with current effective cost)."""
        base_cost = 6 + step * 2  # gentle ramp; events override
        options = []
        for r in DistillationMechanics.REAGENTS:
            cost = int(
                base_cost * r.get("base_cost", 10) / 10
            )  # use the per-reagent base as relative
            # Apply active modifiers (free steps, etc.)
            mult = 1.0
            if session.get("active_modifiers", {}).get("free_next_steps", 0) > 0:
                mult = 0.0
            if session.get("active_modifiers", {}).get("future_free_but_unlucky"):
                mult = 0.0
            effective_cost = max(0, int(cost * mult))
            options.append(
                {
                    **r,
                    "effective_cost": effective_cost,
                    "step": step,
                }
            )
        return options

    @staticmethod
    def get_reagent_options_for_step(session: dict, step: int) -> list[dict]:
        """Generate the 3 reagent options for this specific step, each with a pre-selected property/event from the pool.
        This allows showing the special properties in the UI before the user chooses.
        """
        reagents = DistillationMechanics.REAGENTS
        pool = DistillationMechanics.EVENTS
        # Sample 3 (distinct if possible) with weight bias toward middle outcomes
        if len(pool) >= 3:
            # weighted sample without replacement approx
            chosen_events = []
            temp = list(pool)
            for _ in range(3):
                if not temp:
                    break
                ws = [e.get("weight", 10) for e in temp]
                pick = random.choices(temp, weights=ws, k=1)[0]
                chosen_events.append(pick)
                temp.remove(pick)
        else:
            chosen_events = random.choices(
                pool, k=3, weights=[e.get("weight", 10) for e in pool]
            )
        random.shuffle(chosen_events)  # assign to the 3 reagents
        options = []
        base = 6 + step * 2
        for i, r in enumerate(reagents):
            event = chosen_events[i] if i < len(chosen_events) else random.choice(pool)
            eff = event.get("effect", {})
            cm = eff.get("cost_mult", 1.0)
            mult = 1.0
            mods = session.get("active_modifiers", {})
            if mods.get("free_next_steps", 0) > 0:
                mult = 0.0
            if mods.get("future_free_but_unlucky"):
                mult = 0.0
            if mods.get("all_future_free"):
                mult = 0.0
            if "future_cost_mult" in mods:
                cm *= mods["future_cost_mult"]
            rel = r.get("base_cost", 10) / 10.0
            eff_cost = max(0, int(base * rel * cm * mult))
            options.append(
                {
                    **r,
                    "effective_cost": eff_cost,
                    "event": event,
                    "property_desc": event.get("desc", "Standard step."),
                }
            )
        return options

    @staticmethod
    def prepare_reagent_options(session: dict, for_step: int) -> list[dict]:
        """Idempotent preparation of the 3 reagent properties for a specific step.
        The random draw (weighted, middle-biased) happens only once per step presentation
        and is stored in the session so embed, buttons, and the click callback all see
        the exact same properties + costs.
        """
        if session.get("_options_step") == for_step and session.get("reagent_options"):
            return session["reagent_options"]
        opts = DistillationMechanics.get_reagent_options_for_step(session, for_step)
        session["reagent_options"] = opts
        session["_options_step"] = for_step
        return opts

    @staticmethod
    def get_prepared_reagent_options(session: dict, step: int) -> list[dict]:
        """Return the previously prepared options for this step (or generate as fallback)."""
        if session.get("_options_step") == step and session.get("reagent_options"):
            return session["reagent_options"]
        return DistillationMechanics.get_reagent_options_for_step(session, step)

    @staticmethod
    def apply_step(
        session: dict, choice_idx: int, pre_chosen_event: dict = None
    ) -> dict:
        """
        Apply one reagent choice (the property shown for that colored reagent).
        Mutates session. The pre_chosen_event (from the UI) drives cost and the
        special resolution rules for the background outcome (nothing / inc/dec dur or power).
        """
        reagents = DistillationMechanics.REAGENTS
        if not (0 <= choice_idx < len(reagents)):
            choice_idx = 0
        reagent = reagents[choice_idx]

        step = session.get("step", 0) + 1
        session["step"] = step

        mods = session.setdefault("active_modifiers", {})

        # Prefer the property the player actually saw and clicked.
        event = pre_chosen_event
        if event is None:
            # Fallback (should not normally happen)
            event = DistillationMechanics._roll_event(reagent, mods)

        # --- Cost (use pre-chosen event's multipliers + current free state) ---
        base = 6 + (step - 1) * 2
        rel = reagent.get("base_cost", 10) / 10.0
        cm = 1.0
        eff = event.get("effect", {}) if event else {}
        if eff:
            cm = eff.get("cost_mult", 1.0)
        mult = 1.0
        if mods.get("free_next_steps", 0) > 0:
            mult = 0.0
        if mods.get("future_free_but_unlucky"):
            mult = 0.0
        if mods.get("all_future_free"):
            mult = 0.0
        if "future_cost_mult" in mods:
            cm *= mods["future_cost_mult"]
        final_cost = max(0, int(base * rel * cm * mult))
        session["dust_spent"] = session.get("dust_spent", 0) + final_cost

        # Consume free-step counters
        if mods.get("free_next_steps", 0) > 0:
            mods["free_next_steps"] -= 1
            if mods["free_next_steps"] <= 0:
                mods.pop("free_next_steps", None)

        # --- Background resolution (nothing / duration|value +inc or -dec), property-aware ---
        raw = DistillationMechanics._roll_raw_outcome(mods, event)
        resolved = DistillationMechanics._apply_property_resolution(
            raw, event, mods, session.get("alchemy_level", 1)
        )

        axis = resolved.get("axis")
        delta = resolved.get("delta", 0.0)
        tier_desc = resolved.get("tier_desc", "nothing")

        if axis == "duration":
            session["duration_mod"] = session.get("duration_mod", 0.0) + delta
        elif axis == "value":
            session["value_mod"] = session.get("value_mod", 0.0) + delta

        # Record history (support negative)
        gain_label = tier_desc
        if axis and delta != 0:
            sign = "+" if delta > 0 else ""
            gain_label = f"{sign}{abs(delta):.1f} {axis}"
        history_entry = {
            "step": step,
            "reagent": reagent["key"],
            "event_id": event["id"] if event else None,
            "event_name": event["name"] if event else "Normal",
            "gain": gain_label if axis else "nothing",
        }
        session.setdefault("history", []).append(history_entry)

        # Apply lingering side-effects from the chosen property
        if event:
            eff = event.get("effect", {})
            if eff.get("lucky") or eff.get("this_lucky"):
                # one-shot; the resolution already used it
                pass
            if "free_next_steps" in eff:
                mods["free_next_steps"] = max(
                    mods.get("free_next_steps", 0), eff["free_next_steps"]
                )
            if eff.get("future_free_but_unlucky"):
                mods["future_free_but_unlucky"] = True
            if eff.get("all_future_free"):
                mods["all_future_free"] = True
            if "future_cost_mult" in eff:
                mods["future_cost_mult"] = eff["future_cost_mult"]
            if eff.get("next_lucky"):
                mods["lucky"] = True  # will be consumed on the *next* step

        # one-shot cleanup
        mods.pop("lucky", None)

        # Result for UI
        # Note: We intentionally do *not* re-emit the full property description here
        # (e.g. "Fated Catalyst: This step is guaranteed..."). That was already shown
        # to the player in the "Reagent Properties (this step)" section before they chose.
        # Re-stating it makes it feel like "two things" are being applied.
        # The effect of the property is reflected in the cost charged and the roll outcome.
        result = {
            "step": step,
            "reagent": reagent["key"],
            "cost": final_cost,
            "event": event,
            "gain_type": axis or "none",
            "gain_amount": delta,
            "messages": [
                f"Used **{reagent['emoji']} {reagent['name']}** (-✨ {final_cost} Cosmic Dust)",
            ],
        }
        if axis:
            sign = "+" if delta > 0 else ""
            result["messages"].append(f"**{sign}{abs(delta):.1f}** {axis} power.")
        else:
            result["messages"].append("No change this step.")

        # Optional refund side-effect (after the fact)
        if event and event.get("effect", {}).get("refund_on_gain") and delta > 0:
            session["dust_spent"] = max(0, session.get("dust_spent", 0) - final_cost)
            result["messages"].append("Dust spent on this step was refunded!")
            result["cost"] = 0  # so the view doesn't double-deduct

        return result

    @staticmethod
    def _roll_event(reagent: dict, current_mods: dict) -> Optional[dict]:
        """Pick a weighted event, biased by reagent and current state."""
        events = DistillationMechanics.EVENTS
        weights = []
        for e in events:
            w = e["weight"]
            # Simple bias: red likes dramatic events, green likes safe/positive
            if reagent["key"] == "red" and e["id"] in (
                "double_lucky",
                "future_unlucky_free",
                "guaranteed_duration",
            ):
                w *= 1.6
            if reagent["key"] == "green" and e["id"] in (
                "no_cost",
                "small_boost",
                "this_lucky",
            ):
                w *= 1.4
            if current_mods.get("future_free_but_unlucky") and e["id"] in (
                "no_cost",
                "free_next",
            ):
                w *= 0.3  # less likely to get more free when already in the bargain
            weights.append(w)

        # Normalize and pick
        total = sum(weights)
        r = random.uniform(0, total)
        upto = 0
        for i, w in enumerate(weights):
            upto += w
            if r <= upto:
                return events[i]
        return events[-1]

    # ------------------------------------------------------------------
    # New background outcome + property-driven resolution (per latest spec)
    # ------------------------------------------------------------------

    @staticmethod
    def _roll_raw_outcome(mods: dict, event: Optional[dict]) -> dict:
        """Roll the base background event for the step: nothing, or +/- on duration or value.
        Middle outcomes (small gains, occasional nothing) are favored.
        Decreases exist for variance and are modulated by the chosen property.
        """
        eff = (event or {}).get("effect", {})

        # Forced nothing from property
        if eff.get("force_nothing"):
            return {"axis": None, "sign": 0, "tier": 0, "raw_delta": 0.0}

        # Forced axis
        forced_axis = eff.get("force")  # "duration" or "value"

        # Base category probabilities (nothing / inc / dec). Middle bias.
        # nothing 22%, small-positive 30%, medium-pos 18%, big-pos 8%,
        # small-neg 12%, med-neg 7%, big-neg 3%  (tuned for "middle" feel)
        cat = random.choices(
            [
                "nothing",
                "inc_small",
                "inc_good",
                "inc_big",
                "dec_small",
                "dec_med",
                "dec_big",
            ],
            weights=[22, 30, 18, 8, 12, 7, 3],
        )[0]

        if cat == "nothing":
            return {"axis": None, "sign": 0, "tier": 0, "raw_delta": 0.0}

        sign = 1 if cat.startswith("inc") else -1
        size = cat.split("_")[1]  # small/good/big or med

        # Pick axis (forced wins; otherwise 50/50 with slight value lean for "power" fantasy)
        if forced_axis in ("duration", "value"):
            axis = forced_axis
        else:
            axis = "duration" if random.random() < 0.48 else "value"

        # Magnitude (positive number; sign applied by caller)
        level = 1  # magnitude base is mild; alchemy_level scaling happens in _delta_for
        if size == "small":
            tier = 1
        elif size == "good" or size == "med":
            tier = 2
        else:
            tier = 3

        mag = DistillationMechanics._delta_for(tier, axis, level)
        return {"axis": axis, "sign": sign, "tier": tier, "raw_delta": mag * sign}

    @staticmethod
    def _delta_for(tier: int, axis: str, alchemy_level: int) -> float:
        """Positive magnitude for a tier (little/good/a lot)."""
        if tier <= 0:
            return 0.0
        base = 0.9 + (alchemy_level - 1) * 0.12
        if axis == "duration":
            base *= 0.95
        mult = {1: 1.0, 2: 2.15, 3: 3.9}[tier]
        return round(base * mult, 1)

    @staticmethod
    def _apply_property_resolution(
        raw: dict, event: Optional[dict], mods: dict, alchemy_level: int
    ) -> dict:
        """Take the raw background outcome and apply the rules from the chosen reagent property.
        Implements exactly the requested double-roll / re-roll / take-better (higher for gains,
        smaller loss for decreases) behavior for lucky / very_lucky / safe / force / do-nothing cases.
        """
        eff = (event or {}).get("effect", {})
        axis = raw.get("axis")
        sign = raw.get("sign", 0)
        tier = raw.get("tier", 0)
        delta = raw.get("raw_delta", 0.0)

        # 1) Hard force_nothing from property
        if eff.get("force_nothing"):
            return {"axis": None, "sign": 0, "delta": 0.0, "tier_desc": "nothing"}

        # 2) Guarantee improvement (turn a nothing into at least little of something)
        if eff.get("guarantee_improvement") and (axis is None or sign <= 0):
            # pick a random axis and give a small positive
            axis = "duration" if random.random() < 0.5 else "value"
            sign = 1
            tier = 1
            delta = DistillationMechanics._delta_for(1, axis, alchemy_level)

        # 3) Force axis (the "will always affect power/duration" case)
        if eff.get("force") in ("duration", "value") and axis is not None:
            axis = eff["force"]

        # 4) Safe step: never produce a decrease (or nothing if it would have been bad)
        if eff.get("safe"):
            if sign < 0 or axis is None:
                # turn it into a small positive on a random (or forced) axis
                axis = eff.get("force") or (
                    "duration" if random.random() < 0.5 else "value"
                )
                sign = 1
                tier = 1
                delta = DistillationMechanics._delta_for(1, axis, alchemy_level)

        # 5) Core lucky / very_lucky resolution (the heart of the spec)
        is_very = bool(eff.get("very_lucky"))
        is_slight = bool(eff.get("lucky")) or bool(eff.get("this_lucky"))

        if is_very or is_slight:
            # First, what did the raw roll give us?
            was_good = axis is not None and sign > 0
            was_bad = axis is None or sign < 0

            if is_very and was_bad:
                # Very lucky: re-roll once hoping for a better (increase) outcome
                roll2 = DistillationMechanics._roll_raw_outcome(mods, event)
                if roll2.get("sign", 0) > 0:
                    # great — we fished an increase
                    axis = roll2["axis"]
                    sign = 1
                    tier = roll2["tier"]
                    delta = (
                        roll2["raw_delta"]
                        if roll2["raw_delta"] > 0
                        else DistillationMechanics._delta_for(tier, axis, alchemy_level)
                    )
                    was_good = True
                    was_bad = False
                else:
                    # still bad — pick random between the two bad outcomes
                    candidates = [raw, roll2]
                    chosen = random.choice(candidates)
                    axis = chosen.get("axis")
                    sign = chosen.get("sign", 0)
                    tier = chosen.get("tier", 0)
                    # if still a decrease, double-roll the decrease and take the *better* (smaller loss)
                    if axis and sign < 0:
                        d1 = DistillationMechanics._delta_for(
                            max(1, tier), axis, alchemy_level
                        )
                        d2 = DistillationMechanics._delta_for(
                            max(1, tier), axis, alchemy_level
                        )
                        best_loss = min(
                            d1, d2
                        )  # smaller number = less bad for the player
                        delta = -best_loss
                    else:
                        delta = chosen.get("raw_delta", 0.0)
            elif (is_very or is_slight) and was_good:
                # Good outcome (increase) under any lucky flag → double-roll and take the higher value
                d1 = DistillationMechanics._delta_for(max(1, tier), axis, alchemy_level)
                d2 = DistillationMechanics._delta_for(max(1, tier), axis, alchemy_level)
                best = max(d1, d2)
                delta = best if sign > 0 else -best
            # (if very_lucky and first was good we already doubled above; very_lucky only does the re-roll on bad)

        # 6) Double-gain property (after any lucky resolution)
        if eff.get("double_gain") and axis and sign > 0 and delta > 0:
            delta *= 2.0

        # 7) Big swing just widens variance on the raw (already somewhat accounted in _roll_raw_outcome weights)

        # Final tier description for UI/history
        if axis is None or delta == 0:
            tier_desc = "nothing"
        elif abs(delta) < 1.6:
            tier_desc = "a little"
        elif abs(delta) < 3.5:
            tier_desc = "good"
        else:
            tier_desc = "a lot"

        return {
            "axis": axis,
            "sign": sign,
            "delta": round(delta, 1) if delta else 0.0,
            "tier_desc": tier_desc,
        }

    @staticmethod
    def finalize(session: dict) -> tuple[str, float, float]:
        """
        Turn the accumulated session into a concrete powerful passive.
        Returns (passive_type, final_value, final_duration) for now.
        In a richer version this could return a full dataclass.
        """
        base = session.get("base_type") or "panacea"
        info = DistillationMechanics.POWERFUL_PASSIVES.get(
            base, list(DistillationMechanics.POWERFUL_PASSIVES.values())[0]
        )

        # Combine the two accumulators into the two axes the passive cares about
        dur = max(1.0, 1.0 + session.get("duration_mod", 0.0))
        val = max(5.0, 5.0 + session.get("value_mod", 0.0))

        # Clamp to reasonable final ranges (prevents insane stacking on restarts)
        val = min(val, info.get("value_max", 150) * 1.3)
        dur = min(dur, info.get("duration_max", 6) * 1.3)

        return base, round(val, 1), round(dur, 1)

    @staticmethod
    def format_distilled_passive(
        passive_type: str, value: float, duration: float
    ) -> str:
        info = DistillationMechanics.POWERFUL_PASSIVES.get(passive_type)
        if not info:
            return f"{passive_type} (value {value}, duration {duration})"
        return info["desc"].format(value=value, duration=duration)


# ------------------------------------------------------------------
# Unified passive info helpers (for UI display across old + new system)
# ------------------------------------------------------------------


def get_passive_info(passive_type: str) -> dict:
    """Return the info dict for a passive_type, checking powerful distilled first.
    Safe fallback for any remaining legacy passives in DB (the old PASSIVES dict
    and legacy system have been fully removed).
    """
    info = DistillationMechanics.POWERFUL_PASSIVES.get(passive_type)
    if info:
        return info
    # Safe fallback: show a reasonable name for old data
    return {"name": passive_type.replace("_", " ").title(), "emoji": "⚗️"}


def get_passive_name_emoji(passive_type: str) -> tuple[str, str]:
    """Convenience to get (name, emoji) falling back gracefully."""
    info = get_passive_info(passive_type)
    name = info.get("name", passive_type)
    emoji = info.get("emoji", "⚗️")
    return name, emoji


def get_passive_list_desc(passive_type: str) -> str:
    """Return a nicely worded description for the 'possible passives' list, with ranges instead of {value} placeholders.
    Uses the style from passive_data.py (On potion use:, etc.).
    """
    info = get_passive_info(passive_type)
    if not info:
        return passive_type

    desc = info.get("desc", passive_type)

    # Substitute ranges for value and duration
    if "value_min" in info and "{value" in desc:
        vmin = info.get("value_min", 0)
        vmax = info.get("value_max", vmin)
        if isinstance(vmin, float) and vmin % 1 != 0:
            val_range = f"{vmin:.0f}-{vmax:.0f}"
        else:
            val_range = f"{int(vmin)}-{int(vmax)}"
        desc = desc.replace("{value:.0f}", val_range).replace("{value}", val_range)

    if "duration_min" in info and "{duration" in desc:
        dmin = info.get("duration_min", 0)
        dmax = info.get("duration_max", dmin)
        dur_range = f"{int(dmin)}-{int(dmax)}"
        desc = desc.replace("{duration:.0f}", dur_range).replace(
            "{duration}", dur_range
        )

    # The desc templates now start with "On potion use:" (or similar) per passive_data.py style.
    # No need to force prefix if already present.
    if not desc.lower().startswith(("on potion", "combat start", "during combat")):
        desc = "On potion use: " + desc

    return desc
