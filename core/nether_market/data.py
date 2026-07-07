"""
core/nether_market/data.py — Item pool, wealth tiers, mastery tree nodes, and NPC vendors.

Everything here is flavor-only "curiosities" with a fixed true_value — zero interaction
with any other item table (weapons/armor/accessories/etc). See docs/design/nether_market.md.
"""

from core.images import (
    NETHER_NPC_COUNTESS_VAELORA_THUMBNAIL,
    NETHER_NPC_IRONMONGER_THUMBNAIL,
    NETHER_NPC_LADY_FENWICK_THUMBNAIL,
    NETHER_NPC_OLD_OTTO_THUMBNAIL,
    NETHER_NPC_PENNY_LOAFER_THUMBNAIL,
    NETHER_NPC_THE_HOARDER_THUMBNAIL,
)

# ---------------------------------------------------------------------------
# Item pool (6 per offer tier; only 1 per tier is "active" in any given rotation)
# ---------------------------------------------------------------------------

ITEM_POOL: dict[str, list[dict]] = {
    "cheap": [
        {"key": "choc_dipped_pears", "name": "Choc-Dipped Pears", "true_value": 5_000},
        {
            "key": "suspicious_pickles",
            "name": "Suspicious Pickles",
            "true_value": 2_500,
        },
        {
            "key": "mismatched_buttons",
            "name": "Mismatched Buttons",
            "true_value": 1_800,
        },
        {"key": "dried_sea_kelp", "name": "Dried Sea Kelp", "true_value": 3_200},
        {"key": "crate_rubber_ducks", "name": "Rubber Duck Crate", "true_value": 4_000},
        {"key": "sack_loose_marbles", "name": "Loose Marbles", "true_value": 2_000},
    ],
    "med": [
        {"key": "crate_perfumes", "name": "Perfume Crate", "true_value": 60_000},
        {"key": "empty_jewelry_box", "name": "Empty Jewelry Box", "true_value": 45_000},
        {
            "key": "barrel_aged_vinegar",
            "name": "Aged Vinegar Barrel",
            "true_value": 35_000,
        },
        {
            "key": "counterfeit_watches",
            "name": "Counterfeit Watches",
            "true_value": 90_000,
        },
        {"key": "bundle_silk_scarves", "name": "Silk Scarves", "true_value": 55_000},
        {"key": "ornate_birdcage", "name": "Empty Birdcage", "true_value": 70_000},
    ],
    "expensive": [
        {"key": "gilded_music_box", "name": "Gilded Music Box", "true_value": 400_000},
        {
            "key": "cracked_chandelier",
            "name": "Cracked Chandelier",
            "true_value": 650_000,
        },
        {
            "key": "taxidermied_peacock",
            "name": "Taxidermied Peacock",
            "true_value": 300_000,
        },
        {"key": "ancient_wine", "name": '"Ancient" Wine', "true_value": 900_000},
        {
            "key": "ivory_walking_cane",
            "name": "Ivory Walking Cane",
            "true_value": 550_000,
        },
        {
            "key": "sealed_crate",
            "name": 'Crate: "DO NOT OPEN"',
            "true_value": 1_200_000,
        },
    ],
}

# ---------------------------------------------------------------------------
# Wealth tiers — sorted ascending by `min`; index doubles as tier_index everywhere.
# `attempts` is the baseline mastermind guesses granted to an attacker targeting
# this tier; `shield_hours` is the baseline post-success protection for the defender.
# ---------------------------------------------------------------------------

WEALTH_TIERS: list[dict] = [
    {"min": 0, "name": "Threadbare", "attempts": 17, "shield_hours": 4},
    {"min": 100_000, "name": "Modest", "attempts": 15, "shield_hours": 5},
    {"min": 1_000_000, "name": "Comfortable", "attempts": 13, "shield_hours": 6},
    {"min": 5_000_000, "name": "Affluent", "attempts": 11, "shield_hours": 7},
    {"min": 10_000_000, "name": "Wealthy", "attempts": 9, "shield_hours": 8},
    {"min": 50_000_000, "name": "Opulent", "attempts": 7, "shield_hours": 9},
    {"min": 100_000_000, "name": "Magnate", "attempts": 5, "shield_hours": 10},
]

# ---------------------------------------------------------------------------
# Mastery tree — shared Stash branch (cap/market-read) + Cutpurse (offense) + Strongbox (defense).
# Internal branch key stays "trunk" for backward compatibility with existing node grouping.
# Node shape mirrors core/slayer/mechanics.py:SLAYER_TREE_NODES.
# ---------------------------------------------------------------------------

NETHER_MARKET_NODES: dict[str, dict] = {
    # Shared trunk
    "trunk_cap_1": {
        "branch": "trunk",
        "name": "Bigger Pockets I",
        "cost": 5,
        "prereq": None,
        "desc": "+25 holdings cap",
    },
    "trunk_cap_2": {
        "branch": "trunk",
        "name": "Bigger Pockets II",
        "cost": 10,
        "prereq": "trunk_cap_1",
        "desc": "+25 holdings cap",
    },
    "trunk_cap_3": {
        "branch": "trunk",
        "name": "Bigger Pockets III",
        "cost": 20,
        "prereq": "trunk_cap_2",
        "desc": "+25 holdings cap",
    },
    "trunk_cap_4": {
        "branch": "trunk",
        "name": "Bigger Pockets IV",
        "cost": 35,
        "prereq": "trunk_cap_3",
        "desc": "+25 holdings cap",
    },
    "trunk_market_sense": {
        "branch": "trunk",
        "name": "Market Sense",
        "cost": 15,
        "prereq": None,
        "desc": "Reveals true value alongside listed price",
    },
    # Cutpurse (offense)
    "cp_attempts_1": {
        "branch": "cutpurse",
        "name": "Steady Hands I",
        "cost": 5,
        "prereq": None,
        "desc": "+2 attempts per session (as attacker)",
    },
    "cp_attempts_2": {
        "branch": "cutpurse",
        "name": "Steady Hands II",
        "cost": 15,
        "prereq": "cp_attempts_1",
        "desc": "+3 additional attempts per session (as attacker)",
    },
    "cp_regen_1": {
        "branch": "cutpurse",
        "name": "Quick Fingers I",
        "cost": 10,
        "prereq": None,
        "desc": "Charge regen 8h -> 6h",
    },
    "cp_regen_2": {
        "branch": "cutpurse",
        "name": "Quick Fingers II",
        "cost": 25,
        "prereq": "cp_regen_1",
        "desc": "Charge regen 6h -> 4h",
    },
    "cp_haul": {
        "branch": "cutpurse",
        "name": "Bigger Haul",
        "cost": 20,
        "prereq": "cp_attempts_1",
        "desc": "Plunder % ceiling raised from 30% to 40%",
    },
    # Strongbox (defense)
    "sb_defense_1": {
        "branch": "strongbox",
        "name": "Reinforced Lock I",
        "cost": 5,
        "prereq": None,
        "desc": "Attacker attempts -1 when you're the target",
    },
    "sb_defense_2": {
        "branch": "strongbox",
        "name": "Reinforced Lock II",
        "cost": 15,
        "prereq": "sb_defense_1",
        "desc": "Attacker attempts an additional -2 (total -3)",
    },
    "sb_shield_1": {
        "branch": "strongbox",
        "name": "Vigilant Ward I",
        "cost": 10,
        "prereq": None,
        "desc": "Shield duration +2h",
    },
    "sb_shield_2": {
        "branch": "strongbox",
        "name": "Vigilant Ward II",
        "cost": 25,
        "prereq": "sb_shield_1",
        "desc": "Shield duration +4h (total +6h)",
    },
    "sb_grip": {
        "branch": "strongbox",
        "name": "Tight Grip",
        "cost": 20,
        "prereq": "sb_defense_1",
        "desc": "Plunder % ceiling lowered to 20% when you're hit",
    },
}

# ---------------------------------------------------------------------------
# NPC vendors — one guaranteed target per tier T2-T7 (index 1-6), pre-teched with
# Strongbox-equivalent `attempt_reduction` so they're a real challenge at their tier.
# `reward_marks` is a flat Nether Mark payout on success; `reward_gold` is not
# paid directly — NetherMarketMechanics.build_npc_holdings() uses it to size a
# simulated item inventory (drawn from the server's active rotation) that gets
# plundered the same way a player's real holdings would (see plunder_view.py).
# ---------------------------------------------------------------------------

NPC_VENDORS: list[dict] = [
    {
        "key": "penny_loafer",
        "name": "Penny Loafer",
        "tier_index": 1,
        "flavor": "A jittery pawnbroker who never quite trusts the scale.",
        "attempt_reduction": 1,
        "reward_marks": 1,
        "reward_gold": 5_000,
        "thumbnail": NETHER_NPC_PENNY_LOAFER_THUMBNAIL,
    },
    {
        "key": "old_otto",
        "name": "Old Otto",
        "tier_index": 2,
        "flavor": 'Keeps his "good stuff" in a coat with too many pockets.',
        "attempt_reduction": 1,
        "reward_marks": 1,
        "reward_gold": 25_000,
        "thumbnail": NETHER_NPC_OLD_OTTO_THUMBNAIL,
    },
    {
        "key": "lady_fenwick",
        "name": "Lady Fenwick",
        "tier_index": 3,
        "flavor": "Collects curiosities purely to outbid rivals at auction.",
        "attempt_reduction": 2,
        "reward_marks": 1,
        "reward_gold": 100_000,
        "thumbnail": NETHER_NPC_LADY_FENWICK_THUMBNAIL,
    },
    {
        "key": "ironmonger",
        "name": "The Ironmonger",
        "tier_index": 4,
        "flavor": "Trades in bulk, trusts no one, counts everything twice.",
        "attempt_reduction": 2,
        "reward_marks": 1,
        "reward_gold": 400_000,
        "thumbnail": NETHER_NPC_IRONMONGER_THUMBNAIL,
    },
    {
        "key": "countess_vaelora",
        "name": "Countess Vaelora",
        "tier_index": 5,
        "flavor": "Buys things she'll never use, just to say she has them.",
        "attempt_reduction": 3,
        "reward_marks": 1,
        "reward_gold": 1_500_000,
        "thumbnail": NETHER_NPC_COUNTESS_VAELORA_THUMBNAIL,
    },
    {
        "key": "the_hoarder",
        "name": "The Hoarder",
        "tier_index": 6,
        "flavor": "Nobody's actually seen inside their vault.",
        "attempt_reduction": 3,
        "reward_marks": 1,
        "reward_gold": 5_000_000,
        "thumbnail": NETHER_NPC_THE_HOARDER_THUMBNAIL,
    },
]
