from discord import Interaction, app_commands
from discord.ext import commands

from core.hall_of_firsts.views import HallOfFirstsListView


class HallOfFirsts(commands.Cog, name="hall_of_firsts"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="hallofirsts",
        description="View the Hall of Firsts — the first adventurers to claim each legend.",
    )
    async def hallofirsts(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild_id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "hall_of_firsts")

        view = HallOfFirstsListView(self.bot, user_id, server_id)
        await view.load()
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(HallOfFirsts(bot))
