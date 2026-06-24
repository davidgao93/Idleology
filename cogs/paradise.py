from discord import Interaction, app_commands
from discord.ext import commands

from core.first_use import TutorialGateView
from core.paradise.views import ParadiseHubView


class Paradise(commands.Cog, name="paradise"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="paradise",
        description="Manage your Jewel of Paradise and Skill Jewels.",
    )
    async def paradise(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if existing_user["level"] < 100:
            return await interaction.response.send_message(
                "The Jewel of Paradise awakens at level 100.", ephemeral=True
            )
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "paradise")

        async def _build():
            data = await self.bot.database.paradise.get(user_id)
            uber = await self.bot.database.uber.get_uber_progress(user_id, server_id)
            jewel_count = uber.get("paradise_jewels", 0)
            dust = await self.bot.database.alchemy.get_cosmic_dust(user_id)
            view = ParadiseHubView(
                self.bot, user_id, server_id, data, jewel_count, dust
            )
            return view.build_embed(), view

        if not await self.bot.database.tutorials.has_seen(user_id, "paradise"):
            await self.bot.database.tutorials.mark_seen(user_id, "paradise")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "paradise", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Paradise(bot))
