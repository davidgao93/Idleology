import json

import aiosqlite


class InnerSanctumRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get(self, user_id: str, server_id: str) -> dict:
        cursor = await self.connection.execute(
            "SELECT points_available, points_spent, nodes_owned FROM inner_sanctum "
            "WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if not row:
            return {"points_available": 0, "points_spent": 0, "nodes_owned": {}}
        return {
            "points_available": row["points_available"],
            "points_spent": row["points_spent"],
            "nodes_owned": json.loads(row["nodes_owned"]) if row["nodes_owned"] else {},
        }

    async def add_points(self, user_id: str, server_id: str, amount: int) -> None:
        """Atomically grants `amount` Inner Sanctum points, creating the row if needed."""
        await self.connection.execute(
            """INSERT INTO inner_sanctum (user_id, server_id, points_available)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                 points_available = points_available + excluded.points_available""",
            (user_id, server_id, amount),
        )
        await self.connection.commit()

    async def purchase_node(
        self, user_id: str, server_id: str, node_id: str, cost: int, value
    ) -> None:
        """Deducts `cost` from points_available, adds it to points_spent, and
        writes `value` (True / rank int / choice string) into nodes_owned[node_id]."""
        data = await self.get(user_id, server_id)
        nodes_owned = data["nodes_owned"]
        nodes_owned[node_id] = value
        await self.connection.execute(
            """INSERT INTO inner_sanctum (user_id, server_id, points_available, points_spent, nodes_owned)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                 points_available = excluded.points_available,
                 points_spent = excluded.points_spent,
                 nodes_owned = excluded.nodes_owned""",
            (
                user_id,
                server_id,
                data["points_available"] - cost,
                data["points_spent"] + cost,
                json.dumps(nodes_owned),
            ),
        )
        await self.connection.commit()

    async def reset_tree(self, user_id: str, server_id: str) -> int:
        """Refunds points_spent back into points_available and clears nodes_owned.
        Returns the number of points refunded."""
        data = await self.get(user_id, server_id)
        refunded = data["points_spent"]
        await self.connection.execute(
            """INSERT INTO inner_sanctum (user_id, server_id, points_available, points_spent, nodes_owned)
               VALUES (?, ?, ?, 0, '{}')
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                 points_available = excluded.points_available,
                 points_spent = 0,
                 nodes_owned = '{}'""",
            (user_id, server_id, data["points_available"] + refunded),
        )
        await self.connection.commit()
        return refunded
