-- ALTER TABLE uber_progress ADD COLUMN blessed_bismuth INTEGER DEFAULT 0;
-- ALTER TABLE uber_progress ADD COLUMN sparkling_sprig INTEGER DEFAULT 0;
-- ALTER TABLE uber_progress ADD COLUMN capricious_carp INTEGER DEFAULT 0;

-- ALTER TABLE users ADD COLUMN prestige_border TEXT NOT NULL DEFAULT 'none';
-- ALTER TABLE users ADD COLUMN prestige_title TEXT NOT NULL DEFAULT 'none';
-- ALTER TABLE users ADD COLUMN prestige_display_name TEXT DEFAULT NULL;
-- ALTER TABLE users ADD COLUMN prestige_flair TEXT NOT NULL DEFAULT 'none';
-- ALTER TABLE users ADD COLUMN prestige_death_message TEXT DEFAULT NULL;
-- ALTER TABLE users ADD COLUMN prestige_monument TEXT DEFAULT NULL;

CREATE TABLE IF NOT EXISTS `users` (
  `id` INTEGER PRIMARY KEY,
  `user_id` TEXT NOT NULL UNIQUE,
  `server_id` TEXT NOT NULL,
  `name` TEXT NOT NULL,
  `level` INTEGER NOT NULL DEFAULT 1,
  `experience` INTEGER NOT NULL DEFAULT 0,
  `gold` INTEGER NOT NULL DEFAULT 0,
  `appearance` TEXT NOT NULL,
  `ideology` TEXT NOT NULL,
  `attack` INTEGER NOT NULL DEFAULT 1,
  `defence` INTEGER NOT NULL DEFAULT 1,
  `current_hp` INTEGER NOT NULL DEFAULT 10,
  `max_hp` INTEGER NOT NULL DEFAULT 10,
  `last_rest_time` TIMESTAMP DEFAULT NULL, 
  `last_propagate_time` TIMESTAMP DEFAULT NULL, 
  `ascension` INTEGER NOT NULL DEFAULT 0,
  `potions` INTEGER NOT NULL DEFAULT 0,
  `last_checkin_time` TIMESTAMP DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `refinement_runes` INTEGER NOT NULL DEFAULT 0,
  `passive_points` INTEGER NOT NULL DEFAULT 0,
  `potential_runes` INTEGER NOT NULL DEFAULT 0,
  `curios` INTEGER NOT NULL DEFAULT 0,
  `curios_purchased_today` INTEGER NOT NULL DEFAULT 0,
  `last_combat` TIMESTAMP DEFAULT NULL,
  `dragon_key` INTEGER NOT NULL DEFAULT 0,
  `angel_key` INTEGER NOT NULL DEFAULT 0,
  `imbue_runes` INTEGER NOT NULL DEFAULT 0,
  `soul_cores` INTEGER NOT NULL DEFAULT 0,
  `void_frags` INTEGER NOT NULL DEFAULT 0,
  `void_keys` INTEGER NOT NULL DEFAULT 0,
  `shatter_runes` INTEGER NOT NULL DEFAULT 0,
  `partnership_runes` INTEGER NOT NULL DEFAULT 0,
  `last_companion_collect_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `balance_fragment` INTEGER NOT NULL DEFAULT 0,
  `magma_core` INTEGER NOT NULL DEFAULT 0,
  `life_root` INTEGER NOT NULL DEFAULT 0,
  `spirit_shard` INTEGER NOT NULL DEFAULT 0,
  `doors_enabled` INTEGER NOT NULL DEFAULT 0,
  `celestial_stone` INTEGER NOT NULL DEFAULT 0,
  `void_crystal` INTEGER NOT NULL DEFAULT 0,
  `infernal_cinder` INTEGER NOT NULL DEFAULT 0,
  `bound_crystal` INTEGER NOT NULL DEFAULT 0,
  `codex_fragments` INTEGER NOT NULL DEFAULT 0,
  `codex_pages` INTEGER NOT NULL DEFAULT 0,
  `codex_rerolls` INTEGER NOT NULL DEFAULT 0,
  `highest_ascension_stage` INTEGER NOT NULL DEFAULT 0,
  `spirit_stones` INTEGER NOT NULL DEFAULT 0,
  `exp_protection` INTEGER NOT NULL DEFAULT 0,
  `antique_tome` INTEGER NOT NULL DEFAULT 0,
  `pinnacle_key` INTEGER NOT NULL DEFAULT 0,
  `highest_ascension_floor` INTEGER NOT NULL DEFAULT 0,
  `prestige_border` TEXT NOT NULL DEFAULT 'none',
  `prestige_title` TEXT NOT NULL DEFAULT 'none',
  `prestige_display_name` TEXT DEFAULT NULL,
  `prestige_flair` TEXT NOT NULL DEFAULT 'none',
  `prestige_death_message` TEXT DEFAULT NULL,
  `prestige_monument` TEXT DEFAULT NULL
);


CREATE TABLE IF NOT EXISTS `monster_parts` (
  `id`           INTEGER PRIMARY KEY AUTOINCREMENT,
  `user_id`      TEXT NOT NULL,
  `slot_type`    TEXT NOT NULL,
  `monster_name` TEXT NOT NULL,
  `ilvl`         INTEGER NOT NULL,
  `hp_value`     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS `monster_parts_equipped` (
  `user_id`      TEXT NOT NULL,
  `slot_type`    TEXT NOT NULL,
  `hp_value`     INTEGER NOT NULL,
  `monster_name` TEXT NOT NULL,
  PRIMARY KEY (`user_id`, `slot_type`)
);

CREATE TABLE IF NOT EXISTS `prestige_owned` (
  `user_id` TEXT NOT NULL,
  `item_type` TEXT NOT NULL,
  `item_key` TEXT NOT NULL,
  PRIMARY KEY (`user_id`, `item_type`, `item_key`)
);


CREATE TABLE IF NOT EXISTS `ascension_unlocks` (
  `user_id` TEXT NOT NULL,
  `floor` INTEGER NOT NULL,
  PRIMARY KEY (`user_id`, `floor`)
);

CREATE TABLE IF NOT EXISTS `ideologies` (
  `id` INTEGER PRIMARY KEY,
  `user_id` TEXT NOT NULL,
  `server_id` TEXT NOT NULL,
  `name` TEXT NOT NULL,
  `followers` INTEGER NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `items` (
  `item_id` INTEGER PRIMARY KEY,
  `user_id` TEXT NOT NULL,
  `item_name` TEXT NOT NULL,
  `item_level` INTEGER NOT NULL,
  `attack` INTEGER DEFAULT 0,
  `defence` INTEGER DEFAULT 0,
  `rarity` INTEGER DEFAULT 0,
  `passive` TEXT NOT NULL DEFAULT 'none',
  `is_equipped` BOOLEAN DEFAULT FALSE,
  `forges_remaining` INTEGER DEFAULT 0,
  `refines_remaining` INTEGER DEFAULT 0,
  `refinement_lvl` INTEGER DEFAULT 0,
  `pinnacle_passive` TEXT NOT NULL DEFAULT 'none',
  `utmost_passive` TEXT NOT NULL DEFAULT 'none',
  `infernal_passive` TEXT NOT NULL DEFAULT 'none',
  `forge_tier` INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `accessories` (
  `item_id` INTEGER PRIMARY KEY,
  `user_id` TEXT NOT NULL,
  `item_name` TEXT NOT NULL,
  `item_level` INTEGER NOT NULL,
  `attack` INTEGER DEFAULT 0,
  `defence` INTEGER DEFAULT 0,
  `rarity` INTEGER DEFAULT 0,
  `ward` INTEGER DEFAULT 0,
  `crit` INTEGER DEFAULT 0,
  `passive` TEXT NOT NULL DEFAULT 'none',
  `is_equipped` BOOLEAN DEFAULT FALSE,
  `potential_remaining` INTEGER DEFAULT 10,
  `passive_lvl` INTEGER DEFAULT 0,
  `void_passive` TEXT DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS `armor` (
  `item_id` INTEGER PRIMARY KEY,
  `user_id` TEXT NOT NULL,
  `item_name` TEXT NOT NULL,
  `item_level` INTEGER NOT NULL,
  `block` INTEGER DEFAULT 0,
  `evasion` INTEGER DEFAULT 0,
  `ward` INTEGER DEFAULT 0,
  `armor_passive` TEXT NOT NULL DEFAULT 'none',
  `is_equipped` BOOLEAN DEFAULT FALSE,
  `temper_remaining` INTEGER DEFAULT 0,
  `imbue_remaining` INTEGER DEFAULT 1,
  `pdr` INTEGER DEFAULT 0,
  `fdr` INTEGER DEFAULT 0,
  `celestial_armor_passive` TEXT NOT NULL DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS `gloves` (
  `item_id` INTEGER PRIMARY KEY,
  `user_id` TEXT NOT NULL,
  `item_name` TEXT NOT NULL,
  `item_level` INTEGER NOT NULL,
  `attack` INTEGER DEFAULT 0,
  `defence` INTEGER DEFAULT 0,
  `ward` INTEGER DEFAULT 0,
  `pdr` INTEGER DEFAULT 0,
  `fdr` INTEGER DEFAULT 0,
  `passive` TEXT NOT NULL DEFAULT 'none',
  `is_equipped` BOOLEAN DEFAULT FALSE,
  `potential_remaining` INTEGER DEFAULT 5,
  `passive_lvl` INTEGER DEFAULT 0,
  `essence_1` TEXT DEFAULT 'none',
  `essence_1_val` REAL DEFAULT 0,
  `essence_2` TEXT DEFAULT 'none',
  `essence_2_val` REAL DEFAULT 0,
  `essence_3` TEXT DEFAULT 'none',
  `essence_3_val` REAL DEFAULT 0,
  `corrupted_essence` TEXT DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS `boots` (
  `item_id` INTEGER PRIMARY KEY,
  `user_id` TEXT NOT NULL,
  `item_name` TEXT NOT NULL,
  `item_level` INTEGER NOT NULL,
  `attack` INTEGER DEFAULT 0,
  `defence` INTEGER DEFAULT 0,
  `ward` INTEGER DEFAULT 0,
  `pdr` INTEGER DEFAULT 0,
  `fdr` INTEGER DEFAULT 0,
  `passive` TEXT NOT NULL DEFAULT 'none',
  `is_equipped` BOOLEAN DEFAULT FALSE,
  `potential_remaining` INTEGER DEFAULT 6,
  `passive_lvl` INTEGER DEFAULT 0,
  `essence_1` TEXT DEFAULT 'none',
  `essence_1_val` REAL DEFAULT 0,
  `essence_2` TEXT DEFAULT 'none',
  `essence_2_val` REAL DEFAULT 0,
  `essence_3` TEXT DEFAULT 'none',
  `essence_3_val` REAL DEFAULT 0,
  `corrupted_essence` TEXT DEFAULT 'none'
);


CREATE TABLE IF NOT EXISTS `mining` (
    `user_id` TEXT NOT NULL,
    `server_id` TEXT NOT NULL,
    `pickaxe_tier` TEXT DEFAULT 'iron',
    `iron` INTEGER DEFAULT 0,
    `coal` INTEGER DEFAULT 0,
    `gold` INTEGER DEFAULT 0,
    `platinum` INTEGER DEFAULT 0,
    `idea` INTEGER DEFAULT 0,
    `iron_bar` INTEGER DEFAULT 0,
    `steel_bar` INTEGER DEFAULT 0,
    `gold_bar` INTEGER DEFAULT 0,
    `platinum_bar` INTEGER DEFAULT 0,
    `idea_bar` INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `fishing` (
    `user_id` TEXT,
    `server_id` TEXT,
    `fishing_rod` TEXT DEFAULT 'desiccated',
    `desiccated_bones` INTEGER DEFAULT 0,
    `regular_bones` INTEGER DEFAULT 0,
    `sturdy_bones` INTEGER DEFAULT 0,
    `reinforced_bones` INTEGER DEFAULT 0,
    `titanium_bones` INTEGER DEFAULT 0,
    `desiccated_essence` INTEGER DEFAULT 0,
    `regular_essence` INTEGER DEFAULT 0,
    `sturdy_essence` INTEGER DEFAULT 0,
    `reinforced_essence` INTEGER DEFAULT 0,
    `titanium_essence` INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `woodcutting` (
    `user_id` TEXT,
    `server_id` TEXT,
    `axe_type` TEXT DEFAULT 'flimsy',
    `oak_logs` INTEGER DEFAULT 0,
    `willow_logs` INTEGER DEFAULT 0,
    `mahogany_logs` INTEGER DEFAULT 0,
    `magic_logs` INTEGER DEFAULT 0,
    `idea_logs` INTEGER DEFAULT 0,
    `oak_plank` INTEGER DEFAULT 0,
    `willow_plank` INTEGER DEFAULT 0,
    `mahogany_plank` INTEGER DEFAULT 0,
    `magic_plank` INTEGER DEFAULT 0,
    `idea_plank` INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS helmets (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    item_level INTEGER NOT NULL,
    defence INTEGER DEFAULT 0,
    ward INTEGER DEFAULT 0,
    pdr INTEGER DEFAULT 0,
    fdr INTEGER DEFAULT 0,
    passive TEXT DEFAULT 'none',
    passive_lvl INTEGER DEFAULT 0,
    is_equipped BOOLEAN DEFAULT 0,
    potential_remaining INTEGER DEFAULT 5,
    essence_1 TEXT DEFAULT 'none',
    essence_1_val REAL DEFAULT 0,
    essence_2 TEXT DEFAULT 'none',
    essence_2_val REAL DEFAULT 0,
    essence_3 TEXT DEFAULT 'none',
    essence_3_val REAL DEFAULT 0,
    corrupted_essence TEXT DEFAULT 'none'
);


CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT PRIMARY KEY,
    event_channel_id TEXT
);

CREATE TABLE IF NOT EXISTS companions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT,              -- User custom name
    species TEXT,           -- e.g. "Goblin", "Dragon"
    image_url TEXT,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    passive_type TEXT,      -- 'atk', 'def', 'pdr', 'fdr', 'ward', 'hit', 'crit', 'rarity', 's_rarity'
    passive_tier INTEGER,   -- 1-5
    is_active INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    balanced_passive TEXT DEFAULT 'none',
    balanced_passive_tier INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS delve_progress (
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    delve_xp INTEGER DEFAULT 0,
    obsidian_shards INTEGER DEFAULT 0,
    fuel_level INTEGER DEFAULT 1,
    struct_level INTEGER DEFAULT 1,
    sensor_level INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, server_id)
);

-- 1. New Settlement Tables
CREATE TABLE IF NOT EXISTS settlements (
    user_id TEXT,
    server_id TEXT,
    town_hall_tier INTEGER DEFAULT 1,
    building_slots INTEGER DEFAULT 3, 
    timber INTEGER DEFAULT 0, -- Specific settlement resource
    stone INTEGER DEFAULT 0,  -- Specific settlement resource
    last_collection_time TEXT,
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    server_id TEXT,
    building_type TEXT, -- 'foundry', 'sawmill', 'market', etc.
    tier INTEGER DEFAULT 1,
    slot_index INTEGER,
    workers_assigned INTEGER DEFAULT 0,
    UNIQUE(user_id, server_id, slot_index)
);

CREATE TABLE IF NOT EXISTS slayer_profiles (
    user_id TEXT,
    server_id TEXT,
    level INTEGER DEFAULT 1,
    xp INTEGER DEFAULT 0,
    slayer_points INTEGER DEFAULT 0,
    violent_essence INTEGER DEFAULT 0,
    imbued_heart INTEGER DEFAULT 0,
    active_task_species TEXT,
    active_task_amount INTEGER DEFAULT 0,
    active_task_progress INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS slayer_emblems (
    user_id TEXT,
    server_id TEXT,
    slot_1_type TEXT DEFAULT 'none', slot_1_tier INTEGER DEFAULT 1,
    slot_2_type TEXT DEFAULT 'none', slot_2_tier INTEGER DEFAULT 1,
    slot_3_type TEXT DEFAULT 'none', slot_3_tier INTEGER DEFAULT 1,
    slot_4_type TEXT DEFAULT 'none', slot_4_tier INTEGER DEFAULT 1,
    slot_5_type TEXT DEFAULT 'none', slot_5_tier INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS uber_progress (
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    celestial_sigils INTEGER DEFAULT 0,
    celestial_engrams INTEGER DEFAULT 0,
    celestial_blueprint_unlocked INTEGER DEFAULT 0,
    infernal_sigils INTEGER DEFAULT 0,
    infernal_engrams INTEGER DEFAULT 0,
    infernal_blueprint_unlocked INTEGER DEFAULT 0,
    void_shards INTEGER DEFAULT 0,
    void_engrams INTEGER DEFAULT 0,
    void_blueprint_unlocked INTEGER DEFAULT 0,
    gemini_sigils INTEGER DEFAULT 0,
    gemini_engrams INTEGER DEFAULT 0,
    gemini_blueprint_unlocked INTEGER DEFAULT 0,
    blessed_bismuth INTEGER DEFAULT 0,
    sparkling_sprig INTEGER DEFAULT 0,
    capricious_carp INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS codex_progress (
    user_id TEXT NOT NULL,
    chapter_id INTEGER NOT NULL,
    clears INTEGER NOT NULL DEFAULT 0,
    perfect_clears INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, chapter_id)
);

CREATE TABLE IF NOT EXISTS codex_tomes (
    user_id TEXT NOT NULL,
    slot INTEGER NOT NULL,
    passive_type TEXT NOT NULL,
    tier INTEGER NOT NULL DEFAULT 0,
    value REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (user_id, slot)
);

CREATE TABLE IF NOT EXISTS alchemy_data (
    user_id TEXT PRIMARY KEY,
    level INTEGER NOT NULL DEFAULT 1,
    free_roll_used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS potion_passives (
    user_id TEXT NOT NULL,
    slot INTEGER NOT NULL,
    passive_type TEXT NOT NULL,
    passive_value REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, slot)
);

CREATE TABLE IF NOT EXISTS synthesis_queue (
    user_id    TEXT PRIMARY KEY,
    item_type  TEXT NOT NULL,
    quantity   INTEGER NOT NULL,
    start_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS duel_stats (
    user_id TEXT PRIMARY KEY,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS player_essences (
    user_id TEXT NOT NULL,
    essence_type TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, essence_type)
);

CREATE TABLE IF NOT EXISTS user_partners (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               TEXT NOT NULL,
    partner_id            INTEGER NOT NULL,
    level                 INTEGER NOT NULL DEFAULT 1,
    exp                   INTEGER NOT NULL DEFAULT 0,

    combat_slot_1         TEXT DEFAULT NULL,
    combat_slot_1_lvl     INTEGER NOT NULL DEFAULT 1,
    combat_slot_2         TEXT DEFAULT NULL,
    combat_slot_2_lvl     INTEGER NOT NULL DEFAULT 1,
    combat_slot_3         TEXT DEFAULT NULL,
    combat_slot_3_lvl     INTEGER NOT NULL DEFAULT 1,
    sig_combat_lvl        INTEGER NOT NULL DEFAULT 1,

    dispatch_slot_1       TEXT DEFAULT NULL,
    dispatch_slot_1_lvl   INTEGER NOT NULL DEFAULT 1,
    dispatch_slot_2       TEXT DEFAULT NULL,
    dispatch_slot_2_lvl   INTEGER NOT NULL DEFAULT 1,
    dispatch_slot_3       TEXT DEFAULT NULL,
    dispatch_slot_3_lvl   INTEGER NOT NULL DEFAULT 1,
    sig_dispatch_lvl      INTEGER NOT NULL DEFAULT 1,

    dispatch_task         TEXT DEFAULT NULL,
    dispatch_start_time   TEXT DEFAULT NULL,
    dispatch_task_2       TEXT DEFAULT NULL,
    dispatch_start_time_2 TEXT DEFAULT NULL,

    is_active_combat      INTEGER NOT NULL DEFAULT 0,
    is_dispatched         INTEGER NOT NULL DEFAULT 0,

    affinity_encounters   INTEGER NOT NULL DEFAULT 0,
    affinity_story_seen   INTEGER NOT NULL DEFAULT 0,
    portrait_variant      INTEGER NOT NULL DEFAULT 0,

    UNIQUE(user_id, partner_id)
);

CREATE TABLE IF NOT EXISTS user_partner_items (
    user_id               TEXT PRIMARY KEY,
    guild_tickets         INTEGER NOT NULL DEFAULT 0,
    pity_counter          INTEGER NOT NULL DEFAULT 0,
    combat_skill_shards   INTEGER NOT NULL DEFAULT 0,
    dispatch_skill_shards INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_partner_shards (
    user_id     TEXT NOT NULL,
    partner_id  INTEGER NOT NULL,
    shard_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, partner_id)
);