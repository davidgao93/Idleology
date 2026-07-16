"""
core/base_view.py
Global base class for ALL Discord views in the entire bot.
"""

from __future__ import annotations

import asyncio

import discord
from discord import Interaction, ui


class BaseView(ui.View):
    """Global base class for every view in the bot.
    Supports two initialization styles:
    - Normal:   BaseView(bot, user_id, server_id=...)
    - Child:    BaseView(bot, parent=parent_view)
    """

    #: Views that intentionally handle clicks while a callback is still
    #: running (auto-battle loops, casino cash-out) set this to True and
    #: manage their own per-button re-entry flags instead.
    concurrent_dispatch = False

    def __init__(
        self,
        bot,
        user_id: str | None = None,
        server_id: str | None = None,
        *,
        parent: "BaseView | None" = None,
        timeout: int | None = None,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.message: discord.Message | None = None
        self._dispatch_busy = False

        # Smart resolution of user_id / server_id
        if parent is not None:
            self.user_id = parent.user_id
            self.server_id = parent.server_id
        else:
            if user_id is None:
                raise ValueError("BaseView requires either `user_id` or `parent=...`")
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
        """Central dispatch choke point for every button/select.

        Adds two protections on top of discord.py's dispatch:
        - Session-token check: orphaned views from a force-cleared session
          go dead instead of racing a fresh session against the same state.
        - Re-entry guard: while one callback is running, further clicks on
          this view are swallowed, preventing double DB writes from rapid
          clicks. Per-view opt-out via ``concurrent_dispatch``.
        """
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

    async def _safe_message_edit(
        self, *, retries: int = 1, retry_delay: float = 2.0, **kwargs
    ) -> bool:
        """Best-effort ``self.message.edit(...)`` for background timer tasks.

        Background tasks (cooldown timers, bite windows, etc.) drive state
        transitions outside of any interaction callback, so a transient
        REST hiccup here has no interaction to retry from and no timeout to
        eventually clean things up (views run with ``timeout=None``). Left
        unhandled, a single failed edit permanently strands the player on a
        message full of disabled buttons. This retries once, logs failures
        instead of dropping them, and never raises.
        """
        if not self.message:
            return False
        for attempt in range(retries + 1):
            try:
                await self.message.edit(**kwargs)
                return True
            except asyncio.CancelledError:
                raise
            except Exception:
                if attempt < retries:
                    await asyncio.sleep(retry_delay)
                    continue
                try:
                    self.bot.logger.error(
                        f"{type(self).__name__} background message edit failed "
                        f"for user {self.user_id}",
                        exc_info=True,
                    )
                except Exception:
                    pass
                return False
        return False

    async def on_timeout(self) -> None:
        """Default safe cleanup."""
        if self.user_id:
            self.bot.state_manager.clear_active(self.user_id)

        if self.message:
            try:
                await self.message.edit(view=None)
            except (discord.NotFound, discord.HTTPException, AttributeError):
                pass
            except Exception:
                # Unexpected error during view cleanup; log but do not crash the task
                try:
                    self.bot.logger.error(
                        f"BaseView on_timeout unexpected error while editing message for user {self.user_id}",
                        exc_info=True,
                    )
                except Exception:
                    pass  # Logging must never raise
        self.stop()
