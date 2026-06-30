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
    "piety": "On hit: 10% chance to deal 600% increased damage",
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
    "obliterate": lambda lvl: (
        f"On hit: {lvl * 4}% chance to deal 100% increased damage"
    ),
    "absorb": lambda lvl: (
        f"Combat start: {lvl * 10}% chance to steal 10% of Monster ATK & DEF as bonus ATK & DEF"
    ),
    "prosper": lambda lvl: f"On victory: {lvl * 10}% chance for 100% increased Gold",
    "infinite wisdom": lambda lvl: (
        f"On victory: {lvl * 5}% chance for 100% increased XP"
    ),
    "lucky strikes": lambda lvl: (
        f"Turn start: {lvl * 10}% chance for Hit chance to be lucky"
    ),
}

_GLOVE_PASSIVE_FUNCS: dict = {
    "ward-touched": lambda lvl: f"On hit: Gain {lvl * 25} Ward on non-crits",
    "ward-fused": lambda lvl: f"On crit: Gain {lvl * 50} Ward",
    "instability": lambda lvl: (
        f"On hit: Damage dealt is decreased by 50% or increased by {150 + lvl * 10}%"
    ),
    "deftness": lambda lvl: (
        f"On crit: Crit damage is increased by at least {lvl * 5}% of max"
    ),
    "adroit": lambda lvl: (
        f"On hit: Hit damage is increased by at least {lvl * 2}% of ATK on non-crits"
    ),
    "equilibrium": lambda lvl: f"On victory: Gain {lvl * 5}% of Dmg dealt as XP",
    "plundering": lambda lvl: f"On victory: Gain {lvl * 10}% of Dmg dealt as Gold",
}

_BOOT_PASSIVE_FUNCS: dict = {
    "speedster": lambda lvl: f"On equip: Combat cooldown reduced by {lvl}m",
    "skiller": lambda lvl: (
        f"On victory: {lvl * 5}% chance to find extra gathering materials"
    ),
    "treasure-tracker": lambda lvl: (
        f"On equip: {lvl * 0.5:.1f}% added chance to encounter a Treasure Monster"
    ),
    "hearty": lambda lvl: f"On equip: Increase Max HP by {lvl * 5}%",
    "cleric": lambda lvl: f"During combat: Potion healing is increased by {lvl * 10}%",
    "thrill-seeker": lambda lvl: f"On victory: +{lvl * 0.5:.1f}% Special Rarity",
}

_HELMET_PASSIVE_FUNCS: dict = {
    "juggernaut": lambda lvl: (
        f"Combat start: Gain {lvl * 4}% of total DEF as bonus ATK"
    ),
    "insight": lambda lvl: f"On equip: Crit Dmg Multiplier +{lvl * 0.1:.1f}×",
    "volatile": lambda lvl: (
        f"During combat: Deal {lvl * 100}% of Max HP as Dmg on ward break"
    ),
    "divine": lambda lvl: (
        f"During combat: Converts {lvl * 100}% of Potion Overheal to Ward"
    ),
    "frenzy": lambda lvl: (
        f"During combat: {lvl * 0.5:.1f}% increased damage per 1% missing HP"
    ),
    "leeching": lambda lvl: f"During combat: Heal {lvl * 0.2:.2f}% of damage dealt",
    "thorns": lambda lvl: f"On block: Reflect {lvl * 500}% of blocked damage",
    "ghosted": lambda lvl: f"On dodge: Gain {lvl * 10} Ward",
}

_CORRUPTED_DESC: dict[tuple, str] = {
    (
        "aphrodite",
        "glove",
    ): "During combat: Your ward is considered broken whenever it is damaged.",
    ("aphrodite", "boot"): "On victory: Your gear drop rate is lucky.",
    (
        "aphrodite",
        "helmet",
    ): "During combat: Your ward can never be reduced or disabled by modifiers.",
    ("lucifer", "glove"): "On hit: 15% of your current ward is added to your damage.",
    (
        "lucifer",
        "boot",
    ): "On victory: Gain up to 50% increased gold per monster modifier.",
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
    (
        "neet",
        "boot",
    ): "On victory: Whenever you gain resources during combat, gain double instead.",
    (
        "neet",
        "helmet",
    ): "During combat: Whenever you gain ward, double the ward gained.",
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
    "corrupted_find": lambda t: (
        f"+{t * 0.2:.1f}% corrupted encounter chance (Level 100+)"
    ),
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

_HEMATURGY_SHORT_FUNCS: dict = {
    "reverberation": lambda t: (
        f"On hit: {[40, 50, 60, 70, 80][t - 1]}% chance for echoes to retrigger (−10% per chain)"
    ),
    "soothing_venom": lambda t: (
        f"On miss: Leech {[2, 4, 6, 8, 10][t - 1]}% of poison damage as HP"
    ),
    "iron_momentum": lambda t: (
        f"On hit: +{[3, 5, 7, 9, 11][t - 1]}% ATK per stack (max 5); On miss: reset stacks"
    ),
    "serrated": lambda t: (
        f"On hit: −{[5, 10, 15, 20, 25][t - 1]} monster ATK (crits: ×2 reduction)"
    ),
    "haemorrhage": lambda t: (
        f"On hit: Add {[2, 3, 4, 5, 6][t - 1]}% ATK to bleed pool; Turn start: deal 10% of pool"
    ),
    "vital_resonance": lambda t: (
        f"On ward gain: Heal {[10, 15, 20, 25, 30][t - 1]}% of ward gained as HP"
    ),
    "executioners_rite": lambda t: (
        f"During combat: +{[10, 15, 20, 25, 30][t - 1]}% ATK and crit damage while monster HP < 30%"
    ),
    "crimson_feast": lambda t: (
        f"On kill: Restore {[10, 15, 20, 25, 30][t - 1]}% of Max HP"
    ),
    "phantom_reflex": lambda t: (
        f"On miss: +{[10, 15, 20, 25, 30][t - 1]}% evasion per stack (max 2); On hit: lose 1 stack"
    ),
    "chain_reaction": lambda t: (
        f"On crit: +{[8, 12, 16, 20, 24][t - 1]}% crit damage per stack (max 5); On miss: reset"
    ),
    "regenerative_tissue": lambda t: (
        f"During combat: Heal {[2, 3, 4, 5, 6][t - 1]}% Max HP after any zero-damage round"
    ),
    "fevered_strike": lambda t: (
        f"On potion use: +{[5, 8, 11, 14, 17][t - 1]}% ATK for this fight (stacks)"
    ),
    "predators_mark": lambda t: (
        f"On crit: Mark target; next hit deals +{[15, 20, 25, 30, 35][t - 1]}% bonus damage"
    ),
    "counterforce": lambda t: (
        f"During combat: {[20, 25, 30, 35, 40][t - 1]}% of total DEF added as flat ATK"
    ),
    "defiance": lambda t: (
        f"Once per fight: Below 40% HP, gain +{[10, 15, 20, 25, 30][t - 1]}% ATK and DEF"
    ),
    "spectral_waltz": lambda t: (
        f"On hit: Gain 1 blade (max {[5, 6, 7, 8, 10][t - 1]}); On crit: Release all for {[5, 5, 6, 7, 8][t - 1]}% ATK each"
    ),
    "puncture": lambda t: (
        f"On crit: Build {[5, 8, 11, 14, 17][t - 1]}% crit damage as bleed pool; On miss: burst 50%"
    ),
    "flash_frost": lambda t: (
        f"On miss: After {[15, 13, 11, 9, 7][t - 1]} consecutive misses, freeze monster for 1 round"
    ),
    "ward_inoculation": lambda t: (
        f"Combat start: Ward→DEF, Max HP doubled; On ward gain: deal {[60, 70, 80, 90, 100][t - 1]}% as damage"
    ),
    "soul_fracture": lambda t: (
        f"During combat: +{[3, 5, 7, 9, 11][t - 1]}% ATK per 10% Max HP lost this fight"
    ),
}

# Alchemy potion passives — (value, duration) → description string
_POTION_PASSIVE_DESCS: dict[str, tuple[str, callable]] = {
    "panacea": (
        "🌿 Panacea",
        lambda v, d: (
            f"On potion use: {v:.0f}% chance to cleanse ailments and grant {d:.0f}t immunity"
        ),
    ),
    "eclipse": (
        "🌑 Eclipse",
        lambda v, d: (
            f"On potion use: next {d:.0f} attacks deal +{v:.0f}% damage and are guaranteed crits"
        ),
    ),
    "aegis": (
        "🛡️ Aegis",
        lambda v, d: f"On potion use: shield = {v:.0f}% max HP for {d:.0f} turns",
    ),
    "enfeeble": (
        "🌊 Enfeeble",
        lambda v, d: (
            f"On potion use: monster −{v:.0f}% ATK/DEF for {d:.0f} of its turns"
        ),
    ),
    "blood_tithe": (
        "🩸 Blood Tithe",
        lambda v, d: (
            f"On potion use: leech {v:.0f}% of damage as HP for next {d:.0f} hits"
        ),
    ),
    "accel": (
        "⚡ Accel",
        lambda v, d: f"On potion use: +{v:.0f}% Hit Chance for {d:.0f} turns",
    ),
    "quench": (
        "🍺 Quench",
        lambda v, d: (
            f"On potion use: heal +{v:.0f}% max HP then 5% max HP/turn for {d:.0f} turns"
        ),
    ),
    "viper": (
        "🐍 Viper",
        lambda v, d: (
            f"On potion use: {v:.0f}% heal as burst damage + DoT for {d:.0f} turns"
        ),
    ),
    "enrage": (
        "💪 Enrage",
        lambda v, d: f"On potion use: +{v:.0f}% ATK and DEF for {d:.0f} monster turns",
    ),
    "barrier": (
        "🔮 Barrier",
        lambda v, d: (
            f"On potion use: +{v:.0f}% of heal as Ward each turn for {d:.0f} turns"
        ),
    ),
    "painkiller": (
        "🩹 Painkiller",
        lambda v, d: (
            f"On potion use: −{v:.0f}% damage from the monster's next {d:.0f} hits"
        ),
    ),
}
