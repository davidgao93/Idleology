"""
hit_calc.py — Hit chance, crit chance, and turn-resolution logic.

Testable in isolation: every public function takes plain player/monster objects
and returns a result without touching the DB or Discord.

Public API
----------
calculate_hit_chance(player, monster) -> float
calculate_monster_hit_chance(player, monster) -> float
calculate_crit_chance(player) -> float
build_attack_multiplier(player, monster, log, calc) -> tuple[float, bool]
resolve_hit(player, monster, attack_multiplier, log, calc) -> tuple[bool, float]
resolve_crit(player, monster, is_hit, log, calc) -> bool
"""

from __future__ import annotations

import random

from core.models import Monster, Player

# ---------------------------------------------------------------------------
# Hit chance constants
# ---------------------------------------------------------------------------

_HIT_BASE = 0.60
_HIT_SENSITIVITY = 0.35
_HIT_MIN = 0.20
_HIT_MAX = 0.95

_MON_HIT_BASE = 0.50
_MON_HIT_SENSITIVITY = 0.30
_MON_HIT_MIN = 0.15
_MON_HIT_MAX = 0.80


# ---------------------------------------------------------------------------
# Pure math — safe to import and call from tests with mock players/monsters
# ---------------------------------------------------------------------------


def calculate_hit_chance(player: Player, monster: Monster) -> float:
    """Player hit chance based on attack-vs-defence ratio.
    Base is sourced from the weapon's drop template (default 60% if no weapon)."""
    from core.items.essence_mechanics import compute_essence_stat_bonus

    hit_base = (
        player.equipped_weapon.hit_chance if player.equipped_weapon else _HIT_BASE
    )
    m_def = monster.effective_defence
    if m_def <= 0:
        base = _HIT_MAX
    else:
        pct_diff = (player.get_total_attack(monster) - m_def) / m_def
        base = min(max(hit_base + pct_diff * _HIT_SENSITIVITY, _HIT_MIN), _HIT_MAX)

    # Evelynn's corruption: players start with +30% hit chance at level 1 but lose
    # 1 hit chance permanently each level as her influence takes hold.  The bonus
    # tapers linearly to 0 at level 50 when the corruption window ends.
    if player.level < 50:
        rookie_bonus = 0.30 * (1.0 - (player.level - 1) / 49.0)
        base = min(_HIT_MAX, base + rookie_bonus)

    if player.ascension_unlocks:
        hit_bonus = player.get_ascension_bonuses()["hit"]
        if hit_bonus:
            base = min(_HIT_MAX, base + hit_bonus * 0.01)

    for item in (player.equipped_glove, player.equipped_boot, player.equipped_helmet):
        if item:
            hit_pct = compute_essence_stat_bonus(item).get("hit_pct", 0)
            if hit_pct:
                base = min(_HIT_MAX, base + hit_pct * 0.01)

    if player.alchemy_hit_boost_pct > 0:
        base = min(_HIT_MAX, base + player.alchemy_hit_boost_pct)

    return base


def calculate_monster_hit_chance(player: Player, monster: Monster) -> float:
    """Monster hit chance based on attack-vs-defence ratio. Equal stats → 50%."""
    m_atk = monster.effective_attack
    if m_atk <= 0:
        return _MON_HIT_MIN
    pct_diff = (m_atk - player.get_total_defence(monster)) / m_atk
    return min(
        max(_MON_HIT_BASE + pct_diff * _MON_HIT_SENSITIVITY, _MON_HIT_MIN),
        _MON_HIT_MAX,
    )


def calculate_crit_chance(player: Player) -> float:
    """Returns effective crit chance (0–100) accounting for infernal/partner sources.
    Piercing is now folded directly into player.get_current_crit_chance()."""
    chance = player.get_current_crit_chance()
    if player.get_weapon_infernal() == "voracious" and player.voracious_stacks > 0:
        chance += player.voracious_stacks * 5 * player.get_infernal_strength_mult()
    if player.active_partner:
        for key, lvl in player.active_partner.combat_skills:
            if key == "co_crit_rate":
                chance += lvl
    return chance


# ---------------------------------------------------------------------------
# Turn-level resolution phases
# ---------------------------------------------------------------------------


def build_attack_multiplier(
    player: Player, monster: Monster, log: list[str], calc: list[str]
) -> tuple[float, bool]:
    """Phase 1 — compute the pre-hit attack multiplier from emblems and passive sources.
    Returns (attack_multiplier, sigmund_proc) — sigmund_proc is surfaced for the
    partner-effects display only, the roll and its bonus are already folded into mult.
    """
    from core.combat import jewel_engine as _je

    mult = 1.0
    calc_sources: list[str] = []

    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0

    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0

    # --- Additive damage bonus pool ---
    # All percentage damage bonuses stack additively here; a single multiplier is applied.
    # Damage emblems (combat_dmg / boss_dmg / slayer_dmg), Instability, Obliterate,
    # Piety, Frenzy, Alchemy Eclipse, partner Sigmund, and Soul Stone Piety all
    # contribute to add_pool_bonus.
    # Solo results: Instability−=×0.5, Instability+=(×1.6–2.0), Obliterate=×2, Piety=×7.
    add_pool_bonus = 0.0
    add_pool_parts: list[str] = []

    # Slayer damage emblems — additive with other bonus sources
    if not monster.is_boss:
        tiers = player.get_emblem_bonus("combat_dmg")
        if tiers > 0:
            add_pool_bonus += tiers * 0.02
            add_pool_parts.append(f"combat_dmg+{int(tiers * 2)}%")
    if monster.is_boss:
        tiers = player.get_emblem_bonus("boss_dmg")
        if tiers > 0:
            add_pool_bonus += tiers * 0.05
            add_pool_parts.append(f"boss_dmg+{int(tiers * 5)}%")
    if player.active_task_species and player.active_task_species == monster.species:
        tiers = player.get_emblem_bonus("slayer_dmg")
        if tiers > 0:
            add_pool_bonus += tiers * 0.05
            add_pool_parts.append(f"slayer_dmg+{int(tiers * 5)}%")
        # hu_1 "atk" (+18% ATK vs task species) is a Bonus ATK source, not a damage
        # multiplier — it lives in Player.get_total_attack()'s pct_pool instead of
        # here, so it sums with other ATK% sources rather than compounding on top
        # of them.
        # Slayer tree hu_3 DMG bonus vs task species
        if getattr(player, "slayer_tree_nodes", {}).get("hu_3") == "dmg":
            add_pool_bonus += 0.25
            add_pool_parts.append("hu3_dmg+25%")

    # Burning (weapon passive) — permanent, always-on increased damage that
    # stacks additively with every other add_pool source (Piety, Obliterate,
    # Instability, ...) rather than a separate stat bonus.
    from core.combat.calc.calcs import get_weapon_tier

    burn_idx, _ = get_weapon_tier(player, "burning")
    if burn_idx >= 0:
        burn_bonus = (burn_idx + 1) * 0.08
        add_pool_bonus += burn_bonus
        add_pool_parts.append(f"burning+{int(burn_bonus * 100)}%")

    if glove_passive == "instability" and glove_lvl > 0:
        if random.random() < 0.5:
            add_pool_bonus -= 0.5  # −50% = ×0.5 when alone
            add_pool_parts.append("instability−")
            log.append(f"**Instability ({glove_lvl})** destabilizes! (−50% damage)")
        else:
            bonus = 0.50 + (glove_lvl * 0.10)  # +50–100% above 1× = ×1.6–2.0 alone
            add_pool_bonus += bonus
            add_pool_parts.append(f"instability+{int(bonus * 100)}%")
            log.append(
                f"**Instability ({glove_lvl})** goes wild! (+{int(bonus * 100)}% damage bonus)"
            )
    else:
        # Soul stone: instability — 1:1 tier match to glove lvl.
        _ss_instability = player.get_soul_stone_passive("instability")
        if _ss_instability:
            if random.random() < 0.5:
                add_pool_bonus -= 0.5
                add_pool_parts.append("soul_instability−")
                log.append(
                    f"**Soul Instability T{_ss_instability}** destabilizes! (−50% damage)"
                )
            else:
                bonus = 0.50 + (_ss_instability * 0.10)
                add_pool_bonus += bonus
                add_pool_parts.append(f"soul_instability+{int(bonus * 100)}%")
                log.append(
                    f"**Soul Instability T{_ss_instability}** goes wild! (+{int(bonus * 100)}% damage bonus)"
                )

    if acc_passive == "Obliterate" and random.random() <= (acc_lvl * 0.04):
        add_pool_bonus += 1.0  # +100% = ×2 when alone
        add_pool_parts.append("obliterate")
        log.append(f"**Obliterate ({acc_lvl})** activates! (+100% damage bonus)")
    elif acc_passive != "Obliterate":
        # Soul stone: obliterate — 2:1 tier mapping (matches Absorb's accessory convention).
        _ss_obliterate = player.get_soul_stone_passive("obliterate")
        if _ss_obliterate:
            _equiv_lvl = _ss_obliterate * 2
            if random.random() <= (_equiv_lvl * 0.04):
                add_pool_bonus += 1.0
                add_pool_parts.append("soul_obliterate")
                log.append(
                    f"**Soul Obliterate T{_ss_obliterate}** activates! (+100% damage bonus)"
                )

    if player.get_armor_passive() == "Piety" and random.random() < 0.10:
        add_pool_bonus += 6.0  # +600% = ×7 when alone
        add_pool_parts.append("piety")
        log.append("🙏 **Piety** blesses your strike! (+600% damage bonus!)")

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "frenzy" and helmet_lvl > 0:
        missing_pct = (1 - (player.current_hp / player.total_max_hp)) * 100
        frenzy_bonus = missing_pct * (0.005 * helmet_lvl)
        add_pool_bonus += frenzy_bonus
        add_pool_parts.append(f"frenzy{int(frenzy_bonus * 100)}%")
        log.append(
            f"**Frenzy ({helmet_lvl})** rage increases damage by {int(frenzy_bonus * 100)}%!"
        )
    else:
        # Soul stone: frenzy — 1:1 tier match to helmet lvl.
        _ss_frenzy = player.get_soul_stone_passive("frenzy")
        if _ss_frenzy:
            missing_pct = (1 - (player.current_hp / player.total_max_hp)) * 100
            frenzy_bonus = missing_pct * (0.005 * _ss_frenzy)
            add_pool_bonus += frenzy_bonus
            add_pool_parts.append(f"soul_frenzy{int(frenzy_bonus * 100)}%")
            log.append(
                f"**Soul Frenzy T{_ss_frenzy}** rage increases damage by {int(frenzy_bonus * 100)}%!"
            )

    onslaught_bonus = _je.apply_onslaught_mult(player)
    if onslaught_bonus > 0:
        add_pool_bonus += onslaught_bonus / 100
        add_pool_parts.append(f"onslaught+{onslaught_bonus:.0f}%")
        log.append(f"🔥 **Onslaught** unleashes fury! (+{onslaught_bonus:.0f}% ATK)")

    # Alchemy: Eclipse — bonus damage for the remaining guaranteed-crit potion strikes
    if player.alchemy_eclipse_strikes > 0 and player.alchemy_eclipse_bonus > 0:
        add_pool_bonus += player.alchemy_eclipse_bonus
        add_pool_parts.append(f"eclipse+{int(player.alchemy_eclipse_bonus * 100)}%")
        log.append(
            f"🌑 **Eclipse** empowers your strike! (+{int(player.alchemy_eclipse_bonus * 100)}% damage bonus)"
        )

    # Partner signature — Sigmund: chance for bonus damage
    sigmund_proc = False
    _partner = player.active_partner
    if (
        _partner
        and _partner.sig_combat_key == "sig_co_sigmund"
        and _partner.sig_combat_lvl >= 1
        and random.random() < _partner.sig_combat_lvl * 0.02
    ):
        add_pool_bonus += 1.0  # +100% = ×2 when alone
        add_pool_parts.append("sigmund")
        sigmund_proc = True

    # Soul stone: piety — 10% chance for T1=+120% → T5=+600% bonus damage multiplier
    # Conflict: skipped if Piety armor passive is equipped (rolled separately above).
    if not (player.equipped_armor and player.equipped_armor.passive == "Piety"):
        _ss_piety = player.get_soul_stone_passive("piety")
        if _ss_piety and random.random() < 0.10:
            from core.apex.data import SOUL_STONE_TIER_VALUES as _SST

            _piety_bonus = _SST["piety"][_ss_piety - 1] / 100
            add_pool_bonus += _piety_bonus
            add_pool_parts.append(f"soul_piety_T{_ss_piety}")
            log.append(
                f"✨ **Soul Piety T{_ss_piety}** — divine favour! "
                f"+{int(_piety_bonus * 100)}% bonus damage!"
            )

    if add_pool_bonus != 0:
        pool_factor = 1 + add_pool_bonus
        mult *= pool_factor
        calc_sources.append(f"add_pool[{'+'.join(add_pool_parts)}]×{pool_factor:.3f}")

    # Hematurgy ATK sources (Iron Momentum, Executioner's Rite, Soul Fracture,
    # Counterforce) are applied directly inside Player.get_total_attack()'s
    # pct_pool/bonus_pool now, not as a multiplier here — this just logs
    # Executioner's Rite's activation window since it doesn't fire elsewhere.
    if player.hematurgy_passives:
        from core.hematurgy.engine import get_executioners_rite_bonus

        er_f = get_executioners_rite_bonus(player, monster)
        if er_f > 0:
            log.append(
                f"⚔️ **Executioner's Rite** — monster below 30% HP! +{int(er_f * 100)}% ATK!"
            )

    src_str = " × ".join(calc_sources) if calc_sources else "none"
    calc.append(
        f"  mult: {src_str} → {mult:.4f}x  (base_atk={player.get_total_attack(monster)})"
    )
    return mult, sigmund_proc


def resolve_hit(
    player: Player,
    monster: Monster,
    attack_multiplier: float,
    log: list[str],
    calc: list[str],
) -> tuple[bool, float]:
    """Phase 2 — hit chance roll. Returns (is_hit, attack_multiplier)."""
    from core.combat.calc.calcs import fmt_weapon_passive, get_weapon_tier

    hit_chance = calculate_hit_chance(player, monster)
    acc_bonus = player.get_emblem_bonus("accuracy") * 2

    # Slayer tree hu_1 accuracy bonus vs task species
    if (
        getattr(player, "slayer_tree_nodes", {}).get("hu_1") == "accuracy"
        and player.active_task_species
        and player.active_task_species == monster.species
    ):
        acc_bonus += 8

    idx, name = get_weapon_tier(player, "deadeye")
    if idx >= 0:
        wep_acc = (idx + 1) * 4
        acc_bonus += wep_acc
        log.append(
            f"**{fmt_weapon_passive(name)}** boosts 🎯 accuracy by **{wep_acc}**!"
        )

    # Companion hit passive: flat accuracy bonus (1–5 per tier)
    comp_hit = player._get_companion_bonus("hit")
    if comp_hit > 0:
        acc_bonus += comp_hit

    blinding_note = ""
    if monster.has_modifier("Blinding"):
        penalty = int(monster.get_modifier_value("Blinding"))
        acc_bonus -= penalty
        blinding_note = f" -Blinding{penalty}"

    if player.chapter_hit_penalty:
        acc_bonus -= player.chapter_hit_penalty
        blinding_note += f" -ChapterHaze{player.chapter_hit_penalty}"

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
    elif acc_passive != "Lucky Strikes":
        # Soul stone: lucky strikes — 2:1 tier mapping (matches Absorb's accessory convention).
        _ss_lucky = player.get_soul_stone_passive("lucky strikes")
        if _ss_lucky:
            _equiv_lvl = _ss_lucky * 2
            if random.random() <= (_equiv_lvl * 0.10):
                attack_roll = max(attack_roll, random.randint(0, 100))
                log.append(
                    f"**Soul Lucky Strikes T{_ss_lucky}** activates! Hit chance is now 🍀 lucky!"
                )
                lucky_note = "(lucky)"

    jinxed_note = ""
    if monster.has_modifier("Jinxed") and random.random() < monster.get_modifier_value(
        "Jinxed"
    ):
        attack_roll = min(attack_roll, random.randint(0, 100))
        log.append(
            "The **Jinxed** curse stifles your attack! Hit chance is now 💀 unlucky!"
        )
        jinxed_note = "(jinxed-unlucky)"

    miss_threshold = 100 - int(hit_chance * 100)
    is_hit = (attack_multiplier > 0) and ((attack_roll + acc_bonus) >= miss_threshold)

    bottled_note = ""
    if not is_hit and player.alchemy_guaranteed_hit and attack_multiplier > 0:
        is_hit = True
        player.alchemy_guaranteed_hit = False
        log.append("⚔️ **Bottled Courage** forces the hit!")
        bottled_note = " [bottled_courage]"

    outcome = "HIT" if is_hit else "MISS"
    calc.append(
        f"  hit: chance={hit_chance * 100:.1f}%{blinding_note} → threshold={miss_threshold} | "
        f"roll={attack_roll}{lucky_note}{jinxed_note}+acc={acc_bonus}={attack_roll + acc_bonus}"
        f"{bottled_note} → {outcome}"
    )
    return is_hit, attack_multiplier


def resolve_crit(
    player: Player, monster: Monster, is_hit: bool, log: list[str], calc: list[str]
) -> bool:
    """Phase 3 — crit check. Rolls 0-100; result must exceed (100 - crit_chance)."""
    if not is_hit:
        calc.append("  crit: skipped (miss)")
        return False

    crit_chance = calculate_crit_chance(player)

    # Slayer tree hu_1 crit bonus vs task species
    if (
        getattr(player, "slayer_tree_nodes", {}).get("hu_1") == "crit"
        and player.active_task_species
        and player.active_task_species == monster.species
    ):
        crit_chance += 8

    if monster.has_modifier("Dampening"):
        crit_chance = max(0, crit_chance - monster.get_modifier_value("Dampening"))

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
