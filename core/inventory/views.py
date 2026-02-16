import discord
from discord import Interaction, ButtonStyle
from discord.ui import View, Button
from typing import List, Any

# Core Imports
from core.models import Weapon, Armor, Accessory, Glove, Boot, Helmet
from core.ui.inventory import InventoryUI
from core.items.equipment_mechanics import EquipmentMechanics
from core.inventory.upgrade_views import ForgeView, RefineView, PotentialView, ShatterView, TemperView, ImbueView, VoidforgeView
from core.companions.mechanics import CompanionMechanics

class InventoryListView(View):
    """
    Generic Pagination View for any list of Equipment.
    """
    def __init__(self, bot, user_id: str, items: List[Any], title_emoji: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.items = items
        self.title_emoji = title_emoji
        
        # Pagination state
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = (len(items) + self.items_per_page - 1) // self.items_per_page
        
        # Equipped ID tracking
        self.equipped_id = next((i.item_id for i in items if i.is_equipped), None)

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        

        # Selection Buttons (1-5)
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        current_batch = self.items[start:end]

        for i, item in enumerate(current_batch):
            btn = Button(label=f"{i+1}", style=ButtonStyle.primary, custom_id=f"select_{i}")
            btn.callback = lambda i_interaction, it=item: self.select_item(i_interaction, it)
            self.add_item(btn)

        # Navigation Buttons
        if self.total_pages > 1:
            prev_btn = Button(label="Prev", custom_id="prev", disabled=(self.current_page == 0))
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)

            next_btn = Button(label="Next", custom_id="next", disabled=(self.current_page == self.total_pages - 1))
            next_btn.callback = self.next_page
            self.add_item(next_btn)

        # 3. Close
        close_btn = Button(label="Close", style=ButtonStyle.danger, custom_id="close")
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    async def get_current_embed(self, user_name: str):
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]
        
        return InventoryUI.get_list_embed(
            user_name, page_items, self.current_page, self.total_pages, 
            self.equipped_id, self.title_emoji
        )

    # --- Callbacks ---
    async def prev_page(self, interaction: Interaction):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        embed = await self.get_current_embed(interaction.user.display_name)
        await interaction.response.edit_message(content=None, embed=embed, view=self)

    async def next_page(self, interaction: Interaction):
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_buttons()
        embed = await self.get_current_embed(interaction.user.display_name)
        await interaction.response.edit_message(content=None, embed=embed, view=self)

    async def select_item(self, interaction: Interaction, item: Any):
        # Transition to Detail View
        detail_view = ItemDetailView(self.bot, self.user_id, item, self)
        await detail_view.fetch_data()
        embed = InventoryUI.get_item_details_embed(item, item.item_id == self.equipped_id)
        await interaction.response.edit_message(content=None, embed=embed, view=detail_view)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
            
        try:
            # We need to fetch the current embed to preserve it, but update the footer
            # Note: View.message is populated if we assigned it in the Cog (standard practice)
            if hasattr(self, 'message') and self.message:
                embed = self.message.embeds[0]
                embed.set_footer(text="Session Timed Out.")
                await self.message.edit(embed=embed, view=self)
        except (discord.NotFound, discord.HTTPException):
            pass


class DiscardConfirmView(View):
    """Simple Yes/No view for deleting valuable items."""
    def __init__(self, origin_view):
        super().__init__(timeout=30)
        self.origin_view = origin_view # Refers to ItemDetailView

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.origin_view.user_id

    @discord.ui.button(label="Discard", style=ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: Button):
        # Call back to the main view to handle logic
        await self.origin_view.finalize_discard(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: Button):
        # Go back to Item Detail View
        embed = InventoryUI.get_item_details_embed(self.origin_view.item, self.origin_view.is_equipped)
        await interaction.response.edit_message(content=None, embed=embed, view=self.origin_view)
        self.stop()


class ItemDetailView(View):
    """
    Handles actions for a specific item. Dynamically generates buttons based on Item Type.
    """
    def __init__(self, bot, user_id: str, item: Any, parent_view: InventoryListView):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.item = item
        self.parent = parent_view # To support "Back" button
        
        self.is_equipped = (item.item_id == parent_view.equipped_id)
        self.void_keys = 0
        

    async def fetch_data(self):
        """Async setup to fetch currency/keys needed for button logic."""
        if isinstance(self.item, Weapon):
            self.void_keys = await self.bot.database.users.get_currency(self.user_id, 'void_keys')
            self.shatter_runes = await self.bot.database.users.get_currency(self.user_id, 'shatter_runes')
        self.setup_buttons()

    def setup_buttons(self):
        # 1. Equip/Unequip
        self.clear_items()

        label = "Unequip" if self.is_equipped else "Equip"
        style = ButtonStyle.primary 
        equip_btn = Button(label=label, style=style)
        equip_btn.callback = self.toggle_equip
        self.add_item(equip_btn)

        # 2. Dynamic Upgrade Actions
        if isinstance(self.item, Weapon):
            if self.item.forges_remaining > 0:
                self.add_upgrade_button("Forge", ButtonStyle.success, "forge")
            self.add_upgrade_button("Refine", ButtonStyle.secondary, "refine")
            
            if self.void_keys > 0 and self.is_equipped and self.item.u_passive == 'none':
                 self.add_upgrade_button("Voidforge", ButtonStyle.primary, "voidforge")
            self.add_upgrade_button("Shatter", ButtonStyle.danger, "shatter")  

        elif isinstance(self.item, Armor):
            if self.item.temper_remaining > 0:
                self.add_upgrade_button("Temper", ButtonStyle.success, "temper")
            if self.item.imbue_remaining > 0 and self.item.passive == "none":
                self.add_upgrade_button("Imbue", ButtonStyle.primary, "imbue")

        elif isinstance(self.item, (Accessory, Glove, Boot, Helmet)):
            max_lvl = 10 if isinstance(self.item, Accessory) else (5 if isinstance(self.item, (Glove, Helmet)) else 6)
            if hasattr(self.item, 'potential_remaining') and self.item.potential_remaining > 0 and self.item.passive_lvl < max_lvl:
                self.add_upgrade_button("Enchant", ButtonStyle.success, "potential")

        # 3. Standard Actions
        discard_btn = Button(label="Discard", style=ButtonStyle.danger)
        discard_btn.callback = self.discard_item
        self.add_item(discard_btn)

        back_btn = Button(label="Back", style=ButtonStyle.secondary)
        back_btn.callback = self.go_back
        self.add_item(back_btn)

    def add_upgrade_button(self, label, style, action_type):
        btn = Button(label=label, style=style)
        # Capture action_type in default arg
        btn.callback = lambda i, at=action_type: self.handle_upgrade(i, at)
        self.add_item(btn)

    async def handle_upgrade(self, interaction: Interaction, action_type: str):
        # We MUST defer here because rendering the new View might involve DB fetches
        # If the view render takes > 3s, the interaction fails otherwise.
        await interaction.response.defer()
        view_map = {
            "forge": ForgeView, "refine": RefineView, "temper": TemperView,
            "imbue": ImbueView, "potential": PotentialView, "voidforge": VoidforgeView,
            "shatter": ShatterView
        }
        
        view_class = view_map.get(action_type)
        if view_class:
            view = view_class(self.bot, self.user_id, self.item, self)
            await view.render(interaction)
        else:
            await interaction.followup.send("Unknown action.", ephemeral=True)

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
            
        try:
            # We need to fetch the current embed to preserve it, but update the footer
            # Note: View.message is populated if we assigned it in the Cog (standard practice)
            if hasattr(self, 'message') and self.message:
                embed = self.message.embeds[0]
                embed.set_footer(text="Session Timed Out.")
                await self.message.edit(embed=embed, view=self)
        except (discord.NotFound, discord.HTTPException):
            pass

    # --- Actions ---

    async def toggle_equip(self, interaction: Interaction):
        itype = self._get_db_type()
        if self.is_equipped:
            await self.bot.database.equipment.unequip(self.user_id, itype)
            self.parent.equipped_id = None
            self.is_equipped = False
        else:
            await self.bot.database.equipment.equip(self.user_id, self.item.item_id, itype)
            self.parent.equipped_id = self.item.item_id
            self.is_equipped = True
        
        await self.fetch_data() # Re-check keys/status for button display
        embed = InventoryUI.get_item_details_embed(self.item, self.is_equipped)
        embed.set_thumbnail(url="https://i.imgur.com/Kr0xq5N.png")
        await interaction.response.edit_message(embed=embed, view=self)

    # --- DISCARD LOGIC ---

    def _is_valuable(self) -> bool:
        """Checks if item has any stats that make it worth confirming before delete."""
        if isinstance(self.item, Weapon):
            # Has passive OR refined
            return (self.item.passive != 'none' and self.item.passive != '') or self.item.refinement_lvl > 0
        
        # General check for other items
        if hasattr(self.item, 'passive') and self.item.passive != 'none' and self.item.passive != '':
            return True
        if hasattr(self.item, 'passive_lvl') and self.item.passive_lvl > 0:
            return True
        
        return False

    async def discard_item(self, interaction: Interaction):
        # 1. Check if valuable
        if self._is_valuable():
            confirm_view = DiscardConfirmView(self)
            await interaction.response.edit_message(
                content="⚠️ **Warning:** This item has passives or upgrades. Are you sure you want to discard it?", 
                embed=None, 
                view=confirm_view
            )
        else:
            # 2. Not valuable, delete immediately
            await self.finalize_discard(interaction)

    async def finalize_discard(self, interaction: Interaction):
        """Performs the actual DB deletion and returns to list."""
        # 1. Defer immediately to prevent timeout errors and allow heavy DB logic
        if not interaction.response.is_done():
            await interaction.response.defer()

        itype = self._get_db_type()

        # --- [FEED LOGIC] ---
        # 1. Get ONLY active companions
        active_rows = await self.bot.database.companions.get_active(self.user_id)
        
        if active_rows:
            # Calculate XP
            total_xp_val = CompanionMechanics.calculate_feed_xp(self.item)
            # Integer division to split evenly
            xp_per_pet = total_xp_val // len(active_rows)
            
            if xp_per_pet > 0:
                leveled_up_names = []
                
                for row in active_rows:
                    # Unpack tuple: id(0), ..., level(5), exp(6)
                    comp_id = row[0]
                    name = row[2]
                    current_lvl = row[5]
                    current_exp = row[6]
                    
                    # Add XP
                    current_exp += xp_per_pet
                    
                    # Handle Level Up Loop
                    did_level = False
                    while current_lvl < 100:
                        req_xp = CompanionMechanics.calculate_next_level_xp(current_lvl)
                        if current_exp >= req_xp:
                            current_exp -= req_xp
                            current_lvl += 1
                            did_level = True
                        else:
                            break
                    
                    # Commit changes
                    await self.bot.database.companions.update_stats(comp_id, current_lvl, current_exp)
                    if did_level:
                        leveled_up_names.append(f"{name} (Lv.{current_lvl})")

                # Feedback
                msg = f"🍖 Fed to pets! +{xp_per_pet} XP each."
                if leveled_up_names:
                    msg += f"\n🎉 **Level Up:** {', '.join(leveled_up_names)}!"
                
                # Now safe to use followup because we deferred
                try: await interaction.followup.send(msg, ephemeral=True)
                except: pass
        # --------------------

        await self.bot.database.equipment.discard(self.item.item_id, itype)
        
        # Remove from parent View's list so it doesn't show up again
        self.parent.items = [i for i in self.parent.items if i.item_id != self.item.item_id]
        
        # Update parent pagination in case we deleted the last item on a page
        self.parent.total_pages = (len(self.parent.items) + self.parent.items_per_page - 1) // self.parent.items_per_page if self.parent.items else 1
        if self.parent.current_page >= self.parent.total_pages:
            self.parent.current_page = max(0, self.parent.total_pages - 1)
            
        self.parent.update_buttons()
        
        embed = await self.parent.get_current_embed(interaction.user.display_name)
        
        # Since we deferred at the start, we MUST use edit_original_response
        await interaction.edit_original_response(content="🗑️ **Item discarded.**", embed=embed, view=self.parent)

    async def go_back(self, interaction: Interaction):
        embed = await self.parent.get_current_embed(interaction.user.display_name)
        await interaction.response.edit_message(embed=embed, view=self.parent)

    def _get_db_type(self) -> str:
        if isinstance(self.item, Weapon): return 'weapon'
        if isinstance(self.item, Armor): return 'armor'
        if isinstance(self.item, Accessory): return 'accessory'
        if isinstance(self.item, Glove): return 'glove'
        if isinstance(self.item, Boot): return 'boot'
        if isinstance(self.item, Helmet): return 'helmet'
        return 'weapon'