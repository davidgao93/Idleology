"""
core/combat/base_views.py
Shared base class for ALL combat-related views.
Prevents circular imports and guarantees state_manager cleanup.
"""

import discord
from discord import Interaction, ui


class BaseCombatView(ui.View):
    """Base class for every view in the combat module."""

    def __init__(self, bot, user_id: str, server_id: str, timeout: int = 600):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = str(user_id)
        self.server_id = str(server_id)
        self.message: discord.Message | None = None  # for safe on_timeout

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self) -> None:
        """Default safe cleanup. Most views can just inherit this."""
        self.bot.state_manager.clear_active(self.user_id)
        if self.message:
            try:
                await self.message.edit(view=None)
            except (discord.NotFound, discord.HTTPException, AttributeError, Exception):
                pass
        self.stop()
