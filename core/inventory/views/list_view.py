from typing import Any, List

from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.inventory.inventory import InventoryUI

# Core Imports
from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon

from .detail_view import ItemDetailView
from .modals import MassDiscardModal


class InventoryListView(BaseView):
    """
    Generic Pagination View for any list of Equipment.
    """

    def __init__(self, bot, user_id: str, items: List[Any], title_emoji: str):
        super().__init__(bot=bot, user_id=user_id)
        self.bot = bot
        self.user_id = user_id
        self.items = items
        self.title_emoji = title_emoji

        # Pagination state
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = (len(items) + self.items_per_page - 1) // self.items_per_page
        if self.total_pages == 0:
            self.total_pages = 1

        # Equipped ID tracking
        self.equipped_id = next(
            (i.item_id for i in items if getattr(i, "is_equipped", False)), None
        )

        self.update_buttons()

    def _get_db_type(self) -> str:
        """Helper to determine the item type currently being displayed."""
        if not self.items:
            return "weapon"
        item = self.items[0]
        if isinstance(item, Weapon):
            return "weapon"
        if isinstance(item, Armor):
            return "armor"
        if isinstance(item, Accessory):
            return "accessory"
        if isinstance(item, Glove):
            return "glove"
        if isinstance(item, Boot):
            return "boot"
        if isinstance(item, Helmet):
            return "helmet"
        return "weapon"

    def update_buttons(self):
        self.clear_items()

        # Selection Buttons (1-5) Row 0
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        current_batch = self.items[start:end]

        for i, item in enumerate(current_batch):
            btn = Button(
                label=f"{i+1}",
                style=ButtonStyle.primary,
                custom_id=f"select_{i}",
                row=0,
            )
            btn.callback = lambda i_interaction, it=item: self.select_item(
                i_interaction, it
            )
            self.add_item(btn)

        # Navigation Buttons (Row 1)
        if self.total_pages > 1:
            prev_btn = Button(
                label="Prev", custom_id="prev", disabled=(self.current_page == 0), row=1
            )
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)

            next_btn = Button(
                label="Next",
                custom_id="next",
                disabled=(self.current_page == self.total_pages - 1),
                row=1,
            )
            next_btn.callback = self.next_page
            self.add_item(next_btn)

        # Bottom Controls (Row 2)
        mass_btn = Button(
            label="Mass Discard",
            style=ButtonStyle.danger,
            custom_id="mass_discard",
            emoji="🗑️",
            row=2,
        )
        mass_btn.disabled = len(self.items) == 0
        mass_btn.callback = self.mass_discard_callback
        self.add_item(mass_btn)

        close_btn = Button(
            label="Close", style=ButtonStyle.secondary, custom_id="close", row=2
        )
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    async def mass_discard_callback(self, interaction: Interaction):
        await interaction.response.send_modal(MassDiscardModal(self))

    async def get_current_embed(self, user_name: str):
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]

        return InventoryUI.get_list_embed(
            user_name,
            page_items,
            self.current_page,
            self.total_pages,
            self.equipped_id,
            self.title_emoji,
        )

    # --- Callbacks ---
    async def prev_page(self, interaction: Interaction):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        embed = await self.get_current_embed(interaction.user.display_name)
        await interaction.response.edit_message(content=None, embed=embed, view=self)
        self.message = await interaction.original_response()

    async def next_page(self, interaction: Interaction):
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_buttons()
        embed = await self.get_current_embed(interaction.user.display_name)
        await interaction.response.edit_message(content=None, embed=embed, view=self)
        self.message = await interaction.original_response()

    async def select_item(self, interaction: Interaction, item: Any):
        # Transition to Detail View
        detail_view = ItemDetailView(self.bot, self.user_id, item, self)
        await detail_view.fetch_data()
        embed = InventoryUI.get_item_details_embed(
            item, item.item_id == self.equipped_id
        )
        await interaction.response.edit_message(
            content=None, embed=embed, view=detail_view
        )
        self.message = await interaction.original_response()

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
