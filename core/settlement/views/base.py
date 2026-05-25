# core/settlement/views/base.py
"""Base class for all settlement-related Discord UI views."""

from core.base_view import BaseView


class SettlementBaseView(BaseView):
    """Common base for all settlement views.

    Provides a shared ``on_timeout`` that deletes the original message and
    clears the player's active state.  All settlement views share a single
    Discord message; child views (PlotDetailView, TownHallView, etc.) hold
    a ``parent`` reference back to the top-level dashboard (or an intermediate
    view), and ``_root_message`` walks that chain to find the message object.
    """

    def __init__(self, bot, user_id: str, timeout: int = 600):
        super().__init__(bot, user_id, timeout=timeout)

    @property
    def _root_message(self):
        """Return the Discord Message to delete, climbing parent/origin chains."""
        if self.message:
            return self.message
        for attr in ("parent", "origin"):
            node = getattr(self, attr, None)
            if isinstance(node, SettlementBaseView):
                return node._root_message
        return None

    async def on_timeout(self) -> None:
        self.bot.state_manager.clear_active(self.user_id)
        msg = self._root_message
        if msg is not None:
            try:
                await msg.delete()
            except Exception:
                pass
        self.stop()
