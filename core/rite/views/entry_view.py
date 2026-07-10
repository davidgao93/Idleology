"""The Rite of Convergence — entry lobby, shown from the Arbiter's point of
view every time /rite is invoked with no run in progress. Mirrors the Uber
Hub's readiness-lobby precedent (core/combat/views/views_uber_hub.py): show
what the player currently holds, then require an explicit confirm before any
key is spent. The Rite has no save/resume (see RiteExitConfirmView), so this
is the only point where backing out costs nothing.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.emojis import (
    RITE_KEY_CELESTIAL,
    RITE_KEY_CORRUPT,
    RITE_KEY_GEMINI,
    RITE_KEY_INFERNAL,
    RITE_KEY_VOID,
)
from core.images import ARBITER_PORTRAIT, ARBITER_THUMBNAIL
from core.npc_voices import get_quip

# (display name, currency column, emoji) — mirrors cogs.rite._RITE_KEY_COLUMNS
RITE_KEY_COLUMNS = [
    ("Apex of Dreams", "rite_key_apex_of_dreams", RITE_KEY_CELESTIAL),
    ("Corruption of Memories", "rite_key_corruption_of_memories", RITE_KEY_INFERNAL),
    ("Scales of Judgment", "rite_key_scales_of_judgment", RITE_KEY_GEMINI),
    ("Devoid of Thoughts", "rite_key_devoid_of_thoughts", RITE_KEY_VOID),
    ("Zenith of Nightmares", "rite_key_zenith_of_nightmares", RITE_KEY_CORRUPT),
]


class RiteEntryRow(discord.ui.ActionRow["RiteEntryView"]):
    @discord.ui.button(label="Enter the Rite", style=ButtonStyle.danger, emoji="🕯️")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        await self.view._on_confirm(interaction)

    @discord.ui.button(label="Not Yet", style=ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await self.view._on_cancel(interaction)


class RiteEntryView(BaseLayoutView):
    def __init__(self, bot, user_id: str, server_id: str, balances: dict, on_confirm):
        super().__init__(bot, user_id, server_id)
        self.balances = balances
        # async fn(interaction) -> None; owns everything after confirmation
        # (writ selection for returning players, or straight to _begin_run).
        self.on_confirm = on_confirm
        self._processing = False
        self.add_item(combat_ui.embed_to_container(self.build_embed()))
        self.add_item(RiteEntryRow())

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🕯️ The Rite of Convergence",
            description=(
                f'*"{get_quip("arbiter")}"*\n\n'
                "Five reborn gods stand between you and the truth behind "
                "them. All 5 keys are consumed on entry — held "
                "simultaneously, or not at all.\n\n"
                "**3 attempts** for the entire run. **There is no save.** "
                "Leave mid-run for any reason and the attempt, the wings "
                "cleared, and the keys already spent are all forfeit."
            ),
            color=discord.Color.dark_purple(),
        )
        embed.set_author(name="The Arbiter", icon_url=ARBITER_PORTRAIT)
        embed.set_thumbnail(url=ARBITER_THUMBNAIL)
        key_lines = []
        for name, col, emoji in RITE_KEY_COLUMNS:
            have = self.balances.get(col, 0)
            mark = "✅" if have >= 1 else "❌"
            key_lines.append(f"{mark} {emoji} **{name}** — {have}")
        embed.add_field(name="Your Keys", value="\n".join(key_lines), inline=False)
        return embed

    async def _on_confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await self.on_confirm(interaction)
        self.stop()

    async def _on_cancel(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
