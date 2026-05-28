"""
engine.py — thin coordinator.

All combat logic lives in the focused sub-modules:
  helpers.py      — result dataclasses, _add_ward
  passives.py     — combat-start passives, apply_stat_effects
  player_turn.py  — process_player_turn, process_heal, _pt_* phases
  monster_turn.py — process_monster_turn, _roll_monster_damage
  calcs.py        — hit chance, damage, crit chance (pure math)
  combat_log.py   — CombatLogger, log_combat_debug

Re-exports below keep all existing callers (views, cogs) working unchanged.
"""

from core.combat.calc.ward_system import _add_ward
from core.combat.combat_log import CombatLogger, log_combat_debug
from core.combat.turns.helpers import MonsterTurnResult, PlayerTurnResult
from core.combat.turns.monster_turn import process_monster_turn
from core.combat.turns.passives import apply_combat_start_passives, apply_stat_effects
from core.combat.turns.player_turn import process_heal, process_player_turn

__all__ = [
    # Result types
    "PlayerTurnResult",
    "MonsterTurnResult",
    # Ward helper (used by views and uber views)
    "_add_ward",
    # Combat lifecycle
    "apply_stat_effects",
    "apply_combat_start_passives",
    "process_player_turn",
    "process_monster_turn",  # now accepts optional context_note="" for retaliation logging
    "process_heal",
    # Logging
    "CombatLogger",
    "log_combat_debug",
]
