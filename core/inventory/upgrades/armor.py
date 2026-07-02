import random

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.character.passive_formatters import get_armor_passive_description
from core.images import (
    SYLAS_AUTHOR,
    UPGRADE_CELESTIAL_ENGRAM,
    UPGRADE_REINFORCE,
    UPGRADE_TEMPER,
    VEYRA_AUTHOR,
)
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Armor, Boot, Glove
from core.npc_voices import get_quip


class TemperView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Armor, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self._processing = False

    async def render(self, interaction: Interaction):
        self._render_gen += 1
        _my_gen = self._render_gen
        self._processing = False
        costs = EquipmentMechanics.calculate_temper_cost(self.item)
        if not costs:
            return await interaction.response.send_message(
                "No tempers remaining.", ephemeral=True
            )

        uid, gid = self.user_id, str(interaction.guild.id)
        has_res, cost_lines, self.inventory_snapshot = await self._check_triad_costs(
            costs, uid, gid
        )
        self.costs = costs
        desc = f"{get_quip('temper')}\n\n**Temper Cost:**\n{cost_lines}"

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
        embed.set_author(name="Armorsmith Veyra", icon_url=VEYRA_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_TEMPER)
        await self._send_render(interaction, embed, render_gen=_my_gen)

    async def confirm_temper(self, interaction: Interaction, use_rune: bool):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

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
            try:
                from core.quests.mechanics import tick_quest_progress

                await tick_quest_progress(
                    self.bot, self.user_id, str(interaction.guild_id), "rune_potential"
                )
            except Exception:
                pass
            bonus = 10
        else:
            bonus = 0
        uid, gid = self.user_id, str(interaction.guild.id)

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        ore = self.inventory_snapshot["ore"]
        log = self.inventory_snapshot["log"]
        bone = self.inventory_snapshot["bone"]

        # Re-fetch live counts to avoid negatives from concurrent settlement updates
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

        success, stat, amount = EquipmentMechanics.roll_temper_outcome(
            self.item, bonus_chance=bonus
        )

        res_embed = discord.Embed(title="Temper Result")
        res_embed.set_author(name="Armorsmith Veyra", icon_url=VEYRA_AUTHOR)
        res_embed.set_thumbnail(url=UPGRADE_TEMPER)
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
                f"{get_quip('temper')}\n\n"
                f"🛡️ **Success!**\nIncreased **{stat.upper()}** by **{amount}**."
            )
        else:
            self.item.temper_remaining -= 1
            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                "armor",
                "temper_remaining",
                self.item.temper_remaining,
            )
            res_embed.color = discord.Color.dark_grey()
            res_embed.description = (
                "🔨 **Failed.**\nThe metal cooled too quickly. Materials consumed."
            )

        # UI Refresh
        self.clear_items()
        if self.item.temper_remaining > 0:
            again_btn = Button(label="Temper Again", style=ButtonStyle.success)
            again_btn.callback = self.render
            self.add_item(again_btn)
        self.add_back_button()

        await interaction.edit_original_response(embed=res_embed, view=self)


class ImbueView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Armor, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self._processing = False

    async def render(self, interaction: Interaction):
        self._render_gen += 1
        _my_gen = self._render_gen
        runes = await self.bot.database.users.get_currency(self.user_id, "imbue_runes")

        embed = discord.Embed(
            title="Imbue Armor",
            description=(
                f"{get_quip('imbue')}\n\n"
                f"Cost: 1 Rune of Imbuing (Owned: {runes})\nSuccess Rate: **50%**\n\nGrants a powerful passive ability."
            ),
            color=discord.Color.purple(),
        )
        embed.set_author(name="Armorsmith Veyra", icon_url=VEYRA_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_TEMPER)
        self.clear_items()
        confirm_btn = Button(
            label="Imbue", style=ButtonStyle.primary, disabled=(runes == 0)
        )
        confirm_btn.callback = self.confirm
        self.add_item(confirm_btn)
        self.add_back_button()

        await self._send_render(interaction, embed, render_gen=_my_gen)

    async def confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        await self.bot.database.users.modify_currency(self.user_id, "imbue_runes", -1)

        self.item.imbue_remaining = 0
        await self.bot.database.equipment.update_counter(
            self.item.item_id, "armor", "imbue_remaining", 0
        )

        embed = discord.Embed(title="Imbue Result")
        embed.set_author(name="Armorsmith Veyra", icon_url=VEYRA_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_TEMPER)
        if random.random() <= 0.5:
            new_p = random.choice(
                [
                    "Impregnable",
                    "Piety",
                    "Transcendence",
                    "Treasure Hunter",
                    "Unlimited Wealth",
                    "Alchemist",
                ]
            )
            self.item.passive = new_p
            await self.bot.database.equipment.update_passive(
                self.item.item_id, "armor", new_p, "armor_passive"
            )
            embed.color = discord.Color.gold()
            passive_desc = get_armor_passive_description(new_p)
            embed.description = (
                f"{get_quip('imbue')}\n\n"
                f"✨ **Success!** Imbued with **{new_p}**!"
                + (f"\n*{passive_desc}*" if passive_desc else "")
            )
        else:
            embed.color = discord.Color.dark_grey()
            embed.description = "The Rune shattered without effect."

        self.clear_items()
        self.add_back_button()
        await interaction.edit_original_response(embed=embed, view=self)


class ReinforceView(BaseUpgradeView):
    """
    Reinforcement view for Armor, Glove, Boot, and Helmet.
    Uses Shatter Runes to add reinforcement slots; each slot bumps the item's main stat.
    """

    def __init__(self, bot, user_id, item, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self.cost_data = {}
        self._processing = False

    def _reinforce_info(self):
        """Returns (db_item_type, stat_column, stat_label, current_value, is_pct)."""
        if isinstance(self.item, Armor):
            label = "ATK" if self.item.main_stat_type == "atk" else "DEF"
            return "armor", "main_stat", label, self.item.main_stat, False
        if isinstance(self.item, Glove):
            if self.item.attack > 0:
                return "glove", "attack", "ATK", self.item.attack, False
            if self.item.defence > 0:
                return "glove", "defence", "DEF", self.item.defence, False
            return "glove", "ward", "Ward", self.item.ward, True
        if isinstance(self.item, Boot):
            if self.item.attack > 0:
                return "boot", "attack", "ATK", self.item.attack, False
            if self.item.defence > 0:
                return "boot", "defence", "DEF", self.item.defence, False
            return "boot", "ward", "Ward", self.item.ward, True
        # Helmet
        if self.item.defence > 0:
            return "helmet", "defence", "DEF", self.item.defence, False
        return "helmet", "ward", "Ward", self.item.ward, True

    async def render(self, interaction: Interaction):
        self._render_gen += 1
        _my_gen = self._render_gen
        self._processing = False
        self.cost_data = EquipmentMechanics.calculate_reinforce_cost(self.item)
        cost_gold = self.cost_data["gold"]
        materials = self.cost_data.get("materials", [])
        itype, stat_col, stat_label, stat_val, is_pct = self._reinforce_info()
        val_str = f"{stat_val:,}%" if is_pct else f"{stat_val:,}"

        uid, sid = self.user_id, str(interaction.guild.id)
        user_gold = await self.bot.database.users.get_gold(uid)
        shatter_runes = await self.bot.database.users.get_currency(uid, "shatter_runes")

        has_funds = user_gold >= cost_gold
        has_mats, mat_status = await self._check_listed_materials(materials, uid, sid)

        has_slots = self.item.reinforces_remaining > 0

        desc = (
            f"{get_quip('reinforce')}\n\n"
            f"**Main Stat:** {stat_label} {val_str}\n"
            f"**Reinforces Remaining:** {self.item.reinforces_remaining}\n"
            f"**Reinforcement Level:** +{self.item.reinforcement_lvl}\n"
            f"**Gold Cost:** {cost_gold:,} ({user_gold:,})"
        )
        if mat_status:
            desc += f"\n{mat_status}"

        self.clear_items()

        action_btn = Button(label="Reinforce", style=ButtonStyle.success)
        if not has_slots:
            desc += f"\n\n**0 Reinforces left!** Use a Shatter Rune to add a slot? (Owned: {shatter_runes})"
            action_btn.label = "Use Shatter Rune"
            action_btn.style = ButtonStyle.primary
            action_btn.disabled = shatter_runes == 0
        else:
            action_btn.disabled = not (has_funds and has_mats)

        action_btn.callback = self.confirm_reinforce
        self.add_item(action_btn)

        shattermaxx_btn = Button(label="Reinforcemaxx", style=ButtonStyle.danger)
        shattermaxx_btn.disabled = shatter_runes == 0 and not (
            has_funds and has_mats and has_slots
        )
        shattermaxx_btn.callback = self.shattermaxx_preview
        self.add_item(shattermaxx_btn)

        self.add_back_button()

        color = (
            discord.Color.blue() if (has_funds and has_mats) else discord.Color.red()
        )
        embed = discord.Embed(
            title=f"Reinforce {self.item.name}", description=desc, color=color
        )
        embed.set_author(name="Armorsmith Veyra", icon_url=VEYRA_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_TEMPER)
        await self._send_render(interaction, embed, render_gen=_my_gen)

    async def confirm_reinforce(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        itype, stat_col, stat_label, _, is_pct = self._reinforce_info()

        # Use Shatter Rune to add a slot
        if self.item.reinforces_remaining <= 0:
            shatter_runes = await self.bot.database.users.get_currency(
                self.user_id, "shatter_runes"
            )
            if shatter_runes <= 0:
                return await interaction.response.send_message(
                    "You don't have any Shatter Runes!", ephemeral=True
                )
            await self.bot.database.users.modify_currency(
                self.user_id, "shatter_runes", -1
            )
            await self.bot.database.equipment.update_counter(
                self.item.item_id, itype, "reinforces_remaining", 1
            )
            self.item.reinforces_remaining += 1
            try:
                from core.quests.mechanics import tick_quest_progress

                await tick_quest_progress(
                    self.bot, self.user_id, str(interaction.guild_id), "rune_shatter"
                )
            except Exception:
                pass
            await self.render(interaction)
            return

        # Perform reinforcement
        cost_gold = self.cost_data["gold"]
        materials = self.cost_data.get("materials", [])
        uid, sid = self.user_id, str(interaction.guild.id)

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        try:
            for mat in materials:
                success = await self.bot.database.skills.deduct_resource_atomic(
                    uid, sid, mat["table"], mat["column"], mat["qty"]
                )
                if not success:
                    return await interaction.followup.send(
                        f"Insufficient {mat['name']}!", ephemeral=True
                    )

            gold_ok = await self.bot.database.users.deduct_gold_atomic(
                self.user_id, cost_gold
            )
            if not gold_ok:
                return await interaction.followup.send(
                    "Insufficient gold!", ephemeral=True
                )

            gain = EquipmentMechanics.roll_reinforce_outcome(self.item, stat_col)
            setattr(self.item, stat_col, getattr(self.item, stat_col) + gain)
            await self.bot.database.equipment.increase_stat(
                self.item.item_id, itype, stat_col, gain
            )

            self.item.reinforces_remaining -= 1
            self.item.reinforcement_lvl += 1
            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                itype,
                "reinforces_remaining",
                self.item.reinforces_remaining,
            )
            await self.bot.database.equipment.increase_stat(
                self.item.item_id, itype, "reinforcement_lvl", 1
            )

            new_val = getattr(self.item, stat_col)
            suffix = "%" if is_pct else ""
            embed = discord.Embed(
                title="Reinforce Complete! ✨", color=discord.Color.green()
            )
            embed.set_author(name="Armorsmith Veyra", icon_url=VEYRA_AUTHOR)
            embed.set_thumbnail(url=UPGRADE_REINFORCE)
            embed.description = (
                f"{get_quip('reinforce')}\n\n"
                f"**Gain:** +{gain}{suffix} {stat_label}\n"
                f"**Reinforcement:** +{self.item.reinforcement_lvl}\n\n"
                f"**{stat_label}:** {new_val:,}{suffix}"
            )

            self.clear_items()
            cont_btn = Button(label="Continue", style=ButtonStyle.primary)
            cont_btn.callback = self.render
            self.add_item(cont_btn)
            self.add_back_button()

            await interaction.edit_original_response(embed=embed, view=self)
            self.message = await interaction.original_response()

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    async def shattermaxx_preview(self, interaction: Interaction):
        """Simulate Shattermaxx and show a resource-cost confirmation before executing."""
        await interaction.response.defer()

        uid, sid = self.user_id, str(interaction.guild.id)
        shatter_runes = await self.bot.database.users.get_currency(uid, "shatter_runes")
        gold = await self.bot.database.users.get_gold(uid)

        itype, stat_col, stat_label, _, is_pct = self._reinforce_info()

        # Read current material inventory for simulation
        initial_cost = EquipmentMechanics.calculate_reinforce_cost(self.item)
        all_mat_keys: dict[str, dict] = {}  # column → mat dict
        for m in initial_cost.get("materials", []):
            all_mat_keys[m["column"]] = m
        for m in all_mat_keys.values():
            m["_stock"] = await self.bot.database.skills.get_single_resource(
                uid, sid, m["table"], m["column"]
            )

        import copy

        sim_item = copy.copy(self.item)
        sim_runes = shatter_runes
        sim_gold = gold
        sim_mats = {col: m["_stock"] for col, m in all_mat_keys.items()}
        reinforces_done = 0
        runes_used = 0
        gold_used = 0
        mat_totals: dict[str, int] = {}
        stop_reason = "Complete."

        while True:
            if sim_item.reinforces_remaining == 0:
                if sim_runes == 0:
                    stop_reason = "Ran out of Shatter Runes."
                    break
                sim_runes -= 1
                sim_item.reinforces_remaining = 1
                runes_used += 1

            cost_data = EquipmentMechanics.calculate_reinforce_cost(sim_item)
            cost_gold = cost_data["gold"]
            sim_materials = cost_data.get("materials", [])

            if sim_gold < cost_gold:
                stop_reason = "Ran out of Gold."
                break

            short = next(
                (m for m in sim_materials if sim_mats.get(m["column"], 0) < m["qty"]),
                None,
            )
            if short:
                stop_reason = f"Ran out of {short['name']}."
                break

            sim_gold -= cost_gold
            gold_used += cost_gold
            for mat in sim_materials:
                sim_mats[mat["column"]] = sim_mats.get(mat["column"], 0) - mat["qty"]
                mat_totals[mat["name"]] = mat_totals.get(mat["name"], 0) + mat["qty"]

            sim_item.reinforces_remaining -= 1
            sim_item.reinforcement_lvl += 1
            reinforces_done += 1

            if reinforces_done >= 10_000:
                stop_reason = "Reached simulation cap (10,000 reinforces)."
                break

        if reinforces_done == 0:
            await interaction.followup.send(
                f"No reinforces possible: {stop_reason}", ephemeral=True
            )
            return

        mat_lines = (
            "\n".join(f"  {name}: {qty:,}" for name, qty in mat_totals.items())
            or "  None"
        )
        embed = discord.Embed(title="⚠️ Confirmation", color=discord.Color.orange())
        embed.set_author(name="Armorsmith Veyra", icon_url=VEYRA_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_REINFORCE)
        embed.description = (
            f"This will perform **{reinforces_done:,}** reinforce(s) using up to **{runes_used}** Shatter Rune(s).\n\n"
            f"**Estimated Resources Consumed:**\n"
            f"💰 Gold: {gold_used:,}\n"
            f"💥 Shatter Runes: {runes_used}\n"
            f"📦 Materials:\n{mat_lines}\n\n"
            f"*Stops when: {stop_reason}*\n\n"
            f"Proceed?"
        )

        self.clear_items()
        confirm_btn = Button(label="Confirm", style=ButtonStyle.danger)
        confirm_btn.callback = self.shattermaxx_execute
        self.add_item(confirm_btn)

        cancel_btn = Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self.render
        self.add_item(cancel_btn)

        await interaction.edit_original_response(embed=embed, view=self)
        self.message = await interaction.original_response()

    async def shattermaxx_execute(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        itype, stat_col, stat_label, _, is_pct = self._reinforce_info()
        uid, sid = self.user_id, str(interaction.guild.id)

        reinforces_done = 0
        shatter_runes_used = 0
        total_gain = 0
        stop_reason = "Complete."

        while True:
            if self.item.reinforces_remaining == 0:
                runes = await self.bot.database.users.get_currency(uid, "shatter_runes")
                if runes == 0:
                    stop_reason = "Ran out of Shatter Runes."
                    break
                await self.bot.database.users.modify_currency(uid, "shatter_runes", -1)
                await self.bot.database.equipment.update_counter(
                    self.item.item_id, itype, "reinforces_remaining", 1
                )
                self.item.reinforces_remaining = 1
                shatter_runes_used += 1
                try:
                    from core.quests.mechanics import tick_quest_progress

                    await tick_quest_progress(
                        self.bot,
                        self.user_id,
                        str(interaction.guild.id),
                        "rune_shatter",
                    )
                except Exception:
                    pass

            cost_data = EquipmentMechanics.calculate_reinforce_cost(self.item)
            cost_gold = cost_data["gold"]
            materials = cost_data.get("materials", [])

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

            gold_ok = await self.bot.database.users.deduct_gold_atomic(uid, cost_gold)
            if not gold_ok:
                stop_reason = "Ran out of Gold."
                break

            gain = EquipmentMechanics.roll_reinforce_outcome(self.item, stat_col)
            setattr(self.item, stat_col, getattr(self.item, stat_col) + gain)
            total_gain += gain
            await self.bot.database.equipment.increase_stat(
                self.item.item_id, itype, stat_col, gain
            )

            self.item.reinforces_remaining -= 1
            self.item.reinforcement_lvl += 1
            await self.bot.database.equipment.update_counter(
                self.item.item_id,
                itype,
                "reinforces_remaining",
                self.item.reinforces_remaining,
            )
            await self.bot.database.equipment.increase_stat(
                self.item.item_id, itype, "reinforcement_lvl", 1
            )
            reinforces_done += 1

        if reinforces_done == 0:
            await interaction.followup.send(stop_reason, ephemeral=True)
            return

        suffix = "%" if is_pct else ""
        new_val = getattr(self.item, stat_col)
        embed = discord.Embed(title="⚒️ Complete", color=discord.Color.gold())
        embed.set_author(name="Armorsmith Veyra", icon_url=VEYRA_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_REINFORCE)
        embed.description = (
            f"{get_quip('reinforce')}\n\n"
            f"**Reinforces Performed:** {reinforces_done}\n"
            f"**Shatter Runes Used:** {shatter_runes_used}\n"
            f"**Total Gain:** +{total_gain}{suffix} {stat_label}\n"
            f"**Reinforcement Level:** +{self.item.reinforcement_lvl}\n\n"
            f"**{stat_label}:** {new_val:,}{suffix}\n\n"
            f"*Stopped: {stop_reason}*"
        )

        self.clear_items()
        cont_btn = Button(label="Continue", style=ButtonStyle.primary)
        cont_btn.callback = self.render
        self.add_item(cont_btn)
        self.add_back_button()

        await interaction.edit_original_response(embed=embed, view=self)
        self.message = await interaction.original_response()


class EngramView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Armor, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self._processing = False

    async def render(self, interaction: Interaction):
        self._render_gen += 1
        _my_gen = self._render_gen
        self._processing = False
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
        self.embed.set_author(name="Artificer Sylas", icon_url=SYLAS_AUTHOR)
        self.embed.set_thumbnail(url=UPGRADE_CELESTIAL_ENGRAM)

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

        await self._send_render(interaction, self.embed, render_gen=_my_gen)

    async def confirm_engram(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        server_id = str(interaction.guild.id)
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        if uber_prog["celestial_engrams"] < 1:
            self._processing = False
            return await interaction.response.send_message(
                "You do not have any Celestial Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            self._processing = False
            return await interaction.response.send_message(
                "You need **25,000,000 gold** to use a Celestial Engram.",
                ephemeral=True,
            )

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
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
        res_embed.set_author(name="Artificer Sylas", icon_url=SYLAS_AUTHOR)
        res_embed.set_thumbnail(url=UPGRADE_CELESTIAL_ENGRAM)

        self.clear_items()
        if uber_prog["celestial_engrams"] - 1 > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)
        self.message = await interaction.original_response()
