# core/companions/mastery.py

KP_PER_OVERFLOW_XP = 10000  # 10000 overflow XP → 1 Kinship Point

MASTERY_BRANCHES: dict = {
    "forager": {
        "label": "🌿 Forager's Pack",
        "nodes": [
            {
                "id": "keen_senses",
                "name": "Keen Senses",
                "cost": 15,
                "requires": None,
                "desc": "Loot find chance +10% per companion per cycle (additive).",
            },
            {
                "id": "double_haul",
                "name": "Double Haul",
                "cost": 35,
                "requires": "keen_senses",
                "desc": "20% chance to find an extra loot item on each successful roll.",
            },
            {
                "id": "tireless_scouts",
                "name": "Tireless Scouts",
                "cost": 65,
                "requires": "double_haul",
                "desc": "Loot accumulation window extended from 48 → 72 hours.",
            },
        ],
    },
    "affinity": {
        "label": "🎯 Loot Affinity",
        "nodes": [
            {
                "id": "prey_instinct",
                "name": "Prey Instinct",
                "cost": 20,
                "requires": None,
                "desc": "Choose a primary loot focus — Gold, Runes, or Keys. That category rolls 3× as often.",
                "choice": ["Gold", "Runes", "Keys"],
            },
            {
                "id": "fine_palate",
                "name": "Fine Palate",
                "cost": 45,
                "requires": "prey_instinct",
                "desc": "Primary focus raised to 5× weight. Unlock a second loot focus (3× weight).",
                "choice": [
                    "Gold",
                    "Runes",
                    "Keys",
                ],  # filtered at runtime to exclude prey_instinct pick
            },
            {
                "id": "apex_scavenger",
                "name": "Apex Scavenger",
                "cost": 80,
                "requires": "fine_palate",
                "desc": "Biased loot types always receive an extra roll on every successful find.",
            },
        ],
    },
    "bond": {
        "label": "⚔️ Bonded",
        "nodes": [
            {
                "id": "trusted_ally",
                "name": "Trusted Ally",
                "cost": 15,
                "requires": None,
                "desc": "All active companion passive values +10%.",
            },
            {
                "id": "elite_bond",
                "name": "Elite Bond",
                "cost": 40,
                "requires": "trusted_ally",
                "desc": "Gemini balanced passives are treated as +1 tier higher in combat.",
            },
            {
                "id": "legend_pact",
                "name": "Legend Pact",
                "cost": 75,
                "requires": "elite_bond",
                "desc": "With 2+ active companions, all passive values gain an additional +10%.",
            },
        ],
    },
}

# Loot table keys that belong to each bias category
BIAS_TO_LOOT_KEYS: dict = {
    "Gold": ["Gold"],
    "Runes": ["Rune of Refinement", "Rune of Potential", "Rune of Shattering"],
    "Keys": ["Boss Key"],
}

# Default loot weights (mirrors mechanics.py)
_DEFAULT_WEIGHTS: dict = {
    "Gold": 90,
    "Boss Key": 2,
    "Rune of Refinement": 2,
    "Rune of Potential": 3,
    "Rune of Shattering": 3,
}


def get_all_nodes() -> list[dict]:
    return [n for branch in MASTERY_BRANCHES.values() for n in branch["nodes"]]


def get_node_by_id(node_id: str) -> dict | None:
    for n in get_all_nodes():
        if n["id"] == node_id:
            return n
    return None


def can_purchase(
    node_id: str, nodes_owned: dict, kinship_points: int
) -> tuple[bool, str]:
    node = get_node_by_id(node_id)
    if not node:
        return False, "Unknown node."
    if node_id in nodes_owned:
        return False, "Already unlocked."
    req = node.get("requires")
    if req and req not in nodes_owned:
        parent = get_node_by_id(req)
        name = parent["name"] if parent else req
        return False, f"Requires **{name}** first."
    if kinship_points < node["cost"]:
        return False, f"Need **{node['cost']} KP** (you have {kinship_points})."
    return True, ""


def kp_from_overflow_xp(xp: int) -> int:
    """Convert overflow XP (from maxed companions) into Kinship Points."""
    return max(0, xp // KP_PER_OVERFLOW_XP)


# ── Effect helpers ────────────────────────────────────────────────────────────


def get_find_chance_bonus(nodes_owned: dict) -> float:
    """Additive bonus added to each companion's per-cycle find chance."""
    return 0.10 if "keen_senses" in nodes_owned else 0.0


def get_double_haul_chance(nodes_owned: dict) -> float:
    return 0.20 if "double_haul" in nodes_owned else 0.0


def get_max_cycles(nodes_owned: dict) -> int:
    return 72 if "tireless_scouts" in nodes_owned else 48


def get_loot_weights(nodes_owned: dict) -> dict:
    """Return modified loot weight dict based on affinity nodes."""
    weights = dict(_DEFAULT_WEIGHTS)
    prey = nodes_owned.get("prey_instinct")
    fine = nodes_owned.get("fine_palate")

    if prey and prey in BIAS_TO_LOOT_KEYS:
        mult = 5 if fine else 3
        for k in BIAS_TO_LOOT_KEYS[prey]:
            weights[k] = weights.get(k, 0) * mult

    if fine and fine in BIAS_TO_LOOT_KEYS:
        for k in BIAS_TO_LOOT_KEYS[fine]:
            weights[k] = weights.get(k, 0) * 3

    return weights


def get_biased_loot_keys(nodes_owned: dict) -> set:
    """Set of loot-type strings that apex_scavenger grants an extra roll for."""
    keys: set = set()
    for field in ("prey_instinct", "fine_palate"):
        bias = nodes_owned.get(field)
        if bias:
            keys.update(BIAS_TO_LOOT_KEYS.get(bias, []))
    return keys


def is_apex_scavenger(nodes_owned: dict) -> bool:
    return "apex_scavenger" in nodes_owned


def get_passive_mult(nodes_owned: dict, active_count: int) -> float:
    """Multiplier applied to all companion passive values in combat."""
    mult = 1.0
    if "trusted_ally" in nodes_owned:
        mult += 0.10
    if "legend_pact" in nodes_owned and active_count >= 2:
        mult += 0.10
    return mult


def has_elite_bond(nodes_owned: dict) -> bool:
    return "elite_bond" in nodes_owned


def passive_value_for_type(passive_type: str, tier: int) -> float:
    """Computes companion passive value for a given type+tier (mirrors Companion.passive_value)."""
    tier = max(1, min(5, tier))
    if passive_type in ("atk", "def"):
        return float(4 + tier)
    if passive_type in ("hit", "crit"):
        return float(tier)
    if passive_type == "ward":
        return float(tier * 5)
    if passive_type == "rarity":
        return float(tier * 3)
    if passive_type == "s_rarity":
        return tier * 0.5
    if passive_type == "fdr":
        return float(5 + tier * 2)
    if passive_type == "pdr":
        return float(2 + tier)
    return 0.0
