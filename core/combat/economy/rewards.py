import random
from typing import Any, Dict

from core.combat.economy.config import (
    EMBLEM_FIND_BONUS_PER_TIER,
    FLORA_CONVERSION_PER_LEVEL,
    LUCIFER_BOOT_GOLD_CAP,
    LUCIFER_BOOT_GOLD_PER_MODIFIER,
)
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
        base_xp = int(base_xp * (1 + (xp_find_tiers * EMBLEM_FIND_BONUS_PER_TIER)))

    # Glove Passive: Equilibrium (Pending XP from combat damage)
    if player.equilibrium_bonus_xp_pending > 0:
        base_xp += player.equilibrium_bonus_xp_pending
        results["msgs"].append(
            f"**Equilibrium** siphons an extra {player.equilibrium_bonus_xp_pending:,} XP!"
        )
        player.equilibrium_bonus_xp_pending = 0  # Reset

    results["xp"] = base_xp

    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0

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

    # Glove Passive: Plundering — added BEFORE rarity so the bonus is rarity-scaled
    if player.plundering_bonus_gold_pending > 0:
        gold_award += player.plundering_bonus_gold_pending
        results["msgs"].append(
            f"**Plundering** snatches an extra {player.plundering_bonus_gold_pending:,} Gold!"
        )
        player.plundering_bonus_gold_pending = 0  # Reset

    # Rarity Bonus — diminishing returns via sqrt to prevent runaway scaling at 2000%+
    rarity = player.get_total_rarity()
    if rarity > 0:
        gold_award = int(gold_award * (1 + (rarity**0.5) / 20))

    gold_award += 20  # Base flat amount

    # Gold find emblem
    gold_find_tiers = player.get_emblem_bonus("gold_find")
    if gold_find_tiers > 0:
        gold_award = int(
            gold_award * (1 + (gold_find_tiers * EMBLEM_FIND_BONUS_PER_TIER))
        )

    # Lucifer boot: gold increases per modifier on the monster (cap 50%)
    if player.get_boot_corrupted_essence() == "lucifer" and monster.modifiers:
        num_mods = len(monster.modifiers)
        lucifer_bonus_pct = min(
            LUCIFER_BOOT_GOLD_CAP, num_mods * LUCIFER_BOOT_GOLD_PER_MODIFIER
        )
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

    # Accessory Passive: Prosper — doubles final gold after all other modifiers
    if acc_passive == "Prosper":
        double_gold_chance = acc_lvl * 0.10
        if random.random() <= double_gold_chance:
            results["gold"] *= 2
            results["msgs"].append(f"**Prosper ({acc_lvl})** grants double Gold!")

    # Accessory Passive: Infinite Wisdom — doubles final XP after all other modifiers
    if acc_passive == "Infinite Wisdom":
        double_exp_chance = acc_lvl * 0.05
        if random.random() <= double_exp_chance:
            results["xp"] *= 2
            results["msgs"].append(f"**Infinite Wisdom ({acc_lvl})** grants double XP!")

        sig_key = partner.sig_combat_key
        sig_lvl = partner.sig_combat_lvl
        if sig_key == "sig_co_flora" and sig_lvl >= 1:
            flora_pct = sig_lvl * FLORA_CONVERSION_PER_LEVEL
            converted = int(results["gold"] * flora_pct)
            results["gold"] = max(0, results["gold"] - converted)
            results["flora_skilling_gold"] = converted
            results["msgs"].append(
                f"🌿 **Flora's Blessing (Lv.{sig_lvl})** — {converted:,} GP converted into skilling materials!"
            )

    return results


def check_special_drops(player: Player, monster: Monster) -> Dict[str, bool]:
    """
    Determines which special items (Keys, Runes, Curios) drop.
    Returns a dict of flags like {'draconic_key': True, 'refinement_rune': True}
    """
    drops = {}

    if monster.is_boss:
        special_bonus = player.get_special_drop_bonus() / 100
        rare_chance = 0.05 + special_bonus

        # Boss-specific drop configurations
        boss_configs = {
            "Aphrodite": {
                "refinement_rune": 0.33,
                "potential_rune": 0.33,
                "imbue_rune": 0.30,
                "curio": 1.0,  # guaranteed
            },
            "Lucifer": {
                "refinement_rune": 0.66,
                "potential_rune": 0.33,
            },
            "NEET": {
                "refinement_rune": 0.33,
                "potential_rune": 0.66,
            },
            "Gemini": {
                "partnership_rune": 0.5,
            },
        }

        # Apply boss-specific drops (only the first match wins)
        for boss_name, config in boss_configs.items():
            if boss_name in monster.name:
                for item, chance in config.items():
                    if random.random() < chance:
                        drops[item] = True
                break

        # Common rare drops (identical for all these bosses)
        for item in ["spirit_stone", "antique_tome", "pinnacle_key"]:
            if random.random() < rare_chance:
                drops[item] = True

        # Common elemental boss drops — only available once the player has reached Level 60
        if player.level >= 60:
            for item in ["blessed_bismuth", "sparkling_sprig", "capricious_carp"]:
                if random.random() < rare_chance:
                    drops[item] = True

        return drops

    # --- PARTNER DROPS ---
    if player.active_partner:
        partner = player.active_partner
        # Guild ticket: rare drop from any fight
        if random.random() < 0.01 + player.get_special_drop_bonus() / 100:
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

    if random.random() < 0.01 + special_drop_chance:
        drops["magma_core"] = True
    if random.random() < 0.01 + special_drop_chance:
        drops["life_root"] = True
    if random.random() < 0.01 + special_drop_chance:
        drops["spirit_shard"] = True

    # Level-gated drops — each tier unlocks when the corresponding system opens
    if player.level >= 20:
        if random.random() < (0.01 + special_drop_chance):
            drops["draconic_key"] = True
        if random.random() < (0.01 + special_drop_chance):
            drops["angelic_key"] = True
        if random.random() < (0.01 + special_drop_chance):
            drops["shatter_rune"] = True
        key_drop_chance = 0.01
        if random.random() < key_drop_chance + special_drop_chance:
            drops["antique_tome"] = True
        if random.random() < key_drop_chance + special_drop_chance:
            drops["pinnacle_key"] = True

    if player.level >= 30:
        if random.random() < (0.03 + special_drop_chance):
            drops["soul_core"] = True

    if player.level >= 40:
        if random.random() < (0.01 + special_drop_chance):
            drops["balance_fragment"] = True

    if player.level >= 50:
        if random.random() < (0.02 + special_drop_chance):
            drops["void_frag"] = True
        if random.random() < 0.01 + special_drop_chance:
            drops["unidentified_blueprint"] = True

    if player.level >= 60:
        elemental_key_chance = 0.01 + special_drop_chance
        if random.random() < elemental_key_chance:
            drops["blessed_bismuth"] = True
        if random.random() < elemental_key_chance:
            drops["sparkling_sprig"] = True
        if random.random() < elemental_key_chance:
            drops["capricious_carp"] = True

    return drops


def apply_partner_end_rewards(player: Player, xp_gained: int) -> list[str]:
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
    new_level, new_exp, level_msgs = _partner_grant_xp(
        partner.level, partner.exp, partner_xp
    )
    partner.level = new_level
    partner.exp = new_exp
    partner.affinity_encounters = min(100, partner.affinity_encounters + 1)
    return level_msgs


# ---------------------------------------------------------------------------
# Special-flag → currency / reward dispatch
# ---------------------------------------------------------------------------

# Maps a check_special_drops() flag key to (db_currency_key, display_name).
# Flags that require non-trivial DB calls (uber repo, partners, etc.) are
# handled explicitly in apply_special_flags below.
_SPECIAL_FLAG_CURRENCY_MAP: Dict[str, tuple] = {
    "draconic_key": ("dragon_key", "Draconic Key"),
    "angelic_key": ("angel_key", "Angelic Key"),
    "soul_core": ("soul_cores", "Soul Core"),
    "void_frag": ("void_frags", "Void Fragment"),
    "balance_fragment": ("balance_fragment", "Fragment of Balance"),
    "refinement_rune": ("refinement_runes", "Rune of Refinement"),
    "potential_rune": ("potential_runes", "Rune of Potential"),
    "imbue_rune": ("imbue_runes", "Rune of Imbuing"),
    "shatter_rune": ("shatter_runes", "Rune of Shattering"),
    "partnership_rune": ("partnership_runes", "Rune of Partnership"),
    "magma_core": ("magma_core", "Magma Core"),
    "life_root": ("life_root", "Life Root"),
    "spirit_shard": ("spirit_shard", "Spirit Shard"),
    "unidentified_blueprint": ("unidentified_blueprint", "📋 Unidentified Blueprint"),
    "spirit_stone": ("spirit_stones", "🔮 Spirit Stone"),
    "antique_tome": ("antique_tome", "📖 Antique Tome"),
    "pinnacle_key": ("pinnacle_key", "🗝️ Pinnacle Key"),
}


async def apply_special_flags(
    bot,
    user_id: str,
    server_id: str,
    special_flags: Dict[str, Any],
    reward_data: dict,
) -> None:
    """
    Processes special drop flags returned by check_special_drops().

    For each truthy flag:
      - Simple currency flags    → users DB write + reward_data["special"] append.
      - Elemental boss materials → uber DB write  + reward_data["special"] append.
      - curio                   → curios currency + reward_data["curios"] = 1.
      - velour_doubled           → doubles current reward_data["special"] list.
      - yvenn_slayer_bonus       → stored in reward_data for slayer integration.

    Mutates reward_data in-place; no return value.
    """
    for key, val in special_flags.items():
        if not val:
            continue

        if key in _SPECIAL_FLAG_CURRENCY_MAP:
            currency_key, display_name = _SPECIAL_FLAG_CURRENCY_MAP[key]
            await bot.database.users.modify_currency(user_id, currency_key, 1)
            reward_data["special"].append(display_name)

        elif key == "curio":
            await bot.database.users.modify_currency(user_id, "curios", 1)
            reward_data["curios"] = 1

        elif key == "blessed_bismuth":
            await bot.database.uber.increment_blessed_bismuth(user_id, server_id, 1)
            reward_data["special"].append("⚗️ Blessed Bismuth")

        elif key == "sparkling_sprig":
            await bot.database.uber.increment_sparkling_sprig(user_id, server_id, 1)
            reward_data["special"].append("🌿 Sparkling Sprig")

        elif key == "capricious_carp":
            await bot.database.uber.increment_capricious_carp(user_id, server_id, 1)
            reward_data["special"].append("🐟 Capricious Carp")

        elif key == "guild_ticket":
            await bot.database.partners.add_tickets(user_id, 1)
            reward_data["special"].append("🎫 Guild Ticket")

        elif key == "velour_doubled":
            reward_data["special"] = reward_data["special"] * 2

        elif key == "yvenn_slayer_bonus" and isinstance(val, int):
            # Bonus slayer progress — stored for the slayer integration block
            reward_data["yvenn_slayer_bonus"] = val


def calculate_item_drop_chance(player: Player) -> int:
    """
    Calculates the percentage chance (0-100) for a gear item to drop.
    Base: 10%
    Max Cap: 30% (Asymptotic)
    Scaling: 100% Rarity = 20% Total Chance
    """
    base_chance = 10.0
    max_bonus_chance = 20.0  # The most you can possibly add to the base

    scaling_constant = 1000.0

    rarity = max(0, player.get_total_rarity())

    # Formula: MaxBonus * ( R / (R + K) )
    # As R gets huge, the fraction approaches 1.0, giving the full MaxBonus.
    bonus_chance = max_bonus_chance * (rarity / (rarity + scaling_constant))

    total_chance = base_chance + bonus_chance

    return int(total_chance)
