import aiosqlite
import random
from core.models import CodexTome

# Passive types available for tomes
TOME_PASSIVE_TYPES = [
    'vitality', 'wrath', 'bastion', 'tenacity', 'bloodthirst',
    'providence', 'precision', 'affluence', 'bulwark', 'resilience',
]

# Value ranges per (passive_type, tier). Each tier has a (min, max) tuple.
# When upgrading to a tier, a float is rolled in this range.
TOME_TIER_RANGES: dict[str, list[tuple[float, float]]] = {
    # tier index 0 = tier 1, index 4 = tier 5
    'vitality':    [(3.0, 7.0),  (6.0, 14.0), (10.0, 22.0), (14.0, 30.0), (18.0, 40.0)],
    'wrath':       [(3.0, 8.0),  (6.0, 15.0), (10.0, 24.0), (14.0, 32.0), (18.0, 42.0)],
    'bastion':     [(3.0, 8.0),  (6.0, 15.0), (10.0, 24.0), (14.0, 32.0), (18.0, 42.0)],
    'tenacity':    [(2.0, 5.0),  (4.0, 9.0),  (6.0, 14.0),  (9.0, 19.0),  (12.0, 25.0)],
    'bloodthirst': [(2.0, 5.0),  (4.0, 9.0),  (6.0, 14.0),  (9.0, 19.0),  (12.0, 25.0)],
    'providence':  [(3.0, 8.0),  (6.0, 15.0), (10.0, 24.0), (14.0, 32.0), (18.0, 42.0)],
    'precision':   [(1.0, 3.0),  (2.0, 5.0),  (3.0, 8.0),   (5.0, 11.0),  (7.0, 15.0)],
    'affluence':   [(3.0, 8.0),  (6.0, 15.0), (10.0, 24.0), (14.0, 32.0), (18.0, 42.0)],
    'bulwark':     [(1.0, 3.0),  (2.0, 5.0),  (3.0, 8.0),   (5.0, 11.0),  (7.0, 15.0)],
    'resilience':  [(1.0, 3.0),  (2.0, 5.0),  (3.0, 8.0),   (5.0, 11.0),  (7.0, 15.0)],
}

# Fragment cost to upgrade from tier N-1 to tier N (index 0 = unlock tier 1)
TOME_UPGRADE_COSTS = [5, 10, 20, 40, 80]

# Reroll cost is 50% of the current tier's upgrade cost (minimum 3)
def get_reroll_cost(tier: int) -> int:
    if tier == 0 or tier > 5:
        return 0
    return max(3, TOME_UPGRADE_COSTS[tier - 1] // 2)


def roll_tome_value(passive_type: str, tier: int) -> float:
    """Roll a stat value in the range for the given passive type and tier (1-5)."""
    lo, hi = TOME_TIER_RANGES[passive_type][tier - 1]
    return round(random.uniform(lo, hi), 2)


class CodexRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    # ------------------------------------------------------------------
    # Tomes
    # ------------------------------------------------------------------

    async def get_tomes(self, user_id: str) -> list[CodexTome]:
        cursor = await self.connection.execute(
            "SELECT slot, passive_type, tier, value FROM codex_tomes WHERE user_id = ? ORDER BY slot",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [CodexTome(slot=r[0], passive_type=r[1], tier=r[2], value=r[3]) for r in rows]

    async def get_unlocked_slots(self, user_id: str) -> int:
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM codex_tomes WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def unlock_tome_slot(self, user_id: str) -> CodexTome | None:
        """
        Consume one codex page to open the next tome slot with a random passive type.
        Returns the new CodexTome, or None if all 5 slots are already unlocked.
        """
        unlocked = await self.get_unlocked_slots(user_id)
        if unlocked >= 5:
            return None

        passive_type = random.choice(TOME_PASSIVE_TYPES)
        slot = unlocked  # slots 0-4

        await self.connection.execute(
            "INSERT INTO codex_tomes (user_id, slot, passive_type, tier, value) VALUES (?, ?, ?, 0, 0.0)",
            (user_id, slot, passive_type)
        )
        await self.connection.commit()
        return CodexTome(slot=slot, passive_type=passive_type, tier=0, value=0.0)

    async def upgrade_tome(self, user_id: str, slot: int) -> tuple[bool, float]:
        """
        Upgrade a tome slot to the next tier, rolling a new value in range.
        Returns (success, new_value). Fails if already tier 5.
        """
        cursor = await self.connection.execute(
            "SELECT tier, passive_type FROM codex_tomes WHERE user_id = ? AND slot = ?",
            (user_id, slot)
        )
        row = await cursor.fetchone()
        if not row or row[0] >= 5:
            return False, 0.0

        current_tier, passive_type = row[0], row[1]
        new_tier = current_tier + 1
        new_value = roll_tome_value(passive_type, new_tier)

        await self.connection.execute(
            "UPDATE codex_tomes SET tier = ?, value = ? WHERE user_id = ? AND slot = ?",
            (new_tier, new_value, user_id, slot)
        )
        await self.connection.commit()
        return True, new_value

    async def reroll_tome_value(self, user_id: str, slot: int) -> tuple[bool, float]:
        """
        Reroll the stat value for the current tier without changing the tier.
        Returns (success, new_value). Fails if tome is at tier 0.
        """
        cursor = await self.connection.execute(
            "SELECT tier, passive_type FROM codex_tomes WHERE user_id = ? AND slot = ?",
            (user_id, slot)
        )
        row = await cursor.fetchone()
        if not row or row[0] == 0:
            return False, 0.0

        tier, passive_type = row[0], row[1]
        new_value = roll_tome_value(passive_type, tier)

        await self.connection.execute(
            "UPDATE codex_tomes SET value = ? WHERE user_id = ? AND slot = ?",
            (new_value, user_id, slot)
        )
        await self.connection.commit()
        return True, new_value

    async def reroll_tome_type(self, user_id: str, slot: int) -> tuple[bool, str]:
        """
        Reroll the passive type on a tome slot, resetting tier and value to 0.
        Returns (success, new_passive_type).
        """
        cursor = await self.connection.execute(
            "SELECT passive_type FROM codex_tomes WHERE user_id = ? AND slot = ?",
            (user_id, slot)
        )
        row = await cursor.fetchone()
        if not row:
            return False, ''

        current_type = row[0]
        candidates = [t for t in TOME_PASSIVE_TYPES if t != current_type]
        new_type = random.choice(candidates)

        await self.connection.execute(
            "UPDATE codex_tomes SET passive_type = ?, tier = 0, value = 0.0 WHERE user_id = ? AND slot = ?",
            (new_type, user_id, slot)
        )
        await self.connection.commit()
        return True, new_type

    # ------------------------------------------------------------------
    # Chapter progress
    # ------------------------------------------------------------------

    async def log_chapter_clear(self, user_id: str, chapter_id: int, perfect: bool = False):
        await self.connection.execute(
            """INSERT INTO codex_progress (user_id, chapter_id, clears, perfect_clears)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(user_id, chapter_id) DO UPDATE SET
                   clears = clears + 1,
                   perfect_clears = perfect_clears + ?""",
            (user_id, chapter_id, int(perfect), int(perfect))
        )
        await self.connection.commit()

    async def get_chapter_clears(self, user_id: str) -> dict[int, dict]:
        """Returns {chapter_id: {'clears': int, 'perfect_clears': int}}."""
        cursor = await self.connection.execute(
            "SELECT chapter_id, clears, perfect_clears FROM codex_progress WHERE user_id = ?",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return {r[0]: {'clears': r[1], 'perfect_clears': r[2]} for r in rows}
