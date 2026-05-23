"""
core/character/passive_data.py
Lookup tables for all passive/essence descriptions used in the profile hub.
"""

_WEAPON_PASSIVE_DESC: dict[str, str] = {
    # Burning family — ATK boost (×8% per tier)
    "burning_1": "On equip: Gain 8% of total ATK as bonus ATK",
    "burning_2": "On equip: Gain 16% of total ATK as bonus ATK",
    "burning_3": "On equip: Gain 24% of total ATK as bonus ATK",
    "burning_4": "On equip: Gain 32% of total ATK as bonus ATK",
    "burning_5": "On equip: Gain 40% of total ATK as bonus ATK",
    # Poison family — Miss damage (×8% per tier)
    "poison_1": "On miss: Deal up to 8% of ATK as damage",
    "poison_2": "On miss: Deal up to 16% of ATK as damage",
    "poison_3": "On miss: Deal up to 24% of ATK as damage",
    "poison_4": "On miss: Deal up to 32% of ATK as damage",
    "poison_5": "On miss: Deal up to 40% of ATK as damage",
    # Debilitate family — DEF shred (×8% per tier)
    "debilitate_1": "Combat start: Enemy DEF -8%",
    "debilitate_2": "Combat start: Enemy DEF -16%",
    "debilitate_3": "Combat start: Enemy DEF -24%",
    "debilitate_4": "Combat start: Enemy DEF -32%",
    "debilitate_5": "Combat start: Enemy DEF -40%",
    # Shocking family — Min damage floor (×8% per tier)
    "shocking_1": "On hit: Dmg is at least 8% of ATK on non-crits",
    "shocking_2": "On hit: Dmg is at least 16% of ATK on non-crits",
    "shocking_3": "On hit: Dmg is at least 24% of ATK on non-crits",
    "shocking_4": "On hit: Dmg is at least 32% of ATK on non-crits",
    "shocking_5": "On hit: Dmg is at least 40% of ATK on non-crits",
    # Sturdy family — DEF boost (×8% per tier)
    "sturdy_1": "On equip: Gain 8% of total DEF as bonus DEF",
    "sturdy_2": "On equip: Gain 16% of total DEF as bonus DEF",
    "sturdy_3": "On equip: Gain 24% of total DEF as bonus DEF",
    "sturdy_4": "On equip: Gain 32% of total DEF as bonus DEF",
    "sturdy_5": "On equip: Gain 40% of total DEF as bonus DEF",
    # Piercing family — Crit chance (+5 per tier)
    "piercing_1": "On equip: Crit Chance +5%",
    "piercing_2": "On equip: Crit Chance +10%",
    "piercing_3": "On equip: Crit Chance +15%",
    "piercing_4": "On equip: Crit Chance +20%",
    "piercing_5": "On equip: Crit Chance +25%",
    # Cull family — Culling threshold (×8% per tier)
    "cull_1": "During combat: Attempts to cull if enemy HP < 8%",
    "cull_2": "During combat: Attempts to cull if enemy HP < 16%",
    "cull_3": "During combat: Attempts to cull if enemy HP < 24%",
    "cull_4": "During combat: Attempts to cull if enemy HP < 32%",
    "cull_5": "During combat: Attempts to cull if enemy HP < 40%",
    # Deadeye family — Hit chance (+4 flat per tier)
    "deadeye_1": "On equip: Hit Chance +4",
    "deadeye_2": "On equip: Hit Chance +8",
    "deadeye_3": "On equip: Hit Chance +12",
    "deadeye_4": "On equip: Hit Chance +16",
    "deadeye_5": "On equip: Hit Chance +20",
    # Echo family — Extra hit damage (×10% per tier)
    "echo_1": "On hit: Extra hit dealing 10% Dmg on non-crits",
    "echo_2": "On hit: Extra hit dealing 20% Dmg on non-crits",
    "echo_3": "On hit: Extra hit dealing 30% Dmg on non-crits",
    "echo_4": "On hit: Extra hit dealing 40% Dmg on non-crits",
    "echo_5": "On hit: Extra hit dealing 50% Dmg on non-crits",
    # Arcane family — Ward on hit (+25 per tier)
    "arcane_1": "On hit: Gain 25 Ward",
    "arcane_2": "On hit: Gain 50 Ward",
    "arcane_3": "On hit: Gain 75 Ward",
    "arcane_4": "On hit: Gain 100 Ward",
    "arcane_5": "On hit: Gain 125 Ward",
}

_INFERNAL_PASSIVE_DESC: dict[str, str] = {
    "soulreap": "On victory: Heal to full HP",
    "inverted edge": "Combat start: Swap weapon ATK and DEF",
    "gilded hunger": "Combat start: Gain ATK equal to 10% of weapon rarity",
    "cursed precision": "During combat: +20% Crit Chance; your critical damage is unlucky",
    "diabolic pact": "Combat start: Take 90% max HP as True Damage and double ATK",
    "perdition": "On miss: Deal 75% of weapon ATK",
    "voracious": "On hit: Gain a stack of Voracity; Each stack gives +5% Crit Chance. On crit: Lose all stacks.",
    "last rites": "On crit: Deal an additional 5% of enemy current HP",
}

_ARMOR_PASSIVE_DESC: dict[str, str] = {
    "impregnable": "During combat: Your PDR cap is increased by 10% (90%)",
    "piety": "On hit: 10% chance to deal 700% increased damage",
    "transcendence": "Combat start: Gain 20% of your total ATK and DEF as bonus ATK",
    "treasure hunter": "On victory: +3% Special Rarity",
    "unlimited wealth": "Combat start: 20% chance to gain 200% more Rarity as bonus rarity",
    "alchemist": "During combat: 30% chance to not consume a potion on use",
}

_CELESTIAL_PASSIVE_DESC: dict[str, str] = {
    "celestial ghostreaver": "Turn start: Gain 50–200 Ward",
    "celestial glancing blows": "Combat start: Block Chance doubled. During combat: Blocked hits deal 50% damage",
    "celestial wind dancer": "Combat start: Evasion Chance tripled; Helmet is disabled",
    "celestial sanctity": "During combat: Damage dealt by enemies is unlucky",
    "celestial vow": "Once per combat: Survive a fatal blow at 1 HP, gain 50% of Max HP as Ward",
    "celestial fortress": "During combat: Gain +1% PDR per 5% missing HP",
}

_VOID_PASSIVE_DESC: dict[str, str] = {
    "entropy": "Combat start: 20% of Weapon ATK added to Weapon DEF and vice versa",
    "void echo": "Combat start: Gain 15% of Weapon ATK as bonus ATK",
    "unravelling": "Combat start: Reduce monster DEF by 20%",
    "void gaze": "On crit: Gain a Gaze stack, reduce monster ATK by 3% per stack (up to 30)",
    "fracture": "On crit: 5% chance to instantly kill (Ubers are immune)",
    "nullfield": "Turn start: 15% chance to nullify incoming damage",
    "eternal hunger": "On hit: Gain a Hunger stack, deal 10% of monster max HP and restore to full HP at 10 stacks (lose all stacks after)",
    "oblivion": "On miss: Deal 50% of ATK as damage",
}

_ACCESSORY_PASSIVE_FUNCS: dict = {
    "obliterate": lambda l: f"On hit: {l * 4}% chance to deal 100% increased damage",
    "absorb": lambda l: f"Combat start: {l * 10}% chance to steal 10% of Monster ATK & DEF as bonus ATK & DEF",
    "prosper": lambda l: f"On victory: {l * 10}% chance for 100% increased Gold",
    "infinite wisdom": lambda l: f"On victory: {l * 5}% chance for 100% increased XP",
    "lucky strikes": lambda l: f"Turn start: {l * 10}% chance for Hit chance to be lucky",
}

_GLOVE_PASSIVE_FUNCS: dict = {
    "ward-touched": lambda l: f"On hit: Gain {l*25} Ward on non-crits",
    "ward-fused": lambda l: f"On crit: Gain {l*50} Ward",
    "instability": lambda l: f"On hit: Damage dealt is decreased by 50% or increased by {150 + l * 10}%",
    "deftness": lambda l: f"On crit: Crit damage is increased by at least {l * 5}% of max",
    "adroit": lambda l: f"On hit: Hit damage is increased by at least {l * 2}% of ATK on non-crits",
    "equilibrium": lambda l: f"On victory: Gain {l * 5}% of Dmg dealt as XP",
    "plundering": lambda l: f"On victory: Gain {l * 10}% of Dmg dealt as Gold",
}

_BOOT_PASSIVE_FUNCS: dict = {
    "speedster": lambda l: f"On equip: Combat cooldown reduced by {l}m",
    "skiller": lambda l: f"On victory: {l * 5}% chance to find extra gathering materials",
    "treasure-tracker": lambda l: f"On equip: {l * 0.5:.1f}% added chance to encounter a Treasure Monster",
    "hearty": lambda l: f"On equip: Increase Max HP by {l * 5}%",
    "cleric": lambda l: f"During combat: Potion healing is increased by {l * 10}%",
    "thrill-seeker": lambda l: f"On victory: +{l * 0.5:.1f}% Special Rarity",
}

_HELMET_PASSIVE_FUNCS: dict = {
    "juggernaut": lambda l: f"Combat start: Gain {l * 4}% of total DEF as bonus ATK",
    "insight": lambda l: f"On equip: Crit Dmg Multiplier +{l * 0.1:.1f}×",
    "volatile": lambda l: f"During combat: Deal {l * 100}% of Max HP as Dmg on ward break",
    "divine": lambda l: f"During combat: Converts {l * 100}% of Potion Overheal to Ward",
    "frenzy": lambda l: f"During combat: {l * 0.5:.1f}% increased damage per 1% missing HP",
    "leeching": lambda l: f"During combat: Heal {l * 0.02:.2f}% of damage dealt",
    "thorns": lambda l: f"On block: Reflect {l * 100}% of blocked damage",
    "ghosted": lambda l: f"On dodge: Gain {l * 10} Ward",
}

_CORRUPTED_DESC: dict[tuple, str] = {
    ("aphrodite", "glove"): "During combat: Your ward is considered broken whenever it is damaged.",
    ("aphrodite", "boot"): "On victory: Your gear drop rate is lucky.",
    ("aphrodite", "helmet"): "During combat: Your ward can never be reduced or disabled by modifiers.",
    ("lucifer", "glove"): "On hit: 15% of your current ward is added to your damage.",
    ("lucifer", "boot"): "On victory: Gain up to 50% increased gold per monster modifier.",
    (
        "lucifer",
        "helmet",
    ): "During combat: When your ward is broken, gain 15% PDR.",
    (
        "gemini",
        "glove",
    ): "On crit: Strike again for 50% damage.",
    ("gemini", "boot"): "On victory: Your pet drop chance is doubled.",
    (
        "gemini",
        "helmet",
    ): "During combat: Your damage taken is reduced by 20% and split evenly between HP and Ward.",
    ("neet", "glove"): "During combat: Your accuracy is 0.",
    ("neet", "boot"): "On victory: Whenever you gain resources during combat, gain double instead.",
    ("neet", "helmet"): "During combat: Whenever you gain ward, double the ward gained.",
}

_SLAYER_EMBLEM_NAMES: dict[str, str] = {
    "slayer_dmg": "Slayer Target Damage",
    "boss_dmg": "Boss Damage",
    "combat_dmg": "Normal Monster Damage",
    "slayer_def": "Slayer Target DEF",
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
    "bloodthirst": ("Bloodthirst", lambda v: f"Heal {v:.2f}% of critical hit damage"),
    "providence": ("Providence", lambda v: f"+{v}% more to total rarity"),
    "precision": ("Insight", lambda v: f"+{v} flat crit chance"),
    "affluence": ("Affluence", lambda v: f"+{v}% XP and Gold from combat"),
    "bulwark": ("Bulwark", lambda v: f"+{v}% Percent Damage Reduction"),
    "resilience": ("Resilience", lambda v: f"+{int(v)} Flat Damage Reduction"),
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
