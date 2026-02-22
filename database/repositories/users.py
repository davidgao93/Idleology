# database/repositories/users.py

import aiosqlite
from datetime import datetime, timedelta
from core.models import Player

class UserRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    # ---------------------------------------------------------
    # Core User Management (Get, Register, Delete)
    # ---------------------------------------------------------

    async def get(self, user_id: str, server_id: str):
        """Fetch a user row from the database."""
        rows = await self.connection.execute(
            "SELECT * FROM users WHERE user_id=? AND server_id=?",
            (user_id, server_id)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def get_all(self):
        """Fetch all users (e.g., for global health regen tasks)."""
        rows = await self.connection.execute("SELECT * FROM users")
        async with rows as cursor:
            return await cursor.fetchall()

    async def register(self, user_id: str, server_id: str, name: str, appearance: str, ideology: str) -> None:
        """Register a new adventurer."""
        # Set initial check-in time to 18 hours from now
        last_checkin = (datetime.now() + timedelta(hours=18)).isoformat()
        
        await self.connection.execute(
            """
            INSERT INTO users (user_id, server_id, name, appearance, ideology, last_checkin_time) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, server_id, name, appearance, ideology, last_checkin)
        )
        await self.connection.commit()

    async def unregister(self, user_id: str, server_id: str) -> None:
        """
        Deletes a user. 
        Note: The cascade deletion of items/skills is typically handled here 
        or via SQL Foreign Keys if configured.
        """
        try:
            await self.connection.execute(
                "DELETE FROM users WHERE user_id=? AND server_id=?",
                (user_id, server_id)
            )
            await self.connection.execute(
                "DELETE FROM ideologies WHERE user_id=?",
                (user_id,)
            )
            await self.connection.execute(
                "DELETE FROM items WHERE user_id=?",
                (user_id,)
            )
            await self.connection.execute(
                "DELETE FROM accessories WHERE user_id=?",
                (user_id,)
            )
            await self.connection.execute(
                "DELETE FROM armor WHERE user_id=?",
                (user_id,)
            )
            await self.connection.execute( # Add deletion for gloves table
                "DELETE FROM gloves WHERE user_id=?",
                (user_id,)
            )
            await self.connection.execute( # Add deletion for boots table
                "DELETE FROM boots WHERE user_id=?",
                (user_id,)
            )
            await self.connection.execute(
                "DELETE FROM mining WHERE user_id=?",
                (user_id,)
            )
            await self.connection.execute(
                "DELETE FROM fishing WHERE user_id=?",
                (user_id,)
            )
            await self.connection.execute(
                "DELETE FROM woodcutting WHERE user_id=?",
                (user_id,)
            )
            await self.connection.commit()
        except Exception as e:
            print(f"Error during user unregistration: {e}")
            raise
        await self.connection.commit()

    # ---------------------------------------------------------
    # Player Stats & State Object
    # ---------------------------------------------------------

    async def update_from_player_object(self, player: Player) -> None:
        """
        Syncs a core.models.Player object back to the DB.
        Useful for saving state after combat or heavy logic.
        """
        await self.connection.execute(
            """
            UPDATE users SET 
                level = ?, 
                ascension = ?, 
                experience = ?, 
                current_hp = ?, 
                potions = ?
            WHERE user_id = ?
            """,
            (player.level, player.ascension, player.exp, player.current_hp, player.potions, player.id)
        )
        await self.connection.commit()

    async def update_hp(self, user_id: str, hp: int) -> None:
        """Specific update for HP (e.g., regeneration task)."""
        # Note: Removed server_id check if user_id is globally unique, otherwise add it back
        await self.connection.execute("UPDATE users SET current_hp = ? WHERE user_id = ?", (hp, user_id))
        await self.connection.commit()

    async def modify_stat(self, user_id: str, stat: str, amount: int) -> None:
        """
        Generic method to increment/decrement a basic stat.
        Usage: await users.modify_stat(uid, 'attack', 5)
        """
        valid_stats = ["attack", "defence", "max_hp", "ascension", "potions", "experience"]
        if stat not in valid_stats:
            raise ValueError(f"Invalid stat: {stat}")

        await self.connection.execute(
            f"UPDATE users SET {stat} = {stat} + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await self.connection.commit()


    async def get_value(self, user_id: str, column: str) -> int:
        # Basic validation to prevent SQL injection
        allowed = ["passive_points"] 
        if column not in allowed: return 0
        
        rows = await self.connection.execute(f"SELECT {column} FROM users WHERE user_id = ?", (user_id,))
        result = await rows.fetchone()
        return result[0] if result else 0

    
    async def set_passive_points(self, user_id: str, server_id: str, amount: int):
        await self.connection.execute(
            "UPDATE users SET passive_points = ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id)
        )
        await self.connection.commit()


    # ---------------------------------------------------------
    # Currency & Resources (Gold, Keys, Runes, Curios)
    # ---------------------------------------------------------

    async def get_gold(self, user_id: str) -> int:
        rows = await self.connection.execute(
            "SELECT gold FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = await rows.fetchone()
        return result[0] if result else 0

    async def modify_gold(self, user_id: str, amount: int) -> None:
        """Add (positive) or remove (negative) gold."""
        await self.connection.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (amount, user_id))
        await self.connection.commit()

    async def set_gold(self, user_id: str, amount: int) -> None:
        """Hard set gold amount (e.g. gambling resets)."""
        await self.connection.execute("UPDATE users SET gold = ? WHERE user_id = ?", (amount, user_id))
        await self.connection.commit()

    async def get_currency(self, user_id: str, column: str) -> int:
        # Basic validation to prevent SQL injection
      
        rows = await self.connection.execute(f"SELECT {column} FROM users WHERE user_id = ?", (user_id,))
        result = await rows.fetchone()
        return result[0] if result else 0

    async def modify_currency(self, user_id: str, currency_column: str, amount: int) -> None:
        """
        Generic handler for keys, runes, and misc counters.
        Allowed columns: dragon_key, angel_key, void_keys, soul_cores, void_frags, 
                        balance fragment, partnership_runes
                         refinement_runes, potential_runes, imbue_runes, shatter_runes,
                         curios, curios_purchased_today
        """
        # Could validate column names here to prevent SQL injection
        await self.connection.execute(
            f"UPDATE users SET {currency_column} = {currency_column} + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await self.connection.commit()

    # ---------------------------------------------------------
    # Timers & Cooldowns
    # ---------------------------------------------------------

    async def update_timer(self, user_id: str, timer_column: str) -> None:
        """Updates a specific timestamp column to NOW."""
        valid_timers = ["last_rest_time", "last_checkin_time", "last_propagate_time", "last_combat"]
        if timer_column not in valid_timers:
            raise ValueError(f"Invalid timer column: {timer_column}")

        current_time = datetime.now().isoformat()
        await self.connection.execute(
            f"UPDATE users SET {timer_column} = ? WHERE user_id = ?",
            (current_time, user_id)
        )
        await self.connection.commit()


    async def initialize_companion_timer(self, user_id: str) -> None:
        """
        Sets the companion collection timer to NOW, but ONLY if it hasn't been set yet.
        This prevents resetting pending rewards when activating a 2nd or 3rd pet.
        """
        current_time = datetime.now().isoformat()
        await self.connection.execute(
            """
            UPDATE users 
            SET last_companion_collect_time = ? 
            WHERE user_id = ? AND last_companion_collect_time IS NULL
            """,
            (current_time, user_id)
        )
        await self.connection.commit()

    # ---------------------------------------------------------
    # Leaderboards
    # ---------------------------------------------------------

    async def get_leaderboard(self, limit: int = 10):
        rows = await self.connection.execute(
            "SELECT * FROM users ORDER BY level DESC, ascension DESC LIMIT ?",
            (limit,)
        )
        async with rows as cursor:
            return await cursor.fetchall()
        

    async def get_doors_enabled(self, user_id: str) -> bool:
        """Fetches the boss door preference for a user. Defaults to True."""
        # Using a try/except or safe fetch in case the column was just added
        cursor = await self.connection.execute(
            "SELECT doors_enabled FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row[0]) if row else True

    async def toggle_doors(self, user_id: str, status: bool) -> None:
        """Updates the boss door preference."""
        val = 1 if status else 0
        await self.connection.execute(
            "UPDATE users SET doors_enabled = ? WHERE user_id = ?",
            (val, user_id)
        )
        await self.connection.commit()


    async def get_wealth_leaderboard(self, limit: int = 10):
        rows = await self.connection.execute(
            "SELECT name, gold FROM users ORDER BY gold DESC LIMIT ?",
            (limit,)
        )
        async with rows as cursor:
            return await cursor.fetchall()