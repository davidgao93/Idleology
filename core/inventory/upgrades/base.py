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
        """Fetch raw and refined amounts for ore, log, and bone.
        Returns (mining_res, wood_res, fish_res) as (raw, refined) tuples.
        """
        return await self.bot.database.skills.get_upgrade_materials(uid, gid, cols)

    async def _deduct_smart(
        self,
        table: str,
        raw_col: str,
        ref_col: str,
        raw_held: int,
        cost: int,
        uid: str,
        gid: str,
    ) -> bool:
        """Deduct cost from raw resources first, then spill into refined.
        Returns True if the deduction succeeded."""
        return await self.bot.database.skills.deduct_upgrade_material(
            uid, gid, table, raw_col, ref_col, raw_held, cost
        )

    async def _check_triad_costs(self, costs: dict, uid: str, gid: str) -> tuple:
        """
        Resolve columns, fetch material/gold amounts, evaluate sufficiency,
        and build the display lines + inventory snapshot in one call.

        Returns (has_res: bool, cost_lines: str, snapshot: dict).
        cost_lines contains the ⛏️/🪓/🎣/💰 lines — caller prepends their own header.
        snapshot mirrors the format used by _deduct_smart callsites.
        """
        cols = self._resolve_material_columns(costs)
        mining_res, wood_res, fish_res = await self._fetch_material_amounts(
            cols, uid, gid
        )
        gold = await self.bot.database.users.get_gold(uid)

        total_ore = mining_res[0] + mining_res[1]
        total_log = wood_res[0] + wood_res[1]
        total_bone = fish_res[0] + fish_res[1]

        has_res = (
            total_ore >= costs["ore_qty"]
            and total_log >= costs["log_qty"]
            and total_bone >= costs["bone_qty"]
            and gold >= costs["gold"]
        )

        snapshot = {
            "ore": {**cols["ore"], "raw_amt": mining_res[0], "ref_amt": mining_res[1]},
            "log": {**cols["log"], "raw_amt": wood_res[0], "ref_amt": wood_res[1]},
            "bone": {**cols["bone"], "raw_amt": fish_res[0], "ref_amt": fish_res[1]},
        }

        cost_lines = (
            f"⛏️ {costs['ore_qty']} {costs['ore_type'].title()} (Have: {total_ore})\n"
            f"🪓 {costs['log_qty']} {costs['log_type'].title()} (Have: {total_log})\n"
            f"🎣 {costs['bone_qty']} {costs['bone_type'].title()} (Have: {total_bone})\n"
            f"💰 {costs['gold']:,} Gold"
        )
        if total_ore >= costs["ore_qty"] and mining_res[0] < costs["ore_qty"]:
            cost_lines += "\n*Using Refined Ingots to substitute missing Ore.*"

        return has_res, cost_lines, snapshot

    async def _check_listed_materials(
        self, materials: list, uid: str, sid: str
    ) -> tuple:
        """
        Check a list of {table, column, qty, name} material requirements.
        Returns (has_mats: bool, mat_status: str).
        mat_status is a multi-line string starting with a header, or "" if materials is empty.
        """
        if not materials:
            return True, ""

        has_mats = True
        lines = ["\n**Required Materials:**"]
        for mat in materials:
            owned = await self.bot.database.skills.get_single_resource(
                uid, sid, mat["table"], mat["column"]
            )
            ok = owned >= mat["qty"]
            if not ok:
                has_mats = False
            lines.append(
                f"{'✅' if ok else '❌'} {mat['name']}: {owned:,}/{mat['qty']:,}"
            )

        return has_mats, "\n".join(lines)

    async def go_back(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
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

    async def _send_render(self, interaction: Interaction, embed, view=None):
        """Send or edit the upgrade render embed, then cache the message reference."""
        v = view or self
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=v)
        else:
            await interaction.response.edit_message(embed=embed, view=v)
        self.message = await interaction.original_response()

    def add_back_button(self):
        """Helper to re-add the back button after clearing items."""
        btn = Button(label="Back", style=ButtonStyle.secondary, row=4)
        btn.callback = self.go_back
        self.add_item(btn)
