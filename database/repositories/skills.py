from typing import Dict, List, Literal, Tuple

import aiosqlite

SkillType = Literal["mining", "fishing", "woodcutting"]


class SkillRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

        # Whitelist for dynamic SQL generation to prevent injection (raw resources)
        self.allowed_columns = {
            "mining": ["iron", "coal", "gold", "platinum", "idea", "pickaxe_tier"],
            "woodcutting": [
                "oak_logs",
                "willow_logs",
                "mahogany_logs",
                "magic_logs",
                "idea_logs",
                "axe_type",
            ],
            "fishing": [
                "desiccated_bones",
                "regular_bones",
                "sturdy_bones",
                "reinforced_bones",
                "titanium_bones",
                "fishing_rod",
            ],
        }

        # Extended whitelist covering both raw and refined (used by upgrade views, trade)
        self.allowed_columns_extended = {
            "mining": [
                "iron",
                "iron_bar",
                "coal",
                "steel_bar",
                "gold",
                "gold_bar",
                "platinum",
                "platinum_bar",
                "idea",
                "idea_bar",
                "pickaxe_tier",
            ],
            "woodcutting": [
                "oak_logs",
                "oak_plank",
                "willow_logs",
                "willow_plank",
                "mahogany_logs",
                "mahogany_plank",
                "magic_logs",
                "magic_plank",
                "idea_logs",
                "idea_plank",
                "axe_type",
            ],
            "fishing": [
                "desiccated_bones",
                "desiccated_essence",
                "regular_bones",
                "regular_essence",
                "sturdy_bones",
                "sturdy_essence",
                "reinforced_bones",
                "reinforced_essence",
                "titanium_bones",
                "titanium_essence",
                "fishing_rod",
            ],
        }

    # ---------------------------------------------------------
    # Data Retrieval
    # ---------------------------------------------------------

    async def get_single_resource(
        self, user_id: str, server_id: str, skill_type: str, column: str
    ) -> int:
        """Fetch a single resource amount from a skill table."""
        allowed = self.allowed_columns_extended.get(skill_type, [])
        if column not in allowed:
            raise ValueError(f"Invalid column '{column}' for skill '{skill_type}'")
        async with self.connection.execute(
            f"SELECT {column} FROM {skill_type} WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_multi_resource(
        self, user_id: str, server_id: str, skill_type: str, columns: list
    ) -> tuple:
        """Fetch multiple resource columns from a skill table in one query."""
        allowed = self.allowed_columns_extended.get(skill_type, [])
        for col in columns:
            if col not in allowed:
                raise ValueError(f"Invalid column '{col}' for skill '{skill_type}'")
        col_str = ", ".join(columns)
        async with self.connection.execute(
            f"SELECT {col_str} FROM {skill_type} WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row if row else tuple(0 for _ in columns)

    async def deduct_resource_atomic(
        self, user_id: str, server_id: str, skill_type: str, column: str, qty: int
    ) -> bool:
        """Deduct qty from a skill resource only if sufficient balance exists. Returns True on success."""
        allowed = self.allowed_columns_extended.get(skill_type, [])
        if column not in allowed:
            raise ValueError(f"Invalid column '{column}' for skill '{skill_type}'")
        async with self.connection.execute(
            f"UPDATE {skill_type} SET {column} = {column} - ? WHERE user_id=? AND server_id=? AND {column} >= ?",
            (qty, user_id, server_id, qty),
        ) as cursor:
            return cursor.rowcount > 0

    async def get_data(
        self, user_id: str, server_id: str, skill_type: SkillType
    ) -> Tuple:
        """Fetch the skill row for a user."""
        rows = await self.connection.execute(
            f"SELECT * FROM {skill_type} WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def get_all_users(self, skill_type: SkillType) -> List[Tuple]:
        """Fetch all users who have this skill initialized (for regeneration tasks)."""
        rows = await self.connection.execute(
            f"SELECT user_id, server_id FROM {skill_type}"
        )
        async with rows as cursor:
            return await cursor.fetchall()

    # ---------------------------------------------------------
    # Initialization & Updates
    # ---------------------------------------------------------

    async def initialize(
        self, user_id: str, server_id: str, skill_type: SkillType, tool_tier: str
    ) -> None:
        """Insert a new entry for a skill."""
        tool_col = (
            "pickaxe_tier"
            if skill_type == "mining"
            else ("fishing_rod" if skill_type == "fishing" else "axe_type")
        )

        await self.connection.execute(
            f"INSERT INTO {skill_type} (user_id, server_id, {tool_col}) VALUES (?, ?, ?)",
            (user_id, server_id, tool_tier),
        )
        await self.connection.commit()

    async def update_single_resource(
        self,
        user_id: str,
        server_id: str,
        skill_type: SkillType,
        resource: str,
        amount: int,
    ) -> None:
        """Update a specific resource count."""
        # Sanity check column name
        if resource not in self.allowed_columns[skill_type]:
            raise ValueError(
                f"Invalid resource column '{resource}' for skill '{skill_type}'"
            )

        await self.connection.execute(
            f"UPDATE {skill_type} SET {resource} = {resource} + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def update_batch(
        self,
        user_id: str,
        server_id: str,
        skill_type: SkillType,
        resources: Dict[str, int],
    ) -> None:
        """
        Updates multiple resources at once.
        'resources' should be a dict like {'iron': 5, 'coal': 2}
        """
        if not resources:
            return

        # Dynamic SQL Construction (Safe because we whitelist keys)
        updates = []
        values = []

        for col, amount in resources.items():
            if col in self.allowed_columns[skill_type]:
                updates.append(f"{col} = {col} + ?")
                values.append(amount)

        if not updates:
            return

        query = f"UPDATE {skill_type} SET {', '.join(updates)} WHERE user_id = ? AND server_id = ?"
        values.extend([user_id, server_id])

        await self.connection.execute(query, tuple(values))
        await self.connection.commit()

    # ---------------------------------------------------------
    # Tool Upgrades (Specific Transactions)
    # ---------------------------------------------------------
    # Kept specific due to complex transaction logic (Gold + Multiple Resources + Tier Update)

    async def upgrade_pickaxe(
        self, user_id: str, server_id: str, new_tier: str, costs: tuple
    ) -> None:
        iron, coal, gold, platinum, gp = costs
        await self.connection.execute(
            """UPDATE mining SET iron=iron-?, coal=coal-?, gold=gold-?, platinum=platinum-?, pickaxe_tier=? 
            WHERE user_id=? AND server_id=?""",
            (iron, coal, gold, platinum, new_tier, user_id, server_id),
        )
        await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ?", (gp, user_id)
        )
        await self.connection.commit()

    async def upgrade_axe(
        self, user_id: str, server_id: str, new_tier: str, costs: tuple
    ) -> None:
        oak, willow, mahogany, magic, gp = costs
        await self.connection.execute(
            """UPDATE woodcutting SET oak_logs=oak_logs-?, willow_logs=willow_logs-?, mahogany_logs=mahogany_logs-?, magic_logs=magic_logs-?, axe_type=? 
            WHERE user_id=? AND server_id=?""",
            (oak, willow, mahogany, magic, new_tier, user_id, server_id),
        )
        await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ?", (gp, user_id)
        )
        await self.connection.commit()

    # ---------------------------------------------------------
    # Upgrade material helpers (used by upgrade views via base.py)
    # ---------------------------------------------------------

    async def get_upgrade_materials(
        self, user_id: str, server_id: str, cols: dict
    ) -> tuple:
        """Fetch (raw, refined) amounts for ore, log, and bone in one call.

        `cols` is the dict returned by BaseUpgradeView._resolve_material_columns:
          {"ore": {"raw_col": ..., "ref_col": ...},
           "log": {"raw_col": ..., "ref_col": ...},
           "bone": {"raw_col": ..., "ref_col": ...}}
        Returns (mining_res, wood_res, fish_res) as (raw, refined) tuples.
        """
        mining_res = await self.get_multi_resource(
            user_id, server_id, "mining",
            [cols["ore"]["raw_col"], cols["ore"]["ref_col"]],
        )
        wood_res = await self.get_multi_resource(
            user_id, server_id, "woodcutting",
            [cols["log"]["raw_col"], cols["log"]["ref_col"]],
        )
        fish_res = await self.get_multi_resource(
            user_id, server_id, "fishing",
            [cols["bone"]["raw_col"], cols["bone"]["ref_col"]],
        )
        return mining_res, wood_res, fish_res

    async def deduct_upgrade_material(
        self,
        user_id: str,
        server_id: str,
        table: str,
        raw_col: str,
        ref_col: str,
        raw_held: int,
        cost: int,
    ) -> None:
        """Deduct cost from raw resources first, spilling into refined if needed."""
        to_take_raw = min(raw_held, cost)
        to_take_ref = cost - to_take_raw
        if to_take_raw > 0:
            await self.deduct_resource_atomic(user_id, server_id, table, raw_col, to_take_raw)
        if to_take_ref > 0:
            await self.deduct_resource_atomic(user_id, server_id, table, ref_col, to_take_ref)

    async def charge_entry_cost(self, user_id: str, gold_amount: int) -> None:
        """Deducts gold from a user for a minigame entry cost (bait / forestry pass)."""
        await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ?",
            (gold_amount, user_id),
        )
        await self.connection.commit()

    async def upgrade_fishing_rod(
        self, user_id: str, server_id: str, new_tier: str, costs: tuple
    ) -> None:
        des, reg, stu, rein, gp = costs
        await self.connection.execute(
            """UPDATE fishing SET desiccated_bones=desiccated_bones-?, regular_bones=regular_bones-?, sturdy_bones=sturdy_bones-?, reinforced_bones=reinforced_bones-?, fishing_rod=? 
            WHERE user_id=? AND server_id=?""",
            (des, reg, stu, rein, new_tier, user_id, server_id),
        )
        await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ?", (gp, user_id)
        )
        await self.connection.commit()
