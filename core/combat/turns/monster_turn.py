import math
import random

from core.combat import jewel_engine as _je
from core.combat.calc.damage_calc import calculate_damage_taken
from core.combat.calc.damage_calc import roll_monster_damage as _roll_monster_damage
from core.combat.calc.hit_calc import calculate_monster_hit_chance
from core.combat.calc.ward_system import _add_ward
from core.combat.turns.helpers import MonsterTurnResult, capture_compact_events
from core.emojis import (
    CELESTIAL_ENGRAM,
    GOLD_COIN,
    INFERNAL_ENGRAM,
    MOD_FLASHFIRE,
    MOD_PRESSURE_SURGE,
    STAT_WARD,
    VOID_ENGRAM,
)
from core.models import Monster, Player


def process_monster_turn(
    player: Player, monster: Monster, *, context_note: str = ""
) -> MonsterTurnResult:
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
            return MonsterTurnResult(
                log=_freeze_txt, hp_damage=0, compact_log=_freeze_txt
            )

    monster.combat_round += 1
    prev_hp = player.current_hp
    log: list[str] = []
    clog: list[str] = []  # compact log for auto-battle — no flavor text
    calc: list[str] = []
    if context_note:
        calc.append(f"  [context]{context_note}")

    # Decrement Panacea immunity turns at start of monster turn (before ailments land)
    if getattr(player, "alchemy_ailment_immunity_turns", 0) > 0:
        player.alchemy_ailment_immunity_turns -= 1
        if player.alchemy_ailment_immunity_turns > 0:
            # Simple representation: player is protected this turn
            log.append(
                f"🌿 **Panacea** — protected from ailments this turn ({player.alchemy_ailment_immunity_turns} remaining)."
            )

    # Decrement Enrage duration unconditionally each monster turn (it's advertised as
    # "next N monster turns", not "next N hits taken" — must expire on schedule even
    # if the monster's attack misses entirely).
    if player.alchemy_def_boost_turns > 0:
        player.alchemy_def_boost_turns -= 1
        if player.alchemy_def_boost_turns <= 0:
            player.alchemy_def_boost_pct = 0.0
            player.alchemy_atk_boost_pct = 0.0

    # Decrement Enfeeble duration unconditionally each monster turn, same rule as
    # Enrage above. Enfeeble debuffs the monster's actual ATK/DEF stats directly
    # (applied to monster.bonus_attack_pct / bonus_defence_pct in player_turn.py
    # on potion use — same live-mutation pattern as Frenzied Hunger), so it lowers
    # both the monster's damage output and the player's hit chance against it for
    # its whole duration; when the duration runs out here, undo exactly the amount
    # that was applied.
    if player.alchemy_enfeeble_turns > 0:
        player.alchemy_enfeeble_turns -= 1
        if player.alchemy_enfeeble_turns <= 0 and player.alchemy_enfeeble_pct > 0:
            monster.bonus_attack_pct += player.alchemy_enfeeble_pct
            monster.bonus_defence_pct += player.alchemy_enfeeble_pct
            player.alchemy_enfeeble_pct = 0.0
            log.append("🌊 **Enfeeble** wears off.")

    celestial = player.get_celestial_armor_passive()
    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    previous_ward = player.combat_ward

    # --- Death Rattle: countdown tick → heal if reaches 0 ---
    if monster.death_rattle_triggered and monster.death_rattle_countdown > 0:
        monster.death_rattle_countdown -= 1
        if monster.death_rattle_countdown == 0:
            heal_target = int(
                monster.max_hp * monster.get_modifier_value("Death Rattle")
            )
            if monster.hp < heal_target:
                healed = heal_target - monster.hp
                monster.hp = heal_target
                _dr_heal_msg = f"☠️ **Death Rattle** — {monster.name} endures! Heals to **{monster.hp}** HP! (+{healed})"
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
                f"{MOD_FLASHFIRE} **Flashfire DETONATES!** The buildup erupts for **{burst}** true damage!"
            )
    capture_compact_events(
        log, clog, start
    )  # detonation only (silent on charge buildup)

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

    # --- Pressure Surge: +1 if player didn't crit; -1 if player critted; at 10 → true damage ---
    start = len(log)
    if monster.has_modifier("Pressure Surge"):
        if monster.pressure_player_critted:
            monster.pressure_stacks = max(0, monster.pressure_stacks - 1)
        else:
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
                f"{MOD_PRESSURE_SURGE} **Pressure Surge RELEASES!** Pent-up force slams for **{burst}** true damage!"
            )
    capture_compact_events(
        log, clog, start
    )  # release burst only (silent on stack increment)

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
                    f"💜 **Soul Siphon** drains **{siphon_amt}** {STAT_WARD} ward, healing {monster.name} for **{heal_amt}** HP!"
                )
                # skip in compact — ward change visible in HP bar

    # --- Corrosion: +1 corrode stack every N turns (cap 5); N decreases with tier ---
    if (
        monster.has_modifier("Corrosion")
        and monster.combat_round % int(monster.get_modifier_value("Corrosion")) == 0
    ):
        if monster.corrode_stacks < 5:
            monster.corrode_stacks += 1
        v = int(monster.get_modifier_value("Corrosion"))
        log.append(
            f"🧪 **Corrosion** — your armour degrades! Corrode stack {monster.corrode_stacks}/5 (−{monster.corrode_stacks * v} PDR)"
        )
        # skip in compact — PDR change visible in Afflictions field

    # --- Temporal Collapse: every N turns return a fraction of accumulated damage ---
    # Returns 4% of total damage dealt, hard-capped at 10% of player max HP.
    # This scales naturally with how much damage the player dealt rather than
    # always hitting the ceiling for high-damage players.
    start = len(log)
    if (
        monster.has_modifier("Temporal Collapse")
        and monster.combat_round % int(monster.get_modifier_value("Temporal Collapse"))
        == 0
        and monster.combat_round > 0
    ):
        if monster.temporal_window_damage > 0:
            proportional = int(monster.temporal_window_damage * 0.04)
            cap = int(player.total_max_hp * 0.10)
            collapse_dmg = min(proportional, cap)
            was_capped = proportional > cap
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
    # void_drain_rate defaults to 0.0 on every Monster; when unset we keep the
    # standard Uber NEET rate (0.5%) exactly as before. NEET Reborn (Rite of
    # Convergence, Wing 4) sets a higher rate on the monster at generation time.
    start = len(log)
    if monster.has_modifier("Void Aura"):
        drain_rate = monster.void_drain_rate if monster.void_drain_rate > 0 else 0.005
        drain_atk = max(1, int(player.flat_atk * drain_rate))
        drain_def = max(0, int(player.flat_def * drain_rate))
        player.bonus_atk -= drain_atk
        player.bonus_def -= drain_def
        log.append(
            f"🌑 **Void Drain** siphons **{drain_atk}** ATK and **{drain_def}** DEF!"
        )
    capture_compact_events(log, clog, start)

    # --- Unbreakable (Aphrodite Reborn — Rite of Convergence, Wing 1): +1 charge
    # per turn; at threshold, deals the player's full HP + Ward as true damage
    # (guaranteed kill unless an Undying effect — e.g. Celestial Vow — saves them).
    start = len(log)
    if monster.has_modifier("Unbreakable"):
        monster.unbreakable_charges += 1
        threshold = int(monster.get_modifier_value("Unbreakable"))
        if monster.unbreakable_charges >= threshold:
            if celestial == "celestial_vow" and not getattr(
                player, "celestial_vow_used", False
            ):
                heal_amount = int(player.total_max_hp * 0.5)
                player.current_hp = heal_amount
                ward_gain = int(player.total_max_hp * 0.5)
                added = _add_ward(player, ward_gain, log)
                player.celestial_vow_used = True
                log.append(
                    f"💥 **Unbreakable** reaches its limit — but **Celestial Vow** "
                    f"saves you! You're restored to **{heal_amount}** HP and gain "
                    f"**{added}** {STAT_WARD} Ward!"
                )
            else:
                player.current_hp = 0
                player.combat_ward = 0
                log.append(
                    "💥 **Unbreakable** reaches its limit! An unstoppable wave of "
                    "true damage obliterates you!"
                )
            monster.unbreakable_charges = 0
    capture_compact_events(log, clog, start)

    # ==========================================================================
    # APEX ZONE EFFECTS (pre-hit, per monster turn)
    # ==========================================================================

    apex_zone = getattr(monster, "apex_zone", None)

    # Tempest zone: every 3rd monster turn → unavoidable 10% max HP true damage
    start = len(log)
    if (
        apex_zone == "storm"
        and monster.combat_round % 3 == 0
        and monster.combat_round > 0
    ):
        lightning_dmg = max(1, int(player.total_max_hp * 0.10))
        player.current_hp = max(0, player.current_hp - lightning_dmg)
        log.append(
            f"⚡ **Tempest Lightning** — the storm strikes for **{lightning_dmg}** ⚡ true damage!"
        )
    capture_compact_events(log, clog, start)

    # Living Battlefield: monster regen 0.5% max HP per turn
    if apex_zone == "grove" and monster.hp < monster.max_hp:
        regen = max(1, int(monster.max_hp * 0.005))
        monster.hp = min(monster.max_hp, monster.hp + regen)
        log.append(
            f"🌿 **Living Battlefield** — the grove heals {monster.name} for **{regen}** HP!"
        )
        # skip in compact — monster HP regen visible in HP bar

    # Tempted Fate: every 3rd monster turn drain ALL player ward (Aphrodite
    # helmet's Ward Failsafe converts the drained amount into DEF instead).
    start = len(log)
    if (
        apex_zone == "vault"
        and monster.combat_round % 3 == 0
        and monster.combat_round > 0
    ):
        drained = player.combat_ward
        if drained > 0:
            player.combat_ward = 0
            if player.get_helmet_corrupted_essence() == "aphrodite":
                player.bonus_def += drained
                log.append(
                    f"{GOLD_COIN} **Tempted Fate** — fortune's price is paid! **{drained}** {STAT_WARD} Ward converted to DEF!"
                )
            else:
                log.append(
                    f"{GOLD_COIN} **Tempted Fate** — fortune's price is paid! All **{drained}** {STAT_WARD} Ward drained!"
                )
    capture_compact_events(log, clog, start)

    # Reality Fracture: every 4th monster turn reroll one modifier
    if (
        apex_zone == "shattered"
        and monster.combat_round % 4 == 0
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
    hit_mods: list[str] = [f"base={hit_chance_base * 100:.1f}%"]

    # Difficulty: scaled flat accuracy bonus applied before other modifiers
    _DIFFICULTY_HIT_BONUS = [0.0, 0.15, 0.20, 0.30, 0.50]
    _DIFFICULTY_NAMES_MT = ["", "hard", "extreme", "nightmarish", "delirious"]
    if monster.difficulty_level > 0:
        hit_bonus = _DIFFICULTY_HIT_BONUS[monster.difficulty_level]
        diff_label = _DIFFICULTY_NAMES_MT[monster.difficulty_level]
        hit_chance = min(0.95, hit_chance + hit_bonus)
        hit_mods.append(
            f"+{int(hit_bonus * 100)}%({diff_label}_mode)={hit_chance * 100:.1f}%"
        )

    # Keen: flat bonus treated as +X% hit chance (capped at 0.95 unless Inevitable)
    keen_bonus = (
        int(monster.get_modifier_value("Keen")) if monster.has_modifier("Keen") else 0
    )
    if keen_bonus > 0:
        hit_chance = min(0.95, hit_chance + keen_bonus / 100)
        hit_mods.append(f"+{keen_bonus}%(keen)={hit_chance * 100:.1f}%")

    # Overwhelming: accuracy penalty scales with tier (higher tier = more penalty)
    if monster.has_modifier("Overwhelming"):
        ov = monster.get_modifier_value("Overwhelming")
        ov_penalty = int((ov - 1.6) * 50 + 20) / 100
        hit_chance = max(0.15, hit_chance - ov_penalty)
        hit_mods.append(
            f"-{int(ov_penalty * 100)}%(overwhelming)={hit_chance * 100:.1f}%"
        )

    # Unerring: chance to take higher of two rolls
    if monster.has_modifier("Unerring"):
        hit_mods.append(
            f"unerring({int(monster.get_modifier_value('Unerring') * 100)}%chance-2roll-high)"
        )

    # Inevitable: always hit
    if monster.has_modifier("Inevitable"):
        hit_chance = 1.0
        hit_mods.append("100%(inevitable)")

    monster_roll = random.random()
    if monster.has_modifier(
        "Unerring"
    ) and random.random() < monster.get_modifier_value("Unerring"):
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
            effective_pdr = min(
                effective_pdr, max(0, player.get_raw_pdr() - corrode_reduction)
            )
        pdr_notes = [f"base={effective_pdr}%"]
        pdr_cap = (
            90
            if (
                player.equipped_armor and player.equipped_armor.passive == "Impregnable"
            )
            else 80
        )
        if celestial == "celestial_fortress":
            missing_pct = (1 - (player.current_hp / player.total_max_hp)) * 100
            bonus_pdr = int(missing_pct / 5.0)
            effective_pdr = min(pdr_cap, effective_pdr + bonus_pdr)
            pdr_notes.append(
                f"+{bonus_pdr}%(fortress,{missing_pct:.1f}%missing)={effective_pdr}%"
            )
        effective_fdr = player.get_total_fdr()

        # Slayer tree hu_2 bonus PDR/FDR vs assigned species
        _hu2 = getattr(player, "slayer_tree_nodes", {}).get("hu_2")
        if _hu2 and player.active_task_species == monster.species:
            if _hu2 == "pdr":
                effective_pdr = min(pdr_cap, effective_pdr + 8)
                pdr_notes.append(f"+8%(hu2_pdr)={effective_pdr}%")
            elif _hu2 == "fdr":
                effective_fdr += 24

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
            wr_val = monster.wrathful_stacks * monster.get_modifier_value(
                "Wrathful Retaliation"
            )
            monster.damage_increased_pct += wr_val
            calc.append(
                f"  +{wr_val:.2f} to damage_increased_pct from Wrathful Retaliation ({monster.wrathful_stacks} stacks)"
            )

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
                total_damage, dmg_raw, _, minion_dmg = (
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

        # --- True Reckoning (Gemini Reborn — Rite of Convergence, Wing 3): a fixed
        # percentage of the RAW pre-mitigation hit is unconditionally true damage
        # (bypasses PDR/FDR/Ward entirely); only the remainder is mitigated normally
        # and can still be dodged/blocked/ward-absorbed like a regular hit. Applied
        # once dodge/block are known, further down.
        true_reckoning_portion = 0
        if monster.has_modifier("True Reckoning"):
            tr_pct = monster.get_modifier_value("True Reckoning")
            true_reckoning_portion = int(dmg_raw * tr_pct)
            remaining_raw = dmg_raw - true_reckoning_portion
            total_damage = max(
                0, int(remaining_raw * (1 - effective_pdr / 100)) - effective_fdr
            )
            calc.append(
                f"  true_reckoning: raw={dmg_raw} → true={true_reckoning_portion} "
                f"mitigated_remainder={total_damage}"
            )

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
            dodge_chance = (
                player.get_total_evasion() / 100 + _pr_bonus
            ) * monster.get_modifier_value("Unavoidable")
        else:
            dodge_chance = player.get_total_evasion() / 100 + _pr_bonus
        if celestial == "celestial_wind_dancer":
            dodge_chance *= 3.0
        if random.random() <= dodge_chance:
            is_dodged = True

        if not is_dodged:
            if monster.has_modifier("Unblockable"):
                block_chance = (
                    player.get_total_block()
                    / 100
                    * monster.get_modifier_value("Unblockable")
                )
            else:
                block_chance = player.get_total_block() / 100
            if celestial == "celestial_glancing_blows":
                block_chance *= 2.0
            if random.random() <= block_chance:
                is_blocked = True

        _unav_note = (
            f"(×{monster.get_modifier_value('Unavoidable'):.2f}unavoidable)"
            if monster.has_modifier("Unavoidable")
            else ""
        )
        _unbl_note = (
            f"(×{monster.get_modifier_value('Unblockable'):.2f}unblockable)"
            if monster.has_modifier("Unblockable")
            else ""
        )
        calc.append(
            f"  dodge/block: evasion={player.get_total_evasion()}%{_unav_note} "
            f"block={player.get_total_block()}%{_unbl_note} "
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
                    f"**Ghosted ({helmet_lvl})** manifests **{added}** {STAT_WARD} Ward from the movement!"
                )
                # skip in compact — ward visible in HP bar
            else:
                # Soul stone: ghosted — 1:1 tier match to helmet lvl.
                ss_ghosted = player.get_soul_stone_passive("ghosted")
                if ss_ghosted:
                    ward_gain = ss_ghosted * 10
                    added = _add_ward(player, ward_gain, log)
                    log.append(
                        f"**Soul Ghosted T{ss_ghosted}** manifests **{added}** {STAT_WARD} Ward from the movement!"
                    )

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
                reflect = int(dmg_raw * helmet_lvl * 5)
                monster.hp = max(0, monster.hp - reflect)
                log.append(
                    f"**Thorns ({helmet_lvl})** reflects **{reflect}** damage back!"
                )
                # skip in compact — monster HP change visible in HP bar
            else:
                # Soul stone: thorns — 1:1 tier match to helmet lvl.
                ss_thorns = player.get_soul_stone_passive("thorns")
                if ss_thorns:
                    reflect = int(dmg_raw * ss_thorns * 5)
                    monster.hp = max(0, monster.hp - reflect)
                    log.append(
                        f"**Soul Thorns T{ss_thorns}** reflects **{reflect}** damage back!"
                    )

        # --- True Reckoning: apply the true-damage portion now that dodge/block
        # are known. Dodging or blocking the hit avoids the true portion too. ---
        if true_reckoning_portion > 0 and not is_dodged and not is_blocked:
            player.current_hp = max(0, player.current_hp - true_reckoning_portion)
            _tr_msg = (
                f"⚖️ **True Reckoning** — **{true_reckoning_portion}** damage "
                "bypasses all mitigation!"
            )
            log.append(_tr_msg)
            clog.append(_tr_msg)

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
                _sun_msg = (
                    f"⚡ **Sundering** — {bypass} damage pierces your ward directly!"
                )
                log.append(_sun_msg)
                clog.append(_sun_msg)
            calc.append(
                f"  sundering: bypass={bypass} ward_absorbed={ward_absorbed} remaining={total_damage}"
            )

        # --- Unified damage-taken reduction pool: Painkiller, Tenacity, Slayer ---
        # "Killing Blow" (tank). All active % sources are summed first, then applied
        # as a single reduction — mirrors apply_monster_damage_reduction()'s "Layer 1:
        # Regular DR" additive-pool pattern so these sources add together instead of
        # compounding multiplicatively against each other.
        if total_damage > 0:
            dtr_pct = 0.0
            dtr_parts: list[str] = []

            if player.alchemy_dmg_reduction_turns > 0:
                dtr_pct += player.alchemy_dmg_reduction_pct
                player.alchemy_dmg_reduction_turns -= 1
                dtr_parts.append(
                    f"🩹 Painkiller {int(player.alchemy_dmg_reduction_pct * 100)}% "
                    f"({player.alchemy_dmg_reduction_turns} hit{'s' if player.alchemy_dmg_reduction_turns != 1 else ''} left)"
                )
                if player.alchemy_dmg_reduction_turns <= 0:
                    player.alchemy_dmg_reduction_pct = 0.0

            tenacity_pct = player.get_tome_bonus("tenacity")
            if tenacity_pct > 0 and random.random() < (tenacity_pct / 100):
                dtr_pct += 0.50
                dtr_parts.append("**Tenacity** 50%")

            _tree_nodes = getattr(player, "slayer_tree_nodes", {})
            if (
                _tree_nodes.get("hu_3") == "tank"
                and player.active_task_species == monster.species
            ):
                dtr_pct += 0.25
                dtr_parts.append("Slayer's Killing Blow 25%")

            if dtr_pct > 0:
                dtr_pct = min(0.90, dtr_pct)
                reduction = int(total_damage * dtr_pct)
                total_damage = max(0, total_damage - reduction)
                _dtr_msg = (
                    f"{' + '.join(dtr_parts)} braces the impact, "
                    f"reducing the blow by **{reduction}**!"
                )
                log.append(_dtr_msg)
                clog.append(_dtr_msg)

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

            void_passive = player.get_accessory_void_passive()
            if void_passive == "nullfield" and random.random() < 0.15:
                _null_msg = (
                    f"{VOID_ENGRAM} **Nullfield** absorbs the strike into the void!"
                )
                log.append(_null_msg)
                clog.append(_null_msg)
                total_damage = 0

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
                        f"**Twin Balance** reduces and splits the blow (−20%) — {STAT_WARD} {ward_absorbed} to ward, 💔 {hp_half} bleeds through!"
                    )
                    clog.append(
                        f"⚖️ Twin Balance: {STAT_WARD} {ward_absorbed} to ward, 💔 {hp_half} bleeds through!"
                    )
                total_damage = hp_half

            elif player.combat_ward > 0 and total_damage > 0:
                if total_damage <= player.combat_ward:
                    damage_dealt = total_damage
                    player.combat_ward -= total_damage
                    if not is_blocked:
                        log.append(
                            f"{monster.name} {monster.flavor}.\nYour ward absorbs {STAT_WARD} {total_damage} damage!"
                        )
                        clog.append(f"{STAT_WARD} Ward absorbs {total_damage}!")
                    total_damage = 0
                else:
                    damage_dealt = player.combat_ward
                    if not is_blocked:
                        log.append(
                            f"{monster.name} {monster.flavor}.\nYour ward absorbs {STAT_WARD} {player.combat_ward} damage, but shatters!"
                        )
                        clog.append(
                            f"{STAT_WARD} Ward shatters! ({player.combat_ward} absorbed)"
                        )
                    total_damage -= player.combat_ward
                    player.combat_ward = 0

                    if helmet_corrupted == "lucifer" and player.lucifer_pdr_burst == 0:
                        player.lucifer_pdr_burst = 15
                        log.append(
                            f"{INFERNAL_ENGRAM} **Infernal Resilience** — ward shattered, gaining **+15%** PDR for this combat!"
                        )
                        # skip in compact — subtle buff that will affect future numbers

            # Slayer emblem "slayer_def" is already folded into DEF via
            # apply_stat_effects() (bonus_def), and hu_2 "def" is folded into DEF
            # via get_total_defence()'s pct_pool — neither is re-applied here to
            # avoid double-counting the same source. hu_3 "tank" is handled above
            # in the unified damage-taken reduction pool.

            if total_damage > 0:
                # Aegis shield (powerful distilled passive) — absorb damage
                shield_hp = getattr(player, "alchemy_shield_hp", 0)
                if shield_hp > 0 and total_damage > 0:
                    absorb = min(shield_hp, total_damage)
                    player.alchemy_shield_hp = max(0, shield_hp - absorb)
                    total_damage -= absorb
                    if absorb > 0:
                        _shield_msg = f"🛡️ **Aegis** absorbs **{absorb}** damage!"
                        log.append(_shield_msg)
                        clog.append(_shield_msg)
                    if player.alchemy_shield_hp <= 0:
                        player.alchemy_shield_turns = 0
                        log.append("🛡️ Aegis shield has been depleted.")

                if (
                    celestial == "celestial_vow"
                    and (player.current_hp - total_damage <= 0)
                    and not getattr(player, "celestial_vow_used", False)
                ):
                    heal_amount = int(player.total_max_hp * 0.5)
                    player.current_hp = heal_amount
                    ward_gain = int(player.total_max_hp * 0.5)
                    added = _add_ward(player, ward_gain, log)
                    player.celestial_vow_used = True
                    _vow_msg = (
                        f"{CELESTIAL_ENGRAM} **Celestial Vow** activates! You survive the fatal "
                        f"blow, heal to **{heal_amount}** HP, and gain **{added}** {STAT_WARD} Ward!"
                    )
                    log.append(f"\n{_vow_msg}")
                    clog.append(_vow_msg)
                else:
                    damage_dealt += total_damage
                    player.current_hp -= total_damage
                    if not is_blocked or celestial != "celestial_glancing_blows":
                        log.append(
                            f"{monster.name} {monster.flavor}. You take 💔 **{total_damage}** damage!"
                        )
                        clog.append(f"You take 💔 **{total_damage}** damage!")

                # Tick Aegis duration down after this monster attack
                if getattr(player, "alchemy_shield_turns", 0) > 0:
                    player.alchemy_shield_turns -= 1
                    if player.alchemy_shield_turns <= 0:
                        player.alchemy_shield_hp = 0

            # --- Commanding / Minion Army: % of applied damage as true damage echo ---
            minion_echo_pct = 0.0
            if monster.has_modifier("Minion Army"):
                minion_echo_pct = monster.get_modifier_value("Minion Army")
            elif monster.has_modifier("Commanding"):
                minion_echo_pct = monster.get_modifier_value("Commanding")

            if (
                minion_echo_pct > 0
                and total_damage > 0
                and not is_dodged
                and not is_blocked
            ):
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
                        f"{VOID_ENGRAM} **Eternal Hunger** consumes the pain!\n"
                        f"💀 Devoured **{hunger_dmg}** HP ({monster.name}'s max × 10%)!\n"
                        f"❤️ Wounds consumed — HP restored to full!"
                    )
                    log.append(_hunger_msg)
                    clog.append(_hunger_msg)
                else:
                    log.append(
                        f"{VOID_ENGRAM} **Eternal Hunger** feeds ({player.hunger_stacks}/10 stacks)."
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
            else:
                # Soul stone: volatile — 1:1 tier match to helmet lvl.
                ss_volatile = player.get_soul_stone_passive("volatile")
                if (
                    ss_volatile
                    and previous_ward > 0
                    and (player.combat_ward == 0 or aphrodite_glove_active)
                ):
                    boom = int(player.total_max_hp * ss_volatile)
                    monster.hp = max(0, monster.hp - boom)
                    if player.combat_ward == 0:
                        _vol_msg = f"\n💥 **Soul Volatile T{ss_volatile}** Shield shatters, dealing **{boom}** damage to {monster.name}!"
                    else:
                        _vol_msg = f"\n💥 **Soul Volatile T{ss_volatile}** (Aphrodite) — ward struck, dealing **{boom}** damage to {monster.name}!"
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
                        f"{INFERNAL_ENGRAM} **Infernal Resilience** — ward broken, gaining **+15% PDR** for this combat!"
                    )
                    # skip in compact — subtle buff

            # Artefact: Seal of Duality — on ward break, DEF +15-35% for the
            # rest of combat (rolled on drop).
            if (
                player.has_artefact("seal_of_duality")
                and not player.seal_of_duality_triggered
                and player.combat_ward == 0
                and previous_ward > 0
            ):
                player.seal_of_duality_triggered = True
                log.append(
                    f"🏺 **Seal of Duality** — ward broken, gaining "
                    f"**+{int(player.artefact.roll_1)}% DEF** for the rest of combat!"
                )

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

            # --- Judgment (Lucifer Reborn — Rite of Convergence, Wing 2): +1 charge
            # per hit the player takes; at threshold, deals 99% of full HP + Ward
            # as true damage.
            if monster.has_modifier("Judgment") and damage_dealt > 0:
                monster.judgment_charges += 1
                threshold = int(monster.get_modifier_value("Judgment"))
                if monster.judgment_charges >= threshold:
                    pool = player.current_hp + player.combat_ward
                    j_dmg = int(pool * 0.99)
                    player.current_hp = max(0, player.current_hp - j_dmg)
                    _judgment_msg = (
                        f"⚖️ **Judgment** reaches its limit! A cataclysmic true "
                        f"damage strike deals **{j_dmg}** damage!"
                    )
                    log.append(_judgment_msg)
                    clog.append(_judgment_msg)
                    monster.judgment_charges = 0

            # --- Impending Doom: +1 doom stack per hit; instant kill at tier-scaled threshold ---
            if monster.has_modifier("Impending Doom") and damage_dealt > 0:
                monster.doom_stacks += 1
                if monster.doom_stacks >= int(
                    monster.get_modifier_value("Impending Doom")
                ):
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
                _thorned_msg = (
                    f"🩸 **Thorned** — you take **{thorned_dmg}** damage for striking!"
                )
                log.append(_thorned_msg)
                clog.append(_thorned_msg)

            if minion_dmg > 0:
                _min_msg = (
                    f"Their minions strike for an additional {minion_dmg} damage!"
                )
                log.append(_min_msg)
                clog.append(_min_msg)
            if multistrike_damage > 0:
                _multi_msg = (
                    f"{monster.name} strikes again for {multistrike_damage} damage!"
                )
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
            exec_dmg = int(
                player.current_hp * monster.get_modifier_value("Executioner")
            )
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
            log.append(f"{monster.name} {monster.flavor}, but you shrug it off.")
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
