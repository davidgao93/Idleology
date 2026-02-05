# database/base.py
import aiosqlite

class BaseRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def commit(self):
        await self.connection.commit()