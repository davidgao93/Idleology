"""
Black Market logging — writes per-deal logs to logs/black_market/ when enabled.

Toggle via config.json:  "bm_logging": true
"""

import json
import logging
from datetime import datetime
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "black_market"

logger = logging.getLogger("discord_bot")


def _logging_enabled() -> bool:
    try:
        with open(_CONFIG_PATH) as f:
            return bool(json.load(f).get("bm_logging", False))
    except Exception:
        return False


class BMLogger:
    """
    Writes BM deal logs to a timestamped file.
    All methods are no-ops when bm_logging is disabled in config.json.
    """

    def __init__(self, user_id: str, value: int, turns: int):
        self._file = None

        if not _logging_enabled():
            return

        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            safe_uid = "".join(c if c.isalnum() else "_" for c in str(user_id))
            path = _LOG_DIR / f"{ts}_bm_{safe_uid}.txt"
            self._file = open(path, "w", encoding="utf-8", buffering=1)
        except Exception as e:
            logger.warning(f"BMLogger: failed to open log file: {e}")
            return

        self._w(f"{'=' * 60}")
        self._w(f"BLACK MARKET DEAL  user={user_id}  value={value:,}  turns={turns}")
        self._w(f"{'=' * 60}")

    def _w(self, line: str) -> None:
        if self._file:
            self._file.write(line + "\n")

    def log_offer(self, offer: dict, raw_value: int, event_bonus: float) -> None:
        if not self._file:
            return
        self._w("[OFFER]")
        for k, v in offer.items():
            if v > 0:
                self._w(f"  {k}: {v:,}")
        self._w(f"  raw_value={raw_value:,}  event_bonus={event_bonus * 100:.1f}%")

    def log_tree(self, tree_nodes: dict, active_biases: list[str]) -> None:
        if not self._file:
            return
        self._w("[PASSIVE TREE]")
        if tree_nodes:
            for k, v in sorted(tree_nodes.items()):
                self._w(f"  {k}: {v}")
        else:
            self._w("  (empty)")
        self._w(f"[ACTIVE BIASES] {', '.join(active_biases) or 'none'}")

    def log_roll_plan(self, base_rolls: int, extra_rolls: list[str]) -> None:
        if not self._file:
            return
        self._w(f"[ROLLS] base={base_rolls}  extra_bias={len(extra_rolls)}")
        if extra_rolls:
            self._w(f"  extra categories: {', '.join(extra_rolls)}")

    def log_roll(self, roll_num: int, category: str, sub_type: str, qty: int) -> None:
        if not self._file:
            return
        self._w(f"  [{roll_num:03d}] cat={category:<12} sub={sub_type:<25} qty={qty}")

    def log_summary(self, rewards: dict) -> None:
        if not self._file:
            return
        self._w("[TOTALS]")
        if rewards.get("gold"):
            self._w(f"  gold: {rewards['gold']:,}")
        for cur, qty in rewards.get("currencies", {}).items():
            self._w(f"  {cur}: {qty:,}")
        for item in rewards.get("items", []):
            self._w(f"  gear: {item.get('type', '?')} lv{item.get('level', '?')}")
        self._w(f"{'=' * 60}")

    def close(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
