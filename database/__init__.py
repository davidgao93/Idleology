import aiosqlite
from datetime import datetime, timedelta
from core.models import Player, Weapon, Accessory, Armor, Glove, Boot
from .repositories.users import UserRepository
#from .repositories.equipment import EquipmentRepository
#from .repositories.skills import SkillRepository
#from .repositories.social import SocialRepository

class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection

        # Initialize sub-repositories
        self.users = UserRepository(connection)
        #self.equipment = EquipmentRepository(connection)
        #self.skills = SkillRepository(connection)
        #self.social = SocialRepository(connection)


    async def create_weapon(self, weapon: Weapon) -> None:
        """Create a weapon in the database."""
        item_potential = 0
        if (weapon.level) <= 40:
            item_potential = 3
        elif (40 < weapon.level <= 80):
            item_potential = 4
        else:
            item_potential = 5
        await self.connection.execute(
            """INSERT INTO items 
            (user_id, 
            item_name, 
            item_level, 
            attack, 
            defence, 
            rarity, 
            is_equipped, 
            forges_remaining, 
            refines_remaining) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (weapon.user, 
             weapon.name, 
             weapon.level, 
             weapon.attack, 
             weapon.defence, 
             weapon.rarity, 
             0, 
             item_potential, 
             item_potential)
        )
        await self.connection.commit()


    async def create_accessory(self, acc: Accessory) -> None:
        """
        Insert a new accessory into the accessories table.
        """
        # Insert the new accessory into the database
        await self.connection.execute(
            """INSERT INTO accessories 
            (user_id, 
            item_name, 
            item_level, 
            attack, 
            defence, 
            rarity, 
            ward, 
            crit, 
            is_equipped, 
            potential_remaining, 
            passive_lvl)"""
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (acc.user, 
             acc.name, 
             acc.level, 
             acc.attack, 
             acc.defence, 
             acc.rarity, 
             acc.ward, 
             acc.crit, 
             False, 
             10, 
             0)
        )
        await self.connection.commit()


    async def create_armor(self, armor: Armor) -> None:
        """Insert a new armor in the database."""
        item_potential = 0
        if (armor.level) <= 40:
            item_potential = 3
        elif (40 < armor.level <= 80):
            item_potential = 4
        else:
            item_potential = 5

        await self.connection.execute(
            """INSERT INTO armor 
            (user_id, 
            item_name, 
            item_level, 
            block, 
            evasion, 
            ward, 
            pdr,
            fdr,
            temper_remaining) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (armor.user, 
             armor.name, 
             armor.level, 
             armor.block, 
             armor.evasion, 
             armor.ward, 
             armor.pdr,
             armor.fdr,
             item_potential)
        )
        await self.connection.commit()

    async def create_glove(self, glove: Glove) -> None:
        """Insert a new glove into the gloves table."""
        # Defaults from schema: potential_remaining=5, passive_lvl=0, is_equipped=False
        await self.connection.execute(
            """INSERT INTO gloves 
            (user_id, item_name, item_level, attack, defence, ward, pdr, fdr, passive, 
             is_equipped, potential_remaining, passive_lvl) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (glove.user, glove.name, glove.level, glove.attack, glove.defence, 
             glove.ward, glove.pdr, glove.fdr, glove.passive,
             False, 5, 0) # Using schema defaults for potential_remaining and passive_lvl
        )
        await self.connection.commit()


    async def fetch_ideologies(self, server_id: str):
        """Fetches a list of ideologies from a server."""
        rows = await self.connection.execute(
            "SELECT * FROM ideologies WHERE server_id=?",
            (server_id,)
        )
        results = await rows.fetchall()  
        return [row[3] for row in results]  # Assuming the ideology is in the second column; adjust the index as needed
    

    async def fetch_followers(self, ideology: str):
        """Fetches the number of followers of an ideology directly from the ideologies table."""
        rows = await self.connection.execute(
            "SELECT followers FROM ideologies WHERE name=?",
            (ideology,)  # Ensure this is a tuple
        )
        
        # Fetch the count from the result
        count = await rows.fetchone()  # This will return a tuple with one item
        return count[0] if count else 0  # Return the count or 0 if none

     
    async def create_ideology(self, user_id: str, server_id: str, name: str) -> None:
        """Registers an ideology in the database."""
        await self.connection.execute(
            "INSERT INTO ideologies (user_id, server_id, name) VALUES (?, ?, ?)",
            (user_id, server_id, name)
        )
        await self.connection.commit()

    async def update_experience(self, user_id: str, new_exp: int) -> None:
        """Update the user's experience in the database."""
        await self.connection.execute(
            "UPDATE users SET experience = ? WHERE user_id = ?",
            (new_exp, user_id)
        )
        await self.connection.commit()

    async def fetch_user_weapons(self, user_id: str) -> list:
        """Fetch all items owned by a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM items WHERE user_id=?",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of items
        
    async def fetch_user_accessories(self, user_id: str) -> list:
        """Fetch all accessories owned by a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM accessories WHERE user_id=?",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of accessories
        

    async def fetch_user_armors(self, user_id: str) -> list:
        """Fetch all armors owned by a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM armor WHERE user_id=?",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of armors
        
    async def fetch_user_gloves(self, user_id: str) -> list:
        """Fetch all gloves owned by a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM gloves WHERE user_id=?",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()

    async def fetch_weapon_by_id(self, item_id: int):
        """Fetch an item by its ID."""
        rows = await self.connection.execute(
            "SELECT * FROM items WHERE item_id=?",
            (item_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()  # Returns the item row, if found
        

    async def fetch_accessory_by_id(self, item_id: int):
        """Fetch an acc by its ID."""
        rows = await self.connection.execute(
            "SELECT * FROM accessories WHERE item_id=?",
            (item_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()  # Returns the item row, if found

    async def fetch_glove_by_id(self, item_id: int):
        """Fetch a glove by its ID."""
        rows = await self.connection.execute(
            "SELECT * FROM gloves WHERE item_id=?",
            (item_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def equip_weapon(self, user_id: str, item_id: int) -> None:
        """Equip an item and deselect any previously equipped item."""
        # First, unequip any currently equipped item for this user
        await self.connection.execute(
            "UPDATE items SET is_equipped = FALSE WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        # Then, equip the new item
        await self.connection.execute(
            "UPDATE items SET is_equipped = TRUE WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    
    async def unequip_weapon(self, user_id: str) -> None:
        """Equip an item and deselect any previously equipped item."""
        # First, unequip any currently equipped item for this user
        await self.connection.execute(
            "UPDATE items SET is_equipped = 0 WHERE user_id = ? AND is_equipped = 1",
            (user_id,)
        )
        await self.connection.commit()


    async def unequip_armor(self, user_id: str) -> None:
        """Equip an item and deselect any previously equipped item."""
        # First, unequip any currently equipped item for this user
        await self.connection.execute(
            "UPDATE armor SET is_equipped = 0 WHERE user_id = ? AND is_equipped = 1",
            (user_id,)
        )
        await self.connection.commit()


    async def unequip_accessory(self, user_id: str) -> None:
        """Equip an item and deselect any previously equipped item."""
        # First, unequip any currently equipped item for this user
        await self.connection.execute(
            "UPDATE accessories SET is_equipped = 0 WHERE user_id = ? AND is_equipped = 1",
            (user_id,)
        )
        await self.connection.commit()

    async def unequip_glove(self, user_id: str) -> None:
        """Unequip any currently equipped glove for this user."""
        await self.connection.execute(
            "UPDATE gloves SET is_equipped = FALSE WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        await self.connection.commit()

    async def equip_accessory(self, user_id: str, item_id: int) -> None:
        """Equip an item and deselect any previously equipped item."""
        # First, unequip any currently equipped item for this user
        await self.connection.execute(
            "UPDATE accessories SET is_equipped = FALSE WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        # Then, equip the new item
        await self.connection.execute(
            "UPDATE accessories SET is_equipped = TRUE WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    async def equip_glove(self, user_id: str, item_id: int) -> None:
        """Equip a glove and deselect any previously equipped glove."""
        await self.connection.execute(
            "UPDATE gloves SET is_equipped = FALSE WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        await self.connection.execute(
            "UPDATE gloves SET is_equipped = TRUE WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    async def get_equipped_weapon(self, user_id: str) -> tuple:
        """Fetch the currently equipped item for a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM items WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()       

    async def get_equipped_accessory(self, user_id: str) -> tuple:
        """Fetch the currently equipped accessory for a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM accessories WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()    
        
    async def get_equipped_glove(self, user_id: str) -> tuple:
        """Fetch the currently equipped glove for a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM gloves WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def update_accessory_passive(self, accessory_id: int, passive: str) -> None:
        """Update the potential level of an accessory in the database."""
        await self.connection.execute(
            "UPDATE accessories SET passive = ? WHERE item_id = ?",
            (passive, accessory_id)
        )
        await self.connection.commit() 

    async def update_glove_passive(self, glove_id: int, passive: str) -> None:
        """Update the passive of a glove in the database."""
        await self.connection.execute(
            "UPDATE gloves SET passive = ? WHERE item_id = ?",
            (passive, glove_id)
        )
        await self.connection.commit()

    async def update_accessory_passive_lvl(self, accessory_id: int, new_potential: int) -> None:
        """Update the potential level of an accessory in the database."""
        await self.connection.execute(
            "UPDATE accessories SET passive_lvl = ? WHERE item_id = ?",
            (new_potential, accessory_id)
        )
        await self.connection.commit()

    async def update_glove_passive_lvl(self, glove_id: int, new_passive_lvl: int) -> None:
        """Update the passive level of a glove in the database."""
        await self.connection.execute(
            "UPDATE gloves SET passive_lvl = ? WHERE item_id = ?",
            (new_passive_lvl, glove_id)
        )
        await self.connection.commit()

    async def update_accessory_potential(self, accessory_id: int, new_potential: int) -> None:
        """Update the potential level of an accessory in the database."""
        await self.connection.execute(
            "UPDATE accessories SET potential_remaining = ? WHERE item_id = ?",
            (new_potential, accessory_id)
        )
        await self.connection.commit()

    async def update_glove_potential_remaining(self, glove_id: int, new_potential_remaining: int) -> None:
        """Update the potential remaining of a glove in the database."""
        await self.connection.execute(
            "UPDATE gloves SET potential_remaining = ? WHERE item_id = ?",
            (new_potential_remaining, glove_id)
        )
        await self.connection.commit()


    async def discard_weapon(self, item_id: int) -> None:
        """Remove an item from the items table."""
        await self.connection.execute(
            "DELETE FROM items WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()        


    async def discard_accessory(self, item_id: int) -> None:
        """Remove an acc from the accessories table."""
        await self.connection.execute(
            "DELETE FROM accessories WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()    

    async def discard_glove(self, item_id: int) -> None:
        """Remove a glove from the gloves table."""
        await self.connection.execute(
            "DELETE FROM gloves WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    async def fetch_user_mining(self, user_id: str, server_id: str):
        """Fetch the user's mining data from the database."""
        rows = await self.connection.execute(
            "SELECT * FROM mining WHERE user_id=? AND server_id=?",
            (user_id, server_id)
        )
        async with rows as cursor:
            return await cursor.fetchone()  # Fetch user mining data

    async def fetch_user_fishing(self, user_id: str, server_id: str):
        """Fetch the user's fishing data from the database."""
        rows = await self.connection.execute(
            "SELECT * FROM fishing WHERE user_id=? AND server_id=?",
            (user_id, server_id)
        )
        async with rows as cursor:
            return await cursor.fetchone()  # Fetch user fishing data

    async def fetch_user_woodcutting(self, user_id: str, server_id: str):
        """Fetch the user's woodcutting data from the database."""
        rows = await self.connection.execute(
            "SELECT * FROM woodcutting WHERE user_id=? AND server_id=?",
            (user_id, server_id)
        )
        async with rows as cursor:
            return await cursor.fetchone()  # Fetch user woodcutting data

    async def add_to_mining(self, user_id: str, server_id: str, pickaxe_tier: str) -> None:
        """Insert a new mining entry into the mining table for the user with the default pickaxe."""
        await self.connection.execute(
            "INSERT INTO mining (user_id, server_id, pickaxe_tier) VALUES (?, ?, ?)",
            (user_id, server_id, pickaxe_tier)
        )
        await self.connection.commit()

    async def add_to_fishing(self, user_id: str, server_id: str, fishing_rod: str) -> None:
        """Insert a new fishing entry into the fishing table for the user with the default fishing rod."""
        await self.connection.execute(
            "INSERT INTO fishing (user_id, server_id, fishing_rod) VALUES (?, ?, ?)",
            (user_id, server_id, fishing_rod)
        )
        await self.connection.commit()

    async def add_to_woodcutting(self, user_id: str, server_id: str, axe_type: str) -> None:
        """Insert a new woodcutting entry into the woodcutting table for the user with the default axe."""
        await self.connection.execute(
            "INSERT INTO woodcutting (user_id, server_id, axe_type) VALUES (?, ?, ?)",
            (user_id, server_id, axe_type)
        )
        await self.connection.commit()


    async def update_mining_resource(self, user_id: str, server_id: str, resource: str, amount: int) -> None:
        """Update a specific mining resource count for a user."""
        
        # Define the SQL query for updating the specific resource
        sql_query = f"UPDATE mining SET {resource} = {resource} + ? WHERE user_id = ? AND server_id = ?"
        
        # Execute the query with the provided amount, user ID, and server ID
        await self.connection.execute(sql_query, (amount, user_id, server_id))
        await self.connection.commit()

    async def update_mining_resources(self, user_id: str, server_id: str, resources: dict) -> None:
        """Update mining resource counts for a user."""
        sql_query = (
            "UPDATE mining SET "
            "iron = iron + ?, "
            "coal = coal + ?, "
            "gold = gold + ?, "
            "platinum = platinum + ?, "
            "idea = idea + ? "
            "WHERE user_id = ? AND server_id = ?"
        )

        params = (
            resources['iron'],
            resources['coal'],
            resources['gold'],
            resources['platinum'],
            resources['idea'],
            user_id,
            server_id
        )

        await self.connection.execute(sql_query, params)
        await self.connection.commit()

    async def update_fishing_resource(self, user_id: str, server_id: str, resource: str, amount: int) -> None:
        """Update a specific fishing resource count for a user."""
        
        # Define the SQL query for updating the specific resource
        sql_query = f"UPDATE fishing SET {resource} = {resource} + ? WHERE user_id = ? AND server_id = ?"
        
        # Execute the query with the provided amount, user ID, and server ID
        await self.connection.execute(sql_query, (amount, user_id, server_id))
        await self.connection.commit()

    async def update_fishing_resources(self, user_id: str, server_id: str, resources: dict) -> None:
        """Update fishing resource counts for a user."""
        sql_query = (
            "UPDATE fishing SET "
            "desiccated_bones = desiccated_bones + ?, "
            "regular_bones = regular_bones + ?, "
            "sturdy_bones = sturdy_bones + ?, "
            "reinforced_bones = reinforced_bones + ?, "
            "titanium_bones = titanium_bones + ? "
            "WHERE user_id = ? AND server_id = ?"
        )

        params = (
            resources['desiccated'],
            resources['regular'],
            resources['sturdy'],
            resources['reinforced'],
            resources['titanium'],
            user_id,
            server_id
        )

        await self.connection.execute(sql_query, params)
        await self.connection.commit()

    async def update_woodcutting_resource(self, user_id: str, server_id: str, resource: str, amount: int) -> None:
        """Update a specific woodcutting resource count for a user."""

        # Define the SQL query for updating the specific resource
        sql_query = f"UPDATE woodcutting SET {resource} = {resource} + ? WHERE user_id = ? AND server_id = ?"

        # Execute the query with the provided amount, user ID, and server ID
        await self.connection.execute(sql_query, (amount, user_id, server_id))
        await self.connection.commit()

    async def update_woodcutting_resources(self, user_id: str, server_id: str, resources: dict) -> None:
        """Update woodcutting resource counts for a user."""
        sql_query = (
            "UPDATE woodcutting SET "
            "oak_logs = oak_logs + ?, "
            "willow_logs = willow_logs + ?, "
            "mahogany_logs = mahogany_logs + ?, "
            "magic_logs = magic_logs + ?, "
            "idea_logs = idea_logs + ? "
            "WHERE user_id = ? AND server_id = ?"
        )

        params = (
            resources['oak'],
            resources['willow'],
            resources['mahogany'],
            resources['magic'],
            resources['idea'],
            user_id,
            server_id
        )

        await self.connection.execute(sql_query, params)
        await self.connection.commit()

    async def upgrade_pickaxe(self, user_id: str, 
                              server_id: str, new_pickaxe_tier: str, 
                              required_iron: int,
                              required_coal: int,
                              required_gold: int,
                              required_platinum: int,
                              required_gp: int) -> None:
        """Upgrade the user's pickaxe in the database."""
        # Deduct resources from the user's resources
        await self.connection.execute(
            "UPDATE mining SET "
            "iron = iron - ?, "
            "coal = coal - ?, "
            "gold = gold - ?, "
            "platinum = platinum - ? "
            "WHERE user_id = ? AND server_id = ?",
            (required_iron, required_coal, required_gold, required_platinum, user_id, server_id)
        )
        await self.connection.commit()

        await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ? AND server_id = ?",
            (required_gp, user_id, server_id)
        )

        await self.connection.execute(
            "UPDATE mining SET pickaxe_tier = ? WHERE user_id = ? AND server_id = ?",
            (new_pickaxe_tier, user_id, server_id)
        )
        await self.connection.commit()

    async def upgrade_axe(self, user_id: str, 
                        server_id: str, new_axe_tier: str, 
                        required_oak: int,
                        required_willow: int,
                        required_mahogany: int,
                        required_magic: int,
                        required_gp: int) -> None:
        """Upgrade the user's axe in the database."""
        # Deduct resources from the user's resources
        await self.connection.execute(
            "UPDATE woodcutting SET "
            "oak_logs = oak_logs - ?, "
            "willow_logs = willow_logs - ?, "
            "mahogany_logs = mahogany_logs - ?, "
            "magic_logs = magic_logs - ? "
            "WHERE user_id = ? AND server_id = ?",
            (required_oak, required_willow, required_mahogany, required_magic, user_id, server_id)
        )
        await self.connection.commit()

        await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ? AND server_id = ?",
            (required_gp, user_id, server_id)
        )

        await self.connection.execute(
            "UPDATE woodcutting SET axe_type = ? WHERE user_id = ? AND server_id = ?",
            (new_axe_tier, user_id, server_id)
        )
        await self.connection.commit()

    async def upgrade_fishing_rod(self, user_id: str, 
                                server_id: str, new_fishing_rod_tier: str, 
                                required_desiccated: int,
                                required_regular: int,
                                required_sturdy: int,
                                required_reinforced: int,
                                required_gp: int) -> None:
        """Upgrade the user's fishing rod in the database."""
        # Deduct resources from the user's resources
        await self.connection.execute(
            "UPDATE fishing SET "
            "desiccated_bones = desiccated_bones - ?, "
            "regular_bones = regular_bones - ?, "
            "sturdy_bones = sturdy_bones - ?, "
            "reinforced_bones = reinforced_bones - ? "
            "WHERE user_id = ? AND server_id = ?",
            (required_desiccated, required_regular, required_sturdy, required_reinforced, user_id, server_id)
        )
        await self.connection.commit()

        await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ? AND server_id = ?",
            (required_gp, user_id, server_id)
        )

        await self.connection.execute(
            "UPDATE fishing SET fishing_rod = ? WHERE user_id = ? AND server_id = ?",
            (new_fishing_rod_tier, user_id, server_id)
        )
        await self.connection.commit()

    async def fetch_users_with_mining(self):
        """Fetch user_id and server_id for users with mining data."""
        rows = await self.connection.execute("SELECT user_id, server_id FROM mining")
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of (user_id, server_id) tuples
        
    async def fetch_users_with_fishing(self):
        """Fetch user_id and server_id for users with fishing data."""
        rows = await self.connection.execute("SELECT user_id, server_id FROM fishing")
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of (user_id, server_id) tuples

    async def fetch_users_with_woodcutting(self):
        """Fetch user_id and server_id for users with woodcutting data."""
        rows = await self.connection.execute("SELECT user_id, server_id FROM woodcutting")
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of (user_id, server_id) tuples
        
    async def update_weapon_passive(self, item_id: int, new_passive: str) -> None:
        """Update the passive of an item in the database."""
        sql_query = "UPDATE items SET passive = ? WHERE item_id = ?"
        await self.connection.execute(sql_query, (new_passive, item_id))
        await self.connection.commit()


    async def update_item_pinnacle_passive(self, item_id: int, new_passive: str) -> None:
        """Update the pinnacle_passive of an item in the database."""
        await self.connection.execute(
            "UPDATE items SET pinnacle_passive = ? WHERE item_id = ?",
            (new_passive, item_id)
        )
        await self.connection.commit()    


    async def update_item_utmost_passive(self, item_id: int, new_passive: str) -> None:
        """Update the utmost_passive of an item in the database."""
        await self.connection.execute(
            "UPDATE items SET utmost_passive = ? WHERE item_id = ?",
            (new_passive, item_id)
        )
        await self.connection.commit()


    async def fetch_void_forge_weapons(self, user_id: str) -> list:
        """Fetch all items not equipped for the user with refinement_level >= 5 and forges_remaining = 0."""
        rows = await self.connection.execute(
            "SELECT * FROM items WHERE user_id = ? AND refinement_lvl >= 5 AND forges_remaining = 0 AND is_equipped = 0",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of items matching the criteria


    async def update_weapon_forge_count(self, item_id: int, new_forge_count: int) -> None:
        """Update the forge count of an item in the database."""
        sql_query = "UPDATE items SET forges_remaining = ? WHERE item_id = ?"
        await self.connection.execute(sql_query, (new_forge_count, item_id))
        await self.connection.commit()

    async def update_mining_resources(self, user_id: str, server_id: str, resources: dict) -> None:
        """Update mining resource counts for a user."""
        sql_query = (
            "UPDATE mining SET "
            "iron = iron + ?, "
            "coal = coal + ?, "
            "gold = gold + ?, "
            "platinum = platinum + ?, "
            "idea = idea + ? "
            "WHERE user_id = ? AND server_id = ?"
        )

        params = (
            resources['iron'],
            resources['coal'],
            resources['gold'],
            resources['platinum'],
            resources['idea'],
            user_id,
            server_id
        )

        await self.connection.execute(sql_query, params)
        await self.connection.commit()

    async def update_woodcutting_resources(self, user_id: str, server_id: str, resources: dict) -> None:
        """Update woodcutting resource counts for a user."""
        sql_query = (
            "UPDATE woodcutting SET "
            "oak_logs = oak_logs + ?, "
            "willow_logs = willow_logs + ?, "
            "mahogany_logs = mahogany_logs + ?, "
            "magic_logs = magic_logs + ?, "
            "idea_logs = idea_logs + ? "
            "WHERE user_id = ? AND server_id = ?"
        )

        params = (
            resources['oak'],
            resources['willow'],
            resources['mahogany'],
            resources['magic'],
            resources['idea'],
            user_id,
            server_id
        )

        await self.connection.execute(sql_query, params)
        await self.connection.commit()

    async def update_fishing_resources(self, user_id: str, server_id: str, resources: dict) -> None:
        """Update fishing resource counts for a user."""
        sql_query = (
            "UPDATE fishing SET "
            "desiccated_bones = desiccated_bones + ?, "
            "regular_bones = regular_bones + ?, "
            "sturdy_bones = sturdy_bones + ?, "
            "reinforced_bones = reinforced_bones + ?, "
            "titanium_bones = titanium_bones + ? "
            "WHERE user_id = ? AND server_id = ?"
        )

        params = (
            resources['desiccated'], 
            resources['regular'], 
            resources['sturdy'], 
            resources['reinforced'], 
            resources['titanium'], 
            user_id, 
            server_id
        )

        await self.connection.execute(sql_query, params)
        await self.connection.commit()

    async def update_weapon_refine_count(self, item_id: int, new_refine_count: int) -> None:
        """Update the refine count of an item in the database."""
        await self.connection.execute(
            "UPDATE items SET refines_remaining = ? WHERE item_id = ?",
            (new_refine_count, item_id)
        )
        await self.connection.commit()

    async def update_weapon_refine_lvl(self, item_id: int, lvl: int) -> None:
        """Update the refine count of an item in the database."""
        await self.connection.execute(
            "UPDATE items SET refinement_lvl = refinement_lvl + ? WHERE item_id = ?",
            (lvl, item_id)
        )
        await self.connection.commit()

    async def increase_weapon_rarity(self, item_id: int, rarity_increase: int) -> None:
        """Update the item's rarity in the database."""
        await self.connection.execute(
            "UPDATE items SET rarity = rarity + ? WHERE item_id = ?",
            (rarity_increase, item_id)
        )
        await self.connection.commit()

    async def increase_weapon_attack(self, item_id: str, attack_modifier: int) -> None:
        """
        Increase the attack stat of items owned by the specified user in the database.
        
        :param item_id: The ID of the user whose items are being updated.
        :param attack_modifier: The amount to increase the attack stat by.
        """
        await self.connection.execute(
            "UPDATE items SET attack = attack + ? WHERE item_id = ?",
            (attack_modifier, item_id)
        )
        await self.connection.commit()

    async def increase_weapon_defence(self, item_id: str, defence_modifier: int) -> None:
        """
        Increase the defense stat of items owned by the specified user in the database.
        
        :param item_id: The ID of the user whose items are being updated.
        :param defence_modifier: The amount to increase the defense stat by.
        """
        await self.connection.execute(
            "UPDATE items SET defence = defence + ? WHERE item_id = ?",
            (defence_modifier, item_id)
        )
        await self.connection.commit()

    async def send_weapon(self, receiver_id: str, item_id: int) -> None:
        """Transfer an item from one user to another by changing the user_id."""

        await self.connection.execute(
            "UPDATE items SET user_id = ? WHERE item_id = ?",
            (receiver_id, item_id)
        )
        
        # Commit the transaction
        await self.connection.commit()


    async def send_accessory(self, receiver_id: str, item_id: int) -> None:
        """Transfer an accessory from one user to another by changing the user_id."""

        await self.connection.execute(
            "UPDATE accessories SET user_id = ? WHERE item_id = ?",
            (receiver_id, item_id)
        )
        
        # Commit the transaction
        await self.connection.commit()



    async def send_armor(self, receiver_id: str, item_id: int) -> None:
        """Transfer an armor from one user to another by changing the user_id."""

        await self.connection.execute(
            "UPDATE armor SET user_id = ? WHERE item_id = ?",
            (receiver_id, item_id)
        )
        
        # Commit the transaction
        await self.connection.commit()

    async def send_glove(self, receiver_id: str, item_id: int) -> None:
        """Transfer a glove from one user to another by changing the user_id."""
        await self.connection.execute(
            "UPDATE gloves SET user_id = ? WHERE item_id = ?",
            (receiver_id, item_id)
        )
        await self.connection.commit()

    async def count_user_weapons(self, user_id: str) -> int:
        """Counts the number of weapons for a specific user."""
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM items WHERE user_id = ?",
            (user_id,)
        )
        count = await rows.fetchone()  # Get the count
        return count[0] if count else 0  # Return the count or 0 if none

    async def count_user_accessories(self, user_id: str) -> int:
        """Counts the number of accessories for a specific user."""
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM accessories WHERE user_id = ?",
            (user_id,)
        )
        count = await rows.fetchone()  # Get the count
        return count[0] if count else 0  # Return the count or 0 if none
    
    async def count_user_armors(self, user_id: str) -> int:
        """Counts the number of armor for a specific user."""
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM armor WHERE user_id = ?",
            (user_id,)
        )
        count = await rows.fetchone()  # Get the count
        return count[0] if count else 0  # Return the count or 0 if none

    async def count_user_gloves(self, user_id: str) -> int:
        """Counts the number of gloves for a specific user."""
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM gloves WHERE user_id = ?",
            (user_id,)
        )
        count = await rows.fetchone()
        return count[0] if count else 0


    async def fetch_armor_by_id(self, item_id: int):
        """Fetch armor by its ID."""
        rows = await self.connection.execute(
            "SELECT * FROM armor WHERE item_id=?",
            (item_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()  # Returns the armor row, if found

    async def get_equipped_armor(self, user_id: str):
        """Fetch the currently equipped armor for a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM armor WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()
  
    async def discard_armor(self, item_id: int) -> None:
        """Remove an armor from the armor table."""
        await self.connection.execute(
            "DELETE FROM armor WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    async def equip_armor(self, user_id: str, item_id: int) -> None:
        """Equip an armor piece and deselect any previously equipped armor."""
        # First, unequip any currently equipped armor for this user
        await self.connection.execute(
            "UPDATE armor SET is_equipped = FALSE WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        # Then, equip the new armor
        await self.connection.execute(
            "UPDATE armor SET is_equipped = TRUE WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    async def update_armor_passive(self, armor_id: int, passive: str) -> None:
        """Update the passive of an armor piece in the database."""
        await self.connection.execute(
            "UPDATE armor SET armor_passive = ? WHERE item_id = ?",
            (passive, armor_id)
        )
        await self.connection.commit()

    async def update_armor_temper_count(self, armor_id: int, new_temper_count: int) -> None:
        """Update the temper count of an armor piece in the database."""
        await self.connection.execute(
            "UPDATE armor SET temper_remaining = ? WHERE item_id = ?",
            (new_temper_count, armor_id)
        )
        await self.connection.commit()


    async def update_armor_imbue_count(self, armor_id: int, new_imbue_count: int) -> None:
        """Update the imbue count of an armor piece in the database."""
        await self.connection.execute(
            "UPDATE armor SET imbue_remaining = ? WHERE item_id = ?",
            (new_imbue_count, armor_id)
        )
        await self.connection.commit()

    async def increase_armor_stat(self, armor_id: int, stat: str, increase_by: int) -> None:
        """Increase a specific stat (block, evasion, or ward) of an armor piece in the database."""
        await self.connection.execute(
            f"UPDATE armor SET {stat} = {stat} + ? WHERE item_id = ?",
            (increase_by, armor_id)
        )
        await self.connection.commit()


    async def create_boot(self, boot: Boot) -> None:
        """Insert a new boot into the boots table."""
        # Defaults from schema: potential_remaining=6, passive_lvl=0, is_equipped=False
        await self.connection.execute(
            """INSERT INTO boots 
            (user_id, item_name, item_level, attack, defence, ward, pdr, fdr, passive, 
             is_equipped, potential_remaining, passive_lvl) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (boot.user, boot.name, boot.level, boot.attack, boot.defence, 
             boot.ward, boot.pdr, boot.fdr, boot.passive,
             False, 6, 0) # potential_remaining defaults to 6 for boots
        )
        await self.connection.commit()

    async def fetch_user_boots(self, user_id: str) -> list:
        """Fetch all boots owned by a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM boots WHERE user_id=?",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()

    async def fetch_boot_by_id(self, item_id: int):
        """Fetch a boot by its ID."""
        rows = await self.connection.execute(
            "SELECT * FROM boots WHERE item_id=?",
            (item_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def unequip_boot(self, user_id: str) -> None:
        """Unequip any currently equipped boot for this user."""
        await self.connection.execute(
            "UPDATE boots SET is_equipped = FALSE WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        await self.connection.commit()

    async def equip_boot(self, user_id: str, item_id: int) -> None:
        """Equip a boot and deselect any previously equipped boot."""
        await self.connection.execute(
            "UPDATE boots SET is_equipped = FALSE WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        await self.connection.execute(
            "UPDATE boots SET is_equipped = TRUE WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    async def get_equipped_boot(self, user_id: str) -> tuple:
        """Fetch the currently equipped boot for a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM boots WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def update_boot_passive(self, boot_id: int, passive: str) -> None:
        """Update the passive of a boot in the database."""
        await self.connection.execute(
            "UPDATE boots SET passive = ? WHERE item_id = ?",
            (passive, boot_id)
        )
        await self.connection.commit()

    async def update_boot_passive_lvl(self, boot_id: int, new_passive_lvl: int) -> None:
        """Update the passive level of a boot in the database."""
        await self.connection.execute(
            "UPDATE boots SET passive_lvl = ? WHERE item_id = ?",
            (new_passive_lvl, boot_id)
        )
        await self.connection.commit()

    async def update_boot_potential_remaining(self, boot_id: int, new_potential_remaining: int) -> None:
        """Update the potential remaining of a boot in the database."""
        await self.connection.execute(
            "UPDATE boots SET potential_remaining = ? WHERE item_id = ?",
            (new_potential_remaining, boot_id)
        )
        await self.connection.commit()

    async def discard_boot(self, item_id: int) -> None:
        """Remove a boot from the boots table."""
        await self.connection.execute(
            "DELETE FROM boots WHERE item_id = ?",
            (item_id,)
        )
        await self.connection.commit()

    async def send_boot(self, receiver_id: str, item_id: int) -> None:
        """Transfer a boot from one user to another by changing the user_id."""
        await self.connection.execute(
            "UPDATE boots SET user_id = ? WHERE item_id = ?",
            (receiver_id, item_id)
        )
        await self.connection.commit()

    async def count_user_boots(self, user_id: str) -> int:
        """Counts the number of boots for a specific user."""
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM boots WHERE user_id = ?",
            (user_id,)
        )
        count = await rows.fetchone()
        return count[0] if count else 0