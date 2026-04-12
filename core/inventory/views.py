import discord
from discord import Interaction, ButtonStyle
from discord.ui import View, Button
from typing import List, Any
import asyncio

# Core Imports
from core.models import Weapon, Armor, Accessory, Glove, Boot, Helmet
from core.ui.inventory import InventoryUI
from core.items.equipment_mechanics import EquipmentMechanics
from core.inventory.upgrade_views import ForgeView, RefineView, PotentialView, ShatterView, TemperView, ImbueView, VoidforgeView, EngramView, InfernalEngramView, VoidEngramView
from core.companions.mechanics import CompanionMechanics
from core.items.factory import create_weapon, create_armor, create_accessory, create_glove, create_boot, create_helmet

SLOT_CONFIG = {
    "weapon":    {"emoji": "⚔️",  "label": "Weapon",    "factory": create_weapon},
    "armor":     {"emoji": "🛡️",  "label": "Armor",     "factory": create_armor},
    "helmet":    {"emoji": "🪖",  "label": "Helmet",    "factory": create_helmet},
    "glove":     {"emoji": "🧤",  "label": "Glove",     "factory": create_glove},
    "boot":      {"emoji": "👢",  "label": "Boot",      "factory": create_boot},
    "accessory": {"emoji": "📿",  "label": "Accessory", "factory": create_accessory},
}
SLOT_ORDER = ["weapon", "armor", "helmet", "glove", "boot", "accessory"]

class MassDiscardModal(discord.ui.Modal, title="Mass Discard"):
    level_input = discord.ui.TextInput(
        label="Max Item Level to Discard",
        placeholder="e.g. 50 (Discards <= 50)",
        min_length=1,
        max_length=3
    )
    
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
        
    async def on_submit(self, interaction: Interaction):
        try:
            level_limit = int(self.level_input.value)
        except ValueError:
            return await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            
        # Filter logic: Must not be equipped, must be <= requested level
        items_to_delete = [
            item for item in self.parent_view.items 
            if not getattr(item, 'is_equipped', False) and item.level <= level_limit
        ]
        
        if not items_to_delete:
            return await interaction.response.send_message(f"No unequipped items found at or below level {level_limit}.", ephemeral=True)
            
        await interaction.response.defer()
        
        itype = self.parent_view._get_db_type()
        total_xp_val = 0
        
        # Execute DB Deletions
        for item in items_to_delete:
            total_xp_val += CompanionMechanics.calculate_feed_xp(item)
            await self.parent_view.bot.database.equipment.discard(item.item_id, itype)
            
        # Distribute XP
        xp_msg = ""
        active_rows = await self.parent_view.bot.database.companions.get_active(self.parent_view.user_id)
        
        if active_rows and total_xp_val > 0:
            xp_per_pet = total_xp_val // len(active_rows)
            if xp_per_pet > 0:
                leveled_up_names = []
                for row in active_rows:
                    comp_id, name, current_lvl, current_exp = row[0], row[2], row[5], row[6]
                    current_exp += xp_per_pet
                    
                    did_level = False
                    while current_lvl < 100: # 100 is max level
                        req_xp = CompanionMechanics.calculate_next_level_xp(current_lvl)
                        if current_exp >= req_xp:
                            current_exp -= req_xp
                            current_lvl += 1
                            did_level = True
                        else:
                            break
                            
                    await self.parent_view.bot.database.companions.update_stats(comp_id, current_lvl, current_exp)
                    if did_level:
                        leveled_up_names.append(f"{name} (Lv.{current_lvl})")
                        
                xp_msg = f"\n🐾 Active pets gained **{xp_per_pet:,} XP** each."
                if leveled_up_names:
                    xp_msg += f"\n🎉 **Level Up:** {', '.join(leveled_up_names)}"
        
        # Update List State
        deleted_ids = {i.item_id for i in items_to_delete}
        self.parent_view.items = [i for i in self.parent_view.items if i.item_id not in deleted_ids]
        
        # Recalculate pages
        self.parent_view.total_pages = max(1, (len(self.parent_view.items) + self.parent_view.items_per_page - 1) // self.parent_view.items_per_page)
        if self.parent_view.current_page >= self.parent_view.total_pages:
            self.parent_view.current_page = max(0, self.parent_view.total_pages - 1)
            
        self.parent_view.update_buttons()
        
        # Show temporary popup
        temp_embed = discord.Embed(title="Mass Discard Complete", color=discord.Color.red())
        temp_embed.description = f"🗑️ Dismantled **{len(items_to_delete)}** items (Level <= {level_limit}).{xp_msg}"
        
        await interaction.edit_original_response(content=None, embed=temp_embed, view=None)
        
        await asyncio.sleep(1.5)
        
        # Revert to List View
        list_embed = await self.parent_view.get_current_embed(interaction.user.display_name)
        await interaction.edit_original_response(embed=list_embed, view=self.parent_view)


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
        if self.total_pages == 0: self.total_pages = 1
        
        # Equipped ID tracking
        self.equipped_id = next((i.item_id for i in items if getattr(i, 'is_equipped', False)), None)

        self.update_buttons()

    def _get_db_type(self) -> str:
        """Helper to determine the item type currently being displayed."""
        if not self.items: return 'weapon'
        item = self.items[0]
        if isinstance(item, Weapon): return 'weapon'
        if isinstance(item, Armor): return 'armor'
        if isinstance(item, Accessory): return 'accessory'
        if isinstance(item, Glove): return 'glove'
        if isinstance(item, Boot): return 'boot'
        if isinstance(item, Helmet): return 'helmet'
        return 'weapon'

    def update_buttons(self):
        self.clear_items()

        # Selection Buttons (1-5) Row 0
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        current_batch = self.items[start:end]

        for i, item in enumerate(current_batch):
            btn = Button(label=f"{i+1}", style=ButtonStyle.primary, custom_id=f"select_{i}", row=0)
            btn.callback = lambda i_interaction, it=item: self.select_item(i_interaction, it)
            self.add_item(btn)

        # Navigation Buttons (Row 1)
        if self.total_pages > 1:
            prev_btn = Button(label="Prev", custom_id="prev", disabled=(self.current_page == 0), row=1)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)

            next_btn = Button(label="Next", custom_id="next", disabled=(self.current_page == self.total_pages - 1), row=1)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

        # Bottom Controls (Row 2)
        mass_btn = Button(label="Mass Discard", style=ButtonStyle.danger, custom_id="mass_discard", emoji="🗑️", row=2)
        mass_btn.disabled = len(self.items) == 0
        mass_btn.callback = self.mass_discard_callback
        self.add_item(mass_btn)

        close_btn = Button(label="Close", style=ButtonStyle.secondary, custom_id="close", row=2)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    async def mass_discard_callback(self, interaction: Interaction):
        await interaction.response.send_modal(MassDiscardModal(self))

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

            if self.void_keys > 0 and self.item.passive != 'none' and self.item.u_passive == 'none':
                self.add_upgrade_button("Voidforge", ButtonStyle.primary, "voidforge")
            self.add_upgrade_button("Infernal Engram", ButtonStyle.danger, "infernal_engram")
            self.add_upgrade_button("Shatter", ButtonStyle.danger, "shatter")

        elif isinstance(self.item, Armor):
            if self.item.temper_remaining > 0:
                self.add_upgrade_button("Temper", ButtonStyle.success, "temper")
            if self.item.imbue_remaining > 0 and self.item.passive == "none":
                self.add_upgrade_button("Imbue", ButtonStyle.primary, "imbue")
            self.add_upgrade_button("Engram", ButtonStyle.danger, "engram")

        elif isinstance(self.item, (Accessory, Glove, Boot, Helmet)):
            max_lvl = 10 if isinstance(self.item, Accessory) else (5 if isinstance(self.item, (Glove, Helmet)) else 6)
            if hasattr(self.item, 'potential_remaining') and self.item.potential_remaining > 0 and self.item.passive_lvl < max_lvl:
                self.add_upgrade_button("Enchant", ButtonStyle.success, "potential")
            if isinstance(self.item, Accessory):
                self.add_upgrade_button("Void Engram", ButtonStyle.secondary, "void_engram")

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
            "shatter": ShatterView, "engram": EngramView,
            "infernal_engram": InfernalEngramView,
            "void_engram": VoidEngramView,
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
        """Performs the actual DB deletion and returns to list via a brief flash."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        itype = self._get_db_type()

        # --- [FEED LOGIC] ---
        active_rows = await self.bot.database.companions.get_active(self.user_id)
        xp_msg = ""
        
        if active_rows:
            total_xp_val = CompanionMechanics.calculate_feed_xp(self.item)
            xp_per_pet = total_xp_val // len(active_rows)
            
            if xp_per_pet > 0:
                leveled_up_names = []
                for row in active_rows:
                    comp_id = row[0]
                    name = row[2]
                    current_lvl = row[5]
                    current_exp = row[6]
                    
                    current_exp += xp_per_pet
                    did_level = False
                    while current_lvl < 100:
                        req_xp = CompanionMechanics.calculate_next_level_xp(current_lvl)
                        if current_exp >= req_xp:
                            current_exp -= req_xp
                            current_lvl += 1
                            did_level = True
                        else:
                            break
                            
                    await self.bot.database.companions.update_stats(comp_id, current_lvl, current_exp)
                    if did_level:
                        leveled_up_names.append(f"{name} (Lv.{current_lvl})")

                xp_msg = f"\n🐾 Active pets gained **{xp_per_pet:,} XP** each."
                if leveled_up_names:
                    xp_msg += f"\n🎉 **Level Up:** {', '.join(leveled_up_names)}"
        
        # Discard DB
        await self.bot.database.equipment.discard(self.item.item_id, itype)
        
        # Update List State
        self.parent.items = [i for i in self.parent.items if i.item_id != self.item.item_id]
        self.parent.total_pages = max(1, (len(self.parent.items) + self.parent.items_per_page - 1) // self.parent.items_per_page)
        if self.parent.current_page >= self.parent.total_pages:
            self.parent.current_page = max(0, self.parent.total_pages - 1)
        self.parent.update_buttons()
        
        # Brief Popup (Replaces the annoying ephemeral followup)
        temp_embed = discord.Embed(title="Item Discarded", color=discord.Color.red())
        temp_embed.description = f"🗑️ **{self.item.name}** was dismantled.{xp_msg}"
        
        await interaction.edit_original_response(content=None, embed=temp_embed, view=None)
        await asyncio.sleep(1.0) # Wait 1.5s
        
        # Return to List View
        embed = await self.parent.get_current_embed(interaction.user.display_name)
        await interaction.edit_original_response(embed=embed, view=self.parent)

    async def go_back(self, interaction: Interaction):
        self.parent.update_buttons()
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


# ---------------------------------------------------------------------------
# GearView — unified multi-slot inventory view
# ---------------------------------------------------------------------------

class GearView(View):
    """
    Unified gear management view. Shows all six equipment slots via tab buttons
    and uses a Select menu (up to 25 items per page) instead of number buttons.

    Exposes the same interface as InventoryListView so that ItemDetailView,
    MassDiscardModal, and all upgrade views work without modification:
      .equipped_id          (property — per active slot)
      .items                (property — list for active slot)
      .items_per_page       (property — always 25)
      .total_pages          (property — computed)
      .update_buttons()     (alias for update_components)
      .get_current_embed()  (alias for build_embed)
      ._get_db_type()
    """

    def __init__(self, bot, user_id: str, all_items: dict, initial_slot: str = "weapon"):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.all_items = all_items          # dict[slot -> List[item model]]
        self.active_slot = initial_slot
        self.current_page = 0

        # Per-slot equipped IDs — source of truth; updated by ItemDetailView.toggle_equip
        self.equipped_ids: dict = {
            slot: self._scan_equipped_id(slot) for slot in SLOT_ORDER
        }

        self.update_components()

    # ------------------------------------------------------------------
    # Adapter interface for ItemDetailView / MassDiscardModal compatibility
    # ------------------------------------------------------------------

    @property
    def equipped_id(self):
        return self.equipped_ids.get(self.active_slot)

    @equipped_id.setter
    def equipped_id(self, value):
        self.equipped_ids[self.active_slot] = value

    @property
    def items(self):
        return self.all_items[self.active_slot]

    @items.setter
    def items(self, value):
        self.all_items[self.active_slot] = value

    @property
    def items_per_page(self):
        return 25

    @property
    def total_pages(self):
        return self._get_total_pages()

    @total_pages.setter
    def total_pages(self, value):
        pass  # Computed dynamically; writes from MassDiscardModal are no-ops

    def update_buttons(self):
        """Alias used by ItemDetailView and MassDiscardModal."""
        self.update_components()

    async def get_current_embed(self, user_name: str) -> discord.Embed:
        """Alias used by ItemDetailView.go_back."""
        return self.build_embed(user_name)

    def _get_db_type(self) -> str:
        """Alias used by MassDiscardModal."""
        return self.active_slot

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_equipped_id(self, slot: str):
        for item in self.all_items.get(slot, []):
            if getattr(item, 'is_equipped', False):
                return item.item_id
        return None

    def _get_total_pages(self) -> int:
        count = len(self.all_items.get(self.active_slot, []))
        return max(1, (count + 24) // 25)

    def _find_item_by_id(self, item_id: int):
        for item in self.all_items.get(self.active_slot, []):
            if item.item_id == item_id:
                return item
        return None

    @staticmethod
    def _build_select_description(item) -> str:
        """One-line stat summary for the Select option description (max 100 chars)."""
        parts = []
        if getattr(item, 'attack', 0) > 0:   parts.append(f"ATK:{item.attack}")
        if getattr(item, 'defence', 0) > 0:  parts.append(f"DEF:{item.defence}")
        if getattr(item, 'rarity', 0) > 0:   parts.append(f"Rar:{item.rarity}%")
        if getattr(item, 'ward', 0) > 0:     parts.append(f"Ward:{item.ward}%")
        if getattr(item, 'crit', 0) > 0:     parts.append(f"Crit:{item.crit}")
        if getattr(item, 'block', 0) > 0:    parts.append(f"Block:{item.block}%")
        if getattr(item, 'evasion', 0) > 0:  parts.append(f"Eva:{item.evasion}%")
        if getattr(item, 'pdr', 0) > 0:      parts.append(f"PDR:{item.pdr}%")
        if getattr(item, 'fdr', 0) > 0:      parts.append(f"FDR:{item.fdr}")
        if isinstance(item, Weapon) and item.refinement_lvl > 0:
            parts.append(f"+{item.refinement_lvl}")

        passives = []
        if getattr(item, 'passive', 'none') not in ('none', ''):
            passives.append(item.passive.title())
        if isinstance(item, Weapon):
            if getattr(item, 'p_passive', 'none') not in ('none', ''):
                passives.append(item.p_passive.title())
            if getattr(item, 'u_passive', 'none') not in ('none', ''):
                passives.append(item.u_passive.title())
            if getattr(item, 'infernal_passive', 'none') not in ('none', ''):
                passives.append(f"🔥{item.infernal_passive.title()}")
        if isinstance(item, Armor) and getattr(item, 'celestial_passive', 'none') not in ('none', ''):
            passives.append(f"🌌{item.celestial_passive.title()}")
        if isinstance(item, Accessory) and getattr(item, 'void_passive', 'none') not in ('none', ''):
            passives.append(f"🌀{item.void_passive.title()}")

        stat_str = " ".join(parts)
        passive_str = " · ".join(passives)
        desc = f"{stat_str} | {passive_str}" if stat_str and passive_str else stat_str or passive_str or "No stats"

        if len(desc) > 100:
            desc = desc[:97] + "..."
        return desc

    def _build_select_options(self, page_items) -> list:
        options = []
        for item in page_items:
            is_equipped = (item.item_id == self.equipped_id)

            label = f"{'[E] ' if is_equipped else ''}Lv.{item.level} {item.name}"
            if isinstance(item, Weapon) and item.refinement_lvl > 0:
                label += f" (+{item.refinement_lvl})"
            elif hasattr(item, 'passive_lvl') and item.passive_lvl > 0:
                label += f" (+{item.passive_lvl})"
            if len(label) > 100:
                label = label[:97] + "..."

            options.append(discord.SelectOption(
                label=label,
                value=str(item.item_id),
                description=self._build_select_description(item),
            ))
        return options

    # ------------------------------------------------------------------
    # Component rebuild
    # ------------------------------------------------------------------

    def update_components(self):
        self.clear_items()

        slot_items  = self.all_items.get(self.active_slot, [])
        total_pages = self._get_total_pages()

        # Clamp page
        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)

        start      = self.current_page * 25
        page_items = slot_items[start:start + 25]

        # Row 0 — Select menu or empty placeholder
        if page_items:
            options = self._build_select_options(page_items)
            select  = discord.ui.Select(
                placeholder=f"Choose a {SLOT_CONFIG[self.active_slot]['label'].lower()}...",
                options=options,
                row=0,
            )
            # Capture select in closure so the callback can read .values
            async def _on_select(interaction: Interaction, s=select):
                await self._handle_select(interaction, s)
            select.callback = _on_select
            self.add_item(select)
        else:
            cfg   = SLOT_CONFIG[self.active_slot]
            empty = Button(
                label=f"No {cfg['label']}s in inventory",
                style=ButtonStyle.secondary,
                disabled=True,
                row=0,
            )
            self.add_item(empty)

        # Rows 1–2 — Slot tab buttons (3 per row)
        for row_idx, slots in enumerate([SLOT_ORDER[:3], SLOT_ORDER[3:]], start=1):
            for slot in slots:
                cfg   = SLOT_CONFIG[slot]
                style = ButtonStyle.primary if slot == self.active_slot else ButtonStyle.secondary
                btn   = Button(label=f"{cfg['emoji']} {cfg['label']}", style=style, row=row_idx)
                btn.callback = lambda i, s=slot: self.switch_slot(i, s)
                self.add_item(btn)

        # Row 3 — Prev / Next (only when multi-page)
        if total_pages > 1:
            prev = Button(label="◀ Prev", disabled=(self.current_page == 0), row=3)
            prev.callback = self.prev_page
            self.add_item(prev)

            nxt = Button(label="▶ Next", disabled=(self.current_page >= total_pages - 1), row=3)
            nxt.callback = self.next_page
            self.add_item(nxt)

        # Row 4 — Mass Discard + Close
        mass = Button(
            label="Mass Discard",
            style=ButtonStyle.danger,
            emoji="🗑️",
            disabled=(len(slot_items) == 0),
            row=4,
        )
        mass.callback = self.mass_discard_callback
        self.add_item(mass)

        close = Button(label="Close", style=ButtonStyle.secondary, row=4)
        close.callback = self.close_view
        self.add_item(close)

    # ------------------------------------------------------------------
    # Embed builder
    # ------------------------------------------------------------------

    def build_embed(self, user_name: str) -> discord.Embed:
        return InventoryUI.get_gear_embed(
            user_name,
            self.all_items,
            self.active_slot,
            self.equipped_ids,
            self.current_page,
            self._get_total_pages(),
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def switch_slot(self, interaction: Interaction, slot_key: str):
        self.active_slot  = slot_key
        self.current_page = 0
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(interaction.user.display_name), view=self)

    async def _handle_select(self, interaction: Interaction, select: discord.ui.Select):
        item_id = int(select.values[0])
        item    = self._find_item_by_id(item_id)
        if item is None:
            return await interaction.response.send_message("Item not found.", ephemeral=True)

        detail_view = ItemDetailView(self.bot, self.user_id, item, self)
        await detail_view.fetch_data()
        embed = InventoryUI.get_item_details_embed(item, item.item_id == self.equipped_id)
        await interaction.response.edit_message(content=None, embed=embed, view=detail_view)

    async def prev_page(self, interaction: Interaction):
        self.current_page = max(0, self.current_page - 1)
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(interaction.user.display_name), view=self)

    async def next_page(self, interaction: Interaction):
        self.current_page = min(self._get_total_pages() - 1, self.current_page + 1)
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(interaction.user.display_name), view=self)

    async def mass_discard_callback(self, interaction: Interaction):
        await interaction.response.send_modal(MassDiscardModal(self))

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        for child in self.children:
            child.disabled = True
        try:
            if hasattr(self, 'message') and self.message:
                embed = self.message.embeds[0]
                embed.set_footer(text="Session Timed Out.")
                await self.message.edit(embed=embed, view=self)
        except (discord.NotFound, discord.HTTPException):
            pass