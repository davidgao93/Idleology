"""
hit_calc.py — Hit chance, crit chance, and turn-resolution logic.

Testable in isolation: every public function takes plain player/monster objects
and returns a result without touching the DB or Discord.

Public API
----------
calculate_hit_chance(player, monster) -> float
calculate_monster_hit_chance(player, monster) -> float
calculate_crit_chance(player) -> float
build_attack_multiplier(player, monster, log, calc) -> float
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
    m_def = monster.defence
    if m_def <= 0:
        base = _HIT_MAX
    else:
        pct_diff = (player.get_total_attack() - m_def) / m_def
        base = min(max(hit_base + pct_diff * _HIT_SENSITIVITY, _HIT_MIN), _HIT_MAX)

    if player.ascension_unlocks:
        hit_bonus = player.get_ascension_bonuses()["hit"]
        if hit_bonus:
            base = min(_HIT_MAX, base + hit_bonus * 0.01)

    for item in (player.equipped_glove, player.equipped_boot, player.equipped_helmet):
        if item:
            hit_pct = compute_essence_stat_bonus(item).get("hit_pct", 0)
            if hit_pct:
                base = min(_HIT_MAX, base + hit_pct * 0.01)

    return base


def calculate_monster_hit_chance(player: Player, monster: Monster) -> float:
    """Monster hit chance based on attack-vs-defence ratio. Equal stats → 50%."""
    m_atk = monster.attack
    if m_atk <= 0:
        return _MON_HIT_MIN
    pct_diff = (m_atk - player.get_total_defence()) / m_atk
    return min(
        max(_MON_HIT_BASE + pct_diff * _MON_HIT_SENSITIVITY, _MON_HIT_MIN),
        _MON_HIT_MAX,
    )


def calculate_crit_chance(player: Player) -> float:
    """Returns effective crit chance (0–100) accounting for weapon tier and infernal."""
    from core.combat.calcs import get_weapon_tier

    idx, _ = get_weapon_tier(player, "piercing")
    chance = player.get_current_crit_chance() + ((idx + 1) * 5 if idx >= 0 else 0)
    if player.get_weapon_infernal() == "voracious" and player.voracious_stacks > 0:
        chance += player.voracious_stacks * 5
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
) -> float:
    """Phase 1 — compute the pre-hit attack multiplier from emblems and passive sources."""
    from core.combat import jewel_engine as _je

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

    if player.get_armor_passive() == "Piety" and random.random() < 0.10:
        mult *= 7.0
        calc_sources.append("piety×7.000")
        log.append("🙏 **Piety** blesses your strike! Damage increased 7×!")

    onslaught_bonus = _je.apply_onslaught_mult(player)
    if onslaught_bonus > 0:
        factor = 1 + onslaught_bonus / 100
        mult *= factor
        calc_sources.append(f"onslaught_jewel×{factor:.3f}")
        log.append(f"🔥 **Onslaught** unleashes fury! (+{onslaught_bonus:.0f}% ATK)")

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
    calc.append(
        f"  mult: {src_str} → {mult:.4f}x  (base_atk={player.get_total_attack()})"
    )
    return mult


def resolve_hit(
    player: Player,
    monster: Monster,
    attack_multiplier: float,
    log: list[str],
    calc: list[str],
) -> tuple[bool, float]:
    """Phase 2 — hit chance roll. Returns (is_hit, attack_multiplier)."""
    from core.combat.calcs import fmt_weapon_passive, get_weapon_tier

    hit_chance = calculate_hit_chance(player, monster)
    acc_bonus = player.get_emblem_bonus("accuracy") * 2

    idx, name = get_weapon_tier(player, "deadeye")
    if idx >= 0:
        wep_acc = (idx + 1) * 4
        acc_bonus += wep_acc
        log.append(
            f"**{fmt_weapon_passive(name)}** boosts 🎯 accuracy by **{wep_acc}**!"
        )

    blinding_note = ""
    if monster.has_modifier("Blinding"):
        penalty = int(monster.get_modifier_value("Blinding"))
        acc_bonus -= penalty
        blinding_note = f" -Blinding{penalty}"

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
        f"  hit: chance={hit_chance*100:.1f}%{blinding_note} → threshold={miss_threshold} | "
        f"roll={attack_roll}{lucky_note}{jinxed_note}+acc={acc_bonus}={attack_roll+acc_bonus}"
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
