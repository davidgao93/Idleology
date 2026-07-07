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
ARMOR_SLOT = "<:armor:1524165420196823055>"
HELMET_SLOT = "<:helmet:1524165426857246930>"
GLOVE_SLOT = "<:gloves:1524165426186293360>"
BOOT_SLOT = "<:boots:1524165422503563374>"
ACCESSORY_SLOT = "<:accessory:1524165418598797512>"

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
    "refinement_runes": "🔮",
    "potential_runes": "🔮",
    "shatter_runes": "🔮",
    "imbue_runes": "🔮",
    "dragon_key": DRAGON_KEY,
    "angel_key": ANGEL_KEY,
    "soul_cores": SOUL_CORE,
    "balance_fragment": "⚖️",
    "void_frags": VOID_FRAG,
    "magma_core": "🔥",
    "life_root": "🌿",
    "spirit_shard": "🌟",
    "curios": "📦",
    "unidentified_blueprint": "📋",
    "spirit_stones": "🔮",
    "celestial_stone": "⭐",
    "infernal_cinder": "🔥",
    "void_crystal": "💜",
    "bound_crystal": "🔗",
    "corrupted_crystal": "🌑",
    "blessed_bismuth": BLESSED_BISMUTH,
    "sparkling_sprig": SPARKLING_SPRIG,
    "capricious_carp": CAPRICIOUS_CARP,
}
