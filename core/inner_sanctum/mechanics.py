"""core/inner_sanctum/mechanics.py — Inner Sanctum tree math.

get_tree_bonuses() is the single aggregator every combat/economy hook site
should call — no call site should re-parse `nodes_owned` directly, so all
tuning lives in data.py (costs/ranks/values) and here (aggregation formulas).
"""

from core.inner_sanctum.data import (
    ALL_NODES,
    DEICIDE_DOWNSIDE_ATK_PCT_PER_RANK,
    DEICIDE_DOWNSIDE_DEF_PCT_PER_RANK,
    DEICIDE_DOWNSIDE_HP_PCT_PER_RANK,
    DEICIDE_NODES,
    DEICIDE_UNLOCK_LEVEL,
    RECOVERY_DOWNSIDE_ATK_PCT_PER_RANK,
    RECOVERY_NODES,
    RECOVERY_UNLOCK_LEVEL,
    RESET_RUNE_COST,
    VICE_NODES,
    VICE_UNLOCK_LEVEL,
)

__all__ = [
    "RESET_RUNE_COST",
    "can_purchase",
    "can_purchase_ranks",
    "get_node_cost",
    "get_ranks_cost",
    "get_tree_bonuses",
]


def _node_ranks(node_def: dict, owned_value) -> int:
    """Ranks invested in a single node (1 for an owned choice node)."""
    if node_def.get("is_choice"):
        return 1 if owned_value else 0
    return owned_value or 0


def total_ranks_in_branch(nodes_owned: dict, branch: str) -> int:
    """Total ranks invested across a branch — used for downside scaling.
    Ranks (not points spent) so escalating per-rank costs don't blow up the
    downside past what "minor trade-off" is meant to mean."""
    total = 0
    for node_id, node_def in ALL_NODES.items():
        if node_def["branch"] != branch:
            continue
        total += _node_ranks(node_def, nodes_owned.get(node_id))
    return total


def get_node_cost(node_id: str, nodes_owned: dict) -> int | None:
    """Cost to buy the *next* rank of node_id, or None if maxed / invalid."""
    node_def = ALL_NODES.get(node_id)
    if not node_def:
        return None
    if node_def.get("is_choice"):
        return None if nodes_owned.get(node_id) else node_def["cost"]
    rank = nodes_owned.get(node_id, 0) or 0
    if rank >= node_def["max_rank"]:
        return None
    return node_def["costs"][rank]


_BRANCH_UNLOCK_LEVEL = {
    "vice": VICE_UNLOCK_LEVEL,
    "recovery": RECOVERY_UNLOCK_LEVEL,
    "deicide": DEICIDE_UNLOCK_LEVEL,
}


def can_purchase(
    node_id: str, nodes_owned: dict, player_level: int, points_available: int
) -> tuple[bool, int | None, str]:
    """Returns (ok, cost, reason). reason is empty string when ok.
    Single-purchase check — used for choice nodes (e.g. Deicide's Marked Prey)."""
    node_def = ALL_NODES.get(node_id)
    if not node_def:
        return False, None, "Unknown node."

    unlock_level = _BRANCH_UNLOCK_LEVEL[node_def["branch"]]
    if player_level < unlock_level:
        return False, None, f"Requires level {unlock_level}."

    cost = get_node_cost(node_id, nodes_owned)
    if cost is None:
        return False, None, "Already at max rank."
    if points_available < cost:
        return False, cost, "Not enough Inner Sanctum points."
    return True, cost, ""


def get_ranks_cost(node_id: str, nodes_owned: dict, count: int) -> int | None:
    """Total cost to buy `count` additional ranks of node_id in one go, or
    None if node_id is a choice node, count <= 0, or it would exceed max_rank."""
    node_def = ALL_NODES.get(node_id)
    if not node_def or node_def.get("is_choice") or count <= 0:
        return None
    rank = nodes_owned.get(node_id, 0) or 0
    if rank + count > node_def["max_rank"]:
        return None
    return sum(node_def["costs"][rank : rank + count])


def can_purchase_ranks(
    node_id: str,
    nodes_owned: dict,
    player_level: int,
    points_available: int,
    count: int,
) -> tuple[bool, int | None, str]:
    """Bulk version of can_purchase — buy `count` ranks of a ranked node at once."""
    node_def = ALL_NODES.get(node_id)
    if not node_def:
        return False, None, "Unknown node."

    unlock_level = _BRANCH_UNLOCK_LEVEL[node_def["branch"]]
    if player_level < unlock_level:
        return False, None, f"Requires level {unlock_level}."

    cost = get_ranks_cost(node_id, nodes_owned, count)
    if cost is None:
        return False, None, "Not enough ranks remaining."
    if points_available < cost:
        return False, cost, "Not enough Inner Sanctum points."
    return True, cost, ""


def _sum_vice_field(owned: dict, field_name: str) -> float:
    """Sums `rank * node[field_name]` across every Vice node that declares it."""
    total = 0.0
    for node_id, node_def in VICE_NODES.items():
        rank = owned.get(node_id, 0) or 0
        if rank <= 0:
            continue
        total += rank * node_def.get(field_name, 0.0)
    return total


def get_tree_bonuses(nodes_owned: dict) -> dict:
    """Returns all active Inner Sanctum bonus values, keyed by effect name."""
    owned = nodes_owned or {}

    def rank_of(node_id: str) -> int:
        return owned.get(node_id, 0) or 0

    recovery_ranks = total_ranks_in_branch(owned, "recovery")
    deicide_ranks = total_ranks_in_branch(owned, "deicide")

    bonuses = {
        # Vice — every Vice node contributes to one or more of these via its
        # own *_per_rank keys in data.py; see _sum_vice_field.
        "special_rarity_pct": _sum_vice_field(owned, "special_rarity_per_rank"),
        "vice_monster_atk_pct": _sum_vice_field(owned, "monster_atk_per_rank"),
        "vice_monster_def_pct": _sum_vice_field(owned, "monster_def_per_rank"),
        "vice_monster_crit_pct": _sum_vice_field(owned, "monster_crit_per_rank"),
        "vice_monster_hp_pct": _sum_vice_field(owned, "monster_hp_per_rank"),
        "vice_monster_dmg_pct": _sum_vice_field(owned, "monster_dmg_per_rank"),
        "rune_refinement_chance_pct": _sum_vice_field(owned, "refine_chance_per_rank"),
        "rune_potential_chance_pct": _sum_vice_field(owned, "potential_chance_per_rank"),
        "rune_shattering_chance_pct": _sum_vice_field(owned, "shatter_chance_per_rank"),
        "treasure_chance_pct": _sum_vice_field(owned, "treasure_encounter_per_rank"),
        "bonus_curio_chance": _sum_vice_field(owned, "bonus_curio_per_rank"),
        "bonus_puzzlebox_chance": _sum_vice_field(owned, "bonus_puzzlebox_per_rank"),
        "treasure_stat_bonus_pct": _sum_vice_field(owned, "treasure_stat_per_rank"),
        # Recovery
        "stamina_save_chance": rank_of("re_stamina_save")
        * RECOVERY_NODES["re_stamina_save"]["value_per_rank"],
        "stamina_regen_bonus_chance": rank_of("re_stamina_regen")
        * RECOVERY_NODES["re_stamina_regen"]["value_per_rank"],
        "exp_loss_reduction_pct": rank_of("re_exp_shield")
        * RECOVERY_NODES["re_exp_shield"]["value_per_rank"],
        "recovery_atk_malus_pct": recovery_ranks * RECOVERY_DOWNSIDE_ATK_PCT_PER_RANK,
        # Deicide
        "boss_chance_bonus_pct": rank_of("de_boss_chance")
        * DEICIDE_NODES["de_boss_chance"]["value_per_rank"],
        "boss_affinity": owned.get("de_affinity"),
        "boss_affinity_shift": DEICIDE_NODES["de_affinity"]["affinity_shift"]
        if owned.get("de_affinity")
        else 0.0,
        "boss_rune_chance_pct": rank_of("de_boss_runes")
        * DEICIDE_NODES["de_boss_runes"]["value_per_rank"],
        "boss_dupe_chance": rank_of("de_boss_dupe")
        * DEICIDE_NODES["de_boss_dupe"]["value_per_rank"],
        "deicide_boss_atk_pct": deicide_ranks * DEICIDE_DOWNSIDE_ATK_PCT_PER_RANK,
        "deicide_boss_def_pct": deicide_ranks * DEICIDE_DOWNSIDE_DEF_PCT_PER_RANK,
        "deicide_boss_hp_pct": deicide_ranks * DEICIDE_DOWNSIDE_HP_PCT_PER_RANK,
    }
    return bonuses
