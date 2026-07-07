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
from core.combat.calc.ward_system import _add_ward, generate_player_ward_on_hit
from core.combat.turns.helpers import PlayerTurnResult, capture_compact_events
from core.emojis import QUENCH
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
    else:
        # Soul stone: cleric — 1:1 tier match to boot lvl.
        ss_cleric = player.get_soul_stone_passive("cleric")
        if ss_cleric:
            heal_pct += ss_cleric * 0.10

    potion_passives_by_type = {
        p["passive_type"]: p["passive_value"] for p in player.potion_passives
    }

    potion_durations_by_type = {
        p["passive_type"]: p.get("passive_duration", 2.0)
        for p in player.potion_passives
    }

    quench = potion_passives_by_type.get("quench", 0)
    if quench:
        heal_pct += quench / 100.0

    heal_amount = int((player.total_max_hp * heal_pct) + random.randint(1, 6))

    if player.apothecary_workers > 0:
        flat_bonus = int(
            player.apothecary_workers * 0.2 * (1.0 + player.apothecary_boost_pct)
        )
        heal_amount += flat_bonus

    # Armor Alchemist / Soul Stone save chance (preserves the potion)
    if player.get_armor_passive() == "Alchemist":
        alchemist_saved = random.random() < 0.30
        _alchemist_label = "⚗️ **Alchemist** preserved your potion!\n"
    else:
        _ss_alchemist = player.get_soul_stone_passive("alchemist")
        if _ss_alchemist:
            from core.apex.data import SOUL_STONE_TIER_VALUES as _SST

            _save_pct = _SST["alchemist"][_ss_alchemist - 1] / 100
            alchemist_saved = random.random() < _save_pct
            _alchemist_label = (
                f"⚗️ **Soul Alchemist T{_ss_alchemist}** preserved your potion!\n"
            )
        else:
            alchemist_saved = False
            _alchemist_label = ""

    if alchemist_saved:
        msg_prefix = _alchemist_label
    else:
        player.potions -= 1
        msg_prefix = ""
        if monster is not None and monster.has_modifier("Frenzied Hunger"):
            v = monster.get_modifier_value("Frenzied Hunger")
            monster.bonus_attack_pct += v
            monster.potion_uses_tracked += 1
            msg_prefix += f"😤 **Frenzied Hunger** — the monster grows stronger! (+{int(v * 100)}% ATK)\n"

    if not alchemist_saved and player.hematurgy_passives:
        from core.hematurgy.engine import on_potion_used

        _fevered_log: list[str] = []
        on_potion_used(player, _fevered_log)
        if _fevered_log:
            msg_prefix += "\n".join(_fevered_log) + "\n"

    potential_hp = player.current_hp + heal_amount
    excess = max(0, potential_hp - player.total_max_hp)
    player.current_hp = min(potential_hp, player.total_max_hp)

    # The displayed heal is always heal_amount minus whatever overflowed past max
    # HP — independent of which helmet (if any) is equipped. Divine's amplified
    # overheal->ward conversion is a separate bonus layered on below, not a
    # reduction of this number.
    msg = (
        msg_prefix
        + f"{player.name} uses a potion and heals for **{max(0, heal_amount - excess)}** HP!"
    )
    if player.apothecary_workers > 0:
        msg += f" (Apothecary: +{int(player.apothecary_workers * 0.2 * (1.0 + player.apothecary_boost_pct))})"

    if excess > 0:
        if player.get_helmet_passive() == "divine":
            helmet_lvl = (
                player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
            )
            divine_overheal = int(excess * helmet_lvl)
            if divine_overheal > 0:
                added = _add_ward(player, divine_overheal, [], "Divine")
                msg += f"\n**Divine** converts **{added}** overheal into 🔮 Ward!"
        else:
            # Soul stone: divine — 1:1 tier match to helmet lvl.
            ss_divine = player.get_soul_stone_passive("divine")
            if ss_divine:
                ss_overheal = int(excess * ss_divine)
                if ss_overheal > 0:
                    added = _add_ward(player, ss_overheal, [], "Divine")
                    msg += f"\n**Soul Divine T{ss_divine}** converts **{added}** overheal into 🔮 Ward!"

    # ------------------------------------------------------------------
    # POWERFUL DISTILLED PASSIVES (11-passive system)
    # ------------------------------------------------------------------
    panacea = potion_passives_by_type.get("panacea", 0)
    if panacea:
        if random.random() < (panacea / 100.0):
            dur = max(2, int(potion_durations_by_type.get("panacea", 2.0)))
            player.alchemy_ailment_immunity_turns = max(
                player.alchemy_ailment_immunity_turns, dur
            )
            if getattr(player.cs, "is_snared", False):
                player.cs.is_snared = False
            for attr in (
                "hema_momentum_stacks",
                "hema_bleed_total",
                "hema_chain_stacks",
                "hema_puncture_bleed",
            ):
                if hasattr(player.cs, attr):
                    setattr(player.cs, attr, 0)
            msg += (
                f"\n🌿 **Panacea** triggers! All ailments cleansed. "
                f"Protected for **{player.alchemy_ailment_immunity_turns}** turns!"
            )
        else:
            msg += "\n🌿 **Panacea** — the cleansing fails to trigger this time."

    eclipse = potion_passives_by_type.get("eclipse", 0)
    if eclipse:
        strikes = max(2, int(potion_durations_by_type.get("eclipse", 2.0)))
        player.alchemy_eclipse_strikes = player.alchemy_eclipse_strikes + strikes
        player.alchemy_eclipse_bonus = max(
            player.alchemy_eclipse_bonus, eclipse / 100.0
        )
        msg += (
            f"\n🌑 **Eclipse** — your next **{strikes}** attack(s) are guaranteed crits "
            f"with **+{eclipse:.0f}%** damage!"
        )

    aegis = potion_passives_by_type.get("aegis", 0)
    if aegis:
        dur = max(2, int(potion_durations_by_type.get("aegis", 2.0)))
        shield = int(player.total_max_hp * (aegis / 100.0))
        player.alchemy_shield_hp = player.alchemy_shield_hp + shield
        player.alchemy_shield_turns = max(player.alchemy_shield_turns, dur)
        msg += (
            f"\n🛡️ **Aegis** — you gain a **{shield}** HP shield for "
            f"**{player.alchemy_shield_turns}** turns!"
        )

    enfeeble = potion_passives_by_type.get("enfeeble", 0)
    if enfeeble:
        dur = max(2, int(potion_durations_by_type.get("enfeeble", 2.0)))
        player.alchemy_enfeeble_pct = max(player.alchemy_enfeeble_pct, enfeeble / 100.0)
        player.alchemy_enfeeble_turns = max(player.alchemy_enfeeble_turns, dur)
        msg += (
            f"\n🌊 **Enfeeble** — monster suffers **-{enfeeble:.0f}%** ATK/DEF "
            f"for **{player.alchemy_enfeeble_turns}** of its turns!"
        )

    blood_tithe = potion_passives_by_type.get("blood_tithe", 0)
    if blood_tithe:
        dur = max(2, int(potion_durations_by_type.get("blood_tithe", 2.0)))
        player.alchemy_blood_tithe_leech = max(
            player.alchemy_blood_tithe_leech, blood_tithe / 100.0
        )
        player.alchemy_blood_tithe_hits = max(player.alchemy_blood_tithe_hits, dur)
        msg += f"\n🩸 **Blood Tithe** — leech {blood_tithe:.0f}% of damage for the next **{dur}** hits!"

    accel = potion_passives_by_type.get("accel", 0)
    if accel:
        dur = max(2, int(potion_durations_by_type.get("accel", 2.0)))
        player.alchemy_hit_boost_pct = max(player.alchemy_hit_boost_pct, accel / 100.0)
        player.alchemy_hit_boost_turns = max(player.alchemy_hit_boost_turns, dur)
        msg += f"\n⚡ **Accel** — +{accel:.0f}% Hit Chance for **{dur}** turns!"

    if quench:
        dur = max(2, int(potion_durations_by_type.get("quench", 2.0)))
        regen_per_turn = max(1, int(player.total_max_hp * 0.05))
        player.alchemy_linger_hp = regen_per_turn
        player.alchemy_linger_turns = max(player.alchemy_linger_turns, dur)
        msg += (
            f"\n{QUENCH} **Quench** — healed extra {quench:.0f}% of max HP, "
            f"then +{regen_per_turn:,} HP/turn for **{dur}** turns!"
        )

    viper = potion_passives_by_type.get("viper", 0)
    if viper and monster is not None and monster.hp > 0:
        dur = max(2, int(potion_durations_by_type.get("viper", 2.0)))
        burst_dmg = int(heal_amount * (viper / 100.0))
        dot_pool = int(heal_amount * 20.0)
        dot_per_turn = max(1, int(dot_pool * 0.20))
        monster.hp = max(0, monster.hp - burst_dmg)
        player.alchemy_viper_dot_dmg = dot_per_turn
        player.alchemy_viper_dot_turns = dur
        msg += (
            f"\n🐍 **Viper** — **{burst_dmg}** burst damage! "
            f"DoT: **{dot_per_turn:,}**/turn for **{dur}** turns!"
        )

    enrage = potion_passives_by_type.get("enrage", 0)
    if enrage:
        dur = max(2, int(potion_durations_by_type.get("enrage", 2.0)))
        player.alchemy_atk_boost_pct = max(player.alchemy_atk_boost_pct, enrage / 100.0)
        player.alchemy_def_boost_pct = max(player.alchemy_def_boost_pct, enrage / 100.0)
        player.alchemy_def_boost_turns = max(player.alchemy_def_boost_turns, dur)
        msg += (
            f"\n💪 **Enrage** — +{enrage:.0f}% ATK and DEF for **{dur}** monster turns!"
        )

    barrier = potion_passives_by_type.get("barrier", 0)
    if barrier:
        dur = max(2, int(potion_durations_by_type.get("barrier", 2.0)))
        ward_per_turn = max(1, int(heal_amount * (barrier / 100.0)))
        player.alchemy_barrier_ward_per_turn = ward_per_turn
        player.alchemy_barrier_turns = max(player.alchemy_barrier_turns, dur)
        msg += f"\n🔮 **Barrier** — +{ward_per_turn:,} Ward/turn for **{dur}** turns!"

    painkiller = potion_passives_by_type.get("painkiller", 0)
    if painkiller:
        dur = max(2, int(potion_durations_by_type.get("painkiller", 2.0)))
        player.alchemy_dmg_reduction_pct = max(
            player.alchemy_dmg_reduction_pct, painkiller / 100.0
        )
        player.alchemy_dmg_reduction_turns = max(
            player.alchemy_dmg_reduction_turns, dur
        )
        msg += f"\n🩹 **Painkiller** — -{painkiller:.0f}% damage from the monster's next **{dur}** hits!"

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
    """Phase 8 — effects that fire after damage lands: leech, bloodthirst."""
    if damage <= 0:
        return

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "leeching" and helmet_lvl > 0:
        # 0.2% per level: level 1 = 0.2%, level 5 = 1% of damage dealt as HP
        heal = int(damage * (0.002 * helmet_lvl))
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

    # Living Battlefield: heal 1% of max HP on any connected hit
    if damage > 0 and getattr(monster, "apex_zone", None) == "grove":
        grove_heal = max(1, int(player.total_max_hp * 0.01))
        player.current_hp = min(player.total_max_hp, player.current_hp + grove_heal)
        log.append(
            f"🌿 **Living Battlefield** — you heal **{grove_heal}** HP from the strike!"
        )

    # Blood Tithe: leech % of damage dealt as HP for remaining hits
    if player.alchemy_blood_tithe_hits > 0 and damage > 0:
        leech = int(damage * player.alchemy_blood_tithe_leech)
        if leech > 0:
            player.current_hp = min(player.total_max_hp, player.current_hp + leech)
            log.append(
                f"🩸 **Blood Tithe** leeches **{leech}** HP! "
                f"({player.alchemy_blood_tithe_hits - 1} hit{'s' if player.alchemy_blood_tithe_hits - 1 != 1 else ''} left)"
            )
        player.alchemy_blood_tithe_hits -= 1

    # Soul Stone: leeching (separate from helmet leeching)
    ss_leeching = player.get_soul_stone_passive("leeching")
    if (
        ss_leeching
        and damage > 0
        and not (player.equipped_helmet and player.get_helmet_passive() == "leeching")
    ):
        ss_heal = int(damage * (0.002 * ss_leeching))
        if ss_heal > 0:
            player.current_hp = min(player.total_max_hp, player.current_hp + ss_heal)
            log.append(f"💎 **Soul Leeching** drains **{ss_heal}** HP.")


def _pt_track_pending(player: Player, damage: int, log: list[str]) -> None:
    """Phase 9 — accumulate pending XP/gold from glove passives."""
    if damage <= 0:
        return
    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "equilibrium" and glove_lvl > 0:
        player.equilibrium_bonus_xp_pending += int(damage * (glove_lvl * 0.05))
    else:
        # Soul stone: equilibrium — 1:1 tier match to glove lvl.
        ss_equilibrium = player.get_soul_stone_passive("equilibrium")
        if ss_equilibrium:
            player.equilibrium_bonus_xp_pending += int(damage * (ss_equilibrium * 0.05))
    if glove_passive == "plundering" and glove_lvl > 0:
        player.plundering_bonus_gold_pending += int(damage * (glove_lvl * 0.10))
    else:
        # Soul stone: plundering — 1:1 tier match to glove lvl.
        ss_plundering = player.get_soul_stone_passive("plundering")
        if ss_plundering:
            player.plundering_bonus_gold_pending += int(damage * (ss_plundering * 0.10))


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
                # Time Lord: 80% chance to survive the killing blow
                if (
                    monster.has_modifier("Time Lord")
                    and monster.hp > 1
                    and random.random() < 0.80
                ):
                    monster.hp = 1
                    parts.append(
                        f"💀 **Execute Lv.{lvl}** — {partner.name} strikes for **{dmg - 1}** true damage! "
                        f"**Time Lord** cheats death — {monster.name} clings to 1 HP!"
                    )
                # Undying Resolve: intercept first death
                elif (
                    monster.has_modifier("Undying Resolve")
                    and not monster.undying_resolve_triggered
                ):
                    heal_pct = monster.get_modifier_value("Undying Resolve")
                    monster.hp = max(1, int(monster.max_hp * heal_pct))
                    monster.undying_resolve_triggered = True
                    monster.undying_immune_turns = 2
                    monster.undying_atk_boost_turns = 2
                    parts.append(
                        f"💀 **Execute Lv.{lvl}** — {partner.name} strikes for **{dmg}** true damage! "
                        f"**Undying Resolve!** {monster.name} refuses to die — rises to **{monster.hp}** HP!"
                    )
                else:
                    monster.hp = 0
                    parts.append(
                        f"💀 **Execute Lv.{lvl}** — {partner.name} executes the "
                        f"{monster.name}! (**{dmg}** true damage)"
                    )

    if sigmund_proc:
        sig_lvl = partner.sig_combat_lvl
        parts.append(
            f"🐕 **Decisive Strike Lv.{sig_lvl}** — the hounds drive your strike to double power!"
        )

    partner_log = "\n".join(parts)
    partner_name = f"🤝 {partner.name}" if parts else ""
    return partner_log, partner_name


def _pt_check_cull(player: Player, monster: Monster, log: list[str]) -> bool:
    """Culling strike: instantly kills the monster when its HP falls within the cull threshold.

    Deals true damage (bypasses all DR layers, Stalwart, uber protection, and monster ward)
    by setting HP directly.  Returns True if the killing blow landed (monster.hp == 0).

    Time Lord — 80% chance to survive, leaving the monster at 1 HP; returns False.
    Undying Resolve — fires in the post-cull block of process_player_turn (move cull before
    the Undying Resolve check so it can protect from cull kills).
    """
    from core.combat.calc.calcs import get_weapon_tier

    if monster.hp <= 0:
        return False
    idx, _ = get_weapon_tier(player, "cull")
    if idx < 0:
        return False

    threshold = (idx + 1) * 0.08
    if monster.hp > int(monster.max_hp * threshold):
        return False

    cull_dmg = monster.hp  # true damage = full remaining HP

    # Time Lord: 80% chance to survive the killing blow (stays at 1 HP)
    if monster.has_modifier("Time Lord") and monster.hp > 1 and random.random() < 0.80:
        monster.hp = 1
        log.append(
            f"{player.name}'s weapon culls the weakened {monster.name} "
            f"for 🪓 __**{cull_dmg - 1}**__ true damage! "
            f"**Time Lord** cheats death — {monster.name} clings to 1 HP!"
        )
        return False

    monster.hp = 0
    log.append(
        f"{player.name}'s weapon culls the weakened {monster.name} "
        f"for 🪓 __**{cull_dmg}**__ true damage!"
    )
    return True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def process_player_turn(player: Player, monster: Monster) -> PlayerTurnResult:
    """Executes the player's turn, applying damage to the monster and returning the combat log."""
    log: list[str] = []
    clog: list[str] = []  # compact log for auto-battle — no flavor text, events only
    calc: list[str] = []

    # --- Verdant Snare (Artisan Mastery prestige boss) ---
    if getattr(player.cs, "is_snared", False):
        snare_source = getattr(monster, "name", "the enemy")
        log.append(f"You are **snared** by {snare_source} and cannot act this turn!")
        return PlayerTurnResult(
            log="\n".join(log),
            damage=0,
            is_crit=False,
            is_hit=False,
            compact_log="\n".join(log),
        )

    _je.tick_acrimony_dot(player, monster, log)
    _je.tick_onslaught_charge(player, monster, log)

    if player.alchemy_linger_turns > 0:
        player.current_hp = min(
            player.total_max_hp, player.current_hp + player.alchemy_linger_hp
        )
        log.append(
            f"{QUENCH} **Quench** restores **{player.alchemy_linger_hp}** HP! "
            f"({player.alchemy_linger_turns - 1} turn{'s' if player.alchemy_linger_turns - 1 != 1 else ''} left)"
        )
        player.alchemy_linger_turns -= 1

    if player.alchemy_viper_dot_turns > 0 and monster.hp > 0:
        dot_dmg = player.alchemy_viper_dot_dmg
        monster.hp = max(0, monster.hp - dot_dmg)
        log.append(
            f"🐍 **Viper** DoT deals **{dot_dmg:,}** damage! "
            f"({player.alchemy_viper_dot_turns - 1} turn{'s' if player.alchemy_viper_dot_turns - 1 != 1 else ''} left)"
        )
        player.alchemy_viper_dot_turns -= 1

    if player.alchemy_barrier_turns > 0:
        from core.combat.calc.ward_system import _add_ward as _barrier_add_ward

        added = _barrier_add_ward(player, player.alchemy_barrier_ward_per_turn, [])
        if added > 0:
            log.append(
                f"🔮 **Barrier** adds **{added}** Ward! "
                f"({player.alchemy_barrier_turns - 1} turn{'s' if player.alchemy_barrier_turns - 1 != 1 else ''} left)"
            )
        player.alchemy_barrier_turns -= 1

    if player.alchemy_hit_boost_turns > 0:
        player.alchemy_hit_boost_turns -= 1
        if player.alchemy_hit_boost_turns <= 0:
            player.alchemy_hit_boost_pct = 0.0

    # --- Hematurgy: Haemorrhage bleed tick (before attack) ---
    if player.hematurgy_passives:
        from core.hematurgy.engine import on_haemorrhage_tick

        on_haemorrhage_tick(player, monster, log)

    attack_multiplier, _sigmund_proc = build_attack_multiplier(
        player, monster, log, calc
    )
    is_hit, attack_multiplier = resolve_hit(
        player, monster, attack_multiplier, log, calc
    )

    is_crit = resolve_crit(player, monster, is_hit, log, calc)

    if is_hit and getattr(player, "jewel_cataclysm_primed", False):
        is_crit = True

    # Reality Fracture: 12% per turn to force a critical hit
    if is_hit and not is_crit and getattr(monster, "apex_zone", None) == "shattered":
        if random.random() < 0.12:
            is_crit = True
            calc.append("  reality_fracture: forced crit")

    if player.get_glove_corrupted_essence() == "neet":
        is_hit = False
        is_crit = False
        calc.append("  neet: accuracy 0, always miss")

    # Eclipse: force crit for remaining strikes (damage bonus already folded into
    # attack_multiplier by build_attack_multiplier)
    if player.alchemy_eclipse_strikes > 0:
        is_crit = True
        calc.append("  eclipse: guaranteed crit")
        player.alchemy_eclipse_strikes -= 1
        if player.alchemy_eclipse_strikes <= 0:
            player.alchemy_eclipse_bonus = 0.0

    if is_crit:
        raw_damage = calc_crit_damage(
            player, monster, attack_multiplier, log, calc, clog=clog
        )
    elif is_hit:
        raw_damage = calc_hit_damage(
            player, monster, attack_multiplier, log, calc, clog=clog
        )
    else:
        raw_damage = calc_miss_damage(
            player, monster, attack_multiplier, log, calc, clog=clog
        )

    # Monster DR — capture in compact (explains why damage was reduced)
    start = len(log)
    actual_damage = apply_monster_damage_reduction(monster, raw_damage, log, calc)
    capture_compact_events(log, clog, start)

    # --- Undying Resolve: block all player damage while immune ---
    start = len(log)
    if monster.undying_immune_turns > 0:
        log.append(
            f"💀 **Undying Resolve** — {monster.name} is invulnerable! ({monster.undying_immune_turns} turn{'s' if monster.undying_immune_turns != 1 else ''} remaining)"
        )
        actual_damage = 0
        monster.undying_immune_turns -= 1
    capture_compact_events(log, clog, start)

    # Partner: co_curse_taken — monster takes L*2% more damage (applied after all reductions)
    if player.active_partner and actual_damage > 0:
        for key, lvl in player.active_partner.combat_skills:
            if key == "co_curse_taken":
                bonus = int(actual_damage * lvl * 0.02)
                actual_damage += bonus
                calc.append(f"  co_curse_taken: +{lvl * 2}% (+{bonus})")
                break

    generate_player_ward_on_hit(player, raw_damage, is_hit, is_crit, log)

    # Ward Inoculation: drain accumulated ward-damage buffer onto the monster
    if player.hematurgy_passives and player.cs.hema_ward_dmg_buffer > 0:
        from core.hematurgy.engine import drain_ward_dmg_buffer

        drain_ward_dmg_buffer(player, monster, log)

    # Apply damage to monster ward+HP — capture Time Lord / ward shatter events
    start = len(log)
    final_hit = apply_damage_to_monster(player, monster, actual_damage, log)
    capture_compact_events(log, clog, start)

    # --- Post-damage modifier triggers ---

    # Colossus Protocol: trigger on first time HP drops below 50%
    start = len(log)
    if (
        monster.has_modifier("Colossus Protocol")
        and not monster.colossus_active
        and 0 < monster.hp < int(monster.max_hp * 0.50)
    ):
        monster.colossus_active = True
        cp_v = monster.get_modifier_value("Colossus Protocol")
        monster.bonus_attack_pct += cp_v
        monster.colossus_dr = cp_v / 2
        log.append(
            f"⚙️ **Colossus Protocol ENGAGES!** {monster.name}'s power surges — "
            f"ATK +{int(cp_v * 100)}%, DR +{int(cp_v / 2 * 100)}%!"
        )
    capture_compact_events(log, clog, start)

    # --- Slayer tree hu_4 instant slay (non-boss only, before cull) ---
    _instant_slay_fired = False
    if (
        is_hit
        and monster.hp > 0
        and not monster.is_boss
        and not getattr(monster, "is_uber", False)
        and player.active_task_species
        and player.active_task_species == monster.species
        and getattr(player, "slayer_tree_nodes", {}).get("hu_4") == "slay"
        and random.random() < 0.05
    ):
        slay_dmg = monster.hp
        if (
            monster.has_modifier("Time Lord")
            and monster.hp > 1
            and random.random() < monster.get_modifier_value("Time Lord")
        ):
            monster.hp = 1
            log.append(
                f"⚡ **Instant Slay** triggers! ({slay_dmg - 1} true damage) "
                f"**Time Lord** cheats death — {monster.name} clings to 1 HP!"
            )
        elif (
            monster.has_modifier("Undying Resolve")
            and not monster.undying_resolve_triggered
        ):
            heal_pct = monster.get_modifier_value("Undying Resolve")
            monster.hp = max(1, int(monster.max_hp * heal_pct))
            monster.undying_resolve_triggered = True
            monster.undying_immune_turns = 2
            monster.undying_atk_boost_turns = 2
            log.append(
                f"⚡ **Instant Slay** triggers! **Undying Resolve!** "
                f"{monster.name} refuses to die — rises to **{monster.hp}** HP!"
            )
        else:
            monster.hp = 0
            _instant_slay_fired = True
            log.append(f"⚡ **Instant Slay** strikes true! ({slay_dmg} true damage)")
            clog.append(f"⚡ **Instant Slay!** ({slay_dmg} dmg)")

    # --- Culling strike (before Undying Resolve so it can protect from cull kills) ---
    start = len(log)
    _cull_fired = _pt_check_cull(player, monster, log)
    capture_compact_events(log, clog, start)

    # Undying Resolve: intercept first death
    start = len(log)
    if (
        monster.has_modifier("Undying Resolve")
        and monster.hp <= 0
        and not monster.undying_resolve_triggered
    ):
        heal_pct = monster.get_modifier_value("Undying Resolve")
        monster.hp = max(1, int(monster.max_hp * heal_pct))
        monster.undying_resolve_triggered = True
        monster.undying_immune_turns = 2
        monster.undying_atk_boost_turns = 2
        log.append(
            f"💀 **Undying Resolve!** {monster.name} refuses to die — rises to **{monster.hp}** HP! "
            f"Invulnerable for 2 turns, ATK doubled for 2 turns!"
        )
    capture_compact_events(log, clog, start)

    # Death Rattle: trigger on first time HP drops below 25%
    start = len(log)
    if (
        monster.has_modifier("Death Rattle")
        and not monster.death_rattle_triggered
        and 0 < monster.hp < int(monster.max_hp * 0.25)
    ):
        monster.death_rattle_triggered = True
        monster.death_rattle_countdown = 5
        dr_heal_pct = int(monster.get_modifier_value("Death Rattle") * 100)
        log.append(
            f"☠️ **Death Rattle** — {monster.name} is mortally wounded! "
            f"If it survives **5 turns**, it will heal to {dr_heal_pct}% HP!"
        )
    capture_compact_events(log, clog, start)

    # Wrathful Retaliation: +1 stack per player crit (log only — effect shown in next hit number)
    if is_crit and monster.has_modifier("Wrathful Retaliation"):
        monster.wrathful_stacks += 1
        log.append(
            f"🔱 **Wrathful Retaliation** — {monster.name} fuels its rage! ({monster.wrathful_stacks} stack{'s' if monster.wrathful_stacks != 1 else ''})"
        )

    # Temporal Collapse: accumulate player damage across 6-turn window
    if monster.has_modifier("Temporal Collapse") and final_hit > 0:
        monster.temporal_window_damage += final_hit

    # Pressure Surge: record whether player critted this turn
    if monster.has_modifier("Pressure Surge"):
        monster.pressure_player_critted = is_crit

    _pt_post_hit_effects(player, monster, final_hit, is_crit, log)
    _pt_track_pending(player, final_hit, log)

    # --- Celestial Ghostreaver: ward regen fires every player turn (hit or miss) ---
    if player.get_celestial_armor_passive() == "celestial_ghostreaver":
        _gr_regen = random.randint(50, 200)
        _gr_added = _add_ward(player, _gr_regen, log)
        log.append(f"✨ **Celestial Ghostreaver** restores **{_gr_added}** 🔮 Ward!")
        _je.process_jewel_trigger(player, monster, "ward", _gr_added, log)

    # --- Hematurgy: post-hit and post-miss passives ---
    if player.hematurgy_passives:
        from core.hematurgy.engine import (
            apply_reverberation,
            on_kill,
            on_player_hit,
            on_player_miss,
        )

        if is_hit or is_crit:
            on_player_hit(player, monster, final_hit, is_crit, log)
            # Reverberation: chance to re-echo after the initial echo fires
            from core.combat.calc.calcs import get_weapon_tier as _gwt

            echo_idx, _ = _gwt(player, "echo")
            if echo_idx >= 0 and final_hit > 0:
                echo_scale = (echo_idx + 1) * 0.10
                echo_component = int(final_hit * echo_scale / (1 + echo_scale))
                apply_reverberation(player, monster, echo_component, log)
        else:
            on_player_miss(player, monster, raw_damage, log)
        # Kill hook
        if monster.hp <= 0:
            on_kill(player, log)

    # Wardforge bonus — capture in compact (it deals extra damage to monster)
    start = len(log)
    wf_bonus = _je.consume_wardforge_bonus(player)
    if wf_bonus > 0 and is_hit and monster.hp > 0:
        actual_wf = min(wf_bonus, monster.hp)
        monster.hp = max(0, monster.hp - actual_wf)
        log.append(
            f"🛡️ **Wardforge** — ward energy surges for **{actual_wf}** bonus damage!"
        )
    capture_compact_events(log, clog, start)

    # Jewel triggers — capture in compact (unleashes are significant events)
    _jewel_log: list[str] = []
    if is_crit:
        _je.process_jewel_trigger(player, monster, "crit", 0, _jewel_log)
    if is_hit:
        _je.process_jewel_trigger(player, monster, "hit", 0, _jewel_log)
    else:
        _je.process_jewel_trigger(player, monster, "miss", 0, _jewel_log)
    if _jewel_log:
        log.extend(_jewel_log)
        clog.extend(_jewel_log)

    partner_log, partner_name = _pt_partner_effects(
        player, monster, is_hit, is_crit, final_hit, _sigmund_proc
    )

    calc.append(
        f"  final_dealt: {final_hit}  monster_hp_remaining: {monster.hp}/{monster.max_hp}"
    )

    return PlayerTurnResult(
        log="\n".join(log),
        compact_log="\n".join(clog),
        damage=final_hit,
        is_hit=is_hit,
        is_crit=is_crit,
        calc_detail="\n".join(calc),
        partner_log=partner_log,
        partner_name=partner_name,
        cull_fired=_cull_fired,
    )
