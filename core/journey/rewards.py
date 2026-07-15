import random

from core.emojis import (
    BLESSED_BISMUTH,
    CAPRICIOUS_CARP,
    CODEX_TOME_EMOJI,
    GOLD_COIN,
    SPARKLING_SPRIG,
)
from core.images import (
    ALCHEMY_HUB,
    APEX_HUB,
    ARBITER_PORTRAIT,
    CODEX_HUB,
    COMBAT_ELEMENTAL,
    COMPANIONS_HUB,
    CORRUPTION_GATE,
    HEMATURGY,
    MAW_MAIN,
    PARTNERS_HUB,
    QUEST_BOARD,
    TAVERN_KEEPER,
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


async def _grant_level_5(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_currency(user_id, "curios", 2)
    await bot.database.users.modify_gold(user_id, 10_000)
    return ["📦 **+2 Curios**", f"{GOLD_COIN} **+10,000 Gold**"]


async def _grant_level_10(bot, user_id: str, server_id: str) -> list:
    await bot.database.partners.ensure_items_row(user_id)
    await bot.database.partners.add_tickets(user_id, 10)
    return ["🎫 **+10 Guild Tickets**"]


async def _grant_level_20(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_currency(user_id, "curios", 3)
    await bot.database.users.modify_gold(user_id, 50_000)
    return ["📦 **+3 Curios**", f"{GOLD_COIN} **+50,000 Gold**"]


async def _grant_level_30(bot, user_id: str, server_id: str) -> list:
    for _ in range(3):
        await bot.database.essences.add(user_id, "power")
    await bot.database.users.modify_gold(user_id, 100_000)
    return ["🔆 **+3 Essences of Power**", f"{GOLD_COIN} **+100,000 Gold**"]


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
    return key_lines + [f"{GOLD_COIN} **+150,000 Gold**"]


async def _grant_level_50(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_currency(user_id, "void_keys", 1)
    await bot.database.users.modify_gold(user_id, 200_000)
    return ["🔑 **+1 Void Key**", f"{GOLD_COIN} **+200,000 Gold**"]


async def _grant_level_60(bot, user_id: str, server_id: str) -> list:
    await bot.database.skills.increment_capricious_carp(user_id, server_id, 1)
    await bot.database.skills.increment_sparkling_sprig(user_id, server_id, 1)
    await bot.database.skills.increment_blessed_bismuth(user_id, server_id, 1)
    return [
        f"{CAPRICIOUS_CARP} **+1 Capricious Carp**",
        f"{SPARKLING_SPRIG} **+1 Sparkling Sprig**",
        f"{BLESSED_BISMUTH} **+1 Blessed Bismuth**",
    ]


_SIGIL_POOL = [
    ("celestial", "Celestial Sigil"),
    ("infernal", "Infernal Sigil"),
    ("gemini", "Bound Sigil"),
    ("corruption", "Corruption Sigil"),
]

_SIGIL_INCREMENT = {
    "celestial": lambda bot, uid, sid: bot.database.uber.increment_sigils(uid, sid, 1),
    "infernal": lambda bot, uid, sid: bot.database.uber.increment_infernal_sigils(
        uid, sid, 1
    ),
    "gemini": lambda bot, uid, sid: bot.database.uber.increment_gemini_sigils(
        uid, sid, 1
    ),
    "corruption": lambda bot, uid, sid: bot.database.uber.increment_corruption_sigils(
        uid, sid, 1
    ),
}


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
    await bot.database.uber.get_uber_progress(user_id, server_id)
    sigil_key, sigil_label = random.choice(_SIGIL_POOL)
    await _SIGIL_INCREMENT[sigil_key](bot, user_id, server_id)
    return rune_lines + [f"{GOLD_COIN} **+500,000 Gold**", f"🔱 **+1 {sigil_label}**"]


async def _grant_level_80(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_currency(user_id, "antique_tome", 1)
    return [f"{CODEX_TOME_EMOJI} **+1 Antique Tome**"]


async def _grant_level_90(bot, user_id: str, server_id: str) -> list:
    await bot.database.users.modify_gold(user_id, 500_000)
    return [f"{GOLD_COIN} **+500,000 Gold**"]


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
            "Gathering Skills — mine ore (/gather), fish (/fish), and chop wood (/chop) passively while idle",
            "Equipment Management — collect, equip, and upgrade your gear; per-slot commands (/weapons, /armor, /accessory, /gloves, /boots, /helmets) are in /help",
            "Tavern — buy potions from the shop and rest to recover HP",
            "Adventurer License — your character card and identity",
            "Help — see all available commands, although some you might not be ready to use yet",
        ],
        "commands": [
            "/combat",
            "/gather",
            "/fish",
            "/chop",
            "/gear",
            "/inventory",
            "/shop",
            "/rest",
            "/card",
            "/help",
        ],
        "image": TAVERN_KEEPER,
        "grant": _grant_level_1,
    },
    {
        "level": 5,
        "title": "Finding Your Feet",
        "reward_desc": "2 Curios + 10,000 Gold",
        "systems": [
            "Daily Quests — take contracts from the board for tokens and gold",
            "Slayer Tasks — the Slayer Master assigns species to hunt for bonus rewards",
            "Curios — mystery caches earned from combat and quests; open them here",
            "Delve — a tactical mining expedition mini-game with upgradeable equipment",
            "Consume — consume monster body parts to empower your spirit",
            "Tavern Gambling — risk your gold for a chance at big rewards",
            "Character Sheet — inspect your stats, allocate points, and review passives",
            "Cooldowns — track your long-term timers at a glance",
        ],
        "commands": [
            "/quests",
            "/slayer",
            "/curios",
            "/delve",
            "/consume",
            "/gamble",
            "/sheet",
            "/stats",
            "/allocate_stats",
            "/passives",
            "/cooldowns",
        ],
        "image": QUEST_BOARD,
        "grant": _grant_level_5,
    },
    {
        "level": 10,
        "title": "New Connections",
        "reward_desc": "10 Guild Tickets",
        "systems": [
            "Partner Guild — recruit NPC allies; deploy them in combat or send on dispatch tasks",
            "Trade System — exchange items and gold with other adventurers",
            "Ideology — found or join an ideology; spread it with /propagate",
            "Settlement System — found your ideology's home base for passive resource production, the Black Market, and more",
            "Duels — challenge another player to a gold duel",
            "Daily Check-in — claim rewards from a 14-day rotating track just for showing up",
            "Nether Market — buy, sell, and plunder curiosities in a player-driven economy mini-game",
        ],
        "commands": [
            "/partner",
            "/trade",
            "/ideology",
            "/propagate",
            "/settlement",
            "/duel",
            "/checkin",
            "/nether",
        ],
        "image": PARTNERS_HUB,
        "grant": _grant_level_10,
    },
    {
        "level": 20,
        "title": "The Infinite Maw",
        "reward_desc": "3 Curios + 50,000 Gold",
        "systems": [
            "Maw of Infinity — weekly world boss; deal damage over the week for rewards",
            "Bosses — Aphrodite unlocked; you might encounter her in Combat",
            "Leaderboard — see how you stack up on the server hiscores",
        ],
        "commands": ["/maw", "/leaderboard"],
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
            "Bosses — Lucifer unlocked; you might encounter him in Combat",
            "Inner Sanctum — permanent combat mastery tree; Vice (loot bias) and Recovery (stamina/survivability) paths unlocked",
        ],
        "commands": ["/alchemy", "/gear", "/inner_sanctum"],
        "image": ALCHEMY_HUB,
        "grant": _grant_level_30,
    },
    {
        "level": 40,
        "title": "Bonds & Balance",
        "reward_desc": "3 Random Boss Keys + 150,000 Gold",
        "systems": [
            "Companion System — raise creatures that passively boost your stats",
            "Bosses — Gemini unlocked; you might encounter them in Combat",
            "Loadouts — save and swap full gear sets in one click",
            "Hall of Firsts — a reminder to check `/hallofirsts` — see who was first to claim each server-wide legend",
        ],
        "commands": ["/companions", "/loadouts", "/hallofirsts"],
        "image": COMPANIONS_HUB,
        "grant": _grant_level_40,
    },
    {
        "level": 50,
        "title": "Blood and Void",
        "reward_desc": "1 Void Key + 200,000 Gold",
        "systems": [
            "Hematurgy — spend blood to unlock and upgrade powerful passive abilities (requires Hatchery in your settlement)",
            "Hatchery — incubate monster eggs in your settlement and release the hatchlings for Hematurgy blood",
            "NEET Gate — NEET unlocked; you might encounter him in Combat",
            "Voidforge — infuse weapons with additional passives via the void",
        ],
        "commands": ["/hematurgy", "/hatchery"],
        "image": HEMATURGY,
        "grant": _grant_level_50,
    },
    {
        "level": 60,
        "title": "Elemental Forces",
        "reward_desc": "1 Capricious Carp + 1 Sparkling Sprig + 1 Blessed Bismuth",
        "systems": [
            "Elemental of Elements — a powerful gathering boss available through Elemental Keys; fighting it grants huge amounts of gathering resources",
            "Dojo — be sure to test your DPS against a customizable training dummy",
            "Player Settings — reminder to check your settings, toggle boss doors, EXP protection, auto-pay rest, and more",
        ],
        "commands": ["/dojo", "/player_settings"],
        "image": COMBAT_ELEMENTAL,
        "grant": _grant_level_60,
    },
    {
        "level": 70,
        "title": "The Arbiter's Trial",
        "reward_desc": "500,000 Gold + 2–4 Random Runes + 1 Random Uber Sigil",
        "systems": [
            "Uber Encounters — face the pinnacle bosses: Aphrodite, Lucifer, NEET, Gemini, and Evelynn for exclusive sigils and engrams",
            "Corrupted Monsters — high-danger combat encounters that drop Paradise Jewels and face Evelynn",
            "Paradise — Cut Jewels of Paradise and unlock powerful combat skills with Tessara the lapidary",
        ],
        "commands": ["/uber", "/paradise"],
        "image": ARBITER_PORTRAIT,
        "grant": _grant_level_70,
    },
    {
        "level": 80,
        "title": "The Codex",
        "reward_desc": "1 Antique Tome",
        "systems": [
            "Codex — wave survival mode; complete runs to earn Tomes with powerful passives",
        ],
        "commands": ["/codex"],
        "image": CODEX_HUB,
        "grant": _grant_level_80,
    },
    {
        "level": 90,
        "title": "Monster Safari",
        "reward_desc": "500,000 Gold",
        "systems": [
            "Apex Hunts — fight terrifying Apex monsters for exclusive rewards",
            "Soul System — collect Soul Cores from Apex hunts to power permanent upgrades",
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
            "Ascent Mode — climb numbered floors for permanent stat bonuses",
            "Prestige Hall — available since Level 1, but its titles, emblems, avatars, renames, and monument quotes cost hundreds of millions of gold, so most players can only afford to start spending here",
            "Rite of Convergence — the ultimate endgame raid; collect all 5 Rite keys from Uber and Corrupted encounters to enter",
        ],
        "commands": ["/ascent", "/prestige", "/rite", "/artefact"],
        "image": CORRUPTION_GATE,
        "grant": _grant_level_100,
    },
]
