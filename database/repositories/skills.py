import aiosqlite
from typing import Literal, List, Tuple, Dict

SkillType = Literal["mining", "fishing", "woodcutting"]

class SkillRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection
        
        # Whitelist for dynamic SQL generation to prevent injection
        self.allowed_columns = {
            "mining": ["iron", "coal", "gold", "platinum", "idea", "pickaxe_tier"],
            "woodcutting": ["oak_logs", "willow_logs", "mahogany_logs", "magic_logs", "idea_logs", "axe_type"],
            "fishing": ["desiccated_bones", "regular_bones", "sturdy_bones", "reinforced_bones", "titanium_bones", "fishing_rod"]
        }

    # ---------------------------------------------------------
    # Data Retrieval
    # ---------------------------------------------------------

    async def get_data(self, user_id: str, server_id: str, skill_type: SkillType) -> Tuple:
        """Fetch the skill row for a user."""
        rows = await self.connection.execute(
            f"SELECT * FROM {skill_type} WHERE user_id=? AND server_id=?",
            (user_id, server_id)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def get_all_users(self, skill_type: SkillType) -> List[Tuple]:
        """Fetch all users who have this skill initialized (for regeneration tasks)."""
        rows = await self.connection.execute(f"SELECT user_id, server_id FROM {skill_type}")
        async with rows as cursor:
            return await cursor.fetchall()

    # ---------------------------------------------------------
    # Initialization & Updates
    # ---------------------------------------------------------

    async def initialize(self, user_id: str, server_id: str, skill_type: SkillType, tool_tier: str) -> None:
        """Insert a new entry for a skill."""
        tool_col = "pickaxe_tier" if skill_type == "mining" else ("fishing_rod" if skill_type == "fishing" else "axe_type")
        
        await self.connection.execute(
            f"INSERT INTO {skill_type} (user_id, server_id, {tool_col}) VALUES (?, ?, ?)",
            (user_id, server_id, tool_tier)
        )
        await self.connection.commit()

    async def update_single_resource(self, user_id: str, server_id: str, skill_type: SkillType, resource: str, amount: int) -> None:
        """Update a specific resource count."""
        # Sanity check column name
        if resource not in self.allowed_columns[skill_type]:
            raise ValueError(f"Invalid resource column '{resource}' for skill '{skill_type}'")

        await self.connection.execute(
            f"UPDATE {skill_type} SET {resource} = {resource} + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id)
        )
        await self.connection.commit()

    async def update_batch(self, user_id: str, server_id: str, skill_type: SkillType, resources: Dict[str, int]) -> None:
        """
        Updates multiple resources at once.
        'resources' should be a dict like {'iron': 5, 'coal': 2}
        """
        if not resources: return

        # Dynamic SQL Construction (Safe because we whitelist keys)
        updates = []
        values = []
        
        for col, amount in resources.items():
            if col in self.allowed_columns[skill_type]:
                updates.append(f"{col} = {col} + ?")
                values.append(amount)
        
        if not updates: return

        query = f"UPDATE {skill_type} SET {', '.join(updates)} WHERE user_id = ? AND server_id = ?"
        values.extend([user_id, server_id])

        await self.connection.execute(query, tuple(values))
        await self.connection.commit()

    # ---------------------------------------------------------
    # Tool Upgrades (Specific Transactions)
    # ---------------------------------------------------------
    # Kept specific due to complex transaction logic (Gold + Multiple Resources + Tier Update)

    async def upgrade_pickaxe(self, user_id: str, server_id: str, new_tier: str, costs: tuple) -> None:
        iron, coal, gold, platinum, gp = costs
        await self.connection.execute(
            """UPDATE mining SET iron=iron-?, coal=coal-?, gold=gold-?, platinum=platinum-?, pickaxe_tier=? 
            WHERE user_id=? AND server_id=?""",
            (iron, coal, gold, platinum, new_tier, user_id, server_id)
        )
        await self.connection.execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (gp, user_id))
        await self.connection.commit()

    async def upgrade_axe(self, user_id: str, server_id: str, new_tier: str, costs: tuple) -> None:
        oak, willow, mahogany, magic, gp = costs
        await self.connection.execute(
            """UPDATE woodcutting SET oak_logs=oak_logs-?, willow_logs=willow_logs-?, mahogany_logs=mahogany_logs-?, magic_logs=magic_logs-?, axe_type=? 
            WHERE user_id=? AND server_id=?""",
            (oak, willow, mahogany, magic, new_tier, user_id, server_id)
        )
        await self.connection.execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (gp, user_id))
        await self.connection.commit()

    async def upgrade_fishing_rod(self, user_id: str, server_id: str, new_tier: str, costs: tuple) -> None:
        des, reg, stu, rein, gp = costs
        await self.connection.execute(
            """UPDATE fishing SET desiccated_bones=desiccated_bones-?, regular_bones=regular_bones-?, sturdy_bones=sturdy_bones-?, reinforced_bones=reinforced_bones-?, fishing_rod=? 
            WHERE user_id=? AND server_id=?""",
            (des, reg, stu, rein, new_tier, user_id, server_id)
        )
        await self.connection.execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (gp, user_id))
        await self.connection.commit()