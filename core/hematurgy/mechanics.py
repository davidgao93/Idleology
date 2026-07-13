import random

# ---------------------------------------------------------------------------
# Slot unlock costs (Primordial blood)
# ---------------------------------------------------------------------------

SLOT_UNLOCK_COSTS = {
    "head": 100,
    "torso": 500,
    "right_arm": 1_000,
    "left_arm": 1_000,
    "right_leg": 1_000,
    "left_leg": 1_000,
    "cheeks": 50_000,
    "organs": 50_000,
}

# ---------------------------------------------------------------------------
# Tier upgrade costs (Evolutionary blood) — keyed by target_tier
# ---------------------------------------------------------------------------

UPGRADE_COSTS = {
    2: 200,
    3: 1_000,
    4: 2_000,
    5: 5_000,
}

MUTATIVE_COST = 1_000  # Mutative blood per attempt
TRANSMUTE_RATIO = 3  # 3 of source → 1 of target

# ---------------------------------------------------------------------------
# Per-tier values indexed 0–6 (tier-1); T1–T5 via Evolutionary blood,
# T6–T7 are mutation-only chase tiers.
# ---------------------------------------------------------------------------

_TV: dict[str, list] = {
    # Main pool                                            T1     T2     T3     T4     T5     T6     T7
    "reverberation": [0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90],  # re-echo proc chance
    "soothing_venom": [
        0.02,
        0.04,
        0.06,
        0.08,
        0.10,
        0.12,
        0.14,
    ],  # poison lifesteal fraction
    "iron_momentum": [0.03, 0.05, 0.07, 0.09, 0.11, 0.13, 0.15],  # ATK% bonus per stack
    "serrated": [5, 10, 15, 20, 25, 30, 35],  # flat ATK drain per hit
    "haemorrhage": [
        0.02,
        0.03,
        0.04,
        0.05,
        0.06,
        0.07,
        0.08,
    ],  # bleed added as % ATK per hit
    "vital_resonance": [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40],  # ward→HP fraction
    "executioners_rite": [
        0.10,
        0.15,
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
    ],  # ATK+crit-dmg bonus below 30% HP
    "crimson_feast": [
        0.10,
        0.15,
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
    ],  # Max HP healed on kill
    "phantom_reflex": [
        0.10,
        0.15,
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
    ],  # evasion% per stack on miss
    "chain_reaction": [
        0.08,
        0.12,
        0.16,
        0.20,
        0.24,
        0.28,
        0.32,
    ],  # crit-dmg multiplier per crit stack
    "regenerative_tissue": [
        0.02,
        0.03,
        0.04,
        0.05,
        0.06,
        0.07,
        0.08,
    ],  # HP% healed after zero-damage round
    "fevered_strike": [
        0.05,
        0.08,
        0.11,
        0.14,
        0.17,
        0.20,
        0.23,
    ],  # ATK% per potion consumed
    "predators_mark": [
        0.15,
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
        0.45,
    ],  # damage bonus on marked hit
    "counterforce": [
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
        0.45,
        0.50,
    ],  # DEF% added as flat ATK each round
    "defiance": [
        0.10,
        0.15,
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
    ],  # ATK+DEF% on first HP<40% drop
    # Mutated pool
    "spectral_waltz": [4, 5, 6, 7, 8, 9, 10],  # % ATK per blade released
    "spectral_waltz_max": [5, 6, 7, 8, 10, 12, 15],  # max blade cap
    "puncture": [
        0.05,
        0.08,
        0.11,
        0.14,
        0.17,
        0.20,
        0.23,
    ],  # crit-dmg fraction added to puncture bleed
    "flash_frost": [15, 13, 11, 9, 7, 5, 3],  # miss threshold for freeze (int)
    "ward_inoculation": [
        0.50,
        0.65,
        0.80,
        0.95,
        1.10,
        1.25,
        1.40,
    ],  # combat-start ward→bonus DEF conversion rate
    "soul_fracture": [
        0.03,
        0.05,
        0.07,
        0.09,
        0.11,
        0.13,
        0.15,
    ],  # ATK% per 10% Max HP lost in combat
}

# Maximum tier reachable (T5 via Evolutionary, T6/T7 via Mutation only)
MAX_TIER = 7
EVO_MAX_TIER = 5


def tier_val(passive_id: str, tier: int) -> float:
    """Returns the numeric value for a passive at the given tier (1-indexed, up to T7)."""
    values = _TV.get(passive_id)
    if not values:
        return 0.0
    idx = min(max(tier, 1), len(values)) - 1
    return values[idx]


# ---------------------------------------------------------------------------
# Main passive pool (15 passives)
# ---------------------------------------------------------------------------


def _desc(pid: str, tier: int) -> str:
    """Generates a human-readable description for a passive at a given tier."""
    v = tier_val(pid, tier)

    def pct(x):
        return f"{int(x * 100)}%"

    match pid:
        case "reverberation":
            return (
                f"Your weapon's Echo passive has a {pct(v)} chance to chain re-echo "
                f"again (each successive re-echo is 50% less likely)."
            )
        case "soothing_venom":
            return f"{pct(v)} of your weapon's Poison passive miss-damage is gained as HP."
        case "iron_momentum":
            return (
                f"Each consecutive hit grants +{pct(v)} ATK (max 5 stacks). "
                f"All stacks reset on miss."
            )
        case "serrated":
            return (
                f"Each hit permanently reduces the monster's ATK by {int(v)} "
                f"(Crits: {int(v) * 2}). No cap."
            )
        case "haemorrhage":
            return (
                f"Each hit adds a bleed charge worth {pct(v)} ATK. "
                f"Ticks 10% of total bleed per round."
            )
        case "vital_resonance":
            return f"{pct(v)} of all ward generated is simultaneously applied as HP recovery."
        case "executioners_rite":
            return (
                f"On hit, while the monster is below 30% HP: +{pct(v)} bonus ATK "
                f"and +{v:.2f} critical strike multiplier."
            )
        case "crimson_feast":
            return f"On monster kill: restore {pct(v)} of Max HP."
        case "phantom_reflex":
            return (
                f"On miss: gain +{pct(v)} Evasion for 1 round (max 2 stacks). "
                f"Lose stacks when hit."
            )
        case "chain_reaction":
            return (
                f"Each consecutive crit adds +{pct(v)} crit damage (max 5 stacks). "
                f"Resets on non-crit."
            )
        case "regenerative_tissue":
            return (
                f"Heal {pct(v)} Max HP if you didn't take HP damage. "
                f"(blocked, evaded, ward-absorbed, or reduced to 0)"
            )
        case "fevered_strike":
            return (
                f"Each potion consumed during combat permanently grants +{pct(v)} ATK."
            )
        case "predators_mark":
            return (
                f"Crits apply **Mark** to the monster. Your next hit deals +{pct(v)} damage "
                f"and consumes the Mark. Missing clears the Mark without dealing the bonus."
            )
        case "counterforce":
            return (
                f"During combat, {pct(v)} of your flat DEF is added "
                f"as flat bonus ATK."
            )
        case "defiance":
            return (
                f"The first time your HP drops below 40% during combat: permanently "
                f"gain +{pct(v)} ATK and +{pct(v)} DEF for the remainder of the fight (one-shot)."
            )
        # Mutated
        case "spectral_waltz":
            mx = int(tier_val("spectral_waltz_max", tier))
            return (
                f"+1 blade on hit (max {mx}), −1 blade on miss. Crits release ALL blades "
                f"simultaneously, each dealing {v:.0f}% ATK."
            )
        case "puncture":
            return (
                f"Crits accumulate bleed equal to {pct(v)} of crit damage dealt. "
                f"On miss: monster takes 50% of total puncture bleed as burst damage, "
                f"then bleed resets."
            )
        case "flash_frost":
            thresh = int(v)
            return (
                f"Each miss adds a Frost stack on the monster. After {thresh} stacks, "
                f"the monster cannot act for 1 turn and the stacks fully reset. "
                f"Checks invulnerability before applying."
            )
        case "ward_inoculation":
            return (
                f"Combat start: gain {pct(v)} of your ward as bonus DEF, and Max HP "
                f"is doubled."
            )
        case "soul_fracture":
            return (
                f"For each 10% of your flat Max HP lost **during this combat**: "
                f"+{pct(v)} bonus ATK. Tracks real-time; resets between fights."
            )
    return "Unknown passive."


PASSIVE_POOL: dict[str, dict] = {
    "reverberation": {"name": "Reverberation", "description": _desc},
    "soothing_venom": {"name": "Soothing Venom", "description": _desc},
    "iron_momentum": {"name": "Iron Momentum", "description": _desc},
    "serrated": {"name": "Serrated", "description": _desc},
    "haemorrhage": {"name": "Haemorrhage", "description": _desc},
    "vital_resonance": {"name": "Vital Resonance", "description": _desc},
    "executioners_rite": {"name": "Executioner's Rite", "description": _desc},
    "crimson_feast": {"name": "Crimson Feast", "description": _desc},
    "phantom_reflex": {"name": "Phantom Reflex", "description": _desc},
    "chain_reaction": {"name": "Chain Reaction", "description": _desc},
    "regenerative_tissue": {"name": "Regenerative Tissue", "description": _desc},
    "fevered_strike": {"name": "Fevered Strike", "description": _desc},
    "predators_mark": {"name": "Predator's Mark", "description": _desc},
    "counterforce": {"name": "Counterforce", "description": _desc},
    "defiance": {"name": "Defiance", "description": _desc},
}

# ---------------------------------------------------------------------------
# Mutated passive pool (5 passives — only accessible via Mutative blood)
# ---------------------------------------------------------------------------

MUTATIVE_POOL: dict[str, dict] = {
    "spectral_waltz": {"name": "Spectral Waltz", "description": _desc},
    "puncture": {"name": "Puncture", "description": _desc},
    "flash_frost": {"name": "Flash Frost", "description": _desc},
    "ward_inoculation": {"name": "Ward Inoculation", "description": _desc},
    "soul_fracture": {"name": "Soul Fracture", "description": _desc},
}

# ---------------------------------------------------------------------------
# Mutative outcome weights
# ---------------------------------------------------------------------------

_MUTATIVE_OUTCOMES = ["delete", "downgrade", "upgrade", "new_passive"]
_MUTATIVE_WEIGHTS = [50, 20, 15, 15]


# ---------------------------------------------------------------------------
# HematurgyMechanics
# ---------------------------------------------------------------------------


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
    def passive_description(passive_id: str, tier: int = 1) -> str:
        defn = HematurgyMechanics.get_passive_def(passive_id)
        if not defn:
            return "Unknown passive."
        desc = defn["description"]
        if callable(desc):
            return desc(passive_id, tier)
        return desc

    @staticmethod
    def tier_val(passive_id: str, tier: int) -> float:
        return tier_val(passive_id, tier)

    @staticmethod
    def upgrade_cost(target_tier: int) -> int:
        return UPGRADE_COSTS.get(target_tier, 0)

    @staticmethod
    def unlock_cost(slot_type: str) -> int:
        return SLOT_UNLOCK_COSTS.get(slot_type, 0)
