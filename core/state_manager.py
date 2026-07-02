"""
core/state_manager.py
Tracks which users are currently inside an interactive view.
"""

import time
from typing import Dict


class StateManager:
    """Tracks which users are currently inside an interactive view.

    State is cleared in four ways:
    - Explicitly by each view's exit/complete/flee button path.
    - By ``clear_all()`` when the bot's shard resumes after a disconnect
      (users cannot interact with a view during a shard drop, so their
      session is considered expired on reconnect).
    - By the owner ``/clearall`` command for manual admin resets.
    - Lazily, when ``is_active`` finds a lock older than
      ``STALE_LOCK_SECONDS`` — this covers the "the message with my Close
      button is gone" case that otherwise locks a player out until a
      restart.

    Force-clearing (stale expiry) also bumps the user's session token.
    ``BaseView`` captures the token at construction and rejects
    interactions when it no longer matches, so a force-cleared session's
    orphaned views go dead instead of racing a new session against the
    same state. Regular ``clear_active`` does NOT bump the token: views
    like PostCombatView legitimately outlive their session lock.
    """

    STALE_LOCK_SECONDS = 45 * 60

    def __init__(self, logger):
        self.logger = logger
        # user_id → (operation name, monotonic start time)
        self.active_operations: Dict[str, tuple] = {}
        self._tokens: Dict[str, int] = {}

    def set_active(self, user_id: str, operation: str):
        self.logger.info(f"Set {user_id} as {operation}")
        self.active_operations[user_id] = (operation, time.monotonic())

    def clear_active(self, user_id: str):
        self.logger.info(f"Attempt to clear {user_id}")
        if user_id in self.active_operations:
            self.logger.info(f"{user_id} found in active list, cleared")
            del self.active_operations[user_id]

    def force_clear(self, user_id: str):
        """Clear the lock AND invalidate every live view of the session."""
        self.active_operations.pop(user_id, None)
        self._tokens[user_id] = self._tokens.get(user_id, 0) + 1
        self.logger.info(f"Force-cleared {user_id} (session token bumped)")

    def current_token(self, user_id: str) -> int:
        return self._tokens.get(user_id, 0)

    def is_active(self, user_id: str) -> bool:
        entry = self.active_operations.get(user_id)
        if entry is None:
            return False
        operation, started_at = entry
        if time.monotonic() - started_at > self.STALE_LOCK_SECONDS:
            self.logger.info(
                f"Stale {operation} lock for {user_id} — force-clearing"
            )
            self.force_clear(user_id)
            return False
        return True

    def get_operation(self, user_id: str):
        """Operation name for an active user, or None."""
        entry = self.active_operations.get(user_id)
        return entry[0] if entry else None

    def clear_all(self):
        count = len(self.active_operations)
        self.active_operations.clear()
        self.logger.info(f"Cleared all {count} active operations")

    def get_active_count(self):
        """Get count of active operations."""
        return len(self.active_operations)
