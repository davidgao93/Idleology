import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.items.factory import load_player
from core.character.views import RegistrationView
import json
from discord.ext.tasks import asyncio
from discord import app_commands, Interaction, Message

class Guild(commands.Cog, name="adventurer's guild"):
    def __init__(self, bot):
        self.bot = bot

    def load_exp_table(self):
        with open('assets/exp.json') as file:
            return json.load(file)

    @app_commands.command(name="card", description="See your adventurer card.")
    async def card(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data): return

        # Load Player Model for consistent stat calculation (optional, but good practice)
        player = await load_player(user_id, data, self.bot.database)
        
        exp_table = self.load_exp_table()
        exp_needed = exp_table["levels"].get(str(player.level), 0)
        pct = (player.exp / exp_needed * 100) if exp_needed > 0 else 100

        embed = discord.Embed(title=f"**{player.name}**", color=0x808080)
        
        lvl_str = f"{player.level}"
        if player.ascension > 0: lvl_str += f" (Ascension {player.ascension} 🌟)"
        
        embed.add_field(name="Level", value=lvl_str, inline=True)
        embed.add_field(name="EXP", value=f"{player.exp:,} ({pct:.1f}%)", inline=True)
        embed.add_field(name="Gold", value=f"{data[6]:,}", inline=True)
        embed.add_field(name="Ideology", value=data[8], inline=True)
        embed.set_thumbnail(url=data[7]) # Appearance

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="register", description="Start your journey.")
    async def register(self, interaction: Interaction, name: str):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if not await self.bot.check_is_active(interaction, user_id): return

        existing = await self.bot.database.users.get(user_id, server_id)
        if existing:
            return await interaction.response.send_message("You are already registered! Use `/card`.", ephemeral=True)

        self.bot.state_manager.set_active(user_id, "register")
        
        embed = discord.Embed(
            title="Character Creation",
            description=f"Welcome, **{name}**!\nPlease select your appearance.",
            color=0x00FF00
        )
        embed.set_image(url="https://i.imgur.com/6pRwl0k.jpeg") # Default silhouette
        
        view = RegistrationView(self.bot, user_id, name)
        await interaction.response.send_message(embed=embed, view=view)

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
                followers_count = await self.bot.database.social.get_follower_count(user_ideology)
                await self.bot.database.social.update_followers(user_ideology, followers_count - 1)
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

async def setup(bot):
    await bot.add_cog(Guild(bot))
