"""In-memory run state for an active Rite of Convergence attempt, plus the
JSON snapshot shape persisted to the `rite_runs` table (see
database/repositories/rite.py). The Rite has no save/resume — a leftover
row only exists if the bot crashed mid-run, and /rite discards it outright
rather than reconstructing a live RiteRunState from it (see cogs/rite.py).
Persisting the snapshot still matters for that crash-detection existence
check, and for ad-hoc DB inspection of a stuck run.
"""

from dataclasses import dataclass, field

DEFAULT_ATTEMPTS = 3

ALL_WING_KEYS = ("aphrodite", "lucifer", "gemini", "neet", "evelynn")


@dataclass
class RiteRunState:
    attempts_remaining: int = DEFAULT_ATTEMPTS
    max_attempts: int = DEFAULT_ATTEMPTS  # starting attempts for this run (writ-driven); used for the lives display
    wings_cleared: set[str] = field(default_factory=set)
    room_entry_hp: int = 0  # HP snapshot at the start of the current wing/Arbiter attempt; restored on death
    total_turns: int = 0
    writs: list[str] = field(default_factory=list)
    # Respite's "Power" choice: +30% ATK/DEF per pick, additive, cumulative
    # for the rest of the run (never reset on wing clear or retry).
    power_stacks: int = 0

    @property
    def is_run_complete(self) -> bool:
        return len(self.wings_cleared) >= len(ALL_WING_KEYS)

    def to_snapshot(self) -> dict:
        return {
            "attempts_remaining": self.attempts_remaining,
            "max_attempts": self.max_attempts,
            "wings_cleared": sorted(self.wings_cleared),
            "room_entry_hp": self.room_entry_hp,
            "total_turns": self.total_turns,
            "writs": self.writs,
            "power_stacks": self.power_stacks,
        }
