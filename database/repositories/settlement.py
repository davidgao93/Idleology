# database/repositories/settlement.py

import aiosqlite
from typing import Optional, List
from core.models import Settlement, Building

class SettlementRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_settlement(self, user_id: str, server_id: str) -> Settlement:
        """Fetches settlement or creates default if missing."""
        cursor = await self.connection.execute(
            "SELECT * FROM settlements WHERE user_id = ? AND server_id = ?",
            (user_id, server_id)
        )
        row = await cursor.fetchone()
        
        if not row:
            # Create Default
            await self.connection.execute(
                "INSERT INTO settlements (user_id, server_id, town_hall_tier, building_slots, last_collection_time) VALUES (?, ?, 1, 5, datetime('now'))",
                (user_id, server_id)
            )
            await self.connection.commit()
            return await self.get_settlement(user_id, server_id) # Recurse once

        # Fetch Buildings
        settlement = Settlement(
            user_id=row[0], server_id=row[1], town_hall_tier=row[2],
            building_slots=row[3], timber=row[4], stone=row[5], 
            last_collection_time=row[6]
        )
        
        b_cursor = await self.connection.execute(
            "SELECT * FROM buildings WHERE user_id = ? AND server_id = ? ORDER BY slot_index ASC",
            (user_id, server_id)
        )
        b_rows = await b_cursor.fetchall()
        settlement.buildings = [
            Building(id=r[0], user_id=r[1], server_id=r[2], building_type=r[3], 
                     tier=r[4], slot_index=r[5], workers_assigned=r[6])
            for r in b_rows
        ]
        
        return settlement

    async def build_structure(self, user_id: str, server_id: str, b_type: str, slot: int) -> None:
        await self.connection.execute(
            "INSERT INTO buildings (user_id, server_id, building_type, slot_index) VALUES (?, ?, ?, ?)",
            (user_id, server_id, b_type, slot)
        )
        await self.connection.commit()

    async def assign_workers(self, building_id: int, count: int) -> None:
        await self.connection.execute(
            "UPDATE buildings SET workers_assigned = ? WHERE id = ?",
            (count, building_id)
        )
        await self.connection.commit()

    async def update_collection_timer(self, user_id: str, server_id: str):
        """Updates collection timer using Python time for consistency."""
        from datetime import datetime
        current_time = datetime.now().isoformat()
        
        await self.connection.execute(
            "UPDATE settlements SET last_collection_time = ? WHERE user_id = ? AND server_id = ?",
            (current_time, user_id, server_id)
        )
        await self.connection.commit()

    async def commit_production(self, user_id: str, server_id: str, changes: dict):
        """
        Applies a batch of resource changes (Mining, Woodcutting, Fishing, Gold, Settlement).
        This is a complex transaction crossing multiple tables.
        """
        # 1. Gold
        if "gold" in changes:
            await self.connection.execute(
                "UPDATE users SET gold = gold + ? WHERE user_id = ?", (changes.pop("gold"), user_id)
            )

        # 2. Settlement Resources
        if "timber" in changes or "stone" in changes:
            t = changes.pop("timber", 0)
            s = changes.pop("stone", 0)
            await self.connection.execute(
                "UPDATE settlements SET timber = timber + ?, stone = stone + ? WHERE user_id = ? AND server_id = ?",
                (t, s, user_id, server_id)
            )

        # 3. Skills (Mining, Woodcutting, Fishing)
        # We need to sort keys by table
        # Allowed columns are defined in SkillRepository, but we can infer or hardcode mapping here
        # or call SkillRepository methods. Calling direct SQL here for atomicity is acceptable
        # given the strict MVC rules allow Repo to handle SQL.
        
        # Mappings based on prefixes or known lists
        tables = {
            "mining": ["iron", "iron_bar", "coal", "steel_bar", "gold", "gold_bar", "platinum", "platinum_bar", "idea", "idea_bar"],
            "woodcutting": ["oak_logs", "oak_plank", "willow_logs", "willow_plank", "mahogany_logs", "mahogany_plank", "magic_logs", "magic_plank", "idea_logs", "idea_plank"],
            "fishing": ["desiccated_bones", "desiccated_essence", "regular_bones", "regular_essence", "sturdy_bones", "sturdy_essence", "reinforced_bones", "reinforced_essence", "titanium_bones", "titanium_essence"]
        }

        for table, cols in tables.items():
            updates = []
            values = []
            for col in cols:
                if col in changes:
                    val = changes[col]
                    updates.append(f"{col} = {col} + ?")
                    values.append(val)
            
            if updates:
                sql = f"UPDATE {table} SET {', '.join(updates)} WHERE user_id = ? AND server_id = ?"
                values.extend([user_id, server_id])
                await self.connection.execute(sql, tuple(values))

        await self.connection.commit()


    async def get_building_tier(self, user_id: str, server_id: str, building_type: str) -> int:
        """
        Efficiently fetches the tier of a specific building type. 
        Returns 0 if building does not exist.
        """
        cursor = await self.connection.execute(
            "SELECT tier FROM buildings WHERE user_id = ? AND server_id = ? AND building_type = ?",
            (user_id, server_id, building_type)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_used_slots_count(self, user_id: str, server_id: str) -> int:
        """Counts how many buildings a user has constructed."""
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM buildings WHERE user_id = ? AND server_id = ?",
            (user_id, server_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0