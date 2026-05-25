# database/repositories/settlement.py

import aiosqlite

from core.models import Building, Settlement


class SettlementRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def get_settlement(self, user_id: str, server_id: str) -> Settlement:
        cursor = await self.connection.execute(
            "SELECT user_id, server_id, town_hall_tier, building_slots, timber, stone, last_collection_time FROM settlements WHERE user_id = ? AND server_id = ?",
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
        )

        b_cursor = await self.connection.execute(
            "SELECT id, user_id, server_id, building_type, tier, slot_index, "
            "workers_assigned, plot_index, is_meta "
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

    async def update_collection_timer(self, user_id: str, server_id: str):
        """Updates collection timer using Python time for consistency."""
        from datetime import datetime

        current_time = datetime.now().isoformat()

        await self.connection.execute(
            "UPDATE settlements SET last_collection_time = ? WHERE user_id = ? AND server_id = ?",
            (current_time, user_id, server_id),
        )
        await self.connection.commit()

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
                "workers_assigned, plot_index, is_meta "
                "FROM buildings WHERE user_id = ? AND server_id = ?",
                (user_id, server_id),
            )
            buildings = [
                Building(
                    id=r[0], user_id=r[1], server_id=r[2], building_type=r[3],
                    tier=r[4], slot_index=r[5], workers_assigned=r[6],
                    plot_index=r[7], is_meta=bool(r[8]),
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
                apothecary_boost_pct = (
                    adj_bonuses.get(b.plot_index, {}).get("apothecary_boost", 0.0)
                )
                break

        # --- Shrine effectiveness (sigil shrines only; temple is excluded) ---
        _SIGIL_SHRINES = frozenset({
            "celestial_shrine", "infernal_shrine", "void_shrine", "twin_shrine"
        })
        sacred_ground_val = PLOT_BONUS_TABLE.get("sacred_ground", {}).get("value", 0.20)
        shrine_effectiveness: dict[str, float] = {}
        for b in buildings:
            if b.building_type in _SIGIL_SHRINES and b.plot_index is not None:
                eff = 1.0
                if plot_bonus_by_idx.get(b.plot_index) == "sacred_ground":
                    eff += sacred_ground_val
                eff += adj_bonuses.get(b.plot_index, {}).get("shrine_boost", 0.0)
                shrine_effectiveness[b.building_type] = eff

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
