# database/repositories/companions.py

import aiosqlite
from typing import List, Optional, Tuple
from core.models import Companion

class CompanionRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_all(self, user_id: str) -> List[Tuple]:
        """Fetches all companions for a user."""
        rows = await self.connection.execute(
            "SELECT * FROM companions WHERE user_id = ?", (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()

    async def get_active(self, user_id: str) -> List[Tuple]:
        """Fetches only active companions."""
        rows = await self.connection.execute(
            "SELECT * FROM companions WHERE user_id = ? AND is_active = 1", (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()

    async def get_by_id(self, companion_id: int) -> Optional[Tuple]:
        """Fetches a specific companion."""
        rows = await self.connection.execute(
            "SELECT * FROM companions WHERE id = ?", (companion_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def get_count(self, user_id: str) -> int:
        """Counts total companions owned (for 20 slot cap)."""
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM companions WHERE user_id = ?", (user_id,)
        )
        res = await rows.fetchone()
        return res[0] if res else 0

    async def add_companion(self, user_id: str, name: str, species: str, image: str, 
                          p_type: str, p_tier: int) -> None:
        """Adds a new companion."""
        await self.connection.execute(
            """INSERT INTO companions (user_id, name, species, image_url, passive_type, passive_tier) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, name, species, image, p_type, p_tier)
        )
        await self.connection.commit()

    async def delete_companion(self, companion_id: int, user_id: str) -> None:
        """Releases a companion."""
        await self.connection.execute(
            "DELETE FROM companions WHERE id = ? AND user_id = ?", 
            (companion_id, user_id)
        )
        await self.connection.commit()

    async def set_active(self, user_id: str, companion_id: int, active: bool) -> bool:
        """
        Toggles active state. 
        Returns False if trying to activate a 4th companion.
        """
        if active:
            # Check current active count
            rows = await self.connection.execute(
                "SELECT COUNT(*) FROM companions WHERE user_id = ? AND is_active = 1", 
                (user_id,)
            )
            count = (await rows.fetchone())[0]
            if count >= 3:
                return False

        val = 1 if active else 0
        await self.connection.execute(
            "UPDATE companions SET is_active = ? WHERE id = ? AND user_id = ?",
            (val, companion_id, user_id)
        )
        await self.connection.commit()
        return True

    async def add_exp(self, companion_id: int, amount: int) -> None:
        """Adds experience to a companion."""
        await self.connection.execute(
            "UPDATE companions SET exp = exp + ? WHERE id = ?",
            (amount, companion_id)
        )
        await self.connection.commit()

    async def level_up(self, companion_id: int) -> None:
        """Increments level."""
        await self.connection.execute(
            "UPDATE companions SET level = level + 1 WHERE id = ?",
            (companion_id,)
        )
        await self.connection.commit()

    async def update_passive(self, companion_id: int, p_type: str, p_tier: int) -> None:
        """Rerolls the passive."""
        await self.connection.execute(
            "UPDATE companions SET passive_type = ?, passive_tier = ? WHERE id = ?",
            (p_type, p_tier, companion_id)
        )
        await self.connection.commit()

    async def rename(self, companion_id: int, new_name: str) -> None:
        await self.connection.execute(
            "UPDATE companions SET name = ? WHERE id = ?",
            (new_name, companion_id)
        )
        await self.connection.commit()


async def update_stats(self, companion_id: int, new_level: int, new_exp: int) -> None:
        """Updates Level and XP atomically."""
        await self.connection.execute(
            "UPDATE companions SET level = ?, exp = ? WHERE id = ?",
            (new_level, new_exp, companion_id)
        )
        await self.connection.commit()