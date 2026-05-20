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
