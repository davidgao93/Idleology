import aiosqlite
from typing import List


class AlchemyRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    # ------------------------------------------------------------------
    # Alchemy Level
    # ------------------------------------------------------------------

    async def initialize_if_new(self, user_id: str) -> bool:
        """Insert a level-1 row if none exists. Returns True if this is a new user."""
        async with self.connection.execute(
            "SELECT COUNT(*) FROM alchemy_data WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row[0] == 0:
            await self.connection.execute(
                "INSERT INTO alchemy_data (user_id, level) VALUES (?, 1)", (user_id,)
            )
            await self.connection.commit()
            return True
        return False

    async def _ensure_row(self, user_id: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO alchemy_data (user_id, level) VALUES (?, 1)",
            (user_id,)
        )

    async def get_level(self, user_id: str) -> int:
        await self._ensure_row(user_id)
        async with self.connection.execute(
            "SELECT level FROM alchemy_data WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        level = row[0] if row else 1
        # Migrate legacy level-0 users to level 1
        if level == 0:
            await self.connection.execute(
                "UPDATE alchemy_data SET level = 1 WHERE user_id = ?", (user_id,)
            )
            await self.connection.commit()
            return 1
        return level

    async def set_level(self, user_id: str, level: int) -> None:
        await self._ensure_row(user_id)
        await self.connection.execute(
            "UPDATE alchemy_data SET level = ? WHERE user_id = ?",
            (level, user_id)
        )
        await self.connection.commit()

    async def get_free_roll_used(self, user_id: str) -> bool:
        await self._ensure_row(user_id)
        async with self.connection.execute(
            "SELECT free_roll_used FROM alchemy_data WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row[0]) if row else False

    async def set_free_roll_used(self, user_id: str) -> None:
        await self._ensure_row(user_id)
        await self.connection.execute(
            "UPDATE alchemy_data SET free_roll_used = 1 WHERE user_id = ?", (user_id,)
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Potion Passives
    # ------------------------------------------------------------------

    async def get_potion_passives(self, user_id: str) -> List[dict]:
        """Returns [{slot, passive_type, passive_value}, ...] ordered by slot."""
        async with self.connection.execute(
            "SELECT slot, passive_type, passive_value FROM potion_passives "
            "WHERE user_id = ? ORDER BY slot",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"slot": r[0], "passive_type": r[1], "passive_value": r[2]} for r in rows]

    async def set_passive(self, user_id: str, slot: int,
                          passive_type: str, passive_value: float) -> None:
        await self.connection.execute(
            """INSERT INTO potion_passives (user_id, slot, passive_type, passive_value)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, slot) DO UPDATE SET
                   passive_type = excluded.passive_type,
                   passive_value = excluded.passive_value""",
            (user_id, slot, passive_type, passive_value)
        )
        await self.connection.commit()

    async def delete_passive(self, user_id: str, slot: int) -> None:
        await self.connection.execute(
            "DELETE FROM potion_passives WHERE user_id = ? AND slot = ?",
            (user_id, slot)
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Transmutation helpers
    # ------------------------------------------------------------------

    async def get_resource_amount(self, user_id: str, server_id: str,
                                   skill_type: str, col: str) -> int:
        """Reads a single resource column from the relevant skill table."""
        async with self.connection.execute(
            f"SELECT {col} FROM {skill_type} WHERE user_id = ? AND server_id = ?",
            (user_id, server_id)
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def transmute(self, user_id: str, server_id: str,
                        skill_type: str,
                        src_col: str, src_delta: int,
                        dst_col: str, dst_delta: int) -> None:
        """Atomically deduct src and credit dst in the skill table."""
        await self.connection.execute(
            f"UPDATE {skill_type} "
            f"SET {src_col} = {src_col} + ?, {dst_col} = {dst_col} + ? "
            f"WHERE user_id = ? AND server_id = ?",
            (src_delta, dst_delta, user_id, server_id)
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Cosmic Dust
    # ------------------------------------------------------------------

    async def get_cosmic_dust(self, user_id: str) -> int:
        await self._ensure_row(user_id)
        async with self.connection.execute(
            "SELECT cosmic_dust FROM alchemy_data WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def modify_cosmic_dust(self, user_id: str, delta: int) -> None:
        await self._ensure_row(user_id)
        await self.connection.execute(
            "UPDATE alchemy_data SET cosmic_dust = cosmic_dust + ? WHERE user_id = ?",
            (delta, user_id)
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Synthesis Queue
    # ------------------------------------------------------------------

    async def get_synthesis_queue(self, user_id: str):
        """Returns (item_type, quantity, start_time) or None."""
        async with self.connection.execute(
            "SELECT item_type, quantity, start_time FROM synthesis_queue WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def start_disenchant(self, user_id: str, item_type: str,
                                quantity: int, start_time: str) -> None:
        """Insert or replace the active disenchant task for this user."""
        await self.connection.execute(
            """INSERT INTO synthesis_queue (user_id, item_type, quantity, start_time)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   item_type  = excluded.item_type,
                   quantity   = excluded.quantity,
                   start_time = excluded.start_time""",
            (user_id, item_type, quantity, start_time)
        )
        await self.connection.commit()

    async def clear_synthesis_queue(self, user_id: str) -> None:
        await self.connection.execute(
            "DELETE FROM synthesis_queue WHERE user_id = ?", (user_id,)
        )
        await self.connection.commit()
