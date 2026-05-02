import random as _random
from dataclasses import dataclass
from typing import List


@dataclass
class ModifierDef:
    name: str
    pool: str          # "common" | "rare_tiered" | "rare_flat" | "boss" | "uber"
    tiers: List[float] # values per tier; single-element list for flat mods
    difficulties: List[float]
    level_gates: List[int]  # min monster.level for each tier; empty for flat/boss/uber


MODIFIER_DEFINITIONS: dict = {
    # --- Common ---
    "Empowered": ModifierDef("Empowered", "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],
        difficulties=[0.002, 0.004, 0.006, 0.008, 0.010],
        level_gates=[1, 25, 50, 75, 100]),
    "Fortified": ModifierDef("Fortified", "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],
        difficulties=[0.002, 0.004, 0.006, 0.008, 0.010],
        level_gates=[1, 25, 50, 75, 100]),
    "Titanic": ModifierDef("Titanic", "common",
        tiers=[1.50, 1.75, 2.00, 2.25, 2.50],
        difficulties=[0.001, 0.003, 0.005, 0.007, 0.009],
        level_gates=[1, 25, 50, 75, 100]),
    "Savage": ModifierDef("Savage", "common",
        tiers=[0.20, 0.25, 0.30, 0.35, 0.40],
        difficulties=[0.003, 0.005, 0.007, 0.009, 0.012],
        level_gates=[1, 25, 50, 75, 100]),
    "Lethal": ModifierDef("Lethal", "common",
        tiers=[0.05, 0.10, 0.15, 0.20, 0.25],
        difficulties=[0.001, 0.002, 0.004, 0.006, 0.007],
        level_gates=[1, 25, 50, 75, 100]),
    "Devastating": ModifierDef("Devastating", "common",
        tiers=[0.5, 0.6, 0.7, 0.8, 1.0],  # added to 2.0 base crit mult
        difficulties=[0.002, 0.004, 0.006, 0.008, 0.010],
        level_gates=[1, 25, 50, 75, 100]),
    "Keen": ModifierDef("Keen", "common",
        tiers=[5, 7, 10, 13, 15],
        difficulties=[0.002, 0.004, 0.005, 0.007, 0.009],
        level_gates=[1, 25, 50, 75, 100]),
    "Blinding": ModifierDef("Blinding", "common",
        tiers=[5, 8, 10, 12, 15],  # flat penalty subtracted from player acc_bonus
        difficulties=[0.002, 0.004, 0.006, 0.008, 0.010],
        level_gates=[1, 25, 50, 75, 100]),
    "Jinxed": ModifierDef("Jinxed", "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],
        difficulties=[0.002, 0.004, 0.006, 0.008, 0.010],
        level_gates=[1, 25, 50, 75, 100]),
    "Crushing": ModifierDef("Crushing", "common",
        tiers=[0.05, 0.06, 0.07, 0.08, 0.10],  # fraction of PDR ignored
        difficulties=[0.003, 0.005, 0.007, 0.009, 0.012],
        level_gates=[1, 25, 50, 75, 100]),
    "Searing": ModifierDef("Searing", "common",
        tiers=[0.15, 0.20, 0.25, 0.30, 0.35],  # fraction of FDR ignored
        difficulties=[0.003, 0.005, 0.007, 0.009, 0.012],
        level_gates=[1, 25, 50, 75, 100]),
    "Stalwart": ModifierDef("Stalwart", "common",
        tiers=[0.05, 0.10, 0.15, 0.20, 0.25],  # chance to nullify player damage
        difficulties=[0.001, 0.003, 0.005, 0.007, 0.008],
        level_gates=[1, 25, 50, 75, 100]),
    "Ironclad": ModifierDef("Ironclad", "common",
        tiers=[0.10, 0.15, 0.20, 0.25, 0.30],
        difficulties=[0.002, 0.005, 0.007, 0.009, 0.012],
        level_gates=[1, 25, 50, 75, 100]),
    "Vampiric": ModifierDef("Vampiric", "common",
        tiers=[0.02, 0.04, 0.06, 0.08, 0.10],  # fraction of monster max_hp healed per hit
        difficulties=[0.002, 0.004, 0.006, 0.008, 0.010],
        level_gates=[1, 25, 50, 75, 100]),
    "Mending": ModifierDef("Mending", "common",
        tiers=[0.01, 0.02, 0.03, 0.04, 0.05],  # fraction of monster max_hp per every other turn
        difficulties=[0.002, 0.004, 0.006, 0.007, 0.009],
        level_gates=[1, 25, 50, 75, 100]),
    "Thorned": ModifierDef("Thorned", "common",
        tiers=[0.01, 0.02, 0.03, 0.04, 0.05],  # fraction of monster max_hp dealt to player per hit
        difficulties=[0.003, 0.006, 0.009, 0.012, 0.015],
        level_gates=[1, 25, 50, 75, 100]),
    "Venomous": ModifierDef("Venomous", "common",
        tiers=[0.01, 0.02, 0.03, 0.04, 0.05],  # fraction of monster max_hp dealt to player per miss
        difficulties=[0.002, 0.004, 0.006, 0.008, 0.010],
        level_gates=[1, 25, 50, 75, 100]),
    "Enraged": ModifierDef("Enraged", "common",
        tiers=[0.05, 0.10, 0.15, 0.20, 0.25],  # attack % per stack (1 stack per 25% HP lost)
        difficulties=[0.002, 0.004, 0.006, 0.009, 0.012],
        level_gates=[1, 25, 50, 75, 100]),
    "Parching": ModifierDef("Parching", "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],  # fraction of base healing removed
        difficulties=[0.001, 0.002, 0.004, 0.006, 0.008],
        level_gates=[1, 25, 50, 75, 100]),
    "Veiled": ModifierDef("Veiled", "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],  # fraction of monster max_hp as starting ward
        difficulties=[0.001, 0.002, 0.004, 0.006, 0.008],
        level_gates=[1, 25, 50, 75, 100]),
    # Ascended is handled separately in generation (special rule)

    # --- Rare tiered ---
    "Commanding": ModifierDef("Commanding", "rare_tiered",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],
        difficulties=[0.005, 0.008, 0.010, 0.013, 0.015],
        level_gates=[1, 25, 50, 75, 100]),
    "Dampening": ModifierDef("Dampening", "rare_tiered",
        tiers=[5, 10, 15, 20, 25],  # subtracted from effective crit_chance
        difficulties=[0.003, 0.005, 0.008, 0.010, 0.013],
        level_gates=[1, 25, 50, 75, 100]),
    "Nullifying": ModifierDef("Nullifying", "rare_tiered",
        tiers=[0.30, 0.40, 0.50, 0.60, 0.70],  # fraction of crit damage removed
        difficulties=[0.005, 0.008, 0.010, 0.013, 0.015],
        level_gates=[1, 25, 50, 75, 100]),

    # --- Rare flat ---
    "Unblockable": ModifierDef("Unblockable", "rare_flat",
        tiers=[0.20], difficulties=[0.008], level_gates=[]),
    "Unavoidable": ModifierDef("Unavoidable", "rare_flat",
        tiers=[0.20], difficulties=[0.008], level_gates=[]),
    "Dispelling": ModifierDef("Dispelling", "rare_flat",
        tiers=[0.80], difficulties=[0.010], level_gates=[]),
    "Multistrike": ModifierDef("Multistrike", "rare_flat",
        tiers=[0.50], difficulties=[0.012], level_gates=[]),
    "Spectral": ModifierDef("Spectral", "rare_flat",
        tiers=[0.20], difficulties=[0.010], level_gates=[]),
    "Executioner": ModifierDef("Executioner", "rare_flat",
        tiers=[0.90], difficulties=[0.015], level_gates=[]),
    "Time Lord": ModifierDef("Time Lord", "rare_flat",
        tiers=[0.80], difficulties=[0.015], level_gates=[]),

    # --- Boss flat ---
    "Overwhelming": ModifierDef("Overwhelming", "boss",
        tiers=[2.0], difficulties=[0.0], level_gates=[]),
    "Inevitable": ModifierDef("Inevitable", "boss",
        tiers=[0.50], difficulties=[0.0], level_gates=[]),
    "Sundering": ModifierDef("Sundering", "boss",
        tiers=[0.25], difficulties=[0.0], level_gates=[]),
    "Unerring": ModifierDef("Unerring", "boss",
        tiers=[0.0], difficulties=[0.0], level_gates=[]),

    # --- Uber (hardcoded, not rolled) ---
    "Radiant Protection": ModifierDef("Radiant Protection", "uber",
        tiers=[0.60], difficulties=[0.0], level_gates=[]),
    "Infernal Protection": ModifierDef("Infernal Protection", "uber",
        tiers=[0.60], difficulties=[0.0], level_gates=[]),
    "Balanced Protection": ModifierDef("Balanced Protection", "uber",
        tiers=[0.60], difficulties=[0.0], level_gates=[]),
    "Void Protection": ModifierDef("Void Protection", "uber",
        tiers=[0.60], difficulties=[0.0], level_gates=[]),
    "Hell's Fury": ModifierDef("Hell's Fury", "uber",
        tiers=[3.0], difficulties=[0.0], level_gates=[]),
    "Void Aura": ModifierDef("Void Aura", "uber",
        tiers=[0.05], difficulties=[0.0], level_gates=[]),
    "Balanced Strikes": ModifierDef("Balanced Strikes", "uber",
        tiers=[0.50], difficulties=[0.0], level_gates=[]),
}

COMMON_MOD_NAMES = [k for k, v in MODIFIER_DEFINITIONS.items() if v.pool == "common"]
RARE_TIERED_MOD_NAMES = [k for k, v in MODIFIER_DEFINITIONS.items() if v.pool == "rare_tiered"]
RARE_FLAT_MOD_NAMES = [k for k, v in MODIFIER_DEFINITIONS.items() if v.pool == "rare_flat"]
BOSS_MOD_NAMES = [k for k, v in MODIFIER_DEFINITIONS.items() if v.pool == "boss"]


def roll_tier(monster_level: int, mod_def: ModifierDef) -> int:
    """Returns a 1-based tier index for a tiered modifier given monster.level.

    Only tiers whose level gate is met are eligible. Among eligible tiers,
    weight is linearly biased toward higher tiers based on how far
    monster.level exceeds the gate.
    """
    gates = mod_def.level_gates
    eligible = [i for i, gate in enumerate(gates) if monster_level >= gate]
    if not eligible:
        eligible = [0]  # fallback to T1

    weights = []
    for i in eligible:
        excess = max(0, monster_level - gates[i])
        weights.append(1 + excess // 10)  # +1 weight per 10 levels above gate

    chosen_idx = _random.choices(eligible, weights=weights, k=1)[0]
    return chosen_idx + 1  # 1-based tier


def make_modifier(name: str, monster_level: int, force_max_tier: bool = False) -> "MonsterModifier":
    """Construct a MonsterModifier from a name and monster level."""
    from core.models import MonsterModifier
    # Ascended: special rule — value is level_added, display is "Ascended +N"
    if name == "Ascended":
        level_added = min(20, max(1, monster_level // 10))
        return MonsterModifier(name=name, tier=0, value=float(level_added), difficulty=level_added * 0.0005)
    defn = MODIFIER_DEFINITIONS[name]
    if defn.pool in ("rare_flat", "boss", "uber"):
        tier = 0
        value = defn.tiers[0]
        difficulty = defn.difficulties[0]
    elif force_max_tier:
        tier = len(defn.tiers)
        value = defn.tiers[-1]
        difficulty = defn.difficulties[-1]
    else:
        tier = roll_tier(monster_level, defn)
        value = defn.tiers[tier - 1]
        difficulty = defn.difficulties[tier - 1]
    return MonsterModifier(name=name, tier=tier, value=value, difficulty=difficulty)
