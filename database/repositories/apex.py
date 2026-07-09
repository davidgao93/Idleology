"""
database/repositories/apex.py — Apex Hunts + Soul Stone data layer.

Handles four tables:
  apex_hunt_profiles — hunt charges and per-zone win/loss records
  soul_stones        — three permanent passive slots
  soul_shards        — shard inventories (pyre, tempest, bulwark, verdant, fortune, rift) + soul fragments
  meta_shards        — meta shard inventories (sharpened_fang, engorged_heart, condensed_blood,
                       primal_essence, soul_vessel)
"""

import time

from database.base import BaseRepository


_ZONE_KEYS = ("ashen", "storm", "citadel", "grove", "vault", "shattered")
_SHARD_KEYS = (
    "pyre",
    "tempest",
    "bulwark",
    "verdant",
    "fortune",
    "rift",
    "soul_fragments",
)
_META_KEYS = (
    "sharpened_fang",
    "engorged_heart",
    "condensed_blood",
    "primal_essence",
    "soul_vessel",
)


class ApexRepository(BaseRepository):
    # ------------------------------------------------------------------
    # Hunt Profile
    # ------------------------------------------------------------------

    async def get_or_create_profile(self, user_id: str, server_id: str) -> dict:
        """Returns the hunt profile dict, creating a default row if absent."""
        cursor = await self.connection.execute(
            "SELECT * FROM apex_hunt_profiles WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if row:
            keys = [d[0] for d in cursor.description]
            return dict(zip(keys, row))
        # Create default
        await self.connection.execute(
            "INSERT OR IGNORE INTO apex_hunt_profiles (user_id, server_id) VALUES (?, ?)",
            (user_id, server_id),
        )
        await self.connection.commit()
        return {
            "user_id": user_id,
            "server_id": server_id,
            "hunt_charges": 5,
            "last_charge_time": None,
            **{f"{z}_wins": 0 for z in _ZONE_KEYS},
            **{f"{z}_losses": 0 for z in _ZONE_KEYS},
        }

    async def consume_charge(self, user_id: str, server_id: str) -> None:
        """Decrements hunt_charges by 1 and records the current timestamp if not already set."""
        profile = await self.get_or_create_profile(user_id, server_id)
        new_charges = max(0, profile["hunt_charges"] - 1)
        now_ts = (
            time.time()
            if profile["last_charge_time"] is None
            else profile["last_charge_time"]
        )
        await self.connection.execute(
            "UPDATE apex_hunt_profiles SET hunt_charges = ?, last_charge_time = ? "
            "WHERE user_id = ? AND server_id = ?",
            (new_charges, now_ts, user_id, server_id),
        )
        await self.connection.commit()

    async def restore_charges(
        self, user_id: str, server_id: str, charges: int, timestamp: float | None
    ) -> None:
        """Overwrites hunt_charges and last_charge_time (used by charge regen calculation)."""
        await self.connection.execute(
            "UPDATE apex_hunt_profiles SET hunt_charges = ?, last_charge_time = ? "
            "WHERE user_id = ? AND server_id = ?",
            (charges, timestamp, user_id, server_id),
        )
        await self.connection.commit()

    async def add_charge(
        self, user_id: str, server_id: str, amount: int, max_charges: int
    ) -> int:
        """Increments hunt_charges by `amount`, capped at `max_charges`.
        Returns the new charge count. Used by the Soul Fragment conversion."""
        profile = await self.get_or_create_profile(user_id, server_id)
        new_charges = min(max_charges, profile["hunt_charges"] + amount)
        await self.connection.execute(
            "UPDATE apex_hunt_profiles SET hunt_charges = ? WHERE user_id = ? AND server_id = ?",
            (new_charges, user_id, server_id),
        )
        await self.connection.commit()
        return new_charges

    async def record_win(self, user_id: str, server_id: str, zone_key: str) -> None:
        await self.get_or_create_profile(user_id, server_id)
        col = f"{zone_key}_wins"
        await self.connection.execute(
            f"UPDATE apex_hunt_profiles SET {col} = {col} + 1 WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def record_loss(self, user_id: str, server_id: str, zone_key: str) -> None:
        await self.get_or_create_profile(user_id, server_id)
        col = f"{zone_key}_losses"
        await self.connection.execute(
            f"UPDATE apex_hunt_profiles SET {col} = {col} + 1 WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Soul Stone
    # ------------------------------------------------------------------

    async def get_or_create_soul_stone(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT * FROM soul_stones WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if row:
            keys = [d[0] for d in cursor.description]
            return dict(zip(keys, row))
        await self.connection.execute(
            "INSERT OR IGNORE INTO soul_stones (user_id, server_id) VALUES (?, ?)",
            (user_id, server_id),
        )
        await self.connection.commit()
        return {
            "user_id": user_id,
            "server_id": server_id,
            "slot_1_passive": None,
            "slot_1_tier": None,
            "slot_1_category": None,
            "slot_2_passive": None,
            "slot_2_tier": None,
            "slot_2_category": None,
            "slot_3_passive": None,
            "slot_3_tier": None,
            "slot_3_category": None,
        }

    async def set_slot(
        self,
        user_id: str,
        server_id: str,
        slot: int,  # 1, 2, or 3
        passive: str,
        tier: int,
        category: str,
    ) -> None:
        await self.get_or_create_soul_stone(user_id, server_id)
        s = slot
        await self.connection.execute(
            f"UPDATE soul_stones SET slot_{s}_passive = ?, slot_{s}_tier = ?, slot_{s}_category = ? "
            "WHERE user_id = ? AND server_id = ?",
            (passive, tier, category, user_id, server_id),
        )
        await self.connection.commit()

    async def clear_slot(self, user_id: str, server_id: str, slot: int) -> None:
        await self.get_or_create_soul_stone(user_id, server_id)
        s = slot
        await self.connection.execute(
            f"UPDATE soul_stones SET slot_{s}_passive = NULL, slot_{s}_tier = NULL, slot_{s}_category = NULL "
            "WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def upgrade_slot_tier(
        self, user_id: str, server_id: str, slot: int, new_tier: int
    ) -> None:
        s = slot
        await self.connection.execute(
            f"UPDATE soul_stones SET slot_{s}_tier = ? WHERE user_id = ? AND server_id = ?",
            (new_tier, user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Shards
    # ------------------------------------------------------------------

    async def get_or_create_shards(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT * FROM soul_shards WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if row:
            keys = [d[0] for d in cursor.description]
            return dict(zip(keys, row))
        await self.connection.execute(
            "INSERT OR IGNORE INTO soul_shards (user_id, server_id) VALUES (?, ?)",
            (user_id, server_id),
        )
        await self.connection.commit()
        return {
            "user_id": user_id,
            "server_id": server_id,
            **{k: 0 for k in _SHARD_KEYS},
        }

    async def modify_shard(
        self, user_id: str, server_id: str, shard_type: str, delta: int
    ) -> None:
        if shard_type not in _SHARD_KEYS:
            raise ValueError(f"Unknown shard type: {shard_type}")
        await self.get_or_create_shards(user_id, server_id)
        await self.connection.execute(
            f"UPDATE soul_shards SET {shard_type} = MAX(0, {shard_type} + ?) "
            "WHERE user_id = ? AND server_id = ?",
            (delta, user_id, server_id),
        )
        await self.connection.commit()

    async def deduct_upgrade_cost(
        self,
        user_id: str,
        server_id: str,
        matching_type: str,
        matching_amt: int,
        rift_amt: int,
    ) -> bool:
        """Deducts upgrade shard cost. Returns False if insufficient funds."""
        shards = await self.get_or_create_shards(user_id, server_id)
        if shards.get(matching_type, 0) < matching_amt:
            return False
        if rift_amt > 0 and shards.get("rift", 0) < rift_amt:
            return False
        if matching_amt > 0:
            await self.modify_shard(user_id, server_id, matching_type, -matching_amt)
        if rift_amt > 0:
            await self.modify_shard(user_id, server_id, "rift", -rift_amt)
        return True

    # ------------------------------------------------------------------
    # Meta Shards
    # ------------------------------------------------------------------

    async def get_or_create_meta_shards(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT * FROM meta_shards WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if row:
            keys = [d[0] for d in cursor.description]
            return dict(zip(keys, row))
        await self.connection.execute(
            "INSERT OR IGNORE INTO meta_shards (user_id, server_id) VALUES (?, ?)",
            (user_id, server_id),
        )
        await self.connection.commit()
        return {
            "user_id": user_id,
            "server_id": server_id,
            **{k: 0 for k in _META_KEYS},
        }

    async def modify_meta_shard(
        self, user_id: str, server_id: str, shard_type: str, delta: int
    ) -> None:
        if shard_type not in _META_KEYS:
            raise ValueError(f"Unknown meta shard type: {shard_type}")
        await self.get_or_create_meta_shards(user_id, server_id)
        await self.connection.execute(
            f"UPDATE meta_shards SET {shard_type} = MAX(0, {shard_type} + ?) "
            "WHERE user_id = ? AND server_id = ?",
            (delta, user_id, server_id),
        )
        await self.connection.commit()

    async def deduct_meta_shard_atomic(
        self, user_id: str, server_id: str, shard_type: str, amount: int
    ) -> bool:
        """Deducts meta shards only if balance >= amount. Returns True on success."""
        if shard_type not in _META_KEYS:
            raise ValueError(f"Unknown meta shard type: {shard_type}")
        await self.get_or_create_meta_shards(user_id, server_id)
        cursor = await self.connection.execute(
            f"UPDATE meta_shards SET {shard_type} = {shard_type} - ? "
            f"WHERE user_id = ? AND server_id = ? AND {shard_type} >= ?",
            (amount, user_id, server_id, amount),
        )
        await self.connection.commit()
        return cursor.rowcount == 1

    async def transfer_meta_shard(
        self,
        from_uid: str,
        to_uid: str,
        server_id: str,
        shard_type: str,
        amount: int,
    ) -> bool:
        """Transfers meta shards between players. Returns False if insufficient."""
        if not await self.deduct_meta_shard_atomic(
            from_uid, server_id, shard_type, amount
        ):
            return False
        await self.modify_meta_shard(to_uid, server_id, shard_type, amount)
        return True
