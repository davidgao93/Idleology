import random

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import Button, Select, View

from core.companions.mechanics import CompanionMechanics
from core.items.equipment_mechanics import EquipmentMechanics
from core.items.factory import create_weapon
from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon


class BaseUpgradeView(View):
    """Base class for all upgrade interaction views."""

    def __init__(self, bot, user_id: str, item, parent_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.item = item
        self.parent_view = parent_view
        self.embed = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            await self.parent_view.message.edit(view=self.parent_view)
        except:
            pass

    async def go_back(self, interaction: Interaction):
        # 1. Import inside method to avoid circular import at top of file
        from core.inventory.views import ItemDetailView
        from core.ui.inventory import InventoryUI

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


class ForgeView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        costs = EquipmentMechanics.calculate_forge_cost(self.item)
        if not costs:
            return await interaction.response.send_message(
                "No forges remaining!", ephemeral=True
            )

        # Fetch Resources
        uid, gid = self.user_id, str(interaction.guild.id)
        # 1. Fetch Raw AND Refined
        # We need to map raw resource names to their refined counterparts in the DB
        # Iron -> iron_bar, Coal -> steel_bar, Gold -> gold_bar, etc.
        raw_ore = costs["ore_type"]
        refined_ore = f"{raw_ore if raw_ore != 'coal' else 'steel'}_bar"  # Coal -> Steel special case

        raw_log = costs["log_type"]
        refined_log = f"{raw_log}_plank"

        raw_bone = costs["bone_type"]
        refined_bone = f"{raw_bone}_essence"

        # Fetch quantities via helper to handle DB tuple mapping
        # (Assuming TradeManager logic or direct SQL here for precision)
        # For simplicity in this example, we execute a direct select
        async with self.bot.database.connection.execute(
            f"SELECT {raw_ore}, {refined_ore} FROM mining WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            mining_res = await cursor.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {raw_log}_logs, {refined_log} FROM woodcutting WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            wood_res = await cursor.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {raw_bone}_bones, {refined_bone} FROM fishing WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            fish_res = await cursor.fetchone() or (0, 0)

        gold = await self.bot.database.users.get_gold(uid)

        # 2. Logic: Total Available = Raw + Refined
        total_ore = mining_res[0] + mining_res[1]
        total_log = wood_res[0] + wood_res[1]
        total_bone = fish_res[0] + fish_res[1]

        has_res = (
            total_ore >= costs["ore_qty"]
            and total_log >= costs["log_qty"]
            and total_bone >= costs["bone_qty"]
            and gold >= costs["gold"]
        )

        # 3. Store data for logic
        self.costs = costs
        self.inventory_snapshot = {
            "ore": {
                "raw_col": raw_ore,
                "ref_col": refined_ore,
                "raw_amt": mining_res[0],
                "ref_amt": mining_res[1],
            },
            "log": {
                "raw_col": f"{raw_log}_logs",
                "ref_col": refined_log,
                "raw_amt": wood_res[0],
                "ref_amt": wood_res[1],
            },
            "bone": {
                "raw_col": f"{raw_bone}_bones",
                "ref_col": refined_bone,
                "raw_amt": fish_res[0],
                "ref_amt": fish_res[1],
            },
        }

        desc = (
            f"**Cost:**\n"
            f"⛏️ {costs['ore_qty']} {costs['ore_type'].title()} (Have: {total_ore})\n"
            f"🪓 {costs['log_qty']} {costs['log_type'].title()} (Have: {total_log})\n"
            f"🎣 {costs['bone_qty']} {costs['bone_type'].title()} (Have: {total_bone})\n"
            f"💰 {costs['gold']:,} Gold"
        )

        if total_ore >= costs["ore_qty"] and mining_res[0] < costs["ore_qty"]:
            desc += "\n*Using Refined Ingots to substitute missing Ore.*"

        self.embed = discord.Embed(
            title=f"Forge {self.item.name}",
            description=desc,
            color=discord.Color.green() if has_res else discord.Color.red(),
        )
        self.embed.set_thumbnail(url="https://i.imgur.com/jzEMUxe.jpeg")

        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()

        forge_btn = Button(
            label="Forge!", style=ButtonStyle.success, disabled=not has_res
        )
        forge_btn.callback = self.confirm_forge
        self.add_item(forge_btn)

        forgemaxx_btn = Button(
            label="Forgemaxx", style=ButtonStyle.danger, disabled=not has_res
        )
        forgemaxx_btn.callback = self.forgemaxx
        self.add_item(forgemaxx_btn)

        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirm_forge(self, interaction: Interaction):
        uid, gid = self.user_id, str(interaction.guild.id)

        # Helper for atomic deduction
        # Logic: Deduct from Raw first. If goes negative, add back to Raw (set to 0) and deduct remainder from Refined.
        async def deduct_smart(table, raw_col, ref_col, raw_held, cost):
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

        # Re-fetch live inventory counts so that any settlement collection that ran
        # between render and confirm doesn't cause raw columns to go negative.
        ore = self.inventory_snapshot["ore"]
        log = self.inventory_snapshot["log"]
        bone = self.inventory_snapshot["bone"]

        async with self.bot.database.connection.execute(
            f"SELECT {ore['raw_col']}, {ore['ref_col']} FROM mining WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cur:
            live_ore = await cur.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {log['raw_col']}, {log['ref_col']} FROM woodcutting WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cur:
            live_log = await cur.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {bone['raw_col']}, {bone['ref_col']} FROM fishing WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cur:
            live_bone = await cur.fetchone() or (0, 0)

        # Execute Deductions
        await deduct_smart(
            "mining",
            ore["raw_col"],
            ore["ref_col"],
            live_ore[0],
            self.costs["ore_qty"],
        )
        await deduct_smart(
            "woodcutting",
            log["raw_col"],
            log["ref_col"],
            live_log[0],
            self.costs["log_qty"],
        )
        await deduct_smart(
            "fishing",
            bone["raw_col"],
            bone["ref_col"],
            live_bone[0],
            self.costs["bone_qty"],
        )

        await self.bot.database.users.modify_gold(uid, -self.costs["gold"])
        await self.bot.database.connection.commit()

        success, new_passive = EquipmentMechanics.roll_forge_outcome(self.item)

        result_embed = discord.Embed(title="Forge Result")
        if success:
            self.item.forges_remaining -= 1  # Only decrement on success
            self.item.passive = new_passive
            self.item.forge_tier += 1
            await self.bot.database.equipment.update_passive(
                self.item.item_id, "weapon", new_passive
            )
            await self.bot.database.equipment.update_counter(
                self.item.item_id, "weapon", "forges_remaining", self.item.forges_remaining,
            )
            await self.bot.database.equipment.update_counter(
                self.item.item_id, "weapon", "forge_tier", self.item.forge_tier,
            )

            result_embed.description = (
                f"🔥 **Success!**\nNew Passive: **{new_passive.title()}**"
            )
            result_embed.color = discord.Color.gold()
        else:
            self.item.forges_remaining -= 1
            await self.bot.database.equipment.update_counter(
                self.item.item_id, "weapon", "forges_remaining", self.item.forges_remaining,
            )
            result_embed.description = f"💨 **Failed.**\nThe hammer didn't strike true, resources consumed.\n\nForges Remaining: {self.item.forges_remaining}"
            result_embed.color = discord.Color.dark_grey()

        # --- RESULT UI BUILD ---
        self.clear_items()

        if self.item.forges_remaining > 0:
            again_btn = Button(label="Forge Again", style=ButtonStyle.success)
            again_btn.callback = self.render
            self.add_item(again_btn)

            forgemaxx_btn = Button(label="Forgemaxx", style=ButtonStyle.danger)
            forgemaxx_btn.callback = self.forgemaxx
            self.add_item(forgemaxx_btn)

        self.add_back_button()

        await interaction.response.edit_message(embed=result_embed, view=self)

    async def forgemaxx(self, interaction: Interaction):
        """Loop-forge until the player runs out of resources or forge slots."""
        await interaction.response.defer()
        uid, gid = self.user_id, str(interaction.guild.id)
        forges_done = 0
        successes = 0
        final_passive = self.item.passive

        while self.item.forges_remaining > 0:
            costs = EquipmentMechanics.calculate_forge_cost(self.item)
            if not costs:
                break

            # Re-fetch inventory for current cost tier
            raw_ore = costs["ore_type"]
            refined_ore = f"{raw_ore if raw_ore != 'coal' else 'steel'}_bar"
            raw_log = costs["log_type"]
            refined_log = f"{raw_log}_plank"
            raw_bone = costs["bone_type"]
            refined_bone = f"{raw_bone}_essence"

            async with self.bot.database.connection.execute(
                f"SELECT {raw_ore}, {refined_ore} FROM mining WHERE user_id=? AND server_id=?",
                (uid, gid),
            ) as cursor:
                mining_res = await cursor.fetchone() or (0, 0)
            async with self.bot.database.connection.execute(
                f"SELECT {raw_log}_logs, {refined_log} FROM woodcutting WHERE user_id=? AND server_id=?",
                (uid, gid),
            ) as cursor:
                wood_res = await cursor.fetchone() or (0, 0)
            async with self.bot.database.connection.execute(
                f"SELECT {raw_bone}_bones, {refined_bone} FROM fishing WHERE user_id=? AND server_id=?",
                (uid, gid),
            ) as cursor:
                fish_res = await cursor.fetchone() or (0, 0)

            gold = await self.bot.database.users.get_gold(uid)
            total_ore = mining_res[0] + mining_res[1]
            total_log = wood_res[0] + wood_res[1]
            total_bone = fish_res[0] + fish_res[1]

            if total_ore < costs["ore_qty"] or total_log < costs["log_qty"] or total_bone < costs["bone_qty"] or gold < costs["gold"]:
                break

            # Deduct materials
            async def deduct_smart(table, raw_col, ref_col, raw_held, cost):
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

            await deduct_smart("mining", raw_ore, refined_ore, mining_res[0], costs["ore_qty"])
            await deduct_smart("woodcutting", f"{raw_log}_logs", refined_log, wood_res[0], costs["log_qty"])
            await deduct_smart("fishing", f"{raw_bone}_bones", refined_bone, fish_res[0], costs["bone_qty"])
            await self.bot.database.users.modify_gold(uid, -costs["gold"])
            await self.bot.database.connection.commit()

            success, new_passive = EquipmentMechanics.roll_forge_outcome(self.item)
            self.item.forges_remaining -= 1
            forges_done += 1

            if success:
                successes += 1
                self.item.passive = new_passive
                self.item.forge_tier += 1
                final_passive = new_passive
                await self.bot.database.equipment.update_passive(
                    self.item.item_id, "weapon", new_passive
                )
                await self.bot.database.equipment.update_counter(
                    self.item.item_id, "weapon", "forge_tier", self.item.forge_tier,
                )

            await self.bot.database.equipment.update_counter(
                self.item.item_id, "weapon", "forges_remaining", self.item.forges_remaining,
            )

        result_embed = discord.Embed(
            title="⚒️ Forgemaxx Complete",
            description=(
                f"**Attempts:** {forges_done}  |  **Successes:** {successes}\n"
                f"**Final Passive:** {final_passive.title() if final_passive != 'none' else 'None'}\n"
                f"**Forges Remaining:** {self.item.forges_remaining}"
            ),
            color=discord.Color.gold() if successes > 0 else discord.Color.dark_grey(),
        )
        result_embed.set_thumbnail(url="https://i.imgur.com/jzEMUxe.jpeg")

        self.clear_items()
        self.add_back_button()
        await interaction.edit_original_response(embed=result_embed, view=self)


class RefineView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self.cost_data = {}  # Store calculated costs

    async def render(self, interaction: Interaction):
        # 1. Calculate Costs
        self.cost_data = EquipmentMechanics.calculate_refine_cost(self.item)
        cost_gold = self.cost_data["gold"]
        materials = self.cost_data.get("materials", [])

        # 2. Fetch User Data (Gold & Materials)
        uid, sid = self.user_id, str(interaction.guild.id)
        user_gold = await self.bot.database.users.get_gold(uid)

        has_funds = user_gold >= cost_gold
        has_mats = True

        # Build Material Status String & Check sufficiency
        mat_status = ""
        if materials:
            mat_status = "\n**Required Materials:**"
            for mat in materials:
                # Fetch balance
                # Note: TradeManager logic or raw SQL. Raw SQL is safest here for atomic check.
                table = mat["table"]
                col = mat["column"]
                qty = mat["qty"]
                name = mat["name"]

                async with self.bot.database.connection.execute(
                    f"SELECT {col} FROM {table} WHERE user_id=? AND server_id=?",
                    (uid, sid),
                ) as c:
                    row = await c.fetchone()
                    owned = row[0] if row else 0

                status_icon = "✅" if owned >= qty else "❌"
                if owned < qty:
                    has_mats = False

                mat_status += f"\n{status_icon} {name}: {owned:,}/{qty:,}"

        # 3. Logic
        has_refines = self.item.refines_remaining > 0
        runes = await self.bot.database.users.get_currency(
            self.user_id, "refinement_runes"
        )

        desc = (
            f"**Refines Remaining:** {self.item.refines_remaining}\n"
            f"**Refinement Level:** +{self.item.refinement_lvl}\n"
            f"**Gold Cost:** {cost_gold:,} ({user_gold:,})"
        )

        if mat_status:
            desc += f"\n{mat_status}"

        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()

        action_btn = Button(label="Refine", style=ButtonStyle.success)

        if not has_refines:
            desc += (
                f"\n\n**0 Refines left!** Use a Rune to add a slot? (Owned: {runes})"
            )
            action_btn.label = "Use Rune"
            action_btn.style = ButtonStyle.primary
            action_btn.disabled = runes == 0
        else:
            action_btn.disabled = not (has_funds and has_mats)

        action_btn.callback = self.confirm_refine
        self.add_item(action_btn)

        if has_refines and has_funds and has_mats:
            maxx_btn = Button(label="Refinemaxx", style=ButtonStyle.danger)
            maxx_btn.callback = self.refinemaxx
            self.add_item(maxx_btn)

        if runes > 0:
            maxx_rune_btn = Button(label="Refinemaxx ✨", style=ButtonStyle.danger)
            maxx_rune_btn.callback = self.refinemaxx_with_runes_preview
            self.add_item(maxx_rune_btn)

        self.add_back_button()

        color = (
            discord.Color.blue() if (has_funds and has_mats) else discord.Color.red()
        )
        self.embed = discord.Embed(
            title=f"Refine {self.item.name}", description=desc, color=color
        )
        self.embed.set_thumbnail(url="https://i.imgur.com/NNB21Ix.jpeg")

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirm_refine(self, interaction: Interaction):
        # 1. Rune Logic (Adding Slot) - No Mat Cost
        if self.item.refines_remaining <= 0:
            await self.bot.database.users.modify_currency(
                self.user_id, "refinement_runes", -1
            )
            await self.bot.database.equipment.update_counter(
                self.item.item_id, "weapon", "refines_remaining", 1
            )
            self.item.refines_remaining += 1
            await self.render(interaction)  # Refresh UI immediately
            return

        # 2. Refine Logic (Consuming Slot) - Costs Apply

        # Verify Gold
        cost_gold = self.cost_data["gold"]

        # Verify Materials (DB Atomic Update check)
        materials = self.cost_data.get("materials", [])
        uid, sid = self.user_id, str(interaction.guild.id)

        await interaction.response.defer()

        try:
            # Deduct Mats
            for mat in materials:
                table = mat["table"]
                col = mat["column"]
                qty = mat["qty"]

                # Update with check
                async with self.bot.database.connection.execute(
                    f"UPDATE {table} SET {col} = {col} - ? WHERE user_id=? AND server_id=? AND {col} >= ?",
                    (qty, uid, sid, qty),
                ) as c:
                    if c.rowcount == 0:
                        return await interaction.followup.send(
                            f"Insufficient {mat['name']}!", ephemeral=True
                        )

            # Deduct Gold
            await self.bot.database.users.modify_gold(self.user_id, -cost_gold)

            # Apply Stats
            stats = EquipmentMechanics.roll_refine_outcome(self.item)

            if stats["attack"]:
                self.item.attack += stats["attack"]
                await self.bot.database.equipment.increase_stat(
                    self.item.item_id, "weapon", "attack", stats["attack"]
                )
            if stats["defence"]:
                self.item.defence += stats["defence"]
                await self.bot.database.equipment.increase_stat(
                    self.item.item_id, "weapon", "defence", stats["defence"]
                )
            if stats["rarity"]:
                self.item.rarity += stats["rarity"]
                await self.bot.database.equipment.increase_stat(
                    self.item.item_id, "weapon", "rarity", stats["rarity"]
                )

            self.item.refines_remaining -= 1
            self.item.refinement_lvl += 1

            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "weapon",
                "refines_remaining",
                self.item.refines_remaining,
            )
            await self.bot.database.equipment.increase_stat(
                self.item.item_id, "weapon", "refinement_lvl", 1
            )
            await self.bot.database.connection.commit()

            # Result UI
            res_str = (
                ", ".join([f"+{v} {k.title()}" for k, v in stats.items() if v > 0])
                or "No stats gained."
            )

            embed = discord.Embed(
                title="Refine Complete! ✨", color=discord.Color.green()
            )
            embed.set_thumbnail(url="https://i.imgur.com/NNB21Ix.jpeg")
            embed.description = (
                f"**Gains:** {res_str}\n"
                f"**Refinement:** +{self.item.refinement_lvl}\n\n"
                f"**New Stats:**\n⚔️ {self.item.attack} | 🛡️ {self.item.defence} | ✨ {self.item.rarity}%"
            )

            # --- RESULT UI BUILD ---
            self.clear_items()

            # Allow chain refining
            runes = await self.bot.database.users.get_currency(
                self.user_id, "refinement_runes"
            )
            if self.item.refines_remaining > 0 or runes > 0:
                again_btn = Button(label="Refine Again", style=ButtonStyle.primary)
                again_btn.callback = self.render
                self.add_item(again_btn)

            self.add_back_button()

            await interaction.edit_original_response(embed=embed, view=self)

        except Exception as e:
            self.bot.logger.error(f"Refine Error: {e}")
            await interaction.followup.send(
                "An error occurred processing the refinement.", ephemeral=True
            )

    async def refinemaxx(self, interaction: Interaction):
        """Loop-refine until the player runs out of a required resource."""
        await interaction.response.defer()

        uid, sid = self.user_id, str(interaction.guild.id)
        refines_done = 0
        total_gains = {"attack": 0, "defence": 0, "rarity": 0}
        stop_reason = "Refines exhausted."

        while True:
            if self.item.refines_remaining <= 0:
                stop_reason = "No refine slots remaining."
                break

            cost_data = EquipmentMechanics.calculate_refine_cost(self.item)
            cost_gold = cost_data["gold"]
            materials = cost_data.get("materials", [])

            # Check gold
            user_gold = await self.bot.database.users.get_gold(uid)
            if user_gold < cost_gold:
                stop_reason = "Ran out of Gold."
                break

            # Check materials
            insufficient = None
            for mat in materials:
                async with self.bot.database.connection.execute(
                    f"SELECT {mat['column']} FROM {mat['table']} WHERE user_id=? AND server_id=?",
                    (uid, sid),
                ) as c:
                    row = await c.fetchone()
                    owned = row[0] if row else 0
                if owned < mat["qty"]:
                    insufficient = mat["name"]
                    break

            if insufficient:
                stop_reason = f"Ran out of {insufficient}."
                break

            # Deduct materials
            failed = False
            for mat in materials:
                async with self.bot.database.connection.execute(
                    f"UPDATE {mat['table']} SET {mat['column']} = {mat['column']} - ? "
                    f"WHERE user_id=? AND server_id=? AND {mat['column']} >= ?",
                    (mat["qty"], uid, sid, mat["qty"]),
                ) as c:
                    if c.rowcount == 0:
                        failed = True
                        stop_reason = f"Ran out of {mat['name']}."
                        break
            if failed:
                break

            # Deduct gold
            await self.bot.database.users.modify_gold(uid, -cost_gold)

            # Apply stats
            stats = EquipmentMechanics.roll_refine_outcome(self.item)
            for key in ("attack", "defence", "rarity"):
                if stats[key]:
                    # Fix: Replaced __dict__ update with proper setattr
                    # ensuring Pydantic models or slots behave as expected.
                    setattr(self.item, key, getattr(self.item, key) + stats[key])
                    total_gains[key] += stats[key]
                    await self.bot.database.equipment.increase_stat(
                        self.item.item_id, "weapon", key, stats[key]
                    )

            self.item.refines_remaining -= 1
            self.item.refinement_lvl += 1
            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "weapon",
                "refines_remaining",
                self.item.refines_remaining,
            )
            await self.bot.database.equipment.increase_stat(
                self.item.item_id, "weapon", "refinement_lvl", 1
            )
            await self.bot.database.connection.commit()
            refines_done += 1

        if refines_done == 0:
            await interaction.followup.send(stop_reason, ephemeral=True)
            return

        gains_str = (
            ", ".join([f"+{v} {k.title()}" for k, v in total_gains.items() if v > 0])
            or "No stat gains."
        )

        embed = discord.Embed(
            title="Refinemaxx Complete! ⚡", color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://i.imgur.com/NNB21Ix.jpeg")
        embed.description = (
            f"**Refines Performed:** {refines_done}\n"
            f"**Stopped Because:** {stop_reason}\n\n"
            f"**Total Gains:** {gains_str}\n"
            f"**Refinement Level:** +{self.item.refinement_lvl}\n\n"
            f"**New Stats:**\n⚔️ {self.item.attack} | 🛡️ {self.item.defence} | ✨ {self.item.rarity}%"
        )

        self.clear_items()
        runes = await self.bot.database.users.get_currency(
            self.user_id, "refinement_runes"
        )
        if self.item.refines_remaining > 0 or runes > 0:
            again_btn = Button(label="Back to Refine", style=ButtonStyle.primary)
            again_btn.callback = self.render
            self.add_item(again_btn)
        self.add_back_button()

        await interaction.edit_original_response(embed=embed, view=self)

    async def refinemaxx_with_runes_preview(self, interaction: Interaction):
        """Simulate the full rune-extended refinemaxx and show a confirmation screen."""
        await interaction.response.defer()
        uid, sid = self.user_id, str(interaction.guild.id)

        runes = await self.bot.database.users.get_currency(uid, "refinement_runes")
        if runes == 0:
            await interaction.followup.send(
                "You have no Refinement Runes.", ephemeral=True
            )
            return

        gold = await self.bot.database.users.get_gold(uid)

        # Fetch all material quantities that refining could ever require
        all_mat_cols = {
            "mining": ["iron_bar", "steel_bar", "gold_bar", "platinum_bar", "idea_bar"],
            "woodcutting": [
                "oak_plank",
                "willow_plank",
                "mahogany_plank",
                "magic_plank",
                "idea_plank",
            ],
            "fishing": [
                "desiccated_essence",
                "regular_essence",
                "sturdy_essence",
                "reinforced_essence",
                "titanium_essence",
            ],
        }
        sim_mats = {}
        for table, cols in all_mat_cols.items():
            col_str = ", ".join(cols)
            async with self.bot.database.connection.execute(
                f"SELECT {col_str} FROM {table} WHERE user_id=? AND server_id=?",
                (uid, sid),
            ) as c:
                row = await c.fetchone()
                for i, col in enumerate(cols):
                    sim_mats[col] = row[i] if row and row[i] else 0

        # Simulate the full loop
        import copy

        sim = copy.copy(self.item)
        sim_runes = runes
        sim_gold = gold
        total_cycles = 0
        runes_used = 0
        gold_used = 0
        mat_used = {}
        stop_reason = ""

        while True:
            if sim.refines_remaining == 0:
                if sim_runes == 0:
                    stop_reason = "Ran out of Refinement Runes."
                    break
                sim_runes -= 1
                sim.refines_remaining = 1
                runes_used += 1

            cost_data = EquipmentMechanics.calculate_refine_cost(sim)
            cost_gold = cost_data["gold"]
            materials = cost_data.get("materials", [])

            if sim_gold < cost_gold:
                stop_reason = "Ran out of Gold."
                break

            short = next(
                (m for m in materials if sim_mats.get(m["column"], 0) < m["qty"]), None
            )
            if short:
                stop_reason = f"Ran out of {short['name']}."
                break

            sim_gold -= cost_gold
            gold_used += cost_gold
            for mat in materials:
                sim_mats[mat["column"]] -= mat["qty"]
                mat_used[mat["name"]] = mat_used.get(mat["name"], 0) + mat["qty"]

            sim.refines_remaining -= 1
            sim.refinement_lvl += 1
            total_cycles += 1

            if total_cycles >= 10000:
                stop_reason = "Reached simulation cap (10,000 refines)."
                break

        if total_cycles == 0:
            await interaction.followup.send(
                f"No refines possible: {stop_reason}", ephemeral=True
            )
            return

        mat_lines = (
            "\n".join(f"  {name}: {qty:,}" for name, qty in mat_used.items())
            or "  None"
        )

        embed = discord.Embed(
            title="⚠️ Refinemaxx ✨ Confirmation", color=discord.Color.orange()
        )
        embed.set_thumbnail(url="https://i.imgur.com/NNB21Ix.jpeg")
        embed.description = (
            f"This will perform **{total_cycles:,}** refine(s) using up to **{runes_used}** Rune(s).\n\n"
            f"**Estimated Resources Consumed:**\n"
            f"💰 Gold: {gold_used:,}\n"
            f"💎 Refinement Runes: {runes_used}\n"
            f"📦 Materials:\n{mat_lines}\n\n"
            f"*Stops when: {stop_reason}*\n\n"
            f"Proceed?"
        )

        self.clear_items()
        confirm_btn = Button(label="Confirm", style=ButtonStyle.danger)
        confirm_btn.callback = self.refinemaxx_with_runes_execute
        self.add_item(confirm_btn)

        cancel_btn = Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self.render
        self.add_item(cancel_btn)

        await interaction.edit_original_response(embed=embed, view=self)

    async def refinemaxx_with_runes_execute(self, interaction: Interaction):
        """Execute the rune-extended refinemaxx after confirmation."""
        await interaction.response.defer()
        uid, sid = self.user_id, str(interaction.guild.id)

        refines_done = 0
        runes_used = 0
        total_gains = {"attack": 0, "defence": 0, "rarity": 0}
        stop_reason = "Complete."

        while True:
            if self.item.refines_remaining == 0:
                runes = await self.bot.database.users.get_currency(
                    uid, "refinement_runes"
                )
                if runes == 0:
                    stop_reason = "Ran out of Refinement Runes."
                    break
                await self.bot.database.users.modify_currency(
                    uid, "refinement_runes", -1
                )
                await self.bot.database.equipment.update_counter(
                    self.item.item_id, "weapon", "refines_remaining", 1
                )
                self.item.refines_remaining = 1
                runes_used += 1

            cost_data = EquipmentMechanics.calculate_refine_cost(self.item)
            cost_gold = cost_data["gold"]
            materials = cost_data.get("materials", [])

            user_gold = await self.bot.database.users.get_gold(uid)
            if user_gold < cost_gold:
                stop_reason = "Ran out of Gold."
                break

            failed_mat = None
            for mat in materials:
                async with self.bot.database.connection.execute(
                    f"UPDATE {mat['table']} SET {mat['column']} = {mat['column']} - ? "
                    f"WHERE user_id=? AND server_id=? AND {mat['column']} >= ?",
                    (mat["qty"], uid, sid, mat["qty"]),
                ) as c:
                    if c.rowcount == 0:
                        failed_mat = mat["name"]
                        break
            if failed_mat:
                stop_reason = f"Ran out of {failed_mat}."
                break

            await self.bot.database.users.modify_gold(uid, -cost_gold)

            stats = EquipmentMechanics.roll_refine_outcome(self.item)
            for key in ("attack", "defence", "rarity"):
                if stats[key]:
                    # Fix: Replaced __dict__ update with proper setattr
                    # ensuring Pydantic models or slots behave as expected.
                    setattr(self.item, key, getattr(self.item, key) + stats[key])
                    total_gains[key] += stats[key]
                    await self.bot.database.equipment.increase_stat(
                        self.item.item_id, "weapon", key, stats[key]
                    )

            self.item.refines_remaining -= 1
            self.item.refinement_lvl += 1
            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "weapon",
                "refines_remaining",
                self.item.refines_remaining,
            )
            await self.bot.database.equipment.increase_stat(
                self.item.item_id, "weapon", "refinement_lvl", 1
            )
            await self.bot.database.connection.commit()
            refines_done += 1

        gains_str = (
            ", ".join(f"+{v} {k.title()}" for k, v in total_gains.items() if v > 0)
            or "No stat gains."
        )

        embed = discord.Embed(
            title="Refinemaxx ✨ Complete!", color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://i.imgur.com/NNB21Ix.jpeg")
        embed.description = (
            f"**Refines Performed:** {refines_done:,}\n"
            f"**Runes Consumed:** {runes_used}\n"
            f"**Stopped Because:** {stop_reason}\n\n"
            f"**Total Gains:** {gains_str}\n"
            f"**Refinement Level:** +{self.item.refinement_lvl}\n\n"
            f"**New Stats:**\n⚔️ {self.item.attack} | 🛡️ {self.item.defence} | ✨ {self.item.rarity}%"
        )

        self.clear_items()
        self.add_back_button()
        await interaction.edit_original_response(embed=embed, view=self)


class PotentialView(BaseUpgradeView):
    def __init__(self, bot, user_id, item, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        # 1. Determine Item Type & Bonus
        is_accessory = isinstance(self.item, Accessory)
        if is_accessory:
            cost = EquipmentMechanics.calculate_potential_cost(self.item.passive_lvl)
            max_lvl = 10
            rune_bonus = 25
        else:
            cost = EquipmentMechanics.calculate_ap_cost(self.item.passive_lvl)
            max_lvl = 5 if isinstance(self.item, (Glove, Helmet)) else 6
            rune_bonus = 15

        # 2. Fetch User Data
        gold = await self.bot.database.users.get_gold(self.user_id)
        runes = await self.bot.database.users.get_currency(
            self.user_id, "potential_runes"
        )

        # 3. Logic
        is_capped = self.item.passive_lvl >= max_lvl
        has_attempts = self.item.potential_remaining > 0
        base_rate = max(75 - (self.item.passive_lvl * 5), 30)

        desc = (
            f"**Current Level:** {self.item.passive_lvl}/{max_lvl}\n"
            f"**Attempts Left:** {self.item.potential_remaining}\n"
            f"**Success Rate:** {base_rate}%\n"
            f"**Cost:** {cost:,} Gold ({gold:,})\n\n"
            f"💎 **Runes Owned:** {runes}"
        )

        self.cost = cost
        self.rune_bonus = rune_bonus

        embed = discord.Embed(
            title=f"Enchant {self.item.name}",
            description=desc,
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/hqVvn68.jpeg")

        # --- BUTTONS ---
        self.clear_items()

        # Standard Enchant
        btn_std = Button(
            label=f"Enchant ({base_rate}%)", style=ButtonStyle.primary, row=0
        )
        btn_std.disabled = gold < cost or not has_attempts or is_capped
        btn_std.callback = lambda i: self.confirm_enchant(i, use_rune=False)
        self.add_item(btn_std)

        # Rune Enchant
        boosted_rate = min(100, base_rate + rune_bonus)
        btn_rune = Button(
            label=f"Use Rune ({boosted_rate}%)",
            style=ButtonStyle.success,
            emoji="💎",
            row=0,
        )
        btn_rune.disabled = gold < cost or not has_attempts or is_capped or runes < 1
        btn_rune.callback = lambda i: self.confirm_enchant(i, use_rune=True)
        self.add_item(btn_rune)

        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_enchant(self, interaction: Interaction, use_rune: bool):
        # Re-check funds/runes
        if use_rune:
            runes = await self.bot.database.users.get_currency(
                self.user_id, "potential_runes"
            )
            if runes < 1:
                return await interaction.response.send_message(
                    "No Runes left!", ephemeral=True
                )
            await self.bot.database.users.modify_currency(
                self.user_id, "potential_runes", -1
            )
            bonus = self.rune_bonus
        else:
            bonus = 0

        # Deduct Gold
        await self.bot.database.users.modify_gold(self.user_id, -self.cost)

        # Roll
        success = EquipmentMechanics.roll_potential_outcome(
            self.item.passive_lvl, bonus_chance=bonus
        )

        # DB Updates
        itype = (
            "accessory"
            if isinstance(self.item, Accessory)
            else (
                "glove"
                if isinstance(self.item, Glove)
                else ("boot" if isinstance(self.item, Boot) else "helmet")
            )
        )

        self.item.potential_remaining -= 1
        await self.bot.database.equipment.update_counter(
            self.item.item_id,
            itype,
            "potential_remaining",
            self.item.potential_remaining,
        )

        result_embed = discord.Embed(title="Enchantment Result")
        result_embed.set_thumbnail(url="https://i.imgur.com/hqVvn68.jpeg")

        if success:
            if self.item.passive == "none":
                new_p = EquipmentMechanics.get_new_passive(itype)
                self.item.passive = new_p
                self.item.passive_lvl = 1
                await self.bot.database.equipment.update_passive(
                    self.item.item_id, itype, new_p
                )
                await self.bot.database.equipment.update_counter(
                    self.item.item_id, itype, "passive_lvl", 1
                )
                msg = f"Unlocked **{new_p}**!"
            else:
                self.item.passive_lvl += 1
                await self.bot.database.equipment.update_counter(
                    self.item.item_id, itype, "passive_lvl", self.item.passive_lvl
                )
                msg = f"Upgraded to Level **{self.item.passive_lvl}**!"

            result_embed.color = discord.Color.gold()
            result_embed.description = f"✨ **Success!**\n{msg}"
        else:
            result_embed.color = discord.Color.dark_grey()
            result_embed.description = "💔 **Failed.**\nThe magic failed to take hold."

        # UI Refresh
        self.clear_items()
        max_lvl = (
            10
            if isinstance(self.item, Accessory)
            else (5 if isinstance(self.item, (Glove, Helmet)) else 6)
        )
        if self.item.potential_remaining > 0 and self.item.passive_lvl < max_lvl:
            again_btn = Button(label="Enchant Again", style=ButtonStyle.primary)
            again_btn.callback = self.render
            self.add_item(again_btn)

        self.add_back_button()
        await interaction.response.edit_message(embed=result_embed, view=self)


class TemperView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Armor, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        costs = EquipmentMechanics.calculate_temper_cost(self.item)
        if not costs:
            return await interaction.response.send_message(
                "No tempers remaining.", ephemeral=True
            )

        uid, gid = self.user_id, str(interaction.guild.id)

        # 1. Fetch Raw AND Refined (Mapped Identically to ForgeView)
        raw_ore = costs["ore_type"]
        refined_ore = f"{raw_ore if raw_ore != 'coal' else 'steel'}_bar"

        raw_log = costs["log_type"]
        refined_log = f"{raw_log}_plank"

        raw_bone = costs["bone_type"]
        refined_bone = f"{raw_bone}_essence"

        # Direct SQL fetch for precision
        async with self.bot.database.connection.execute(
            f"SELECT {raw_ore}, {refined_ore} FROM mining WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            mining_res = await cursor.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {raw_log}_logs, {refined_log} FROM woodcutting WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            wood_res = await cursor.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {raw_bone}_bones, {refined_bone} FROM fishing WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cursor:
            fish_res = await cursor.fetchone() or (0, 0)

        gold = await self.bot.database.users.get_gold(uid)

        # 2. Logic: Total Available = Raw + Refined
        total_ore = mining_res[0] + mining_res[1]
        total_log = wood_res[0] + wood_res[1]
        total_bone = fish_res[0] + fish_res[1]

        has_res = (
            total_ore >= costs["ore_qty"]
            and total_log >= costs["log_qty"]
            and total_bone >= costs["bone_qty"]
            and gold >= costs["gold"]
        )

        # 3. Store Snapshot for Confirm Logic
        self.costs = costs
        self.inventory_snapshot = {
            "ore": {
                "raw_col": raw_ore,
                "ref_col": refined_ore,
                "raw_amt": mining_res[0],
                "ref_amt": mining_res[1],
            },
            "log": {
                "raw_col": f"{raw_log}_logs",
                "ref_col": refined_log,
                "raw_amt": wood_res[0],
                "ref_amt": wood_res[1],
            },
            "bone": {
                "raw_col": f"{raw_bone}_bones",
                "ref_col": refined_bone,
                "raw_amt": fish_res[0],
                "ref_amt": fish_res[1],
            },
        }

        desc = (
            f"**Temper Cost:**\n"
            f"⛏️ {costs['ore_qty']} {costs['ore_type'].title()} (Have: {total_ore})\n"
            f"🪓 {costs['log_qty']} {costs['log_type'].title()} (Have: {total_log})\n"
            f"🎣 {costs['bone_qty']} {costs['bone_type'].title()} (Have: {total_bone})\n"
            f"💰 {costs['gold']:,} Gold"
        )

        if total_ore >= costs["ore_qty"] and mining_res[0] < costs["ore_qty"]:
            desc += "\n*Using Refined Ingots to substitute missing Ore.*"

        # New: Get Runes
        runes = await self.bot.database.users.get_currency(
            self.user_id, "potential_runes"
        )

        # Calculate Rates
        base_rate = 0.8
        max_tempers = 3
        if self.item.level > 40:
            max_tempers = 4
        if self.item.level > 80:
            max_tempers = 5
        current_step = max_tempers - self.item.temper_remaining

        current_pct = int((base_rate - (current_step * 0.05)) * 100)
        boosted_pct = min(100, current_pct + 10)

        desc += f"\n\n💎 **Runes Owned:** {runes}"

        # --- BUTTONS ---
        self.clear_items()

        # Standard Temper
        btn_std = Button(
            label=f"Temper ({current_pct}%)", style=ButtonStyle.success, row=0
        )
        btn_std.disabled = not has_res
        btn_std.callback = lambda i: self.confirm_temper(i, use_rune=False)
        self.add_item(btn_std)

        # Rune Temper (+10%)
        btn_rune = Button(
            label=f"Use Rune ({boosted_pct}%)",
            style=ButtonStyle.primary,
            emoji="💎",
            row=0,
        )
        btn_rune.disabled = not has_res or runes < 1
        btn_rune.callback = lambda i: self.confirm_temper(i, use_rune=True)
        self.add_item(btn_rune)

        self.add_back_button()

        embed = discord.Embed(
            title="Temper Armor",
            description=desc,
            color=discord.Color.blue() if has_res else discord.Color.red(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/tpEyVBm.png")

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_temper(self, interaction: Interaction, use_rune: bool):
        # Rune Check
        if use_rune:
            runes = await self.bot.database.users.get_currency(
                self.user_id, "potential_runes"
            )
            if runes < 1:
                return await interaction.response.send_message(
                    "No Runes left!", ephemeral=True
                )
            await self.bot.database.users.modify_currency(
                self.user_id, "potential_runes", -1
            )
            bonus = 10
        else:
            bonus = 0
        uid, gid = self.user_id, str(interaction.guild.id)

        # Helper for atomic deduction (Raw First, then Refined)
        async def deduct_smart(table, raw_col, ref_col, raw_held, cost):
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

        # Re-fetch live inventory counts so that any settlement collection that ran
        # between render and confirm doesn't cause raw columns to go negative.
        ore = self.inventory_snapshot["ore"]
        log = self.inventory_snapshot["log"]
        bone = self.inventory_snapshot["bone"]

        async with self.bot.database.connection.execute(
            f"SELECT {ore['raw_col']}, {ore['ref_col']} FROM mining WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cur:
            live_ore = await cur.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {log['raw_col']}, {log['ref_col']} FROM woodcutting WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cur:
            live_log = await cur.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {bone['raw_col']}, {bone['ref_col']} FROM fishing WHERE user_id=? AND server_id=?",
            (uid, gid),
        ) as cur:
            live_bone = await cur.fetchone() or (0, 0)

        # Execute Deductions
        await deduct_smart(
            "mining",
            ore["raw_col"],
            ore["ref_col"],
            live_ore[0],
            self.costs["ore_qty"],
        )
        await deduct_smart(
            "woodcutting",
            log["raw_col"],
            log["ref_col"],
            live_log[0],
            self.costs["log_qty"],
        )
        await deduct_smart(
            "fishing",
            bone["raw_col"],
            bone["ref_col"],
            live_bone[0],
            self.costs["bone_qty"],
        )

        await self.bot.database.users.modify_gold(uid, -self.costs["gold"])

        # ... (Roll logic and Result Embed identical to before) ...
        success, stat, amount = EquipmentMechanics.roll_temper_outcome(
            self.item, bonus_chance=bonus
        )

        res_embed = discord.Embed(title="Temper Result")
        res_embed.set_thumbnail(url="https://i.imgur.com/tpEyVBm.png")
        if success:
            self.item.temper_remaining -= 1
            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "armor",
                "temper_remaining",
                self.item.temper_remaining,
            )
            await self.bot.database.equipment.increase_stat(
                self.item.item_id, "armor", stat, amount
            )
            if stat == "pdr":
                self.item.pdr += amount
            elif stat == "fdr":
                self.item.fdr += amount

            res_embed.color = discord.Color.green()
            res_embed.description = (
                f"🛡️ **Success!**\nIncreased **{stat.upper()}** by **{amount}**."
            )
        else:
            res_embed.color = discord.Color.dark_grey()
            res_embed.description = (
                "🔨 **Failed.**\nThe metal cooled too quickly. Materials consumed."
            )

        await self.bot.database.connection.commit()

        # UI Refresh
        self.clear_items()
        if self.item.temper_remaining > 0:
            again_btn = Button(label="Temper Again", style=ButtonStyle.success)
            again_btn.callback = self.render
            self.add_item(again_btn)
        self.add_back_button()

        await interaction.response.edit_message(embed=res_embed, view=self)


class ImbueView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Armor, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        runes = await self.bot.database.users.get_currency(self.user_id, "imbue_runes")

        embed = discord.Embed(
            title="Imbue Armor",
            description=f"Cost: 1 Rune of Imbuing (Owned: {runes})\nSuccess Rate: **50%**\n\nGrants a powerful passive ability.",
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/tpEyVBm.png")
        self.clear_items()
        confirm_btn = Button(
            label="Imbue", style=ButtonStyle.primary, disabled=(runes == 0)
        )
        confirm_btn.callback = self.confirm
        self.add_item(confirm_btn)
        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def confirm(self, interaction: Interaction):
        await self.bot.database.users.modify_currency(self.user_id, "imbue_runes", -1)

        self.item.imbue_remaining = 0
        await self.bot.database.equipment.update_counter(
            self.item.item_id, "armor", "imbue_remaining", 0
        )

        embed = discord.Embed(title="Imbue Result")
        embed.set_thumbnail(url="https://i.imgur.com/tpEyVBm.png")
        if random.random() <= 0.5:
            new_p = random.choice(
                [
                    "Invulnerable",
                    "Mystical Might",
                    "Omnipotent",
                    "Treasure Hunter",
                    "Unlimited Wealth",
                    "Everlasting Blessing",
                ]
            )
            self.item.passive = new_p
            await self.bot.database.equipment.update_passive(
                self.item.item_id, "armor", new_p, "armor_passive"
            )
            embed.color = discord.Color.gold()
            embed.description = f"✨ Success! Imbued with **{new_p}**!"
        else:
            embed.color = discord.Color.dark_grey()
            embed.description = "The Rune shattered without effect."

        self.clear_items()
        self.add_back_button()
        await interaction.response.edit_message(embed=embed, view=self)


class VoidforgeView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self.candidates = []
        self.gold_cost = 0
        self.selected_target = None  # Store the item they selected for confirmation

    async def render(self, interaction: Interaction):
        self.selected_target = None  # Reset state

        # 1. Calculate Cost (5m if Pinnacle is empty, 10m if rolling for Utmost)
        self.gold_cost = 5_000_000 if self.item.p_passive == "none" else 10_000_000
        user_gold = await self.bot.database.users.get_gold(self.user_id)

        # 2. Fetch Candidates (Unequipped, Has active passive)
        raw_rows = await self.bot.database.equipment.fetch_void_forge_candidates(
            self.user_id
        )
        self.candidates = [
            create_weapon(r) for r in raw_rows if r[0] != self.item.item_id
        ]

        if not self.candidates:
            return await interaction.response.send_message(
                "No eligible sacrifice weapons found.\nRequires: Unequipped, Must have an active passive.",
                ephemeral=True,
            )

        if user_gold < self.gold_cost:
            return await interaction.response.send_message(
                f"Insufficient funds! You need **{self.gold_cost:,} gold** to initiate a Voidforge.",
                ephemeral=True,
            )

        # 3. Build Select Menu
        options = []
        for w in self.candidates[:25]:  # Discord Select limit
            lbl = f"Lv{w.level} {w.name} (+{w.refinement_lvl})"
            desc = f"Passive: {w.passive.title()}"
            options.append(
                SelectOption(label=lbl, description=desc, value=str(w.item_id))
            )

        select = Select(placeholder="Select Sacrifice Weapon...", options=options)
        select.callback = self.select_callback

        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()
        self.add_item(select)
        self.add_back_button()

        embed = discord.Embed(
            title="🌌 Voidforge",
            description=(
                f"Select a weapon to sacrifice.\n"
                f"**Cost:** 1 Void Key & {self.gold_cost:,} Gold\n\n"
                "**Effects:**\n"
                "25%: Add Passive as Pinnacle/Utmost\n"
                "25%: Overwrite Main Passive\n"
                "50%: Failure (Item Lost)"
            ),
            color=discord.Color.dark_purple(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/rZnRu0R.jpeg")

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def select_callback(self, interaction: Interaction):
        """Displays the confirmation prompt before executing."""
        target_id = int(interaction.data["values"][0])
        self.selected_target = next(
            (w for w in self.candidates if w.item_id == target_id), None
        )

        if not self.selected_target:
            return

        self.clear_items()

        confirm_btn = Button(
            label="CONFIRM SACRIFICE", style=ButtonStyle.danger, emoji="⚠️"
        )
        confirm_btn.callback = self.execute_voidforge
        self.add_item(confirm_btn)

        cancel_btn = Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self.cancel_confirmation
        self.add_item(cancel_btn)

        embed = discord.Embed(
            title="⚠️ Confirm Voidforge Sacrifice",
            description=(
                f"You are about to sacrifice:\n"
                f"🗡️ **{self.selected_target.name}** (Lv{self.selected_target.level})\n"
                f"✨ **Passive:** {self.selected_target.passive.title()}\n\n"
                f"**Cost:** 1 Void Key & {self.gold_cost:,} Gold\n\n"
                "**This item will be PERMANENTLY DESTROYED regardless of success or failure.**"
            ),
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/rZnRu0R.jpeg")

        await interaction.response.edit_message(embed=embed, view=self)

    async def cancel_confirmation(self, interaction: Interaction):
        """Returns to the selection menu without sacrificing."""
        await self.render(interaction)

    async def execute_voidforge(self, interaction: Interaction):
        """Handles the actual deduction and RNG roll."""
        target = self.selected_target
        if not target:
            return

        # Re-verify Gold just in case
        user_gold = await self.bot.database.users.get_gold(self.user_id)
        if user_gold < self.gold_cost:
            return await interaction.response.send_message(
                "You no longer have enough gold!", ephemeral=True
            )

        await interaction.response.defer()

        # Deduct Key & Gold
        await self.bot.database.users.modify_gold(self.user_id, -self.gold_cost)
        await self.bot.database.users.modify_currency(self.user_id, "void_keys", -1)

        # Destroy sacrifice weapon
        await self.bot.database.equipment.discard(target.item_id, "weapon")

        # Clean up Grandparent (Inventory List) View State
        inventory_view = self.parent_view.parent
        inventory_view.items = [
            i for i in inventory_view.items if i.item_id != target.item_id
        ]

        # Recalculate pagination
        inventory_view.total_pages = max(
            1,
            (len(inventory_view.items) + inventory_view.items_per_page - 1)
            // inventory_view.items_per_page,
        )
        if inventory_view.current_page >= inventory_view.total_pages:
            inventory_view.current_page = max(0, inventory_view.total_pages - 1)
        inventory_view.update_buttons()

        # Execute Roll Logic
        roll = random.random()
        res_txt = ""
        color = discord.Color.dark_grey()

        if roll < 0.25:
            # Add as secondary
            slot = (
                "pinnacle_passive"
                if self.item.p_passive == "none"
                else "utmost_passive"
            )
            await self.bot.database.equipment.update_passive(
                self.item.item_id, "weapon", target.passive, slot
            )

            if slot == "pinnacle_passive":
                self.item.p_passive = target.passive
            else:
                self.item.u_passive = target.passive

            res_txt = f"🌌 **Success!**\n{target.passive.title()} added as {slot.replace('_', ' ').title()}."
            color = discord.Color.purple()

        elif roll < 0.50:
            # Overwrite main
            await self.bot.database.equipment.update_passive(
                self.item.item_id, "weapon", target.passive
            )
            self.item.passive = target.passive
            res_txt = f"🔄 **Chaos!**\nMain passive overwritten with {target.passive.title()}."
            color = discord.Color.orange()
        else:
            res_txt = "❌ **Failure.**\nThe essence dissipated into the void."

        embed = discord.Embed(
            title="Voidforge Result", description=res_txt, color=color
        )
        embed.set_thumbnail(url="https://i.imgur.com/rZnRu0R.jpeg")

        # --- RESULT UI BUILD ---
        self.clear_items()
        self.add_back_button()

        await interaction.edit_original_response(embed=embed, view=self)


class ShatterView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        # Calculate Runes Back
        runes_back = max(0, int(self.item.refinement_lvl - 5 * 0.8))
        if self.item.attack > 0 and self.item.defence > 0 and self.item.rarity > 0:
            runes_back += 1

        self.runes_back = runes_back

        embed = discord.Embed(
            title="Shatter Weapon",
            description=f"Destroy **{self.item.name}**?\n\n**Returns:** {runes_back} Refinement Runes\n**Cost:** 1 Shatter Rune\n\n⚠️ **This cannot be undone.**",
            color=discord.Color.dark_red(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/KSTfiW3.png")
        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()

        confirm_btn = Button(label="CONFIRM SHATTER", style=ButtonStyle.danger)
        confirm_btn.callback = self.confirm
        self.add_item(confirm_btn)

        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def confirm(self, interaction: Interaction):
        # Execute
        await self.bot.database.equipment.discard(self.item.item_id, "weapon")
        await self.bot.database.users.modify_currency(
            self.user_id, "refinement_runes", self.runes_back
        )
        await self.bot.database.users.modify_currency(self.user_id, "shatter_runes", -1)

        # Update Parent List (since item is gone)
        self.parent_view.parent.items = [
            i for i in self.parent_view.parent.items if i.item_id != self.item.item_id
        ]
        self.parent_view.parent.update_buttons()  # Refresh page buttons

        embed = discord.Embed(title="Shattered", color=discord.Color.red())
        embed.description = (
            f"Item destroyed.\nYou gained **{self.runes_back}** Refinement Runes."
        )

        # --- RESULT UI BUILD ---
        self.clear_items()

        # Since item is gone, "Back" implies "Back to Inventory List"
        return_btn = Button(label="Return to Inventory", style=ButtonStyle.secondary)
        return_btn.callback = self.return_to_list
        self.add_item(return_btn)

        await interaction.response.edit_message(embed=embed, view=self)

    async def return_to_list(self, interaction: Interaction):
        # Go back to the Inventory List (grandparent view)
        embed = await self.parent_view.parent.get_current_embed(
            interaction.user.display_name
        )
        await interaction.response.edit_message(
            embed=embed, view=self.parent_view.parent
        )
        self.stop()


class InfernalEngramView(BaseUpgradeView):
    """Allows consuming an Infernal Engram to unlock or reroll an infernal weapon passive."""

    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        server_id = str(interaction.guild.id)

        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        self.engrams = uber_prog["infernal_engrams"]

        current_passive = getattr(self.item, "infernal_passive", "none")
        display_passive = (
            current_passive.replace("_", " ").title()
            if current_passive != "none"
            else "None"
        )

        desc = (
            f"**Current Infernal Passive:** {display_passive}\n"
            f"**Infernal Engrams Owned:** {self.engrams}\n"
            f"**Gold Cost:** 25,000,000\n\n"
            "Consuming an Engram will imbue your weapon with a powerful Infernal passive, or reroll your existing one."
        )

        self.embed = discord.Embed(
            title=f"🔥 Infernal Imbue: {self.item.name}",
            description=desc,
            color=discord.Color.dark_red(),
        )
        self.embed.set_thumbnail(url="https://i.imgur.com/x9suAGK.png")

        self.clear_items()
        btn_consume = Button(
            label="Consume Engram",
            style=ButtonStyle.danger,
            emoji="🔥",
            disabled=(self.engrams < 1),
        )
        btn_consume.callback = self.confirm_engram
        self.add_item(btn_consume)
        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirm_engram(self, interaction: Interaction):
        server_id = str(interaction.guild.id)
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        if uber_prog["infernal_engrams"] < 1:
            return await interaction.response.send_message(
                "You do not have any Infernal Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            return await interaction.response.send_message(
                "You need **25,000,000 gold** to use an Infernal Engram.", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_gold(self.user_id, -25_000_000)
        await self.bot.database.uber.increment_infernal_engrams(
            self.user_id, server_id, -1
        )

        current_p = getattr(self.item, "infernal_passive", "none")
        new_passive = EquipmentMechanics.roll_infernal_passive(current_p)

        await self.bot.database.equipment.update_passive(
            self.item.item_id, "weapon", new_passive, "infernal_passive"
        )
        self.item.infernal_passive = new_passive

        display_new = new_passive.replace("_", " ").title()
        res_embed = discord.Embed(
            title="🔥 Engram Ignited!",
            description=f"The Engram shatters in hellfire, branding your weapon.\n\n**New Passive:** {display_new}",
            color=discord.Color.red(),
        )
        res_embed.set_thumbnail(url="https://i.imgur.com/x9suAGK.png")

        self.clear_items()
        if uber_prog["infernal_engrams"] - 1 > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)


class BalancedEngramView(BaseUpgradeView):
    """Allows consuming a Gemini Engram to awaken or reroll a companion's balanced (secondary) passive."""

    def __init__(self, bot, user_id, companion, parent_view):
        super().__init__(bot, user_id, companion, parent_view)
        self.comp = companion

    async def render(self, interaction: Interaction):
        server_id = str(interaction.guild.id)

        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        self.engrams = uber_prog.get("gemini_engrams", 0)

        current_passive = self.comp.balanced_passive
        display_passive = (
            current_passive.replace("_", " ").title()
            if current_passive != "none"
            else "Not Awakened"
        )
        tier_display = (
            f"T{self.comp.balanced_passive_tier} "
            if self.comp.balanced_passive_tier > 0
            else ""
        )

        desc = (
            f"**Current Balanced Passive:** {tier_display}{display_passive}\n"
            f"**Gemini Engrams Owned:** {self.engrams}\n\n"
            f"Consuming an Engram awakens your companion's hidden potential, granting a secondary passive "
            f"at T{max(1, self.comp.passive_tier - 2)} (Primary Tier − 2, minimum T1).\n"
            f"Re-rolling always changes the secondary passive type."
        )

        self.embed = discord.Embed(
            title=f"♊ Balanced Awakening: {self.comp.name}",
            description=desc,
            color=discord.Color.blurple(),
        )
        self.embed.set_thumbnail(url=self.comp.image_url)

        self.clear_items()
        btn_consume = Button(
            label="Consume Engram",
            style=ButtonStyle.blurple,
            emoji="♊",
            disabled=(self.engrams < 1),
        )
        btn_consume.callback = self.confirm_engram
        self.add_item(btn_consume)
        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def go_back(self, interaction: Interaction):
        """Returns to the companion detail view."""
        embed = self.parent_view.get_embed()
        self.parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
        self.stop()

    async def confirm_engram(self, interaction: Interaction):
        server_id = str(interaction.guild.id)
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        if uber_prog.get("gemini_engrams", 0) < 1:
            return await interaction.response.send_message(
                "You do not have any Gemini Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            return await interaction.response.send_message(
                "You need **25,000,000 gold** to use a Balanced Engram.", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_gold(self.user_id, -25_000_000)
        await self.bot.database.uber.increment_gemini_engrams(
            self.user_id, server_id, -1
        )

        new_type, new_tier = CompanionMechanics.roll_balanced_passive(
            self.comp.passive_type, self.comp.passive_tier
        )

        await self.bot.database.companions.update_balanced_passive(
            self.comp.id, new_type, new_tier
        )
        self.comp.balanced_passive = new_type
        self.comp.balanced_passive_tier = new_tier

        display_new = new_type.replace("_", " ").title()
        res_embed = discord.Embed(
            title="♊ Balanced Awakening!",
            description=(
                f"The twins' constellation realigns, awakening a new potential.\n\n"
                f"**New Balanced Passive:** T{new_tier} {display_new}"
            ),
            color=discord.Color.blurple(),
        )
        res_embed.set_thumbnail(url=self.comp.image_url)

        self.clear_items()
        remaining = uber_prog.get("gemini_engrams", 0) - 1
        if remaining > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)


class VoidEngramView(BaseUpgradeView):
    """Allows consuming a Void Engram to unlock or reroll a void accessory passive."""

    def __init__(self, bot, user_id, item: Accessory, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        server_id = str(interaction.guild.id)

        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        self.engrams = uber_prog["void_engrams"]

        current_passive = getattr(self.item, "void_passive", "none")
        display_passive = (
            current_passive.replace("_", " ").title()
            if current_passive != "none"
            else "None"
        )

        desc = (
            f"**Current Void Passive:** {display_passive}\n"
            f"**Void Engrams Owned:** {self.engrams}\n"
            f"**Gold Cost:** 25,000,000\n\n"
            "Consuming an Engram will corrupt your accessory with a Void passive, or reroll your existing one."
        )

        self.embed = discord.Embed(
            title=f"⬛ Void Corruption: {self.item.name}",
            description=desc,
            color=discord.Color.dark_theme(),
        )

        self.clear_items()
        btn_consume = Button(
            label="Consume Engram",
            style=ButtonStyle.secondary,
            emoji="⬛",
            disabled=(self.engrams < 1),
        )
        btn_consume.callback = self.confirm_engram
        self.add_item(btn_consume)
        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirm_engram(self, interaction: Interaction):
        server_id = str(interaction.guild.id)
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        if uber_prog["void_engrams"] < 1:
            return await interaction.response.send_message(
                "You do not have any Void Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            return await interaction.response.send_message(
                "You need **25,000,000 gold** to use a Void Engram.", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_gold(self.user_id, -25_000_000)
        await self.bot.database.uber.increment_void_engrams(self.user_id, server_id, -1)

        current_p = getattr(self.item, "void_passive", "none")
        new_passive = EquipmentMechanics.roll_void_passive(current_p)

        await self.bot.database.equipment.update_passive(
            self.item.item_id, "accessory", new_passive, "void_passive"
        )
        self.item.void_passive = new_passive

        display_new = new_passive.replace("_", " ").title()
        res_embed = discord.Embed(
            title="⬛ Engram Absorbed!",
            description=f"The Engram dissolves into the void, reshaping your accessory.\n\n**New Passive:** {display_new}",
            color=discord.Color.dark_theme(),
        )

        self.clear_items()
        if uber_prog["void_engrams"] - 1 > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)


class EngramView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Armor, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        server_id = str(interaction.guild.id)

        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        self.engrams = uber_prog["celestial_engrams"]

        current_passive = getattr(self.item, "celestial_passive", "none")
        display_passive = current_passive.replace("_", " ").title()

        desc = (
            f"**Current Celestial Passive:** {display_passive}\n"
            f"**Celestial Engrams Owned:** {self.engrams}\n"
            f"**Gold Cost:** 25,000,000\n\n"
            "Consuming an Engram will imbue your armor with a powerful Celestial passive, or reroll your existing one."
        )

        self.embed = discord.Embed(
            title=f"🌌 Imbue {self.item.name}",
            description=desc,
            color=discord.Color.purple(),
        )
        self.embed.set_thumbnail(url="https://i.imgur.com/LjE5VZF.png")

        self.clear_items()
        btn_consume = Button(
            label="Consume Engram",
            style=ButtonStyle.danger,
            emoji="🌌",
            disabled=(self.engrams < 1),
        )
        btn_consume.callback = self.confirm_engram
        self.add_item(btn_consume)
        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirm_engram(self, interaction: Interaction):
        server_id = str(interaction.guild.id)
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        if uber_prog["celestial_engrams"] < 1:
            return await interaction.response.send_message(
                "You do not have any Celestial Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            return await interaction.response.send_message(
                "You need **25,000,000 gold** to use a Celestial Engram.", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_gold(self.user_id, -25_000_000)
        await self.bot.database.uber.increment_engrams(self.user_id, server_id, -1)

        current_p = getattr(self.item, "celestial_passive", "none")
        new_passive = EquipmentMechanics.roll_celestial_passive(current_p)

        await self.bot.database.equipment.update_passive(
            self.item.item_id, "armor", new_passive, "celestial_armor_passive"
        )
        self.item.celestial_passive = new_passive

        display_new = new_passive.replace("_", " ").title()
        res_embed = discord.Embed(
            title="🌌 Engram Resonated!", color=discord.Color.gold()
        )
        res_embed.description = f"The Engram shatters, weaving divine energy into your armor.\n\n**New Passive:** {display_new}"
        res_embed.set_thumbnail(url="https://i.imgur.com/LjE5VZF.png")

        self.clear_items()
        if uber_prog["celestial_engrams"] - 1 > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)
