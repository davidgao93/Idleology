import json

import aiosqlite

# Matches the 60-item cap used by the six normal gear slots' inventories.
ARTEFACT_CAP = 60


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
    # Artefact inventory (multi-item; one may be equipped at a time)
    # ------------------------------------------------------------------

    async def get_artefact_inventory(self, user_id: str, server_id: str) -> list[dict]:
        """All artefacts owned by this player, equipped one first."""
        async with self.connection.execute(
            "SELECT item_id, artefact_key, roll_1, roll_2, roll_3, is_equipped "
            "FROM rite_artefact_items WHERE user_id = ? AND server_id = ? "
            "ORDER BY is_equipped DESC, item_id DESC",
            (user_id, server_id),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_equipped_artefact(self, user_id: str, server_id: str) -> dict | None:
        async with self.connection.execute(
            "SELECT item_id, artefact_key, roll_1, roll_2, roll_3, is_equipped "
            "FROM rite_artefact_items WHERE user_id = ? AND server_id = ? AND is_equipped = 1",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def count_artefacts(self, user_id: str, server_id: str) -> int:
        async with self.connection.execute(
            "SELECT COUNT(*) AS c FROM rite_artefact_items WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row["c"] if row else 0

    async def add_artefact(
        self,
        user_id: str,
        server_id: str,
        artefact_key: str,
        roll_1: float = 0.0,
        roll_2: float = 0.0,
        roll_3: float = 0.0,
        auto_equip: bool = False,
    ) -> int | None:
        """Adds a newly-dropped artefact to the inventory. Returns the new
        item_id, or None if the player is already at ARTEFACT_CAP (the drop
        is not inserted — caller must tell the player it was lost).
        auto_equip only takes effect if nothing is currently equipped (e.g.
        this is the player's first artefact ever)."""
        if await self.count_artefacts(user_id, server_id) >= ARTEFACT_CAP:
            return None

        equip_now = False
        if auto_equip:
            equip_now = await self.get_equipped_artefact(user_id, server_id) is None

        cursor = await self.connection.execute(
            """INSERT INTO rite_artefact_items
                   (user_id, server_id, artefact_key, roll_1, roll_2, roll_3, is_equipped)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, server_id, artefact_key, roll_1, roll_2, roll_3, int(equip_now)),
        )
        await self.connection.commit()
        return cursor.lastrowid

    async def equip_artefact(self, user_id: str, server_id: str, item_id: int) -> None:
        """Unequips whatever else was equipped, then equips item_id."""
        await self.connection.execute(
            "UPDATE rite_artefact_items SET is_equipped = 0 "
            "WHERE user_id = ? AND server_id = ? AND is_equipped = 1",
            (user_id, server_id),
        )
        await self.connection.execute(
            "UPDATE rite_artefact_items SET is_equipped = 1 WHERE item_id = ?",
            (item_id,),
        )
        await self.connection.commit()

    async def unequip_artefact(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "UPDATE rite_artefact_items SET is_equipped = 0 "
            "WHERE user_id = ? AND server_id = ? AND is_equipped = 1",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def discard_artefact(self, item_id: int) -> None:
        await self.connection.execute(
            "DELETE FROM rite_artefact_items WHERE item_id = ?", (item_id,)
        )
        await self.connection.commit()
