"""
core/base_view.py
Global base class for ALL Discord views in the entire bot.
"""

from __future__ import annotations  # ← This MUST be at the absolute top

import discord
from discord import Interaction, ui


class BaseView(ui.View):
    """Global base class for every view in the bot.
    Supports two initialization styles:
    - Normal:   BaseView(bot, user_id, server_id=...)
    - Child:    BaseView(bot, parent=parent_view)
    """

    def __init__(
        self,
        bot,
        user_id: str | None = None,
        server_id: str | None = None,
        *,
        parent: "BaseView | None" = None,
        timeout: int = 600,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.message: discord.Message | None = None

        # Smart resolution of user_id / server_id
        if parent is not None:
            self.user_id = parent.user_id
            self.server_id = parent.server_id
        else:
            if user_id is None:
                raise ValueError("BaseView requires either `user_id` or `parent=...`")
            self.user_id = str(user_id)
            self.server_id = str(server_id) if server_id is not None else None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self) -> None:
        """Default safe cleanup."""
        self.bot.state_manager.clear_active(self.user_id)
        if self.message:
            try:
                await self.message.edit(view=None)
            except (discord.NotFound, discord.HTTPException, AttributeError, Exception):
                pass
        self.stop()
