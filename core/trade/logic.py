from typing import Optional, Tuple, Literal
from core.models import Weapon, Armor, Accessory, Glove, Boot, Helmet

class TradeManager:
    """Handles logic for mapping items/resources and executing transfers."""

    # Mappings for "Special Items" / Resources
    RESOURCE_MAP = {
        # Keys & Misc
        "Draconic Key": ("users", "dragon_key"),
        "Angelic Key": ("users", "angel_key"),
        "Void Key": ("users", "void_keys"),
        "Soul Core": ("users", "soul_cores"),
        "Void Fragment": ("users", "void_frags"),
        "Curio": ("users", "curios"),
        # Runes
        "Rune of Refinement": ("users", "refinement_runes"),
        "Rune of Potential": ("users", "potential_runes"),
        "Rune of Imbuing": ("users", "imbue_runes"),
        "Rune of Shattering": ("users", "shatter_runes"),
        # Mining
        "Iron Ore": ("mining", "iron"),
        "Coal": ("mining", "coal"),
        "Gold Ore": ("mining", "gold"),
        "Platinum Ore": ("mining", "platinum"),
        # Woodcutting
        "Oak Logs": ("woodcutting", "oak_logs"),
        "Willow Logs": ("woodcutting", "willow_logs"),
        "Mahogany Logs": ("woodcutting", "mahogany_logs"),
        "Magic Logs": ("woodcutting", "magic_logs"),
        # Fishing
        "Desiccated Bones": ("fishing", "desiccated_bones"),
        "Regular Bones": ("fishing", "regular_bones"),
        "Sturdy Bones": ("fishing", "sturdy_bones"),
        "Reinforced Bones": ("fishing", "reinforced_bones"),
    }

    @staticmethod
    async def get_resource_balance(bot, user_id: str, server_id: str, resource_name: str) -> int:
        table, col = TradeManager.RESOURCE_MAP[resource_name]
        
        if table == "users":
            return await bot.database.users.get_currency(user_id, col)
        else:
            # Skill tables: need to find the index of the column
            # We fetch the row and manually map it based on known schemas
            row = await bot.database.skills.get_data(user_id, server_id, table)
            if not row: return 0
            
            # This relies on the column order in the DB repository whitelist
            # A safer way is to perform a direct SELECT query for that specific column
            # But since we are inside logic layer, let's use a repository helper if available
            # or a raw specific query here to be precise.
            
            # Using raw query via connection for precision since repo methods are bulk getters
            cursor = await bot.database.connection.execute(f"SELECT {col} FROM {table} WHERE user_id=? AND server_id=?", (user_id, server_id))
            res = await cursor.fetchone()
            return res[0] if res else 0

    @staticmethod
    async def transfer_gold(bot, sender_id: str, receiver_id: str, amount: int) -> bool:
        sender_gold = await bot.database.users.get_gold(sender_id)
        if sender_gold < amount:
            return False
        await bot.database.users.modify_gold(sender_id, -amount)
        await bot.database.users.modify_gold(receiver_id, amount)
        return True

    @staticmethod
    async def transfer_resource(bot, sender_id: str, receiver_id: str, server_id: str, resource_name: str, amount: int):
        table, col = TradeManager.RESOURCE_MAP[resource_name]
        
        if table == "users":
            await bot.database.users.modify_currency(sender_id, col, -amount)
            await bot.database.users.modify_currency(receiver_id, col, amount)
        else:
            # Skill tables require server_id
            await bot.database.skills.update_single_resource(sender_id, server_id, table, col, -amount)
            await bot.database.skills.update_single_resource(receiver_id, server_id, table, col, amount)

    @staticmethod
    async def transfer_equipment(bot, sender_id: str, receiver_id: str, item_type: str, item_id: int):
        # Using the generic transfer method in equipment repo
        await bot.database.equipment.transfer(item_id, receiver_id, item_type)