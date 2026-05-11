from discord import Interaction, app_commands
from discord.ext import commands

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
        self.bot.state_manager.set_active(user_id, "paradise")
        data = await self.bot.database.paradise.get(user_id)
        uber = await self.bot.database.uber.get_uber_progress(user_id, server_id)
        jewel_count = uber.get("paradise_jewels", 0)
        dust = await self.bot.database.alchemy.get_cosmic_dust(user_id)

        view = ParadiseHubView(self.bot, user_id, server_id, data, jewel_count, dust)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Paradise(bot))
