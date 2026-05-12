# Backward-compatible module re-exports for jewel_engine and rewards.
# These were previously importable as `from core.combat import jewel_engine`
# and `from core.combat import rewards`. Existing callers continue to work.
from core.combat.turns import jewel_engine  # noqa: F401
from core.combat.economy import rewards     # noqa: F401
