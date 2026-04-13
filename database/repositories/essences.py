import aiosqlite
from typing import Dict, Optional


# All valid essence type identifiers.
ESSENCE_TYPES = {
    # Common
    "power",
    "protection",
    # Rare
    "insight",
    "evasion",
    "warding",
    # Utility
    "cleansing",
    "chaos",
    "annulment",
    # Corrupted
    "aphrodite",
    "lucifer",
    "gemini",
    "neet",
}

CORRUPTED_ESSENCE_TYPES = {"aphrodite", "lucifer", "gemini", "neet"}
UTILITY_ESSENCE_TYPES = {"cleansing", "chaos", "annulment"}
RARE_ESSENCE_TYPES = {"insight", "evasion", "warding"}
COMMON_ESSENCE_TYPES = {"power", "protection"}


class EssencesRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_all(self, user_id: str) -> Dict[str, int]:
        """Returns {essence_type: quantity} for all essence types the player has (qty > 0)."""
        cursor = await self.connection.execute(
            "SELECT essence_type, quantity FROM player_essences WHERE user_id = ? AND quantity > 0",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    async def get_quantity(self, user_id: str, essence_type: str) -> int:
        """Returns quantity of a specific essence type (0 if none)."""
        cursor = await self.connection.execute(
            "SELECT quantity FROM player_essences WHERE user_id = ? AND essence_type = ?",
            (user_id, essence_type)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def add(self, user_id: str, essence_type: str, quantity: int = 1) -> None:
        """Adds essence(s) to the player's inventory (upsert)."""
        await self.connection.execute(
            """INSERT INTO player_essences (user_id, essence_type, quantity)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, essence_type) DO UPDATE SET quantity = quantity + excluded.quantity""",
            (user_id, essence_type, quantity)
        )
        await self.connection.commit()

    async def consume(self, user_id: str, essence_type: str, quantity: int = 1) -> bool:
        """
        Removes essence(s) from inventory. Returns True if successful, False if insufficient stock.
        Does not commit on failure.
        """
        current = await self.get_quantity(user_id, essence_type)
        if current < quantity:
            return False
        await self.connection.execute(
            "UPDATE player_essences SET quantity = quantity - ? WHERE user_id = ? AND essence_type = ?",
            (quantity, user_id, essence_type)
        )
        await self.connection.commit()
        return True
