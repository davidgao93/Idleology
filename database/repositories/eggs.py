from datetime import datetime, timezone

from database.base import BaseRepository

_EGG_CAP = 20


class EggsRepository(BaseRepository):
    # ------------------------------------------------------------------ #
    #  Monster Egg Inventory
    # ------------------------------------------------------------------ #

    async def get_egg_count(self, user_id: str) -> int:
        cursor = await self.connection.execute(
            "SELECT COUNT(*) AS cnt FROM monster_eggs WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_eggs(self, user_id: str) -> list:
        """Returns all egg rows as list of (id, egg_tier, monster_level, monster_name)."""
        cursor = await self.connection.execute(
            "SELECT id, egg_tier, monster_level, monster_name "
            "FROM monster_eggs WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        )
        return await cursor.fetchall()

    async def add_egg(
        self,
        user_id: str,
        egg_tier: str,
        monster_level: int,
        monster_name: str,
    ) -> bool:
        """Inserts an egg. Returns False and does nothing if cap is reached."""
        count = await self.get_egg_count(user_id)
        if count >= _EGG_CAP:
            return False
        await self.connection.execute(
            "INSERT INTO monster_eggs (user_id, egg_tier, monster_level, monster_name) "
            "VALUES (?, ?, ?, ?)",
            (user_id, egg_tier, monster_level, monster_name),
        )
        await self.connection.commit()
        return True

    async def delete_egg(self, egg_id: int) -> None:
        await self.connection.execute(
            "DELETE FROM monster_eggs WHERE id = ?", (egg_id,)
        )
        await self.connection.commit()

    async def get_egg_by_id(self, egg_id: int) -> tuple | None:
        cursor = await self.connection.execute(
            "SELECT id, user_id, egg_tier, monster_level, monster_name "
            "FROM monster_eggs WHERE id = ?",
            (egg_id,),
        )
        return await cursor.fetchone()

    # ------------------------------------------------------------------ #
    #  Hatchery Incubation (one slot per user+server)
    # ------------------------------------------------------------------ #

    async def get_incubation(self, user_id: str, server_id: str) -> dict | None:
        cursor = await self.connection.execute(
            "SELECT egg_id, egg_tier, monster_level, monster_name, start_time, duration_seconds "
            "FROM hatchery_incubation WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "egg_id": row["egg_id"],
                "egg_tier": row["egg_tier"],
                "monster_level": row["monster_level"],
                "monster_name": row["monster_name"],
                "start_time": row["start_time"],
                "duration_seconds": row["duration_seconds"],
            }
        return None

    async def start_incubation(
        self,
        user_id: str,
        server_id: str,
        egg_id: int,
        egg_tier: str,
        monster_level: int,
        monster_name: str,
        duration_seconds: int,
    ) -> None:
        start_time = datetime.now(timezone.utc).isoformat()
        await self.connection.execute(
            """INSERT INTO hatchery_incubation
               (user_id, server_id, egg_id, egg_tier, monster_level, monster_name, start_time, duration_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                server_id,
                egg_id,
                egg_tier,
                monster_level,
                monster_name,
                start_time,
                duration_seconds,
            ),
        )
        await self.connection.commit()

    async def complete_incubation(self, user_id: str, server_id: str) -> None:
        """Removes the active incubation row once the player clicks Release."""
        await self.connection.execute(
            "DELETE FROM hatchery_incubation WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------ #
    #  Incubated Encounter Queue
    # ------------------------------------------------------------------ #

    async def queue_incubated_encounter(
        self,
        user_id: str,
        monster_name: str,
        monster_level: int,
        egg_tier: str,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        await self.connection.execute(
            "INSERT INTO incubated_encounters (user_id, monster_name, monster_level, egg_tier, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, monster_name, monster_level, egg_tier, created_at),
        )
        await self.connection.commit()

    async def get_next_incubated(self, user_id: str) -> dict | None:
        """Returns the oldest queued incubated encounter, or None."""
        cursor = await self.connection.execute(
            "SELECT id, monster_name, monster_level, egg_tier "
            "FROM incubated_encounters WHERE user_id = ? ORDER BY id ASC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "monster_name": row["monster_name"],
                "monster_level": row["monster_level"],
                "egg_tier": row["egg_tier"],
            }
        return None

    async def consume_incubated_encounter(self, encounter_id: int) -> None:
        """Removes an encounter from the queue after it has been used."""
        await self.connection.execute(
            "DELETE FROM incubated_encounters WHERE id = ?", (encounter_id,)
        )
        await self.connection.commit()

    async def get_incubated_queue_count(self, user_id: str) -> int:
        cursor = await self.connection.execute(
            "SELECT COUNT(*) AS cnt FROM incubated_encounters WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
