import random
from typing import Any, Dict

from core.models import Monster, Player


def calculate_rewards(player: Player, monster: Monster) -> Dict[str, Any]:
    """
    Calculates XP and Gold rewards based on player stats, passives, and monster level.
    Returns a dict containing 'xp', 'gold', and a list of 'msgs' for logs.
    """
    results = {"xp": 0, "gold": 0, "msgs": [], "items": []}

    # --- XP Calculation ---
    base_xp = monster.xp

    xp_find_tiers = player.get_emblem_bonus("xp_find")
    if xp_find_tiers > 0:
        base_xp = int(base_xp * (1 + (xp_find_tiers * 0.03)))

    # Accessory Passive: Infinite Wisdom
    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0

    if acc_passive == "Infinite Wisdom":
        double_exp_chance = acc_lvl * 0.05
        if random.random() <= double_exp_chance:
            base_xp *= 2
            results["msgs"].append(f"**Infinite Wisdom ({acc_lvl})** grants double XP!")

    # Glove Passive: Equilibrium (Pending XP)
    if player.equilibrium_bonus_xp_pending > 0:
        base_xp += player.equilibrium_bonus_xp_pending
        results["msgs"].append(
            f"**Equilibrium** siphons an extra {player.equilibrium_bonus_xp_pending:,} XP!"
        )
        player.equilibrium_bonus_xp_pending = 0  # Reset

    results["xp"] = base_xp

    # --- Gold Calculation ---
    rare_monsters = [
        "Treasure Chest",
        "Random Korean Lady",
        "KPOP STAR",
        "Loot Goblin",
        "Yggdrasil",
        "Capybara Sauna",
    ]

    reward_scale = 0
    if monster.name in rare_monsters:
        reward_scale = int(player.level / 10)
    else:
        reward_scale = max(0, (monster.level - player.level) / 10)

    gold_award = int(
        (monster.level ** random.uniform(1.4, 1.6)) * (1 + (reward_scale**1.3))
    )

    # Rarity Bonus — diminishing returns via sqrt to prevent runaway scaling at 2000%+
    rarity = player.get_total_rarity()
    if rarity > 0:
        gold_award = int(gold_award * (1 + (rarity ** 0.5) / 20))

    gold_award += 20  # Base flat amount

    # Accessory Passive: Prosper
    if acc_passive == "Prosper":
        double_gold_chance = acc_lvl * 0.10
        if random.random() <= double_gold_chance:
            gold_award *= 2
            results["msgs"].append(f"**Prosper ({acc_lvl})** grants double Gold!")

    # Glove Passive: Plundering (Pending Gold)
    if player.plundering_bonus_gold_pending > 0:
        gold_award += player.plundering_bonus_gold_pending
        results["msgs"].append(
            f"**Plundering** snatches an extra {player.plundering_bonus_gold_pending:,} Gold!"
        )
        player.plundering_bonus_gold_pending = 0  # Reset

    # Gold find
    gold_find_tiers = player.get_emblem_bonus("gold_find")
    if gold_find_tiers > 0:
        gold_award = int(gold_award * (1 + (gold_find_tiers * 0.03)))

    # Lucifer boot: gold increases 10% per modifier on the monster (cap 50%)
    if player.get_boot_corrupted_essence() == "lucifer" and monster.modifiers:
        num_mods = len(monster.modifiers)
        lucifer_bonus_pct = min(0.50, num_mods * 0.10)
        bonus_gold = int(gold_award * lucifer_bonus_pct)
        gold_award += bonus_gold
        results["msgs"].append(
            f"🔥 **Infernal Plunder** — {num_mods} modifiers grant +{int(lucifer_bonus_pct * 100)}% gold! (+{bonus_gold:,})"
        )

    results["gold"] = gold_award

    # Codex Tome: Affluence (+% XP and Gold from all combat)
    affluence_pct = player.get_tome_bonus("affluence")
    if affluence_pct > 0:
        mult = 1 + (affluence_pct / 100)
        results["xp"] = int(results["xp"] * mult)
        results["gold"] = int(results["gold"] * mult)

    # Partner combat skill bonuses (applied after affluence)
    if player.active_partner:
        partner = player.active_partner
        for key, lvl in partner.combat_skills:
            if key == "co_xp_boost":
                results["xp"] = int(results["xp"] * (1 + lvl * 0.05))
            elif key == "co_gold_boost":
                results["gold"] = int(results["gold"] * (1 + lvl * 0.05))

        sig_key = partner.sig_combat_key
        sig_lvl = partner.sig_combat_lvl
        if sig_key == "sig_co_flora" and sig_lvl >= 1:
            flora_pct = sig_lvl * 0.10
            converted = int(results["gold"] * flora_pct)
            results["gold"] = max(0, results["gold"] - converted)
            results["flora_skilling_gold"] = converted

    return results


def check_special_drops(player: Player, monster: Monster) -> Dict[str, bool]:
    """
    Determines which special items (Keys, Runes, Curios) drop.
    Returns a dict of flags like {'draconic_key': True, 'refinement_rune': True}
    """
    drops = {}

    # --- BOSS DROPS (Aphrodite, Lucifer, NEET, Gemini) ---
    if "Aphrodite" in monster.name:
        if random.random() < 0.33:
            drops["refinement_rune"] = True
        if random.random() < 0.33:
            drops["potential_rune"] = True
        if random.random() < 0.33:
            drops["imbue_rune"] = True
        drops["curio"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["spirit_stone"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["antique_tome"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["pinnacle_key"] = True
        _elemental_boss_chance = 0.05 + (player.get_special_drop_bonus() / 100)
        if random.random() < _elemental_boss_chance:
            drops["blessed_bismuth"] = True
        if random.random() < _elemental_boss_chance:
            drops["sparkling_sprig"] = True
        if random.random() < _elemental_boss_chance:
            drops["capricious_carp"] = True
        return drops

    if "Lucifer" in monster.name:
        if random.random() < 0.66:
            drops["refinement_rune"] = True
        if random.random() < 0.33:
            drops["potential_rune"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["spirit_stone"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["antique_tome"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["pinnacle_key"] = True
        _elemental_boss_chance = 0.05 + (player.get_special_drop_bonus() / 100)
        if random.random() < _elemental_boss_chance:
            drops["blessed_bismuth"] = True
        if random.random() < _elemental_boss_chance:
            drops["sparkling_sprig"] = True
        if random.random() < _elemental_boss_chance:
            drops["capricious_carp"] = True
        return drops

    if "NEET" in monster.name:
        if random.random() < 0.33:
            drops["refinement_rune"] = True
        if random.random() < 0.66:
            drops["potential_rune"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["spirit_stone"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["antique_tome"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["pinnacle_key"] = True
        _elemental_boss_chance = 0.05 + (player.get_special_drop_bonus() / 100)
        if random.random() < _elemental_boss_chance:
            drops["blessed_bismuth"] = True
        if random.random() < _elemental_boss_chance:
            drops["sparkling_sprig"] = True
        if random.random() < _elemental_boss_chance:
            drops["capricious_carp"] = True
        return drops

    if "Gemini" in monster.name:
        if random.random() < 0.5:
            drops["partnership_rune"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["spirit_stone"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["antique_tome"] = True
        if random.random() < 0.05 + (player.get_special_drop_bonus() / 100):
            drops["pinnacle_key"] = True
        _elemental_boss_chance = 0.05 + (player.get_special_drop_bonus() / 100)
        if random.random() < _elemental_boss_chance:
            drops["blessed_bismuth"] = True
        if random.random() < _elemental_boss_chance:
            drops["sparkling_sprig"] = True
        if random.random() < _elemental_boss_chance:
            drops["capricious_carp"] = True
        return drops

    # --- PARTNER DROPS ---
    if player.active_partner:
        partner = player.active_partner
        # Guild ticket: rare drop from any fight
        if random.random() < 0.0001 + player.get_special_drop_bonus() / 100:
            drops["guild_ticket"] = True

        sig_key = partner.sig_combat_key
        sig_lvl = partner.sig_combat_lvl
        if sig_key == "sig_co_kay" and sig_lvl >= 1:
            if random.random() < sig_lvl * 0.05:
                drops["curio"] = True
        if sig_key == "sig_co_velour" and sig_lvl >= 1:
            if random.random() < sig_lvl * 0.02:
                drops["velour_doubled"] = True
        if sig_key == "sig_co_yvenn" and sig_lvl >= 1:
            drops["yvenn_slayer_bonus"] = sig_lvl

    # --- STANDARD MOBS ---
    # 1% Spirit Stone drop from any normal combat encounter
    if random.random() < 0.01 + (player.get_special_drop_bonus() / 100):
        drops["spirit_stone"] = True

    rare_monsters = [
        "Treasure Chest",
        "Random Korean Lady",
        "KPOP STAR",
        "Loot Goblin",
        "Yggdrasil",
        "Capybara Sauna",
    ]

    special_drop_chance = min(0.05, sum(m.difficulty for m in monster.modifiers))
    if monster.name in rare_monsters:
        special_drop_chance = 0.05
        drops["curio"] = True

    special_drop_chance += player.get_special_drop_bonus() / 100

    if random.random() < 0.02 + special_drop_chance:
        drops["magma_core"] = True
    if random.random() < 0.02 + special_drop_chance:
        drops["life_root"] = True
    if random.random() < 0.02 + special_drop_chance:
        drops["spirit_shard"] = True

    # Level 20+ Drops
    if player.level > 20:
        if random.random() < (0.03 + special_drop_chance):
            drops["draconic_key"] = True
        if random.random() < (0.03 + special_drop_chance):
            drops["angelic_key"] = True
        if random.random() < (0.08 + special_drop_chance):
            drops["soul_core"] = True
        if random.random() < (0.05 + special_drop_chance):
            drops["void_frag"] = True
        if random.random() < (0.01 + special_drop_chance):
            drops["shatter_rune"] = True
        if random.random() < (0.05 + special_drop_chance):
            drops["balance_fragment"] = True

        key_drop_chance = 0.05 if monster.is_boss else 0.01
        if random.random() < key_drop_chance + special_drop_chance:
            drops["antique_tome"] = True
        if random.random() < key_drop_chance + special_drop_chance:
            drops["pinnacle_key"] = True

        elemental_key_chance = (0.05 if monster.is_boss else 0.01) + special_drop_chance
        if random.random() < elemental_key_chance:
            drops["blessed_bismuth"] = True
        if random.random() < elemental_key_chance:
            drops["sparkling_sprig"] = True
        if random.random() < elemental_key_chance:
            drops["capricious_carp"] = True

    return drops


def apply_partner_end_rewards(
    player: Player, xp_gained: int
) -> list[str]:
    """
    Grants XP to the active combat partner and increments affinity.
    Modifies partner in-place; caller must persist changes to DB.
    Returns level-up message strings (if any).
    """
    partner = player.active_partner
    if not partner:
        return []

    from core.partners.mechanics import grant_xp as _partner_grant_xp

    partner_xp = max(1, xp_gained // 10)
    new_level, new_exp, level_msgs = _partner_grant_xp(partner.level, partner.exp, partner_xp)
    partner.level = new_level
    partner.exp = new_exp
    partner.affinity_encounters = min(100, partner.affinity_encounters + 1)
    return level_msgs


def calculate_item_drop_chance(player: Player) -> int:
    """
    Calculates the percentage chance (0-100) for a gear item to drop.
    Base: 10%
    Max Cap: 30% (Asymptotic)
    Scaling: 100% Rarity = 20% Total Chance
    """
    base_chance = 10.0
    max_bonus_chance = 20.0  # The most you can possibly add to the base

    scaling_constant = 100.0

    rarity = max(0, player.get_total_rarity())

    # Formula: MaxBonus * ( R / (R + K) )
    # As R gets huge, the fraction approaches 1.0, giving the full MaxBonus.
    bonus_chance = max_bonus_chance * (rarity / (rarity + scaling_constant))

    total_chance = base_chance + bonus_chance

    return int(total_chance)
