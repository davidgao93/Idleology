import math
import random

from core.combat import jewel_engine as _je
from core.combat.calc.damage_calc import calculate_damage_taken
from core.combat.calc.damage_calc import roll_monster_damage as _roll_monster_damage
from core.combat.calc.hit_calc import calculate_monster_hit_chance
from core.combat.calc.ward_system import _add_ward
from core.combat.turns.helpers import MonsterTurnResult, capture_compact_events
from core.models import Monster, Player


def process_monster_turn(player: Player, monster: Monster, *, context_note: str = "") -> MonsterTurnResult:
    """Executes the monster's turn, applies damage to player, and returns combat log."""
    if player.is_invulnerable_this_combat:
        return MonsterTurnResult(
            log=f"The **Invulnerable** armor protects {player.name}, absorbing all damage from {monster.name}!",
            hp_damage=0,
            compact_log="🛡️ Invulnerable — all damage absorbed!",
        )

    # --- Hematurgy: Flash Frost freeze check ---
    if player.hematurgy_passives:
        from core.hematurgy.engine import on_monster_turn_start

        _freeze_log: list[str] = []
        if on_monster_turn_start(player, monster, _freeze_log):
            monster.combat_round += 1
            _freeze_txt = "\n".join(_freeze_log)
            return MonsterTurnResult(log=_freeze_txt, hp_damage=0, compact_log=_freeze_txt)

    monster.combat_round += 1
    prev_hp = player.current_hp
    log: list[str] = []
    clog: list[str] = []  # compact log for auto-battle — no flavor text
    calc: list[str] = []
    if context_note:
        calc.append(f"  [context]{context_note}")

    # Decrement powerful distilled potion transients (Aegis shield, Panacea immunity, etc.)
    if getattr(player, "alchemy_shield_turns", 0) > 0:
        player.alchemy_shield_turns -= 1
        if player.alchemy_shield_turns <= 0:
            player.alchemy_shield_hp = 0
    if getattr(player, "alchemy_ailment_immunity_turns", 0) > 0:
        player.alchemy_ailment_immunity_turns -= 1
        if player.alchemy_ailment_immunity_turns > 0:
            # Simple representation: player is protected this turn
            log.append(f"🌿 **Panacea** — protected from ailments this turn ({player.alchemy_ailment_immunity_turns} remaining).")

    celestial = player.get_celestial_armor_passive()
    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    previous_ward = player.combat_ward

    # --- Death Rattle: countdown tick → heal if reaches 0 ---
    if monster.death_rattle_triggered and monster.death_rattle_countdown > 0:
        monster.death_rattle_countdown -= 1
        if monster.death_rattle_countdown == 0:
            heal_target = int(monster.max_hp * 0.25)
            if monster.hp < heal_target:
                healed = heal_target - monster.hp
                monster.hp = heal_target
                _dr_heal_msg = (
                    f"☠️ **Death Rattle** — {monster.name} endures! Heals to **{monster.hp}** HP! (+{healed})"
                )
                log.append(_dr_heal_msg)
                clog.append(_dr_heal_msg)  # heal is a significant event
        else:
            log.append(
                f"☠️ **Death Rattle** — countdown: **{monster.death_rattle_countdown}** turns remaining..."
            )
            # skip in compact — countdown visible in Afflictions field

    # --- Flashfire: +1 charge per turn; at 8 → true damage burst ---
    start = len(log)
    if monster.has_modifier("Flashfire"):
        monster.flashfire_charges += 1
        if monster.flashfire_charges >= 8:
            v = monster.get_modifier_value("Flashfire")
            burst = int(player.total_max_hp * v)
            player.current_hp = max(0, player.current_hp - burst)
            monster.flashfire_charges = 0
            log.append(
                f"🔥 **Flashfire DETONATES!** The buildup erupts for **{burst}** 🔥 true damage!"
            )
    capture_compact_events(log, clog, start)  # detonation only (silent on charge buildup)

    # --- Hemorrhage: true DoT per stack at start of each monster turn ---
    start = len(log)
    if monster.has_modifier("Hemorrhage") and monster.bleed_stacks > 0:
        v = monster.get_modifier_value("Hemorrhage")
        bleed_dmg = int(player.total_max_hp * v * monster.bleed_stacks)
        if bleed_dmg > 0:
            player.current_hp = max(0, player.current_hp - bleed_dmg)
            log.append(
                f"🩸 **Hemorrhage** — {monster.bleed_stacks} bleed stacks deal **{bleed_dmg}** true damage!"
            )
    capture_compact_events(log, clog, start)

    # --- Verdant Colossus (Artisan Mastery prestige boss) snare chance ---
    start = len(log)
    if monster.has_modifier("Verdant Snare") and not player.cs.is_snared:
        v = monster.get_modifier_value("Verdant Snare")
        if random.random() < v:
            player.cs.is_snared = True
            log.append(
                f"🌿 **Verdant Snare!** {monster.name} entangles you! You cannot act until you free yourself."
            )
    capture_compact_events(log, clog, start)

    # --- Pressure Surge: +1 if player didn't crit; at 10 → true damage ---
    start = len(log)
    if monster.has_modifier("Pressure Surge"):
        if not monster.pressure_player_critted:
            monster.pressure_stacks = min(10, monster.pressure_stacks + 1)
        monster.pressure_player_critted = (
            False  # reset; player_turn will write it again
        )
        if monster.pressure_stacks >= 10:
            v = monster.get_modifier_value("Pressure Surge")
            burst = int(player.total_max_hp * v)
            player.current_hp = max(0, player.current_hp - burst)
            monster.pressure_stacks = 0
            log.append(
                f"⚡ **Pressure Surge RELEASES!** Pent-up force slams for **{burst}** true damage!"
            )
    capture_compact_events(log, clog, start)  # release burst only (silent on stack increment)

    # --- Soul Siphon: every 2 turns drain ward → monster heals 50% of drained ---
    if monster.has_modifier("Soul Siphon") and monster.combat_round % 2 == 0:
        v = monster.get_modifier_value("Soul Siphon")
        if player.combat_ward > 0:
            siphon_amt = int(player.combat_ward * v)
            if siphon_amt > 0:
                player.combat_ward = max(0, player.combat_ward - siphon_amt)
                heal_amt = max(1, siphon_amt // 2)
                monster.hp = min(monster.max_hp, monster.hp + heal_amt)
                log.append(
                    f"💜 **Soul Siphon** drains **{siphon_amt}** 🔮 ward, healing {monster.name} for **{heal_amt}** HP!"
                )
                # skip in compact — ward change visible in HP bar

    # --- Corrosion: +1 corrode stack every 3 turns (cap 5) ---
    if monster.has_modifier("Corrosion") and monster.combat_round % 3 == 0:
        if monster.corrode_stacks < 5:
            monster.corrode_stacks += 1
        v = int(monster.get_modifier_value("Corrosion"))
        log.append(
            f"🧪 **Corrosion** — your armour degrades! Corrode stack {monster.corrode_stacks}/5 (−{monster.corrode_stacks * v} PDR)"
        )
        # skip in compact — PDR change visible in Afflictions field

    # --- Temporal Collapse: every 6 turns return accumulated player damage as true damage ---
    # Burst is capped at 35% of player max HP to prevent instant kills — endgame players
    # can deal 100-200k damage in 6 turns while only having ~1200-1400 HP.
    start = len(log)
    if (
        monster.has_modifier("Temporal Collapse")
        and monster.combat_round % 6 == 0
        and monster.combat_round > 0
    ):
        if monster.temporal_window_damage > 0:
            cap = int(player.total_max_hp * 0.15)
            was_capped = monster.temporal_window_damage > cap
            collapse_dmg = min(monster.temporal_window_damage, cap)
            player.current_hp = max(0, player.current_hp - collapse_dmg)
            monster.temporal_window_damage = 0
            cap_note = " *(capped)*" if was_capped else ""
            log.append(
                f"⏳ **Temporal Collapse!** Time reverses your strikes — **{collapse_dmg}** true damage!{cap_note}"
            )
    capture_compact_events(log, clog, start)

    # --- Mending: passive HP regen every other monster turn ---
    if monster.has_modifier("Mending") and monster.combat_round % 2 == 0:
        # sqrt scaling: same heal at 10k HP, tapers naturally above that
        regen = int(
            math.sqrt(monster.max_hp * 10_000) * monster.get_modifier_value("Mending")
        )
        monster.hp = min(monster.max_hp, monster.hp + regen)
        log.append(f"{monster.name}'s **Mending** restores **{regen}** HP!")
        # skip in compact — HP regen visible in monster HP bar

    # --- Void Aura drain (regardless of hit) ---
    start = len(log)
    if monster.has_modifier("Void Aura"):
        drain_atk = max(1, int(player.flat_atk * 0.005))
        drain_def = max(0, int(player.flat_def * 0.005))
        player.bonus_atk -= drain_atk
        player.bonus_def -= drain_def
        log.append(
            f"🌑 **Void Drain** siphons **{drain_atk}** ATK and **{drain_def}** DEF!"
        )
    capture_compact_events(log, clog, start)

    # ==========================================================================
    # APEX ZONE EFFECTS (pre-hit, per monster turn)
    # ==========================================================================

    apex_zone = getattr(monster, "apex_zone", None)

    # Tempest zone: every 3rd monster turn → unavoidable 8% max HP true damage
    start = len(log)
    if (
        apex_zone == "storm"
        and monster.combat_round % 3 == 0
        and monster.combat_round > 0
    ):
        lightning_dmg = max(1, int(player.total_max_hp * 0.08))
        player.current_hp = max(0, player.current_hp - lightning_dmg)
        log.append(
            f"⚡ **Tempest Lightning** — the storm strikes for **{lightning_dmg}** ⚡ true damage!"
        )
    capture_compact_events(log, clog, start)

    # Living Battlefield: monster regen 0.4% max HP per turn
    if apex_zone == "grove" and monster.hp < monster.max_hp:
        regen = max(1, int(monster.max_hp * 0.004))
        monster.hp = min(monster.max_hp, monster.hp + regen)
        log.append(
            f"🌿 **Living Battlefield** — the grove heals {monster.name} for **{regen}** HP!"
        )
        # skip in compact — monster HP regen visible in HP bar

    # Tempted Fate: every 4th monster turn drain ALL player ward
    start = len(log)
    if (
        apex_zone == "vault"
        and monster.combat_round % 4 == 0
        and monster.combat_round > 0
    ):
        drained = player.combat_ward
        if drained > 0:
            player.combat_ward = 0
            log.append(
                f"💰 **Tempted Fate** — fortune's price is paid! All **{drained}** 🔮 Ward drained!"
            )
    capture_compact_events(log, clog, start)

    # Reality Fracture: every 5th monster turn reroll one modifier
    if (
        apex_zone == "shattered"
        and monster.combat_round % 5 == 0
        and monster.combat_round > 0
    ):
        if monster.modifiers:
            from core.combat.mobgen.modifier_data import make_modifier

            idx = random.randrange(len(monster.modifiers))
            old_name = monster.modifiers[idx].name
            new_mod = make_modifier(old_name, monster.level)
            if new_mod:
                monster.modifiers[idx] = new_mod
                log.append(
                    f"🌀 **Reality Fracture** — {monster.name}'s **{old_name}** rerolls!"
                    f" Now tier {new_mod.tier}."
                )
                # skip in compact — modifier changes visible in monster description

    # ==========================================================================
    # END APEX ZONE EFFECTS
    # ==========================================================================

    # --- Origin of Corruption: every 3 turns drain 10% ward → 10× HP heal ---
    if monster.has_modifier("Origin of Corruption") and monster.combat_round % 3 == 0:
        ward_drain = int(player.combat_ward * 0.10)
        if ward_drain > 0:
            player.combat_ward = max(0, player.combat_ward - ward_drain)
            hp_healed = ward_drain * 10
            monster.hp = min(monster.max_hp, monster.hp + hp_healed)
            log.append(
                f"💀 **Origin of Corruption awakens!** A wave of primordial rot drains **{ward_drain}** ward, "
                f"healing Evelynn for **{hp_healed}** HP!"
            )
            # skip in compact — ward/HP changes visible in HP bars

    # --- Hit chance ---
    hit_chance_base = calculate_monster_hit_chance(player, monster)
    hit_chance = hit_chance_base
    hit_mods: list[str] = [f"base={hit_chance_base*100:.1f}%"]

    # Difficulty: scaled flat accuracy bonus applied before other modifiers
    _DIFFICULTY_HIT_BONUS = [0.0, 0.15, 0.20, 0.30, 0.50]
    _DIFFICULTY_NAMES_MT = ["", "hard", "extreme", "nightmarish", "delirious"]
    if monster.difficulty_level > 0:
        hit_bonus = _DIFFICULTY_HIT_BONUS[monster.difficulty_level]
        diff_label = _DIFFICULTY_NAMES_MT[monster.difficulty_level]
        hit_chance = min(0.95, hit_chance + hit_bonus)
        hit_mods.append(f"+{int(hit_bonus*100)}%({diff_label}_mode)={hit_chance*100:.1f}%")

    # Keen: flat bonus treated as +X% hit chance (capped at 0.95 unless Inevitable)
    keen_bonus = (
        int(monster.get_modifier_value("Keen")) if monster.has_modifier("Keen") else 0
    )
    if keen_bonus > 0:
        hit_chance = min(0.95, hit_chance + keen_bonus / 100)
        hit_mods.append(f"+{keen_bonus}%(keen)={hit_chance*100:.1f}%")

    # Overwhelming: −25 accuracy penalty (trade-off for double damage)
    if monster.has_modifier("Overwhelming"):
        hit_chance = max(0.15, hit_chance - 0.25)
        hit_mods.append(f"-25%(overwhelming)={hit_chance*100:.1f}%")

    # Unerring: hit rolls take the higher of two
    if monster.has_modifier("Unerring"):
        hit_mods.append("unerring(2-roll-high)")

    # Inevitable: always hit
    if monster.has_modifier("Inevitable"):
        hit_chance = 1.0
        hit_mods.append("100%(inevitable)")

    monster_roll = random.random()
    if monster.has_modifier("Unerring"):
        monster_roll = max(monster_roll, random.random())

    is_monster_hit = monster_roll <= hit_chance
    is_dodged = False
    is_blocked = False
    calc.append(
        f"  hit: {' → '.join(hit_mods)} | roll={monster_roll:.4f} "
        f"→ {'HIT' if is_monster_hit else 'MISS'}"
    )

    if is_monster_hit:
        # --- PDR / FDR setup ---
        effective_pdr = player.get_total_pdr()
        # Corrosion: each stack reduces player PDR; excess PDR above the cap acts as a buffer
        if monster.has_modifier("Corrosion") and monster.corrode_stacks > 0:
            corrode_reduction = monster.corrode_stacks * int(
                monster.get_modifier_value("Corrosion")
            )
            effective_pdr = min(effective_pdr, max(0, player.get_raw_pdr() - corrode_reduction))
        pdr_notes = [f"base={effective_pdr}%"]
        if celestial == "celestial_fortress":
            missing_pct = (1 - (player.current_hp / player.total_max_hp)) * 100
            bonus_pdr = int(missing_pct / 5.0)
            pdr_cap = (
                90
                if (
                    player.equipped_armor
                    and player.equipped_armor.passive == "Impregnable"
                )
                else 80
            )
            effective_pdr = min(pdr_cap, effective_pdr + bonus_pdr)
            pdr_notes.append(
                f"+{bonus_pdr}%(fortress,{missing_pct:.1f}%missing)={effective_pdr}%"
            )
        effective_fdr = player.get_total_fdr()
        calc.append(f"  PDR: {' → '.join(pdr_notes)} | FDR: {effective_fdr}")

        # --- Phase 1: Prepare unified damage modifier pools for this turn's hit ---
        # Reset ensures static always-on sources (Savage, Overwhelming, Hell's Fury, zone, Enraged, Spectral proc)
        # are applied exactly once per damage roll and do not accumulate across turns or internal re-rolls
        # (e.g. Celestial Sanctity "lower of two" or Balanced Strikes twin).
        monster.damage_increased_pct = 0.0
        monster.damage_more_mult = 1.0

        # Dynamic per-turn / per-phase bonuses (Wrathful stacks, Undying phase) are added below.
        # These are the base that roll_monster_damage will build static contributions on top of.
        # Onslaught now boosts effective ATK (surplus) instead of the damage pool.

        if monster.has_modifier("Wrathful Retaliation") and monster.wrathful_stacks > 0:
            wr_val = monster.wrathful_stacks * monster.get_modifier_value("Wrathful Retaliation")
            monster.damage_increased_pct += wr_val
            calc.append(f"  +{wr_val:.2f} to damage_increased_pct from Wrathful Retaliation ({monster.wrathful_stacks} stacks)")

        if monster.undying_atk_boost_turns > 0:
            monster.damage_increased_pct += 1.0
            calc.append("  +1.00 to damage_increased_pct from Undying Resolve phase")
            monster.undying_atk_boost_turns -= 1

        # --- Base damage roll (Celestial Sanctity takes the lower of two) ---
        total_damage, dmg_raw, dmg_base, minion_dmg = _roll_monster_damage(
            player, monster, effective_pdr, effective_fdr, calc
        )
        if celestial == "celestial_sanctity":
            alt_total, alt_raw, alt_base, alt_minion = _roll_monster_damage(
                player, monster, effective_pdr, effective_fdr
            )
            if alt_total < total_damage:
                total_damage, dmg_raw, dmg_base, minion_dmg = (
                    alt_total,
                    alt_raw,
                    alt_base,
                    alt_minion,
                )
                calc.append(f"  celestial_sanctity: took lower roll → {total_damage}")

        # (Wrathful/Undying dynamic contributions for the turn were prepared before the roll call.)

        # --- Multistrike: 50% chance to strike twice, second hit at 50% damage ---
        multistrike_damage = 0
        if monster.has_modifier(
            "Multistrike"
        ) and random.random() <= monster.get_modifier_value("Multistrike"):
            multistrike_damage = max(
                0,
                (
                    int(
                        calculate_damage_taken(player, monster)
                        * 0.5
                        * (1 - effective_pdr / 100)
                    )
                )
                - effective_fdr,
            )
            total_damage += multistrike_damage
            calc.append(f"  multistrike: +{multistrike_damage} → total={total_damage}")

        # --- Executioner: 1% proc; true damage fires after dodge/block if not avoided ---
        is_executed = False
        if monster.has_modifier("Executioner") and random.random() < 0.01:
            is_executed = True
            calc.append(
                "  executioner: PROC'd — true damage applied if not dodged/blocked"
            )

        # --- Dodge & Block ---
        # (is_dodged and is_blocked initialized above before the hit-check branch)

        # Phantom Reflex: temporary evasion bonus from miss stacks
        _pr_bonus = 0.0
        if player.hematurgy_passives:
            from core.hematurgy.engine import get_phantom_reflex_evasion_bonus

            _pr_bonus = get_phantom_reflex_evasion_bonus(player)

        if monster.has_modifier("Unavoidable"):
            dodge_chance = (player.get_total_evasion() / 100 + _pr_bonus) * 0.20
        else:
            dodge_chance = player.get_total_evasion() / 100 + _pr_bonus
        if celestial == "celestial_wind_dancer":
            dodge_chance *= 3.0
        if random.random() <= dodge_chance:
            is_dodged = True

        if not is_dodged:
            if monster.has_modifier("Unblockable"):
                block_chance = player.get_total_block() / 100 * 0.20
            else:
                block_chance = player.get_total_block() / 100
            if celestial == "celestial_glancing_blows":
                block_chance *= 2.0
            if random.random() <= block_chance:
                is_blocked = True

        calc.append(
            f"  dodge/block: evasion={player.get_total_evasion()}%"
            f"{'(×0.2unavoidable)' if monster.has_modifier('Unavoidable') else ''} "
            f"block={player.get_total_block()}%"
            f"{'(×0.2unblockable)' if monster.has_modifier('Unblockable') else ''} "
            f"→ {'DODGED' if is_dodged else ('BLOCKED' if is_blocked else 'none')}"
        )

        # --- Resolve mitigation states ---
        if is_dodged:
            total_damage = 0
            # Volatile Spikes and Onslaught reset on dodge
            if monster.has_modifier("Volatile Spikes"):
                monster.spike_stacks = 0
            if monster.has_modifier("Onslaught"):
                monster.onslaught_bonus_atk = 0.0
            log.append(
                f"{monster.name} {monster.flavor}, but you 🏃 nimbly step aside!"
            )
            clog.append("🏃 Dodged!")
            if helmet_passive == "ghosted" and helmet_lvl > 0:
                ward_gain = helmet_lvl * 10
                added = _add_ward(player, ward_gain, log)
                log.append(
                    f"**Ghosted ({helmet_lvl})** manifests **{added}** 🔮 Ward from the movement!"
                )
                # skip in compact — ward visible in HP bar

        elif is_blocked:
            # Volatile Spikes and Onslaught reset on block
            if monster.has_modifier("Volatile Spikes"):
                monster.spike_stacks = 0
            if monster.has_modifier("Onslaught"):
                monster.onslaught_bonus_atk = 0.0
            if celestial == "celestial_glancing_blows":
                total_damage = int(total_damage * 0.5)
                log.append(
                    f"{monster.name} {monster.flavor}, but your armor 🛡️ partially blocks it (Bleedthrough: {total_damage})!"
                )
                clog.append(f"🛡️ Partially blocked! (Bleedthrough: {total_damage})")
            else:
                total_damage = 0
                log.append(
                    f"{monster.name} {monster.flavor}, but your armor 🛡️ blocks all damage!"
                )
                clog.append("🛡️ Blocked all damage!")

            if helmet_passive == "thorns" and helmet_lvl > 0:
                # Reflects pre-PDR/FDR damage — the raw incoming hit before player mitigation
                reflect = int(dmg_raw * helmet_lvl)
                monster.hp = max(0, monster.hp - reflect)
                log.append(
                    f"**Thorns ({helmet_lvl})** reflects **{reflect}** damage back!"
                )
                # skip in compact — monster HP change visible in HP bar

        # --- Sundering: 25% of damage bypasses player ward directly to HP ---
        if (
            monster.has_modifier("Sundering")
            and player.combat_ward > 0
            and total_damage > 0
            and not is_dodged
            and not is_blocked
        ):
            bypass = int(total_damage * monster.get_modifier_value("Sundering"))
            ward_portion = total_damage - bypass
            ward_absorbed = min(ward_portion, player.combat_ward)
            player.combat_ward -= ward_absorbed
            player.current_hp = max(0, player.current_hp - bypass)
            total_damage = ward_portion - ward_absorbed  # remaining after ward
            if bypass > 0:
                _sun_msg = f"⚡ **Sundering** — {bypass} damage pierces your ward directly!"
                log.append(_sun_msg)
                clog.append(_sun_msg)
            calc.append(
                f"  sundering: bypass={bypass} ward_absorbed={ward_absorbed} remaining={total_damage}"
            )

        # --- Apply damage to ward / HP ---
        if player.alchemy_def_boost_turns > 0 and total_damage > 0:
            reduction = int(total_damage * player.alchemy_def_boost_pct)
            total_damage = max(0, total_damage - reduction)
            player.alchemy_def_boost_turns -= 1
            if reduction > 0:
                _iron_msg = (
                    f"🛡️ **Iron Skin** absorbs **{reduction}** damage! "
                    f"({player.alchemy_def_boost_turns} turn{'s' if player.alchemy_def_boost_turns != 1 else ''} left)"
                )
                log.append(_iron_msg)
                clog.append(_iron_msg)
            if player.alchemy_def_boost_turns <= 0:
                player.alchemy_def_boost_pct = 0.0

        if player.alchemy_dmg_reduction_turns > 0 and total_damage > 0:
            reduction = int(total_damage * player.alchemy_dmg_reduction_pct)
            total_damage = max(0, total_damage - reduction)
            player.alchemy_dmg_reduction_turns = 0
            player.alchemy_dmg_reduction_pct = 0.0
            if reduction > 0:
                _dulled_msg = f"🩹 **Dulled Pain** reduces damage by **{reduction}**!"
                log.append(_dulled_msg)
                clog.append(_dulled_msg)

        # Partner: co_damage_reduction (L×5% chance to halve incoming damage)
        if (
            player.active_partner
            and total_damage > 0
            and not is_dodged
            and not is_blocked
        ):
            for key, lvl in player.active_partner.combat_skills:
                if key == "co_damage_reduction":
                    if random.random() < lvl * 0.05:
                        halved = total_damage // 2
                        total_damage = max(1, total_damage - halved)
                        _pdr_msg = (
                            f"🛡️ **{player.active_partner.name}** intercepts part of the blow!"
                            f" (−{halved} damage)"
                        )
                        log.append(_pdr_msg)
                        clog.append(_pdr_msg)
                    break

        if total_damage > 0 and not is_dodged:
            # --- Volatile Spikes: 30% chance to add +1 spike on connected hit (cap 10) ---
            if monster.has_modifier("Volatile Spikes") and not is_blocked:
                if random.random() < 0.30:
                    monster.spike_stacks = min(10, monster.spike_stacks + 1)

            # --- Onslaught: +v ATK bonus per consecutive hit ---
            if monster.has_modifier("Onslaught") and not is_blocked:
                monster.onslaught_bonus_atk += monster.get_modifier_value("Onslaught")

            damage_dealt = 0

            if player.get_tome_bonus("tenacity") > 0 and random.random() < (
                player.get_tome_bonus("tenacity") / 100
            ):
                total_damage = max(1, total_damage // 2)
                _ten_msg = "**Tenacity** braces the impact, halving the damage!"
                log.append(_ten_msg)
                clog.append(_ten_msg)

            void_passive = player.get_accessory_void_passive()
            if void_passive == "nullfield" and random.random() < 0.15:
                _null_msg = "⬛ **Nullfield** absorbs the strike into the void!"
                log.append(_null_msg)
                clog.append(_null_msg)
                total_damage = 0

            if player.alchemy_overcap_hp > 0 and total_damage > 0:
                absorbed = min(player.alchemy_overcap_hp, total_damage)
                player.alchemy_overcap_hp = 0
                total_damage -= absorbed
                _overcap_msg = f"💥 **Overcap Brew** temp HP absorbs **{absorbed}** damage and shatters!"
                log.append(_overcap_msg)
                clog.append(_overcap_msg)

            glove_corrupted = player.get_glove_corrupted_essence()
            helmet_corrupted = player.get_helmet_corrupted_essence()

            # --- Gemini helmet: reduce damage by 20%, then split evenly between ward and HP simultaneously ---
            if (
                helmet_corrupted == "gemini"
                and player.combat_ward > 0
                and total_damage > 0
            ):
                reduced = int(total_damage * 0.8)
                ward_half = reduced // 2
                hp_half = reduced - ward_half
                ward_absorbed = min(ward_half, player.combat_ward)
                player.combat_ward -= ward_absorbed
                damage_dealt = ward_absorbed
                if not is_blocked:
                    log.append(
                        f"{monster.name} {monster.flavor}.\n"
                        f"**Twin Balance** reduces and splits the blow (−20%) — 🔮 {ward_absorbed} to ward, 💔 {hp_half} bleeds through!"
                    )
                    clog.append(f"⚖️ Twin Balance: 🔮 {ward_absorbed} to ward, 💔 {hp_half} bleeds through!")
                total_damage = hp_half

            elif player.combat_ward > 0 and total_damage > 0:
                if total_damage <= player.combat_ward:
                    damage_dealt = total_damage
                    player.combat_ward -= total_damage
                    if not is_blocked:
                        log.append(
                            f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {total_damage} damage!"
                        )
                        clog.append(f"🔮 Ward absorbs {total_damage}!")
                    total_damage = 0
                else:
                    damage_dealt = player.combat_ward
                    if not is_blocked:
                        log.append(
                            f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {player.combat_ward} damage, but shatters!"
                        )
                        clog.append(f"🔮 Ward shatters! ({player.combat_ward} absorbed)")
                    total_damage -= player.combat_ward
                    player.combat_ward = 0

                    if helmet_corrupted == "lucifer" and player.lucifer_pdr_burst == 0:
                        player.lucifer_pdr_burst = 15
                        log.append(
                            "🔥 **Infernal Resilience** — ward shattered, gaining **+15%** PDR for this combat!"
                        )
                        # skip in compact — subtle buff that will affect future numbers

            if total_damage > 0:
                if player.active_task_species == monster.species:
                    tiers = player.get_emblem_bonus("slayer_def")
                    if tiers > 0:
                        total_damage = int(total_damage * (1 - min(0.50, tiers * 0.02)))

                # Astral Aegis shield (powerful distilled passive) — absorb damage, prevent death while active
                shield_hp = getattr(player, "alchemy_shield_hp", 0)
                if shield_hp > 0 and total_damage > 0:
                    absorb = min(shield_hp, total_damage)
                    player.alchemy_shield_hp = max(0, shield_hp - absorb)
                    total_damage -= absorb
                    if absorb > 0:
                        _shield_msg = f"🛡️ **Astral Aegis** absorbs **{absorb}** damage!"
                        log.append(_shield_msg)
                        clog.append(_shield_msg)
                    if player.alchemy_shield_hp <= 0:
                        player.alchemy_shield_turns = 0
                        log.append("🛡️ Astral Aegis shield has been depleted.")

                if (
                    celestial == "celestial_vow"
                    and (player.current_hp - total_damage <= 0)
                    and not getattr(player, "celestial_vow_used", False)
                ):
                    player.current_hp = 1
                    ward_gain = int(player.total_max_hp * 0.5)
                    added = _add_ward(player, ward_gain, log)
                    player.celestial_vow_used = True
                    _vow_msg = f"✨ **Celestial Vow** activates! You survive the fatal blow and gain {added} 🔮 Ward!"
                    log.append(f"\n{_vow_msg}")
                    clog.append(_vow_msg)
                elif getattr(player, "alchemy_shield_hp", 0) > 0 and (player.current_hp - total_damage <= 0):
                    # Astral Aegis saves from lethal while shield active
                    remaining_shield = player.alchemy_shield_hp
                    player.current_hp = max(1, player.current_hp)
                    player.alchemy_shield_hp = 0
                    player.alchemy_shield_turns = 0
                    _aegis_save = f"🛡️ **Astral Aegis** shatters to prevent a lethal blow!"
                    log.append(f"\n{_aegis_save}")
                    clog.append(_aegis_save)
                else:
                    damage_dealt += total_damage
                    player.current_hp -= total_damage
                    if not is_blocked or celestial != "celestial_glancing_blows":
                        log.append(
                            f"{monster.name} {monster.flavor}. You take 💔 **{total_damage}** damage!"
                        )
                        clog.append(f"You take 💔 **{total_damage}** damage!")

            # --- Commanding / Minion Army: % of applied damage as true damage echo ---
            minion_echo_pct = 0.0
            if monster.has_modifier("Minion Army"):
                minion_echo_pct = 0.15
            elif monster.has_modifier("Commanding"):
                minion_echo_pct = 0.075

            if minion_echo_pct > 0 and total_damage > 0 and not is_dodged and not is_blocked:
                echo_dmg = int(total_damage * minion_echo_pct)
                if echo_dmg > 0:
                    player.current_hp = max(0, player.current_hp - echo_dmg)
                    _echo_msg = f"👹 Minions strike for **{echo_dmg}** true damage!"
                    log.append(_echo_msg)
                    clog.append(_echo_msg)

            if void_passive == "eternal_hunger" and damage_dealt > 0:
                player.hunger_stacks += 1
                if player.hunger_stacks >= 10:
                    hunger_dmg = int(monster.max_hp * 0.10)
                    monster.hp = max(0, monster.hp - hunger_dmg)
                    player.current_hp = player.total_max_hp
                    player.hunger_stacks = 0
                    _hunger_msg = (
                        f"⬛ **Eternal Hunger** consumes the pain!\n"
                        f"💀 Devoured **{hunger_dmg}** HP ({monster.name}'s max × 10%)!\n"
                        f"❤️ Wounds consumed — HP restored to full!"
                    )
                    log.append(_hunger_msg)
                    clog.append(_hunger_msg)
                else:
                    log.append(
                        f"⬛ **Eternal Hunger** feeds ({player.hunger_stacks}/10 stacks)."
                    )
                    # skip in compact — stack count visible in Status field

            ward_was_hit = damage_dealt > 0 and previous_ward > 0
            # Aphrodite glove corrupted essence: all ward damage counts as ward-breaking
            aphrodite_glove_active = (
                glove_corrupted == "aphrodite"
                and ward_was_hit
                and player.combat_ward > 0
            )
            if helmet_passive == "volatile" and helmet_lvl > 0:
                if previous_ward > 0 and (
                    player.combat_ward == 0 or aphrodite_glove_active
                ):
                    boom = int(player.total_max_hp * helmet_lvl)
                    monster.hp = max(0, monster.hp - boom)
                    if player.combat_ward == 0:
                        _vol_msg = f"\n💥 **Volatile** Shield shatters, dealing **{boom}** damage to {monster.name}!"
                        log.append(_vol_msg)
                        clog.append(_vol_msg.strip())
                    else:
                        _vol_msg = f"\n💥 **Volatile** (Aphrodite) — ward struck, dealing **{boom}** damage to {monster.name}!"
                        log.append(_vol_msg)
                        clog.append(_vol_msg.strip())

            # Lucifer helmet: gain PDR burst when ward is fully broken.
            # Also triggers via Aphrodite glove (any ward damage = "broken" condition).
            if helmet_corrupted == "lucifer" and player.lucifer_pdr_burst == 0:
                lucifer_trigger = False
                if player.combat_ward == 0 and previous_ward > 0:
                    lucifer_trigger = True
                elif aphrodite_glove_active:
                    lucifer_trigger = True
                if lucifer_trigger:
                    player.lucifer_pdr_burst = 15
                    log.append(
                        "🔥 **Infernal Resilience** — ward broken, gaining **+15% PDR** for this combat!"
                    )
                    # skip in compact — subtle buff

            # Vampiric: heals X% of max HP per successful hit
            if monster.has_modifier("Vampiric") and damage_dealt > 0:
                # sqrt scaling: same heal at 10k HP, tapers naturally above that
                heal = int(
                    math.sqrt(monster.max_hp * 10_000)
                    * monster.get_modifier_value("Vampiric")
                )
                monster.hp = min(monster.max_hp, monster.hp + heal)
                log.append(
                    f"The monster's **Vampiric** essence siphons life, healing it for **{heal}** HP!"
                )
                # skip in compact — monster HP regen visible in HP bar

            # --- Hemorrhage: 30% chance to add +1 bleed stack on each hit ---
            if monster.has_modifier("Hemorrhage") and damage_dealt > 0:
                if random.random() < 0.30:
                    monster.bleed_stacks += 1
                    # skip in compact — stack count visible in Afflictions

            # --- Impending Doom: +1 doom stack per hit; instant kill at 44 ---
            if monster.has_modifier("Impending Doom") and damage_dealt > 0:
                monster.doom_stacks += 1
                if monster.doom_stacks >= 44:
                    player.current_hp = 0
                    _doom_msg = "☠️ **Impending Doom fulfills itself!** The accumulated curse shatters your existence!"
                    log.append(_doom_msg)
                    clog.append(_doom_msg)
                # stack gain itself: skip in compact — visible in Afflictions

            # Thorned: player takes X% of player max HP on each hit
            if not is_dodged and monster.has_modifier("Thorned") and damage_dealt > 0:
                thorned_pct = monster.get_modifier_value("Thorned")
                base_thorned = int(player.total_max_hp * thorned_pct)
                t_pdr = player.get_total_pdr()
                t_fdr = player.get_total_fdr()
                thorned_dmg = max(1, int(base_thorned * (1 - t_pdr / 100)) - t_fdr)
                player.current_hp = max(0, player.current_hp - thorned_dmg)
                _thorned_msg = f"🩸 **Thorned** — you take **{thorned_dmg}** damage for striking!"
                log.append(_thorned_msg)
                clog.append(_thorned_msg)

            if minion_dmg > 0:
                _min_msg = f"Their minions strike for an additional {minion_dmg} damage!"
                log.append(_min_msg)
                clog.append(_min_msg)
            if multistrike_damage > 0:
                _multi_msg = f"{monster.name} strikes again for {multistrike_damage} damage!"
                log.append(_multi_msg)
                clog.append(_multi_msg)

            # Balanced Strikes: every even round, second hit at 50% damage bypassing ward
            if (
                monster.has_modifier("Balanced Strikes")
                and monster.combat_round % 2 == 0
            ):
                balanced_pct = monster.get_modifier_value("Balanced Strikes")
                twin_raw, _, _, _ = _roll_monster_damage(
                    player, monster, effective_pdr, effective_fdr
                )
                twin_dmg = max(1, int(twin_raw * balanced_pct))
                player.current_hp = max(0, player.current_hp - twin_dmg)
                _bs_msg = f"⚡ **Balanced Strikes!** The bound sovereigns strike as one for **{twin_dmg}** damage! *(Bypasses ward)*"
                log.append(_bs_msg)
                clog.append(_bs_msg)

        # --- Executioner: true damage — bypasses all PDR/FDR/ward/DR layers ---
        # Fires only when the attack connected (not dodged, not blocked).
        if is_executed and not is_dodged and not is_blocked and player.current_hp > 0:
            exec_dmg = int(player.current_hp * 0.90)
            if exec_dmg > 0:
                player.current_hp = max(0, player.current_hp - exec_dmg)
                calc.append(
                    f"  executioner_true_dmg: {exec_dmg} (90% of {player.current_hp + exec_dmg} current HP)"
                )
                _exec_msg = (
                    f"⚔️ The {monster.name}'s **Executioner** cleaves through your defenses"
                    f" for **{exec_dmg}** 💀 true damage!"
                )
                log.append(_exec_msg)
                clog.append(_exec_msg)

        if not log:
            log.append(
                f"{monster.name} {monster.flavor}, but you mitigate all its damage."
            )
        if not clog:
            clog.append("All damage mitigated!")

    else:  # Miss
        # Venomous: true damage on miss — bypasses PDR/FDR/ward entirely
        if monster.has_modifier("Venomous"):
            venom_pct = monster.get_modifier_value("Venomous")
            venom_dmg = max(1, int(player.total_max_hp * venom_pct))
            player.current_hp = max(0, player.current_hp - venom_dmg)
            _ven_msg = f"{monster.name} misses, but **Venomous** aura deals **{venom_dmg}** 🐍 true damage!"
            log.append(_ven_msg)
            clog.append(_ven_msg)
        else:
            log.append(f"{monster.name} misses!")
            clog.append("🏃 Miss!")

    # Partner: sig_co_eve — survive a fatal hit by consuming potions
    start = len(log)
    if (
        player.current_hp <= 0
        and player.active_partner
        and player.active_partner.sig_combat_key == "sig_co_eve"
        and player.active_partner.sig_combat_lvl >= 1
    ):
        from core.partners.mechanics import _EVE_SIG_POTIONS

        potions_needed = _EVE_SIG_POTIONS.get(player.active_partner.sig_combat_lvl, 5)
        if player.potions >= potions_needed:
            player.potions -= potions_needed
            player.current_hp = player.total_max_hp
            log.append(
                f"💊 **Final Stand Lv.{player.active_partner.sig_combat_lvl}**"
                f" — Intercepted a fatal blow! Consumed {potions_needed} potion(s). "
                f"You recover to full HP before taking the blow!"
            )
    capture_compact_events(log, clog, start)

    player.current_hp = max(0, player.current_hp)
    hp_damage = max(0, prev_hp - player.current_hp)

    # --- Paradise Jewel: Bastion — charge on HP damage taken ---
    start = len(log)
    if hp_damage > 0:
        _bastion_log: list[str] = []
        _je.process_jewel_trigger(
            player, monster, "hp_damage_taken", hp_damage, _bastion_log
        )
        if _bastion_log:
            log.extend(_bastion_log)
    capture_compact_events(log, clog, start)

    # --- Hematurgy: end-of-monster-turn effects ---
    if player.hematurgy_passives:
        from core.hematurgy.engine import on_monster_turn_end

        _hema_log: list[str] = []
        on_monster_turn_end(
            player, monster, hp_damage, is_dodged, is_blocked, _hema_log
        )
        if _hema_log:
            log.extend(_hema_log)
        # skip in compact — hematurgy effects are secondary

    calc.append(
        f"  final: ward_remaining={player.combat_ward} hp_damage={hp_damage} "
        f"player_hp={player.current_hp}/{player.total_max_hp}"
    )
    return MonsterTurnResult(
        log="\n".join(log),
        hp_damage=hp_damage,
        calc_detail="\n".join(calc),
        compact_log="\n".join(clog),
    )
