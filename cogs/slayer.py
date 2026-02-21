import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.slayer.views import SlayerDashboardView

class Slayer(commands.Cog, name="slayer"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="slayer", description="Open the Slayer management interface.")
    async def slayer(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Standard Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        # 2. State Lock
        self.bot.state_manager.set_active(user_id, "slayer")

        # 3. Fetch Slayer Data
        profile = await self.bot.database.slayer.get_profile(user_id, server_id)
        player_level = existing_user[4] # We need player level to generate appropriate tasks

        # 4. Launch Dashboard View
        view = SlayerDashboardView(self.bot, user_id, server_id, profile, player_level)
        embed = view.build_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Slayer(bot))