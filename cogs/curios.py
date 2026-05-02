import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.curios.views import CurioView


class Curios(commands.Cog, name="curios"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="curios", description="Open your Curios and Curio Puzzle Boxes.")
    async def curios(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        curio_count = existing_user[22]
        puzzle_box_count = await self.bot.database.users.get_currency(user_id, "curio_puzzle_boxes")

        if curio_count <= 0 and puzzle_box_count <= 0:
            return await interaction.response.send_message("You don't have any Curios or Puzzle Boxes!", ephemeral=True)

        self.bot.state_manager.set_active(user_id, "curios")

        view = CurioView(self.bot, user_id, server_id, curio_count, puzzle_box_count)
        embed = view.build_hub_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Curios(bot))
