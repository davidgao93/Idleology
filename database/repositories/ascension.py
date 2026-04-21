from database.base import BaseRepository


class AscensionRepository(BaseRepository):

    async def get_highest_floor(self, user_id: str) -> int:
        cursor = await self.connection.execute(
            "SELECT highest_ascension_floor FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def update_highest_floor(self, user_id: str, floor: int) -> None:
        await self.connection.execute(
            "UPDATE users SET highest_ascension_floor = MAX(highest_ascension_floor, ?) WHERE user_id = ?",
            (floor, user_id),
        )
        await self.connection.commit()

    async def get_unlocked_floors(self, user_id: str) -> set:
        cursor = await self.connection.execute(
            "SELECT floor FROM ascension_unlocks WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return {row[0] for row in rows}

    async def unlock_floor(self, user_id: str, floor: int) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO ascension_unlocks (user_id, floor) VALUES (?, ?)",
            (user_id, floor),
        )
        await self.connection.commit()
