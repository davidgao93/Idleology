import discord
from discord.ext import commands
from discord.ext.commands import Context
import asyncio
from discord import app_commands, Interaction, Message

class Trade(commands.Cog, name="trade"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.active_users = {}  # Dictionary to track active users

    @app_commands.command(name="send", description="Send gold to another player.")
    async def send(self, interaction: Interaction, receiver: discord.User, amount: int) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        # Check if the user is trying to send gold to themselves
        if receiver.id == interaction.user:
            await interaction.response.send_message("You cannot send gold to yourself.", 
                                                    ephemeral=True)
            return
            
        # Fetch the sender's user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        if user_id in self.active_users:
            await interaction.response.send_message("You are already sending gold. Please finish that process first.")
            return

        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        if existing_user[4] <= 10:
            await interaction.response.send_message("You have to be above level 10 to send gold.")
            return
        
        self.bot.state_manager.set_active(user_id, "trade")
        self.active_users[user_id] = True
        # Check if the amount is valid
        if amount <= 0:
            await interaction.response.send_message("You cannot send zero or negative gold.")
            return

        current_gold = existing_user[6]  # Assuming gold is at index 6
        
        # Check if the sender has enough gold
        if amount > current_gold:
            await interaction.response.send_message(f"You don't have enough gold to send. Your current balance is: 💰 **{current_gold:,}**.")
            return

        # Confirm the action
        embed = discord.Embed(
            title="Confirm",
            description=f"Are you sure you want to send 💰 **{amount:,}** gold to {receiver.mention}?",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()

        await message.add_reaction("✅")  # Confirm
        await message.add_reaction("❌")  # Cancel

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "✅":
                # The sender has confirmed the action
                await self.bot.database.update_user_gold(user_id, current_gold - amount)  # Deduct from sender
                await self.bot.database.add_gold(str(receiver.id), amount)  # Add to receiver

                # Update the embed message to inform of the successful transaction
                embed.description = f"Successfully sent 💰 **{amount:,}** gold to {receiver.mention}! 🎉"
                await message.edit(embed=embed)
                await message.clear_reactions()
            else:
                embed.description = "Transaction cancelled."
                await message.edit(embed=embed)
        except asyncio.TimeoutError:
            await message.delete()  # Delete the confirmation message if timed out.
        finally:
            del self.active_users[user_id]
            self.bot.state_manager.clear_active(user_id)


    @app_commands.command(name="send_material", description="Send skilling materials to another player.")
    async def send_material(self, interaction: Interaction, receiver: discord.User, material: str, amount: int) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        # Check if the user is trying to send materials to themselves
        if receiver.id == interaction.user:
            await interaction.response.send_message("You cannot send materials to yourself.")
            return
        
        if not await self.bot.check_is_active(interaction, user_id):
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
                await interaction.response.send_message(f"Invalid material type.\n"
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
                await interaction.response.send_message("Invalid amount. You must specify a positive amount of materials.")
                return

            if amount > current_amount:
                await interaction.response.send_message(f"You do not have enough {material_lower} to send. You currently have: {current_amount}.")
                return

            # Create a confirmation embed
            embed = discord.Embed(
                title="Confirm",
                description=(f"Are you sure you want to send **{amount:,}** **{material_lower.title()}** "
                            f"to {receiver.mention}?"),
                color=0x00FF00
            )

            # Send the confirmation embed and get user reaction
            await interaction.response.send_message(embed=embed)
            message: Message = await interaction.original_response()
            await message.add_reaction("✅")  # Confirm
            await message.add_reaction("❌")  # Cancel

            def confirm_check(reaction, user):
                return (user == interaction.user and 
                        reaction.message.id == message.id and 
                        str(reaction.emoji) in ["✅", "❌"])

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
                    embed.description = f"Successfully sent **{amount:,}** **{material_lower.title()}** to {receiver.mention}! 🎉"
                    await message.clear_reactions()
                    await message.edit(embed=embed)               
                    
                else:
                    await message.delete()
                    self.bot.state_manager.clear_active(user_id)
            except asyncio.TimeoutError:
                await message.delete()  # Delete the confirmation message if timed out.
                self.bot.state_manager.clear_active(user_id)
        finally:
            # Ensure we clear the active operation regardless of success/failure
            self.bot.state_manager.clear_active(user_id)


    @app_commands.command(name="send_key", description="Send a key to another player.")
    async def send_key(self, interaction: Interaction, key_type: str, receiver: discord.User) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Check if the user is trying to send a key to themselves
        if receiver.id == interaction.user.id:
            await interaction.response.send_message("You cannot send keys to yourself.", ephemeral=True)
            return

        if key_type.lower() not in ["angelic", "draconic", "void"]:
            await interaction.response.send_message("Please specify either 'angelic', 'draconic', or 'void'.", ephemeral=True)
            return

        # Fetch the sender's user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        # Check if the sender has any active operations
        if not await self.bot.check_is_active(interaction, user_id):
            return
     
        dragon_keys = existing_user[25] # dragon keys
        angel_keys = existing_user[26]
        void_keys = existing_user[30]

        # Check if the sender has the specified key
        if key_type.lower() == "angelic":
            sender_key_count = angel_keys
        if key_type.lower() == "draconic":
            sender_key_count = dragon_keys
        if key_type.lower() == "void":
            sender_key_count = void_keys

        if sender_key_count < 1:
            await interaction.response.send_message(f"You do not have any {key_type} keys to send.", ephemeral=True)
            return

        self.bot.state_manager.set_active(user_id, "send_key")

        # Confirm the action
        embed = discord.Embed(
            title="Confirm Send Key",
            description=f"Send a {key_type.title()} Key to {receiver.mention}?",
            color=0x00FF00
        )

        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()

        await message.add_reaction("✅")  # Confirm
        await message.add_reaction("❌")  # Cancel

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)
            if str(reaction.emoji) == "✅":
                # Reduce the key count from the sender and add to the receiver
                if key_type.lower() == "angelic":
                    await self.bot.database.add_angel_key(user_id, -1)
                    await self.bot.database.add_angel_key(str(receiver.id), 1)
                elif key_type.lower() == "draconic":
                    await self.bot.database.add_dragon_key(user_id, -1)
                    await self.bot.database.add_dragon_key(str(receiver.id), 1)
                elif key_type.lower() == "void":
                    await self.bot.database.add_void_keys(user_id, -1)
                    await self.bot.database.add_void_keys(str(receiver.id), 1)

                # Update the embed to indicate success
                embed.description = f"Sent a {key_type.title()} Key to {receiver.mention}! 🎉"
                await message.clear_reactions()
                await message.edit(embed=embed)

            else:
                await message.delete()

        except asyncio.TimeoutError:
            await message.delete()

        finally:
            self.bot.state_manager.clear_active(user_id)

async def setup(bot) -> None:
    await bot.add_cog(Trade(bot))