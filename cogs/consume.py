import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.consume.views import ConsumeView
from core.items.factory import load_player


class Consume(commands.Cog, name="consume"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="consume",
        description="Manage your monster body parts to increase Max HP.",
    )
    async def consume(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        player = await load_player(user_id, user_data, self.bot.database)
        inventory = await self.bot.database.monster_parts.get_inventory(user_id)

        self.bot.state_manager.set_active(user_id, "consume")
        view = ConsumeView(player, inventory, self.bot)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Consume(bot))
