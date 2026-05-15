import copy

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.images import UPGRADE_REFINE
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Weapon


class RefineView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self.cost_data = {}

    async def render(self, interaction: Interaction):
        self.cost_data = EquipmentMechanics.calculate_refine_cost(self.item)
        cost_gold = self.cost_data["gold"]
        materials = self.cost_data.get("materials", [])

        uid, sid = self.user_id, str(interaction.guild.id)
        user_gold = await self.bot.database.users.get_gold(uid)

        has_funds = user_gold >= cost_gold
        has_mats, mat_status = await self._check_listed_materials(materials, uid, sid)

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

        await self._send_render(interaction, self.embed)

    async def confirm_refine(self, interaction: Interaction):
        if self.item.refines_remaining <= 0:
            await self.bot.database.users.modify_currency(
                self.user_id, "refinement_runes", -1
            )
            await self.bot.database.equipment.update_counter(
                self.item.item_id, "weapon", "refines_remaining", 1
            )
            self.item.refines_remaining += 1
            await self.render(interaction)
            return

        cost_gold = self.cost_data["gold"]
        materials = self.cost_data.get("materials", [])
        uid, sid = self.user_id, str(interaction.guild.id)

        await interaction.response.defer()

        try:
            for mat in materials:
                table = mat["table"]
                col = mat["column"]
                qty = mat["qty"]

                success = await self.bot.database.skills.deduct_resource_atomic(
                    uid, sid, table, col, qty
                )
                if not success:
                    return await interaction.followup.send(
                        f"Insufficient {mat['name']}!", ephemeral=True
                    )

            await self.bot.database.users.modify_gold(self.user_id, -cost_gold)

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

            self.clear_items()

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

            user_gold = await self.bot.database.users.get_gold(uid)
            if user_gold < cost_gold:
                stop_reason = "Ran out of Gold."
                break

            insufficient = None
            for mat in materials:
                owned = await self.bot.database.skills.get_single_resource(
                    uid, sid, mat["table"], mat["column"]
                )
                if owned < mat["qty"]:
                    insufficient = mat["name"]
                    break

            if insufficient:
                stop_reason = f"Ran out of {insufficient}."
                break

            failed = False
            for mat in materials:
                success = await self.bot.database.skills.deduct_resource_atomic(
                    uid, sid, mat["table"], mat["column"], mat["qty"]
                )
                if not success:
                    failed = True
                    stop_reason = f"Ran out of {mat['name']}."
                    break
            if failed:
                break

            await self.bot.database.users.modify_gold(uid, -cost_gold)

            stats = EquipmentMechanics.roll_refine_outcome(self.item)
            for key in ("attack", "defence", "rarity"):
                if stats[key]:
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
                sim_mats[col] = await self.bot.database.skills.get_single_resource(
                    uid, sid, table, col
                )

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
                success = await self.bot.database.skills.deduct_resource_atomic(
                    uid, sid, mat["table"], mat["column"], mat["qty"]
                )
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
