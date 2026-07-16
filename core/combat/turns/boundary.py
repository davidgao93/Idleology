"""
core/combat/turns/boundary.py — Centralised combat boundary transitions.

Provides three functions that all callers should use instead of scattering
explicit field resets across view files:

  reset_combat_transients(player)
      Full per-fight transient reset.  Used by:
        • Ascent   — every _next_floor call
        • Codex    — every _setup_next_wave call (all 7 waves of a chapter)
      NOT used for boss phase transitions (stacks/ward persist across phases).

      Ward is intentionally excluded — the rule differs per archetype:
        Ascent: fresh ward each floor (caller: combat_ward = get_combat_ward_value())
        Codex:  ward carried from baseline snapshot (caller: _restore_wave_baseline)

  reset_for_phase_transition(player)
      Minimal reset for boss phase transitions (Aphrodite, Lucifer, NEET, Gemini).
      Preserves all transient stacks, ward, combat_bonus accumulators, and
      Start-of-Combat passive bonuses (those only ever fire once, guarded by
      player.cs.combat_start_fired). Only resets invulnerability, which is
      genuinely per-phase rather than per-fight.

  fire_on_victory_effects(player) -> list[str]
      Fires passive effects that trigger on encounter victory.
      Must NOT be called on phase transitions (mid-fight, not a true victory).
      Called at: regular wins, Ascent floor clears, Codex wave clears, Uber wins.
      Returns log lines (currently empty — callers may display them if desired).
"""

from __future__ import annotations

from core.combat import jewel_engine as _je
from core.emojis import STAT_HP
from core.models import Player


def reset_combat_transients(player: Player) -> None:
    """Resets all per-fight transient stacks and flags.

    Ward and chapter_* penalties are intentionally excluded — see module docstring.
    Adding a new CombatState field that should reset between fights?  Add it here.
    """
    from core.hematurgy.engine import reset_hematurgy_transients

    cs = player.cs
    cs.is_invulnerable = False
    cs.voracious_stacks = 0
    cs.cursed_precision_active = False
    cs.gaze_stacks = 0
    cs.hunger_stacks = 0
    cs.celestial_vow_used = False
    cs.lucifer_pdr_burst = 0
    cs.is_snared = False
    cs.combat_start_fired = False
    _je.reset_jewel_transients(player)
    reset_hematurgy_transients(player)


def reset_for_phase_transition(player: Player) -> None:
    """Minimal reset for boss phase transitions.

    All stacks, ward, combat_bonus accumulators, and Start-of-Combat passive
    bonuses (Infernal/Void/partner/Hematurgy/Soul Stone, guarded by
    player.cs.combat_start_fired) persist — the fight is continuous, and
    those passives only ever fire once, at true Phase 1 start. Only
    invulnerability resets, since it is genuinely per-phase.
    """
    player.cs.is_invulnerable = False


def fire_on_victory_effects(player: Player) -> list[str]:
    """Fires passive effects that trigger on encounter victory.

    Do NOT call on phase transitions — those are mid-fight, not true victories.

    Returns log lines for optional display in the victory embed.
    """
    msgs: list[str] = []

    if player.get_weapon_infernal() == "soulreap":
        player.current_hp = player.total_max_hp
        msgs.append(f"{STAT_HP} **Soulreap** — restored to full HP!")

    return msgs
