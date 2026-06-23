from typing import Any, Dict, List, Optional
import json


from database.base import BaseRepository

# Safelists for dynamically-named identifiers (SQLite doesn't support parameterized
# table/column names, so we validate against known-good values instead).
_SKILL_TABLES = frozenset({"mining", "fishing", "woodcutting"})
_SKILL_COLUMNS = frozenset(
    {
        # Raw gathering resources
        "iron",
        "coal",
        "gold",
        "platinum",
        "idea",
        "desiccated_bones",
        "regular_bones",
        "sturdy_bones",
        "reinforced_bones",
        "titanium_bones",
        "oak_logs",
        "willow_logs",
        "mahogany_logs",
        "magic_logs",
        "idea_logs",
        # Processed (converter building outputs)
        "iron_bar",
        "steel_bar",
        "gold_bar",
        "platinum_bar",
        "idea_bar",
        "oak_plank",
        "willow_plank",
        "mahogany_plank",
        "magic_plank",
        "idea_plank",
        "desiccated_essence",
        "regular_essence",
        "sturdy_essence",
        "reinforced_essence",
        "titanium_essence",
    }
)
_UBER_COLUMNS = frozenset({"capricious_carp", "blessed_bismuth", "sparkling_sprig"})


class AlchemyRepository(BaseRepository):
    _passive_duration_col_added: bool = False

    async def _ensure_passive_duration_column(self) -> None:
        """Idempotent: adds passive_duration column to potion_passives if not yet present."""
        if AlchemyRepository._passive_duration_col_added:
            return
        try:
            await self.connection.execute(
                "ALTER TABLE potion_passives ADD COLUMN passive_duration REAL DEFAULT 2.0"
            )
            await self.connection.commit()
        except Exception:
            pass  # column already exists
        AlchemyRepository._passive_duration_col_added = True

    # ------------------------------------------------------------------
    # Alchemy Level
    # ------------------------------------------------------------------

    async def initialize_if_new(self, user_id: str) -> bool:
        """Insert a level-1 row if none exists. Returns True if this is a new user."""
        async with self.connection.execute(
            "SELECT COUNT(*) AS cnt FROM alchemy_data WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row["cnt"] == 0:
            await self.connection.execute(
                "INSERT INTO alchemy_data (user_id, level) VALUES (?, 1)", (user_id,)
            )
            await self.connection.commit()
            return True
        return False

    async def _ensure_row(self, user_id: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO alchemy_data (user_id, level) VALUES (?, 1)",
            (user_id,),
        )
        await self.connection.commit()

    async def get_level(self, user_id: str) -> int:
        await self._ensure_row(user_id)
        async with self.connection.execute(
            "SELECT level FROM alchemy_data WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        level = row["level"] if row else 1
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
            "UPDATE alchemy_data SET level = ? WHERE user_id = ?", (level, user_id)
        )
        await self.connection.commit()

    async def get_free_roll_used(self, user_id: str) -> bool:
        await self._ensure_row(user_id)
        async with self.connection.execute(
            "SELECT free_roll_used FROM alchemy_data WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row["free_roll_used"]) if row else False

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
        """Returns [{slot, passive_type, passive_value, passive_duration}, ...] ordered by slot."""
        await self._ensure_passive_duration_column()
        async with self.connection.execute(
            "SELECT slot, passive_type, passive_value, passive_duration FROM potion_passives "
            "WHERE user_id = ? ORDER BY slot",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "slot": r["slot"],
                "passive_type": r["passive_type"],
                "passive_value": r["passive_value"],
                "passive_duration": r["passive_duration"] if r["passive_duration"] is not None else 2.0,
            }
            for r in rows
        ]

    async def set_passive(
        self,
        user_id: str,
        slot: int,
        passive_type: str,
        passive_value: float,
        passive_duration: float = 2.0,
    ) -> None:
        await self._ensure_passive_duration_column()
        await self.connection.execute(
            """INSERT INTO potion_passives (user_id, slot, passive_type, passive_value, passive_duration)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, slot) DO UPDATE SET
                   passive_type = excluded.passive_type,
                   passive_value = excluded.passive_value,
                   passive_duration = excluded.passive_duration""",
            (user_id, slot, passive_type, passive_value, passive_duration),
        )
        await self.connection.commit()

    async def delete_passive(self, user_id: str, slot: int) -> None:
        await self.connection.execute(
            "DELETE FROM potion_passives WHERE user_id = ? AND slot = ?",
            (user_id, slot),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Transmutation helpers
    # ------------------------------------------------------------------

    async def get_resource_amount(
        self, user_id: str, server_id: str, skill_type: str, col: str
    ) -> int:
        """Reads a single resource column from the relevant skill table."""
        if skill_type not in _SKILL_TABLES or col not in _SKILL_COLUMNS:
            raise ValueError(f"Invalid skill_type/col: {skill_type!r}/{col!r}")
        async with self.connection.execute(
            f"SELECT {col} FROM {skill_type} WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row[col] if row else 0

    async def transmute(
        self,
        user_id: str,
        server_id: str,
        skill_type: str,
        src_col: str,
        src_delta: int,
        dst_col: str,
        dst_delta: int,
    ) -> None:
        """Atomically deduct src and credit dst in the skill table."""
        if (
            skill_type not in _SKILL_TABLES
            or src_col not in _SKILL_COLUMNS
            or dst_col not in _SKILL_COLUMNS
        ):
            raise ValueError(
                f"Invalid transmute identifiers: {skill_type!r}/{src_col!r}/{dst_col!r}"
            )
        await self.connection.execute(
            f"UPDATE {skill_type} "
            f"SET {src_col} = {src_col} + ?, {dst_col} = {dst_col} + ? "
            f"WHERE user_id = ? AND server_id = ?",
            (src_delta, dst_delta, user_id, server_id),
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
        return row["cosmic_dust"] if row else 0

    async def modify_cosmic_dust(self, user_id: str, delta: int) -> None:
        await self._ensure_row(user_id)
        await self.connection.execute(
            "UPDATE alchemy_data SET cosmic_dust = cosmic_dust + ? WHERE user_id = ?",
            (delta, user_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Synthesis Queue (multi-slot: 1, 2, 3)
    # ------------------------------------------------------------------

    def _queue_table(self, slot: int) -> str:
        if slot == 2:
            return "synthesis_queue_2"
        if slot == 3:
            return "synthesis_queue_3"
        return "synthesis_queue"

    async def get_synthesis_queue(self, user_id: str, slot: int = 1):
        """Returns (item_type, quantity, start_time) or None."""
        table = self._queue_table(slot)
        async with self.connection.execute(
            f"SELECT item_type, quantity, start_time FROM {table} WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            return await cursor.fetchone()

    async def get_all_queues(self, user_id: str) -> list:
        """Returns list of (slot, item_type, quantity, start_time) for all active queues."""
        result = []
        for slot in (1, 2, 3):
            row = await self.get_synthesis_queue(user_id, slot)
            if row:
                result.append((slot, row["item_type"], row["quantity"], row["start_time"]))
        return result

    async def start_disenchant(
        self,
        user_id: str,
        item_type: str,
        quantity: int,
        start_time: str,
        slot: int = 1,
    ) -> None:
        """Insert or replace the active disenchant task for this user in the given slot."""
        table = self._queue_table(slot)
        await self.connection.execute(
            f"""INSERT INTO {table} (user_id, item_type, quantity, start_time)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   item_type  = excluded.item_type,
                   quantity   = excluded.quantity,
                   start_time = excluded.start_time""",
            (user_id, item_type, quantity, start_time),
        )
        await self.connection.commit()

    async def clear_synthesis_queue(self, user_id: str, slot: int = 1) -> None:
        table = self._queue_table(slot)
        await self.connection.execute(
            f"DELETE FROM {table} WHERE user_id = ?", (user_id,)
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Uber material helpers (for disenchanting elemental keys)
    # ------------------------------------------------------------------

    async def get_uber_material(self, user_id: str, server_id: str, col: str) -> int:
        """Reads a single elemental key column from gathering_mastery."""
        if col not in _UBER_COLUMNS:
            raise ValueError(f"Invalid elemental key column: {col!r}")
        async with self.connection.execute(
            f"SELECT {col} FROM gathering_mastery WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row[col] if row else 0

    async def deduct_uber_material(
        self, user_id: str, server_id: str, col: str, amount: int
    ) -> None:
        """Deducts from an elemental key column in gathering_mastery."""
        if col not in _UBER_COLUMNS:
            raise ValueError(f"Invalid elemental key column: {col!r}")
        await self.connection.execute(
            f"UPDATE gathering_mastery SET {col} = {col} - ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Essence helpers (for disenchanting essences)
    # ------------------------------------------------------------------

    async def get_essence_quantity(self, user_id: str, essence_type: str) -> int:
        async with self.connection.execute(
            "SELECT quantity FROM player_essences WHERE user_id = ? AND essence_type = ?",
            (user_id, essence_type),
        ) as cursor:
            row = await cursor.fetchone()
        return row["quantity"] if row else 0

    async def deduct_essence(
        self, user_id: str, essence_type: str, amount: int
    ) -> None:
        await self.connection.execute(
            "UPDATE player_essences SET quantity = quantity - ? WHERE user_id = ? AND essence_type = ?",
            (amount, user_id, essence_type),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Potion Distillation sessions (9-step Sage Elixir style crafting)
    # Session is stored as JSON in the `data` column for flexibility.
    # ------------------------------------------------------------------

    async def get_distillation(
        self, user_id: str, server_id: str
    ) -> Optional[Dict[str, Any]]:
        """Returns the active distillation session or None.
        The returned dict has keys: step, data (already parsed JSON dict), started_at.
        """
        async with self.connection.execute(
            "SELECT step, data, started_at FROM potion_distillations WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return {
            "step": row["step"],
            "data": json.loads(row["data"]) if row["data"] else {},
            "started_at": row["started_at"],
        }

    async def upsert_distillation(
        self, user_id: str, server_id: str, step: int, data: Dict[str, Any]
    ) -> None:
        """Create or update the distillation session for this user/server."""
        data_json = json.dumps(data)
        await self.connection.execute(
            """INSERT INTO potion_distillations (user_id, server_id, step, data)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                   step = excluded.step,
                   data = excluded.data""",
            (user_id, server_id, step, data_json),
        )
        await self.connection.commit()

    async def delete_distillation(self, user_id: str, server_id: str) -> None:
        """Abandon / clear an in-progress distillation."""
        await self.connection.execute(
            "DELETE FROM potion_distillations WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()
