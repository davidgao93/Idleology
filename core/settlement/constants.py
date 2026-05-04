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
    "foundry": "Converts Ore into Ingots.",
    "sawmill": "Converts Logs into Planks.",
    "reliquary": "Converts Bones into Essence.",
    "market": "Generates Passive Gold.",
    "barracks": "Passive: +1% Atk/Def per 100 Workers.",
    "temple": "Passive: +5% Propagate follower gain per 100 Workers.",
    "apothecary": "Passive: Increases Potion Healing (+0.02% HP per assigned Worker).",
    "black_market": "Special: Trade various resources for myterious caches.",
    "companion_ranch": "Generator: Produces XP Cookies for pets.",
    "celestial_shrine": "Passive: Increases chance to find Celestial Sigils from Aphrodite.",
    "infernal_forge": "Passive: Increases chance to find Infernal Sigils from Lucifer.",
    "void_sanctum": "Passive: Increases chance to find Void Sigils from NEET.",
    "twin_shrine": "Passive: Increases chance to find Gemini Sigils from the Gemini Twins.",
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
    "celestial_shrine": {"gold": 10000000, "timber": 100000, "stone": 100000},
    "infernal_forge": {"gold": 10000000, "timber": 100000, "stone": 100000},
    "void_sanctum": {"gold": 10000000, "timber": 100000, "stone": 100000},
    "twin_shrine": {"gold": 10000000, "timber": 100000, "stone": 100000},
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
    "celestial_shrine": "celestial_stone",
    "infernal_forge": "infernal_cinder",
    "void_sanctum": "void_crystal",
    "twin_shrine": "bound_crystal",
}

ITEM_NAMES = {
    "magma_core": "Magma Core",
    "life_root": "Life Root",
    "spirit_shard": "Spirit Shard",
    "celestial_stone": "Celestial Stone",
    "infernal_cinder": "Infernal Cinder",
    "void_crystal": "Void Crystal",
    "bound_crystal": "Bound Crystal",
}

UBER_BUILDINGS = {"celestial_shrine", "infernal_forge", "void_sanctum", "twin_shrine"}

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
