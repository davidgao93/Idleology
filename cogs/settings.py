import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.settings.views import DoorToggleView

class Settings(commands.Cog, name="settings"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="doors", description="Toggle random Boss Door encounters during combat.")
    async def doors(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        # Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        
        # Fetch status
        current_status = await self.bot.database.users.get_doors_enabled(user_id)
        
        # Launch View
        view = DoorToggleView(self.bot, user_id, current_status)
        
        # We send this as ephemeral because settings are private and shouldn't clutter the chat
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Settings(bot))