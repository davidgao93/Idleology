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

MONSTER_CHEEK = "<:monster_cheeks:1524443430304874617>"
GOLD_ORE = "<:gold_ore:1524443428795187261>"
PLATINUM_ORE = "<:platinum_ore:1524443419165069512>"
QUENCH = "<:quench_potion:1524443419441627177>"

# ── Monster parts (Consume / Hematurgy slot icons) ─────────────────────────
MONSTER_HEAD = "<:monster_head:1525489774289354884>"
MONSTER_TORSO = "<:monster_torso:1525489772250923060>"
MONSTER_RIGHT_ARM = "<:monster_right_arm:1525489773106561114>"
MONSTER_LEFT_ARM = "<:monster_left_arm:1525489776822583407>"
MONSTER_RIGHT_LEG = "<:monster_right_leg:1525489776265007205>"
MONSTER_LEFT_LEG = "<:monster_left_leg:1525489774461194412>"
MONSTER_ORGANS = "<:monster_organs:1525489775472021716>"

MONSTER_PART_SLOT_EMOJI: dict[str, str] = {
    "head": MONSTER_HEAD,
    "torso": MONSTER_TORSO,
    "right_arm": MONSTER_RIGHT_ARM,
    "left_arm": MONSTER_LEFT_ARM,
    "right_leg": MONSTER_RIGHT_LEG,
    "left_leg": MONSTER_LEFT_LEG,
    "cheeks": MONSTER_CHEEK,
    "organs": MONSTER_ORGANS,
}

# ── Gathering materials ─────────────────────────────────────────────────────
IRON_ORE = "<:iron_ore:1524443400382840842>"
COAL_ORE = "<:coal:1524443395194491071>"
IDEA_ORE = "<:idea_ore:1524443399195857016>"
BARS_REFINED = "<:refined_bars:1524443432167411722>"  # shared icon for all bar tiers
WOODEN_PLANKS = (
    "<:wooden_planks:1524443361698644109>"  # shared icon for all plank tiers
)
OAK_LOGS = "<:oak_logs:1524443403264462949>"
WILLOW_LOGS = "<:willow_logs:1524443407655633087>"
MAHOGANY_LOGS = "<:mahogany_logs:1524443402236592318>"
MAGIC_LOGS = "<:magic_log:1524443401129558223>"
IDEA_LOGS = "<:idea_log:1524443398210195527>"
DESICCATED_BONES = "<:desiccated_bones:1524443423585865888>"
REGULAR_BONES = "<:regular_bone:1524443420708307097>"
STURDY_BONES = "<:sturdy_bone:1524443405785108673>"
REINFORCED_BONES = "<:reinforced_bone:1524443403956387950>"
TITANIUM_BONES = "<:titanium_bone:1524443406800261232>"

# ── Boss keys / high-value materials ────────────────────────────────────────
DRAGON_KEY = "<:draconic_key:1524443377431482590>"
ANGEL_KEY = "<:angelic_key:1524443390840803358>"
SOUL_CORE = "<:soul_core:1524443408242835496>"
VOID_FRAG = "<:void_fragment:1524443364051783760>"
BLESSED_BISMUTH = "<:blessed_bismuth:1524443391428133065>"
SPARKLING_SPRIG = "<:sparkling_sprig:1524443404665229583>"
CAPRICIOUS_CARP = "<:capricious_carp:1524443394318012516>"
PINNACLE_KEY = "<:pinnacle_key:1524449793085145269>"

# ── Equipment slots (see core/inventory/views/_slot_defs.py: SLOT_EMOJIS) ───
WEAPON_SLOT = "<:gear_weapons:1524443375711948800>"
ARMOR_SLOT = "<:gear_armor:1524443396117106869>"
HELMET_SLOT = "<:gear_helmet:1524443427306209431>"
GLOVE_SLOT = "<:gear_gloves:1524443397476323399>"
BOOT_SLOT = "<:gear_boots:1524443392963252358>"
ACCESSORY_SLOT = "<:gear_accessory:1524443431513096279>"
GEAR_BACKPACK = "<:gear_backpack:1524443376320118794>"  # generic "Gear" category icon (not slot-specific)

# ── Combat stats (profile stat sheet + in-combat stat lines) ───────────────
STAT_ATK = "<:stat_atk:1524443366342004948>"
STAT_DEF = "<:stat_def:1524443410956681367>"
STAT_HP = "<:stat_hp:1524443413070610432>"
STAT_WARD = "<:stat_ward:1524443414555525243>"
STAT_PDR = "<:stat_pdr:1524443413926117387>"
STAT_FDR = "<:stat_fdr:1524443411627774052>"
STAT_BLOCK = "<:stat_block:1524443409836802082>"

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
RUNE_GENERIC = "<:rune_generic:1524443371404398704>"  # category-title icon (crafting section header)
RUNE_REFINEMENT = "<:rune_refine:1524443368724238377>"
RUNE_POTENTIAL = "<:rune_potential:1524443421987831900>"
RUNE_SHATTER = "<:rune_shatter:1524443368002818068>"
RUNE_IMBUE = "<:rune_imbue:1524443370699620352>"
RUNE_PARTNERSHIP = "<:rune_companion:1524443372209705100>"
RUNE_REGRET = "<:rune_regret:1524443422969036971>"
RUNE_NATURE = "<:rune_nature:1524443421782048788>"
RUNE_MIRAGE_IMPERFECT = "<:rune_mirage_imperfect:1524443370091577554>"
RUNE_MIRAGE_PERFECT = "<:rune_mirage_perfect:1524443369281945661>"

# ── Essence tiers (category headers, not per-type essence icons) ───────────
ESSENCE_COMMON = "<:essence_common:1524443425158467704>"
ESSENCE_RARE = "<:essence_rare:1524443426534330490>"
ESSENCE_CORRUPT = "<:essence_corrupted:1524443425728889077>"

# ── Misc materials / currencies ─────────────────────────────────────────────
CURIO = "<:curio:1524443379805589524>"
PUZZLE_BOX = "<:curio_puzle_box:1524443378845089862>"
VOID_KEY = "<:void_key:1524443363414245659>"
DIVINER_ROD = "<:diviner_rod:1524443424558678056>"
SPIRIT_STONE = "<:spirit_stone:1524443409375297810>"
SPIRIT_SHARD = "<:spirit_shard:1524443408490434653>"
MAGMA_CORE = "<:magma_core:1524443416711401665>"
LIFE_ROOT = "<:life_root:1524443372905824337>"
PARADISE_JEWEL_UNCUT = "<:paradise_jewel_uncut:1524443417952780460>"
DEVELOPMENT_CONTRACT = "<:development_contract:1524443378329190450>"

# ── Artisan Mastery remnants (prestige gathering-boss drops) ───────────────
TIDE_RELIC = "<:tide_relic:1524443415113367562>"
HEARTWOOD_SHARD = "<:heartwood_shard:1524443429629722736>"
GEODE_CORE = "<:geode_core:1524443428111388743>"

# ── Feature / hub branding icons ─────────────────────────────────────────────
CONSUME_ICON = "<:consume:1524443382795993209>"
NETHER_MARKET_PLUNDER = "<:nether_plunder:1524443417638076516>"
INFINITE_MAW = "<:maw:1524474466770620571>"
HEMATURGY_ICON = "<:hematurgy:1524465821743710281>"

# ── Combat / loot stats (previously generic Unicode, now dedicated art) ────
GOLD_COIN = "<:coins_gold:1524465818681868428>"
CRIT_MULTI = "<:crit_multi:1524465817868046436>"
RARITY = "<:rarity:1524465819290046475>"
DODGE_EVASION = "<:dodge_evasion:1524465821139603608>"
POTION = "<:potion:1524465820363919490>"
COSMIC_DUST = "<:cosmic_dust:1524465822309945464>"

# ── Uber boss materials (sigils / engrams / statue specials) ───────────────
CELESTIAL_SIGIL = "<:celestial_sigil:1524443385950376088>"
CELESTIAL_ENGRAM = "<:celestial_engram:1524443387493748918>"
CELESTIAL_STONE = "<:celestial_stone:1524443384557862962>"
INFERNAL_SIGIL = "<:infernal_sigil:1524443373476516070>"
INFERNAL_ENGRAM = "<:infernal_engram:1524443374122307674>"
INFERNAL_CINDER = "<:infernal_cinder:1524443374906642523>"
VOID_SIGIL = "<:void_sigil:1524443362411679784>"
VOID_ENGRAM = "<:void_engram:1524443364756422806>"
VOID_CRYSTAL = "<:void_crystal:1524443365347819582>"
BOUND_SIGIL = "<:bound_sigil:1524443388194062538>"
BOUND_ENGRAM = "<:bound_engram:1524443389158883539>"
BOUND_CRYSTAL = "<:bound_crystal:1524443390220177429>"
CORRUPTION_SIGIL = "<:corruption_sigil:1524443380699107449>"
CORRUPTION_CORE = "<:corruption_core:1524449916989214791>"
CORRUPTION_ENGRAM = "<:corruption_engram:1524443381776777238>"

# ── The Rite of Convergence entry keys ──────────────────────────────────────
RITE_KEY_CELESTIAL = (
    "<:celestial_raid_key:1524874694438682792>"  # Apex of Dreams (Aphrodite)
)
RITE_KEY_INFERNAL = (
    "<:infernal_raid_key:1524874697580347452>"  # Corruption of Memories (Lucifer)
)
RITE_KEY_GEMINI = (
    "<:gemini_raid_key:1524874695390920874>"  # Scales of Judgment (Gemini)
)
RITE_KEY_VOID = "<:void_raid_key:1524874696066203687>"  # Devoid of Thoughts (NEET)
RITE_KEY_CORRUPT = (
    "<:corrupt_raid_key:1524874693767856340>"  # Zenith of Nightmares (Evelynn)
)

# ── Apex Hunt materials (zone shards, meta shards, soul fragments) ─────────
PYRE_SHARD = "<:pyre_shard:1524798356965167125>"
TEMPEST_SHARD = "<:tempest_shard:1524798351223291924>"
BULWARK_SHARD = "<:bulwark_shard:1524798362493386863>"
VERDANT_SHARD = "<:verdant_shard:1524798350430437536>"
FORTUNE_SHARD = "<:fortune_shard:1524798359003594883>"
RIFT_SHARD = "<:rift_shard:1524798356629491772>"
SOUL_FRAGMENT = "<:soul_fragment:1524798353173643355>"
SHARPENED_FANG = "<:sharpened_fang:1524798355421790319>"
ENGORGED_HEART = "<:engorged_heart:1524798359640998131>"
CONDENSED_BLOOD = "<:condensed_blood:1524798360249438298>"
PRIMAL_ESSENCE = "<:primal_essence:1524798358282305547>"
SOUL_VESSEL = "<:soul_vessel:1524798361318850600>"
# NOTE: named _EMOJI to avoid colliding with core.images.APEX_IMPRINT (a thumbnail URL)
APEX_IMPRINT_EMOJI = "<:apex_imprint:1524798361838817471>"

APEX_SHARD_EMOJI: dict[str, str] = {
    "pyre": PYRE_SHARD,
    "tempest": TEMPEST_SHARD,
    "bulwark": BULWARK_SHARD,
    "verdant": VERDANT_SHARD,
    "fortune": FORTUNE_SHARD,
    "rift": RIFT_SHARD,
    "soul_fragments": SOUL_FRAGMENT,
}

APEX_META_SHARD_EMOJI: dict[str, str] = {
    "sharpened_fang": SHARPENED_FANG,
    "engorged_heart": ENGORGED_HEART,
    "condensed_blood": CONDENSED_BLOOD,
    "primal_essence": PRIMAL_ESSENCE,
    "soul_vessel": SOUL_VESSEL,
}

# ── Crafting tab: Meta (Utility) essence category icon ─────────────────────
ESSENCE_META = "<:essence_meta:1525652764573831238>"

# ── Monster eggs (Inventory / Consume / Hatchery) ───────────────────────────
MONSTER_EGG = "<:monster_egg:1525652762401050694>"
MONSTER_EGG_RARE = "<:monster_egg_rare:1525652763214745711>"
MONSTER_EGG_GIGA = "<:monster_egg_giga:1525652763793555538>"

MONSTER_EGG_TIER_EMOJI: dict[str, str] = {
    "normal": MONSTER_EGG,
    "rare": MONSTER_EGG_RARE,
    "giga": MONSTER_EGG_GIGA,
}

# ── Hematurgy passives (15 main + 5 mutative — Hematurgy view + combat embeds) ─
HEMA_REVERBERATION = "<:hema_reverberation:1525652750166261830>"
HEMA_SOOTHING_VENOM = "<:hema_soothingvenom:1525652748698128424>"
HEMA_IRON_MOMENTUM = "<:hema_ironmomentum:1525652753794207815>"
HEMA_SERRATED = "<:hema_serrate:1525652749327405136>"
HEMA_HAEMORRHAGE = "<:hema_haemorrhage:1525652754389930024>"
HEMA_VITAL_RESONANCE = "<:hema_vitalresonance:1525652746378809404>"
HEMA_EXECUTIONERS_RITE = "<:hema_executioner:1525652757590179872>"
HEMA_CRIMSON_FEAST = "<:hema_crimsonfeast:1525652759955640440>"
HEMA_PHANTOM_REFLEX = "<:hema_phantomreflex:1525652753177776340>"
HEMA_CHAIN_REACTION = "<:hema_chainreaction:1525652761603997706>"
HEMA_REGENERATIVE_TISSUE = "<:hema_regentissue:1525652750892007474>"
HEMA_FEVERED_STRIKE = "<:hema_feveredstrike:1525652755719651378>"
HEMA_PREDATORS_MARK = "<:hema_predatormark:1525652752460677190>"
HEMA_COUNTERFORCE = "<:hema_counterforce:1525652760803020851>"
HEMA_DEFIANCE = "<:hema_defiance:1525652759037345822>"
HEMA_SPECTRAL_WALTZ = "<:hema_spectralwaltz:1525652747112808518>"
HEMA_PUNCTURE = "<:hema_puncture:1525652751579742380>"
HEMA_FLASH_FROST = "<:hema_flashfrost:1525652755048300645>"
HEMA_WARD_INOCULATION = "<:hema_wardinoculation:1525652745670103241>"
HEMA_SOUL_FRACTURE = "<:hema_soulfracture:1525652747532238981>"

HEMATURGY_PASSIVE_EMOJI: dict[str, str] = {
    "reverberation": HEMA_REVERBERATION,
    "soothing_venom": HEMA_SOOTHING_VENOM,
    "iron_momentum": HEMA_IRON_MOMENTUM,
    "serrated": HEMA_SERRATED,
    "haemorrhage": HEMA_HAEMORRHAGE,
    "vital_resonance": HEMA_VITAL_RESONANCE,
    "executioners_rite": HEMA_EXECUTIONERS_RITE,
    "crimson_feast": HEMA_CRIMSON_FEAST,
    "phantom_reflex": HEMA_PHANTOM_REFLEX,
    "chain_reaction": HEMA_CHAIN_REACTION,
    "regenerative_tissue": HEMA_REGENERATIVE_TISSUE,
    "fevered_strike": HEMA_FEVERED_STRIKE,
    "predators_mark": HEMA_PREDATORS_MARK,
    "counterforce": HEMA_COUNTERFORCE,
    "defiance": HEMA_DEFIANCE,
    "spectral_waltz": HEMA_SPECTRAL_WALTZ,
    "puncture": HEMA_PUNCTURE,
    "flash_frost": HEMA_FLASH_FROST,
    "ward_inoculation": HEMA_WARD_INOCULATION,
    "soul_fracture": HEMA_SOUL_FRACTURE,
}

# ── Monster modifiers (combat embeds / monster-turn log lines) ─────────────
MOD_FLASHFIRE = "<:mod_flashfire:1525652744839626822>"
MOD_PRESSURE_SURGE = "<:mod_pressuresurge:1525652743795118210>"

# ── General combat embed ────────────────────────────────────────────────────
WIN_STREAK = "<:win_streak:1525652742213734525>"

# ── Settlement and loot ─────────────────────────────────────────────────────
ZEAL = "<:zeal:1525652741731520712>"

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
    "oak_plank": WOODEN_PLANKS,
    "willow_plank": WOODEN_PLANKS,
    "mahogany_plank": WOODEN_PLANKS,
    "magic_plank": WOODEN_PLANKS,
    "idea_plank": WOODEN_PLANKS,
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
    "celestial_stone": CELESTIAL_STONE,
    "infernal_cinder": INFERNAL_CINDER,
    "void_crystal": VOID_CRYSTAL,
    "bound_crystal": BOUND_CRYSTAL,
    "corrupted_core": CORRUPTION_CORE,
    "blessed_bismuth": BLESSED_BISMUTH,
    "sparkling_sprig": SPARKLING_SPRIG,
    "capricious_carp": CAPRICIOUS_CARP,
    "tide_relics": TIDE_RELIC,
    "heartwood_shards": HEARTWOOD_SHARD,
    "geode_cores": GEODE_CORE,
    "development_contracts": DEVELOPMENT_CONTRACT,
    "rite_key_apex_of_dreams": RITE_KEY_CELESTIAL,
    "rite_key_corruption_of_memories": RITE_KEY_INFERNAL,
    "rite_key_scales_of_judgment": RITE_KEY_GEMINI,
    "rite_key_devoid_of_thoughts": RITE_KEY_VOID,
    "rite_key_zenith_of_nightmares": RITE_KEY_CORRUPT,
}

# ── EMBLEM_CATALOG ───────────────────────────────────────────────────────────
# Every uploaded application emoji, offered as a purchasable Prestige "Emblem"
# (see cogs/prestige.py). key -> (display label, emoji tag). Keep in sync with
# the constants above when new emoji are added.
#
# IMPORTANT: keys are persisted verbatim in the `prestige_owned` table and in
# `users.prestige_emblem` — never rename or remove an existing key, even if
# the underlying live emoji's name has since changed. Only append new keys.
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
    # Appended for the 2026-07-08 emoji batch — new keys only, per the note above.
    "gear_backpack": ("Gear Bag", GEAR_BACKPACK),
    "wooden_planks": ("Wooden Planks", WOODEN_PLANKS),
    "rune_generic": ("Rune", RUNE_GENERIC),
    "development_contract": ("Development Contract", DEVELOPMENT_CONTRACT),
    "celestial_sigil": ("Celestial Sigil", CELESTIAL_SIGIL),
    "celestial_engram": ("Celestial Engram", CELESTIAL_ENGRAM),
    "celestial_stone": ("Celestial Stone", CELESTIAL_STONE),
    "infernal_sigil": ("Infernal Sigil", INFERNAL_SIGIL),
    "infernal_engram": ("Infernal Engram", INFERNAL_ENGRAM),
    "infernal_cinder": ("Infernal Cinder", INFERNAL_CINDER),
    "void_sigil": ("Void Sigil", VOID_SIGIL),
    "void_engram": ("Void Engram", VOID_ENGRAM),
    "void_crystal": ("Void Crystal", VOID_CRYSTAL),
    "bound_sigil": ("Bound Sigil", BOUND_SIGIL),
    "bound_engram": ("Bound Engram", BOUND_ENGRAM),
    "bound_crystal": ("Bound Crystal", BOUND_CRYSTAL),
    "corruption_sigil": ("Corruption Sigil", CORRUPTION_SIGIL),
    "corruption_core": ("Corruption Core", CORRUPTION_CORE),
    "corruption_engram": ("Corruption Engram", CORRUPTION_ENGRAM),
    "hematurgy": ("Hematurgy", HEMATURGY_ICON),
    "coins_gold": ("Gold", GOLD_COIN),
    "crit_multi": ("Crit Multiplier", CRIT_MULTI),
    "rarity": ("Rarity", RARITY),
    "dodge_evasion": ("Evasion", DODGE_EVASION),
    "potion": ("Potion", POTION),
    "cosmic_dust": ("Cosmic Dust", COSMIC_DUST),
    # Appended for the Apex Hunt shard/meta-shard emoji batch.
    "pyre_shard": ("Pyre Shard", PYRE_SHARD),
    "tempest_shard": ("Tempest Shard", TEMPEST_SHARD),
    "bulwark_shard": ("Bulwark Shard", BULWARK_SHARD),
    "verdant_shard": ("Verdant Shard", VERDANT_SHARD),
    "fortune_shard": ("Fortune Shard", FORTUNE_SHARD),
    "rift_shard": ("Rift Shard", RIFT_SHARD),
    "soul_fragment": ("Soul Fragment", SOUL_FRAGMENT),
    "sharpened_fang": ("Sharpened Fang", SHARPENED_FANG),
    "engorged_heart": ("Engorged Heart", ENGORGED_HEART),
    "condensed_blood": ("Condensed Blood", CONDENSED_BLOOD),
    "primal_essence": ("Primal Essence", PRIMAL_ESSENCE),
    "soul_vessel": ("Soul Vessel", SOUL_VESSEL),
    "apex_imprint": ("Apex Imprint", APEX_IMPRINT_EMOJI),
    # Appended for the monster part slot emoji batch.
    "monster_head": ("Monster Head", MONSTER_HEAD),
    "monster_torso": ("Monster Torso", MONSTER_TORSO),
    "monster_right_arm": ("Monster Right Arm", MONSTER_RIGHT_ARM),
    "monster_left_arm": ("Monster Left Arm", MONSTER_LEFT_ARM),
    "monster_right_leg": ("Monster Right Leg", MONSTER_RIGHT_LEG),
    "monster_left_leg": ("Monster Left Leg", MONSTER_LEFT_LEG),
    "monster_organs": ("Monster Organs", MONSTER_ORGANS),
    # Appended for the 2026-07-11 emoji batch (crafting/eggs/hematurgy/modifiers/streak/zeal).
    "essence_meta": ("Meta Essence", ESSENCE_META),
    "monster_egg": ("Monster Egg", MONSTER_EGG),
    "monster_egg_rare": ("Rare Monster Egg", MONSTER_EGG_RARE),
    "monster_egg_giga": ("Giga Monster Egg", MONSTER_EGG_GIGA),
    "hema_reverberation": ("Reverberation", HEMA_REVERBERATION),
    "hema_soothing_venom": ("Soothing Venom", HEMA_SOOTHING_VENOM),
    "hema_iron_momentum": ("Iron Momentum", HEMA_IRON_MOMENTUM),
    "hema_serrated": ("Serrated", HEMA_SERRATED),
    "hema_haemorrhage": ("Haemorrhage", HEMA_HAEMORRHAGE),
    "hema_vital_resonance": ("Vital Resonance", HEMA_VITAL_RESONANCE),
    "hema_executioners_rite": ("Executioner's Rite", HEMA_EXECUTIONERS_RITE),
    "hema_crimson_feast": ("Crimson Feast", HEMA_CRIMSON_FEAST),
    "hema_phantom_reflex": ("Phantom Reflex", HEMA_PHANTOM_REFLEX),
    "hema_chain_reaction": ("Chain Reaction", HEMA_CHAIN_REACTION),
    "hema_regenerative_tissue": ("Regenerative Tissue", HEMA_REGENERATIVE_TISSUE),
    "hema_fevered_strike": ("Fevered Strike", HEMA_FEVERED_STRIKE),
    "hema_predators_mark": ("Predator's Mark", HEMA_PREDATORS_MARK),
    "hema_counterforce": ("Counterforce", HEMA_COUNTERFORCE),
    "hema_defiance": ("Defiance", HEMA_DEFIANCE),
    "hema_spectral_waltz": ("Spectral Waltz", HEMA_SPECTRAL_WALTZ),
    "hema_puncture": ("Puncture", HEMA_PUNCTURE),
    "hema_flash_frost": ("Flash Frost", HEMA_FLASH_FROST),
    "hema_ward_inoculation": ("Ward Inoculation", HEMA_WARD_INOCULATION),
    "hema_soul_fracture": ("Soul Fracture", HEMA_SOUL_FRACTURE),
    "mod_flashfire": ("Flashfire", MOD_FLASHFIRE),
    "mod_pressure_surge": ("Pressure Surge", MOD_PRESSURE_SURGE),
    "win_streak": ("Win Streak", WIN_STREAK),
    "zeal": ("Zeal", ZEAL),
}
