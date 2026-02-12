import discord
import random
from discord import Interaction, ButtonStyle, SelectOption
from discord.ui import View, Button, Select
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Weapon, Armor, Accessory, Glove, Boot, Helmet
from core.items.factory import create_weapon

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
        # Try to return to parent view if possible, or just disable
        try:
            await self.parent_view.message.edit(view=self.parent_view)
        except: pass

    async def go_back(self, interaction: Interaction):
        # Return to item details
        from core.ui.inventory import InventoryUI
        embed = InventoryUI.get_item_details_embed(self.item, self.item.item_id == self.parent_view.parent.equipped_id)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
        self.stop()

    @discord.ui.button(label="Back", style=ButtonStyle.secondary, row=4)
    async def back_btn(self, interaction: Interaction, button: Button):
        await self.go_back(interaction)

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

        # Check sufficiency
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
                f"⛏️ {costs['ore_qty']} {costs['ore_type'].title()} Ore ({mining[ore_idx]:,})\n"
                f"🪓 {costs['log_qty']} {costs['log_type'].title()} Logs ({wood[log_idx]:,})\n"
                f"🎣 {costs['bone_qty']} {costs['bone_type'].title()} Bones ({fish[bone_idx]:,})\n"
                f"💰 {costs['gold']:,} Gold ({gold:,})")

        self.embed = discord.Embed(
            title=f"Forge {self.item.name}",
            description=desc,
            color=discord.Color.green() if has_res else discord.Color.red()
        )
        self.costs = costs # Store for callback
        
        # Update Button State
        self.confirm_forge.disabled = not has_res
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label="Forge!", style=ButtonStyle.success)
    async def confirm_forge(self, interaction: Interaction, button: Button):
        uid, gid = self.user_id, str(interaction.guild.id)
        
        # Deduct
        await self.bot.database.skills.update_single_resource(uid, gid, 'mining', self.costs['ore_type'], -self.costs['ore_qty'])
        await self.bot.database.skills.update_single_resource(uid, gid, 'woodcutting', f"{self.costs['log_type']}_logs", -self.costs['log_qty'])
        await self.bot.database.skills.update_single_resource(uid, gid, 'fishing', f"{self.costs['bone_type']}_bones", -self.costs['bone_qty'])
        await self.bot.database.users.modify_gold(uid, -self.costs['gold'])

        # Roll
        success, new_passive = EquipmentMechanics.roll_forge_outcome(self.item)
        
        # Update Object & DB
        self.item.forges_remaining -= 1
        await self.bot.database.equipment.update_counter(self.item.item_id, 'weapon', 'forges_remaining', self.item.forges_remaining)
        
        result_embed = discord.Embed(title="Forge Result")
        if success:
            self.item.passive = new_passive
            await self.bot.database.equipment.update_passive(self.item.item_id, 'weapon', new_passive)
            result_embed.description = f"🔥 Success! Passive is now **{new_passive.title()}**!"
            result_embed.color = discord.Color.gold()
        else:
            result_embed.description = "💨 The magic fizzled out. Resources consumed."
            result_embed.color = discord.Color.dark_grey()

        await interaction.response.edit_message(embed=result_embed, view=self)
        
        # If possible to forge again, re-render after short delay? 
        # For simplicity, we stay on result screen or go back. User can click Back.
        # But to allow chain forging, we call render again if forges > 0
        if self.item.forges_remaining > 0:
            await self.render(interaction) 
        else:
            # Refresh parent view item data
            self.confirm_forge.disabled = True
            await interaction.edit_original_response(embed=result_embed, view=self)


class RefineView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        cost = EquipmentMechanics.calculate_refine_cost(self.item)
        gold = await self.bot.database.users.get_gold(self.user_id, str(interaction.guild.id))
        
        has_funds = gold >= cost
        has_refines = self.item.refines_remaining > 0
        
        # Check Runes if no refines left
        runes = 0
        if not has_refines:
            runes = await self.bot.database.users.get_currency(self.user_id, 'refinement_runes')

        desc = (f"**Refines Remaining:** {self.item.refines_remaining}\n"
                f"**Refinement Level:** +{self.item.refinement_lvl}\n"
                f"**Cost:** {cost:,} Gold ({gold:,})\n")
        
        if not has_refines:
            desc += f"\n**0 Refines left!** Use a Rune? (Owned: {runes})"
            self.confirm_refine.label = "Use Rune"
            self.confirm_refine.style = ButtonStyle.primary
            self.confirm_refine.disabled = (runes == 0)
        else:
            self.confirm_refine.label = "Refine"
            self.confirm_refine.style = ButtonStyle.success
            self.confirm_refine.disabled = not has_funds

        self.embed = discord.Embed(title=f"Refine {self.item.name}", description=desc, color=discord.Color.blue())
        self.cost = cost
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label="Refine", style=ButtonStyle.success)
    async def confirm_refine(self, interaction: Interaction, button: Button):
        # Rune Logic
        if self.item.refines_remaining <= 0:
            await self.bot.database.users.modify_currency(self.user_id, 'refinement_runes', -1)
            await self.bot.database.equipment.update_counter(self.item.item_id, 'weapon', 'refines_remaining', 1)
            self.item.refines_remaining += 1
            await self.render(interaction)
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

        # Show interim result
        res_str = ", ".join([f"+{v} {k.title()}" for k,v in stats.items() if v > 0]) or "No stats gained."
        self.embed.add_field(name="Result", value=res_str)
        
        await self.render(interaction)


class PotentialView(BaseUpgradeView):
    """Handles Potential/Enchanting for Accessories, Gloves, Boots, Helmets."""
    def __init__(self, bot, user_id, item, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        # Determine cost function based on item type
        if isinstance(self.item, Accessory):
            cost = EquipmentMechanics.calculate_potential_cost(self.item.passive_lvl)
        else:
            cost = EquipmentMechanics.calculate_ap_cost(self.item.passive_lvl)
            
        gold = await self.bot.database.users.get_gold(self.user_id, str(interaction.guild.id))
        
        # Cap logic
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
        
        self.confirm_btn.disabled = (gold < cost or not has_attempts or is_capped)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label="Enchant", style=ButtonStyle.success)
    async def confirm_btn(self, interaction: Interaction, button: Button):
        await self.bot.database.users.modify_gold(self.user_id, -self.cost)
        
        success = EquipmentMechanics.roll_potential_outcome(self.item.passive_lvl)
        
        # Determine Item Type String for DB calls
        itype = 'accessory' if isinstance(self.item, Accessory) else \
                ('glove' if isinstance(self.item, Glove) else \
                ('boot' if isinstance(self.item, Boot) else 'helmet'))

        self.item.potential_remaining -= 1
        await self.bot.database.equipment.update_counter(self.item.item_id, itype, 'potential_remaining', self.item.potential_remaining)

        result_msg = "Enchantment Failed."
        if success:
            if self.item.passive == "none":
                new_p = EquipmentMechanics.get_new_passive(itype)
                self.item.passive = new_p
                self.item.passive_lvl = 1
                await self.bot.database.equipment.update_passive(self.item.item_id, itype, new_p)
                await self.bot.database.equipment.update_counter(self.item.item_id, itype, 'passive_lvl', 1)
                result_msg = f"Unlocked **{new_p}**!"
            else:
                self.item.passive_lvl += 1
                await self.bot.database.equipment.update_counter(self.item.item_id, itype, 'passive_lvl', self.item.passive_lvl)
                result_msg = f"Upgraded to Level **{self.item.passive_lvl}**!"

        self.embed.add_field(name="Result", value=result_msg)
        await self.render(interaction)

class ShatterView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        
    async def render(self, interaction: Interaction):
        runes_back = max(0, int(self.item.refinement_lvl - 5 * 0.8))
        if self.item.attack > 0 and self.item.defence > 0 and self.item.rarity > 0:
            runes_back += 1
            
        embed = discord.Embed(
            title="Shatter Weapon",
            description=f"Destroy **{self.item.name}**?\nReturns: **{runes_back}** Refinement Runes.\nCost: 1 Shatter Rune.",
            color=discord.Color.dark_red()
        )
        self.runes_back = runes_back
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="CONFIRM SHATTER", style=ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: Button):
        await self.bot.database.equipment.discard(self.item.item_id, 'weapon')
        await self.bot.database.users.modify_currency(self.user_id, 'refinement_runes', self.runes_back)
        await self.bot.database.users.modify_currency(self.user_id, 'shatter_runes', -1)
        
        await interaction.response.edit_message(content=f"Shattered! Gained {self.runes_back} runes.", embed=None, view=None)
        
        # Remove item from parent view list
        self.parent_view.parent.items = [i for i in self.parent_view.parent.items if i.item_id != self.item.item_id]
        self.parent_view.parent.update_buttons()
        self.stop()


class BaseUpgradeView(View):
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
        # Refresh parent data if needed
        await self.parent_view.fetch_data() 
        from core.ui.inventory import InventoryUI
        embed = InventoryUI.get_item_details_embed(self.item, self.item.item_id == self.parent_view.parent.equipped_id)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
        self.stop()

    @discord.ui.button(label="Back", style=ButtonStyle.secondary, row=4)
    async def back_btn(self, interaction: Interaction, button: Button):
        await self.go_back(interaction)

# --- ARMOR VIEWS ---

class TemperView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Armor, parent_view):
        super().__init__(bot, user_id, item, parent_view)

    async def render(self, interaction: Interaction):
        costs = EquipmentMechanics.calculate_temper_cost(self.item)
        if not costs: return await interaction.response.send_message("No tempers remaining.", ephemeral=True)

        # Resource Checks (Copy logic from ForgeView or abstract it)
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
        self.confirm_temper.disabled = not has_res
        
        embed = discord.Embed(title="Temper Armor", description=desc, color=discord.Color.blue() if has_res else discord.Color.red())
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Temper!", style=ButtonStyle.success)
    async def confirm_temper(self, interaction: Interaction, button: Button):
        uid, gid = self.user_id, str(interaction.guild.id)
        # Deduct
        await self.bot.database.skills.update_single_resource(uid, gid, 'mining', self.costs['ore_type'], -self.costs['ore_qty'])
        await self.bot.database.skills.update_single_resource(uid, gid, 'woodcutting', f"{self.costs['log_type']}_logs", -self.costs['log_qty'])
        await self.bot.database.skills.update_single_resource(uid, gid, 'fishing', f"{self.costs['bone_type']}_bones", -self.costs['bone_qty'])
        await self.bot.database.users.modify_gold(uid, -self.costs['gold'])

        success, stat, amount = EquipmentMechanics.roll_temper_outcome(self.item)
        
        self.item.temper_remaining -= 1
        await self.bot.database.equipment.update_counter(self.item.item_id, 'armor', 'temper_remaining', self.item.temper_remaining)

        res_embed = discord.Embed(title="Temper Result")
        if success:
            await self.bot.database.equipment.increase_stat(self.item.item_id, 'armor', stat, amount)
            # Update object
            if stat == 'pdr': self.item.pdr += amount
            elif stat == 'fdr': self.item.fdr += amount
            
            res_embed.color = discord.Color.green()
            res_embed.description = f"Success! Increased **{stat.upper()}** by **{amount}**."
        else:
            res_embed.color = discord.Color.dark_grey()
            res_embed.description = "Temper failed. Materials consumed."

        await interaction.response.edit_message(embed=res_embed, view=self)
        if self.item.temper_remaining > 0:
            await self.render(interaction)
        else:
            self.confirm_temper.disabled = True
            await interaction.edit_original_response(embed=res_embed, view=self)


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
        self.confirm.disabled = (runes == 0)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Imbue", style=ButtonStyle.primary)
    async def confirm(self, interaction: Interaction, button: Button):
        await self.bot.database.users.modify_currency(self.user_id, 'imbue_runes', -1)
        
        # Remove imbue slot regardless of outcome
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

        self.confirm.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)


# --- VOIDFORGE VIEW ---

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
        
        # Replace items with just the select and back button
        self.clear_items()
        self.add_item(select)
        self.add_item(self.back_btn)

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
        # User selected an item
        target_id = int(interaction.data['values'][0])
        target = next((w for w in self.candidates if w.item_id == target_id), None)
        
        if not target: return

        # Consume Cost
        await self.bot.database.users.modify_currency(self.user_id, 'void_keys', -1)
        await self.bot.database.equipment.discard(target.item_id, 'weapon')

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
            
            res_txt = f"🌌 **Success!** {target.passive.title()} added as {slot.replace('_', ' ').title()}."
            color = discord.Color.purple()
            
        elif roll < 0.50:
            # Overwrite main
            await self.bot.database.equipment.update_passive(self.item.item_id, 'weapon', target.passive)
            self.item.passive = target.passive
            res_txt = f"🔄 **Chaos!** Main passive overwritten with {target.passive.title()}."
            color = discord.Color.orange()
        else:
            res_txt = "❌ **Failure.** The essence dissipated."

        embed = discord.Embed(title="Voidforge Result", description=res_txt, color=color)
        
        # Remove buttons, show result
        self.clear_items()
        self.add_item(self.back_btn)
        
        await interaction.response.edit_message(embed=embed, view=self)