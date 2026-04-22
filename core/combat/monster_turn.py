import random

from core.combat.calcs import calculate_damage_taken, calculate_monster_hit_chance
from core.combat.helpers import MonsterTurnResult, _add_ward
from core.models import Monster, Player


def _roll_monster_damage(
    player: Player, monster: Monster, effective_pdr: int, effective_fdr: int
) -> tuple[int, int, int]:
    """Rolls a single monster damage hit including modifiers, PDR, FDR, and minions.
    Returns (total_damage, base_damage, minion_damage)."""
    dmg = calculate_damage_taken(player, monster)

    if "Celestial Watcher" in monster.modifiers:
        dmg = int(dmg * 1.2)
    if "Hellborn" in monster.modifiers:
        dmg = int(dmg * 1.12)
    if "Hell's Fury" in monster.modifiers:
        dmg = int(dmg * 1.25)
    if "Mirror Image" in monster.modifiers and random.random() < 0.2:
        dmg *= 2
    if "Unlimited Blade Works" in monster.modifiers:
        dmg *= 2

    pdr = max(0, effective_pdr - (20 if "Penetrator" in monster.modifiers else 0))
    dmg = max(0, int(dmg * (1 - pdr / 100)))

    fdr = int(effective_fdr * (0.65 if "Clobberer" in monster.modifiers else 1.0))
    dmg = max(0, dmg - fdr)

    minions = 0
    if "Summoner" in monster.modifiers:
        minions += int(dmg * (1 / 3))
    if "Infernal Legion" in monster.modifiers:
        minions += dmg
    minions = max(0, minions - fdr)

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

    celestial = player.get_celestial_armor_passive()
    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    previous_ward = player.combat_ward

    # --- Hit chance ---
    hit_chance = calculate_monster_hit_chance(player, monster)
    if "Prescient" in monster.modifiers:
        hit_chance = min(0.95, hit_chance + 0.10)
    if "All-seeing" in monster.modifiers:
        hit_chance = min(0.95, hit_chance * 1.10)
    if "Celestial Watcher" in monster.modifiers:
        hit_chance = 1.0

    monster_roll = random.random()
    if "Lucifer-touched" in monster.modifiers and random.random() < 0.5:
        monster_roll = min(monster_roll, random.random())

    # --- Void Aura drain (regardless of hit) ---
    if "Void Aura" in monster.modifiers:
        drain_atk = max(1, int(player.flat_atk * 0.05))
        drain_def = max(0, int(player.flat_def * 0.05))
        player.bonus_atk -= drain_atk
        player.bonus_def -= drain_def
        log.append(
            f"🌑 **Void Drain** siphons **{drain_atk}** ATK and **{drain_def}** DEF!"
        )

    if monster_roll <= hit_chance:
        # --- PDR / FDR setup ---
        effective_pdr = player.get_total_pdr()
        if celestial == "celestial_fortress":
            missing_pct = (1 - (player.current_hp / player.total_max_hp)) * 100
            effective_pdr += int(missing_pct / 5.0)
        effective_fdr = player.get_total_fdr()

        # --- Base damage roll (Celestial Sanctity takes the lower of two) ---
        total_damage, dmg_base, minion_dmg = _roll_monster_damage(
            player, monster, effective_pdr, effective_fdr
        )
        if celestial == "celestial_sanctity":
            alt_total, alt_base, alt_minion = _roll_monster_damage(
                player, monster, effective_pdr, effective_fdr
            )
            if alt_total < total_damage:
                total_damage, dmg_base, minion_dmg = alt_total, alt_base, alt_minion

        # --- Multistrike & Executioner ---
        multistrike_damage = 0
        if "Multistrike" in monster.modifiers and random.random() <= hit_chance:
            multistrike_damage = max(
                0, int(calculate_damage_taken(player, monster) * 0.5) - effective_fdr
            )
            total_damage += multistrike_damage

        is_executed = False
        if "Executioner" in monster.modifiers and random.random() < 0.01:
            total_damage = max(total_damage, int(player.current_hp * 0.90))
            is_executed = True

        # --- Dodge & Block ---
        is_dodged = False
        is_blocked = False

        if "Unavoidable" not in monster.modifiers:
            dodge_chance = player.get_total_evasion() / 100
            if celestial == "celestial_wind_dancer":
                dodge_chance *= 3.0
            if random.random() <= dodge_chance:
                is_dodged = True

        if not is_dodged and "Unblockable" not in monster.modifiers:
            block_chance = player.get_total_block() / 100
            if celestial == "celestial_glancing_blows":
                block_chance *= 2.0
            if random.random() <= block_chance:
                is_blocked = True

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

            if "Vampiric" in monster.modifiers and damage_dealt > 0:
                heal = int(monster.max_hp * 0.05)
                monster.hp = min(monster.max_hp, monster.hp + heal)
                log.append(
                    f"The monster's **Vampiric** essence siphons life, healing it for **{heal}** HP!"
                )

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

            if "Twin Strike" in monster.modifiers and monster.combat_round % 2 == 0:
                twin_raw, _, _ = _roll_monster_damage(
                    player, monster, effective_pdr, effective_fdr
                )
                twin_dmg = max(1, int(twin_raw * 0.5))
                player.current_hp = max(0, player.current_hp - twin_dmg)
                log.append(
                    f"⚡ **Twin Strike!** The bound sovereigns strike as one for **{twin_dmg}** damage!"
                )

        if not log:
            log.append(
                f"{monster.name} {monster.flavor}, but you mitigate all its damage."
            )

    else:  # Miss
        if "Venomous" in monster.modifiers:
            venom_dmg = max(1, int(player.total_max_hp * 0.02))
            player.current_hp = max(1, player.current_hp - venom_dmg)
            log.append(
                f"{monster.name} misses, but their **Venomous** aura deals **{venom_dmg}** 🐍 damage!"
            )
        else:
            log.append(f"{monster.name} misses!")

    player.current_hp = max(0, player.current_hp)
    return MonsterTurnResult(
        log="\n".join(log),
        hp_damage=max(0, prev_hp - player.current_hp),
    )
