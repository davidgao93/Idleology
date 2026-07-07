from discord import Interaction, app_commands
from discord.ext import commands

from core.combat.views.views_uber import UberHubView
from core.first_use import TutorialGateView
from core.items.factory import load_player


class Uber(commands.Cog, name="uber"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="uber", description="Challenge the pinnacle of power.")
    async def uber(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return
        if existing_user["level"] < 70:
            return await interaction.response.send_message(
                "You must be **Level 70** to access the Uber Encounters.",
                ephemeral=True,
            )

        async def _build():
            player = await load_player(user_id, existing_user, self.bot.database)
            uber_data = await self.bot.database.uber.get_uber_progress(
                user_id, server_id
            )
            view = UberHubView(self.bot, user_id, server_id, player, uber_data)
            return view.build_embed(), view

        if not await self.bot.database.tutorials.has_seen(user_id, "uber"):
            await self.bot.database.tutorials.mark_seen(user_id, "uber")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "uber", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        _, view = await _build()
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Uber(bot))
