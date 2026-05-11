from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView  # note: views.base_view


class BaseUpgradeView(BaseView):
    """Base class for all upgrade interaction views."""

    def __init__(self, bot, user_id: str, item, parent_view):
        super().__init__(bot=bot, user_id=user_id, parent=parent_view)
        self.bot = bot
        self.user_id = user_id
        self.item = item
        self.parent_view = parent_view
        self.embed = None

    # ------------------------------------------------------------------
    # Shared resource helpers (used by ForgeView, TemperView, etc.)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_material_columns(costs: dict) -> dict:
        """Map a costs dict to raw/refined DB column names for ore, log, and bone."""
        raw_ore = costs["ore_type"]
        refined_ore = f"{'steel' if raw_ore == 'coal' else raw_ore}_bar"
        raw_log = costs["log_type"]
        raw_bone = costs["bone_type"]
        return {
            "ore": {"raw_col": raw_ore, "ref_col": refined_ore},
            "log": {"raw_col": f"{raw_log}_logs", "ref_col": f"{raw_log}_plank"},
            "bone": {"raw_col": f"{raw_bone}_bones", "ref_col": f"{raw_bone}_essence"},
        }

    async def _fetch_material_amounts(self, cols: dict, uid: str, gid: str):
        """Fetch raw and refined amounts for ore, log, and bone from the DB.
        Returns (mining_res, wood_res, fish_res) as (raw, refined) tuples.
        """
        async with self.bot.database.connection.execute(
            f"SELECT {cols['ore']['raw_col']}, {cols['ore']['ref_col']} FROM mining WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            mining_res = await cursor.fetchone() or (0, 0)
        async with self.bot.database.connection.execute(
            f"SELECT {cols['log']['raw_col']}, {cols['log']['ref_col']} FROM woodcutting WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            wood_res = await cursor.fetchone() or (0, 0)
        async with self.bot.database.connection.execute(
            f"SELECT {cols['bone']['raw_col']}, {cols['bone']['ref_col']} FROM fishing WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            fish_res = await cursor.fetchone() or (0, 0)
        return mining_res, wood_res, fish_res

    async def _deduct_smart(
        self, table: str, raw_col: str, ref_col: str, raw_held: int, cost: int, uid: str, gid: str
    ):
        """Deduct cost from raw resources first, then spill into refined."""
        to_take_raw = min(raw_held, cost)
        to_take_ref = cost - to_take_raw
        if to_take_raw > 0:
            await self.bot.database.connection.execute(
                f"UPDATE {table} SET {raw_col} = {raw_col} - ? WHERE user_id=? AND server_id=?",
                (to_take_raw, uid, gid),
            )
        if to_take_ref > 0:
            await self.bot.database.connection.execute(
                f"UPDATE {table} SET {ref_col} = {ref_col} - ? WHERE user_id=? AND server_id=?",
                (to_take_ref, uid, gid),
            )

    async def go_back(self, interaction: Interaction):
        # 1. Import inside method to avoid circular import at top of file
        from core.inventory.inventory import InventoryUI
        from core.inventory.views import ItemDetailView

        # 2. Get the Grandparent (Inventory List) to pass down
        inventory_view = self.parent_view.parent

        # 3. Create a FRESH ItemDetailView
        # This resets the timeout counter (180s) and regenerates buttons cleanly
        new_detail_view = ItemDetailView(
            self.bot, self.user_id, self.item, inventory_view
        )
        await new_detail_view.fetch_data()  # Ensure keys/currency checks run

        # 4. Check equipped status using the Grandparent's state
        is_equipped = self.item.item_id == inventory_view.equipped_id

        embed = InventoryUI.get_item_details_embed(self.item, is_equipped)

        # 5. Edit message with NEW view and clear any status content
        await interaction.response.edit_message(
            content=None, embed=embed, view=new_detail_view
        )
        self.stop()

    def add_back_button(self):
        """Helper to re-add the back button after clearing items."""
        btn = Button(label="Back", style=ButtonStyle.secondary, row=4)
        btn.callback = self.go_back
        self.add_item(btn)
