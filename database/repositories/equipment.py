import aiosqlite
from typing import Literal, Optional, List, Tuple
from core.models import Weapon, Armor, Accessory, Glove, Boot

ItemType = Literal["weapon", "armor", "accessory", "glove", "boot"]

class EquipmentRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection
        # Map friendly names to DB Table names
        self.tables = {
            "weapon": "items",
            "armor": "armor",
            "accessory": "accessories",
            "accessories": "accessories",
            "glove": "gloves",
            "boot": "boots"
        }

    # ---------------------------------------------------------
    # Generic Management (Fetch, Equip, Discard, Transfer)
    # ---------------------------------------------------------

    async def get_all(self, user_id: str, item_type: ItemType) -> List[Tuple]:
        """Fetch all items of a specific type for a user."""
        table = self.tables[item_type]
        rows = await self.connection.execute(f"SELECT * FROM {table} WHERE user_id=?", (user_id,))
        async with rows as cursor:
            return await cursor.fetchall()

    async def get_by_id(self, item_id: int, item_type: ItemType) -> Optional[Tuple]:
        """Fetch a single item by ID."""
        table = self.tables[item_type]
        rows = await self.connection.execute(f"SELECT * FROM {table} WHERE item_id=?", (item_id,))
        async with rows as cursor:
            return await cursor.fetchone()

    async def get_equipped(self, user_id: str, item_type: ItemType) -> Optional[Tuple]:
        """Fetch the currently equipped item of a type."""
        table = self.tables[item_type]
        # Note: SQLite booleans are 1/0, so is_equipped=1 works generally
        rows = await self.connection.execute(
            f"SELECT * FROM {table} WHERE user_id = ? AND is_equipped = 1", 
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def equip(self, user_id: str, item_id: int, item_type: ItemType) -> None:
        """Unequips current item of type, then equips the new one."""
        table = self.tables[item_type]
        # 1. Unequip all (safety)
        await self.connection.execute(
            f"UPDATE {table} SET is_equipped = 0 WHERE user_id = ? AND is_equipped = 1",
            (user_id,)
        )
        # 2. Equip specific
        await self.connection.execute(
            f"UPDATE {table} SET is_equipped = 1 WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    async def unequip(self, user_id: str, item_type: ItemType) -> None:
        """Unequips item of type."""
        table = self.tables[item_type]
        await self.connection.execute(
            f"UPDATE {table} SET is_equipped = 0 WHERE user_id = ? AND is_equipped = 1",
            (user_id,)
        )
        await self.connection.commit()

    async def discard(self, item_id: int, item_type: ItemType) -> None:
        """Permanently delete an item."""
        table = self.tables[item_type]
        await self.connection.execute(f"DELETE FROM {table} WHERE item_id = ?", (item_id,))
        await self.connection.commit()

    async def transfer(self, item_id: int, new_user_id: str, item_type: ItemType) -> None:
        """Send item to another player (updates user_id)."""
        table = self.tables[item_type]
        # Also unequip it to be safe
        await self.connection.execute(
            f"UPDATE {table} SET user_id = ?, is_equipped = 0 WHERE item_id = ?",
            (new_user_id, item_id)
        )
        await self.connection.commit()

    async def get_count(self, user_id: str, item_type: ItemType) -> int:
        """Count items of a type (for inventory limits)."""
        table = self.tables[item_type]
        rows = await self.connection.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,))
        res = await rows.fetchone()
        return res[0] if res else 0

    # ---------------------------------------------------------
    # Creation (Insert)
    # ---------------------------------------------------------

    async def create_weapon(self, w: Weapon) -> None:
        potential = 3 if w.level <= 40 else (4 if w.level <= 80 else 5)
        await self.connection.execute(
            """INSERT INTO items (user_id, item_name, item_level, attack, defence, rarity, 
            is_equipped, forges_remaining, refines_remaining) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (w.user, w.name, w.level, w.attack, w.defence, w.rarity, potential, potential)
        )
        await self.connection.commit()

    async def create_armor(self, a: Armor) -> None:
        potential = 3 if a.level <= 40 else (4 if a.level <= 80 else 5)
        await self.connection.execute(
            """INSERT INTO armor (user_id, item_name, item_level, block, evasion, ward, 
            pdr, fdr, temper_remaining) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (a.user, a.name, a.level, a.block, a.evasion, a.ward, a.pdr, a.fdr, potential)
        )
        await self.connection.commit()

    async def create_accessory(self, a: Accessory) -> None:
        await self.connection.execute(
            """INSERT INTO accessories (user_id, item_name, item_level, attack, defence, 
            rarity, ward, crit, is_equipped, potential_remaining, passive_lvl) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 10, 0)""",
            (a.user, a.name, a.level, a.attack, a.defence, a.rarity, a.ward, a.crit)
        )
        await self.connection.commit()

    async def create_glove(self, g: Glove) -> None:
        await self.connection.execute(
            """INSERT INTO gloves (user_id, item_name, item_level, attack, defence, ward, 
            pdr, fdr, passive, is_equipped, potential_remaining, passive_lvl) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 5, 0)""",
            (g.user, g.name, g.level, g.attack, g.defence, g.ward, g.pdr, g.fdr, g.passive)
        )
        await self.connection.commit()

    async def create_boot(self, b: Boot) -> None:
        await self.connection.execute(
            """INSERT INTO boots (user_id, item_name, item_level, attack, defence, ward, 
            pdr, fdr, passive, is_equipped, potential_remaining, passive_lvl) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 6, 0)""",
            (b.user, b.name, b.level, b.attack, b.defence, b.ward, b.pdr, b.fdr, b.passive)
        )
        await self.connection.commit()

    # ---------------------------------------------------------
    # Upgrades & Modifications (Specifics)
    # ---------------------------------------------------------

    async def update_passive(self, item_id: int, item_type: ItemType, passive_name: str, passive_column: str = "passive") -> None:
        """Updates a passive column (passive, pinnacle_passive, utmost_passive, armor_passive)."""
        table = self.tables[item_type]
        await self.connection.execute(f"UPDATE {table} SET {passive_column} = ? WHERE item_id = ?", (passive_name, item_id))
        await self.connection.commit()

    async def update_counter(self, item_id: int, item_type: ItemType, column: str, new_value: int) -> None:
        """Updates an integer counter (potential, forges, refines, level)."""
        table = self.tables[item_type]
        # Basic validation to prevent arbitrary SQL injection if column comes from untrusted source
        allowed = ["forges_remaining", "refines_remaining", "refinement_lvl", "potential_remaining", 
                   "passive_lvl", "temper_remaining", "imbue_remaining"]
        if column not in allowed:
            raise ValueError(f"Invalid column for update_counter: {column}")
            
        await self.connection.execute(f"UPDATE {table} SET {column} = ? WHERE item_id = ?", (new_value, item_id))
        await self.connection.commit()

    async def increase_stat(self, item_id: int, item_type: ItemType, stat: str, amount: int) -> None:
        """Increments a stat (attack, defence, pdr, fdr, rarity, block, etc)."""
        table = self.tables[item_type]
        await self.connection.execute(f"UPDATE {table} SET {stat} = {stat} + ? WHERE item_id = ?", (amount, item_id))
        await self.connection.commit()

    async def fetch_void_forge_candidates(self, user_id: str) -> List[Tuple]:
        """Specific query for Voidforge eligibility."""
        # Requirements: Refinement >= 5, Forges = 0, Unequipped
        rows = await self.connection.execute(
            "SELECT * FROM items WHERE user_id = ? AND refinement_lvl >= 5 AND forges_remaining = 0 AND is_equipped = 0",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()