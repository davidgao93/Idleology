"""
Migration: Settlement Plot System
==================================
Introduces the 5×5 grid-based settlement layout.

Changes applied
---------------
  buildings table
    • building_type rename: infernal_forge → infernal_shrine
    • building_type rename: void_sanctum   → void_shrine
    • ADD COLUMN plot_index  INTEGER DEFAULT NULL
    • ADD COLUMN is_meta     INTEGER NOT NULL DEFAULT 0
    • Existing buildings are assigned plot indices derived from slot_index.
      Town Hall → plot_index = 0  (sentinel; TH is fixed at grid centre)
      All other → plot_index = slot_index + 1  (slots 0-19 → plots 1-20)

  users table
    • ADD COLUMN development_contracts  INTEGER NOT NULL DEFAULT 0

  settlement_plots table  (new)
    • 20 rows per settlement, all undeveloped initially.
    • Plots that already have a regular building are marked is_developed = 1
      with bonus_type = 'common_ground'.

Run once
--------
  python scripts/migrate_settlement_plots.py [path/to/game.db]

Safe to re-run: every step is idempotent or guarded.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = "C:/Users/yugao/Idleology/database/database.db"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def _add_column(
    conn: sqlite3.Connection,
    table: str,
    col: str,
    definition: str,
    existing: set[str],
) -> bool:
    if col in existing:
        print(f"    = {table}.{col} already exists — skipped")
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN `{col}` {definition}")
    print(f"    + {table}.{col} added")
    return True


# ---------------------------------------------------------------------------
# Migration steps
# ---------------------------------------------------------------------------


def step_rename_building_types(conn: sqlite3.Connection) -> None:
    print("\n[1] Renaming building types …")

    renames = [
        ("infernal_forge", "infernal_shrine"),
        ("void_sanctum", "void_shrine"),
    ]
    for old, new in renames:
        cur = conn.execute(
            "SELECT COUNT(*) FROM buildings WHERE building_type = ?", (old,)
        )
        count = cur.fetchone()[0]
        if count:
            conn.execute(
                "UPDATE buildings SET building_type = ? WHERE building_type = ?",
                (new, old),
            )
            print(f"    Renamed {count} row(s): {old} → {new}")
        else:
            print(f"    No rows to rename for {old} — skipped")


def step_alter_buildings(conn: sqlite3.Connection) -> None:
    print("\n[2] Altering 'buildings' table …")
    existing = _columns(conn, "buildings")
    _add_column(conn, "buildings", "plot_index", "INTEGER DEFAULT NULL", existing)
    _add_column(conn, "buildings", "is_meta", "INTEGER NOT NULL DEFAULT 0", existing)


def step_alter_users(conn: sqlite3.Connection) -> None:
    print("\n[3] Altering 'users' table …")
    existing = _columns(conn, "users")
    _add_column(
        conn,
        "users",
        "development_contracts",
        "INTEGER NOT NULL DEFAULT 0",
        existing,
    )


def step_create_settlement_plots(conn: sqlite3.Connection) -> None:
    print("\n[4] Creating 'settlement_plots' table …")
    if _table_exists(conn, "settlement_plots"):
        print("    = Table already exists — skipped")
        return

    conn.execute(
        """
        CREATE TABLE settlement_plots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT    NOT NULL,
            server_id    TEXT    NOT NULL,
            plot_index   INTEGER NOT NULL,
            is_developed INTEGER NOT NULL DEFAULT 0,
            bonus_type   TEXT    DEFAULT NULL,
            UNIQUE(user_id, server_id, plot_index)
        )
    """
    )
    print("    + Table created")


def step_assign_plot_indices(conn: sqlite3.Connection) -> None:
    """
    Assign plot_index to existing buildings.

      town_hall → 0   (reserved sentinel; TH lives at grid centre, not a plot)
      everything else → slot_index + 1

    Only touches rows where plot_index IS NULL.
    """
    print("\n[5] Assigning plot_index to existing buildings …")

    # Town Hall → sentinel 0
    conn.execute(
        """
        UPDATE buildings
        SET    plot_index = 0
        WHERE  building_type = 'town_hall'
          AND  plot_index IS NULL
    """
    )

    # Remaining buildings: slot_index + 1
    conn.execute(
        """
        UPDATE buildings
        SET    plot_index = slot_index + 1
        WHERE  plot_index IS NULL
          AND  slot_index IS NOT NULL
          AND  building_type != 'town_hall'
    """
    )

    cur = conn.execute("SELECT COUNT(*) FROM buildings WHERE plot_index IS NOT NULL")
    n = cur.fetchone()[0]
    print(f"    {n} building(s) now have a plot_index")


def step_seed_plots(conn: sqlite3.Connection) -> None:
    """
    For every row in `settlements`, insert the 20 undeveloped plot rows
    (INSERT OR IGNORE — safe to run again).
    Then mark plots that already have a regular building as developed.
    """
    print("\n[6] Seeding settlement_plots rows …")

    # All 20 plots for every settlement (undeveloped by default)
    conn.execute(
        """
        INSERT OR IGNORE INTO settlement_plots (user_id, server_id, plot_index)
        SELECT s.user_id, s.server_id, p.n
        FROM   settlements s
        CROSS JOIN (
            SELECT 1  AS n UNION ALL SELECT 2  UNION ALL SELECT 3  UNION ALL
            SELECT 4  UNION ALL SELECT 5  UNION ALL SELECT 6  UNION ALL
            SELECT 7  UNION ALL SELECT 8  UNION ALL SELECT 9  UNION ALL
            SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL
            SELECT 13 UNION ALL SELECT 14 UNION ALL SELECT 15 UNION ALL
            SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL
            SELECT 19 UNION ALL SELECT 20
        ) p
    """
    )

    cur = conn.execute("SELECT COUNT(*) FROM settlement_plots")
    total = cur.fetchone()[0]
    print(f"    {total} plot row(s) now exist (INSERT OR IGNORE applied)")

    # Develop the plots that already have a non-TH building on them.
    # SQLite UPDATE does not support table aliases — use full table name inside EXISTS.
    conn.execute(
        """
        UPDATE settlement_plots
        SET    is_developed = 1,
               bonus_type   = 'common_ground'
        WHERE  is_developed = 0
          AND  EXISTS (
              SELECT 1
              FROM   buildings b
              WHERE  b.user_id    = settlement_plots.user_id
                AND  b.server_id  = settlement_plots.server_id
                AND  b.plot_index = settlement_plots.plot_index
                AND  b.building_type != 'town_hall'
          )
    """
    )

    cur = conn.execute("SELECT COUNT(*) FROM settlement_plots WHERE is_developed = 1")
    developed = cur.fetchone()[0]
    print(f"    {developed} plot(s) marked developed (common_ground bonus assigned)")


# ---------------------------------------------------------------------------
# Verification report
# ---------------------------------------------------------------------------


def report(conn: sqlite3.Connection) -> None:
    print("\n─── Post-migration summary ───────────────────────────────")

    cur = conn.execute("SELECT COUNT(*) FROM buildings WHERE plot_index IS NULL")
    unassigned = cur.fetchone()[0]
    if unassigned:
        print(f"  ⚠  {unassigned} building(s) still have plot_index = NULL")
        conn.execute(
            "SELECT id, user_id, building_type, slot_index FROM buildings WHERE plot_index IS NULL"
        )
        for row in conn.execute(
            "SELECT id, user_id, building_type, slot_index "
            "FROM buildings WHERE plot_index IS NULL LIMIT 20"
        ):
            print(f"      id={row[0]} user={row[1]} type={row[2]} slot={row[3]}")
    else:
        print("  ✓  All buildings have a plot_index")

    cur = conn.execute(
        "SELECT COUNT(*) FROM buildings "
        "WHERE building_type IN ('infernal_forge', 'void_sanctum')"
    )
    old_names = cur.fetchone()[0]
    if old_names:
        print(f"  ⚠  {old_names} building(s) still use deprecated building_type names")
    else:
        print("  ✓  No deprecated building_type names remain")

    cur = conn.execute("SELECT COUNT(*) FROM settlement_plots")
    plots = cur.fetchone()[0]
    cur2 = conn.execute("SELECT COUNT(*) FROM settlement_plots WHERE is_developed = 1")
    developed = cur2.fetchone()[0]
    print(f"  ✓  settlement_plots: {plots} total, {developed} developed")

    cur = conn.execute(
        "SELECT COUNT(DISTINCT user_id || '|' || server_id) FROM settlements"
    )
    settlements = cur.fetchone()[0]
    expected_plots = settlements * 20
    if plots < expected_plots:
        print(
            f"  ⚠  Expected {expected_plots} plot rows ({settlements} settlements × 20),"
            f" found {plots} — re-run to fix"
        )

    print("──────────────────────────────────────────────────────────")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def migrate(db_path: str) -> None:
    path = Path(db_path)
    if not path.exists():
        print(f"ERROR: database not found at {path.resolve()}")
        sys.exit(1)

    print(f"Database: {path.resolve()}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")  # allow ALTER TABLE freely

    try:
        conn.execute("BEGIN")

        step_rename_building_types(conn)
        step_alter_buildings(conn)
        step_alter_users(conn)
        step_create_settlement_plots(conn)
        step_assign_plot_indices(conn)
        step_seed_plots(conn)

        conn.execute("COMMIT")
        print("\n✅ Migration committed successfully.")
    except Exception as exc:
        conn.execute("ROLLBACK")
        print(f"\n❌ Migration ROLLED BACK due to error: {exc}")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        report(conn)
        conn.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    migrate(path)
