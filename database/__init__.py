import aiosqlite
from datetime import datetime, timedelta
from core.models import Player, Weapon, Accessory, Armor

class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def update_player(self, player: Player) -> None:
        """Update the player's data in the database."""
        await self.connection.execute(
            """
            UPDATE users SET 
                level = ?, 
                ascension = ?, 
                experience = ?, 
                current_hp = ?, 
                max_hp = ?, 
                potions = ?
            WHERE user_id = ?
            """,
            (
                player.level,
                player.ascension,
                player.exp,
                player.hp,
                player.max_hp,
                player.potions,
                player.id
            )
        )
        await self.connection.commit()


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
            temper_remaining) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (armor.user, 
             armor.name, 
             armor.level, 
             armor.block, 
             armor.evasion, 
             armor.ward, 
             item_potential)
        )
        await self.connection.commit()

    
    async def fetch_user(self, user_id: str, server_id: str):
        """Fetches a user from the database."""
        rows = await self.connection.execute(
            "SELECT * FROM users WHERE user_id=? AND server_id=?",
            (user_id, server_id)
        )
        async with rows as cursor:
            return await cursor.fetchone()
        
    async def fetch_all_users(self):
        """Fetch all users from the database."""
        rows = await self.connection.execute("SELECT * FROM users")
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of all users

    async def register_user(self, user_id: str, server_id: str, name: str, selected_appearance: str, ideology: str) -> None:
        """Registers a user in the database."""
        last_checkin_time = (datetime.now() + timedelta(hours=18)).isoformat()
        await self.connection.execute(
            "INSERT INTO users (user_id, server_id, name, appearance, ideology, last_checkin_time) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, server_id, name, selected_appearance, ideology, last_checkin_time)
        )
        await self.connection.commit()

    async def unregister_user(self, user_id: str, server_id: str) -> None:
        """Deletes a user from the database."""
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


    async def fetch_user_gold(self, user_id: str, server_id: str):
        """Fetch the user's gold from the database."""
        rows = await self.connection.execute(
            "SELECT gold FROM users WHERE user_id = ? AND server_id = ?",
            (user_id, server_id)
        )
        result = await rows.fetchone()
        return result[0] if result else 0  # Return the gold value or 0 if user not found


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
    

    async def update_player_hp(self, user_id: str, hp: int, server_id: str) -> None:
        """Update the player's current HP in the database."""
        await self.connection.execute(
            "UPDATE users SET current_hp = ? WHERE user_id = ? AND server_id = ?",
            (hp, user_id, server_id)
        )
        await self.connection.commit()
     
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


    async def add_gold(self, user_id: str, increase_by: int) -> None:
        """Increase the user's gold in the database."""
        await self.connection.execute(
            "UPDATE users SET gold = gold + ? WHERE user_id = ?",
            (increase_by, user_id)
        )
        await self.connection.commit()


    async def add_dragon_key(self, user_id: str, increase_by: int) -> None:
        """Increase the user's dragon keys in the database."""
        await self.connection.execute(
            "UPDATE users SET dragon_key = dragon_key + ? WHERE user_id = ?",
            (increase_by, user_id)
        )
        await self.connection.commit()

    async def add_angel_key(self, user_id: str, increase_by: int) -> None:
        """Increase the user's angel keys in the database."""
        await self.connection.execute(
            "UPDATE users SET angel_key = angel_key + ? WHERE user_id = ?",
            (increase_by, user_id)
        )
        await self.connection.commit()     


    async def add_soul_cores(self, user_id: str, increase_by: int) -> None:
        """Increase the user's soul cores in the database."""
        await self.connection.execute(
            "UPDATE users SET soul_cores = soul_cores + ? WHERE user_id = ?",
            (increase_by, user_id)
        )
        await self.connection.commit()      

    async def update_user_gold(self, user_id: str, new_gold: int) -> None:
        """Update the user's gold in the database."""
        await self.connection.execute(
            "UPDATE users SET gold = ? WHERE user_id = ?",
            (new_gold, user_id)
        )
        await self.connection.commit()

    async def update_rest_time(self, user_id: str) -> None:
        """Update the last rest time of the user in the database to now."""
        current_time = datetime.now().isoformat()
        await self.connection.execute(
            "UPDATE users SET last_rest_time = ? WHERE user_id = ?",
            (current_time, user_id)
        )
        await self.connection.commit()

    async def increase_attack(self, user_id: str, increase_by: int) -> None:
        """Increase the user's attack stat in the database."""
        await self.connection.execute(
            "UPDATE users SET attack = attack + ? WHERE user_id = ?",
            (increase_by, user_id)
        )
        await self.connection.commit()

    async def increase_defence(self, user_id: str, increase_by: int) -> None:
        """Increase the user's defense stat in the database."""
        await self.connection.execute(
            "UPDATE users SET defence = defence + ? WHERE user_id = ?",
            (increase_by, user_id)
        )
        await self.connection.commit()


    async def update_player_hp(self, user_id: str, hp: int) -> None:
        """Update the player's current HP in the database."""
        await self.connection.execute(
            "UPDATE users SET current_hp = ? WHERE user_id = ?",
            (hp, user_id)
        )
        await self.connection.commit()

    async def update_player_attack(self, user_id: str, atk: int) -> None:
        """Update the player's attack in the database."""
        await self.connection.execute(
            "UPDATE users SET attack = ? WHERE user_id = ?",
            (atk, user_id)
        )
        await self.connection.commit()

    async def update_player_defence(self, user_id: str, defence: int) -> None:
        """Update the player's defence in the database."""
        await self.connection.execute(
            "UPDATE users SET defence = ? WHERE user_id = ?",
            (defence, user_id)
        )
        await self.connection.commit()

    async def update_player_max_hp(self, user_id: str, hp: int) -> None:
        """Update the player's maximum HP in the database."""
        await self.connection.execute(
            "UPDATE users SET max_hp = ? WHERE user_id = ?",
            (hp, user_id)
        )
        await self.connection.commit()

    async def update_followers_count(self, ideology: str, new_count: int) -> None:
        """Update the followers count in the ideologies table."""
        await self.connection.execute(
            "UPDATE ideologies SET followers = ? WHERE name = ?",
            (new_count, ideology)
        )
        await self.connection.commit()

    async def increase_potion_count(self, user_id: str) -> None:
        """Increases the potion count for a user by 1."""
        await self.connection.execute(
            "UPDATE users SET potions = potions + 1 WHERE user_id = ?",
            (user_id,)
        )
        await self.connection.commit()

    async def increase_ascension_level(self, user_id: str) -> None:
        """Increase the user's ascension level in the database."""
        await self.connection.execute(
            "UPDATE users SET ascension = ascension + 1 WHERE user_id = ?",
            (user_id,)
        )
        await self.connection.commit()

    async def update_propagate_time(self, user_id: str) -> None:
        """Update the last propagate time of the user in the database to now."""
        current_time = datetime.now().isoformat()
        await self.connection.execute(
            "UPDATE users SET last_propagate_time = ? WHERE user_id = ?",
            (current_time, user_id)
        )
        await self.connection.commit()

    async def update_checkin_time(self, user_id: str) -> None:
        """Update the last check-in time of the user to the current time."""
        current_time = datetime.now().isoformat()  # Get the current timestamp in ISO format
        await self.connection.execute(
            "UPDATE users SET last_checkin_time = ? WHERE user_id = ?",
            (current_time, user_id)
        )
        await self.connection.commit()


    async def update_combat_time(self, user_id: str) -> None:
        """Update the last combat time of the user to the current time."""
        current_time = datetime.now().isoformat()  # Get the current timestamp in ISO format
        await self.connection.execute(
            "UPDATE users SET last_combat = ? WHERE user_id = ?",
            (current_time, user_id)
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
        

    async def update_accessory_passive(self, accessory_id: int, passive: str) -> None:
        """Update the potential level of an accessory in the database."""
        await self.connection.execute(
            "UPDATE accessories SET passive = ? WHERE item_id = ?",
            (passive, accessory_id)
        )
        await self.connection.commit() 

    async def update_accessory_passive_lvl(self, accessory_id: int, new_potential: int) -> None:
        """Update the potential level of an accessory in the database."""
        await self.connection.execute(
            "UPDATE accessories SET passive_lvl = ? WHERE item_id = ?",
            (new_potential, accessory_id)
        )
        await self.connection.commit()


    async def update_accessory_potential(self, accessory_id: int, new_potential: int) -> None:
        """Update the potential level of an accessory in the database."""
        await self.connection.execute(
            "UPDATE accessories SET potential_remaining = ? WHERE item_id = ?",
            (new_potential, accessory_id)
        )
        await self.connection.commit()


    async def update_accessory_passive(self, accessory_id: int, passive: str) -> None:
        """Update the passive of an accessory in the database."""
        await self.connection.execute(
            "UPDATE accessories SET passive = ? WHERE item_id = ?",
            (passive, accessory_id)
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

    async def fetch_top_users_by_level(self, limit: int = 10):
        """Fetch the top users sorted by level."""
        rows = await self.connection.execute(
            "SELECT * FROM users ORDER BY level DESC LIMIT ?",
            (limit,)
        )
        async with rows as cursor:
            return await cursor.fetchall()  # Returns the list of top users


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


    # Method to update the number of refinement runes for a user
    async def update_refinement_runes(self, user_id: str, count: int) -> None:
        """Update the user's count of refinement runes in the database."""
        await self.connection.execute(
            "UPDATE users SET refinement_runes = refinement_runes + ? WHERE user_id = ?",
            (count, user_id)
        )
        await self.connection.commit()

    async def update_potential_runes(self, user_id: str, count: int) -> None:
        """Update the user's count of potential runes in the database."""
        await self.connection.execute(
            "UPDATE users SET potential_runes = potential_runes + ? WHERE user_id = ?",
            (count, user_id)
        )
        await self.connection.commit()

    async def update_imbuing_runes(self, user_id: str, count: int) -> None:
        """Update the user's count of imbuing runes in the database."""
        await self.connection.execute(
            "UPDATE users SET imbue_runes = imbue_runes + ? WHERE user_id = ?",
            (count, user_id)
        )
        await self.connection.commit()

    # Method to fetch the number of refinement runes for a user
    async def fetch_refinement_runes(self, user_id: str) -> int:
        """Fetch the user's refinement runes count from the database."""
        rows = await self.connection.execute(
            "SELECT refinement_runes FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = await rows.fetchone()
        return result[0] if result else 0  # Return the count or 0 if user not found
    
    # Method to fetch the number of refinement runes for a user
    async def fetch_potential_runes(self, user_id: str) -> int:
        """Fetch the user's potential runes count from the database."""
        rows = await self.connection.execute(
            "SELECT potential_runes FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = await rows.fetchone()
        return result[0] if result else 0  # Return the count or 0 if user not found
    

    async def set_passive_points(self, user_id: str, server_id: str, passive_points: int) -> None:
        """Set the number of passive points for a user in the database."""
        await self.connection.execute(
            "UPDATE users SET passive_points = ? WHERE user_id = ? AND server_id = ?",
            (passive_points, user_id, server_id)
        )
        await self.connection.commit()


    async def fetch_passive_points(self, user_id: str, server_id: str) -> int:
        """Fetch the number of passive points for a user."""
        rows = await self.connection.execute(
            "SELECT passive_points FROM users WHERE user_id = ? AND server_id = ?",
            (user_id, server_id)
        )
        result = await rows.fetchone()
        return result[0] if result else 0  # Return the passive points or 0 if not found

    async def update_curios_count(self, user_id: str, server_id: str, amount: int) -> None:
        """
        Updates the user's curios count by adding or subtracting a specified amount.
        
        :param user_id: The ID of the user whose curios count will be updated.
        :param server_id: The server ID where the user is registered.
        :param amount: The amount to add (positive) or subtract (negative) from the user's curios count.
        """
        await self.connection.execute(
            "UPDATE users SET curios = curios + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id)
        )
        await self.connection.commit()

    async def update_curios_bought(self, user_id: str, server_id: str, amount: int) -> None:
        """Updates the user's curios purchased today count."""
        await self.connection.execute(
            "UPDATE users SET curios_purchased_today = curios_purchased_today + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id)
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