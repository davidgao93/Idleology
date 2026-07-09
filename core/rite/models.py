"""The Rite of Convergence's Artefact slot — a single equippable item,
entirely separate from the 6 normal gear slots, only obtainable from a
completed Rite run. Stats are randomized on drop (see core/rite/loot.py).

Mirrors core/apex/models.py's SoulStone single-slot storage/load pattern.
"""

from dataclasses import dataclass


@dataclass
class Artefact:
    key: str
    roll_1: float = 0.0
    roll_2: float = 0.0
    roll_3: float = 0.0


def artefact_from_db(row) -> "Artefact | None":
    if row is None or not row["artefact_key"]:
        return None
    return Artefact(
        key=row["artefact_key"],
        roll_1=row["roll_1"] or 0.0,
        roll_2=row["roll_2"] or 0.0,
        roll_3=row["roll_3"] or 0.0,
    )
