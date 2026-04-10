import discord
from discord.ext import commands
from discord import app_commands, Interaction

from core.alchemy.views import AlchemyHubView, SPIRIT_STONES_COL


class Alchemy(commands.Cog, name="alchemy"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="alchemy", description="Open the Alchemy menu to transmute resources and manage potion passives.")
    async def alchemy(self, interaction: Interaction):
        user_id   = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Basic guards
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # 2. Fetch alchemy state
        alchemy_level = await self.bot.database.alchemy.get_level(user_id)
        passives      = await self.bot.database.alchemy.get_potion_passives(user_id)
        gold          = existing_user[6]
        spirit_stones = existing_user[SPIRIT_STONES_COL]

        # 3. Open hub (non-blocking — no state_manager lock needed for a menu)
        view  = AlchemyHubView(self.bot, user_id, server_id,
                               alchemy_level, passives, gold, spirit_stones)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Alchemy(bot))
