import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.emojis import INNER_SANC
from core.inner_sanctum.data import VICE_UNLOCK_LEVEL
from core.inner_sanctum.views import InnerSanctumHubView


class InnerSanctum(commands.Cog, name="inner_sanctum"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="inner_sanctum",
        description="Open the Inner Sanctum — permanent combat mastery tree.",
    )
    async def inner_sanctum(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        player_level = existing_user["level"]
        if player_level < VICE_UNLOCK_LEVEL:
            embed = discord.Embed(
                title=f"{INNER_SANC} Inner Sanctum — Locked",
                description=(
                    f"The Inner Sanctum awakens at **level {VICE_UNLOCK_LEVEL}**.\n"
                    "Keep fighting — you'll feel it stir soon enough."
                ),
                color=discord.Color.dark_purple(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.bot.state_manager.set_active(user_id, "inner_sanctum")

        tree_data = await self.bot.database.inner_sanctum.get(user_id, server_id)
        all_currencies = await self.bot.database.users.get_all_currencies(user_id)
        rune_count = all_currencies.get("rune_of_regret", 0) if all_currencies else 0

        view = InnerSanctumHubView(
            self.bot, user_id, server_id, player_level, tree_data, rune_count
        )
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(InnerSanctum(bot))
