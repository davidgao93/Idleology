from __future__ import annotations

from datetime import datetime

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.character.prestige_display import format_prestige_name
from core.hall_of_firsts.data import CategoryDef


class HallOfFirstDetailView(BaseLayoutView):
    """Single-achievement detail screen — the one place a Section+Thumbnail
    pair (the holder's snapshotted appearance) gets rendered, since 17 of
    these on one screen would exceed Discord's component budget."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str | None,
        category: CategoryDef,
        row,
        list_view,
    ):
        super().__init__(bot, user_id, server_id)
        self.category = category
        self.row = row
        self.list_view = list_view
        self._sync_items()

    def _build_container(self) -> discord.ui.Container:
        if self.row is None:
            text = (
                f"## {self.category.emoji} {self.category.name}\n"
                f"*{self.category.flavor}*\n\n"
                "🔓 **Not yet claimed.** Be the first!"
            )
            return discord.ui.Container(
                discord.ui.TextDisplay(text), accent_color=discord.Color.dark_grey()
            )

        decorated = format_prestige_name(
            self.row["snapshot_name"],
            self.row["snapshot_title"] or "",
            self.row["snapshot_emblem"] or "",
        )
        try:
            achieved = datetime.fromisoformat(self.row["achieved_at"]).strftime(
                "%Y-%m-%d"
            )
        except (ValueError, TypeError):
            achieved = self.row["achieved_at"]

        text = (
            f"## {self.category.emoji} {self.category.name}\n"
            f"*{self.category.flavor}*\n\n"
            f"**Holder:** {decorated}\n"
            f"**Achieved:** {achieved}"
        )
        appearance = self.row["snapshot_appearance"]
        if appearance:
            section = discord.ui.Section(
                text, accessory=discord.ui.Thumbnail(appearance, description=decorated)
            )
        else:
            section = discord.ui.TextDisplay(text)
        return discord.ui.Container(section, accent_color=discord.Color.gold())

    def _sync_items(self) -> None:
        self.clear_items()
        self.add_item(self._build_container())

        back_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="↩️")
        back_btn.callback = self._back
        back_row.add_item(back_btn)
        self.add_item(back_row)

    async def _back(self, interaction: Interaction) -> None:
        await self.list_view.load()
        await interaction.response.edit_message(view=self.list_view)
        self.list_view.message = self.message
        self.stop()
