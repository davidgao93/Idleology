from dataclasses import dataclass

# _add_ward moved to ward_system.py; re-exported here for backward compatibility.
from core.combat.ward_system import add_ward as _add_ward


@dataclass
class PlayerTurnResult:
    log: str
    damage: int  # actual damage dealt to monster this turn (0 on full miss/block)
    is_hit: bool  # True for both normal hits and crits
    is_crit: bool  # True only for crits (subset of is_hit)
    calc_detail: str = ""  # numerical breakdown for combat log file only
    partner_log: str = ""  # partner per-turn effects (joint attack, heal, etc.)
    partner_name: str = ""  # embed field name for the partner log

    def __str__(self) -> str:
        return self.log


@dataclass
class MonsterTurnResult:
    log: str
    hp_damage: int  # net HP lost by the player this turn
    calc_detail: str = ""  # numerical breakdown for combat log file only

    def __str__(self) -> str:
        return self.log
