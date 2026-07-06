# core/settlement/constants.py
"""All static configuration for the settlement system."""

RESOURCE_DISPLAY_NAMES = {
    "timber": "Timber",
    "stone": "Stone",
    "gold": "Gold",
    "iron_ore": "Iron Ore",
    "coal_ore": "Coal",
    "platinum_ore": "Platinum Ore",
    "idea_ore": "Idea Ore",
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
    "logging_camp": "Hybrid: Produces **20 Timber/hr per 100 Workers** at T1 passively, scaling with tier (×2 at T2, ×3 at T3, up to ×5 at T5). Also awards a **5× burst** each Development Turn. Raw timber for construction and the Sawmill.",
    "quarry": "Hybrid: Produces **20 Stone/hr per 100 Workers** at T1 passively, scaling with tier (×2 at T2, up to ×5 at T5). Also awards a **5× burst** each Development Turn. Raw stone for construction and the Foundry.",
    "foundry": "Hybrid: Processes ore into ingots — **100 conversions/hr per 100 Workers** at T1 passively, plus a **5× burst** each Development Turn. Tiers unlock ore grades: T1→Iron, T2→Coal, T3→Gold, T4→Platinum, T5→Idea. All unlocked tiers run simultaneously.",
    "sawmill": "Hybrid: Processes logs into planks — **100 conversions/hr per 100 Workers** at T1 passively, plus a **5× burst** each Development Turn. Tiers unlock log grades: T1→Oak, T2→Willow, T3→Mahogany, T4→Magic, T5→Idea. All unlocked tiers run simultaneously.",
    "reliquary": "Hybrid: Processes bones into essences — **100 conversions/hr per 100 Workers** at T1 passively, plus a **5× burst** each Development Turn. Tiers unlock bone grades: T1→Desiccated, T2→Regular, T3→Sturdy, T4→Reinforced, T5→Titanium. All unlocked tiers run simultaneously.",
    "market": "Hybrid: Produces **5,000 Gold/hr per 100 Workers** at T1 passively, scaling with tier (up to 25,000/hr at T5). Also awards a **5× burst** each Development Turn.",
    "barracks": "Passive: Grants **+1% Attack and Defence per 100 Workers** (applied globally during combat). Scales with tier — higher tiers raise the worker cap, increasing the maximum bonus.",
    "temple": "Passive: Grants **+5% Propagate follower gain per 100 Workers**. Scales with tier. Followers are required to staff all buildings, so this multiplies your workforce growth.",
    "apothecary": "Passive: Each potion use heals an additional **+20 flat HP per 100 Workers**. Scales with tier. Stacks with all other healing bonuses.",
    "black_market": "Special: Submit resource bundles as trade offers. Deals process over Development Turns and return curated loot. Invest Idlem into the passive tree to improve deal value, speed, and loot bias.",
    "companion_ranch": "Hybrid: Produces **10 Companion XP/hr per 100 Workers** at T1 passively, scaling with tier. Also awards a **5× burst** each Development Turn. XP accumulates as Cookies and is claimed manually from **/companions**.",
    "hatchery": "Special: Incubate monster eggs for Hematurgy blood drops. Workers reduce incubation time — **10% faster per 100 Workers**. Requires Level 50 to build.",
    "war_camp": "Passive generator: Produces Combat Stamina — **~10 Stamina per 24h per 100 Workers**. Collected via its own **War Camp Stamina** button (separate from the main Collect button). This stamina stacks on top of your current total, even past the normal 10-stamina cap.",
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
    "hatchery": {"gold": 30000, "timber": 30000, "stone": 30000},
    "war_camp": {"gold": 20000, "timber": 1500, "stone": 1500},
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
    "apothecary": "spirit_shard",
    "companion_ranch": "life_root",
    "hatchery": "life_root",
    "war_camp": "magma_core",
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
UBER_BUILDINGS = {
    "celestial_shrine",
    "infernal_shrine",
    "void_shrine",
    "twin_shrine",
    "corruption_shrine",
    "uber_shrine",
}

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

# ---------------------------------------------------------------------------
# New Buildings — Nursery + Idlem Foundry + Uber Shrine
# ---------------------------------------------------------------------------

BUILDING_INFO.update(
    {
        "nursery": "Project Building: Produces **~1–2 Workers per 100 workers/Turn**. Completed workers are added to your ideology's follower count.",
        "idlem_foundry": "Project Building: Produces **~1–2 Idlem per 100 workers/ Turn**. Idlem is the currency for the Black Market passive tree — invest it to unlock better deal speeds, value, and loot biases.",
        "uber_shrine": "Passive: Houses shrine statues dedicated to the gods. Statue blueprints drop from uber bosses. Allocate workers to each statue individually — each statue provides a sigil drop boost. Higher tiers raise the total worker cap across all statues.",
        "sanctum": "Passive: Each combat victory has a **1% chance per 10 workers assigned** to convert the fallen enemy into an ideology follower. Chance never exceeds 95%. Sacred Ground plots boost conversion rate by 20%.",
    }
)

CONSTRUCTION_COSTS.update(
    {
        "nursery": {"gold": 25000, "timber": 2000, "stone": 2000},
        "idlem_foundry": {"gold": 50000, "timber": 5000, "stone": 5000},
        "sanctum": {"gold": 25000, "timber": 2000, "stone": 2000},
        "uber_shrine": {"gold": 10_000_000, "timber": 100_000, "stone": 100_000},
    }
)

SPECIAL_MAP.update(
    {
        "nursery": "life_root",
        "idlem_foundry": "magma_core",
        "sanctum": "spirit_shard",
        "uber_shrine": "celestial_stone",  # uses all 5 types for T3+; handled in upgrade logic
    }
)

# ---------------------------------------------------------------------------
# Uber Shrine — statue definitions
# ---------------------------------------------------------------------------
# Each uber statue can be unlocked (via a 15-DT project), then staffed with workers.
# Workers provide a sigil drop bonus per assigned worker.

UBER_STATUE_DEFS: dict[str, dict] = {
    "celestial": {
        "name": "Celestial Statue",
        "emoji": "⭐",
        "slot": 1,
        "blueprint_key": "celestial_blueprint_unlocked",
        "boss_name": "Aphrodite",
        "material": "celestial_stone",
        "material_name": "Celestial Stone",
        "material_qty": 1,
        "build_dt": 40,
        "sigil_key": "celestial_shrine",
    },
    "infernal": {
        "name": "Infernal Statue",
        "emoji": "🔥",
        "slot": 2,
        "blueprint_key": "infernal_blueprint_unlocked",
        "boss_name": "Lucifer",
        "material": "infernal_cinder",
        "material_name": "Infernal Cinder",
        "material_qty": 1,
        "build_dt": 40,
        "sigil_key": "infernal_shrine",
    },
    "void": {
        "name": "Void Statue",
        "emoji": "🌀",
        "slot": 3,
        "blueprint_key": "void_blueprint_unlocked",
        "boss_name": "NEET",
        "material": "void_crystal",
        "material_name": "Void Crystal",
        "material_qty": 1,
        "build_dt": 40,
        "sigil_key": "void_shrine",
    },
    "bound": {
        "name": "Twin Statue",
        "emoji": "🔗",
        "slot": 4,
        "blueprint_key": "gemini_blueprint_unlocked",
        "boss_name": "Gemini",
        "material": "bound_crystal",
        "material_name": "Bound Crystal",
        "material_qty": 1,
        "build_dt": 40,
        "sigil_key": "twin_shrine",
    },
    "corrupted": {
        "name": "Corrupted Statue",
        "emoji": "☠️",
        "slot": 5,
        "blueprint_key": "corruption_blueprint_unlocked",
        "boss_name": "Evelynn",
        "material": "corrupted_crystal",
        "material_name": "Corrupted Crystal",
        "material_qty": 1,
        "build_dt": 40,
        "sigil_key": "corruption_shrine",
    },
}

# Statue tier upgrade DT costs (T1→T2, T2→T3, T3→T4, T4→T5)
STATUE_UPGRADE_DT: dict[int, int] = {2: 40, 3: 80, 4: 120, 5: 200}

# Statue tier upgrade gold costs
STATUE_UPGRADE_GOLD: dict[int, int] = {
    2: 100_000,
    3: 500_000,
    4: 2_000_000,
    5: 5_000_000,
}

# Statue tier upgrade material quantities (of the statue's own material): T2=1, T3=2, T4=3, T5=4
STATUE_UPGRADE_MATERIAL_QTY: dict[int, int] = {2: 1, 3: 2, 4: 3, 5: 4}

# ---------------------------------------------------------------------------
# Development Turns / Zeal economy
# ---------------------------------------------------------------------------

# Zeal earned per combat win (first ZEAL_DAILY_HARD_CAP zeal, then diminishing returns).
ZEAL_PER_COMBAT = 10
# Conversions
ZEAL_TO_DT = 10  # 10 Zeal = 1 Development Turn
# Daily hard cap on total zeal earned (800 = ~80 DTs per day from active play).
ZEAL_DAILY_HARD_CAP = 800
# Soft cap: after this much zeal earned today, gains are halved.
ZEAL_DAILY_SOFT_CAP = 600
# Passive zeal generated per hour per settlement (T1 = 5/hr, T7 ≈ 59/hr).
PASSIVE_ZEAL_PER_HOUR_BASE = 5
# Maximum Zeal collectible in a single Gather Zeal action.
ZEAL_GATHER_CAP = 400
# Idlem produced per 100 workers assigned, per turn, by the Idlem Foundry (before tier scaling).
IDLEM_PER_TURN_BASE = 1
# Workers produced per 100 workers assigned, per turn, by the Nursery (before tier scaling).
WORKERS_PER_TURN_BASE = 1.2  # fractional — rounded to int each turn, +0/1 variance

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
    "sanctum": 18,
    "uber_shrine": 40,
}

# Legacy reference — upgrade DT costs are now a lookup table in turn_engine.py:
# T1→T2 = 5 DTs, T2→T3 = 10, T3→T4 = 25, T4→T5 = 50
PROJECT_UPGRADE_DT_PER_TIER = {
    "default": 5,
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
    "iron_ore": 10,
    "coal_ore": 20,
    "gold_ore": 30,
    "platinum_ore": 40,
    "idea_ore": 50,
    # Logs
    "oak_logs": 10,
    "willow_logs": 20,
    "mahogany_logs": 30,
    "magic_logs": 40,
    "idea_logs": 50,
    # Refined bars
    "iron_bar": 20,
    "steel_bar": 30,
    "gold_bar": 40,
    "platinum_bar": 50,
    "idea_bar": 60,
    # Planks
    "oak_plank": 20,
    "willow_plank": 30,
    "mahogany_plank": 40,
    "magic_plank": 50,
    "idea_plank": 60,
    # Bones
    "desiccated_bones": 10,
    "regular_bones": 20,
    "sturdy_bones": 30,
    "reinforced_bones": 40,
    "titanium_bones": 50,
    # Essences
    "desiccated_essence": 20,
    "regular_essence": 30,
    "sturdy_essence": 40,
    "reinforced_essence": 50,
    "titanium_essence": 60,
    # Runes — Valuables ×100
    "refinement_runes": 100_000,
    "potential_runes": 60_000,
    "shatter_runes": 85_000,
    "imbue_runes": 175_000,
    "partnership_runes": 50_000,
    # Boss keys — Valuables ×100
    "dragon_key": 40_000,
    "angel_key": 40_000,
    "soul_cores": 30_000,
    "balance_fragment": 40_000,
    "void_frags": 35_000,
    "void_keys": 150_000,
    # Elemental keys — Valuables ×100
    "blessed_bismuth": 50_000,
    "sparkling_sprig": 50_000,
    "capricious_carp": 50_000,
    # Settlement materials — Valuables ×100
    "magma_core": 50_000,
    "life_root": 50_000,
    "spirit_shard": 50_000,
    "celestial_stone": 1_250_000,
    "infernal_cinder": 1_250_000,
    "void_crystal": 1_250_000,
    "bound_crystal": 1_250_000,
    "corrupted_crystal": 10_000_000,
    # Blueprints etc. — Valuables ×100
    "unidentified_blueprint": 100_000,
    "diviners_rod": 100_000,
    "spirit_stones": 100_000,
    # Endgame — Valuables ×100
    "antique_tome": 150_000,
    "pinnacle_key": 200_000,
    # Uber sigils — Valuables ×100
    "celestial_sigils": 300_000,
    "infernal_sigils": 300_000,
    "void_shards": 300_000,
    "gemini_sigils": 300_000,
    "corruption_sigils": 300_000,
    # Curios — Valuables ×100
    "curios": 200_000,
}

# Processing turn formula: turns = BM_TURNS_BASE + (value / BM_TURNS_PER_VALUE)
BM_TURNS_BASE = 5
BM_TURNS_PER_VALUE = 10_000  # every 10k value ≈ +1 turn

# ---------------------------------------------------------------------------
# Black Market — base loot table
# ---------------------------------------------------------------------------
# Each entry: (category_key, weight)
# When a base roll fires, pick a category; then roll quantity from sub-table.
BM_BASE_LOOT_WEIGHTS: list[tuple[str, int]] = [
    ("gold", 25),
    ("rune", 12),
    ("boss_key", 15),
    ("gathering", 10),
    ("essence", 8),
    ("gear", 8),
    ("settler_mat", 5),
    ("guild_ticket", 5),
    ("curio", 4),
    ("high_end", 3),
]

# Rolls = floor(value / BM_ROLLS_PER_VALUE) (min 1)
BM_ROLLS_PER_VALUE = 2_000

# Gold range per gold roll (multiplied by value bonus)
BM_GOLD_MIN = 15_000
BM_GOLD_MAX = 150_000

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
# Each event: event_key → {name, type, description, trigger_at, recurring_interval,
#   effects, modifier_bands?, duration_bands?, requires_buildings?,
#   targets_any_building?, targets_building_types?, advance_warning_turns?}
#
# Effects whose value is "band" are resolved at scheduling time by picking a
# random entry from modifier_bands and storing the result in the event's data
# JSON column.  "neg_band" means the band value is negated (penalty).
# Duration is picked from duration_bands at scheduling time and stored as
# data["duration"].
# Crisis events store data["target_building"] and data["target_building_label"]
# when targets_any_building or targets_building_types is set.
SETTLEMENT_EVENTS: dict[str, dict] = {
    # ── POSITIVE EVENTS ──────────────────────────────────────────────────────
    "merchant_caravan": {
        "name": "🐪 Merchant Caravan",
        "type": "ongoing",
        "description": "A merchant caravan is in town — Black Market offer values are {band_pct}% higher. Submit resource bundles now to get extra returns.",
        "duration_bands": [4, 5, 6],
        "effects": {"bm_value_bonus": "band"},
        "modifier_bands": [0.15, 0.20, 0.25, 0.30, 0.35],
        "requires_buildings": ["black_market"],
        "trigger_at": [15, 40, 80, 130, 190],
        "recurring_interval": 50,
    },
    "inspiration_surge": {
        "name": "💡 Inspiration Surge",
        "type": "ongoing",
        "description": "Construction DT costs are halved. Queue up new builds or upgrades before this expires.",
        "duration_bands": [2, 3, 4],
        "effects": {"construction_dt_halved": True},
        "trigger_at": [20, 60, 110, 170],
        "recurring_interval": 50,
    },
    "resource_windfall": {
        "name": "🌾 Resource Windfall",
        "type": "ongoing",
        "description": "Favorable conditions boost all generator output by {band_pct}%. Your workers benefit automatically — no action needed.",
        "duration_bands": [3, 4, 5],
        "effects": {"generator_bonus": "band"},
        "modifier_bands": [0.20, 0.30, 0.40, 0.50, 0.60],
        "requires_buildings": [
            "logging_camp",
            "quarry",
            "market",
            "companion_ranch",
            "war_camp",
        ],
        "trigger_at": [10, 35, 70, 120, 180],
        "recurring_interval": 45,
    },
    "zeal_rally": {
        "name": "🔥 Ideological Rally",
        "type": "instant",
        "description": "Your followers erupt in fervor — {band} Zeal granted immediately.",
        "effects": {"grant_zeal": "band"},
        "modifier_bands": [50, 75, 100, 125],
        "trigger_at": [5, 25, 55, 95, 145, 205],
        "recurring_interval": 60,
    },
    "worker_boom": {
        "name": "👶 Baby Boom",
        "type": "ongoing",
        "description": "Population surges — Nursery produces {band}× output. Advance turns while it lasts to convert this into extra workers.",
        "duration_bands": [4, 5, 6],
        "effects": {"nursery_mult": "band"},
        "modifier_bands": [1.5, 2.0, 2.5],
        "requires_buildings": ["nursery"],
        "trigger_at": [30, 90, 160],
        "recurring_interval": 80,
    },
    "wandering_scholar": {
        "name": "📚 Wandering Scholar",
        "type": "instant",
        "description": "A passing scholar leaves behind 1 Unidentified Blueprint. Open the Research panel to identify and apply it.",
        "effects": {"grant_blueprints": 1},
        "trigger_at": [18, 65, 130],
        "recurring_interval": 70,
    },
    "idlem_surge": {
        "name": "⚗️ Foundry Surge",
        "type": "ongoing",
        "description": "Ley line energy spikes — the Idlem Foundry runs at {band}× output. Spend Development Turns to stockpile Idlem for the Black Market tree.",
        "duration_bands": [3, 4],
        "effects": {"idlem_mult": "band"},
        "modifier_bands": [1.5, 2.0],
        "requires_buildings": ["idlem_foundry"],
        "trigger_at": [45, 100, 175],
        "recurring_interval": 70,
    },
    "artisan_week": {
        "name": "⚙️ Artisan's Week",
        "type": "ongoing",
        "description": "Skilled craftspeople visit — converter buildings are {band_pct}% more efficient. Keep them stocked with raw materials.",
        "duration_bands": [3, 4, 5],
        "effects": {"converter_bonus": "band"},
        "modifier_bands": [0.20, 0.30, 0.40],
        "requires_buildings": ["foundry", "sawmill", "reliquary"],
        "trigger_at": [28, 72, 135, 195],
        "recurring_interval": 65,
    },
    "trade_boom": {
        "name": "💰 Trade Boom",
        "type": "ongoing",
        "description": "Demand is high — Market gold output is {band_pct}% higher. Staff your Market fully to maximize returns.",
        "duration_bands": [3, 4, 5],
        "effects": {"market_gold_bonus": "band"},
        "modifier_bands": [0.20, 0.30, 0.40, 0.50],
        "requires_buildings": ["market"],
        "trigger_at": [22, 58, 105, 162],
        "recurring_interval": 55,
    },
    # ── NEGATIVE EVENTS ──────────────────────────────────────────────────────
    "worker_fatigue": {
        "name": "😴 Worker Fatigue",
        "type": "ongoing",
        "description": "Workers are exhausted — generator output is reduced by {band_pct}%. This will resolve on its own; no action required.",
        "duration_bands": [3, 4, 5],
        "effects": {"generator_bonus": "neg_band"},
        "modifier_bands": [0.10, 0.15, 0.20, 0.25],
        "requires_buildings": [
            "logging_camp",
            "quarry",
            "market",
            "companion_ranch",
            "war_camp",
        ],
        "trigger_at": [12, 38, 78, 128, 188],
        "recurring_interval": 55,
    },
    "supply_disruption": {
        "name": "📦 Supply Disruption",
        "type": "ongoing",
        "description": "Raw material shipments delayed — converter efficiency is reduced by {band_pct}%. No action required; this will resolve on its own.",
        "duration_bands": [3, 4],
        "effects": {"converter_bonus": "neg_band"},
        "modifier_bands": [0.10, 0.15, 0.20, 0.25],
        "requires_buildings": ["foundry", "sawmill", "reliquary"],
        "trigger_at": [32, 82, 148],
        "recurring_interval": 65,
    },
    "market_slump": {
        "name": "📉 Market Slump",
        "type": "ongoing",
        "description": "Trade is slow — Market gold output is down {band_pct}%. Wait for it to pass.",
        "duration_bands": [3, 4],
        "effects": {"market_gold_bonus": "neg_band"},
        "modifier_bands": [0.15, 0.25, 0.35],
        "requires_buildings": ["market"],
        "trigger_at": [42, 95, 165],
        "recurring_interval": 70,
    },
    # ── CRISIS EVENTS ────────────────────────────────────────────────────────
    "bandit_raid": {
        "name": "⚔️ Bandit Raid",
        "type": "upcoming",
        "description": "Raiders are targeting your {target_building_label}. Use the **Confront** button on your settlement dashboard to repel them, or the building will be disabled.",
        "effects": {
            "spawn_combat": "bandit_captain",
            "on_fail_disable": "target_building",
        },
        "targets_any_building": True,
        "trigger_at": [25, 75, 140, 220],
        "recurring_interval": 80,
        "advance_warning_turns": 3,
    },
    "plague_outbreak": {
        "name": "🦠 Plague Outbreak",
        "type": "upcoming",
        "description": "Disease spreads through your workforce. Use the **Confront** button on your settlement dashboard to purge it, or lose {band_pct}% of all workers.",
        "effects": {
            "spawn_combat": "plague_wraith",
            "on_fail_lose_workers_pct": "band",
        },
        "modifier_bands": [0.01, 0.03, 0.05, 0.07, 0.10],
        "trigger_at": [50, 120, 200],
        "recurring_interval": 90,
        "advance_warning_turns": 4,
    },
    "void_incursion": {
        "name": "🌑 Void Incursion",
        "type": "upcoming",
        "description": "A void rift opens near your {target_building_label}. Use the **Confront** button on your settlement dashboard to seal it, or the building will be disabled.",
        "effects": {
            "spawn_combat": "void_sentry",
            "on_fail_disable": "target_building",
        },
        "targets_building_types": [
            "uber_shrine",
            "void_shrine",
            "black_market",
            "companion_ranch",
            "reliquary",
        ],
        "trigger_at": [100, 200],
        "recurring_interval": 120,
        "advance_warning_turns": 5,
    },
    "fire_hazard": {
        "name": "🔥 Fire Hazard",
        "type": "upcoming",
        "description": "A fire breaks out near your {target_building_label}. Use the **Confront** button on your settlement dashboard to extinguish it, or the building will be disabled.",
        "effects": {
            "spawn_combat": "ember_wraith",
            "on_fail_disable": "target_building",
        },
        "targets_building_types": [
            "logging_camp",
            "sawmill",
            "market",
            "apothecary",
            "barracks",
        ],
        "trigger_at": [35, 85, 150, 225],
        "recurring_interval": 85,
        "advance_warning_turns": 2,
    },
}

# Resources that can be offered to the Black Market (displayed in offering UI)
BM_OFFERABLE_RESOURCES: list[tuple[str, str]] = [
    # (resource_key, display_label)
    ("timber", "🪵 Timber"),
    ("stone", "🪨 Stone"),
    ("iron_ore", "⛏️ Iron Ore"),
    ("coal_ore", "🪨 Coal"),
    ("gold_ore", "🏅 Gold Ore"),
    ("platinum_ore", "💿 Platinum Ore"),
    ("idea_ore", "💡 Idea Ore"),
    ("iron_bar", "🔧 Iron Bars"),
    ("steel_bar", "🔧 Steel Bars"),
    ("gold_bar", "🔧 Gold Bars"),
    ("platinum_bar", "🔧 Platinum Bars"),
    ("idea_bar", "🔧 Idea Bars"),
    ("oak_logs", "🌲 Oak Logs"),
    ("willow_logs", "🌲 Willow Logs"),
    ("mahogany_logs", "🌲 Mahogany Logs"),
    ("magic_logs", "🌲 Magic Logs"),
    ("idea_logs", "🌲 Idea Logs"),
    ("oak_plank", "🪵 Oak Planks"),
    ("willow_plank", "🪵 Willow Planks"),
    ("mahogany_plank", "🪵 Mahogany Planks"),
    ("magic_plank", "🪵 Magic Planks"),
    ("idea_plank", "🪵 Idea Planks"),
    ("desiccated_bones", "🦴 Desiccated Bones"),
    ("regular_bones", "🦴 Regular Bones"),
    ("sturdy_bones", "🦴 Sturdy Bones"),
    ("reinforced_bones", "🦴 Reinforced Bones"),
    ("titanium_bones", "🦴 Titanium Bones"),
    ("refinement_runes", "🔮 Refinement Runes"),
    ("potential_runes", "🔮 Potential Runes"),
    ("shatter_runes", "🔮 Shatter Runes"),
    ("imbue_runes", "🔮 Imbuing Runes"),
    ("dragon_key", "🗝️ Draconic Keys"),
    ("angel_key", "🗝️ Angelic Keys"),
    ("soul_cores", "💠 Soul Cores"),
    ("balance_fragment", "⚖️ Fragments of Balance"),
    ("void_frags", "🌑 Void Fragments"),
    ("magma_core", "🔥 Magma Cores"),
    ("life_root", "🌿 Life Roots"),
    ("spirit_shard", "🌟 Spirit Shards"),
    ("curios", "📦 Curios"),
    ("unidentified_blueprint", "📋 Blueprints"),
    ("spirit_stones", "🔮 Spirit Stones"),
]
