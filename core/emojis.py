# Centralised custom emoji registry.
# All custom Discord emoji tags live here — never hardcode `<:name:id>` elsewhere.
#
# These are "application emojis": uploaded once via the Discord Developer Portal
# (or the API) to the bot's application, rather than to any one server. They
# render in messages/components sent by the bot in ANY server it's in — no
# per-guild emoji slot or "Use External Emojis" permission needed.
#
# Run `python scripts/sync_emojis.py` after uploading a new emoji to see which
# constants below are stale and which live application emojis aren't registered
# yet — that's the fastest way to "preview" one without a running bot.

MONSTER_CHEEK = "<:monster_cheeks:1524223653330554890>"
GOLD_ORE = "<:gold_ore:1524223636624379924>"
PLATINUM_ORE = "<:platinum_ore:1524223622044975115>"
QUENCH = "<:quench_potion:1524223620786819204>"

# ── Gathering materials ─────────────────────────────────────────────────────
IRON_ORE = "<:iron_ore:1524223630509211658>"
COAL_ORE = "<:coal:1524223652218933438>"
IDEA_ORE = "<:idea_ore:1524223632476209162>"
BARS_REFINED = "<:refined_bars:1524223657679917206>"  # shared icon for all bar tiers
OAK_LOGS = "<:oak_log:1524223624561819820>"
WILLOW_LOGS = "<:willow_log:1524223586448052334>"
MAHOGANY_LOGS = "<:mahogany_log:1524223626230890516>"
MAGIC_LOGS = "<:magic_log:1524223627506221086>"
IDEA_LOGS = "<:idea_log:1524223633239572490>"
DESICCATED_BONES = "<:desiccated_bones:1524223649455018075>"
REGULAR_BONES = "<:regular_bone:1524223620157673594>"
STURDY_BONES = "<:sturdy_bone:1524223591506378894>"
REINFORCED_BONES = "<:reinforced_bone:1524223618572226660>"
TITANIUM_BONES = "<:titanium_bone:1524223589711216640>"

# ── Boss keys / high-value materials ────────────────────────────────────────
DRAGON_KEY = "<:draconic_key:1524223647688949940>"
ANGEL_KEY = "<:angelic_key:1524223659265364028>"
SOUL_CORE = "<:soul_core:1524223609328111666>"
VOID_FRAG = "<:void_frag:1524223588507324539>"
BLESSED_BISMUTH = "<:blessed_bismuth:1524223656841056367>"
SPARKLING_SPRIG = "<:sparkling_sprig:1524223605397917786>"
CAPRICIOUS_CARP = "<:capricious_carp:1524223653993120015>"

# ── Equipment slots (see core/inventory/views/_slot_defs.py: SLOT_EMOJIS) ───
WEAPON_SLOT = "<:weapon:1524223586951237722>"
ARMOR_SLOT = "<:armor:1524223658422440056>"
HELMET_SLOT = "<:helmet:1524223634988601474>"
GLOVE_SLOT = "<:gloves:1524223644098756779>"
BOOT_SLOT = "<:boots:1524223655381303456>"
ACCESSORY_SLOT = "<:accessory:1524223660104355870>"

# ── Combat stats (profile stat sheet + in-combat stat lines) ───────────────
STAT_ATK = "<:stat_atk:1524223599618035742>"
STAT_DEF = "<:stat_def:1524223597047185429>"
STAT_HP = "<:stat_hp:1524223594413031565>"
STAT_WARD = "<:stat_ward:1524223592320209037>"
STAT_PDR = "<:stat_pdr:1524223593423175770>"
STAT_FDR = "<:stat_fdr:1524223595591630928>"
STAT_BLOCK = "<:stat_block:1524223598141898912>"

STAT_EMOJI: dict[str, str] = {
    "atk": STAT_ATK,
    "def": STAT_DEF,
    "hp": STAT_HP,
    "ward": STAT_WARD,
    "pdr": STAT_PDR,
    "fdr": STAT_FDR,
    "block": STAT_BLOCK,
}

# ── Runes (9 types — previously all shared one generic 🔮) ──────────────────
RUNE_REFINEMENT = "<:rune_refinement:1524223611747963072>"
RUNE_POTENTIAL = "<:rune_potential:1524223612197015694>"
RUNE_SHATTER = "<:rune_shatter:1524223610028429554>"
RUNE_IMBUE = "<:rune_imbue:1524223617301221537>"
RUNE_PARTNERSHIP = "<:rune_partnership:1524223613350187040>"
RUNE_REGRET = "<:rune_regret:1524223610749849630>"
RUNE_NATURE = "<:rune_nature:1524223614306615327>"
RUNE_MIRAGE_IMPERFECT = "<:rune_mirage_imperfect:1524223616244388061>"
RUNE_MIRAGE_PERFECT = "<:rune_mirage_perfect:1524223615032229948>"

# ── Essence tiers (category headers, not per-type essence icons) ───────────
ESSENCE_COMMON = "<:essence_common:1524223646921527296>"
ESSENCE_RARE = "<:essence_rare:1524223645679882340>"
ESSENCE_CORRUPT = "<:essence_corrupt:1524223646380458188>"

# ── Misc materials / currencies ─────────────────────────────────────────────
CURIO = "<:curio:1524223650205663383>"
PUZZLE_BOX = "<:puzzle_box:1524223621545853148>"
PINNACLE_KEY = "<:pinnacle_key:1524223622934429776>"
VOID_KEY = "<:void_key:1524223587660202134>"
DIVINER_ROD = "<:diviner_rod:1524223648318095380>"
SPIRIT_STONE = "<:spirit_stone:1524223600805150780>"
SPIRIT_SHARD = "<:spirit_shard:1524223601396416522>"
MAGMA_CORE = "<:magma_core:1524223626860167278>"
LIFE_ROOT = "<:life_root:1524223629141999707>"
PARADISE_JEWEL_UNCUT = "<:paradise_jewel_uncut:1524223623718506607>"

# ── Artisan Mastery remnants (prestige gathering-boss drops) ───────────────
TIDE_RELIC = "<:tide_relic:1524223590776438794>"
HEARTWOOD_SHARD = "<:heartwood_shard:1524223636066533526>"
GEODE_CORE = "<:geode_core:1524223645021507715>"

# ── Feature / hub branding icons ─────────────────────────────────────────────
CONSUME_ICON = "<:consume:1524223651485061251>"
NETHER_MARKET_PLUNDER = "<:nether_plunder:1524223625685897307>"
INFINITE_MAW = "<:infinite_maw:1524223631436021872>"

# ── RESOURCE_EMOJI ─────────────────────────────────────────────────────────
# Single source of truth for gathering/settlement/Black Market material icons.
# Several views used to hardcode their own emoji per resource key (and
# sometimes disagreed with each other — e.g. gold_ore was 🏅 in one place,
# ⛏️ in another). Look up materials here instead of inlining a new literal.
RESOURCE_EMOJI: dict[str, str] = {
    "timber": "🪵",
    "stone": "🪨",
    "iron_ore": IRON_ORE,
    "coal_ore": COAL_ORE,
    "gold_ore": GOLD_ORE,
    "platinum_ore": PLATINUM_ORE,
    "idea_ore": IDEA_ORE,
    "iron_bar": BARS_REFINED,
    "steel_bar": BARS_REFINED,
    "gold_bar": BARS_REFINED,
    "platinum_bar": BARS_REFINED,
    "idea_bar": BARS_REFINED,
    "oak_logs": OAK_LOGS,
    "willow_logs": WILLOW_LOGS,
    "mahogany_logs": MAHOGANY_LOGS,
    "magic_logs": MAGIC_LOGS,
    "idea_logs": IDEA_LOGS,
    "oak_plank": "🪵",
    "willow_plank": "🪵",
    "mahogany_plank": "🪵",
    "magic_plank": "🪵",
    "idea_plank": "🪵",
    "desiccated_bones": DESICCATED_BONES,
    "regular_bones": REGULAR_BONES,
    "sturdy_bones": STURDY_BONES,
    "reinforced_bones": REINFORCED_BONES,
    "titanium_bones": TITANIUM_BONES,
    "desiccated_essence": "⚗️",
    "regular_essence": "⚗️",
    "sturdy_essence": "⚗️",
    "reinforced_essence": "⚗️",
    "titanium_essence": "⚗️",
    "refinement_runes": RUNE_REFINEMENT,
    "potential_runes": RUNE_POTENTIAL,
    "shatter_runes": RUNE_SHATTER,
    "imbue_runes": RUNE_IMBUE,
    "partnership_runes": RUNE_PARTNERSHIP,
    "rune_of_regret": RUNE_REGRET,
    "runes_of_nature": RUNE_NATURE,
    "mirage_runes_imperfect": RUNE_MIRAGE_IMPERFECT,
    "mirage_runes_perfected": RUNE_MIRAGE_PERFECT,
    "dragon_key": DRAGON_KEY,
    "angel_key": ANGEL_KEY,
    "soul_cores": SOUL_CORE,
    "balance_fragment": "⚖️",
    "void_frags": VOID_FRAG,
    "void_keys": VOID_KEY,
    "magma_core": MAGMA_CORE,
    "life_root": LIFE_ROOT,
    "spirit_shard": SPIRIT_SHARD,
    "curios": CURIO,
    "curio_puzzle_boxes": PUZZLE_BOX,
    "unidentified_blueprint": "📋",
    "diviners_rod": DIVINER_ROD,
    "spirit_stones": SPIRIT_STONE,
    "pinnacle_key": PINNACLE_KEY,
    "paradise_jewels": PARADISE_JEWEL_UNCUT,
    "celestial_stone": "⭐",
    "infernal_cinder": "🔥",
    "void_crystal": "💜",
    "bound_crystal": "🔗",
    "corrupted_core": "🌑",
    "blessed_bismuth": BLESSED_BISMUTH,
    "sparkling_sprig": SPARKLING_SPRIG,
    "capricious_carp": CAPRICIOUS_CARP,
    "tide_relics": TIDE_RELIC,
    "heartwood_shards": HEARTWOOD_SHARD,
    "geode_cores": GEODE_CORE,
}

# ── EMBLEM_CATALOG ───────────────────────────────────────────────────────────
# Every uploaded application emoji, offered as a purchasable Prestige "Emblem"
# (see cogs/prestige.py). key -> (display label, emoji tag). Keep in sync with
# the constants above when new emoji are added.
EMBLEM_CATALOG: dict[str, tuple[str, str]] = {
    "monster_cheeks": ("Monster Cheeks", MONSTER_CHEEK),
    "gold_ore": ("Gold Ore", GOLD_ORE),
    "platinum_ore": ("Platinum Ore", PLATINUM_ORE),
    "quench_potion": ("Quench Potion", QUENCH),
    "iron_ore": ("Iron Ore", IRON_ORE),
    "coal_ore": ("Coal", COAL_ORE),
    "idea_ore": ("Idea Ore", IDEA_ORE),
    "refined_bars": ("Refined Bars", BARS_REFINED),
    "oak_log": ("Oak Log", OAK_LOGS),
    "willow_log": ("Willow Log", WILLOW_LOGS),
    "mahogany_log": ("Mahogany Log", MAHOGANY_LOGS),
    "magic_log": ("Magic Log", MAGIC_LOGS),
    "idea_log": ("Idea Log", IDEA_LOGS),
    "desiccated_bones": ("Desiccated Bones", DESICCATED_BONES),
    "regular_bone": ("Regular Bone", REGULAR_BONES),
    "sturdy_bone": ("Sturdy Bone", STURDY_BONES),
    "reinforced_bone": ("Reinforced Bone", REINFORCED_BONES),
    "titanium_bone": ("Titanium Bone", TITANIUM_BONES),
    "draconic_key": ("Draconic Key", DRAGON_KEY),
    "angelic_key": ("Angelic Key", ANGEL_KEY),
    "soul_core": ("Soul Core", SOUL_CORE),
    "void_frag": ("Void Fragment", VOID_FRAG),
    "blessed_bismuth": ("Blessed Bismuth", BLESSED_BISMUTH),
    "sparkling_sprig": ("Sparkling Sprig", SPARKLING_SPRIG),
    "capricious_carp": ("Capricious Carp", CAPRICIOUS_CARP),
    "weapon": ("Weapon", WEAPON_SLOT),
    "armor": ("Armor", ARMOR_SLOT),
    "helmet": ("Helmet", HELMET_SLOT),
    "gloves": ("Gloves", GLOVE_SLOT),
    "boots": ("Boots", BOOT_SLOT),
    "accessory": ("Accessory", ACCESSORY_SLOT),
    "stat_atk": ("Attack", STAT_ATK),
    "stat_def": ("Defence", STAT_DEF),
    "stat_hp": ("HP", STAT_HP),
    "stat_ward": ("Ward", STAT_WARD),
    "stat_pdr": ("PDR", STAT_PDR),
    "stat_fdr": ("FDR", STAT_FDR),
    "stat_block": ("Block", STAT_BLOCK),
    "rune_refinement": ("Rune of Refinement", RUNE_REFINEMENT),
    "rune_potential": ("Rune of Potential", RUNE_POTENTIAL),
    "rune_shatter": ("Rune of Shatter", RUNE_SHATTER),
    "rune_imbue": ("Rune of Imbue", RUNE_IMBUE),
    "rune_partnership": ("Rune of Partnership", RUNE_PARTNERSHIP),
    "rune_regret": ("Rune of Regret", RUNE_REGRET),
    "rune_nature": ("Rune of Nature", RUNE_NATURE),
    "rune_mirage_imperfect": ("Mirage Rune (Imperfect)", RUNE_MIRAGE_IMPERFECT),
    "rune_mirage_perfect": ("Mirage Rune (Perfected)", RUNE_MIRAGE_PERFECT),
    "essence_common": ("Common Essence", ESSENCE_COMMON),
    "essence_rare": ("Rare Essence", ESSENCE_RARE),
    "essence_corrupt": ("Corrupt Essence", ESSENCE_CORRUPT),
    "curio": ("Curio", CURIO),
    "puzzle_box": ("Puzzle Box", PUZZLE_BOX),
    "pinnacle_key": ("Pinnacle Key", PINNACLE_KEY),
    "void_key": ("Void Key", VOID_KEY),
    "diviner_rod": ("Diviner's Rod", DIVINER_ROD),
    "spirit_stone": ("Spirit Stone", SPIRIT_STONE),
    "spirit_shard": ("Spirit Shard", SPIRIT_SHARD),
    "magma_core": ("Magma Core", MAGMA_CORE),
    "life_root": ("Life Root", LIFE_ROOT),
    "paradise_jewel_uncut": ("Paradise Jewel", PARADISE_JEWEL_UNCUT),
    "tide_relic": ("Tide Relic", TIDE_RELIC),
    "heartwood_shard": ("Heartwood Shard", HEARTWOOD_SHARD),
    "geode_core": ("Geode Core", GEODE_CORE),
    "consume": ("Consume", CONSUME_ICON),
    "nether_plunder": ("Nether Plunder", NETHER_MARKET_PLUNDER),
    "infinite_maw": ("Infinite Maw", INFINITE_MAW),
}
