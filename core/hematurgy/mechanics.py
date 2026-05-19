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
# Tier upgrade costs (Evolutionary blood) — keyed by target_tier
# ---------------------------------------------------------------------------

UPGRADE_COSTS = {
    2: 200,
    3: 1_000,
    4: 2_000,
    5: 5_000,
}

MUTATIVE_COST = 1_000   # Mutative blood per attempt
TRANSMUTE_RATIO = 3     # 3 of source → 1 of target

# ---------------------------------------------------------------------------
# Per-tier values indexed 0–4 (tier-1)
# ---------------------------------------------------------------------------

_TV: dict[str, list] = {
    # Main pool
    "reverberation":        [0.10, 0.15, 0.20, 0.25, 0.30],   # re-echo proc chance
    "soothing_venom":       [0.25, 0.35, 0.45, 0.55, 0.65],   # poison lifesteal fraction
    "iron_momentum":        [0.03, 0.05, 0.07, 0.09, 0.11],   # ATK% bonus per stack
    "serrated":             [5,    10,   15,   20,   25  ],    # flat ATK drain per hit
    "haemorrhage":          [0.02, 0.03, 0.04, 0.05, 0.06],   # bleed added as % ATK per hit
    "vital_resonance":      [0.10, 0.15, 0.20, 0.25, 0.30],   # ward→HP fraction
    "executioners_rite":    [0.10, 0.15, 0.20, 0.25, 0.30],   # ATK+crit-dmg bonus below 30% HP
    "bloodthirst":          [0.10, 0.15, 0.20, 0.25, 0.30],   # Max HP healed on kill
    "phantom_reflex":       [0.10, 0.15, 0.20, 0.25, 0.30],   # evasion% per stack on miss
    "chain_reaction":       [0.08, 0.12, 0.16, 0.20, 0.24],   # crit-dmg multiplier per crit stack
    "regenerative_tissue":  [0.02, 0.03, 0.04, 0.05, 0.06],   # HP% healed after zero-damage round
    "fevered_strike":       [0.05, 0.08, 0.11, 0.14, 0.17],   # ATK% per potion consumed
    "predators_mark":       [0.15, 0.20, 0.25, 0.30, 0.35],   # damage bonus on marked hit
    "counterforce":         [0.05, 0.08, 0.11, 0.14, 0.17],   # DEF% added as flat ATK each round
    "tenacity":             [0.10, 0.15, 0.20, 0.25, 0.30],   # ATK+DEF% on first HP<40% drop
    # Mutated pool
    "spectral_waltz":       [5,    5,    6,    7,    8   ],    # % ATK per blade released
    "spectral_waltz_max":   [5,    6,    7,    8,    10  ],    # max blade cap
    "puncture":             [0.05, 0.08, 0.11, 0.14, 0.17],   # crit-dmg fraction added to puncture bleed
    "flash_frost":          [15,   13,   11,   9,    7   ],    # miss threshold for freeze (int)
    "ward_inoculation":     [0.60, 0.70, 0.80, 0.90, 1.00],   # ward→damage efficiency
    "soul_fracture":        [0.03, 0.05, 0.07, 0.09, 0.11],   # ATK% per 10% Max HP lost in combat
}


def tier_val(passive_id: str, tier: int) -> float:
    """Returns the numeric value for a passive at the given tier (1-indexed)."""
    values = _TV.get(passive_id)
    if not values:
        return 0.0
    return values[min(max(tier, 1), 5) - 1]


# ---------------------------------------------------------------------------
# Main passive pool (15 passives)
# ---------------------------------------------------------------------------

def _desc(pid: str, tier: int) -> str:
    """Generates a human-readable description for a passive at a given tier."""
    v = tier_val(pid, tier)
    pct = lambda x: f"{int(x * 100)}%"
    match pid:
        case "reverberation":
            return (
                f"Echo hits have a {pct(v)} chance to re-echo again (each successive "
                f"re-echo is -10% less likely, resets on miss)."
            )
        case "soothing_venom":
            return (
                f"{pct(v)} of your Poison passive's miss-damage is returned as HP lifesteal."
            )
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
                f"Ticks 10% of total bleed per round. On kill: full bleed discharges instantly."
            )
        case "vital_resonance":
            return (
                f"{pct(v)} of all ward generated is simultaneously applied as HP recovery."
            )
        case "executioners_rite":
            return (
                f"While the monster is below 30% HP: +{pct(v)} ATK and +{pct(v)} crit damage."
            )
        case "bloodthirst":
            return (
                f"On monster kill: restore {pct(v)} of Max HP. Carries into the next fight. "
                f"(Non-Soulreap alternative.)"
            )
        case "phantom_reflex":
            return (
                f"On miss: gain +{pct(v)} Evasion for 1 round (max 2 stacks). "
                f"Stacks are consumed by incoming hits. Respects 80% evasion cap."
            )
        case "chain_reaction":
            return (
                f"Each consecutive crit adds +{pct(v)} crit damage (max 5 stacks). "
                f"Resets on any non-crit outcome."
            )
        case "regenerative_tissue":
            return (
                f"After any round in which zero effective HP damage was taken "
                f"(fully blocked, evaded, PDR'd, or ward-absorbed): heal {pct(v)} Max HP."
            )
        case "fevered_strike":
            return (
                f"Each potion consumed during combat permanently grants +{pct(v)} ATK "
                f"for the remainder of the fight."
            )
        case "predators_mark":
            return (
                f"Crits apply **Mark** to the monster. Your next hit deals +{pct(v)} damage "
                f"and consumes the Mark. Missing clears the Mark without dealing the bonus."
            )
        case "counterforce":
            return (
                f"At the start of each player turn, {pct(v)} of your total DEF is added "
                f"as flat bonus ATK for that turn."
            )
        case "tenacity":
            return (
                f"The first time your HP drops below 40% during combat: permanently "
                f"gain +{pct(v)} ATK and +{pct(v)} DEF for the remainder of the fight (one-shot)."
            )
        # Mutated
        case "spectral_waltz":
            mx = int(tier_val("spectral_waltz_max", tier))
            return (
                f"+1 blade on hit (max {mx}), −1 blade on miss. Crits release ALL blades "
                f"simultaneously, each dealing {pct(v)} ATK."
            )
        case "puncture":
            return (
                f"Crits accumulate bleed equal to {pct(v)} of crit damage dealt. "
                f"On miss: monster takes 50% of total puncture bleed as burst damage, "
                f"then bleed resets. Does not interact with Soothing Venom."
            )
        case "flash_frost":
            thresh = int(v)
            return (
                f"After {thresh} consecutive misses the monster cannot act for 1 round "
                f"and the counter fully resets. Checks invulnerability before applying."
            )
        case "ward_inoculation":
            return (
                f"Combat start: all ward is converted to DEF and Max HP is doubled. "
                f"Ward gained during combat instead deals {pct(v)} of its value as damage."
            )
        case "soul_fracture":
            return (
                f"For each 10% of Max HP lost **during this combat** (HP at combat start "
                f"excluded): +{pct(v)} ATK. Tracks real-time; resets between fights."
            )
    return "Unknown passive."


PASSIVE_POOL: dict[str, dict] = {
    "reverberation":        {"name": "Reverberation",       "description": _desc},
    "soothing_venom":       {"name": "Soothing Venom",      "description": _desc},
    "iron_momentum":        {"name": "Iron Momentum",        "description": _desc},
    "serrated":             {"name": "Serrated",             "description": _desc},
    "haemorrhage":          {"name": "Haemorrhage",          "description": _desc},
    "vital_resonance":      {"name": "Vital Resonance",      "description": _desc},
    "executioners_rite":    {"name": "Executioner's Rite",  "description": _desc},
    "bloodthirst":          {"name": "Bloodthirst",          "description": _desc},
    "phantom_reflex":       {"name": "Phantom Reflex",       "description": _desc},
    "chain_reaction":       {"name": "Chain Reaction",       "description": _desc},
    "regenerative_tissue":  {"name": "Regenerative Tissue",  "description": _desc},
    "fevered_strike":       {"name": "Fevered Strike",       "description": _desc},
    "predators_mark":       {"name": "Predator's Mark",      "description": _desc},
    "counterforce":         {"name": "Counterforce",         "description": _desc},
    "tenacity":             {"name": "Tenacity",             "description": _desc},
}

# ---------------------------------------------------------------------------
# Mutated passive pool (5 passives — only accessible via Mutative blood)
# ---------------------------------------------------------------------------

MUTATIVE_POOL: dict[str, dict] = {
    "spectral_waltz":   {"name": "Spectral Waltz",     "description": _desc},
    "puncture":         {"name": "Puncture",            "description": _desc},
    "flash_frost":      {"name": "Flash Frost",         "description": _desc},
    "ward_inoculation": {"name": "Ward Inoculation",    "description": _desc},
    "soul_fracture":    {"name": "Soul Fracture",       "description": _desc},
}

# ---------------------------------------------------------------------------
# Mutative outcome weights
# ---------------------------------------------------------------------------

_MUTATIVE_OUTCOMES = ["delete", "downgrade", "double", "new_passive"]
_MUTATIVE_WEIGHTS  = [50, 20, 15, 15]


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
