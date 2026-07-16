"""core/inner_sanctum/mechanics.py — Inner Sanctum tree math.

get_tree_bonuses() is the single aggregator every combat/economy hook site
should call — no call site should re-parse `nodes_owned` directly, so all
tuning lives in data.py (costs/ranks/values) and here (aggregation formulas).
"""

from core.inner_sanctum.data import (
    ALL_NODES,
    DEICIDE_NODES,
    DEICIDE_UNLOCK_LEVEL,
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
    "owned_rank",
]


def owned_rank(node_def: dict, owned_value) -> int:
    """Ranks invested in a single node, regardless of archetype.
    - Plain ranked node: owned_value is a bare int rank.
    - Single-purchase choice node (`is_choice`): 1 if owned, else 0.
    - Ranked-choice node (`is_choice_ranked`): owned_value is
      {"choice": str, "rank": int}; returns the rank, or 0 if unpurchased."""
    if node_def.get("is_choice"):
        return 1 if owned_value else 0
    if node_def.get("is_choice_ranked"):
        return (owned_value or {}).get("rank", 0)
    return owned_value or 0


def get_node_cost(node_id: str, nodes_owned: dict) -> int | None:
    """Cost to buy the *next* rank of node_id, or None if maxed / invalid."""
    node_def = ALL_NODES.get(node_id)
    if not node_def:
        return None
    if node_def.get("is_choice"):
        return None if nodes_owned.get(node_id) else node_def["cost"]
    rank = owned_rank(node_def, nodes_owned.get(node_id))
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
    rank = owned_rank(node_def, nodes_owned.get(node_id))
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


def _sum_field(node_dict: dict, owned: dict, field_name: str) -> float:
    """Sums `rank * node[field_name]` across every node in node_dict that
    declares field_name — branch-agnostic, works for any node archetype via
    owned_rank(). Several nodes can share one field_name (e.g. Deicide's
    boss_dmg_pct_per_rank) so their contributions sum into one aggregate."""
    total = 0.0
    for node_id, node_def in node_dict.items():
        rank = owned_rank(node_def, owned.get(node_id))
        if rank <= 0:
            continue
        total += rank * node_def.get(field_name, 0.0)
    return total


def get_tree_bonuses(nodes_owned: dict) -> dict:
    """Returns all active Inner Sanctum bonus values, keyed by effect name."""
    owned = nodes_owned or {}

    _aff = owned.get("de_affinity")
    _aff_choice = _aff.get("choice") if isinstance(_aff, dict) else None
    _aff_rank = _aff.get("rank", 0) if isinstance(_aff, dict) else 0

    bonuses = {
        # Vice — every Vice node contributes to one or more of these via its
        # own *_per_rank keys in data.py; see _sum_field.
        "special_rarity_pct": _sum_field(VICE_NODES, owned, "special_rarity_per_rank"),
        "vice_monster_atk_pct": _sum_field(VICE_NODES, owned, "monster_atk_per_rank"),
        "vice_monster_def_pct": _sum_field(VICE_NODES, owned, "monster_def_per_rank"),
        "vice_monster_crit_pct": _sum_field(VICE_NODES, owned, "monster_crit_per_rank"),
        "vice_monster_hp_pct": _sum_field(VICE_NODES, owned, "monster_hp_per_rank"),
        "vice_monster_dmg_pct": _sum_field(VICE_NODES, owned, "monster_dmg_per_rank"),
        "rune_refinement_chance_pct": _sum_field(
            VICE_NODES, owned, "refine_chance_per_rank"
        ),
        "rune_potential_chance_pct": _sum_field(
            VICE_NODES, owned, "potential_chance_per_rank"
        ),
        "rune_shattering_chance_pct": _sum_field(
            VICE_NODES, owned, "shatter_chance_per_rank"
        ),
        "treasure_chance_pct": _sum_field(
            VICE_NODES, owned, "treasure_encounter_per_rank"
        ),
        "bonus_curio_chance": _sum_field(VICE_NODES, owned, "bonus_curio_per_rank"),
        "bonus_puzzlebox_chance": _sum_field(
            VICE_NODES, owned, "bonus_puzzlebox_per_rank"
        ),
        "treasure_stat_bonus_pct": _sum_field(
            VICE_NODES, owned, "treasure_stat_per_rank"
        ),
        # Recovery — each node pairs its own upside with its own downside.
        "stamina_save_chance": _sum_field(
            RECOVERY_NODES, owned, "stamina_save_chance_per_rank"
        ),
        "stamina_regen_bonus_chance": _sum_field(
            RECOVERY_NODES, owned, "stamina_regen_bonus_chance_per_rank"
        ),
        "exp_loss_reduction_pct": _sum_field(
            RECOVERY_NODES, owned, "exp_loss_reduction_per_rank"
        ),
        # Shared field name — Frugal Spirit + Deep Reserves both add flat
        # seconds to the no-stamina combat cooldown.
        "recovery_cooldown_penalty_sec": _sum_field(
            RECOVERY_NODES, owned, "cooldown_penalty_sec_per_rank"
        ),
        "rest_cost_penalty_pct": _sum_field(
            RECOVERY_NODES, owned, "rest_cost_pct_per_rank"
        ),
        # Deicide
        "boss_chance_bonus_pct": _sum_field(
            DEICIDE_NODES, owned, "boss_chance_bonus_per_rank"
        ),
        # Marked Prey — ranked-choice: the pick locks in the boss type, and
        # the rank (1-5) indexes the weight-shift table. No downside.
        "boss_affinity": _aff_choice,
        "boss_affinity_shift": (
            DEICIDE_NODES["de_affinity"]["affinity_shift_by_rank"][_aff_rank - 1]
            if _aff_choice and 1 <= _aff_rank <= 5
            else 0.0
        ),
        "corrupted_reroll_chance": _sum_field(
            DEICIDE_NODES, owned, "corrupted_reroll_chance_per_rank"
        ),
        "corrupted_monster_atk_pct": _sum_field(
            DEICIDE_NODES, owned, "corrupted_atk_pct_per_rank"
        ),
        "corrupted_monster_def_pct": _sum_field(
            DEICIDE_NODES, owned, "corrupted_def_pct_per_rank"
        ),
        "corrupted_monster_hp_pct": _sum_field(
            DEICIDE_NODES, owned, "corrupted_hp_pct_per_rank"
        ),
        "boss_rune_chance_pct": _sum_field(
            DEICIDE_NODES, owned, "boss_rune_chance_per_rank"
        ),
        "boss_dupe_chance": _sum_field(DEICIDE_NODES, owned, "dupe_chance_per_rank"),
        "boss_sigil_chance_pct": _sum_field(
            DEICIDE_NODES, owned, "sigil_chance_per_rank"
        ),
        "deicide_boss_hp_pct": _sum_field(
            DEICIDE_NODES, owned, "boss_hp_pct_per_rank"
        ),
        # Shared field name — Reliquary Sense + Twinned Fortune + Sigil
        # Fortune all add to bosses' damage dealt.
        "deicide_boss_dmg_pct": _sum_field(
            DEICIDE_NODES, owned, "boss_dmg_pct_per_rank"
        ),
    }
    return bonuses
