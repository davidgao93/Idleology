"""In-memory run state for an active Rite of Convergence attempt, plus the
JSON snapshot shape persisted to the `rite_runs` table (see
database/repositories/rite.py). Mirrors core/codex/views/run_view.py's
to_snapshot()/resume-from-snapshot split, adapted for a run that spans
several distinct views (wing hub, respite, combat) rather than one.
"""

from dataclasses import dataclass, field

# 5 attempts fields deliberately omitted here: writ-driven starting attempts
# (One Last Chance / No Mercy) land in Milestone 4. Fixed at 3 until then.
DEFAULT_ATTEMPTS = 3

ALL_WING_KEYS = ("aphrodite", "lucifer", "gemini", "neet", "evelynn")


@dataclass
class RiteRunState:
    attempts_remaining: int = DEFAULT_ATTEMPTS
    wings_cleared: set[str] = field(default_factory=set)
    current_wing: str | None = None  # wing key currently being attempted, if any
    room_entry_hp: int = 0
    room_entry_potions: int = 0
    total_turns: int = 0
    writs: list[str] = field(default_factory=list)  # empty until Milestone 4
    pending_power_buff: bool = False  # Respite's "Power" choice: +30% ATK/DEF, cleared on wing clear

    @property
    def is_run_complete(self) -> bool:
        return len(self.wings_cleared) >= len(ALL_WING_KEYS)

    def to_snapshot(self) -> dict:
        return {
            "attempts_remaining": self.attempts_remaining,
            "wings_cleared": sorted(self.wings_cleared),
            "current_wing": self.current_wing,
            "room_entry_hp": self.room_entry_hp,
            "room_entry_potions": self.room_entry_potions,
            "total_turns": self.total_turns,
            "writs": self.writs,
            "pending_power_buff": self.pending_power_buff,
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> "RiteRunState":
        return cls(
            attempts_remaining=data.get("attempts_remaining", DEFAULT_ATTEMPTS),
            wings_cleared=set(data.get("wings_cleared", [])),
            current_wing=data.get("current_wing"),
            room_entry_hp=data.get("room_entry_hp", 0),
            room_entry_potions=data.get("room_entry_potions", 0),
            total_turns=data.get("total_turns", 0),
            writs=data.get("writs", []),
            pending_power_buff=data.get("pending_power_buff", False),
        )
