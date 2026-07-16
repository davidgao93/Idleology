"""The Rite of Convergence's Artefact inventory — a 7th gear-like slot,
entirely separate from the 6 normal equipment tables (see
database/repositories/rite.py: rite_artefact_items). Players can own
multiple artefacts and equip one at a time; only the equipped one affects
combat (see Player.artefact / Player.has_artefact in core/combat/models.py).
Stats are randomized on drop (see core/rite/loot.py).
"""

from dataclasses import dataclass


@dataclass
class Artefact:
    item_id: int
    key: str
    roll_1: float = 0.0
    roll_2: float = 0.0
    roll_3: float = 0.0
    is_equipped: bool = False

    @property
    def name(self) -> str:
        from core.rite.loot import ARTEFACT_TABLE

        return ARTEFACT_TABLE[self.key][0]

    @property
    def source(self) -> str:
        from core.rite.loot import ARTEFACT_TABLE

        return ARTEFACT_TABLE[self.key][1]

    @property
    def image(self) -> str:
        from core.rite.loot import ARTEFACT_TABLE

        return ARTEFACT_TABLE[self.key][4]

    @property
    def roll_1_range(self) -> "tuple[int, int] | None":
        """(min, max) this artefact's roll_1 could have landed on, or None
        for artefacts with no variable roll — lets the UI show how good a
        drop was, e.g. '27% (range 15-35%)'."""
        from core.rite.loot import roll_1_range

        return roll_1_range(self.key)


def artefact_from_db(row: dict | None) -> "Artefact | None":
    if row is None or not row.get("artefact_key"):
        return None
    return Artefact(
        item_id=row["item_id"],
        key=row["artefact_key"],
        roll_1=row.get("roll_1") or 0.0,
        roll_2=row.get("roll_2") or 0.0,
        roll_3=row.get("roll_3") or 0.0,
        is_equipped=bool(row.get("is_equipped")),
    )


def artefact_list_from_db(rows: list[dict]) -> list["Artefact"]:
    return [a for row in rows if (a := artefact_from_db(row)) is not None]
