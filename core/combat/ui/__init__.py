"""
core/combat/ui — Combat embed builders.

Re-exports the full public surface so all callers using
``from core.combat import ui as combat_ui`` continue to work unchanged.
"""

from core.combat.ui.combat_embed import (  # noqa: F401
    build_status_text,
    create_combat_embed,
    get_hp_display,
)
from core.combat.ui.defeat_screen import create_defeat_embed  # noqa: F401
from core.combat.ui.victory_screen import create_victory_embed  # noqa: F401

__all__ = [
    "get_hp_display",
    "build_status_text",
    "create_combat_embed",
    "create_victory_embed",
    "create_defeat_embed",
]
