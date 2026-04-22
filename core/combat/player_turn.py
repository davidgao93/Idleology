import random

from core.combat.calcs import calculate_hit_chance, get_weapon_tier
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
    if player.equipped_boot and player.equipped_boot.passive == "cleric":
        heal_pct += player.equipped_boot.passive_lvl * 0.10

    potion_passives_by_type = {
        p["passive_type"]: p["passive_value"] for p in player.potion_passives
    }

    # --- Alchemy: Fermented Brew (bonus heal %) ---
    fermented = potion_passives_by_type.get("fermented_brew", 0)
    if fermented:
        heal_pct += fermented / 100.0

    heal_amount = int((player.total_max_hp * heal_pct) + random.randint(1, 6))

    # --- Alchemy: Unstable Mixture (50% double / 50% halve) ---
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

    # --- Overcap Brew: can we store overheal as temp HP? ---
    overcap = potion_passives_by_type.get("overcap_brew", 0)
    overcap_cap = int(player.total_max_hp * (overcap / 100.0)) if overcap else 0

    potential_hp = player.current_hp + heal_amount
    overheal = 0
    if potential_hp > player.total_max_hp:
        excess = potential_hp - player.total_max_hp
        helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        overheal = excess * helmet_lvl  # Divine helmet

        if overcap_cap > 0:
            stored = min(excess, overcap_cap)
            player.alchemy_overcap_hp = stored
        player.current_hp = player.total_max_hp
    else:
        player.current_hp = potential_hp

    player.potions -= 1

    msg = f"{player.name} uses a potion and heals for **{heal_amount - overheal}** HP!"
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

    # --- Alchemy: Ward Infusion (% of heal amount as Ward) ---
    ward_inf = potion_passives_by_type.get("ward_infusion", 0)
    if ward_inf:
        ward_gain = int(heal_amount * (ward_inf / 100.0))
        added = _add_ward(player, ward_gain, [], "Ward Infusion")
        msg += f"\n🔮 **Ward Infusion** generates **{added}** Ward!"

    # --- Alchemy: Lingering Remedy ---
    linger = potion_passives_by_type.get("lingering_remedy", 0)
    if linger:
        player.alchemy_linger_hp = int(linger)
        player.alchemy_linger_turns = 3
        msg += f"\n🌿 **Lingering Remedy** — +{player.alchemy_linger_hp} HP/turn for 3 turns!"

    # --- Alchemy: Bottled Courage ---
    if potion_passives_by_type.get("bottled_courage"):
        player.alchemy_guaranteed_hit = True
        msg += "\n⚔️ **Bottled Courage** — your next attack cannot miss!"

    # --- Alchemy: Warrior's Draft (next attack only) ---
    draft = potion_passives_by_type.get("warriors_draft", 0)
    if draft:
        player.alchemy_atk_boost_pct = draft / 100.0
        msg += f"\n💪 **Warrior's Draft** — +{draft:.0f}% ATK on next attack!"

    # --- Alchemy: Iron Skin (+DEF for 2 monster turns) ---
    iron = potion_passives_by_type.get("iron_skin", 0)
    if iron:
        player.alchemy_def_boost_pct = iron / 100.0
        player.alchemy_def_boost_turns = 2
        msg += f"\n🛡️ **Iron Skin** — +{iron:.0f}% DEF for 2 monster turns!"

    # --- Alchemy: Dulled Pain (next monster attack) ---
    dulled = potion_passives_by_type.get("dulled_pain", 0)
    if dulled:
        player.alchemy_dmg_reduction_pct = dulled / 100.0
        player.alchemy_dmg_reduction_turns = 1
        msg += f"\n🩹 **Dulled Pain** — -{dulled:.0f}% damage from next monster attack!"

    # --- Alchemy: Venom Cure (deal N× heal as damage) ---
    venom_mult = potion_passives_by_type.get("venom_cure", 0)
    if venom_mult and monster is not None and monster.hp > 0:
        venom_dmg = int(heal_amount * venom_mult)
        monster.hp = max(0, monster.hp - venom_dmg)
        msg += (
            f"\n🐍 **Venom Cure** courses through the enemy for **{venom_dmg}** damage!"
        )

    msg += f"\n**{player.potions}** potions left."
    return msg


# ---------------------------------------------------------------------------
# Player Turn — Phase Helpers
# ---------------------------------------------------------------------------


def _pt_attack_multiplier(player: Player, monster: Monster, log: list[str], calc: list[str]) -> float:
    """Phase 1 — compute the pre-hit attack multiplier from emblems and passive sources."""
    mult = 1.0
    calc_sources: list[str] = []

    if not monster.is_boss:
        tiers = player.get_emblem_bonus("combat_dmg")
        if tiers > 0:
            factor = 1 + tiers * 0.02
            mult *= factor
            calc_sources.append(f"combat_dmg_emblem×{factor:.3f}")
    if monster.is_boss:
        tiers = player.get_emblem_bonus("boss_dmg")
        if tiers > 0:
            factor = 1 + tiers * 0.05
            mult *= factor
            calc_sources.append(f"boss_dmg_emblem×{factor:.3f}")
    if player.active_task_species == monster.species:
        tiers = player.get_emblem_bonus("slayer_dmg")
        if tiers > 0:
            factor = 1 + tiers * 0.05
            mult *= factor
            calc_sources.append(f"slayer_emblem×{factor:.3f}")

    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "instability" and glove_lvl > 0:
        if random.random() < 0.5:
            mult *= 0.5
            calc_sources.append("instability×0.500")
        else:
            factor = 1.50 + (glove_lvl * 0.10)
            mult *= factor
            calc_sources.append(f"instability×{factor:.3f}")
        log.append(
            f"**Instability ({glove_lvl})** gives you {int(mult * 100)}% damage."
        )

    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0
    if acc_passive == "Obliterate" and random.random() <= (acc_lvl * 0.02):
        log.append(f"**Obliterate ({acc_lvl})** activates, doubling 💥 damage dealt!")
        mult *= 2.0
        calc_sources.append("obliterate×2.000")

    if player.get_armor_passive() == "Mystical Might" and random.random() < 0.2:
        mult *= 10.0
        calc_sources.append("mystical_might×10.000")
        log.append(
            "The **Mystical Might** armor imbues with power, massively increasing damage!"
        )

    # --- Alchemy: Warrior's Draft (one-shot, reset after this attack) ---
    if player.alchemy_atk_boost_pct > 0:
        factor = 1 + player.alchemy_atk_boost_pct
        mult *= factor
        calc_sources.append(f"warriors_draft×{factor:.3f}")
        log.append(
            f"💪 **Warrior's Draft** boosts damage! (+{int(player.alchemy_atk_boost_pct * 100)}% ATK)"
        )
        player.alchemy_atk_boost_pct = 0.0

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "frenzy" and helmet_lvl > 0:
        missing_pct = (1 - (player.current_hp / player.total_max_hp)) * 100
        bonus = missing_pct * (0.005 * helmet_lvl)
        factor = 1 + bonus
        mult *= factor
        calc_sources.append(f"frenzy×{factor:.3f}({missing_pct:.1f}%missing)")
        log.append(
            f"**Frenzy ({helmet_lvl})** rage increases damage by {int(bonus * 100)}%!"
        )

    src_str = " × ".join(calc_sources) if calc_sources else "none"
    calc.append(f"  mult: {src_str} → {mult:.4f}x  (base_atk={player.get_total_attack()})")
    return mult


def _pt_resolve_hit(
    player: Player, monster: Monster, attack_multiplier: float, log: list[str], calc: list[str]
) -> tuple[bool, float]:
    """Phase 2 — hit chance roll. Returns (is_hit, attack_multiplier)."""
    hit_chance = calculate_hit_chance(player, monster)
    dodgy_note = ""
    if "Dodgy" in monster.modifiers:
        hit_chance = max(0.05, hit_chance - 0.10)
        log.append("The monster's **Dodgy** nature makes it harder to hit!")
        dodgy_note = " -10%(Dodgy)"

    acc_bonus = player.get_emblem_bonus("accuracy") * 2

    idx, name = get_weapon_tier(player, "accuracy")
    if idx >= 0:
        wep_acc = (idx + 1) * 4
        acc_bonus += wep_acc
        log.append(f"The **{name}** weapon boosts 🎯 accuracy roll by **{wep_acc}**!")

    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0
    attack_roll = random.randint(0, 100)
    lucky_note = ""

    if acc_passive == "Lucky Strikes" and random.random() <= (acc_lvl * 0.10):
        attack_roll = max(attack_roll, random.randint(0, 100))
        log.append(
            f"**Lucky Strikes ({acc_lvl})** activates! Hit chance is now 🍀 lucky!"
        )
        lucky_note = "(lucky)"

    suffocator_note = ""
    if "Suffocator" in monster.modifiers and random.random() < 0.2:
        log.append(
            f"The {monster.name}'s **Suffocator** aura stifles your attack! Hit chance is now 💀 unlucky!"
        )
        attack_roll = min(attack_roll, random.randint(0, 100))
        suffocator_note = "(unlucky)"

    shields_note = ""
    if "Shields-up" in monster.modifiers and random.random() < 0.1:
        attack_multiplier = 0
        log.append(f"{monster.name} projects a magical barrier, nullifying the hit!")
        shields_note = " [shields-up nullified]"

    miss_threshold = 100 - int(hit_chance * 100)
    is_hit = (attack_multiplier > 0) and ((attack_roll + acc_bonus) >= miss_threshold)

    # --- Alchemy: Bottled Courage (guaranteed hit override) ---
    bottled_note = ""
    if not is_hit and player.alchemy_guaranteed_hit and attack_multiplier > 0:
        is_hit = True
        player.alchemy_guaranteed_hit = False
        log.append("⚔️ **Bottled Courage** forces the hit!")
        bottled_note = " [bottled_courage]"

    outcome = "HIT" if is_hit else "MISS"
    calc.append(
        f"  hit: chance={hit_chance*100:.1f}%{dodgy_note} → threshold={miss_threshold} | "
        f"roll={attack_roll}{lucky_note}{suffocator_note}+acc={acc_bonus}={attack_roll+acc_bonus}"
        f"{shields_note}{bottled_note} → {outcome}"
    )
    return is_hit, attack_multiplier


def _pt_resolve_crit(
    player: Player, monster: Monster, is_hit: bool, log: list[str], calc: list[str]
) -> bool:
    """Phase 3 — crit check. Rolls 0-100; result must exceed (100 - crit_chance)."""
    if not is_hit:
        calc.append("  crit: skipped (miss)")
        return False

    from core.combat.calcs import calculate_crit_chance
    crit_chance = calculate_crit_chance(player)

    if crit_chance >= 100:
        calc.append(f"  crit: chance={crit_chance:.1f}% → guaranteed CRIT")
        return True

    crit_roll = random.randint(0, 100)
    crit_threshold = 100 - crit_chance
    is_crit = crit_roll > crit_threshold
    calc.append(
        f"  crit: chance={crit_chance:.1f}% → threshold={crit_threshold:.1f} | "
        f"roll={crit_roll} → {'CRIT' if is_crit else 'NORMAL HIT'}"
    )
    return is_crit


def _pt_crit_damage(
    player: Player, monster: Monster, attack_multiplier: float, log: list[str], calc: list[str]
) -> int:
    """Phase 4a — crit damage. Returns pre-reduction damage."""
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
    base_dmg = int(crit_rolled * 2.0)
    calc_dmg_notes: list[str] = [
        f"range=[{crit_min}–{crit_max}] rolled={crit_rolled} ×2.0={base_dmg}"
    ]

    crit_dmg_tiers = player.get_emblem_bonus("crit_dmg")
    if crit_dmg_tiers > 0:
        factor = 1 + crit_dmg_tiers * 0.05
        base_dmg = int(base_dmg * factor)
        calc_dmg_notes.append(f"crit_dmg_emblem×{factor:.3f}={base_dmg}")

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "insight" and helmet_lvl > 0:
        extra = helmet_lvl * 0.1
        base_dmg = int(base_dmg * (1 + extra))
        calc_dmg_notes.append(f"insight×{1+extra:.3f}={base_dmg}")
        log.append(
            f"**Insight ({helmet_lvl})** exposes a weak point! (Crit Dmg +{int(extra * 100)}%)"
        )

    if "Smothering" in monster.modifiers:
        base_dmg = int(base_dmg * 0.80)
        calc_dmg_notes.append(f"smothering×0.800={base_dmg}")
        log.append("The monster's **Smothering** aura dampens your critical hit!")

    if player.cursed_precision_active:
        alt = int(random.randint(crit_min, crit_max) * 2.0)
        if alt < base_dmg:
            base_dmg = alt
            calc_dmg_notes.append(f"cursed_precision(alt={alt})={base_dmg}")
        log.append("**Cursed Precision** — the weaker roll applies!")

    damage = int(base_dmg * attack_multiplier)
    calc_dmg_notes.append(f"×mult={attack_multiplier:.4f}={damage}")

    infernal = player.get_weapon_infernal()
    if infernal == "last_rites" and monster.hp > 0:
        bonus = int(monster.hp * 0.10)
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

    # Lucifer glove: bonus flat damage equal to 15% of current ward
    if player.get_glove_corrupted_essence() == "lucifer" and player.combat_ward > 0:
        ward_bonus = int(player.combat_ward * 0.15)
        if ward_bonus > 0:
            damage += ward_bonus
            calc_dmg_notes.append(f"+lucifer_ward={ward_bonus}")
            log.append(f"🔥 **Soul Burn** — ward fuels the crit! (+{ward_bonus})")

    # Gemini glove: second strike at 40-60% of crit damage
    if player.get_glove_corrupted_essence() == "gemini":
        second_pct = random.uniform(0.40, 0.60)
        second_hit = int(damage * second_pct)
        if second_hit > 0:
            damage += second_hit
            calc_dmg_notes.append(f"+gemini_twin={second_hit}({second_pct:.0%})")
            log.append(f"⚖️ **Twin Strike** — a second blow lands! (+{second_hit})")

    calc.append("  crit_dmg: " + " → ".join(calc_dmg_notes) + f" = {damage}")

    idx, _ = get_weapon_tier(player, "crit")
    if idx >= 0:
        log.append("The weapon glimmers with power!")
    log.append(f"Critical Hit! Damage: 🗡️ **{damage}**")
    return damage


def _pt_hit_damage(
    player: Player, monster: Monster, attack_multiplier: float, log: list[str], calc: list[str]
) -> int:
    """Phase 4b — normal hit damage. Returns pre-reduction damage."""
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
    idx, name = get_weapon_tier(player, "burn")
    if idx >= 0:
        bonus = int(player.get_total_attack() * ((idx + 1) * 0.08))
        base_max += bonus
        burn_note = f" burn+{bonus}"
        log.append(
            f"The **{name}** weapon 🔥 burns bright!\nAttack damage potential boosted by **{bonus}**."
        )

    spark_note = ""
    idx, name = get_weapon_tier(player, "spark")
    if idx >= 0:
        base_min = max(base_min, int(base_max * ((idx + 1) * 0.08)))
        spark_note = f" spark_min={base_min}"
        log.append(
            f"The **{name}** weapon surges with ⚡ lightning, ensuring solid impact!"
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
    # Lucifer glove: bonus flat damage equal to 15% of current ward
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


def _pt_miss_damage(
    player: Player, monster: Monster, attack_multiplier: float, log: list[str], calc: list[str]
) -> int:
    """Phase 4c — miss, any on-miss damage sources. Returns total miss damage."""
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
        glove_p = player.get_glove_passive()
        glove_l = player.equipped_glove.passive_lvl if player.equipped_glove else 0
        base_max = player.get_total_attack()
        base_min = (
            max(1, int(base_max * (glove_l * 0.02)))
            if glove_p == "adroit" and glove_l > 0
            else 1
        )
        oblivion_dmg = max(1, int(base_min * 0.5))
        damage += oblivion_dmg
        miss_parts.append(f"**Oblivion** phases through for ⬛ **{oblivion_dmg}**")

    if infernal == "voracious":
        player.voracious_stacks += 1

    if miss_parts:
        log.append("Miss! But " + ", ".join(miss_parts) + " damage.")
    else:
        log.append("Miss!")
    calc.append(f"  miss_dmg: {damage} (sources: {', '.join(miss_parts) if miss_parts else 'none'})")
    return damage


def _pt_apply_reductions(monster: Monster, damage: int, log: list[str], calc: list[str]) -> int:
    """Phase 5 — apply monster damage-reduction modifiers."""
    pre = damage
    if "Radiant Protection" in monster.modifiers and damage > 0:
        reduction = int(damage * 0.60)
        damage = max(0, damage - reduction)
        log.append(f"✨ **Radiant Protection** mitigates {reduction} damage!")

    if "Titanium" in monster.modifiers and damage > 0:
        reduction = int(damage * 0.10)
        damage = max(0, damage - reduction)
        log.append(
            f"{monster.name}'s **Titanium** plating reduces damage by {reduction}."
        )

    if damage != pre:
        calc.append(f"  mon_reductions: {pre} → {damage} (saved {pre - damage})")
    return damage


def _pt_generate_ward(
    player: Player, raw_damage: int, is_crit: bool, log: list[str]
) -> None:
    """Phase 6 — glove ward generation on hit (uses pre-reduction damage)."""
    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0

    if (
        not is_crit
        and glove_passive == "ward-touched"
        and glove_lvl > 0
        and raw_damage > 0
    ):
        ward = int(raw_damage * (glove_lvl * 0.01))
        if ward > 0:
            added = _add_ward(player, ward, log)
            log.append(f"**Ward-Touched ({glove_lvl})** generates 🔮 **{added}** ward!")

    if is_crit and glove_passive == "ward-fused" and glove_lvl > 0 and raw_damage > 0:
        ward = int(raw_damage * (glove_lvl * 0.02))
        if ward > 0:
            added = _add_ward(player, ward, log)
            log.append(f"**Ward-Fused ({glove_lvl})** generates 🔮 **{added}** ward!")


def _pt_apply_to_monster(
    player: Player, monster: Monster, damage: int, log: list[str]
) -> int:
    """Phase 7 — apply damage to monster HP, respecting Time Lord. Returns damage actually dealt."""
    if damage >= monster.hp:
        if (
            "Time Lord" in monster.modifiers
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

    if is_crit:
        bloodthirst_pct = player.get_tome_bonus("bloodthirst")
        if bloodthirst_pct > 0:
            heal = max(1, int(damage * (bloodthirst_pct / 100)))
            player.current_hp = min(player.total_max_hp, player.current_hp + heal)
            log.append(
                f"**Bloodthirst** siphons **{heal}** HP from the critical strike."
            )

    if player.get_celestial_armor_passive() == "celestial_ghostreaver":
        regen = random.randint(50, 200)
        added = _add_ward(player, regen, log)
        log.append(f"✨ **Celestial Ghostreaver** restores **{added}** 🔮 Ward!")


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


def _pt_check_cull(player: Player, monster: Monster, log: list[str]) -> None:
    """Phase 10 — culling strike: if monster HP is below threshold, reduce to 1."""
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


def process_player_turn(player: Player, monster: Monster) -> PlayerTurnResult:
    """Executes the player's turn, applying damage to the monster and returning the combat log."""
    log: list[str] = []
    calc: list[str] = []

    # --- Alchemy: Lingering Remedy (tick at start of player's turn) ---
    if player.alchemy_linger_turns > 0:
        player.current_hp = min(
            player.total_max_hp, player.current_hp + player.alchemy_linger_hp
        )
        log.append(
            f"🌿 **Lingering Remedy** restores **{player.alchemy_linger_hp}** HP! "
            f"({player.alchemy_linger_turns - 1} turn{'s' if player.alchemy_linger_turns - 1 != 1 else ''} left)"
        )
        player.alchemy_linger_turns -= 1

    attack_multiplier = _pt_attack_multiplier(player, monster, log, calc)
    is_hit, attack_multiplier = _pt_resolve_hit(player, monster, attack_multiplier, log, calc)
    is_crit = _pt_resolve_crit(player, monster, is_hit, log, calc)

    # NEET glove: all normal hits are treated as misses; crits are unaffected
    if is_hit and not is_crit and player.get_glove_corrupted_essence() == "neet":
        is_hit = False
        calc.append("  neet: hit converted to miss")
        log.append("🌑 **Void Form** — the strike phases through as nothingness!")

    if is_crit:
        raw_damage = _pt_crit_damage(player, monster, attack_multiplier, log, calc)
    elif is_hit:
        raw_damage = _pt_hit_damage(player, monster, attack_multiplier, log, calc)
    else:
        raw_damage = _pt_miss_damage(player, monster, attack_multiplier, log, calc)

    actual_damage = _pt_apply_reductions(monster, raw_damage, log, calc)
    _pt_generate_ward(player, raw_damage, is_crit, log)
    final_hit = _pt_apply_to_monster(player, monster, actual_damage, log)
    _pt_post_hit_effects(player, monster, final_hit, is_crit, log)
    _pt_track_pending(player, final_hit, log)
    _pt_check_cull(player, monster, log)
    calc.append(f"  final_dealt: {final_hit}  monster_hp_remaining: {monster.hp}/{monster.max_hp}")

    return PlayerTurnResult(
        log="\n".join(log),
        damage=final_hit,
        is_hit=is_hit,
        is_crit=is_crit,
        calc_detail="\n".join(calc),
    )
