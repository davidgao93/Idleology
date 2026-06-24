"""
Artisan Mastery (Gathering Mastery) system — stateless helpers.

All numbers and node effects are locked per docs/design/gathering_mastery.md + expansions.
Pure functions + data only. No I/O, no Discord.

Features:
- 3 per-skill trees (Yield/Quality/Synergy) + 10 bonus pts per branch after capstone
- Nature's Attunement (cross-skill tree: 3 nodes x 5 pts, gate = 20 invested in each main tree)
- Mastery Insight (post-max infinite scaling: 5 excess pts -> 1 insight)
- Prestige gathering bosses, triple-tick consumption, Free Yourself snare, Rune of Nature
"""

from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Literal, Tuple

SkillType = Literal["mining", "fishing", "woodcutting"]
Branch = Literal["yield", "quality", "synergy"]

# =========================================================
# Locked Point Economy (design 5 + 8.5)
# =========================================================
TOOL_POINT_RATES = {
    # mining
    "iron": 0.6,
    "steel": 0.9,
    "gold": 1.2,
    "platinum": 1.5,
    "ideal": 1.8,
    # fishing
    "desiccated": 0.6,
    "regular": 0.9,
    "sturdy": 1.2,
    "reinforced": 1.5,
    "titanium": 1.8,
    # woodcutting
    "flimsy": 0.6,
    "carved": 0.9,
    "chopping": 1.2,
    "magic": 1.5,
    "felling": 1.8,
}

DAILY_POINTS_AT_BIS = 1.8
CATCHUP_HOURS = 24

# Rune crafting (locked)
RUNE_CRAFT_COST = {
    "geode_cores": 68,
    "tide_relics": 68,
    "heartwood_shards": 68,
    "gold": 350_000,
    "spirit_stones": 2,
}

# Black Market exchange (locked)
BLACK_MARKET_REMNANT_COST = 55  # any mix or single type

# Remnant generation (Quality branch)
REMNANT_BASELINE_CHANCE = 0.055  # 5.5%
RICH_REMNANT_GUARANTEED_AVG = 4.0

# =========================================================
# Node Definitions (exact locked tables from design 8.1-8.3)
# Structure: node_key -> {cost, effect, desc, req_branch_pts (optional)}
# =========================================================

MINING_TREE: Dict[str, Dict[str, Any]] = {
    # Yield (Deep Veins)
    "enduring_veins": {
        "branch": "yield",
        "cost": 1,
        "desc": "+8% ore yield from passive hourly ticks.",
    },
    "bountiful_veins": {
        "branch": "yield",
        "cost": 2,
        "desc": "+16% total ore yield from passive hourly ticks.",
        "requires": ["enduring_veins"],
    },
    "motherlode": {
        "branch": "yield",
        "cost": 5,
        "desc": "+26% total ore yield from passive hourly ticks.",
        "requires": ["bountiful_veins"],
    },
    "never_empty": {
        "branch": "yield",
        "cost": 4,
        "desc": "Each passive tick has a 12% chance to yield an extra 70% resources.",
        "requires_branch_pts": 9,
    },
    # Quality (Vein Memory)
    "ideal_seeker": {
        "branch": "quality",
        "cost": 1,
        "desc": "+20% Idea Ore yield from passive hourly ticks.",
    },
    "crystallized_insight": {
        "branch": "quality",
        "cost": 2,
        "desc": "+38% total Idea Ore yield. Lower-tier pickaxes gain a 6% chance to produce Idea Ore.",
        "requires": ["ideal_seeker"],
    },
    "geode_cores": {
        "branch": "quality",
        "cost": 3,
        "desc": "Unlocks Geode Core remnants: 5.5% drop chance per tick (1–2 each). Enables Rich Vein events (4% chance per tick): 2.6× yield plus 3–5 Geode Cores guaranteed.",
    },
    "worldcore_resonance": {
        "branch": "quality",
        "cost": 5,
        "desc": "Rich Vein events now trigger at 22% per tick (up from 4%). On trigger: 2.6× yield and 3–5 Geode Cores guaranteed.",
        "requires": ["geode_cores"],
    },
    # Synergy (Stonebound Mastery)
    "tool_resonance": {
        "branch": "synergy",
        "cost": 1,
        "desc": "Mining tool upgrade costs reduced by 12%.",
    },
    "skilled_hands": {
        "branch": "synergy",
        "cost": 2,
        "desc": "Skiller boot procs are 65% more likely and yield 45% more resources.",
    },
    "master_quarry": {
        "branch": "synergy",
        "cost": 3,
        "desc": "+10% output from all ore smelting.",
    },
    "living_mountain": {
        "branch": "synergy",
        "cost": 5,
        "desc": "+55% Idea Ore yield from passive ticks. Also provides an independent 3% Rich Vein chance per tick.",
        "requires": ["master_quarry"],
    },
    "echo_first_vein": {
        "branch": "synergy",
        "cost": 8,
        "desc": "Prestige Capstone: the Meridian Golem treasure boss may appear during combat.",
        "requires": ["living_mountain"],
    },
}

FISHING_TREE: Dict[str, Dict[str, Any]] = {
    # Yield (Patient Waters) — symmetric
    "patient_waters": {
        "branch": "yield",
        "cost": 1,
        "desc": "+8% bone yield from passive hourly ticks.",
    },
    "abundant_catch": {
        "branch": "yield",
        "cost": 2,
        "desc": "+16% total bone yield from passive hourly ticks.",
        "requires": ["patient_waters"],
    },
    "bountiful_haul": {
        "branch": "yield",
        "cost": 5,
        "desc": "+26% total bone yield from passive hourly ticks.",
        "requires": ["abundant_catch"],
    },
    "never_empty_nets": {
        "branch": "yield",
        "cost": 4,
        "desc": "12% chance per passive tick for +70% extra resources that tick.",
        "requires_branch_pts": 9,
    },
    # Quality (Abyssal Memory)
    "tide_seeker": {
        "branch": "quality",
        "cost": 1,
        "desc": "+20% Titanium Bones yield from passive hourly ticks.",
    },
    "abyssal_memory": {
        "branch": "quality",
        "cost": 2,
        "desc": "+38% total Titanium Bones yield. Lower-tier rods gain a 6% chance to produce Titanium Bones.",
        "requires": ["tide_seeker"],
    },
    "tide_relics": {
        "branch": "quality",
        "cost": 3,
        "desc": "Unlocks Tide Relic remnants: 5.5% drop chance per tick (1–2 each). Enables Rich Catch events (4% chance per tick): 2.6× yield plus 3–5 Tide Relics guaranteed.",
    },
    "deep_current_resonance": {
        "branch": "quality",
        "cost": 5,
        "desc": "Rich Catch events now trigger at 22% per tick (up from 4%). On trigger: 2.6× yield and 3–5 Tide Relics guaranteed.",
        "requires": ["tide_relics"],
    },
    # Synergy (Tidebound Mastery)
    "lighter_bait": {
        "branch": "synergy",
        "cost": 1,
        "desc": "Bait cost reduced by 12%.",
    },
    "favored_currents": {
        "branch": "synergy",
        "cost": 2,
        "desc": "Skiller boot procs are 65% more likely and yield 45% more resources.",
    },
    "master_baiter": {
        "branch": "synergy",
        "cost": 3,
        "desc": "Alchemy conversions use one step better transmutation ratios.",
    },
    "old_ones_favor": {
        "branch": "synergy",
        "cost": 5,
        "desc": "+55% Titanium Bones yield from passive ticks. Also provides an independent 3% Rich Catch chance per tick.",
        "requires": ["master_baiter"],
    },
    "lord_of_the_deep": {
        "branch": "synergy",
        "cost": 8,
        "desc": "Prestige Capstone: the Drowned Leviathan treasure boss may appear during combat.",
        "requires": ["old_ones_favor"],
    },
}

WOODCUTTING_TREE: Dict[str, Dict[str, Any]] = {
    # Yield (Strong Arm)
    "strong_arm": {
        "branch": "yield",
        "cost": 1,
        "desc": "+8% log yield from passive hourly ticks.",
    },
    "mighty_swing": {
        "branch": "yield",
        "cost": 2,
        "desc": "+16% total log yield from passive hourly ticks.",
        "requires": ["strong_arm"],
    },
    "titanic_felling": {
        "branch": "yield",
        "cost": 5,
        "desc": "+26% total log yield from passive hourly ticks.",
        "requires": ["mighty_swing"],
    },
    "forest_bounty": {
        "branch": "yield",
        "cost": 4,
        "desc": "12% chance per passive tick for +70% extra resources that tick.",
        "requires_branch_pts": 9,
    },
    # Quality (Heartwood Memory)
    "heartwood_seeker": {
        "branch": "quality",
        "cost": 1,
        "desc": "+20% Idea Log yield from passive hourly ticks.",
    },
    "living_heartwood": {
        "branch": "quality",
        "cost": 2,
        "desc": "+38% total Idea Log yield. Lower-tier axes gain a 6% chance to produce Idea Logs.",
        "requires": ["heartwood_seeker"],
    },
    "heartwood_shards": {
        "branch": "quality",
        "cost": 3,
        "desc": "Unlocks Heartwood Shard remnants: 5.5% drop chance per tick (1–2 each). Enables Rich Felling events (4% chance per tick): 2.6× yield plus 3–5 Heartwood Shards guaranteed.",
    },
    "elder_resonance": {
        "branch": "quality",
        "cost": 5,
        "desc": "Rich Felling events now trigger at 22% per tick (up from 4%). On trigger: 2.6× yield and 3–5 Heartwood Shards guaranteed.",
        "requires": ["heartwood_shards"],
    },
    # Synergy (Rootbound Mastery)
    "foresters_eye": {
        "branch": "synergy",
        "cost": 1,
        "desc": "Forestry pass cost reduced by 12%.",
    },
    "skilled_forester": {
        "branch": "synergy",
        "cost": 2,
        "desc": "Skiller boot procs are 65% more likely and yield 45% more resources.",
    },
    "seasoned_timber": {
        "branch": "synergy",
        "cost": 3,
        "desc": "+10% output from all wood conversion.",
    },
    "forest_remembers": {
        "branch": "synergy",
        "cost": 5,
        "desc": "+55% Idea Log yield from passive ticks. Also provides an independent 3% Rich Felling chance per tick.",
        "requires": ["seasoned_timber"],
    },
    "elderheart": {
        "branch": "synergy",
        "cost": 8,
        "desc": "Prestige Capstone: the Verdant Colossus treasure boss may appear during combat.",
        "requires": ["forest_remembers"],
    },
}

ALL_TREES = {
    "mining": MINING_TREE,
    "fishing": FISHING_TREE,
    "woodcutting": WOODCUTTING_TREE,
}

# =========================================================
# Nature's Attunement (Cross-Skill Tree)
# Unlocked only after >= 20 total invested points in EACH main tree
# (including the +10 bonus investment per branch).
# Players may freely allocate points into any unlocked node (no sequential branches).
# Max 15 points total (3 nodes x 5 pts).
# =========================================================

NATURE_ATTUNEMENT_TREE: Dict[str, Dict[str, Any]] = {
    "elemental_resonance_plus": {
        "cost": 5,
        "label": "Elemental Resonance+",
        "desc": "Per point invested, +1% chance for a Rune of Nature to drop from the Elemental of Elements encounter.",
    },
    "druidic_ritual": {
        "cost": 5,
        "label": "Druidic Ritual",
        "desc": "Per point invested, +1% bonus material when performing Alchemy conversions/transmutations.",
    },
    "groves_reckoning": {
        "cost": 5,
        "label": "Grove's Reckoning",
        "desc": "Per point invested, gain +1 additional tripled tick when harvesting a prestige gathering boss (Golem / Leviathan / Colossus).",
    },
}

NATURE_ATTUNEMENT_NODE_ORDER = [
    "elemental_resonance_plus",
    "druidic_ritual",
    "groves_reckoning",
]  # for display only

# =========================================================
# Post-Max Infinite Scaling — Mastery Insight
# Every 5 excess artisan points (summed across skills, after everything is maxed)
# converts into 1 Mastery Insight. Insight gives tiny, permanent, global bonuses.
# =========================================================

INSIGHT_CONVERSION_RATE = 5  # excess points per insight

# Gentle caps / scaling chosen for long-term play (no combat power)
MAX_INSIGHT_EFFECT = 100  # soft display cap; math continues linearly if desired


def get_insight_global_yield_bonus(insight: int) -> float:
    """+0.2% global gathering yield per insight (very gentle)."""
    return min(insight * 0.002, MAX_INSIGHT_EFFECT * 0.002)


def get_insight_remnant_bonus(insight: int) -> float:
    """+0.5% extra remnant chance on prestige boss harvests per insight."""
    return min(insight * 0.005, MAX_INSIGHT_EFFECT * 0.005)


def get_insight_rune_bonus(insight: int) -> float:
    """+0.25% additional Rune of Nature drop chance from Elemental of Elements per insight."""
    return min(insight * 0.0025, MAX_INSIGHT_EFFECT * 0.0025)


# =========================================================
# Branch node unlock order (sequential)
# Used for the new "invest in branch" model.
# Nodes unlock in the order listed here as investment accumulates.
# =========================================================

BRANCH_NODE_ORDERS = {
    "mining": {
        "yield": ["enduring_veins", "bountiful_veins", "motherlode", "never_empty"],
        "quality": [
            "ideal_seeker",
            "crystallized_insight",
            "geode_cores",
            "worldcore_resonance",
        ],
        "synergy": [
            "tool_resonance",
            "skilled_hands",
            "master_quarry",
            "living_mountain",
            "echo_first_vein",
        ],
    },
    "fishing": {
        "yield": [
            "patient_waters",
            "abundant_catch",
            "bountiful_haul",
            "never_empty_nets",
        ],
        "quality": [
            "tide_seeker",
            "abyssal_memory",
            "tide_relics",
            "deep_current_resonance",
        ],
        "synergy": [
            "lighter_bait",
            "favored_currents",
            "master_baiter",
            "old_ones_favor",
            "lord_of_the_deep",
        ],
    },
    "woodcutting": {
        "yield": ["strong_arm", "mighty_swing", "titanic_felling", "forest_bounty"],
        "quality": [
            "heartwood_seeker",
            "living_heartwood",
            "heartwood_shards",
            "elder_resonance",
        ],
        "synergy": [
            "foresters_eye",
            "skilled_forester",
            "seasoned_timber",
            "forest_remembers",
            "elderheart",
        ],
    },
}

# Node key -> human label for UI
NODE_LABELS = {
    # mining
    "enduring_veins": "Enduring Veins",
    "bountiful_veins": "Bountiful Veins",
    "motherlode": "Motherlode",
    "never_empty": "Never Empty",
    "ideal_seeker": "Ideal Seeker",
    "crystallized_insight": "Crystallized Insight",
    "geode_cores": "Geode Cores",
    "worldcore_resonance": "Worldcore Resonance",
    "tool_resonance": "Tool Resonance",
    "skilled_hands": "Skilled Hands",
    "master_quarry": "Master Quarry",
    "living_mountain": "Living Mountain",
    "echo_first_vein": "Echo of the First Vein",
    # fishing
    "patient_waters": "Patient Waters",
    "abundant_catch": "Abundant Catch",
    "bountiful_haul": "Bountiful Haul",
    "never_empty_nets": "Never-Empty Nets",
    "tide_seeker": "Tide Seeker",
    "abyssal_memory": "Abyssal Memory",
    "tide_relics": "Tide Relics",
    "deep_current_resonance": "Deep Current Resonance",
    "lighter_bait": "Lighter Bait",
    "favored_currents": "Favored by the Currents",
    "master_baiter": "Master Baiter",
    "old_ones_favor": "The Old One's Favor",
    "lord_of_the_deep": "Lord of the Deep",
    # woodcutting
    "strong_arm": "Strong Arm",
    "mighty_swing": "Mighty Swing",
    "titanic_felling": "Titanic Felling",
    "forest_bounty": "Forest's Bounty",
    "heartwood_seeker": "Heartwood Seeker",
    "living_heartwood": "Living Heartwood",
    "heartwood_shards": "Heartwood Shards",
    "elder_resonance": "Elder Resonance",
    "foresters_eye": "Forester's Eye",
    "skilled_forester": "Skilled Forester",
    "seasoned_timber": "Seasoned Timber",
    "forest_remembers": "The Forest Remembers",
    "elderheart": "Elderheart",
}

# =========================================================
# Core Helpers
# =========================================================


def get_tree(skill: SkillType) -> Dict[str, Dict[str, Any]]:
    return ALL_TREES[skill]


def get_node(skill: SkillType, node_key: str) -> Dict[str, Any] | None:
    return ALL_TREES[skill].get(node_key)


def get_branch_nodes(skill: SkillType, branch: Branch) -> List[str]:
    return [k for k, v in ALL_TREES[skill].items() if v["branch"] == branch]


def calculate_branch_points_spent(
    alloc: Dict[str, List[str]], branch: Branch, skill: SkillType
) -> int:
    """Sum costs of purchased nodes in one branch."""
    tree = ALL_TREES[skill]
    total = 0
    for node in alloc.get(branch, []):
        if node in tree and tree[node]["branch"] == branch:
            total += tree[node]["cost"]
    return total


def get_total_points_spent(alloc: Dict[str, List[str]], skill: SkillType) -> int:
    tree = ALL_TREES[skill]
    total = 0
    for branch_nodes in alloc.values():
        for node in branch_nodes:
            if node in tree:
                total += tree[node]["cost"]
    return total


def can_purchase_node(
    skill: SkillType, node_key: str, alloc: Dict[str, List[str]], current_points: int
) -> Tuple[bool, str]:
    """Validation for a purchase attempt. Returns (ok, reason_if_not)."""
    tree = ALL_TREES[skill]
    node = tree.get(node_key)
    if not node:
        return False, "Unknown node."

    branch = node["branch"]
    cost = node["cost"]
    spent_in_branch = calculate_branch_points_spent(alloc, branch, skill)

    if node_key in alloc.get(branch, []):
        return False, "Already purchased."

    # Hard reqs
    if cost > current_points:
        return False, f"Need {cost} points in {skill} (have {current_points})."

    reqs = node.get("requires", [])
    for req in reqs:
        if req not in alloc.get(branch, []):
            return False, f"Requires prerequisite: {NODE_LABELS.get(req, req)}."

    req_branch_pts = node.get("requires_branch_pts")
    if req_branch_pts and spent_in_branch < req_branch_pts:
        return False, f"Requires {req_branch_pts} points already spent in this branch."

    return True, ""


def apply_purchase(skill: SkillType, node_key: str, alloc_json: str) -> str:
    """Return new alloc JSON after adding the node (assumes validation passed)."""
    alloc = (
        json.loads(alloc_json)
        if alloc_json
        else {"yield": [], "quality": [], "synergy": []}
    )
    node = ALL_TREES[skill][node_key]
    branch = node["branch"]
    if branch not in alloc:
        alloc[branch] = []
    if node_key not in alloc[branch]:
        alloc[branch].append(node_key)
    return json.dumps(alloc, separators=(",", ":"))


# =========================================================
# Yield & Rich Event Modifiers (core integration)
# =========================================================


def _get_unlocked_nodes_from_alloc(alloc: dict, branch: str) -> list[str]:
    """Helper that works with both old list format and new rich dict format."""
    val = alloc.get(branch, [])
    if isinstance(val, dict):
        return val.get("unlocked", [])
    return val if isinstance(val, (list, tuple)) else []


def get_yield_multiplier(skill: SkillType, mastery_row: dict) -> float:
    """Global % yield bonus from Yield branch (8/16/26%) + Mastery Insight."""
    alloc = json.loads(mastery_row.get(f"{skill}_alloc", "{}") or "{}")
    mult = 1.0
    tree = ALL_TREES[skill]
    for node in _get_unlocked_nodes_from_alloc(alloc, "yield"):
        if node in tree:
            # The three cumulative nodes
            if node in ("enduring_veins", "patient_waters", "strong_arm"):
                mult += 0.08
            elif node in ("bountiful_veins", "abundant_catch", "mighty_swing"):
                mult += 0.08  # cumulative to 16
            elif node in ("motherlode", "bountiful_haul", "titanic_felling"):
                mult += 0.10  # cumulative to 26

    # Post-max infinite scaling (global, very gentle)
    insight = get_mastery_insight(mastery_row)
    mult += get_insight_global_yield_bonus(insight)
    return mult


def get_signature_resource_bonus(skill: SkillType, mastery_row: dict) -> float:
    """Quality branch signature bonuses (+20/38%) + Synergy 5pt capstone (+55% from passive hourly ticks per Living Mountain / Old One's Favor / Forest Remembers)."""
    alloc = json.loads(mastery_row.get(f"{skill}_alloc", "{}") or "{}")
    bonus = 1.0
    for node in _get_unlocked_nodes_from_alloc(alloc, "quality"):
        if node in ("ideal_seeker", "tide_seeker", "heartwood_seeker"):
            bonus += 0.20
        elif node in ("crystallized_insight", "abyssal_memory", "living_heartwood"):
            bonus += 0.18  # cumulative to 38%

    # Synergy capstone: +55% to the signature resource (Idea Ore / Titanium Bones / Idea Logs) from ALL sources.
    # This stacks multiplicatively with the Quality bonus. The "small independent Rich proc" is already
    # handled in get_rich_event_chance (3% fallback when no Worldcore but synergy 5pt owned).
    synergy_nodes = _get_unlocked_nodes_from_alloc(alloc, "synergy")
    if skill == "mining" and "living_mountain" in synergy_nodes:
        bonus += 0.55
    elif skill == "fishing" and "old_ones_favor" in synergy_nodes:
        bonus += 0.55
    elif skill == "woodcutting" and "forest_remembers" in synergy_nodes:
        bonus += 0.55

    return bonus


def get_below_tier_chance(skill: SkillType, mastery_row: dict) -> float:
    """6% chance from Quality tier-2 nodes."""
    alloc = json.loads(mastery_row.get(f"{skill}_alloc", "{}") or "{}")
    for node in _get_unlocked_nodes_from_alloc(alloc, "quality"):
        if node in ("crystallized_insight", "abyssal_memory", "living_heartwood"):
            return 0.06
    return 0.0


def get_rich_event_chance(skill: SkillType, mastery_row: dict) -> float:
    """Base Rich proc chance per passive tick.

    - 4% base chance once the 3pt Quality unlock node (Geode Cores / Tide Relics / Heartwood Shards) is taken.
    - Upgraded to 22% when the 5pt Resonance node in the same Quality branch is taken.
    - 3% fallback from Synergy 5pt capstones (Living Mountain / Old One's Favor / Forest Remembers)
      if the player does not have the Quality 5pt resonance.
    Plus any additional % from Quality branch bonus investment points (+0.5% per point).
    """
    alloc = json.loads(mastery_row.get(f"{skill}_alloc", "{}") or "{}")
    quality_nodes = _get_unlocked_nodes_from_alloc(alloc, "quality")
    synergy_nodes = _get_unlocked_nodes_from_alloc(alloc, "synergy")

    base = 0.0

    resonance_nodes = (
        "worldcore_resonance",
        "deep_current_resonance",
        "elder_resonance",
    )
    if any(n in quality_nodes for n in resonance_nodes):
        base = 0.22
    else:
        # 3pt Quality unlock now grants a small base chance when events are first enabled
        unlock_nodes = ("geode_cores", "tide_relics", "heartwood_shards")
        if any(n in quality_nodes for n in unlock_nodes):
            base = 0.04
        else:
            # Small independent chance from Synergy 5pt capstones (alternative path)
            synergy_caps = ("living_mountain", "old_ones_favor", "forest_remembers")
            if any(n in synergy_nodes for n in synergy_caps):
                base = 0.03

    bonus = get_rich_base_bonus(skill, mastery_row)
    return base + bonus


def roll_rich_event(skill: SkillType, mastery_row: dict) -> bool:
    """Should this passive tick trigger a Rich event?"""
    chance = get_rich_event_chance(skill, mastery_row)
    return random.random() < chance if chance > 0 else False


def roll_remnant_generation(skill: SkillType, mastery_row: dict, is_rich: bool) -> int:
    """
    Returns number of remnants of the skill's type.
    Quality 3pt node (geode_cores etc) required for any chance.
    """
    alloc = json.loads(mastery_row.get(f"{skill}_alloc", "{}") or "{}")
    quality_nodes = alloc.get("quality", {}).get("unlocked", [])
    has_unlock = False
    if skill == "mining" and "geode_cores" in quality_nodes:
        has_unlock = True
    elif skill == "fishing" and "tide_relics" in quality_nodes:
        has_unlock = True
    elif skill == "woodcutting" and "heartwood_shards" in quality_nodes:
        has_unlock = True

    if not has_unlock:
        return 0

    if is_rich:
        # Guaranteed 3-5 average ~4
        return max(3, min(5, int(random.gauss(4.0, 0.8))))

    # Baseline 5.5%
    if random.random() < REMNANT_BASELINE_CHANCE:
        return random.randint(1, 2)
    return 0


def get_remnant_column(skill: SkillType) -> str:
    return {
        "mining": "geode_cores",
        "fishing": "tide_relics",
        "woodcutting": "heartwood_shards",
    }[skill]


# =========================================================
# Synergy helpers (called from settlement, alchemy, dispatch, drops)
# =========================================================


def has_master_quarry(mastery_row: dict) -> bool:
    alloc = json.loads(mastery_row.get("mining_alloc", "{}") or "{}")
    return "master_quarry" in alloc.get("synergy", {}).get("unlocked", [])


def has_seasoned_timber(mastery_row: dict) -> bool:
    alloc = json.loads(mastery_row.get("woodcutting_alloc", "{}") or "{}")
    return "seasoned_timber" in alloc.get("synergy", {}).get("unlocked", [])


def has_master_baiter(mastery_row: dict) -> bool:
    alloc = json.loads(mastery_row.get("fishing_alloc", "{}") or "{}")
    return "master_baiter" in alloc.get("synergy", {}).get("unlocked", [])


def get_skiller_bonus(mastery_row: dict, skill: SkillType) -> Tuple[float, float]:
    """Returns (proc_chance_mult, yield_mult) for Skiller boots. 1.65x chance, 1.45x yield if owned."""
    alloc = json.loads(mastery_row.get(f"{skill}_alloc", "{}") or "{}")
    synergy = alloc.get("synergy", {}).get("unlocked", [])
    if any(
        n in synergy for n in ("skilled_hands", "favored_currents", "skilled_forester")
    ):
        return 1.65, 1.45
    return 1.0, 1.0


def get_tool_cost_reduction(mastery_row: dict, skill: SkillType) -> float:
    """12% reduction if the 1pt synergy node owned."""
    alloc = json.loads(mastery_row.get(f"{skill}_alloc", "{}") or "{}")
    synergy = alloc.get("synergy", {}).get("unlocked", [])
    if skill == "mining" and "tool_resonance" in synergy:
        return 0.12
    if skill == "fishing" and "lighter_bait" in synergy:
        return 0.12
    if skill == "woodcutting" and "foresters_eye" in synergy:
        return 0.12
    return 0.0


# =========================================================
# Point accrual + catch-up (called from hourly task in cogs/skills)
# =========================================================


def get_points_for_tool(tool_tier: str) -> float:
    return TOOL_POINT_RATES.get(tool_tier, 0.6)


def compute_catchup_points(
    last_claim_iso: str | None, tool_tier: str, now_iso: str
) -> int:
    """Return integer points to award (capped at 24h worth)."""
    from datetime import datetime

    rate = get_points_for_tool(tool_tier)
    if not last_claim_iso:
        return int(rate)  # first claim, give 1 day worth floored

    try:
        last = datetime.fromisoformat(last_claim_iso.replace("Z", "+00:00"))
        now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    except Exception:
        return 0

    hours = (now - last).total_seconds() / 3600.0
    hours = min(hours, CATCHUP_HOURS)
    raw = hours * (rate / 24.0)
    return max(0, int(raw))


# =========================================================
# Cross-skill helpers (kept for any external callers; real gate logic lives below)
# =========================================================


def get_total_mastery_invested(all_mastery_rows: Dict[str, dict]) -> int:
    total = 0
    for row in all_mastery_rows.values():
        total += row.get("total_mastery_invested", 0)
    return total


# =========================================================
# New Branch Investment Model (user-driven redesign)
# Instead of buying specific nodes via Selects for exact costs,
# the player invests points into a branch one at a time.
# Nodes unlock automatically in sequence when investment thresholds are met.
# The alloc JSON is extended to support:
#   {"yield": {"invested": 7, "unlocked": ["node1", "node2"]}, ... }
# Old flat list format is still read for compatibility.
# =========================================================


def _normalize_alloc(alloc: dict) -> dict:
    """
    Convert alloc data (old or new) into the canonical rich format:
        {"yield": {"invested": N, "unlocked": [...]}, ...}

    Legacy flat lists are converted with invested=0. Backfilling of a
    sensible 'invested' value is handled in get_branch_progress() where
    we have access to the skill (and therefore the correct node order).
    """
    if not alloc:
        return {
            "yield": {"invested": 0, "unlocked": []},
            "quality": {"invested": 0, "unlocked": []},
            "synergy": {"invested": 0, "unlocked": []},
        }

    normalized = {}
    for branch in ("yield", "quality", "synergy"):
        val = alloc.get(branch, [])
        if isinstance(val, dict):
            normalized[branch] = {
                "invested": int(val.get("invested", 0)),
                "unlocked": list(val.get("unlocked", [])),
            }
        else:
            # old format: list of unlocked node keys
            normalized[branch] = {
                "invested": 0,
                "unlocked": list(val) if isinstance(val, (list, tuple)) else [],
            }
    return normalized


def get_branch_investment(alloc: dict, branch: Branch) -> int:
    """Return how many points have been invested into this branch."""
    norm = _normalize_alloc(alloc)
    return norm.get(branch, {}).get("invested", 0)


def get_unlocked_nodes(alloc: dict, branch: Branch) -> list[str]:
    norm = _normalize_alloc(alloc)
    return norm.get(branch, {}).get("unlocked", [])


def get_branch_progress(skill: SkillType, branch: Branch, alloc: dict) -> dict:
    """
    Returns a dict with:
      - invested: current investment (backfilled for legacy data)
      - unlocked: list of unlocked node keys
      - next_node: the next node key to unlock (or None if branch complete)
      - next_cost: points still needed for the next node (0 if none left)
      - total_for_next: the cost threshold for the next node
    """
    tree = ALL_TREES[skill]
    order = BRANCH_NODE_ORDERS.get(skill, {}).get(branch, [])
    norm = _normalize_alloc(alloc)

    invested = norm.get(branch, {}).get("invested", 0)
    unlocked = set(norm.get(branch, {}).get("unlocked", []))

    # Backfill invested for legacy data (pre-redesign unlocks).
    # If the stored invested is 0 but nodes are unlocked, calculate the
    # minimum investment that would have been required to unlock them
    # in the correct sequential order.
    if invested == 0 and unlocked:
        cumulative = 0
        for node_key in order:
            if node_key in unlocked:
                cumulative += tree.get(node_key, {}).get("cost", 0)
            else:
                break
        invested = cumulative

    # Determine the true next node to unlock, taking investment into account.
    # A node is considered "effectively unlocked" for progress purposes if
    # either it is in the persisted unlocked set OR the current invested total
    # meets or exceeds the cumulative cost to reach it.
    next_node = None
    cumulative = 0
    for node_key in order:
        node_cost = tree.get(node_key, {}).get("cost", 1)
        cumulative += node_cost

        required_for_this_node = cumulative
        effectively_unlocked = (node_key in unlocked) or (
            invested >= required_for_this_node
        )

        if not effectively_unlocked:
            next_node = node_key
            break

    if next_node is None:
        # Branch is fully unlocked for nodes — allow bonus investment (up to 10 extra points)
        total_cost = get_branch_total_cost(skill, branch)
        bonus_invested = max(0, invested - total_cost)
        bonus_remaining = max(0, 10 - bonus_invested)

        return {
            "invested": invested,
            "unlocked": list(unlocked),
            "next_node": "bonus" if bonus_remaining > 0 else None,
            "next_cost": bonus_remaining,
            "total_for_next": 10,
            "complete": bonus_remaining == 0,
            "bonus_invested": bonus_invested,
            "bonus_max": 10,
        }

    # Recalculate the cumulative up to (but not including) the true next node
    # for accurate "how much toward it" math.
    prev_threshold = 0
    for node_key in order:
        if node_key == next_node:
            break
        prev_threshold += tree.get(node_key, {}).get("cost", 1)

    # The full cumulative required to unlock the next_node
    required_for_next = prev_threshold + tree.get(next_node, {}).get("cost", 1)

    needed_for_next = max(0, required_for_next - invested)
    progress_toward_next = max(0, invested - prev_threshold)

    return {
        "invested": invested,
        "unlocked": list(unlocked),
        "next_node": next_node,
        "next_cost": needed_for_next,
        "total_for_next": tree.get(next_node, {}).get("cost", 1),
        "progress_toward_next": progress_toward_next,
        "complete": False,
        "bonus_invested": 0,
        "bonus_max": 10,
    }


def invest_in_branch(
    skill: SkillType,
    branch: Branch,
    alloc_json: str,
    points_available: int,
    amount: int = 1,
) -> tuple[str, int, str | None]:
    """
    Invest up to `amount` points into the given branch.
    Returns (new_alloc_json, points_actually_spent, newly_unlocked_node_or_None)
    Only spends as many points as are available and as are useful.
    """
    if amount <= 0 or points_available <= 0:
        return alloc_json, 0, None

    tree = ALL_TREES[skill]
    order = BRANCH_NODE_ORDERS.get(skill, {}).get(branch, [])
    if not order:
        return alloc_json, 0, None

    alloc = _normalize_alloc(json.loads(alloc_json) if alloc_json else {})

    invested = alloc[branch]["invested"]
    unlocked = set(alloc[branch]["unlocked"])

    points_to_spend = min(amount, points_available)
    newly_unlocked = None

    for _ in range(points_to_spend):
        progress = get_branch_progress(skill, branch, alloc)

        # Allow investment even after all nodes are unlocked (for the new +10 bonus points)
        if progress.get("complete") and progress.get(
            "bonus_invested", 0
        ) >= progress.get("bonus_max", 10):
            break

        # Spend 1 point
        invested += 1
        alloc[branch]["invested"] = invested

        # Robust reconcile: unlock any nodes the current invested now qualifies for.
        # This fixes stuck states where invested >= threshold but node not in unlocked.
        order = BRANCH_NODE_ORDERS.get(skill, {}).get(branch, [])
        tree = ALL_TREES[skill]
        cumulative = 0
        any_new = False
        for node_key in order:
            cumulative += tree.get(node_key, {}).get("cost", 0)
            if cumulative <= invested and node_key not in unlocked:
                unlocked.add(node_key)
                any_new = True
                if newly_unlocked is None:
                    newly_unlocked = node_key

        if any_new:
            alloc[branch]["unlocked"] = list(unlocked)

    new_json = json.dumps(alloc, separators=(",", ":"))

    # Calculate how many points were actually spent this call
    original_invested = 0
    if alloc_json:
        orig = _normalize_alloc(json.loads(alloc_json))
        original_invested = orig.get(branch, {}).get("invested", 0)
    actual_spent = max(0, invested - original_invested)

    return new_json, actual_spent, newly_unlocked


# =========================================================
# Bonus Investment (Phase 2 expansion — +10 points per branch)
# These functions return the *additional* percentage from extra investment
# beyond the normal node costs (capped at +10 points).
# =========================================================


def _get_bonus_points(skill: SkillType, branch: Branch, mastery_row: dict) -> int:
    """How many bonus points (0-10) the player has invested in this branch."""
    alloc = json.loads(mastery_row.get(f"{skill}_alloc", "{}") or "{}")
    invested = get_branch_investment(alloc, branch)
    total_cost = get_branch_total_cost(skill, branch)
    return max(0, min(10, invested - total_cost))


def get_yield_proc_bonus(skill: SkillType, mastery_row: dict) -> float:
    """
    Additional % chance for the 'Never Empty' style proc node
    (Never Empty / Never-Empty Nets / Forest's Bounty).
    +0.4% per bonus point (max +4%).
    """
    bonus_points = _get_bonus_points(skill, "yield", mastery_row)
    return bonus_points * 0.004


def get_rich_base_bonus(skill: SkillType, mastery_row: dict) -> float:
    """
    Additional % to the base Rich event chance.
    +0.5% per Quality branch bonus investment point (max +5%).
    Now applies on top of the 4% base from the 3pt unlock (or higher bases from 5pt nodes).
    """
    bonus_points = _get_bonus_points(skill, "quality", mastery_row)
    return bonus_points * 0.005


def get_prestige_spawn_bonus(skill: SkillType, mastery_row: dict) -> float:
    """
    Additional % chance for the prestige boss to spawn
    (Meridian Golem / Drowned Leviathan / Verdant Colossus).
    +0.2% per bonus point (max +2%).
    """
    bonus_points = _get_bonus_points(skill, "synergy", mastery_row)
    return bonus_points * 0.002


def get_never_empty_proc_chance(skill: SkillType, mastery_row: dict) -> float:
    """
    Total chance per passive tick for the Yield proc node effect
    (Never Empty / Never-Empty Nets / Forest's Bounty) to trigger +70% yield.
    Base 12% + bonus from extra Yield investment (max +4%).
    """
    base = 0.12
    bonus = get_yield_proc_bonus(skill, mastery_row)
    return base + bonus


# =========================================================
# Nature's Attunement Gate + Investment + Bonus Getters
# =========================================================


def get_total_invested_for_skill(skill: SkillType, mastery_row: dict | None) -> int:
    """Total points ever spent in one skill (main nodes + all bonus investment)."""
    if not mastery_row:
        return 0
    alloc_json = mastery_row.get(f"{skill}_alloc") or "{}"
    try:
        alloc = json.loads(alloc_json)
    except (json.JSONDecodeError, TypeError):
        alloc = {}
    total = 0
    for branch in ("yield", "quality", "synergy"):
        progress = get_branch_progress(skill, branch, alloc)
        total += progress.get("invested", 0)
    return total


def has_nature_attunement_unlocked(mastery_row: dict) -> bool:
    """
    Gate check: player must have at least 20 points invested in EACH of the three
    main trees (including the +10 bonus investment per branch).
    """
    mining = get_total_invested_for_skill("mining", mastery_row)
    fishing = get_total_invested_for_skill("fishing", mastery_row)
    woodcutting = get_total_invested_for_skill("woodcutting", mastery_row)
    return min(mining, fishing, woodcutting) >= 20


def get_attunement_progress(alloc_json: str) -> dict:
    """Returns invested per node + total for the free-form attunement tree."""
    alloc = json.loads(alloc_json) if alloc_json else {}
    result = {}
    total = 0
    for node_key, node in NATURE_ATTUNEMENT_TREE.items():
        invested = max(0, min(5, alloc.get(node_key, 0)))
        result[node_key] = invested
        total += invested
    result["total"] = total
    result["max"] = 15
    result["complete"] = total >= 15
    return result


def invest_in_attunement(
    current_alloc_json: str, points_available: int, node_key: str, amount: int = 1
) -> tuple[str, int, bool]:
    """
    Freely invest `amount` points into one attunement node (max 5 per node).
    Returns (new_alloc_json, points_actually_spent, node_now_maxed).
    """
    if amount <= 0 or points_available <= 0:
        return current_alloc_json, 0, False
    if node_key not in NATURE_ATTUNEMENT_TREE:
        return current_alloc_json, 0, False

    alloc = json.loads(current_alloc_json) if current_alloc_json else {}
    current = max(0, min(5, alloc.get(node_key, 0)))
    node_max = 5
    can_take = min(amount, points_available, node_max - current)
    if can_take <= 0:
        return current_alloc_json, 0, False

    alloc[node_key] = current + can_take
    new_json = json.dumps(alloc, separators=(",", ":"))
    now_maxed = alloc[node_key] >= node_max
    return new_json, can_take, now_maxed


def get_attunement_rune_bonus(mastery_row: dict) -> float:
    """+1% per point invested (max +5%)."""
    progress = get_attunement_progress(mastery_row.get("attunement_alloc", "{}"))
    pts = progress.get("elemental_resonance_plus", 0)
    return pts * 0.01


def get_attunement_alchemy_bonus(mastery_row: dict) -> float:
    """+1% material on alchemy conversions per point (max +5%)."""
    progress = get_attunement_progress(mastery_row.get("attunement_alloc", "{}"))
    pts = progress.get("druidic_ritual", 0)
    return pts * 0.01


def get_attunement_harvest_tripled_bonus(mastery_row: dict) -> int:
    """Extra tripled ticks awarded on prestige gathering boss harvest."""
    progress = get_attunement_progress(mastery_row.get("attunement_alloc", "{}"))
    pts = progress.get("groves_reckoning", 0)
    return pts  # +0 to +5 on top of base 10


def get_mastery_insight(mastery_row: dict) -> int:
    return max(0, mastery_row.get("mastery_insight", 0) or 0)


def get_total_insight_bonuses(mastery_row: dict) -> dict:
    """Convenience bundle for UI."""
    insight = get_mastery_insight(mastery_row)
    return {
        "count": insight,
        "global_yield": get_insight_global_yield_bonus(insight),
        "remnant": get_insight_remnant_bonus(insight),
        "rune": get_insight_rune_bonus(insight),
    }


# Future: get_rune_drop_rate_modifier etc.

# =========================================================
# Small UI helpers (for MasteryView)
# =========================================================


def get_branch_display_name(branch: Branch) -> str:
    return {"yield": "Yield", "quality": "Quality", "synergy": "Synergy"}[branch]


def format_node_for_select(skill: SkillType, node_key: str) -> str:
    node = ALL_TREES[skill][node_key]
    label = NODE_LABELS.get(node_key, node_key)
    cost = node["cost"]
    return f"{label} ({cost} pt) — {node['desc'][:60]}..."


def get_all_node_keys(skill: SkillType) -> List[str]:
    return list(ALL_TREES[skill].keys())


def get_branch_total_cost(skill: SkillType, branch: Branch) -> int:
    """Total points required to unlock every node in a branch."""
    tree = ALL_TREES[skill]
    order = BRANCH_NODE_ORDERS.get(skill, {}).get(branch, [])
    return sum(tree.get(node, {}).get("cost", 0) for node in order)


def _get_cumulative_cost_to_unlock_node(
    skill: SkillType, branch: Branch, target_node: str
) -> int:
    """Return the total points that must be invested in the branch to unlock up to (and including) target_node."""
    tree = ALL_TREES[skill]
    order = BRANCH_NODE_ORDERS.get(skill, {}).get(branch, [])
    total = 0
    for node_key in order:
        total += tree.get(node_key, {}).get("cost", 0)
        if node_key == target_node:
            return total
    return total
