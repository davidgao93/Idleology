"""
core/settlement/plots.py — Plot layout constants, bonus table, meta-building
definitions, and pure helper functions for the settlement grid system.

Grid layout (5×5, corners excluded):
       col0   col1   col2   col3   col4
  row0  DEAD   P01    P02    P03   DEAD
  row1  P04    P05    P06    P07   P08
  row2  P09    P10    TH     P11   P12
  row3  P13    P14    P15    P16   P17
  row4  DEAD   P18    P19    P20   DEAD

Town Hall is fixed at (row=2, col=2) and is always treated as "developed"
for adjacency-gate purposes.  Plots are numbered 1-20 in reading order
skipping the TH cell and all four dead corners.
"""

from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# Grid geometry
# ---------------------------------------------------------------------------

TH_POSITION: tuple[int, int] = (2, 2)
DEAD_CORNERS: frozenset[tuple[int, int]] = frozenset({(0, 0), (0, 4), (4, 0), (4, 4)})

PLOT_POSITIONS: dict[int, tuple[int, int]] = {
    1:  (0, 1),  2:  (0, 2),  3:  (0, 3),
    4:  (1, 0),  5:  (1, 1),  6:  (1, 2),  7:  (1, 3),  8:  (1, 4),
    9:  (2, 0), 10:  (2, 1),             11:  (2, 3), 12:  (2, 4),
   13:  (3, 0), 14:  (3, 1), 15:  (3, 2), 16:  (3, 3), 17:  (3, 4),
   18:  (4, 1), 19:  (4, 2), 20:  (4, 3),
}

# (row, col) → plot_index; 0 = Town Hall
POSITION_TO_PLOT: dict[tuple[int, int], int] = {
    pos: idx for idx, pos in PLOT_POSITIONS.items()
}
POSITION_TO_PLOT[TH_POSITION] = 0

# ---------------------------------------------------------------------------
# Building short codes (2 chars, shown inside the grid cells)
# ---------------------------------------------------------------------------

BUILDING_CODES: dict[str, str] = {
    "logging_camp":     "LC",
    "quarry":           "QY",
    "foundry":          "FD",
    "sawmill":          "SM",
    "reliquary":        "RQ",
    "market":           "MK",
    "barracks":         "BK",
    "temple":           "TP",
    "apothecary":       "AP",
    "black_market":     "BM",
    "companion_ranch":  "CR",
    "hatchery":         "HT",
    "celestial_shrine": "CS",
    "infernal_shrine":  "IS",
    "void_shrine":      "VS",
    "twin_shrine":      "TS",
    "war_camp":         "WC",
    # Meta buildings
    "servants_quarters": "SQ",
    "grand_cathedral":   "GC",
    "supply_depot":      "SD",
    "watchtower":        "WT",
    "foremans_post":     "FP",
    "shrine_garden":     "SG",
    "encampment":        "EC",
    "apothecary_annex":  "AA",
}

# Building types considered "shrines" for Grand Cathedral and Sacred Ground
SHRINE_BUILDING_TYPES: frozenset[str] = frozenset({
    "celestial_shrine", "infernal_shrine", "void_shrine", "twin_shrine", "temple",
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
            "Adjacent production buildings gain +1% effectiveness per 10 workers "
            "here (max +20%)."
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
            "Adjacent converter buildings are 15% more effective per worker."
        ),
        "effect": "converter_boost",
    },
    "watchtower": {
        "label": "Watchtower",
        "emoji": "🗼",
        "cost": {"gold": 20_000, "timber": 800, "stone": 1_200},
        "max_workers": 0,
        "description": (
            "All buildings gain +1% max worker cap per tier. "
            "Passive — no workers needed."
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
            "Adjacent War Camps generate +0.005 additional stamina per "
            "worker per hour."
        ),
        "effect": "war_camp_boost",
    },
    "apothecary_annex": {
        "label": "Apothecary Annex",
        "emoji": "⚗️",
        "cost": {"gold": 35_000, "timber": 1_500, "stone": 1_500},
        "max_workers": 100,
        "description": (
            "Adjacent Apothecary gains +0.04% additional healing per "
            "worker assigned here."
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
    building_by_plot: dict[int, str],   # plot_index → building_type
) -> str:
    """
    Renders the 5×5 settlement grid as a monospace string suitable for a
    Discord code block.

    Cell legend (4 chars each):
      "    "   dead corner
      " TH "   Town Hall (centre)
      " 01 "   undeveloped plot (shows number)
      " ·· "   developed, empty
      " LC "   developed with building (2-char code)
    """
    rows: list[str] = []
    for r in range(5):
        cells: list[str] = []
        for c in range(5):
            pos = (r, c)
            if pos in DEAD_CORNERS:
                cells.append("    ")
            elif pos == TH_POSITION:
                cells.append(" TH ")
            else:
                idx = POSITION_TO_PLOT[pos]
                if idx not in developed_indices:
                    cells.append(f" {idx:02d} ")
                else:
                    b_type = building_by_plot.get(idx)
                    if b_type:
                        code = BUILDING_CODES.get(b_type, "??")
                        cells.append(f" {code} ")
                    else:
                        cells.append(" ·· ")
        rows.append("│" + "│".join(cells) + "│")

    sep = "├────┼────┼────┼────┼────┤"
    top = "┌────┬────┬────┬────┬────┐"
    bot = "└────┴────┴────┴────┴────┘"
    return "```\n" + top + "\n" + f"\n{sep}\n".join(rows) + "\n" + bot + "\n```"
