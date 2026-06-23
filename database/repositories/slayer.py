import json

import aiosqlite


class SlayerRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_profile(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT * FROM slayer_profiles WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if not row:
            await self.connection.execute(
                "INSERT INTO slayer_profiles (user_id, server_id) VALUES (?, ?)",
                (user_id, server_id),
            )
            await self.connection.execute(
                "INSERT INTO slayer_emblems (user_id, server_id) VALUES (?, ?)",
                (user_id, server_id),
            )
            await self.connection.commit()
            return await self.get_profile(user_id, server_id)

        return {
            "level": row["level"],
            "xp": row["xp"],
            "points": row["slayer_points"],
            "violent_essence": row["violent_essence"],
            "imbued_heart": row["imbued_heart"],
            "active_task_species": row["active_task_species"],
            "active_task_amount": row["active_task_amount"],
            "active_task_progress": row["active_task_progress"],
        }

    async def get_emblem(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT * FROM slayer_emblems WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if not row:
            return {}
        return {
            1: {"type": row["slot_1_type"], "tier": row["slot_1_tier"]},
            2: {"type": row["slot_2_type"], "tier": row["slot_2_tier"]},
            3: {"type": row["slot_3_type"], "tier": row["slot_3_tier"]},
            4: {"type": row["slot_4_type"], "tier": row["slot_4_tier"]},
            5: {"type": row["slot_5_type"], "tier": row["slot_5_tier"]},
        }

    async def assign_task(
        self, user_id: str, server_id: str, species: str, amount: int
    ):
        await self.connection.execute(
            "UPDATE slayer_profiles SET active_task_species = ?, active_task_amount = ?, active_task_progress = 0 WHERE user_id = ? AND server_id = ?",
            (species, amount, user_id, server_id),
        )
        await self.connection.commit()

    async def update_task_progress(self, user_id: str, server_id: str, amount: int):
        await self.connection.execute(
            "UPDATE slayer_profiles SET active_task_progress = active_task_progress + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def clear_task(self, user_id: str, server_id: str):
        await self.connection.execute(
            "UPDATE slayer_profiles SET active_task_species = NULL, active_task_amount = 0, active_task_progress = 0 WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def add_rewards(self, user_id: str, server_id: str, xp: int, points: int):
        await self.connection.execute(
            "UPDATE slayer_profiles SET xp = xp + ?, slayer_points = slayer_points + ? WHERE user_id = ? AND server_id = ?",
            (xp, points, user_id, server_id),
        )
        await self.connection.commit()

    async def update_level(self, user_id: str, server_id: str, new_level: int):
        await self.connection.execute(
            "UPDATE slayer_profiles SET level = ? WHERE user_id = ? AND server_id = ?",
            (new_level, user_id, server_id),
        )
        await self.connection.commit()

    async def modify_materials(
        self, user_id: str, server_id: str, col: str, amount: int
    ):
        await self.connection.execute(
            f"UPDATE slayer_profiles SET {col} = {col} + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def update_emblem_slot(
        self, user_id: str, server_id: str, slot: int, p_type: str, p_tier: int
    ):
        type_col = f"slot_{slot}_type"
        tier_col = f"slot_{slot}_tier"
        await self.connection.execute(
            f"UPDATE slayer_emblems SET {type_col} = ?, {tier_col} = ? WHERE user_id = ? AND server_id = ?",
            (p_type, p_tier, user_id, server_id),
        )
        await self.connection.commit()

    async def consume_material(
        self, user_id: str, server_id: str, col: str, amount: int
    ) -> bool:
        """
        Atomically attempts to deduct a material.
        Returns True if successful, False if insufficient balance.
        """
        cursor = await self.connection.execute(
            f"UPDATE slayer_profiles SET {col} = {col} - ? WHERE user_id = ? AND server_id = ? AND {col} >= ?",
            (amount, user_id, server_id, amount),
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def get_tree(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT nodes_owned, points_spent FROM slayer_tree WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if not row:
            return {"nodes_owned": {}, "points_spent": 0}
        return {
            "nodes_owned": json.loads(row["nodes_owned"]) if row["nodes_owned"] else {},
            "points_spent": row["points_spent"],
        }

    async def upsert_tree(
        self, user_id: str, server_id: str, nodes_owned: dict, points_spent: int
    ) -> None:
        await self.connection.execute(
            """INSERT INTO slayer_tree (user_id, server_id, nodes_owned, points_spent)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                 nodes_owned = excluded.nodes_owned,
                 points_spent = excluded.points_spent""",
            (user_id, server_id, json.dumps(nodes_owned), points_spent),
        )
        await self.connection.commit()

    async def reset_tree(self, user_id: str, server_id: str) -> int:
        """Clears the tree and returns points_spent before the reset (for refund calc)."""
        data = await self.get_tree(user_id, server_id)
        pts = data["points_spent"]
        await self.upsert_tree(user_id, server_id, {}, 0)
        return pts

    async def get_leaderboard(self, limit: int = 10):
        # Join with users table to get the player's name
        rows = await self.connection.execute(
            """
            SELECT u.name, s.level, s.xp 
            FROM slayer_profiles s 
            JOIN users u ON s.user_id = u.user_id AND s.server_id = u.server_id
            WHERE s.level > 1 
            ORDER BY s.level DESC, s.xp DESC 
            LIMIT ?
            """,
            (limit,),
        )
        async with rows as cursor:
            return await cursor.fetchall()
