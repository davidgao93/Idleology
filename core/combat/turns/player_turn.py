"""
player_turn.py — Player turn orchestrator.

This module wires together the focused sub-modules in the correct order.
Business logic lives in:
  hit_calc.py    — build_attack_multiplier, resolve_hit, resolve_crit
  damage_calc.py — calc_crit_damage, calc_hit_damage, calc_miss_damage,
                   apply_monster_damage_reduction, apply_damage_to_monster
  ward_system.py — add_ward, generate_player_ward_on_hit
"""

import random

from core.combat import jewel_engine as _je
from core.combat.calc.damage_calc import (
    apply_damage_to_monster,
    apply_monster_damage_reduction,
    calc_crit_damage,
    calc_hit_damage,
    calc_miss_damage,
)
from core.combat.calc.hit_calc import build_attack_multiplier, resolve_crit, resolve_hit
from core.combat.calc.ward_system import generate_player_ward_on_hit
from core.combat.helpers import PlayerTurnResult, _add_ward
from core.models import Monster, Player

# ---------------------------------------------------------------------------
# Healing
# ---------------------------------------------------------------------------


def process_heal(player: Player, monster=None) -> str:
    """Handles the logic of a player using a potion.
    Pass *monster* so venomous_tincture can deal damage to it.
    """
    if player.potions <= 0:
        return f"{player.name} has no potions left to use!"

    if player.current_hp >= player.total_max_hp:
        return f"{player.name} is already full HP!"

    heal_pct = 0.30

    if monster is not None and monster.has_modifier("Parching"):
        heal_pct *= 1 - monster.get_modifier_value("Parching")

    if player.equipped_boot and player.equipped_boot.passive == "cleric":
        heal_pct += player.equipped_boot.passive_lvl * 0.10

    potion_passives_by_type = {
        p["passive_type"]: p["passive_value"] for p in player.potion_passives
    }

    fermented = potion_passives_by_type.get("fermented_brew", 0)
    if fermented:
        heal_pct += fermented / 100.0

    heal_amount = int((player.total_max_hp * heal_pct) + random.randint(1, 6))

    if potion_passives_by_type.get("unstable_mixture"):
        if random.random() < 0.5:
            heal_amount *= 2
            _unstable_result = "doubled"
        else:
            heal_amount = max(1, heal_amount // 2)
            _unstable_result = "halved"
    else:
        _unstable_result = None

    if player.apothecary_workers > 0:
        flat_bonus = int(player.apothecary_workers * 0.2)
        heal_amount += flat_bonus

    overcap = potion_passives_by_type.get("overcap_brew", 0)
    overcap_cap = int(player.total_max_hp * (overcap / 100.0)) if overcap else 0

    potential_hp = player.current_hp + heal_amount
    overheal = 0
    if potential_hp > player.total_max_hp:
        excess = potential_hp - player.total_max_hp
        helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        overheal = excess * helmet_lvl

        if overcap_cap > 0:
            stored = min(excess, overcap_cap)
            player.alchemy_overcap_hp = stored
        player.current_hp = player.total_max_hp
    else:
        player.current_hp = potential_hp

    if player.get_armor_passive() == "Alchemist" and random.random() < 0.30:
        msg_prefix = "⚗️ **Alchemist** preserved your potion!\n"
    else:
        player.potions -= 1
        msg_prefix = ""

    msg = (
        msg_prefix
        + f"{player.name} uses a potion and heals for **{max(0, heal_amount - overheal)}** HP!"
    )
    if player.apothecary_workers > 0:
        msg += f" (Apothecary: +{int(player.apothecary_workers * 0.2)})"

    if _unstable_result:
        msg += f"\n🌀 **Unstable Mixture** — heal was {_unstable_result}!"

    if player.get_helmet_passive() == "divine" and overheal > 0:
        added = _add_ward(player, overheal, [], "Divine")
        msg += f"\n**Divine** converts **{added}** overheal into 🔮 Ward!"

    if overcap_cap > 0 and getattr(player, "alchemy_overcap_hp", 0) > 0:
        msg += (
            f"\n💥 **Overcap Brew** — stored **{player.alchemy_overcap_hp}** temp HP!"
        )

    ward_inf = potion_passives_by_type.get("ward_infusion", 0)
    if ward_inf:
        ward_gain = int(heal_amount * (ward_inf / 100.0))
        added = _add_ward(player, ward_gain, [], "Ward Infusion")
        msg += f"\n🔮 **Ward Infusion** generates **{added}** Ward!"

    linger = potion_passives_by_type.get("lingering_remedy", 0)
    if linger:
        player.alchemy_linger_hp = int(linger)
        player.alchemy_linger_turns = 3
        msg += f"\n🌿 **Lingering Remedy** — +{player.alchemy_linger_hp} HP/turn for 3 turns!"

    if potion_passives_by_type.get("bottled_courage"):
        player.alchemy_guaranteed_hit = True
        msg += "\n⚔️ **Bottled Courage** — your next attack cannot miss!"

    draft = potion_passives_by_type.get("warriors_draft", 0)
    if draft:
        player.alchemy_atk_boost_pct = draft / 100.0
        msg += f"\n💪 **Warrior's Draft** — +{draft:.0f}% ATK on next attack!"

    iron = potion_passives_by_type.get("iron_skin", 0)
    if iron:
        player.alchemy_def_boost_pct = iron / 100.0
        player.alchemy_def_boost_turns = 2
        msg += f"\n🛡️ **Iron Skin** — +{iron:.0f}% DEF for 2 monster turns!"

    dulled = potion_passives_by_type.get("dulled_pain", 0)
    if dulled:
        player.alchemy_dmg_reduction_pct = dulled / 100.0
        player.alchemy_dmg_reduction_turns = 1
        msg += f"\n🩹 **Dulled Pain** — -{dulled:.0f}% damage from next monster attack!"

    venom_mult = potion_passives_by_type.get("venom_cure", 0)
    if venom_mult and monster is not None and monster.hp > 0:
        venom_dmg = int(heal_amount * venom_mult)
        monster.hp = max(0, monster.hp - venom_dmg)
        msg += (
            f"\n🐍 **Venom Cure** courses through the enemy for **{venom_dmg}** damage!"
        )

    msg += f"\n**{player.potions}** potions left."

    _heal_jewel_log: list[str] = []
    _je.process_jewel_trigger(player, monster, "potion", 0, _heal_jewel_log)
    if _heal_jewel_log:
        msg += "\n" + "\n".join(_heal_jewel_log)

    if player.current_hp > 0:
        _siphon_log: list[str] = []
        _je.process_jewel_trigger(player, monster, "heal", 0, _siphon_log)
        if _siphon_log:
            msg += "\n" + "\n".join(_siphon_log)

    return msg


# ---------------------------------------------------------------------------
# Post-damage phases — these remain here as they don't fit the pure modules
# ---------------------------------------------------------------------------


def _pt_post_hit_effects(
    player: Player, monster: Monster, damage: int, is_crit: bool, log: list[str]
) -> None:
    """Phase 8 — effects that fire after damage lands: leech, bloodthirst, ward regen."""
    if damage <= 0:
        return

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "leeching" and helmet_lvl > 0:
        heal = int(damage * (0.02 * helmet_lvl))
        if heal > 0:
            player.current_hp = min(player.total_max_hp, player.current_hp + heal)
            log.append(f"**Leeching** drains life, healing you for **{heal}** HP.")
            _je.process_jewel_trigger(player, monster, "heal", heal, log)

    if is_crit:
        bloodthirst_pct = player.get_tome_bonus("bloodthirst")
        if bloodthirst_pct > 0:
            heal = max(1, int(damage * (bloodthirst_pct / 100)))
            player.current_hp = min(player.total_max_hp, player.current_hp + heal)
            log.append(
                f"**Bloodthirst** siphons **{heal}** HP from the critical strike."
            )
            _je.process_jewel_trigger(player, monster, "heal", heal, log)

    if player.get_celestial_armor_passive() == "celestial_ghostreaver":
        regen = random.randint(50, 200)
        added = _add_ward(player, regen, log)
        log.append(f"✨ **Celestial Ghostreaver** restores **{added}** 🔮 Ward!")
        _je.process_jewel_trigger(player, monster, "ward", added, log)


def _pt_track_pending(player: Player, damage: int, log: list[str]) -> None:
    """Phase 9 — accumulate pending XP/gold from glove passives."""
    if damage <= 0:
        return
    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "equilibrium" and glove_lvl > 0:
        player.equilibrium_bonus_xp_pending += int(damage * (glove_lvl * 0.05))
    if glove_passive == "plundering" and glove_lvl > 0:
        player.plundering_bonus_gold_pending += int(damage * (glove_lvl * 0.10))


def _pt_partner_effects(
    player: Player,
    monster: Monster,
    is_hit: bool,
    is_crit: bool,
    damage_dealt: int = 0,
    sigmund_proc: bool = False,
) -> tuple[str, str]:
    """
    Partner per-turn effects. Returns (partner_log, partner_name).
    Modifies monster.hp and player state directly.
    damage_dealt: actual damage dealt to the monster this turn (for co_ward_leech).
    sigmund_proc: whether sig_co_sigmund already fired this turn (for display only).
    """
    partner = player.active_partner
    if not partner:
        return "", ""

    parts = []

    for key, lvl in partner.combat_skills:
        if not key:
            continue
        if key == "co_joint_attack" and monster.hp > 0:
            if random.random() < lvl * 0.10:
                dmg = random.randint(1, max(1, partner.total_attack * 2))
                dmg = min(dmg, monster.hp)
                monster.hp = max(0, monster.hp - dmg)
                parts.append(
                    f"⚔️ **Joint Attack Lv.{lvl}** — {partner.name} strikes for **{dmg}** damage!"
                )
        elif (
            key == "co_heal"
            and monster.combat_round % 3 == 0
            and monster.combat_round > 0
        ):
            heal = int(player.total_max_hp * lvl * 0.01)
            if heal > 0:
                player.current_hp = min(player.total_max_hp, player.current_hp + heal)
                parts.append(
                    f"💚 **Heal Lv.{lvl}** — {partner.name} restores **{heal}** HP!"
                )
                _je.process_jewel_trigger(player, monster, "heal", heal, parts)
        elif key == "co_ward_regen":
            ward_gain = lvl * 10
            added = _add_ward(player, ward_gain, [])
            if added > 0:
                parts.append(
                    f"🔮 **Ward Regen Lv.{lvl}** — {partner.name} restores **{added}** Ward!"
                )
                _je.process_jewel_trigger(player, monster, "ward", added, parts)
        elif key == "co_ward_leech" and (is_hit or is_crit) and damage_dealt > 0:
            leech_base = max(1, int(damage_dealt * lvl * 0.001))
            added = _add_ward(player, leech_base, [])
            if added > 0:
                parts.append(
                    f"🔮 **Ward Leech Lv.{lvl}** — {partner.name} siphons **{added}** Ward!"
                )
                _je.process_jewel_trigger(player, monster, "ward", added, parts)
        elif key == "co_execute" and monster.hp > 0:
            threshold_pct = lvl / 100
            if monster.hp <= int(monster.max_hp * threshold_pct):
                dmg = monster.hp
                monster.hp = 0
                parts.append(
                    f"💀 **Execute Lv.{lvl}** — {partner.name} executes the "
                    f"{monster.name}! (**{dmg}** damage)"
                )

    if sigmund_proc:
        sig_lvl = partner.sig_combat_lvl
        parts.append(
            f"🐕 **Decisive Strike Lv.{sig_lvl}** — the hounds drive your strike to double power!"
        )

    partner_log = "\n".join(parts)
    partner_name = f"🤝 {partner.name}" if parts else ""
    return partner_log, partner_name


def _pt_check_cull(player: Player, monster: Monster, log: list[str]) -> None:
    """Phase 10 — culling strike: if monster HP is below threshold, reduce to 1."""
    from core.combat.calc.calcs import get_weapon_tier

    if monster.hp <= 0:
        return
    idx, _ = get_weapon_tier(player, "cull")
    if idx >= 0:
        threshold = (idx + 1) * 0.08
        if monster.hp <= (monster.max_hp * threshold):
            cull_dmg = monster.hp - 1
            if cull_dmg > 0:
                monster.hp = 1
                log.append(
                    f"{player.name}'s weapon culls the weakened {monster.name}, "
                    f"dealing an additional 🪓 __**{cull_dmg}**__ damage!"
                )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def process_player_turn(player: Player, monster: Monster) -> PlayerTurnResult:
    """Executes the player's turn, applying damage to the monster and returning the combat log."""
    log: list[str] = []
    calc: list[str] = []

    _je.tick_acrimony_dot(player, monster, log)
    _je.tick_onslaught_charge(player, monster, log)

    if player.alchemy_linger_turns > 0:
        player.current_hp = min(
            player.total_max_hp, player.current_hp + player.alchemy_linger_hp
        )
        log.append(
            f"🌿 **Lingering Remedy** restores **{player.alchemy_linger_hp}** HP! "
            f"({player.alchemy_linger_turns - 1} turn{'s' if player.alchemy_linger_turns - 1 != 1 else ''} left)"
        )
        player.alchemy_linger_turns -= 1

    attack_multiplier = build_attack_multiplier(player, monster, log, calc)
    is_hit, attack_multiplier = resolve_hit(
        player, monster, attack_multiplier, log, calc
    )

    _sigmund_proc = False
    if is_hit:
        _partner = player.active_partner
        if (
            _partner
            and _partner.sig_combat_key == "sig_co_sigmund"
            and _partner.sig_combat_lvl >= 1
            and random.random() < _partner.sig_combat_lvl * 0.02
        ):
            attack_multiplier *= 2
            _sigmund_proc = True

    is_crit = resolve_crit(player, monster, is_hit, log, calc)

    if is_hit and getattr(player, "jewel_cataclysm_primed", False):
        is_crit = True

    if player.get_glove_corrupted_essence() == "neet":
        is_hit = False
        is_crit = False
        calc.append("  neet: accuracy 0, always miss")
        log.append(
            "🌑 **Void Form** — accuracy reduced to zero, the strike phases through!"
        )

    if is_crit:
        raw_damage = calc_crit_damage(player, monster, attack_multiplier, log, calc)
    elif is_hit:
        raw_damage = calc_hit_damage(player, monster, attack_multiplier, log, calc)
    else:
        raw_damage = calc_miss_damage(player, monster, attack_multiplier, log, calc)

    actual_damage = apply_monster_damage_reduction(monster, raw_damage, log, calc)
    generate_player_ward_on_hit(player, raw_damage, is_crit, log)
    final_hit = apply_damage_to_monster(player, monster, actual_damage, log)
    _pt_post_hit_effects(player, monster, final_hit, is_crit, log)
    _pt_track_pending(player, final_hit, log)
    _pt_check_cull(player, monster, log)

    wf_bonus = _je.consume_wardforge_bonus(player)
    if wf_bonus > 0 and is_hit and monster.hp > 0:
        actual_wf = min(wf_bonus, monster.hp)
        monster.hp = max(0, monster.hp - actual_wf)
        log.append(
            f"🛡️ **Wardforge** — ward energy surges for **{actual_wf}** bonus damage!"
        )

    _jewel_log: list[str] = []
    if is_crit:
        _je.process_jewel_trigger(player, monster, "crit", 0, _jewel_log)
    if is_hit:
        _je.process_jewel_trigger(player, monster, "hit", 0, _jewel_log)
    else:
        _je.process_jewel_trigger(player, monster, "miss", 0, _jewel_log)
    if _jewel_log:
        log.extend(_jewel_log)

    partner_log, partner_name = _pt_partner_effects(
        player, monster, is_hit, is_crit, final_hit, _sigmund_proc
    )

    calc.append(
        f"  final_dealt: {final_hit}  monster_hp_remaining: {monster.hp}/{monster.max_hp}"
    )

    return PlayerTurnResult(
        log="\n".join(log),
        damage=final_hit,
        is_hit=is_hit,
        is_crit=is_crit,
        calc_detail="\n".join(calc),
        partner_log=partner_log,
        partner_name=partner_name,
    )
