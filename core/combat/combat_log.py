"""
Combat logging — writes per-encounter logs to logs/combat/ when enabled.

Toggle via config.json:  "combat_logging": true
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from core.models import Monster, Player

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "combat"

logger = logging.getLogger("discord_bot")


def _logging_enabled() -> bool:
    try:
        with open(_CONFIG_PATH) as f:
            return bool(json.load(f).get("combat_logging", False))
    except Exception:
        return False


class CombatLogger:
    """
    Writes turn-by-turn combat logs to a timestamped file.
    All methods are no-ops when combat_logging is disabled in config.json.
    """

    def __init__(self, player: Player, monster: Monster):
        self._file = None
        self._turn = 0
        self._total_dealt = 0
        self._total_taken = 0

        if not _logging_enabled():
            return

        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            safe_player = "".join(c if c.isalnum() else "_" for c in player.name)
            safe_monster = "".join(c if c.isalnum() else "_" for c in monster.name)
            path = _LOG_DIR / f"{ts}_{safe_player}_vs_{safe_monster}.txt"
            self._file = open(path, "w", encoding="utf-8")
        except Exception as e:
            logger.warning(f"CombatLogger: failed to open log file: {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _w(self, line: str) -> None:
        if self._file:
            self._file.write(line + "\n")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_combat_start(self, player: Player, monster: Monster) -> None:
        if not self._file:
            return

        from core.combat.calcs import calculate_hit_chance, calculate_monster_hit_chance

        p_hit = calculate_hit_chance(player, monster)
        m_hit = calculate_monster_hit_chance(player, monster)

        self._w(f"{'=' * 60}")
        self._w(f"COMBAT: {player.name}  vs  {monster.name} (Lv.{monster.level})")
        self._w(f"{'=' * 60}")
        self._w(
            f"[START] Player : HP {player.current_hp}/{player.total_max_hp} | "
            f"Atk {player.get_total_attack()} | Def {player.get_total_defence()} | "
            f"PDR {player.get_total_pdr()}% | FDR {player.get_total_fdr()} | "
            f"Crit {player.get_current_crit_chance()}% | Ward {player.combat_ward}"
        )
        self._w(
            f"[START] Monster: HP {monster.hp}/{monster.max_hp} | "
            f"Atk {monster.attack} | Def {monster.defence} | "
            f"Mods: {', '.join(monster.modifiers) or 'None'}"
        )
        self._w(
            f"[START] Player hit chance: {p_hit * 100:.1f}% | "
            f"Monster hit chance: {m_hit * 100:.1f}%"
        )
        self._w("")

    def log_player_turn(self, result, monster: Monster) -> None:
        if not self._file:
            return

        self._turn += 1
        self._total_dealt += result.damage
        outcome = "CRIT" if result.is_crit else ("HIT" if result.is_hit else "MISS")

        self._w(
            f"[T{self._turn} PLAYER] {outcome} | "
            f"Damage dealt: {result.damage} | "
            f"Monster HP: {monster.hp}/{monster.max_hp}"
        )
        for line in result.log.splitlines():
            if line.strip():
                self._w(f"  {line}")
        self._w("")

    def log_monster_turn(self, result, player: Player) -> None:
        if not self._file:
            return

        self._total_taken += result.hp_damage

        self._w(
            f"[T{self._turn} MONSTER] HP damage: {result.hp_damage} | "
            f"Player HP: {player.current_hp}/{player.total_max_hp} | "
            f"Ward: {player.combat_ward}"
        )
        for line in result.log.splitlines():
            if line.strip():
                self._w(f"  {line}")
        self._w("")

    def log_combat_end(self, player: Player, monster: Monster, outcome: str) -> None:
        if not self._file:
            return

        self._w(f"{'=' * 60}")
        self._w(
            f"END: {outcome.upper()} | Turns: {self._turn} | "
            f"Total dealt: {self._total_dealt} | Total taken: {self._total_taken}"
        )
        self._w(
            f"Player HP: {player.current_hp}/{player.total_max_hp} | "
            f"Monster HP: {monster.hp}/{monster.max_hp}"
        )
        self._w(f"{'=' * 60}")
        self.close()

    def close(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None


# ---------------------------------------------------------------------------
# Debug stat summary — moved from engine.py, kept accessible as engine.log_combat_debug
# ---------------------------------------------------------------------------


def log_combat_debug(player: Player, monster: Monster, log: logging.Logger) -> None:
    """Logs a pre-combat stat summary and theoretical max damage for both sides."""
    p_atk = player.get_total_attack()
    p_def = player.get_total_defence()
    p_crit = player.get_current_crit_chance()

    crit_mult = 2.0
    if player.get_helmet_passive() == "insight":
        lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        crit_mult += lvl * 0.1
    if "Smothering" in monster.modifiers:
        crit_mult *= 0.8
    p_max_dmg = int(p_atk * crit_mult)
    if player.get_glove_passive() == "instability":
        lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
        p_max_dmg = int(p_max_dmg * (1.50 + (lvl * 0.10)))

    m_atk = monster.attack
    m_def = monster.defence

    raw_base = m_atk * max(0.0, 1.0 - p_def / m_atk) if m_atk > 0 else 0.0
    if "Strengthened" in monster.modifiers:
        raw_base *= 1.5
    if "Celestial Watcher" in monster.modifiers:
        raw_base *= 1.2
    if "Hellborn" in monster.modifiers:
        raw_base *= 1.12
    if "Hell's Fury" in monster.modifiers:
        raw_base *= 1.25

    pdr = player.get_total_pdr()
    if "Penetrator" in monster.modifiers:
        pdr = max(0, pdr - 20)
    fdr = player.get_total_fdr()
    if "Clobberer" in monster.modifiers:
        fdr = int(fdr * 0.65)

    m_max_dmg = max(0, int(raw_base * 1.15 * (1 - pdr / 100)) - fdr)
    if (
        "Mirror Image" in monster.modifiers
        or "Unlimited Blade Works" in monster.modifiers
    ):
        m_max_dmg *= 2

    log.info(f"--- COMBAT DEBUG: {player.name} VS {monster.name} ---")
    log.info(
        f"PLAYER : HP {player.current_hp}/{player.max_hp} | Atk {p_atk} | Def {p_def} | "
        f"Ward {player.combat_ward} | Crit {p_crit}% | PDR {player.get_total_pdr()}% | FDR {player.get_total_fdr()}"
    )
    log.info(
        f"MONSTER: HP {monster.hp}/{monster.max_hp} | Atk {m_atk} | Def {m_def} | Mods: {monster.modifiers}"
    )
    log.info(f"THEORETICAL MAX HIT -> Player: ~{p_max_dmg} | Monster: ~{m_max_dmg}")
    log.info("--------------------------------------------------")
