from discord import Interaction, app_commands
from discord.ext import commands

from core.items.factory import load_player
from core.rite.views.wing_hub_view import WingHubView


class Rite(commands.Cog, name="rite"):
    """Milestone 2 scaffolding: a debug-only entry point into the Rite of
    Convergence's 5 wing fights. No key consumption, no attempts, no writs,
    no loot — see core/rite/views/wing_hub_view.py. Replaced by the real
    entry flow in Milestone 3.
    """

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="rite_debug",
        description="[DEBUG] Fight the Rite of Convergence's wing bosses directly.",
    )
    async def rite_debug(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        player = await load_player(user_id, existing_user, self.bot.database)
        view = WingHubView(self.bot, user_id, server_id, player)
        self.bot.state_manager.set_active(user_id, "rite")
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Rite(bot))
