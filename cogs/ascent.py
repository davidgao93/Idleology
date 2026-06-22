from discord import Interaction, app_commands
from discord.ext import commands

from core.ascent.views import AscentLobbyView
from core.first_use import TutorialGateView
from core.items.factory import load_player


class Ascent(commands.Cog, name="ascent"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="ascent", description="Begin your ascent (Lvl 100+).")
    async def ascent(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validate
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if existing_user["level"] < 100:
            await interaction.response.send_message(
                "Come back at level 100.", ephemeral=True
            )
            return

        self.bot.state_manager.set_active(user_id, "ascent")

        # 2. Get user info and start lobby
        pinnacle_keys = await self.bot.database.users.get_currency(
            user_id, "pinnacle_key"
        )

        player = await load_player(user_id, existing_user, self.bot.database)
        best_floor = await self.bot.database.ascension.get_highest_floor(user_id)

        async def _build():
            _view = AscentLobbyView(
                self.bot, user_id, server_id, player, best_floor, pinnacle_keys
            )
            return _view.build_embed(), _view

        if not await self.bot.database.tutorials.has_seen(user_id, "ascent"):
            await self.bot.database.tutorials.mark_seen(user_id, "ascent")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "ascent", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Ascent(bot))
