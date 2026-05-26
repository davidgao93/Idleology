from discord import Interaction, app_commands
from discord.ext import commands

from core.quests.views import QuestBoardView


class Quests(commands.Cog, name="quests"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quests", description="View your quest board and horizon path.")
    async def quests(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return
        self.bot.state_manager.set_active(user_id, "quests")
        await self.bot.database.quests.ensure_meta(user_id)
        view = QuestBoardView(self.bot, user_id, server_id)
        await view.load()
        view._build_view_components()
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Quests(bot))
