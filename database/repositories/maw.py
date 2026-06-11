"""
database/repositories/maw.py — Maw of Infinity data layer.

Schema note: `last_fight_ts` tracks the 20-hour fight cooldown. Existing
installs had this column as `last_damage_check`; the startup migration in
bot.py renames it so both old and new installs converge on `last_fight_ts`.
The legacy `boost_used_at` column is unused but retained in old DBs.
"""

from typing import Optional

import aiosqlite


class MawRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_record(self, user_id: str, cycle_id: int) -> Optional[dict]:
        cursor = await self.connection.execute(
            """SELECT signup_timestamp, last_fight_ts, damage_dealt,
                      rewards_collected,
                      COALESCE(fights_this_cycle, 0)
               FROM maw_participants WHERE user_id = ? AND cycle_id = ?""",
            (user_id, cycle_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "signup_timestamp": row[0],
            "last_fight_ts": row[1],  # last_damage_check repurposed; 0 = never fought
            "damage_dealt": row[2],
            "rewards_collected": row[3],
            "fights_this_cycle": row[4],
        }

    async def sign_up(self, user_id: str, cycle_id: int, now_ts: int) -> None:
        await self.connection.execute(
            """INSERT INTO maw_participants
               (user_id, cycle_id, signup_timestamp, last_fight_ts,
                damage_dealt, fights_this_cycle)
               VALUES (?, ?, ?, 0, 0, 0)""",
            (user_id, cycle_id, now_ts),
        )
        await self.connection.commit()

    async def add_damage(
        self, user_id: str, cycle_id: int, damage: int, now_ts: int
    ) -> None:
        """Adds damage from one completed fight and records the fight timestamp."""
        await self.connection.execute(
            """UPDATE maw_participants
               SET damage_dealt       = damage_dealt + ?,
                   last_fight_ts      = ?,
                   fights_this_cycle  = fights_this_cycle + 1
               WHERE user_id = ? AND cycle_id = ?""",
            (damage, now_ts, user_id, cycle_id),
        )
        await self.connection.commit()

    async def get_cycle_total_damage(self, cycle_id: int) -> int:
        """Total damage dealt to the Maw across all participants this cycle."""
        cursor = await self.connection.execute(
            "SELECT COALESCE(SUM(damage_dealt), 0) FROM maw_participants WHERE cycle_id = ?",
            (cycle_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_top_n(self, cycle_id: int, n: int = 3) -> list[str]:
        """Returns up to n user_ids ordered by damage_dealt DESC."""
        cursor = await self.connection.execute(
            """SELECT user_id FROM maw_participants
               WHERE cycle_id = ? ORDER BY damage_dealt DESC LIMIT ?""",
            (cycle_id, n),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def mark_rewards_collected(self, user_id: str, cycle_id: int) -> None:
        await self.connection.execute(
            "UPDATE maw_participants SET rewards_collected = 1 WHERE user_id = ? AND cycle_id = ?",
            (user_id, cycle_id),
        )
        await self.connection.commit()

    async def count_participants(self, cycle_id: int) -> int:
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM maw_participants WHERE cycle_id = ?",
            (cycle_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
