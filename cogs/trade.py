import discord
from discord.ext import commands
from discord.ext.commands import Context
import asyncio

class Trade(commands.Cog, name="trade"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.active_users = {}  # Dictionary to track active users

    @commands.hybrid_command(name="send", description="Send gold to another player.")
    async def send(self, context: Context, receiver: discord.User, amount: int) -> None:
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        
        # Check if the user is trying to send gold to themselves
        if receiver.id == context.author.id:
            await context.send("You cannot send gold to yourself.")
            return
            
        # Fetch the sender's user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return
        
        if user_id in self.active_users:
            await context.send("You are already sending gold. Please finish that process first.")
            return

        if self.bot.state_manager.is_active(user_id):
            await context.send("You are currently busy with another operation. Please finish that first.")
            return
        
        if existing_user[4] <= 10:
            await context.send("You have to be above level 10 to send gold.")
            return
        
        self.bot.state_manager.set_active(user_id, "gamble")
        self.active_users[user_id] = True
        # Check if the amount is valid
        if amount <= 0:
            await context.send("You cannot send zero or negative gold.")
            return

        current_gold = existing_user[6]  # Assuming gold is at index 6
        
        # Check if the sender has enough gold
        if amount > current_gold:
            await context.send(f"You don't have enough gold to send. Your current balance is: 💰 **{current_gold:,}**.")
            return

        # Confirm the action
        confirm_embed = discord.Embed(
            title="Confirm Send Gold",
            description=f"Are you sure you want to send 💰 **{amount}** gold to {receiver.mention}?",
            color=0x00FF00
        )
        message = await context.send(embed=confirm_embed)

        await message.add_reaction("✅")  # Confirm
        await message.add_reaction("❌")  # Cancel

        def confirm_check(reaction, user):
            return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "✅":
                # The sender has confirmed the action
                await self.bot.database.update_user_gold(user_id, current_gold - amount)  # Deduct from sender
                await self.bot.database.add_gold(str(receiver.id), amount)  # Add to receiver

                # Update the embed message to inform of the successful transaction
                confirm_embed.description = f"Successfully sent 💰 **{amount}** gold to {receiver.mention}! 🎉"
                await message.edit(embed=confirm_embed)
            else:
                confirm_embed.description = "Transaction cancelled."
                await message.edit(embed=confirm_embed)
        except asyncio.TimeoutError:
            await message.delete()  # Delete the confirmation message if timed out.
        finally:
            del self.active_users[user_id]
            self.bot.state_manager.clear_active(user_id)

    @commands.hybrid_command(name="send_item", description="Send an item to another player.")
    async def send_item(self, context: Context, receiver: discord.User, item_id: int) -> None:
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        # Check if the user is trying to send the item to themselves
        if receiver.id == context.author.id:
            await context.send("You cannot send items to yourself.")
            return

        # Check if the user has any active operations
        if self.bot.state_manager.is_active(user_id):
            await context.send("You are currently busy with another operation. Please finish that first.")
            return
        self.bot.state_manager.set_active(user_id, "send_item")  # Set send_item as active operation

        # Fetch the sender's user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return

        # Fetch the item details
        item_details = await self.bot.database.fetch_item_by_id(item_id)
        if not item_details:
            await context.send("Item not found. Please check the item ID and try again.")
            return

        item_level = int(item_details[3])  # Assuming item_level is at index 3
        current_level = existing_user[4]  # Assuming user level is at index 4
        
        # Check level difference
        if (current_level - item_level) > 15:
            await context.send(f"You cannot send this item due to ilvl diff being too great. (< 15)")
            return
        
        # Check if the item is equipped
        equipped_item = await self.bot.database.get_equipped_item(user_id)
        if equipped_item and equipped_item[0] == item_id:  # Assuming item_id is at index 0
            await context.send("You cannot send an item that you have equipped.")
            return
        
        # Fetch the receiver's item data to check their current item count
        receiver_items = await self.bot.database.fetch_user_items(str(receiver.id))
        
        # Check if the receiver has less than 3 items in their inventory
        if len(receiver_items) >= 3:
            await context.send(f"{receiver.mention} cannot receive more items because they already have 3 items in their inventory.")
            return

        # Confirm the action
        confirm_embed = discord.Embed(
            title="Confirm Send Item",
            description=f"Send **{item_details[2]}** to {receiver.mention}?",
            color=0x00FF00
        )
        message = await context.send(embed=confirm_embed)

        await message.add_reaction("✅")  # Confirm
        await message.add_reaction("❌")  # Cancel

        def confirm_check(reaction, user):
            return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "✅":
                # The sender has confirmed the action
                await self.bot.database.send_item(receiver.id, item_id)  # Create a method to handle item transfer
                await context.send(f"Sent **{item_details[2]}** to {receiver.mention}! 🎉")
            else:
                await context.send("Transaction cancelled.")
        except asyncio.TimeoutError:
            await message.delete()  # Delete the confirmation message if timed out.
        finally:
            self.bot.state_manager.clear_active(user_id)


    @commands.hybrid_command(name="send_material", description="Send skilling materials to another player.")
    async def send_material(self, context: Context, receiver: discord.User, material: str, amount: int) -> None:
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return

        # Check if the user is trying to send materials to themselves
        if receiver.id == context.author.id:
            await context.send("You cannot send materials to yourself.")
            return
        
        if self.bot.state_manager.is_active(user_id):
            await context.send("You are currently busy with another operation. Please finish that first.")
            return
        # Set the user as active in operations
        self.bot.state_manager.set_active(user_id, "send_material")

        try:
            # Prepare the material name and types
            material_lower = material.lower()  # Case-insensitive match

            # Determine which table to query based on material type
            if material_lower in ["iron", "coal", "gold", "platinum"]:
                table = "mining"
                material_name = material_lower
            elif material_lower in ["desiccated", "regular", "sturdy", "reinforced"]:
                table = "fishing"
                material_name = f"{material_lower}_bones"
            elif material_lower in ["oak", "willow", "mahogany", "magic"]:
                table = "woodcutting"
                material_name = f"{material_lower}_logs"
            else:
                await context.send(f"Invalid material type.\n"
                                   f"Ores: iron, coal, gold, and platinum.\n"
                                   f"Bones: desiccated, regular, sturdy, and reinforced.\n"
                                   f"Wood: oak, willow, mahogany, magic.")
                return

            # Fetch the user's current resources from the respective table
            if table == "mining":
                material_index = {
                    "iron": 3,
                    "coal": 4,
                    "gold": 5,
                    "platinum": 6
                }[material_lower]
                user_resources = await self.bot.database.fetch_user_mining(user_id, server_id)
                current_amount = user_resources[material_index]
            elif table == "fishing":
                material_index = {
                    "desiccated": 3, "regular": 4, "sturdy": 5, "reinforced": 6
                                  }[material_lower]
                user_resources = await self.bot.database.fetch_user_fishing(user_id, server_id)
                current_amount = user_resources[material_index]
            else:  # woodcutting
                material_index = {
                    "oak": 3, "willow": 4, "mahogany": 5, "magic": 6, "idea": 7
                    }[material_lower]
                user_resources = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
                current_amount = user_resources[material_index]

            # Check if the specified amount is valid
            if amount <= 0:
                await context.send("Invalid amount. You must specify a positive amount of materials.")
                return

            if amount > current_amount:
                await context.send(f"You do not have enough {material_lower} to send. You currently have: {current_amount}.")
                return

            # Create a confirmation embed
            confirm_embed = discord.Embed(
                title="Confirm",
                description=(f"Are you sure you want to send **{amount}** **{material_lower.title()}** "
                            f"to {receiver.mention}?"),
                color=0x00FF00
            )

            # Send the confirmation embed and get user reaction
            confirm_message = await context.send(embed=confirm_embed)
            await confirm_message.add_reaction("✅")  # Confirm
            await confirm_message.add_reaction("❌")  # Cancel

            def confirm_check(reaction, user):
                return user == context.author and reaction.message.id == confirm_message.id and str(reaction.emoji) in ["✅", "❌"]

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)
                if str(reaction.emoji) == "✅":
                    if table == "mining":
                        await self.bot.database.update_mining_resource(user_id, server_id, material_name, -amount)  # Subtract from sender
                        await self.bot.database.update_mining_resource(str(receiver.id), server_id, material_name, amount)  # Add to receiver
                    elif table == "fishing":
                        await self.bot.database.update_fishing_resource(user_id, server_id, material_name, -amount)  # Subtract from sender
                        await self.bot.database.update_fishing_resource(str(receiver.id), server_id, material_name, amount)  # Add to receiver
                    elif table == "woodcutting":
                        await self.bot.database.update_woodcutting_resource(user_id, server_id, material_name, -amount)  # Subtract from sender
                        await self.bot.database.update_woodcutting_resource(str(receiver.id), server_id, material_name, amount)  # Add to receiver
                    
                    # Update the confirmation embed to indicate success
                    confirm_embed.description = f"Successfully sent **{amount}** **{material_lower.title()}** to {receiver.mention}! 🎉"
                    await confirm_message.clear_reactions()
                    await confirm_message.edit(embed=confirm_embed)               
                    
                else:
                    confirm_embed.description = "Transaction cancelled."
                    await confirm_message.delete()

            except asyncio.TimeoutError:
                await confirm_message.delete()  # Delete the confirmation message if timed out.
        finally:
            # Ensure we clear the active operation regardless of success/failure
            self.bot.state_manager.clear_active(user_id)

async def setup(bot) -> None:
    await bot.add_cog(Trade(bot))