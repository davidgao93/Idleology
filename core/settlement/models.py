"""
core/settlement/models.py — Settlement, Building, and Plot dataclasses.

No project-level imports at module load time.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Plot:
    """Represents one cell of the 5×5 settlement grid (index 1–20)."""

    plot_index: int
    is_developed: bool
    bonus_type: Optional[str]  # e.g. "fertile_ground"; None when undeveloped


@dataclass
class Building:
    id: int
    user_id: str
    server_id: str
    building_type: str
    tier: int
    slot_index: int  # legacy column — kept for DB compat
    workers_assigned: int
    plot_index: Optional[int] = None  # which grid plot this building sits on
    is_meta: bool = False  # True = meta building (no tiers, no slot cost)

    @property
    def name(self) -> str:
        if self.is_meta:
            # Avoid a circular import at class-definition time by importing lazily
            from core.settlement.plots import META_BUILDINGS

            meta = META_BUILDINGS.get(self.building_type)
            if meta:
                return meta["label"]
        return self.building_type.replace("_", " ").title()


@dataclass
class Settlement:
    user_id: str
    server_id: str
    town_hall_tier: int
    building_slots: int
    timber: int
    stone: int
    last_collection_time: str
    last_zeal_gather_time: Optional[str] = None
    buildings: List[Building] = field(default_factory=list)
    plots: List[Plot] = field(default_factory=list)
