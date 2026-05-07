import random

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.images import (
    UPGRADE_CELESTIAL_ENGRAM,
    UPGRADE_REINFORCE,
    UPGRADE_TEMPER,
)
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Armor, Boot, Glove


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
        embed.set_thumbnail(url=UPGRADE_TEMPER)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
        self.message = await interaction.original_response()

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

        success, stat, amount = EquipmentMechanics.roll_temper_outcome(
            self.item, bonus_chance=bonus
        )

        res_embed = discord.Embed(title="Temper Result")
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
        embed.set_thumbnail(url=UPGRADE_TEMPER)
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
        self.message = await interaction.original_response()

    async def confirm(self, interaction: Interaction):
        await self.bot.database.users.modify_currency(self.user_id, "imbue_runes", -1)

        self.item.imbue_remaining = 0
        await self.bot.database.equipment.update_counter(
            self.item.item_id, "armor", "imbue_remaining", 0
        )

        embed = discord.Embed(title="Imbue Result")
        embed.set_thumbnail(url=UPGRADE_TEMPER)
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


class ReinforceView(BaseUpgradeView):
    """
    Reinforcement view for Armor, Glove, Boot, and Helmet.
    Uses Shatter Runes to add reinforcement slots; each slot bumps the item's main stat.
    """

    def __init__(self, bot, user_id, item, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self.cost_data = {}

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
        self.cost_data = EquipmentMechanics.calculate_reinforce_cost(self.item)
        cost_gold = self.cost_data["gold"]
        materials = self.cost_data.get("materials", [])
        itype, stat_col, stat_label, stat_val, is_pct = self._reinforce_info()
        val_str = f"{stat_val:,}%" if is_pct else f"{stat_val:,}"

        uid, sid = self.user_id, str(interaction.guild.id)
        user_gold = await self.bot.database.users.get_gold(uid)
        shatter_runes = await self.bot.database.users.get_currency(uid, "shatter_runes")

        has_funds = user_gold >= cost_gold
        has_mats = True

        mat_status = ""
        if materials:
            mat_status = "\n**Required Materials:**"
            for mat in materials:
                table, col, qty, name = (
                    mat["table"],
                    mat["column"],
                    mat["qty"],
                    mat["name"],
                )
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

        has_slots = self.item.reinforces_remaining > 0

        desc = (
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
        self.add_back_button()

        color = (
            discord.Color.blue() if (has_funds and has_mats) else discord.Color.red()
        )
        embed = discord.Embed(
            title=f"Reinforce {self.item.name}", description=desc, color=color
        )
        embed.set_thumbnail(url=UPGRADE_REINFORCE)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
        self.message = await interaction.original_response()

    async def confirm_reinforce(self, interaction: Interaction):
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
            await self.render(interaction)
            return

        # Perform reinforcement
        cost_gold = self.cost_data["gold"]
        materials = self.cost_data.get("materials", [])
        uid, sid = self.user_id, str(interaction.guild.id)

        await interaction.response.defer()

        try:
            for mat in materials:
                async with self.bot.database.connection.execute(
                    f"UPDATE {mat['table']} SET {mat['column']} = {mat['column']} - ? "
                    f"WHERE user_id=? AND server_id=? AND {mat['column']} >= ?",
                    (mat["qty"], uid, sid, mat["qty"]),
                ) as c:
                    if c.rowcount == 0:
                        return await interaction.followup.send(
                            f"Insufficient {mat['name']}!", ephemeral=True
                        )

            await self.bot.database.users.modify_gold(self.user_id, -cost_gold)

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
            await self.bot.database.connection.commit()

            new_val = getattr(self.item, stat_col)
            suffix = "%" if is_pct else ""
            embed = discord.Embed(
                title="Reinforce Complete! ✨", color=discord.Color.green()
            )
            embed.set_thumbnail(url=UPGRADE_REINFORCE)
            embed.description = (
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
        if uber_prog["celestial_engrams"] < 1:
            return await interaction.response.send_message(
                "You do not have any Celestial Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            return await interaction.response.send_message(
                "You need **25,000,000 gold** to use a Celestial Engram.",
                ephemeral=True,
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
        res_embed.set_thumbnail(url=UPGRADE_CELESTIAL_ENGRAM)

        self.clear_items()
        if uber_prog["celestial_engrams"] - 1 > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)
        self.message = await interaction.original_response()
