from discord import Interaction, app_commands
from discord.ext import commands

from core.alchemy.views import AlchemyHubView
from core.first_use import TutorialGateView


class Alchemy(commands.Cog, name="alchemy"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="alchemy",
        description="Open the Alchemy menu to transmute resources and manage potion passives.",
    )
    async def alchemy(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Basic guards
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "alchemy")

        try:
            # 2. Initialize alchemy row if this is a first visit
            is_new = await self.bot.database.alchemy.initialize_if_new(user_id)
            welcome_msg = None
            if is_new:
                welcome_msg = (
                    "✨ **Welcome to Alchemist's Guild!** You start at Level 1 with 1 passive slot.\n"
                    "Head to the **Potion Lab** to roll your first passive!"
                )

            # 3. Fetch alchemy state
            alchemy_level = await self.bot.database.alchemy.get_level(user_id)
            passives = await self.bot.database.alchemy.get_potion_passives(user_id)
            gold = existing_user["gold"]
            spirit_stones = await self.bot.database.users.get_currency(
                user_id, "spirit_stones"
            )
            cosmic_dust = await self.bot.database.alchemy.get_cosmic_dust(user_id)

            async def _build():
                view = AlchemyHubView(
                    self.bot,
                    user_id,
                    server_id,
                    alchemy_level,
                    passives,
                    gold,
                    spirit_stones,
                    cosmic_dust,
                )
                embed = view.build_embed()
                if welcome_msg:
                    embed.title = "⚗️ The Alchemy Guild"
                    embed.description = welcome_msg + "\n\n" + (embed.description or "")
                return embed, view

            if not await self.bot.database.tutorials.has_seen(user_id, "alchemy"):
                await self.bot.database.tutorials.mark_seen(user_id, "alchemy")
                gate = TutorialGateView(
                    self.bot, user_id, server_id, "alchemy", build_main=_build
                )
                await interaction.response.send_message(
                    embed=gate.build_embed(), view=gate
                )
                gate.message = await interaction.original_response()
                return

            embed, view = await _build()
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
        except Exception:
            self.bot.state_manager.clear_active(user_id)
            raise


async def setup(bot) -> None:
    await bot.add_cog(Alchemy(bot))
