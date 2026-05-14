"""
core/models.py — Backward-compatibility re-export shim.

All dataclasses have moved to domain-specific modules:
  core/items/models.py       — Weapon, Accessory, Armor, Glove, Boot, Helmet,
                               Companion, CodexTome, MonsterPart
  core/combat/models.py      — CombatState, CodexRunState, MonsterModifier,
                               Monster, DungeonRoomOption, DungeonState, Player
  core/settlement/models.py  — Settlement, Building
  core/partners/models.py    — Partner

Every existing ``from core.models import X`` continues to work unchanged.
New code should import directly from the canonical module.
"""

from core.combat.models import (  # noqa: F401
    CodexRunState,
    CombatState,
    DungeonRoomOption,
    DungeonState,
    Monster,
    MonsterModifier,
    Player,
)
from core.items.models import (  # noqa: F401
    _PART_SLOT_LABELS,
    Accessory,
    Armor,
    Boot,
    CodexTome,
    Companion,
    Glove,
    Helmet,
    MonsterPart,
    Weapon,
)
from core.partners.models import Partner  # noqa: F401
from core.settlement.models import Building, Settlement  # noqa: F401

__all__ = [
    # items
    "Weapon",
    "Accessory",
    "Armor",
    "Glove",
    "Boot",
    "Helmet",
    "Companion",
    "CodexTome",
    "MonsterPart",
    "_PART_SLOT_LABELS",
    # combat
    "CombatState",
    "CodexRunState",
    "MonsterModifier",
    "Monster",
    "DungeonRoomOption",
    "DungeonState",
    "Player",
    # settlement
    "Settlement",
    "Building",
    # partners
    "Partner",
]
