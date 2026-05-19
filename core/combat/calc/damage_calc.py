"""
damage_calc.py — Damage number computation.

Testable in isolation: every public function takes plain player/monster objects
and returns an integer without touching the DB or Discord.

Public API
----------
calculate_damage_taken(player, monster) -> int          # raw monster hit before PDR/FDR
roll_monster_damage(player, monster, pdr, fdr, calc)   # full monster damage roll with mods
calc_crit_damage(player, monster, mult, log, calc)      # player crit damage
calc_hit_damage(player, monster, mult, log, calc)       # player normal hit damage
calc_miss_damage(player, monster, mult, log, calc)      # player miss on-hit damage
apply_monster_damage_reduction(monster, dmg, log, calc) # monster's own DR modifiers
apply_damage_to_monster(player, monster, dmg, log)      # final application to monster ward+HP
"""

from __future__ import annotations

import random

from core.models import Monster, Player

_DMG_VARIANCE = (0.85, 1.15)


# ---------------------------------------------------------------------------
# Base formulas — pure math, trivially testable
# ---------------------------------------------------------------------------


def calculate_damage_taken(player: Player, monster: Monster) -> int:
    """Raw monster damage before PDR/FDR.
    Guaranteed base from monster level, amplified/dampened by stat surplus."""
    p_def = max(player.get_total_defence(), 1)
    base_raw = 5 + monster.level * 1.5
    surplus = (monster.attack - p_def) / p_def
    surplus = max(-0.95, surplus)
    raw = base_raw * (1.0 + surplus)
    return max(1, int(raw * random.uniform(*_DMG_VARIANCE)))


# ---------------------------------------------------------------------------
# Monster damage roll — includes all monster modifiers, PDR, FDR
# ---------------------------------------------------------------------------


def roll_monster_damage(
    player: Player,
    monster: Monster,
    effective_pdr: int,
    effective_fdr: int,
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

    if monster.has_modifier("Enraged"):
        enrage_pct = monster.get_modifier_value("Enraged")
        hp_lost = 1.0 - (monster.hp / monster.max_hp) if monster.max_hp > 0 else 0.0
        stacks = min(3, int(hp_lost / 0.25))
        if stacks > 0:
            enrage_mult = 1 + enrage_pct * stacks
            dmg = int(dmg * enrage_mult)
            calc_notes.append(f"enraged×{enrage_mult:.2f}(stacks={stacks})={dmg}")

    if monster.has_modifier("Savage"):
        dmg = int(dmg * (1 + monster.get_modifier_value("Savage")))
        calc_notes.append(f"savage×{1+monster.get_modifier_value('Savage'):.2f}={dmg}")

    if monster.has_modifier("Overwhelming"):
        dmg *= 2
        calc_notes.append(f"overwhelming×2={dmg}")

    if monster.has_modifier("Hell's Fury"):
        fury_mult = monster.get_modifier_value("Hell's Fury")
        dmg = int(dmg * fury_mult)
        calc_notes.append(f"hells_fury×{fury_mult:.1f}={dmg}")

    if monster.has_modifier(
        "Spectral"
    ) and random.random() < monster.get_modifier_value("Spectral"):
        dmg *= 2
        calc_notes.append(f"spectral×2={dmg}")

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

    pdr = effective_pdr
    if monster.has_modifier("Crushing"):
        pdr = max(0, int(pdr * (1 - monster.get_modifier_value("Crushing"))))
        calc_notes.append(f"crushing pdr→{pdr}%")
    pre_pdr = dmg
    dmg = max(0, int(dmg * (1 - pdr / 100)))
    calc_notes.append(f"PDR={pdr}% {pre_pdr}→{dmg}")

    fdr = effective_fdr
    if monster.has_modifier("Searing"):
        fdr = max(0, int(fdr * (1 - monster.get_modifier_value("Searing"))))
        calc_notes.append(f"searing fdr→{fdr}")
    pre_fdr = dmg
    dmg = max(0, dmg - fdr)
    if fdr > 0:
        calc_notes.append(f"FDR={fdr} {pre_fdr}→{dmg}")

    minions = 0
    if monster.has_modifier("Commanding"):
        echo_pct = monster.get_modifier_value("Commanding")
        raw_echo = int(pre_fdr * echo_pct)
        minions = max(0, int((raw_echo - fdr) * (1 - pdr / 100)))
    minions = max(0, minions)
    if minions > 0:
        calc_notes.append(f"commanding_echo={minions}")

    if monster.has_modifier("Inevitable"):
        dmg = max(1, int(dmg * monster.get_modifier_value("Inevitable")))
        calc_notes.append(
            f"inevitable×{monster.get_modifier_value('Inevitable'):.2f}={dmg}"
        )

    if calc is not None:
        calc.append(
            "  dmg_roll: "
            + " → ".join(calc_notes)
            + f" | base={dmg} minions={minions} total={dmg+minions}"
        )

    return dmg + minions, dmg, minions


# ---------------------------------------------------------------------------
# Player damage phases — called by player_turn orchestrator
# ---------------------------------------------------------------------------


def calc_crit_damage(
    player: Player,
    monster: Monster,
    attack_multiplier: float,
    log: list[str],
    calc: list[str],
) -> int:
    """Phase 4a — crit damage. Returns pre-reduction damage."""
    from core.combat import jewel_engine as _je
    from core.combat.calc.calcs import get_weapon_tier

    max_atk = player.get_total_attack()

    crit_floor = 0.5
    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "deftness" and glove_lvl > 0:
        crit_floor = min(0.75, crit_floor + (glove_lvl * 0.05))
        log.append(f"**Deftness ({glove_lvl})** hones your crits!")

    crit_min = max(1, int(max_atk * crit_floor) + 1)
    crit_max = max(crit_min, max_atk)
    crit_rolled = random.randint(crit_min, crit_max)

    crit_mult = player.get_weapon_crit_multi()
    nullifying_note = ""
    if monster.has_modifier("Nullifying"):
        null_val = monster.get_modifier_value("Nullifying")
        crit_mult = player.get_weapon_crit_multi() * (1 - null_val)
        nullifying_note = f" nullifying×{crit_mult:.2f}"

    base_dmg = int(crit_rolled * crit_mult)
    calc_dmg_notes: list[str] = [
        f"range=[{crit_min}–{crit_max}] rolled={crit_rolled} ×{crit_mult:.2f}={base_dmg}{nullifying_note}"
    ]
    if nullifying_note:
        log.append(
            f"The **Nullifying** aura dampens your critical hit! (×{crit_mult:.2f})"
        )

    crit_dmg_tiers = player.get_emblem_bonus("crit_dmg")
    if crit_dmg_tiers > 0:
        factor = 1 + crit_dmg_tiers * 0.05
        base_dmg = int(base_dmg * factor)
        calc_dmg_notes.append(f"crit_dmg_emblem×{factor:.3f}={base_dmg}")

    if player.active_partner:
        for key, lvl in player.active_partner.combat_skills:
            if key == "co_crit_damage":
                factor = 1 + lvl * 0.10
                base_dmg = int(base_dmg * factor)
                calc_dmg_notes.append(f"partner_crit_dmg×{factor:.3f}={base_dmg}")

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "insight" and helmet_lvl > 0:
        extra = helmet_lvl * 0.1
        base_dmg = int(base_dmg * (1 + extra))
        calc_dmg_notes.append(f"insight×{1+extra:.3f}={base_dmg}")
        log.append(
            f"**Insight ({helmet_lvl})** exposes a weak point! (Crit Dmg +{int(extra * 100)}%)"
        )

    if player.cursed_precision_active:
        alt = int(random.randint(crit_min, crit_max) * player.get_weapon_crit_multi())
        if alt < base_dmg:
            base_dmg = alt
            calc_dmg_notes.append(f"cursed_precision(alt={alt})={base_dmg}")
        log.append("**Cursed Precision** — the weaker roll applies!")

    cat_bonus = _je.apply_cataclysm_crit_bonus(player)
    if cat_bonus > 0:
        base_dmg = int(base_dmg * (1 + cat_bonus))
        calc_dmg_notes.append(f"cataclysm_jewel×{1+cat_bonus:.3f}={base_dmg}")
        log.append(f"💥 **Cataclysm** detonates! (×{1+cat_bonus:.2f} crit damage)")

    # --- Hematurgy: Chain Reaction and Executioner's Rite crit damage bonuses ---
    if player.hematurgy_passives:
        from core.hematurgy.engine import (
            get_chain_reaction_crit_bonus,
            get_executioners_rite_bonus,
        )
        cr_bonus = get_chain_reaction_crit_bonus(player)
        if cr_bonus > 0:
            base_dmg = int(base_dmg * (1 + cr_bonus))
            calc_dmg_notes.append(f"chain_reaction×{1+cr_bonus:.3f}={base_dmg}")
        er_crit = get_executioners_rite_bonus(player, monster)
        if er_crit > 0:
            base_dmg = int(base_dmg * (1 + er_crit))
            calc_dmg_notes.append(f"executioners_rite_crit×{1+er_crit:.3f}={base_dmg}")

    damage = int(base_dmg * attack_multiplier)
    calc_dmg_notes.append(f"×mult={attack_multiplier:.4f}={damage}")

    infernal = player.get_weapon_infernal()
    if infernal == "last_rites" and monster.hp > 0:
        bonus = int(monster.hp * 0.05)
        damage += bonus
        calc_dmg_notes.append(f"+last_rites={bonus}")
        log.append(f"**Last Rites** seals {monster.name}'s fate! (+{bonus})")

    if infernal == "voracious":
        if player.voracious_stacks > 0:
            log.append(
                f"**Voracious** resets after a crit! ({player.voracious_stacks} stacks lost)"
            )
        player.voracious_stacks = 0

    void_passive = player.get_accessory_void_passive()
    if void_passive == "void_gaze" and player.gaze_stacks < 30 and monster.attack > 0:
        player.gaze_stacks += 1
        reduction = max(1, int(monster.attack * 0.03))
        monster.attack = max(0, monster.attack - reduction)
        log.append(
            f"⬛ **Void Gaze** ({player.gaze_stacks}/30) — {monster.name}'s ATK -{reduction}!"
        )

    if (
        void_passive == "fracture"
        and not getattr(monster, "is_uber", False)
        and random.random() < 0.05
    ):
        damage = monster.hp
        calc_dmg_notes.append(f"fracture(instant_kill)={damage}")
        log.append("💀 **Fracture** tears open a void rift — **instant kill!**")

    if player.get_glove_corrupted_essence() == "lucifer" and player.combat_ward > 0:
        ward_bonus = int(player.combat_ward * 0.15)
        if ward_bonus > 0:
            damage += ward_bonus
            calc_dmg_notes.append(f"+lucifer_ward={ward_bonus}")
            log.append(f"🔥 **Soul Burn** — ward fuels the crit! (+{ward_bonus})")

    if player.get_glove_corrupted_essence() == "gemini":
        second_pct = random.uniform(0.40, 0.60)
        second_hit = int(damage * second_pct)
        if second_hit > 0:
            damage += second_hit
            calc_dmg_notes.append(f"+gemini_twin={second_hit}({second_pct:.0%})")
            log.append(f"⚖️ **Twin Strike** — a second blow lands! (+{second_hit})")

    calc.append("  crit_dmg: " + " → ".join(calc_dmg_notes) + f" = {damage}")

    idx, _ = get_weapon_tier(player, "piercing")
    if idx >= 0:
        log.append("The weapon glimmers with power!")
    log.append(f"Critical Hit! Damage: 🗡️ **{damage}**")
    return damage


def calc_hit_damage(
    player: Player,
    monster: Monster,
    attack_multiplier: float,
    log: list[str],
    calc: list[str],
) -> int:
    """Phase 4b — normal hit damage. Returns pre-reduction damage."""
    from core.combat.calc.calcs import fmt_weapon_passive, get_weapon_tier

    base_max = player.get_total_attack()
    base_min = 1

    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    adroit_note = ""
    if glove_passive == "adroit" and glove_lvl > 0:
        base_min = max(base_min, int(base_max * (glove_lvl * 0.02)))
        adroit_note = f" adroit_min={base_min}"
        log.append(f"**Adroit ({glove_lvl})** sharpens your technique!")

    burn_note = ""
    idx, name = get_weapon_tier(player, "burning")
    if idx >= 0:
        bonus = int(player.get_total_attack() * ((idx + 1) * 0.08))
        base_max += bonus
        burn_note = f" burn+{bonus}"
        log.append(
            f"**{fmt_weapon_passive(name)}** 🔥 burns bright!\nAttack damage potential boosted by **{bonus}**."
        )

    spark_note = ""
    idx, name = get_weapon_tier(player, "shocking")
    if idx >= 0:
        base_min = max(base_min, int(base_max * ((idx + 1) * 0.08)))
        spark_note = f" spark_min={base_min}"
        log.append(
            f"**{fmt_weapon_passive(name)}** surges with ⚡ lightning, ensuring solid impact!"
        )

    rolled = random.randint(min(base_min, base_max), base_max)
    damage = int(rolled * attack_multiplier)

    echo_idx, _ = get_weapon_tier(player, "echo")
    echo_damage = 0
    if echo_idx >= 0:
        echo_damage = int(damage * (echo_idx + 1) * 0.10)
        damage += echo_damage

    infernal = player.get_weapon_infernal()
    if infernal == "voracious":
        player.voracious_stacks += 1
        log.append(
            f"**Voracious** charges! ({player.voracious_stacks} stack{'s' if player.voracious_stacks != 1 else ''})"
        )

    lucifer_note = ""
    if player.get_glove_corrupted_essence() == "lucifer" and player.combat_ward > 0:
        ward_bonus = int(player.combat_ward * 0.15)
        if ward_bonus > 0:
            damage += ward_bonus
            lucifer_note = f" +lucifer_ward={ward_bonus}"
            log.append(f"🔥 **Soul Burn** — ward fuels the strike! (+{ward_bonus})")

    echo_note = f" +echo={echo_damage}" if echo_damage else ""
    calc.append(
        f"  hit_dmg: range=[{base_min}–{base_max}]{adroit_note}{burn_note}{spark_note} "
        f"rolled={rolled} ×mult={attack_multiplier:.4f}={int(rolled*attack_multiplier)}"
        f"{echo_note}{lucifer_note} = {damage}"
    )

    log.append(f"Hit! Damage: 💥 **{damage - echo_damage}**")
    if echo_damage:
        log.append(f"The hit is 🎶 echoed!\nEcho damage: 💥 **{echo_damage}**")
    return damage


def calc_miss_damage(
    player: Player,
    monster: Monster,
    attack_multiplier: float,
    log: list[str],
    calc: list[str],
) -> int:
    """Phase 4c — miss, any on-miss damage sources. Returns total miss damage."""
    from core.combat.calc.calcs import get_weapon_tier

    damage = 0
    miss_parts = []

    infernal = player.get_weapon_infernal()
    if infernal == "perdition" and player.equipped_weapon:
        perdition_dmg = int(player.equipped_weapon.attack * 0.75)
        if perdition_dmg > 0:
            damage += perdition_dmg
            miss_parts.append(f"**Perdition** tears through for 🔥 **{perdition_dmg}**")

    idx, _ = get_weapon_tier(player, "poison")
    if idx >= 0:
        poison_pct = (idx + 1) * 0.08
        poison_dmg = int(
            random.randint(1, int(player.get_total_attack() * poison_pct))
            * attack_multiplier
        )
        if poison_dmg > 0:
            damage += poison_dmg
            miss_parts.append(f"poison 🐍 deals **{poison_dmg}**")

    void_passive = player.get_accessory_void_passive()
    if void_passive == "oblivion":
        oblivion_dmg = int(player.get_total_attack() * 0.5 * attack_multiplier)
        damage += oblivion_dmg
        miss_parts.append(f"**Oblivion** phases through for ⬛ **{oblivion_dmg}**")

    if infernal == "voracious":
        player.voracious_stacks += 1

    if miss_parts:
        log.append("Miss! But " + ", ".join(miss_parts) + " damage.")
    else:
        log.append("Miss!")
    calc.append(
        f"  miss_dmg: {damage} (sources: {', '.join(miss_parts) if miss_parts else 'none'})"
    )
    return damage


# ---------------------------------------------------------------------------
# Damage application — monster modifiers and final HP/ward resolution
# ---------------------------------------------------------------------------


def apply_monster_damage_reduction(
    monster: Monster, damage: int, log: list[str], calc: list[str]
) -> int:
    """Phase 5 — apply monster damage-reduction modifiers."""
    pre = damage

    for prot_name in (
        "Radiant Protection",
        "Infernal Protection",
        "Balanced Protection",
        "Void Protection",
        "Corrupted Protection",
    ):
        if monster.has_modifier(prot_name) and damage > 0:
            reduction = int(damage * 0.60)
            damage = max(0, damage - reduction)
            log.append(f"✨ **{prot_name}** mitigates {reduction} damage!")
            break

    if monster.has_modifier("Ironclad") and damage > 0:
        reduction = int(damage * monster.get_modifier_value("Ironclad"))
        damage = max(0, damage - reduction)
        log.append(
            f"{monster.name}'s **Ironclad** plating reduces damage by {reduction}."
        )

    if monster.has_modifier("Stalwart") and damage > 0:
        if random.random() < monster.get_modifier_value("Stalwart"):
            log.append(f"{monster.name}'s **Stalwart** shield nullifies the attack!")
            damage = 0

    if damage != pre:
        calc.append(f"  mon_reductions: {pre} → {damage} (saved {pre - damage})")
    return damage


def apply_damage_to_monster(
    player: Player, monster: Monster, damage: int, log: list[str]
) -> int:
    """Phase 7 — apply damage to monster ward then HP, respecting Time Lord.
    Returns damage actually dealt."""
    if monster.ward > 0 and damage > 0:
        if damage <= monster.ward:
            monster.ward -= damage
            log.append(
                f"Your attack is absorbed by the monster's 🔮 ward! ({damage} absorbed)"
            )
            damage = 0
        else:
            log.append(f"You shatter the monster's 🔮 ward! ({monster.ward} absorbed)")
            damage -= monster.ward
            monster.ward = 0

    if damage >= monster.hp:
        if (
            monster.has_modifier("Time Lord")
            and random.random() < 0.80
            and monster.hp > 1
        ):
            damage = monster.hp - 1
            log.append(
                f"A fatal blow was dealt, but **{monster.name}** cheated death via **Time Lord**!"
            )
        else:
            damage = monster.hp
    monster.hp -= damage
    return damage
