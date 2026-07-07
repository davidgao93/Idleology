# cogs/companions.py

from discord import Interaction, app_commands
from discord.ext import commands

from core.companions.views import CompanionListView
from core.first_use import TutorialGateView
from core.images import COMPANIONS_HUB
from core.items.factory import create_companion


class Companions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="companions", description="View and manage your companions (pets)."
    )
    async def companions(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild_id)

        # 1. Standard validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if existing_user["level"] < 40:
            await interaction.response.send_message(
                "Companions reveal themselves only to adventurers who have reached **Level 40**.",
                ephemeral=True,
            )
            return

        self.bot.state_manager.set_active(user_id, "companions")

        async def _build():
            rows = await self.bot.database.companions.get_all(user_id)
            companions = [create_companion(row) for row in rows] if rows else []
            pending_cookies = await self.bot.database.users.get_currency(
                user_id, "companion_pet_xp"
            )
            last_collect_time = (
                await self.bot.database.users.get_companion_collect_time(user_id)
            )
            view = CompanionListView(
                self.bot,
                user_id,
                companions,
                server_id=server_id,
                pending_cookies=pending_cookies,
                last_collect_time=last_collect_time,
            )
            embed = view.get_embed()
            embed.set_thumbnail(url=COMPANIONS_HUB)
            return embed, view

        # No companions yet is fine — show the tutorial (or empty roster) regardless.
        rows_check = await self.bot.database.companions.get_all(user_id)
        if not rows_check:
            # Still show the tutorial if first visit, but use an informational embed instead.
            if not await self.bot.database.tutorials.has_seen(user_id, "companions"):
                await self.bot.database.tutorials.mark_seen(user_id, "companions")
                gate = TutorialGateView(
                    self.bot, user_id, server_id, "companions", build_main=_build
                )
                await interaction.response.send_message(
                    embed=gate.build_embed(), view=gate
                )
                gate.message = await interaction.original_response()
                return
            self.bot.state_manager.clear_active(user_id)
            return await interaction.response.send_message(
                "You have no companions yet. Defeat monsters in combat after level 40 to tame them!",
                ephemeral=True,
            )

        if not await self.bot.database.tutorials.has_seen(user_id, "companions"):
            await self.bot.database.tutorials.mark_seen(user_id, "companions")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "companions", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Companions(bot))
