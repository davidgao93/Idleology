import random

from core.images import (
    ALCHEMY_HUB,
    APEX_HUB,
    CODEX_HUB,
    COMBAT_ELEMENTAL,
    COMPANIONS_HUB,
    CORRUPTION_GATE,
    HEMATURGY,
    MAW_MAIN,
    PARTNERS_HUB,
    TAVERN_KEEPER,
    UPGRADE_FORGE,
)
from core.items.models import Weapon

# ---------------------------------------------------------------------------
# Per-milestone grant functions
# ---------------------------------------------------------------------------


async def _grant_level_1(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_stat(user_id, "potions", 20)
    starter = Weapon(
        user=user_id,
        name="Adventurer's Blade",
        level=1,
        attack=3,
        defence=1,
        rarity=2,
        passive="none",
        description="",
        p_passive="none",
        u_passive="none",
        hit_chance=0.65,
        crit_chance=0.05,
        crit_multi=2.0,
        base_rarity=2,
    )
    await bot.database.equipment.create_weapon(starter)
    return [
        "⚔️ **Adventurer's Blade** (starter weapon added to inventory)",
        "🧪 **+20 Potions**",
    ]


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
    await bot.database.skills.increment_capricious_carp(user_id, server_id, 1)
    await bot.database.skills.increment_sparkling_sprig(user_id, server_id, 1)
    await bot.database.skills.increment_blessed_bismuth(user_id, server_id, 1)
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


# ---------------------------------------------------------------------------
# Milestone table
# ---------------------------------------------------------------------------
# Fields:
#   level        — the milestone level
#   title        — short label shown in the select menu
#   reward_desc  — one-line summary of the reward
#   systems      — systems unlocked at this tier (display only)
#   commands     — slash commands that become available (display only)
#   image        — embed image URL from core.images
#   grant        — async (bot, user_id, server_id) -> list[str]
# ---------------------------------------------------------------------------

MILESTONES = [
    {
        "level": 1,
        "title": "The Beginning",
        "reward_desc": "Adventurer's Blade (starter weapon) + 20 Potions",
        "systems": [
            "Combat — fight monsters to earn gold, XP, and equipment drops",
            "Gathering Skills — mine ore, fish, and chop wood passively while idle",
            "Daily Quests — take contracts from the board for tokens and gold",
            "Slayer Tasks — the Slayer Master assigns species to hunt for bonus rewards",
            "Tavern Gambling — risk your gold for a chance at big rewards",
            "Equipment Management — collect, equip, and upgrade your gear",
            "Shop — buy potions for the long road ahead",
            "Consume — consume monster body parts to empower your spirit",
            "Help — see all available commands, although some you might be ready to use yet",
        ],
        "commands": [
            "/combat",
            "/gather",
            "/quests",
            "/slayer",
            "/gamble",
            "/gear",
            "/consume",
            "/shop",
            "/help",
        ],
        "image": TAVERN_KEEPER,
        "grant": _grant_level_1,
    },
    {
        "level": 10,
        "title": "New Connections",
        "reward_desc": "10 Guild Tickets",
        "systems": [
            "Partner Guild — recruit NPC allies; deploy them in combat or send on dispatch tasks",
            "Trade System — exchange items and gold with other adventurers",
            "Settlement System — found your ideology's home base for passive resource production, the Black Market, and more",
        ],
        "commands": ["/partner", "/trade", "/settlement"],
        "image": PARTNERS_HUB,
        "grant": _grant_level_10,
    },
    {
        "level": 20,
        "title": "The Infinite Maw",
        "reward_desc": "3 Curios + 50,000 Gold",
        "systems": [
            "Maw of Infinity — weekly world boss; deal damage over the week for rewards",
            "Bosses — Aphrodite (and Uber Aphrodite) unlocked; you might encounter her in Combat",
        ],
        "commands": ["/maw", "/uber"],
        "image": MAW_MAIN,
        "grant": _grant_level_20,
    },
    {
        "level": 30,
        "title": "Essence & Alchemy",
        "reward_desc": "3 Essences of Power + 100,000 Gold",
        "systems": [
            "Calcified Monsters — rare calcified enemies drop Essences to socket into equipment",
            "Alchemy — transmute, sythesize, and upgrade your potions",
            "Bosses — Lucifer (and Uber Lucifer) unlocked; you might encounter him in Combat",
        ],
        "commands": ["/consume", "/gear", "/alchemy"],
        "image": ALCHEMY_HUB,
        "grant": _grant_level_30,
    },
    {
        "level": 40,
        "title": "Bonds & Balance",
        "reward_desc": "3 Random Boss Keys + 150,000 Gold",
        "systems": [
            "Companion System — raise creatures that passively boost your combat stats",
            "Bosses — Gemini (and Uber Gemini) unlocked; you might encounter them in Combat",
        ],
        "commands": ["/companions"],
        "image": COMPANIONS_HUB,
        "grant": _grant_level_40,
    },
    {
        "level": 50,
        "title": "Blood and Void",
        "reward_desc": "1 Void Key + 200,000 Gold",
        "systems": [
            "Hematurgy — spend blood to unlock and upgrade powerful passive abilities (requires Hatchery in your settlement)",
            "NEET Gate — fourth Uber Boss unlocked",
            "Voidforge — infuse weapons with Void passives using Void Crystals",
        ],
        "commands": ["/hematurgy"],
        "image": HEMATURGY,
        "grant": _grant_level_50,
    },
    {
        "level": 60,
        "title": "Elemental Forces",
        "reward_desc": "1 Capricious Carp + 1 Sparkling Sprig + 1 Blessed Bismuth",
        "systems": [
            "Elemental of Elements — a powerful gathering boss encountered while fishing, mining, or woodcutting; defeating it rewards rare Elemental Keys",
        ],
        "commands": ["/gather", "/fish", "/chop"],
        "image": COMBAT_ELEMENTAL,
        "grant": _grant_level_60,
    },
    {
        "level": 70,
        "title": "Veteran's Cache",
        "reward_desc": "500,000 Gold + 2–4 Random Runes",
        "systems": [],
        "commands": [],
        "image": UPGRADE_FORGE,
        "grant": _grant_level_70,
    },
    {
        "level": 80,
        "title": "The Codex",
        "reward_desc": "1 Antique Tome",
        "systems": [
            "Codex — wave survival mode; complete runs to earn Tomes that permanently multiply your stats",
        ],
        "commands": ["/codex"],
        "image": CODEX_HUB,
        "grant": _grant_level_80,
    },
    {
        "level": 90,
        "title": "The Edge of Everything",
        "reward_desc": "500,000 Gold",
        "systems": [
            "Apex Hunts — fight escalating Apex monsters for exclusive meta shards and rewards",
            "Soul System — collect Soul Cores from Apex hunts to power permanent soul upgrades",
        ],
        "commands": ["/apex", "/soul"],
        "image": APEX_HUB,
        "grant": _grant_level_90,
    },
    {
        "level": 100,
        "title": "Pinnacle",
        "reward_desc": "1 Pinnacle Key",
        "systems": [
            "Corrupted Monsters — high-danger combat encounters with corrupted drops",
            "Ascent Mode — climb numbered floors for permanent stat bonuses; Evelynn (final Uber) unlocked",
        ],
        "commands": ["/ascent"],
        "image": CORRUPTION_GATE,
        "grant": _grant_level_100,
    },
]
