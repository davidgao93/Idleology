from dataclasses import dataclass

from core.models import Player


@dataclass
class PlayerTurnResult:
    log: str
    damage: int      # actual damage dealt to monster this turn (0 on full miss/block)
    is_hit: bool     # True for both normal hits and crits
    is_crit: bool    # True only for crits (subset of is_hit)
    calc_detail: str = ""   # numerical breakdown for combat log file only
    partner_log: str = ""   # partner per-turn effects (joint attack, heal, etc.)
    partner_name: str = ""  # embed field name for the partner log

    def __str__(self) -> str:
        return self.log


@dataclass
class MonsterTurnResult:
    log: str
    hp_damage: int   # net HP lost by the player this turn
    calc_detail: str = ""   # numerical breakdown for combat log file only

    def __str__(self) -> str:
        return self.log


def _add_ward(player: Player, amount: int, log: list, label: str = "") -> int:
    """
    Adds ward to the player, doubling if the NEET helmet corrupted essence is active.
    Returns the final amount added. Logs only if label is provided.
    """
    if amount <= 0:
        return 0
    if player.get_helmet_corrupted_essence() == "neet":
        amount *= 2
        if label:
            log.append(
                f"🌑 **Void Resonance** doubles ward gain! ({label}: +{amount} 🔮)"
            )
    player.combat_ward += amount
    return amount
