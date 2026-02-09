import aiosqlite
from typing import List

class SocialRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_all_by_server(self, server_id: str) -> List[str]:
        """Fetches a list of ideology names for a specific server."""
        # Note: I optimized the query to select 'name' specifically, 
        # but kept the logic compatible with your existing structure.
        rows = await self.connection.execute(
            "SELECT name FROM ideologies WHERE server_id=?",
            (server_id,)
        )
        async with rows as cursor:
            results = await cursor.fetchall()
        # Flatten [(name1,), (name2,)] to [name1, name2]
        return [row[0] for row in results]

    async def get_follower_count(self, ideology_name: str) -> int:
        """Fetches the number of followers for a specific ideology."""
        rows = await self.connection.execute(
            "SELECT followers FROM ideologies WHERE name=?",
            (ideology_name,)
        )
        async with rows as cursor:
            count = await cursor.fetchone()
        return count[0] if count else 0

    async def create_ideology(self, user_id: str, server_id: str, name: str) -> None:
        """Registers a new ideology."""
        await self.connection.execute(
            "INSERT INTO ideologies (user_id, server_id, name) VALUES (?, ?, ?)",
            (user_id, server_id, name)
        )
        await self.connection.commit()

    async def update_followers(self, ideology_name: str, new_count: int) -> None:
        """Sets the follower count for an ideology."""
        await self.connection.execute(
            "UPDATE ideologies SET followers = ? WHERE name = ?",
            (new_count, ideology_name)
        )
        await self.connection.commit()