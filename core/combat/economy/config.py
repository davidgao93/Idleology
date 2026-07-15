"""
core/combat/config.py — Centralised gameplay tuning constants for combat.

All drop rates, chance modifiers, and other numeric knobs live here so that
balance changes only require editing one file.  Import the constants you need
rather than hardcoding magic floats at the call site.
"""

# ---------------------------------------------------------------------------
# Defeat / XP loss
# ---------------------------------------------------------------------------

# Fraction of current XP lost on defeat (regular and uber encounters).
XP_LOSS_ON_DEFEAT: float = 0.10

# ---------------------------------------------------------------------------
# Pet / companion drops
# ---------------------------------------------------------------------------

# Boss-encounter pet drop probabilities.
BOSS_PET_CHANCE: float = 0.03
BOSS_PET_CHANCE_GEMINI_BOOT: float = 0.06  # Gemini boot corrupted essence doubles it

# Regular-encounter pet capture probabilities.
REGULAR_PET_CHANCE: float = 0.05
REGULAR_PET_CHANCE_GEMINI_BOOT: float = 0.10

# ---------------------------------------------------------------------------
# NEET boss drops
# ---------------------------------------------------------------------------

# Chance to drop a Void Key from the NEET boss encounter.
NEET_VOID_KEY_CHANCE: float = 0.30

# ---------------------------------------------------------------------------
# Uber boss drops (generic per-uber)
# ---------------------------------------------------------------------------

# Probability that an engram drops after any uber victory.
UBER_ENGRAM_CHANCE: float = 0.10

# Probability that a blueprint / stone drops after any uber victory.
UBER_BLUEPRINT_CHANCE: float = 0.10

# ---------------------------------------------------------------------------
# Evelynn (Mirage boss) unique drops
# ---------------------------------------------------------------------------

# Chance for an Imperfect Rune of Mirage (drops off Evelynn only).
EVELYNN_MIRAGE_RUNE_IMPERFECT_CHANCE: float = 0.01

# Chance for a Perfected Rune of Mirage (ultra-rare, Evelynn only).
EVELYNN_MIRAGE_RUNE_PERFECTED_CHANCE: float = 0.001

# ---------------------------------------------------------------------------
# Slayer emblem proc rates
# ---------------------------------------------------------------------------

# Per-tier chance for the Scavenger emblem passive to double slayer drops.
SLAYER_SCAVENGER_CHANCE_PER_TIER: float = 0.05

# Per-tier chance for the Taskmaster emblem passive to double task progress.
SLAYER_TASKMASTER_CHANCE_PER_TIER: float = 0.05

# ---------------------------------------------------------------------------
# Reward scaling — emblem find bonuses
# ---------------------------------------------------------------------------

# Multiplier added to XP and Gold rewards per tier of the xp_find / gold_find
# emblem passives. Both use the same per-tier rate.
EMBLEM_FIND_BONUS_PER_TIER: float = 0.03

# ---------------------------------------------------------------------------
# Lucifer boot — "Infernal Plunder" gold bonus
# ---------------------------------------------------------------------------

# Extra gold percentage granted per active monster modifier.
LUCIFER_BOOT_GOLD_PER_MODIFIER: float = 0.10

# Hard cap on the total Infernal Plunder bonus regardless of modifier count.
LUCIFER_BOOT_GOLD_CAP: float = 0.50

# ---------------------------------------------------------------------------
# Flora's Blessing — gold-to-skilling-materials conversion
# ---------------------------------------------------------------------------

# Fraction of earned gold converted to skilling materials per signature level.
FLORA_CONVERSION_PER_LEVEL: float = 0.10

# ---------------------------------------------------------------------------
# Special drop pool — applies to Body Parts, Eggs, Spirit Stones, Guild Tickets,
# and all level-gated material/key/rune drops.
# Formula: chance = base_rate + min(MODIFIER_DIFFICULTY_CAP, sum_difficulty)
#                              + player.get_special_drop_bonus() / 100
# ---------------------------------------------------------------------------

# Hard cap on the modifier-difficulty contribution to the special drop pool.
MODIFIER_DIFFICULTY_CAP: float = 0.08

# Generic base rate used by most special drops (magma core, runes, etc.)
SPECIAL_DROP_BASE_CHANCE: float = 0.01

# Drop-specific base rates that differ from the generic baseline.
SPIRIT_STONE_BASE_CHANCE: float = 0.01
SOUL_CORE_BASE_CHANCE: float = 0.04  # +2% from 0.03
VOID_FRAG_BASE_CHANCE: float = 0.02  # +2% from 0.02

# Boss key drop rates (each raised +2% from the generic SPECIAL_DROP_BASE_CHANCE baseline).
DRACONIC_KEY_BASE_CHANCE: float = 0.02
ANGELIC_KEY_BASE_CHANCE: float = 0.02
BALANCE_FRAG_BASE_CHANCE: float = 0.03

# Guild Ticket — drops without an active partner; requires a minimum level.
GUILD_TICKET_BASE_CHANCE: float = 0.01
GUILD_TICKET_MIN_LEVEL: int = 10

# Body part and egg base drop chances (also now boosted by modifier difficulty).
BODY_PART_BASE_CHANCE: float = 0.05
EGG_BASE_CHANCE: float = 0.05

# Corrupted essence selection chance (3 % of all essence drops are corrupted).
CORRUPTED_ESSENCE_CHANCE: float = 0.03

# Corrupted-monster additional drops.
CORRUPTED_PARADISE_JEWEL_CHANCE: float = 0.25
CORRUPTED_MIRAGE_RUNE_CHANCE: float = 0.0001

# Corrupted-monster encounter gate — unlocked at level 70. Base roll chance
# scales by level bracket, capping out at level 100+.
CORRUPTED_MIN_LEVEL: int = 70
CORRUPTED_BASE_CHANCE_BY_LEVEL: list[tuple[int, float]] = [
    (100, 0.03),
    (90, 0.015),
    (80, 0.01),
    (70, 0.005),
]


def get_corrupted_base_chance(level: int) -> float:
    """Base corrupted-encounter roll chance for a player's level (0 below CORRUPTED_MIN_LEVEL)."""
    for threshold, chance in CORRUPTED_BASE_CHANCE_BY_LEVEL:
        if level >= threshold:
            return chance
    return 0.0


# ---------------------------------------------------------------------------
# Boss / corruption sigil drops
# ---------------------------------------------------------------------------

# Flat chance for the first sigil on each named boss kill.
BOSS_SIGIL_FIRST_CHANCE: float = 0.50

# Bonus-second-sigil rate: workers * this * shrine_effectiveness.
# Used for both named bosses and corrupted monsters.
SIGIL_WORKER_MULTIPLIER: float = 0.0005

# ---------------------------------------------------------------------------
# Gold calculation
# ---------------------------------------------------------------------------

# Flat gold added to every reward after the rarity multiplier.
GOLD_BASE_FLAT: int = 88

# Buff applied directly to the base gold formula (before the rarity multiplier,
# flat bonus, and additive pool), so it compounds with rarity/emblems/procs
# instead of being a flat tack-on at the end.
GOLD_BASE_BUFF_PCT: float = 0.25

# Divisor used in the rarity multiplier: mult = 1 + sqrt(rarity) / denominator.
GOLD_RARITY_DENOMINATOR: float = 18.0

# Fraction of final gold added per point of stat_invest_gold.
STAT_INVEST_GOLD_PER_POINT: float = 0.001

# ---------------------------------------------------------------------------
# Gear item drop thresholds
# ---------------------------------------------------------------------------

GEAR_DROP_BASE_CHANCE: float = 15.0  # % floor for any rarity
GEAR_DROP_MAX_BONUS: float = 20.0  # % maximum bonus achievable via rarity
GEAR_DROP_SCALING_CONSTANT: float = 1000.0  # rarity value at which bonus = half max

# ---------------------------------------------------------------------------
# Accessory passive proc rates
# ---------------------------------------------------------------------------

# Chance per passive level for Prosper to grant +100 % gold.
PROSPER_CHANCE_PER_LEVEL: float = 0.10

# Chance per passive level for Infinite Wisdom to grant +100 % XP.
INFINITE_WISDOM_CHANCE_PER_LEVEL: float = 0.05

# ---------------------------------------------------------------------------
# Partner combat skill rates
# ---------------------------------------------------------------------------

# XP / gold bonus per skill level of the co_xp_boost / co_gold_boost skills.
CO_XP_BOOST_PER_LEVEL: float = 0.05
CO_GOLD_BOOST_PER_LEVEL: float = 0.05

# ---------------------------------------------------------------------------
# Gear stat soft-caps per equipment slot
# (get_scaled_stat approaches these asymptotically — never literally reached)
# ---------------------------------------------------------------------------

WEAPON_STAT_CAPS: dict = {"attack": 80, "defence": 80, "rarity": 200}
ACC_STAT_CAPS: dict = {
    "attack": 80,
    "defence": 80,
    "rarity": 200,
    "ward": 60,
    "crit": 20,
}
ARMOR_STAT_CAPS: dict = {
    "block": 50,
    "evasion": 50,
    "ward": 100,
    "pdr": 40,
    "fdr": 80,
    "main_stat": 60,
}
GLOVE_STAT_CAPS: dict = {"attack": 80, "defence": 80, "ward": 100, "pdr": 15, "fdr": 50}
BOOT_STAT_CAPS: dict = {"attack": 80, "defence": 80, "ward": 100, "pdr": 15, "fdr": 50}
HELM_STAT_CAPS: dict = {"defence": 40, "ward": 80, "pdr": 15, "fdr": 50}

# ---------------------------------------------------------------------------
# Weapon stat roll chances (integer percent)
# ---------------------------------------------------------------------------

WEAPON_ATTACK_ROLL_CHANCE: int = 80
WEAPON_DEFENCE_ROLL_CHANCE: int = 50
WEAPON_RARITY_ROLL_CHANCE: int = 20
