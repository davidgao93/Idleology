import discord
from discord import Interaction, ButtonStyle, SelectOption
from discord.ui import View, Button, Select
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Weapon, Armor, Accessory, Glove, Boot, Helmet
from core.items.factory import create_weapon
import random

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
        try: await self.parent_view.message.edit(view=self.parent_view)
        except: pass

    async def go_back(self, interaction: Interaction):
        # 1. Import inside method to avoid circular import at top of file
        from core.inventory.views import ItemDetailView
        from core.ui.inventory import InventoryUI

        # 2. Get the Grandparent (Inventory List) to pass down
        inventory_view = self.parent_view.parent
        
        # 3. Create a FRESH ItemDetailView
        # This resets the timeout counter (180s) and regenerates buttons cleanly
        new_detail_view = ItemDetailView(self.bot, self.user_id, self.item, inventory_view)
        await new_detail_view.fetch_data() # Ensure keys/currency checks run
        
        # 4. Check equipped status using the Grandparent's state
        is_equipped = (self.item.item_id == inventory_view.equipped_id)
        
        embed = InventoryUI.get_item_details_embed(self.item, is_equipped)
        
        # 5. Edit message with NEW view and clear any status content
        await interaction.response.edit_message(content=None, embed=embed, view=new_detail_view)
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
            return await interaction.response.send_message("No forges remaining!", ephemeral=True)

        # Fetch Resources
        uid, gid = self.user_id, str(interaction.guild.id)
        # 1. Fetch Raw AND Refined
        # We need to map raw resource names to their refined counterparts in the DB
        # Iron -> iron_bar, Coal -> steel_bar, Gold -> gold_bar, etc.
        raw_ore = costs['ore_type']
        refined_ore = f"{raw_ore if raw_ore != 'coal' else 'steel'}_bar" # Coal -> Steel special case
        
        raw_log = costs['log_type']
        refined_log = f"{raw_log}_plank"
        
        raw_bone = costs['bone_type']
        refined_bone = f"{raw_bone}_essence"

        # Fetch quantities via helper to handle DB tuple mapping
        # (Assuming TradeManager logic or direct SQL here for precision)
        # For simplicity in this example, we execute a direct select
        async with self.bot.database.connection.execute(
            f"SELECT {raw_ore}, {refined_ore} FROM mining WHERE user_id=? AND server_id=?", (uid, gid)
        ) as cursor:
            mining_res = await cursor.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {raw_log}_logs, {refined_log} FROM woodcutting WHERE user_id=? AND server_id=?", (uid, gid)
        ) as cursor:
            wood_res = await cursor.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {raw_bone}_bones, {refined_bone} FROM fishing WHERE user_id=? AND server_id=?", (uid, gid)
        ) as cursor:
            fish_res = await cursor.fetchone() or (0, 0)

        gold = await self.bot.database.users.get_gold(uid)

        # 2. Logic: Total Available = Raw + Refined
        total_ore = mining_res[0] + mining_res[1]
        total_log = wood_res[0] + wood_res[1]
        total_bone = fish_res[0] + fish_res[1]

        has_res = (
            total_ore >= costs['ore_qty'] and
            total_log >= costs['log_qty'] and
            total_bone >= costs['bone_qty'] and
            gold >= costs['gold']
        )

        # 3. Store data for logic
        self.costs = costs
        self.inventory_snapshot = {
            'ore': {'raw_col': raw_ore, 'ref_col': refined_ore, 'raw_amt': mining_res[0], 'ref_amt': mining_res[1]},
            'log': {'raw_col': f"{raw_log}_logs", 'ref_col': refined_log, 'raw_amt': wood_res[0], 'ref_amt': wood_res[1]},
            'bone': {'raw_col': f"{raw_bone}_bones", 'ref_col': refined_bone, 'raw_amt': fish_res[0], 'ref_amt': fish_res[1]}
        }

        desc = (f"**Cost:**\n"
                f"⛏️ {costs['ore_qty']} {costs['ore_type'].title()} (Have: {total_ore})\n"
                f"🪓 {costs['log_qty']} {costs['log_type'].title()} (Have: {total_log})\n"
                f"🎣 {costs['bone_qty']} {costs['bone_type'].title()} (Have: {total_bone})\n"
                f"💰 {costs['gold']:,} Gold")
        
        if total_ore >= costs['ore_qty'] and mining_res[0] < costs['ore_qty']:
            desc += "\n*Using Refined Ingots to substitute missing Ore.*"

        self.embed = discord.Embed(
            title=f"Forge {self.item.name}",
            description=desc,
            color=discord.Color.green() if has_res else discord.Color.red()
        )
        self.embed.set_thumbnail(url="https://i.imgur.com/jzEMUxe.jpeg")
        
        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()
        
        forge_btn = Button(label="Forge!", style=ButtonStyle.success, disabled=not has_res)
        forge_btn.callback = self.confirm_forge
        self.add_item(forge_btn)
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
                    (to_take_raw, uid, gid)
                )
            if to_take_ref > 0:
                await self.bot.database.connection.execute(
                    f"UPDATE {table} SET {ref_col} = {ref_col} - ? WHERE user_id=? AND server_id=?", 
                    (to_take_ref, uid, gid)
                )

        # Execute Deductions
        await deduct_smart('mining', self.inventory_snapshot['ore']['raw_col'], self.inventory_snapshot['ore']['ref_col'], self.inventory_snapshot['ore']['raw_amt'], self.costs['ore_qty'])
        await deduct_smart('woodcutting', self.inventory_snapshot['log']['raw_col'], self.inventory_snapshot['log']['ref_col'], self.inventory_snapshot['log']['raw_amt'], self.costs['log_qty'])
        await deduct_smart('fishing', self.inventory_snapshot['bone']['raw_col'], self.inventory_snapshot['bone']['ref_col'], self.inventory_snapshot['bone']['raw_amt'], self.costs['bone_qty'])
        
        await self.bot.database.users.modify_gold(uid, -self.costs['gold'])
        await self.bot.database.connection.commit()

        success, new_passive = EquipmentMechanics.roll_forge_outcome(self.item)
        
        result_embed = discord.Embed(title="Forge Result")
        if success:
            self.item.forges_remaining -= 1 # Only decrement on success
            self.item.passive = new_passive
            await self.bot.database.equipment.update_passive(self.item.item_id, 'weapon', new_passive)
            await self.bot.database.equipment.update_counter(self.item.item_id, 'weapon', 'forges_remaining', self.item.forges_remaining)
            
            result_embed.description = f"🔥 **Success!**\nNew Passive: **{new_passive.title()}**"
            result_embed.color = discord.Color.gold()
        else:
            self.item.forges_remaining -= 1
            await self.bot.database.equipment.update_counter(self.item.item_id, 'weapon', 'forges_remaining', self.item.forges_remaining)
            result_embed.description = f"💨 **Failed.**\nThe hammer didn't strike true, resources consumed.\n\nForges Remaining: {self.item.forges_remaining}"
            result_embed.color = discord.Color.dark_grey()

        # --- RESULT UI BUILD ---
        self.clear_items()
        
        if self.item.forges_remaining > 0:
            again_btn = Button(label="Forge Again", style=ButtonStyle.success)
            again_btn.callback = self.render # Points back to render to refresh costs/buttons
            self.add_item(again_btn)
            
        self.add_back_button()

        await interaction.response.edit_message(embed=result_embed, view=self)


class RefineView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        cost = EquipmentMechanics.calculate_refine_cost(self.item)
        gold = await self.bot.database.users.get_gold(self.user_id)
        
        has_funds = gold >= cost
        has_refines = self.item.refines_remaining > 0
        
        runes = 0
        if not has_refines:
            runes = await self.bot.database.users.get_currency(self.user_id, 'refinement_runes')

        desc = (f"**Refines Remaining:** {self.item.refines_remaining}\n"
                f"**Refinement Level:** +{self.item.refinement_lvl}\n"
                f"**Cost:** {cost:,} Gold ({gold:,})\n")
        
        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()
        
        action_btn = Button(label="Refine", style=ButtonStyle.success)
        
        if not has_refines:
            desc += f"\n**0 Refines left!** Use a Rune? (Owned: {runes})"
            action_btn.label = "Use Rune"
            action_btn.style = ButtonStyle.primary
            action_btn.disabled = (runes == 0)
        else:
            action_btn.disabled = not has_funds

        action_btn.callback = self.confirm_refine
        self.add_item(action_btn)
        self.add_back_button()

        self.embed = discord.Embed(title=f"Refine {self.item.name}", description=desc, color=discord.Color.blue())
        self.embed.set_thumbnail(url="https://i.imgur.com/NNB21Ix.jpeg")
        self.cost = cost
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirm_refine(self, interaction: Interaction):
        # Rune Logic
        if self.item.refines_remaining <= 0:
            await self.bot.database.users.modify_currency(self.user_id, 'refinement_runes', -1)
            await self.bot.database.equipment.update_counter(self.item.item_id, 'weapon', 'refines_remaining', 1)
            self.item.refines_remaining += 1
            await self.render(interaction) # Refresh UI immediately
            return

        # Gold Logic
        await self.bot.database.users.modify_gold(self.user_id, -self.cost)
        
        stats = EquipmentMechanics.roll_refine_outcome(self.item)
        
        # Commit Updates
        if stats['attack']: 
            self.item.attack += stats['attack']
            await self.bot.database.equipment.increase_stat(self.item.item_id, 'weapon', 'attack', stats['attack'])
        if stats['defence']: 
            self.item.defence += stats['defence']
            await self.bot.database.equipment.increase_stat(self.item.item_id, 'weapon', 'defence', stats['defence'])
        if stats['rarity']: 
            self.item.rarity += stats['rarity']
            await self.bot.database.equipment.increase_stat(self.item.item_id, 'weapon', 'rarity', stats['rarity'])

        self.item.refines_remaining -= 1
        self.item.refinement_lvl += 1
        await self.bot.database.equipment.update_counter(self.item.item_id, 'weapon', 'refines_remaining', self.item.refines_remaining)
        await self.bot.database.equipment.increase_stat(self.item.item_id, 'weapon', 'refinement_lvl', 1)

        # Result Logic
        res_str = ", ".join([f"+{v} {k.title()}" for k,v in stats.items() if v > 0]) or "No stats gained."
        
        embed = discord.Embed(title="Refine Complete! ✨", color=discord.Color.green())
        embed.set_thumbnail(url="https://i.imgur.com/NNB21Ix.jpeg")
        embed.description = f"**Gains:** {res_str}\n\n**New Stats:**\n⚔️ {self.item.attack} | 🛡️ {self.item.defence} | ✨ {self.item.rarity}%"
        
        # --- RESULT UI BUILD ---
        self.clear_items()
        
        # Allow chain refining
        runes = await self.bot.database.users.get_currency(self.user_id, 'refinement_runes')
        if self.item.refines_remaining > 0 or runes > 0:
            again_btn = Button(label="Refine Again", style=ButtonStyle.primary)
            again_btn.callback = self.render
            self.add_item(again_btn)
            
        self.add_back_button()
        
        await interaction.response.edit_message(embed=embed, view=self)


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
        runes = await self.bot.database.users.get_currency(self.user_id, 'potential_runes')
        
        # 3. Logic
        is_capped = self.item.passive_lvl >= max_lvl
        has_attempts = self.item.potential_remaining > 0
        base_rate = max(75 - (self.item.passive_lvl * 5), 30)
        
        desc = (f"**Current Level:** {self.item.passive_lvl}/{max_lvl}\n"
                f"**Attempts Left:** {self.item.potential_remaining}\n"
                f"**Success Rate:** {base_rate}%\n"
                f"**Cost:** {cost:,} Gold ({gold:,})\n\n"
                f"💎 **Runes Owned:** {runes}")

        self.cost = cost
        self.rune_bonus = rune_bonus
        
        embed = discord.Embed(title=f"Enchant {self.item.name}", description=desc, color=discord.Color.purple())
        embed.set_thumbnail(url="https://i.imgur.com/hqVvn68.jpeg")
        
        # --- BUTTONS ---
        self.clear_items()
        
        # Standard Enchant
        btn_std = Button(label=f"Enchant ({base_rate}%)", style=ButtonStyle.primary, row=0)
        btn_std.disabled = (gold < cost or not has_attempts or is_capped)
        btn_std.callback = lambda i: self.confirm_enchant(i, use_rune=False)
        self.add_item(btn_std)

        # Rune Enchant
        boosted_rate = min(100, base_rate + rune_bonus)
        btn_rune = Button(label=f"Use Rune ({boosted_rate}%)", style=ButtonStyle.success, emoji="💎", row=0)
        btn_rune.disabled = (gold < cost or not has_attempts or is_capped or runes < 1)
        btn_rune.callback = lambda i: self.confirm_enchant(i, use_rune=True)
        self.add_item(btn_rune)
        
        self.add_back_button()
        
        if interaction.response.is_done(): await interaction.edit_original_response(embed=embed, view=self)
        else: await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_enchant(self, interaction: Interaction, use_rune: bool):
        # Re-check funds/runes
        if use_rune:
            runes = await self.bot.database.users.get_currency(self.user_id, 'potential_runes')
            if runes < 1: return await interaction.response.send_message("No Runes left!", ephemeral=True)
            await self.bot.database.users.modify_currency(self.user_id, 'potential_runes', -1)
            bonus = self.rune_bonus
        else:
            bonus = 0

        # Deduct Gold
        await self.bot.database.users.modify_gold(self.user_id, -self.cost)
        
        # Roll
        success = EquipmentMechanics.roll_potential_outcome(self.item.passive_lvl, bonus_chance=bonus)
        
        # DB Updates
        itype = 'accessory' if isinstance(self.item, Accessory) else \
                ('glove' if isinstance(self.item, Glove) else \
                ('boot' if isinstance(self.item, Boot) else 'helmet'))

        self.item.potential_remaining -= 1
        await self.bot.database.equipment.update_counter(self.item.item_id, itype, 'potential_remaining', self.item.potential_remaining)

        result_embed = discord.Embed(title="Enchantment Result")
        result_embed.set_thumbnail(url="https://i.imgur.com/hqVvn68.jpeg")
        
        if success:
            if self.item.passive == "none":
                new_p = EquipmentMechanics.get_new_passive(itype)
                self.item.passive = new_p
                self.item.passive_lvl = 1
                await self.bot.database.equipment.update_passive(self.item.item_id, itype, new_p)
                await self.bot.database.equipment.update_counter(self.item.item_id, itype, 'passive_lvl', 1)
                msg = f"Unlocked **{new_p}**!"
            else:
                self.item.passive_lvl += 1
                await self.bot.database.equipment.update_counter(self.item.item_id, itype, 'passive_lvl', self.item.passive_lvl)
                msg = f"Upgraded to Level **{self.item.passive_lvl}**!"
            
            result_embed.color = discord.Color.gold()
            result_embed.description = f"✨ **Success!**\n{msg}"
        else:
            result_embed.color = discord.Color.dark_grey()
            result_embed.description = "💔 **Failed.**\nThe magic failed to take hold."

        # UI Refresh
        self.clear_items()
        max_lvl = 10 if isinstance(self.item, Accessory) else (5 if isinstance(self.item, (Glove, Helmet)) else 6)
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
        if not costs: return await interaction.response.send_message("No tempers remaining.", ephemeral=True)

        uid, gid = self.user_id, str(interaction.guild.id)

        # 1. Fetch Raw AND Refined (Mapped Identically to ForgeView)
        raw_ore = costs['ore_type']
        refined_ore = f"{raw_ore if raw_ore != 'coal' else 'steel'}_bar"
        
        raw_log = costs['log_type']
        refined_log = f"{raw_log}_plank"
        
        raw_bone = costs['bone_type']
        refined_bone = f"{raw_bone}_essence"

        # Direct SQL fetch for precision
        async with self.bot.database.connection.execute(
            f"SELECT {raw_ore}, {refined_ore} FROM mining WHERE user_id=? AND server_id=?", (uid, gid)
        ) as cursor:
            mining_res = await cursor.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {raw_log}_logs, {refined_log} FROM woodcutting WHERE user_id=? AND server_id=?", (uid, gid)
        ) as cursor:
            wood_res = await cursor.fetchone() or (0, 0)

        async with self.bot.database.connection.execute(
            f"SELECT {raw_bone}_bones, {refined_bone} FROM fishing WHERE user_id=? AND server_id=?", (uid, gid)
        ) as cursor:
            fish_res = await cursor.fetchone() or (0, 0)

        gold = await self.bot.database.users.get_gold(uid)

        # 2. Logic: Total Available = Raw + Refined
        total_ore = mining_res[0] + mining_res[1]
        total_log = wood_res[0] + wood_res[1]
        total_bone = fish_res[0] + fish_res[1]

        has_res = (
            total_ore >= costs['ore_qty'] and
            total_log >= costs['log_qty'] and
            total_bone >= costs['bone_qty'] and
            gold >= costs['gold']
        )

        # 3. Store Snapshot for Confirm Logic
        self.costs = costs
        self.inventory_snapshot = {
            'ore': {'raw_col': raw_ore, 'ref_col': refined_ore, 'raw_amt': mining_res[0], 'ref_amt': mining_res[1]},
            'log': {'raw_col': f"{raw_log}_logs", 'ref_col': refined_log, 'raw_amt': wood_res[0], 'ref_amt': wood_res[1]},
            'bone': {'raw_col': f"{raw_bone}_bones", 'ref_col': refined_bone, 'raw_amt': fish_res[0], 'ref_amt': fish_res[1]}
        }

        desc = (f"**Temper Cost:**\n"
                f"⛏️ {costs['ore_qty']} {costs['ore_type'].title()} (Have: {total_ore})\n"
                f"🪓 {costs['log_qty']} {costs['log_type'].title()} (Have: {total_log})\n"
                f"🎣 {costs['bone_qty']} {costs['bone_type'].title()} (Have: {total_bone})\n"
                f"💰 {costs['gold']:,} Gold")

        if total_ore >= costs['ore_qty'] and mining_res[0] < costs['ore_qty']:
            desc += "\n*Using Refined Ingots to substitute missing Ore.*"

        # New: Get Runes
        runes = await self.bot.database.users.get_currency(self.user_id, 'potential_runes')
        
        # Calculate Rates
        base_rate = 0.8
        max_tempers = 3
        if self.item.level > 40: max_tempers = 4
        if self.item.level > 80: max_tempers = 5
        current_step = max_tempers - self.item.temper_remaining
        
        current_pct = int((base_rate - (current_step * 0.05)) * 100)
        boosted_pct = min(100, current_pct + 10)

        desc += f"\n\n💎 **Runes Owned:** {runes}"

        # --- BUTTONS ---
        self.clear_items()
        
        # Standard Temper
        btn_std = Button(label=f"Temper ({current_pct}%)", style=ButtonStyle.success, row=0)
        btn_std.disabled = not has_res
        btn_std.callback = lambda i: self.confirm_temper(i, use_rune=False)
        self.add_item(btn_std)

        # Rune Temper (+10%)
        btn_rune = Button(label=f"Use Rune ({boosted_pct}%)", style=ButtonStyle.primary, emoji="💎", row=0)
        btn_rune.disabled = (not has_res or runes < 1)
        btn_rune.callback = lambda i: self.confirm_temper(i, use_rune=True)
        self.add_item(btn_rune)
        
        self.add_back_button()
        
        embed = discord.Embed(title="Temper Armor", description=desc, color=discord.Color.blue() if has_res else discord.Color.red())
        embed.set_thumbnail(url="https://i.imgur.com/tpEyVBm.png")
        
        if interaction.response.is_done(): await interaction.edit_original_response(embed=embed, view=self)
        else: await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_temper(self, interaction: Interaction, use_rune: bool):
        # Rune Check
        if use_rune:
            runes = await self.bot.database.users.get_currency(self.user_id, 'potential_runes')
            if runes < 1: return await interaction.response.send_message("No Runes left!", ephemeral=True)
            await self.bot.database.users.modify_currency(self.user_id, 'potential_runes', -1)
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
                    (to_take_raw, uid, gid)
                )
            if to_take_ref > 0:
                await self.bot.database.connection.execute(
                    f"UPDATE {table} SET {ref_col} = {ref_col} - ? WHERE user_id=? AND server_id=?", 
                    (to_take_ref, uid, gid)
                )

        # Execute Deductions
        await deduct_smart('mining', self.inventory_snapshot['ore']['raw_col'], self.inventory_snapshot['ore']['ref_col'], self.inventory_snapshot['ore']['raw_amt'], self.costs['ore_qty'])
        await deduct_smart('woodcutting', self.inventory_snapshot['log']['raw_col'], self.inventory_snapshot['log']['ref_col'], self.inventory_snapshot['log']['raw_amt'], self.costs['log_qty'])
        await deduct_smart('fishing', self.inventory_snapshot['bone']['raw_col'], self.inventory_snapshot['bone']['ref_col'], self.inventory_snapshot['bone']['raw_amt'], self.costs['bone_qty'])
        
        await self.bot.database.users.modify_gold(uid, -self.costs['gold'])
        
        # ... (Roll logic and Result Embed identical to before) ...
        success, stat, amount = EquipmentMechanics.roll_temper_outcome(self.item, bonus_chance=bonus)
        
        res_embed = discord.Embed(title="Temper Result")
        res_embed.set_thumbnail(url="https://i.imgur.com/tpEyVBm.png")
        if success:
            self.item.temper_remaining -= 1
            await self.bot.database.equipment.update_counter(self.item.item_id, 'armor', 'temper_remaining', self.item.temper_remaining)
            await self.bot.database.equipment.increase_stat(self.item.item_id, 'armor', stat, amount)
            if stat == 'pdr': self.item.pdr += amount
            elif stat == 'fdr': self.item.fdr += amount
            
            res_embed.color = discord.Color.green()
            res_embed.description = f"🛡️ **Success!**\nIncreased **{stat.upper()}** by **{amount}**."
        else:
            res_embed.color = discord.Color.dark_grey()
            res_embed.description = "🔨 **Failed.**\nThe metal cooled too quickly. Materials consumed."

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
        runes = await self.bot.database.users.get_currency(self.user_id, 'imbue_runes')
        
        embed = discord.Embed(
            title="Imbue Armor", 
            description=f"Cost: 1 Rune of Imbuing (Owned: {runes})\nSuccess Rate: **50%**\n\nGrants a powerful passive ability.",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url="https://i.imgur.com/tpEyVBm.png")
        self.clear_items()
        confirm_btn = Button(label="Imbue", style=ButtonStyle.primary, disabled=(runes == 0))
        confirm_btn.callback = self.confirm
        self.add_item(confirm_btn)
        self.add_back_button()
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def confirm(self, interaction: Interaction):
        await self.bot.database.users.modify_currency(self.user_id, 'imbue_runes', -1)
        
        self.item.imbue_remaining = 0
        await self.bot.database.equipment.update_counter(self.item.item_id, 'armor', 'imbue_remaining', 0)

        embed = discord.Embed(title="Imbue Result")
        embed.set_thumbnail(url="https://i.imgur.com/tpEyVBm.png")
        if random.random() <= 0.5:
            new_p = random.choice(["Invulnerable", "Mystical Might", "Omnipotent", "Treasure Hunter", "Unlimited Wealth", "Everlasting Blessing"])
            self.item.passive = new_p
            await self.bot.database.equipment.update_passive(self.item.item_id, 'armor', new_p, 'armor_passive')
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

    async def render(self, interaction: Interaction):
        # 1. Fetch Candidates (Unequipped, Refine >= 5, 0 Forges)
        raw_rows = await self.bot.database.equipment.fetch_void_forge_candidates(self.user_id)
        # Filter out self just in case, and convert
        self.candidates = [create_weapon(r) for r in raw_rows if r[0] != self.item.item_id]

        if not self.candidates:
            await interaction.response.send_message("No eligible sacrifice weapons found.\nRequires: Unequipped, Refinement +5, 0 Forges remaining.", ephemeral=True)
            return

        # 2. Build Select Menu
        options = []
        for w in self.candidates[:25]: # Discord Select limit
            lbl = f"Lv{w.level} {w.name} (+{w.refinement_lvl})"
            desc = f"Passive: {w.passive}"
            options.append(SelectOption(label=lbl, description=desc, value=str(w.item_id)))

        select = Select(placeholder="Select Sacrifice Weapon...", options=options)
        select.callback = self.select_callback
        
        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()
        self.add_item(select)
        self.add_back_button()

        embed = discord.Embed(
            title="Voidforge",
            description="Select a weapon to sacrifice.\nCost: 1 Void Key.\n\n**Effects:**\n25%: Add Passive as Pinnacle/Utmost\n25%: Overwrite Main Passive\n50%: Failure (Item Lost)",
            color=discord.Color.dark_purple()
        )
        embed.set_thumbnail(url="https://i.imgur.com/rZnRu0R.jpeg")
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def select_callback(self, interaction: Interaction):
        target_id = int(interaction.data['values'][0])
        target = next((w for w in self.candidates if w.item_id == target_id), None)
        
        if not target: return

        await self.bot.database.users.modify_currency(self.user_id, 'void_keys', -1)
        await self.bot.database.equipment.discard(target.item_id, 'weapon')

        inventory_view = self.parent_view.parent
        inventory_view.items = [i for i in inventory_view.items if i.item_id != target.item_id]
        
        # Recalculate pagination (in case pages decreased)
        inventory_view.total_pages = (len(inventory_view.items) + inventory_view.items_per_page - 1) // inventory_view.items_per_page
        if inventory_view.total_pages == 0: inventory_view.total_pages = 1 # Prevent div by zero errors elsewhere
        
        # Adjust current page if we were on the last page and it disappeared
        if inventory_view.current_page >= inventory_view.total_pages:
            inventory_view.current_page = max(0, inventory_view.total_pages - 1)
            
        # Refresh the buttons on the inventory view so they represent the new state when we go back
        inventory_view.update_buttons()

        # Logic
        roll = random.random()
        res_txt = ""
        color = discord.Color.dark_grey()

        if roll < 0.25:
            # Add as secondary
            slot = "pinnacle_passive" if self.item.p_passive == 'none' else "utmost_passive"
            await self.bot.database.equipment.update_passive(self.item.item_id, 'weapon', target.passive, slot)
            if slot == "pinnacle_passive": self.item.p_passive = target.passive
            else: self.item.u_passive = target.passive
            
            res_txt = f"🌌 **Success!**\n{target.passive.title()} added as {slot.replace('_', ' ').title()}."
            color = discord.Color.purple()
            
        elif roll < 0.50:
            # Overwrite main
            await self.bot.database.equipment.update_passive(self.item.item_id, 'weapon', target.passive)
            self.item.passive = target.passive
            res_txt = f"🔄 **Chaos!**\nMain passive overwritten with {target.passive.title()}."
            color = discord.Color.orange()
        else:
            res_txt = "❌ **Failure.**\nThe essence dissipated into the void."

        embed = discord.Embed(title="Voidforge Result", description=res_txt, color=color)
        embed.set_thumbnail(url="https://i.imgur.com/rZnRu0R.jpeg")
        # --- RESULT UI BUILD ---
        self.clear_items()
        
        # Voidforge is typically one-off due to key cost/rarity, but we can offer 'Voidforge Again' 
        # if they have more keys and candidates. For now, Back is sufficient.
        self.add_back_button()
        
        await interaction.response.edit_message(embed=embed, view=self)


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
            color=discord.Color.dark_red()
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
        await self.bot.database.equipment.discard(self.item.item_id, 'weapon')
        await self.bot.database.users.modify_currency(self.user_id, 'refinement_runes', self.runes_back)
        await self.bot.database.users.modify_currency(self.user_id, 'shatter_runes', -1)
        
        # Update Parent List (since item is gone)
        self.parent_view.parent.items = [i for i in self.parent_view.parent.items if i.item_id != self.item.item_id]
        self.parent_view.parent.update_buttons() # Refresh page buttons
        
        embed = discord.Embed(title="Shattered", color=discord.Color.red())
        embed.description = f"Item destroyed.\nYou gained **{self.runes_back}** Refinement Runes."

        # --- RESULT UI BUILD ---
        self.clear_items()
        
        # Since item is gone, "Back" implies "Back to Inventory List"
        return_btn = Button(label="Return to Inventory", style=ButtonStyle.secondary)
        return_btn.callback = self.return_to_list
        self.add_item(return_btn)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def return_to_list(self, interaction: Interaction):
        # Go back to the Inventory List (grandparent view)
        embed = await self.parent_view.parent.get_current_embed(interaction.user.display_name)
        await interaction.response.edit_message(embed=embed, view=self.parent_view.parent)
        self.stop()