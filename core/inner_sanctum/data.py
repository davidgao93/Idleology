"""core/inner_sanctum/data.py — Inner Sanctum tree node definitions.

Three paths, unlocked at different levels:
  Vice     (level 25) — rarity / loot bias.       Downside: monster stats up.
  Recovery (level 25) — stamina / survivability.   Downside: small player ATK malus.
  Deicide  (level 75) — boss-hunting.              Downside: boss ATK/DEF/HP up.

Nodes are *ranked* — each rank costs points. `costs` is the list of per-rank
prices (costs[0] = price of rank 1). Choice nodes (`is_choice=True`) are
single-purchase and store the player's picked option string in nodes_owned
instead of an int rank.

Vice nodes carry their upside/downside as explicit `*_per_rank` numeric keys
(read generically by mechanics.get_tree_bonuses) rather than a single
`value_per_rank` — several Vice nodes grant two effects at once (an upside
and its paired downside), so a single scalar isn't enough.
"""

VICE_UNLOCK_LEVEL = 25
RECOVERY_UNLOCK_LEVEL = 25
DEICIDE_UNLOCK_LEVEL = 75

# ---------------------------------------------------------------------------
# Vice — rarity & loot bias (70 points total at full investment)
# ---------------------------------------------------------------------------
VICE_NODES: dict = {
    # ── Special Needs — 5 nodes x 5 ranks x 1 pt/rank = 25 pts.
    # +0.5% Special Rarity total at full investment. ─────────────────────────
    "vi_sn_atk": {
        "branch": "vice",
        "group": "Special Needs",
        "name": "Vicious Instinct",
        "desc": lambda rank: (
            f"+{rank * 0.02:.2f}% Special Rarity | +{rank * 1}% monster ATK"
        ),
        "max_rank": 5,
        "costs": [1, 1, 1, 1, 1],
        "special_rarity_per_rank": 0.02,
        "monster_atk_per_rank": 0.01,
    },
    "vi_sn_def": {
        "branch": "vice",
        "group": "Special Needs",
        "name": "Reckless Greed",
        "desc": lambda rank: (
            f"+{rank * 0.02:.2f}% Special Rarity | +{rank * 1}% monster DEF"
        ),
        "max_rank": 5,
        "costs": [1, 1, 1, 1, 1],
        "special_rarity_per_rank": 0.02,
        "monster_def_per_rank": 0.01,
    },
    "vi_sn_crit": {
        "branch": "vice",
        "group": "Special Needs",
        "name": "Gambler's Edge",
        "desc": lambda rank: (
            f"+{rank * 0.02:.2f}% Special Rarity | +{rank * 1}% monster Crit Chance"
        ),
        "max_rank": 5,
        "costs": [1, 1, 1, 1, 1],
        "special_rarity_per_rank": 0.02,
        "monster_crit_per_rank": 0.01,
    },
    "vi_sn_hp": {
        "branch": "vice",
        "group": "Special Needs",
        "name": "Indulgent Excess",
        "desc": lambda rank: (
            f"+{rank * 0.02:.2f}% Special Rarity | +{rank * 1}% monster Max HP"
        ),
        "max_rank": 5,
        "costs": [1, 1, 1, 1, 1],
        "special_rarity_per_rank": 0.02,
        "monster_hp_per_rank": 0.01,
    },
    "vi_sn_dmg": {
        "branch": "vice",
        "group": "Special Needs",
        "name": "Tempting Fate",
        "desc": lambda rank: (
            f"+{rank * 0.02:.2f}% Special Rarity | +{rank * 1}% monster damage dealt"
        ),
        "max_rank": 5,
        "costs": [1, 1, 1, 1, 1],
        "special_rarity_per_rank": 0.02,
        "monster_dmg_per_rank": 0.01,
    },
    # ── Runefinder — 3 nodes x 5 ranks x 1 pt/rank = 15 pts. ─────────────────
    "vi_rf_refine": {
        "branch": "vice",
        "group": "Runefinder",
        "name": "Refiner's Eye",
        "desc": lambda rank: (
            f"+{rank * 0.1:.1f}% chance for a Rune of Refinement "
            f"| +{rank * 1}% monster ATK"
        ),
        "max_rank": 5,
        "costs": [1, 1, 1, 1, 1],
        "refine_chance_per_rank": 0.001,
        "monster_atk_per_rank": 0.01,
    },
    "vi_rf_potential": {
        "branch": "vice",
        "group": "Runefinder",
        "name": "Potential Unbound",
        "desc": lambda rank: (
            f"+{rank * 0.2:.1f}% chance for a Rune of Potential "
            f"| +{rank * 1}% monster DEF"
        ),
        "max_rank": 5,
        "costs": [1, 1, 1, 1, 1],
        "potential_chance_per_rank": 0.002,
        "monster_def_per_rank": 0.01,
    },
    "vi_rf_shatter": {
        "branch": "vice",
        "group": "Runefinder",
        "name": "Shattered Fortune",
        "desc": lambda rank: (
            f"+{rank * 0.3:.1f}% chance for a Rune of Shattering "
            f"| +{rank * 0.5}% monster ATK, +{rank * 0.5}% monster DEF"
        ),
        "max_rank": 5,
        "costs": [1, 1, 1, 1, 1],
        "shatter_chance_per_rank": 0.003,
        "monster_atk_per_rank": 0.005,
        "monster_def_per_rank": 0.005,
    },
    # ── Curio-sity — 3 nodes x 10 ranks x 1 pt/rank = 30 pts.
    # Treasure monsters (baseline 1 ATK / 1 DEF / 10 HP) gain back up to 90%
    # of a normal same-level monster's stats when all three are maxed. ──────
    "vi_cur_treasure": {
        "branch": "vice",
        "group": "Curio-sity",
        "name": "Wandering Eye",
        "desc": lambda rank: (
            f"+{rank * 0.01:.2f}% chance to encounter a Treasure monster "
            f"| Treasure monsters +{rank * 3}% of normal stats"
        ),
        "max_rank": 10,
        "costs": [1] * 10,
        "treasure_encounter_per_rank": 0.0001,
        "treasure_stat_per_rank": 0.03,
    },
    "vi_cur_curio": {
        "branch": "vice",
        "group": "Curio-sity",
        "name": "Grasping Hands",
        "desc": lambda rank: (
            f"+{rank * 0.01:.2f}% chance for an additional Curio on victory "
            f"| Treasure monsters +{rank * 3}% of normal stats"
        ),
        "max_rank": 10,
        "costs": [1] * 10,
        "bonus_curio_per_rank": 0.0001,
        "treasure_stat_per_rank": 0.03,
    },
    "vi_cur_box": {
        "branch": "vice",
        "group": "Curio-sity",
        "name": "Boundless Hoard",
        "desc": lambda rank: (
            f"+{rank * 0.001:.3f}% chance for an additional Curio Puzzle Box "
            f"| Treasure monsters +{rank * 3}% of normal stats"
        ),
        "max_rank": 10,
        "costs": [1] * 10,
        "bonus_puzzlebox_per_rank": 0.00001,
        "treasure_stat_per_rank": 0.03,
    },
}

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
