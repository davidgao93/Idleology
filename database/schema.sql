-- Drop the tables if they exist
--DROP TABLE IF EXISTS `users`;
--DROP TABLE IF EXISTS `ideologies`;
--DROP TABLE IF EXISTS `items`;
--DROP TABLE IF EXISTS `fishing`;
--DROP TABLE IF EXISTS `woodcutting`;
--DROP TABLE IF EXISTS `mining`;
-- ALTER TABLE users ADD COLUMN `dragon_key` INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE users ADD COLUMN `angel_key` INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE users ADD COLUMN `imbue_runes` INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE users ADD COLUMN `soul_cores` INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE accessories ADD COLUMN `passive_lvl` INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE items ADD COLUMN `refinement_lvl` INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE users ADD COLUMN `last_combat` TIMESTAMP DEFAULT NULL;

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
  `last_checkin_time` TIMESTAMP DEFAULT NULL,  -- New column for storing the last check-in time
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
  `soul_cores` INTEGER NOT NULL DEFAULT 0
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
  `refinement_lvl` INTEGER DEFAULT 0
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
  `passive_lvl` INTEGER DEFAULT 0
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
  `imbue_remaining` INTEGER DEFAULT 1
);


CREATE TABLE IF NOT EXISTS mining (
    `user_id` TEXT NOT NULL,
    `server_id` TEXT NOT NULL,
    `pickaxe_tier` TEXT DEFAULT 'iron',
    `iron` INTEGER DEFAULT 0,
    `coal` INTEGER DEFAULT 0,
    `gold` INTEGER DEFAULT 0,
    `platinum` INTEGER DEFAULT 0,
    `idea` INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fishing (
    `user_id` TEXT,
    `server_id` TEXT,
    `fishing_rod` TEXT DEFAULT 'desiccated',
    `desiccated_bones` INTEGER DEFAULT 0,
    `regular_bones` INTEGER DEFAULT 0,
    `sturdy_bones` INTEGER DEFAULT 0,
    `reinforced_bones` INTEGER DEFAULT 0,
    `titanium_bones` INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS woodcutting (
    `user_id` TEXT,
    `server_id` TEXT,
    `axe_type` TEXT DEFAULT 'flimsy',
    `oak_logs` INTEGER DEFAULT 0,
    `willow_logs` INTEGER DEFAULT 0,
    `mahogany_logs` INTEGER DEFAULT 0,
    `magic_logs` INTEGER DEFAULT 0,
    `idea_logs` INTEGER DEFAULT 0
);