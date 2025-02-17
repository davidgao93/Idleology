import aiosqlite
from datetime import datetime

class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection

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
        await self.connection.execute(
            "INSERT INTO users (user_id, server_id, name, appearance, ideology) VALUES (?, ?, ?, ?, ?)",
            (user_id, server_id, name, selected_appearance, ideology)
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
                "DELETE FROM items WHERE user_id=?",
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
    
    async def count_followers(self, ideology: str) -> int:
        """Counts the number of followers of a specific ideology."""
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM users WHERE ideology=?",
            (ideology,)
        )
        count = await rows.fetchone()  # Fetch the count from the result
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

    async def update_level(self, user_id: str, new_level: int) -> None:
        """Update the user's level in the database."""
        await self.connection.execute(
            "UPDATE users SET level = ? WHERE user_id = ?",
            (new_level, user_id)
        )
        await self.connection.commit()

    async def add_gold(self, user_id: str, increase_by: int) -> None:
        """Increase the user's gold in the database."""
        await self.connection.execute(
            "UPDATE users SET gold = gold + ? WHERE user_id = ?",
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

    async def increase_level(self, user_id: str) -> None:
        """Increase the user's level in the database."""
        await self.connection.execute(
            "UPDATE users SET level = level + 1 WHERE user_id = ?",
            (user_id,)
        )
        await self.connection.commit()

    async def update_player_hp(self, user_id: str, hp: int) -> None:
        """Update the player's current HP in the database."""
        await self.connection.execute(
            "UPDATE users SET current_hp = ? WHERE user_id = ?",
            (hp, user_id)
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

    async def decrease_potion_count(self, user_id: str) -> None:
        """Decreases the potion count for a user by 1."""
        await self.connection.execute(
            "UPDATE users SET potions = potions - 1 WHERE user_id = ?",
            (user_id,)
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

    async def create_item(self, user_id: str, item_name: str, item_level: int,
                           attack: int, defence: int, rarity: int, is_equipped: bool = False) -> None:
        """Insert a new item into the items table."""
        await self.connection.execute(
            "INSERT INTO items (user_id, item_name, item_level, attack, defence, rarity, is_equipped) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, item_name, item_level, attack, defence, rarity, is_equipped)
        )
        await self.connection.commit()
    
    async def fetch_user_items(self, user_id: str) -> list:
        """Fetch all items owned by a specific user."""
        rows = await self.connection.execute(
            "SELECT item_id, item_name, item_level, attack, defence, rarity, passive is_equipped FROM items WHERE user_id=?",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchall()  # Returns a list of items
    
    async def update_item_equipped_status(self, item_id: int, is_equipped: bool) -> None:
        """Update the equipped status of an item."""
        await self.connection.execute(
            "UPDATE items SET is_equipped = ? WHERE item_id = ?",
            (is_equipped, item_id)
        )
        await self.connection.commit()
    
    async def fetch_item_by_id(self, item_id: int):
        """Fetch an item by its ID."""
        rows = await self.connection.execute(
            "SELECT * FROM items WHERE item_id=?",
            (item_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()  # Returns the item row, if found

    async def equip_item(self, user_id: str, item_id: int) -> None:
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

    async def get_equipped_item(self, user_id: str) -> tuple:
        """Fetch the currently equipped item for a specific user."""
        rows = await self.connection.execute(
            "SELECT * FROM items WHERE user_id = ? AND is_equipped = TRUE",
            (user_id,)
        )
        async with rows as cursor:
            return await cursor.fetchone()       

    async def discard_item(self, item_id: int) -> None:
        """Remove an item from the items table."""
        await self.connection.execute(
            "DELETE FROM items WHERE item_id = ?",
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
        # Deduct resources from the user's inventory
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
        # Deduct resources from the user's inventory
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
        # Deduct resources from the user's inventory
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
        
    async def update_item_passive(self, item_id: int, new_passive: str) -> None:
        """Update the passive of an item in the database."""
        sql_query = "UPDATE items SET passive = ? WHERE item_id = ?"
        await self.connection.execute(sql_query, (new_passive, item_id))
        await self.connection.commit()

    async def update_item_forge_count(self, item_id: int, new_forge_count: int) -> None:
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

    async def update_item_refine_count(self, item_id: int, new_refine_count: int) -> None:
        """Update the refine count of an item in the database."""
        await self.connection.execute(
            "UPDATE items SET refines_remaining = ? WHERE item_id = ?",
            (new_refine_count, item_id)
        )
        await self.connection.commit()

    async def update_item_rarity(self, item_id: int, rarity_increase: int) -> None:
        """Update the item's rarity in the database."""
        await self.connection.execute(
            "UPDATE items SET rarity = rarity + ? WHERE item_id = ?",
            (rarity_increase, item_id)
        )
        await self.connection.commit()

    async def increase_item_attack(self, item_id: str, attack_modifier: int) -> None:
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

    async def increase_item_defence(self, item_id: str, defence_modifier: int) -> None:
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


    async def send_item(self, receiver_id: str, item_id: int) -> None:
        """Transfer an item from one user to another by changing the user_id."""

        await self.connection.execute(
            "UPDATE items SET user_id = ? WHERE item_id = ?",
            (receiver_id, item_id)
        )
        
        # Commit the transaction
        await self.connection.commit()