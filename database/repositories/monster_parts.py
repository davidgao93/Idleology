from database.base import BaseRepository

_INVENTORY_CAP = 20

# Lower tier = destroyed first when inventory is full
_SLOT_RARITY_TIER = {
    "head": 0, "torso": 0,
    "right_arm": 1, "left_arm": 1, "right_leg": 1, "left_leg": 1,
    "cheeks": 2, "organs": 2,
}


class MonsterPartsRepository(BaseRepository):

    async def get_inventory(self, user_id: str) -> list:
        cursor = await self.connection.execute(
            "SELECT id, user_id, slot_type, monster_name, ilvl, hp_value "
            "FROM monster_parts WHERE user_id = ? ORDER BY ilvl ASC",
            (user_id,),
        )
        return await cursor.fetchall()

    async def get_count(self, user_id: str) -> int:
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM monster_parts WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def _discard_worst(self, user_id: str) -> None:
        rows = await self.get_inventory(user_id)
        if not rows:
            return
        worst = min(rows, key=lambda r: (_SLOT_RARITY_TIER.get(r[2], 0), r[5]))
        await self.connection.execute(
            "DELETE FROM monster_parts WHERE id = ?", (worst[0],)
        )

    async def add_part(
        self,
        user_id: str,
        slot_type: str,
        monster_name: str,
        ilvl: int,
        hp_value: int,
    ) -> None:
        count = await self.get_count(user_id)
        if count >= _INVENTORY_CAP:
            await self._discard_worst(user_id)
        await self.connection.execute(
            "INSERT INTO monster_parts (user_id, slot_type, monster_name, ilvl, hp_value) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, slot_type, monster_name, ilvl, hp_value),
        )
        await self.connection.commit()

    async def delete_part(self, part_id: int) -> None:
        await self.connection.execute(
            "DELETE FROM monster_parts WHERE id = ?", (part_id,)
        )
        await self.connection.commit()

    async def delete_below_ilvl(self, user_id: str, threshold: int) -> int:
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM monster_parts WHERE user_id = ? AND ilvl < ?",
            (user_id, threshold),
        )
        row = await cursor.fetchone()
        count = row[0] if row else 0
        if count > 0:
            await self.connection.execute(
                "DELETE FROM monster_parts WHERE user_id = ? AND ilvl < ?",
                (user_id, threshold),
            )
            await self.connection.commit()
        return count

    async def get_equipped_parts(self, user_id: str) -> dict:
        """Returns {slot_type: {"hp": int, "monster_name": str}} for all equipped slots."""
        cursor = await self.connection.execute(
            "SELECT slot_type, hp_value, monster_name "
            "FROM monster_parts_equipped WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return {r[0]: {"hp": r[1], "monster_name": r[2]} for r in rows}

    async def equip_part(
        self,
        user_id: str,
        slot_type: str,
        hp_value: int,
        monster_name: str,
    ) -> None:
        """Upserts into the equipped table. Old equipped part in that slot is overwritten."""
        await self.connection.execute(
            """INSERT INTO monster_parts_equipped (user_id, slot_type, hp_value, monster_name)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, slot_type)
               DO UPDATE SET hp_value = excluded.hp_value, monster_name = excluded.monster_name""",
            (user_id, slot_type, hp_value, monster_name),
        )
        await self.connection.commit()

    async def unequip_slot(self, user_id: str, slot_type: str) -> None:
        await self.connection.execute(
            "DELETE FROM monster_parts_equipped WHERE user_id = ? AND slot_type = ?",
            (user_id, slot_type),
        )
        await self.connection.commit()
