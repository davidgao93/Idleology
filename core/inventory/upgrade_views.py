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
        # Return to item details
        await self.parent_view.fetch_data()
        from core.ui.inventory import InventoryUI
        embed = InventoryUI.get_item_details_embed(self.item, self.item.item_id == self.parent_view.parent.equipped_id)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
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
        mining = await self.bot.database.skills.get_data(uid, gid, 'mining')
        wood = await self.bot.database.skills.get_data(uid, gid, 'woodcutting')
        fish = await self.bot.database.skills.get_data(uid, gid, 'fishing')
        gold = await self.bot.database.users.get_gold(uid, gid)

        ore_idx = {'iron': 3, 'coal': 4, 'gold': 5, 'platinum': 6, 'idea': 7}.get(costs['ore_type'])
        log_idx = {'oak': 3, 'willow': 4, 'mahogany': 5, 'magic': 6, 'idea': 7}.get(costs['log_type'])
        bone_idx = {'desiccated': 3, 'regular': 4, 'sturdy': 5, 'reinforced': 6, 'titanium': 7}.get(costs['bone_type'])

        has_res = (
            mining[ore_idx] >= costs['ore_qty'] and
            wood[log_idx] >= costs['log_qty'] and
            fish[bone_idx] >= costs['bone_qty'] and
            gold >= costs['gold']
        )

        desc = (f"**Cost:**\n"
                f"⛏️ {costs['ore_qty']} {costs['ore_type'].title()} Ore ({mining[ore_idx]})\n"
                f"🪓 {costs['log_qty']} {costs['log_type'].title()} Logs ({wood[log_idx]})\n"
                f"🎣 {costs['bone_qty']} {costs['bone_type'].title()} Bones ({fish[bone_idx]})\n"
                f"💰 {costs['gold']:,} Gold ({gold:,})")

        self.costs = costs 
        self.embed = discord.Embed(
            title=f"Forge {self.item.name}",
            description=desc,
            color=discord.Color.green() if has_res else discord.Color.red()
        )
        self.embed.set_thumbnail(url="https://i.imgur.com/k8nPS3E.jpeg")
        self.costs = costs # Store for callback
        
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
        
        # Deduct
        await self.bot.database.skills.update_single_resource(uid, gid, 'mining', self.costs['ore_type'], -self.costs['ore_qty'])
        await self.bot.database.skills.update_single_resource(uid, gid, 'woodcutting', f"{self.costs['log_type']}_logs", -self.costs['log_qty'])
        await self.bot.database.skills.update_single_resource(uid, gid, 'fishing', f"{self.costs['bone_type']}_bones", -self.costs['bone_qty'])
        await self.bot.database.users.modify_gold(uid, -self.costs['gold'])

        # Roll
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
        gold = await self.bot.database.users.get_gold(self.user_id, str(interaction.guild.id))
        
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
        self.embed.set_thumbnail(url="https://i.imgur.com/jgq4aGA.jpeg")
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
        self.embed.set_thumbnail(url="https://i.imgur.com/jgq4aGA.jpeg")
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
        if isinstance(self.item, Accessory):
            cost = EquipmentMechanics.calculate_potential_cost(self.item.passive_lvl)
        else:
            cost = EquipmentMechanics.calculate_ap_cost(self.item.passive_lvl)
            
        gold = await self.bot.database.users.get_gold(self.user_id, str(interaction.guild.id))
        
        max_lvl = 10 if isinstance(self.item, Accessory) else (5 if isinstance(self.item, (Glove, Helmet)) else 6)
        is_capped = self.item.passive_lvl >= max_lvl
        has_attempts = self.item.potential_remaining > 0
        
        success_rate = max(75 - (self.item.passive_lvl * 5), 30)
        
        desc = (f"**Current Level:** {self.item.passive_lvl}/{max_lvl}\n"
                f"**Attempts Left:** {self.item.potential_remaining}\n"
                f"**Success Rate:** {success_rate}%\n"
                f"**Cost:** {cost:,} Gold ({gold:,})")

        self.cost = cost
        self.embed = discord.Embed(title=f"Enchant {self.item.name}", description=desc, color=discord.Color.purple())
        self.embed.set_thumbnail(url="https://i.imgur.com/Tkikr5b.jpeg")
        
        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()
        
        enchant_btn = Button(label="Enchant", style=ButtonStyle.success, disabled=(gold < cost or not has_attempts or is_capped))
        enchant_btn.callback = self.confirm_enchant
        self.add_item(enchant_btn)
        
        self.add_back_button()
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirm_enchant(self, interaction: Interaction):
        await self.bot.database.users.modify_gold(self.user_id, -self.cost)
        
        success = EquipmentMechanics.roll_potential_outcome(self.item.passive_lvl)
        
        itype = 'accessory' if isinstance(self.item, Accessory) else \
                ('glove' if isinstance(self.item, Glove) else \
                ('boot' if isinstance(self.item, Boot) else 'helmet'))

        self.item.potential_remaining -= 1
        await self.bot.database.equipment.update_counter(self.item.item_id, itype, 'potential_remaining', self.item.potential_remaining)

        result_embed = discord.Embed(title="Enchantment Result")
        result_embed.set_thumbnail(url="https://i.imgur.com/83Ahb6w.jpeg")
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

        # --- RESULT UI BUILD ---
        self.clear_items()
        
        max_lvl = 10 if isinstance(self.item, Accessory) else (5 if isinstance(self.item, (Glove, Helmet)) else 6)
        if self.item.potential_remaining > 0 and self.item.passive_lvl < max_lvl:
            again_btn = Button(label="Enchant Again", style=ButtonStyle.success)
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
        mining = await self.bot.database.skills.get_data(uid, gid, 'mining')
        wood = await self.bot.database.skills.get_data(uid, gid, 'woodcutting')
        fish = await self.bot.database.skills.get_data(uid, gid, 'fishing')
        gold = await self.bot.database.users.get_gold(uid, gid)

        ore_idx = {'iron': 3, 'coal': 4, 'gold': 5, 'platinum': 6, 'idea': 7}.get(costs['ore_type'])
        log_idx = {'oak': 3, 'willow': 4, 'mahogany': 5, 'magic': 6, 'idea': 7}.get(costs['log_type'])
        bone_idx = {'desiccated': 3, 'regular': 4, 'sturdy': 5, 'reinforced': 6, 'titanium': 7}.get(costs['bone_type'])

        has_res = (
            mining[ore_idx] >= costs['ore_qty'] and
            wood[log_idx] >= costs['log_qty'] and
            fish[bone_idx] >= costs['bone_qty'] and
            gold >= costs['gold']
        )

        desc = (f"**Temper Cost:**\n"
                f"⛏️ {costs['ore_qty']} {costs['ore_type'].title()} Ore\n"
                f"🪓 {costs['log_qty']} {costs['log_type'].title()} Logs\n"
                f"🎣 {costs['bone_qty']} {costs['bone_type'].title()} Bones\n"
                f"💰 {costs['gold']:,} Gold")

        self.costs = costs
        
        # --- DYNAMIC BUTTON BUILD ---
        self.clear_items()
        
        temper_btn = Button(label="Temper!", style=ButtonStyle.success, disabled=not has_res)
        temper_btn.callback = self.confirm_temper
        self.add_item(temper_btn)
        
        self.add_back_button()
        
        embed = discord.Embed(title="Temper Armor", description=desc, color=discord.Color.blue() if has_res else discord.Color.red())
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def confirm_temper(self, interaction: Interaction):
        uid, gid = self.user_id, str(interaction.guild.id)
        # Deduct
        await self.bot.database.skills.update_single_resource(uid, gid, 'mining', self.costs['ore_type'], -self.costs['ore_qty'])
        await self.bot.database.skills.update_single_resource(uid, gid, 'woodcutting', f"{self.costs['log_type']}_logs", -self.costs['log_qty'])
        await self.bot.database.skills.update_single_resource(uid, gid, 'fishing', f"{self.costs['bone_type']}_bones", -self.costs['bone_qty'])
        await self.bot.database.users.modify_gold(uid, -self.costs['gold'])

        success, stat, amount = EquipmentMechanics.roll_temper_outcome(self.item)
        
        res_embed = discord.Embed(title="Temper Result")
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

        # --- RESULT UI BUILD ---
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
        if random.random() <= 0.5:
            new_p = random.choice(["Invulnerable", "Mystical Might", "Omnipotent", "Treasure Hunter", "Unlimited Wealth", "Everlasting Blessing"])
            self.item.passive = new_p
            await self.bot.database.equipment.update_passive(self.item.item_id, 'armor', new_p)
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