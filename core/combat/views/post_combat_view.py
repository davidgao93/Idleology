import discord
from discord import Interaction

from core.base_view import BaseView
from core.items.factory import load_player


class PostCombatView(BaseView):
    """Shown after a regular victory. Has a Fight Again button when stamina > 0,
    or no buttons when stamina is empty (the embed field carries the cooldown info)."""

    def __init__(
        self, bot, user_id: str, server_id: str, player, stamina: int, rematch_callback
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.rematch_callback = rematch_callback
        self._stamina = stamina
        self._launching = False  # Re-entry guard

        if stamina > 0:
            btn = discord.ui.Button(
                label=f"Fight Again  ⚡{stamina:g}",
                style=discord.ButtonStyle.green,
            )
            btn.callback = self._fight_again
            self.add_item(btn)

    async def on_timeout(self) -> None:
        """Expire the Fight Again button without touching active state.
        The player was already freed at victory time; calling clear_active here
        would incorrectly interrupt any new fight they started within this window."""
        if self.message:
            try:
                await self.message.edit(view=None)
            except (discord.NotFound, discord.HTTPException):
                pass
        self.stop()

    async def _fight_again(self, interaction: Interaction):
        # Synchronous guard — assigned before the first await, so the event loop
        # cannot schedule a second invocation while this one is still running.
        if self._launching:
            await interaction.response.defer()
            return
        self._launching = True

        await interaction.response.defer()

        # Disable the button right away so Discord shows it as locked.
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        if self.bot.state_manager.is_active(self.user_id):
            await interaction.followup.send(
                "You're already in an activity.", ephemeral=True
            )
            self.stop()  # View is unusable (buttons disabled); stop to cancel the timeout.
            return

        # Re-fetch user and reload player so any changes (rest, gear swaps, etc.) are reflected.
        existing_user = await self.bot.database.users.get(self.user_id, self.server_id)
        if existing_user["combat_stamina"] <= 0:
            await interaction.followup.send("No stamina remaining!", ephemeral=True)
            self.stop()
            return

        fresh_player = await load_player(self.user_id, existing_user, self.bot.database)
        self.bot.state_manager.set_active(self.user_id, "combat")
        await self.rematch_callback(
            interaction, self.user_id, self.server_id, existing_user, fresh_player
        )
        self.stop()
