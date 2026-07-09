import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.items.factory import load_player
from core.rite.run_state import RiteRunState
from core.rite.views.wing_hub_view import WingHubView

_RITE_KEY_COLUMNS = [
    ("Apex of Dreams", "rite_key_apex_of_dreams"),
    ("Corruption of Memories", "rite_key_corruption_of_memories"),
    ("Scales of Judgment", "rite_key_scales_of_judgment"),
    ("Devoid of Thoughts", "rite_key_devoid_of_thoughts"),
    ("Zenith of Nightmares", "rite_key_zenith_of_nightmares"),
]


class Rite(commands.Cog, name="rite"):
    """The Rite of Convergence. Writs/Devotion Points (Milestone 4) and the
    Arbiter finale (Milestone 5) are not built yet — see wing_hub_view.py.
    """

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="rite",
        description="Enter The Rite of Convergence — the ultimate endgame raid.",
    )
    async def rite(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        player = await load_player(user_id, existing_user, self.bot.database)

        saved_run = await self.bot.database.rite.get_run(user_id, server_id)
        if saved_run:
            run_state = RiteRunState.from_snapshot(saved_run)
        else:
            balances = {
                col: await self.bot.database.users.get_currency(user_id, col)
                for _, col in _RITE_KEY_COLUMNS
            }
            missing = [name for name, col in _RITE_KEY_COLUMNS if balances[col] < 1]
            if missing:
                return await interaction.response.send_message(
                    "You need all 5 Rite keys to enter, held simultaneously:\n"
                    + "\n".join(f"- {name}" for name in missing)
                    + "\n\nMissing the above.",
                    ephemeral=True,
                )

            async with self.bot.database.transaction():
                for _name, col in _RITE_KEY_COLUMNS:
                    ok = await self.bot.database.users.deduct_currency_atomic(
                        user_id, col, 1
                    )
                    if not ok:
                        raise RuntimeError(
                            f"Rite key balance changed mid-transaction for {user_id} ({col})"
                        )

            run_state = RiteRunState()
            await self.bot.database.rite.upsert_run(
                user_id, server_id, run_state.to_snapshot()
            )

        view = WingHubView(self.bot, user_id, server_id, player, run_state)
        self.bot.state_manager.set_active(user_id, "rite")
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="rite_debug",
        description="[DEBUG] Start a fresh Rite run without consuming keys.",
    )
    async def rite_debug(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        player = await load_player(user_id, existing_user, self.bot.database)

        run_state = RiteRunState()
        await self.bot.database.rite.upsert_run(
            user_id, server_id, run_state.to_snapshot()
        )

        view = WingHubView(self.bot, user_id, server_id, player, run_state)
        self.bot.state_manager.set_active(user_id, "rite")
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Rite(bot))
