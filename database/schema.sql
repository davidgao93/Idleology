

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
  `combat_stamina` INTEGER NOT NULL DEFAULT 10,
  `last_stamina_regen` TIMESTAMP DEFAULT NULL,
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
  `doors_enabled` INTEGER NOT NULL DEFAULT 1,
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
  `prestige_monument` TEXT DEFAULT NULL,
  `curio_puzzle_boxes` INTEGER NOT NULL DEFAULT 0,
  `mirage_runes_imperfect` INTEGER NOT NULL DEFAULT 0,
  `mirage_runes_perfected` INTEGER NOT NULL DEFAULT 0,
  `unidentified_blueprint` INTEGER NOT NULL DEFAULT 0,
  `diviners_rod` INTEGER NOT NULL DEFAULT 0,
  `hard_mode` INTEGER NOT NULL DEFAULT 0,
  `auto_rest_pay` INTEGER NOT NULL DEFAULT 0,
  `combat_streak` INTEGER NOT NULL DEFAULT 0,
  `pending_stat_packages` TEXT DEFAULT NULL,
  `stat_invest_atk` INTEGER NOT NULL DEFAULT 0,
  `stat_invest_def` INTEGER NOT NULL DEFAULT 0,
  `stat_invest_hp` INTEGER NOT NULL DEFAULT 0,
  `stat_invest_gold` INTEGER NOT NULL DEFAULT 0,
  `rune_of_regret` INTEGER NOT NULL DEFAULT 0,
  `development_contracts` INTEGER NOT NULL DEFAULT 0,
  `dc_crafted_today` INTEGER NOT NULL DEFAULT 0,
  `last_dc_craft_date` TEXT DEFAULT NULL,
  `runes_of_nature` INTEGER NOT NULL DEFAULT 0,
  `settlement_zeal` INTEGER NOT NULL DEFAULT 0,
  `idlem` INTEGER NOT NULL DEFAULT 0,
  `zeal_earned_today` INTEGER NOT NULL DEFAULT 0,
  `last_zeal_reset` TEXT DEFAULT NULL,
  `pending_companion_cookies` INTEGER NOT NULL DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS `maw_participants` (
  `user_id`            TEXT    NOT NULL,
  `cycle_id`           INTEGER NOT NULL,
  `signup_timestamp`   INTEGER NOT NULL,
  `last_fight_ts`      INTEGER NOT NULL DEFAULT 0,
  `damage_dealt`       INTEGER NOT NULL DEFAULT 0,
  `fights_this_cycle`  INTEGER NOT NULL DEFAULT 0,
  `rewards_collected`  INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (`user_id`, `cycle_id`)
);

CREATE TABLE IF NOT EXISTS `prestige_owned` (
  `user_id` TEXT NOT NULL,
  `item_type` TEXT NOT NULL,
  `item_key` TEXT NOT NULL,
  PRIMARY KEY (`user_id`, `item_type`, `item_key`)
);

CREATE TABLE IF NOT EXISTS `journey_milestones` (
  `user_id`         TEXT    NOT NULL,
  `milestone_level` INTEGER NOT NULL,
  `claimed_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`, `milestone_level`)
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
    `forge_tier` INTEGER DEFAULT 0,
    `hit_chance` REAL NOT NULL DEFAULT 0.60,
    `crit_chance` REAL NOT NULL DEFAULT 0.00,
    `crit_multi` REAL NOT NULL DEFAULT 2.00,
    `base_rarity` INTEGER NOT NULL DEFAULT 3
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
  `celestial_armor_passive` TEXT NOT NULL DEFAULT 'none',
  `main_stat_type` TEXT NOT NULL DEFAULT 'def',
  `main_stat` INTEGER DEFAULT 0,
  `reinforces_remaining` INTEGER DEFAULT 0,
  `reinforcement_lvl` INTEGER DEFAULT 0
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
  `corrupted_essence` TEXT DEFAULT 'none',
  `reinforces_remaining` INTEGER DEFAULT 0,
  `reinforcement_lvl` INTEGER DEFAULT 0
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
  `corrupted_essence` TEXT DEFAULT 'none',
  `reinforces_remaining` INTEGER DEFAULT 0,
  `reinforcement_lvl` INTEGER DEFAULT 0
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
    `idea_bar` INTEGER DEFAULT 0,
    -- Gathering Expansion: tool familiarization gate + session momentum (gathering_expansion.md)
    `familiarization_end` TEXT DEFAULT NULL,
    `momentum_minutes` INTEGER DEFAULT 0
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
    `titanium_essence` INTEGER DEFAULT 0,
    -- Gathering Expansion: tool familiarization gate + session momentum (gathering_expansion.md)
    `familiarization_end` TEXT DEFAULT NULL,
    `momentum_minutes` INTEGER DEFAULT 0
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
    `idea_plank` INTEGER DEFAULT 0,
    -- Gathering Expansion: tool familiarization gate + session momentum (gathering_expansion.md)
    `familiarization_end` TEXT DEFAULT NULL,
    `momentum_minutes` INTEGER DEFAULT 0
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
    corrupted_essence TEXT DEFAULT 'none',
    reinforces_remaining INTEGER DEFAULT 0,
    reinforcement_lvl INTEGER DEFAULT 0
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
    timber INTEGER DEFAULT 0,
    stone INTEGER DEFAULT 0,
    last_collection_time TEXT,
    last_zeal_gather_time TEXT DEFAULT NULL,
    total_development_turns INTEGER NOT NULL DEFAULT 0,
    pending_zeal INTEGER NOT NULL DEFAULT 0,
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
    plot_index INTEGER DEFAULT NULL,  -- which settlement plot this building occupies (1-20)
    is_meta INTEGER NOT NULL DEFAULT 0,  -- 1 = meta building (no tier, doesn't count toward slot cap)
    is_disabled INTEGER NOT NULL DEFAULT 0,  -- 1 = disabled by crisis event; requires repair
    UNIQUE(user_id, server_id, slot_index)
);

-- Plot grid for the settlement map system (5×5 minus corners = 20 buildable plots)
CREATE TABLE IF NOT EXISTS settlement_plots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    server_id   TEXT NOT NULL,
    plot_index  INTEGER NOT NULL,   -- 1–20
    is_developed INTEGER NOT NULL DEFAULT 0,
    bonus_type  TEXT DEFAULT NULL,  -- e.g. "fertile_ground", NULL if undeveloped
    UNIQUE(user_id, server_id, plot_index)
);

CREATE TABLE IF NOT EXISTS settlement_research (
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    building_type TEXT NOT NULL,
    start_time TEXT NOT NULL DEFAULT '',
    completed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, server_id, building_type)
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

CREATE TABLE IF NOT EXISTS slayer_tree (
    user_id      TEXT    NOT NULL,
    server_id    TEXT    NOT NULL,
    nodes_owned  TEXT    NOT NULL DEFAULT '{}',
    points_spent INTEGER NOT NULL DEFAULT 0,
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
    corruption_sigils INTEGER DEFAULT 0,
    paradise_jewels INTEGER DEFAULT 0,
    corruption_engrams INTEGER DEFAULT 0,
    corruption_blueprint_unlocked INTEGER DEFAULT 0,
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
    free_roll_used INTEGER NOT NULL DEFAULT 0,
    cosmic_dust INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS potion_passives (
    user_id TEXT NOT NULL,
    slot INTEGER NOT NULL,
    passive_type TEXT NOT NULL,
    passive_value REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, slot)
);

-- Potion Distillation sessions (multi-step Sage Elixir style crafting for powerful passives).
-- Stores live progress for the 9-step reagent choice + event system.
-- `data` is JSON containing: base_type, duration_mod, value_mod, active_modifiers (dict of event state),
-- history (list of step results), dust_spent, etc.
-- The full table (and any future columns) will be created by schema.sql executescript for everyone.
-- Old DBs get it automatically on next bot startup because of CREATE IF NOT EXISTS.
CREATE TABLE IF NOT EXISTS potion_distillations (
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    step INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS synthesis_queue (
    user_id    TEXT PRIMARY KEY,
    item_type  TEXT NOT NULL,
    quantity   INTEGER NOT NULL,
    start_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS synthesis_queue_2 (
    user_id    TEXT PRIMARY KEY,
    item_type  TEXT NOT NULL,
    quantity   INTEGER NOT NULL,
    start_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS synthesis_queue_3 (
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

CREATE TABLE IF NOT EXISTS paradise_jewel_data (
    user_id                  TEXT PRIMARY KEY,
    unlocked_skills          TEXT NOT NULL DEFAULT '[]',
    equipped_skill           TEXT DEFAULT NULL,
    skill_levels             TEXT NOT NULL DEFAULT '{}',
    skill_charges            TEXT NOT NULL DEFAULT '{}',
    passive_slots            TEXT NOT NULL DEFAULT '[]',
    passive_jewels_invested  INTEGER NOT NULL DEFAULT 0,
    total_jewels_obtained    INTEGER NOT NULL DEFAULT 0,
    total_jewels_consumed    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS boss_party_dispatch (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL,
    server_id     TEXT NOT NULL,
    attacker_id   INTEGER NOT NULL,
    tank_id       INTEGER NOT NULL,
    healer_id     INTEGER NOT NULL,
    boss_name     TEXT NOT NULL,
    boss_max_hp   INTEGER NOT NULL,
    start_time    TEXT NOT NULL,
    UNIQUE(user_id, server_id)
);

-- Hematurgy System

CREATE TABLE IF NOT EXISTS hematurgy_passives (
    user_id    TEXT NOT NULL,
    slot_type  TEXT NOT NULL,
    passive_id TEXT NOT NULL,
    tier       INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, slot_type)
);

CREATE TABLE IF NOT EXISTS hematurgy_blood (
    user_id      TEXT PRIMARY KEY,
    primordial   INTEGER NOT NULL DEFAULT 0,
    evolutionary INTEGER NOT NULL DEFAULT 0,
    mutative     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS monster_eggs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL,
    egg_tier      TEXT NOT NULL,
    monster_level INTEGER NOT NULL,
    monster_name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hatchery_incubation (
    user_id          TEXT NOT NULL,
    server_id        TEXT NOT NULL,
    egg_id           INTEGER NOT NULL,
    egg_tier         TEXT NOT NULL,
    monster_level    INTEGER NOT NULL,
    monster_name     TEXT NOT NULL,
    start_time       TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS incubated_encounters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL,
    monster_name  TEXT NOT NULL,
    monster_level INTEGER NOT NULL,
    egg_tier      TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- ============================================================
-- Apex Hunts System
-- ============================================================

CREATE TABLE IF NOT EXISTS apex_hunt_profiles (
    user_id          TEXT NOT NULL,
    server_id        TEXT NOT NULL,
    hunt_charges     INTEGER NOT NULL DEFAULT 3,
    last_charge_time REAL    DEFAULT NULL,
    ashen_wins       INTEGER NOT NULL DEFAULT 0,
    ashen_losses     INTEGER NOT NULL DEFAULT 0,
    storm_wins       INTEGER NOT NULL DEFAULT 0,
    storm_losses     INTEGER NOT NULL DEFAULT 0,
    citadel_wins     INTEGER NOT NULL DEFAULT 0,
    citadel_losses   INTEGER NOT NULL DEFAULT 0,
    grove_wins       INTEGER NOT NULL DEFAULT 0,
    grove_losses     INTEGER NOT NULL DEFAULT 0,
    vault_wins       INTEGER NOT NULL DEFAULT 0,
    vault_losses     INTEGER NOT NULL DEFAULT 0,
    shattered_wins   INTEGER NOT NULL DEFAULT 0,
    shattered_losses INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS soul_stones (
    user_id       TEXT NOT NULL,
    server_id     TEXT NOT NULL,
    slot_1_passive   TEXT DEFAULT NULL,
    slot_1_tier      INTEGER DEFAULT NULL,
    slot_1_category  TEXT DEFAULT NULL,
    slot_2_passive   TEXT DEFAULT NULL,
    slot_2_tier      INTEGER DEFAULT NULL,
    slot_2_category  TEXT DEFAULT NULL,
    slot_3_passive   TEXT DEFAULT NULL,
    slot_3_tier      INTEGER DEFAULT NULL,
    slot_3_category  TEXT DEFAULT NULL,
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS soul_shards (
    user_id        TEXT NOT NULL,
    server_id      TEXT NOT NULL,
    pyre           INTEGER NOT NULL DEFAULT 0,
    tempest        INTEGER NOT NULL DEFAULT 0,
    bulwark        INTEGER NOT NULL DEFAULT 0,
    verdant        INTEGER NOT NULL DEFAULT 0,
    fortune        INTEGER NOT NULL DEFAULT 0,
    rift           INTEGER NOT NULL DEFAULT 0,
    soul_fragments INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS meta_shards (
    user_id          TEXT NOT NULL,
    server_id        TEXT NOT NULL,
    sharpened_fang   INTEGER NOT NULL DEFAULT 0,
    engorged_heart   INTEGER NOT NULL DEFAULT 0,
    condensed_blood  INTEGER NOT NULL DEFAULT 0,
    primal_essence   INTEGER NOT NULL DEFAULT 0,
    soul_vessel      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, server_id)
);

-- ============================================================
-- Artisan Mastery (Gathering Mastery) System
-- Per design doc (docs/design/gathering_mastery.md) + 2026 expansions:
-- Points exclusively from hourly passive (1.8/day at BiS tool), 3-branch trees per skill + 10 bonus pts/branch,
-- Nature's Attunement cross-skill tree (3 nodes x 5 pts, gate = 20+ invested in each main tree),
-- Mastery Insight (post-max infinite scaling: 5 excess pts -> 1 insight, tiny global yield / remnant / rune bonuses),
-- Remnants via Quality branch + Rich procs, Rune of Nature (68x3 remnants + 350k gold + 2 spirit stones),
-- Respecs (1 rune per skill), Black Market exchange (55 remnants = 1 rare Settlement currency),
-- Prestige gathering bosses (Golem/Leviathan/Colossus) with triple ticks + Free Yourself snare.
-- ============================================================

CREATE TABLE IF NOT EXISTS gathering_mastery (
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    mining_points INTEGER DEFAULT 0,
    fishing_points INTEGER DEFAULT 0,
    woodcutting_points INTEGER DEFAULT 0,
    mining_alloc TEXT DEFAULT '{}',
    fishing_alloc TEXT DEFAULT '{}',
    woodcutting_alloc TEXT DEFAULT '{}',
    last_point_claim TEXT,
    -- Remnant currencies (Quality branch output, used for Rune crafting + Black Market)
    geode_cores INTEGER DEFAULT 0,
    tide_relics INTEGER DEFAULT 0,
    heartwood_shards INTEGER DEFAULT 0,
    mining_tripled_ticks INTEGER DEFAULT 0,
    fishing_tripled_ticks INTEGER DEFAULT 0,
    woodcutting_tripled_ticks INTEGER DEFAULT 0,
    total_mastery_invested INTEGER DEFAULT 0,
    -- Nature's Attunement (cross-skill tree unlocked at 20+ pts per main tree)
    attunement_alloc TEXT DEFAULT '{}',
    -- Post-max infinite scaling (every 5 excess points across skills -> 1 insight)
    mastery_insight INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, server_id)
);

-- ── COMPANION MASTERY ────────────────────────────────────────────────────────
-- Three branches (Forager / Affinity / Bonded), 3 nodes each.
-- Kinship Points earned from overflow XP when companions are already at level 100.
-- nodes_owned: JSON {node_id: true | "choice_str"}.  Choice nodes store the player's pick.
CREATE TABLE IF NOT EXISTS companion_mastery (
    user_id         TEXT NOT NULL,
    server_id       TEXT NOT NULL,
    nodes_owned     TEXT NOT NULL DEFAULT '{}',
    points_spent    INTEGER NOT NULL DEFAULT 0,
    kinship_points  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, server_id)
);

-- ── FIRST-USE TUTORIALS ───────────────────────────────────────────────────────
-- Tracks which tutorial prompts a player has already been shown.
-- Keyed by (user_id, feature_key); no server_id needed since tutorials are
-- per-player globally.
CREATE TABLE IF NOT EXISTS tutorial_seen (
    user_id     TEXT NOT NULL,
    feature_key TEXT NOT NULL,
    seen_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, feature_key)
);

-- ── Settlement Turns Economy ──────────────────────────────────────────────────

-- Pending multi-turn Black Market deals waiting to be processed by Next Turn.
CREATE TABLE IF NOT EXISTS settlement_pending_deals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          TEXT    NOT NULL,
    server_id        TEXT    NOT NULL,
    offer_data       TEXT    NOT NULL,  -- JSON: {resource: qty, ...}
    total_value      INTEGER NOT NULL,
    turns_remaining  INTEGER NOT NULL,
    active_biases    TEXT    NOT NULL DEFAULT '[]',  -- JSON array of bias keys
    created_turn     INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, server_id)
);

-- Active construction / upgrade / research / nursery / foundry projects.
-- Each row represents one in-progress project spending Development Turns.
-- Uniqueness is enforced at the application layer (upsert_project) to avoid
-- SQLite's prohibition on expressions in UNIQUE constraints.
CREATE TABLE IF NOT EXISTS settlement_projects (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        TEXT    NOT NULL,
    server_id      TEXT    NOT NULL,
    project_type   TEXT    NOT NULL,  -- 'construction','upgrade','research','nursery','foundry'
    target_id      INTEGER,           -- buildings.id for upgrades; NULL for new builds
    required_turns INTEGER NOT NULL,
    invested_turns INTEGER NOT NULL DEFAULT 0,
    data           TEXT    DEFAULT NULL  -- JSON extra info (building_type, plot_index, etc.)
);

-- Active settlement events (upcoming, ongoing, instant-resolved).
CREATE TABLE IF NOT EXISTS settlement_active_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        TEXT    NOT NULL,
    server_id      TEXT    NOT NULL,
    event_key      TEXT    NOT NULL,  -- matches key in SETTLEMENT_EVENTS constant
    event_type     TEXT    NOT NULL,  -- 'upcoming','ongoing','instant'
    turns_until    INTEGER NOT NULL DEFAULT 0,   -- for upcoming: turns until it fires
    turns_remaining INTEGER NOT NULL DEFAULT 0,  -- for ongoing: turns left
    data           TEXT    DEFAULT NULL          -- JSON extra state per-event
);

-- Black Market passive tree node investment (Idlem-powered).
CREATE TABLE IF NOT EXISTS bm_passive_tree (
    user_id   TEXT    NOT NULL,
    server_id TEXT    NOT NULL,
    node_key  TEXT    NOT NULL,  -- e.g. 'efficiency_1', 'rune_bias_2'
    level     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, server_id, node_key)
);

-- For existing databases, add ALTER statements here:
-- ALTER TABLE users ADD COLUMN runes_of_nature INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE gathering_mastery ADD COLUMN attunement_alloc TEXT DEFAULT '{}';
-- ALTER TABLE gathering_mastery ADD COLUMN mastery_insight INTEGER DEFAULT 0;