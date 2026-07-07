from typing import List, Optional

import aiosqlite

from .equipment import LOADOUT_SLOT_DEFS as _ITEM_QUERIES

SLOT_COSTS = {
    4: 50_000_000,
    5: 100_000_000,
    6: 250_000_000,
    7: 500_000_000,
    8: 1_000_000_000,
    9: 1_500_000_000,
    10: 2_000_000_000,
}


class LoadoutRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_slots_unlocked(self, user_id: str) -> int:
        cursor = await self.connection.execute(
            "SELECT loadout_slots FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row["loadout_slots"] if row else 3

    async def unlock_slot(self, user_id: str) -> None:
        await self.connection.execute(
            "UPDATE users SET loadout_slots = loadout_slots + 1 WHERE user_id = ?",
            (user_id,),
        )
        await self.connection.commit()

    async def ensure_default_rows(self, user_id: str, slots_unlocked: int) -> None:
        """Insert placeholder rows for any unlocked slot that has no row yet."""
        for i in range(1, slots_unlocked + 1):
            await self.connection.execute(
                "INSERT OR IGNORE INTO gear_loadouts (user_id, slot_index, name) VALUES (?, ?, ?)",
                (user_id, i, f"Loadout {i}"),
            )
        await self.connection.commit()

    async def get_all(self, user_id: str) -> List:
        cursor = await self.connection.execute(
            "SELECT * FROM gear_loadouts WHERE user_id = ? ORDER BY slot_index",
            (user_id,),
        )
        return await cursor.fetchall()

    async def get(self, user_id: str, slot_index: int) -> Optional:
        cursor = await self.connection.execute(
            "SELECT * FROM gear_loadouts WHERE user_id = ? AND slot_index = ?",
            (user_id, slot_index),
        )
        return await cursor.fetchone()

    async def save(
        self,
        user_id: str,
        slot_index: int,
        weapon_id,
        armor_id,
        helmet_id,
        glove_id,
        boot_id,
        accessory_id,
    ) -> None:
        await self.connection.execute(
            """INSERT INTO gear_loadouts
               (user_id, slot_index, weapon_id, armor_id, helmet_id, glove_id, boot_id, accessory_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, slot_index) DO UPDATE SET
                 weapon_id    = excluded.weapon_id,
                 armor_id     = excluded.armor_id,
                 helmet_id    = excluded.helmet_id,
                 glove_id     = excluded.glove_id,
                 boot_id      = excluded.boot_id,
                 accessory_id = excluded.accessory_id""",
            (
                user_id,
                slot_index,
                weapon_id,
                armor_id,
                helmet_id,
                glove_id,
                boot_id,
                accessory_id,
            ),
        )
        await self.connection.commit()

    async def rename(self, user_id: str, slot_index: int, name: str) -> None:
        await self.connection.execute(
            "UPDATE gear_loadouts SET name = ? WHERE user_id = ? AND slot_index = ?",
            (name, user_id, slot_index),
        )
        await self.connection.commit()

    async def get_item_names(self, loadout_row) -> dict:
        """
        Returns {slot_type: display_string} for each of the 6 gear slots.
        None  → slot was never saved.
        str   → item name (may be "⚠️ Missing" if the item no longer exists).
        """
        names = {}
        user_id = loadout_row["user_id"]
        for slot_type, id_col, table in _ITEM_QUERIES:
            item_id = loadout_row[id_col]
            if item_id is None:
                names[slot_type] = None
            else:
                cursor = await self.connection.execute(
                    f"SELECT item_name FROM {table} WHERE item_id = ? AND user_id = ?",
                    (item_id, user_id),
                )
                row = await cursor.fetchone()
                names[slot_type] = row["item_name"] if row else "⚠️ Missing"
        return names
