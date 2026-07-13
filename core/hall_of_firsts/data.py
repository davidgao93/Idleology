"""core/hall_of_firsts/data.py — Category definitions for the Hall of Firsts.

Each entry is the single source of truth for a category's key, display name,
emoji, and flavor line. Thresholds referenced by these categories live in
core/hall_of_firsts/triggers.py, not here.
"""

from dataclasses import dataclass

# Channel the bot posts a celebratory announcement to whenever a category is claimed.
HALL_ANNOUNCE_CHANNEL_ID = 1521953415528316938


@dataclass(frozen=True)
class CategoryDef:
    key: str
    name: str
    emoji: str
    flavor: str


CATEGORIES: list[CategoryDef] = [
    CategoryDef(
        "absolute_cinema",
        "Absolute Cinema",
        "🎬",
        "First to clear the Rite of Convergence.",
    ),
    CategoryDef("nolife_andy", "Nolife Andy", "📈", "First to reach Level 100."),
    CategoryDef(
        "looksmaxxer", "Looksmaxxer", "💅", "First to purchase a Prestige avatar."
    ),
    CategoryDef(
        "really_board", "Really Board", "📋", "First to 300 lifetime quest completions."
    ),
    CategoryDef(
        "king", "King", "👑", "First to fully develop all 20 settlement plots."
    ),
    CategoryDef("mixologist", "Mixologist", "🧪", "First to reach Alchemy Level 5."),
    CategoryDef(
        "hunter_of_hunters",
        "Hunter of Hunters",
        "🗡️",
        "First to max out a Soul Stone (all 3 slots at tier 5).",
    ),
    CategoryDef("dang_yo", "Dang Yo", "🔨", "First weapon to reach 500 refinement."),
    CategoryDef(
        "all_in",
        "All In",
        "🎰",
        "First to win 1,000,000,000 gold in a single casino payout.",
    ),
    CategoryDef(
        "friends_with_benefits",
        "Friends with Benefits",
        "🤝",
        "First to a Level 100 Partner.",
    ),
    CategoryDef(
        "monster_tamer", "Monster Tamer", "🐾", "First to a Level 100 Companion."
    ),
    CategoryDef("peak", "Peak", "🏔️", "First to reach Ascent Floor 666."),
    CategoryDef("loremaster", "Loremaster", "📖", "First to 5 Tier 5 Codex Tomes."),
    CategoryDef(
        "fabulous",
        "Fabulous",
        "💁",
        "First to equip a monster part in the Cheeks slot.",
    ),
    CategoryDef(
        "the_trickster",
        "The Trickster",
        "🃏",
        "First to earn 100,000,000 gold from a single Nether Market sale.",
    ),
    CategoryDef(
        "cult_leader", "Cult Leader", "🕯️", "First ideology to reach 100,000 followers."
    ),
    CategoryDef(
        "one_with_nature",
        "One with Nature",
        "🌿",
        "First to max-tier pickaxe, fishing rod, and axe simultaneously.",
    ),
]

CATEGORIES_BY_KEY: dict[str, CategoryDef] = {c.key: c for c in CATEGORIES}
