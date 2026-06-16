"""
core/character/profile_ui.py
Aggregates all profile embed builders into a single ProfileBuilder class.

Split across three implementation modules:
  profile_ui_card.py    — build_card, build_cooldowns
  profile_ui_combat.py  — build_stats, build_passives
  profile_ui_storage.py — build_inventory, build_crafting, build_resources,
                          build_uber, build_essences
"""

from core.character.profile_ui_card import CardProfileBuilder
from core.character.profile_ui_combat import CombatProfileBuilder
from core.character.profile_ui_storage import StorageProfileBuilder


class ProfileBuilder(CardProfileBuilder, CombatProfileBuilder, StorageProfileBuilder):
    """Unified profile embed builder. All methods are static async functions."""
