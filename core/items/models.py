"""
core/items/models.py — Equipment and companion dataclasses.

Canonical home for all item-slot models (Weapon, Armor, Accessory, Glove, Boot,
Helmet), companion/tome models, and monster-part models.  No project-level
imports at module load time — safe to import from anywhere without circular risk.
"""

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Equipment models
# ---------------------------------------------------------------------------


@dataclass
class Weapon:
    user: str
    name: str
    level: int
    attack: int
    defence: int
    rarity: int
    passive: str
    description: str
    p_passive: str
    u_passive: str
    item_id: Optional[int] = None
    is_equipped: bool = False
    forges_remaining: int = 0
    refines_remaining: int = 0
    refinement_lvl: int = 0
    infernal_passive: str = "none"
    forge_tier: int = 0
    hit_chance: float = 0.60
    crit_chance: float = 0.00
    crit_multi: float = 2.00
    base_rarity: int = 3


@dataclass
class Accessory:
    user: str
    name: str
    level: int
    attack: int
    defence: int
    rarity: int
    ward: int
    crit: int
    passive: str
    passive_lvl: int
    description: str
    item_id: Optional[int] = None
    is_equipped: bool = False
    potential_remaining: int = 0
    void_passive: str = "none"


@dataclass
class Armor:
    user: str
    name: str
    level: int
    block: int
    evasion: int
    ward: int
    pdr: int
    fdr: int
    passive: str
    description: str
    item_id: Optional[int] = None
    is_equipped: bool = False
    temper_remaining: int = 0
    imbue_remaining: int = 0
    celestial_passive: str = "none"
    main_stat_type: str = "def"
    main_stat: int = 0
    reinforces_remaining: int = 0
    reinforcement_lvl: int = 0


@dataclass
class Glove:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    attack: int = 0
    defence: int = 0
    ward: int = 0  # Percentage
    pdr: int = 0  # Percentage
    fdr: int = 0  # Flat
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0
    essence_1: str = "none"
    essence_1_val: float = 0.0
    essence_2: str = "none"
    essence_2_val: float = 0.0
    essence_3: str = "none"
    essence_3_val: float = 0.0
    corrupted_essence: str = "none"
    reinforces_remaining: int = 0
    reinforcement_lvl: int = 0


@dataclass
class Boot:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    attack: int = 0
    defence: int = 0
    ward: int = 0  # Percentage
    pdr: int = 0  # Percentage
    fdr: int = 0  # Flat
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0
    essence_1: str = "none"
    essence_1_val: float = 0.0
    essence_2: str = "none"
    essence_2_val: float = 0.0
    essence_3: str = "none"
    essence_3_val: float = 0.0
    corrupted_essence: str = "none"
    reinforces_remaining: int = 0
    reinforcement_lvl: int = 0


@dataclass
class Helmet:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    defence: int = 0
    ward: int = 0  # Percentage
    pdr: int = 0
    fdr: int = 0
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0
    essence_1: str = "none"
    essence_1_val: float = 0.0
    essence_2: str = "none"
    essence_2_val: float = 0.0
    essence_3: str = "none"
    essence_3_val: float = 0.0
    corrupted_essence: str = "none"
    reinforces_remaining: int = 0
    reinforcement_lvl: int = 0


# ---------------------------------------------------------------------------
# Companion model
# ---------------------------------------------------------------------------


@dataclass
class Companion:
    id: int
    user_id: str
    name: str
    species: str
    image_url: str
    level: int
    exp: int
    passive_type: str
    passive_tier: int
    is_active: bool = False
    balanced_passive: str = "none"
    balanced_passive_tier: int = 0

    @property
    def passive_value(self) -> int:
        """Calculates the numerical value based on Type and Tier."""
        if self.passive_type in ["atk", "def"]:  # Percentage
            return 4 + self.passive_tier  # 5, 6, 7, 8, 9
        elif self.passive_type in ["hit", "crit"]:  # Flat
            return self.passive_tier  # 1, 2, 3, 4, 5
        elif self.passive_type == "ward":  # Percentage
            return self.passive_tier * 5  # 5, 10, 15, 20, 25
        elif self.passive_type == "rarity":  # Base Rarity
            return self.passive_tier * 3  # 3, 6, 9, 12, 15
        elif self.passive_type == "s_rarity":  # Special Rarity
            return round(self.passive_tier * 0.5, 1)  # 0.5, 1.0, 1.5, 2.0, 2.5
        elif self.passive_type == "fdr":  # Flat Damage Reduction
            return 5 + self.passive_tier * 2  # 6, 9, 11, 13, 15
        elif self.passive_type == "pdr":  # Percent Damage Reduction
            return 2 + self.passive_tier  # 3, 4, 5, 6, 7
        return 0

    @property
    def description(self) -> str:
        """Returns formatted string like '+9% Atk'"""
        val = self.passive_value
        p_map = {
            "atk": f"+{val}% Atk",
            "def": f"+{val}% Def",
            "hit": f"+{val} Hit Chance",
            "crit": f"+{val} Crit Chance",
            "ward": f"+{val}% HP as Ward",
            "rarity": f"+{val}% More Rarity",
            "s_rarity": f"+{val:.1f}% Special Drop Rate",
            "fdr": f"+{val} FDR",
            "pdr": f"+{val}% PDR",
        }
        return p_map.get(self.passive_type, "Unknown Effect")

    @property
    def balanced_passive_value(self) -> int:
        """Calculates the numerical value of the secondary balanced passive."""
        if self.balanced_passive == "none" or self.balanced_passive_tier == 0:
            return 0
        t = self.balanced_passive_tier
        if self.balanced_passive in ["atk", "def"]:
            return 4 + t
        elif self.balanced_passive in ["hit", "crit"]:
            return t
        elif self.balanced_passive == "ward":
            return t * 5
        elif self.balanced_passive == "rarity":
            return t * 3
        elif self.balanced_passive == "s_rarity":
            return round(t * 0.5, 1)
        elif self.balanced_passive == "fdr":
            return 1 + t
        elif self.balanced_passive == "pdr":
            return 2 + t
        return 0

    @property
    def balanced_description(self) -> str:
        """Returns formatted string for the balanced passive."""
        if self.balanced_passive == "none" or self.balanced_passive_tier == 0:
            return "Not Awakened"
        val = self.balanced_passive_value
        p_map = {
            "atk": f"+{val}% Atk",
            "def": f"+{val}% Def",
            "hit": f"+{val} Hit Chance",
            "crit": f"+{val} Crit Chance",
            "ward": f"+{val}% Ward",
            "rarity": f"+{val}% More Rarity",
            "s_rarity": f"+{val:.1f}% Special Drop Rate",
            "fdr": f"+{val} FDR",
            "pdr": f"+{val}% PDR",
        }
        return p_map.get(self.balanced_passive, "Unknown Effect")


# ---------------------------------------------------------------------------
# Codex tome model
# ---------------------------------------------------------------------------


@dataclass
class CodexTome:
    slot: int
    passive_type: str
    tier: int
    value: float  # Actual rolled stat contribution (not a fixed tier value)


# ---------------------------------------------------------------------------
# Monster parts (Consume system)
# ---------------------------------------------------------------------------

_PART_SLOT_LABELS = {
    "head": "Head",
    "torso": "Torso",
    "right_arm": "Right Arm",
    "left_arm": "Left Arm",
    "right_leg": "Right Leg",
    "left_leg": "Left Leg",
    "cheeks": "Cheeks",
    "organs": "Organs",
}


@dataclass
class MonsterPart:
    id: int
    user_id: str
    slot_type: str
    monster_name: str
    ilvl: int
    hp_value: int

    @property
    def display_name(self) -> str:
        label = _PART_SLOT_LABELS.get(
            self.slot_type, self.slot_type.replace("_", " ").title()
        )
        return f"{self.monster_name}'s **{label}**"
