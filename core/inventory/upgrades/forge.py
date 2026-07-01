import copy

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.combat.calc.calcs import fmt_weapon_passive
from core.character.passive_formatters import get_weapon_passive_description
from core.images import HARLAN_AUTHOR, UPGRADE_FORGE
from core.inventory.upgrades.base import BaseUpgradeView
from core.npc_voices import get_quip
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Weapon


class ForgeView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self._processing = False

    async def render(self, interaction: Interaction):
        self._render_gen += 1
        _my_gen = self._render_gen
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
            description=get_quip("forge"),
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

        await self._send_render(interaction, self.embed, render_gen=_my_gen)

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

            passive_desc = get_weapon_passive_description(new_passive)
            result_embed.description = (
                f"🔥 **Success!**\nNew Passive: **{fmt_weapon_passive(new_passive)}**"
                + (f"\n*{passive_desc}*" if passive_desc else "")
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
        """Simulate Forgemaxx and show a resource-cost confirmation before executing.

        Simulates worst-case (every attempt succeeds) so forge_tier escalates at the
        maximum possible rate. Each step checks the correct material tier for that
        forge_tier level. This gives an accurate upper-bound on resource consumption
        and correctly catches cases where the player lacks higher-tier materials.
        """
        await interaction.response.defer()

        uid, gid = self.user_id, str(interaction.guild.id)

        if not EquipmentMechanics.calculate_forge_cost(self.item):
            await interaction.followup.send("No forges remaining!", ephemeral=True)
            return

        # Material column maps for each resource type
        _ORE_REFINED = {
            "iron_ore": ("mining", "iron_bar"),
            "coal_ore": ("mining", "steel_bar"),
            "gold_ore": ("mining", "gold_bar"),
            "platinum_ore": ("mining", "platinum_bar"),
            "idea_ore": ("mining", "idea_bar"),
        }
        _LOG_BASES = ["oak", "willow", "mahogany", "magic", "idea"]
        _BONE_BASES = ["desiccated", "regular", "sturdy", "reinforced", "titanium"]
        _MAT_LABEL = {
            "iron_ore": "⛏️ Iron Ore",
            "coal_ore": "⛏️ Coal",
            "gold_ore": "⛏️ Gold Ore",
            "platinum_ore": "⛏️ Platinum Ore",
            "idea_ore": "⛏️ Idea Ore",
            "oak_logs": "🪓 Oak Logs",
            "willow_logs": "🪓 Willow Logs",
            "mahogany_logs": "🪓 Mahogany Logs",
            "magic_logs": "🪓 Magic Logs",
            "idea_logs": "🪓 Idea Logs",
            "desiccated_bones": "🎣 Desiccated Bones",
            "regular_bones": "🎣 Regular Bones",
            "sturdy_bones": "🎣 Sturdy Bones",
            "reinforced_bones": "🎣 Reinforced Bones",
            "titanium_bones": "🎣 Titanium Bones",
        }

        # Fetch every possible material tier up front
        sim_mats: dict[str, int] = {}
        for ore_col, (table, ref_col) in _ORE_REFINED.items():
            raw = await self.bot.database.skills.get_single_resource(uid, gid, table, ore_col)
            ref = await self.bot.database.skills.get_single_resource(uid, gid, table, ref_col)
            sim_mats[ore_col] = raw + ref
        for base in _LOG_BASES:
            raw = await self.bot.database.skills.get_single_resource(uid, gid, "woodcutting", f"{base}_logs")
            ref = await self.bot.database.skills.get_single_resource(uid, gid, "woodcutting", f"{base}_plank")
            sim_mats[f"{base}_logs"] = raw + ref
        for base in _BONE_BASES:
            raw = await self.bot.database.skills.get_single_resource(uid, gid, "fishing", f"{base}_bones")
            ref = await self.bot.database.skills.get_single_resource(uid, gid, "fishing", f"{base}_essence")
            sim_mats[f"{base}_bones"] = raw + ref

        sim_gold = await self.bot.database.users.get_gold(uid)
        sim_item = copy.copy(self.item)

        forges_possible = 0
        cost_totals: dict[str, int] = {}
        total_gold = 0
        stop_reason = "All forge slots exhausted."

        while sim_item.forges_remaining > 0:
            c = EquipmentMechanics.calculate_forge_cost(sim_item)
            if not c:
                break

            ore_col = c["ore_type"]
            log_col = f"{c['log_type']}_logs"
            bone_col = f"{c['bone_type']}_bones"

            if sim_mats.get(ore_col, 0) < c["ore_qty"]:
                stop_reason = f"Ran out of {c['ore_type'].removesuffix('_ore').title()}."
                break
            if sim_mats.get(log_col, 0) < c["log_qty"]:
                stop_reason = f"Ran out of {c['log_type'].title()} Logs."
                break
            if sim_mats.get(bone_col, 0) < c["bone_qty"]:
                stop_reason = f"Ran out of {c['bone_type'].title()} Bones."
                break
            if sim_gold < c["gold"]:
                stop_reason = "Ran out of Gold."
                break

            sim_mats[ore_col] -= c["ore_qty"]
            sim_mats[log_col] -= c["log_qty"]
            sim_mats[bone_col] -= c["bone_qty"]
            sim_gold -= c["gold"]
            cost_totals[ore_col] = cost_totals.get(ore_col, 0) + c["ore_qty"]
            cost_totals[log_col] = cost_totals.get(log_col, 0) + c["log_qty"]
            cost_totals[bone_col] = cost_totals.get(bone_col, 0) + c["bone_qty"]
            total_gold += c["gold"]

            # Worst-case: treat every attempt as a success so forge_tier escalates
            sim_item.forge_tier += 1
            sim_item.forges_remaining -= 1
            forges_possible += 1

        if forges_possible == 0:
            await interaction.followup.send(
                f"No forges possible: {stop_reason}", ephemeral=True
            )
            return

        self._forgemaxx_planned = forges_possible

        mat_lines = "\n".join(
            f"{_MAT_LABEL.get(col, col)}: {qty:,}"
            for col, qty in cost_totals.items()
            if qty > 0
        )

        embed = discord.Embed(title="⚠️ Confirmation", color=discord.Color.orange())
        embed.set_author(name="Master Smith Harlan", icon_url=HARLAN_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_FORGE)
        embed.description = (
            f"This will attempt **{forges_possible}** forge(s).\n\n"
            f"**Estimated Resources Consumed:**\n"
            f"{mat_lines}\n"
            f"💰 Gold: {total_gold:,}\n\n"
            f"*Estimate assumes all forges succeed — actual cost is lower if any fail.*\n"
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
        """Loop-forge up to the planned count confirmed in the preview."""
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        uid, gid = self.user_id, str(interaction.guild.id)
        planned = getattr(self, "_forgemaxx_planned", self.item.forges_remaining)
        forges_done = 0
        successes = 0
        final_passive = self.item.passive
        attempt_log: list[str] = []

        while self.item.forges_remaining > 0 and forges_done < planned:
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
                attempt_log.append(
                    f"**#{forges_done}** ✅ → {fmt_weapon_passive(new_passive)}"
                )
                await self.bot.database.equipment.update_passive(
                    self.item.item_id, "weapon", new_passive
                )
                await self.bot.database.equipment.update_counter(
                    self.item.item_id,
                    "weapon",
                    "forge_tier",
                    self.item.forge_tier,
                )
            else:
                attempt_log.append(f"**#{forges_done}** ❌ Failed")

            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "weapon",
                "forges_remaining",
                self.item.forges_remaining,
            )

        final_passive_desc = (
            get_weapon_passive_description(final_passive)
            if final_passive != "none"
            else ""
        )
        result_embed = discord.Embed(
            title="⚒️ Forgemaxx Complete",
            color=discord.Color.gold() if successes > 0 else discord.Color.dark_grey(),
        )
        result_embed.set_author(name="Master Smith Harlan", icon_url=HARLAN_AUTHOR)
        result_embed.set_thumbnail(url=UPGRADE_FORGE)
        result_embed.description = (
            f"**Attempts:** {forges_done}  |  **Successes:** {successes}\n"
            f"**Final Passive:** {fmt_weapon_passive(final_passive) if final_passive != 'none' else 'None'}"
            + (f"\n*{final_passive_desc}*" if final_passive_desc else "")
            + f"\n**Forges Remaining:** {self.item.forges_remaining}"
        )
        if attempt_log:
            result_embed.add_field(
                name="Attempt Log",
                value="\n".join(attempt_log),
                inline=False,
            )

        self.clear_items()
        self.add_back_button()
        await interaction.edit_original_response(embed=result_embed, view=self)
        self.message = await interaction.original_response()
