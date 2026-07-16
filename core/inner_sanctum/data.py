"""core/inner_sanctum/data.py — Inner Sanctum tree node definitions.

Three paths, unlocked at different levels:
  Vice     (level 25) — rarity / loot bias.      Every node pairs its own upside
                                                  with its own downside.
  Recovery (level 25) — stamina / survivability. Same per-node pairing.
  Deicide  (level 75) — boss-hunting.             Same per-node pairing.

Nodes are *ranked* — each rank costs points. `costs` is the list of per-rank
prices (costs[0] = price of rank 1). Choice nodes (`is_choice=True`) are
single-purchase and store the player's picked option string in nodes_owned
instead of an int rank. Ranked-choice nodes (`is_choice_ranked=True`) combine
both: the player picks one option on the first purchase (locked forever short
of a full tree reset) and then invests ranks 1..max_rank same as any ranked
node; nodes_owned stores `{"choice": <str>, "rank": <int>}` for these.

Every node carries its upside/downside as explicit `*_per_rank` numeric keys
(read generically by mechanics.get_tree_bonuses via `_sum_field`) rather than
a single `value_per_rank` — several nodes grant two effects at once (an
upside and its paired downside), and several Deicide nodes deliberately share
a downside field name (e.g. `boss_dmg_pct_per_rank`) so multiple nodes' boss
damage penalties sum into one aggregate.
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
# Recovery — stamina & survivability (55 pts at full investment)
# ---------------------------------------------------------------------------
RECOVERY_NODES: dict = {
    "re_stamina_save": {
        "branch": "recovery",
        "name": "Frugal Spirit",
        "desc": lambda rank: (
            f"{rank * 0.5:.1f}% chance combat doesn't consume stamina "
            f"| +{rank * 10}s to the no-stamina combat cooldown"
        ),
        "max_rank": 20,
        "costs": [1] * 20,
        "stamina_save_chance_per_rank": 0.005,
        "cooldown_penalty_sec_per_rank": 10,
    },
    "re_stamina_regen": {
        "branch": "recovery",
        "name": "Deep Reserves",
        "desc": lambda rank: (
            f"{rank * 0.5:.1f}% chance a stamina regen tick grants +2 instead of +1 "
            f"| +{rank * 5}s to the no-stamina combat cooldown"
        ),
        "max_rank": 20,
        "costs": [1] * 20,
        "stamina_regen_bonus_chance_per_rank": 0.005,
        "cooldown_penalty_sec_per_rank": 5,
    },
    "re_exp_shield": {
        "branch": "recovery",
        "name": "Merciful Fall",
        "desc": lambda rank: (
            f"-{rank * 5}% EXP lost on death | /rest gold cost +{rank}%"
        ),
        "max_rank": 15,
        "costs": [1] * 15,
        "exp_loss_reduction_per_rank": 0.05,
        "rest_cost_pct_per_rank": 0.01,
    },
}

# ---------------------------------------------------------------------------
# Deicide — boss hunting (unlocked at level 75; 110 pts at full investment)
# Every node pairs its own downside — phase-door bosses (Aphrodite/Lucifer/
# NEET/Gemini boss-key encounters) get tougher; Uber bosses are unaffected.
# ---------------------------------------------------------------------------
DEICIDE_NODES: dict = {
    "de_boss_chance": {
        "branch": "deicide",
        "name": "Zealous Pursuit",
        "desc": lambda rank: (
            f"+{rank}% chance to encounter a boss door "
            f"| bosses +{rank}% Max HP"
        ),
        "max_rank": 10,
        "costs": [1] * 10,
        "boss_chance_bonus_per_rank": 0.01,
        "boss_hp_pct_per_rank": 0.01,
    },
    "de_affinity": {
        "branch": "deicide",
        "name": "Marked Prey",
        "is_choice_ranked": True,
        "max_rank": 5,
        "costs": [1] * 5,
        "choices": [
            ("aphrodite", "Aphrodite (Celestial) — boss doors favor Aphrodite"),
            ("lucifer", "Lucifer (Infernal) — boss doors favor Lucifer"),
            ("gemini", "Gemini (Balance) — boss doors favor Gemini"),
            ("NEET", "NEET (Void) — boss doors favor NEET"),
        ],
        # Index 0 = rank 1. No downside — locked in permanently once picked
        # (only a full tree reset can change the chosen boss type).
        "affinity_shift_by_rank": [0.50, 0.60, 0.70, 0.80, 0.90],
        "desc": lambda rank: (
            f"boss doors are {[50, 60, 70, 80, 90][rank - 1]}% likely to favor "
            "the chosen boss type" if rank > 0 else ""
        ),
    },
    "de_corrupted_affinity": {
        "branch": "deicide",
        "name": "Corrupted Affinity",
        "desc": lambda rank: (
            f"{rank * 10}% chance to re-roll a failed corrupted encounter check "
            f"| corrupted monsters +{rank * 2}% ATK/DEF/Max HP"
        ),
        "max_rank": 10,
        "costs": [1] * 10,
        "corrupted_reroll_chance_per_rank": 0.10,
        "corrupted_atk_pct_per_rank": 0.02,
        "corrupted_def_pct_per_rank": 0.02,
        "corrupted_hp_pct_per_rank": 0.02,
    },
    "de_boss_runes": {
        "branch": "deicide",
        "name": "Reliquary Sense",
        "desc": lambda rank: (
            f"+{rank}% chance for bosses to drop bonus runes "
            f"| bosses deal +{rank}% damage"
        ),
        "max_rank": 25,
        "costs": [1] * 25,
        "boss_rune_chance_per_rank": 0.01,
        "boss_dmg_pct_per_rank": 0.01,
    },
    "de_boss_dupe": {
        "branch": "deicide",
        "name": "Twinned Fortune",
        "desc": lambda rank: (
            f"{rank * 0.1:.1f}% chance for an already-dropped boss rune/key to "
            f"drop in double quantity | bosses deal +{rank}% damage"
        ),
        "max_rank": 50,
        "costs": [1] * 50,
        "dupe_chance_per_rank": 0.001,
        "boss_dmg_pct_per_rank": 0.01,
    },
    "de_sigil_chance": {
        "branch": "deicide",
        "name": "Sigil Fortune",
        "desc": lambda rank: (
            f"+{rank * 0.1:.1f}% chance for a bonus boss sigil "
            f"| bosses deal +{rank}% damage"
        ),
        "max_rank": 10,
        "costs": [1] * 10,
        "sigil_chance_per_rank": 0.001,
        "boss_dmg_pct_per_rank": 0.01,
    },
}

ALL_NODES: dict = {**VICE_NODES, **RECOVERY_NODES, **DEICIDE_NODES}

RESET_RUNE_COST = 3  # Runes of Regret consumed to fully reset the tree
