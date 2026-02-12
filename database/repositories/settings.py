import aiosqlite
from typing import List, Tuple, Optional

class SettingsRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def set_event_channel(self, guild_id: str, channel_id: str) -> None:
        """Upserts the event channel for a guild."""
        await self.connection.execute(
            """
            INSERT INTO guild_settings (guild_id, event_channel_id) 
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET event_channel_id = excluded.event_channel_id
            """,
            (guild_id, channel_id)
        )
        await self.connection.commit()

    async def get_event_channel(self, guild_id: str) -> Optional[str]:
        """Gets the channel ID for a specific guild."""
        rows = await self.connection.execute(
            "SELECT event_channel_id FROM guild_settings WHERE guild_id = ?", 
            (guild_id,)
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

    async def get_all_event_channels(self) -> List[Tuple[str, str]]:
        """
        Returns a list of (guild_id, channel_id) tuples for the event loop.
        """
        rows = await self.connection.execute("SELECT guild_id, event_channel_id FROM guild_settings")
        async with rows as cursor:
            return await cursor.fetchall()