# cogs/companions.py

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.items.factory import create_companion
from core.companions.views import CompanionListView
from core.companions.logic import CompanionLogic

class Companions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    group = app_commands.Group(name="companions", description="Manage your companions")

    @group.command(name="list", description="View and manage your companions.")
    async def list_companions(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        
        # 1. Check State
        if not await self.bot.check_is_active(interaction, user_id): return
        
        # 2. Fetch Data
        rows = await self.bot.database.companions.get_all(user_id)
        if not rows:
            return await interaction.response.send_message("You have no companions yet.", ephemeral=True)
            
        companions = [create_companion(row) for row in rows]
        
        # 3. View
        self.bot.state_manager.set_active(user_id, "companions")
        view = CompanionListView(self.bot, user_id, companions)
        embed = view.get_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @group.command(name="collect", description="Quickly collect passive loot from active companions.")
    async def collect(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if not await self.bot.check_is_active(interaction, user_id): return
        
        # Defer because DB writes might take a moment
        await interaction.response.defer(ephemeral=True)
        
        # Call Logic
        result_msg = await CompanionLogic.collect_passive_rewards(self.bot, user_id, guild_id)
        
        await interaction.followup.send(result_msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Companions(bot))