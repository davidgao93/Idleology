import re

import aiosqlite

from database.base import BaseRepository

_VALID_MATERIALS = frozenset(
    {
        "magma_core",
        "life_root",
        "spirit_shard",
        "celestial_stone",
        "void_crystal",
        "infernal_cinder",
        "bound_crystal",
        "diviners_rod",
        "unidentified_blueprint",
        "corrupted_core",
    }
)
_COLUMN_RE = re.compile(r"^[a-z_]+$")


class SettlementMaterialsRepository(BaseRepository):
    def __init__(self, connection: aiosqlite.Connection):
        super().__init__(connection)

    async def migrate_schema(self) -> None:
        """Add new columns to settlement_materials for existing databases."""
        try:
            await self.connection.execute(
                "ALTER TABLE settlement_materials ADD COLUMN corrupted_core "
                "INTEGER NOT NULL DEFAULT 0"
            )
            await self.connection.commit()
        except Exception:
            pass  # column already exists

    async def _ensure(self, user_id: str) -> None:
        """Insert a default row for the user if one doesn't exist yet."""
        await self.connection.execute(
            "INSERT OR IGNORE INTO settlement_materials (user_id) VALUES (?)",
            (user_id,),
        )

    async def get_all(self, user_id: str) -> dict:
        """Returns a dict of all material quantities for a user (defaults to 0)."""
        await self._ensure(user_id)
        async with self.connection.execute(
            "SELECT magma_core, life_root, spirit_shard, celestial_stone, "
            "void_crystal, infernal_cinder, bound_crystal, diviners_rod, "
            "unidentified_blueprint, corrupted_core FROM settlement_materials "
            "WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return {k: 0 for k in _VALID_MATERIALS}
        keys = [
            "magma_core",
            "life_root",
            "spirit_shard",
            "celestial_stone",
            "void_crystal",
            "infernal_cinder",
            "bound_crystal",
            "diviners_rod",
            "unidentified_blueprint",
            "corrupted_core",
        ]
        return {k: (row[i] or 0) for i, k in enumerate(keys)}

    async def get_rare_materials(self, user_id: str) -> tuple:
        """Returns (magma_core, life_root, spirit_shard)."""
        await self._ensure(user_id)
        async with self.connection.execute(
            "SELECT magma_core, life_root, spirit_shard "
            "FROM settlement_materials WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row if row else (0, 0, 0)

    async def get_uber_materials(self, user_id: str) -> tuple:
        """Returns (celestial_stone, infernal_cinder, void_crystal, bound_crystal, corrupted_core)."""
        await self._ensure(user_id)
        async with self.connection.execute(
            "SELECT celestial_stone, infernal_cinder, void_crystal, bound_crystal, "
            "corrupted_core FROM settlement_materials WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row if row else (0, 0, 0, 0, 0)

    async def modify(self, user_id: str, material: str, amount: int) -> None:
        """Add *amount* (may be negative) to a material column, flooring at 0."""
        if material not in _VALID_MATERIALS:
            raise ValueError(
                f"settlement_materials.modify: unknown material {material!r}"
            )
        await self._ensure(user_id)
        await self.connection.execute(
            f"UPDATE settlement_materials "
            f"SET `{material}` = MAX(0, `{material}` + ?) WHERE user_id = ?",
            (amount, user_id),
        )
        await self.connection.commit()
