from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import aiosqlite

from database.base import BaseRepository

# Allowlist prevents SQL injection through dynamic column names
_VALID_SKILL_COLS = frozenset({
    "combat_slot_1", "combat_slot_1_lvl",
    "combat_slot_2", "combat_slot_2_lvl",
    "combat_slot_3", "combat_slot_3_lvl",
    "sig_combat_lvl",
    "dispatch_slot_1", "dispatch_slot_1_lvl",
    "dispatch_slot_2", "dispatch_slot_2_lvl",
    "dispatch_slot_3", "dispatch_slot_3_lvl",
    "sig_dispatch_lvl",
})


class PartnerRepository(BaseRepository):

    # ------------------------------------------------------------------
    # Items row  (guild_tickets, pity, shards)
    # ------------------------------------------------------------------

    async def ensure_items_row(self, user_id: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO user_partner_items (user_id) VALUES (?)",
            (user_id,),
        )
        await self.connection.commit()

    async def get_items(self, user_id: str) -> Dict[str, int]:
        await self.ensure_items_row(user_id)
        cursor = await self.connection.execute(
            "SELECT guild_tickets, pity_counter, combat_skill_shards, dispatch_skill_shards "
            "FROM user_partner_items WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        char_shards = await self.get_shard_count(user_id, 0)  # shared pool (partner_id=0)
        return {
            "guild_tickets": row[0],
            "pity_counter": row[1],
            "combat_skill_shards": row[2],
            "dispatch_skill_shards": row[3],
            "char_shards": char_shards,
        }

    async def add_tickets(self, user_id: str, amount: int) -> None:
        await self.ensure_items_row(user_id)
        await self.connection.execute(
            "UPDATE user_partner_items SET guild_tickets = guild_tickets + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def spend_tickets(self, user_id: str, amount: int) -> bool:
        """Returns False if insufficient tickets."""
        items = await self.get_items(user_id)
        if items["guild_tickets"] < amount:
            return False
        await self.connection.execute(
            "UPDATE user_partner_items SET guild_tickets = guild_tickets - ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()
        return True

    async def update_pity(self, user_id: str, counter: int) -> None:
        await self.ensure_items_row(user_id)
        await self.connection.execute(
            "UPDATE user_partner_items SET pity_counter = ? WHERE user_id = ?",
            (counter, user_id),
        )
        await self.connection.commit()

    async def add_combat_shards(self, user_id: str, amount: int) -> None:
        await self.ensure_items_row(user_id)
        await self.connection.execute(
            "UPDATE user_partner_items SET combat_skill_shards = combat_skill_shards + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def add_dispatch_shards(self, user_id: str, amount: int) -> None:
        await self.ensure_items_row(user_id)
        await self.connection.execute(
            "UPDATE user_partner_items SET dispatch_skill_shards = dispatch_skill_shards + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def spend_combat_shards(self, user_id: str, amount: int) -> bool:
        items = await self.get_items(user_id)
        if items["combat_skill_shards"] < amount:
            return False
        await self.connection.execute(
            "UPDATE user_partner_items SET combat_skill_shards = combat_skill_shards - ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()
        return True

    async def spend_dispatch_shards(self, user_id: str, amount: int) -> bool:
        items = await self.get_items(user_id)
        if items["dispatch_skill_shards"] < amount:
            return False
        await self.connection.execute(
            "UPDATE user_partner_items SET dispatch_skill_shards = dispatch_skill_shards - ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()
        return True

    # ------------------------------------------------------------------
    # Character shards  (6★ signature upgrades)
    # ------------------------------------------------------------------

    async def get_shard_count(self, user_id: str, partner_id: int) -> int:
        cursor = await self.connection.execute(
            "SELECT shard_count FROM user_partner_shards WHERE user_id = ? AND partner_id = ?",
            (user_id, partner_id),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def add_shard(self, user_id: str, partner_id: int, amount: int) -> None:
        await self.connection.execute(
            """INSERT INTO user_partner_shards (user_id, partner_id, shard_count)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, partner_id) DO UPDATE SET shard_count = shard_count + ?""",
            (user_id, partner_id, amount, amount),
        )
        await self.connection.commit()

    async def spend_shard(self, user_id: str, partner_id: int, amount: int) -> bool:
        count = await self.get_shard_count(user_id, partner_id)
        if count < amount:
            return False
        await self.connection.execute(
            "UPDATE user_partner_shards SET shard_count = shard_count - ? WHERE user_id = ? AND partner_id = ?",
            (amount, user_id, partner_id),
        )
        await self.connection.commit()
        return True

    # ------------------------------------------------------------------
    # Partner rows
    # ------------------------------------------------------------------

    async def get_owned(self, user_id: str) -> List[Tuple]:
        cursor = await self.connection.execute(
            "SELECT * FROM user_partners WHERE user_id = ? ORDER BY partner_id",
            (user_id,),
        )
        return await cursor.fetchall()

    async def get_partner(self, user_id: str, partner_id: int) -> Optional[Tuple]:
        cursor = await self.connection.execute(
            "SELECT * FROM user_partners WHERE user_id = ? AND partner_id = ?",
            (user_id, partner_id),
        )
        return await cursor.fetchone()

    async def get_active_combat(self, user_id: str) -> Optional[Tuple]:
        cursor = await self.connection.execute(
            "SELECT * FROM user_partners WHERE user_id = ? AND is_active_combat = 1",
            (user_id,),
        )
        return await cursor.fetchone()

    async def get_active_dispatch(self, user_id: str) -> Optional[Tuple]:
        cursor = await self.connection.execute(
            "SELECT * FROM user_partners WHERE user_id = ? AND is_dispatched = 1",
            (user_id,),
        )
        return await cursor.fetchone()

    async def owns_partner(self, user_id: str, partner_id: int) -> bool:
        row = await self.get_partner(user_id, partner_id)
        return row is not None

    async def add_partner(
        self,
        user_id: str,
        partner_id: int,
        combat_slots: List[Optional[str]],
        dispatch_slots: List[Optional[str]],
    ) -> None:
        """Insert a newly-obtained partner. Slots are lists of up to 3 skill keys (None for empty)."""
        c = (combat_slots + [None, None, None])[:3]
        d = (dispatch_slots + [None, None, None])[:3]
        await self.connection.execute(
            """INSERT OR IGNORE INTO user_partners
               (user_id, partner_id,
                combat_slot_1, combat_slot_2, combat_slot_3,
                dispatch_slot_1, dispatch_slot_2, dispatch_slot_3)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, partner_id, c[0], c[1], c[2], d[0], d[1], d[2]),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Active partner assignment
    # ------------------------------------------------------------------

    async def set_active_combat(self, user_id: str, partner_id: int) -> None:
        await self.connection.execute(
            "UPDATE user_partners SET is_active_combat = 0 WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.execute(
            "UPDATE user_partners SET is_active_combat = 1 WHERE user_id = ? AND partner_id = ?",
            (user_id, partner_id),
        )
        await self.connection.commit()

    async def clear_active_combat(self, user_id: str) -> None:
        await self.connection.execute(
            "UPDATE user_partners SET is_active_combat = 0 WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.commit()

    async def set_dispatch(
        self,
        user_id: str,
        partner_id: int,
        task: str,
        start_time: str,
    ) -> None:
        await self.connection.execute(
            "UPDATE user_partners SET is_dispatched = 0 WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.execute(
            """UPDATE user_partners
               SET is_dispatched = 1, dispatch_task = ?, dispatch_start_time = ?
               WHERE user_id = ? AND partner_id = ?""",
            (task, start_time, user_id, partner_id),
        )
        await self.connection.commit()

    async def set_dispatch_2(
        self,
        user_id: str,
        partner_id: int,
        task: str,
        start_time: str,
    ) -> None:
        """Sets the secondary dispatch slot (Sigmund sig only)."""
        await self.connection.execute(
            """UPDATE user_partners
               SET dispatch_task_2 = ?, dispatch_start_time_2 = ?
               WHERE user_id = ? AND partner_id = ?""",
            (task, start_time, user_id, partner_id),
        )
        await self.connection.commit()

    async def reset_dispatch_timer(self, user_id: str, partner_id: int, new_start: str) -> None:
        """Resets the primary dispatch timer after reward collection."""
        await self.connection.execute(
            "UPDATE user_partners SET dispatch_start_time = ? WHERE user_id = ? AND partner_id = ?",
            (new_start, user_id, partner_id),
        )
        await self.connection.commit()

    async def reset_dispatch_timer_2(self, user_id: str, partner_id: int, new_start: str) -> None:
        await self.connection.execute(
            "UPDATE user_partners SET dispatch_start_time_2 = ? WHERE user_id = ? AND partner_id = ?",
            (new_start, user_id, partner_id),
        )
        await self.connection.commit()

    async def clear_dispatch(self, user_id: str, partner_id: int) -> None:
        await self.connection.execute(
            """UPDATE user_partners
               SET is_dispatched = 0,
                   dispatch_task = NULL, dispatch_start_time = NULL,
                   dispatch_task_2 = NULL, dispatch_start_time_2 = NULL
               WHERE user_id = ? AND partner_id = ?""",
            (user_id, partner_id),
        )
        await self.connection.commit()

    async def set_boss_party_dispatch(
        self,
        user_id: str,
        attacker_id: int,
        tank_id: int,
        healer_id: int,
        start_time: str,
    ) -> None:
        """Marks three partners as dispatched on a boss party without clearing others."""
        for pid in (attacker_id, tank_id, healer_id):
            await self.connection.execute(
                """UPDATE user_partners
                   SET is_dispatched = 1, dispatch_task = 'boss_party',
                       dispatch_start_time = ?
                   WHERE user_id = ? AND partner_id = ?""",
                (start_time, user_id, pid),
            )
        await self.connection.commit()

    async def clear_boss_party_dispatch(
        self,
        user_id: str,
        attacker_id: int,
        tank_id: int,
        healer_id: int,
    ) -> None:
        """Clears dispatch state for all three boss party members."""
        for pid in (attacker_id, tank_id, healer_id):
            await self.connection.execute(
                """UPDATE user_partners
                   SET is_dispatched = 0, dispatch_task = NULL,
                       dispatch_start_time = NULL
                   WHERE user_id = ? AND partner_id = ?""",
                (user_id, pid),
            )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Skill upgrades / rerolls
    # ------------------------------------------------------------------

    async def update_skill_slot(
        self,
        user_id: str,
        partner_id: int,
        key_col: str,
        key: Optional[str],
        lvl_col: str,
        lvl: int,
    ) -> None:
        if key_col not in _VALID_SKILL_COLS or lvl_col not in _VALID_SKILL_COLS:
            raise ValueError(f"Invalid skill column: {key_col!r} or {lvl_col!r}")
        await self.connection.execute(
            f"UPDATE user_partners SET {key_col} = ?, {lvl_col} = ? WHERE user_id = ? AND partner_id = ?",
            (key, lvl, user_id, partner_id),
        )
        await self.connection.commit()

    async def update_skill_level(
        self,
        user_id: str,
        partner_id: int,
        lvl_col: str,
        lvl: int,
    ) -> None:
        if lvl_col not in _VALID_SKILL_COLS:
            raise ValueError(f"Invalid skill column: {lvl_col!r}")
        await self.connection.execute(
            f"UPDATE user_partners SET {lvl_col} = ? WHERE user_id = ? AND partner_id = ?",
            (lvl, user_id, partner_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Leveling
    # ------------------------------------------------------------------

    async def update_exp(
        self, user_id: str, partner_id: int, exp: int, level: int
    ) -> None:
        await self.connection.execute(
            "UPDATE user_partners SET exp = ?, level = ? WHERE user_id = ? AND partner_id = ?",
            (exp, level, user_id, partner_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Affinity
    # ------------------------------------------------------------------

    async def increment_affinity(self, user_id: str, partner_id: int) -> None:
        await self.connection.execute(
            "UPDATE user_partners SET affinity_encounters = affinity_encounters + 1 "
            "WHERE user_id = ? AND partner_id = ?",
            (user_id, partner_id),
        )
        await self.connection.commit()

    async def update_affinity_story_seen(
        self, user_id: str, partner_id: int, story_index: int
    ) -> None:
        await self.connection.execute(
            "UPDATE user_partners SET affinity_story_seen = ? WHERE user_id = ? AND partner_id = ?",
            (story_index, user_id, partner_id),
        )
        await self.connection.commit()

    async def update_portrait(
        self, user_id: str, partner_id: int, variant: int
    ) -> None:
        await self.connection.execute(
            "UPDATE user_partners SET portrait_variant = ? WHERE user_id = ? AND partner_id = ?",
            (variant, user_id, partner_id),
        )
        await self.connection.commit()
