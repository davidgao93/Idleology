"""
Paradise Jewel combat engine.
Called from player_turn.py, monster_turn.py, and process_heal.
All jewel charge accumulation, unleash effects, and DoT ticks live here.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from core.combat.helpers import _add_ward
from core.paradise import mechanics as M
from core.paradise.data import SKILL_JEWELS

if TYPE_CHECKING:
    from core.models import Monster, Player


# ---------------------------------------------------------------------------
# Internal: get equipped skill shortcut
# ---------------------------------------------------------------------------


def _equipped(player: "Player") -> str | None:
    jop = getattr(player, "jewel_of_paradise", None)
    if not jop:
        return None
    return jop.get("equipped_skill")


def _jop(player: "Player") -> dict | None:
    jop = getattr(player, "jewel_of_paradise", None)
    if not jop or not jop.get("equipped_skill"):
        return None
    return jop


# ---------------------------------------------------------------------------
# Unleash effects
# ---------------------------------------------------------------------------


def _unleash_surge(
    player: "Player", monster: "Monster", data: dict, log: list[str]
) -> int:
    """Returns extra damage dealt to monster."""
    eff_lvl = M.get_effective_level("surge", data, M.mastery_bonus(data))
    pct = M.roll_scale_pct("surge", eff_lvl)
    fury = M.get_fury_pct(data)
    spec = M.get_spec_pct(data, "surge")
    force = M.get_force_pct(data)

    total_mult = 1.0 + (fury + spec + force) / 100
    atk = player.get_total_attack()
    dmg = max(1, int(atk * pct / 100 * total_mult))
    dmg = min(dmg, max(1, monster.hp))
    monster.hp = max(0, monster.hp - dmg)
    log.append(f"⚡ **Surge** unleashes a lightning storm for 🗡️ **{dmg}** damage!")
    return dmg


def _unleash_cataclysm(player: "Player", data: dict, log: list[str]) -> None:
    """Primes Cataclysm: next hit is a guaranteed crit with bonus multiplier."""
    eff_lvl = M.get_effective_level("cataclysm", data, M.mastery_bonus(data))
    bonus_pct = M.roll_scale_pct("cataclysm", eff_lvl)
    force = M.get_force_pct(data)
    spec = M.get_spec_pct(data, "cataclysm")
    final_bonus = bonus_pct * (1 + (force + spec) / 100)
    player.jewel_cataclysm_primed = True
    player.jewel_cataclysm_bonus_multi = final_bonus / 100  # stored as multiplier bonus
    log.append(
        f"💥 **Cataclysm** primes! Next attack: guaranteed crit (+{final_bonus:.0f}% crit multi)."
    )


def _unleash_acrimony(
    player: "Player", monster: "Monster", data: dict, log: list[str]
) -> int:
    """Venom burst + DoT. Returns immediate damage dealt."""
    eff_lvl = M.get_effective_level("acrimony", data, M.mastery_bonus(data))
    pct = M.roll_scale_pct("acrimony", eff_lvl)
    fury = M.get_fury_pct(data)
    spec = M.get_spec_pct(data, "acrimony")
    force = M.get_force_pct(data)
    total_mult = 1.0 + (fury + spec + force) / 100

    atk = player.get_total_attack()
    imm_dmg = max(1, int(atk * pct / 100 * total_mult))
    imm_dmg = min(imm_dmg, max(1, monster.hp))
    monster.hp = max(0, monster.hp - imm_dmg)

    # Set up DoT (25% of immediate, for 4 turns)
    dot_per_turn = max(1, int(imm_dmg * 0.25))
    player.jewel_acrimony_dot = 4
    player.jewel_acrimony_dot_dmg = dot_per_turn

    log.append(
        f"🐍 **Acrimony** venom bursts for 🗡️ **{imm_dmg}** damage"
        f" + 🐍 **{dot_per_turn}**/turn DoT for 4 turns!"
    )
    return imm_dmg


def _unleash_wardforge(player: "Player", data: dict, log: list[str]) -> None:
    """Massive ward burst + primes bonus damage on next attack from current ward."""
    eff_lvl = M.get_effective_level("wardforge", data, M.mastery_bonus(data))
    ward_gain_raw = int(M.roll_scale_pct("wardforge", eff_lvl))
    arcane = M.get_arcane_pct(data)
    spec = M.get_spec_pct(data, "wardforge")
    force = M.get_force_pct(data)
    total_mult = 1.0 + (arcane + spec + force) / 100
    ward_gain = max(1, int(ward_gain_raw * total_mult))
    added = _add_ward(player, ward_gain, log, "Wardforge")
    # 30% of current ward as bonus damage on next attack
    bonus_dmg = int(player.combat_ward * 0.30)
    player.jewel_wardforge_bonus_dmg = bonus_dmg
    log.append(
        f"🛡️ **Wardforge** erupts: +🔮 **{added}** ward!"
        f" Next attack gains **{bonus_dmg}** bonus damage from ward!"
    )


def _unleash_bastion(
    player: "Player", monster: "Monster", data: dict, hit_dmg: int, log: list[str]
) -> int:
    """Reflect damage. Returns reflected damage."""
    eff_lvl = M.get_effective_level("bastion", data, M.mastery_bonus(data))
    pct = M.roll_scale_pct("bastion", eff_lvl)
    fury = M.get_fury_pct(data)
    spec = M.get_spec_pct(data, "bastion")
    force = M.get_force_pct(data)
    total_mult = 1.0 + (fury + spec + force) / 100
    reflect = max(1, int(hit_dmg * pct / 100 * total_mult))
    reflect = min(reflect, max(1, monster.hp))
    monster.hp = max(0, monster.hp - reflect)
    log.append(
        f"🔱 **Bastion** reflects 🗡️ **{reflect}** damage back at {monster.name}!"
    )
    return reflect


def _unleash_siphon(player: "Player", data: dict, log: list[str]) -> int:
    """Burst heal + convert 50% to ward. Returns actual HP healed."""
    eff_lvl = M.get_effective_level("siphon", data, M.mastery_bonus(data))
    pct = M.roll_scale_pct("siphon", eff_lvl)
    sustenance = M.get_sustenance_pct(data)
    spec = M.get_spec_pct(data, "siphon")
    force = M.get_force_pct(data)
    total_mult = 1.0 + (sustenance + spec + force) / 100
    heal_raw = max(1, int(player.total_max_hp * pct / 100 * total_mult))
    actual_hp_heal = min(heal_raw, player.total_max_hp - player.current_hp)
    player.current_hp = min(player.total_max_hp, player.current_hp + actual_hp_heal)
    # 50% as ward
    ward_from_heal = int(heal_raw * 0.50)
    if ward_from_heal > 0:
        added = _add_ward(player, ward_from_heal, log, "Siphon")
        log.append(
            f"💚 **Siphon** restores 💚 **{actual_hp_heal}** HP"
            f" and generates 🔮 **{added}** ward!"
        )
    else:
        log.append(f"💚 **Siphon** restores 💚 **{actual_hp_heal}** HP!")
    return actual_hp_heal


def _unleash_onslaught(player: "Player", data: dict, log: list[str]) -> None:
    """Primes ATK multiplier for the next attack."""
    eff_lvl = M.get_effective_level("onslaught", data, M.mastery_bonus(data))
    bonus_pct = M.roll_scale_pct("onslaught", eff_lvl)
    spec = M.get_spec_pct(data, "onslaught")
    force = M.get_force_pct(data)
    final_bonus = bonus_pct * (1 + (spec + force) / 100)
    player.jewel_onslaught_primed = True
    player.jewel_onslaught_bonus_pct = final_bonus  # stored as %
    log.append(
        f"🔥 **Onslaught** surges! Next attack: +**{final_bonus:.0f}%** ATK multiplier."
    )


def _unleash_draught(player: "Player", data: dict, log: list[str]) -> None:
    """Generate 0-N potions; overflow becomes ward."""
    eff_lvl = M.get_effective_level("draught", data, M.mastery_bonus(data))
    low, high = M.draught_potion_range(eff_lvl)
    spec = M.get_spec_pct(data, "draught")
    force = M.get_force_pct(data)
    # Force/spec influence the upper bound slightly
    adjusted_high = int(high * (1 + (spec + force) / 100))
    generated = random.randint(low, max(low, adjusted_high))

    potion_cap = 20
    overflow = max(0, (player.potions + generated) - potion_cap)
    actual_potions = generated - overflow
    player.potions += actual_potions

    parts = [f"🧪 **Draught** distills **{actual_potions}** potion(s)!"]
    if overflow > 0:
        ward_gain = overflow * 200
        added = _add_ward(player, ward_gain, log, "Draught overflow")
        parts.append(f"Overflow → 🔮 **{added}** ward!")
    log.append(" ".join(parts))


# ---------------------------------------------------------------------------
# Main charge trigger dispatcher
# ---------------------------------------------------------------------------


SKILL_TRIGGERS = {
    "surge": "hit",
    "cataclysm": "crit",
    "acrimony": "miss",
    "wardforge": "ward",
    "bastion": "hp_damage_taken",
    "siphon": "heal",
    "onslaught": "low_hp_turn",
    "draught": "potion",
}


def _fire_unleash(
    skill_key: str,
    player: "Player",
    monster: "Monster | None",
    data: dict,
    log: list[str],
    trigger_value: int = 0,
) -> None:
    """Calls the correct unleash function for the given skill."""
    if skill_key == "surge":
        if monster:
            _unleash_surge(player, monster, data, log)
    elif skill_key == "cataclysm":
        _unleash_cataclysm(player, data, log)
    elif skill_key == "acrimony":
        if monster:
            _unleash_acrimony(player, monster, data, log)
    elif skill_key == "wardforge":
        _unleash_wardforge(player, data, log)
    elif skill_key == "bastion":
        if monster and trigger_value > 0:
            _unleash_bastion(player, monster, data, trigger_value, log)
    elif skill_key == "siphon":
        _unleash_siphon(player, data, log)
    elif skill_key == "onslaught":
        _unleash_onslaught(player, data, log)
    elif skill_key == "draught":
        _unleash_draught(player, data, log)


def _do_charge_and_maybe_unleash(
    player: "Player",
    monster: "Monster | None",
    data: dict,
    skill_key: str,
    amount: int,
    log: list[str],
    trigger_value: int = 0,
) -> None:
    """
    Adds charges and fires unleash if threshold is met.
    Also handles Mirage (double proc) and Lingering (keep charges).
    """
    did_unleash, charges_after = M.add_charge(data, skill_key, amount)
    if not did_unleash:
        return

    def _do_unleash() -> None:
        _fire_unleash(skill_key, player, monster, data, log, trigger_value)

    # First unleash
    M.consume_charges(data, skill_key)
    _do_unleash()

    # Mirage: chance to double proc
    if M.should_double_proc(data):
        defn_name = (
            SKILL_JEWELS[skill_key].name if skill_key in SKILL_JEWELS else skill_key
        )
        log.append(f"✨ **Mirage** — {defn_name} triggers twice!")
        _do_unleash()


def process_jewel_trigger(
    player: "Player",
    monster: "Monster | None",
    trigger_type: str,
    trigger_value: int,
    log: list[str],
) -> None:
    """
    Public entry point for jewel charge triggers.
    trigger_type: one of "hit", "crit", "miss", "ward", "hp_damage_taken",
                          "heal", "low_hp_turn", "potion"
    trigger_value: relevant numeric value (e.g. damage taken for "hp_damage_taken")
    """
    data = _jop(player)
    if not data:
        return
    skill_key = data.get("equipped_skill")
    if not skill_key:
        return
    expected_trigger = SKILL_TRIGGERS.get(skill_key)
    if expected_trigger != trigger_type:
        return
    _do_charge_and_maybe_unleash(
        player, monster, data, skill_key, 1, log, trigger_value
    )


# ---------------------------------------------------------------------------
# Acrimony DoT tick (called at start of player turn)
# ---------------------------------------------------------------------------


def tick_acrimony_dot(player: "Player", monster: "Monster", log: list[str]) -> None:
    """Tick Acrimony DoT. Call at the start of process_player_turn."""
    if player.jewel_acrimony_dot <= 0:
        return
    dot_dmg = player.jewel_acrimony_dot_dmg
    if dot_dmg > 0 and monster.hp > 0:
        actual = min(dot_dmg, monster.hp)
        monster.hp = max(0, monster.hp - actual)
        log.append(
            f"🐍 **Acrimony** venom pulses for **{actual}** DoT damage! ({player.jewel_acrimony_dot - 1} turns left)"
        )
    player.jewel_acrimony_dot -= 1
    if player.jewel_acrimony_dot <= 0:
        player.jewel_acrimony_dot_dmg = 0


# ---------------------------------------------------------------------------
# Onslaught low-HP charge (called at start of player turn)
# ---------------------------------------------------------------------------


def tick_onslaught_charge(player: "Player", monster: "Monster", log: list[str]) -> None:
    """Add an Onslaught charge if HP < 50%. Call at the start of process_player_turn."""
    data = _jop(player)
    if not data:
        return
    if data.get("equipped_skill") != "onslaught":
        return
    if player.current_hp < player.total_max_hp * 0.50:
        _do_charge_and_maybe_unleash(player, monster, data, "onslaught", 1, log)


# ---------------------------------------------------------------------------
# Cataclysm + Onslaught: apply primed bonuses in player_turn
# ---------------------------------------------------------------------------


def apply_cataclysm_crit_bonus(player: "Player") -> float:
    """
    Returns the bonus crit multiplier from Cataclysm if primed.
    Resets the primed flag. Call before rolling crit damage.
    """
    if not getattr(player, "jewel_cataclysm_primed", False):
        return 0.0
    bonus = getattr(player, "jewel_cataclysm_bonus_multi", 0.0)
    player.jewel_cataclysm_primed = False
    player.jewel_cataclysm_bonus_multi = 0.0
    return bonus


def apply_onslaught_mult(player: "Player") -> float:
    """
    Returns the bonus attack multiplier % from Onslaught if primed.
    Resets the primed flag. Call in _pt_attack_multiplier.
    """
    if not getattr(player, "jewel_onslaught_primed", False):
        return 0.0
    bonus_pct = getattr(player, "jewel_onslaught_bonus_pct", 0.0)
    player.jewel_onslaught_primed = False
    player.jewel_onslaught_bonus_pct = 0.0
    return bonus_pct


async def save_jewel_state(bot, user_id: str, player: "Player") -> None:
    """Persist jewel charges, skill levels, and skill progress after combat.
    Call alongside update_from_player_object at every combat exit point."""
    data = getattr(player, "jewel_of_paradise", None)
    if not data or not data.get("equipped_skill"):
        return
    try:
        # Skill progress (only for natural-level cap 20)
        equipped = data["equipped_skill"]
        if equipped:
            M.add_skill_progress(data, equipped)
        await bot.database.paradise.save(user_id, data)
    except Exception:
        pass


def consume_wardforge_bonus(player: "Player") -> int:
    """
    Returns pending Wardforge bonus damage and resets it.
    Call once per attack in _pt_apply_to_monster or after damage rolls.
    """
    bonus = getattr(player, "jewel_wardforge_bonus_dmg", 0)
    player.jewel_wardforge_bonus_dmg = 0
    return bonus


def reset_jewel_charges(player: "Player") -> None:
    """Reset accumulated skill charges to zero.
    Call at the start of every new standalone encounter (normal combat, ascent session, codex run).
    Does NOT reset primed/DoT transients — those are managed by reset_jewel_transients.
    """
    jop = getattr(player, "jewel_of_paradise", None)
    if jop:
        jop["skill_charges"] = {}


def reset_jewel_transients(player: "Player") -> None:
    """Reset per-fight jewel primed/DoT states in CombatState.
    Call between each individual monster in Ascent and Codex.
    Does NOT reset skill_charges — those persist within a session."""
    player.jewel_cataclysm_primed = False
    player.jewel_cataclysm_bonus_multi = 0.0
    player.jewel_onslaught_primed = False
    player.jewel_onslaught_bonus_pct = 0.0
    player.jewel_wardforge_bonus_dmg = 0
    player.jewel_acrimony_dot = 0
    player.jewel_acrimony_dot_dmg = 0
