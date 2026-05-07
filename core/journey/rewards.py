import random


# ---------------------------------------------------------------------------
# Milestone definitions
# ---------------------------------------------------------------------------
# Each entry:
#   level          — the milestone level
#   reward_desc    — short display string shown in the journey embed
#   systems        — list of system names unlocked at this tier (display only)
#   grant          — async (bot, user_id, server_id) -> list[str]  (returns log lines)
# ---------------------------------------------------------------------------

async def _grant_level_1(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_stat(user_id, "potions", 20)
    return ["🧪 **+20 Potions**"]


async def _grant_level_10(bot, user_id: str, server_id: str) -> list:
    await bot.database.partners.ensure_items_row(user_id)
    await bot.database.partners.add_tickets(user_id, 10)
    return ["🎫 **+10 Guild Tickets**"]


async def _grant_level_20(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_currency(user_id, "curios", 3)
    await bot.database.users.modify_gold(user_id, 50_000)
    return ["📦 **+3 Curios**", "💰 **+50,000 Gold**"]


async def _grant_level_30(bot, user_id: str, server_id: str) -> list:
    for _ in range(3):
        await bot.database.essences.add(user_id, "power")
    await bot.database.users.modify_gold(user_id, 100_000)
    return ["🔆 **+3 Essences of Power**", "💰 **+100,000 Gold**"]


async def _grant_level_40(bot, user_id: str, server_id: str) -> list:
    key_pool = ["dragon_key", "angel_key"]
    keys_granted: dict[str, int] = {}
    for _ in range(3):
        chosen = random.choice(key_pool)
        await bot.database.users.modify_currency(user_id, chosen, 1)
        keys_granted[chosen] = keys_granted.get(chosen, 0) + 1
    await bot.database.users.modify_gold(user_id, 150_000)
    key_lines = [
        f"🗝️ **+{count} {'Dragon' if k == 'dragon_key' else 'Angel'} Key{'s' if count > 1 else ''}**"
        for k, count in keys_granted.items()
    ]
    return key_lines + ["💰 **+150,000 Gold**"]


async def _grant_level_50(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_currency(user_id, "void_keys", 1)
    await bot.database.users.modify_gold(user_id, 200_000)
    return ["🔑 **+1 Void Key**", "💰 **+200,000 Gold**"]


async def _grant_level_60(bot, user_id: str, server_id: str) -> list:
    await bot.database.uber.increment_capricious_carp(user_id, server_id, 1)
    await bot.database.uber.increment_sparkling_sprig(user_id, server_id, 1)
    await bot.database.uber.increment_blessed_bismuth(user_id, server_id, 1)
    return [
        "🐟 **+1 Capricious Carp**",
        "🌿 **+1 Sparkling Sprig**",
        "💎 **+1 Blessed Bismuth**",
    ]


async def _grant_level_70(bot, user_id: str, server_id: str) -> list:
    rune_pool = ["refinement_runes", "shatter_runes", "potential_runes"]
    rune_count = random.randint(2, 4)
    runes_granted: dict[str, int] = {}
    for _ in range(rune_count):
        chosen = random.choice(rune_pool)
        await bot.database.users.modify_currency(user_id, chosen, 1)
        runes_granted[chosen] = runes_granted.get(chosen, 0) + 1
    await bot.database.users.modify_gold(user_id, 500_000)
    _RUNE_LABELS = {
        "refinement_runes": "Refinement Rune",
        "shatter_runes": "Shatter Rune",
        "potential_runes": "Potential Rune",
    }
    rune_lines = [
        f"🔮 **+{count} {_RUNE_LABELS[r]}{'s' if count > 1 else ''}**"
        for r, count in runes_granted.items()
    ]
    return rune_lines + ["💰 **+500,000 Gold**"]


async def _grant_level_80(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_currency(user_id, "antique_tome", 1)
    return ["📖 **+1 Antique Tome**"]


async def _grant_level_90(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_gold(user_id, 500_000)
    return ["💰 **+500,000 Gold**"]


async def _grant_level_100(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_currency(user_id, "pinnacle_key", 1)
    return ["👑 **+1 Pinnacle Key**"]


MILESTONES = [
    {
        "level": 1,
        "reward_desc": "20 Potions",
        "systems": ["Combat", "Gathering Skills", "Tavern Gambling", "Equipment Management"],
        "grant": _grant_level_1,
    },
    {
        "level": 10,
        "reward_desc": "10 Guild Tickets",
        "systems": ["Partner Guild", "Trade System"],
        "grant": _grant_level_10,
    },
    {
        "level": 20,
        "reward_desc": "3 Curios + 50,000 Gold",
        "systems": ["Maw of Infinity", "Aphrodite Gate"],
        "grant": _grant_level_20,
    },
    {
        "level": 30,
        "reward_desc": "3 Essences of Power + 100,000 Gold",
        "systems": ["Calcified Monsters (Essences)", "Lucifer Gate"],
        "grant": _grant_level_30,
    },
    {
        "level": 40,
        "reward_desc": "3 Random Boss Keys + 150,000 Gold",
        "systems": ["Companion System", "Gemini Gate"],
        "grant": _grant_level_40,
    },
    {
        "level": 50,
        "reward_desc": "1 Void Key + 200,000 Gold",
        "systems": ["Settlement System", "NEET Gate", "Voidforge"],
        "grant": _grant_level_50,
    },
    {
        "level": 60,
        "reward_desc": "1 Capricious Carp + 1 Sparkling Sprig + 1 Blessed Bismuth",
        "systems": ["Elemental Encounters"],
        "grant": _grant_level_60,
    },
    {
        "level": 70,
        "reward_desc": "500,000 Gold + 2–4 Random Runes",
        "systems": [],
        "grant": _grant_level_70,
    },
    {
        "level": 80,
        "reward_desc": "1 Antique Tome",
        "systems": ["Codex"],
        "grant": _grant_level_80,
    },
    {
        "level": 90,
        "reward_desc": "500,000 Gold",
        "systems": [],
        "grant": _grant_level_90,
    },
    {
        "level": 100,
        "reward_desc": "1 Pinnacle Key",
        "systems": ["Corrupted Monsters", "Ascent Mode"],
        "grant": _grant_level_100,
    },
]
