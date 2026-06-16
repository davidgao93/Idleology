import asyncio

from discord import Interaction, app_commands
from discord.ext import commands

from core.first_use import TutorialGateView
from core.slayer.views import SlayerDashboardView


class Slayer(commands.Cog, name="slayer"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="slayer", description="Open the Slayer management interface."
    )
    async def slayer(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "slayer")

        async def _build():
            profile, tree_data = await asyncio.gather(
                self.bot.database.slayer.get_profile(user_id, server_id),
                self.bot.database.slayer.get_tree(user_id, server_id),
            )
            view = SlayerDashboardView(
                self.bot, user_id, server_id, profile, existing_user[4], tree_data
            )
            return view.build_embed(), view

        if not await self.bot.database.tutorials.has_seen(user_id, "slayer"):
            await self.bot.database.tutorials.mark_seen(user_id, "slayer")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "slayer", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Slayer(bot))
