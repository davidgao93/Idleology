"""The fifth-wing reveal — a two-screen narrative beat between clearing the
final wing and the Arbiter's 6-phase finale. Per RAID-DESIGN.md, the Arbiter
was the guide all along; this plays out as two explicit, button-gated
screens (previously a single embed on a timed auto-advance, too fast to
actually register):

Screen 1 (ArbiterMaterializesView) — the Arbiter congratulates the player,
then something feels wrong. [Proceed]
Screen 2 (ArbiterConfrontView) — the Arbiter vanishes from the player's
side; its voice now speaks from within the converging essences.
[Fight the Amalgam]

Re-entry after a flee/death during the Arbiter fight skips both screens —
see WingHubView's "Challenge the Arbiter" button, which calls
arbiter_view.enter_arbiter_fight() directly.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.images import ARBITER_PORTRAIT, ARBITER_THUMBNAIL
from core.npc_voices import get_quip
from core.rite.run_state import RiteRunState


class ArbiterProceedRow(discord.ui.ActionRow["ArbiterMaterializesView"]):
    @discord.ui.button(label="Proceed", style=ButtonStyle.primary, emoji="➡️")
    async def proceed(self, interaction: Interaction, button: ui.Button):
        await self.view._on_proceed(interaction)


class ArbiterMaterializesView(BaseLayoutView):
    """Screen 1: the guide congratulates the player, then something feels
    wrong. Shown once, immediately after the 5th wing falls."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player,
        run_state: RiteRunState,
        last_boss_name: str,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.run_state = run_state
        self._processing = False
        self.add_item(combat_ui.embed_to_container(self._build_embed(last_boss_name)))
        self.add_item(ArbiterProceedRow())

    def _build_embed(self, last_boss_name: str) -> discord.Embed:
        embed = discord.Embed(
            title="🕯️ The Arbiter Materializes",
            description=(
                f"As you deliver the final blow to **{last_boss_name}**, the "
                "Arbiter materializes at your side, exactly as it always has.\n\n"
                f'*"{get_quip("arbiter_congratulate")}"*\n\n'
                "But something is wrong. The Arbiter's smile doesn't quite "
                "reach its eyes, and the air around you has gone thin and "
                "cold — like the moment before a held breath finally breaks."
            ),
            color=discord.Color.dark_purple(),
        )
        embed.set_author(name="The Arbiter", icon_url=ARBITER_PORTRAIT)
        embed.set_thumbnail(url=ARBITER_THUMBNAIL)
        return embed

    async def _on_proceed(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        confront = ArbiterConfrontView(
            self.bot, self.user_id, self.server_id, self.player, self.run_state
        )
        await interaction.edit_original_response(embed=None, view=confront)
        confront.message = await interaction.original_response()
        self.stop()


class ArbiterConfrontRow(discord.ui.ActionRow["ArbiterConfrontView"]):
    @discord.ui.button(label="Fight the Amalgam", style=ButtonStyle.danger, emoji="🕯️")
    async def confront(self, interaction: Interaction, button: ui.Button):
        await self.view._on_confirm(interaction)


class ArbiterConfrontView(BaseLayoutView):
    """Screen 2: the Arbiter vanishes from the player's side; the five
    essences converge into the Amalgam, and its voice speaks from within."""

    def __init__(
        self, bot, user_id: str, server_id: str, player, run_state: RiteRunState
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.run_state = run_state
        self._processing = False
        self.add_item(combat_ui.embed_to_container(self._build_embed()))
        self.add_item(ArbiterConfrontRow())

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🕯️ The Mask Drops",
            description=(
                "The atmosphere twists into itself as the essences of the "
                "five reborn gods converge. You stare on in horror. You look "
                "to your side — the Arbiter is no longer there.\n\n"
                f'*"{get_quip("arbiter_amalgam_taunt")}"*\n\n'
                "No respite. No aid. Whatever this thing is, it stands "
                "between you and the end of this."
            ),
            color=discord.Color.dark_purple(),
        )
        embed.set_author(name="The Arbiter", icon_url=ARBITER_PORTRAIT)
        embed.set_thumbnail(url=ARBITER_THUMBNAIL)
        return embed

    async def _on_confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # Lazy import: arbiter_view <-> wing_hub_view/reveal_view form a
        # small import cycle at the module level otherwise.
        from core.rite.views.arbiter_view import enter_arbiter_fight

        combat_view = await enter_arbiter_fight(
            self.bot, self.user_id, self.server_id, self.player, self.run_state
        )
        self.bot.state_manager.set_active(self.user_id, "rite")
        await interaction.edit_original_response(embed=None, view=combat_view)
        combat_view.message = await interaction.original_response()
        self.stop()
