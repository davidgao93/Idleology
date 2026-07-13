from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.hall_of_firsts.data import CATEGORIES, CATEGORIES_BY_KEY


class HallOfFirstsListView(BaseLayoutView):
    """Text-only list of all 17 categories — deliberately no per-row
    thumbnails, since 17 Section+Thumbnail pairs would blow past Discord's
    40-component-per-message cap. Selecting a row opens HallOfFirstDetailView,
    which gets the full Section+Thumbnail treatment for just that one entry."""

    def __init__(self, bot, user_id: str, server_id: str | None = None):
        super().__init__(bot, user_id, server_id)
        self.claimed: dict = {}
        self._sync_items()

    async def load(self) -> None:
        self.claimed = await self.bot.database.hall_of_firsts.get_all()
        self._sync_items()

    def _sync_items(self) -> None:
        self.clear_items()
        self.add_item(self._build_container())

        select_row = ui.ActionRow()
        select = ui.Select(
            placeholder="View an achievement…",
            options=[
                discord.SelectOption(
                    label=f"{c.name}"[:100],
                    value=c.key,
                    emoji=c.emoji,
                    description=("Claimed" if c.key in self.claimed else "Unclaimed")[
                        :100
                    ],
                )
                for c in CATEGORIES
            ],
        )
        select.callback = self._on_select
        select_row.add_item(select)
        self.add_item(select_row)

        close_row = ui.ActionRow()
        close_btn = ui.Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        close_btn.callback = self._close
        close_row.add_item(close_btn)
        self.add_item(close_row)

    def _build_container(self) -> discord.ui.Container:
        lines = [
            "## 🏛️ Hall of Firsts",
            "*The first adventurers to claim each legend.*",
            "",
        ]
        for c in CATEGORIES:
            row = self.claimed.get(c.key)
            holder = row["snapshot_name"] if row else "*Unclaimed*"
            lines.append(f"{c.emoji} **{c.name}** — {holder}")
        return discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            accent_color=discord.Color.gold(),
        )

    async def _on_select(self, interaction: Interaction) -> None:
        from core.hall_of_firsts.views.detail_view import HallOfFirstDetailView

        category_key = interaction.data["values"][0]
        category = CATEGORIES_BY_KEY[category_key]
        row = self.claimed.get(category_key)

        detail = HallOfFirstDetailView(
            self.bot, self.user_id, self.server_id, category, row, self
        )
        await interaction.response.edit_message(view=detail)
        detail.message = self.message

    async def _close(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass
        self.stop()
