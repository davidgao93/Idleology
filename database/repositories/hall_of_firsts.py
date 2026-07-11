import aiosqlite


class HallOfFirstsRepository:
    """Global 'first player to reach X' tracker. One row per category,
    first-write-wins via INSERT OR IGNORE (no transaction needed for a
    single insert — SQLite's own uniqueness check resolves the race)."""

    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def try_claim(
        self,
        category_key: str,
        user_id: str,
        achieved_at: str,
        snapshot_name: str,
        snapshot_title: str | None,
        snapshot_emblem: str | None,
        snapshot_appearance: str | None,
    ) -> bool:
        """Attempts to claim `category_key` for `user_id`. Returns True if this
        call won the claim (category was previously unclaimed), False if someone
        already holds it."""
        cursor = await self.connection.execute(
            """INSERT OR IGNORE INTO hall_of_firsts
               (category_key, user_id, achieved_at, snapshot_name, snapshot_title,
                snapshot_emblem, snapshot_appearance)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                category_key,
                user_id,
                achieved_at,
                snapshot_name,
                snapshot_title,
                snapshot_emblem,
                snapshot_appearance,
            ),
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def get_all(self) -> dict:
        """Returns {category_key: row} for every claimed category."""
        cursor = await self.connection.execute("SELECT * FROM hall_of_firsts")
        rows = await cursor.fetchall()
        return {row["category_key"]: row for row in rows}

    async def get_one(self, category_key: str):
        cursor = await self.connection.execute(
            "SELECT * FROM hall_of_firsts WHERE category_key = ?",
            (category_key,),
        )
        return await cursor.fetchone()
