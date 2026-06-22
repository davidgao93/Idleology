# database/repositories/settlement.py

import json
import aiosqlite

from core.models import Building, Settlement


class SettlementRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def migrate_buildings_schema(self) -> None:
        """Add new columns to the buildings table for existing databases."""
        try:
            await self.connection.execute(
                "ALTER TABLE buildings ADD COLUMN is_disabled INTEGER NOT NULL DEFAULT 0"
            )
            await self.connection.commit()
        except Exception:
            pass  # column already exists

    async def get_settlement(self, user_id: str, server_id: str) -> Settlement:
        cursor = await self.connection.execute(
            "SELECT user_id, server_id, town_hall_tier, building_slots, timber, stone, last_collection_time, last_zeal_gather_time FROM settlements WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()

        if not row:
            # Create Default
            await self.connection.execute(
                "INSERT INTO settlements (user_id, server_id, town_hall_tier, building_slots, last_collection_time) VALUES (?, ?, 1, 5, datetime('now'))",
                (user_id, server_id),
            )
            await self.connection.commit()
            return await self.get_settlement(user_id, server_id)

        # Fetch Buildings
        settlement = Settlement(
            user_id=row[0],
            server_id=row[1],
            town_hall_tier=row[2],
            building_slots=row[3],
            timber=row[4],
            stone=row[5],
            last_collection_time=row[6],
            last_zeal_gather_time=row[7],
        )

        b_cursor = await self.connection.execute(
            "SELECT id, user_id, server_id, building_type, tier, slot_index, "
            "workers_assigned, plot_index, is_meta, COALESCE(is_disabled, 0) "
            "FROM buildings WHERE user_id = ? AND server_id = ? "
            "ORDER BY COALESCE(plot_index, slot_index) ASC",
            (user_id, server_id),
        )
        b_rows = await b_cursor.fetchall()
        settlement.buildings = [
            Building(
                id=r[0],
                user_id=r[1],
                server_id=r[2],
                building_type=r[3],
                tier=r[4],
                slot_index=r[5],
                workers_assigned=r[6],
                plot_index=r[7],
                is_meta=bool(r[8]),
                is_disabled=bool(r[9]),
            )
            for r in b_rows
        ]

        return settlement

    async def build_structure(
        self,
        user_id: str,
        server_id: str,
        b_type: str,
        plot_index: int,
        is_meta: bool = False,
    ) -> None:
        """Insert a new building on *plot_index*. slot_index mirrors plot_index."""
        await self.connection.execute(
            "INSERT INTO buildings "
            "(user_id, server_id, building_type, slot_index, plot_index, is_meta) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, server_id, b_type, plot_index, plot_index, int(is_meta)),
        )
        await self.connection.commit()

    async def assign_workers(self, building_id: int, count: int) -> None:
        await self.connection.execute(
            "UPDATE buildings SET workers_assigned = ? WHERE id = ?",
            (count, building_id),
        )
        await self.connection.commit()

    async def disable_building(self, building_id: int) -> None:
        await self.connection.execute(
            "UPDATE buildings SET is_disabled = 1 WHERE id = ?",
            (building_id,),
        )
        await self.connection.commit()

    async def repair_building(self, building_id: int) -> None:
        await self.connection.execute(
            "UPDATE buildings SET is_disabled = 0 WHERE id = ?",
            (building_id,),
        )
        await self.connection.commit()

    async def get_building_by_type(
        self, user_id: str, server_id: str, building_type: str
    ):
        """Returns the first building row matching building_type, or None."""
        from core.settlement.models import Building

        cursor = await self.connection.execute(
            "SELECT id, user_id, server_id, building_type, tier, slot_index, "
            "workers_assigned, plot_index, is_meta, COALESCE(is_disabled, 0) "
            "FROM buildings WHERE user_id = ? AND server_id = ? AND building_type = ? LIMIT 1",
            (user_id, server_id, building_type),
        )
        r = await cursor.fetchone()
        if not r:
            return None
        return Building(
            id=r[0],
            user_id=r[1],
            server_id=r[2],
            building_type=r[3],
            tier=r[4],
            slot_index=r[5],
            workers_assigned=r[6],
            plot_index=r[7],
            is_meta=bool(r[8]),
            is_disabled=bool(r[9]),
        )

    async def update_collection_timer(self, user_id: str, server_id: str):
        """Updates collection timer using Python time for consistency."""
        from datetime import datetime

        current_time = datetime.now().isoformat()

        await self.connection.execute(
            "UPDATE settlements SET last_collection_time = ? WHERE user_id = ? AND server_id = ?",
            (current_time, user_id, server_id),
        )
        await self.connection.commit()

    async def update_zeal_gather_time(self, user_id: str, server_id: str) -> str:
        """Stamps last_zeal_gather_time to now; returns the ISO timestamp."""
        from datetime import datetime

        ts = datetime.now().isoformat()
        await self.connection.execute(
            "UPDATE settlements SET last_zeal_gather_time = ? WHERE user_id = ? AND server_id = ?",
            (ts, user_id, server_id),
        )
        await self.connection.commit()
        return ts

    async def commit_production(self, user_id: str, server_id: str, changes: dict):
        """
        Applies a batch of resource changes (Mining, Woodcutting, Fishing, Gold, Settlement).
        This is a complex transaction crossing multiple tables.
        """
        # 1. Settlement Resources
        if "timber" in changes or "stone" in changes:
            t = changes.pop("timber", 0)
            s = changes.pop("stone", 0)
            await self.connection.execute(
                "UPDATE settlements SET timber = timber + ?, stone = stone + ? WHERE user_id = ? AND server_id = ?",
                (t, s, user_id, server_id),
            )

        # 3. Skills (Mining, Woodcutting, Fishing)
        # We need to sort keys by table
        # Allowed columns are defined in SkillRepository, but we can infer or hardcode mapping here
        # or call SkillRepository methods. Calling direct SQL here for atomicity is acceptable
        # given the strict MVC rules allow Repo to handle SQL.

        # Mappings based on prefixes or known lists
        tables = {
            "mining": [
                "iron",
                "iron_bar",
                "coal",
                "steel_bar",
                "gold",
                "gold_bar",
                "platinum",
                "platinum_bar",
                "idea",
                "idea_bar",
            ],
            "woodcutting": [
                "oak_logs",
                "oak_plank",
                "willow_logs",
                "willow_plank",
                "mahogany_logs",
                "mahogany_plank",
                "magic_logs",
                "magic_plank",
                "idea_logs",
                "idea_plank",
            ],
            "fishing": [
                "desiccated_bones",
                "desiccated_essence",
                "regular_bones",
                "regular_essence",
                "sturdy_bones",
                "sturdy_essence",
                "reinforced_bones",
                "reinforced_essence",
                "titanium_bones",
                "titanium_essence",
            ],
        }

        for table, cols in tables.items():
            updates = []
            values = []
            for col in cols:
                if col in changes:
                    val = changes[col]
                    updates.append(f"{col} = {col} + ?")
                    values.append(val)

            if updates:
                sql = f"UPDATE {table} SET {', '.join(updates)} WHERE user_id = ? AND server_id = ?"
                values.extend([user_id, server_id])
                await self.connection.execute(sql, tuple(values))

        await self.connection.commit()

    async def get_building_tier(
        self, user_id: str, server_id: str, building_type: str
    ) -> int:
        """
        Efficiently fetches the tier of a specific building type.
        Returns 0 if building does not exist.
        """
        cursor = await self.connection.execute(
            "SELECT tier FROM buildings WHERE user_id = ? AND server_id = ? AND building_type = ?",
            (user_id, server_id, building_type),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_building_details(
        self, user_id: str, server_id: str, building_type: str
    ) -> tuple[int, int]:
        """
        Fetches the (tier, workers_assigned) of a specific building.
        Returns (0, 0) if the building does not exist.
        """
        cursor = await self.connection.execute(
            "SELECT tier, workers_assigned FROM buildings WHERE user_id = ? AND server_id = ? AND building_type = ?",
            (user_id, server_id, building_type),
        )
        row = await cursor.fetchone()
        return row if row else (0, 0)

    async def get_combat_bonuses(self, user_id: str, server_id: str) -> dict:
        """
        Computes settlement adjacency and plot bonuses that affect live combat:

        - ``apothecary_boost_pct``: additive multiplier on the Apothecary's flat
          heal bonus (from an adjacent Apothecary Annex meta building).
        - ``shrine_effectiveness``: dict mapping each sigil-shrine building type
          to a float multiplier (≥ 1.0) applied to the per-worker second-sigil
          drop chance (from ``sacred_ground`` plot bonus and/or an adjacent
          Shrine Garden meta building).

        Returns default values (all bonuses zero / empty) when the player has no
        settlement, no relevant buildings, or the tables do not yet exist.
        """
        from core.settlement.mechanics import SettlementMechanics
        from core.settlement.models import Building, Plot
        from core.settlement.plots import PLOT_BONUS_TABLE

        _DEFAULT = {"apothecary_boost_pct": 0.0, "shrine_effectiveness": {}}

        # Load all buildings
        try:
            b_cursor = await self.connection.execute(
                "SELECT id, user_id, server_id, building_type, tier, slot_index, "
                "workers_assigned, plot_index, is_meta, COALESCE(is_disabled, 0) "
                "FROM buildings WHERE user_id = ? AND server_id = ?",
                (user_id, server_id),
            )
            buildings = [
                Building(
                    id=r[0],
                    user_id=r[1],
                    server_id=r[2],
                    building_type=r[3],
                    tier=r[4],
                    slot_index=r[5],
                    workers_assigned=r[6],
                    plot_index=r[7],
                    is_meta=bool(r[8]),
                    is_disabled=bool(r[9]),
                )
                for r in await b_cursor.fetchall()
            ]
        except Exception:
            return _DEFAULT

        if not buildings:
            return _DEFAULT

        # Load all plots (may not exist for brand-new players)
        try:
            p_cursor = await self.connection.execute(
                "SELECT plot_index, is_developed, bonus_type "
                "FROM settlement_plots WHERE user_id = ? AND server_id = ?",
                (user_id, server_id),
            )
            plots = [
                Plot(plot_index=r[0], is_developed=bool(r[1]), bonus_type=r[2])
                for r in await p_cursor.fetchall()
            ]
        except Exception:
            plots = []

        adj_bonuses = SettlementMechanics.calculate_adjacency_bonuses(plots, buildings)
        plot_bonus_by_idx = {
            p.plot_index: p.bonus_type for p in plots if p.is_developed
        }

        # --- Apothecary Annex boost ---
        apothecary_boost_pct = 0.0
        for b in buildings:
            if b.building_type == "apothecary" and b.plot_index is not None:
                apothecary_boost_pct = adj_bonuses.get(b.plot_index, {}).get(
                    "apothecary_boost", 0.0
                )
                break

        # --- Shrine effectiveness (sigil shrines only; temple is excluded) ---
        _SIGIL_SHRINES = frozenset(
            {
                "celestial_shrine",
                "infernal_shrine",
                "void_shrine",
                "twin_shrine",
                "corruption_shrine",
                "uber_shrine",
            }
        )
        sacred_ground_val = PLOT_BONUS_TABLE.get("sacred_ground", {}).get("value", 0.20)
        shrine_effectiveness: dict[str, float] = {}
        for b in buildings:
            if b.building_type in _SIGIL_SHRINES and b.plot_index is not None:
                eff = 1.0
                if plot_bonus_by_idx.get(b.plot_index) == "sacred_ground":
                    eff += sacred_ground_val
                eff += adj_bonuses.get(b.plot_index, {}).get("shrine_boost", 0.0)
                shrine_effectiveness[b.building_type] = eff

        # Uber Shrine consolidates all five individual shrines. Expose its
        # effectiveness under each individual shrine key so drop-rate lookups
        # that query by shrine type work for both old and new owners.
        if "uber_shrine" in shrine_effectiveness:
            uber_eff = shrine_effectiveness["uber_shrine"]
            for _key in (
                "celestial_shrine",
                "infernal_shrine",
                "void_shrine",
                "twin_shrine",
                "corruption_shrine",
            ):
                shrine_effectiveness.setdefault(_key, uber_eff)

        return {
            "apothecary_boost_pct": apothecary_boost_pct,
            "shrine_effectiveness": shrine_effectiveness,
        }

    async def get_used_slots_count(self, user_id: str, server_id: str) -> int:
        """Counts how many *regular* (non-meta) buildings a user has constructed."""
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM buildings "
            "WHERE user_id = ? AND server_id = ? AND is_meta = 0",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Research
    # ------------------------------------------------------------------

    async def get_researched(self, user_id: str, server_id: str) -> set[str]:
        """Returns the set of building types that have been fully researched."""
        cursor = await self.connection.execute(
            "SELECT building_type FROM settlement_research WHERE user_id = ? AND server_id = ? AND completed = 1",
            (user_id, server_id),
        )
        rows = await cursor.fetchall()
        return {r[0] for r in rows}

    async def get_active_research(self, user_id: str, server_id: str):
        """Returns (building_type, start_time) for in-progress research, or None."""
        cursor = await self.connection.execute(
            "SELECT building_type, start_time FROM settlement_research "
            "WHERE user_id = ? AND server_id = ? AND completed = 0 AND start_time != ''",
            (user_id, server_id),
        )
        return await cursor.fetchone()

    async def start_research(
        self, user_id: str, server_id: str, building_type: str, start_time: str
    ) -> None:
        await self.connection.execute(
            """INSERT INTO settlement_research (user_id, server_id, building_type, start_time, completed)
               VALUES (?, ?, ?, ?, 0)
               ON CONFLICT(user_id, server_id, building_type) DO UPDATE SET
                   start_time = excluded.start_time,
                   completed  = 0""",
            (user_id, server_id, building_type, start_time),
        )
        await self.connection.commit()

    async def complete_research(
        self, user_id: str, server_id: str, building_type: str
    ) -> None:
        await self.connection.execute(
            "UPDATE settlement_research SET completed = 1, start_time = '' "
            "WHERE user_id = ? AND server_id = ? AND building_type = ?",
            (user_id, server_id, building_type),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Building mutations
    # ------------------------------------------------------------------

    async def demolish_building(self, building_id: int) -> None:
        await self.connection.execute(
            "DELETE FROM buildings WHERE id = ?", (building_id,)
        )
        await self.connection.commit()

    async def upgrade_building_tier(self, building_id: int) -> None:
        await self.connection.execute(
            "UPDATE buildings SET tier = tier + 1 WHERE id = ?", (building_id,)
        )
        await self.connection.commit()

    async def expand_building_slots(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "UPDATE settlements SET building_slots = building_slots + 1 WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def upgrade_town_hall(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "UPDATE settlements SET town_hall_tier = town_hall_tier + 1, building_slots = building_slots + 1 "
            "WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Settlement Turns Economy
    # ------------------------------------------------------------------

    async def get_turns_data(self, user_id: str, server_id: str) -> dict:
        """Returns {total_development_turns, pending_zeal} for the settlement."""
        _default = {"total_development_turns": 0, "pending_zeal": 0}
        try:
            cursor = await self.connection.execute(
                "SELECT total_development_turns, pending_zeal FROM settlements "
                "WHERE user_id = ? AND server_id = ?",
                (user_id, server_id),
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "total_development_turns": row[0] or 0,
                    "pending_zeal": row[1] or 0,
                }
        except Exception:
            pass
        return _default

    async def increment_turns(
        self, user_id: str, server_id: str, amount: int = 1
    ) -> None:
        try:
            await self.connection.execute(
                "UPDATE settlements SET total_development_turns = total_development_turns + ? "
                "WHERE user_id = ? AND server_id = ?",
                (amount, user_id, server_id),
            )
            await self.connection.commit()
        except Exception:
            pass

    async def add_pending_zeal(self, user_id: str, server_id: str, amount: int) -> None:
        from core.settlement.constants import ZEAL_GATHER_CAP
        try:
            await self.connection.execute(
                "UPDATE settlements SET pending_zeal = MIN(pending_zeal + ?, ?) "
                "WHERE user_id = ? AND server_id = ?",
                (amount, ZEAL_GATHER_CAP, user_id, server_id),
            )
            await self.connection.commit()
        except Exception:
            pass

    async def collect_pending_zeal(self, user_id: str, server_id: str) -> int:
        """Transfers all pending_zeal to user.settlement_zeal; returns amount collected."""
        try:
            cursor = await self.connection.execute(
                "SELECT pending_zeal FROM settlements WHERE user_id = ? AND server_id = ?",
                (user_id, server_id),
            )
            row = await cursor.fetchone()
            amount = (row[0] or 0) if row else 0
            if amount <= 0:
                return 0
            await self.connection.execute(
                "UPDATE settlements SET pending_zeal = 0 WHERE user_id = ? AND server_id = ?",
                (user_id, server_id),
            )
            await self.connection.execute(
                "UPDATE users SET settlement_zeal = settlement_zeal + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await self.connection.commit()
            return amount
        except Exception:
            return 0

    async def spend_pending_zeal(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Deducts *amount* from pending_zeal (floors at 0). Does NOT credit settlement_zeal."""
        await self.connection.execute(
            "UPDATE settlements SET pending_zeal = MAX(0, pending_zeal - ?) "
            "WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def collect_capped_pending_zeal(
        self, user_id: str, server_id: str, cap: int
    ) -> int:
        """
        Collects up to *cap* from pending_zeal into settlement_zeal.
        Returns the amount actually collected.
        Does NOT update zeal_earned_today (passive income, not active gain).
        """
        try:
            cursor = await self.connection.execute(
                "SELECT pending_zeal FROM settlements WHERE user_id = ? AND server_id = ?",
                (user_id, server_id),
            )
            row = await cursor.fetchone()
            pending = (row[0] or 0) if row else 0
            amount = min(pending, cap)
            if amount <= 0:
                return 0
            await self.connection.execute(
                "UPDATE settlements SET pending_zeal = pending_zeal - ? "
                "WHERE user_id = ? AND server_id = ?",
                (amount, user_id, server_id),
            )
            await self.connection.execute(
                "UPDATE users SET settlement_zeal = settlement_zeal + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await self.connection.commit()
            return amount
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Zeal & Idlem on users table
    # ------------------------------------------------------------------

    async def get_zeal_data(self, user_id: str) -> dict:
        """Returns {settlement_zeal, idlem, zeal_earned_today, last_zeal_reset}."""
        _default = {
            "settlement_zeal": 0,
            "idlem": 0,
            "zeal_earned_today": 0,
            "last_zeal_reset": None,
        }
        try:
            cursor = await self.connection.execute(
                "SELECT settlement_zeal, idlem, zeal_earned_today, last_zeal_reset "
                "FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "settlement_zeal": row[0] or 0,
                    "idlem": row[1] or 0,
                    "zeal_earned_today": row[2] or 0,
                    "last_zeal_reset": row[3],
                }
        except Exception:
            pass
        return _default

    async def add_zeal(self, user_id: str, amount: int) -> None:
        """Adds Zeal to the user's settlement_zeal and zeal_earned_today totals."""
        try:
            await self.connection.execute(
                "UPDATE users SET settlement_zeal = settlement_zeal + ?, "
                "zeal_earned_today = zeal_earned_today + ? WHERE user_id = ?",
                (amount, amount, user_id),
            )
            await self.connection.commit()
        except Exception:
            pass

    async def spend_zeal(self, user_id: str, amount: int) -> bool:
        """Deducts Zeal atomically if sufficient; returns True on success."""
        try:
            cursor = await self.connection.execute(
                "UPDATE users SET settlement_zeal = settlement_zeal - ? "
                "WHERE user_id = ? AND settlement_zeal >= ?",
                (amount, user_id, amount),
            )
            await self.connection.commit()
            return cursor.rowcount == 1
        except Exception:
            return False

    async def reset_daily_zeal_if_needed(self, user_id: str) -> None:
        """Resets zeal_earned_today if a new UTC day has started."""
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            cursor = await self.connection.execute(
                "SELECT last_zeal_reset FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            last = row[0] if row else None
            if last != today:
                await self.connection.execute(
                    "UPDATE users SET zeal_earned_today = 0, last_zeal_reset = ? WHERE user_id = ?",
                    (today, user_id),
                )
                await self.connection.commit()
        except Exception:
            pass

    async def add_idlem(self, user_id: str, amount: int) -> None:
        try:
            await self.connection.execute(
                "UPDATE users SET idlem = idlem + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await self.connection.commit()
        except Exception:
            pass

    async def spend_idlem(self, user_id: str, amount: int) -> bool:
        try:
            cursor = await self.connection.execute(
                "SELECT idlem FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row or (row[0] or 0) < amount:
                return False
            await self.connection.execute(
                "UPDATE users SET idlem = idlem - ? WHERE user_id = ?",
                (amount, user_id),
            )
            await self.connection.commit()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def get_projects(self, user_id: str, server_id: str) -> list[dict]:
        cursor = await self.connection.execute(
            "SELECT id, project_type, target_id, required_turns, invested_turns, data "
            "FROM settlement_projects WHERE user_id = ? AND server_id = ? "
            "ORDER BY id ASC",
            (user_id, server_id),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "project_type": r[1],
                "target_id": r[2],
                "required_turns": r[3],
                "invested_turns": r[4],
                "data": json.loads(r[5]) if r[5] else {},
            }
            for r in rows
        ]

    async def upsert_project(
        self,
        user_id: str,
        server_id: str,
        project_type: str,
        target_id: int | None,
        required_turns: int,
        data: dict | None = None,
    ) -> int:
        """
        Creates or updates a project row; returns its row id.

        Uniqueness is keyed on (user_id, server_id, project_type, target_id).
        We use an explicit SELECT + UPDATE/INSERT instead of ON CONFLICT because
        SQLite prohibits expressions (e.g. COALESCE) inside UNIQUE constraints
        and ON CONFLICT target lists.
        """
        data_json = json.dumps(data or {})

        # Try to find an existing row with the same logical key.
        if target_id is None:
            cursor = await self.connection.execute(
                "SELECT id FROM settlement_projects "
                "WHERE user_id = ? AND server_id = ? AND project_type = ? AND target_id IS NULL",
                (user_id, server_id, project_type),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT id FROM settlement_projects "
                "WHERE user_id = ? AND server_id = ? AND project_type = ? AND target_id = ?",
                (user_id, server_id, project_type, target_id),
            )
        existing = await cursor.fetchone()

        if existing:
            row_id = existing[0]
            await self.connection.execute(
                "UPDATE settlement_projects SET required_turns = ?, data = ? WHERE id = ?",
                (required_turns, data_json, row_id),
            )
        else:
            await self.connection.execute(
                "INSERT INTO settlement_projects "
                "(user_id, server_id, project_type, target_id, required_turns, invested_turns, data) "
                "VALUES (?, ?, ?, ?, ?, 0, ?)",
                (
                    user_id,
                    server_id,
                    project_type,
                    target_id,
                    required_turns,
                    data_json,
                ),
            )
            cursor2 = await self.connection.execute("SELECT last_insert_rowid()")
            r = await cursor2.fetchone()
            row_id = r[0] if r else -1

        await self.connection.commit()
        return row_id

    async def advance_projects(self, user_id: str, server_id: str) -> list[dict]:
        """Increments invested_turns by 1 for all projects; returns completed ones."""
        await self.connection.execute(
            "UPDATE settlement_projects SET invested_turns = invested_turns + 1 "
            "WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()
        cursor = await self.connection.execute(
            "SELECT id, project_type, target_id, required_turns, invested_turns, data "
            "FROM settlement_projects "
            "WHERE user_id = ? AND server_id = ? AND invested_turns >= required_turns",
            (user_id, server_id),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "project_type": r[1],
                "target_id": r[2],
                "required_turns": r[3],
                "invested_turns": r[4],
                "data": json.loads(r[5]) if r[5] else {},
            }
            for r in rows
        ]

    async def delete_project(self, project_id: int) -> None:
        await self.connection.execute(
            "DELETE FROM settlement_projects WHERE id = ?", (project_id,)
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Pending Black Market deals
    # ------------------------------------------------------------------

    async def get_pending_deal(self, user_id: str, server_id: str) -> dict | None:
        cursor = await self.connection.execute(
            "SELECT id, offer_data, total_value, turns_remaining, active_biases, created_turn "
            "FROM settlement_pending_deals WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "offer_data": json.loads(row[1]),
            "total_value": row[2],
            "turns_remaining": row[3],
            "active_biases": json.loads(row[4]) if row[4] else [],
            "created_turn": row[5],
        }

    async def create_pending_deal(
        self,
        user_id: str,
        server_id: str,
        offer_data: dict,
        total_value: int,
        turns_required: int,
        active_biases: list,
        current_turn: int,
    ) -> None:
        await self.connection.execute(
            """INSERT INTO settlement_pending_deals
               (user_id, server_id, offer_data, total_value, turns_remaining, active_biases, created_turn)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, server_id) DO UPDATE SET
                   offer_data = excluded.offer_data,
                   total_value = excluded.total_value,
                   turns_remaining = excluded.turns_remaining,
                   active_biases = excluded.active_biases,
                   created_turn = excluded.created_turn""",
            (
                user_id,
                server_id,
                json.dumps(offer_data),
                total_value,
                turns_required,
                json.dumps(active_biases),
                current_turn,
            ),
        )
        await self.connection.commit()

    async def decrement_deal_turn(self, user_id: str, server_id: str) -> dict | None:
        """Decrements turns_remaining by 1; returns deal if now complete (turns_remaining <= 0)."""
        await self.connection.execute(
            "UPDATE settlement_pending_deals SET turns_remaining = turns_remaining - 1 "
            "WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()
        return await self.get_pending_deal(user_id, server_id)

    async def delete_pending_deal(self, user_id: str, server_id: str) -> None:
        await self.connection.execute(
            "DELETE FROM settlement_pending_deals WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Active Events
    # ------------------------------------------------------------------

    async def get_active_events(self, user_id: str, server_id: str) -> list[dict]:
        cursor = await self.connection.execute(
            "SELECT id, event_key, event_type, turns_until, turns_remaining, data "
            "FROM settlement_active_events WHERE user_id = ? AND server_id = ? "
            "ORDER BY id ASC",
            (user_id, server_id),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "event_key": r[1],
                "event_type": r[2],
                "turns_until": r[3],
                "turns_remaining": r[4],
                "data": json.loads(r[5]) if r[5] else {},
            }
            for r in rows
        ]

    async def add_event(
        self,
        user_id: str,
        server_id: str,
        event_key: str,
        event_type: str,
        turns_until: int = 0,
        turns_remaining: int = 0,
        data: dict | None = None,
    ) -> None:
        await self.connection.execute(
            """INSERT INTO settlement_active_events
               (user_id, server_id, event_key, event_type, turns_until, turns_remaining, data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                server_id,
                event_key,
                event_type,
                turns_until,
                turns_remaining,
                json.dumps(data or {}),
            ),
        )
        await self.connection.commit()

    async def tick_events(
        self, user_id: str, server_id: str
    ) -> tuple[list[dict], list[dict]]:
        """
        Advances all events by one turn.
        Returns (newly_fired, expired) where:
          - newly_fired: upcoming events whose turns_until reached 0
          - expired: ongoing events whose turns_remaining reached 0
        """
        events = await self.get_active_events(user_id, server_id)
        newly_fired: list[dict] = []
        expired: list[dict] = []

        for ev in events:
            if ev["event_type"] == "upcoming":
                new_until = ev["turns_until"] - 1
                await self.connection.execute(
                    "UPDATE settlement_active_events SET turns_until = ? WHERE id = ?",
                    (new_until, ev["id"]),
                )
                if new_until <= 0:
                    newly_fired.append(ev)
            elif ev["event_type"] == "ongoing":
                new_rem = ev["turns_remaining"] - 1
                await self.connection.execute(
                    "UPDATE settlement_active_events SET turns_remaining = ? WHERE id = ?",
                    (new_rem, ev["id"]),
                )
                if new_rem <= 0:
                    expired.append(ev)

        await self.connection.commit()
        return newly_fired, expired

    async def remove_event(self, event_id: int) -> None:
        await self.connection.execute(
            "DELETE FROM settlement_active_events WHERE id = ?", (event_id,)
        )
        await self.connection.commit()

    async def remove_events_by_key(
        self, user_id: str, server_id: str, event_key: str
    ) -> None:
        await self.connection.execute(
            "DELETE FROM settlement_active_events WHERE user_id = ? AND server_id = ? AND event_key = ?",
            (user_id, server_id, event_key),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # BM Passive Tree
    # ------------------------------------------------------------------

    async def get_bm_tree(self, user_id: str, server_id: str) -> dict[str, int]:
        """Returns {node_key: level} for all unlocked BM passive nodes."""
        cursor = await self.connection.execute(
            "SELECT node_key, level FROM bm_passive_tree WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}

    async def set_bm_node(
        self, user_id: str, server_id: str, node_key: str, level: int
    ) -> None:
        await self.connection.execute(
            """INSERT INTO bm_passive_tree (user_id, server_id, node_key, level)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, server_id, node_key) DO UPDATE SET level = excluded.level""",
            (user_id, server_id, node_key, level),
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Uber Shrine Statues
    # ------------------------------------------------------------------

    async def get_uber_shrine_statues(
        self, user_id: str, server_id: str
    ) -> dict[str, dict]:
        """Returns {statue_type: {can_build, is_unlocked, workers_assigned, tier}}.

        can_build     — blueprint earned from defeating the uber boss (uber_progress table).
        is_unlocked   — statue has been physically constructed via the build project.
        workers_assigned — workers currently staffing the statue.
        tier          — statue upgrade tier (1–5).
        """
        # Blueprint prerequisite flags from uber_progress
        bp_cursor = await self.connection.execute(
            "SELECT celestial_blueprint_unlocked, infernal_blueprint_unlocked, "
            "void_blueprint_unlocked, gemini_blueprint_unlocked, "
            "corruption_blueprint_unlocked "
            "FROM uber_progress WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        bp_row = await bp_cursor.fetchone()
        can_build = {
            "celestial": bool(bp_row[0]) if bp_row else False,
            "infernal": bool(bp_row[1]) if bp_row else False,
            "void": bool(bp_row[2]) if bp_row else False,
            "bound": bool(bp_row[3]) if bp_row else False,
            "corrupted": bool(bp_row[4]) if bp_row else False,
        }

        # Built state + worker counts + tier + slot_index from uber_shrine_statues
        s_cursor = await self.connection.execute(
            "SELECT statue_type, is_unlocked, workers_assigned, tier, slot_index "
            "FROM uber_shrine_statues WHERE user_id = ? AND server_id = ?",
            (user_id, server_id),
        )
        s_rows = await s_cursor.fetchall()
        statue_state = {
            r[0]: {
                "is_unlocked": bool(r[1]),
                "workers_assigned": r[2],
                "tier": r[3] if r[3] is not None else 1,
                "slot_index": r[4] if r[4] else 0,
            }
            for r in s_rows
        }

        return {
            key: {
                "can_build": can_build[key],
                "is_unlocked": statue_state.get(key, {}).get("is_unlocked", False),
                "workers_assigned": statue_state.get(key, {}).get("workers_assigned", 0),
                "tier": statue_state.get(key, {}).get("tier", 1),
                "slot_index": statue_state.get(key, {}).get("slot_index", 0),
            }
            for key in ("celestial", "infernal", "void", "bound", "corrupted")
        }

    async def set_statue_workers(
        self,
        user_id: str,
        server_id: str,
        statue_type: str,
        workers: int,
    ) -> None:
        await self.connection.execute(
            """INSERT INTO uber_shrine_statues (user_id, server_id, statue_type, workers_assigned)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, server_id, statue_type)
               DO UPDATE SET workers_assigned = excluded.workers_assigned""",
            (user_id, server_id, statue_type, workers),
        )
        await self.connection.commit()

    async def upgrade_statue_tier(
        self, user_id: str, server_id: str, statue_type: str
    ) -> None:
        """Increments the statue's tier by 1 (max 5)."""
        await self.connection.execute(
            """UPDATE uber_shrine_statues
               SET tier = MIN(tier + 1, 5)
               WHERE user_id = ? AND server_id = ? AND statue_type = ?""",
            (user_id, server_id, statue_type),
        )
        await self.connection.commit()

    async def unlock_statue(
        self, user_id: str, server_id: str, statue_type: str, slot_index: int = 0
    ) -> None:
        """Marks the statue as built (called when the build project completes)."""
        await self.connection.execute(
            """INSERT INTO uber_shrine_statues
               (user_id, server_id, statue_type, is_unlocked, slot_index)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(user_id, server_id, statue_type)
               DO UPDATE SET is_unlocked = 1, slot_index = excluded.slot_index""",
            (user_id, server_id, statue_type, slot_index),
        )
        await self.connection.commit()
