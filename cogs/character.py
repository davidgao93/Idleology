import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
import asyncio
import random

"""
Index	Attribute Description
0	Unique ID
1	User ID
2	Server ID
3	Player Name
4	Level
5	Experience
6	Gold
7	Image URL (for player image)
8	Ideology
9	Attack
10	Defense
11	Current HP
12	Maximum HP
13	Last Rest Time
14	Last Propagate Time
15	Ascension Level
16	Potion Count
17	Created at
18  Last Checkin Time
"""

class Character(commands.Cog, name="character"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_hp.is_running():
            print('Starting self heal')
            self.check_hp.start()

    @tasks.loop(minutes=5)
    async def check_hp(self):
        """Check and increment current_hp for all users every hour."""
        # Fetch all users from the database
        users = await self.bot.database.fetch_all_users()

        for user in users:
            user_id = user[1]  # Assuming the user ID is the first element
            current_hp = user[11]  # current_hp index
            max_hp = user[12]  # max_hp index
            scaling = int(max_hp / 30)
            if current_hp < max_hp:
                # Update current_hp by incrementing it by 1
                # print(f'healing {user_id} by 1')
                new_hp = current_hp + 1 + scaling
                if (new_hp > max_hp):
                    new_hp = max_hp
                
                await self.bot.database.update_player_hp(user_id, new_hp)

    @commands.hybrid_command(name="stats", description="Get your character's stats.")
    async def get_stats(self, context: Context) -> None:
        """Fetch and display the character's stats."""
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if existing_user:
            embed = discord.Embed(
                title=f"{existing_user[3]}'s Stats",
                color=0x00FF00,
            )
            equipped_item = await self.bot.database.get_equipped_item(user_id)
            add_atk = 0
            add_def = 0
            if equipped_item:
                add_atk = equipped_item[4]
                add_def = equipped_item[5]
            # Add the character stats to the embed
            embed.add_field(name="Level ⭐", value=existing_user[4], inline=True)
            embed.add_field(name="Experience ✨", value=f"{existing_user[5]:,}", inline=True) 
            embed.add_field(name="Gold 💰", value=f"{existing_user[6]:,}", inline=True) 
            embed.add_field(name="Ideology 🧠", value=existing_user[8], inline=True)
            attack_display = f"{existing_user[9]} (+{add_atk})" if add_atk > 0 else f"{existing_user[9]}"
            embed.add_field(name="Attack ⚔️", value=attack_display, inline=True)
            defense_display = f"{existing_user[10]} (+{add_def})" if add_def > 0 else f"{existing_user[10]}"
            embed.add_field(name="Defense 🛡️", value=defense_display, inline=True)
            embed.add_field(name="Current HP ❤️", value=existing_user[11], inline=True)
            embed.add_field(name="Maximum HP ❤️", value=existing_user[12], inline=True) 
            ascension = existing_user[15]
            if (ascension > 0):
                embed.add_field(name="Ascension 🌟", value=ascension, inline=True)
            embed.add_field(name="Potions 🍹", value=existing_user[16], inline=True) 

            message = await context.send(embed=embed)
            await asyncio.sleep(10)
            await message.delete()
        else:
            await context.send("You are not registered with the 🏦 Adventurer's guild. Please /register first.")

    @commands.hybrid_command(name="inventory", description="View your character's inventory and modify items.")
    async def inventory(self, context: Context) -> None:
        await context.defer()
        """Fetch and display the character's inventory."""
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        
        if not existing_user: 
            await context.send("You are not registered with the 🏦 Adventurer's guild."
                               " Please /register first.")
            return
        
        items = await self.bot.database.fetch_user_items(user_id)
        
        if not items:
            await context.send("You peer into your inventory, it is empty.")
            return
        player_name = existing_user[3]
        embed = discord.Embed(
            title=f"📦",
            description=f"{player_name}'s Inventory:",
            color=0x00FF00,
        )

        inventory_message = await context.send(embed=embed)
        while True:
            items = await self.bot.database.fetch_user_items(user_id)
            embed.description = f"{player_name}'s Inventory:"
            if not items:
                await context.send("You peer into your inventory, it is empty.")
                return

            items.sort(key=lambda item: item[2], reverse=True)  # item_level at index 2
            items_to_display = items[:5]
            equipped_item = await self.bot.database.get_equipped_item(user_id)
            await inventory_message.clear_reactions()
            embed.clear_fields()
            number_emojis = ["🚪", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            items_display_string = ""

            for index, item in enumerate(items_to_display):
                item_name = item[1]  # index 1: item name
                item_level = item[2]  # index 2: item level
                is_equipped = equipped_item and (equipped_item[0] == item[0])
                
                # Append item details to the display string
                items_display_string += (
                        f"{number_emojis[index + 1]}: "
                        f"{item_name} (Level {item_level})"
                        f"{' [E]' if is_equipped else ''}\n"
                )
            # Add a single field for all items
            embed.add_field(
                name="Items:",
                value=items_display_string.strip(),  # Use strip to remove any trailing newline
                inline=False
            )
                
            # Add the choose field outside the loop, since it is the same for all items
            embed.add_field(
                name="Instructions",
                value=(f"[ℹ️] Select an item you want to interact with.\n"
                       f"[🚪] Close your inventory."),
                inline=False
            )
            await inventory_message.edit(embed=embed)
            

            for i in range(len(items_to_display) + 1):  # Only add reactions for existing items
                await inventory_message.add_reaction(number_emojis[i])

            def check(reaction, user):
                return (user == context.author
                        and reaction.message.id == inventory_message.id)

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                selected_index = number_emojis.index(str(reaction.emoji))  # Get the index of the selected item
                print(f'{selected_index} was selected')
                if selected_index == 0: # exit
                    await inventory_message.delete()
                    return
                selected_index -= 1 # get to true index of item
                selected_item = items_to_display[selected_index]
                print(f'associated item: {selected_item}')
                # Display selected item details
                item_name = selected_item[1] 
                item_level = selected_item[2] 
                item_attack = selected_item[3] if len(selected_item) > 4 else 0  # Assuming attack is at index 4
                item_defence = selected_item[4] if len(selected_item) > 5 else 0  # Assuming defence is at index 5
                item_rarity = selected_item[5] if len(selected_item) > 6 else 0  # Assuming rarity is at index 6
                item_passive = selected_item[6]
                embed.description = f"**{item_name}** (Level {item_level}):"
                embed.clear_fields()
                embed.add_field(name="Attack", value=item_attack, inline=True)
                embed.add_field(name="Defence", value=item_defence, inline=True)
                embed.add_field(name="Rarity", value=item_rarity, inline=True)
                embed.add_field(name="Passive", value=item_passive, inline=False)
                effect_description = self.get_passive_effect(item_passive)  # Get the associated effect message
                embed.add_field(name="Effect", value=effect_description, inline=False)
                item_guide = (
                    "⚔️ to equip.\n"
                    "🔨 to forge.\n"
                    "⚙️ to refine.\n"
                    "🗑️ to discard.\n"
                    "◀️ to go back."
                )

                embed.add_field(name="Item Guide", value=item_guide, inline=False)

                await inventory_message.edit(embed=embed)

                await inventory_message.clear_reactions()
                action_reactions = ["⚔️", "🔨", "⚙️", "🗑️", "◀️"]

                for emoji in action_reactions:
                    await inventory_message.add_reaction(emoji)

                try:
                    action_reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                    if str(action_reaction.emoji) == "⚔️":
                        await self.equip(context, selected_item, item_name, inventory_message, embed)
                        continue
                    elif str(action_reaction.emoji) == "🔨":
                        await self.forge_item(context, selected_item, user_id, server_id, embed, inventory_message)
                        continue
                    elif str(action_reaction.emoji) == "⚙️":
                        await self.refine_item(context, selected_item, user_id, server_id, embed, inventory_message)
                        continue
                    elif str(action_reaction.emoji) == "🗑️":
                        await self.discard(context, selected_item, item_name, inventory_message, embed)
                        continue
                    elif str(action_reaction.emoji) == "◀️":
                        print('Go back')
                        continue

                except asyncio.TimeoutError:
                    await inventory_message.delete()
                    break
            except asyncio.TimeoutError:
                await inventory_message.delete()
                break

    async def equip(self, context: Context, selected_item: tuple, new_equip: str, message, embed) -> None:
        """Equip an item."""
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        
        if not existing_user: 
            await context.send("You are not registered with the 🏦 Adventurer's guild."
                               " Please /register first.")
            return
                
        equipped_item = await self.bot.database.get_equipped_item(user_id)

        if equipped_item:
            current_equipped_id = equipped_item[0] 
            if selected_item[0] == current_equipped_id:
                embed.add_field(name="But why", value=(f"You already have **{new_equip}** equipped! "
                                                       " Returning to main menu..."), inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

            item_name = equipped_item[2]  # Assuming item_name is at index 2
            confirmation_embed = discord.Embed(
                title="Switch weapon",
                description=f"Unequip **{item_name}** and equip **{new_equip}** instead?",
                color=0xFFCC00
            )
            await message.edit(embed=confirmation_embed)
            await message.clear_reactions()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def confirm_check(reaction, user):
                return (user == context.author and 
                        reaction.message.id == message.id 
                        and str(reaction.emoji) in ["✅", "❌"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)
                if str(reaction.emoji) == "❌":
                    await context.send("You put the equipment away.")
                    return

            except asyncio.TimeoutError:
                await context.send("Your arms grow tired, you put your equipment away.")
                return

        item_id = selected_item[0]
        await self.bot.database.equip_item(user_id, item_id)
        confirmation_embed.add_field(name="Equip", value=f"Equipped **{new_equip}**\nReturning to main menu...", inline=False)
        await message.edit(embed=confirmation_embed)
        await asyncio.sleep(3)

    async def discard(self, context: Context, selected_item: tuple, item_name: str, message, embed) -> None:
        """Discard an item from the inventory."""
        item_id = selected_item[0]

        confirmation_embed = discord.Embed(
            title="Confirm Discard",
            description=f"Are you sure you want to discard **{item_name}**? This action cannot be undone.",
            color=0xFF0000,
        )
        await message.edit(embed=confirmation_embed)
        await message.clear_reactions()
        await message.add_reaction("✅")  # Confirm discard
        await message.add_reaction("❌")  # Cancel discard

        def confirm_check(reaction, user):
            return (user == context.author and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                confirmation_embed.add_field(name="Cancel", value=f"Returning to main menu...", inline=False)
                await message.edit(embed=confirmation_embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await context.send("You took too long to decide.")
            return

        await self.bot.database.discard_item(item_id)
        confirmation_embed.add_field(name="Discard", 
                                     value=f"Discarded **{item_name}**. Returning to main menu...", 
                                     inline=False)
        await message.edit(embed=confirmation_embed)
        await asyncio.sleep(3)


    async def forge_item(self, context: Context, selected_item: tuple, user_id: str, server_id: str, embed, message) -> None:
        item_id = selected_item[0] # unique id of item
        item_name = selected_item[1]

        # Fetch current item details
        item_details = await self.bot.database.fetch_item_by_id(item_id)
        
        if not item_details:
            await context.send("Item not found.")
            return

        # Get the current state of the item
        forges_remaining = item_details[9]  # Index where `forges_remaining` is stored
        print(f'Forges remaining for item id {item_id}: {forges_remaining}')
        # Define the costs lookup based on the forges remaining
        costs = {
            5: (50, 50, 50, 500),   # (ore_cost, wood_cost, bone_cost, gp_cost)
            4: (50, 50, 50, 2000),
            3: (50, 50, 50, 5000),
            2: (50, 50, 50, 10000),
            1: (50, 50, 50, 20000),
        }
        
        # Check if there are forges remaining
        if forges_remaining == 0:
            embed.add_field(name="Forging", value=f"This item cannot be forged anymore.", inline=True)
            await message.edit(embed=embed)
            return

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]  # Fetch the amount of gold from existing_user

        # Resources from the mining, woodcutting, and fishing tables
        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

        # Get the corresponding costs based on forges remaining
        ore_cost, wood_cost, bone_cost, gp_cost = costs[forges_remaining]
        cost_index = 8 - forges_remaining
        print(f'forge will cost {ore_cost} ore, {wood_cost} logs, {bone_cost} bones, {gp_cost} gp')
        # print(mining_data[cost_index])
        forges_data = {
            5: ('iron', 'oak', 'desiccated'),
            4: ('coal', 'willow', 'regular'),
            3: ('gold', 'mahogany', 'sturdy'),
            2: ('platinum', 'magic', 'reinforced'),
            1: ('idea', 'idea', 'titanium'),
        }

        if forges_remaining in forges_data:
            ore, logs, bones = forges_data[forges_remaining]
        else:
            ore, logs, bones = None, None, None
        # Check if the user has enough resources and gold
        if (mining_data[cost_index] < ore_cost or  # Check for the required ore
            woodcutting_data[cost_index] < wood_cost or  # Check for the required wood
            fishing_data[cost_index] < bone_cost or  # Check for the required bones
            player_gp < gp_cost):  # Check for the gold
            embed.add_field(name="Forging", 
                            value=(f"You do not have enough resources to forge this item.\n"
                                    f"Forging costs:\n"
                                    f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                                    f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                                    f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                                    f"- GP cost: **{gp_cost}**\n"), 
                            inline=True)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        

        # Create a confirmation embed to show the costs
        confirm_embed = discord.Embed(
            title="Forge",
            description=(f"You are about to forge **{item_name}**.\n"
                        f"Forging costs:\n"
                        f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                        f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                        f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                        f"- GP cost: **{gp_cost}**\n"
                        "Do you want to continue?"),
            color=0xFFFF00
        )
        await message.edit(embed=confirm_embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return (user == context.author and 
                    reaction.message.id == message.id 
                    and str(reaction.emoji) in ["✅", "❌"])
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                confirm_embed.add_field(name="Cancel", value=f"Returning to main menu...", inline=False)
                await message.edit(embed=confirm_embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await context.send("You took too long to decide.")
            return
        # Deduct the costs from the user's resources
        print('subtracting ore')
        await self.bot.database.update_mining_resources(user_id, server_id, {
            'iron': -ore_cost if forges_remaining == 5 else 0,  # Set cost based on forges_remaining
            'coal': -ore_cost if forges_remaining == 4 else 0,  # Coal for forges_remaining == 4
            'gold': -ore_cost if forges_remaining == 3 else 0,  # Gold for forges_remaining == 3
            'platinum': -ore_cost if forges_remaining == 2 else 0,  # Platinum for forges_remaining == 2
            'idea': -ore_cost if forges_remaining == 1 else 0,  # Idea for forges_remaining == 1
        })
        print('subtracting wood')
        await self.bot.database.update_woodcutting_resources(user_id, server_id, {
            'oak': -wood_cost if forges_remaining == 5 else 0,  # Oak for 5 or 4
            'willow': -wood_cost if forges_remaining == 4 else 0,  # Willow for 4
            'mahogany': -wood_cost if forges_remaining == 3 else 0,  # Mahogany for 3
            'magic': -wood_cost if forges_remaining == 2 else 0,  # Magic for 2
            'idea': -wood_cost if forges_remaining == 1 else 0,  # Idea for 1
        })
        print('subtracting bones')
        await self.bot.database.update_fishing_resources(user_id, server_id, {
            'desiccated': -bone_cost if forges_remaining == 5 else 0,  # Desiccated for 5 or 4
            'regular': -bone_cost if forges_remaining == 4 else 0,  # Regular for 4
            'sturdy': -bone_cost if forges_remaining == 3 else 0,  # Sturdy for 3
            'reinforced': -bone_cost if forges_remaining == 2 else 0,  # Reinforced for 2
            'titanium': -bone_cost if forges_remaining == 1 else 0,  # Titanium for 1
        })
        print('subtracting gold')
        # Deduct the gold
        await self.bot.database.add_gold(user_id, -gp_cost)

        new_forges_remaining = forges_remaining - 1
        base_success_rate = 0.8
        success_rate = base_success_rate - (5 - forges_remaining) * 0.05
        success_rate = max(0, min(success_rate, 1))
        forge_success = random.random() <= success_rate  

        if forge_success:
            print('forge success')
            current_passive = item_details[7]  # Index where `passive` is stored
            
            if current_passive == "none":
                print('item has no passive')
                # Assign a new passive
                passives = [
                    "burning",
                    "poisonous",
                    "polished",
                    "sparking",
                    "sturdy",
                    "piercing",
                    "strengthened",
                    "accurate",
                    "echo"
                ]
                new_passive = random.choice(passives)  # Assign default new passive (you can define logic for tiering)
                print(f'Assigning {new_passive} to item {item_id}')
                # Set the passive in the database
                await self.bot.database.update_item_passive(item_id, new_passive)
                embed.add_field(name="Forging success", 
                                value=(f"🎊 Congratulations! 🎊 " 
                                        f"**{item_name}** has gained the " 
                                        f"**{new_passive.capitalize()}** passive."), 
                                        inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(7)
            else:
                print('item has passive, upgrade it')
                new_passive = await self.upgrade_passive(current_passive)  # Function to upgrade the passive
                print(f'new passive is {new_passive}')
                await self.bot.database.update_item_passive(item_id, new_passive)
                embed.add_field(name="Forging success", 
                                value=(f"🎊 Congratulations! 🎊 "
                                       f"**{item_name}**'s passive upgrades from **{current_passive.capitalize()}**"
                                       f" to **{new_passive.capitalize()}**."),
                                       inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(7)
        else:
            print('forging failed')
            embed.add_field(name="Forging", 
                value=(f"Forging failed! "
                        f"Better luck next time. 🥺 \n"
                        f"Returning to main menu..."),
                        inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
        
        # Update the item in the database with the new forges_remaining count
        await self.bot.database.update_item_forge_count(item_id, new_forges_remaining)

    async def upgrade_passive(self, current_passive: str) -> str:
        """Upgrade the current passive to a stronger version."""
        passive_upgrade_table = {
            "burning": "flaming",
            "flaming": "scorching",
            "scorching": "incinerating",
            "incinerating": "carbonising",
            "poisonous": "noxious",
            "noxious": "venomous",
            "venomous": "toxic",
            "toxic": "lethal",
            "polished": "honed",
            "honed": "gleaming",
            "gleaming": "tempered",
            "tempered": "flaring",
            "sparking": "shocking",
            "shocking": "discharging",
            "discharging": "electrocuting",
            "electrocuting": "vapourising",
            "sturdy": "reinforced",
            "reinforced": "thickened",
            "thickened": "impregnable",
            "impregnable": "impenetrable",
            "piercing": "keen",
            "keen": "incisive",
            "incisive": "puncturing",
            "puncturing": "penetrating",
            "strengthened": "forceful",
            "forceful": "overwhelming",
            "overwhelming": "devastating",
            "devastating": "catastrophic",
            "accurate": "precise",
            "precise": "sharpshooter",
            "sharpshooter": "deadeye",
            "deadeye": "bullseye",
            "echo": "echoo",
            "echoo": "echooo",
            "echooo": "echoooo",
            "echoooo": "echoes"
        }
        return passive_upgrade_table.get(current_passive, current_passive)  # Return current if maxed out
    
    def get_passive_effect(self, passive: str) -> str:
        passive_messages = {
            "burning": "Increases your maximum hit (1d6).",
            "flaming": "Increases your maximum hit. (2d6)",
            "scorching": "Increases your maximum hit. (3d6)",
            "incinerating": "Increases your maximum hit. (4d6)",
            "carbonising": "Increases your maximum hit. (5d6)",
            
            "poisonous": "Additional damage on misses. (3d6)",
            "noxious": "Additional damage on misses. (4d6)",
            "venomous": "Additional damage on misses. (5d6)",
            "toxic": "Additional damage on misses. (6d6)",
            "lethal": "Additional damage on misses. (7d6)",
            
            "polished": "Reduce monster's defence. (5%)",
            "honed": "Reduce monster's defence. (10%)",
            "gleaming": "Reduce monster's defence. (15%)",
            "tempered": "Reduce monster's defence. (20%)",
            "flaring": "Reduce monster's defence. (25%)",
            
            "sparking": "Additional damage on normal hits. (2d6)",
            "shocking": "Additional damage on normal hits. (3d6)",
            "discharging": "Additional damage on normal hits. (4d6)",
            "electrocuting": "Additional damage on normal hits. (5d6)",
            "vapourising": "Additional damage on normal hits. (6d6)",
            
            "sturdy": "Additional defence. (+3)",
            "reinforced": "Additional defence. (+6)",
            "thickened": "Additional defence. (+9)",
            "impregnable": "Additional defence. (+12)",
            "impenetrable": "Additional defence. (+15)",
            
            "piercing": "Additional crit chance. (3%)",
            "keen": "Additional crit chance. (6%)",
            "incisive": "Additional crit chance. (9%)",
            "puncturing": "Additional crit chance. (12%)",
            "penetrating": "Additional crit chance. (15%)",
            
            "strengthened": "Culling strike.",
            "forceful": "Culling strike.",
            "overwhelming": "Culling strike.",
            "devastating": "Culling strike.",
            "catastrophic": "Culling strike.",
            
            "accurate": "Increased accuracy.",
            "precise": "Increased accuracy.",
            "sharpshooter": "Increased accuracy.",
            "deadeye": "Increased accuracy.",
            "bullseye": "Increased accuracy.",
            
            "echo": "Echo normal hits.",
            "echoo": "Echo normal hits.",
            "echooo": "Echo normal hits.",
            "echoooo": "Echo normal hits.",
            "echoes": "Echo normal hits."
        }
        return passive_messages.get(passive, "No effect.")
    
    async def refine_item(self, context: Context, 
                          selected_item: tuple, 
                          user_id: str, server_id: str,
                          embed,
                          message) -> None:
        item_id = selected_item[0]  # unique id of item
        item_name = selected_item[1]
        item_level = selected_item[2]
        # Fetch current item details
        item_details = await self.bot.database.fetch_item_by_id(item_id)
        
        if not item_details:
            await context.send("Item not found.")
            return

        # Get the current state of the item
        refines_remaining = item_details[10]  # Assuming refines_remaining is at index 10
        player_gold = await self.bot.database.fetch_user_gold(user_id, server_id)
        refinement_runes = await self.bot.database.fetch_refinement_runes(user_id)

        if refines_remaining <= 0:
            if refinement_runes > 0:
                # Create confirmation embed for applying a Rune of Refinement
                confirm_embed = discord.Embed(
                    title="Apply Rune of Refinement?",
                    description=(f"**{item_name}** has no refine attempts remaining.\n"
                                f"Do you want to use a **Rune of Refinement** to add a refining attempt?\n"
                                f"(You have {refinement_runes} runes available)"),
                    color=0xFFCC00
                )
                await message.edit(embed=confirm_embed)

                await message.add_reaction("✅")  # Confirm
                await message.add_reaction("❌")  # Cancel

                def confirm_check(reaction, user):
                    return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

                    if str(reaction.emoji) == "✅":
                        # Applying the rune
                        await self.bot.database.update_refinement_runes(user_id, -1)  # Deduct a rune
                        await self.bot.database.update_item_refine_count(item_id, 1)  # Set refines_remaining to 1
                        confirm_embed.add_field(name="Rune of Refinement",
                                                 value=(f"You have successfully applied a **Rune of Refinement**!"
                                                        f"{item_name} now has **1** refine remaining."),
                                                   inline=False)
                        refines_remaining = 1  # Update local variable to reflect the change
                        await message.edit(embed=confirm_embed)
                        await asyncio.sleep(5)
                    elif str(reaction.emoji) == "❌":
                        confirm_embed.add_field(name="Rune of Refinement",
                            value=(f"You chose not to apply a Rune of Refinement."),
                            inline=False)
                        await message.edit(embed=confirm_embed)
                        await asyncio.sleep(5)
                        return  # Exit the method to return to the inventory interface

                except asyncio.TimeoutError:
                    return
            return

        # Determine cost of the refinement
        refine_costs = [10000, 30000, 50000, 100000, 200000]
        cost = refine_costs[5 - refines_remaining]  # Costs increase when refines_remaining decreases
        # Create a confirmation embed showing the cost
        cost_embed = discord.Embed(
            title="Confirm Refinement",
            description=f"You are about to refine **{item_name}**.\n"
                        f"Cost: **{cost:,} GP**\n"
                        f"Refines Remaining: **{refines_remaining}**\n"
                        "Do you want to proceed?",
            color=0xFFCC00
        )
        await message.edit(embed=cost_embed)
        await message.clear_reactions()
        await message.add_reaction("✅")  # Confirm
        await message.add_reaction("❌")  # Cancel

        def confirm_check(reaction, user):
            return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                cost_embed.add_field(name="Refining", value=f"Refinement cancelled. Returning to main menu...", inline=False)
                await message.edit(embed=cost_embed)
                await asyncio.sleep(5)
                return

        except asyncio.TimeoutError:
            await context.send("You took too long to respond. Refinement cancelled.")
            return
        
        if player_gold < cost:
            cost_embed.add_field(name="Refining", value=f"You do not have enough gold. Returning to main menu...", inline=False)
            await message.edit(embed=cost_embed)
            await asyncio.sleep(5)
            return

        # Deduct the gold cost from the user's resources
        await self.bot.database.update_user_gold(user_id, player_gold - cost)

        # Printing the refinement process
        cost_embed.add_field(name="Refining", value=f"You chose to refine {item_name}.", inline=False)
        await message.edit(embed=cost_embed)
        
        # Perform roll checks for attack, defense, rarity
        attack_roll = random.randint(0, 100) < 80  # 80% chance for attack
        defense_roll = random.randint(0, 100) < 50  # 50% chance for defense
        rarity_roll = random.randint(0, 100) < 20  # 20% chance for rarity

        attack_modifier = 0
        defense_modifier = 0
        rarity_modifier = 0
        max_range = int(item_level / 10) + 2
        if attack_roll:
            attack_modifier = random.randint(2, max_range)
            await self.bot.database.increase_item_attack(item_id, attack_modifier) 
        else:
            attack_modifier = 1
            await self.bot.database.increase_item_attack(item_id, attack_modifier) 
        
        if defense_roll:
            defense_modifier = random.randint(2, max_range)
            await self.bot.database.increase_item_defence(item_id, defense_modifier) 
        else:
            defense_modifier = 1
            await self.bot.database.increase_item_defence(item_id, defense_modifier)  

        if rarity_roll:
            rarity_modifier = random.randint(5, max_range * 5)  # Example range for rarity increase
            await self.bot.database.update_item_rarity(item_id, rarity_modifier)

        # Update refines_remaining in the database
        await self.bot.database.update_item_refine_count(item_id, refines_remaining - 1)

        # Sending a message about the refinements
        result_message = []
        if attack_modifier > 0:
            result_message.append(f"Attack increased by **{attack_modifier}**!")
        if defense_modifier > 0:
            result_message.append(f"Defense increased by **{defense_modifier}**!")
        if rarity_modifier > 0:
            result_message.append(f"Rarity increased by **{rarity_modifier}**!")

        if not result_message:
            cost_embed.add_field(name="Refining", value=f"The refinement was successful, but no stats were upgraded.", inline=False)
            await message.edit(embed=cost_embed)
            await asyncio.sleep(5)
        else:
            cost_embed.add_field(name="Refining", value=("\n".join(result_message)), inline=False)
            await message.edit(embed=cost_embed)
            await asyncio.sleep(5)

    @commands.hybrid_command(name="leaderboard", description="Show the top adventurers sorted by level.")
    async def leaderboard(self, context: Context) -> None:
        """Fetch and display the top 10 adventurers sorted by level."""
        top_users = await self.bot.database.fetch_top_users_by_level(limit=10)

        if not top_users:
            await context.send("No adventurers found.")
            return

        # Create an embed for the leaderboard
        embed = discord.Embed(
            title="Hiscores 🏆",
            color=0x00FF00
        )

        # Construct the leaderboard information
        leaderboard_lines = []
        for idx, user in enumerate(top_users, start=1):
            user_name = user[3]  # Assuming player name is at index 3
            user_level = user[4]  # Assuming level is at index 4

            # Build leaderboard line with the appropriate emoji
            if idx == 1:
                leaderboard_lines.append(f"🥇 **{user_name}** - Level {user_level}")
            elif idx == 2:
                leaderboard_lines.append(f"🥈 **{user_name}** - Level {user_level}")
            elif idx == 3:
                leaderboard_lines.append(f"🥉 **{user_name}** - Level {user_level}")
            else:
                leaderboard_lines.append(f"**{idx}: {user_name}** - Level {user_level}")

        leaderboard_text = "\n".join(leaderboard_lines)
        embed.add_field(name="Top Adventurers:", value=leaderboard_text, inline=False)

        await context.send(embed=embed)
    
async def setup(bot) -> None:
    await bot.add_cog(Character(bot))