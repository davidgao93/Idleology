import aiosqlite

class SlayerRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_profile(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT * FROM slayer_profiles WHERE user_id = ? AND server_id = ?", (user_id, server_id)
        )
        row = await cursor.fetchone()
        if not row:
            await self.connection.execute(
                "INSERT INTO slayer_profiles (user_id, server_id) VALUES (?, ?)", (user_id, server_id)
            )
            await self.connection.execute(
                "INSERT INTO slayer_emblems (user_id, server_id) VALUES (?, ?)", (user_id, server_id)
            )
            await self.connection.commit()
            return await self.get_profile(user_id, server_id)

        return {
            'level': row[2], 'xp': row[3], 'points': row[4], 
            'violent_essence': row[5], 'imbued_heart': row[6],
            'active_task_species': row[7], 'active_task_amount': row[8], 'active_task_progress': row[9]
        }

    async def get_emblem(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT * FROM slayer_emblems WHERE user_id = ? AND server_id = ?", (user_id, server_id)
        )
        row = await cursor.fetchone()
        if not row: return {}
        # Map row[2] through row[11] to dict
        return {
            1: {'type': row[2], 'tier': row[3]},
            2: {'type': row[4], 'tier': row[5]},
            3: {'type': row[6], 'tier': row[7]},
            4: {'type': row[8], 'tier': row[9]},
            5: {'type': row[10], 'tier': row[11]}
        }

    async def assign_task(self, user_id: str, server_id: str, species: str, amount: int):
        await self.connection.execute(
            "UPDATE slayer_profiles SET active_task_species = ?, active_task_amount = ?, active_task_progress = 0 WHERE user_id = ? AND server_id = ?",
            (species, amount, user_id, server_id)
        )
        await self.connection.commit()

    async def update_task_progress(self, user_id: str, server_id: str, amount: int):
        await self.connection.execute(
            "UPDATE slayer_profiles SET active_task_progress = active_task_progress + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id)
        )
        await self.connection.commit()

    async def clear_task(self, user_id: str, server_id: str):
        await self.connection.execute(
            "UPDATE slayer_profiles SET active_task_species = NULL, active_task_amount = 0, active_task_progress = 0 WHERE user_id = ? AND server_id = ?",
            (user_id, server_id)
        )
        await self.connection.commit()

    async def add_rewards(self, user_id: str, server_id: str, xp: int, points: int):
        await self.connection.execute(
            "UPDATE slayer_profiles SET xp = xp + ?, slayer_points = slayer_points + ? WHERE user_id = ? AND server_id = ?",
            (xp, points, user_id, server_id)
        )
        await self.connection.commit()
        
    async def update_level(self, user_id: str, server_id: str, new_level: int):
        await self.connection.execute(
            "UPDATE slayer_profiles SET level = ? WHERE user_id = ? AND server_id = ?",
            (new_level, user_id, server_id)
        )
        await self.connection.commit()

    async def modify_materials(self, user_id: str, server_id: str, col: str, amount: int):
        await self.connection.execute(
            f"UPDATE slayer_profiles SET {col} = {col} + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id)
        )
        await self.connection.commit()

    async def update_emblem_slot(self, user_id: str, server_id: str, slot: int, p_type: str, p_tier: int):
        type_col = f"slot_{slot}_type"
        tier_col = f"slot_{slot}_tier"
        await self.connection.execute(
            f"UPDATE slayer_emblems SET {type_col} = ?, {tier_col} = ? WHERE user_id = ? AND server_id = ?",
            (p_type, p_tier, user_id, server_id)
        )
        await self.connection.commit()

    async def consume_material(self, user_id: str, server_id: str, col: str, amount: int) -> bool:
        """
        Atomically attempts to deduct a material. 
        Returns True if successful, False if insufficient balance.
        """
        cursor = await self.connection.execute(
            f"UPDATE slayer_profiles SET {col} = {col} - ? WHERE user_id = ? AND server_id = ? AND {col} >= ?",
            (amount, user_id, server_id, amount)
        )
        await self.connection.commit()
        return cursor.rowcount > 0