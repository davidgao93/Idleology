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


_DIFFICULTY_SURPLUS_MULT = [1.0, 1.2, 1.3, 1.4, 1.5]
# Flat crit chance added to base monster crit per difficulty tier (all sources sum together).
_DIFFICULTY_CRIT_CHANCE = [0.0, 0.15, 0.20, 0.30, 0.50]


def calculate_damage_taken(player: Player, monster: Monster) -> int:
    """Raw monster damage before PDR/FDR.
    Guaranteed base from monster level, amplified/dampened by stat surplus.
    Difficulty mode scales the surplus multiplier (Hard ×1.2 … Delirious ×1.5)."""
    p_def = max(player.get_total_defence(), 1)
    base_raw = 5 + monster.level * 1.5
    surplus = (monster.attack - p_def) / p_def
    surplus = max(-0.95, surplus)
    surplus_mult = _DIFFICULTY_SURPLUS_MULT[monster.difficulty_level]
    raw = base_raw * (1.0 + surplus * surplus_mult)
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
) -> tuple[int, int, int, int]:
    """Rolls a single monster damage hit including modifiers, PDR, FDR, and minions.
    Returns (total_damage, pre_reduction_damage, base_damage, minion_damage).
    pre_reduction_damage = raw damage after all monster modifiers but BEFORE player PDR/FDR.
    Used by Thorns to reflect the true incoming hit rather than the post-mitigation value."""
    m_atk = monster.attack
    p_def = max(player.get_total_defence(), 1)
    base_raw = 5 + monster.level * 1.5
    surplus = max(-0.95, (m_atk - p_def) / p_def)
    surplus_mult = _DIFFICULTY_SURPLUS_MULT[monster.difficulty_level]
    dmg = calculate_damage_taken(player, monster)

    diff_note = f" surplus_mult=×{surplus_mult}" if monster.difficulty_level > 0 else ""
    calc_notes: list[str] = [
        f"m_atk={m_atk} p_def={p_def} base={base_raw:.0f} surplus={surplus:+.3f}{diff_note} → raw≈{int(base_raw*(1+surplus*surplus_mult))} rolled={dmg}"
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
    # Volatile Spikes: each spike stack adds v to monster crit chance
    if monster.has_modifier("Volatile Spikes") and monster.spike_stacks > 0:
        spikes_bonus = monster.spike_stacks * monster.get_modifier_value("Volatile Spikes")
        base_crit_chance += spikes_bonus
        calc_notes.append(f"volatile_spikes crit+{spikes_bonus:.3f}")
    # Difficulty: flat bonus to crit chance (all sources sum together)
    if monster.difficulty_level > 0:
        diff_crit = _DIFFICULTY_CRIT_CHANCE[monster.difficulty_level]
        base_crit_chance += diff_crit
        calc_notes.append(f"difficulty_crit+{diff_crit*100:.0f}%")
    crit_roll = random.random()
    is_monster_crit = crit_roll < base_crit_chance
    calc_notes.append(f"mon_crit: {base_crit_chance*100:.1f}% roll={crit_roll:.4f} → {'CRIT' if is_monster_crit else 'no crit'}")
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

    # --- Apex zone: Scorched damage boost (+20% on monster hits) ---
    zone_boost = getattr(monster, "zone_dmg_boost", 0.0)
    if zone_boost > 0 and dmg > 0:
        pre_boost = dmg
        dmg = int(dmg * (1.0 + zone_boost))
        calc_notes.append(f"scorched_zone+{int(zone_boost*100)}% {pre_boost}→{dmg}")

    if calc is not None:
        calc.append(
            "  dmg_roll: "
            + " → ".join(calc_notes)
            + f" | pre_pdr={pre_pdr} base={dmg} minions={minions} total={dmg+minions}"
        )

    return dmg + minions, pre_pdr, dmg, minions


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
    """Phase 4a — crit damage. Returns pre-reduction damage.

    Crits use the same roll range as normal hits (Burning ceiling, Shocking floor),
    then multiply the rolled value by the crit multiplier.
    Adroit does NOT apply to crits — it is a Normal Hit Floor only.
    Deftness applies only to crits, raising the crit roll floor by lvl×5% of ceiling.
    Cursed Precision: roll the range twice, take the worse result, then multiply.
    """
    from core.combat import jewel_engine as _je
    from core.combat.calc.calcs import fmt_weapon_passive, get_weapon_tier

    base_max = player.get_total_attack()
    base_min = 1
    calc_dmg_notes: list[str] = [f"base_atk={base_max}"]

    # Burning: raises the ceiling (same as hit damage)
    burn_idx, burn_name = get_weapon_tier(player, "burning")
    if burn_idx >= 0:
        burn_bonus = int(base_max * (burn_idx + 1) * 0.08)
        base_max += burn_bonus
        calc_dmg_notes.append(f"burn+{burn_bonus}={base_max}")
        log.append(
            f"**{fmt_weapon_passive(burn_name)}** 🔥 burns bright!\n"
            f"Attack damage potential boosted by **{burn_bonus}**."
        )

    # Shocking: raises the roll floor (same as hit damage)
    shock_idx, shock_name = get_weapon_tier(player, "shocking")
    if shock_idx >= 0:
        shock_min = int(base_max * (shock_idx + 1) * 0.08)
        base_min = max(base_min, shock_min)
        calc_dmg_notes.append(f"shock_min={base_min}")
        log.append(
            f"**{fmt_weapon_passive(shock_name)}** surges with ⚡ lightning, ensuring solid impact!"
        )

    # Deftness: crit-exclusive roll floor (complement to Adroit for normal hits)
    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "deftness" and glove_lvl > 0:
        deft_min = int(base_max * (glove_lvl * 0.05))
        base_min = max(base_min, deft_min)
        calc_dmg_notes.append(f"deft_min={base_min}")
        log.append(f"**Deftness ({glove_lvl})** steadies your critical strike!")

    crit_mult = player.get_weapon_crit_multi()
    if monster.has_modifier("Nullifying"):
        null_val = monster.get_modifier_value("Nullifying")
        crit_mult = player.get_weapon_crit_multi() * (1 - null_val)
        log.append(f"The **Nullifying** aura dampens your critical hit! (×{crit_mult:.2f})")
        calc_dmg_notes.append(f"nullifying×{crit_mult:.2f}")

    if player.chapter_crit_dmg_reduction > 0:
        crit_mult *= (1 - player.chapter_crit_dmg_reduction)
        calc_dmg_notes.append(f"chapter_dull×{crit_mult:.2f}")

    # Roll within the crit range, then multiply by crit_mult.
    # Cursed Precision: roll the range twice, take the worse result.
    safe_min = min(base_min, base_max)
    if player.cursed_precision_active:
        roll_a = random.randint(safe_min, base_max)
        roll_b = random.randint(safe_min, base_max)
        cp_roll = min(roll_a, roll_b)
        base_dmg = int(cp_roll * crit_mult)
        calc_dmg_notes.append(
            f"cursed_precision range=[{safe_min}–{base_max}] rolls=({roll_a},{roll_b}) worst={cp_roll} ×{crit_mult:.2f}={base_dmg}"
        )
        log.append("**Cursed Precision** — the weaker roll applies!")
    else:
        rolled = random.randint(safe_min, base_max)
        base_dmg = int(rolled * crit_mult)
        calc_dmg_notes.append(f"range=[{safe_min}–{base_max}] rolled={rolled} ×{crit_mult:.2f}={base_dmg}")

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
        second_pct = random.uniform(0.20, 0.40)
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

    # Burning raises the damage ceiling first — floor passives must see the true maximum
    burn_note = ""
    idx, name = get_weapon_tier(player, "burning")
    if idx >= 0:
        bonus = int(player.get_total_attack() * ((idx + 1) * 0.08))
        base_max += bonus
        burn_note = f" burn+{bonus}"
        log.append(
            f"**{fmt_weapon_passive(name)}** 🔥 burns bright!\nAttack damage potential boosted by **{bonus}**."
        )

    # Floor: Adroit + Shocking stack ADDITIVELY against the post-Burning base_max.
    # Both percentages are summed, then applied once as a single floor.
    floor_pct = 0.0
    floor_parts: list[str] = []

    if glove_passive == "adroit" and glove_lvl > 0:
        floor_pct += glove_lvl * 0.02
        floor_parts.append(f"adroit{glove_lvl * 2}%")
        log.append(f"**Adroit ({glove_lvl})** sharpens your technique!")

    shock_idx, shock_name = get_weapon_tier(player, "shocking")
    if shock_idx >= 0:
        floor_pct += (shock_idx + 1) * 0.08
        floor_parts.append(f"shocking{int((shock_idx + 1) * 8)}%")
        log.append(
            f"**{fmt_weapon_passive(shock_name)}** surges with ⚡ lightning, ensuring solid impact!"
        )

    floor_note = ""
    if floor_pct > 0:
        base_min = max(1, int(base_max * floor_pct))
        floor_note = f" floor_min={base_min}({'+'.join(floor_parts)}={int(floor_pct*100)}%)"

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
        f"  hit_dmg: range=[{base_min}–{base_max}]{burn_note}{floor_note} "
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
        oblivion_dmg = int(player.get_total_attack() * 0.5)
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
    """Phase 5 — apply monster damage-reduction modifiers.

    Two independent layers applied in order:

    Layer 1 — Regular DR (additive pool, hard cap 80%):
      Sources: Ironclad modifier, Colossus Protocol (colossus_dr field).
      All percentages sum first, then the combined rate is capped at 80% and
      applied once.  This prevents compounding between sources and ensures a
      hard ceiling even if both are maxed simultaneously.

    Stalwart — chance-based full nullification, checked after Layer 1.

    Layer 2 — Uber Protection (multiplicative, applied after Layer 1):
      Sources: Radiant / Infernal / Balanced / Void / Corrupted Protection.
      Treated as a separate multiplicative layer so it cannot be diluted by
      regular DR stacking.  At most one Protection modifier fires (break).

    Example with Ironclad T5 (30%) + Colossus (15%) + Radiant Protection:
      1000 × (1 − 0.45) = 550  →  550 × (1 − 0.60) = 220 final damage.
    """
    pre = damage

    # --- Layer 1: Regular DR (additive pool, hard cap 80%) ---
    regular_dr = 0.0
    dr_labels: list[str] = []

    if monster.has_modifier("Ironclad"):
        v = monster.get_modifier_value("Ironclad")
        regular_dr += v
        dr_labels.append(f"Ironclad {int(v * 100)}%")

    if getattr(monster, "colossus_dr", 0.0) > 0:
        regular_dr += monster.colossus_dr
        dr_labels.append(f"Colossus {int(monster.colossus_dr * 100)}%")

    # Apex zone: Siege Grounds adds DR against player hits
    _zone_dr = getattr(monster, "zone_dr", 0.0)
    if _zone_dr > 0:
        regular_dr += _zone_dr
        dr_labels.append(f"Siege Grounds {int(_zone_dr * 100)}%")

    # Difficulty DR: Nightmarish (+10%) and Delirious (+25%)
    _diff_dr = getattr(monster, "difficulty_dr", 0.0)
    if _diff_dr > 0:
        regular_dr += _diff_dr
        dr_labels.append(f"Difficulty {int(_diff_dr * 100)}%")

    if regular_dr > 0 and damage > 0:
        capped_dr = min(0.80, regular_dr)
        reduction = int(damage * capped_dr)
        damage = max(0, damage - reduction)
        cap_note = " *(capped at 80%)*" if regular_dr > 0.80 else ""
        source = " + ".join(dr_labels)
        log.append(
            f"{monster.name}'s **DR** ({source}{cap_note}) blocks **{reduction}** damage."
        )
        calc.append(
            f"  regular_dr: {source} = {int(regular_dr * 100)}%"
            f" → applied {int(capped_dr * 100)}%: {pre}→{damage}"
        )

    # --- Stalwart: chance-based full nullification ---
    if monster.has_modifier("Stalwart") and damage > 0:
        if random.random() < monster.get_modifier_value("Stalwart"):
            log.append(f"{monster.name}'s **Stalwart** shield nullifies the attack!")
            damage = 0

    # --- Layer 2: Uber Protection (multiplicative, after regular DR) ---
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
