import discord
import re
from discord.ext import commands
from discord.ext.tasks import asyncio
from discord import app_commands, Interaction, Message
import csv
from datetime import datetime
import json

class Guild(commands.Cog, name="adventurer's guild"):
    def __init__(self, bot) -> None:
        self.bot = bot

    def load_character_appearances(self, gender: str):
        appearances = []
        with open('assets/profiles.csv', mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['Sex'].upper() == gender.upper():
                    appearances.append(row['URL'])
        return appearances

    @app_commands.command(name="card", description="See your adventurer card.")
    async def card(
        self, interaction: Interaction
    ) -> None:
        """
        Returns info about the sender's adventurer.
        """
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        if existing_user:
            timestamp_str = str(existing_user[18])  # e.g., '2025-05-14 21:44:30'
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

            # Get the current timestamp
            current_time = datetime.now()

            # Calculate the difference in days
            days_passed = (current_time - timestamp).days
            embed = discord.Embed(
                title=f"**{existing_user[3]}**",
                description=f"You've been an adventurer for **{days_passed}** day(s).",
                color=0x808080,
            )
            embed.add_field(name="Level ⭐", value=existing_user[4], inline=True)
                        # Fetch experience table
            with open('assets/exp.json') as file:
                exp_table = json.load(file)

            current_level = existing_user[4]  # Assuming level is at index 4
            current_exp = existing_user[5]      # Current experience
            exp_needed = exp_table["levels"].get(str(current_level), 0)  # Fetch the necessary EXP for this level

            # Calculate experience percentage
            if exp_needed > 0:
                exp_percentage = (current_exp / exp_needed) * 100
            else:
                exp_percentage = 100  # Full EXP if already max level or no exp required
            # Add the character stats to the embed
            embed.add_field(name="Experience ✨", value=f"{current_exp:,} ({exp_percentage:.2f}%)", inline=True)
            ascension = existing_user[15]
            if (ascension > 0):
                embed.add_field(name="Ascension 🌟", value=ascension, inline=True)
            embed.add_field(name="Gold 💰", value=f"{existing_user[6]:,}", inline=True)
            embed.set_thumbnail(url=existing_user[7])
            embed.add_field(name="Ideology 🧠", value=existing_user[8], inline=True)

            await interaction.response.send_message(embed=embed)


    @app_commands.command(name="register", description="Register as an adventurer.")
    async def register_adventurer(
        self, interaction: Interaction, name: str
    ) -> None:
        """
        Registers the command sender as an adventurer with the specified name.

        :param interaction: The command interaction.
        :param name: The name of the adventurer.
        """
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        success = False

        if existing_user:
            embed = discord.Embed(
                title="Registration",
                description=(f"You are already registered as **{existing_user[3]}**!"
                             f" Use /card to see your Guild card."),
                color=0x808080,
            )
            await interaction.response.send_message(embed=embed)
            return
        
        self.bot.state_manager.set_active(user_id, "register")  # Set register as active operation
        # Ask for gender selection
        embed = discord.Embed(
            title="Gender",
            description=f"Welcome to the adventurer's guild {name}!\nWhat would you like to identify as?",
            color=0x00FF00,
        )
        embed.set_image(url="https://i.imgur.com/6pRwl0k.jpeg")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        reactions = ["♂️", "♀️"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def gender_check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in reactions

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=gender_check)
            gender = "M" if str(reaction.emoji) == "♂️" else "F"

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(user_id)  
            return

        # Load appearances based on gender
        embed = discord.Embed(
            title="Appearance",
            description=f"Pick an appearance for {name}",
            color=0x00FF00,
        )
        await message.clear_reactions()
        appearances = self.load_character_appearances(gender)
        
        current_index = 0
        async def update_embed(message, index):
            embed.set_image(url=appearances[index])
            await message.edit(embed=embed)

        await update_embed(message, current_index)
        reactions = ["⬅️", "➡️", "✅"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["⬅️", "➡️", "✅"]
        appearance_url = ""
        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                if str(reaction.emoji) == "⬅️":  # Left arrow
                    current_index = (current_index - 1) % len(appearances)
                elif str(reaction.emoji) == "➡️":  # Right arrow
                    current_index = (current_index + 1) % len(appearances)
                elif str(reaction.emoji) == "✅":  # Confirm selection
                    appearance_url = appearances[current_index]
                    break
                await update_embed(message, current_index)
                await message.remove_reaction(reaction.emoji, user)

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(user_id)  
                return
            
        selected_appearance = f"{appearances[current_index]}"

        ideologies = await self.bot.database.fetch_ideologies(server_id)

        embed = discord.Embed(
            title="Ideology",
            description=f"Please **enter** your desired ideology:\n",
            color=0x00FF00,
        )
        embed.set_image(url=appearance_url)
        await message.edit(embed=embed)
        await message.clear_reactions()
        while True:
            def ideology_check(m):
                return m.author == interaction.user and m.channel == interaction.channel

            try:
                ideology_message = await self.bot.wait_for('message', timeout=60.0, check=ideology_check)
                ideology = ideology_message.content.strip()

                if ideology in ideologies:
                    embed = discord.Embed(
                            title="Ideology",
                            description=f"Please **enter** your desired ideology:\n",
                            color=0x00FF00,
                        )
                    embed.set_image(url=appearance_url)
                    embed.add_field(name="Invalid Ideology",
                                    value="That ideology is already taken, try again.",
                                    inline=False)
                    await message.clear_reactions()
                    await message.edit(embed=embed)
                    continue

                if not re.match(r'^[A-Za-z0-9\s]+$', ideology) or len(ideology) > 24:
                    embed = discord.Embed(
                            title="Ideology",
                            description=f"Please **enter** your desired ideology:\n",
                            color=0x00FF00,
                        )
                    embed.set_image(url=appearance_url)
                    embed.add_field(name="Invalid Ideology",
                                    value="That name is not valid, try again.",
                                    inline=False)
                    await message.clear_reactions()
                    await message.edit(embed=embed)
                    continue

                confirm_msg=f"Are you sure {name} follows **{ideology}**?"
                embed.add_field(name="Confirm", value=confirm_msg, inline=False)
                await message.edit(embed=embed)

                reactions = ["✅", "❌"]
                await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

                def confirmation_check(reaction, user):
                    return (user == interaction.user and 
                            reaction.message.id == message.id and
                              str(reaction.emoji) in ["✅", "❌"])
                
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', 
                                                             timeout=60.0, 
                                                             check=confirmation_check)

                    if str(reaction.emoji) == "✅":
                        await message.clear_reactions()
                        if ideology in ideologies:
                            followers = await self.bot.database.fetch_followers(ideology)
                            follow_text = (f"{name} has adopted **{ideology}**! Followers: {followers + 1}\n"
                                               f"{name} is now registered.")
                            embed.add_field(name="Follower", value=follow_text, inline=True)
                            await message.edit(embed=embed)
                            await self.bot.database.update_followers_count(ideology, followers + 1)
                            self.bot.state_manager.clear_active(user_id)
                        else:
                            await self.bot.database.create_ideology(user_id, server_id, ideology)
                            await self.bot.database.update_followers_count(ideology, 1)
                            founder_text = (f"Congratulations, {name} has founded a new ideology called **{ideology}**!\n"
                                               f"{name} is now registered.")
                            embed.add_field(name="Founder", value=founder_text, inline=True)
                            await message.edit(embed=embed)
                            self.bot.state_manager.clear_active(user_id)  
                        success = True
                        break

                    elif str(reaction.emoji) == "❌":
                        embed = discord.Embed(
                            title="Ideology",
                            description=f"Please **enter** your desired ideology:\n",
                            color=0x00FF00,
                        )
                        embed.set_image(url=appearance_url)
                        await message.edit(embed=embed)
                        await message.clear_reactions()
                        continue

                except asyncio.TimeoutError:
                    await message.delete()
                    self.bot.state_manager.clear_active(user_id)  
                    break

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(user_id)  
                break

        if (success):
            self.bot.state_manager.clear_active(user_id)
            await self.bot.database.users.register(user_id, server_id, name, selected_appearance, ideology)
            await self.bot.database.add_to_mining(user_id, server_id, 'iron')
            await self.bot.database.add_to_fishing(user_id, server_id, 'desiccated')
            await self.bot.database.add_to_woodcutting(user_id, server_id, 'flimsy')
            await self.bot.database.users.modify_gold(user_id, 200)
            await self.bot.database.users.modify_stat(user_id, 'potions', 10)
            self.bot.state_manager.clear_active(user_id)  
    

    @app_commands.command(name="unregister", description="Unregister as an adventurer.")
    async def unregister_adventurer(self, interaction: Interaction) -> None:
        """
        Unregisters the command sender as an adventurer.
        """
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        embed = discord.Embed(
            title="Confirm Unregistration",
            description=("Are you sure you want to unregister as an adventurer? "
                         "This action is **permanent**."),
            color=0xFFCC00
        )
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        reactions = ["✅", "❌"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

            if str(reaction.emoji) == "✅":
                user_ideology = existing_user[8]
                followers_count = await self.bot.database.fetch_followers(user_ideology)
                await self.bot.database.update_followers_count(user_ideology, followers_count - 1)
                await self.bot.database.users.unregister(user_id, server_id)
                embed = discord.Embed(
                    title="Retirement",
                    description="You have been successfully unregistered.",
                    color=0x00FF00,
                )
                await message.edit(embed=embed)
                await message.clear_reactions()
            else:
                embed = discord.Embed(
                    title="Good choice",
                    description="Your story doesn't end here.",
                    color=0x00FF00
                )
                await message.edit(embed=embed)
                await message.clear_reactions()

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(user_id)  
    

async def setup(bot) -> None:
    await bot.add_cog(Guild(bot))
