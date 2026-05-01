from __future__ import annotations

from typing import Optional

import aiosqlite


class BossPartyRepository:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def get_active(self, user_id: str, server_id: str) -> Optional[dict]:
        """Returns the active boss party row, or None."""
        cursor = await self.connection.execute(
            """SELECT id, attacker_id, tank_id, healer_id,
                      boss_name, boss_max_hp, start_time
               FROM boss_party_dispatch
               WHERE user_id = ? AND server_id = ?""",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id":           row[0],
            "attacker_id":  row[1],
            "tank_id":      row[2],
            "healer_id":    row[3],
            "boss_name":    row[4],
            "boss_max_hp":  row[5],
            "start_time":   row[6],
        }

    async def create(
        self,
        user_id: str,
        server_id: str,
        attacker_id: int,
        tank_id: int,
        healer_id: int,
        boss_name: str,
        boss_max_hp: int,
        start_time: str,
    ) -> None:
        await self.connection.execute(
            """INSERT INTO boss_party_dispatch
               (user_id, server_id, attacker_id, tank_id, healer_id,
                boss_name, boss_max_hp, start_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, server_id, attacker_id, tank_id, healer_id,
             boss_name, boss_max_hp, start_time),
        )
        await self.connection.commit()

    async def delete(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "DELETE FROM boss_party_dispatch WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()
