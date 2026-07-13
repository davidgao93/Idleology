"""core/inner_sanctum/data.py — Inner Sanctum tree node definitions.

Three paths, unlocked at different levels:
  Vice     (level 25) — rarity / loot bias.       Downside: monster ATK/HP up.
  Recovery (level 25) — stamina / survivability.   Downside: small player ATK malus.
  Deicide  (level 75) — boss-hunting.              Downside: boss ATK/DEF/HP up.

Nodes are *ranked* — each rank costs points and adds `value_per_rank` to its
effect. `costs` is the list of per-rank prices (costs[0] = price of rank 1).
Choice nodes (`is_choice=True`) are single-purchase and store the player's
picked option string in nodes_owned instead of an int rank.
"""

VICE_UNLOCK_LEVEL = 25
RECOVERY_UNLOCK_LEVEL = 25
DEICIDE_UNLOCK_LEVEL = 75

# ---------------------------------------------------------------------------
# Vice — rarity & loot bias
# ---------------------------------------------------------------------------
VICE_NODES: dict = {
    "vi_rarity": {
        "branch": "vice",
        "name": "Gilded Instinct",
        "desc": lambda rank: f"+{rank * 0.75:.2f}% Special Rarity chance",
        "max_rank": 5,
        "costs": [15, 20, 30, 45, 65],
        "value_per_rank": 0.75,  # feeds player.get_special_drop_bonus() pool
    },
    "vi_rune_chance": {
        "branch": "vice",
        "name": "Hoarder's Eye",
        "desc": lambda rank: f"+{rank * 0.6:.1f}% chance to find a rune",
        "max_rank": 5,
        "costs": [20, 30, 45, 65, 90],
        "value_per_rank": 0.006,  # additive fraction on rune-flag rolls
    },
    "vi_treasure": {
        "branch": "vice",
        "name": "Treasure Sense",
        "desc": lambda rank: (
            f"+{rank * 0.5:.1f}% chance to encounter a Treasure monster"
        ),
        "max_rank": 5,
        "costs": [15, 20, 30, 45, 65],
        "value_per_rank": 0.5,  # same units as Treasure-Tracker boot (%)
    },
}
# Per *rank* invested anywhere in Vice (15 ranks at full investment), spawned
# monsters get slightly tankier/harder-hitting. Scaled per rank rather than per
# point spent — per-rank costs escalate fast, so a points-based scalar would
# make the downside balloon far past "minor" at full investment.
VICE_DOWNSIDE_ATK_PCT_PER_RANK = 0.005
VICE_DOWNSIDE_HP_PCT_PER_RANK = 0.005

# ---------------------------------------------------------------------------
# Recovery — stamina & survivability
# ---------------------------------------------------------------------------
RECOVERY_NODES: dict = {
    "re_stamina_save": {
        "branch": "recovery",
        "name": "Frugal Spirit",
        "desc": lambda rank: f"{rank * 3}% chance combat doesn't consume stamina",
        "max_rank": 5,
        "costs": [15, 20, 30, 45, 65],
        "value_per_rank": 0.03,
    },
    "re_stamina_regen": {
        "branch": "recovery",
        "name": "Deep Reserves",
        "desc": lambda rank: (
            f"{rank * 4}% chance stamina regen tick grants +2 instead of +1"
        ),
        "max_rank": 5,
        "costs": [15, 20, 30, 45, 65],
        "value_per_rank": 0.04,
    },
    "re_exp_shield": {
        "branch": "recovery",
        "name": "Merciful Fall",
        "desc": lambda rank: f"-{rank * 4}% EXP lost on death",
        "max_rank": 5,
        "costs": [15, 20, 30, 45, 65],
        "value_per_rank": 0.04,
    },
}
# Per rank invested anywhere in Recovery (15 ranks at full investment), a small
# permanent ATK malus (the calm dulls your edge).
RECOVERY_DOWNSIDE_ATK_PCT_PER_RANK = 0.002

# ---------------------------------------------------------------------------
# Deicide — boss hunting (unlocked at level 75)
# ---------------------------------------------------------------------------
DEICIDE_NODES: dict = {
    "de_boss_chance": {
        "branch": "deicide",
        "name": "Hunter's Resolve",
        "desc": lambda rank: f"+{rank * 3}% chance to encounter a boss door",
        "max_rank": 5,
        "costs": [20, 35, 50, 70, 100],
        "value_per_rank": 0.03,
    },
    "de_affinity": {
        "branch": "deicide",
        "name": "Marked Prey",
        "is_choice": True,
        "cost": 25,
        "choices": [
            ("aphrodite", "Aphrodite (Celestial) — boss doors favor Aphrodite"),
            ("lucifer", "Lucifer (Infernal) — boss doors favor Lucifer"),
            ("gemini", "Gemini (Balance) — boss doors favor Gemini"),
            ("NEET", "NEET (Void) — boss doors favor NEET"),
        ],
        "affinity_shift": 0.5,  # +50% relative weight toward the chosen boss type
    },
    "de_boss_runes": {
        "branch": "deicide",
        "name": "Reliquary Sense",
        "desc": lambda rank: f"+{rank}% chance for bosses to drop bonus runes",
        "max_rank": 5,
        "costs": [25, 35, 50, 70, 100],
        "value_per_rank": 0.01,
    },
    "de_boss_dupe": {
        "branch": "deicide",
        "name": "Greedy Conquest",
        "desc": lambda rank: (
            f"{rank * 10}% chance for a second bonus rune roll on boss kills"
        ),
        "max_rank": 3,
        "costs": [40, 60, 90],
        "value_per_rank": 0.10,
    },
}
# Per rank invested anywhere in Deicide (14 ranks at full investment — including
# the single-purchase affinity choice), phase-door bosses get tougher (Uber
# bosses unaffected).
DEICIDE_DOWNSIDE_ATK_PCT_PER_RANK = 0.006
DEICIDE_DOWNSIDE_DEF_PCT_PER_RANK = 0.006
DEICIDE_DOWNSIDE_HP_PCT_PER_RANK = 0.006

ALL_NODES: dict = {**VICE_NODES, **RECOVERY_NODES, **DEICIDE_NODES}

RESET_RUNE_COST = 3  # Runes of Regret consumed to fully reset the tree
