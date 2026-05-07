import aiosqlite


class JourneyRepository:
    MILESTONE_LEVELS = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def get_claimed(self, user_id: str) -> set:
        """Returns the set of milestone levels already claimed by this user."""
        cursor = await self.connection.execute(
            "SELECT milestone_level FROM journey_milestones WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return {row[0] for row in rows}

    async def claim(self, user_id: str, milestone_level: int) -> None:
        """Records a milestone claim. Safe to call even if already claimed (no-op)."""
        await self.connection.execute(
            "INSERT OR IGNORE INTO journey_milestones (user_id, milestone_level) VALUES (?, ?)",
            (user_id, milestone_level),
        )
        await self.connection.commit()
