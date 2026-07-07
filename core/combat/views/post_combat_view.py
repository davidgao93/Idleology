import discord
from discord import Interaction

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.items.factory import load_player


class PostCombatRow(discord.ui.ActionRow["PostCombatView"]):
    @discord.ui.button(label="Fight Again", style=discord.ButtonStyle.green)
    async def fight_again_btn(self, interaction: Interaction, button: discord.ui.Button):
        await self.view._fight_again(interaction)


class PostCombatView(BaseLayoutView):
    """Shown after a regular victory. Has a Fight Again button when stamina > 0,
    or no buttons when stamina is empty (the content carries the cooldown info).

    Callers must build the victory embed themselves and pass it to set_content()
    before displaying this view — PostCombatView only owns the button row."""

    def __init__(
        self, bot, user_id: str, server_id: str, player, stamina: int, rematch_callback
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.rematch_callback = rematch_callback
        self._stamina = stamina
        self._launching = False  # Re-entry guard

        self.row = PostCombatRow()
        if stamina > 0:
            self.row.fight_again_btn.label = f"Fight Again  ⚡{stamina:g}"
        else:
            self.row.remove_item(self.row.fight_again_btn)

    def set_content(self, embed: discord.Embed) -> None:
        """Renders `embed` as this view's Components V2 content, followed by
        the button row (if any)."""
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        if self.row.children:
            self.add_item(self.row)

    async def on_timeout(self) -> None:
        """Expire the Fight Again button without touching active state.
        The player was already freed at victory time; calling clear_active here
        would incorrectly interrupt any new fight they started within this window."""
        if self.message:
            try:
                for item in list(self.children):
                    if isinstance(item, discord.ui.ActionRow):
                        self.remove_item(item)
                await self.message.edit(view=self)
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
        self.row.fight_again_btn.disabled = True
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
