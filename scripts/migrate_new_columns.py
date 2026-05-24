"""
Migration script: adds new columns introduced in this update.
Safe to run on existing databases — uses IF NOT EXISTS / IGNORE logic.
Run once: python scripts/migrate_new_columns.py
"""

import sqlite3
import sys

DB_PATH = "C:/Users/yugao/Idleology/database/database.db"  # adjust if different

NEW_COLUMNS = [
    ("hard_mode", "INTEGER NOT NULL DEFAULT 0"),
    ("combat_streak", "INTEGER NOT NULL DEFAULT 0"),
    ("pending_stat_packages", "TEXT DEFAULT NULL"),
    ("stat_invest_atk", "INTEGER NOT NULL DEFAULT 0"),
    ("stat_invest_def", "INTEGER NOT NULL DEFAULT 0"),
    ("stat_invest_hp", "INTEGER NOT NULL DEFAULT 0"),
    ("stat_invest_gold", "INTEGER NOT NULL DEFAULT 0"),
    ("rune_of_regret", "INTEGER NOT NULL DEFAULT 0"),
]


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    existing = {row[1] for row in cursor.fetchall()}

    added = []
    for col, definition in NEW_COLUMNS:
        if col not in existing:
            cursor.execute(f"ALTER TABLE users ADD COLUMN `{col}` {definition}")
            added.append(col)
            print(f"  + Added column: {col}")
        else:
            print(f"  = Already exists: {col}")

    conn.commit()
    conn.close()
    print(f"\nDone. {len(added)} column(s) added.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    print(f"Migrating: {path}")
    migrate(path)
