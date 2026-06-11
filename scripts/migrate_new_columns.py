"""
Migration script: adds new columns introduced in schema.sql updates.
Safe to run on existing databases (idempotent via PRAGMA column checks).
Run once: python scripts/migrate_new_columns.py

Columns are taken from the commented "-- ALTER TABLE ..." notes at the
end of database/schema.sql (plus prior ones this script has historically
managed). Tables that do not yet exist in the target DB are skipped
(they will be created with the full current schema by init_db / schema.sql).
"""

import sqlite3
import sys

DB_PATH = "C:/Users/yugao/Idleology/database/database.db"  # adjust if different

# Format: (table_name, column_name, column_definition)
# Pulled from trailing ALTER notes in database/schema.sql + previous entries.
COLUMN_ADDITIONS = [
    # users table
    ("users", "hard_mode", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "combat_streak", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "pending_stat_packages", "TEXT DEFAULT NULL"),
    ("users", "stat_invest_atk", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "stat_invest_def", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "stat_invest_hp", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "stat_invest_gold", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "rune_of_regret", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "diviners_rod", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "auto_rest_pay", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "runes_of_nature", "INTEGER NOT NULL DEFAULT 0"),
    # New from end of schema.sql (Gathering / Settlement expansion)
    ("users", "settlement_zeal", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "idlem", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "zeal_earned_today", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "last_zeal_reset", "TEXT DEFAULT NULL"),
    # gathering_mastery (Nature's Attunement + post-max insight)
    ("gathering_mastery", "attunement_alloc", "TEXT DEFAULT '{}'"),
    ("gathering_mastery", "mastery_insight", "INTEGER DEFAULT 0"),
    # Skill tables: Gathering Expansion (familiarization + momentum)
    ("mining", "familiarization_end", "TEXT DEFAULT NULL"),
    ("mining", "momentum_minutes", "INTEGER DEFAULT 0"),
    ("fishing", "familiarization_end", "TEXT DEFAULT NULL"),
    ("fishing", "momentum_minutes", "INTEGER DEFAULT 0"),
    ("woodcutting", "familiarization_end", "TEXT DEFAULT NULL"),
    ("woodcutting", "momentum_minutes", "INTEGER DEFAULT 0"),
    # settlements table (development turns / zeal)
    ("settlements", "total_development_turns", "INTEGER NOT NULL DEFAULT 0"),
    ("settlements", "pending_zeal", "INTEGER NOT NULL DEFAULT 0"),
]


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    added = []
    current_table = None
    existing_cols = set()

    for table, col, definition in COLUMN_ADDITIONS:
        if table != current_table:
            current_table = table
            print(f"\nTable: {table}")

            # Skip tables that don't exist in this DB (they'll be created
            # with the complete current schema by schema.sql / init_db).
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if not cursor.fetchone():
                print(
                    "  ! Table does not exist — skipping (full table will come from schema.sql)."
                )
                existing_cols = set()
                continue

            cursor.execute(f"PRAGMA table_info(`{table}`)")
            existing_cols = {row[1] for row in cursor.fetchall()}

        if col in existing_cols:
            print(f"  = Already exists: {col}")
            continue

        try:
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {definition}")
            added.append(f"{table}.{col}")
            print(f"  + Added column: {col}")
        except Exception as e:
            print(f"  ! Failed to add {col} to {table}: {e}")

    conn.commit()
    conn.close()
    print(f"\nDone. {len(added)} column(s) added.")
    if added:
        print("  Added:", ", ".join(added))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    print(f"Migrating: {path}")
    migrate(path)
