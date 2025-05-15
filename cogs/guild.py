import discord
import re
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.tasks import asyncio
import csv

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

    @commands.hybrid_command(name="card", description="See your adventurer card.")
    async def card(
        self, context: Context
    ) -> None:
        """
        Returns info about the sender's adventurer.
        """
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if existing_user:
            embed = discord.Embed(
                title="User Info",
                description=f"You are registered as **{existing_user[3]}**.",
                color=0x808080,
            )
            embed.add_field(name="Level", value=existing_user[4], inline=True)
            embed.add_field(name="Experience", value=existing_user[5], inline=True)
            embed.add_field(name="Gold", value=existing_user[6], inline=True)
            embed.set_image(url=existing_user[7])
            embed.add_field(name="Ideology", value=existing_user[8], inline=True)
            await context.send(embed=embed)
        else:
            embed = discord.Embed(
                title="What isn't there cannot be found",
                description="You are not registered with the 🏦 Adventurer's Guild, you can do so with /register.",
                color=0xFF0000,
            )
            await context.send(embed=embed)

    @commands.hybrid_command(name="register", description="Register as an adventurer.")
    async def register_adventurer(
        self, context: Context, name: str
    ) -> None:
        """
        Registers the command sender as an adventurer with the specified name.

        :param context: The hybrid command context.
        :param name: The name of the adventurer.
        """
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)

        if self.bot.state_manager.is_active(user_id):
            await context.send("You are currently busy with another operation. Please finish that first.")
            return

        if existing_user:
            embed = discord.Embed(
                title="Registration",
                description=(f"You are already registered as **{existing_user[3]}**!"
                             f" Use /card to see your Guild card."),
                color=0x808080,
            )
            await context.send(embed=embed)
            return
        
        self.bot.state_manager.set_active(user_id, "register")  # Set register as active operation
        # Ask for gender selection
        embed = discord.Embed(
            title="What are you?",
            description="Pick a gender:",
            color=0x00FF00,
        )
        message = await context.send(embed=embed)
        reactions = ["♂️", "♀️"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def gender_check(reaction, user):
            return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in reactions

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=gender_check)
            gender = "M" if str(reaction.emoji) == "♂️" else "F"

        except asyncio.TimeoutError:
            await context.send(f"{name} took too long to respond!")
            self.bot.state_manager.clear_active(user_id)  
            return

        # Load appearances based on gender
        appearances = self.load_character_appearances(gender)
        if not appearances:
            await context.send("No appearances found, please try again later.")
            self.bot.state_manager.clear_active(user_id)
            return
        
        current_index = 0

        async def update_embed(message, index):
            embed.set_image(url=appearances[index])
            await message.edit(embed=embed)

        message = await context.send(embed=embed)
        await update_embed(message, current_index)
        reactions = ["⬅️", "➡️", "✅"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def check(reaction, user):
            return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["⬅️", "➡️", "✅"]

        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                if str(reaction.emoji) == "⬅️":  # Left arrow
                    current_index = (current_index - 1) % len(appearances)
                elif str(reaction.emoji) == "➡️":  # Right arrow
                    current_index = (current_index + 1) % len(appearances)
                elif str(reaction.emoji) == "✅":  # Confirm selection
                    break
                await update_embed(message, current_index)
                await message.remove_reaction(reaction.emoji, user)

            except asyncio.TimeoutError:
                await context.send(f"{name} took too long to respond!")
                self.bot.state_manager.clear_active(user_id)  
                return
            
        selected_appearance = f"{appearances[current_index]}"
        ideologies = await self.bot.database.fetch_ideologies(server_id)
        ideology_str = ""
        for ideology in ideologies:
            ideology_str += ('💡' + ideology + '\n')

        if ideology_str:
            embed_description = (
                "Appearance confirmed. Please enter your school's ideology from the list below:\n"
                f"{ideology_str}"
                "Or type a new ideology name to create one."
            )
        else:
            embed_description = (
                "Appearance confirmed. No ideologies are available.\n"
                "Please type a new ideology name to create one."
            )            

        embed = discord.Embed(
            title=f"Choose {name}'s Ideology",
            description=embed_description,
            color=0x00FF00,
        )
        await context.send(embed=embed)
        while True:
            def ideology_check(m):
                return m.author == context.author and m.channel == context.channel

            try:
                ideology_message = await self.bot.wait_for('message', timeout=60.0, check=ideology_check)
                ideology = ideology_message.content.strip()

                if not re.match(r'^[A-Za-z0-9\s]+$', ideology) or len(ideology) > 24:
                    await context.send("Invalid input. Please enter an alphanumeric ideology with spaces (max 24 characters).")
                    continue

                confirmation_embed = discord.Embed(
                    title=f"Confirm {name}'s Ideology",
                    description=f"Are you sure {name} follows **{ideology}**? Note that Ideologies are **CASE SENSITIVE!**",
                    color=0xFFCC00
                )
                message = await context.send(embed=confirmation_embed)

                reactions = ["✅", "❌"]
                await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

                def confirmation_check(reaction, user):
                    return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]
                
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirmation_check)

                    if str(reaction.emoji) == "✅":
                        if ideology in ideologies:
                            followers = await self.bot.database.fetch_followers(ideology)
                            await context.send(f"{name} has adopted **{ideology}**! Followers: {followers + 1}\n"
                                               "You are now registered.")
                            await self.bot.database.update_followers_count(ideology, followers + 1)
                            self.bot.state_manager.clear_active(user_id)  
                        else:
                            await self.bot.database.create_ideology(user_id, server_id, ideology)
                            await self.bot.database.update_followers_count(ideology, 1)
                            await context.send(f"Congratulations, {name} has founded a new ideology called **{ideology}**!\n"
                                               "You are now registered.")
                            self.bot.state_manager.clear_active(user_id)  
                        break

                    elif str(reaction.emoji) == "❌":
                        await context.send("Please enter a new ideology name.")
                        continue

                except asyncio.TimeoutError:
                    await context.send(f"{name} took too long, the confirmation has been cancelled.")
                    self.bot.state_manager.clear_active(user_id)  
                    break

            except asyncio.TimeoutError:
                await context.send(f"{name} took too long, the registration has been cancelled.")
                self.bot.state_manager.clear_active(user_id)  
                break

        self.bot.state_manager.clear_active(user_id)
        await self.bot.database.register_user(user_id, server_id, name, selected_appearance, ideology)
        await self.bot.database.add_to_mining(user_id, server_id, 'iron')
        await self.bot.database.add_to_fishing(user_id, server_id, 'desiccated')
        await self.bot.database.add_to_woodcutting(user_id, server_id, 'flimsy')
        await self.bot.database.add_gold(user_id, 200)
        for _ in range (0, 10):
            await self.bot.database.increase_potion_count(user_id)
        self.bot.state_manager.clear_active(user_id)  
    
    @commands.hybrid_command(name="unregister", description="Unregister as an adventurer.")
    async def unregister_adventurer(self, context: commands.Context) -> None:
        """
        Unregisters the command sender as an adventurer.
        """
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            embed = discord.Embed(
                title="What isn't there cannot be found",
                description="You are not registered with the 🏦 Adventurer's Guild, you can do so with /register.",
                color=0xFF0000,
            )
            await context.send(embed=embed)
            return

        embed = discord.Embed(
            title="Confirm Unregistration",
            description=("Are you sure you want to unregister as an adventurer? "
                         "This action is **permanent**."),
            color=0xFFCC00
        )
        message = await context.send(embed=embed)
        reactions = ["✅", "❌"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def check(reaction, user):
            return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

            if str(reaction.emoji) == "✅":
                user_ideology = existing_user[8]
                followers_count = await self.bot.database.fetch_followers(user_ideology)
                await self.bot.database.update_followers_count(user_ideology, followers_count - 1)
                await self.bot.database.unregister_user(user_id, server_id)
                success_embed = discord.Embed(
                    title="Retirement",
                    description="You have been successfully unregistered.",
                    color=0x00FF00,
                )
                await context.send(embed=success_embed)
            else:
                cancel_embed = discord.Embed(
                    title="Good choice",
                    description="Your story doesn't end here.",
                    color=0x00FF00
                )
                await context.send(embed=cancel_embed)

        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="Unregistration Timeout",
                description="You took too long to respond! Your retirement has been cancelled.",
                color=0xFF0000
            )
            await context.send(embed=timeout_embed)
    

async def setup(bot) -> None:
    await bot.add_cog(Guild(bot))
