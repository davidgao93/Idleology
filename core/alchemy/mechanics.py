import math
import random
from typing import Optional

from core.emojis import (
    ALCHEMY_ACCEL,
    ALCHEMY_AEGIS,
    ALCHEMY_BARRIER,
    ALCHEMY_ECLIPSE,
    ALCHEMY_ENFEEBLE,
    ALCHEMY_ENRAGE,
    ALCHEMY_PAINKILLER,
    ALCHEMY_PANACEA,
    ALCHEMY_QUENCH,
    ALCHEMY_TITHE,
    ALCHEMY_VIPER,
    ANGEL_KEY,
    BLESSED_BISMUTH,
    CAPRICIOUS_CARP,
    COSMIC_DUST,
    DRAGON_KEY,
    INFERNAL_ENGRAM,
    SOUL_CORE,
    SPARKLING_SPRIG,
    VOID_FRAG,
)


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
        "mining": ["iron_ore", "coal_ore", "gold_ore", "platinum_ore", "idea_ore"],
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
    TRANSMUTE_UPGRADE_GOLD: dict[int, int] = {1: 200, 2: 800, 3: 2_500, 4: 7_500}

    # Gold cost per downgrade transmutation, keyed by source tier index (1=T2 … 4=T5)
    TRANSMUTE_DOWNGRADE_GOLD: dict[int, int] = {1: 50, 2: 200, 3: 600, 4: 2_000}

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
            result = pinfo["desc"].format(
                value=passive_value, duration=passive_duration
            )
            return result.removeprefix("On potion use: ")

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
        "dragon_key": DRAGON_KEY,
        "angel_key": ANGEL_KEY,
        "soul_cores": SOUL_CORE,
        "void_frags": VOID_FRAG,
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
        "capricious_carp": CAPRICIOUS_CARP,
        "blessed_bismuth": BLESSED_BISMUTH,
        "sparkling_sprig": SPARKLING_SPRIG,
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
        "lucifer": INFERNAL_ENGRAM,
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
            "name": "Verdant",
            "emoji": "🟢",
            "color": "green",
            "desc": "Stable growth. Favors consistent value increases with lower variance.",
            "base_cost": 8,
            "bias": "value",  # hint for future weighting
        },
        {
            "key": "blue",
            "name": "Astral",
            "emoji": "🔵",
            "color": "blue",
            "desc": "Balanced essence. Good mix of duration and value potential.",
            "base_cost": 10,
            "bias": "balanced",
        },
        {
            "key": "red",
            "name": "Crimson",
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
        "panacea": {
            "name": "Panacea",
            "emoji": ALCHEMY_PANACEA,
            "desc": "On potion use: {value:.0f}% chance to cleanse all ailments and grant {duration:.0f} turns of ailment immunity.",
            "value_min": 20.0,
            "value_max": 100.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "defensive",
        },
        "eclipse": {
            "name": "Eclipse",
            "emoji": ALCHEMY_ECLIPSE,
            "desc": "On potion use: Your next {duration:.0f} attacks deal {value:.0f}% increased damage and are guaranteed crits.",
            "value_min": 40.0,
            "value_max": 100.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "offensive",
        },
        "aegis": {
            "name": "Aegis",
            "emoji": ALCHEMY_AEGIS,
            "desc": "On potion use: Gain a shield equal to {value:.0f}% of max HP for {duration:.0f} turns.",
            "value_min": 30.0,
            "value_max": 80.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "defensive",
        },
        "enfeeble": {
            "name": "Enfeeble",
            "emoji": ALCHEMY_ENFEEBLE,
            "desc": "On potion use: Monster suffers {value:.0f}% reduced ATK and DEF for the next {duration:.0f} of its turns.",
            "value_min": 15.0,
            "value_max": 40.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "control",
        },
        "blood_tithe": {
            "name": "Blood Tithe",
            "emoji": ALCHEMY_TITHE,
            "desc": "On potion use: Your attacks leech {value:.0f}% of damage dealt as HP for the next {duration:.0f} hits.",
            "value_min": 2.0,
            "value_max": 5.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "offensive",
        },
        "accel": {
            "name": "Accel",
            "emoji": ALCHEMY_ACCEL,
            "desc": "On potion use: Gain +{value:.0f}% hit chance for {duration:.0f} turns.",
            "value_min": 15.0,
            "value_max": 35.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "utility",
        },
        "quench": {
            "name": "Quench",
            "emoji": ALCHEMY_QUENCH,
            "desc": "On potion use: Heal an additional {value:.0f}% of max HP, then restore 5% max HP at the start of each of your next {duration:.0f} turns.",
            "value_min": 20.0,
            "value_max": 50.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "healing",
        },
        "viper": {
            "name": "Viper",
            "emoji": ALCHEMY_VIPER,
            "desc": "On potion use: Deal {value:.0f}% of the heal amount as instant damage, then deal a DoT based on that hit per turn as venom for {duration:.0f} turns.",
            "value_min": 100.0,
            "value_max": 500.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "offensive",
        },
        "enrage": {
            "name": "Enrage",
            "emoji": ALCHEMY_ENRAGE,
            "desc": "On potion use: Gain {value:.0f}% ATK and DEF for the next {duration:.0f} monster turns.",
            "value_min": 25.0,
            "value_max": 75.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "offensive",
        },
        "barrier": {
            "name": "Barrier",
            "emoji": ALCHEMY_BARRIER,
            "desc": "On potion use: Add Ward equal to {value:.0f}% of the heal amount at the start of each of your next {duration:.0f} turns.",
            "value_min": 50.0,
            "value_max": 150.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "defensive",
        },
        "painkiller": {
            "name": "Painkiller",
            "emoji": ALCHEMY_PAINKILLER,
            "desc": "On potion use: Reduce damage from the monster's next {duration:.0f} hits by {value:.0f}%.",
            "value_min": 30.0,
            "value_max": 80.0,
            "duration_min": 2.0,
            "duration_max": 5.0,
            "category": "defensive",
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
            "weight": 4,
            "effect": {"this_lucky": True},
        },
        {
            "id": "guaranteed_duration",
            "name": "Time-Infused",
            "desc": "This step is **guaranteed to affect duration** — for better or worse, but never nothing.",
            "weight": 15,
            "effect": {"force": "duration"},
        },
        {
            "id": "guaranteed_value",
            "name": "Potency-Infused",
            "desc": "This step is **guaranteed to affect power** — for better or worse, but never nothing.",
            "weight": 15,
            "effect": {"force": "value"},
        },
        {
            "id": "small_boost",
            "name": "Gentle Bloom",
            "desc": "Guarantees at least a **good** tier gain this step.",
            "weight": 5,
            "effect": {"min_tier": "good"},
        },
        {
            "id": "free_next",
            "name": "Lingering Essence",
            "desc": "The **next step costs no dust**.",
            "weight": 18,
            "effect": {"free_next_steps": 1},
        },
        {
            "id": "half_cost",
            "name": "Efficient Mixture",
            "desc": "This step costs **half the usual dust**.",
            "weight": 15,
            "effect": {"cost_mult": 0.5},
        },
        {
            "id": "guaranteed_improvement",
            "name": "Fated Catalyst",
            "desc": "This step is **guaranteed to improve** either duration or power.",
            "weight": 8,
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
            "weight": 1,
            "effect": {"very_lucky": True},
        },
        {
            "id": "safe_step",
            "name": "Warded Catalyst",
            "desc": "This step will **not decrease** the passive's duration or power.",
            "weight": 2,
            "effect": {"safe": True},
        },
        {
            "id": "free_next_three",
            "name": "Harmonic Cascade",
            "desc": "The **next 3 steps cost no dust**.",
            "weight": 2,
            "effect": {"free_next_steps": 3},
        },
        {
            "id": "big_swing",
            "name": "Chaotic Catalyst",
            "desc": "Bigger swings: higher chance of large gains *or* noticeable losses.",
            "weight": 5,
            "effect": {"big_swing": True},
        },
        {
            "id": "next_free_lucky",
            "name": "Serendipitous Flow",
            "desc": "The next step is **free and lucky**.",
            "weight": 2,
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

        # Pending lucky from previous step's next_lucky effect
        pending_lucky = mods.pop("lucky", False)

        level = session.get("alchemy_level", 1)

        # Determine luck level from event + pending state
        is_very = bool(eff.get("very_lucky"))
        is_lucky = bool(eff.get("lucky")) or pending_lucky
        is_slight = bool(eff.get("this_lucky"))
        if is_very:
            n_out, n_mag = 3, 3
        elif is_lucky:
            n_out, n_mag = 2, 2
        elif is_slight:
            n_out, n_mag = 2, 1
        else:
            n_out, n_mag = 1, 1

        # --- Roll both axes independently ---
        if eff.get("force_nothing"):
            val_out = {"sign": 0, "tier": 0, "delta": 0.0}
            dur_out = {"sign": 0, "tier": 0, "delta": 0.0}
        elif eff.get("big_swing"):
            # Big swing: roll each axis twice, take higher absolute magnitude
            val_rolls = [DistillationMechanics._roll_one_axis(level) for _ in range(2)]
            dur_rolls = [DistillationMechanics._roll_one_axis(level) for _ in range(2)]
            val_out = max(val_rolls, key=lambda o: abs(o["delta"]))
            dur_out = max(dur_rolls, key=lambda o: abs(o["delta"]))
        else:
            val_out = DistillationMechanics._roll_axis_with_luck(level, n_out, n_mag)
            dur_out = DistillationMechanics._roll_axis_with_luck(level, n_out, n_mag)

        # Apply force: guarantee the specified axis is non-nothing (can be +/-)
        forced = eff.get("force")
        if forced == "value":
            val_out = DistillationMechanics._guarantee_non_nothing(val_out, level)
        elif forced == "duration":
            dur_out = DistillationMechanics._guarantee_non_nothing(dur_out, level)

        # Save raw roll for debug before effects are applied
        val_raw_pre = dict(val_out)
        dur_raw_pre = dict(dur_out)

        # Apply per-axis property effects (safe, guarantee_improvement, min_tier, unlucky, double_gain)
        val_out = DistillationMechanics._apply_axis_effects(val_out, eff, level)
        dur_out = DistillationMechanics._apply_axis_effects(dur_out, eff, level)

        val_delta = val_out["delta"]
        dur_delta = dur_out["delta"]

        # Cap accumulators at 0 — negative steps can never bank debt that offsets future gains
        val_before = max(0.0, session.get("value_mod", 0.0))
        dur_before = max(0.0, session.get("duration_mod", 0.0))
        val_new = max(0.0, round(val_before + val_delta, 3))
        dur_new = max(0.0, round(dur_before + dur_delta, 3))
        # Effective deltas after capping (what actually changed)
        actual_val_delta = val_new - val_before
        actual_dur_delta = dur_new - dur_before
        session["value_mod"] = val_new
        session["duration_mod"] = dur_new

        # Format changes as percentages of raw_max using actual (capped) deltas
        raw_max = DistillationMechanics.get_raw_max(session)

        def _fmt_pct(d: float, label: str) -> str | None:
            if d == 0.0 or raw_max == 0:
                return None
            pct = round(d / raw_max * 100)
            return f"{pct:+d}% {label}" if pct != 0 else None

        val_str = _fmt_pct(actual_val_delta, "power")
        dur_str = _fmt_pct(actual_dur_delta, "duration")
        parts = [p for p in [val_str, dur_str] if p]
        gain_label = ", ".join(parts) if parts else "nothing"

        # History entry
        history_entry = {
            "step": step,
            "reagent": reagent["key"],
            "reagent_label": f"{reagent['emoji']} {reagent['name']}",
            "event_id": event["id"] if event else None,
            "event_name": event["name"] if event else "Normal",
            "gain": gain_label,
        }
        session.setdefault("history", []).append(history_entry)

        # Apply lingering side-effects
        if "free_next_steps" in eff:
            mods["free_next_steps"] = max(
                mods.get("free_next_steps", 0), eff["free_next_steps"]
            )
        if eff.get("all_future_free"):
            mods["all_future_free"] = True
        if "future_cost_mult" in eff:
            mods["future_cost_mult"] = eff["future_cost_mult"]
        if eff.get("next_lucky"):
            mods["lucky"] = True

        # Build a diagnostic string captured in session state for debugging distillation rolls.
        def _sign(s):
            return "+" if s > 0 else ("-" if s < 0 else "0")

        debug_str = (
            f"event={event['id'] if event else 'None'}\n"
            f"eff={eff}\n"
            f"luck: very={is_very} lucky={is_lucky} slight={is_slight} pending={pending_lucky}\n"
            f"val  raw({_sign(val_raw_pre['sign'])}T{val_raw_pre['tier']} "
            f"Δ{val_raw_pre['delta']:+.2f})→after({_sign(val_out['sign'])}T{val_out['tier']} "
            f"Δ{val_out['delta']:+.2f}) actual={actual_val_delta:+.3f}\n"
            f"dur  raw({_sign(dur_raw_pre['sign'])}T{dur_raw_pre['tier']} "
            f"Δ{dur_raw_pre['delta']:+.2f})→after({_sign(dur_out['sign'])}T{dur_out['tier']} "
            f"Δ{dur_out['delta']:+.2f}) actual={actual_dur_delta:+.3f}\n"
            f"mods_after={dict(mods)}"
        )

        # Build result for UI
        result = {
            "step": step,
            "reagent": reagent["key"],
            "cost": final_cost,
            "event": event,
            "debug": debug_str,
            "messages": [
                f"Used **{reagent['emoji']} {reagent['name']}** (-{COSMIC_DUST} {final_cost} Cosmic Dust)",
            ],
        }
        if parts:
            result["messages"].append(", ".join(f"**{p}**" for p in parts) + ".")
        else:
            result["messages"].append("No change this step.")

        # Refund side-effect
        any_gain = val_delta > 0 or dur_delta > 0
        if event and eff.get("refund_on_gain") and any_gain:
            session["dust_spent"] = max(0, session.get("dust_spent", 0) - final_cost)
            result["messages"].append("Dust spent on this step was refunded!")
            result["cost"] = 0

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
    def _roll_one_axis(level: int) -> dict:
        """Roll an outcome for a single axis (no axis choice). Returns {sign, tier, delta}."""
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
            weights=[
                35,
                22,
                13,
                5,
                14,
                8,
                3,
            ],  # 35% nothing, 40% positive, 25% negative
        )[0]
        if cat == "nothing":
            return {"sign": 0, "tier": 0, "delta": 0.0}
        sign = 1 if cat.startswith("inc") else -1
        size = cat.split("_")[1]
        tier = {"small": 1, "good": 2, "med": 2, "big": 3}[size]
        mag = DistillationMechanics._delta_for(tier, "value", level)
        return {"sign": sign, "tier": tier, "delta": mag * sign}

    @staticmethod
    def _better_axis_outcome(a: dict, b: dict) -> dict:
        """Return whichever single-axis outcome is better for the player."""
        sa, sb = a["sign"], b["sign"]
        if sa != sb:
            return a if sa > sb else b  # positive > nothing > negative
        if sa > 0:
            return a if a["tier"] >= b["tier"] else b  # higher tier for positive
        if sa < 0:
            return (
                a if a["tier"] <= b["tier"] else b
            )  # lower tier (less loss) for negative
        return a  # both nothing

    @staticmethod
    def _roll_axis_with_luck(level: int, n_outcome: int, n_mag: int) -> dict:
        """Roll a single-axis outcome applying luck (n_outcome outcome rolls, n_mag magnitude rolls)."""
        outcomes = [
            DistillationMechanics._roll_one_axis(level) for _ in range(n_outcome)
        ]
        best = outcomes[0]
        for o in outcomes[1:]:
            best = DistillationMechanics._better_axis_outcome(best, o)
        # If lucky, also try additional magnitude rolls in the same direction
        if n_mag > 1 and best["sign"] != 0:
            for _ in range(n_mag - 1):
                extra = DistillationMechanics._roll_one_axis(level)
                if extra["sign"] == best["sign"]:
                    best = DistillationMechanics._better_axis_outcome(best, extra)
        return best

    @staticmethod
    def _guarantee_non_nothing(outcome: dict, level: int) -> dict:
        """For force events: ensure the outcome is not nothing — can be positive or negative."""
        if outcome["sign"] == 0:
            sign = 1 if random.random() < 0.5 else -1
            mag = DistillationMechanics._delta_for(1, "value", level)
            return {"sign": sign, "tier": 1, "delta": mag * sign}
        return outcome

    @staticmethod
    def _apply_axis_effects(outcome: dict, eff: dict, level: int) -> dict:
        """Apply property effects (safe, guarantee_improvement, min_tier, unlucky, double_gain) to one axis."""
        sign, tier, delta = outcome["sign"], outcome["tier"], outcome["delta"]

        # safe: no decreases — negative becomes nothing
        if eff.get("safe") and sign < 0:
            sign, tier, delta = 0, 0, 0.0

        # guarantee_improvement: nothing or negative becomes small positive
        if eff.get("guarantee_improvement") and sign <= 0:
            sign = 1
            tier = 1
            delta = DistillationMechanics._delta_for(1, "value", level)

        # min_tier: ensure at least minimum tier on a positive outcome
        min_tier_val = {"good": 2, "a_lot": 3}.get(eff.get("min_tier", ""), 0)
        if min_tier_val > 0:
            if sign <= 0:
                sign = 1
                tier = min_tier_val
                delta = DistillationMechanics._delta_for(min_tier_val, "value", level)
            elif tier < min_tier_val:
                tier = min_tier_val
                delta = DistillationMechanics._delta_for(min_tier_val, "value", level)

        # unlucky: degrade outcome by one tier
        if eff.get("unlucky"):
            if sign > 0 and tier > 1:
                tier -= 1
                delta = DistillationMechanics._delta_for(tier, "value", level)
            elif sign > 0 and tier == 1:
                sign, tier, delta = 0, 0, 0.0
            elif sign == 0 and random.random() < 0.4:
                sign = -1
                tier = 1
                delta = -DistillationMechanics._delta_for(1, "value", level)

        # double_gain: double any positive gain
        if eff.get("double_gain") and sign > 0 and delta > 0:
            delta *= 2.0

        return {"sign": sign, "tier": tier, "delta": delta}

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
    def project_values(session: dict) -> tuple[float, float]:
        """Compute current projected (value, duration) for the in-progress session.

        The raw accumulators (value_mod, duration_mod) are range-relative: they
        map onto each passive's [value_min, value_max] / [duration_min, duration_max]
        so the stated minimums are guaranteed even with zero gains, and a perfect
        all-tier-3 run reaches the stated maximum.
        """
        base = session.get("base_type") or "panacea"
        info = DistillationMechanics.POWERFUL_PASSIVES.get(
            base, list(DistillationMechanics.POWERFUL_PASSIVES.values())[0]
        )
        val_min = info.get("value_min", 5.0)
        val_max = info.get("value_max", 150.0)
        dur_min = info.get("duration_min", 2.0)
        dur_max = info.get("duration_max", 5.0)

        raw_max = DistillationMechanics.get_raw_max(session)

        val_frac = max(0.0, session.get("value_mod", 0.0)) / raw_max
        dur_frac = max(0.0, session.get("duration_mod", 0.0)) / raw_max

        val = val_min + val_frac * (val_max - val_min)
        dur = dur_min + dur_frac * (dur_max - dur_min)

        # Duration is always an integer number of turns — use floor so 3.5 shows as 3, not 4.
        dur_int = max(int(dur_min), min(int(dur), int(dur_max)))
        return (
            max(val_min, min(round(val, 1), val_max)),
            float(dur_int),
        )

    # Calibrated ceiling: was half the steps giving tier-2 (good) gains; bumped to
    # 0.65 to raise the bar for reaching value_max (nerf — same run now lands closer
    # to the bottom of the advertised range). The theoretical all-tier-3 max is still
    # far higher than any real run achieves, so using it as the denominator would
    # crowd everything into the bottom of the range instead.
    RAW_MAX_STEPS_FACTOR = 0.65

    @staticmethod
    def get_raw_max(session: dict) -> float:
        """Return the calibrated raw accumulator ceiling used by project_values."""
        alchemy_level = session.get("alchemy_level", 1)
        return (
            DistillationMechanics.STEPS * DistillationMechanics.RAW_MAX_STEPS_FACTOR
        ) * DistillationMechanics._delta_for(2, "value", alchemy_level)

    @staticmethod
    def finalize(session: dict) -> tuple[str, float, float]:
        """Turn the accumulated session into a concrete powerful passive."""
        base = session.get("base_type") or "panacea"
        val, dur = DistillationMechanics.project_values(session)
        return base, val, dur

    @staticmethod
    def format_distilled_passive(
        passive_type: str, value: float, duration: float
    ) -> str:
        info = DistillationMechanics.POWERFUL_PASSIVES.get(passive_type)
        if not info:
            return f"{passive_type} (value {value}, duration {duration})"
        return (
            info["desc"]
            .format(value=value, duration=duration)
            .removeprefix("On potion use: ")
        )


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
