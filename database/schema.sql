
-- ============================================================
-- CORE PLAYER
-- ============================================================

CREATE TABLE IF NOT EXISTS `users` (
  -- Identity
  `id`                          INTEGER PRIMARY KEY,
  `user_id`                     TEXT NOT NULL UNIQUE,
  `server_id`                   TEXT NOT NULL,
  `name`                        TEXT NOT NULL,
  `appearance`                  TEXT NOT NULL,
  `ideology`                    TEXT NOT NULL,
  `created_at`                  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- Progression
  `level`                       INTEGER NOT NULL DEFAULT 1,
  `experience`                  INTEGER NOT NULL DEFAULT 0,
  `ascension`                   INTEGER NOT NULL DEFAULT 0,
  `highest_ascension_stage`     INTEGER NOT NULL DEFAULT 0,
  `highest_ascension_floor`     INTEGER NOT NULL DEFAULT 0,
  `pending_stat_packages`       TEXT DEFAULT NULL,
  `stat_invest_atk`             INTEGER NOT NULL DEFAULT 0,
  `stat_invest_def`             INTEGER NOT NULL DEFAULT 0,
  `stat_invest_hp`              INTEGER NOT NULL DEFAULT 0,
  `stat_invest_gold`            INTEGER NOT NULL DEFAULT 0,
  `loadout_slots`               INTEGER NOT NULL DEFAULT 3,

  -- Base Stats
  `attack`                      INTEGER NOT NULL DEFAULT 1,
  `defence`                     INTEGER NOT NULL DEFAULT 1,
  `current_hp`                  INTEGER NOT NULL DEFAULT 10,
  `max_hp`                      INTEGER NOT NULL DEFAULT 10,

  -- Economy
  `gold`                        INTEGER NOT NULL DEFAULT 0,
  `potions`                     INTEGER NOT NULL DEFAULT 0,

  -- Combat
  `combat_stamina`              INTEGER NOT NULL DEFAULT 10,
  `combat_streak`               INTEGER NOT NULL DEFAULT 0,

  -- Settings
  `doors_enabled`               INTEGER NOT NULL DEFAULT 1,
  `exp_protection`              INTEGER NOT NULL DEFAULT 0,
  `hard_mode`                   INTEGER NOT NULL DEFAULT 0,
  `auto_rest_pay`               INTEGER NOT NULL DEFAULT 0,
  `corrupted_encounters_enabled` INTEGER NOT NULL DEFAULT 1,
  `auto_potion_reload`          INTEGER NOT NULL DEFAULT 0,

  -- Prestige Cosmetics
  `prestige_border`             TEXT NOT NULL DEFAULT 'none',
  `prestige_title`              TEXT NOT NULL DEFAULT 'none',
  `prestige_display_name`       TEXT DEFAULT NULL,
  `prestige_flair`              TEXT NOT NULL DEFAULT 'none',
  `prestige_death_message`      TEXT DEFAULT NULL,
  `prestige_monument`           TEXT DEFAULT NULL,
  `prestige_emblem`             TEXT DEFAULT NULL,

  -- Timestamps
  `last_combat`                 TIMESTAMP DEFAULT NULL,
  `last_rest_time`              TIMESTAMP DEFAULT NULL,
  `last_propagate_time`         TIMESTAMP DEFAULT NULL,
  `last_checkin_time`           TIMESTAMP DEFAULT NULL,
  `last_stamina_regen`          TIMESTAMP DEFAULT NULL,
  `last_companion_collect_time` TIMESTAMP DEFAULT NULL
);

-- All additive integer currencies (runes, keys, fragments, etc.) live here.
-- modify_currency / get_currency / deduct_currency_atomic all target this table.
-- Add new consumable currencies here, never back on users.
CREATE TABLE IF NOT EXISTS `player_currencies` (
  `user_id`                TEXT PRIMARY KEY,
  `passive_points`         INTEGER NOT NULL DEFAULT 0,
  `refinement_runes`       INTEGER NOT NULL DEFAULT 0,
  `potential_runes`        INTEGER NOT NULL DEFAULT 0,
  `imbue_runes`            INTEGER NOT NULL DEFAULT 0,
  `shatter_runes`          INTEGER NOT NULL DEFAULT 0,
  `partnership_runes`      INTEGER NOT NULL DEFAULT 0,
  `rune_of_regret`         INTEGER NOT NULL DEFAULT 0,
  `runes_of_nature`        INTEGER NOT NULL DEFAULT 0,
  `dragon_key`             INTEGER NOT NULL DEFAULT 0,
  `angel_key`              INTEGER NOT NULL DEFAULT 0,
  `void_keys`              INTEGER NOT NULL DEFAULT 0,
  `pinnacle_key`           INTEGER NOT NULL DEFAULT 0,
  `soul_cores`             INTEGER NOT NULL DEFAULT 0,
  `void_frags`             INTEGER NOT NULL DEFAULT 0,
  `balance_fragment`       INTEGER NOT NULL DEFAULT 0,
  `spirit_stones`          INTEGER NOT NULL DEFAULT 0,
  `antique_tome`           INTEGER NOT NULL DEFAULT 0,
  `curios`                 INTEGER NOT NULL DEFAULT 0,
  `curio_puzzle_boxes`     INTEGER NOT NULL DEFAULT 0,
  `codex_fragments`        INTEGER NOT NULL DEFAULT 0,
  `codex_pages`            INTEGER NOT NULL DEFAULT 0,
  `codex_rerolls`          INTEGER NOT NULL DEFAULT 0,
  `mirage_runes_imperfect` INTEGER NOT NULL DEFAULT 0,
  `mirage_runes_perfected` INTEGER NOT NULL DEFAULT 0,
  `companion_pet_xp`       INTEGER NOT NULL DEFAULT 0,
  -- Rite of Convergence entry keys (fully tradeable)
  `rite_key_apex_of_dreams`          INTEGER NOT NULL DEFAULT 0,
  `rite_key_corruption_of_memories`  INTEGER NOT NULL DEFAULT 0,
  `rite_key_scales_of_judgment`      INTEGER NOT NULL DEFAULT 0,
  `rite_key_devoid_of_thoughts`      INTEGER NOT NULL DEFAULT 0,
  `rite_key_zenith_of_nightmares`    INTEGER NOT NULL DEFAULT 0
);


-- ============================================================
-- EQUIPMENT
-- ============================================================

CREATE TABLE IF NOT EXISTS `items` (
  `item_id`           INTEGER PRIMARY KEY,
  `user_id`           TEXT NOT NULL,
  `item_name`         TEXT NOT NULL,
  `item_level`        INTEGER NOT NULL,
  `attack`            INTEGER DEFAULT 0,
  `defence`           INTEGER DEFAULT 0,
  `rarity`            INTEGER DEFAULT 0,
  `base_rarity`       INTEGER NOT NULL DEFAULT 3,
  `passive`           TEXT NOT NULL DEFAULT 'none',
  `pinnacle_passive`  TEXT NOT NULL DEFAULT 'none',
  `utmost_passive`    TEXT NOT NULL DEFAULT 'none',
  `infernal_passive`  TEXT NOT NULL DEFAULT 'none',
  `forge_tier`        INTEGER DEFAULT 0,
  `forges_remaining`  INTEGER DEFAULT 0,
  `refines_remaining` INTEGER DEFAULT 0,
  `refinement_lvl`    INTEGER DEFAULT 0,
  `hit_chance`        REAL NOT NULL DEFAULT 0.60,
  `crit_chance`       REAL NOT NULL DEFAULT 0.00,
  `crit_multi`        REAL NOT NULL DEFAULT 2.00,
  `is_equipped`       BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS `armor` (
  `item_id`                  INTEGER PRIMARY KEY,
  `user_id`                  TEXT NOT NULL,
  `item_name`                TEXT NOT NULL,
  `item_level`               INTEGER NOT NULL,
  `main_stat_type`           TEXT NOT NULL DEFAULT 'def',
  `main_stat`                INTEGER DEFAULT 0,
  `block`                    INTEGER DEFAULT 0,
  `evasion`                  INTEGER DEFAULT 0,
  `ward`                     INTEGER DEFAULT 0,
  `pdr`                      INTEGER DEFAULT 0,
  `fdr`                      INTEGER DEFAULT 0,
  `armor_passive`            TEXT NOT NULL DEFAULT 'none',
  `celestial_armor_passive`  TEXT NOT NULL DEFAULT 'none',
  `temper_remaining`         INTEGER DEFAULT 0,
  `imbue_remaining`          INTEGER DEFAULT 1,
  `reinforces_remaining`     INTEGER DEFAULT 0,
  `reinforcement_lvl`        INTEGER DEFAULT 0,
  `is_equipped`              BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS `accessories` (
  `item_id`             INTEGER PRIMARY KEY,
  `user_id`             TEXT NOT NULL,
  `item_name`           TEXT NOT NULL,
  `item_level`          INTEGER NOT NULL,
  `attack`              INTEGER DEFAULT 0,
  `defence`             INTEGER DEFAULT 0,
  `rarity`              INTEGER DEFAULT 0,
  `ward`                INTEGER DEFAULT 0,
  `crit`                INTEGER DEFAULT 0,
  `passive`             TEXT NOT NULL DEFAULT 'none',
  `passive_lvl`         INTEGER DEFAULT 0,
  `void_passive`        TEXT DEFAULT 'none',
  `potential_remaining` INTEGER DEFAULT 10,
  `is_equipped`         BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS `gloves` (
  `item_id`             INTEGER PRIMARY KEY,
  `user_id`             TEXT NOT NULL,
  `item_name`           TEXT NOT NULL,
  `item_level`          INTEGER NOT NULL,
  `attack`              INTEGER DEFAULT 0,
  `defence`             INTEGER DEFAULT 0,
  `ward`                INTEGER DEFAULT 0,
  `pdr`                 INTEGER DEFAULT 0,
  `fdr`                 INTEGER DEFAULT 0,
  `passive`             TEXT NOT NULL DEFAULT 'none',
  `passive_lvl`         INTEGER DEFAULT 0,
  `essence_1`           TEXT DEFAULT 'none',
  `essence_1_val`       REAL DEFAULT 0,
  `essence_2`           TEXT DEFAULT 'none',
  `essence_2_val`       REAL DEFAULT 0,
  `essence_3`           TEXT DEFAULT 'none',
  `essence_3_val`       REAL DEFAULT 0,
  `corrupted_essence`   TEXT DEFAULT 'none',
  `potential_remaining` INTEGER DEFAULT 5,
  `reinforces_remaining` INTEGER DEFAULT 0,
  `reinforcement_lvl`   INTEGER DEFAULT 0,
  `is_equipped`         BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS `boots` (
  `item_id`             INTEGER PRIMARY KEY,
  `user_id`             TEXT NOT NULL,
  `item_name`           TEXT NOT NULL,
  `item_level`          INTEGER NOT NULL,
  `attack`              INTEGER DEFAULT 0,
  `defence`             INTEGER DEFAULT 0,
  `ward`                INTEGER DEFAULT 0,
  `pdr`                 INTEGER DEFAULT 0,
  `fdr`                 INTEGER DEFAULT 0,
  `passive`             TEXT NOT NULL DEFAULT 'none',
  `passive_lvl`         INTEGER DEFAULT 0,
  `essence_1`           TEXT DEFAULT 'none',
  `essence_1_val`       REAL DEFAULT 0,
  `essence_2`           TEXT DEFAULT 'none',
  `essence_2_val`       REAL DEFAULT 0,
  `essence_3`           TEXT DEFAULT 'none',
  `essence_3_val`       REAL DEFAULT 0,
  `corrupted_essence`   TEXT DEFAULT 'none',
  `potential_remaining` INTEGER DEFAULT 6,
  `reinforces_remaining` INTEGER DEFAULT 0,
  `reinforcement_lvl`   INTEGER DEFAULT 0,
  `is_equipped`         BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS helmets (
  item_id               INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id               TEXT NOT NULL,
  item_name             TEXT NOT NULL,
  item_level            INTEGER NOT NULL,
  defence               INTEGER DEFAULT 0,
  ward                  INTEGER DEFAULT 0,
  pdr                   INTEGER DEFAULT 0,
  fdr                   INTEGER DEFAULT 0,
  passive               TEXT DEFAULT 'none',
  passive_lvl           INTEGER DEFAULT 0,
  essence_1             TEXT DEFAULT 'none',
  essence_1_val         REAL DEFAULT 0,
  essence_2             TEXT DEFAULT 'none',
  essence_2_val         REAL DEFAULT 0,
  essence_3             TEXT DEFAULT 'none',
  essence_3_val         REAL DEFAULT 0,
  corrupted_essence     TEXT DEFAULT 'none',
  potential_remaining   INTEGER DEFAULT 5,
  reinforces_remaining  INTEGER DEFAULT 0,
  reinforcement_lvl     INTEGER DEFAULT 0,
  is_equipped           BOOLEAN DEFAULT 0
);


CREATE TABLE IF NOT EXISTS gear_loadouts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      TEXT    NOT NULL,
  slot_index   INTEGER NOT NULL,
  name         TEXT    NOT NULL DEFAULT 'Loadout',
  weapon_id    INTEGER DEFAULT NULL,
  armor_id     INTEGER DEFAULT NULL,
  helmet_id    INTEGER DEFAULT NULL,
  glove_id     INTEGER DEFAULT NULL,
  boot_id      INTEGER DEFAULT NULL,
  accessory_id INTEGER DEFAULT NULL,
  UNIQUE(user_id, slot_index)
);


-- ============================================================
-- GATHERING / SKILLS
-- ============================================================

CREATE TABLE IF NOT EXISTS `mining` (
  `user_id`       TEXT NOT NULL,
  `server_id`     TEXT NOT NULL,
  `pickaxe_tier`  TEXT DEFAULT 'iron',
  -- Ore
  `iron_ore`      INTEGER DEFAULT 0,
  `coal_ore`      INTEGER DEFAULT 0,
  `gold_ore`      INTEGER DEFAULT 0,
  `platinum_ore`  INTEGER DEFAULT 0,
  `idea_ore`      INTEGER DEFAULT 0,
  -- Bars
  `iron_bar`      INTEGER DEFAULT 0,
  `steel_bar`     INTEGER DEFAULT 0,
  `gold_bar`      INTEGER DEFAULT 0,
  `platinum_bar`  INTEGER DEFAULT 0,
  `idea_bar`      INTEGER DEFAULT 0,
  -- Session state
  `familiarization_end` TEXT DEFAULT NULL,
  `momentum_minutes`    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `fishing` (
  `user_id`            TEXT,
  `server_id`          TEXT,
  `fishing_rod`        TEXT DEFAULT 'desiccated',
  -- Bones
  `desiccated_bones`   INTEGER DEFAULT 0,
  `regular_bones`      INTEGER DEFAULT 0,
  `sturdy_bones`       INTEGER DEFAULT 0,
  `reinforced_bones`   INTEGER DEFAULT 0,
  `titanium_bones`     INTEGER DEFAULT 0,
  -- Essence
  `desiccated_essence` INTEGER DEFAULT 0,
  `regular_essence`    INTEGER DEFAULT 0,
  `sturdy_essence`     INTEGER DEFAULT 0,
  `reinforced_essence` INTEGER DEFAULT 0,
  `titanium_essence`   INTEGER DEFAULT 0,
  -- Session state
  `familiarization_end` TEXT DEFAULT NULL,
  `momentum_minutes`    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `woodcutting` (
  `user_id`          TEXT,
  `server_id`        TEXT,
  `axe_type`         TEXT DEFAULT 'flimsy',
  -- Logs
  `oak_logs`         INTEGER DEFAULT 0,
  `willow_logs`      INTEGER DEFAULT 0,
  `mahogany_logs`    INTEGER DEFAULT 0,
  `magic_logs`       INTEGER DEFAULT 0,
  `idea_logs`        INTEGER DEFAULT 0,
  -- Planks
  `oak_plank`        INTEGER DEFAULT 0,
  `willow_plank`     INTEGER DEFAULT 0,
  `mahogany_plank`   INTEGER DEFAULT 0,
  `magic_plank`      INTEGER DEFAULT 0,
  `idea_plank`       INTEGER DEFAULT 0,
  -- Session state
  `familiarization_end` TEXT DEFAULT NULL,
  `momentum_minutes`    INTEGER DEFAULT 0
);

-- Per design doc (docs/design/gathering_mastery.md) + 2026 expansions:
-- Points exclusively from hourly passive (1.8/day at BiS tool), 3-branch trees per skill + 10 bonus pts/branch,
-- Nature's Attunement cross-skill tree (3 nodes x 5 pts, gate = 20+ invested in each main tree),
-- Mastery Insight (post-max infinite scaling: 5 excess pts -> 1 insight, tiny global yield / remnant / rune bonuses),
-- Remnants via Quality branch + Rich procs, Rune of Nature (68x3 remnants + 350k gold + 2 spirit stones),
-- Respecs (1 rune per skill)
-- Prestige gathering bosses (Golem/Leviathan/Colossus) with triple ticks + Free Yourself snare.
CREATE TABLE IF NOT EXISTS gathering_mastery (
  user_id                    TEXT NOT NULL,
  server_id                  TEXT NOT NULL,
  -- Mastery points and allocation
  mining_points              INTEGER DEFAULT 0,
  fishing_points             INTEGER DEFAULT 0,
  woodcutting_points         INTEGER DEFAULT 0,
  mining_alloc               TEXT DEFAULT '{}',
  fishing_alloc              TEXT DEFAULT '{}',
  woodcutting_alloc          TEXT DEFAULT '{}',
  attunement_alloc           TEXT DEFAULT '{}',
  total_mastery_invested     INTEGER DEFAULT 0,
  mastery_insight            INTEGER DEFAULT 0,
  last_point_claim           TEXT,
  -- Remnant currencies (Quality branch output, used for Rune crafting + Black Market)
  geode_cores                INTEGER DEFAULT 0,
  tide_relics                INTEGER DEFAULT 0,
  heartwood_shards           INTEGER DEFAULT 0,
  -- Prestige boss tracking
  mining_tripled_ticks       INTEGER DEFAULT 0,
  fishing_tripled_ticks      INTEGER DEFAULT 0,
  woodcutting_tripled_ticks  INTEGER DEFAULT 0,
  -- Elemental boss keys
  blessed_bismuth            INTEGER DEFAULT 0,
  sparkling_sprig            INTEGER DEFAULT 0,
  capricious_carp            INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, server_id)
);


-- ============================================================
-- MONSTERS & CREATURE PARTS
-- ============================================================

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
-- COMPANIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS companions (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id              TEXT NOT NULL,
  name                 TEXT,
  species              TEXT,
  image_url            TEXT,
  level                INTEGER DEFAULT 1,
  exp                  INTEGER DEFAULT 0,
  passive_type         TEXT,
  passive_tier         INTEGER,
  balanced_passive     TEXT DEFAULT 'none',
  balanced_passive_tier INTEGER DEFAULT 0,
  is_active            INTEGER DEFAULT 0,
  created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Three branches (Forager / Affinity / Bonded), 3 nodes each.
-- Kinship Points earned from converting XP.
-- nodes_owned: JSON {node_id: true | "choice_str"}.  Choice nodes store the player's pick.
CREATE TABLE IF NOT EXISTS companion_mastery (
  user_id        TEXT NOT NULL,
  server_id      TEXT NOT NULL,
  nodes_owned    TEXT NOT NULL DEFAULT '{}',
  points_spent   INTEGER NOT NULL DEFAULT 0,
  kinship_points INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, server_id)
);


-- ============================================================
-- PARTNERS
-- ============================================================

CREATE TABLE IF NOT EXISTS user_partners (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id               TEXT NOT NULL,
  partner_id            INTEGER NOT NULL,
  level                 INTEGER NOT NULL DEFAULT 1,
  exp                   INTEGER NOT NULL DEFAULT 0,
  -- Combat skills
  combat_slot_1         TEXT DEFAULT NULL,
  combat_slot_1_lvl     INTEGER NOT NULL DEFAULT 1,
  combat_slot_2         TEXT DEFAULT NULL,
  combat_slot_2_lvl     INTEGER NOT NULL DEFAULT 1,
  combat_slot_3         TEXT DEFAULT NULL,
  combat_slot_3_lvl     INTEGER NOT NULL DEFAULT 1,
  sig_combat_lvl        INTEGER NOT NULL DEFAULT 1,
  -- Dispatch skills
  dispatch_slot_1       TEXT DEFAULT NULL,
  dispatch_slot_1_lvl   INTEGER NOT NULL DEFAULT 1,
  dispatch_slot_2       TEXT DEFAULT NULL,
  dispatch_slot_2_lvl   INTEGER NOT NULL DEFAULT 1,
  dispatch_slot_3       TEXT DEFAULT NULL,
  dispatch_slot_3_lvl   INTEGER NOT NULL DEFAULT 1,
  sig_dispatch_lvl      INTEGER NOT NULL DEFAULT 1,
  -- Active dispatch state
  dispatch_task         TEXT DEFAULT NULL,
  dispatch_start_time   TEXT DEFAULT NULL,
  dispatch_task_2       TEXT DEFAULT NULL,
  dispatch_start_time_2 TEXT DEFAULT NULL,
  -- Status flags
  is_active_combat      INTEGER NOT NULL DEFAULT 0,
  is_dispatched         INTEGER NOT NULL DEFAULT 0,
  -- Affinity
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


-- ============================================================
-- SOCIAL
-- ============================================================

CREATE TABLE IF NOT EXISTS `ideologies` (
  `id`         INTEGER PRIMARY KEY,
  `user_id`    TEXT NOT NULL,
  `server_id`  TEXT NOT NULL,
  `name`       TEXT NOT NULL,
  `followers`  INTEGER NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- PROGRESSION
-- ============================================================

CREATE TABLE IF NOT EXISTS `journey_milestones` (
  `user_id`         TEXT    NOT NULL,
  `milestone_level` INTEGER NOT NULL,
  `claimed_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`, `milestone_level`)
);

CREATE TABLE IF NOT EXISTS `ascension_unlocks` (
  `user_id` TEXT NOT NULL,
  `floor`   INTEGER NOT NULL,
  PRIMARY KEY (`user_id`, `floor`)
);

CREATE TABLE IF NOT EXISTS codex_progress (
  user_id        TEXT NOT NULL,
  chapter_id     INTEGER NOT NULL,
  clears         INTEGER NOT NULL DEFAULT 0,
  perfect_clears INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, chapter_id)
);

CREATE TABLE IF NOT EXISTS codex_tomes (
  user_id      TEXT NOT NULL,
  slot         INTEGER NOT NULL,
  passive_type TEXT NOT NULL,
  tier         INTEGER NOT NULL DEFAULT 0,
  value        REAL NOT NULL DEFAULT 0.0,
  PRIMARY KEY (user_id, slot)
);


-- ============================================================
-- ENDGAME COMBAT
-- ============================================================

CREATE TABLE IF NOT EXISTS `slayer_profiles` (
  `user_id`               TEXT,
  `server_id`             TEXT,
  `level`                 INTEGER DEFAULT 1,
  `xp`                    INTEGER DEFAULT 0,
  `slayer_points`         INTEGER DEFAULT 0,
  `violent_essence`       INTEGER DEFAULT 0,
  `imbued_heart`          INTEGER DEFAULT 0,
  `active_task_species`   TEXT,
  `active_task_amount`    INTEGER DEFAULT 0,
  `active_task_progress`  INTEGER DEFAULT 0,
  PRIMARY KEY (`user_id`, `server_id`)
);

CREATE TABLE IF NOT EXISTS `slayer_emblems` (
  `user_id`    TEXT,
  `server_id`  TEXT,
  `slot_1_type` TEXT DEFAULT 'none', `slot_1_tier` INTEGER DEFAULT 1,
  `slot_2_type` TEXT DEFAULT 'none', `slot_2_tier` INTEGER DEFAULT 1,
  `slot_3_type` TEXT DEFAULT 'none', `slot_3_tier` INTEGER DEFAULT 1,
  `slot_4_type` TEXT DEFAULT 'none', `slot_4_tier` INTEGER DEFAULT 1,
  `slot_5_type` TEXT DEFAULT 'none', `slot_5_tier` INTEGER DEFAULT 1,
  PRIMARY KEY (`user_id`, `server_id`)
);

CREATE TABLE IF NOT EXISTS slayer_tree (
  user_id      TEXT    NOT NULL,
  server_id    TEXT    NOT NULL,
  nodes_owned  TEXT    NOT NULL DEFAULT '{}',
  points_spent INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS uber_progress (
  user_id                          TEXT NOT NULL,
  server_id                        TEXT NOT NULL,
  -- Celestial
  celestial_sigils                 INTEGER DEFAULT 0,
  celestial_engrams                INTEGER DEFAULT 0,
  celestial_blueprint_unlocked     INTEGER DEFAULT 0,
  -- Infernal
  infernal_sigils                  INTEGER DEFAULT 0,
  infernal_engrams                 INTEGER DEFAULT 0,
  infernal_blueprint_unlocked      INTEGER DEFAULT 0,
  -- Void
  void_shards                      INTEGER DEFAULT 0,
  void_engrams                     INTEGER DEFAULT 0,
  void_blueprint_unlocked          INTEGER DEFAULT 0,
  -- Gemini
  gemini_sigils                    INTEGER DEFAULT 0,
  gemini_engrams                   INTEGER DEFAULT 0,
  gemini_blueprint_unlocked        INTEGER DEFAULT 0,
  -- Corruption / Paradise
  corruption_sigils                INTEGER DEFAULT 0,
  corruption_engrams               INTEGER DEFAULT 0,
  corruption_blueprint_unlocked    INTEGER DEFAULT 0,
  paradise_jewels                  INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, server_id)
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

CREATE TABLE IF NOT EXISTS boss_party_dispatch (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     TEXT NOT NULL,
  server_id   TEXT NOT NULL,
  attacker_id INTEGER NOT NULL,
  tank_id     INTEGER NOT NULL,
  healer_id   INTEGER NOT NULL,
  boss_name   TEXT NOT NULL,
  boss_max_hp INTEGER NOT NULL,
  start_time  TEXT NOT NULL,
  UNIQUE(user_id, server_id)
);

CREATE TABLE IF NOT EXISTS duel_stats (
  user_id TEXT PRIMARY KEY,
  wins    INTEGER NOT NULL DEFAULT 0,
  losses  INTEGER NOT NULL DEFAULT 0
);


-- ============================================================
-- ALCHEMY
-- ============================================================

CREATE TABLE IF NOT EXISTS alchemy_data (
  user_id       TEXT PRIMARY KEY,
  level         INTEGER NOT NULL DEFAULT 1,
  free_roll_used INTEGER NOT NULL DEFAULT 0,
  cosmic_dust   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS potion_passives (
  user_id       TEXT NOT NULL,
  slot          INTEGER NOT NULL,
  passive_type  TEXT NOT NULL,
  passive_value REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, slot)
);

-- Stores live progress for the 9-step reagent choice + event system.
-- `data` is JSON: base_type, duration_mod, value_mod, active_modifiers, history, dust_spent, etc.
CREATE TABLE IF NOT EXISTS potion_distillations (
  user_id    TEXT NOT NULL,
  server_id  TEXT NOT NULL,
  step       INTEGER NOT NULL DEFAULT 0,
  data       TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, server_id)
);

-- Codex run save state (chapter-boundary snapshots; `data` is a JSON blob:
-- chapters, chapter_idx, boons, run_state, deaths, cumulative xp/gold, hp, run penalties)
CREATE TABLE IF NOT EXISTS codex_runs (
  user_id    TEXT NOT NULL,
  server_id  TEXT NOT NULL,
  data       TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, server_id)
);

-- Rite of Convergence run save state (room-boundary snapshots; `data` is a JSON blob:
-- attempts_remaining, wings_cleared, room_entry_hp/potions, writ_selection, total_turns)
CREATE TABLE IF NOT EXISTS rite_runs (
  user_id    TEXT NOT NULL,
  server_id  TEXT NOT NULL,
  data       TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, server_id)
);

-- Permanent per-player unlock flag: writs are locked until the first full Rite clear.
CREATE TABLE IF NOT EXISTS rite_progress (
  user_id          TEXT NOT NULL,
  server_id        TEXT NOT NULL,
  has_first_clear  INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, server_id)
);

-- The Rite of Convergence's single Artefact slot. A new drop overwrites
-- whatever was previously equipped (no separate inventory — see
-- core/rite/models.py). roll_1-3 hold the artefact's randomized stat value(s);
-- unused for artefacts with no variable roll.
CREATE TABLE IF NOT EXISTS player_artefacts (
  user_id      TEXT NOT NULL,
  server_id    TEXT NOT NULL,
  artefact_key TEXT NOT NULL,
  roll_1       REAL NOT NULL DEFAULT 0,
  roll_2       REAL NOT NULL DEFAULT 0,
  roll_3       REAL NOT NULL DEFAULT 0,
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


-- ============================================================
-- HEMATURGY
-- ============================================================

CREATE TABLE IF NOT EXISTS hematurgy_blood (
  user_id      TEXT PRIMARY KEY,
  primordial   INTEGER NOT NULL DEFAULT 0,
  evolutionary INTEGER NOT NULL DEFAULT 0,
  mutative     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hematurgy_passives (
  user_id    TEXT NOT NULL,
  slot_type  TEXT NOT NULL,
  passive_id TEXT NOT NULL,
  tier       INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (user_id, slot_type)
);


-- ============================================================
-- PARADISE JEWEL
-- ============================================================

CREATE TABLE IF NOT EXISTS paradise_jewel_data (
  user_id                 TEXT PRIMARY KEY,
  unlocked_skills         TEXT NOT NULL DEFAULT '[]',
  equipped_skill          TEXT DEFAULT NULL,
  skill_levels            TEXT NOT NULL DEFAULT '{}',
  skill_charges           TEXT NOT NULL DEFAULT '{}',
  skill_engrams           TEXT NOT NULL DEFAULT '{}',
  passive_slots           TEXT NOT NULL DEFAULT '[]',
  passive_jewels_invested INTEGER NOT NULL DEFAULT 0,
  total_jewels_obtained   INTEGER NOT NULL DEFAULT 0,
  total_jewels_consumed   INTEGER NOT NULL DEFAULT 0
);


-- ============================================================
-- APEX HUNTS
-- ============================================================

CREATE TABLE IF NOT EXISTS apex_hunt_profiles (
  user_id          TEXT NOT NULL,
  server_id        TEXT NOT NULL,
  hunt_charges     INTEGER NOT NULL DEFAULT 5,
  last_charge_time REAL    DEFAULT NULL,
  -- Win/loss per zone
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
  user_id          TEXT NOT NULL,
  server_id        TEXT NOT NULL,
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
  user_id         TEXT NOT NULL,
  server_id       TEXT NOT NULL,
  sharpened_fang  INTEGER NOT NULL DEFAULT 0,
  engorged_heart  INTEGER NOT NULL DEFAULT 0,
  condensed_blood INTEGER NOT NULL DEFAULT 0,
  primal_essence  INTEGER NOT NULL DEFAULT 0,
  soul_vessel     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, server_id)
);


-- ============================================================
-- SETTLEMENT
-- ============================================================

CREATE TABLE IF NOT EXISTS settlements (
  user_id                   TEXT,
  server_id                 TEXT,
  town_hall_tier            INTEGER DEFAULT 1,
  building_slots            INTEGER DEFAULT 3,
  timber                    INTEGER DEFAULT 0,
  stone                     INTEGER DEFAULT 0,
  last_collection_time      TEXT DEFAULT NULL,
  last_zeal_gather_time     TEXT DEFAULT NULL,
  last_war_camp_stamina_time TEXT DEFAULT NULL,
  -- Zeal economy
  settlement_zeal           INTEGER NOT NULL DEFAULT 0,
  pending_zeal              INTEGER NOT NULL DEFAULT 0,
  zeal_earned_today         INTEGER NOT NULL DEFAULT 0,
  last_zeal_reset           TEXT DEFAULT NULL,
  -- Development turns
  total_development_turns   INTEGER NOT NULL DEFAULT 0,
  development_contracts     INTEGER NOT NULL DEFAULT 0,
  dc_crafted_today          INTEGER NOT NULL DEFAULT 0,
  last_dc_craft_date        TEXT DEFAULT NULL,
  -- Resources
  idlem                     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, server_id)
);

CREATE TABLE IF NOT EXISTS settlement_materials (
  user_id               TEXT PRIMARY KEY,
  magma_core            INTEGER NOT NULL DEFAULT 0,
  life_root             INTEGER NOT NULL DEFAULT 0,
  spirit_shard          INTEGER NOT NULL DEFAULT 0,
  celestial_stone       INTEGER NOT NULL DEFAULT 0,
  void_crystal          INTEGER NOT NULL DEFAULT 0,
  infernal_cinder       INTEGER NOT NULL DEFAULT 0,
  bound_crystal         INTEGER NOT NULL DEFAULT 0,
  diviners_rod          INTEGER NOT NULL DEFAULT 0,
  unidentified_blueprint INTEGER NOT NULL DEFAULT 0,
  corrupted_core        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS buildings (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       TEXT,
  server_id     TEXT,
  building_type TEXT,
  tier          INTEGER DEFAULT 1,
  slot_index    INTEGER,
  workers_assigned INTEGER DEFAULT 0,
  plot_index    INTEGER DEFAULT NULL,  -- which settlement plot this building occupies (1-20)
  is_meta       INTEGER NOT NULL DEFAULT 0,  -- 1 = meta building (no tier, doesn't count toward slot cap)
  is_disabled   INTEGER NOT NULL DEFAULT 0,  -- 1 = disabled by crisis event; requires repair
  UNIQUE(user_id, server_id, slot_index)
);

-- blueprint from uber_progress gates the build; is_unlocked = statue built
CREATE TABLE IF NOT EXISTS uber_shrine_statues (
  user_id          TEXT NOT NULL,
  server_id        TEXT NOT NULL,
  statue_type      TEXT NOT NULL,  -- 'celestial' | 'infernal' | 'void' | 'bound' | 'corrupted'
  is_unlocked      INTEGER NOT NULL DEFAULT 0,
  workers_assigned INTEGER NOT NULL DEFAULT 0,
  tier             INTEGER NOT NULL DEFAULT 1,
  slot_index       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, server_id, statue_type)
);

-- 5×5 grid (corners excluded) = 20 developable plots + Town Hall at center. Plot indices 1–20.
CREATE TABLE IF NOT EXISTS settlement_plots (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     TEXT NOT NULL,
  server_id   TEXT NOT NULL,
  plot_index  INTEGER NOT NULL,
  is_developed INTEGER NOT NULL DEFAULT 0,
  bonus_type  TEXT DEFAULT NULL,
  UNIQUE(user_id, server_id, plot_index)
);

CREATE TABLE IF NOT EXISTS settlement_research (
  user_id       TEXT NOT NULL,
  server_id     TEXT NOT NULL,
  building_type TEXT NOT NULL,
  start_time    TEXT NOT NULL DEFAULT '',
  completed     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, server_id, building_type)
);

-- Each row is one in-progress project spending Development Turns.
-- Uniqueness enforced at app layer (upsert_project) to avoid SQLite's prohibition on
-- expressions in UNIQUE constraints.
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

-- Multi-turn Black Market deals waiting to be processed by Next Turn.
CREATE TABLE IF NOT EXISTS settlement_pending_deals (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         TEXT    NOT NULL,
  server_id       TEXT    NOT NULL,
  offer_data      TEXT    NOT NULL,  -- JSON: {resource: qty, ...}
  total_value     INTEGER NOT NULL,
  turns_remaining INTEGER NOT NULL,
  active_biases   TEXT    NOT NULL DEFAULT '[]',
  created_turn    INTEGER NOT NULL DEFAULT 0,
  UNIQUE(user_id, server_id)
);

-- Active settlement events (upcoming, ongoing, instant-resolved).
CREATE TABLE IF NOT EXISTS settlement_active_events (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         TEXT    NOT NULL,
  server_id       TEXT    NOT NULL,
  event_key       TEXT    NOT NULL,
  event_type      TEXT    NOT NULL,  -- 'upcoming','ongoing','instant'
  turns_until     INTEGER NOT NULL DEFAULT 0,
  turns_remaining INTEGER NOT NULL DEFAULT 0,
  data            TEXT    DEFAULT NULL
);

-- Black Market passive tree node investment (Idlem-powered).
CREATE TABLE IF NOT EXISTS bm_passive_tree (
  user_id   TEXT    NOT NULL,
  server_id TEXT    NOT NULL,
  node_key  TEXT    NOT NULL,
  level     INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (user_id, server_id, node_key)
);


-- ============================================================
-- DELVE
-- ============================================================

CREATE TABLE IF NOT EXISTS delve_progress (
  user_id        TEXT NOT NULL,
  server_id      TEXT NOT NULL,
  delve_xp       INTEGER DEFAULT 0,
  obsidian_shards INTEGER DEFAULT 0,
  fuel_level     INTEGER DEFAULT 1,
  struct_level   INTEGER DEFAULT 1,
  sensor_level   INTEGER DEFAULT 1,
  PRIMARY KEY (user_id, server_id)
);


-- ============================================================
-- MISC / ECONOMY
-- ============================================================

CREATE TABLE IF NOT EXISTS player_essences (
  user_id      TEXT NOT NULL,
  essence_type TEXT NOT NULL,
  quantity     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, essence_type)
);

CREATE TABLE IF NOT EXISTS `prestige_owned` (
  `user_id`   TEXT NOT NULL,
  `item_type` TEXT NOT NULL,
  `item_key`  TEXT NOT NULL,
  PRIMARY KEY (`user_id`, `item_type`, `item_key`)
);

-- ============================================================
-- HALL OF FIRSTS
-- ============================================================

-- Global (one bot instance, effectively one server) "first player to reach
-- X" tracker. One row per category, first-write-wins via INSERT OR IGNORE.
-- Snapshot columns freeze how the player looked at the moment of claiming,
-- independent of later cosmetic changes.
CREATE TABLE IF NOT EXISTS `hall_of_firsts` (
  `category_key`        TEXT PRIMARY KEY,
  `user_id`             TEXT NOT NULL,
  `achieved_at`          TEXT NOT NULL,
  `snapshot_name`        TEXT NOT NULL,
  `snapshot_title`       TEXT,
  `snapshot_emblem`      TEXT,
  `snapshot_appearance`  TEXT
);


-- ============================================================
-- REDEEM CODES
-- ============================================================

CREATE TABLE IF NOT EXISTS redeem_codes (
  code          TEXT PRIMARY KEY,
  rewards       TEXT NOT NULL,           -- JSON: {"gold": 200000, "curios": 10, ...}
  max_uses      INTEGER DEFAULT NULL,    -- NULL = no global cap (still 1-use per user)
  total_uses    INTEGER NOT NULL DEFAULT 0,
  is_admin_only INTEGER NOT NULL DEFAULT 0,
  expires_at    TEXT DEFAULT NULL,       -- ISO datetime, NULL = never
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS code_redemptions (
  code        TEXT NOT NULL,
  user_id     TEXT NOT NULL,
  redeemed_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (code, user_id)
);


-- ============================================================
-- NETHER MARKET
-- ============================================================
-- Self-contained economy/PvP mini-game. Items are flavor-only "curiosities"
-- with no interaction with any other item table. Scoped per (user_id, server_id)
-- like Apex/Companion Mastery; rotation is shared per server_id.

CREATE TABLE IF NOT EXISTS nether_market_rotation (
  server_id          TEXT PRIMARY KEY,
  cheap_lo_item      TEXT,
  cheap_lo_price     INTEGER,
  cheap_hi_item      TEXT,
  cheap_hi_price     INTEGER,
  med_lo_item        TEXT,
  med_lo_price       INTEGER,
  med_hi_item        TEXT,
  med_hi_price       INTEGER,
  expensive_lo_item  TEXT,
  expensive_lo_price INTEGER,
  expensive_hi_item  TEXT,
  expensive_hi_price INTEGER,
  rotated_at         REAL
);

CREATE TABLE IF NOT EXISTS nether_market_holdings (
  user_id   TEXT    NOT NULL,
  server_id TEXT    NOT NULL,
  item_key  TEXT    NOT NULL,
  quantity  INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, server_id, item_key)
);

CREATE TABLE IF NOT EXISTS nether_market_profile (
  user_id                   TEXT    NOT NULL,
  server_id                 TEXT    NOT NULL,
  nether_marks              INTEGER NOT NULL DEFAULT 0,
  mastery_nodes             TEXT    NOT NULL DEFAULT '{}',
  plunder_charges           INTEGER NOT NULL DEFAULT 3,
  last_charge_time          REAL    DEFAULT NULL,
  shield_expires_at         REAL    DEFAULT NULL,
  last_plundered_at         REAL    DEFAULT NULL,
  pending_plunder_notice    TEXT    DEFAULT NULL,
  PRIMARY KEY (user_id, server_id)
);


-- ============================================================
-- INFRASTRUCTURE
-- ============================================================

CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id         TEXT PRIMARY KEY,
  event_channel_id TEXT
);

-- Tracks which tutorial prompts a player has already been shown.
-- Keyed by (user_id, feature_key); no server_id needed since tutorials are per-player globally.
CREATE TABLE IF NOT EXISTS tutorial_seen (
  user_id     TEXT NOT NULL,
  feature_key TEXT NOT NULL,
  seen_at     TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, feature_key)
);