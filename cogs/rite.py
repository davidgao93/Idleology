import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.items.factory import load_player
from core.rite.data import starting_attempts
from core.rite.run_state import RiteRunState
from core.rite.views.wing_hub_view import WingHubView
from core.rite.views.writ_select_view import WritSelectView

_RITE_KEY_COLUMNS = [
    ("Apex of Dreams", "rite_key_apex_of_dreams"),
    ("Corruption of Memories", "rite_key_corruption_of_memories"),
    ("Scales of Judgment", "rite_key_scales_of_judgment"),
    ("Devoid of Thoughts", "rite_key_devoid_of_thoughts"),
    ("Zenith of Nightmares", "rite_key_zenith_of_nightmares"),
]


class Rite(commands.Cog, name="rite"):
    """The Rite of Convergence. The Arbiter finale (Milestone 5) is not
    built yet — see wing_hub_view.py.
    """

    def __init__(self, bot):
        self.bot = bot

    async def _begin_run(
        self, interaction: Interaction, user_id: str, server_id: str, player, writ_keys: list[str]
    ):
        """Checks + consumes the 5 entry keys atomically, creates a fresh run
        (with writ-driven starting attempts), and shows the wing hub. Shared
        by the writ-selection confirm/skip buttons and the no-writs-available
        fast path."""
        balances = {
            col: await self.bot.database.users.get_currency(user_id, col)
            for _, col in _RITE_KEY_COLUMNS
        }
        missing = [name for name, col in _RITE_KEY_COLUMNS if balances[col] < 1]
        if missing:
            self.bot.state_manager.clear_active(user_id)
            await interaction.edit_original_response(
                content=(
                    "You need all 5 Rite keys to enter, held simultaneously:\n"
                    + "\n".join(f"- {name}" for name in missing)
                    + "\n\nMissing the above."
                ),
                embed=None,
                view=None,
            )
            return

        async with self.bot.database.transaction():
            for _name, col in _RITE_KEY_COLUMNS:
                ok = await self.bot.database.users.deduct_currency_atomic(user_id, col, 1)
                if not ok:
                    raise RuntimeError(
                        f"Rite key balance changed mid-transaction for {user_id} ({col})"
                    )

        run_state = RiteRunState(
            attempts_remaining=starting_attempts(writ_keys), writs=writ_keys
        )
        await self.bot.database.rite.upsert_run(user_id, server_id, run_state.to_snapshot())

        view = WingHubView(self.bot, user_id, server_id, player, run_state)
        self.bot.state_manager.set_active(user_id, "rite")
        await interaction.edit_original_response(embed=None, view=view)
        view.message = await interaction.original_response()

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
            view = WingHubView(self.bot, user_id, server_id, player, run_state)
            self.bot.state_manager.set_active(user_id, "rite")
            await interaction.response.send_message(view=view)
            view.message = await interaction.original_response()
            return

        has_first_clear = await self.bot.database.rite.has_first_clear(user_id, server_id)
        if has_first_clear:
            async def _on_writs_confirmed(inner_interaction: Interaction, writ_keys: list[str]):
                await self._begin_run(inner_interaction, user_id, server_id, player, writ_keys)

            view = WritSelectView(self.bot, user_id, server_id, player, _on_writs_confirmed)
            self.bot.state_manager.set_active(user_id, "rite")
            await interaction.response.send_message(view=view)
            view.message = await interaction.original_response()
            return

        # First-ever run: writs are locked, skip straight to entry.
        await interaction.response.send_message(
            "Consuming your 5 Rite keys...", ephemeral=False
        )
        self.bot.state_manager.set_active(user_id, "rite")
        await self._begin_run(interaction, user_id, server_id, player, [])

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

    @app_commands.command(
        name="artefact",
        description="View your equipped Rite of Convergence Artefact.",
    )
    async def artefact(self, interaction: Interaction):
        from core.rite.loot import ARTEFACT_TABLE, describe_artefact

        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        row = await self.bot.database.rite.get_artefact(user_id, server_id)
        if not row or not row["artefact_key"]:
            return await interaction.response.send_message(
                "You haven't found an Artefact yet — they only drop from a "
                "completed Rite of Convergence run.",
                ephemeral=True,
            )

        key = row["artefact_key"]
        name, source, req_dp, _weight = ARTEFACT_TABLE[key]
        embed = discord.Embed(
            title=f"🏺 {name}",
            description=(
                f"*Thematic source: {source}*\n\n"
                f"{describe_artefact(key, row['roll_1'])}"
            ),
            color=discord.Color.dark_gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Rite(bot))
