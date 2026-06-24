import copy

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.combat.calc.calcs import fmt_weapon_passive
from core.images import HARLAN_AUTHOR, UPGRADE_FORGE
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Weapon


class ForgeView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self._processing = False

    async def render(self, interaction: Interaction):
        self._processing = False
        costs = EquipmentMechanics.calculate_forge_cost(self.item)
        if not costs:
            return await interaction.response.send_message(
                "No forges remaining!", ephemeral=True
            )

        uid, gid = self.user_id, str(interaction.guild.id)
        has_res, cost_lines, self.inventory_snapshot = await self._check_triad_costs(
            costs, uid, gid
        )
        self.costs = costs

        current_passive = fmt_weapon_passive(self.item.passive) if self.item.passive and self.item.passive != "none" else "None"

        self.embed = discord.Embed(
            title=f"Forge {self.item.name}",
            description=(
                "Another blade that needs real work. Hand it over — I'll make it sing. "
                "Costs are fair, results are better than fair."
            ),
            color=discord.Color.green() if has_res else discord.Color.red(),
        )
        self.embed.set_author(name="Master Smith Harlan", icon_url=HARLAN_AUTHOR)
        self.embed.set_thumbnail(url=UPGRADE_FORGE)
        self.embed.add_field(name="Current Passive", value=current_passive, inline=False)
        self.embed.add_field(
            name=f"Cost (Forges Remaining: {self.item.forges_remaining})",
            value=cost_lines,
            inline=False,
        )

        self.clear_items()

        forge_btn = Button(
            label="Forge!", style=ButtonStyle.success, disabled=not has_res
        )
        forge_btn.callback = self.confirm_forge
        self.add_item(forge_btn)

        forgemaxx_btn = Button(
            label="Forgemaxx", style=ButtonStyle.danger, disabled=not has_res
        )
        forgemaxx_btn.callback = self.forgemaxx_preview
        self.add_item(forgemaxx_btn)

        self.add_back_button()

        await self._send_render(interaction, self.embed)

    async def confirm_forge(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        uid, gid = self.user_id, str(interaction.guild.id)

        ore = self.inventory_snapshot["ore"]
        log = self.inventory_snapshot["log"]
        bone = self.inventory_snapshot["bone"]

        live_ore, live_log, live_bone = await self._fetch_material_amounts(
            self.inventory_snapshot, uid, gid
        )

        mats_ok = (
            await self._deduct_smart(
                "mining",
                ore["raw_col"],
                ore["ref_col"],
                live_ore[0],
                self.costs["ore_qty"],
                uid,
                gid,
            )
            and await self._deduct_smart(
                "woodcutting",
                log["raw_col"],
                log["ref_col"],
                live_log[0],
                self.costs["log_qty"],
                uid,
                gid,
            )
            and await self._deduct_smart(
                "fishing",
                bone["raw_col"],
                bone["ref_col"],
                live_bone[0],
                self.costs["bone_qty"],
                uid,
                gid,
            )
        )
        if not mats_ok:
            return await interaction.followup.send(
                "Insufficient materials!", ephemeral=True
            )

        gold_ok = await self.bot.database.users.deduct_gold_atomic(
            uid, self.costs["gold"]
        )
        if not gold_ok:
            return await interaction.followup.send("Insufficient gold!", ephemeral=True)

        success, new_passive = EquipmentMechanics.roll_forge_outcome(self.item)

        result_embed = discord.Embed(title="Forge Result")
        if success:
            self.item.forges_remaining -= 1
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

        self.clear_items()

        if self.item.forges_remaining > 0:
            again_btn = Button(label="Forge Again", style=ButtonStyle.success)
            again_btn.callback = self.render
            self.add_item(again_btn)

            forgemaxx_btn = Button(label="Forgemaxx", style=ButtonStyle.danger)
            forgemaxx_btn.callback = self.forgemaxx_preview
            self.add_item(forgemaxx_btn)

        self.add_back_button()

        await interaction.edit_original_response(embed=result_embed, view=self)

    async def forgemaxx_preview(self, interaction: Interaction):
        """Simulate Forgemaxx and show a resource-cost confirmation before executing."""
        await interaction.response.defer()

        uid, gid = self.user_id, str(interaction.guild.id)

        initial_costs = EquipmentMechanics.calculate_forge_cost(self.item)
        if not initial_costs:
            await interaction.followup.send("No forges remaining!", ephemeral=True)
            return

        has_res, _, snap = await self._check_triad_costs(initial_costs, uid, gid)
        if not has_res:
            await interaction.followup.send(
                "Insufficient resources for even one forge.", ephemeral=True
            )
            return

        sim_item = copy.copy(self.item)
        sim_gold = await self.bot.database.users.get_gold(uid)
        sim_ore = snap["ore"]["raw_amt"] + snap["ore"]["ref_amt"]
        sim_log = snap["log"]["raw_amt"] + snap["log"]["ref_amt"]
        sim_bone = snap["bone"]["raw_amt"] + snap["bone"]["ref_amt"]

        forges_possible = 0
        total_ore = total_log = total_bone = total_gold = 0
        stop_reason = "All forge slots exhausted."

        while sim_item.forges_remaining > 0:
            c = EquipmentMechanics.calculate_forge_cost(sim_item)
            if not c:
                break
            if sim_ore < c["ore_qty"]:
                stop_reason = f"Ran out of {c['ore_type'].removesuffix('_ore').title()}."
                break
            if sim_log < c["log_qty"]:
                stop_reason = f"Ran out of {c['log_type'].title()}."
                break
            if sim_bone < c["bone_qty"]:
                stop_reason = f"Ran out of {c['bone_type'].title()}."
                break
            if sim_gold < c["gold"]:
                stop_reason = "Ran out of Gold."
                break

            sim_ore -= c["ore_qty"]
            sim_log -= c["log_qty"]
            sim_bone -= c["bone_qty"]
            sim_gold -= c["gold"]
            total_ore += c["ore_qty"]
            total_log += c["log_qty"]
            total_bone += c["bone_qty"]
            total_gold += c["gold"]
            sim_item.forges_remaining -= 1
            forges_possible += 1

        if forges_possible == 0:
            await interaction.followup.send(
                f"No forges possible: {stop_reason}", ephemeral=True
            )
            return

        ore_name = initial_costs["ore_type"].removesuffix("_ore").title()
        log_name = initial_costs["log_type"].title()
        bone_name = initial_costs["bone_type"].title()

        embed = discord.Embed(title="⚠️ Confirmation", color=discord.Color.orange())
        embed.set_author(name="Master Smith Harlan", icon_url=HARLAN_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_FORGE)
        embed.description = (
            f"This will attempt **{forges_possible}** forge(s).\n\n"
            f"**Estimated Resources Consumed:**\n"
            f"⛏️ {ore_name}: {total_ore:,}\n"
            f"🪓 {log_name}: {total_log:,}\n"
            f"🎣 {bone_name}: {total_bone:,}\n"
            f"💰 Gold: {total_gold:,}\n\n"
            f"*Cost is estimated at current forge tier — successes may increase costs slightly.*\n"
            f"*Stops when: {stop_reason}*\n\n"
            f"Proceed?"
        )

        self.clear_items()
        confirm_btn = Button(label="Confirm", style=ButtonStyle.danger)
        confirm_btn.callback = self.forgemaxx_execute
        self.add_item(confirm_btn)

        cancel_btn = Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self.render
        self.add_item(cancel_btn)

        await interaction.edit_original_response(embed=embed, view=self)
        self.message = await interaction.original_response()

    async def forgemaxx_execute(self, interaction: Interaction):
        """Loop-forge until the player runs out of resources or forge slots."""
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        uid, gid = self.user_id, str(interaction.guild.id)
        forges_done = 0
        successes = 0
        final_passive = self.item.passive

        while self.item.forges_remaining > 0:
            costs = EquipmentMechanics.calculate_forge_cost(self.item)
            if not costs:
                break

            has_res, _, snap = await self._check_triad_costs(costs, uid, gid)
            if not has_res:
                break

            await self._deduct_smart(
                "mining",
                snap["ore"]["raw_col"],
                snap["ore"]["ref_col"],
                snap["ore"]["raw_amt"],
                costs["ore_qty"],
                uid,
                gid,
            )
            await self._deduct_smart(
                "woodcutting",
                snap["log"]["raw_col"],
                snap["log"]["ref_col"],
                snap["log"]["raw_amt"],
                costs["log_qty"],
                uid,
                gid,
            )
            await self._deduct_smart(
                "fishing",
                snap["bone"]["raw_col"],
                snap["bone"]["ref_col"],
                snap["bone"]["raw_amt"],
                costs["bone_qty"],
                uid,
                gid,
            )
            gold_ok = await self.bot.database.users.deduct_gold_atomic(
                uid, costs["gold"]
            )
            if not gold_ok:
                break

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
        result_embed.set_author(name="Master Smith Harlan", icon_url=HARLAN_AUTHOR)
        result_embed.set_thumbnail(url=UPGRADE_FORGE)

        self.clear_items()
        self.add_back_button()
        await interaction.edit_original_response(embed=result_embed, view=self)
        self.message = await interaction.original_response()
