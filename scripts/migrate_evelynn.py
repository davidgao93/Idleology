"""
scripts/migrate_evelynn.py
==========================
One-time migration adding Evelynn uber-boss columns to uber_progress.

The two new columns are already part of schema.sql for fresh installs.
Run this script once against any existing live database.

Usage:
    python scripts/migrate_evelynn.py [path/to/database.db]

Default DB path: database/idleology.db
"""

import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "database/database.db"

COLUMNS = [
    ("corruption_engrams", "INTEGER DEFAULT 0"),
    ("corruption_blueprint_unlocked", "INTEGER DEFAULT 0"),
]

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

existing = {row[1] for row in cursor.execute("PRAGMA table_info(uber_progress)")}

added = 0
for col_name, col_def in COLUMNS:
    if col_name not in existing:
        cursor.execute(f"ALTER TABLE uber_progress ADD COLUMN {col_name} {col_def}")
        print(f"  + Added column: {col_name} {col_def}")
        added += 1
    else:
        print(f"  - Skipped (already exists): {col_name}")

conn.commit()
conn.close()

print(f"\nDone — {added} column(s) added to uber_progress.")
