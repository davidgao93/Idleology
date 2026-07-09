"""
core/quests/data.py — Quest definitions, damage bands, horizon paths, and check-in track.
"""

from __future__ import annotations

import random

from core.emojis import SOUL_CORE, SPIRIT_STONE, VOID_FRAG

# ---------------------------------------------------------------------------
# Daily Quest Pool
# ---------------------------------------------------------------------------

DAILY_QUESTS = [
    {
        "id": "combat_wins",
        "label": "Veteran's Quarry",
        "flavor": "The sleepy town of Nous has recently been under siege by an increased monster population. Cull them.",
        "event_type": "combat_win",
        "level_required": 1,
        "goals": {1: 5, 3: 15},
    },
    {
        "id": "damage_dealt",
        "label": "Trial by Force",
        "flavor": "The royal arcanists measure combat worth by raw destructive output. Prove yourself.",
        "event_type": "damage",
        "level_required": 1,
        "goals": "banded",
    },
    {
        "id": "slay_aphrodite",
        "label": "The Celestial Rampage",
        "flavor": "Aphrodite has been causing chaos in the Celestia mountains. The Council demands action.",
        "event_type": "boss_kill:aphrodite",
        "level_required": 20,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "slay_lucifer",
        "label": "The Infernal Siege",
        "flavor": "Lucifer's forces grow bold. The Ember Citadel needs champions willing to fight back.",
        "event_type": "boss_kill:lucifer",
        "level_required": 30,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "slay_gemini",
        "label": "Twin Disruption",
        "flavor": "Castor & Pollux disrupt trade routes with their synchronized assaults. Restore order.",
        "event_type": "boss_kill:gemini",
        "level_required": 40,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "slay_neet",
        "label": "Void Containment",
        "flavor": "NEET's entropic void tears at the fabric of reality near the eastern settlements. Contain it.",
        "event_type": "boss_kill:neet",
        "level_required": 50,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "slay_evelynn",
        "label": "The Crimson Silence",
        "flavor": "Evelynn moves unseen through the night, leaving only ruin in her wake. The Guild demands one thing: her head.",
        "event_type": "boss_kill:evelynn",
        "level_required": 100,
        "tier_3_only": True,
        "goals": {3: 1},
    },
    {
        "id": "slay_calcified",
        "label": "Essence Disruption",
        "flavor": "Calcified monsters have begun appearing in unusual numbers, their essence threatening local mages.",
        "event_type": "calcified_kill",
        "level_required": 30,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "slay_corrupted",
        "label": "Corruption Patrol",
        "flavor": "Corrupted creatures have breached the outer walls. Veteran hunters are called to the front.",
        "event_type": "corrupted_kill",
        "level_required": 100,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "codex_runs",
        "label": "The Archive Trial",
        "flavor": "The Codex scholars seek brave souls willing to delve into the Archive's most dangerous chambers.",
        "event_type": "codex_complete",
        "level_required": 80,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "ascent_runs",
        "label": "Tower Vigil",
        "flavor": "The Tower of Ascent calls for dedicated climbers. Each floor cleared brings glory and reward.",
        "event_type": "ascent_floor",
        "level_required": 100,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "apex_hunts",
        "label": "The Hunt Mandate",
        "flavor": "The Apex zones hunger for capable hunters. Charge accepted from those who dare the depths.",
        "event_type": "apex_complete",
        "level_required": 90,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "hatch_egg",
        "label": "Hatchery Commission",
        "flavor": "The Hatchery Guild requests field data on incubated specimens. Release and slay the creature in the wild.",
        "event_type": "egg_release",
        "level_required": 50,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "slayer_task",
        "label": "Slayer's Commission",
        "flavor": "The Slayer's Guild has posted new marks. Report to the board and carry out your assigned hunt.",
        "event_type": "slayer_task_complete",
        "level_required": 1,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "settlement_event",
        "label": "Crisis Response",
        "flavor": "Your settlement is under threat. Rally your defences and repel the intruders before they cause lasting damage.",
        "event_type": "settlement_event_complete",
        "level_required": 10,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "zeal_spent",
        "label": "Driven by Purpose",
        "flavor": "The guild masters track which settlers are truly committed to their cause. Spend your Zeal advancing the settlement.",
        "event_type": "zeal_spent",
        "level_required": 10,
        "goals": {1: 200, 3: 600},
    },
    {
        "id": "partner_recruit",
        "label": "Recruitment Drive",
        "flavor": "The Partner Guild is looking for new talent. Visit the guild and recruit to support the cause.",
        "event_type": "partner_recruit",
        "level_required": 10,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "use_refinement_rune",
        "label": "Refinement Ritual",
        "flavor": "The Weaponsmiths' Union tracks rune usage as a mark of dedication. Prove your commitment to the craft.",
        "event_type": "rune_refinement",
        "level_required": 50,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "use_shatter_rune",
        "label": "Shatter Protocol",
        "flavor": "The Armorers' Guild demands proof of reinforcement mastery. Push your gear beyond its limits.",
        "event_type": "rune_shatter",
        "level_required": 50,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "use_potential_rune",
        "label": "Potential Unleashed",
        "flavor": "The Academy of Potential requires demonstration of enchantment skill. Channel the rune's energy.",
        "event_type": "rune_potential",
        "level_required": 50,
        "goals": {1: 1, 3: 3},
    },
    {
        "id": "casino_gold",
        "label": "High Roller",
        "flavor": "The casino owners have posted a bounty for their most profitable players. Show them what winning looks like.",
        "event_type": "casino_win",
        "level_required": 1,
        "goals": {1: 15_000, 3: 100_000},
    },
]


# ---------------------------------------------------------------------------
# Damage Bands
# ---------------------------------------------------------------------------

DAMAGE_BANDS = [
    (1, 10, 500, 1_500),
    (11, 20, 1_500, 4_500),
    (21, 30, 4_500, 13_500),
    (31, 40, 15_000, 45_000),
    (41, 50, 40_000, 120_000),
    (51, 60, 120_000, 300_000),
    (61, 70, 300_000, 900_000),
    (71, 80, 250_000, 500_000),
    (81, 90, 500_000, 2_000_000),
    (91, 999, 1_000_000, 3_000_000),
]


def get_damage_goals(level: int) -> tuple:
    for lo, hi, g1, g3 in DAMAGE_BANDS:
        if lo <= level <= hi:
            return g1, g3
    return 2_500_000, 7_500_000


# ---------------------------------------------------------------------------
# Horizon Paths
# ---------------------------------------------------------------------------

HORIZON_PATHS = {
    "settlers_oath": {
        "name": "The Settler's Oath",
        "description": "The frontier needs defenders. Prove your resolve through sustained combat before claiming your right to build.",
        "event_type": "combat_win",
        "goal": 25,
        "token_reward": 2,
        "level_required": 10,
        "loot_preview": "🏗️ +2 Quest Tokens + 1 Random Settlement Material",
    },
    "celestial_calling": {
        "name": "The Celestial Calling",
        "description": "Whispers from the mountains speak of a gateway between worlds. Strengthen yourself through battle before the Celestia gates open to you.",
        "event_type": "combat_win",
        "goal": 40,
        "token_reward": 2,
        "level_required": 20,
        "loot_preview": "🗝️ +1 Random Aphrodite Key",
    },
    "infernal_pact": {
        "name": "The Infernal Pact",
        "description": "The Ember Citadel demands a blood toll. Fight until the flames acknowledge your worth.",
        "event_type": "combat_win",
        "goal": 16,
        "token_reward": 1,
        "level_required": 30,
        "loot_preview": f"{SOUL_CORE} +1 Soul Core",
    },
    "twin_accord": {
        "name": "The Twin Accord",
        "description": "Castor & Pollux recognize only those who have proven themselves in equal measure. Fight to tip the scales.",
        "event_type": "combat_win",
        "goal": 40,
        "token_reward": 2,
        "level_required": 40,
        "loot_preview": "⚖️ +1 Fragment of Balance",
    },
    "void_threshold": {
        "name": "The Void Threshold",
        "description": "Something stirs beyond the edge of the known world. Fight enough battles and the Void will take notice.",
        "event_type": "combat_win",
        "goal": 26,
        "token_reward": 2,
        "level_required": 50,
        "loot_preview": f"{VOID_FRAG} +1 Void Fragment",
    },
    "slayer": {
        "name": "The Slayer's Reckoning",
        "description": "The Slayer's Guild has posted an urgent commission. Complete 6 assigned Slayer tasks to fulfill it.",
        "event_type": "slayer_task_complete",
        "goal": 6,
        "token_reward": 4,
        "level_required": 1,
        "loot_preview": "⚔️ +3 Violent Essence",
    },
    "blood_compact": {
        "name": "The Blood Compact",
        "description": "The Blood Compact calls on hatchery handlers. Release your incubated creatures and slay them.",
        "event_type": "egg_release",
        "goal": 3,
        "token_reward": 3,
        "level_required": 50,
        "loot_preview": "🩸 +250 Primordial Blood",
    },
    "sovereign": {
        "name": "The Sovereign's Trial",
        "description": "The Sovereign Council issues a challenge: face the pinnacle Uber Bosses and emerge victorious.",
        "event_type": "uber_complete",
        "goal": 3,
        "token_reward": 4,
        "level_required": 70,
        "loot_preview": "✨ +2 Random Uber Sigils",
    },
    "alchemist": {
        "name": "The Alchemist's Obsession",
        "description": "The alchemical society has recently been investigating rumors of mutations in Spirit Stones dropped by monsters. Slay them.",
        "event_type": "combat_win",
        "goal": 50,
        "token_reward": 3,
        "level_required": 30,
        "loot_preview": f"{SPIRIT_STONE} +1 Spirit Stone",
    },
    "glutton": {
        "name": "The Glutton's Crusade",
        "description": "The monster consumption enthusiast's club have been disappointed by the quality of recent parts. Fight for worthy specimens.",
        "event_type": "combat_win",
        "goal": 50,
        "token_reward": 3,
        "level_required": 30,
        "loot_preview": "🦴 +1 Monster Part (scaled to your collection)",
    },
    "elemental": {
        "name": "The Elemental Accord",
        "description": "The elemental convergence grows unstable. Skilled hunters are sought to pacify the Elemental of Elements.",
        "event_type": "elemental_defeat",
        "goal": 2,
        "token_reward": 5,
        "level_required": 60,
        "loot_preview": "⛏️ Gathering Resources (all three skills)",
    },
    "antiquarian": {
        "name": "The Antiquarian's Trail",
        "description": "The Codex scholars seek chroniclers willing to document the Archive's most treacherous depths.",
        "event_type": "codex_complete",
        "goal": 3,
        "token_reward": 5,
        "level_required": 80,
        "loot_preview": "📚 +50 Codex Fragments",
    },
    "apex": {
        "name": "The Apex Covenant",
        "description": "The Apex Zones hunger for worthy challengers. Prove your mettle in the hunting grounds.",
        "event_type": "apex_complete",
        "goal": 5,
        "token_reward": 3,
        "level_required": 90,
        "loot_preview": "💠 +1 Random Meta Shard",
    },
    "ascent": {
        "name": "The Tower Warden's Vigil",
        "description": "The Tower Warden calls on those brave enough to scale the Ascent. Each floor cleared is a victory claimed.",
        "event_type": "ascent_floor",
        "goal": 15,
        "token_reward": 3,
        "level_required": 100,
        "loot_preview": "🔮 +1 Random Rune",
    },
}


# ---------------------------------------------------------------------------
# Check-in Day Labels
# ---------------------------------------------------------------------------

CHECKIN_DAY_LABELS = {
    1: "Curios & Tickets",
    2: "Essence Cache",
    3: "Material Cache",
    4: "Key Cache",
    5: "Curio & Tokens",
    6: "Rune Cache",
    7: "5 Curios & 5 Tickets",
    8: "Power Cache",
    9: "Tome Cache",
    10: "Elemental Cache",
    11: "Rune Cache",
    12: "Key Cache",
    13: "Tokens & Curio",
    14: "10 Curios & 10 Tickets",
}


# ---------------------------------------------------------------------------
# Token Shop
# ---------------------------------------------------------------------------

TOKEN_SHOP_ITEMS = [
    # ── Consumables ──────────────────────────────────────────────────────────
    {
        "id": "curio",
        "label": "Curio",
        "cost": 3,
        "description": "Purchase one Curious Curio.",
    },
    {
        "id": "equip_cache",
        "label": "Equipment Cache",
        "cost": 10,
        "description": "Receive 1 random equipment item at your level (capped at ilvl 100).",
    },
    {
        "id": "rune_cache",
        "label": "Rune Cache",
        "cost": 10,
        "description": "Receive 1–5 random Runes (Refinement, Potential, or Shatter).",
    },
    {
        "id": "key_cache",
        "label": "Boss Key Cache",
        "cost": 10,
        "description": "Receive 1–5 random Boss Keys.",
    },
    # ── Utility ───────────────────────────────────────────────────────────────
    {
        "id": "board_reset",
        "label": "Board Reset",
        "cost": 5,
        "description": "Clear the 20-hour contract cooldown immediately.",
    },
    # ── Permanent Upgrades ───────────────────────────────────────────────────
    {
        "id": "enrichment",
        "label": "Enrichment",
        "cost": 50,
        "description": "Permanently increase quest gold rewards by 50%. One-time unlock.",
        "one_time": True,
        "unlock_field": "enrichment_unlocked",
    },
    {
        "id": "prospector_license",
        "label": "Prospector's License",
        "cost": 50,
        "description": "Receive a free gathering materials cache on every quest turn-in. One-time unlock.",
        "one_time": True,
        "unlock_field": "prospector_unlocked",
    },
    {
        "id": "quest_veteran",
        "label": "Quest Veteran",
        "cost": 75,
        "description": "Permanently award +1 bonus token on every quest completion. One-time unlock.",
        "one_time": True,
        "unlock_field": "veteran_unlocked",
    },
    {
        "id": "extra_slot",
        "label": "Contract Extension",
        "cost": 200,
        "description": "Permanently unlock a 4th daily contract slot. One-time unlock.",
        "one_time": True,
        "unlock_field": "extra_slot_unlocked",
    },
]


# ---------------------------------------------------------------------------
# Check-in reward granting
# ---------------------------------------------------------------------------


async def grant_checkin_day(
    bot, user_id: str, server_id: str, day: int, level: int
) -> list:
    """Grant the check-in reward for the given day based on player level. Returns display strings."""
    rewards = []

    if day == 1:
        await bot.database.users.modify_currency(user_id, "curios", 3)
        await bot.database.partners.add_tickets(user_id, 3)
        rewards += ["📦 +3 Curios", "🎫 +3 Guild Tickets"]

    elif day == 2:
        if level >= 70:
            rune_pool = ["refinement_runes", "potential_runes", "shatter_runes"]
            count = random.randint(1, 3)
            runes = {}
            for _ in range(count):
                r = random.choice(rune_pool)
                runes[r] = runes.get(r, 0) + 1
            _RUNE_LABELS = {
                "refinement_runes": "Refinement Rune",
                "potential_runes": "Potential Rune",
                "shatter_runes": "Shatter Rune",
            }
            for r, n in runes.items():
                await bot.database.users.modify_currency(user_id, r, n)
                rewards.append(f"🔮 +{n} {_RUNE_LABELS[r]}{'s' if n > 1 else ''}")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        elif level >= 30:
            essence_pool = [
                "power",
                "protection",
                "insight",
                "evasion",
                "blocking",
                "deftness",
            ]
            for _ in range(3):
                etype = random.choice(essence_pool)
                await bot.database.essences.add(user_id, etype)
            rewards.append("✨ +3 Random Essences")
            await bot.database.quests.add_tokens(user_id, 1)
            rewards.append("🎫 +1 Quest Token")
        else:
            await bot.database.quests.add_tokens(user_id, 2)
            await bot.database.partners.add_tickets(user_id, 3)
            rewards += ["🎫 +2 Quest Tokens", "🎫 +3 Guild Tickets"]

    elif day == 3:
        if level >= 80:
            await bot.database.users.modify_currency(user_id, "antique_tome", 1)
            await bot.database.quests.add_tokens(user_id, 2)
            rewards += ["📖 +1 Antique Tome", "🎫 +2 Quest Tokens"]
        elif level >= 50:
            mat_pool = ["magma_core", "life_root", "spirit_shard"]
            count = random.randint(1, 3)
            mats = {}
            for _ in range(count):
                m = random.choice(mat_pool)
                mats[m] = mats.get(m, 0) + 1
            _MAT_LABELS = {
                "magma_core": "Magma Core",
                "life_root": "Life Root",
                "spirit_shard": "Spirit Shard",
            }
            for m, n in mats.items():
                await bot.database.settlement_materials.modify(user_id, m, n)
                rewards.append(f"🪨 +{n} {_MAT_LABELS[m]}{'s' if n > 1 else ''}")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        else:
            await bot.database.quests.add_tokens(user_id, 2)
            await bot.database.partners.add_tickets(user_id, 3)
            rewards += ["🎫 +2 Quest Tokens", "🎫 +3 Guild Tickets"]

    elif day == 4:
        if level >= 60:
            elemental_funcs = [
                bot.database.skills.increment_blessed_bismuth,
                bot.database.skills.increment_sparkling_sprig,
                bot.database.skills.increment_capricious_carp,
            ]
            fn = random.choice(elemental_funcs)
            await fn(user_id, server_id, 1)
            rewards.append("🔑 +1 Random Elemental Key")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        elif level >= 40:
            key = random.choice(["dragon_key", "angel_key"])
            await bot.database.users.modify_currency(user_id, key, 1)
            label = "Dragon Key" if key == "dragon_key" else "Angel Key"
            rewards.append(f"🗝️ +1 {label}")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        else:
            await bot.database.quests.add_tokens(user_id, 2)
            await bot.database.users.modify_currency(user_id, "curios", 1)
            rewards += ["🎫 +2 Quest Tokens", "📦 +1 Curio"]

    elif day == 5:
        await bot.database.users.modify_currency(user_id, "curios", 1)
        await bot.database.quests.add_tokens(user_id, 2)
        rewards += ["📦 +1 Curio", "🎫 +2 Quest Tokens"]

    elif day == 6:
        if level >= 70:
            rune_pool = ["refinement_runes", "potential_runes", "shatter_runes"]
            count = random.randint(1, 2)
            runes = {}
            for _ in range(count):
                r = random.choice(rune_pool)
                runes[r] = runes.get(r, 0) + 1
            _RUNE_LABELS = {
                "refinement_runes": "Refinement Rune",
                "potential_runes": "Potential Rune",
                "shatter_runes": "Shatter Rune",
            }
            for r, n in runes.items():
                await bot.database.users.modify_currency(user_id, r, n)
                rewards.append(f"🔮 +{n} {_RUNE_LABELS[r]}{'s' if n > 1 else ''}")
            await bot.database.users.modify_currency(user_id, "curios", 1)
            rewards.append("📦 +1 Curio")
        elif level >= 30:
            essence_pool = [
                "power",
                "protection",
                "insight",
                "evasion",
                "blocking",
                "deftness",
            ]
            for _ in range(2):
                etype = random.choice(essence_pool)
                await bot.database.essences.add(user_id, etype)
            rewards.append("✨ +2 Random Essences")
            await bot.database.quests.add_tokens(user_id, 1)
            rewards.append("🎫 +1 Quest Token")
        else:
            await bot.database.quests.add_tokens(user_id, 2)
            await bot.database.partners.add_tickets(user_id, 3)
            rewards += ["🎫 +2 Quest Tokens", "🎫 +3 Guild Tickets"]

    elif day == 7:
        await bot.database.users.modify_currency(user_id, "curios", 5)
        await bot.database.partners.add_tickets(user_id, 5)
        rewards += ["📦 +5 Curios", "🎫 +5 Guild Tickets"]

    elif day == 8:
        if level >= 100:
            await bot.database.users.modify_currency(user_id, "pinnacle_key", 1)
            await bot.database.quests.add_tokens(user_id, 2)
            rewards += ["👑 +1 Pinnacle Key", "🎫 +2 Quest Tokens"]
        elif level >= 60:
            elemental_funcs = [
                bot.database.skills.increment_blessed_bismuth,
                bot.database.skills.increment_sparkling_sprig,
                bot.database.skills.increment_capricious_carp,
            ]
            fn = random.choice(elemental_funcs)
            await fn(user_id, server_id, 1)
            rewards.append("🔑 +1 Random Elemental Key")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        elif level >= 30:
            essence_pool = [
                "power",
                "protection",
                "insight",
                "evasion",
                "blocking",
                "deftness",
            ]
            for _ in range(3):
                etype = random.choice(essence_pool)
                await bot.database.essences.add(user_id, etype)
            rewards.append("✨ +3 Random Essences")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        else:
            await bot.database.quests.add_tokens(user_id, 3)
            await bot.database.partners.add_tickets(user_id, 3)
            rewards += ["🎫 +3 Quest Tokens", "🎫 +3 Guild Tickets"]

    elif day == 9:
        if level >= 80:
            await bot.database.users.modify_currency(user_id, "antique_tome", 1)
            await bot.database.users.modify_currency(user_id, "curios", 1)
            rewards += ["📖 +1 Antique Tome", "📦 +1 Curio"]
        elif level >= 70:
            rune_pool = ["refinement_runes", "potential_runes", "shatter_runes"]
            count = random.randint(1, 3)
            runes = {}
            for _ in range(count):
                r = random.choice(rune_pool)
                runes[r] = runes.get(r, 0) + 1
            _RUNE_LABELS = {
                "refinement_runes": "Refinement Rune",
                "potential_runes": "Potential Rune",
                "shatter_runes": "Shatter Rune",
            }
            for r, n in runes.items():
                await bot.database.users.modify_currency(user_id, r, n)
                rewards.append(f"🔮 +{n} {_RUNE_LABELS[r]}{'s' if n > 1 else ''}")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        else:
            await bot.database.quests.add_tokens(user_id, 2)
            await bot.database.users.modify_currency(user_id, "curios", 1)
            rewards += ["🎫 +2 Quest Tokens", "📦 +1 Curio"]

    elif day == 10:
        if level >= 60:
            elemental_funcs = [
                bot.database.skills.increment_blessed_bismuth,
                bot.database.skills.increment_sparkling_sprig,
                bot.database.skills.increment_capricious_carp,
            ]
            fn = random.choice(elemental_funcs)
            await fn(user_id, server_id, 1)
            rewards.append("🔑 +1 Random Elemental Key")
            await bot.database.users.modify_currency(user_id, "curios", 1)
            rewards.append("📦 +1 Curio")
        elif level >= 50:
            mat_pool = ["magma_core", "life_root", "spirit_shard"]
            count = random.randint(1, 3)
            mats = {}
            for _ in range(count):
                m = random.choice(mat_pool)
                mats[m] = mats.get(m, 0) + 1
            _MAT_LABELS = {
                "magma_core": "Magma Core",
                "life_root": "Life Root",
                "spirit_shard": "Spirit Shard",
            }
            for m, n in mats.items():
                await bot.database.settlement_materials.modify(user_id, m, n)
                rewards.append(f"🪨 +{n} {_MAT_LABELS[m]}{'s' if n > 1 else ''}")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        else:
            await bot.database.quests.add_tokens(user_id, 2)
            await bot.database.partners.add_tickets(user_id, 3)
            rewards += ["🎫 +2 Quest Tokens", "🎫 +3 Guild Tickets"]

    elif day == 11:
        if level >= 100:
            await bot.database.users.modify_currency(user_id, "pinnacle_key", 1)
            await bot.database.users.modify_currency(user_id, "curios", 1)
            rewards += ["👑 +1 Pinnacle Key", "📦 +1 Curio"]
        elif level >= 70:
            rune_pool = ["refinement_runes", "potential_runes", "shatter_runes"]
            count = random.randint(1, 3)
            runes = {}
            for _ in range(count):
                r = random.choice(rune_pool)
                runes[r] = runes.get(r, 0) + 1
            _RUNE_LABELS = {
                "refinement_runes": "Refinement Rune",
                "potential_runes": "Potential Rune",
                "shatter_runes": "Shatter Rune",
            }
            for r, n in runes.items():
                await bot.database.users.modify_currency(user_id, r, n)
                rewards.append(f"🔮 +{n} {_RUNE_LABELS[r]}{'s' if n > 1 else ''}")
            await bot.database.users.modify_currency(user_id, "curios", 1)
            rewards.append("📦 +1 Curio")
        elif level >= 30:
            essence_pool = [
                "power",
                "protection",
                "insight",
                "evasion",
                "blocking",
                "deftness",
            ]
            for _ in range(3):
                etype = random.choice(essence_pool)
                await bot.database.essences.add(user_id, etype)
            rewards.append("✨ +3 Random Essences")
            await bot.database.quests.add_tokens(user_id, 2)
            rewards.append("🎫 +2 Quest Tokens")
        else:
            await bot.database.quests.add_tokens(user_id, 3)
            await bot.database.partners.add_tickets(user_id, 3)
            rewards += ["🎫 +3 Quest Tokens", "🎫 +3 Guild Tickets"]

    elif day == 12:
        if level >= 50:
            await bot.database.users.modify_currency(user_id, "void_keys", 1)
            await bot.database.quests.add_tokens(user_id, 2)
            rewards += ["🔑 +1 Void Key", "🎫 +2 Quest Tokens"]
        elif level >= 40:
            key = random.choice(["dragon_key", "angel_key"])
            await bot.database.users.modify_currency(user_id, key, 1)
            label = "Dragon Key" if key == "dragon_key" else "Angel Key"
            rewards.append(f"🗝️ +1 {label}")
            await bot.database.quests.add_tokens(user_id, 3)
            rewards.append("🎫 +3 Quest Tokens")
        else:
            await bot.database.quests.add_tokens(user_id, 3)
            await bot.database.users.modify_currency(user_id, "curios", 1)
            rewards += ["🎫 +3 Quest Tokens", "📦 +1 Curio"]

    elif day == 13:
        await bot.database.quests.add_tokens(user_id, 3)
        await bot.database.users.modify_currency(user_id, "curios", 1)
        rewards += ["🎫 +3 Quest Tokens", "📦 +1 Curio"]

    elif day == 14:
        await bot.database.users.modify_currency(user_id, "curios", 10)
        await bot.database.partners.add_tickets(user_id, 10)
        rewards += ["📦 +10 Curios", "🎫 +10 Guild Tickets"]

    return rewards
