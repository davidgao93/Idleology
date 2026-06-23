"""
database/repositories/quests.py — Quest Board, Contracts, Horizon, and Check-in data layer.
"""

from __future__ import annotations

from datetime import datetime

from database.base import BaseRepository


class QuestsRepository(BaseRepository):
    async def create_tables(self) -> None:
        """Ensure all quest tables exist."""
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS quest_board (
                user_id TEXT NOT NULL,
                server_id TEXT NOT NULL,
                slot INTEGER NOT NULL,
                quest_id TEXT NOT NULL,
                tier INTEGER NOT NULL,
                free_reroll_used INTEGER DEFAULT 0,
                board_rolled_at TEXT,
                PRIMARY KEY (user_id, server_id, slot)
            )
            """
        )
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS quest_contracts (
                user_id TEXT NOT NULL,
                server_id TEXT NOT NULL,
                slot INTEGER NOT NULL,
                quest_id TEXT NOT NULL,
                tier INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                goal INTEGER NOT NULL,
                locked_at TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                turned_in INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, server_id, slot)
            )
            """
        )
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS quest_horizon (
                user_id TEXT NOT NULL,
                server_id TEXT NOT NULL,
                path_id TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                goal INTEGER NOT NULL,
                locked_at TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                turned_in INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, server_id)
            )
            """
        )
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS quest_meta (
                user_id TEXT PRIMARY KEY,
                tokens INTEGER DEFAULT 0,
                veteran_unlocked INTEGER DEFAULT 0,
                extra_slot_unlocked INTEGER DEFAULT 0,
                horizon_boost_uses INTEGER DEFAULT 0,
                checkin_day INTEGER DEFAULT 0,
                checkin_last_time TEXT,
                enrichment_unlocked INTEGER DEFAULT 0,
                prospector_unlocked INTEGER DEFAULT 0
            )
            """
        )
        # Migrations for existing databases
        for col, defval in (
            ("enrichment_unlocked", "0"),
            ("prospector_unlocked", "0"),
        ):
            try:
                await self.connection.execute(
                    f"ALTER TABLE quest_meta ADD COLUMN {col} INTEGER DEFAULT {defval}"
                )
            except Exception:
                pass  # column already exists
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    async def ensure_meta(self, user_id: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO quest_meta (user_id) VALUES (?)",
            (user_id,),
        )
        await self.connection.commit()

    async def get_meta(self, user_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT user_id, tokens, veteran_unlocked, extra_slot_unlocked, "
            "horizon_boost_uses, checkin_day, checkin_last_time, "
            "enrichment_unlocked, prospector_unlocked "
            "FROM quest_meta WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return {
                "user_id": user_id,
                "tokens": 0,
                "veteran_unlocked": 0,
                "extra_slot_unlocked": 0,
                "horizon_boost_uses": 0,
                "checkin_day": 0,
                "checkin_last_time": None,
                "enrichment_unlocked": 0,
                "prospector_unlocked": 0,
            }
        return {
            "user_id": row["user_id"],
            "tokens": row["tokens"],
            "veteran_unlocked": row["veteran_unlocked"],
            "extra_slot_unlocked": row["extra_slot_unlocked"],
            "horizon_boost_uses": row["horizon_boost_uses"],
            "checkin_day": row["checkin_day"],
            "checkin_last_time": row["checkin_last_time"],
            "enrichment_unlocked": row["enrichment_unlocked"],
            "prospector_unlocked": row["prospector_unlocked"],
        }

    async def add_tokens(self, user_id: str, amount: int) -> None:
        await self.connection.execute(
            "UPDATE quest_meta SET tokens = tokens + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def spend_tokens(self, user_id: str, amount: int) -> bool:
        meta = await self.get_meta(user_id)
        if meta["tokens"] < amount:
            return False
        await self.connection.execute(
            "UPDATE quest_meta SET tokens = tokens - ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()
        return True

    async def set_meta_field(self, user_id: str, field: str, value) -> None:
        """Generic field setter for quest_meta boolean/integer fields."""
        allowed = {
            "veteran_unlocked",
            "extra_slot_unlocked",
            "horizon_boost_uses",
            "enrichment_unlocked",
            "prospector_unlocked",
        }
        if field not in allowed:
            raise ValueError(f"Invalid meta field: {field}")
        await self.connection.execute(
            f"UPDATE quest_meta SET {field} = ? WHERE user_id = ?",
            (value, user_id),
        )
        await self.connection.commit()

    async def decrement_horizon_boost(self, user_id: str) -> None:
        await self.connection.execute(
            "UPDATE quest_meta SET horizon_boost_uses = MAX(0, horizon_boost_uses - 1) WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Board (pre-contract browsing state)
    # ------------------------------------------------------------------

    async def get_board(self, user_id: str, server_id: str) -> list:
        cursor = await self.connection.execute(
            "SELECT slot, quest_id, tier, free_reroll_used, board_rolled_at "
            "FROM quest_board WHERE user_id = ? AND server_id = ? ORDER BY slot",
            (user_id, server_id),
        )
        rows = await cursor.fetchall()
        return [
            {
                "slot": r["slot"],
                "quest_id": r["quest_id"],
                "tier": r["tier"],
                "free_reroll_used": r["free_reroll_used"],
                "board_rolled_at": r["board_rolled_at"],
            }
            for r in rows
        ]

    async def set_board_slot(
        self, user_id: str, server_id: str, slot: int, quest_id: str, tier: int
    ) -> None:
        now = datetime.now().isoformat()
        await self.connection.execute(
            """INSERT OR REPLACE INTO quest_board
               (user_id, server_id, slot, quest_id, tier, free_reroll_used, board_rolled_at)
               VALUES (?, ?, ?, ?, ?, 0, ?)""",
            (user_id, server_id, slot, quest_id, tier, now),
        )
        await self.connection.commit()

    async def mark_free_reroll_used(
        self, user_id: str, server_id: str, slot: int
    ) -> None:
        await self.connection.execute(
            "UPDATE quest_board SET free_reroll_used = 1 WHERE user_id = ? AND server_id = ? AND slot = ?",
            (user_id, server_id, slot),
        )
        await self.connection.commit()

    async def update_board_slot_quest(
        self, user_id: str, server_id: str, slot: int, quest_id: str, tier: int
    ) -> None:
        """Updates quest_id and tier for an existing board slot (reroll without resetting free_reroll_used)."""
        await self.connection.execute(
            "UPDATE quest_board SET quest_id = ?, tier = ? WHERE user_id = ? AND server_id = ? AND slot = ?",
            (quest_id, tier, user_id, server_id, slot),
        )
        await self.connection.commit()

    async def clear_board(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "DELETE FROM quest_board WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Contracts
    # ------------------------------------------------------------------

    async def get_contracts(self, user_id: str, server_id: str) -> list:
        cursor = await self.connection.execute(
            "SELECT slot, quest_id, tier, progress, goal, locked_at, completed, turned_in "
            "FROM quest_contracts WHERE user_id = ? AND server_id = ? ORDER BY slot",
            (user_id, server_id),
        )
        rows = await cursor.fetchall()
        return [
            {
                "slot": r["slot"],
                "quest_id": r["quest_id"],
                "tier": r["tier"],
                "progress": r["progress"],
                "goal": r["goal"],
                "locked_at": r["locked_at"],
                "completed": r["completed"],
                "turned_in": r["turned_in"],
            }
            for r in rows
        ]

    async def set_contracts_from_board(self, user_id: str, server_id: str) -> None:
        """Copy all board slots into contracts table (sets locked_at = now)."""
        board = await self.get_board(user_id, server_id)
        now = datetime.now().isoformat()
        for row in board:
            # Determine goal from the quest data
            from core.quests.data import DAILY_QUESTS

            quest_def = next(
                (q for q in DAILY_QUESTS if q["id"] == row["quest_id"]), None
            )
            if quest_def is None:
                continue
            if quest_def["goals"] == "banded":
                # Can't determine player level here; use a placeholder - caller must handle separately
                g1, g3 = 5, 15
            else:
                g1 = quest_def["goals"][1]
                g3 = quest_def["goals"][3]
            goal = g1 if row["tier"] == 1 else g3

            await self.connection.execute(
                """INSERT OR REPLACE INTO quest_contracts
                   (user_id, server_id, slot, quest_id, tier, progress, goal, locked_at, completed, turned_in)
                   VALUES (?, ?, ?, ?, ?, 0, ?, ?, 0, 0)""",
                (
                    user_id,
                    server_id,
                    row["slot"],
                    row["quest_id"],
                    row["tier"],
                    goal,
                    now,
                ),
            )
        await self.connection.commit()

    async def set_contract_slot(
        self,
        user_id: str,
        server_id: str,
        slot: int,
        quest_id: str,
        tier: int,
        goal: int,
    ) -> None:
        """Insert or replace a specific contract slot."""
        now = datetime.now().isoformat()
        await self.connection.execute(
            """INSERT OR REPLACE INTO quest_contracts
               (user_id, server_id, slot, quest_id, tier, progress, goal, locked_at, completed, turned_in)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?, 0, 0)""",
            (user_id, server_id, slot, quest_id, tier, goal, now),
        )
        await self.connection.commit()

    async def tick_contract_progress(
        self, user_id: str, server_id: str, quest_id: str, amount: int = 1
    ) -> list:
        """Increment progress on all matching active (not turned_in) contracts. Returns updated rows."""
        cursor = await self.connection.execute(
            "SELECT slot, quest_id, tier, progress, goal, locked_at, completed, turned_in "
            "FROM quest_contracts WHERE user_id = ? AND server_id = ? AND quest_id = ? AND turned_in = 0",
            (user_id, server_id, quest_id),
        )
        rows = await cursor.fetchall()
        updated = []
        for r in rows:
            slot = r["slot"]
            new_progress = r["progress"] + amount
            completed = 1 if new_progress >= r["goal"] else 0
            await self.connection.execute(
                "UPDATE quest_contracts SET progress = ?, completed = ? "
                "WHERE user_id = ? AND server_id = ? AND slot = ?",
                (new_progress, completed, user_id, server_id, slot),
            )
            updated.append(
                {
                    "slot": slot,
                    "quest_id": r["quest_id"],
                    "tier": r["tier"],
                    "progress": new_progress,
                    "goal": r["goal"],
                    "locked_at": r["locked_at"],
                    "completed": completed,
                    "turned_in": r["turned_in"],
                }
            )
        if updated:
            await self.connection.commit()
        return updated

    async def complete_contract(self, user_id: str, server_id: str, slot: int) -> None:
        await self.connection.execute(
            "UPDATE quest_contracts SET turned_in = 1 WHERE user_id = ? AND server_id = ? AND slot = ?",
            (user_id, server_id, slot),
        )
        await self.connection.commit()

    async def abandon_contract(self, user_id: str, server_id: str, slot: int) -> None:
        await self.connection.execute(
            "DELETE FROM quest_contracts WHERE user_id = ? AND server_id = ? AND slot = ?",
            (user_id, server_id, slot),
        )
        await self.connection.commit()

    async def restore_free_reroll(
        self, user_id: str, server_id: str, slot: int
    ) -> None:
        """Restores the free reroll on a contract slot (for shop use)."""
        await self.connection.execute(
            "UPDATE quest_board SET free_reroll_used = 0 WHERE user_id = ? AND server_id = ? AND slot = ?",
            (user_id, server_id, slot),
        )
        await self.connection.commit()

    async def reset_board_cooldown(self, user_id: str, server_id: str) -> None:
        """Sets all contract locked_at to an old timestamp (clears cooldown)."""
        old_time = "2000-01-01T00:00:00"
        await self.connection.execute(
            "UPDATE quest_contracts SET locked_at = ? WHERE user_id = ? AND server_id = ?",
            (old_time, user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Horizon
    # ------------------------------------------------------------------

    async def get_horizon(self, user_id: str, server_id: str) -> dict | None:
        cursor = await self.connection.execute(
            "SELECT path_id, progress, goal, locked_at, completed, turned_in "
            "FROM quest_horizon WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "path_id": row["path_id"],
            "progress": row["progress"],
            "goal": row["goal"],
            "locked_at": row["locked_at"],
            "completed": row["completed"],
            "turned_in": row["turned_in"],
        }

    async def set_horizon(
        self, user_id: str, server_id: str, path_id: str, goal: int
    ) -> None:
        now = datetime.now().isoformat()
        await self.connection.execute(
            """INSERT OR REPLACE INTO quest_horizon
               (user_id, server_id, path_id, progress, goal, locked_at, completed, turned_in)
               VALUES (?, ?, ?, 0, ?, ?, 0, 0)""",
            (user_id, server_id, path_id, goal, now),
        )
        await self.connection.commit()

    async def tick_horizon_progress(
        self, user_id: str, server_id: str, amount: int = 1
    ) -> dict | None:
        cursor = await self.connection.execute(
            "SELECT path_id, progress, goal, locked_at, completed, turned_in "
            "FROM quest_horizon WHERE user_id = ? AND server_id = ? AND turned_in = 0",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        new_progress = row["progress"] + amount
        completed = 1 if new_progress >= row["goal"] else 0
        await self.connection.execute(
            "UPDATE quest_horizon SET progress = ?, completed = ? WHERE user_id = ? AND server_id = ?",
            (new_progress, completed, user_id, server_id),
        )
        await self.connection.commit()
        return {
            "path_id": row["path_id"],
            "progress": new_progress,
            "goal": row["goal"],
            "locked_at": row["locked_at"],
            "completed": completed,
            "turned_in": row["turned_in"],
        }

    async def complete_horizon(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "UPDATE quest_horizon SET turned_in = 1 WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def abandon_horizon(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "DELETE FROM quest_horizon WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Check-in
    # ------------------------------------------------------------------

    async def get_checkin_day(self, user_id: str) -> int:
        meta = await self.get_meta(user_id)
        return meta["checkin_day"]

    async def advance_checkin(self, user_id: str) -> None:
        meta = await self.get_meta(user_id)
        current = meta["checkin_day"]
        if current == 0:
            next_day = 1
        elif current >= 14:
            next_day = 1  # reset track
        else:
            next_day = current + 1
        now = datetime.now().isoformat()
        await self.connection.execute(
            "UPDATE quest_meta SET checkin_day = ?, checkin_last_time = ? WHERE user_id = ?",
            (next_day, now, user_id),
        )
        await self.connection.commit()

    async def get_checkin_last_time(self, user_id: str) -> str | None:
        meta = await self.get_meta(user_id)
        return meta["checkin_last_time"]
