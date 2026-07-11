"""
Static definitions for Skill Jewels and Paradise Passives.
All values here are source-of-truth; nothing is hardcoded elsewhere.
"""

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Skill Jewels
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillJewelDef:
    key: str
    name: str
    description_short: str
    # charge trigger description
    charge_trigger: str
    # threshold at level 1, level 20, level 30+
    threshold_lv1: int
    threshold_lv20: int
    threshold_lv30: int
    # unleash description template (use {low}, {high} for damage range)
    unleash_template_lv1: str
    unleash_template_lv20: str
    unleash_template_lv30: str
    emoji: str = "💎"


SKILL_JEWELS: dict[str, SkillJewelDef] = {
    "surge": SkillJewelDef(
        key="surge",
        name="Surge",
        description_short="Lightning storm on repeated hits.",
        charge_trigger="Gain +1 charge on each successful hit.",
        threshold_lv1=16,
        threshold_lv20=10,
        threshold_lv30=8,
        unleash_template_lv1="Lightning storm deals **5–8%** of total ATK as bonus damage.",
        unleash_template_lv20="Lightning storm deals **100–180%** of total ATK as bonus damage.",
        unleash_template_lv30="Lightning storm deals **200–380%** of total ATK as bonus damage.",
        emoji="⚡",
    ),
    "cataclysm": SkillJewelDef(
        key="cataclysm",
        name="Cataclysm",
        description_short="Prime a devastating guaranteed critical strike.",
        charge_trigger="Gain +1 charge on each critical hit.",
        threshold_lv1=12,
        threshold_lv20=8,
        threshold_lv30=5,
        unleash_template_lv1="Next attack is a guaranteed crit with **+50%** bonus crit multiplier.",
        unleash_template_lv20="Next attack is a guaranteed crit with **+150%** bonus crit multiplier.",
        unleash_template_lv30="Next attack is a guaranteed crit with **+250%** bonus crit multiplier.",
        emoji="💥",
    ),
    "acrimony": SkillJewelDef(
        key="acrimony",
        name="Acrimony",
        description_short="Venom burst that poisons on miss.",
        charge_trigger="Gain +1 charge on each missed attack.",
        threshold_lv1=18,
        threshold_lv20=12,
        threshold_lv30=9,
        unleash_template_lv1="Venom burst deals **40–80%** total ATK + 25% of that as DoT for 4 turns.",
        unleash_template_lv20="Venom burst deals **150–250%** total ATK + 25% of that as DoT for 4 turns.",
        unleash_template_lv30="Venom burst deals **300–450%** total ATK + 25% of that as DoT for 4 turns.",
        emoji="🐍",
    ),
    "wardforge": SkillJewelDef(
        key="wardforge",
        name="Wardforge",
        description_short="Ward burst and damage on ward generation.",
        charge_trigger="Gain +1 charge whenever ward is generated from any source.",
        threshold_lv1=25,
        threshold_lv20=15,
        threshold_lv30=10,
        unleash_template_lv1="Generate **80–150** bonus ward; next attack gains 30% of current ward as bonus damage.",
        unleash_template_lv20="Generate **400–700** bonus ward; next attack gains 30% of current ward as bonus damage.",
        unleash_template_lv30="Generate **800–1200** bonus ward; next attack gains 30% of current ward as bonus damage.",
        emoji="🛡️",
    ),
    "bastion": SkillJewelDef(
        key="bastion",
        name="Bastion",
        description_short="Reflect incoming damage back at the monster.",
        charge_trigger="Gain +1 charge every time you take HP damage.",
        threshold_lv1=12,
        threshold_lv20=9,
        threshold_lv30=5,
        unleash_template_lv1="Reflect **200–400%** of the triggering hit back at the monster.",
        unleash_template_lv20="Reflect **600–1000%** of the triggering hit back at the monster.",
        unleash_template_lv30="Reflect **1200–1800%** of the triggering hit back at the monster.",
        emoji="🔱",
    ),
    "siphon": SkillJewelDef(
        key="siphon",
        name="Siphon",
        description_short="Burst heal converting HP to ward.",
        charge_trigger="Gain +1 charge whenever HP is regenerated (leech, partner heal, alchemy).",
        threshold_lv1=20,
        threshold_lv20=15,
        threshold_lv30=10,
        unleash_template_lv1="Burst heal **30–60%** of max HP; 50% of heal becomes ward.",
        unleash_template_lv20="Burst heal **40–80%** of max HP; 50% of heal becomes ward.",
        unleash_template_lv30="Burst heal **50–100%** of max HP; 50% of heal becomes ward.",
        emoji="💚",
    ),
    "onslaught": SkillJewelDef(
        key="onslaught",
        name="Onslaught",
        description_short="Massive ATK boost at low HP.",
        charge_trigger="Gain +1 charge each turn while HP is below 50%.",
        threshold_lv1=12,
        threshold_lv20=8,
        threshold_lv30=5,
        unleash_template_lv1="Next attack gains **+60–120%** ATK multiplier.",
        unleash_template_lv20="Next attack gains **+200–350%** ATK multiplier.",
        unleash_template_lv30="Next attack gains **+400–600%** ATK multiplier.",
        emoji="🔥",
    ),
    "draught": SkillJewelDef(
        key="draught",
        name="Draught",
        description_short="Distill potions from combat rhythm.",
        charge_trigger="Gain +1 charge each time a potion is used.",
        threshold_lv1=6,
        threshold_lv20=3,
        threshold_lv30=1,
        unleash_template_lv1="Generates **0–1** potions (overflow converts to ward).",
        unleash_template_lv20="Generates **0–2** potions (overflow converts to ward).",
        unleash_template_lv30="Generates **0–3** potions (overflow converts to ward).",
        emoji="🧪",
    ),
}


# ---------------------------------------------------------------------------
# Passive Definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PassiveDef:
    key: str
    name: str
    description_template: str  # use {value} for the rolled number
    min_value: float
    max_value: float
    is_percent: bool = True  # whether {value} should be shown as %
    skill_specific: Optional[str] = None  # if set, only applies to this skill key


PASSIVES: dict[str, PassiveDef] = {
    # Charge Manipulation
    "rapid": PassiveDef(
        key="rapid",
        name="Rapid",
        description_template="+{value}% chance to gain +1 extra charge on any trigger.",
        min_value=12.0,
        max_value=40.0,
    ),
    "compression": PassiveDef(
        key="compression",
        name="Compression",
        description_template="-{value} to all skill jewel thresholds (floor 1).",
        min_value=1.0,
        max_value=4.0,
        is_percent=False,
    ),
    # Unleash Power
    "force": PassiveDef(
        key="force",
        name="Force",
        description_template="+{value}% to all unleash effect strength.",
        min_value=15.0,
        max_value=70.0,
    ),
    "mirage": PassiveDef(
        key="mirage",
        name="Mirage",
        description_template="{value}% chance any unleash triggers twice.",
        min_value=6.0,
        max_value=24.0,
    ),
    "lingering": PassiveDef(
        key="lingering",
        name="Lingering",
        description_template="{value}% chance to keep 1–5 charges after unleash.",
        min_value=15.0,
        max_value=50.0,
    ),
    # Progression & Mastery
    "savant": PassiveDef(
        key="savant",
        name="Savant",
        description_template="+{value}% faster skill jewel leveling.",
        min_value=15.0,
        max_value=60.0,
    ),
    "mastery": PassiveDef(
        key="mastery",
        name="Mastery",
        description_template="+{value} bonus levels to all skill jewels.",
        min_value=1.0,
        max_value=4.0,
        is_percent=False,
    ),
    # Specific Synergies
    "fury": PassiveDef(
        key="fury",
        name="Fury",
        description_template="+{value}% damage on damage-dealing unleashes.",
        min_value=6.0,
        max_value=25.0,
    ),
    "arcane": PassiveDef(
        key="arcane",
        name="Arcane",
        description_template="+{value}% ward generated by jewel effects.",
        min_value=12.0,
        max_value=45.0,
    ),
    "sustenance": PassiveDef(
        key="sustenance",
        name="Sustenance",
        description_template="+{value}% healing from jewel effects.",
        min_value=15.0,
        max_value=55.0,
    ),
    # Utility
    "fortune": PassiveDef(
        key="fortune",
        name="Fortune",
        description_template="{value}% chance to duplicate Paradise Jewels found.",
        min_value=1.0,
        max_value=5.0,
    ),
    # Skill Specialization (rare) — one entry per skill
    "spec_surge": PassiveDef(
        key="spec_surge",
        name="Surge Specialization",
        description_template="+{value}% power to Surge.",
        min_value=20.0,
        max_value=60.0,
        skill_specific="surge",
    ),
    "spec_cataclysm": PassiveDef(
        key="spec_cataclysm",
        name="Cataclysm Specialization",
        description_template="+{value}% power to Cataclysm.",
        min_value=20.0,
        max_value=60.0,
        skill_specific="cataclysm",
    ),
    "spec_acrimony": PassiveDef(
        key="spec_acrimony",
        name="Acrimony Specialization",
        description_template="+{value}% power to Acrimony.",
        min_value=20.0,
        max_value=60.0,
        skill_specific="acrimony",
    ),
    "spec_wardforge": PassiveDef(
        key="spec_wardforge",
        name="Wardforge Specialization",
        description_template="+{value}% power to Wardforge.",
        min_value=20.0,
        max_value=60.0,
        skill_specific="wardforge",
    ),
    "spec_bastion": PassiveDef(
        key="spec_bastion",
        name="Bastion Specialization",
        description_template="+{value}% power to Bastion.",
        min_value=20.0,
        max_value=60.0,
        skill_specific="bastion",
    ),
    "spec_siphon": PassiveDef(
        key="spec_siphon",
        name="Siphon Specialization",
        description_template="+{value}% power to Siphon.",
        min_value=20.0,
        max_value=60.0,
        skill_specific="siphon",
    ),
    "spec_onslaught": PassiveDef(
        key="spec_onslaught",
        name="Onslaught Specialization",
        description_template="+{value}% power to Onslaught.",
        min_value=20.0,
        max_value=60.0,
        skill_specific="onslaught",
    ),
    "spec_draught": PassiveDef(
        key="spec_draught",
        name="Draught Specialization",
        description_template="+{value}% power to Draught.",
        min_value=20.0,
        max_value=60.0,
        skill_specific="draught",
    ),
}

# Passives available in the general roll pool (excludes skill specializations)
GENERAL_PASSIVE_KEYS: list[str] = [
    "rapid",
    "compression",
    "force",
    "mirage",
    "lingering",
    "savant",
    "mastery",
    "fury",
    "arcane",
    "sustenance",
    "fortune",
]
SPEC_PASSIVE_KEYS: list[str] = [k for k in PASSIVES if k.startswith("spec_")]

# Weighted pool: specs are "rare" — appear at 1/4 the rate of general passives
REROLL_TYPE_POOL: list[str] = GENERAL_PASSIVE_KEYS * 4 + SPEC_PASSIVE_KEYS

# Passive slot unlock thresholds per slot index (0-indexed)
PASSIVE_SLOT_THRESHOLDS: list[int] = [1, 4, 9, 19, 34]

# Cosmic Dust costs
DUST_REROLL_TYPE = 12_000
DUST_REROLL_VALUE = 8_000
DUST_FROM_JEWEL_BASE = 8_000


# ---------------------------------------------------------------------------
# Corruption Engram (Evelynn) — per-skill etch effects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngramEffectDef:
    key: str
    kind: str  # "level" | "threshold" | "double_proc"
    value: float
    description: str


# Equal weighting — one entry chosen at random per etch, ~9.1% chance each.
CORRUPTION_ENGRAM_EFFECTS: list[EngramEffectDef] = [
    EngramEffectDef("level_1", "level", 1, "+1 to skill level"),
    EngramEffectDef("level_2", "level", 2, "+2 to skill level"),
    EngramEffectDef("level_3", "level", 3, "+3 to skill level"),
    EngramEffectDef("level_4", "level", 4, "+4 to skill level"),
    EngramEffectDef("level_5", "level", 5, "+5 to skill level"),
    EngramEffectDef("threshold_1", "threshold", 1, "-1 to Charge Threshold"),
    EngramEffectDef("threshold_2", "threshold", 2, "-2 to Charge Threshold"),
    EngramEffectDef("threshold_3", "threshold", 3, "-3 to Charge Threshold"),
    EngramEffectDef(
        "double_5", "double_proc", 5, "+5% chance for unleash to trigger twice"
    ),
    EngramEffectDef(
        "double_10", "double_proc", 10, "+10% chance for unleash to trigger twice"
    ),
    EngramEffectDef(
        "double_15", "double_proc", 15, "+15% chance for unleash to trigger twice"
    ),
]

CORRUPTION_ENGRAM_GOLD_COST = 25_000_000
