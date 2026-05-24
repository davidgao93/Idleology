# database/repositories/plots.py
"""Repository for settlement_plots table."""

from __future__ import annotations

import aiosqlite


class PlotRepository:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def ensure_plots(self, user_id: str, server_id: str) -> None:
        """Insert all 20 plot rows (undeveloped) if they don't already exist."""
        for plot_index in range(1, 21):
            await self.connection.execute(
                "INSERT OR IGNORE INTO settlement_plots "
                "(user_id, server_id, plot_index) VALUES (?, ?, ?)",
                (user_id, server_id, plot_index),
            )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_plots(self, user_id: str, server_id: str) -> list:
        """
        Returns all 20 plot rows, initialising them first if needed.
        Each row: (plot_index, is_developed, bonus_type)
        """
        await self.ensure_plots(user_id, server_id)
        async with self.connection.execute(
            "SELECT plot_index, is_developed, bonus_type "
            "FROM settlement_plots "
            "WHERE user_id = ? AND server_id = ? "
            "ORDER BY plot_index ASC",
            (user_id, server_id),
        ) as cursor:
            return await cursor.fetchall()

    async def get_plot(
        self, user_id: str, server_id: str, plot_index: int
    ) -> tuple | None:
        """Returns (plot_index, is_developed, bonus_type) or None."""
        async with self.connection.execute(
            "SELECT plot_index, is_developed, bonus_type "
            "FROM settlement_plots "
            "WHERE user_id = ? AND server_id = ? AND plot_index = ?",
            (user_id, server_id, plot_index),
        ) as cursor:
            return await cursor.fetchone()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def develop_plot(
        self,
        user_id: str,
        server_id: str,
        plot_index: int,
        bonus_type: str,
    ) -> None:
        """Mark a plot as developed and assign its rolled bonus."""
        await self.connection.execute(
            "UPDATE settlement_plots "
            "SET is_developed = 1, bonus_type = ? "
            "WHERE user_id = ? AND server_id = ? AND plot_index = ?",
            (bonus_type, user_id, server_id, plot_index),
        )
        await self.connection.commit()
