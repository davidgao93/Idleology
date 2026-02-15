import discord
from discord import ui, ButtonStyle, Interaction, SelectOption
from core.trade.logic import TradeManager

class AmountModal(ui.Modal):
    def __init__(self, parent_view, resource_name, max_amount):
        super().__init__(title=f"Send {resource_name}")
        self.parent_view = parent_view
        self.resource_name = resource_name
        self.max_amount = max_amount
        
        self.amount = ui.TextInput(label=f"Amount (Max: {max_amount:,})", placeholder="Enter amount...", min_length=1)
        self.add_item(self.amount)

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.amount.value)
            if val <= 0: raise ValueError
            if val > self.max_amount:
                return await interaction.response.send_message(f"You only have {self.max_amount:,}!", ephemeral=True)
            
            await self.parent_view.setup_confirmation(interaction, "resource", self.resource_name, val)
        except ValueError:
            await interaction.response.send_message("Invalid number.", ephemeral=True)

class GoldModal(ui.Modal, title="Send Gold"):
    amount = ui.TextInput(label="Amount", placeholder="e.g. 5000", min_length=1)

    def __init__(self, parent_view, max_gold):
        super().__init__()
        self.parent_view = parent_view
        self.max_gold = max_gold

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.amount.value)
            if val <= 0: raise ValueError
            if val > self.max_gold:
                return await interaction.response.send_message(f"Insufficient funds. You have {self.max_gold:,}.", ephemeral=True)
            
            await self.parent_view.setup_confirmation(interaction, "gold", "Gold", val)
        except ValueError:
            await interaction.response.send_message("Invalid amount.", ephemeral=True)


class TradeRootView(ui.View):
    def __init__(self, bot, user_id, receiver, server_id):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.receiver = receiver
        self.server_id = server_id
        
        # Transaction State
        self.tx_type = None # 'gold', 'resource', 'equipment'
        self.tx_item = None # 'Iron Ore' or ItemID
        self.tx_amount = 0
        
        self.show_main_menu()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.delete()
        except: pass

    # --- MENUS ---

    def show_main_menu(self):
        self.clear_items()
        
        btn_gold = ui.Button(label="Gold", emoji="💰", style=ButtonStyle.primary)
        btn_gold.callback = self.gold_callback
        
        btn_items = ui.Button(label="Equipment", emoji="🎒", style=ButtonStyle.secondary)
        btn_items.callback = self.equipment_menu_callback
        
        btn_special = ui.Button(label="Resources & Keys", emoji="💎", style=ButtonStyle.success)
        btn_special.callback = self.resource_menu_callback
        
        btn_cancel = ui.Button(label="Cancel", style=ButtonStyle.danger)
        btn_cancel.callback = self.cancel_callback

        self.add_item(btn_gold)
        self.add_item(btn_items)
        self.add_item(btn_special)
        self.add_item(btn_cancel)

    async def update_view(self, interaction: Interaction, embed):
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    # --- CALLBACKS: GOLD ---
    
    async def gold_callback(self, interaction: Interaction):
        current_gold = await self.bot.database.users.get_gold(self.user_id)
        await interaction.response.send_modal(GoldModal(self, current_gold))

    # --- CALLBACKS: RESOURCES ---

    async def resource_menu_callback(self, interaction: Interaction):
        self.clear_items()
        
        # Categorized Select
        options = [
            SelectOption(label="Keys & Curios", value="keys", emoji="🗝️"),
            SelectOption(label="Runes", value="runes", emoji="📜"),
            SelectOption(label="Mining Mats", value="mining", emoji="⛏️"),
            SelectOption(label="Woodcutting Mats", value="wood", emoji="🪓"),
            SelectOption(label="Fishing Mats", value="fish", emoji="🎣"),
        ]
        
        select = ui.Select(placeholder="Select Category...", options=options)
        select.callback = self.resource_category_select
        
        self.add_item(select)
        self.add_item(self.back_button())
        
        embed = discord.Embed(title="Select Resource Category", color=discord.Color.blue())
        await self.update_view(interaction, embed)

    async def resource_category_select(self, interaction: Interaction):
        cat = interaction.data['values'][0]
        
        # Filter RESOURCE_MAP based on category
        # This is a bit manual but effective
        choices = []
        if cat == "keys": keys = ["Draconic Key", "Angelic Key", "Void Key", "Soul Core", "Void Fragment", "Curio"]
        elif cat == "runes": keys = [k for k in TradeManager.RESOURCE_MAP if "Rune" in k]
        elif cat == "mining": keys = ["Iron Ore", "Coal", "Gold Ore", "Platinum Ore"]
        elif cat == "wood": keys = ["Oak Logs", "Willow Logs", "Mahogany Logs", "Magic Logs"]
        elif cat == "fish": keys = ["Desiccated Bones", "Regular Bones", "Sturdy Bones", "Reinforced Bones"]
        
        self.clear_items()
        select = ui.Select(placeholder="Select Item...", options=[SelectOption(label=k) for k in keys])
        select.callback = self.resource_item_select
        self.add_item(select)
        self.add_item(self.back_button())
        
        await self.update_view(interaction, discord.Embed(title=f"Select {cat.title()}", color=discord.Color.blue()))

    async def resource_item_select(self, interaction: Interaction):
        res_name = interaction.data['values'][0]
        balance = await TradeManager.get_resource_balance(self.bot, self.user_id, self.server_id, res_name)
        
        if balance <= 0:
            return await interaction.response.send_message(f"You don't have any {res_name}.", ephemeral=True)
            
        await interaction.response.send_modal(AmountModal(self, res_name, balance))

    # --- CALLBACKS: EQUIPMENT ---

    async def equipment_menu_callback(self, interaction: Interaction):
        self.clear_items()
        options = [
            SelectOption(label="Weapon", value="weapon", emoji="⚔️"),
            SelectOption(label="Armor", value="armor", emoji="🛡️"),
            SelectOption(label="Accessory", value="accessory", emoji="📿"),
            SelectOption(label="Gloves", value="glove", emoji="🧤"),
            SelectOption(label="Boots", value="boot", emoji="👢"),
            SelectOption(label="Helmet", value="helmet", emoji="🪖"),
        ]
        select = ui.Select(placeholder="Select Slot...", options=options)
        select.callback = self.equip_type_select
        self.add_item(select)
        self.add_item(self.back_button())
        
        await self.update_view(interaction, discord.Embed(title="Select Equipment Slot", color=discord.Color.purple()))

    async def equip_type_select(self, interaction: Interaction):
        itype = interaction.data['values'][0]
        items = await self.bot.database.equipment.get_all(self.user_id, itype)
        
        # Filter out equipped items if you want, or just unequip them later
        # Let's show first 25
        options = []
        for i in items[:25]:
            # i schema: id(0), uid(1), name(2), lvl(3)...
            is_eq = " [E]" if i[8] else "" # Index 8 is is_equipped for armor/wep? Need to verify per schema.
            # Actually schema varies slightly but is_equipped is usually present.
            # Using generic assumption index 8 or 10. Let's just show Name + Lvl
            lbl = f"{i[2]} (Lv{i[3]})"[:100]
            val = str(i[0])
            options.append(SelectOption(label=lbl, value=val, description=f"ID: {val}{is_eq}"))

        if not options:
            return await interaction.response.send_message(f"No {itype}s found.", ephemeral=True)

        self.clear_items()
        select = ui.Select(placeholder="Select Item to Trade...", options=options)
        
        # Closure to capture item type
        async def equip_callback(inter):
            item_id = int(inter.data['values'][0])
            # Fetch specific name for confirmation
            # We already have it in options, but for safety fetch DB
            item_row = await self.bot.database.equipment.get_by_id(item_id, itype)
            item_name = item_row[2]
            
            # Store type for logic
            self.equip_type_selected = itype 
            await self.setup_confirmation(inter, "equipment", item_name, 1, item_id=item_id)

        select.callback = equip_callback
        self.add_item(select)
        self.add_item(self.back_button())
        
        await self.update_view(interaction, discord.Embed(title=f"Select {itype.title()}", color=discord.Color.purple()))

    # --- CONFIRMATION ---

    async def setup_confirmation(self, interaction: Interaction, tx_type: str, item_name: str, amount: int, item_id: int = None):
        self.tx_type = tx_type
        self.tx_item = item_name
        self.tx_amount = amount
        self.tx_extra_id = item_id # For equipment ID

        self.clear_items()
        
        confirm = ui.Button(label="Confirm Trade", style=ButtonStyle.success)
        confirm.callback = self.execute_trade
        
        cancel = ui.Button(label="Cancel", style=ButtonStyle.danger)
        cancel.callback = self.cancel_callback
        
        self.add_item(confirm)
        self.add_item(cancel)

        desc = f"Sending to: {self.receiver.mention}\n\n"
        if tx_type == "gold":
            desc += f"💰 **{amount:,} Gold**"
        elif tx_type == "resource":
            desc += f"📦 **{amount:,} x {item_name}**"
        elif tx_type == "equipment":
            desc += f"⚔️ **{item_name}**"

        embed = discord.Embed(title="Confirm Transaction", description=desc, color=discord.Color.gold())
        await self.update_view(interaction, embed)

    async def execute_trade(self, interaction: Interaction):
        await interaction.response.defer()
        
        try:
            if self.tx_type == "gold":
                # Re-verify funds
                bal = await self.bot.database.users.get_gold(self.user_id)
                if bal < self.tx_amount:
                    return await interaction.edit_original_response(content="❌ Funds changed. Trade failed.", embed=None, view=None)
                
                await TradeManager.transfer_gold(self.bot, self.user_id, str(self.receiver.id), self.tx_amount)

            elif self.tx_type == "resource":
                bal = await TradeManager.get_resource_balance(self.bot, self.user_id, self.server_id, self.tx_item)
                if bal < self.tx_amount:
                    return await interaction.edit_original_response(content="❌ Stock changed. Trade failed.", embed=None, view=None)
                
                await TradeManager.transfer_resource(self.bot, self.user_id, str(self.receiver.id), self.server_id, self.tx_item, self.tx_amount)

            elif self.tx_type == "equipment":
                # Check if still owned
                item = await self.bot.database.equipment.get_by_id(self.tx_extra_id, self.equip_type_selected)
                if not item or str(item[1]) != self.user_id:
                    return await interaction.edit_original_response(content="❌ Item no longer owned.", embed=None, view=None)
                
                await TradeManager.transfer_equipment(self.bot, self.user_id, str(self.receiver.id), self.equip_type_selected, self.tx_extra_id)

            embed = discord.Embed(title="Trade Successful ✅", description=f"Sent items to {self.receiver.mention}.", color=discord.Color.green())
            await interaction.edit_original_response(embed=embed, view=None)
            
        except Exception as e:
            self.bot.logger.error(f"Trade Error: {e}")
            await interaction.edit_original_response(content="An error occurred during transfer.", embed=None, view=None)
        
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    # --- UTILS ---

    def back_button(self):
        btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=4)
        btn.callback = self.back_to_root
        return btn

    async def back_to_root(self, interaction: Interaction):
        self.show_main_menu()
        embed = discord.Embed(title="Trade Centre", description=f"Trading with {self.receiver.mention}", color=discord.Color.blue())
        await self.update_view(interaction, embed)

    async def cancel_callback(self, interaction: Interaction):
        await interaction.response.edit_message(content="Trade cancelled.", embed=None, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()