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

async def setup(bot) -> None:
    await bot.add_cog(Trade(bot))