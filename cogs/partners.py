from discord import Interaction, app_commands
from discord.ext import commands

from core.first_use import TutorialGateView
from core.partners.views import PartnerMainView


class Partners(commands.Cog, name="partners"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="partner", description="Manage your partners.")
    async def partner(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if user_data["level"] < 10:
            await interaction.response.send_message(
                "The Partner Guild only opens its doors to adventurers who have reached **Level 10**.",
                ephemeral=True,
            )
            return

        self.bot.state_manager.set_active(user_id, "partners")

        await self.bot.database.partners.ensure_items_row(user_id)

        async def _build():
            view = PartnerMainView(self.bot, user_id)
            embed, _items, _partners = await view._fetch_fresh_data()
            return embed, view

        if not await self.bot.database.tutorials.has_seen(user_id, "partner"):
            await self.bot.database.tutorials.mark_seen(user_id, "partner")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "partner", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Partners(bot))
