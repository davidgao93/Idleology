# core/config.py
MONSTER_MODIFIERS = {
    "Steel-born": {
        "effect": "defence",
        "value": 1.1,
        "description": "10% boost to monster defense"
    },
    "All-seeing": {
        "effect": "accuracy",
        "value": 1.1,
        "description": "10% boost to monster accuracy"
    },
    "Mirror Image": {
        "effect": "double_damage_chance",
        "value": 0.2,
        "description": "20% chance to deal double damage"
    },
    "Volatile": {
        "effect": "post_combat_explosion",
        "value": 1,
        "description": "Explodes after combat, reducing player HP to 1"
    },
    "Glutton": {
        "effect": "hp_multiplier",
        "value": 2.0,
        "description": "Doubles monster HP, no extra XP"
    },
    "Enfeeble": {
        "effect": "decrease_player_attack",
        "value": 0.9,
        "description": "Decreases player's attack by 10%"
    },
    "Venomous": {
        "effect": "damage_on_miss",
        "value": 1,
        "description": "Deals 1 damage on every miss"
    },
    "Strengthened": {
        "effect": "max_hit_increase",
        "value": 3,
        "description": "+3 to monster max hit"
    },
    "Hellborn": {
        "effect": "extra_damage_per_hit",
        "value": 2,
        "description": "+2 damage on each successful hit"
    },
    "Lucifer-touched": {
        "effect": "lucky_attacks",
        "value": "lucky",
        "description": "Lucky attacks"
    },
    "Titanium": {
        "effect": "damage_reduction",
        "value": 0.9,
        "description": "Player damage reduced by 10%"
    },
    "Ascended": {
        "effect": "stats_boost",
        "value": {"attack": 10, "defence": 10},
        "description": "+10 Attack, +10 Defence"
    },
    "Summoner": {
        "effect": "echo_damage",
        "value": 1/6,
        "description": "Minions echo hits for 1/6 the monster hit"
    },
    "Shield-breaker": {
        "effect": "disable_ward",
        "value": True,
        "description": "Player has no ward"
    },
    "Impenetrable": {
        "effect": "disable_crit",
        "value": True,
        "description": "Player cannot crit"
    },
    "Unblockable": {
        "effect": "disable_block",
        "value": True,
        "description": "Player cannot block"
    },
    "Unavoidable": {
        "effect": "disable_evade",
        "value": True,
        "description": "Player has no additional evade chance"
    }
}

DROP_RATES = {
    "weapon": 90,
    "accessory": 97,
    "armor": 99,
    "draconic_key": 0.03,
    "angelic_key": 0.03,
}

ASSET_PATHS = {
    "prefixes": "assets/items/pref.txt",
    "weapons": "assets/items/wep.txt",
    "suffixes": "assets/items/suff.txt",
    "accessories": "assets/items/acc.txt",
    "armor": "assets/items/armor.txt",
    "monsters": "assets/monsters.csv",
    "exp_table": "assets/exp.json",
}