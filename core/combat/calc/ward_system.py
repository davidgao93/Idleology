"""
ward_system.py — Ward generation and management.

Testable in isolation: add_ward is a pure accumulator with a single multiplier
special case; generate_player_ward_on_hit is the only caller of on-hit ward sources.

Public API
----------
add_ward(player, amount, log, label="") -> int
generate_player_ward_on_hit(player, raw_damage, is_crit, log) -> None

_add_ward                          # backward-compat alias used by engine.py re-exports
"""

from __future__ import annotations

from core.models import Player


def add_ward(player: Player, amount: int, log: list, label: str = "") -> int:
    """Adds ward to the player, doubling if the NEET helmet corrupted essence is active.
    Vital Resonance (hematurgy): X% of ward generated → HP heal.
    Ward Inoculation (hematurgy): redirects ward to a damage buffer instead.
    Returns the final amount added to ward (may be 0). Logs only if label is provided."""
    if amount <= 0:
        return 0
    if player.get_helmet_corrupted_essence() == "neet":
        amount *= 2
        if label:
            log.append(
                f"🌑 **Void Resonance** doubles ward gain! ({label}: +{amount} 🔮)"
            )

    # Hematurgy hook: may redirect to damage buffer (Ward Inoculation) or heal (Vital Resonance)
    if player.hematurgy_passives:
        from core.hematurgy.engine import on_ward_gained
        amount = on_ward_gained(player, amount, log)

    if amount <= 0:
        return 0
    player.combat_ward += amount
    return amount


# Backward-compat alias — engine.py and other callers import `_add_ward` from helpers.py
# which re-exports this symbol.
_add_ward = add_ward


def generate_player_ward_on_hit(
    player: Player, raw_damage: int, is_hit: bool, is_crit: bool, log: list[str]
) -> None:
    """Phase 6 — ward generation triggered by a player hit or crit.

    Sources handled here:
    - Ward-Touched glove passive (normal hits only, not crits or misses)
    - Ward-Fused glove passive (crits only)
    - Arcane weapon passive (hits and crits; does NOT fire on misses)
    """
    from core.combat import jewel_engine as _je
    from core.combat.calc.calcs import fmt_weapon_passive, get_weapon_tier

    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0

    if is_hit and not is_crit and glove_passive == "ward-touched" and glove_lvl > 0:
        ward = int(glove_lvl * 25)
        if ward > 0:
            added = add_ward(player, ward, log)
            log.append(f"**Ward-Touched ({glove_lvl})** generates 🔮 **{added}** ward!")
            _je.process_jewel_trigger(player, None, "ward", added, log)

    if is_crit and glove_passive == "ward-fused" and glove_lvl > 0:
        ward = int(glove_lvl * 50)
        if ward > 0:
            added = add_ward(player, ward, log)
            log.append(f"**Ward-Fused ({glove_lvl})** generates 🔮 **{added}** ward!")
            _je.process_jewel_trigger(player, None, "ward", added, log)

    if is_hit or is_crit:
        idx, name = get_weapon_tier(player, "arcane")
        if idx >= 0:
            arcane_ward = (idx + 1) * 25
            added = add_ward(player, arcane_ward, log)
            if added > 0:
                log.append(
                    f"🔮 **{fmt_weapon_passive(name)}** — the weapon pulses, generating **{added}** Ward!"
                )
                _je.process_jewel_trigger(player, None, "ward", added, log)
