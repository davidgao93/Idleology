# cogs/companions.py

from discord.ext import commands
from discord import app_commands, Interaction

from core.companions.views import CompanionListView
from core.images import COMPANIONS_HUB
from core.items.factory import create_companion

class Companions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="companions", description="View and manage your companions.")
    async def companions(self, interaction: Interaction):
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
        embed.set_thumbnail(url=COMPANIONS_HUB)

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Companions(bot))