import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.settings.views import SettingsView

class Settings(commands.Cog, name="settings"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="Manage your personal game settings.")
    async def settings(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return

        doors_status = await self.bot.database.users.get_doors_enabled(user_id)
        exp_protection = await self.bot.database.users.get_exp_protection(user_id)

        view = SettingsView(self.bot, user_id, doors_status, exp_protection)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Settings(bot))
