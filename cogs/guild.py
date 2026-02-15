import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.items.factory import load_player
from core.character.views import RegistrationView, UnregisterView
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
        view.message = await interaction.original_response()

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
        if not await self.bot.check_is_active(interaction, user_id): return

        # 2. State Lock
        self.bot.state_manager.set_active(user_id, "unregister")
        embed = discord.Embed(
            title="Confirm Unregistration",
            description=("Are you sure you want to unregister as an adventurer? \n"
                         "**This action is permanent and deletes all progress.**"),
            color=0xFFCC00
        )        # 3. View Instantiation
        view = UnregisterView(self.bot, user_id, existing_user[8]) # existing_user[8] is ideology
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Guild(bot))
