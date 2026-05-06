"""
core/alchemy/base_views.py
Shared base class for all Alchemy views
"""

import discord
from discord import Interaction, ui


class BaseAlchemyView(ui.View):
    """Base class for ALL Alchemy module views.
    Guarantees consistent interaction checks + proper state_manager cleanup on timeout.
    """

    def __init__(self, bot, user_id: str, server_id: str, timeout: int = 600):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = str(user_id)
        self.server_id = str(server_id)
        self.message: discord.Message | None = None  # used by on_timeout

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self) -> None:
        """Always clear the active state when any Alchemy view times out."""
        self.bot.state_manager.clear_active(self.user_id)
        if self.message:
            try:
                await self.message.edit(view=None)
            except (discord.NotFound, discord.HTTPException, AttributeError, Exception):
                pass
        self.stop()
