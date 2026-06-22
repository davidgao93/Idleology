"""
core/settlement/encounter.py — Inline combat simulation for settlement crisis events.

Runs a full combat with the real engine (no interaction required) and returns a
structured result.  Used by bandit_raid, fire_hazard, void_incursion, and
plague_outbreak events when the player clicks the "Confront" button.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from core.models import Monster

_REPAIR_COSTS: dict[int, int] = {
    1: 5_000,
    2: 10_000,
    3: 15_000,
    4: 25_000,
    5: 50_000,
}

# Gold penalty range when the player loses a crisis encounter.
_DEFEAT_GOLD_MIN = 500
_DEFEAT_GOLD_MAX = 5_000

# Max rounds before we declare a draw (very defensive player vs. weak monster).
_MAX_ROUNDS = 200


@dataclass
class EncounterResult:
    player_won: bool
    rounds: int
    player_hp_remaining: int
    monster_hp_remaining: int
    gold_loss: int = 0  # only set on defeat
    reward_data: dict = field(default_factory=dict)
    reward_lines: list[str] = field(default_factory=list)


def get_repair_cost(tier: int) -> int:
    return _REPAIR_COSTS.get(max(1, min(5, tier)), 5_000)


async def run_settlement_encounter(
    bot,
    user_id: str,
    server_id: str,
    player_level: int,
) -> EncounterResult:
    """
    Simulate a full combat encounter for a settlement crisis.

    Loads the player with gear, generates a level-appropriate monster, and
    runs the real combat engine to completion.  Returns an EncounterResult
    regardless of outcome — the caller decides what to do with it.
    """
    from core.combat.mobgen.gen_mob import (
        calculate_monster_stats,
        finalize_monster_spawn,
    )
    from core.combat.turns import engine
    from core.items.factory import load_player

    user_row = await bot.database.users.get(user_id, server_id)
    player = await load_player(user_id, user_row, bot.database)

    # Generate a monster scaled to player level (no rarity multiplier for simplicity).
    difficulty = random.randint(2, 6) if player.level <= 80 else random.randint(8, 12)
    monster = Monster(
        name="Bandit Captain",
        level=player.level + player.ascension + difficulty,
        hp=1,
        max_hp=1,
        xp=0,
        attack=0,
        defence=0,
        modifiers=[],
        image="",
        flavor="",
        species="humanoid",
        is_boss=False,
        combat_round=0,
        is_essence=False,
    )
    monster = calculate_monster_stats(monster)
    base_hp = random.randint(0, 9) + int(
        10 * (monster.level ** random.uniform(1.6, 1.7))
    )
    monster.base_max_hp = base_hp
    monster.hp = base_hp
    monster.max_hp = base_hp
    monster.xp = random.randint(1, 9) + monster.level * 100
    finalize_monster_spawn(monster)

    # Work on copies so the original player/monster objects are never mutated.
    sim_player = copy.deepcopy(player)
    sim_monster = copy.deepcopy(monster)

    # Initialise combat state the same way CombatView does.
    from core.combat.turns.boundary import reset_combat_transients

    reset_combat_transients(sim_player)
    sim_player.cs.ward = sim_player.get_combat_ward_value()
    sim_player.current_hp = sim_player.total_max_hp
    engine.apply_stat_effects(sim_player, sim_monster)
    engine.apply_combat_start_passives(sim_player, sim_monster)

    rounds = 0
    while sim_player.current_hp > 0 and sim_monster.hp > 0 and rounds < _MAX_ROUNDS:
        rounds += 1
        sim_monster.combat_round = rounds

        # Player turn
        p_result = engine.process_player_turn(sim_player, sim_monster)
        if p_result.damage > 0:
            sim_monster.hp = max(0, sim_monster.hp - p_result.damage)
        if sim_monster.hp <= 0:
            break

        # Monster turn
        m_result = engine.process_monster_turn(sim_player, sim_monster)
        if m_result.hp_damage > 0:
            sim_player.current_hp = max(0, sim_player.current_hp - m_result.hp_damage)

    player_won = sim_monster.hp <= 0

    result = EncounterResult(
        player_won=player_won,
        rounds=rounds,
        player_hp_remaining=max(0, sim_player.current_hp),
        monster_hp_remaining=max(0, sim_monster.hp),
    )

    if player_won:
        # Apply full victory rewards (loot, XP, gold).
        from core.combat.economy.victory import apply_victory_rewards

        reward_data = await apply_victory_rewards(
            bot,
            user_id,
            server_id,
            sim_player,
            monster,
            message=None,
            combat_logger=None,
        )
        await bot.database.users.update_from_player_object(sim_player)
        # +50 Zeal bonus for defending the settlement.
        await bot.database.settlement.add_zeal(user_id, server_id, 50)
        result.reward_data = reward_data
        result.reward_lines = reward_data.get("msgs", [])
    else:
        # Gold penalty.
        gold_loss = random.randint(_DEFEAT_GOLD_MIN, _DEFEAT_GOLD_MAX)
        current_gold = await bot.database.users.get_gold(user_id)
        actual_loss = min(gold_loss, current_gold)
        if actual_loss > 0:
            await bot.database.users.modify_gold(user_id, -actual_loss)
        result.gold_loss = actual_loss

    return result
