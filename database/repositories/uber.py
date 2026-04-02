import aiosqlite
from typing import Dict


class UberRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_uber_progress(self, user_id: str, server_id: str) -> Dict[str, int]:
        """Fetches Uber progression data. Creates a default row if it doesn't exist."""
        cursor = await self.connection.execute(
            """SELECT celestial_sigils, celestial_engrams, celestial_blueprint_unlocked,
                      infernal_sigils, infernal_engrams, infernal_blueprint_unlocked,
                      void_shards, void_engrams, void_blueprint_unlocked,
                      gemini_sigils, gemini_engrams, gemini_blueprint_unlocked
               FROM uber_progress WHERE user_id = ? AND server_id = ?""",
            (user_id, server_id),
        )
        row = await cursor.fetchone()

        if not row:
            await self.connection.execute(
                "INSERT INTO uber_progress (user_id, server_id) VALUES (?, ?)",
                (user_id, server_id),
            )
            await self.connection.commit()
            return {
                "celestial_sigils": 0,
                "celestial_engrams": 0,
                "celestial_blueprint_unlocked": 0,
                "infernal_sigils": 0,
                "infernal_engrams": 0,
                "infernal_blueprint_unlocked": 0,
                "void_shards": 0,
                "void_engrams": 0,
                "void_blueprint_unlocked": 0,
                "gemini_sigils": 0,
                "gemini_engrams": 0,
                "gemini_blueprint_unlocked": 0,
            }

        return {
            "celestial_sigils": row[0],
            "celestial_engrams": row[1],
            "celestial_blueprint_unlocked": row[2],
            "infernal_sigils": row[3] if row[3] is not None else 0,
            "infernal_engrams": row[4] if row[4] is not None else 0,
            "infernal_blueprint_unlocked": row[5] if row[5] is not None else 0,
            "void_shards": row[6] if row[6] is not None else 0,
            "void_engrams": row[7] if row[7] is not None else 0,
            "void_blueprint_unlocked": row[8] if row[8] is not None else 0,
            "gemini_sigils": row[9] if row[9] is not None else 0,
            "gemini_engrams": row[10] if row[10] is not None else 0,
            "gemini_blueprint_unlocked": row[11] if row[11] is not None else 0,
        }

    # --- Celestial (Aphrodite) ---

    async def increment_sigils(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the celestial_sigils count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET celestial_sigils = celestial_sigils + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_engrams(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the celestial_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET celestial_engrams = celestial_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_blueprint_unlocked(self, user_id: str, server_id: str, unlocked: bool) -> None:
        """Sets the celestial blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET celestial_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()

    # --- Infernal (Lucifer) ---

    async def increment_infernal_sigils(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the infernal_sigils count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET infernal_sigils = infernal_sigils + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_infernal_engrams(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the infernal_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET infernal_engrams = infernal_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_infernal_blueprint_unlocked(self, user_id: str, server_id: str, unlocked: bool) -> None:
        """Sets the infernal blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET infernal_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()

    # --- Void (NEET) ---

    async def increment_void_shards(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the void_shards count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET void_shards = void_shards + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_void_engrams(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the void_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET void_engrams = void_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_void_blueprint_unlocked(self, user_id: str, server_id: str, unlocked: bool) -> None:
        """Sets the void blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET void_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()

    # --- Gemini (Twins) ---

    async def increment_gemini_sigils(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the gemini_sigils count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET gemini_sigils = gemini_sigils + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_gemini_engrams(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the gemini_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET gemini_engrams = gemini_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_gemini_blueprint_unlocked(self, user_id: str, server_id: str, unlocked: bool) -> None:
        """Sets the gemini blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET gemini_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()
