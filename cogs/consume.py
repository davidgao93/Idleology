from discord import Interaction, app_commands
from discord.ext import commands

from core.consume.views import ConsumeView
from core.first_use import TutorialGateView
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

        self.bot.state_manager.set_active(user_id, "consume")

        async def _build():
            player = await load_player(user_id, user_data, self.bot.database)
            inventory = await self.bot.database.monster_parts.get_inventory(user_id)
            eggs = await self.bot.database.eggs.get_eggs(user_id)
            view = ConsumeView(player, inventory, self.bot, eggs=eggs)
            return view.build_embed(), view

        if not await self.bot.database.tutorials.has_seen(user_id, "consume"):
            await self.bot.database.tutorials.mark_seen(user_id, "consume")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "consume", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="hematurgy",
        description="Manage your Hematurgy blood passives directly.",
    )
    async def hematurgy(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if user_data["level"] < 50:
            return await interaction.response.send_message(
                "You're not powerful enough for the Hematurgy system, come back at **Level 50**.",
                ephemeral=True,
            )

        self.bot.state_manager.set_active(user_id, "consume")

        async def _build():
            from core.hematurgy.views import HematurgyView, _build_hematurgy_embed

            passives = await self.bot.database.hematurgy.get_all_passives(user_id)
            blood = await self.bot.database.hematurgy.get_blood(user_id)
            view = HematurgyView(
                self.bot, passives, blood, user_id=user_id, server_id=server_id
            )
            return _build_hematurgy_embed(passives, blood), view

        if not await self.bot.database.tutorials.has_seen(user_id, "hematurgy"):
            await self.bot.database.tutorials.mark_seen(user_id, "hematurgy")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "hematurgy", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Consume(bot))
