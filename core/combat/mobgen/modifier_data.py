import random as _random
from dataclasses import dataclass, field
from typing import Callable, List

from core.models import MonsterModifier


@dataclass
class ModifierDef:
    name: str
    pool: str  # "common" | "rare_tiered" | "rare_flat" | "boss" | "uber"
    tiers: List[float]  # values per tier; single-element list for flat mods
    difficulties: List[float]
    level_gates: List[int]  # min monster.level for each tier; empty for flat/boss/uber
    description: Callable[[float], str] = field(default=lambda v: "", repr=False)


MODIFIER_DEFINITIONS: dict = {
    # --- Common ---
    "Empowered": ModifierDef(
        "Empowered",
        "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: +{int(v * 100)}% ATK",
    ),
    "Fortified": ModifierDef(
        "Fortified",
        "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: +{int(v * 100)}% DEF",
    ),
    "Titanic": ModifierDef(
        "Titanic",
        "common",
        tiers=[1.50, 1.75, 2.00, 2.25, 2.50],
        difficulties=[0.0056, 0.0168, 0.028, 0.0392, 0.0504],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: +{int((v - 1) * 100)}% Max HP",
    ),
    "Savage": ModifierDef(
        "Savage",
        "common",
        tiers=[0.20, 0.25, 0.30, 0.35, 0.40],
        difficulties=[0.0168, 0.028, 0.0392, 0.0504, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: +{int(v * 100)}% damage",
    ),
    "Lethal": ModifierDef(
        "Lethal",
        "common",
        tiers=[0.05, 0.10, 0.15, 0.20, 0.25],
        difficulties=[0.0056, 0.0112, 0.0224, 0.0336, 0.0392],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: +{int(v * 100)}% Crit Chance",
    ),
    "Devastating": ModifierDef(
        "Devastating",
        "common",
        tiers=[0.5, 0.6, 0.7, 0.8, 1.0],  # added to 2.0 base crit mult
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: Crits deal {round(1.5 + v, 1)}× damage",
    ),
    "Keen": ModifierDef(
        "Keen",
        "common",
        tiers=[5, 7, 10, 13, 15],
        difficulties=[0.0112, 0.0224, 0.028, 0.0392, 0.0504],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: +{int(v)} to its hit rolls",
    ),
    "Blinding": ModifierDef(
        "Blinding",
        "common",
        tiers=[5, 8, 10, 12, 15],  # flat penalty subtracted from player acc_bonus
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: −{int(v)} to your hit rolls",
    ),
    "Jinxed": ModifierDef(
        "Jinxed",
        "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: {int(v * 100)}% chance your hit rolls are unlucky"
        ),
    ),
    "Crushing": ModifierDef(
        "Crushing",
        "common",
        tiers=[0.05, 0.06, 0.07, 0.08, 0.10],  # fraction of PDR ignored
        difficulties=[0.0168, 0.028, 0.0392, 0.0504, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: Ignores {int(v * 100)}% of your PDR",
    ),
    "Searing": ModifierDef(
        "Searing",
        "common",
        tiers=[0.15, 0.20, 0.25, 0.30, 0.35],  # fraction of FDR ignored
        difficulties=[0.0168, 0.028, 0.0392, 0.0504, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: Ignores {int(v * 100)}% of your FDR",
    ),
    "Stalwart": ModifierDef(
        "Stalwart",
        "common",
        tiers=[
            0.05,
            0.10,
            0.15,
            0.20,
            0.25,
        ],  # chance to nullify ALL player damage that turn
        difficulties=[0.0056, 0.0168, 0.028, 0.0392, 0.0448],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"During combat: {int(v * 100)}% chance to nullify all incoming damage"
        ),
    ),
    "Ironclad": ModifierDef(
        "Ironclad",
        "common",
        tiers=[0.10, 0.15, 0.20, 0.25, 0.30],
        difficulties=[0.0112, 0.028, 0.0392, 0.0504, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"During combat: {int(v * 100)}% less damage taken",
    ),
    "Vampiric": ModifierDef(
        "Vampiric",
        "common",
        tiers=[
            0.004,
            0.008,
            0.012,
            0.016,
            0.02,
        ],  # fraction of monster max_hp healed per hit
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"On hit: Heals {v * 100:.1f}% of its Max HP",
    ),
    "Mending": ModifierDef(
        "Mending",
        "common",
        tiers=[
            0.0025,
            0.005,
            0.0075,
            0.01,
            0.0125,
        ],  # fraction of monster max_hp per every other turn
        difficulties=[0.0224, 0.0448, 0.0504, 0.056, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Every other turn: Heals {v * 100:.2f}% of its Max HP",
    ),
    "Thorned": ModifierDef(
        "Thorned",
        "common",
        tiers=[
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
        ],  # fraction of player max_hp dealt to player per hit; applies PDR/FDR, bypasses ward
        difficulties=[0.0168, 0.0336, 0.0504, 0.0672, 0.084],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On hit: You take {int(v * 100)}% of your Max HP as damage (after PDR/FDR; bypasses Ward)"
        ),
    ),
    "Venomous": ModifierDef(
        "Venomous",
        "common",
        tiers=[
            0.004,
            0.008,
            0.012,
            0.016,
            0.020,
        ],  # fraction of player max_hp as true damage on each miss; bypasses all defences
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On miss: {v * 100:.1f}% of your Max HP as true damage (bypasses all defences)"
        ),
    ),
    "Enraged": ModifierDef(
        "Enraged",
        "common",
        tiers=[
            0.05,
            0.10,
            0.15,
            0.20,
            0.25,
        ],  # attack % per stack (1 stack per 25% HP lost, capped at 3 stacks / 75% HP lost)
        difficulties=[0.0112, 0.0224, 0.0336, 0.0504, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"During combat: +{int(v * 100)}% DMG per 25% HP lost (max 3 stacks)"
        ),
    ),
    "Parching": ModifierDef(
        "Parching",
        "common",
        tiers=[0.10, 0.20, 0.30, 0.40, 0.50],  # fraction of base healing removed
        difficulties=[0.0056, 0.0112, 0.0224, 0.0336, 0.0448],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"During combat: Your potions heal {int(v * 100)}% less",
    ),
    "Veiled": ModifierDef(
        "Veiled",
        "common",
        tiers=[
            0.10,
            0.20,
            0.30,
            0.40,
            0.50,
        ],  # fraction of monster max_hp as starting ward
        difficulties=[0.0056, 0.0112, 0.0224, 0.0336, 0.0448],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: Starts with {int(v * 100)}% Max HP as Ward"
        ),
    ),
    # --- Common (new) ---
    "Flashfire": ModifierDef(
        "Flashfire",
        "common",
        tiers=[0.02, 0.04, 0.06, 0.08, 0.10],
        difficulties=[0.0168, 0.028, 0.0392, 0.0504, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"During combat: Gains +1 charge per turn; at 8 charges: deals {int(v * 100)}% of your Max HP as true damage"
        ),
    ),
    "Hemorrhage": ModifierDef(
        "Hemorrhage",
        "common",
        tiers=[0.0015, 0.0020, 0.0028, 0.0036, 0.0045],
        difficulties=[0.0168, 0.028, 0.0392, 0.0504, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On hit: 30% chance to apply 1 Bleed stack; each stack deals {v * 100:.2f}% of your Max HP as true damage per turn"
        ),
    ),
    "Volatile Spikes": ModifierDef(
        "Volatile Spikes",
        "common",
        tiers=[0.02, 0.03, 0.04, 0.05, 0.06],
        difficulties=[0.0168, 0.028, 0.0392, 0.0504, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On hit: 30% chance to apply 1 Spike (max 10, +{int(v * 100)}% monster Crit Chance per stack); evade or block resets stacks"
        ),
    ),
    "Onslaught": ModifierDef(
        "Onslaught",
        "common",
        tiers=[0.015, 0.020, 0.030, 0.040, 0.050],
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"During combat: +{int(v * 100)}% ATK per consecutive hit; resets on evade or block"
        ),
    ),
    "Pressure Surge": ModifierDef(
        "Pressure Surge",
        "common",
        tiers=[0.10, 0.125, 0.15, 0.175, 0.20],
        difficulties=[0.0224, 0.0336, 0.0448, 0.056, 0.0728],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"During combat: Builds when you don't crit; at 10 stacks: deals {int(v * 100)}% of your Max HP as true damage"
        ),
    ),
    "Soul Siphon": ModifierDef(
        "Soul Siphon",
        "common",
        tiers=[0.05, 0.08, 0.12, 0.16, 0.20],
        difficulties=[0.0168, 0.028, 0.0392, 0.0504, 0.0616],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Every 2 turns: Drains {int(v * 100)}% of your Ward and heals 50% of the amount drained"
        ),
    ),
    "Frenzied Hunger": ModifierDef(
        "Frenzied Hunger",
        "common",
        tiers=[0.05, 0.08, 0.12, 0.16, 0.20],
        difficulties=[0.0112, 0.0224, 0.0336, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"On potion use: +{int(v * 100)}% ATK (stacking)",
    ),
    # Ascended is handled separately in generation (special rule)
    # --- Rare tiered ---
    "Commanding": ModifierDef(
        "Commanding",
        "rare_tiered",
        tiers=[0.035, 0.045, 0.055, 0.065, 0.075],
        difficulties=[0.0130, 0.0168, 0.0206, 0.0243, 0.0280],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On hit: Minions deal {v * 100:.1f}% of damage applied to you as true damage (bypasses all layers)"
        ),
    ),
    "Minion Army": ModifierDef(
        "Minion Army",
        "boss",
        tiers=[0.11, 0.12, 0.13, 0.14, 0.15],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On hit: Minions deal {int(v * 100)}% of damage applied to you as true damage (bypasses all layers)"
        ),
    ),
    "Dampening": ModifierDef(
        "Dampening",
        "rare_tiered",
        tiers=[5, 10, 15, 20, 25],  # subtracted from effective crit_chance
        difficulties=[0.0168, 0.028, 0.0448, 0.056, 0.0728],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"Combat start: Your Crit Chance −{int(v)}",
    ),
    "Nullifying": ModifierDef(
        "Nullifying",
        "rare_tiered",
        tiers=[0.30, 0.40, 0.50, 0.60, 0.70],  # fraction of crit damage removed
        difficulties=[0.028, 0.0448, 0.056, 0.0728, 0.084],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: Your crits deal {int(v * 100)}% less damage"
        ),
    ),
    # --- Rare tiered (formerly rare_flat) ---
    "Unblockable": ModifierDef(
        "Unblockable",
        "rare_tiered",
        tiers=[0.36, 0.28, 0.24, 0.20, 0.16],
        difficulties=[0.0224, 0.0336, 0.0448, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: Block Chance is {int((1 - v) * 100)}% less effective"
        ),
    ),
    "Unavoidable": ModifierDef(
        "Unavoidable",
        "rare_tiered",
        tiers=[0.36, 0.28, 0.24, 0.20, 0.16],
        difficulties=[0.0224, 0.0336, 0.0448, 0.0448, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: Evasion Chance is {int((1 - v) * 100)}% less effective"
        ),
    ),
    "Dispelling": ModifierDef(
        "Dispelling",
        "rare_tiered",
        tiers=[0.50, 0.60, 0.70, 0.80, 0.90],
        difficulties=[0.028, 0.0392, 0.0448, 0.056, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: Your starting Ward is reduced by {int(v * 100)}%"
        ),
    ),
    "Multistrike": ModifierDef(
        "Multistrike",
        "rare_tiered",
        tiers=[0.20, 0.30, 0.40, 0.50, 0.60],
        difficulties=[0.0336, 0.0448, 0.056, 0.0672, 0.0784],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On hit: {int(v * 100)}% chance to strike twice (second hit at 50% damage, after PDR/FDR)"
        ),
    ),
    "Spectral": ModifierDef(
        "Spectral",
        "rare_tiered",
        tiers=[0.50, 0.75, 1.00, 1.25, 1.50],
        difficulties=[0.028, 0.0392, 0.0504, 0.056, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On hit: 20% chance to deal {int(v * 100)}% increased damage"
        ),
    ),
    "Executioner": ModifierDef(
        "Executioner",
        "rare_tiered",
        tiers=[0.70, 0.75, 0.80, 0.85, 0.90],
        difficulties=[0.0392, 0.0504, 0.0616, 0.0728, 0.084],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On hit: 1% chance to deal {int(v * 100)}% of your current HP as true damage (can be evaded or blocked)"
        ),
    ),
    "Time Lord": ModifierDef(
        "Time Lord",
        "rare_tiered",
        tiers=[0.80, 0.81, 0.82, 0.83, 0.84],
        difficulties=[0.0392, 0.0504, 0.0616, 0.0728, 0.084],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"On lethal hit: {int(v * 100)}% chance to survive at 1 HP"
        ),
    ),
    "Corrosion": ModifierDef(
        "Corrosion",
        "rare_tiered",
        tiers=[7.0, 6.0, 5.0, 4.0, 3.0],
        difficulties=[0.028, 0.0392, 0.0448, 0.0504, 0.056],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Every {int(v)} turns: Gains a Corrode stack (max 5; each stack −3 your PDR)"
        ),
    ),
    "Death Rattle": ModifierDef(
        "Death Rattle",
        "rare_tiered",
        tiers=[0.10, 0.15, 0.20, 0.25, 0.30],
        difficulties=[0.0336, 0.0448, 0.056, 0.0616, 0.0672],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Below 25% HP: Starts a 5-turn countdown; if it survives, heals to {int(v * 100)}% HP"
        ),
    ),
    # --- Boss tiered ---
    "Overwhelming": ModifierDef(
        "Overwhelming",
        "boss",
        tiers=[1.60, 1.70, 1.80, 1.90, 2.00],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: Deals {int((v - 1) * 100)}% increased damage; −{int((v - 1.6) * 50 + 20)} to its hit rolls"
        ),
    ),
    "Inevitable": ModifierDef(
        "Inevitable",
        "boss",
        tiers=[0.50, 0.45, 0.40, 0.35, 0.30],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: Always hits; {int((1 - v) * 100)}% less damage (applied after increased sources)"
        ),
    ),
    "Sundering": ModifierDef(
        "Sundering",
        "boss",
        tiers=[0.15, 0.20, 0.25, 0.30, 0.35],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: {int(v * 100)}% of its damage bypasses your Ward"
        ),
    ),
    "Unerring": ModifierDef(
        "Unerring",
        "boss",
        tiers=[0.40, 0.50, 0.60, 0.70, 0.80],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Combat start: {int(v * 100)}% chance its hit rolls take the highest of two"
        ),
    ),
    "Impending Doom": ModifierDef(
        "Impending Doom",
        "boss",
        tiers=[88.0, 77.0, 66.0, 55.0, 44.0],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"During combat: Each hit builds Doom; at {int(v)} stacks: instant kill"
        ),
    ),
    "Wrathful Retaliation": ModifierDef(
        "Wrathful Retaliation",
        "boss",
        tiers=[0.04, 0.05, 0.06, 0.07, 0.08],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: f"On your crit: +{int(v * 100)}% DMG (stacking)",
    ),
    "Colossus Protocol": ModifierDef(
        "Colossus Protocol",
        "boss",
        tiers=[0.20, 0.25, 0.30, 0.35, 0.40],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Below 50% HP: +{int(v * 100)}% ATK and +{int(v / 2 * 100)}% damage reduction"
        ),
    ),
    "Temporal Collapse": ModifierDef(
        "Temporal Collapse",
        "boss",
        tiers=[11.0, 10.0, 9.0, 8.0, 7.0],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"Every {int(v)} turns: Returns damage dealt this fight as true damage (capped at 15% of your Max HP)"
        ),
    ),
    "Undying Resolve": ModifierDef(
        "Undying Resolve",
        "boss",
        tiers=[0.20, 0.25, 0.30, 0.35, 0.40],
        difficulties=[0.0, 0.0, 0.0, 0.0, 0.0],
        level_gates=[20, 40, 60, 80, 100],
        description=lambda v: (
            f"First death: Revives to {int(v * 100)}% HP, immune for 2 turns, deals 100% increased damage for 2 turns"
        ),
    ),
    # --- Uber (hardcoded, not rolled) ---
    "Radiant Protection": ModifierDef(
        "Radiant Protection",
        "uber",
        tiers=[0.60],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: "Combat start: 60% damage reduction",
    ),
    "Infernal Protection": ModifierDef(
        "Infernal Protection",
        "uber",
        tiers=[0.60],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: "Combat start: 60% damage reduction",
    ),
    "Balanced Protection": ModifierDef(
        "Balanced Protection",
        "uber",
        tiers=[0.60],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: "Combat start: 60% damage reduction",
    ),
    "Void Protection": ModifierDef(
        "Void Protection",
        "uber",
        tiers=[0.60],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: "Combat start: 60% damage reduction",
    ),
    "Hell's Fury": ModifierDef(
        "Hell's Fury",
        "uber",
        tiers=[3.0],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: "Combat start: Deals 200% increased damage",
    ),
    "Void Aura": ModifierDef(
        "Void Aura",
        "uber",
        tiers=[0.05],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: "Each round: Drains 0.5% of your ATK and DEF",
    ),
    "Balanced Strikes": ModifierDef(
        "Balanced Strikes",
        "uber",
        tiers=[0.50],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: "Every even turn: Deals 50% damage, bypassing Ward",
    ),
    "Corrupted Protection": ModifierDef(
        "Corrupted Protection",
        "uber",
        tiers=[0.60],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: "Combat start: 60% damage reduction",
    ),
    "Origin of Corruption": ModifierDef(
        "Origin of Corruption",
        "uber",
        tiers=[0.0],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: (
            "Every 3 turns: Drains 10% of your Ward, healing for 10× the amount"
        ),
    ),
    # --- Prestige Gathering Boss Modifiers (unrollable "uber" style, for Artisan Mastery capstones) ---
    "Meridian Golem DR": ModifierDef(
        "Meridian Golem DR",
        "uber",
        tiers=[0.15],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: (
            "This ancient construct has +15% additional Physical Damage Reduction"
        ),
    ),
    "Leviathan Bite": ModifierDef(
        "Leviathan Bite",
        "uber",
        tiers=[0.01],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: (
            "50% chance per turn: Deals 1% of your Max HP as true damage"
        ),
    ),
    "Verdant Snare": ModifierDef(
        "Verdant Snare",
        "uber",
        tiers=[0.10],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: (
            "10% chance per turn to snare you, preventing your action until freed"
        ),
    ),
    # --- The Rite of Convergence (unrollable "uber" style, one per reborn wing) ---
    "Unbreakable": ModifierDef(
        "Unbreakable",
        "uber",
        tiers=[150],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: (
            f"Gains 1 charge per turn; at {int(v)} charges, deals your full HP + "
            "Ward as true damage (guaranteed kill unless an Undying effect saves you)"
        ),
    ),
    "Judgment": ModifierDef(
        "Judgment",
        "uber",
        tiers=[50],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: (
            f"Gains 1 charge whenever you take damage; at {int(v)} charges, deals "
            "99% of your full HP + Ward as true damage"
        ),
    ),
    "True Reckoning": ModifierDef(
        "True Reckoning",
        "uber",
        tiers=[0.80],
        difficulties=[0.0],
        level_gates=[],
        description=lambda v: (
            f"{int(v * 100)}% of each hit is unconditionally true damage, "
            "bypassing PDR, FDR, and Ward"
        ),
    ),
}

COMMON_MOD_NAMES = [k for k, v in MODIFIER_DEFINITIONS.items() if v.pool == "common"]
RARE_TIERED_MOD_NAMES = [
    k for k, v in MODIFIER_DEFINITIONS.items() if v.pool == "rare_tiered"
]
RARE_FLAT_MOD_NAMES = [
    k for k, v in MODIFIER_DEFINITIONS.items() if v.pool == "rare_flat"
]
BOSS_MOD_NAMES = [k for k, v in MODIFIER_DEFINITIONS.items() if v.pool == "boss"]

_TIER_NUMERALS = ["I", "II", "III", "IV", "V"]


def omnipotent_label(tier: int, name: str = "Omnipotent") -> str:
    """Display label for a monster carrying an entire modifier pool at one
    uniform tier — see Monster.omnipotent_display. Used instead of listing
    every individual modifier name (all-corrupted-mods monsters, the Rite of
    Convergence's Amalgam/Arbiter phases)."""
    idx = max(1, min(tier, len(_TIER_NUMERALS))) - 1
    return f"{name} {_TIER_NUMERALS[idx]}"


def roll_tier(monster_level: int, mod_def: ModifierDef) -> int:
    """Returns a 1-based tier index for a tiered modifier given monster.level.

    Only tiers whose level gate is met are eligible. The highest eligible tier
    is weighted to grow further past the pack the deeper monster.level exceeds
    its own gate, so it comes to dominate at high levels; every other eligible
    tier keeps a flat baseline weight so lower rolls stay possible but don't
    scale up. (Weighting excess off each tier's own gate — the previous
    approach — always favored T1 the furthest, since its gate is the lowest
    and therefore accumulates the largest excess as monster.level grows.)
    """
    gates = mod_def.level_gates
    if not gates:
        return 1  # no level gates defined — always T1
    eligible = [i for i, gate in enumerate(gates) if monster_level >= gate]
    if not eligible:
        eligible = [0]  # fallback to T1

    top = eligible[-1]
    top_excess = max(0, monster_level - gates[top])

    weights = [3 + top_excess // 10 if i == top else 1 for i in eligible]

    chosen_idx = _random.choices(eligible, weights=weights, k=1)[0]
    return chosen_idx + 1  # 1-based tier


def make_modifier(
    name: str,
    monster_level: int,
    force_max_tier: bool = False,
    force_max_eligible_tier: bool = False,
    force_tier: int | None = None,
) -> "MonsterModifier":
    """Construct a MonsterModifier from a name and monster level.

    force_max_tier           — always T5 (used for uber/ascent/incubated).
    force_max_eligible_tier  — highest tier whose level_gate the monster meets
                               (used for regular bosses so their modifiers
                               are as strong as possible without exceeding the
                               level bracket the player is actually fighting in).
    """

    # Ascended: special rule — value is level_added, display is "Ascended +N"
    if name == "Ascended":
        level_added = min(20, max(1, monster_level // 10))
        return MonsterModifier(
            name=name, tier=0, value=float(level_added), difficulty=level_added * 0.0005
        )
    defn = MODIFIER_DEFINITIONS[name]
    if defn.pool == "uber":
        tier = 0
        value = defn.tiers[0]
        difficulty = defn.difficulties[0]
    elif force_tier is not None:
        tier = max(1, min(force_tier, len(defn.tiers)))
        value = defn.tiers[tier - 1]
        difficulty = defn.difficulties[tier - 1]
    elif force_max_tier:
        tier = len(defn.tiers)
        value = defn.tiers[-1]
        difficulty = defn.difficulties[-1]
    elif force_max_eligible_tier:
        gates = defn.level_gates
        eligible = [i for i, gate in enumerate(gates) if monster_level >= gate]
        chosen_idx = max(eligible) if eligible else 0
        tier = chosen_idx + 1
        value = defn.tiers[chosen_idx]
        difficulty = defn.difficulties[chosen_idx]
    else:
        tier = roll_tier(monster_level, defn)
        value = defn.tiers[tier - 1]
        difficulty = defn.difficulties[tier - 1]
    return MonsterModifier(name=name, tier=tier, value=value, difficulty=difficulty)
