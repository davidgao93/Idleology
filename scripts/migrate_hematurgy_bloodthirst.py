"""
Migration script: renames two hematurgy passives with conflicting display names.

  bloodthirst  → crimson_feast
    Resolves conflict with the Codex Tome passive "Bloodthirst" (heal % of crit damage).
    The Hematurgy version (on kill: restore % Max HP) is the one being renamed.

  tenacity     → defiance
    Resolves conflict with the Codex Tome passive "Tenacity" (% chance per hit to halve damage).
    The Hematurgy version (below 40% HP: permanent +ATK/DEF) is the one being renamed.

Safe to run on databases that have already been migrated (UPDATE affects 0 rows).
Run once: python scripts/migrate_hematurgy_bloodthirst.py
"""

import sqlite3
import sys

DB_PATH = "C:/Users/yugao/Idleology/database/database.db"

RENAMES = [
    ("bloodthirst", "crimson_feast"),
    ("tenacity", "defiance"),
]


def migrate(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        total = 0
        for old, new in RENAMES:
            cur = con.execute(
                "UPDATE hematurgy_passives SET passive_id = ? WHERE passive_id = ?",
                (new, old),
            )
            rows = cur.rowcount
            total += rows
            print(f"  {rows} row(s): {old} → {new}")
        con.commit()
        print(f"Migration complete — {total} total row(s) updated.")
    except Exception as exc:
        con.rollback()
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        con.close()


if __name__ == "__main__":
    migrate(DB_PATH)
