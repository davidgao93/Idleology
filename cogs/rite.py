import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.first_use import TutorialGateView
from core.items.factory import load_player
from core.rite.data import RITE_KEY_FLAVOR, starting_attempts
from core.rite.run_state import RiteRunState
from core.rite.views.entry_view import RITE_KEY_COLUMNS as _RITE_KEY_COLUMNS
from core.rite.views.entry_view import RiteEntryView
from core.rite.views.wing_hub_view import WingHubView
from core.rite.views.writ_select_view import WritSelectView


class Rite(commands.Cog, name="rite"):
    """The Rite of Convergence — 5 wing fights, writs/Devotion Points, and
    the 6-phase Arbiter finale. See core/rite/views/wing_hub_view.py for the
    run loop and core/rite/views/arbiter_view.py for the finale.
    """

    def __init__(self, bot):
        self.bot = bot

    async def _begin_run(
        self,
        interaction: Interaction,
        user_id: str,
        server_id: str,
        player,
        writ_keys: list[str],
    ):
        """Checks + consumes the 5 entry keys atomically, creates a fresh run
        (with writ-driven starting attempts), and shows the wing hub. Shared
        by the writ-selection confirm/skip buttons and the no-writs-available
        fast path."""
        balances = {
            col: await self.bot.database.users.get_currency(user_id, col)
            for _, col, _emoji in _RITE_KEY_COLUMNS
        }
        missing = [name for name, col, _emoji in _RITE_KEY_COLUMNS if balances[col] < 1]
        if missing:
            self.bot.state_manager.clear_active(user_id)
            embed = discord.Embed(
                title="🕯️ The Rite of Convergence",
                description="You need all 5 Rite keys held simultaneously to enter.",
                color=discord.Color.dark_purple(),
            )
            for name, _col, emoji in _RITE_KEY_COLUMNS:
                source, blurb = RITE_KEY_FLAVOR[name]
                have = "✅" if name not in missing else "❌"
                embed.add_field(
                    name=f"{have} {emoji} {name}",
                    value=f"*{source}* — {blurb}",
                    inline=False,
                )
            # This branch is reached both from a deferred-with-no-content
            # interaction (fast path) AND from a button click on the
            # Components V2 WritSelectView (writ-confirm path). A classic
            # `embed=` response can't be edited onto an already-IS_COMPONENTS_V2
            # message (same class of error as the content/LayoutView bug this
            # cog just fixed), so wrap the embed as a LayoutView unconditionally
            # — safe for either caller.
            from core.combat import ui as combat_ui

            missing_view = discord.ui.LayoutView()
            missing_view.add_item(combat_ui.embed_to_container(embed))
            await interaction.edit_original_response(
                content=None, embed=None, view=missing_view
            )
            return

        async with self.bot.database.transaction():
            for _name, col, _emoji in _RITE_KEY_COLUMNS:
                ok = await self.bot.database.users.deduct_currency_atomic(
                    user_id, col, 1
                )
                if not ok:
                    raise RuntimeError(
                        f"Rite key balance changed mid-transaction for {user_id} ({col})"
                    )

        start_attempts = starting_attempts(writ_keys)
        run_state = RiteRunState(
            attempts_remaining=start_attempts,
            max_attempts=start_attempts,
            writs=writ_keys,
        )
        await self.bot.database.rite.upsert_run(
            user_id, server_id, run_state.to_snapshot()
        )

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

        # No save/resume — RiteExitConfirmView forfeits the run on any
        # deliberate exit. A leftover row can only come from a hard crash
        # mid-run; discard it rather than silently resuming stale state.
        if await self.bot.database.rite.get_run(user_id, server_id):
            await self.bot.database.rite.delete_run(user_id, server_id)

        has_first_clear = await self.bot.database.rite.has_first_clear(
            user_id, server_id
        )

        async def _on_entry_confirmed(inner_interaction: Interaction):
            if has_first_clear:

                async def _on_writs_confirmed(
                    writ_interaction: Interaction, writ_keys: list[str]
                ):
                    await self._begin_run(
                        writ_interaction, user_id, server_id, player, writ_keys
                    )

                writ_view = WritSelectView(
                    self.bot, user_id, server_id, player, _on_writs_confirmed
                )
                await inner_interaction.edit_original_response(
                    embed=None, view=writ_view
                )
                writ_view.message = await inner_interaction.original_response()
                return

            # First-ever run: writs are locked, skip straight to entry.
            await self._begin_run(inner_interaction, user_id, server_id, player, [])

        balances = {
            col: await self.bot.database.users.get_currency(user_id, col)
            for _, col, _emoji in _RITE_KEY_COLUMNS
        }

        async def _build():
            entry_view = RiteEntryView(
                self.bot, user_id, server_id, balances, _on_entry_confirmed
            )
            return None, entry_view

        if not await self.bot.database.tutorials.has_seen(user_id, "rite"):
            await self.bot.database.tutorials.mark_seen(user_id, "rite")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "rite", build_main=_build
            )
            self.bot.state_manager.set_active(user_id, "rite")
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        _, entry_view = await _build()
        self.bot.state_manager.set_active(user_id, "rite")
        await interaction.response.send_message(view=entry_view)
        entry_view.message = await interaction.original_response()

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
        name, source, req_dp, _weight, image = ARTEFACT_TABLE[key]
        embed = discord.Embed(
            title=f"🏺 {name}",
            description=(
                f"*Thematic source: {source}*\n\n"
                f"{describe_artefact(key, row['roll_1'])}"
            ),
            color=discord.Color.dark_gold(),
        )
        embed.set_thumbnail(url=image)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Rite(bot))
