"""Run-completion rewards for The Rite of Convergence.

Base (non-artefact) loot reuses the Black Market's hidden-value roll
pipeline verbatim — a flat value scaled by excess Devotion Points is turned
into itemized rewards via the same code path an instant Black Market deal
uses (core/settlement/turn_engine.py: complete_bm_deal_instant).
"""

import random

from core.images import (
    ARTEFACT_BLESSED_BULWARK,
    ARTEFACT_BRAND_OF_RUIN,
    ARTEFACT_CORRUPTED_INSIGNIA,
    ARTEFACT_SAD_ONES_GAMBLE,
    ARTEFACT_THE_FINAL_EDICT,
    MONSTER_GEMINI_REBORN,
)
from core.settlement.turn_engine import complete_bm_deal_instant

BASE_LOOT_VALUE = 300_000

ARTEFACT_TIER_1_DP = 60
ARTEFACT_TIER_2_DP = 130
ARTEFACT_TIER_3_DP = 350

# RAID-DESIGN.md doesn't specify an overall "does an artefact drop at all"
# chance — only the relative weights BETWEEN artefacts once eligible. This
# flat per-run chance is a placeholder pending real balance/playtesting
# (see RAID-DESIGN.md's "Non-artefact loot distribution" TBD note).
ARTEFACT_DROP_CHANCE = 0.20

# key -> (display name, thematic source, dp required to enter the pool, weight, image)
# NOTE: Seal of Duality has no dedicated artefact asset yet — falls back to
# MONSTER_GEMINI_REBORN until one is provided.
ARTEFACT_TABLE: dict[str, tuple[str, str, int, int, str]] = {
    "blessed_bulwark": ("Blessed Bulwark", "Aphrodite", ARTEFACT_TIER_1_DP, 25, ARTEFACT_BLESSED_BULWARK),
    "brand_of_ruin": ("Brand of Ruin", "Lucifer", ARTEFACT_TIER_1_DP, 25, ARTEFACT_BRAND_OF_RUIN),
    "seal_of_duality": ("Seal of Duality", "Gemini", ARTEFACT_TIER_1_DP, 25, MONSTER_GEMINI_REBORN),
    "sad_ones_gamble": ("Sad One's Gamble", "NEET", ARTEFACT_TIER_2_DP, 10, ARTEFACT_SAD_ONES_GAMBLE),
    "corrupted_insignia": ("Corrupted Insignia", "Evelynn", ARTEFACT_TIER_2_DP, 10, ARTEFACT_CORRUPTED_INSIGNIA),
    "the_final_edict": ("The Final Edict", "Arbiter", ARTEFACT_TIER_3_DP, 5, ARTEFACT_THE_FINAL_EDICT),
}


def excess_dp_bonus_pct(total_dp: int) -> float:
    """% bonus to non-artefact loot value from DP above 350, capped at 65%."""
    if total_dp <= 350:
        return 0.0
    return min(65.0, (total_dp - 350) / 10)


def effective_loot_value(total_dp: int) -> int:
    return int(BASE_LOOT_VALUE * (1 + excess_dp_bonus_pct(total_dp) / 100))


def roll_artefact_key(total_dp: int) -> str | None:
    """Rolls whether an artefact drops and, if so, which one — weighted among
    whatever tiers `total_dp` has unlocked. Returns None on no drop."""
    eligible = [
        (key, weight)
        for key, (_name, _source, req_dp, weight, _image) in ARTEFACT_TABLE.items()
        if total_dp >= req_dp
    ]
    if not eligible or random.random() > ARTEFACT_DROP_CHANCE:
        return None
    keys, weights = zip(*eligible)
    return random.choices(keys, weights=weights, k=1)[0]


def roll_artefact_stats(key: str) -> tuple[float, float, float]:
    """Rolls the randomized stat value(s) for a freshly-dropped artefact.
    Unused rolls stay 0.0. Ranges are taken directly from RAID-DESIGN.md."""
    if key == "blessed_bulwark":
        return (float(random.randint(2, 8)), 0.0, 0.0)  # PDR cap +2-8%
    if key == "brand_of_ruin":
        return (float(random.randint(15, 30)), 0.0, 0.0)  # infernal passive +15-30%
    if key == "seal_of_duality":
        return (float(random.randint(15, 35)), 0.0, 0.0)  # DEF +15-35% on ward break
    if key == "the_final_edict":
        return (float(random.randint(80, 100)), 0.0, 0.0)  # true damage chance 80-100%
    # sad_ones_gamble / corrupted_insignia have no variable roll
    return (0.0, 0.0, 0.0)


def describe_artefact(key: str, roll_1: float) -> str:
    """Human-readable effect description for the /artefact command, including
    the rolled value where relevant."""
    if key == "blessed_bulwark":
        return f"PDR cap increased by {int(roll_1)}%. Cannot be lowered in combat."
    if key == "brand_of_ruin":
        return f"Your weapon's infernal passive is {int(roll_1)}% stronger."
    if key == "seal_of_duality":
        return f"On ward break: gain DEF +{int(roll_1)}% for the remainder of combat."
    if key == "sad_ones_gamble":
        return (
            "Start of combat: roll a d6. 2-5: Unlucky effects become Lucky. "
            "6: also, Lucky effects roll 3x instead of twice. 1: no effect."
        )
    if key == "corrupted_insignia":
        return "On crit: 50% chance for on-hit-only passives to also apply."
    if key == "the_final_edict":
        return f"On hit: {int(roll_1)}% chance for the whole hit to become true damage."
    return "Unknown artefact."


async def grant_run_completion_rewards(
    bot, user_id: str, server_id: str, player, total_dp: int
) -> dict:
    """Grants the base loot payout for a completed Rite run and, if eligible,
    rolls + equips a new Artefact. Returns a summary dict for the victory screen."""
    value = effective_loot_value(total_dp)
    bm_rewards = await complete_bm_deal_instant(
        bot,
        user_id,
        server_id,
        value,
        active_biases=[],
        player_level=player.level,
        tree_nodes={},
    )

    artefact_key = roll_artefact_key(total_dp)
    artefact_name = None
    artefact_image = None
    if artefact_key:
        roll_1, roll_2, roll_3 = roll_artefact_stats(artefact_key)
        await bot.database.rite.set_artefact(
            user_id, server_id, artefact_key, roll_1, roll_2, roll_3
        )
        artefact_name = ARTEFACT_TABLE[artefact_key][0]
        artefact_image = ARTEFACT_TABLE[artefact_key][4]

    return {
        "value": value,
        "excess_dp_bonus_pct": excess_dp_bonus_pct(total_dp),
        "bm_rewards": bm_rewards,
        "artefact_key": artefact_key,
        "artefact_name": artefact_name,
        "artefact_image": artefact_image,
    }
