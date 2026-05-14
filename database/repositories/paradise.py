import json

import aiosqlite

# Jewel costs to unlock each passive slot (cumulative thresholds: 1, 4, 9, 19, 34)
PASSIVE_SLOT_COSTS = [1, 3, 5, 10, 15]
PASSIVE_SLOT_THRESHOLDS = [1, 4, 9, 19, 34]


def _default_data() -> dict:
    return {
        "unlocked_skills": [],
        "equipped_skill": None,
        "skill_levels": {},
        "skill_charges": {},
        "passive_slots": [],
        "passive_jewels_invested": 0,
        "total_jewels_obtained": 0,
        "total_jewels_consumed": 0,
    }


def _row_to_dict(row) -> dict:
    return {
        "unlocked_skills": json.loads(row[1]),
        "equipped_skill": row[2],
        "skill_levels": json.loads(row[3]),
        "skill_charges": json.loads(row[4]),
        "passive_slots": json.loads(row[5]),
        "passive_jewels_invested": row[6],
        "total_jewels_obtained": row[7],
        "total_jewels_consumed": row[8],
    }


class ParadiseRepository:
    def __init__(self, connection: aiosqlite.Connection):
        self.connection = connection

    async def _ensure_row(self, user_id: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO paradise_jewel_data (user_id) VALUES (?)",
            (user_id,),
        )

    async def get(self, user_id: str) -> dict:
        """Returns the paradise jewel data dict, creating a default row if needed."""
        await self._ensure_row(user_id)
        async with self.connection.execute(
            """SELECT user_id, unlocked_skills, equipped_skill, skill_levels,
                      skill_charges, passive_slots, passive_jewels_invested,
                      total_jewels_obtained, total_jewels_consumed
               FROM paradise_jewel_data WHERE user_id = ?""",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return _default_data()
        return _row_to_dict(row)

    async def save(self, user_id: str, data: dict) -> None:
        """Persists the full paradise jewel data dict."""
        await self._ensure_row(user_id)
        await self.connection.execute(
            """UPDATE paradise_jewel_data
               SET unlocked_skills = ?, equipped_skill = ?, skill_levels = ?,
                   skill_charges = ?, passive_slots = ?, passive_jewels_invested = ?,
                   total_jewels_obtained = ?, total_jewels_consumed = ?
               WHERE user_id = ?""",
            (
                json.dumps(data["unlocked_skills"]),
                data.get("equipped_skill"),
                json.dumps(data["skill_levels"]),
                json.dumps(data["skill_charges"]),
                json.dumps(data["passive_slots"]),
                data["passive_jewels_invested"],
                data["total_jewels_obtained"],
                data["total_jewels_consumed"],
                user_id,
            ),
        )
        await self.connection.commit()

    async def update_skill_charges(self, user_id: str, skill_charges: dict) -> None:
        """Lightweight update for charge counters only (called after every combat)."""
        await self._ensure_row(user_id)
        await self.connection.execute(
            "UPDATE paradise_jewel_data SET skill_charges = ? WHERE user_id = ?",
            (json.dumps(skill_charges), user_id),
        )
        await self.connection.commit()

    async def update_skill_levels(self, user_id: str, skill_levels: dict) -> None:
        """Lightweight update for skill level progression."""
        await self._ensure_row(user_id)
        await self.connection.execute(
            "UPDATE paradise_jewel_data SET skill_levels = ? WHERE user_id = ?",
            (json.dumps(skill_levels), user_id),
        )
        await self.connection.commit()

    def passive_slot_count(self, data: dict) -> int:
        """Returns how many passive slots are currently unlocked from invested jewels."""
        invested = data["passive_jewels_invested"]
        count = 0
        for threshold in PASSIVE_SLOT_THRESHOLDS:
            if invested >= threshold:
                count += 1
        return count

    def jewels_needed_for_next_slot(self, data: dict) -> int | None:
        """Returns how many more jewels need to be invested for the next passive slot,
        or None if all 5 slots are already unlocked."""
        invested = data["passive_jewels_invested"]
        for threshold in PASSIVE_SLOT_THRESHOLDS:
            if invested < threshold:
                return threshold - invested
        return None
