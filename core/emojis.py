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

MONSTER_CHEEK = "<:monster_cheek:1524149883941032157>"
GOLD_ORE = "<:gold_ore:1524149884658389072>"
PLATINUM_ORE = "<:platinum_ore:1524149885459234957>"
QUENCH = "<:quench:1524149885719543901>"

# ── Gathering materials ─────────────────────────────────────────────────────
IRON_ORE = "<:iron_ore:1524165429898252420>"
COAL_ORE = "<:coal:1524165423975764078>"
IDEA_ORE = "<:idea_ore:1524165428937752796>"
BARS_REFINED = "<:bars_refined:1524165421241204876>"  # shared icon for all bar tiers
OAK_LOGS = "<:oak_logs:1524165432406315008>"
WILLOW_LOGS = "<:willow:1524165440069173468>"
MAHOGANY_LOGS = "<:mahogany_logs:1524165431395352827>"
MAGIC_LOGS = "<:magic_logs:1524165430556622958>"
IDEA_LOGS = "<:idea_log:1524165427943702681>"
DESICCATED_BONES = "<:desiccated_fish:1524165424785264880>"
REGULAR_BONES = "<:regular_bone:1524165433446633502>"
STURDY_BONES = "<:sturdy_bone:1524165437242478774>"
REINFORCED_BONES = "<:reinforced_bone:1524165433995952338>"
TITANIUM_BONES = "<:titanium_bone:1524165438102175855>"

# ── Boss keys / high-value materials ────────────────────────────────────────
DRAGON_KEY = "<:draconic_key:1524165425385046167>"
ANGEL_KEY = "<:angelic_key_noBackground:1524165419332665354>"
SOUL_CORE = "<:soul_core:1524165435065372732>"
VOID_FRAG = "<:void_frag:1524165438890840185>"
BLESSED_BISMUTH = "<:blessed_bismuth:1524165421802979430>"
SPARKLING_SPRIG = "<:sparkling_sprig:1524165436130725988>"
CAPRICIOUS_CARP = "<:capricious_carp:1524165423162069033>"

# ── Equipment slots (see core/inventory/views/_slot_defs.py: SLOT_EMOJIS) ───
WEAPON_SLOT = "<:weapon:1524182189208637521>"
ARMOR_SLOT = "<:armor:1524165420196823055>"
HELMET_SLOT = "<:helmet:1524165426857246930>"
GLOVE_SLOT = "<:gloves:1524165426186293360>"
BOOT_SLOT = "<:boots:1524165422503563374>"
ACCESSORY_SLOT = "<:accessory:1524165418598797512>"

# ── Combat stats (profile stat sheet + in-combat stat lines) ───────────────
STAT_ATK = "<:stat_atk:1524182195516870756>"
STAT_DEF = "<:stat_def:1524182194229084250>"
STAT_HP = "<:stat_hp:1524182193037901954>"
STAT_WARD = "<:stat_ward:1524182191867691129>"
STAT_PDR = "<:stat_pdr:1524182192438251650>"
STAT_FDR = "<:stat_fdr:1524182193725902898>"
STAT_BLOCK = "<:stat_block:1524182194728210696>"

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
RUNE_REFINEMENT = "<:rune_refinement:1524182208817139763>"
RUNE_POTENTIAL = "<:rune_potential:1524182209882493098>"
RUNE_SHATTER = "<:rune_shatter:1524182207701192785>"
RUNE_IMBUE = "<:rune_imbue:1524182215544672266>"
RUNE_PARTNERSHIP = "<:rune_partnership:1524182211190984735>"
RUNE_REGRET = "<:rune_regret:1524182208347373718>"
RUNE_NATURE = "<:rune_nature:1524182212084498585>"
RUNE_MIRAGE_IMPERFECT = "<:rune_mirage_imperfect:1524182214458343565>"
RUNE_MIRAGE_PERFECT = "<:rune_mirage_perfect:1524182212734484520>"

# ── Essence tiers (category headers, not per-type essence icons) ───────────
ESSENCE_COMMON = "<:essence_common:1524182185802731744>"
ESSENCE_RARE = "<:essence_rare:1524182184028672162>"
ESSENCE_CORRUPT = "<:essence_corrupt:1524182184947224640>"

# ── Misc materials / currencies ─────────────────────────────────────────────
CURIO = "<:curio:1524182187656876143>"
PUZZLE_BOX = "<:puzzle_box:1524182216165560442>"
PINNACLE_KEY = "<:pinnacle_key:1524182216975061083>"
VOID_KEY = "<:void_key:1524182190240432338>"
DIVINER_ROD = "<:diviner_rod:1524182186910285854>"
SPIRIT_STONE = "<:spirit_stone:1524182196267651122>"
SPIRIT_SHARD = "<:spirit_shard:1524182197395783691>"
MAGMA_CORE = "<:magma_core:1524182219080601622>"
LIFE_ROOT = "<:life_root:1524182219768336464>"
PARADISE_JEWEL_UNCUT = "<:paradise_jewel_uncut:1524182217595551955>"

# ── Artisan Mastery remnants (prestige gathering-boss drops) ───────────────
TIDE_RELIC = "<:tide_relic:1524182191188349008>"
HEARTWOOD_SHARD = "<:heartwood_shard:1524182220976423057>"
GEODE_CORE = "<:geode_core:1524182222062747699>"

# ── Feature / hub branding icons ─────────────────────────────────────────────
CONSUME_ICON = "<:consume:1524182188256526376>"
NETHER_MARKET_PLUNDER = "<:nether_market_plunder:1524182218329555055>"
INFINITE_MAW = "<:infinite_maw:1524182220552798238>"

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
    "corrupted_crystal": "🌑",
    "blessed_bismuth": BLESSED_BISMUTH,
    "sparkling_sprig": SPARKLING_SPRIG,
    "capricious_carp": CAPRICIOUS_CARP,
    "tide_relics": TIDE_RELIC,
    "heartwood_shards": HEARTWOOD_SHARD,
    "geode_cores": GEODE_CORE,
}
