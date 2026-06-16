"""
core/apex/models.py — Dataclasses for the Apex Hunts system.

SoulStoneSlot   — one slot in the Soul Stone (passive, tier, category)
SoulStone       — the three-slot Soul Stone for a player
ShardInventory  — per-player shard counts
MetaShardInventory — per-player meta shard counts
ApexHuntProfile — hunt charge state + per-zone win/loss records
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SoulStoneSlot:
    passive: Optional[str]  # e.g. "burning", "hearty"
    tier: Optional[int]  # 1–5
    category: Optional[str]  # "offensive" | "defensive" | "mixed" | "utility"

    @property
    def is_empty(self) -> bool:
        return self.passive is None


@dataclass
class SoulStone:
    user_id: str
    server_id: str
    slot_1: SoulStoneSlot = field(
        default_factory=lambda: SoulStoneSlot(None, None, None)
    )
    slot_2: SoulStoneSlot = field(
        default_factory=lambda: SoulStoneSlot(None, None, None)
    )
    slot_3: SoulStoneSlot = field(
        default_factory=lambda: SoulStoneSlot(None, None, None)
    )

    @property
    def slots(self) -> list[SoulStoneSlot]:
        return [self.slot_1, self.slot_2, self.slot_3]

    @property
    def first_empty_slot(self) -> int | None:
        """Returns 1-indexed slot number of first empty slot, or None."""
        for i, s in enumerate(self.slots, 1):
            if s.is_empty:
                return i
        return None

    def get_passive_tier(self, passive_key: str) -> int | None:
        """Returns the tier of the given passive if it exists in any slot, else None."""
        for s in self.slots:
            if s.passive == passive_key and s.tier is not None:
                return s.tier
        return None

    @property
    def resonance_key(self) -> str | None:
        """
        Computes the resonance key based on the categories of filled slots.
        Returns e.g. 'offensive_3', 'defensive_2', or None if no resonance.
        """
        categories = [s.category for s in self.slots if not s.is_empty]
        if not categories:
            return None
        from collections import Counter

        counts = Counter(categories)
        # Find the category with the highest count (at least 2)
        best_cat, best_count = counts.most_common(1)[0]
        if best_count >= 3:
            return f"{best_cat}_3"
        elif best_count >= 2:
            return f"{best_cat}_2"
        return None


@dataclass
class ShardInventory:
    user_id: str
    server_id: str
    pyre: int = 0
    tempest: int = 0
    bulwark: int = 0
    verdant: int = 0
    fortune: int = 0
    rift: int = 0
    soul_fragments: int = 0

    def get(self, shard_type: str) -> int:
        return getattr(self, shard_type, 0)


@dataclass
class MetaShardInventory:
    user_id: str
    server_id: str
    sharpened_fang: int = 0
    engorged_heart: int = 0
    condensed_blood: int = 0
    primal_essence: int = 0
    soul_vessel: int = 0

    def get(self, shard_type: str) -> int:
        return getattr(self, shard_type, 0)


@dataclass
class ApexHuntProfile:
    user_id: str
    server_id: str
    hunt_charges: int
    last_charge_time: Optional[float]
    zone_stats: dict  # zone_key → {"wins": int, "losses": int}

    @property
    def shattered_realm_unlocked(self) -> bool:
        """True when the player has at least 1 win in each of the 5 non-shattered zones."""
        non_shattered = ("ashen", "storm", "citadel", "grove", "vault")
        return all(
            self.zone_stats.get(z, {}).get("wins", 0) >= 1 for z in non_shattered
        )


# ---------------------------------------------------------------------------
# Factory helpers — build models from DB dicts
# ---------------------------------------------------------------------------


def soul_stone_from_db(row: dict) -> SoulStone:
    def _slot(n: int) -> SoulStoneSlot:
        return SoulStoneSlot(
            passive=row.get(f"slot_{n}_passive"),
            tier=row.get(f"slot_{n}_tier"),
            category=row.get(f"slot_{n}_category"),
        )

    return SoulStone(
        user_id=row["user_id"],
        server_id=row["server_id"],
        slot_1=_slot(1),
        slot_2=_slot(2),
        slot_3=_slot(3),
    )


def shards_from_db(row: dict) -> ShardInventory:
    return ShardInventory(
        user_id=row["user_id"],
        server_id=row["server_id"],
        pyre=row.get("pyre", 0),
        tempest=row.get("tempest", 0),
        bulwark=row.get("bulwark", 0),
        verdant=row.get("verdant", 0),
        fortune=row.get("fortune", 0),
        rift=row.get("rift", 0),
        soul_fragments=row.get("soul_fragments", 0),
    )


def meta_shards_from_db(row: dict) -> MetaShardInventory:
    return MetaShardInventory(
        user_id=row["user_id"],
        server_id=row["server_id"],
        sharpened_fang=row.get("sharpened_fang", 0),
        engorged_heart=row.get("engorged_heart", 0),
        condensed_blood=row.get("condensed_blood", 0),
        primal_essence=row.get("primal_essence", 0),
        soul_vessel=row.get("soul_vessel", 0),
    )


def profile_from_db(row: dict) -> ApexHuntProfile:
    zone_keys = ("ashen", "storm", "citadel", "grove", "vault", "shattered")
    zone_stats = {
        z: {"wins": row.get(f"{z}_wins", 0), "losses": row.get(f"{z}_losses", 0)}
        for z in zone_keys
    }
    return ApexHuntProfile(
        user_id=row["user_id"],
        server_id=row["server_id"],
        hunt_charges=row.get("hunt_charges", 3),
        last_charge_time=row.get("last_charge_time"),
        zone_stats=zone_stats,
    )
