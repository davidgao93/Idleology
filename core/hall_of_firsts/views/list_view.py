from __future__ import annotations

from datetime import datetime

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.character.prestige_display import format_prestige_name
from core.emojis import EMBLEM_CATALOG
from core.hall_of_firsts.data import CATEGORIES


class HallOfFirstsListView(BaseLayoutView):
    """Full Hall of Firsts board — every category, its completion requirement,
    and (for claimed categories) the holder's current appearance as a
    thumbnail, all rendered directly with no select-menu drill-down needed."""

    def __init__(self, bot, user_id: str, server_id: str | None = None):
        super().__init__(bot, user_id, server_id)
        self.claimed: dict = {}
        self.current_appearances: dict[str, str] = {}
        self._sync_items()

    async def load(self) -> None:
        self.claimed = await self.bot.database.hall_of_firsts.get_all()
        self.current_appearances = {}
        for row in self.claimed.values():
            user_row = await self.bot.database.users.get_by_user_id(row["user_id"])
            if user_row and user_row["appearance"]:
                self.current_appearances[row["user_id"]] = user_row["appearance"]
        self._sync_items()

    def _sync_items(self) -> None:
        self.clear_items()
        self.add_item(self._build_container())

        close_row = ui.ActionRow()
        close_btn = ui.Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        close_btn.callback = self._close
        close_row.add_item(close_btn)
        self.add_item(close_row)

    def _build_container(self) -> discord.ui.Container:
        children: list = [
            discord.ui.TextDisplay(
                "## 🏛️ Hall of Firsts\n*The first adventurers to claim each legend.*"
            )
        ]
        for c in CATEGORIES:
            row = self.claimed.get(c.key)
            if row is None:
                text = f"{c.emoji} **{c.name}**\n*{c.flavor}*\n🔓 *Unclaimed*"
                children.append(discord.ui.TextDisplay(text))
                continue

            # Older rows snapshotted the EMBLEM_CATALOG *key* (e.g.
            # "monster_cheeks") instead of the emoji itself — resolve it here
            # so legacy claims render the real emoji instead of literal key
            # text; newer rows already store the resolved emoji, and a
            # lookup miss on those just falls back to using the value as-is.
            emblem_raw = row["snapshot_emblem"] or ""
            emblem_entry = EMBLEM_CATALOG.get(emblem_raw)
            emblem = emblem_entry[1] if emblem_entry else emblem_raw
            decorated = format_prestige_name(
                row["snapshot_name"],
                row["snapshot_title"] or "",
                emblem,
            )
            try:
                achieved = datetime.fromisoformat(row["achieved_at"]).strftime(
                    "%Y-%m-%d"
                )
            except (ValueError, TypeError):
                achieved = row["achieved_at"]

            text = (
                f"{c.emoji} **{c.name}**\n*{c.flavor}*\n"
                f"**{decorated}** — {achieved}"
            )
            appearance = self.current_appearances.get(row["user_id"])
            if appearance:
                children.append(
                    discord.ui.Section(
                        text,
                        accessory=discord.ui.Thumbnail(
                            appearance, description=decorated
                        ),
                    )
                )
            else:
                children.append(discord.ui.TextDisplay(text))

        return discord.ui.Container(*children, accent_color=discord.Color.gold())

    async def _close(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass
        self.stop()
