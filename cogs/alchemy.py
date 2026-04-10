import discord
from discord.ext import commands
from discord import app_commands, Interaction

from core.alchemy.mechanics import AlchemyMechanics
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

        # 2. Initialize alchemy row if this is a first visit; auto-roll slot 1 for free
        is_new = await self.bot.database.alchemy.initialize_if_new(user_id)
        welcome_msg = None
        if is_new:
            passive_type, passive_value = AlchemyMechanics.roll_passive(1)
            await self.bot.database.alchemy.set_passive(user_id, 1, passive_type, passive_value)
            info = AlchemyMechanics.PASSIVES.get(passive_type, {})
            welcome_msg = (
                f"✨ **Welcome to Alchemy!** You start at Level 1 with 1 passive slot.\n"
                f"**Slot 1** (free roll): {info.get('emoji', '⚗️')} **{info.get('name', passive_type)}** — "
                f"*{AlchemyMechanics.format_passive(passive_type, passive_value)}*"
            )

        # 3. Fetch alchemy state
        alchemy_level = await self.bot.database.alchemy.get_level(user_id)
        passives      = await self.bot.database.alchemy.get_potion_passives(user_id)
        gold          = existing_user[6]
        spirit_stones = existing_user[SPIRIT_STONES_COL]

        # 4. Open hub
        view  = AlchemyHubView(self.bot, user_id, server_id,
                               alchemy_level, passives, gold, spirit_stones)
        embed = view.build_embed()
        if welcome_msg:
            embed.title = "⚗️ Alchemy — First Visit!"
            embed.description = welcome_msg + "\n\n" + (embed.description or "")

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Alchemy(bot))
