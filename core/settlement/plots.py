"""
core/settlement/plots.py — Plot layout constants, bonus table, meta-building
definitions, and pure helper functions for the settlement grid system.

Grid layout (5×5, corners excluded):
       col0   col1   col2   col3   col4
  row0  DEAD   P12    P13    P14   DEAD
  row1  P11    P02    P03    P04   P15
  row2  P10    P01    TH     P05   P16
  row3  P09    P08    P07    P06   P17
  row4  DEAD   P20    P19    P18   DEAD

Inner ring (P01–P08) surrounds the Town Hall clockwise starting left.
Outer ring (P09–P20) runs clockwise from the bottom-left corner.
Town Hall is fixed at (row=2, col=2) and is always treated as "developed"
for adjacency-gate purposes.
"""

from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# Grid geometry
# ---------------------------------------------------------------------------

TH_POSITION: tuple[int, int] = (2, 2)
DEAD_CORNERS: frozenset[tuple[int, int]] = frozenset({(0, 0), (0, 4), (4, 0), (4, 4)})

PLOT_POSITIONS: dict[int, tuple[int, int]] = {
    # Inner ring — clockwise from left of TH
    1:  (2, 1),  2:  (1, 1),  3:  (1, 2),  4:  (1, 3),
    5:  (2, 3),  6:  (3, 3),  7:  (3, 2),  8:  (3, 1),
    # Outer ring — clockwise from bottom-left
    9:  (3, 0), 10:  (2, 0), 11:  (1, 0), 12:  (0, 1),
   13:  (0, 2), 14:  (0, 3), 15:  (1, 4), 16:  (2, 4),
   17:  (3, 4), 18:  (4, 3), 19:  (4, 2), 20:  (4, 1),
}

# (row, col) → plot_index; 0 = Town Hall
POSITION_TO_PLOT: dict[tuple[int, int], int] = {
    pos: idx for idx, pos in PLOT_POSITIONS.items()
}
POSITION_TO_PLOT[TH_POSITION] = 0

# ---------------------------------------------------------------------------
# Building short codes (3 chars × 2 lines, shown inside the grid cells)
# Each tuple is (top_line, bot_line) — both exactly 3 ASCII characters.
# ---------------------------------------------------------------------------

BUILDING_CODES: dict[str, tuple[str, str]] = {
    "logging_camp":      ("LOG", "CMP"),
    "quarry":            ("QUA", "RRY"),
    "foundry":           ("FOU", "NDY"),
    "sawmill":           ("SAW", "MIL"),
    "reliquary":         ("REL", "QRY"),
    "market":            ("MAR", "KET"),
    "barracks":          ("BAR", "RCK"),
    "temple":            ("TEM", "PLE"),
    "apothecary":        ("APO", "ECY"),
    "black_market":      ("BLK", "MKT"),
    "companion_ranch":   ("COM", "RCH"),
    "hatchery":          ("HAT", "CHR"),
    "celestial_shrine":  ("CEL", "SHR"),
    "infernal_shrine":   ("INF", "SHR"),
    "void_shrine":       ("VOI", "SHR"),
    "twin_shrine":       ("TWN", "SHR"),
    "corruption_shrine": ("COR", "SHR"),
    "war_camp":          ("WAR", "CMP"),
    # Meta buildings
    "servants_quarters": ("SRV", "QTR"),
    "grand_cathedral":   ("GRD", "CTH"),
    "supply_depot":      ("SUP", "DPT"),
    "watchtower":        ("WAT", "TWR"),
    "foremans_post":     ("FOR", "PST"),
    "shrine_garden":     ("SHR", "GDN"),
    "encampment":        ("ENC", "AMP"),
    "apothecary_annex":  ("APO", "ANX"),
}

# 1:1 emoji mapping — used in the dashboard legend
BUILDING_EMOJIS: dict[str, str] = {
    "logging_camp":      "🪵",
    "quarry":            "🪨",
    "foundry":           "⚒️",
    "sawmill":           "🪚",
    "reliquary":         "🏺",
    "market":            "💰",
    "barracks":          "🛡️",
    "temple":            "⛪",
    "apothecary":        "⚗️",
    "black_market":      "🕵️",
    "companion_ranch":   "🐾",
    "hatchery":          "🐣",
    "celestial_shrine":  "✨",
    "infernal_shrine":   "🌋",
    "void_shrine":       "🔮",
    "twin_shrine":       "♊",
    "corruption_shrine": "☠️",
    "war_camp":          "⚔️",
    # Meta buildings
    "servants_quarters": "🏠",
    "grand_cathedral":   "🕍",
    "supply_depot":      "📦",
    "watchtower":        "🗼",
    "foremans_post":     "📋",
    "shrine_garden":     "🌺",
    "encampment":        "🏕️",
    "apothecary_annex":  "💊",
}

# Building types considered "shrines" for Grand Cathedral and Sacred Ground
SHRINE_BUILDING_TYPES: frozenset[str] = frozenset({
    "celestial_shrine", "infernal_shrine", "void_shrine", "twin_shrine",
    "corruption_shrine", "uber_shrine", "temple",
})

# ---------------------------------------------------------------------------
# Plot bonus table
# ---------------------------------------------------------------------------

PLOT_BONUS_TABLE: dict[str, dict] = {
    "fertile_ground": {
        "label": "Fertile Ground",
        "emoji": "🌿",
        "description": "Production buildings here are 10% more effective per worker.",
        "applies_to": "generator_mult",
        "value": 0.10,
    },
    "rich_seam": {
        "label": "Rich Seam",
        "emoji": "⛏️",
        "description": "Converter buildings here are 10% more effective per worker.",
        "applies_to": "converter_mult",
        "value": 0.10,
    },
    "sacred_ground": {
        "label": "Sacred Ground",
        "emoji": "✨",
        "description": "Shrine buildings here are 20% more effective.",
        "applies_to": "shrine_mult",
        "value": 0.20,
    },
    "gold_vein": {
        "label": "Gold Vein",
        "emoji": "💛",
        "description": "Buildings constructed here cost 35% less gold.",
        "applies_to": "construction_gold",
        "value": 0.35,
    },
    "bedrock": {
        "label": "Bedrock",
        "emoji": "🪨",
        "description": "The building here can hold 25% more workers per tier.",
        "applies_to": "worker_cap",
        "value": 0.25,
    },
    "trade_route": {
        "label": "Trade Route",
        "emoji": "🛤️",
        "description": "Market and War Camp output here is 20% greater.",
        "applies_to": "trade_mult",
        "value": 0.20,
    },
    "ancient_foundation": {
        "label": "Ancient Foundation",
        "emoji": "🏺",
        "description": "Buildings constructed here cost 30% fewer timber and stone.",
        "applies_to": "construction_materials",
        "value": 0.30,
    },
    "ley_line": {
        "label": "Ley Line",
        "emoji": "🔮",
        "description": "Adjacent meta-buildings provide 50% stronger adjacency bonuses.",
        "applies_to": "meta_amplifier",
        "value": 0.50,
    },
    "expedition_camp": {
        "label": "Expedition Camp",
        "emoji": "⛺",
        "description": "Generates 1 Development Contract every 48 hours.",
        "applies_to": "passive_dc",
        "value": 1.0,
    },
    "common_ground": {
        "label": "Common Ground",
        "emoji": "🟫",
        "description": "A plain plot with no special properties.",
        "applies_to": "none",
        "value": 0.0,
    },
}

# Weighted pool for bonus rolls
_BONUS_POOL: list[str] = (
    ["common_ground"]      * 30 +
    ["fertile_ground"]     * 12 +
    ["rich_seam"]          * 12 +
    ["bedrock"]            * 12 +
    ["gold_vein"]          *  8 +
    ["ancient_foundation"] *  8 +
    ["trade_route"]        *  5 +
    ["sacred_ground"]      *  5 +
    ["ley_line"]           *  5 +
    ["expedition_camp"]    *  3
)

# ---------------------------------------------------------------------------
# Meta-building definitions
# ---------------------------------------------------------------------------

META_BUILDINGS: dict[str, dict] = {
    "servants_quarters": {
        "label": "Servant's Quarters",
        "emoji": "🏠",
        "cost": {"gold": 15_000, "timber": 500, "stone": 500},
        "max_workers": 100,
        "description": (
            "Adjacent production buildings gain +2% effectiveness per 10 workers "
            "here, up to +20% at full capacity."
        ),
        "effect": "production_boost",
    },
    "grand_cathedral": {
        "label": "Grand Cathedral",
        "emoji": "⛪",
        "cost": {"gold": 75_000, "timber": 3_000, "stone": 3_000},
        "max_workers": 100,
        "description": (
            "Adjacent shrine buildings can have twice as many workers per tier."
        ),
        "effect": "shrine_cap",
    },
    "supply_depot": {
        "label": "Supply Depot",
        "emoji": "📦",
        "cost": {"gold": 25_000, "timber": 1_000, "stone": 1_000},
        "max_workers": 100,
        "description": (
            "Adjacent converter buildings are 15% more effective."
        ),
        "effect": "converter_boost",
    },
    "watchtower": {
        "label": "Watchtower",
        "emoji": "🗼",
        "cost": {"gold": 20_000, "timber": 800, "stone": 1_200},
        "max_workers": 0,
        "description": (
            "Each regular building's worker cap is increased by +1% per its own tier "
            "(T1 → +1%, T5 → +5%). Passive — no workers needed."
        ),
        "effect": "global_cap",
    },
    "foremans_post": {
        "label": "Foreman's Post",
        "emoji": "📋",
        "cost": {"gold": 30_000, "timber": 1_500, "stone": 500},
        "max_workers": 100,
        "description": "Adjacent buildings gain +25% output rate.",
        "effect": "output_boost",
    },
    "shrine_garden": {
        "label": "Shrine Garden",
        "emoji": "🌺",
        "cost": {"gold": 40_000, "timber": 2_000, "stone": 2_000},
        "max_workers": 100,
        "description": "Adjacent shrine buildings are 15% more effective.",
        "effect": "shrine_boost",
    },
    "encampment": {
        "label": "Encampment",
        "emoji": "🏕️",
        "cost": {"gold": 20_000, "timber": 1_000, "stone": 500},
        "max_workers": 100,
        "description": (
            "Adjacent War Camps generate +0.5 additional Combat Stamina "
            "per 100 War Camp workers/hr."
        ),
        "effect": "war_camp_boost",
    },
    "apothecary_annex": {
        "label": "Apothecary Annex",
        "emoji": "⚗️",
        "cost": {"gold": 35_000, "timber": 1_500, "stone": 1_500},
        "max_workers": 100,
        "description": (
            "Adjacent Apothecary gains +4% to its flat heal bonus "
            "per 100 workers assigned here."
        ),
        "effect": "apothecary_boost",
    },
}

# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def get_adjacent_plot_indices(plot_index: int) -> list[int]:
    """
    Returns all plot indices (0 = TH) orthogonally adjacent to *plot_index*.
    Dead corners are never returned.
    """
    row, col = PLOT_POSITIONS[plot_index]
    adjacent: list[int] = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        pos = (row + dr, col + dc)
        if pos in DEAD_CORNERS:
            continue
        if pos == TH_POSITION:
            adjacent.append(0)
        elif pos in POSITION_TO_PLOT:
            adjacent.append(POSITION_TO_PLOT[pos])
    return adjacent


def can_develop(plot_index: int, developed_indices: set[int]) -> bool:
    """
    A plot is developable when at least one orthogonal neighbour is already
    developed (TH = index 0 is always treated as developed).
    """
    for adj in get_adjacent_plot_indices(plot_index):
        if adj == 0 or adj in developed_indices:
            return True
    return False


def roll_plot_bonus() -> str:
    """Randomly selects a plot-bonus type from the weighted pool."""
    return random.choice(_BONUS_POOL)


def get_meta_slots(th_tier: int) -> int:
    """Number of meta buildings allowed, equal to the Town Hall tier (T1=1 … T7=7)."""
    return th_tier


def get_effective_max_workers(
    building_type: str,
    tier: int,
    plot_bonus_type: str | None,
    adj_shrine_cap_x2: bool,
    has_watchtower: bool,
) -> int:
    """
    Computes the effective max-worker cap incorporating plot bonuses and
    adjacency bonuses from meta buildings.

    Stacking order (additive first, then multiplicative):
      base           = 100 × tier
      additive       +=  25% if Bedrock
                     +=   1% × tier if Watchtower present globally
      multiplicative ×=   2 if Grand Cathedral adjacent AND shrine building
    """
    base = 100 * tier
    additive = 1.0
    if plot_bonus_type == "bedrock":
        additive += 0.25
    if has_watchtower:
        additive += 0.01 * tier
    result = int(base * additive)
    if adj_shrine_cap_x2 and building_type in SHRINE_BUILDING_TYPES:
        result *= 2
    return result


def render_grid(
    developed_indices: set[int],
    building_by_plot: dict[int, str],         # plot_index → building_type
    pending_by_plot: dict[int, str] | None = None,  # plot_index → building_type (queued, not yet built)
) -> str:
    """
    Renders the 5×5 settlement grid in a monospace code block.

    Each grid row produces TWO text lines; cell width is 3 columns
    (no padding — 3 ASCII content chars exactly).

      Dead corner   both lines: "   "
      Town Hall     top: "TWN"   bot: "HAL"
      Undeveloped   top: "LCK"   bot: "P##"   (e.g. "P01")
      Empty plot    top: "---"   bot: "P##"
      Building      top: TOP     bot: BOT     (from BUILDING_CODES tuple)
    """
    line_pairs: list[tuple[str, str]] = []
    for r in range(5):
        top_cells: list[str] = []
        bot_cells: list[str] = []
        for c in range(5):
            pos = (r, c)
            if pos in DEAD_CORNERS:
                top_cells.append("   ")
                bot_cells.append("   ")
            elif pos == TH_POSITION:
                top_cells.append("TWN")
                bot_cells.append("HAL")
            else:
                idx = POSITION_TO_PLOT[pos]
                if idx not in developed_indices:
                    top_cells.append("LCK")
                    bot_cells.append(f"P{idx:02d}")
                else:
                    b_type = building_by_plot.get(idx)
                    p_type = (pending_by_plot or {}).get(idx)
                    if b_type and b_type in BUILDING_CODES:
                        t, b = BUILDING_CODES[b_type]
                        top_cells.append(t)
                        bot_cells.append(b)
                    elif p_type:
                        # Under construction — top = CNS, bottom = target building code
                        _, bot_code = BUILDING_CODES.get(p_type, ("???", "???"))
                        top_cells.append("CNS")
                        bot_cells.append(bot_code)
                    else:
                        top_cells.append("---")
                        bot_cells.append(f"P{idx:02d}")
        line_pairs.append((
            "│" + "│".join(top_cells) + "│",
            "│" + "│".join(bot_cells) + "│",
        ))

    top = "┌───┬───┬───┬───┬───┐"
    sep = "├───┼───┼───┼───┼───┤"
    bot = "└───┴───┴───┴───┴───┘"

    lines = [top]
    for i, (top_line, bot_line) in enumerate(line_pairs):
        if i > 0:
            lines.append(sep)
        lines.append(top_line)
        lines.append(bot_line)
    lines.append(bot)

    return "```\n" + "\n".join(lines) + "\n```"
