import aiosqlite
from typing import Tuple
from core.minigames.mechanics import DelveMechanics

class DelveRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_profile(self, user_id: str, server_id: str) -> dict:
        """Fetches or creates the delve profile."""
        cursor = await self.connection.execute(
            "SELECT * FROM delve_progress WHERE user_id = ? AND server_id = ?",
            (user_id, server_id)
        )
        row = await cursor.fetchone()
        
        if not row:
            await self.connection.execute(
                "INSERT INTO delve_progress (user_id, server_id) VALUES (?, ?)",
                (user_id, server_id)
            )
            await self.connection.commit()
            return {
                'xp': 0, 'shards': 0, 
                'fuel_lvl': 1, 'struct_lvl': 1, 'sensor_lvl': 1
            }
            
        return {
            'xp': row[2], 'shards': row[3],
            'fuel_lvl': row[4], 'struct_lvl': row[5], 'sensor_lvl': row[6]
        }

    async def modify_shards(self, user_id: str, server_id: str, amount: int):
        await self.connection.execute(
            "UPDATE delve_progress SET obsidian_shards = obsidian_shards + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id)
        )
        await self.connection.commit()

    async def add_xp(self, user_id: str, server_id: str, amount: int) -> int:
            """
            Adds XP and returns the (old_level, new_level) to check for level-ups.
            """
            # Fetch current state first
            cursor = await self.connection.execute(
                "SELECT delve_xp FROM delve_progress WHERE user_id = ? AND server_id = ?",
                (user_id, server_id)
            )
            row = await cursor.fetchone()
            old_xp = row[0] if row else 0
            old_lvl = DelveMechanics.calculate_level_from_xp(old_xp)
            
            new_xp = old_xp + amount
            new_lvl = DelveMechanics.calculate_level_from_xp(new_xp)
            
            # Update DB
            await self.connection.execute(
                "UPDATE delve_progress SET delve_xp = ? WHERE user_id = ? AND server_id = ?",
                (new_xp, user_id, server_id)
            )
            await self.connection.commit()
            
            return old_lvl, new_lvl

    async def upgrade_stat(self, user_id: str, server_id: str, stat_col: str, cost: int):
        # Atomic deduction and level up
        await self.connection.execute(
            f"UPDATE delve_progress SET obsidian_shards = obsidian_shards - ?, {stat_col} = {stat_col} + 1 WHERE user_id = ? AND server_id = ?",
            (cost, user_id, server_id)
        )
        await self.connection.commit()