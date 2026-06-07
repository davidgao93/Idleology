from dataclasses import dataclass

# _add_ward moved to ward_system.py; re-exported here for backward compatibility.


@dataclass
class PlayerTurnResult:
    log: str
    damage: int  # actual damage dealt to monster this turn (0 on full miss/block)
    is_hit: bool  # True for both normal hits and crits
    is_crit: bool  # True only for crits (subset of is_hit)
    calc_detail: str = ""  # numerical breakdown for combat log file only
    compact_log: str = ""  # condensed log for auto-battle display (no flavor text)
    partner_log: str = ""  # partner per-turn effects (joint attack, heal, etc.)
    partner_name: str = ""  # embed field name for the partner log
    cull_fired: bool = False  # True when cull dealt the killing blow this turn

    def __str__(self) -> str:
        return self.log


@dataclass
class MonsterTurnResult:
    log: str
    hp_damage: int  # net HP lost by the player this turn
    calc_detail: str = ""  # numerical breakdown for combat log file only
    compact_log: str = ""  # condensed log for auto-battle display (no flavor text)

    def __str__(self) -> str:
        return self.log


def capture_compact_events(log: list[str], clog: list[str], start_len: int) -> None:
    """Append any new entries added to `log` (since `start_len`) into the compact log.

    Used throughout monster/player turn processing to surface only "significant"
    events (detonations, procs, DoTs, bursts — not silent charge-ups or countdowns)
    into the auto-battle / compact view. Pure and side-effect free.
    """
    if len(log) > start_len:
        clog.extend(log[start_len:])
