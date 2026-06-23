from typing import Dict

import aiosqlite


class UberRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_uber_progress(self, user_id: str, server_id: str) -> Dict[str, int]:
        """Fetches Uber progression data. Creates a default row if it doesn't exist."""
        cursor = await self.connection.execute(
            """SELECT celestial_sigils, celestial_engrams, celestial_blueprint_unlocked,
                      infernal_sigils, infernal_engrams, infernal_blueprint_unlocked,
                      void_shards, void_engrams, void_blueprint_unlocked,
                      gemini_sigils, gemini_engrams, gemini_blueprint_unlocked,
                      corruption_sigils, paradise_jewels,
                      corruption_engrams, corruption_blueprint_unlocked
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
                "corruption_sigils": 0,
                "paradise_jewels": 0,
                "corruption_engrams": 0,
                "corruption_blueprint_unlocked": 0,
            }

        return {
            "celestial_sigils": row["celestial_sigils"],
            "celestial_engrams": row["celestial_engrams"],
            "celestial_blueprint_unlocked": row["celestial_blueprint_unlocked"],
            "infernal_sigils": row["infernal_sigils"]
            if row["infernal_sigils"] is not None
            else 0,
            "infernal_engrams": row["infernal_engrams"]
            if row["infernal_engrams"] is not None
            else 0,
            "infernal_blueprint_unlocked": row["infernal_blueprint_unlocked"]
            if row["infernal_blueprint_unlocked"] is not None
            else 0,
            "void_shards": row["void_shards"] if row["void_shards"] is not None else 0,
            "void_engrams": row["void_engrams"]
            if row["void_engrams"] is not None
            else 0,
            "void_blueprint_unlocked": row["void_blueprint_unlocked"]
            if row["void_blueprint_unlocked"] is not None
            else 0,
            "gemini_sigils": row["gemini_sigils"]
            if row["gemini_sigils"] is not None
            else 0,
            "gemini_engrams": row["gemini_engrams"]
            if row["gemini_engrams"] is not None
            else 0,
            "gemini_blueprint_unlocked": row["gemini_blueprint_unlocked"]
            if row["gemini_blueprint_unlocked"] is not None
            else 0,
            "corruption_sigils": row["corruption_sigils"]
            if row["corruption_sigils"] is not None
            else 0,
            "paradise_jewels": row["paradise_jewels"]
            if row["paradise_jewels"] is not None
            else 0,
            "corruption_engrams": row["corruption_engrams"]
            if row["corruption_engrams"] is not None
            else 0,
            "corruption_blueprint_unlocked": row["corruption_blueprint_unlocked"]
            if row["corruption_blueprint_unlocked"] is not None
            else 0,
        }

    # --- Celestial (Aphrodite) ---

    async def increment_sigils(self, user_id: str, server_id: str, amount: int) -> None:
        """Modifies the celestial_sigils count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET celestial_sigils = celestial_sigils + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_engrams(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the celestial_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET celestial_engrams = celestial_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_blueprint_unlocked(
        self, user_id: str, server_id: str, unlocked: bool
    ) -> None:
        """Sets the celestial blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET celestial_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()

    # --- Infernal (Lucifer) ---

    async def increment_infernal_sigils(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the infernal_sigils count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET infernal_sigils = infernal_sigils + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_infernal_engrams(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the infernal_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET infernal_engrams = infernal_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_infernal_blueprint_unlocked(
        self, user_id: str, server_id: str, unlocked: bool
    ) -> None:
        """Sets the infernal blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET infernal_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()

    # --- Void (NEET) ---

    async def increment_void_shards(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the void_shards count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET void_shards = void_shards + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_void_engrams(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the void_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET void_engrams = void_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_void_blueprint_unlocked(
        self, user_id: str, server_id: str, unlocked: bool
    ) -> None:
        """Sets the void blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET void_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()

    # --- Gemini (Twins) ---

    async def increment_gemini_sigils(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the gemini_sigils count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET gemini_sigils = gemini_sigils + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_gemini_engrams(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the gemini_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET gemini_engrams = gemini_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_gemini_blueprint_unlocked(
        self, user_id: str, server_id: str, unlocked: bool
    ) -> None:
        """Sets the gemini blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET gemini_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()

    # --- Corrupted Monsters ---

    async def increment_corruption_sigils(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the corruption_sigils count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET corruption_sigils = corruption_sigils + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_paradise_jewels(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the paradise_jewels count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET paradise_jewels = paradise_jewels + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_corruption_engrams(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Modifies the corruption_engrams count (can be negative)."""
        await self.connection.execute(
            "UPDATE uber_progress SET corruption_engrams = corruption_engrams + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def set_corruption_blueprint_unlocked(
        self, user_id: str, server_id: str, unlocked: bool
    ) -> None:
        """Sets the corruption blueprint unlocked flag."""
        val = 1 if unlocked else 0
        await self.connection.execute(
            "UPDATE uber_progress SET corruption_blueprint_unlocked = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()
