import random

from core.combat.calcs import calculate_damage_taken, calculate_monster_hit_chance
from core.combat.helpers import MonsterTurnResult, _add_ward
from core.models import Monster, Player


def _roll_monster_damage(
    player: Player, monster: Monster, effective_pdr: int, effective_fdr: int,
    calc: list[str] | None = None,
) -> tuple[int, int, int]:
    """Rolls a single monster damage hit including modifiers, PDR, FDR, and minions.
    Returns (total_damage, base_damage, minion_damage)."""
    m_atk = monster.attack
    p_def = max(player.get_total_defence(), 1)
    base_raw = 5 + monster.level * 1.5
    surplus = max(-0.95, (m_atk - p_def) / p_def)
    dmg = calculate_damage_taken(player, monster)

    calc_notes: list[str] = [
        f"m_atk={m_atk} p_def={p_def} base={base_raw:.0f} surplus={surplus:+.3f} → raw≈{int(base_raw*(1+surplus))} rolled={dmg}"
    ]

    # Enraged: continuous attack scaling based on HP lost (applied as damage multiplier)
    if monster.has_modifier("Enraged"):
        enrage_pct = monster.get_modifier_value("Enraged")
        hp_lost = 1.0 - (monster.hp / monster.max_hp) if monster.max_hp > 0 else 0.0
        stacks = min(3, int(hp_lost / 0.25))
        if stacks > 0:
            enrage_mult = 1 + enrage_pct * stacks
            dmg = int(dmg * enrage_mult)
            calc_notes.append(f"enraged×{enrage_mult:.2f}(stacks={stacks})={dmg}")

    # Savage: flat damage multiplier
    if monster.has_modifier("Savage"):
        dmg = int(dmg * (1 + monster.get_modifier_value("Savage")))
        calc_notes.append(f"savage×{1+monster.get_modifier_value('Savage'):.2f}={dmg}")

    # Overwhelming: always double damage (boss mod)
    if monster.has_modifier("Overwhelming"):
        dmg *= 2
        calc_notes.append(f"overwhelming×2={dmg}")

    # Hell's Fury: triple damage (uber Lucifer only)
    if monster.has_modifier("Hell's Fury"):
        fury_mult = monster.get_modifier_value("Hell's Fury")
        dmg = int(dmg * fury_mult)
        calc_notes.append(f"hells_fury×{fury_mult:.1f}={dmg}")

    # Spectral: 20% chance to double raw damage before reductions
    if monster.has_modifier("Spectral") and random.random() < monster.get_modifier_value("Spectral"):
        dmg *= 2
        calc_notes.append(f"spectral×2={dmg}")

    # Monster crit (base 10% + Lethal)
    base_crit_chance = 0.10
    if monster.has_modifier("Lethal"):
        base_crit_chance += monster.get_modifier_value("Lethal")
    is_monster_crit = random.random() < base_crit_chance
    if is_monster_crit:
        crit_mult = 2.0
        if monster.has_modifier("Devastating"):
            crit_mult += monster.get_modifier_value("Devastating")
        dmg = int(dmg * crit_mult)
        calc_notes.append(f"monster_crit×{crit_mult:.1f}={dmg}")

    # PDR: Crushing ignores X% of player's PDR
    pdr = effective_pdr
    if monster.has_modifier("Crushing"):
        pdr = max(0, int(pdr * (1 - monster.get_modifier_value("Crushing"))))
        calc_notes.append(f"crushing pdr→{pdr}%")
    pre_pdr = dmg
    dmg = max(0, int(dmg * (1 - pdr / 100)))
    calc_notes.append(f"PDR={pdr}% {pre_pdr}→{dmg}")

    # FDR: Searing ignores X% of player's FDR
    fdr = effective_fdr
    if monster.has_modifier("Searing"):
        fdr = max(0, int(fdr * (1 - monster.get_modifier_value("Searing"))))
        calc_notes.append(f"searing fdr→{fdr}")
    pre_fdr = dmg
    dmg = max(0, dmg - fdr)
    if fdr > 0:
        calc_notes.append(f"FDR={fdr} {pre_fdr}→{dmg}")

    # Commanding: minions echo X% of pre-FDR damage, then FDR applies to echo
    minions = 0
    if monster.has_modifier("Commanding"):
        echo_pct = monster.get_modifier_value("Commanding")
        raw_echo = int(pre_fdr * echo_pct)
        minions = max(0, raw_echo - fdr)
    minions = max(0, minions)
    if minions > 0:
        calc_notes.append(f"commanding_echo={minions}")

    # Inevitable: 50% damage (boss mod — always hits but halved)
    if monster.has_modifier("Inevitable"):
        dmg = max(1, int(dmg * monster.get_modifier_value("Inevitable")))
        calc_notes.append(f"inevitable×{monster.get_modifier_value('Inevitable'):.2f}={dmg}")

    if calc is not None:
        calc.append("  dmg_roll: " + " → ".join(calc_notes) + f" | base={dmg} minions={minions} total={dmg+minions}")

    return dmg + minions, dmg, minions


def process_monster_turn(player: Player, monster: Monster) -> MonsterTurnResult:
    """Executes the monster's turn, applies damage to player, and returns combat log."""
    if player.is_invulnerable_this_combat:
        return MonsterTurnResult(
            log=f"The **Invulnerable** armor protects {player.name}, absorbing all damage from {monster.name}!",
            hp_damage=0,
        )

    monster.combat_round += 1
    prev_hp = player.current_hp
    log: list[str] = []
    calc: list[str] = []

    celestial = player.get_celestial_armor_passive()
    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    previous_ward = player.combat_ward

    # --- Mending: passive HP regen every other monster turn ---
    if monster.has_modifier("Mending") and monster.combat_round % 2 == 0:
        regen = int(monster.max_hp * monster.get_modifier_value("Mending"))
        monster.hp = min(monster.max_hp, monster.hp + regen)
        log.append(f"{monster.name}'s **Mending** restores **{regen}** HP!")

    # --- Void Aura drain (regardless of hit) ---
    if monster.has_modifier("Void Aura"):
        drain_atk = max(1, int(player.flat_atk * 0.005))
        drain_def = max(0, int(player.flat_def * 0.005))
        player.bonus_atk -= drain_atk
        player.bonus_def -= drain_def
        log.append(
            f"🌑 **Void Drain** siphons **{drain_atk}** ATK and **{drain_def}** DEF!"
        )

    # --- Hit chance ---
    hit_chance_base = calculate_monster_hit_chance(player, monster)
    hit_chance = hit_chance_base
    hit_mods: list[str] = [f"base={hit_chance_base*100:.1f}%"]

    # Keen: flat bonus treated as +X% hit chance (capped at 0.95 unless Inevitable)
    keen_bonus = int(monster.get_modifier_value("Keen")) if monster.has_modifier("Keen") else 0
    if keen_bonus > 0:
        hit_chance = min(0.95, hit_chance + keen_bonus / 100)
        hit_mods.append(f"+{keen_bonus}%(keen)={hit_chance*100:.1f}%")

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
    calc.append(
        f"  hit: {' → '.join(hit_mods)} | roll={monster_roll:.4f} "
        f"→ {'HIT' if is_monster_hit else 'MISS'}"
    )

    if is_monster_hit:
        # --- PDR / FDR setup ---
        effective_pdr = player.get_total_pdr()
        pdr_notes = [f"base={effective_pdr}%"]
        if celestial == "celestial_fortress":
            missing_pct = (1 - (player.current_hp / player.total_max_hp)) * 100
            bonus_pdr = int(missing_pct / 5.0)
            effective_pdr += bonus_pdr
            pdr_notes.append(f"+{bonus_pdr}%(fortress,{missing_pct:.1f}%missing)={effective_pdr}%")
        effective_fdr = player.get_total_fdr()
        calc.append(f"  PDR: {' → '.join(pdr_notes)} | FDR: {effective_fdr}")

        # --- Base damage roll (Celestial Sanctity takes the lower of two) ---
        total_damage, dmg_base, minion_dmg = _roll_monster_damage(
            player, monster, effective_pdr, effective_fdr, calc
        )
        if celestial == "celestial_sanctity":
            alt_total, alt_base, alt_minion = _roll_monster_damage(
                player, monster, effective_pdr, effective_fdr
            )
            if alt_total < total_damage:
                total_damage, dmg_base, minion_dmg = alt_total, alt_base, alt_minion
                calc.append(f"  celestial_sanctity: took lower roll → {total_damage}")

        # --- Multistrike ---
        multistrike_damage = 0
        if monster.has_modifier("Multistrike") and random.random() <= hit_chance:
            multistrike_damage = max(
                0, int(calculate_damage_taken(player, monster) * 0.5) - effective_fdr
            )
            total_damage += multistrike_damage
            calc.append(f"  multistrike: +{multistrike_damage} → total={total_damage}")

        # --- Executioner ---
        is_executed = False
        if monster.has_modifier("Executioner") and random.random() < 0.01:
            total_damage = max(total_damage, int(player.current_hp * 0.90))
            is_executed = True
            calc.append(f"  executioner: forced={total_damage} (90% of player_hp={player.current_hp})")

        # --- Dodge & Block ---
        is_dodged = False
        is_blocked = False

        if monster.has_modifier("Unavoidable"):
            dodge_chance = player.get_total_evasion() / 100 * 0.20
        else:
            dodge_chance = player.get_total_evasion() / 100
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
            log.append(
                f"{monster.name} {monster.flavor}, but you 🏃 nimbly step aside!"
            )
            if helmet_passive == "ghosted" and helmet_lvl > 0:
                ward_gain = helmet_lvl * 10
                added = _add_ward(player, ward_gain, log)
                log.append(
                    f"**Ghosted ({helmet_lvl})** manifests **{added}** 🔮 Ward from the movement!"
                )

        elif is_blocked:
            if celestial == "celestial_glancing_blows":
                total_damage = int(total_damage * 0.5)
                log.append(
                    f"{monster.name} {monster.flavor}, but your armor 🛡️ partially blocks it (Bleedthrough: {total_damage})!"
                )
            else:
                total_damage = 0
                log.append(
                    f"{monster.name} {monster.flavor}, but your armor 🛡️ blocks all damage!"
                )

            if helmet_passive == "thorns" and helmet_lvl > 0:
                reflect = int(dmg_base * helmet_lvl)
                monster.hp -= reflect
                log.append(
                    f"**Thorns ({helmet_lvl})** reflects **{reflect}** damage back!"
                )

        # --- Sundering: 25% of damage bypasses player ward directly to HP ---
        if monster.has_modifier("Sundering") and player.combat_ward > 0 and total_damage > 0 and not is_dodged and not is_blocked:
            bypass = int(total_damage * monster.get_modifier_value("Sundering"))
            ward_portion = total_damage - bypass
            ward_absorbed = min(ward_portion, player.combat_ward)
            player.combat_ward -= ward_absorbed
            player.current_hp = max(0, player.current_hp - bypass)
            total_damage = ward_portion - ward_absorbed  # remaining after ward
            if bypass > 0:
                log.append(f"⚡ **Sundering** — {bypass} damage pierces your ward directly!")
            calc.append(f"  sundering: bypass={bypass} ward_absorbed={ward_absorbed} remaining={total_damage}")

        # --- Apply damage to ward / HP ---
        if player.alchemy_def_boost_turns > 0 and total_damage > 0:
            reduction = int(total_damage * player.alchemy_def_boost_pct)
            total_damage = max(0, total_damage - reduction)
            player.alchemy_def_boost_turns -= 1
            if reduction > 0:
                log.append(
                    f"🛡️ **Iron Skin** absorbs **{reduction}** damage! "
                    f"({player.alchemy_def_boost_turns} turn{'s' if player.alchemy_def_boost_turns != 1 else ''} left)"
                )
            if player.alchemy_def_boost_turns <= 0:
                player.alchemy_def_boost_pct = 0.0

        if player.alchemy_dmg_reduction_turns > 0 and total_damage > 0:
            reduction = int(total_damage * player.alchemy_dmg_reduction_pct)
            total_damage = max(0, total_damage - reduction)
            player.alchemy_dmg_reduction_turns = 0
            player.alchemy_dmg_reduction_pct = 0.0
            if reduction > 0:
                log.append(f"🩹 **Dulled Pain** reduces damage by **{reduction}**!")

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
                        log.append(
                            f"🛡️ **{player.active_partner.name}** intercepts part of the blow!"
                            f" (−{halved} damage)"
                        )
                    break

        if total_damage > 0 and not is_dodged:
            damage_dealt = 0

            if player.get_tome_bonus("tenacity") > 0 and random.random() < (
                player.get_tome_bonus("tenacity") / 100
            ):
                total_damage = max(1, total_damage // 2)
                log.append("**Tenacity** braces the impact, halving the damage!")

            void_passive = player.get_accessory_void_passive()
            if void_passive == "nullfield" and random.random() < 0.15:
                log.append("⬛ **Nullfield** absorbs the strike into the void!")
                total_damage = 0

            if player.alchemy_overcap_hp > 0 and total_damage > 0:
                absorbed = min(player.alchemy_overcap_hp, total_damage)
                player.alchemy_overcap_hp = 0
                total_damage -= absorbed
                log.append(
                    f"💥 **Overcap Brew** temp HP absorbs **{absorbed}** damage and shatters!"
                )

            glove_corrupted = player.get_glove_corrupted_essence()
            helmet_corrupted = player.get_helmet_corrupted_essence()

            # --- Gemini helmet: split damage evenly between ward and HP simultaneously ---
            if (
                helmet_corrupted == "gemini"
                and player.combat_ward > 0
                and total_damage > 0
            ):
                ward_half = total_damage // 2
                hp_half = total_damage - ward_half
                ward_absorbed = min(ward_half, player.combat_ward)
                player.combat_ward -= ward_absorbed
                damage_dealt = ward_absorbed
                if not is_blocked:
                    log.append(
                        f"{monster.name} {monster.flavor}.\n"
                        f"**Twin Balance** splits the blow — 🔮 {ward_absorbed} to ward, 💔 {hp_half} bleeds through!"
                    )
                total_damage = hp_half

            elif player.combat_ward > 0 and total_damage > 0:
                if total_damage <= player.combat_ward:
                    damage_dealt = total_damage
                    player.combat_ward -= total_damage
                    if not is_blocked:
                        log.append(
                            f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {total_damage} damage!"
                        )
                    total_damage = 0
                else:
                    damage_dealt = player.combat_ward
                    if not is_blocked:
                        log.append(
                            f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {player.combat_ward} damage, but shatters!"
                        )
                    total_damage -= player.combat_ward
                    player.combat_ward = 0

                    if helmet_corrupted == "lucifer" and player.lucifer_pdr_burst == 0:
                        player.lucifer_pdr_burst = 15
                        log.append(
                            "🔥 **Infernal Resilience** — ward shattered, gaining **+15%** PDR for this combat!"
                        )

            if total_damage > 0:
                if player.active_task_species == monster.species:
                    tiers = player.get_emblem_bonus("slayer_def")
                    if tiers > 0:
                        total_damage = int(total_damage * (1 - min(0.50, tiers * 0.02)))

                if (
                    celestial == "celestial_vow"
                    and (player.current_hp - total_damage <= 0)
                    and not getattr(player, "celestial_vow_used", False)
                ):
                    player.current_hp = 1
                    ward_gain = int(player.total_max_hp * 0.5)
                    added = _add_ward(player, ward_gain, log)
                    player.celestial_vow_used = True
                    damage_dealt += player.current_hp - 1
                    log.append(
                        f"\n✨ **Celestial Vow** activates! You survive the fatal blow and gain {added} 🔮 Ward!"
                    )
                else:
                    damage_dealt += total_damage
                    player.current_hp -= total_damage
                    if not is_blocked or celestial != "celestial_glancing_blows":
                        log.append(
                            f"{monster.name} {monster.flavor}. You take 💔 **{total_damage}** damage!"
                        )

            if void_passive == "eternal_hunger" and damage_dealt > 0:
                player.hunger_stacks += 1
                if player.hunger_stacks >= 10:
                    hunger_dmg = int(monster.max_hp * 0.10)
                    monster.hp = max(0, monster.hp - hunger_dmg)
                    player.current_hp = player.total_max_hp
                    player.hunger_stacks = 0
                    log.append(
                        f"⬛ **Eternal Hunger** consumes the pain!\n"
                        f"💀 Devoured **{hunger_dmg}** HP ({monster.name}'s max × 10%)!\n"
                        f"❤️ Wounds consumed — HP restored to full!"
                    )
                else:
                    log.append(
                        f"⬛ **Eternal Hunger** feeds ({player.hunger_stacks}/10 stacks)."
                    )

            ward_was_hit = damage_dealt > 0 and previous_ward > 0
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
                    monster.hp -= boom
                    if player.combat_ward == 0:
                        log.append(
                            f"\n💥 **Volatile** Shield shatters, dealing **{boom}** damage to {monster.name}!"
                        )
                    else:
                        log.append(
                            f"\n💥 **Volatile** (Aphrodite) — ward struck, dealing **{boom}** damage to {monster.name}!"
                        )

            # Vampiric: heals X% of max HP per successful hit
            if monster.has_modifier("Vampiric") and damage_dealt > 0:
                heal = int(monster.max_hp * monster.get_modifier_value("Vampiric"))
                monster.hp = min(monster.max_hp, monster.hp + heal)
                log.append(
                    f"The monster's **Vampiric** essence siphons life, healing it for **{heal}** HP!"
                )

            # Thorned: player takes X% of monster max HP on each hit
            if not is_dodged and monster.has_modifier("Thorned") and damage_dealt > 0:
                thorned_pct = monster.get_modifier_value("Thorned")
                base_thorned = int(monster.max_hp * thorned_pct)
                t_pdr = player.get_total_pdr()
                t_fdr = player.get_total_fdr()
                thorned_dmg = max(1, int(base_thorned * (1 - t_pdr / 100)) - t_fdr)
                player.current_hp = max(0, player.current_hp - thorned_dmg)
                log.append(f"🩸 **Thorned** — you take **{thorned_dmg}** damage for striking!")

            if is_executed:
                log.append(
                    f"The {monster.name}'s **Executioner** ability cleaves through you!"
                )
            if minion_dmg > 0:
                log.append(
                    f"Their minions strike for an additional {minion_dmg} damage!"
                )
            if multistrike_damage > 0:
                log.append(
                    f"{monster.name} strikes again for {multistrike_damage} damage!"
                )

            # Balanced Strikes: every even round, second hit at 50% damage bypassing ward
            if monster.has_modifier("Balanced Strikes") and monster.combat_round % 2 == 0:
                balanced_pct = monster.get_modifier_value("Balanced Strikes")
                twin_raw, _, _ = _roll_monster_damage(
                    player, monster, effective_pdr, effective_fdr
                )
                twin_dmg = max(1, int(twin_raw * balanced_pct))
                player.current_hp = max(0, player.current_hp - twin_dmg)
                log.append(
                    f"⚡ **Balanced Strikes!** The bound sovereigns strike as one for **{twin_dmg}** damage! *(Bypasses ward)*"
                )

        if not log:
            log.append(
                f"{monster.name} {monster.flavor}, but you mitigate all its damage."
            )

    else:  # Miss
        # Venomous: player takes X% of monster max HP on each miss
        if monster.has_modifier("Venomous"):
            venom_pct = monster.get_modifier_value("Venomous")
            base_venom = int(player.max_hp * venom_pct)
            t_pdr = player.get_total_pdr()
            t_fdr = player.get_total_fdr()
            venom_dmg = max(1, int(base_venom * (1 - t_pdr / 100)) - t_fdr)
            player.current_hp = max(0, player.current_hp - venom_dmg)
            log.append(
                f"{monster.name} misses, but their **Venomous** aura deals **{venom_dmg}** 🐍 damage!"
            )
        else:
            log.append(f"{monster.name} misses!")

    # Partner: sig_co_eve — survive a fatal hit by consuming potions
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
            player.current_hp = 1
            log.append(
                f"💊 **{player.active_partner.name}'s Sig Lv.{player.active_partner.sig_combat_lvl}**"
                f" — Intercepted a fatal blow! Consumed {potions_needed} potion(s). "
                f"You survive with 1 HP!"
            )

    player.current_hp = max(0, player.current_hp)
    hp_damage = max(0, prev_hp - player.current_hp)
    calc.append(
        f"  final: ward_remaining={player.combat_ward} hp_damage={hp_damage} "
        f"player_hp={player.current_hp}/{player.total_max_hp}"
    )
    return MonsterTurnResult(
        log="\n".join(log),
        hp_damage=hp_damage,
        calc_detail="\n".join(calc),
    )
