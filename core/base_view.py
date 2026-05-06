"""
core/base_view.py
Global base class for ALL Discord views in the bot.
"""

import discord
from discord import Interaction, ui


class BaseView(ui.View):
    """Base class for every view in the entire bot.
    Guarantees consistent interaction checks + proper state_manager cleanup.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str | None = None,  # optional
        timeout: int = 600,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = str(user_id)
        self.server_id = str(server_id) if server_id is not None else None
        self.message: discord.Message | None = None

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
