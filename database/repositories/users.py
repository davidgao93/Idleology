# database/repositories/users.py

import re
from datetime import datetime, timedelta

import aiosqlite

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
            "SELECT * FROM users WHERE user_id=? AND server_id=?", (user_id, server_id)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def get_all(self):
        """Fetch all users (e.g., for global health regen tasks)."""
        rows = await self.connection.execute("SELECT * FROM users")
        async with rows as cursor:
            return await cursor.fetchall()

    async def register(
        self, user_id: str, server_id: str, name: str, appearance: str, ideology: str
    ) -> None:
        """Register a new adventurer."""
        # Set initial check-in time to 18 hours from now
        last_checkin = (datetime.now() + timedelta(hours=18)).isoformat()

        await self.connection.execute(
            """
            INSERT INTO users (user_id, server_id, name, appearance, ideology, last_checkin_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, server_id, name, appearance, ideology, last_checkin),
        )
        await self.connection.execute(
            "INSERT INTO player_currencies (user_id) VALUES (?)",
            (user_id,),
        )
        await self.connection.commit()

    async def unregister(self, user_id: str, server_id: str) -> None:
        """
        Deletes a user and all associated data.

        The `users` and `ideologies` rows are hard-deleted (raise on failure).
        All other tables are best-effort: if a table doesn't exist in an older
        schema the delete is silently skipped so nothing blocks the wipe.
        """
        u = (user_id,)
        us = (user_id, server_id)

        # ── Hard deletes — must succeed ────────────────────────────────────
        await self.connection.execute(
            "DELETE FROM users WHERE user_id=? AND server_id=?", us
        )
        await self.connection.execute("DELETE FROM ideologies WHERE user_id=?", u)

        # ── Best-effort cleanup: tables keyed by user_id only ──────────────
        _by_user = [
            "player_currencies",
            "items",
            "accessories",
            "armor",
            "gloves",
            "boots",
            "helmets",
            "companions",
            "monster_parts",
            "monster_parts_equipped",
            "monster_eggs",
            "incubated_encounters",
            "mining",
            "fishing",
            "woodcutting",
            "journey_milestones",
            "ascension_unlocks",
            "codex_progress",
            "codex_tomes",
            "alchemy_data",
            "potion_passives",
            "synthesis_queue",
            "synthesis_queue_2",
            "synthesis_queue_3",
            "duel_stats",
            "player_essences",
            "user_partners",
            "user_partner_items",
            "user_partner_shards",
            "paradise_jewel_data",
            "hematurgy_passives",
            "hematurgy_blood",
            "prestige_owned",
            "maw_participants",
            "quest_board",
            "quest_contracts",
            "quest_horizon",
            "quest_meta",
        ]
        for table in _by_user:
            try:
                await self.connection.execute(f"DELETE FROM {table} WHERE user_id=?", u)
            except Exception as e:
                print(f"[unregister] skipped {table}: {e}")

        # ── Best-effort cleanup: tables keyed by (user_id, server_id) ──────
        _by_user_server = [
            "gathering_mastery",
            "hatchery_incubation",
            "delve_progress",
            "slayer_profiles",
            "slayer_emblems",
            "uber_progress",
            "settlements",
            "buildings",
            "settlement_plots",
            "settlement_research",
            "apex_hunt_profiles",
            "soul_stones",
            "soul_shards",
            "meta_shards",
            "boss_party_dispatch",
        ]
        for table in _by_user_server:
            try:
                await self.connection.execute(
                    f"DELETE FROM {table} WHERE user_id=? AND server_id=?", us
                )
            except Exception as e:
                print(f"[unregister] skipped {table}: {e}")

        await self.connection.commit()

    # ---------------------------------------------------------
    # Player Stats & State Object
    # ---------------------------------------------------------

    async def update_from_player_object(self, player: Player) -> None:
        """Syncs the five combat-outcome fields of a Player object back to the DB.

        Deliberately narrow: only level, ascension, current_hp, potions, and
        experience are written here.  All other mutable fields (gold, attack,
        defence, max_hp, currencies, cooldown timestamps) have their own
        dedicated repo methods (modify_gold, modify_stat, update_timer, …) that
        are called explicitly at the site where the mutation happens.  Adding a
        new Player field that needs persistence requires a dedicated method —
        do not widen this update to a broad "write everything" query, as that
        would hide mutation sites and create silent staleness bugs when Player
        fields diverge from what the DB expects.
        """
        await self.connection.execute(
            """
                UPDATE users SET
                    level = ?,
                    ascension = ?,
                    current_hp = ?,
                    potions = ?,
                    experience = ?
                WHERE user_id = ?
                """,
            (
                player.level,
                player.ascension,
                player.current_hp,
                player.potions,
                player.exp,
                player.id,
            ),
        )
        await self.connection.commit()

    async def update_hp(self, user_id: str, hp: int) -> None:
        """Specific update for HP (e.g., regeneration task)."""
        await self.connection.execute(
            "UPDATE users SET current_hp = ? WHERE user_id = ?", (hp, user_id)
        )
        await self.connection.commit()

    async def batch_regen_hp(self) -> int:
        """Regen HP for all users below their base max_hp in a single query.

        Uses stored max_hp (base stat) as the cap to avoid loading all player
        data per-user. Returns the number of rows updated.
        """
        await self.connection.execute(
            """
            UPDATE users
            SET current_hp = MIN(max_hp, current_hp + 1 + CAST(max_hp / 30 AS INTEGER))
            WHERE current_hp < max_hp
            """
        )
        await self.connection.commit()
        async with self.connection.execute(
            "SELECT changes()"
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def update_appearance(self, user_id: str, url: str) -> None:
        """Update the player's avatar URL across all servers."""
        await self.connection.execute(
            "UPDATE users SET appearance = ? WHERE user_id = ?", (url, user_id)
        )
        await self.connection.commit()

    async def modify_stat(self, user_id: str, stat: str, amount: int) -> None:
        """
        Generic method to increment/decrement a basic stat.
        Usage: await users.modify_stat(uid, 'attack', 5)
        """
        valid_stats = [
            "attack",
            "defence",
            "max_hp",
            "ascension",
            "potions",
            "experience",
        ]
        if stat not in valid_stats:
            raise ValueError(f"Invalid stat: {stat}")

        await self.connection.execute(
            f"UPDATE users SET {stat} = {stat} + ? WHERE user_id = ?", (amount, user_id)
        )
        await self.connection.commit()

    async def get_value(self, user_id: str, column: str) -> int:
        allowed = ["passive_points"]
        if column not in allowed:
            return 0

        rows = await self.connection.execute(
            f"SELECT {column} FROM player_currencies WHERE user_id = ?", (user_id,)
        )
        result = await rows.fetchone()
        return result[column] if result else 0

    async def set_passive_points(self, user_id: str, server_id: str, amount: int):
        await self.connection.execute(
            "UPDATE player_currencies SET passive_points = ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    # ---------------------------------------------------------
    # Currency & Resources (Gold, Keys, Runes, Curios)
    # ---------------------------------------------------------

    async def get_gold(self, user_id: str) -> int:
        rows = await self.connection.execute(
            "SELECT gold FROM users WHERE user_id = ?", (user_id,)
        )
        result = await rows.fetchone()
        return result["gold"] if result else 0

    async def modify_gold(self, user_id: str, amount: int) -> None:
        """Add (positive) or remove (negative) gold."""
        await self.connection.execute(
            "UPDATE users SET gold = gold + ? WHERE user_id = ?", (amount, user_id)
        )
        await self.connection.commit()

    async def deduct_gold_atomic(self, user_id: str, amount: int) -> bool:
        """Deducts gold only if the current balance covers it. Returns True on success."""
        cursor = await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ? AND gold >= ?",
            (amount, user_id, amount),
        )
        await self.connection.commit()
        return cursor.rowcount == 1

    async def set_gold(self, user_id: str, amount: int) -> None:
        """Hard set gold amount (e.g. gambling resets)."""
        await self.connection.execute(
            "UPDATE users SET gold = ? WHERE user_id = ?", (amount, user_id)
        )
        await self.connection.commit()

    _COLUMN_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    async def get_all_currencies(self, user_id: str) -> dict:
        """Fetch the full player_currencies row as a plain dict. Returns {} if no row exists."""
        cursor = await self.connection.execute(
            "SELECT * FROM player_currencies WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}

    async def get_currency(self, user_id: str, column: str) -> int:
        if not self._COLUMN_RE.match(column):
            raise ValueError(f"get_currency: invalid column name {column!r}")
        rows = await self.connection.execute(
            f"SELECT {column} FROM player_currencies WHERE user_id = ?", (user_id,)
        )
        result = await rows.fetchone()
        return result[column] if result else 0

    async def modify_currency(
        self, user_id: str, currency_column: str, amount: int
    ) -> None:
        """Generic handler for all player_currencies columns (runes, keys, misc counters)."""
        if not self._COLUMN_RE.match(currency_column):
            raise ValueError(
                f"modify_currency: invalid column name {currency_column!r}"
            )
        await self.connection.execute(
            f"UPDATE player_currencies SET {currency_column} = {currency_column} + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def deduct_currency_atomic(
        self, user_id: str, currency_column: str, amount: int
    ) -> bool:
        """Deducts a player_currencies column only if balance >= amount. Returns True on success."""
        if not self._COLUMN_RE.match(currency_column):
            raise ValueError(
                f"deduct_currency_atomic: invalid column name {currency_column!r}"
            )
        cursor = await self.connection.execute(
            f"UPDATE player_currencies SET {currency_column} = {currency_column} - ? "
            f"WHERE user_id = ? AND {currency_column} >= ?",
            (amount, user_id, amount),
        )
        await self.connection.commit()
        return cursor.rowcount == 1

    # ---------------------------------------------------------
    # Timers & Cooldowns
    # ---------------------------------------------------------

    async def update_timer(self, user_id: str, timer_column: str) -> None:
        """Updates a specific timestamp column to NOW."""
        valid_timers = [
            "last_rest_time",
            "last_checkin_time",
            "last_propagate_time",
            "last_combat",
        ]
        if timer_column not in valid_timers:
            raise ValueError(f"Invalid timer column: {timer_column}")

        current_time = datetime.now().isoformat()
        await self.connection.execute(
            f"UPDATE users SET {timer_column} = ? WHERE user_id = ?",
            (current_time, user_id),
        )
        await self.connection.commit()

    async def get_timer(self, user_id: str, timer_column: str):
        """Fetches a specific timestamp column for a user."""
        valid_timers = [
            "last_rest_time",
            "last_checkin_time",
            "last_propagate_time",
            "last_combat",
        ]
        if timer_column not in valid_timers:
            raise ValueError(f"Invalid timer column: {timer_column}")
        cursor = await self.connection.execute(
            f"SELECT {timer_column} FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[timer_column] if row else None

    async def get_companion_collect_time(self, user_id: str) -> str | None:
        """Returns the last companion collection timestamp for a user."""
        async with self.connection.execute(
            "SELECT last_companion_collect_time FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row["last_companion_collect_time"] if row else None

    async def update_companion_collect_time(self, user_id: str, timestamp: str) -> None:
        """Sets the companion collection timer to the given ISO timestamp."""
        await self.connection.execute(
            "UPDATE users SET last_companion_collect_time = ? WHERE user_id = ?",
            (timestamp, user_id),
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
            (current_time, user_id),
        )
        await self.connection.commit()

    async def modify_spirit_stones(self, user_id: str, delta: int) -> None:
        """Adds delta (may be negative) to spirit_stones, flooring at 0."""
        await self.connection.execute(
            "UPDATE player_currencies SET spirit_stones = MAX(0, spirit_stones + ?) WHERE user_id = ?",
            (delta, user_id),
        )
        await self.connection.commit()

    # ---------------------------------------------------------
    # Combat Stamina
    # ---------------------------------------------------------

    async def get_stamina(self, user_id: str) -> dict:
        """Returns combat_stamina and last_stamina_regen for a user."""
        async with self.connection.execute(
            "SELECT combat_stamina, last_stamina_regen FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            return {
                "combat_stamina": row["combat_stamina"],
                "last_stamina_regen": row["last_stamina_regen"],
            }
        return {"combat_stamina": 10, "last_stamina_regen": None}

    async def set_stamina(self, user_id: str, value: int) -> None:
        """Sets combat_stamina to the given value (clamped 0–10)."""
        await self.connection.execute(
            "UPDATE users SET combat_stamina = ? WHERE user_id = ?",
            (max(0, min(10, value)), user_id),
        )
        await self.connection.commit()

    async def add_stamina_uncapped(self, user_id: str, amount: float) -> None:
        """Adds stamina without enforcing the normal 10-unit cap. Used by War Camp."""
        await self.connection.execute(
            "UPDATE users SET combat_stamina = combat_stamina + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def add_stamina_capped(self, user_id: str, amount: int) -> None:
        """Adds stamina, honouring the normal 10-unit cap. Used by the new War Camp collection."""
        await self.connection.execute(
            "UPDATE users SET combat_stamina = MIN(10, combat_stamina + ?) WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def consume_stamina(self, user_id: str) -> None:
        """Decrements combat_stamina by 1, flooring at 0. Does NOT enforce the 10-unit cap,
        so over-cap stamina (e.g. 12.5) drains correctly (→ 11.5) without being truncated."""
        await self.connection.execute(
            "UPDATE users SET combat_stamina = MAX(0, combat_stamina - 1) WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.commit()

    async def set_stamina_regen_time(self, user_id: str) -> None:
        """Stamps last_stamina_regen to NOW, starting the hourly regen clock."""
        await self.connection.execute(
            "UPDATE users SET last_stamina_regen = ? WHERE user_id = ?",
            (datetime.now().isoformat(), user_id),
        )
        await self.connection.commit()

    async def regen_stamina_tick(self) -> int:
        """
        Grants +1 combat_stamina to every user below cap whose last regen
        was >= 1 hour ago (or has never been set). Returns number of users updated.
        """
        now = datetime.now()
        async with self.connection.execute(
            "SELECT user_id, combat_stamina, last_stamina_regen FROM users WHERE combat_stamina < 10"
        ) as cursor:
            rows = await cursor.fetchall()

        updated = 0
        for row in rows:
            user_id, stamina, last_regen_str = (
                row["user_id"],
                row["combat_stamina"],
                row["last_stamina_regen"],
            )
            should_grant = False
            if last_regen_str is None:
                should_grant = True
            else:
                try:
                    elapsed = (
                        now - datetime.fromisoformat(last_regen_str)
                    ).total_seconds()
                    if elapsed >= 3600:
                        should_grant = True
                except ValueError:
                    should_grant = True

            if should_grant:
                await self.connection.execute(
                    "UPDATE users SET combat_stamina = ?, last_stamina_regen = ? WHERE user_id = ?",
                    (min(10, stamina + 1), now.isoformat(), user_id),
                )
                await self.connection.commit()
                updated += 1

        return updated

    # ---------------------------------------------------------
    # Leaderboards
    # ---------------------------------------------------------

    async def get_leaderboard(self, limit: int = 10):
        rows = await self.connection.execute(
            "SELECT * FROM users ORDER BY level DESC, ascension DESC LIMIT ?", (limit,)
        )
        async with rows as cursor:
            return await cursor.fetchall()

    async def get_ascension_leaderboard(self, limit: int = 10):
        rows = await self.connection.execute(
            "SELECT name, highest_ascension_stage, level FROM users ORDER BY highest_ascension_stage DESC, level DESC LIMIT ?",
            (limit,),
        )
        async with rows as cursor:
            return await cursor.fetchall()

    async def update_highest_ascension_stage(self, user_id: str, stage: int) -> None:
        """Records the stage if it's higher than the player's current record."""
        await self.connection.execute(
            "UPDATE users SET highest_ascension_stage = MAX(highest_ascension_stage, ?) WHERE user_id = ?",
            (stage, user_id),
        )
        await self.connection.commit()

    async def get_doors_enabled(self, user_id: str) -> bool:
        """Fetches the boss door preference for a user. Defaults to True."""
        # Using a try/except or safe fetch in case the column was just added
        cursor = await self.connection.execute(
            "SELECT doors_enabled FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row["doors_enabled"]) if row else True

    async def toggle_doors(self, user_id: str, status: bool) -> None:
        """Updates the boss door preference."""
        val = 1 if status else 0
        await self.connection.execute(
            "UPDATE users SET doors_enabled = ? WHERE user_id = ?", (val, user_id)
        )
        await self.connection.commit()

    async def get_exp_protection(self, user_id: str) -> bool:
        """Fetches the exp protection preference for a user. Defaults to False."""
        cursor = await self.connection.execute(
            "SELECT exp_protection FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row["exp_protection"]) if row else False

    async def toggle_exp_protection(self, user_id: str, status: bool) -> None:
        """Updates the exp protection preference."""
        val = 1 if status else 0
        await self.connection.execute(
            "UPDATE users SET exp_protection = ? WHERE user_id = ?", (val, user_id)
        )
        await self.connection.commit()

    async def get_wealth_leaderboard(self, limit: int = 10):
        rows = await self.connection.execute(
            "SELECT name, gold FROM users ORDER BY gold DESC LIMIT ?", (limit,)
        )
        async with rows as cursor:
            return await cursor.fetchall()

    # ---------------------------------------------------------
    # Hard Combat Mode
    # ---------------------------------------------------------

    async def get_hard_mode(self, user_id: str) -> int:
        """Returns the difficulty level (0=off, 1=hard, 2=extreme, 3=nightmarish, 4=delirious)."""
        cursor = await self.connection.execute(
            "SELECT hard_mode FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return int(row["hard_mode"]) if row else 0

    async def set_difficulty(self, user_id: str, level: int) -> None:
        """Persists the difficulty level (0–4)."""
        await self.connection.execute(
            "UPDATE users SET hard_mode = ? WHERE user_id = ?",
            (max(0, min(4, level)), user_id),
        )
        await self.connection.commit()

    async def get_auto_rest_pay(self, user_id: str) -> bool:
        """Fetches the auto-pay for tavern rest preference. Defaults to False."""
        cursor = await self.connection.execute(
            "SELECT auto_rest_pay FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row["auto_rest_pay"]) if row else False

    async def toggle_auto_rest_pay(self, user_id: str, status: bool) -> None:
        """Updates the auto-pay for tavern rest preference."""
        val = 1 if status else 0
        await self.connection.execute(
            "UPDATE users SET auto_rest_pay = ? WHERE user_id = ?", (val, user_id)
        )
        await self.connection.commit()

    async def toggle_hard_mode(self, user_id: str, status: bool) -> None:
        """Legacy shim — sets difficulty to 1 (Hard) or 0 (Off)."""
        await self.set_difficulty(user_id, 1 if status else 0)

    # ---------------------------------------------------------
    # Combat Streak
    # ---------------------------------------------------------

    async def get_combat_streak(self, user_id: str) -> int:
        cursor = await self.connection.execute(
            "SELECT combat_streak FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row["combat_streak"] if row else 0

    async def increment_combat_streak(self, user_id: str) -> int:
        """Increments and returns the new streak value."""
        await self.connection.execute(
            "UPDATE users SET combat_streak = combat_streak + 1 WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.commit()
        cursor = await self.connection.execute(
            "SELECT combat_streak FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row["combat_streak"] if row else 1

    async def reset_combat_streak(self, user_id: str) -> None:
        await self.connection.execute(
            "UPDATE users SET combat_streak = 0 WHERE user_id = ?", (user_id,)
        )
        await self.connection.commit()

    # ---------------------------------------------------------
    # Stat Investment (passive_points allocation)
    # ---------------------------------------------------------

    async def get_stat_investments(self, user_id: str) -> dict:
        """Returns how many passive_points are invested per stat category."""
        cursor = await self.connection.execute(
            "SELECT stat_invest_atk, stat_invest_def, stat_invest_hp, stat_invest_gold "
            "FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return {"atk": 0, "def": 0, "hp": 0, "gold": 0}
        return {
            "atk": row["stat_invest_atk"],
            "def": row["stat_invest_def"],
            "hp": row["stat_invest_hp"],
            "gold": row["stat_invest_gold"],
        }

    async def invest_stat_point(self, user_id: str, server_id: str, stat: str) -> bool:
        """
        Spends 1 passive_point and allocates it to `stat` (atk/def/hp/gold).
        Returns False if no passive_points available.
        """
        col = f"stat_invest_{stat}"
        cursor = await self.connection.execute(
            "SELECT passive_points FROM player_currencies WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row or row["passive_points"] <= 0:
            return False
        await self.connection.execute(
            "UPDATE player_currencies SET passive_points = passive_points - 1 WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.execute(
            f"UPDATE users SET {col} = {col} + 1 WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()
        return True

    async def refund_stat_point(self, user_id: str, server_id: str, stat: str) -> bool:
        """
        Uses a Rune of Regret: removes 1 from `stat` investment, returns 1 passive_point.
        Returns False if no points invested in that stat, or no rune available.
        """
        col = f"stat_invest_{stat}"
        u_cursor = await self.connection.execute(
            f"SELECT {col} FROM users WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        u_row = await u_cursor.fetchone()
        c_cursor = await self.connection.execute(
            "SELECT rune_of_regret FROM player_currencies WHERE user_id = ?",
            (user_id,),
        )
        c_row = await c_cursor.fetchone()
        if not u_row or u_row[col] <= 0 or not c_row or c_row["rune_of_regret"] <= 0:
            return False
        await self.connection.execute(
            f"UPDATE users SET {col} = {col} - 1 WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.execute(
            "UPDATE player_currencies SET passive_points = passive_points + 1, "
            "rune_of_regret = rune_of_regret - 1 WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.commit()
        return True

    # ---------------------------------------------------------
    # Pending stat packages (level-up choice)
    # ---------------------------------------------------------

    async def get_pending_packages(self, user_id: str, server_id: str):
        """Returns the pending stat package JSON (list of 3 dicts) or None."""
        import json

        cursor = await self.connection.execute(
            "SELECT pending_stat_packages FROM users WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if row and row["pending_stat_packages"]:
            return json.loads(row["pending_stat_packages"])
        return None

    async def set_pending_packages(
        self, user_id: str, server_id: str, packages
    ) -> None:
        import json

        val = json.dumps(packages) if packages else None
        await self.connection.execute(
            "UPDATE users SET pending_stat_packages = ? WHERE user_id = ? AND server_id = ?",
            (val, user_id, server_id),
        )
        await self.connection.commit()
