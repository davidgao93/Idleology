# database/repositories/prestige.py

import aiosqlite


class PrestigeRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def owns(self, user_id: str, item_type: str, item_key: str) -> bool:
        cursor = await self.connection.execute(
            "SELECT 1 FROM prestige_owned WHERE user_id = ? AND item_type = ? AND item_key = ?",
            (user_id, item_type, item_key),
        )
        return await cursor.fetchone() is not None

    async def get_owned(self, user_id: str, item_type: str) -> list[str]:
        cursor = await self.connection.execute(
            "SELECT item_key FROM prestige_owned WHERE user_id = ? AND item_type = ?",
            (user_id, item_type),
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def add_owned(self, user_id: str, item_type: str, item_key: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO prestige_owned (user_id, item_type, item_key) VALUES (?, ?, ?)",
            (user_id, item_type, item_key),
        )
        await self.connection.commit()

    async def get_active(self, user_id: str) -> dict:
        cursor = await self.connection.execute(
            """SELECT prestige_border, prestige_title, prestige_display_name,
                      prestige_flair, prestige_death_message, prestige_monument
               FROM users WHERE user_id = ?""",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return {}
        return {
            "border": row[0],
            "title": row[1],
            "display_name": row[2],
            "flair": row[3],
            "death_message": row[4],
            "monument": row[5],
        }

    async def set_field(self, user_id: str, field: str, value: str) -> None:
        valid = {
            "prestige_border", "prestige_title", "prestige_display_name",
            "prestige_flair", "prestige_death_message", "prestige_monument",
        }
        if field not in valid:
            raise ValueError(f"Invalid prestige field: {field}")
        await self.connection.execute(
            f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id)
        )
        await self.connection.commit()

    async def get_monument_hall(self, server_id: str, limit: int = 10) -> list:
        cursor = await self.connection.execute(
            """SELECT name, prestige_monument, prestige_title, level
               FROM users
               WHERE server_id = ? AND prestige_monument IS NOT NULL AND prestige_monument != ''
               ORDER BY level DESC
               LIMIT ?""",
            (server_id, limit),
        )
        return await cursor.fetchall()
