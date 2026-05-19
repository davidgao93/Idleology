"""
core/character/passive_data.py
Lookup tables for all passive/essence descriptions used in the profile hub.
"""

_WEAPON_PASSIVE_DESC: dict[str, str] = {
    # Burning family — Atk boost (×8% per tier)
    "burning_1": "Atk +8%",
    "burning_2": "Atk +16%",
    "burning_3": "Atk +24%",
    "burning_4": "Atk +32%",
    "burning_5": "Atk +40%",
    # Poison family — Miss damage (×8% per tier)
    "poison_1": "Miss deals up to 8% Atk",
    "poison_2": "Miss deals up to 16% Atk",
    "poison_3": "Miss deals up to 24% Atk",
    "poison_4": "Miss deals up to 32% Atk",
    "poison_5": "Miss deals up to 40% Atk",
    # Debilitate family — Def shred (×8% per tier)
    "debilitate_1": "Enemy Def -8%",
    "debilitate_2": "Enemy Def -16%",
    "debilitate_3": "Enemy Def -24%",
    "debilitate_4": "Enemy Def -32%",
    "debilitate_5": "Enemy Def -40%",
    # Shocking family — Min damage floor (×8% per tier)
    "shocking_1": "Min Dmg floor 8% of max",
    "shocking_2": "Min Dmg floor 16% of max",
    "shocking_3": "Min Dmg floor 24% of max",
    "shocking_4": "Min Dmg floor 32% of max",
    "shocking_5": "Min Dmg floor 40% of max",
    # Sturdy family — Def boost (×8% per tier)
    "sturdy_1": "Def +8%",
    "sturdy_2": "Def +16%",
    "sturdy_3": "Def +24%",
    "sturdy_4": "Def +32%",
    "sturdy_5": "Def +40%",
    # Piercing family — Crit chance (+5 per tier)
    "piercing_1": "Crit Chance +5%",
    "piercing_2": "Crit Chance +10%",
    "piercing_3": "Crit Chance +15%",
    "piercing_4": "Crit Chance +20%",
    "piercing_5": "Crit Chance +25%",
    # Cull family — Culling threshold (×8% per tier)
    "cull_1": "Instantly kill if enemy HP < 8%",
    "cull_2": "Instantly kill if enemy HP < 16%",
    "cull_3": "Instantly kill if enemy HP < 24%",
    "cull_4": "Instantly kill if enemy HP < 32%",
    "cull_5": "Instantly kill if enemy HP < 40%",
    # Deadeye family — Hit chance (+4 flat per tier)
    "deadeye_1": "Flat Hit Chance +4",
    "deadeye_2": "Flat Hit Chance +8",
    "deadeye_3": "Flat Hit Chance +12",
    "deadeye_4": "Flat Hit Chance +16",
    "deadeye_5": "Flat Hit Chance +20",
    # Echo family — Extra hit damage (×10% per tier)
    "echo_1": "Extra hit 10% Dmg",
    "echo_2": "Extra hit 20% Dmg",
    "echo_3": "Extra hit 30% Dmg",
    "echo_4": "Extra hit 40% Dmg",
    "echo_5": "Extra hit 50% Dmg",
    # Arcane family — Ward on hit (+25 per tier)
    "arcane_1": "Gain 25 Ward on hit",
    "arcane_2": "Gain 50 Ward on hit",
    "arcane_3": "Gain 75 Ward on hit",
    "arcane_4": "Gain 100 Ward on hit",
    "arcane_5": "Gain 125 Ward on hit",
}

_INFERNAL_PASSIVE_DESC: dict[str, str] = {
    "soulreap": "Restore HP to full after every successful encounter",
    "inverted edge": "At combat start, swap weapon Attack and Defence",
    "gilded hunger": "Gain Attack equal to 10% of weapon rarity",
    "cursed precision": "+20% Crit Chance; your critical damage is unlucky",
    "diabolic pact": "At combat start, lose 90% max HP and double Attack",
    "perdition": "Missed attacks deal 75% weapon Attack",
    "voracious": "Gain a voracious stack on hit; Each stack gives +5% crit chance. Stacks reset on crit.",
    "last rites": "Critical hits deal an additional 10% of enemy current HP",
}

_ARMOR_PASSIVE_DESC: dict[str, str] = {
    "impregnable": "Raises your PDR cap from 80% to 90% during combat",
    "piety": "Attacks have a 10% chance to deal 7× damage",
    "transcendence": "On Combat Start, gain 20% of your total ATK and DEF as bonus ATK",
    "treasure hunter": "+3% Special Drop Chance",
    "unlimited wealth": "20% chance to multiply Rarity ×5 at combat start",
    "alchemist": "30% chance to not consume a potion when using one in combat",
}

_CELESTIAL_PASSIVE_DESC: dict[str, str] = {
    "celestial ghostreaver": "Generate 50–200 Ward every turn",
    "celestial glancing blows": "Doubles Block Chance; blocked hits deal 50% damage",
    "celestial wind dancer": "Triples Evasion Chance; disables Helmet entirely",
    "celestial sanctity": "Enemies roll final damage twice, apply the lower result",
    "celestial vow": "Once per combat, survive a fatal blow at 1 HP, gain 50% Max HP as Ward",
    "celestial fortress": "+1% PDR per 5% missing HP",
}

_VOID_PASSIVE_DESC: dict[str, str] = {
    "entropy": "At combat start, 20% of weapon ATK added to DEF and vice versa",
    "void echo": "At combat start, 15% of weapon Attack copied to accessory",
    "unravelling": "At combat start, reduce monster Defence by 20%",
    "void gaze": "On crit, reduce monster Attack by 3% per stack (up to 30 stacks)",
    "fracture": "On crit, 5% chance to instantly kill",
    "nullfield": "15% chance to completely absorb incoming damage",
    "eternal hunger": "At 10 hit stacks, deal 10% of monster max HP and restore full HP",
    "oblivion": "Missed attacks deal 50% of total attack damage",
}

_ACCESSORY_PASSIVE_FUNCS: dict = {
    "obliterate": lambda l: f"{l * 2}% chance to deal Double Damage",
    "absorb": lambda l: f"{l * 10}% chance to steal 10% of Monster ATK & DEF",
    "prosper": lambda l: f"{l * 10}% chance to Double Gold",
    "infinite wisdom": lambda l: f"{l * 5}% chance to Double XP",
    "lucky strikes": lambda l: f"{l * 10}% chance for Lucky Hits",
}

_GLOVE_PASSIVE_FUNCS: dict = {
    "ward-touched": lambda l: f"Gain {l*25} Ward on Hits",
    "ward-fused": lambda l: f"Gain {l*50} Ward on Crits",
    "instability": lambda l: f"Hits are 50% OR {150 + l * 10}% damage",
    "deftness": lambda l: f"Crit Floor raised by {l * 5}%",
    "adroit": lambda l: f"Normal Hit Floor raised by {l * 2}%",
    "equilibrium": lambda l: f"Gain {l * 5}% of Dmg as Bonus XP",
    "plundering": lambda l: f"Gain {l * 10}% of Dmg as Bonus Gold",
}

_BOOT_PASSIVE_FUNCS: dict = {
    "speedster": lambda l: f"Cooldown reduced by {l}m",
    "skiller": lambda l: f"{l * 5}% chance for extra skill materials",
    "treasure-tracker": lambda l: f"Treasure Mob chance +{l * 0.5:.1f}%",
    "hearty": lambda l: f"Max HP +{l * 5}%",
    "cleric": lambda l: f"Potions heal {l * 10}% extra",
    "thrill-seeker": lambda l: f"Special Drop Chance +{l}%",
}

_HELMET_PASSIVE_FUNCS: dict = {
    "juggernaut": lambda l: f"Gain {l * 4}% of Base Def as Atk",
    "insight": lambda l: f"Crit Dmg Multiplier +{l * 0.1:.1f}× (total: {2.0 + l * 0.1:.1f}×)",
    "volatile": lambda l: f"Deal {l * 100}% of Max HP as Dmg on ward break",
    "divine": lambda l: f"Converts {l * 100}% of Potion Overheal to Ward",
    "frenzy": lambda l: f"{l * 0.5:.1f}% increased damage per 1% missing HP",
    "leeching": lambda l: f"Heal {l * 2}% of base damage dealt",
    "thorns": lambda l: f"Reflect {l * 100}% of blocked damage",
    "ghosted": lambda l: f"Gain {l * 10} Ward on Dodge",
}

_CORRUPTED_DESC: dict[tuple, str] = {
    ("aphrodite", "glove"): "Your ward is considered broken when it is damaged.",
    ("aphrodite", "boot"): "Your gear drop rate is lucky.",
    ("aphrodite", "helmet"): "Your ward can never be reduced by modifiers.",
    ("lucifer", "glove"): "15% of your current ward is added to your hit damage.",
    ("lucifer", "boot"): "Gain up to 50% increased gold per monster modifier.",
    (
        "lucifer",
        "helmet",
    ): "When your ward is broken, gain 15% PDR for the remainder of that encounter.",
    (
        "gemini",
        "glove",
    ): "Critical hits strike twice, the second strike deals less damage.",
    ("gemini", "boot"): "Your pet drop chance is doubled.",
    (
        "gemini",
        "helmet",
    ): "Your damage taken is halved, but is split evenly between HP and Ward.",
    ("neet", "glove"): "Your accuracy is 0.",
    ("neet", "boot"): "Whenever you gain resources during combat, gain double instead.",
    ("neet", "helmet"): "Whenever you gain ward, double the ward gained.",
}

_SLAYER_EMBLEM_NAMES: dict[str, str] = {
    "slayer_dmg": "Slayer Target Damage",
    "boss_dmg": "Boss Damage",
    "combat_dmg": "Normal Monster Damage",
    "slayer_def": "Slayer Target Defence",
    "crit_dmg": "Crit Damage",
    "accuracy": "Accuracy",
    "gold_find": "Gold Find",
    "xp_find": "XP Find",
    "task_progress": "Double Task Progress",
    "slayer_drops": "Slayer Drop Rate",
    "corrupted_find": "Corrupted Attunement",
}

_SLAYER_EMBLEM_FUNCS: dict = {
    "slayer_dmg": lambda t: f"+{t * 5}% damage vs assigned slayer species",
    "boss_dmg": lambda t: f"+{t * 5}% damage vs bosses",
    "combat_dmg": lambda t: f"+{t * 2}% damage vs normal monsters",
    "slayer_def": lambda t: f"+{t * 2}% defence vs assigned slayer species",
    "crit_dmg": lambda t: f"+{t * 5}% critical hit damage",
    "accuracy": lambda t: f"+{t * 2} flat accuracy",
    "gold_find": lambda t: f"+{t * 3}% gold from combat",
    "xp_find": lambda t: f"+{t * 3}% XP from combat",
    "task_progress": lambda t: f"{t * 5}% chance for a kill to count twice",
    "slayer_drops": lambda t: f"{t * 5}% chance for extra slayer drops",
    "corrupted_find": lambda t: f"+{t * 0.2:.1f}% corrupted encounter chance",
}

_CODEX_TOME_INFO: dict = {
    "vitality": ("Vitality", lambda v: f"+{v}% Max HP"),
    "wrath": ("Wrath", lambda v: f"+{v}% of base DEF as bonus ATK"),
    "bastion": ("Bastion", lambda v: f"+{v}% of base ATK as bonus DEF"),
    "tenacity": ("Tenacity", lambda v: f"{v}% chance per hit to halve damage"),
    "bloodthirst": ("Bloodthirst", lambda v: f"Heal {v}% of critical hit damage"),
    "providence": ("Providence", lambda v: f"+{v}% more to total rarity"),
    "precision": ("Precision", lambda v: f"+{v} flat crit chance"),
    "insight": ("Insight", lambda v: f"+{v} flat crit chance"),
    "affluence": ("Affluence", lambda v: f"+{v}% XP and Gold from combat"),
    "bulwark": ("Bulwark", lambda v: f"+{v}% Percent Damage Reduction"),
    "resilience": ("Resilience", lambda v: f"+{v} Flat Damage Reduction"),
}

# Roman numeral display for passive tiers
_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}

_HEMATURGY_PASSIVE_NAMES: dict[str, str] = {
    # Main pool
    "reverberation": "Reverberation",
    "soothing_venom": "Soothing Venom",
    "iron_momentum": "Iron Momentum",
    "serrated": "Serrated",
    "haemorrhage": "Haemorrhage",
    "vital_resonance": "Vital Resonance",
    "executioners_rite": "Executioner's Rite",
    "bloodthirst": "Bloodthirst",
    "phantom_reflex": "Phantom Reflex",
    "chain_reaction": "Chain Reaction",
    "regenerative_tissue": "Regenerative Tissue",
    "fevered_strike": "Fevered Strike",
    "predators_mark": "Predator's Mark",
    "counterforce": "Counterforce",
    "tenacity": "Tenacity",
    # Mutated pool
    "spectral_waltz": "Spectral Waltz",
    "puncture": "Puncture",
    "flash_frost": "Flash Frost",
    "ward_inoculation": "Ward Inoculation",
    "soul_fracture": "Soul Fracture",
}

_HEMATURGY_SHORT_FUNCS: dict = {
    "reverberation": lambda t: f"Echoing hits have {[40,50,60,70,80][t-1]}% to retrigger",
    "soothing_venom": lambda t: f"{[2,4,6,8,10][t-1]}% of poison dmg leeched as hp",
    "iron_momentum": lambda t: f"+{[3,5,7,9,11][t-1]}% ATK per consecutive hit (max 5; resets on miss)",
    "serrated": lambda t: f"−{[5,10,15,20,25][t-1]} monster ATK per hit (crits: ×2)",
    "haemorrhage": lambda t: f"Hits add {[2,3,4,5,6][t-1]}% ATK to bleed pool; pool ticks 10%/round",
    "vital_resonance": lambda t: f"{[10,15,20,25,30][t-1]}% of ward gained simultaneously heals HP",
    "executioners_rite": lambda t: f"+{[10,15,20,25,30][t-1]}% ATK & crit-dmg while monster HP < 30%",
    "bloodthirst": lambda t: f"On kill: restore {[10,15,20,25,30][t-1]}% Max HP",
    "phantom_reflex": lambda t: f"On miss: +{[10,15,20,25,30][t-1]}% evasion, lose ",
    "chain_reaction": lambda t: f"+{[8,12,16,20,24][t-1]}% crit-dmg per consecutive crit (max 5)",
    "regenerative_tissue": lambda t: f"Heal {[2,3,4,5,6][t-1]}% Max HP after any zero-damage round",
    "fevered_strike": lambda t: f"+{[5,8,11,14,17][t-1]}% ATK per potion consumed this fight",
    "predators_mark": lambda t: f"Crits mark target; next hit deals +{[15,20,25,30,35][t-1]}% bonus dmg",
    "counterforce": lambda t: f"{[5,8,11,14,17][t-1]}% of total DEF added as flat ATK",
    "tenacity": lambda t: f"HP < 40% trigger: +{[10,15,20,25,30][t-1]}% ATK & DEF for this fight",
    "spectral_waltz": lambda t: f"+1 blade/hit (max {[5,6,7,8,10][t-1]}); crits release all at {[5,5,6,7,8][t-1]}% ATK each",
    "puncture": lambda t: f"Crits build {[5,8,11,14,17][t-1]}% crit-dmg as bleed; 50% bursts on miss",
    "flash_frost": lambda t: f"After {[15,13,11,9,7][t-1]} consecutive misses: freeze monster 1 round",
    "ward_inoculation": lambda t: f"Start: ward→DEF + Max HP doubled; ward gained deals {[60,70,80,90,100][t-1]}% as dmg",
    "soul_fracture": lambda t: f"+{[3,5,7,9,11][t-1]}% ATK per 10% Max HP lost this combat",
}
