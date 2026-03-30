import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.items.factory import load_player
from core.combat.views_uber import UberHubView


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

        player = await load_player(user_id, existing_user, self.bot.database)
        uber_data = await self.bot.database.uber.get_uber_progress(user_id, server_id)

        view = UberHubView(self.bot, user_id, server_id, player, uber_data)
        embed = view.build_embed()

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Uber(bot))
