import json

import aiosqlite


class RiteRepository:
    """The Rite of Convergence: run persistence + first-clear unlock flag."""

    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    # ------------------------------------------------------------------
    # Persisted runs (room-boundary save state, codex_runs pattern)
    # Snapshot is stored as JSON in the `data` column.
    # ------------------------------------------------------------------

    async def get_run(self, user_id: str, server_id: str) -> dict | None:
        """Returns the saved run snapshot dict, or None."""
        async with self.connection.execute(
            "SELECT data FROM rite_runs WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        if not row or not row["data"]:
            return None
        return json.loads(row["data"])

    async def upsert_run(self, user_id: str, server_id: str, data: dict) -> None:
        """Create or update the saved run for this user/server."""
        await self.connection.execute(
            """INSERT INTO rite_runs (user_id, server_id, data)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                   data = excluded.data""",
            (user_id, server_id, json.dumps(data)),
        )
        await self.connection.commit()

    async def delete_run(self, user_id: str, server_id: str) -> None:
        """Clear the saved run (completion, defeat with no attempts left, or abandon)."""
        await self.connection.execute(
            "DELETE FROM rite_runs WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # First-clear unlock flag (gates Writ selection)
    # ------------------------------------------------------------------

    async def has_first_clear(self, user_id: str, server_id: str) -> bool:
        async with self.connection.execute(
            "SELECT has_first_clear FROM rite_progress WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row and row["has_first_clear"])

    async def set_first_clear(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            """INSERT INTO rite_progress (user_id, server_id, has_first_clear)
               VALUES (?, ?, 1)
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                   has_first_clear = 1""",
            (user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Artefact slot (single equipped item, overwritten on each new drop)
    # ------------------------------------------------------------------

    async def get_artefact(self, user_id: str, server_id: str) -> dict | None:
        async with self.connection.execute(
            "SELECT artefact_key, roll_1, roll_2, roll_3 FROM player_artefacts "
            "WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def set_artefact(
        self,
        user_id: str,
        server_id: str,
        artefact_key: str,
        roll_1: float = 0.0,
        roll_2: float = 0.0,
        roll_3: float = 0.0,
    ) -> None:
        """Equips a newly-dropped artefact, overwriting whatever was equipped before."""
        await self.connection.execute(
            """INSERT INTO player_artefacts (user_id, server_id, artefact_key, roll_1, roll_2, roll_3)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                   artefact_key = excluded.artefact_key,
                   roll_1 = excluded.roll_1,
                   roll_2 = excluded.roll_2,
                   roll_3 = excluded.roll_3""",
            (user_id, server_id, artefact_key, roll_1, roll_2, roll_3),
        )
        await self.connection.commit()
