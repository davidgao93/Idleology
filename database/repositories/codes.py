import json

import aiosqlite


class CodesRepository:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def get_code(self, code: str) -> dict | None:
        cursor = await self.connection.execute(
            "SELECT * FROM redeem_codes WHERE code = ?", (code.upper(),)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def has_redeemed(self, code: str, user_id: str) -> bool:
        cursor = await self.connection.execute(
            "SELECT 1 FROM code_redemptions WHERE code = ? AND user_id = ?",
            (code.upper(), user_id),
        )
        return await cursor.fetchone() is not None

    async def record_redemption(self, code: str, user_id: str) -> None:
        await self.connection.execute(
            "INSERT OR IGNORE INTO code_redemptions (code, user_id) VALUES (?, ?)",
            (code.upper(), user_id),
        )
        await self.connection.execute(
            "UPDATE redeem_codes SET total_uses = total_uses + 1 WHERE code = ?",
            (code.upper(),),
        )
        await self.connection.commit()

    async def create_code(
        self,
        code: str,
        rewards: dict,
        max_uses: int | None = None,
        is_admin_only: bool = False,
        expires_at: str | None = None,
    ) -> None:
        await self.connection.execute(
            "INSERT INTO redeem_codes (code, rewards, max_uses, is_admin_only, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                code.upper(),
                json.dumps(rewards),
                max_uses,
                int(is_admin_only),
                expires_at,
            ),
        )
        await self.connection.commit()
