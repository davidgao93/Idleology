import random

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import Button, Select

from core.combat.calc.calcs import fmt_weapon_passive
from core.images import (
    UPGRADE_FORGE,
    UPGRADE_INFERNAL_ENGRAM,
    UPGRADE_REFINE,
    UPGRADE_VOIDFORGE,
)
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.equipment_mechanics import EquipmentMechanics
from core.items.factory import create_weapon
from core.models import Weapon


class ForgeView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        costs = EquipmentMechanics.calculate_forge_cost(self.item)
        if not costs:
            return await interaction.response.send_message(
                "No forges remaining!", ephemeral=True
            )

        uid, gid = self.user_id, str(interaction.guild.id)
        cols = self._resolve_material_columns(costs)
        mining_res, wood_res, fish_res = await self._fetch_material_amounts(cols, uid, gid)
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

        self.costs = costs
        self.inventory_snapshot = {
            "ore": {**cols["ore"], "raw_amt": mining_res[0], "ref_amt": mining_res[1]},
            "log": {**cols["log"], "raw_amt": wood_res[0], "ref_amt": wood_res[1]},
            "bone": {**cols["bone"], "raw_amt": fish_res[0], "ref_amt": fish_res[1]},
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
        self.embed.set_thumbnail(url=UPGRADE_FORGE)

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
        self.message = await interaction.original_response()

    async def confirm_forge(self, interaction: Interaction):
        uid, gid = self.user_id, str(interaction.guild.id)

        ore = self.inventory_snapshot["ore"]
        log = self.inventory_snapshot["log"]
        bone = self.inventory_snapshot["bone"]

        # Re-fetch live counts to avoid negatives from concurrent settlement updates
        live_ore, live_log, live_bone = await self._fetch_material_amounts(
            self.inventory_snapshot, uid, gid
        )

        await self._deduct_smart("mining", ore["raw_col"], ore["ref_col"], live_ore[0], self.costs["ore_qty"], uid, gid)
        await self._deduct_smart("woodcutting", log["raw_col"], log["ref_col"], live_log[0], self.costs["log_qty"], uid, gid)
        await self._deduct_smart("fishing", bone["raw_col"], bone["ref_col"], live_bone[0], self.costs["bone_qty"], uid, gid)

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
                self.item.item_id,
                "weapon",
                "forges_remaining",
                self.item.forges_remaining,
            )
            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "weapon",
                "forge_tier",
                self.item.forge_tier,
            )

            result_embed.description = (
                f"🔥 **Success!**\nNew Passive: **{fmt_weapon_passive(new_passive)}**"
            )
            result_embed.color = discord.Color.gold()
        else:
            self.item.forges_remaining -= 1
            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "weapon",
                "forges_remaining",
                self.item.forges_remaining,
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
            cols = self._resolve_material_columns(costs)
            mining_res, wood_res, fish_res = await self._fetch_material_amounts(cols, uid, gid)

            gold = await self.bot.database.users.get_gold(uid)
            total_ore = mining_res[0] + mining_res[1]
            total_log = wood_res[0] + wood_res[1]
            total_bone = fish_res[0] + fish_res[1]

            if (
                total_ore < costs["ore_qty"]
                or total_log < costs["log_qty"]
                or total_bone < costs["bone_qty"]
                or gold < costs["gold"]
            ):
                break

            await self._deduct_smart("mining", cols["ore"]["raw_col"], cols["ore"]["ref_col"], mining_res[0], costs["ore_qty"], uid, gid)
            await self._deduct_smart("woodcutting", cols["log"]["raw_col"], cols["log"]["ref_col"], wood_res[0], costs["log_qty"], uid, gid)
            await self._deduct_smart("fishing", cols["bone"]["raw_col"], cols["bone"]["ref_col"], fish_res[0], costs["bone_qty"], uid, gid)
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
                    self.item.item_id,
                    "weapon",
                    "forge_tier",
                    self.item.forge_tier,
                )

            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "weapon",
                "forges_remaining",
                self.item.forges_remaining,
            )

        result_embed = discord.Embed(
            title="⚒️ Forgemaxx Complete",
            description=(
                f"**Attempts:** {forges_done}  |  **Successes:** {successes}\n"
                f"**Final Passive:** {fmt_weapon_passive(final_passive) if final_passive != 'none' else 'None'}\n"
                f"**Forges Remaining:** {self.item.forges_remaining}"
            ),
            color=discord.Color.gold() if successes > 0 else discord.Color.dark_grey(),
        )
        result_embed.set_thumbnail(url=UPGRADE_FORGE)

        self.clear_items()
        self.add_back_button()
        await interaction.edit_original_response(embed=result_embed, view=self)
        self.message = await interaction.original_response()


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

                owned = await self.bot.database.skills.get_single_resource(uid, sid, table, col)

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
        self.embed.set_thumbnail(url=UPGRADE_REFINE)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)
        self.message = await interaction.original_response()

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

                success = await self.bot.database.skills.deduct_resource_atomic(uid, sid, table, col, qty)
                if not success:
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
            embed.set_thumbnail(url=UPGRADE_REFINE)
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
            self.message = await interaction.original_response()

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
                owned = await self.bot.database.skills.get_single_resource(uid, sid, mat["table"], mat["column"])
                if owned < mat["qty"]:
                    insufficient = mat["name"]
                    break

            if insufficient:
                stop_reason = f"Ran out of {insufficient}."
                break

            # Deduct materials
            failed = False
            for mat in materials:
                success = await self.bot.database.skills.deduct_resource_atomic(uid, sid, mat["table"], mat["column"], mat["qty"])
                if not success:
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
        embed.set_thumbnail(url=UPGRADE_REFINE)
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
        self.message = await interaction.original_response()

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
            for col in cols:
                sim_mats[col] = await self.bot.database.skills.get_single_resource(uid, sid, table, col)

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
        embed.set_thumbnail(url=UPGRADE_REFINE)
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
        self.message = await interaction.original_response()

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
                success = await self.bot.database.skills.deduct_resource_atomic(uid, sid, mat["table"], mat["column"], mat["qty"])
                if not success:
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
        embed.set_thumbnail(url=UPGRADE_REFINE)
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
        self.message = await interaction.original_response()


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
            desc = f"Passive: {fmt_weapon_passive(w.passive)}"
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
        embed.set_thumbnail(url=UPGRADE_VOIDFORGE)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
        self.message = await interaction.original_response()

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
                f"✨ **Passive:** {fmt_weapon_passive(self.selected_target.passive)}\n\n"
                f"**Cost:** 1 Void Key & {self.gold_cost:,} Gold\n\n"
                "**This item will be PERMANENTLY DESTROYED regardless of success or failure.**"
            ),
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=UPGRADE_VOIDFORGE)

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

            res_txt = f"🌌 **Success!**\n{fmt_weapon_passive(target.passive)} added as {slot.replace('_', ' ').title()}."
            color = discord.Color.purple()

        elif roll < 0.50:
            # Overwrite main
            await self.bot.database.equipment.update_passive(
                self.item.item_id, "weapon", target.passive
            )
            self.item.passive = target.passive
            res_txt = f"🔄 **Chaos!**\nMain passive overwritten with {fmt_weapon_passive(target.passive)}."
            color = discord.Color.orange()
        else:
            res_txt = "❌ **Failure.**\nThe essence dissipated into the void."

        embed = discord.Embed(
            title="Voidforge Result", description=res_txt, color=color
        )
        embed.set_thumbnail(url=UPGRADE_VOIDFORGE)

        # --- RESULT UI BUILD ---
        self.clear_items()
        self.add_back_button()

        await interaction.edit_original_response(embed=embed, view=self)
        self.message = await interaction.original_response()


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
        self.embed.set_thumbnail(url=UPGRADE_INFERNAL_ENGRAM)

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
        self.message = await interaction.original_response()

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
                "You need **25,000,000 gold** to use an Infernal Engram.",
                ephemeral=True,
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
        res_embed.set_thumbnail(url=UPGRADE_INFERNAL_ENGRAM)

        self.clear_items()
        if uber_prog["infernal_engrams"] - 1 > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)
        self.message = await interaction.original_response()
