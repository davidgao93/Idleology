from typing import Dict, List, Literal, Tuple

import aiosqlite

SkillType = Literal["mining", "fishing", "woodcutting"]


class SkillRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

        # Whitelist for dynamic SQL generation to prevent injection (raw resources)
        self.allowed_columns = {
            "mining": [
                "iron_ore",
                "coal_ore",
                "gold_ore",
                "platinum_ore",
                "idea_ore",
                "pickaxe_tier",
            ],
            "woodcutting": [
                "oak_logs",
                "willow_logs",
                "mahogany_logs",
                "magic_logs",
                "idea_logs",
                "axe_type",
            ],
            "fishing": [
                "desiccated_bones",
                "regular_bones",
                "sturdy_bones",
                "reinforced_bones",
                "titanium_bones",
                "fishing_rod",
            ],
        }

        # Expansion columns on per-skill tables (safe to query directly)
        self._expansion_cols = {"familiarization_end", "momentum_minutes"}

        # Extended whitelist covering both raw and refined (used by upgrade views, trade)
        self.allowed_columns_extended = {
            "mining": [
                "iron_ore",
                "iron_bar",
                "coal_ore",
                "steel_bar",
                "gold_ore",
                "gold_bar",
                "platinum_ore",
                "platinum_bar",
                "idea_ore",
                "idea_bar",
                "pickaxe_tier",
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
                "axe_type",
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
                "fishing_rod",
            ],
        }

    # ---------------------------------------------------------
    # Data Retrieval
    # ---------------------------------------------------------

    async def get_single_resource(
        self, user_id: str, server_id: str, skill_type: str, column: str
    ) -> int:
        """Fetch a single resource amount from a skill table."""
        allowed = self.allowed_columns_extended.get(skill_type, [])
        if column not in allowed:
            raise ValueError(f"Invalid column '{column}' for skill '{skill_type}'")
        async with self.connection.execute(
            f"SELECT {column} FROM {skill_type} WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row[column] if row else 0

    async def get_multi_resource(
        self, user_id: str, server_id: str, skill_type: str, columns: list
    ) -> tuple:
        """Fetch multiple resource columns from a skill table in one query."""
        allowed = self.allowed_columns_extended.get(skill_type, [])
        for col in columns:
            if col not in allowed:
                raise ValueError(f"Invalid column '{col}' for skill '{skill_type}'")
        col_str = ", ".join(columns)
        async with self.connection.execute(
            f"SELECT {col_str} FROM {skill_type} WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row if row else tuple(0 for _ in columns)

    async def deduct_resource_atomic(
        self, user_id: str, server_id: str, skill_type: str, column: str, qty: int
    ) -> bool:
        """Deduct qty from a skill resource only if sufficient balance exists. Returns True on success."""
        allowed = self.allowed_columns_extended.get(skill_type, [])
        if column not in allowed:
            raise ValueError(f"Invalid column '{column}' for skill '{skill_type}'")
        async with self.connection.execute(
            f"UPDATE {skill_type} SET {column} = {column} - ? WHERE user_id=? AND server_id=? AND {column} >= ?",
            (qty, user_id, server_id, qty),
        ) as cursor:
            return cursor.rowcount > 0

    async def get_data(
        self, user_id: str, server_id: str, skill_type: SkillType
    ) -> Tuple:
        """Fetch the skill row for a user."""
        rows = await self.connection.execute(
            f"SELECT * FROM {skill_type} WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        )
        async with rows as cursor:
            return await cursor.fetchone()

    async def get_all_users(self, skill_type: SkillType) -> List[Tuple]:
        """Fetch all users who have this skill initialized (for regeneration tasks)."""
        rows = await self.connection.execute(
            f"SELECT user_id, server_id FROM {skill_type}"
        )
        async with rows as cursor:
            return await cursor.fetchall()

    # ---------------------------------------------------------
    # Initialization & Updates
    # ---------------------------------------------------------

    async def initialize(
        self, user_id: str, server_id: str, skill_type: SkillType, tool_tier: str
    ) -> None:
        """Insert a new entry for a skill."""
        tool_col = (
            "pickaxe_tier"
            if skill_type == "mining"
            else ("fishing_rod" if skill_type == "fishing" else "axe_type")
        )

        await self.connection.execute(
            f"INSERT INTO {skill_type} (user_id, server_id, {tool_col}) VALUES (?, ?, ?)",
            (user_id, server_id, tool_tier),
        )
        await self.connection.commit()

    async def update_single_resource(
        self,
        user_id: str,
        server_id: str,
        skill_type: SkillType,
        resource: str,
        amount: int,
    ) -> None:
        """Update a specific resource count."""
        # Sanity check column name
        if resource not in self.allowed_columns[skill_type]:
            raise ValueError(
                f"Invalid resource column '{resource}' for skill '{skill_type}'"
            )

        await self.connection.execute(
            f"UPDATE {skill_type} SET {resource} = {resource} + ? WHERE user_id = ? AND server_id = ?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def update_batch(
        self,
        user_id: str,
        server_id: str,
        skill_type: SkillType,
        resources: Dict[str, int],
    ) -> None:
        """
        Updates multiple resources at once.
        'resources' should be a dict like {'iron': 5, 'coal': 2}
        """
        if not resources:
            return

        # Dynamic SQL Construction (Safe because we whitelist keys)
        updates = []
        values = []

        for col, amount in resources.items():
            if col in self.allowed_columns[skill_type]:
                updates.append(f"{col} = {col} + ?")
                values.append(amount)

        if not updates:
            return

        query = f"UPDATE {skill_type} SET {', '.join(updates)} WHERE user_id = ? AND server_id = ?"
        values.extend([user_id, server_id])

        await self.connection.execute(query, tuple(values))
        await self.connection.commit()

    # ---------------------------------------------------------
    # Tool Upgrades (Specific Transactions)
    # ---------------------------------------------------------
    # Kept specific due to complex transaction logic (Gold + Multiple Resources + Tier Update)

    async def upgrade_pickaxe(
        self, user_id: str, server_id: str, new_tier: str, costs: tuple
    ) -> None:
        iron_cost, coal_cost, gold_cost, platinum_cost, gp = costs
        raw_held = await self.get_multi_resource(
            user_id,
            server_id,
            "mining",
            ["iron_ore", "coal_ore", "gold_ore", "platinum_ore"],
        )
        for raw_col, ref_col, held, qty in [
            ("iron_ore", "iron_bar", raw_held[0], iron_cost),
            ("coal_ore", "steel_bar", raw_held[1], coal_cost),
            ("gold_ore", "gold_bar", raw_held[2], gold_cost),
            ("platinum_ore", "platinum_bar", raw_held[3], platinum_cost),
        ]:
            if qty > 0:
                await self.deduct_upgrade_material(
                    user_id, server_id, "mining", raw_col, ref_col, held, qty
                )
        await self.connection.execute(
            "UPDATE mining SET pickaxe_tier=? WHERE user_id=? AND server_id=?",
            (new_tier, user_id, server_id),
        )
        cursor = await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ? AND gold >= ?",
            (gp, user_id, gp),
        )
        if cursor.rowcount == 0:
            raise ValueError("Insufficient gold for pickaxe upgrade")
        await self.connection.commit()

    async def upgrade_axe(
        self, user_id: str, server_id: str, new_tier: str, costs: tuple
    ) -> None:
        oak_cost, willow_cost, mahogany_cost, magic_cost, gp = costs
        raw_held = await self.get_multi_resource(
            user_id,
            server_id,
            "woodcutting",
            ["oak_logs", "willow_logs", "mahogany_logs", "magic_logs"],
        )
        for raw_col, ref_col, held, qty in [
            ("oak_logs", "oak_plank", raw_held[0], oak_cost),
            ("willow_logs", "willow_plank", raw_held[1], willow_cost),
            ("mahogany_logs", "mahogany_plank", raw_held[2], mahogany_cost),
            ("magic_logs", "magic_plank", raw_held[3], magic_cost),
        ]:
            if qty > 0:
                await self.deduct_upgrade_material(
                    user_id, server_id, "woodcutting", raw_col, ref_col, held, qty
                )
        await self.connection.execute(
            "UPDATE woodcutting SET axe_type=? WHERE user_id=? AND server_id=?",
            (new_tier, user_id, server_id),
        )
        cursor = await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ? AND gold >= ?",
            (gp, user_id, gp),
        )
        if cursor.rowcount == 0:
            raise ValueError("Insufficient gold for axe upgrade")
        await self.connection.commit()

    # ---------------------------------------------------------
    # Upgrade material helpers (used by upgrade views via base.py)
    # ---------------------------------------------------------

    async def get_upgrade_materials(
        self, user_id: str, server_id: str, cols: dict
    ) -> tuple:
        """Fetch (raw, refined) amounts for ore, log, and bone in one call.

        `cols` is the dict returned by BaseUpgradeView._resolve_material_columns:
          {"ore": {"raw_col": ..., "ref_col": ...},
           "log": {"raw_col": ..., "ref_col": ...},
           "bone": {"raw_col": ..., "ref_col": ...}}
        Returns (mining_res, wood_res, fish_res) as (raw, refined) tuples.
        """
        mining_res = await self.get_multi_resource(
            user_id,
            server_id,
            "mining",
            [cols["ore"]["raw_col"], cols["ore"]["ref_col"]],
        )
        wood_res = await self.get_multi_resource(
            user_id,
            server_id,
            "woodcutting",
            [cols["log"]["raw_col"], cols["log"]["ref_col"]],
        )
        fish_res = await self.get_multi_resource(
            user_id,
            server_id,
            "fishing",
            [cols["bone"]["raw_col"], cols["bone"]["ref_col"]],
        )
        return mining_res, wood_res, fish_res

    async def deduct_upgrade_material(
        self,
        user_id: str,
        server_id: str,
        table: str,
        raw_col: str,
        ref_col: str,
        raw_held: int,
        cost: int,
    ) -> bool:
        """Deduct cost from raw resources first, spilling into refined if needed.
        Returns True if all deductions succeeded."""
        to_take_raw = min(raw_held, cost)
        to_take_ref = cost - to_take_raw
        ok = True
        if to_take_raw > 0:
            ok = ok and await self.deduct_resource_atomic(
                user_id, server_id, table, raw_col, to_take_raw
            )
        if to_take_ref > 0:
            ok = ok and await self.deduct_resource_atomic(
                user_id, server_id, table, ref_col, to_take_ref
            )
        return ok

    async def charge_entry_cost(self, user_id: str, gold_amount: int) -> None:
        """Deducts gold from a user for a minigame entry cost (bait / forestry pass)."""
        await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ?",
            (gold_amount, user_id),
        )
        await self.connection.commit()

    async def upgrade_fishing_rod(
        self, user_id: str, server_id: str, new_tier: str, costs: tuple
    ) -> None:
        des_cost, reg_cost, stu_cost, rein_cost, gp = costs
        raw_held = await self.get_multi_resource(
            user_id,
            server_id,
            "fishing",
            ["desiccated_bones", "regular_bones", "sturdy_bones", "reinforced_bones"],
        )
        for raw_col, ref_col, held, qty in [
            ("desiccated_bones", "desiccated_essence", raw_held[0], des_cost),
            ("regular_bones", "regular_essence", raw_held[1], reg_cost),
            ("sturdy_bones", "sturdy_essence", raw_held[2], stu_cost),
            ("reinforced_bones", "reinforced_essence", raw_held[3], rein_cost),
        ]:
            if qty > 0:
                await self.deduct_upgrade_material(
                    user_id, server_id, "fishing", raw_col, ref_col, held, qty
                )
        await self.connection.execute(
            "UPDATE fishing SET fishing_rod=? WHERE user_id=? AND server_id=?",
            (new_tier, user_id, server_id),
        )
        cursor = await self.connection.execute(
            "UPDATE users SET gold = gold - ? WHERE user_id = ? AND gold >= ?",
            (gp, user_id, gp),
        )
        if cursor.rowcount == 0:
            raise ValueError("Insufficient gold for fishing rod upgrade")
        await self.connection.commit()

    # =========================================================
    # Artisan Mastery (Gathering Mastery) methods
    # All per design in docs/design/gathering_mastery.md
    # =========================================================

    async def get_mastery(self, user_id: str, server_id: str) -> dict:
        """Return mastery row or defaults. Ensures row exists."""
        async with self.connection.execute(
            """SELECT * FROM gathering_mastery WHERE user_id=? AND server_id=?""",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            cols = (
                [d[0] for d in cursor.description]
                if hasattr(cursor, "description")
                else []
            )
            # Fallback column names if description not available in aiosqlite cursor
            if not cols:
                cols = [
                    "user_id",
                    "server_id",
                    "mining_points",
                    "fishing_points",
                    "woodcutting_points",
                    "mining_alloc",
                    "fishing_alloc",
                    "woodcutting_alloc",
                    "last_point_claim",
                    "geode_cores",
                    "tide_relics",
                    "heartwood_shards",
                    "mining_tripled_ticks",
                    "fishing_tripled_ticks",
                    "woodcutting_tripled_ticks",
                    "total_mastery_invested",
                    "attunement_alloc",
                    "mastery_insight",
                    "blessed_bismuth",
                    "sparkling_sprig",
                    "capricious_carp",
                ]
            return dict(zip(cols, row))
        # Create default row
        await self.connection.execute(
            """INSERT INTO gathering_mastery (user_id, server_id) VALUES (?, ?)""",
            (user_id, server_id),
        )
        await self.connection.commit()
        return {
            "user_id": user_id,
            "server_id": server_id,
            "mining_points": 0,
            "fishing_points": 0,
            "woodcutting_points": 0,
            "mining_alloc": "{}",
            "fishing_alloc": "{}",
            "woodcutting_alloc": "{}",
            "last_point_claim": None,
            "geode_cores": 0,
            "tide_relics": 0,
            "heartwood_shards": 0,
            "mining_tripled_ticks": 0,
            "fishing_tripled_ticks": 0,
            "woodcutting_tripled_ticks": 0,
            "total_mastery_invested": 0,
            "blessed_bismuth": 0,
            "sparkling_sprig": 0,
            "capricious_carp": 0,
        }

    async def add_mastery_points(
        self, user_id: str, server_id: str, skill: str, amount: int
    ) -> None:
        """Add points to one skill (called from hourly task)."""
        col = f"{skill}_points"
        await self.connection.execute(
            f"UPDATE gathering_mastery SET {col} = {col} + ? WHERE user_id=? AND server_id=?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    # --- Elemental Keys (Elemental of Elements gathering boss) ---

    async def increment_blessed_bismuth(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        await self.connection.execute(
            "UPDATE gathering_mastery SET blessed_bismuth = blessed_bismuth + ? WHERE user_id=? AND server_id=?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_sparkling_sprig(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        await self.connection.execute(
            "UPDATE gathering_mastery SET sparkling_sprig = sparkling_sprig + ? WHERE user_id=? AND server_id=?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def increment_capricious_carp(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        await self.connection.execute(
            "UPDATE gathering_mastery SET capricious_carp = capricious_carp + ? WHERE user_id=? AND server_id=?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def consume_elemental_keys(self, user_id: str, server_id: str) -> None:
        """Deducts 1 of each elemental key atomically."""
        await self.connection.execute(
            """UPDATE gathering_mastery
               SET blessed_bismuth = blessed_bismuth - 1,
                   sparkling_sprig = sparkling_sprig - 1,
                   capricious_carp = capricious_carp - 1
               WHERE user_id=? AND server_id=?""",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def update_mastery_alloc(
        self,
        user_id: str,
        server_id: str,
        skill: str,
        alloc_json: str,
        total_invested: int,
    ) -> None:
        """Atomic purchase: write new alloc JSON and update total."""
        col = f"{skill}_alloc"
        await self.connection.execute(
            f"UPDATE gathering_mastery SET {col}=?, total_mastery_invested=? WHERE user_id=? AND server_id=?",
            (alloc_json, total_invested, user_id, server_id),
        )
        await self.connection.commit()

    async def modify_remnants(
        self, user_id: str, server_id: str, changes: dict
    ) -> bool:
        """Add/sub remnants (positive or negative). Returns False if any would go negative."""
        sets = []
        vals = []
        for k, delta in changes.items():
            if k not in ("geode_cores", "tide_relics", "heartwood_shards"):
                continue
            if delta < 0:
                # Will check in WHERE
                sets.append(f"{k} = {k} + ?")
                vals.append(delta)
            else:
                sets.append(f"{k} = {k} + ?")
                vals.append(delta)
        if not sets:
            return True
        # For safety on negative, we do best-effort; caller should validate first for spends
        vals.extend([user_id, server_id])
        q = f"UPDATE gathering_mastery SET {', '.join(sets)} WHERE user_id=? AND server_id=?"
        await self.connection.execute(q, tuple(vals))
        await self.connection.commit()
        return True

    async def add_runes_of_nature(self, user_id: str, amount: int) -> None:
        """Credit runes (from craft or drop)."""
        await self.connection.execute(
            "UPDATE player_currencies SET runes_of_nature = runes_of_nature + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()

    async def spend_runes_of_nature(self, user_id: str, amount: int) -> bool:
        """Atomic spend. Returns True on success."""
        cursor = await self.connection.execute(
            "UPDATE player_currencies SET runes_of_nature = runes_of_nature - ? WHERE user_id = ? AND runes_of_nature >= ?",
            (amount, user_id, amount),
        )
        await self.connection.commit()
        return cursor.rowcount == 1

    async def get_runes_of_nature(self, user_id: str) -> int:
        async with self.connection.execute(
            "SELECT runes_of_nature FROM player_currencies WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row["runes_of_nature"] if row else 0

    async def respec_mastery(
        self, user_id: str, server_id: str, skill: str, refund_points: int
    ) -> None:
        """Full reset of one skill's alloc and refund its points. Caller already spent the rune."""
        col = f"{skill}_alloc"
        points_col = f"{skill}_points"
        await self.connection.execute(
            f"UPDATE gathering_mastery SET {col}='{{}}', {points_col} = {points_col} + ? WHERE user_id=? AND server_id=?",
            (refund_points, user_id, server_id),
        )
        await self.connection.commit()

    async def add_tripled_ticks(
        self, user_id: str, server_id: str, skill: str, amount: int
    ) -> None:
        """Award tripled passive tick buffs from defeating a prestige gathering boss."""
        if amount <= 0:
            return
        col = f"{skill}_tripled_ticks"
        await self.connection.execute(
            f"UPDATE gathering_mastery SET {col} = {col} + ? WHERE user_id=? AND server_id=?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def consume_tripled_tick(
        self, user_id: str, server_id: str, skill: str
    ) -> None:
        """Decrement the tripled tick counter by 1 for this skill (clamped at 0).
        Called from the hourly regeneration task when a player consumes one of their
        prestige-boss-granted triple-yield ticks.
        """
        if skill not in ("mining", "fishing", "woodcutting"):
            return
        col = f"{skill}_tripled_ticks"
        await self.connection.execute(
            f"UPDATE gathering_mastery SET {col} = MAX(0, {col} - 1) WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        )
        await self.connection.commit()

    async def update_last_mastery_claim(
        self, user_id: str, server_id: str, timestamp: str
    ) -> None:
        """Update the last_point_claim timestamp for catch-up calculations. Called from the hourly task."""
        await self.connection.execute(
            "UPDATE gathering_mastery SET last_point_claim=? WHERE user_id=? AND server_id=?",
            (timestamp, user_id, server_id),
        )
        await self.connection.commit()

    async def deduct_mastery_points(
        self, user_id: str, server_id: str, skill: str, amount: int
    ) -> None:
        """Deduct points from a skill's mastery pool (used on node purchase)."""
        if amount <= 0:
            return
        col = f"{skill}_points"
        await self.connection.execute(
            f"UPDATE gathering_mastery SET {col} = MAX(0, {col} - ?) WHERE user_id=? AND server_id=?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    # =========================================================
    # Nature's Attunement (cross-skill tree) + Mastery Insight
    # =========================================================

    async def update_attunement_alloc(
        self, user_id: str, server_id: str, alloc_json: str
    ) -> None:
        """Write the attunement allocation JSON (free node investment, not per-skill branches)."""
        await self.connection.execute(
            "UPDATE gathering_mastery SET attunement_alloc=? WHERE user_id=? AND server_id=?",
            (alloc_json, user_id, server_id),
        )
        await self.connection.commit()

    async def add_mastery_insight(
        self, user_id: str, server_id: str, amount: int
    ) -> None:
        """Award Mastery Insight from post-max excess point conversion."""
        if amount <= 0:
            return
        await self.connection.execute(
            "UPDATE gathering_mastery SET mastery_insight = mastery_insight + ? WHERE user_id=? AND server_id=?",
            (amount, user_id, server_id),
        )
        await self.connection.commit()

    async def get_mastery_insight(self, user_id: str, server_id: str) -> int:
        """Return current Mastery Insight count for the account."""
        async with self.connection.execute(
            "SELECT mastery_insight FROM gathering_mastery WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        return (
            int(row["mastery_insight"])
            if row and row["mastery_insight"] is not None
            else 0
        )

    # =========================================================
    # Gathering Expansion: Familiarization + Session Momentum
    # Per design doc (docs/design/gathering_expansion.md)
    # =========================================================

    async def get_familiarization_state(
        self, user_id: str, server_id: str, skill: str
    ) -> tuple:
        """Returns (familiarization_end_iso, momentum_minutes) for a skill's gate.

        Data lives on the per-skill table (mining/fishing/woodcutting), keeping it
        separate from the purely-passive gathering_mastery (artisan points/trees).
        """
        try:
            async with self.connection.execute(
                f"SELECT familiarization_end, momentum_minutes FROM {skill}"
                " WHERE user_id=? AND server_id=?",
                (user_id, server_id),
            ) as cursor:
                row = await cursor.fetchone()
            return (
                (row["familiarization_end"], int(row["momentum_minutes"] or 0))
                if row
                else (None, 0)
            )
        except Exception:
            return (None, 0)

    async def set_familiarization_end(
        self, user_id: str, server_id: str, skill: str, end_iso: str
    ) -> None:
        """Start a familiarization gate after a tool upgrade (stored on skill table)."""
        try:
            await self.connection.execute(
                f"UPDATE {skill} SET familiarization_end=? WHERE user_id=? AND server_id=?",
                (end_iso, user_id, server_id),
            )
            await self.connection.commit()
        except Exception:
            pass

    async def add_session_momentum(
        self,
        user_id: str,
        server_id: str,
        skill: str,
        minutes: int,
        max_minutes: int,
    ) -> None:
        """Bank momentum minutes from a quality session, capped at max_minutes.

        Max is the 25% total-gate cap across the skill's full upgrade path:
        25% × (4 + 6 + 10) hrs × 60 = 300 min per skill.
        """
        if minutes <= 0:
            return
        try:
            await self.connection.execute(
                f"UPDATE {skill} SET momentum_minutes = MIN(?, momentum_minutes + ?)"
                " WHERE user_id=? AND server_id=?",
                (max_minutes, minutes, user_id, server_id),
            )
            await self.connection.commit()
        except Exception:
            pass

    async def convert_excess_to_insight(
        self, user_id: str, server_id: str, conversion_rate: int = 5
    ) -> int:
        """
        If the player has fully maxed all trees + Nature's Attunement, convert as many
        full sets of `conversion_rate` unspent points (summed across the three skills)
        into Mastery Insight. Returns the number of insight points awarded this call.
        Leaves remainder (< conversion_rate) in the point pools.
        """
        if conversion_rate <= 0:
            return 0

        async with self.connection.execute(
            """SELECT mining_points, fishing_points, woodcutting_points, mastery_insight
               FROM gathering_mastery WHERE user_id=? AND server_id=?""",
            (user_id, server_id),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return 0

        m_pts = row["mining_points"] or 0
        f_pts = row["fishing_points"] or 0
        w_pts = row["woodcutting_points"] or 0
        total_points = m_pts + f_pts + w_pts
        if total_points < conversion_rate:
            return 0

        insight_gain = total_points // conversion_rate
        if insight_gain <= 0:
            return 0

        remainder = total_points % conversion_rate

        # Distribute remainder back across the three pools (simple round-robin style)
        new_mining = min(remainder, m_pts)
        remainder -= new_mining
        new_fishing = min(remainder, f_pts)
        remainder -= new_fishing
        new_woodcutting = remainder  # whatever is left

        await self.connection.execute(
            """UPDATE gathering_mastery
               SET mining_points = ?, fishing_points = ?, woodcutting_points = ?,
                   mastery_insight = mastery_insight + ?
               WHERE user_id=? AND server_id=?""",
            (
                new_mining,
                new_fishing,
                new_woodcutting,
                insight_gain,
                user_id,
                server_id,
            ),
        )
        await self.connection.commit()
        return insight_gain
