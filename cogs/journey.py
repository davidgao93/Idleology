from discord import Interaction, app_commands
from discord.ext import commands

from core.journey.views import JourneyView, build_journey_embed


class Journey(commands.Cog, name="journey"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="journey",
        description="View your progression milestones and claim level-up rewards.",
    )
    async def journey(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild_id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return
        self.bot.state_manager.set_active(user_id, "journey")
        player_level = existing_user["level"]
        claimed = await self.bot.database.journey.get_claimed(user_id)

        view = JourneyView(self.bot, user_id, server_id, player_level, claimed)
        embed = build_journey_embed(player_level, claimed)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Journey(bot))
