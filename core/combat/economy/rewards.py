import random
from typing import Any, Dict

from core.combat.economy.config import (
    ANGELIC_KEY_BASE_CHANCE,
    BALANCE_FRAG_BASE_CHANCE,
    CO_GOLD_BOOST_PER_LEVEL,
    CO_XP_BOOST_PER_LEVEL,
    DRACONIC_KEY_BASE_CHANCE,
    EMBLEM_FIND_BONUS_PER_TIER,
    FLORA_CONVERSION_PER_LEVEL,
    GEAR_DROP_BASE_CHANCE,
    GEAR_DROP_MAX_BONUS,
    GEAR_DROP_SCALING_CONSTANT,
    GOLD_BASE_BUFF_PCT,
    GOLD_BASE_FLAT,
    GOLD_RARITY_DENOMINATOR,
    GUILD_TICKET_BASE_CHANCE,
    GUILD_TICKET_MIN_LEVEL,
    INFINITE_WISDOM_CHANCE_PER_LEVEL,
    LUCIFER_BOOT_GOLD_CAP,
    LUCIFER_BOOT_GOLD_PER_MODIFIER,
    MODIFIER_DIFFICULTY_CAP,
    PROSPER_CHANCE_PER_LEVEL,
    SOUL_CORE_BASE_CHANCE,
    SPECIAL_DROP_BASE_CHANCE,
    SPIRIT_STONE_BASE_CHANCE,
    STAT_INVEST_GOLD_PER_POINT,
    VOID_FRAG_BASE_CHANCE,
)
from core.emojis import INFERNAL_ENGRAM
from core.models import Monster, Player

# Rite of Convergence entry keys — RAID-DESIGN.md: "Each key drops
# independently from any Level 100 combat at 0% base rate + Special Rarity."
# No generic SPECIAL_DROP_BASE_CHANCE floor like the other level-gated drops
# below; the chance is exactly the modifier-difficulty + special-rarity pool.
RITE_KEY_CURRENCY_COLUMNS: tuple = (
    "rite_key_apex_of_dreams",
    "rite_key_corruption_of_memories",
    "rite_key_scales_of_judgment",
    "rite_key_devoid_of_thoughts",
    "rite_key_zenith_of_nightmares",
)


def calculate_rewards(
    player: Player, monster: Monster, *, apply_modifier_xp_bonus: bool = False
) -> Dict[str, Any]:
    """
    Calculates XP and Gold rewards for a combat victory.

    XP flow
    -------
    1. Base XP from monster.
    2. Single additive pool: xp_find emblem, Affluence tome, co_xp_boost partner
       skill, Midas soul-stone, Infinite Wisdom proc (+100 %), Apex Vault (+100 %),
       modifier difficulty (uncapped — normal combat only, see apply_modifier_xp_bonus).
    3. final_xp = base_xp × (1 + additive_pool).
    4. Flat bonus: Equilibrium glove pending XP added AFTER pool — unscaled.

    apply_modifier_xp_bonus — when True, adds the monster's uncapped modifier
    difficulty sum (same per-modifier values that drive the capped special-drop
    bonus, see MODIFIER_DIFFICULTY_CAP) straight into the XP pool. Only normal
    (non-uber) combat opts in via apply_victory_rewards; Apex/Uber/Codex call
    this function directly and leave it off. Also populates
    results['difficulty_xp_pct'] / results['difficulty_drop_pct'] for display.

    Gold flow
    ---------
    1. Base gold from monster level / reward_scale formula, buffed by
       GOLD_BASE_BUFF_PCT (applied here so it compounds with every later step
       instead of being a flat tack-on at the end).
    2. Rarity multiplier (sole multiplicative step): × (1 + √rarity / denom).
    3. Flat floor: +GOLD_BASE_FLAT.
    4. Single additive pool: gold_find emblem, Infernal Plunder (Lucifer boot),
       Affluence tome, co_gold_boost partner skill, Midas soul-stone,
       stat_invest_gold, Prosper proc (+100 %), Apex Vault (+100 %).
    5. final_gold = step-3 result × (1 + additive_pool).
    6. Flat bonus: Plundering glove pending gold added AFTER pool — unscaled.
    7. Flora sig: converts a portion of final_gold into skilling materials.

    Returns a dict: 'xp', 'gold', 'msgs', 'items'.
    """
    results: Dict[str, Any] = {"xp": 0, "gold": 0, "msgs": [], "items": []}

    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0

    # ── Shared bonuses — computed once ──────────────────────────────────────
    affluence_pct = player.get_tome_bonus("affluence")  # e.g. 15 → 0.15
    in_vault = getattr(player.cs, "apex_zone", None) == "vault"

    # Midas soul-stone resonance
    midas_xp_frac = 0.0
    midas_gold_frac = 0.0
    if player.soul_stone:
        from core.apex.mechanics import ApexMechanics

        res = ApexMechanics.get_resonance_multipliers(player.soul_stone)
        if res["xp_bonus_pct"] > 0:
            midas_xp_frac = res["xp_bonus_pct"] / 100
        if res["gold_bonus_pct"] > 0:
            midas_gold_frac = res["gold_bonus_pct"] / 100

    # Partner combat skill fractions
    co_xp_frac = 0.0
    co_gold_frac = 0.0
    partner_sig_key: str | None = None
    partner_sig_lvl: int = 0
    if player.active_partner:
        partner = player.active_partner
        for key, lvl in partner.combat_skills:
            if key == "co_xp_boost":
                co_xp_frac += lvl * CO_XP_BOOST_PER_LEVEL
            elif key == "co_gold_boost":
                co_gold_frac += lvl * CO_GOLD_BOOST_PER_LEVEL
        partner_sig_key = partner.sig_combat_key
        partner_sig_lvl = partner.sig_combat_lvl

    # ── XP ──────────────────────────────────────────────────────────────────
    base_xp = monster.xp
    xp_additive = 0.0

    results["difficulty_xp_pct"] = 0.0
    results["difficulty_drop_pct"] = 0.0
    if apply_modifier_xp_bonus and monster.modifiers:
        mod_difficulty_sum = sum(m.difficulty for m in monster.modifiers)
        if mod_difficulty_sum > 0:
            xp_additive += mod_difficulty_sum
            results["difficulty_xp_pct"] = mod_difficulty_sum
            results["difficulty_drop_pct"] = min(
                MODIFIER_DIFFICULTY_CAP, mod_difficulty_sum
            )

    xp_find_tiers = player.get_emblem_bonus("xp_find")
    if xp_find_tiers > 0:
        xp_additive += xp_find_tiers * EMBLEM_FIND_BONUS_PER_TIER

    if affluence_pct > 0:
        xp_additive += affluence_pct / 100

    xp_additive += co_xp_frac
    xp_additive += midas_xp_frac

    if in_vault:
        xp_additive += 1.0  # +100 % from Apex Vault

    # Infinite Wisdom — proc adds +100 % to XP pool
    if acc_passive == "Infinite Wisdom":
        if random.random() < acc_lvl * INFINITE_WISDOM_CHANCE_PER_LEVEL:
            xp_additive += 1.0
            results["msgs"].append(f"**Infinite Wisdom ({acc_lvl})** grants +100% XP!")
    elif acc_passive != "Infinite Wisdom":
        # Soul stone: infinite wisdom — 2:1 tier mapping (matches Absorb's accessory convention).
        ss_wisdom = player.get_soul_stone_passive("infinite wisdom")
        if ss_wisdom:
            equiv_lvl = ss_wisdom * 2
            if random.random() < equiv_lvl * INFINITE_WISDOM_CHANCE_PER_LEVEL:
                xp_additive += 1.0
                results["msgs"].append(
                    f"**Soul Infinite Wisdom T{ss_wisdom}** grants +100% XP!"
                )

    results["xp"] = int(base_xp * (1 + xp_additive))

    # Equilibrium glove: flat XP added AFTER pool — unaffected by modifiers
    if player.equilibrium_bonus_xp_pending > 0:
        results["xp"] += player.equilibrium_bonus_xp_pending
        results["msgs"].append(
            f"**Equilibrium** siphons an extra {player.equilibrium_bonus_xp_pending:,} XP!"
        )
        player.equilibrium_bonus_xp_pending = 0

    # ── Gold ─────────────────────────────────────────────────────────────────
    rare_monsters = [
        "Treasure Chest",
        "Random Korean Lady",
        "KPOP STAR",
        "Loot Goblin",
        "Yggdrasil",
        "Capybara Sauna",
    ]

    if monster.name in rare_monsters:
        reward_scale = int(player.level / 10)
    else:
        reward_scale = max(0, (monster.level - player.level) / 10)

    gold_base = int(
        (monster.level ** random.uniform(1.4, 1.6))
        * (1 + (reward_scale**1.3))
        * (1 + GOLD_BASE_BUFF_PCT)
    )

    # Rarity — sole multiplicative step, applied first
    rarity = player.get_total_rarity()
    if rarity > 0:
        gold_base = int(gold_base * (1 + (rarity**0.5) / GOLD_RARITY_DENOMINATOR))

    gold_base += GOLD_BASE_FLAT

    # Additive pool
    gold_additive = 0.0

    gold_find_tiers = player.get_emblem_bonus("gold_find")
    if gold_find_tiers > 0:
        gold_additive += gold_find_tiers * EMBLEM_FIND_BONUS_PER_TIER

    # Lucifer boot: Infernal Plunder — % per modifier, capped
    if player.get_boot_corrupted_essence() == "lucifer" and monster.modifiers:
        num_mods = len(monster.modifiers)
        lucifer_pct = min(
            LUCIFER_BOOT_GOLD_CAP, num_mods * LUCIFER_BOOT_GOLD_PER_MODIFIER
        )
        gold_additive += lucifer_pct
        results["msgs"].append(
            f"{INFERNAL_ENGRAM} **Infernal Plunder** — {num_mods} modifier"
            f"{'s' if num_mods > 1 else ''} grant +{int(lucifer_pct * 100)}% increased gold!"
        )

    if affluence_pct > 0:
        gold_additive += affluence_pct / 100

    gold_additive += co_gold_frac
    gold_additive += midas_gold_frac

    # Stat investment gold bonus (0.1 % per point)
    if getattr(player, "stat_invest_gold", 0) > 0:
        gold_additive += player.stat_invest_gold * STAT_INVEST_GOLD_PER_POINT

    if in_vault:
        gold_additive += 1.0  # +100 % from Apex Vault

    # Prosper — proc adds +100 % to gold pool
    if acc_passive == "Prosper":
        if random.random() < acc_lvl * PROSPER_CHANCE_PER_LEVEL:
            gold_additive += 1.0
            results["msgs"].append(f"**Prosper ({acc_lvl})** grants +100% Gold!")
    elif acc_passive != "Prosper":
        # Soul stone: prosper — 2:1 tier mapping (matches Absorb's accessory convention).
        ss_prosper = player.get_soul_stone_passive("prosper")
        if ss_prosper:
            equiv_lvl = ss_prosper * 2
            if random.random() < equiv_lvl * PROSPER_CHANCE_PER_LEVEL:
                gold_additive += 1.0
                results["msgs"].append(
                    f"**Soul Prosper T{ss_prosper}** grants +100% Gold!"
                )

    results["gold"] = int(gold_base * (1 + gold_additive))

    # Plundering glove: flat gold added AFTER pool — unaffected by modifiers
    if player.plundering_bonus_gold_pending > 0:
        results["gold"] += player.plundering_bonus_gold_pending
        results["msgs"].append(
            f"**Plundering** snatches an extra {player.plundering_bonus_gold_pending:,} Gold!"
        )
        player.plundering_bonus_gold_pending = 0

    # Flora sig: convert a portion of final gold into skilling materials.
    # Applied after all gold multipliers so the conversion is from the true final value.
    if partner_sig_key == "sig_co_flora" and partner_sig_lvl >= 1:
        flora_pct = partner_sig_lvl * FLORA_CONVERSION_PER_LEVEL
        converted = int(results["gold"] * flora_pct)
        results["gold"] = max(0, results["gold"] - converted)
        results["flora_skilling_gold"] = converted
        results["msgs"].append(
            f"🌿 **Nature's Bounty (Lv.{partner_sig_lvl})** — "
            f"{converted:,} GP converted into skilling materials!"
        )

    return results


def check_special_drops(player: Player, monster: Monster) -> Dict[str, bool]:
    """
    Determines which special items (Keys, Runes, Curios, Stones) drop.

    Special Drop Pool formula (non-boss, for every eligible drop):
        chance = base_rate
                 + min(MODIFIER_DIFFICULTY_CAP, sum(m.difficulty for m in modifiers))
                 + player.get_special_drop_bonus() / 100

    Items in the pool: Spirit Stones, Guild Tickets, material/key/rune drops.
    Body Parts and Eggs are handled separately in drops.py using the same formula.

    Returns a dict of truthy flags like {'spirit_stone': True, 'draconic_key': True}.
    """
    from core.inner_sanctum.mechanics import get_tree_bonuses

    is_bonuses = get_tree_bonuses(getattr(player, "inner_sanctum_nodes", {}))
    drops = {}

    # ── Boss encounters ──────────────────────────────────────────────────────
    if monster.is_boss:
        special_bonus = player.get_special_drop_bonus() / 100
        rare_chance = 0.05 + special_bonus

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

        # Inner Sanctum Deicide — Reliquary Sense: flat bonus % added to every
        # boss rune/key chance (curio excluded — it's already guaranteed).
        boss_rune_bonus = is_bonuses["boss_rune_chance_pct"]

        for boss_name, config in boss_configs.items():
            if boss_name in monster.name:
                for item, chance in config.items():
                    eff_chance = (
                        chance if item == "curio" else min(1.0, chance + boss_rune_bonus)
                    )
                    if random.random() < eff_chance:
                        drops[item] = True

                # Deicide — Greedy Conquest: chance for one extra bonus item from
                # this boss's table (can duplicate an already-rolled rune type).
                dupe_chance = is_bonuses["boss_dupe_chance"]
                dupe_candidates = [k for k in config if k != "curio"]
                if dupe_chance and dupe_candidates and random.random() < dupe_chance:
                    drops["deicide_dupe_item"] = random.choice(dupe_candidates)
                break

        if player.level >= 30:
            if random.random() < rare_chance:
                drops["spirit_stone"] = True

        if player.level >= 60:
            for item in ["blessed_bismuth", "sparkling_sprig", "capricious_carp"]:
                if random.random() < rare_chance:
                    drops[item] = True
        if player.level >= 80:
            if random.random() < rare_chance:
                drops["antique_tome"] = True

        if player.level >= 100:
            if random.random() < rare_chance:
                drops["pinnacle_key"] = True

        return drops

    # ── Compute special drop pool bonus ─────────────────────────────────────
    # Used by guild tickets, spirit stones, and all level-gated drops.
    special_rarity = player.get_special_drop_bonus() / 100
    mod_difficulty_bonus = min(
        MODIFIER_DIFFICULTY_CAP,
        sum(m.difficulty for m in monster.modifiers),
    )
    special_drop_chance = mod_difficulty_bonus + special_rarity

    # Inner Sanctum Vice — Hoarder's Eye: flat bonus % on rune-specific rolls only
    # (shatter_rune, rune_of_regret) — deliberately not folded into special_drop_chance
    # so it doesn't also buff unrelated drops like Guild Tickets or Blueprints.
    rune_chance_bonus = is_bonuses["rune_chance_pct"]

    # Rare monsters always receive the full difficulty cap bonus + a free curio.
    rare_monsters = [
        "Treasure Chest",
        "Random Korean Lady",
        "KPOP STAR",
        "Loot Goblin",
        "Yggdrasil",
        "Capybara Sauna",
    ]
    if monster.name in rare_monsters:
        special_drop_chance = MODIFIER_DIFFICULTY_CAP + special_rarity
        drops["curio"] = True

    # ── Partner signature drops ──────────────────────────────────────────────
    if player.active_partner:
        partner = player.active_partner
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

    # ── Guild Ticket — level-gated, no active partner required ──────────────
    if player.level >= GUILD_TICKET_MIN_LEVEL:
        if random.random() < GUILD_TICKET_BASE_CHANCE + special_drop_chance:
            drops["guild_ticket"] = True

    # ── Level-gated drops ────────────────────────────────────────────────────
    if player.level >= 20:
        if random.random() < DRACONIC_KEY_BASE_CHANCE + special_drop_chance:
            drops["draconic_key"] = True
        if random.random() < ANGELIC_KEY_BASE_CHANCE + special_drop_chance:
            drops["angelic_key"] = True
        if random.random() < SPECIAL_DROP_BASE_CHANCE + special_drop_chance + rune_chance_bonus:
            drops["shatter_rune"] = True

    if player.level >= 30:
        if random.random() < SOUL_CORE_BASE_CHANCE + special_drop_chance:
            drops["soul_core"] = True
        if random.random() < SPIRIT_STONE_BASE_CHANCE + special_drop_chance:
            drops["spirit_stone"] = True

    if player.level >= 40:
        if random.random() < BALANCE_FRAG_BASE_CHANCE + special_drop_chance:
            drops["balance_fragment"] = True

    if player.level >= 10:
        for item in ("unidentified_blueprint", "diviners_rod"):
            if random.random() < SPECIAL_DROP_BASE_CHANCE + special_drop_chance:
                drops[item] = True
        for item in ("magma_core", "life_root", "spirit_shard"):
            if random.random() < SPECIAL_DROP_BASE_CHANCE + special_drop_chance:
                drops[item] = True
        if random.random() < SPECIAL_DROP_BASE_CHANCE + special_drop_chance + rune_chance_bonus:
            drops["rune_of_regret"] = True

    if player.level >= 50:
        if random.random() < VOID_FRAG_BASE_CHANCE + special_drop_chance:
            drops["void_frag"] = True

    if player.level >= 60:
        elemental_chance = SPECIAL_DROP_BASE_CHANCE + special_drop_chance
        for item in ("blessed_bismuth", "sparkling_sprig", "capricious_carp"):
            if random.random() < elemental_chance:
                drops[item] = True

    if player.level >= 80:
        if random.random() < SPECIAL_DROP_BASE_CHANCE + special_drop_chance:
            drops["antique_tome"] = True

    if player.level >= 100:
        if random.random() < SPECIAL_DROP_BASE_CHANCE + special_drop_chance:
            drops["pinnacle_key"] = True
        for rite_key_col in RITE_KEY_CURRENCY_COLUMNS:
            if random.random() < special_drop_chance:
                drops[rite_key_col] = True

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
    "spirit_stone": ("spirit_stones", "Spirit Stone"),
    "antique_tome": ("antique_tome", "Antique Tome"),
    "pinnacle_key": ("pinnacle_key", "Pinnacle Key"),
    "rune_of_regret": ("rune_of_regret", "Rune of Regret"),
    "rite_key_apex_of_dreams": ("rite_key_apex_of_dreams", "Apex of Dreams"),
    "rite_key_corruption_of_memories": (
        "rite_key_corruption_of_memories",
        "Corruption of Memories",
    ),
    "rite_key_scales_of_judgment": (
        "rite_key_scales_of_judgment",
        "Scales of Judgment",
    ),
    "rite_key_devoid_of_thoughts": (
        "rite_key_devoid_of_thoughts",
        "Devoid of Thoughts",
    ),
    "rite_key_zenith_of_nightmares": (
        "rite_key_zenith_of_nightmares",
        "Zenith of Nightmares",
    ),
}

# Settlement materials routed to settlement_materials repo (not users table)
_SETTLEMENT_MATERIAL_MAP: Dict[str, str] = {
    "magma_core": "Magma Core",
    "life_root": "Life Root",
    "spirit_shard": "Spirit Shard",
    "unidentified_blueprint": "Unidentified Blueprint",
    "diviners_rod": "Diviner's Rod",
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

        if key in _SETTLEMENT_MATERIAL_MAP:
            display_name = _SETTLEMENT_MATERIAL_MAP[key]
            await bot.database.settlement_materials.modify(user_id, key, 1)
            reward_data["special"].append(display_name)

        elif key in _SPECIAL_FLAG_CURRENCY_MAP:
            currency_key, display_name = _SPECIAL_FLAG_CURRENCY_MAP[key]
            await bot.database.users.modify_currency(user_id, currency_key, 1)
            reward_data["special"].append(display_name)

        elif key == "curio":
            await bot.database.users.modify_currency(user_id, "curios", 1)
            reward_data["curios"] = 1

        elif key == "blessed_bismuth":
            await bot.database.skills.increment_blessed_bismuth(user_id, server_id, 1)
            reward_data["special"].append("Blessed Bismuth")

        elif key == "sparkling_sprig":
            await bot.database.skills.increment_sparkling_sprig(user_id, server_id, 1)
            reward_data["special"].append("Sparkling Sprig")

        elif key == "capricious_carp":
            await bot.database.skills.increment_capricious_carp(user_id, server_id, 1)
            reward_data["special"].append("Capricious Carp")

        elif key == "guild_ticket":
            await bot.database.partners.add_tickets(user_id, 1)
            reward_data["special"].append("Guild Ticket")

        elif key == "velour_doubled":
            reward_data["special"] = reward_data["special"] * 2

        elif key == "yvenn_slayer_bonus" and isinstance(val, int):
            # Bonus slayer progress — stored for the slayer integration block
            reward_data["yvenn_slayer_bonus"] = val

        elif key == "deicide_dupe_item" and isinstance(val, str):
            # Inner Sanctum Deicide — Greedy Conquest: a second unit of a boss
            # rune/key type, granted even if the same type already dropped above.
            if val in _SPECIAL_FLAG_CURRENCY_MAP:
                currency_key, display_name = _SPECIAL_FLAG_CURRENCY_MAP[val]
                await bot.database.users.modify_currency(user_id, currency_key, 1)
                reward_data["special"].append(f"{display_name} (Deicide bonus)")


def calculate_item_drop_chance(player: Player) -> int:
    """
    Calculates the percentage chance (0–100) for a gear item to drop.

    Base:  GEAR_DROP_BASE_CHANCE  (10 %)
    Cap:   base + GEAR_DROP_MAX_BONUS  (30 % asymptotic)
    Scale: bonus = MAX_BONUS × rarity / (rarity + SCALING_CONSTANT)
           → 100 % rarity ≈ 18.2 % total, asymptotes to 30 % at infinite rarity.
    """
    rarity = max(0, player.get_total_rarity())
    bonus_chance = GEAR_DROP_MAX_BONUS * (
        rarity / (rarity + GEAR_DROP_SCALING_CONSTANT)
    )
    return int(GEAR_DROP_BASE_CHANCE + bonus_chance)
