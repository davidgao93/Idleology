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
    VICE_DOWNSIDE_ATK_PCT_PER_RANK,
    VICE_DOWNSIDE_HP_PCT_PER_RANK,
    VICE_NODES,
    VICE_UNLOCK_LEVEL,
)

__all__ = [
    "RESET_RUNE_COST",
    "can_purchase",
    "get_node_cost",
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


def can_purchase(
    node_id: str, nodes_owned: dict, player_level: int, points_available: int
) -> tuple[bool, int | None, str]:
    """Returns (ok, cost, reason). reason is empty string when ok."""
    node_def = ALL_NODES.get(node_id)
    if not node_def:
        return False, None, "Unknown node."

    branch = node_def["branch"]
    unlock_level = {
        "vice": VICE_UNLOCK_LEVEL,
        "recovery": RECOVERY_UNLOCK_LEVEL,
        "deicide": DEICIDE_UNLOCK_LEVEL,
    }[branch]
    if player_level < unlock_level:
        return False, None, f"Requires level {unlock_level}."

    cost = get_node_cost(node_id, nodes_owned)
    if cost is None:
        return False, None, "Already at max rank."
    if points_available < cost:
        return False, cost, "Not enough Inner Sanctum points."
    return True, cost, ""


def get_tree_bonuses(nodes_owned: dict) -> dict:
    """Returns all active Inner Sanctum bonus values, keyed by effect name."""
    owned = nodes_owned or {}

    def rank_of(node_id: str) -> int:
        return owned.get(node_id, 0) or 0

    vice_ranks = total_ranks_in_branch(owned, "vice")
    recovery_ranks = total_ranks_in_branch(owned, "recovery")
    deicide_ranks = total_ranks_in_branch(owned, "deicide")

    bonuses = {
        # Vice
        "special_rarity_pct": rank_of("vi_rarity") * VICE_NODES["vi_rarity"]["value_per_rank"],
        "rune_chance_pct": rank_of("vi_rune_chance")
        * VICE_NODES["vi_rune_chance"]["value_per_rank"],
        "treasure_chance_pct": rank_of("vi_treasure")
        * VICE_NODES["vi_treasure"]["value_per_rank"],
        "vice_monster_atk_pct": vice_ranks * VICE_DOWNSIDE_ATK_PCT_PER_RANK,
        "vice_monster_hp_pct": vice_ranks * VICE_DOWNSIDE_HP_PCT_PER_RANK,
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
