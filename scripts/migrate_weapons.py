"""
scripts/migrate_weapons.py
==========================
One-time migration for the weapon base template rework.

Run AFTER adding the new columns to the DB:
    ALTER TABLE items ADD COLUMN hit_chance   REAL    NOT NULL DEFAULT 0.60;
    ALTER TABLE items ADD COLUMN crit_chance  REAL    NOT NULL DEFAULT 0.00;
    ALTER TABLE items ADD COLUMN crit_multi   REAL    NOT NULL DEFAULT 2.00;
    ALTER TABLE items ADD COLUMN base_rarity  INTEGER NOT NULL DEFAULT 3;

Then run:
    python scripts/migrate_weapons.py [path/to/database.db]

Default DB path: database/idleology.db
"""

import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "database/idleology.db"

# ---------------------------------------------------------------------------
# Job A — Apply Premium Balanced template to all existing weapons.
# All existing weapons get the Premium Balanced defaults (★★★).
# New weapons will have their template selected at drop time.
# ---------------------------------------------------------------------------
TEMPLATE_DEFAULTS = {
    "hit_chance": 0.60,
    "crit_chance": 0.05,
    "crit_multi": 2.00,
    "base_rarity": 3,
}

# ---------------------------------------------------------------------------
# Job B — Convert old-style passive names to family_tier format.
# Applied to all three passive columns on the items table.
# ---------------------------------------------------------------------------
PASSIVE_RENAME: dict[str, str] = {
    # Burning family
    "burning": "burning_1",
    "flaming": "burning_2",
    "scorching": "burning_3",
    "incinerating": "burning_4",
    "carbonising": "burning_5",
    # Poison family (was Poisonous)
    "poisonous": "poison_1",
    "noxious": "poison_2",
    "venomous": "poison_3",
    "toxic": "poison_4",
    "lethal": "poison_5",
    # Debilitate family (was Polished)
    "polished": "debilitate_1",
    "honed": "debilitate_2",
    "gleaming": "debilitate_3",
    "tempered": "debilitate_4",
    "flaring": "debilitate_5",
    # Shocking family (was Sparking)
    "sparking": "shocking_1",
    "shocking": "shocking_2",
    "discharging": "shocking_3",
    "electrocuting": "shocking_4",
    "vapourising": "shocking_5",
    # Sturdy family
    "sturdy": "sturdy_1",
    "reinforced": "sturdy_2",
    "thickened": "sturdy_3",
    "impregnable": "sturdy_4",
    "impenetrable": "sturdy_5",
    # Piercing family
    "piercing": "piercing_1",
    "keen": "piercing_2",
    "incisive": "piercing_3",
    "puncturing": "piercing_4",
    "penetrating": "piercing_5",
    # Cull family (was Strengthened)
    "strengthened": "cull_1",
    "forceful": "cull_2",
    "overwhelming": "cull_3",
    "devastating": "cull_4",
    "catastrophic": "cull_5",
    # Deadeye family (was Accurate)
    "accurate": "deadeye_1",
    "precise": "deadeye_2",
    "sharpshooter": "deadeye_3",
    "deadeye": "deadeye_4",
    "bullseye": "deadeye_5",
    # Echo family
    "echo": "echo_1",
    "echoo": "echo_2",
    "echooo": "echo_3",
    "echoooo": "echo_4",
    "echoes": "echo_5",
}

PASSIVE_COLUMNS = ("passive", "pinnacle_passive", "utmost_passive")


def run_migration(db_path: str) -> None:
    print(f"Connecting to: {db_path}")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # ── Job A: template defaults ─────────────────────────────────────────────
    print("\n[Job A] Applying Premium Balanced template to all existing weapons...")
    cur.execute(
        """UPDATE items SET
            hit_chance  = :hit_chance,
            crit_chance = :crit_chance,
            crit_multi  = :crit_multi,
            base_rarity = :base_rarity""",
        TEMPLATE_DEFAULTS,
    )
    print(f"  Updated {cur.rowcount} weapon rows.")

    # ── Job B: passive name conversion ──────────────────────────────────────
    print("\n[Job B] Converting old passive names to family_tier format...")
    total_updated = 0
    for col in PASSIVE_COLUMNS:
        for old_name, new_name in PASSIVE_RENAME.items():
            cur.execute(
                f"UPDATE items SET {col} = ? WHERE {col} = ?",
                (new_name, old_name),
            )
            if cur.rowcount:
                print(f"  {col}: '{old_name}' → '{new_name}' ({cur.rowcount} rows)")
                total_updated += cur.rowcount
    print(f"  Total passive conversions: {total_updated}")

    con.commit()
    con.close()
    print("\nMigration complete.")
    print(
        "\nNote: combat file key references (player_turn.py, passives.py) still use"
        " the old family keys and will be updated in phase 2."
    )


if __name__ == "__main__":
    run_migration(DB_PATH)
