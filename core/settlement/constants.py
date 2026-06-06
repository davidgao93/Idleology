# core/settlement/constants.py
"""All static configuration for the settlement system."""

RESOURCE_DISPLAY_NAMES = {
    "timber": "Timber",
    "stone": "Stone",
    "gold": "Gold",
    "iron": "Iron Ore",
    "coal": "Coal",
    "platinum": "Platinum Ore",
    "idea": "Idea Ore",
    "iron_bar": "Iron Bars",
    "steel_bar": "Steel Bars",
    "gold_bar": "Gold Bars",
    "platinum_bar": "Platinum Bars",
    "idea_bar": "Idea Bars",
    "oak_logs": "Oak Logs",
    "willow_logs": "Willow Logs",
    "mahogany_logs": "Mahogany Logs",
    "magic_logs": "Magic Logs",
    "idea_logs": "Idea Logs",
    "oak_plank": "Oak Planks",
    "willow_plank": "Willow Planks",
    "mahogany_plank": "Mahogany Planks",
    "magic_plank": "Magic Planks",
    "idea_plank": "Idea Planks",
    "desiccated_bones": "Desiccated Bones",
    "regular_bones": "Regular Bones",
    "sturdy_bones": "Sturdy Bones",
    "reinforced_bones": "Reinforced Bones",
    "titanium_bones": "Titanium Bones",
    "desiccated_essence": "Desiccated Essence",
    "regular_essence": "Regular Essence",
    "sturdy_essence": "Sturdy Essence",
    "reinforced_essence": "Reinforced Essence",
    "titanium_essence": "Titanium Essence",
}

# Unified building info (used by dashboard, construction, and detail views)
BUILDING_INFO = {
    "logging_camp": "Generates Timber over time.",
    "quarry": "Generates Stone over time.",
    "foundry": "Converts Ore into Ingots. Each tier unlocks the next ore type (T1→Iron, T2→Coal, T3→Gold, T4→Platinum, T5→Idea). All unlocked tiers are processed simultaneously; higher tiers convert at a slower rate.",
    "sawmill": "Converts Logs into Planks. Each tier unlocks the next log type (T1→Oak, T2→Willow, T3→Mahogany, T4→Magic, T5→Idea). All unlocked tiers are processed simultaneously; higher tiers convert at a slower rate.",
    "reliquary": "Converts Bones into Essence. Each tier unlocks the next bone type (T1→Desiccated, T2→Regular, T3→Sturdy, T4→Reinforced, T5→Titanium). All unlocked tiers are processed simultaneously; higher tiers convert at a slower rate.",
    "market": "Generates Passive Gold.",
    "barracks": "Passive: +1% Atk/Def per 100 Workers.",
    "temple": "Passive: +5% Propagate follower gain per 100 Workers.",
    "apothecary": "Passive: Increases Potion Healing (+20 flat HP per 100 Workers per potion use).",
    "black_market": "Special: Trade various resources for mysterious caches.",
    "companion_ranch": "Generator: Produces XP Cookies for pets.",
    "hatchery": "Incubate monster eggs. Workers reduce incubation time (10% per 100 Workers).",
    "celestial_shrine": "Passive: Increases chance to find Celestial Sigils from Aphrodite.",
    "infernal_shrine": "Passive: Increases chance to find Infernal Sigils from Lucifer.",
    "void_shrine":     "Passive: Increases chance to find Void Sigils from NEET.",
    "twin_shrine": "Passive: Increases chance to find Gemini Sigils from the Gemini Twins.",
    "corruption_shrine": "Passive: Increases chance to find bonus Corruption Sigils from Corrupted monsters.",
    "war_camp": "Generates Combat Stamina over time. Collection is capped at **10 stamina** and never exceeds the normal maximum. (~10 per 24h at 100 workers; ~5h at 500 workers.)",
}

# Construction costs (used by BuildConstructionView)
CONSTRUCTION_COSTS = {
    "logging_camp": {"gold": 100, "stone": 0},
    "quarry": {"gold": 100, "timber": 0},
    "foundry": {"gold": 5000, "timber": 200, "stone": 600},
    "sawmill": {"gold": 5000, "timber": 600, "stone": 200},
    "reliquary": {"gold": 5000, "timber": 400, "stone": 400},
    "market": {"gold": 10000, "timber": 500, "stone": 500},
    "barracks": {"gold": 15000, "timber": 1000, "stone": 1000},
    "temple": {"gold": 20000, "timber": 1500, "stone": 1500},
    "apothecary": {"gold": 25000, "timber": 2000, "stone": 2000},
    "black_market": {"gold": 50000, "timber": 50000, "stone": 50000},
    "companion_ranch": {"gold": 30000, "timber": 30000, "stone": 30000},
    "hatchery":        {"gold": 30000, "timber": 30000, "stone": 30000},
    "war_camp":        {"gold": 20000, "timber": 1500, "stone": 1500},
    "celestial_shrine": {"gold": 10000000, "timber": 100000, "stone": 100000},
    "infernal_shrine": {"gold": 10000000, "timber": 100000, "stone": 100000},
    "void_shrine": {"gold": 10000000, "timber": 100000, "stone": 100000},
    "twin_shrine": {"gold": 10000000, "timber": 100000, "stone": 100000},
    "corruption_shrine": {"gold": 10000000, "timber": 100000, "stone": 100000},
}

# Special material mapping for upgrades
SPECIAL_MAP = {
    "foundry": "magma_core",
    "quarry": "magma_core",
    "sawmill": "life_root",
    "barracks": "magma_core",
    "logging_camp": "life_root",
    "reliquary": "spirit_shard",
    "temple": "spirit_shard",
    "market": "spirit_shard",
    "town_hall": "spirit_shard",
    "apothecary": "life_root",
    "companion_ranch": "life_root",
    "hatchery":        "life_root",
    "war_camp":        "magma_core",
    "celestial_shrine": "celestial_stone",
    "infernal_shrine": "infernal_cinder",
    "void_shrine": "void_crystal",
    "twin_shrine": "bound_crystal",
    "corruption_shrine": "corrupted_crystal",
}

ITEM_NAMES = {
    "magma_core": "Magma Core",
    "life_root": "Life Root",
    "spirit_shard": "Spirit Shard",
    "celestial_stone": "Celestial Stone",
    "infernal_cinder": "Infernal Cinder",
    "void_crystal": "Void Crystal",
    "bound_crystal": "Bound Crystal",
    "corrupted_crystal": "Corrupted Crystal",
}

# Legacy individual shrine types (kept for DB backward-compat; new builds use uber_shrine)
UBER_BUILDINGS = {"celestial_shrine", "infernal_shrine", "void_shrine", "twin_shrine", "corruption_shrine", "uber_shrine"}

# Black Market bulk trade configuration
BLACK_MARKET_TRADES = {
    "equip": {
        "label": "Equipment Caches (2.5M Gold each)",
        "key": "equip",
    },
    "rune": {
        "label": "Rune Caches (1 each: Refine/Potential/Shatter)",
        "key": "rune",
    },
    "key": {"label": "Boss Key Caches (1 Void Key each)", "key": "key"},
}

# Construction flavor text (used during building animation)
BUILD_MESSAGES = [
    ("Your workers start building...", 6),
    ("Laying the foundations...", 5),
    ("Hammering beams into place...", 4),
    ("Raising the walls...", 4),
    ("Roofing the structure...", 3),
    ("Clearing up dead workers...", 1),  # darker / rarer
    ("Incinerating bodies...", 1),
    ("Burying the fallen...", 1),
    ("Whispering dark incantations...", 1),
]

UPGRADE_MESSAGES = [
    ("Reinforcing the foundations...", 6),
    ("Expanding the structure...", 5),
    ("Upgrading the core systems...", 5),
    ("Fortifying the walls...", 4),
    ("Installing new machinery...", 4),
    ("Sacrificing resources to the old gods...", 1),
    ("Binding worker souls to the framework...", 1),
    ("Incinerating outdated materials...", 1),
    ("Clearing out the weak...", 1),
]

# ---------------------------------------------------------------------------
# New Buildings — Nursery + Idlem Foundry + Uber Shrine
# ---------------------------------------------------------------------------

BUILDING_INFO.update({
    "nursery": "Produces Workers over Development Turns. Each turn generates ~1–2 new workers for your workforce.",
    "idlem_foundry": "Produces Idlem over Development Turns (~1–2 per turn). Idlem powers the Black Market passive tree.",
    "uber_shrine": "Houses five shrines (Celestial, Infernal, Void, Twin, Corruption). Assign workers per shrine to boost sigil drop chances from each respective Uber boss.",
})

CONSTRUCTION_COSTS.update({
    "nursery": {"gold": 25000, "timber": 2000, "stone": 2000},
    "idlem_foundry": {"gold": 50000, "timber": 5000, "stone": 5000},
    "uber_shrine": {"gold": 10_000_000, "timber": 100_000, "stone": 100_000},
})

SPECIAL_MAP.update({
    "nursery": "life_root",
    "idlem_foundry": "spirit_shard",
    "uber_shrine": "celestial_stone",  # uses all 5 types for T3+; handled in upgrade logic
})

# ---------------------------------------------------------------------------
# Development Turns / Zeal economy
# ---------------------------------------------------------------------------

# Zeal earned per combat win (first ZEAL_DAILY_HARD_CAP zeal, then diminishing returns).
ZEAL_PER_COMBAT = 10
# Conversions
ZEAL_TO_DT = 10            # 10 Zeal = 1 Development Turn
# Daily hard cap on total zeal earned (800 = ~80 DTs per day from active play).
ZEAL_DAILY_HARD_CAP = 800
# Soft cap: after this much zeal earned today, gains are halved.
ZEAL_DAILY_SOFT_CAP = 600
# Passive zeal generated per hour per settlement (baseline; scales with TH tier).
PASSIVE_ZEAL_PER_HOUR_BASE = 10   # 10/hr = 1 DT/hr at base
# Idlem produced per turn by the Idlem Foundry (before tier scaling).
IDLEM_PER_TURN_BASE = 1
# Workers produced per turn by the Nursery (before tier scaling).
WORKERS_PER_TURN_BASE = 1.2  # fractional — rounded to int each turn

# Project DT costs per building for construction.
PROJECT_CONSTRUCTION_DT = {
    "logging_camp": 4,
    "quarry": 4,
    "foundry": 10,
    "sawmill": 10,
    "reliquary": 10,
    "market": 14,
    "barracks": 18,
    "temple": 18,
    "apothecary": 20,
    "black_market": 24,
    "companion_ranch": 20,
    "hatchery": 20,
    "war_camp": 16,
    "nursery": 16,
    "idlem_foundry": 22,
    "uber_shrine": 40,
}

# Extra DT cost per tier level for upgrades (applied on top of resource cost).
PROJECT_UPGRADE_DT_PER_TIER = {
    "default": 8,        # T1→T2 = 8 DTs, T2→T3 = 16, etc.
    "uber_shrine": 20,
    "black_market": 15,
    "town_hall": 20,
}

# ---------------------------------------------------------------------------
# Black Market — value table
# ---------------------------------------------------------------------------

# Each item maps to its value score used in calculate_offer_value().
BM_ITEM_VALUES: dict[str, int] = {
    # Settlement basics
    "timber": 1,
    "stone": 1,
    # Raw ores / materials
    "iron": 2,
    "coal": 2,
    "gold": 3,
    "platinum": 4,
    "idea": 5,
    # Logs
    "oak_logs": 2,
    "willow_logs": 2,
    "mahogany_logs": 3,
    "magic_logs": 4,
    "idea_logs": 5,
    # Refined bars
    "iron_bar": 4,
    "steel_bar": 5,
    "gold_bar": 6,
    "platinum_bar": 7,
    "idea_bar": 8,
    # Planks
    "oak_plank": 4,
    "willow_plank": 5,
    "mahogany_plank": 6,
    "magic_plank": 7,
    "idea_plank": 8,
    # Bones
    "desiccated_bones": 2,
    "regular_bones": 3,
    "sturdy_bones": 4,
    "reinforced_bones": 5,
    "titanium_bones": 6,
    # Essences
    "desiccated_essence": 5,
    "regular_essence": 6,
    "sturdy_essence": 7,
    "reinforced_essence": 8,
    "titanium_essence": 9,
    # Runes
    "refinement_runes": 150,
    "potential_runes": 150,
    "shatter_runes": 150,
    "imbue_runes": 250,
    "partnership_runes": 200,
    # Boss keys
    "dragon_key": 400,
    "angel_key": 400,
    "soul_cores": 450,
    "balance_fragment": 420,
    "void_frags": 380,
    "void_keys": 350,
    # Elemental keys
    "blessed_bismuth": 800,
    "sparkling_sprig": 800,
    "capricious_carp": 800,
    # Settlement materials
    "magma_core": 1200,
    "life_root": 1200,
    "spirit_shard": 1200,
    "celestial_stone": 2500,
    "infernal_cinder": 2500,
    "void_crystal": 2500,
    "bound_crystal": 2500,
    "corrupted_crystal": 2500,
    # Blueprints etc.
    "unidentified_blueprint": 800,
    "diviners_rod": 600,
    "spirit_stones": 50,
    # Endgame
    "antique_tome": 1800,
    "pinnacle_key": 2200,
    # Uber sigils
    "celestial_sigils": 3000,
    "infernal_sigils": 3000,
    "void_shards": 3000,
    "gemini_sigils": 3000,
    "corruption_sigils": 3000,
    # Curios
    "curios": 200,
}

# Processing turn formula: turns = BM_TURNS_BASE + (value / BM_TURNS_PER_VALUE)
BM_TURNS_BASE = 5
BM_TURNS_PER_VALUE = 10_000   # every 10k value ≈ +1 turn

# ---------------------------------------------------------------------------
# Black Market — base loot table
# ---------------------------------------------------------------------------
# Each entry: (category_key, weight)
# When a base roll fires, pick a category; then roll quantity from sub-table.
BM_BASE_LOOT_WEIGHTS: list[tuple[str, int]] = [
    ("gold",       25),
    ("rune",       12),
    ("boss_key",   15),
    ("gathering",  10),
    ("essence",     8),
    ("gear",        8),
    ("settler_mat", 5),
    ("egg",         4),
    ("guild_ticket",4),
    ("consume",     3),
    ("curio",       3),
    ("high_end",    3),
]

# Rolls = floor(value / BM_ROLLS_PER_VALUE) (min 1)
BM_ROLLS_PER_VALUE = 2_000

# Gold range per gold roll (multiplied by value bonus)
BM_GOLD_MIN = 10_000
BM_GOLD_MAX = 80_000

# ---------------------------------------------------------------------------
# Black Market passive tree node definitions
# ---------------------------------------------------------------------------
# key → {name, description, branch, max_level, idlem_costs: list[int per level]}
BM_TREE_NODES: dict[str, dict] = {
    # Branch 1: Efficiency
    "efficiency_1": {
        "name": "Processing I",
        "description": "−10% deal processing turns.",
        "branch": "efficiency",
        "max_level": 1,
        "idlem_costs": [50],
    },
    "efficiency_2": {
        "name": "Processing II",
        "description": "−20% deal processing turns.",
        "branch": "efficiency",
        "max_level": 1,
        "idlem_costs": [120],
    },
    "efficiency_3": {
        "name": "Swift Commerce",
        "description": "−35% deal processing turns.",
        "branch": "efficiency",
        "max_level": 1,
        "idlem_costs": [250],
    },
    "efficiency_4": {
        "name": "Instant Deals",
        "description": "Small deals (≤ 5 turns) complete instantly.",
        "branch": "efficiency",
        "max_level": 1,
        "idlem_costs": [450],
    },
    # Branch 2: Value
    "value_1": {
        "name": "Shrewd Bargaining I",
        "description": "+5% to all offer values.",
        "branch": "value",
        "max_level": 1,
        "idlem_costs": [200],
    },
    "value_2": {
        "name": "Shrewd Bargaining II",
        "description": "+10% to all offer values.",
        "branch": "value",
        "max_level": 1,
        "idlem_costs": [500],
    },
    "value_3": {
        "name": "Master Appraiser",
        "description": "+15% to all offer values.",
        "branch": "value",
        "max_level": 1,
        "idlem_costs": [1000],
    },
    # Branch 3: Biases (toggleable during offering)
    "rune_bias": {
        "name": "Rune Focus",
        "description": "+1/+2/+3 extra Rune rolls per deal (by level).",
        "branch": "bias",
        "max_level": 3,
        "idlem_costs": [150, 400, 900],
        "extra_rolls": [1, 2, 3],
        "category": "rune",
    },
    "gathering_bias": {
        "name": "Gathering Focus",
        "description": "+1/+2/+3 extra Gathering rolls per deal (by level).",
        "branch": "bias",
        "max_level": 3,
        "idlem_costs": [150, 400, 900],
        "extra_rolls": [1, 2, 3],
        "category": "gathering",
    },
    "key_bias": {
        "name": "Key Focus",
        "description": "+1/+2/+3 extra Boss Key rolls per deal (by level).",
        "branch": "bias",
        "max_level": 3,
        "idlem_costs": [150, 400, 900],
        "extra_rolls": [1, 2, 3],
        "category": "boss_key",
    },
    "egg_bias": {
        "name": "Egg & Consume Focus",
        "description": "+1/+2 extra Egg/Consume rolls per deal (by level).",
        "branch": "bias",
        "max_level": 2,
        "idlem_costs": [200, 600],
        "extra_rolls": [1, 2],
        "category": "egg",
    },
    "gear_bias": {
        "name": "Gear Focus",
        "description": "+1/+2 extra Gear rolls per deal (by level).",
        "branch": "bias",
        "max_level": 2,
        "idlem_costs": [200, 600],
        "extra_rolls": [1, 2],
        "category": "gear",
    },
    "high_end_bias": {
        "name": "High-End Focus",
        "description": "+1/+2 extra High-End rolls (Tomes, Pinnacle Keys) per deal.",
        "branch": "bias",
        "max_level": 2,
        "idlem_costs": [300, 800],
        "extra_rolls": [1, 2],
        "category": "high_end",
    },
    "gold_bias": {
        "name": "Liquid Assets",
        "description": "+2/+4 extra Gold rolls per deal (by level).",
        "branch": "bias",
        "max_level": 2,
        "idlem_costs": [100, 300],
        "extra_rolls": [2, 4],
        "category": "gold",
    },
}

# ---------------------------------------------------------------------------
# Settlement Events
# ---------------------------------------------------------------------------
# Each event: event_key → {name, type, description, trigger_turn (or 'recurring'),
#   recurring_interval, duration_turns, effects, flavor_text}
SETTLEMENT_EVENTS: dict[str, dict] = {
    # --- Opportunity events ---
    "merchant_caravan": {
        "name": "🐪 Merchant Caravan",
        "type": "ongoing",
        "description": "A travelling caravan arrives offering excellent rates.",
        "flavor": "Madame Vespera leans forward. 'Exceptional timing. My traders have overstocked.'",
        "duration_turns": 5,
        "effects": {"bm_value_bonus": 0.25},  # +25% BM offer value
        "trigger_at": [15, 40, 80, 130, 190],  # cumulative turns
        "recurring_interval": 50,
    },
    "inspiration_surge": {
        "name": "💡 Inspiration Surge",
        "type": "ongoing",
        "description": "Your architects are inspired — construction DT costs halved.",
        "flavor": "The Maid brings blueprints you barely remember drafting. 'You designed these in your sleep, it seems.'",
        "duration_turns": 3,
        "effects": {"construction_dt_halved": True},
        "trigger_at": [20, 60, 110, 170],
        "recurring_interval": 50,
    },
    "resource_windfall": {
        "name": "🌾 Resource Windfall",
        "type": "ongoing",
        "description": "Your generators produce 50% more for the next few turns.",
        "flavor": "'Something in the soil, perhaps,' the Maid muses. 'Or the stars. Either way, harvest while it lasts.'",
        "duration_turns": 4,
        "effects": {"generator_bonus": 0.50},
        "trigger_at": [10, 35, 70, 120, 180],
        "recurring_interval": 45,
    },
    "zeal_rally": {
        "name": "🔥 Ideological Rally",
        "type": "instant",
        "description": "Your followers erupt in fervor — gain 100 Zeal.",
        "flavor": "Chants echo through the settlement. The Maid watches with approval.",
        "duration_turns": 0,
        "effects": {"grant_zeal": 100},
        "trigger_at": [5, 25, 55, 95, 145, 205],
        "recurring_interval": 60,
    },
    "worker_boom": {
        "name": "👶 Baby Boom",
        "type": "ongoing",
        "description": "Population grows rapidly — Nursery output doubled for 5 turns.",
        "flavor": "'An unusual number of cradles being built,' the Maid notes. 'Plan accordingly.'",
        "duration_turns": 5,
        "effects": {"nursery_mult": 2.0},
        "trigger_at": [30, 90, 160],
        "recurring_interval": 80,
    },
    # --- Crisis events ---
    "bandit_raid": {
        "name": "⚔️ Bandit Raid",
        "type": "upcoming",
        "description": "Raiders are spotted on the horizon — defend your settlement!",
        "flavor": "'I suggest preparing your weapons,' the Maid says calmly, polishing silverware.",
        "duration_turns": 0,
        "effects": {"spawn_combat": "bandit_captain", "on_fail_disable": "market"},
        "trigger_at": [25, 75, 140, 220],
        "recurring_interval": 80,
        "advance_warning_turns": 3,
    },
    "plague_outbreak": {
        "name": "🦠 Plague Outbreak",
        "type": "upcoming",
        "description": "Sickness spreads among workers — your Apothecary can contain it.",
        "flavor": "'The healer's work is never done,' the Maid sighs, laying out potions.",
        "duration_turns": 0,
        "effects": {"spawn_combat": "plague_wraith", "on_fail": "lose_workers_20pct"},
        "trigger_at": [50, 120, 200],
        "recurring_interval": 90,
        "advance_warning_turns": 4,
    },
    "void_incursion": {
        "name": "🌑 Void Incursion",
        "type": "upcoming",
        "description": "A void rift has opened near your settlement. Only void-touched warriors can close it.",
        "flavor": "'The void does not knock,' the Maid says, drawing the curtains.",
        "duration_turns": 0,
        "effects": {"spawn_combat": "void_sentry", "on_fail_disable": "void_shrine"},
        "trigger_at": [100, 200],
        "recurring_interval": 120,
        "advance_warning_turns": 5,
    },
    # --- Flavor / narrative ---
    "wandering_scholar": {
        "name": "📚 Wandering Scholar",
        "type": "instant",
        "description": "A scholar visits and shares wisdom — gain 3 Research Blueprints.",
        "flavor": "'Knowledge freely given is doubly returned,' the Maid quotes, showing the visitor to the library.",
        "duration_turns": 0,
        "effects": {"grant_blueprints": 3},
        "trigger_at": [18, 65, 130],
        "recurring_interval": 70,
    },
    "idlem_surge": {
        "name": "⚗️ Foundry Surge",
        "type": "ongoing",
        "description": "The Idlem Foundry runs at double capacity for 4 turns.",
        "flavor": "'The ley lines are aligned,' the Maid explains. 'I wouldn't question it.'",
        "duration_turns": 4,
        "effects": {"idlem_mult": 2.0},
        "trigger_at": [45, 100, 175],
        "recurring_interval": 70,
    },
}

# Mapping building types that raids can disable (for event resolution)
RAID_DISABLE_BUILDINGS = {"market", "void_shrine", "logging_camp", "apothecary"}

# Resources that can be offered to the Black Market (displayed in offering UI)
BM_OFFERABLE_RESOURCES: list[tuple[str, str]] = [
    # (resource_key, display_label)
    ("timber",          "🪵 Timber"),
    ("stone",           "🪨 Stone"),
    ("iron",            "⛏️ Iron Ore"),
    ("coal",            "🪨 Coal"),
    ("gold",            "🏅 Gold Ore"),
    ("platinum",        "💿 Platinum Ore"),
    ("idea",            "💡 Idea Ore"),
    ("iron_bar",        "🔧 Iron Bars"),
    ("steel_bar",       "🔧 Steel Bars"),
    ("gold_bar",        "🔧 Gold Bars"),
    ("platinum_bar",    "🔧 Platinum Bars"),
    ("idea_bar",        "🔧 Idea Bars"),
    ("oak_logs",        "🌲 Oak Logs"),
    ("willow_logs",     "🌲 Willow Logs"),
    ("mahogany_logs",   "🌲 Mahogany Logs"),
    ("magic_logs",      "🌲 Magic Logs"),
    ("idea_logs",       "🌲 Idea Logs"),
    ("oak_plank",       "🪵 Oak Planks"),
    ("willow_plank",    "🪵 Willow Planks"),
    ("mahogany_plank",  "🪵 Mahogany Planks"),
    ("magic_plank",     "🪵 Magic Planks"),
    ("idea_plank",      "🪵 Idea Planks"),
    ("desiccated_bones","🦴 Desiccated Bones"),
    ("regular_bones",   "🦴 Regular Bones"),
    ("sturdy_bones",    "🦴 Sturdy Bones"),
    ("reinforced_bones","🦴 Reinforced Bones"),
    ("titanium_bones",  "🦴 Titanium Bones"),
    ("refinement_runes","🔮 Refinement Runes"),
    ("potential_runes", "🔮 Potential Runes"),
    ("shatter_runes",   "🔮 Shatter Runes"),
    ("imbue_runes",     "🔮 Imbuing Runes"),
    ("dragon_key",      "🗝️ Draconic Keys"),
    ("angel_key",       "🗝️ Angelic Keys"),
    ("soul_cores",      "💠 Soul Cores"),
    ("balance_fragment","⚖️ Fragments of Balance"),
    ("void_frags",      "🌑 Void Fragments"),
    ("magma_core",      "🔥 Magma Cores"),
    ("life_root",       "🌿 Life Roots"),
    ("spirit_shard",    "🌟 Spirit Shards"),
    ("curios",          "📦 Curios"),
    ("unidentified_blueprint", "📋 Blueprints"),
    ("spirit_stones",   "🔮 Spirit Stones"),
]
