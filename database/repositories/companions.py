# database/repositories/companions.py

import json
from typing import List, Optional, Tuple

import aiosqlite


class CompanionRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_all(self, user_id: str) -> List[Tuple]:
        """Fetches all companions for a user."""
        rows = await self.connection.execute(
            "SELECT * FROM companions WHERE user_id = ?", (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()

    async def get_active(self, user_id: str) -> List[Tuple]:
        """Fetches only active companions."""
        rows = await self.connection.execute(
            "SELECT * FROM companions WHERE user_id = ? AND is_active = 1", (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()

    async def get_by_id(self, companion_id: int) -> Optional[Tuple]:
        """Fetches a specific companion."""
        rows = await self.connection.execute(
            "SELECT * FROM companions WHERE id = ?", (companion_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def get_count(self, user_id: str) -> int:
        """Counts total companions owned (for 20 slot cap)."""
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM companions WHERE user_id = ?", (user_id,)
        )
        res = await rows.fetchone()
        return res[0] if res else 0

    async def add_companion(
        self,
        user_id: str,
        name: str,
        species: str,
        image: str,
        p_type: str,
        p_tier: int,
    ) -> None:
        """Adds a new companion."""
        await self.connection.execute(
            """INSERT INTO companions (user_id, name, species, image_url, passive_type, passive_tier) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, name, species, image, p_type, p_tier),
        )
        await self.connection.commit()

    async def delete_companion(self, companion_id: int, user_id: str) -> None:
        """Releases a companion."""
        await self.connection.execute(
            "DELETE FROM companions WHERE id = ? AND user_id = ?",
            (companion_id, user_id),
        )
        await self.connection.commit()

    async def set_active(
        self,
        user_id: str,
        companion_id: int,
        active: bool,
        max_active: int = 3,
    ) -> bool:
        """
        Toggles active state.
        Returns False if trying to activate more companions than the player's slot cap.

        Slot caps (pass the result of get_companion_slot_cap):
          level >= 40        → 1 slot
          level >= 80        → 2 slots
          ascension >= 20    → 3 slots
        """
        if active:
            # Check current active count against the caller-supplied cap
            rows = await self.connection.execute(
                "SELECT COUNT(*) FROM companions WHERE user_id = ? AND is_active = 1",
                (user_id,),
            )
            count = (await rows.fetchone())[0]
            if count >= max_active:
                return False

        val = 1 if active else 0
        await self.connection.execute(
            "UPDATE companions SET is_active = ? WHERE id = ? AND user_id = ?",
            (val, companion_id, user_id),
        )
        await self.connection.commit()
        return True

    async def add_exp(self, companion_id: int, amount: int) -> None:
        """Adds experience to a companion."""
        await self.connection.execute(
            "UPDATE companions SET exp = exp + ? WHERE id = ?", (amount, companion_id)
        )
        await self.connection.commit()

    async def level_up(self, companion_id: int) -> None:
        """Increments level."""
        await self.connection.execute(
            "UPDATE companions SET level = level + 1 WHERE id = ?", (companion_id,)
        )
        await self.connection.commit()

    async def update_passive(self, companion_id: int, p_type: str, p_tier: int) -> None:
        """Rerolls the passive."""
        await self.connection.execute(
            "UPDATE companions SET passive_type = ?, passive_tier = ? WHERE id = ?",
            (p_type, p_tier, companion_id),
        )
        await self.connection.commit()

    async def update_balanced_passive(
        self, companion_id: int, b_type: str, b_tier: int
    ) -> None:
        """Sets the balanced (secondary) passive from a Gemini Engram."""
        await self.connection.execute(
            "UPDATE companions SET balanced_passive = ?, balanced_passive_tier = ? WHERE id = ?",
            (b_type, b_tier, companion_id),
        )
        await self.connection.commit()

    async def rename(self, companion_id: int, new_name: str) -> None:
        await self.connection.execute(
            "UPDATE companions SET name = ? WHERE id = ?", (new_name, companion_id)
        )
        await self.connection.commit()

    async def update_stats(
        self, companion_id: int, new_level: int, new_exp: int
    ) -> None:
        """Updates Level and XP in a single transaction."""
        await self.connection.execute(
            "UPDATE companions SET level = ?, exp = ? WHERE id = ?",
            (new_level, new_exp, companion_id),
        )
        await self.connection.commit()

    async def fuse_companions(
        self, user_id: str, id_a: int, id_b: int, new_stats: dict, cost: int
    ) -> None:
        """
        Fuses two companions into one child.
        All three mutations (gold deduct, parent deletes, child insert) are
        rolled back atomically if any step fails.
        """
        # new_stats dict keys: name, species, image_url, passive_type, passive_tier, level, exp
        try:
            # 1. Deduct Gold (guard prevents going negative)
            cursor = await self.connection.execute(
                "UPDATE users SET gold = gold - ? WHERE user_id = ? AND gold >= ?",
                (cost, user_id, cost),
            )
            if cursor.rowcount == 0:
                raise ValueError("Insufficient gold for companion fusion")

            # 2. Delete Parents
            await self.connection.execute(
                "DELETE FROM companions WHERE id IN (?, ?) AND user_id = ?",
                (id_a, id_b, user_id),
            )

            # 3. Create Child (starts inactive)
            await self.connection.execute(
                """INSERT INTO companions (user_id, name, species, image_url,
                   passive_type, passive_tier, level, exp, is_active,
                   balanced_passive, balanced_passive_tier)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (
                    user_id,
                    new_stats["name"],
                    new_stats["species"],
                    new_stats["image_url"],
                    new_stats["passive_type"],
                    new_stats["passive_tier"],
                    new_stats["level"],
                    new_stats["exp"],
                    new_stats.get("balanced_passive", "none"),
                    new_stats.get("balanced_passive_tier", 0),
                ),
            )

            await self.connection.commit()
        except Exception:
            await self.connection.rollback()
            raise

    # ------------------------------------------------------------------
    # Companion Mastery
    # ------------------------------------------------------------------

    async def ensure_mastery(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO companion_mastery (user_id, server_id) VALUES (?, ?)",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def get_mastery(self, user_id: str, server_id: str) -> dict:
        await self.ensure_mastery(user_id, server_id)
        async with self.connection.execute(
            "SELECT nodes_owned, points_spent, kinship_points FROM companion_mastery WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return {
            "nodes_owned": json.loads(row[0]) if row and row[0] else {},
            "points_spent": row[1] if row else 0,
            "kinship_points": row[2] if row else 0,
        }

    async def add_kinship_points(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        await self.ensure_mastery(user_id, server_id)
        await self.connection.execute(
            "UPDATE companion_mastery SET kinship_points = kinship_points + ? WHERE user_id=? AND server_id=?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def purchase_mastery_node(
        self,
        user_id: str,
        server_id: str,
        node_id: str,
        cost: int,
        choice: str | None = None,
    ) -> bool:
        """Atomically deducts KP and stores the node. Returns True on success."""
        async with self.connection.execute(
            "SELECT nodes_owned, kinship_points FROM companion_mastery WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row[1] < cost:
            return False
        nodes = json.loads(row[0]) if row[0] else {}
        nodes[node_id] = choice if choice is not None else True
        await self.connection.execute(
            "UPDATE companion_mastery SET nodes_owned=?, kinship_points=kinship_points-?, points_spent=points_spent+? WHERE user_id=? AND server_id=?",
            (json.dumps(nodes), cost, cost, user_id, server_id),
        )
        await self.connection.commit()
        return True
