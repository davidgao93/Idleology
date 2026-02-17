# cogs/companions.py

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.items.factory import create_companion
from core.companions.views import CompanionListView
from core.companions.logic import CompanionLogic
from core.companions.fusion_views import FusionWizardView

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
        embed.set_thumbnail(url="https://i.imgur.com/oQBm9HF.png")
        
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

    @group.command(name="fusion", description="Merge two companions into one.")
    async def fusion(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        
        # 1. State Check
        if not await self.bot.check_is_active(interaction, user_id): return

        # 2. Pre-Check Gold
        gold = await self.bot.database.users.get_gold(user_id)
        if gold < 50000:
            return await interaction.response.send_message("Fusion costs **50,000 Gold**. You cannot afford it.", ephemeral=True)

        # 3. Pre-Check Pet Count
        rows = await self.bot.database.companions.get_all(user_id)
        if len(rows) < 2:
            return await interaction.response.send_message("You need at least **2** companions to perform fusion.", ephemeral=True)

        # 4. Launch View
        self.bot.state_manager.set_active(user_id, "fusion")
        companions = [create_companion(row) for row in rows]
        
        view = FusionWizardView(self.bot, user_id, companions)
        embed = discord.Embed(
            title="🧬 Companion Fusion", 
            description="Combine two companions to merge their XP and randomize their traits.\n\n**Cost:** 50,000 Gold\nSelect your **Primary** companion below.",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Companions(bot))