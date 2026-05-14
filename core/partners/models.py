"""
core/partners/models.py — Partner dataclass.

Canonical home for the Partner model and its associated signature key maps.
No project-level imports at module load time.
"""

from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------------
# Signature skill key maps (partner_id → DB column name)
# ---------------------------------------------------------------------------

_SIG_COMBAT_KEYS = {
    1: "sig_co_skol",
    2: "sig_co_eve",
    3: "sig_co_kay",
    4: "sig_co_sigmund",
    5: "sig_co_velour",
    6: "sig_co_flora",
    7: "sig_co_yvenn",
}

_SIG_DISPATCH_KEYS = {
    1: "sig_di_skol",
    2: "sig_di_eve",
    3: "sig_di_kay",
    4: "sig_di_sigmund",
    5: "sig_di_velour",
    6: "sig_di_flora",
    7: "sig_di_yvenn",
}


# ---------------------------------------------------------------------------
# Partner model
# ---------------------------------------------------------------------------


@dataclass
class Partner:
    # --- DB row fields ---
    row_id: int
    user_id: str
    partner_id: int
    level: int
    exp: int

    combat_slot_1: Optional[str]
    combat_slot_1_lvl: int
    combat_slot_2: Optional[str]
    combat_slot_2_lvl: int
    combat_slot_3: Optional[str]
    combat_slot_3_lvl: int
    sig_combat_lvl: int

    dispatch_slot_1: Optional[str]
    dispatch_slot_1_lvl: int
    dispatch_slot_2: Optional[str]
    dispatch_slot_2_lvl: int
    dispatch_slot_3: Optional[str]
    dispatch_slot_3_lvl: int
    sig_dispatch_lvl: int

    dispatch_task: Optional[str]
    dispatch_start_time: Optional[str]
    dispatch_task_2: Optional[str]
    dispatch_start_time_2: Optional[str]

    is_active_combat: bool
    is_dispatched: bool

    affinity_encounters: int
    affinity_story_seen: int
    portrait_variant: int

    # --- Static data from CSV ---
    name: str
    title: str
    rarity: int
    pull_message: str
    base_attack: int
    base_defence: int
    base_hp: int
    image_url: str
    affinity_image_url: str
    partner_class: str = ""

    # --- Computed stats ---

    @property
    def total_attack(self) -> int:
        return self.base_attack + (self.level - 1) * self.rarity

    @property
    def total_defence(self) -> int:
        return self.base_defence + (self.level - 1) * self.rarity

    @property
    def total_hp(self) -> int:
        return self.base_hp + (self.level - 1) * self.rarity

    @property
    def num_slots(self) -> int:
        """Number of regular skill slots (same for combat and dispatch): 4★=1, 5★=2, 6★=3."""
        return self.rarity - 3

    @property
    def combat_skills(self) -> List[tuple]:
        """Active combat skill slots as (key, level) pairs."""
        all_slots = [
            (self.combat_slot_1, self.combat_slot_1_lvl),
            (self.combat_slot_2, self.combat_slot_2_lvl),
            (self.combat_slot_3, self.combat_slot_3_lvl),
        ]
        return all_slots[: self.num_slots]

    @property
    def dispatch_skills(self) -> List[tuple]:
        """Active dispatch skill slots as (key, level) pairs."""
        all_slots = [
            (self.dispatch_slot_1, self.dispatch_slot_1_lvl),
            (self.dispatch_slot_2, self.dispatch_slot_2_lvl),
            (self.dispatch_slot_3, self.dispatch_slot_3_lvl),
        ]
        return all_slots[: self.num_slots]

    @property
    def sig_combat_key(self) -> Optional[str]:
        return _SIG_COMBAT_KEYS.get(self.partner_id) if self.rarity >= 6 else None

    @property
    def sig_dispatch_key(self) -> Optional[str]:
        return _SIG_DISPATCH_KEYS.get(self.partner_id) if self.rarity >= 6 else None

    @property
    def display_image(self) -> str:
        if self.portrait_variant == 1 and self.affinity_image_url:
            return self.affinity_image_url
        return self.image_url

    @property
    def stars(self) -> str:
        return "★" * self.rarity

    @classmethod
    def from_row(cls, row: tuple, static: dict) -> "Partner":
        return cls(
            row_id=row[0],
            user_id=row[1],
            partner_id=row[2],
            level=row[3],
            exp=row[4],
            combat_slot_1=row[5],
            combat_slot_1_lvl=row[6],
            combat_slot_2=row[7],
            combat_slot_2_lvl=row[8],
            combat_slot_3=row[9],
            combat_slot_3_lvl=row[10],
            sig_combat_lvl=row[11],
            dispatch_slot_1=row[12],
            dispatch_slot_1_lvl=row[13],
            dispatch_slot_2=row[14],
            dispatch_slot_2_lvl=row[15],
            dispatch_slot_3=row[16],
            dispatch_slot_3_lvl=row[17],
            sig_dispatch_lvl=row[18],
            dispatch_task=row[19],
            dispatch_start_time=row[20],
            dispatch_task_2=row[21],
            dispatch_start_time_2=row[22],
            is_active_combat=bool(row[23]),
            is_dispatched=bool(row[24]),
            affinity_encounters=row[25],
            affinity_story_seen=row[26],
            portrait_variant=row[27],
            name=static["name"],
            title=static["title"],
            rarity=static["rarity"],
            pull_message=static["pull_message"],
            base_attack=static["base_attack"],
            base_defence=static["base_defence"],
            base_hp=static["base_hp"],
            image_url=static["image_url"],
            affinity_image_url=static["affinity_image_url"],
            partner_class=static.get("partner_class", ""),
        )
