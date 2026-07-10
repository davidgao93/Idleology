"""The fifth-wing reveal. Per RAID-DESIGN.md: clearing the 5th wing triggers
the Arbiter's true nature — no respite, no aid, the finale begins. This is a
static, one-time narrative screen: the player must explicitly click
"Confront the Arbiter" before Phase 1 starts (previously this auto-advanced
after a timed sleep, too fast for the reveal to actually register).

Re-entry after a flee/death during the Arbiter fight skips this screen
entirely — see WingHubView's "Challenge the Arbiter" button, which calls
arbiter_view.enter_arbiter_fight() directly.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.images import ARBITER_PORTRAIT, ARBITER_THUMBNAIL
from core.npc_voices import get_quip
from core.rite.run_state import RiteRunState


class ArbiterConfrontRow(discord.ui.ActionRow["ArbiterConfrontView"]):
    @discord.ui.button(
        label="Confront the Arbiter", style=ButtonStyle.danger, emoji="🕯️"
    )
    async def confront(self, interaction: Interaction, button: ui.Button):
        await self.view._on_confirm(interaction)


class ArbiterConfrontView(BaseLayoutView):
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
            title="🕯️ The Arbiter Reveals Itself",
            description=(
                f'*"{get_quip("arbiter_reveal")}"*\n\n'
                "The essences of the five defeated bosses converge. The air fractures. "
                "The Arbiter's true form emerges — the architect behind everything "
                "you have faced tonight.\n\n"
                "No respite. No aid. Six phases stand between you and the end of this."
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
