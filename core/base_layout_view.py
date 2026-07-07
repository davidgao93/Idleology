"""
core/base_layout_view.py
Global base class for Discord views built on Components V2
(discord.ui.LayoutView) — mirrors core/base_view.py's BaseView contract
(session-token invalidation, re-entry guard, state_manager cleanup) but for
LayoutView, which is a sibling of discord.ui.View, not a subclass of it.

Once a message is sent with a LayoutView, Discord permanently flags it
IS_COMPONENTS_V2 and that flag cannot be removed — every future edit to that
message must supply components, never content/embeds. Views that hand off
to a classic BaseView-based screen must send a new message rather than
editing in place.
"""

from __future__ import annotations

import discord
from discord import Interaction, ui


class BaseLayoutView(ui.LayoutView):
    """Global base class for every Components V2 view in the bot.
    Supports two initialization styles:
    - Normal:   BaseLayoutView(bot, user_id, server_id=...)
    - Child:    BaseLayoutView(bot, parent=parent_view)
    """

    #: Views that intentionally handle clicks while a callback is still
    #: running (auto-battle loops) set this to True and manage their own
    #: per-button re-entry flags instead.
    concurrent_dispatch = False

    def __init__(
        self,
        bot,
        user_id: str | None = None,
        server_id: str | None = None,
        *,
        parent: "BaseLayoutView | None" = None,
        timeout: int | None = None,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.message: discord.Message | None = None
        self._dispatch_busy = False

        if parent is not None:
            self.user_id = parent.user_id
            self.server_id = parent.server_id
        else:
            if user_id is None:
                raise ValueError("BaseLayoutView requires either `user_id` or `parent=...`")
            self.user_id = str(user_id)
            self.server_id = str(server_id) if server_id is not None else None

        # Snapshot of the user's session token. force_clear() bumps the
        # token, which kills every view created before it (see
        # _session_token_valid).
        sm = getattr(bot, "state_manager", None)
        self._session_token = sm.current_token(self.user_id) if sm else 0

    def _session_token_valid(self) -> bool:
        sm = getattr(self.bot, "state_manager", None)
        if sm is None or self.user_id is None:
            return True
        return self._session_token == sm.current_token(self.user_id)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def _scheduled_task(self, item: ui.Item, interaction: Interaction):
        """Central dispatch choke point for every button/select — identical
        contract to BaseView._scheduled_task. See core/base_view.py."""
        if not self._session_token_valid():
            try:
                await interaction.response.defer()
            except discord.HTTPException:
                pass
            return

        if self.concurrent_dispatch:
            return await super()._scheduled_task(item, interaction)

        if self._dispatch_busy:
            try:
                await interaction.response.defer()
            except discord.HTTPException:
                pass
            return
        self._dispatch_busy = True
        try:
            await super()._scheduled_task(item, interaction)
        finally:
            self._dispatch_busy = False

    async def on_timeout(self) -> None:
        """Default safe cleanup.

        Unlike BaseView (where the embed and the view/buttons are separate
        message fields), a LayoutView's visible content lives inside its own
        components — so "removing the buttons" means pruning ActionRow
        items out of the tree while leaving informational components
        (Container, TextDisplay, MediaGallery, ...) in place, then
        re-editing with the pruned view rather than passing view=None.
        """
        if self.user_id:
            self.bot.state_manager.clear_active(self.user_id)

        if self.message:
            try:
                for item in list(self.children):
                    if isinstance(item, ui.ActionRow):
                        self.remove_item(item)
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException, AttributeError):
                pass
            except Exception:
                try:
                    self.bot.logger.error(
                        f"BaseLayoutView on_timeout unexpected error while editing message for user {self.user_id}",
                        exc_info=True,
                    )
                except Exception:
                    pass  # Logging must never raise
        self.stop()
