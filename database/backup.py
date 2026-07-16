"""
database/backup.py — Hot database backups for rollback safety.

Uses sqlite3's built-in Connection.backup() API, which safely snapshots the
database file even while the bot's aiosqlite connection holds it open under
WAL mode. Pure/sync file I/O — callers should run create_backup() off the
event loop thread (see bot.py's backup_task, which wraps it in asyncio.to_thread).
"""

import os
import sqlite3
import time

BACKUP_PREFIX = "database_"
BACKUP_SUFFIX = ".db"


def create_backup(db_path: str, backup_dir: str, keep: int) -> str:
    """Creates a timestamped hot-backup copy of db_path inside backup_dir, then
    prunes older backups beyond `keep`. Returns the path of the new backup."""
    os.makedirs(backup_dir, exist_ok=True)
    # Microsecond precision avoids collisions if called more than once per second
    # (e.g. an admin manually triggering a backup right after the scheduled one).
    timestamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1_000_000) % 1_000_000:06d}"
    backup_path = os.path.join(backup_dir, f"{BACKUP_PREFIX}{timestamp}{BACKUP_SUFFIX}")

    source = sqlite3.connect(db_path, timeout=30)
    try:
        dest = sqlite3.connect(backup_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    _prune_old_backups(backup_dir, keep)
    return backup_path


def _prune_old_backups(backup_dir: str, keep: int) -> None:
    backups = sorted(
        f
        for f in os.listdir(backup_dir)
        if f.startswith(BACKUP_PREFIX) and f.endswith(BACKUP_SUFFIX)
    )
    excess = len(backups) - keep
    for name in backups[: max(0, excess)]:
        try:
            os.remove(os.path.join(backup_dir, name))
        except OSError:
            pass


def list_backups(backup_dir: str) -> list[str]:
    """Returns backup filenames (oldest first), or an empty list if the dir doesn't exist."""
    if not os.path.isdir(backup_dir):
        return []
    return sorted(
        f
        for f in os.listdir(backup_dir)
        if f.startswith(BACKUP_PREFIX) and f.endswith(BACKUP_SUFFIX)
    )
