"""
database/repositories/tutorials.py — First-use tutorial tracking.

Each (user_id, feature_key) pair is stored once a tutorial has been shown.
has_seen() returns False until mark_seen() is called, making the check a
single-line async bool anywhere in a cog.
"""

from database.base import BaseRepository


class TutorialsRepository(BaseRepository):
    async def has_seen(self, user_id: str, feature_key: str) -> bool:
        """Return True if the player has already seen this tutorial."""
        async with self.connection.execute(
            "SELECT 1 FROM tutorial_seen WHERE user_id = ? AND feature_key = ?",
            (user_id, feature_key),
        ) as cur:
            return await cur.fetchone() is not None

    async def mark_seen(self, user_id: str, feature_key: str) -> None:
        """Record that the player has seen this tutorial (idempotent)."""
        await self.connection.execute(
            "INSERT OR IGNORE INTO tutorial_seen (user_id, feature_key) VALUES (?, ?)",
            (user_id, feature_key),
        )
        await self.connection.commit()
