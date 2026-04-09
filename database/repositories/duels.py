import aiosqlite


class DuelStatsRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def _ensure_row(self, user_id: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO duel_stats (user_id) VALUES (?)",
            (user_id,)
        )

    async def record_result(self, winner_id: str, loser_id: str) -> None:
        await self._ensure_row(winner_id)
        await self._ensure_row(loser_id)
        await self.connection.execute(
            "UPDATE duel_stats SET wins = wins + 1 WHERE user_id = ?",
            (winner_id,)
        )
        await self.connection.execute(
            "UPDATE duel_stats SET losses = losses + 1 WHERE user_id = ?",
            (loser_id,)
        )
        await self.connection.commit()

    async def get_stats(self, user_id: str):
        """Returns (wins, losses) for a user, or (0, 0) if not found."""
        async with self.connection.execute(
            "SELECT wins, losses FROM duel_stats WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return row if row else (0, 0)

    async def get_leaderboard(self, limit: int = 10):
        """Returns [(user_id, wins, losses), ...] ordered by wins desc."""
        async with self.connection.execute(
            "SELECT user_id, wins, losses FROM duel_stats ORDER BY wins DESC LIMIT ?",
            (limit,)
        ) as cursor:
            return await cursor.fetchall()
