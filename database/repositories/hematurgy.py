from database.base import BaseRepository


class HematurgyRepository(BaseRepository):

    async def get_blood(self, user_id: str) -> dict:
        """Returns {primordial, evolutionary, mutative} for the user, creating a row if absent."""
        cursor = await self.connection.execute(
            "SELECT primordial, evolutionary, mutative FROM hematurgy_blood WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return {"primordial": row[0], "evolutionary": row[1], "mutative": row[2]}
        await self.connection.execute(
            "INSERT OR IGNORE INTO hematurgy_blood (user_id) VALUES (?)", (user_id,)
        )
        await self.connection.commit()
        return {"primordial": 0, "evolutionary": 0, "mutative": 0}

    async def modify_blood(self, user_id: str, blood_type: str, amount: int) -> None:
        """Add (positive) or subtract (negative) from a specific blood type.
        Creates the row if it doesn't exist first."""
        await self.connection.execute(
            "INSERT OR IGNORE INTO hematurgy_blood (user_id) VALUES (?)", (user_id,)
        )
        col = {"primordial": "primordial", "evolutionary": "evolutionary", "mutative": "mutative"}.get(blood_type)
        if col is None:
            raise ValueError(f"Unknown blood type: {blood_type}")
        await self.connection.execute(
            f"UPDATE hematurgy_blood SET {col} = MAX(0, {col} + ?) WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def get_passive(self, user_id: str, slot_type: str) -> dict | None:
        """Returns {passive_id, tier} for the slot, or None if no passive is unlocked."""
        cursor = await self.connection.execute(
            "SELECT passive_id, tier FROM hematurgy_passives WHERE user_id = ? AND slot_type = ?",
            (user_id, slot_type),
        )
        row = await cursor.fetchone()
        if row:
            return {"passive_id": row[0], "tier": row[1]}
        return None

    async def get_all_passives(self, user_id: str) -> dict:
        """Returns {slot_type: {passive_id, tier}} for all unlocked slots."""
        cursor = await self.connection.execute(
            "SELECT slot_type, passive_id, tier FROM hematurgy_passives WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return {r[0]: {"passive_id": r[1], "tier": r[2]} for r in rows}

    async def set_passive(self, user_id: str, slot_type: str, passive_id: str, tier: int = 1) -> None:
        """Upserts a hematurgy passive for a slot."""
        await self.connection.execute(
            """INSERT INTO hematurgy_passives (user_id, slot_type, passive_id, tier)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, slot_type)
               DO UPDATE SET passive_id = excluded.passive_id, tier = excluded.tier""",
            (user_id, slot_type, passive_id, tier),
        )
        await self.connection.commit()

    async def upgrade_passive(self, user_id: str, slot_type: str) -> int:
        """Increments the tier by 1 (max 5). Returns the new tier, or -1 if no passive exists."""
        row = await self.get_passive(user_id, slot_type)
        if row is None:
            return -1
        new_tier = min(5, row["tier"] + 1)
        await self.connection.execute(
            "UPDATE hematurgy_passives SET tier = ? WHERE user_id = ? AND slot_type = ?",
            (new_tier, user_id, slot_type),
        )
        await self.connection.commit()
        return new_tier

    async def delete_passive(self, user_id: str, slot_type: str) -> None:
        """Removes the hematurgy passive for a slot (used by Mutative delete outcome)."""
        await self.connection.execute(
            "DELETE FROM hematurgy_passives WHERE user_id = ? AND slot_type = ?",
            (user_id, slot_type),
        )
        await self.connection.commit()

    async def get_unlocked_passive_ids(self, user_id: str) -> set:
        """Returns the set of passive_ids currently owned across all slots."""
        cursor = await self.connection.execute(
            "SELECT passive_id FROM hematurgy_passives WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return {r[0] for r in rows}
