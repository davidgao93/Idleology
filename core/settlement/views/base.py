# core/settlement/views/base.py
"""Base class for all settlement-related Discord UI views."""

from discord import Interaction, ui


class SettlementBaseView(ui.View):
    """Common base for all settlement views with shared behavior."""

    def __init__(self, bot, user_id: str, timeout: int = 600):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Only allow the original user to interact."""
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        """Default timeout behavior (can be overridden)."""
        self.stop()
