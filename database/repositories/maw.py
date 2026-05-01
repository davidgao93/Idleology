import aiosqlite
from typing import Optional


class MawRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_record(self, user_id: str, cycle_id: int) -> Optional[dict]:
        cursor = await self.connection.execute(
            """SELECT signup_timestamp, last_damage_check, damage_dealt, boost_used_at, rewards_collected
               FROM maw_participants WHERE user_id = ? AND cycle_id = ?""",
            (user_id, cycle_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "signup_timestamp": row[0],
            "last_damage_check": row[1],
            "damage_dealt": row[2],
            "boost_used_at": row[3],
            "rewards_collected": row[4],
        }

    async def sign_up(self, user_id: str, cycle_id: int, now_ts: int) -> None:
        await self.connection.execute(
            """INSERT INTO maw_participants (user_id, cycle_id, signup_timestamp, last_damage_check, damage_dealt)
               VALUES (?, ?, ?, ?, 0)""",
            (user_id, cycle_id, now_ts, now_ts),
        )
        await self.connection.commit()

    async def update_damage(self, user_id: str, cycle_id: int, damage_dealt: int, last_damage_check: int) -> None:
        await self.connection.execute(
            """UPDATE maw_participants SET damage_dealt = ?, last_damage_check = ?
               WHERE user_id = ? AND cycle_id = ?""",
            (damage_dealt, last_damage_check, user_id, cycle_id),
        )
        await self.connection.commit()

    async def set_boost_used(self, user_id: str, cycle_id: int, damage_dealt: int, boost_ts: int) -> None:
        await self.connection.execute(
            """UPDATE maw_participants SET boost_used_at = ?, damage_dealt = ?
               WHERE user_id = ? AND cycle_id = ?""",
            (boost_ts, damage_dealt, user_id, cycle_id),
        )
        await self.connection.commit()

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
