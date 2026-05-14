"""
core/settlement/models.py — Settlement and Building dataclasses.

No project-level imports at module load time.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Settlement:
    user_id: str
    server_id: str
    town_hall_tier: int
    building_slots: int
    timber: int
    stone: int
    last_collection_time: str
    # Helper to hold building objects after fetching
    buildings: List["Building"] = field(default_factory=list)


@dataclass
class Building:
    id: int
    user_id: str
    server_id: str
    building_type: str
    tier: int
    slot_index: int
    workers_assigned: int

    @property
    def name(self) -> str:
        return self.building_type.replace("_", " ").title()
