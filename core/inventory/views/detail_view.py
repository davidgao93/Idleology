import asyncio
from typing import Any

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.companions.mechanics import CompanionMechanics
from core.inventory.inventory import InventoryUI
from core.inventory.upgrades import (
    EngramView,
    ForgeView,
    ImbueView,
    InfernalEngramView,
    MirageView,
    PotentialView,
    RefineView,
    ReinforceView,
    TemperView,
    VoidEngramView,
    VoidforgeView,
)

# Core Imports
from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon


class DiscardConfirmView(BaseView):
    """Simple Yes/No view for deleting valuable items."""

    def __init__(self, origin_view):
        super().__init__(bot=origin_view.bot, parent=origin_view)
        self.origin_view = origin_view  # Refers to ItemDetailView

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
        embed = InventoryUI.get_item_details_embed(
            self.origin_view.item, self.origin_view.is_equipped
        )
        await interaction.response.edit_message(
            content=None, embed=embed, view=self.origin_view
        )

        self.stop()


class ItemDetailView(BaseView):
    """
    Handles actions for a specific item. Dynamically generates buttons based on Item Type.
    """

    def __init__(self, bot, user_id: str, item: Any, parent_view: Any):
        super().__init__(bot=bot, user_id=user_id)
        self.bot = bot
        self.user_id = user_id
        self.item = item
        self.parent = parent_view  # To support "Back" button

        self.is_equipped = item.item_id == parent_view.equipped_id
        self.void_keys = 0
        self.mirage_runes_imperfect = 0
        self.mirage_runes_perfected = 0
        self._processing = False

    async def fetch_data(self):
        """Async setup to fetch currency/keys needed for button logic."""
        if isinstance(self.item, Weapon):
            self.void_keys = await self.bot.database.users.get_currency(
                self.user_id, "void_keys"
            )
        if isinstance(self.item, (Armor, Glove, Boot, Helmet)):
            self.shatter_runes = await self.bot.database.users.get_currency(
                self.user_id, "shatter_runes"
            )
        self.mirage_runes_imperfect = await self.bot.database.users.get_currency(
            self.user_id, "mirage_runes_imperfect"
        )
        self.mirage_runes_perfected = await self.bot.database.users.get_currency(
            self.user_id, "mirage_runes_perfected"
        )
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

            if (
                self.void_keys > 0
                and self.item.passive != "none"
                and self.item.u_passive == "none"
            ):
                self.add_upgrade_button("Voidforge", ButtonStyle.primary, "voidforge")
            self.add_upgrade_button(
                "Infernal Engram", ButtonStyle.danger, "infernal_engram"
            )

        elif isinstance(self.item, Armor):
            if self.item.temper_remaining > 0:
                self.add_upgrade_button("Temper", ButtonStyle.success, "temper")
            if self.item.imbue_remaining > 0 and self.item.passive == "none":
                self.add_upgrade_button("Imbue", ButtonStyle.primary, "imbue")
            self.add_upgrade_button("Reinforce", ButtonStyle.primary, "reinforce")
            self.add_upgrade_button("Engram", ButtonStyle.danger, "engram")

        elif isinstance(self.item, (Accessory, Glove, Boot, Helmet)):
            max_lvl = (
                10
                if isinstance(self.item, Accessory)
                else (5 if isinstance(self.item, (Glove, Helmet)) else 6)
            )
            if (
                hasattr(self.item, "potential_remaining")
                and self.item.potential_remaining > 0
                and self.item.passive_lvl < max_lvl
            ):
                self.add_upgrade_button("Enchant", ButtonStyle.success, "potential")
            if isinstance(self.item, Accessory):
                self.add_upgrade_button(
                    "Void Engram", ButtonStyle.secondary, "void_engram"
                )
            if isinstance(self.item, (Glove, Boot, Helmet)):
                self.add_upgrade_button("Reinforce", ButtonStyle.primary, "reinforce")
                essence_btn = Button(
                    label="Essences", style=ButtonStyle.primary, emoji="💎"
                )
                essence_btn.callback = self._open_essences
                self.add_item(essence_btn)

        # 3. Mirage (all item types, requires at least one rune)
        if self.mirage_runes_imperfect > 0 or self.mirage_runes_perfected > 0:
            self.add_upgrade_button("Mirage", ButtonStyle.secondary, "mirage")

        # 4. Standard Actions
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
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.bot.state_manager.set_active(self.user_id, "upgrade")
        view_map = {
            "forge": ForgeView,
            "refine": RefineView,
            "temper": TemperView,
            "imbue": ImbueView,
            "potential": PotentialView,
            "voidforge": VoidforgeView,
            "reinforce": ReinforceView,
            "engram": EngramView,
            "infernal_engram": InfernalEngramView,
            "void_engram": VoidEngramView,
            "mirage": MirageView,
        }

        view_class = view_map.get(action_type)
        if view_class:
            view = view_class(self.bot, self.user_id, self.item, self)
            await view.render(interaction)
        else:
            await interaction.followup.send("Unknown action.", ephemeral=True)

    async def _open_essences(self, interaction: Interaction):
        await interaction.response.defer()
        from core.items.essence_views import EssenceView

        item_type = self._get_db_type()
        essence_inventory = await self.bot.database.essences.get_all(self.user_id)
        view = EssenceView(
            self.bot, self.user_id, self.item, item_type, self, essence_inventory
        )
        await interaction.edit_original_response(embed=view._get_embed(), view=view)
        view.message = await interaction.original_response()

    # --- Actions ---

    async def toggle_equip(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        await interaction.response.defer()
        itype = self._get_db_type()
        if self.is_equipped:
            await self.bot.database.equipment.unequip(self.user_id, itype)
            self.parent.equipped_id = None
            self.is_equipped = False
        else:
            await self.bot.database.equipment.equip(
                self.user_id, self.item.item_id, itype
            )
            self.parent.equipped_id = self.item.item_id
            self.is_equipped = True

        await self.fetch_data()  # Re-check keys/status for button display
        self._processing = False
        embed = InventoryUI.get_item_details_embed(self.item, self.is_equipped)
        await interaction.edit_original_response(embed=embed, view=self)
        self.message = await interaction.original_response()

    # --- DISCARD LOGIC ---

    def _is_valuable(self) -> bool:
        """Checks if item has any stats that make it worth confirming before delete."""
        if isinstance(self.item, Weapon):
            return (
                self.item.passive != "none" and self.item.passive != ""
            ) or self.item.refinement_lvl > 0

        if isinstance(self.item, Armor):
            return (
                self.item.passive != "none" and self.item.passive != ""
            ) or self.item.reinforcement_lvl > 0

        # General check for other items
        if (
            hasattr(self.item, "passive")
            and self.item.passive != "none"
            and self.item.passive != ""
        ):
            return True
        if hasattr(self.item, "passive_lvl") and self.item.passive_lvl > 0:
            return True

        return False

    async def discard_item(self, interaction: Interaction):
        # 1. Check if valuable
        if self._is_valuable():
            confirm_view = DiscardConfirmView(self)
            await interaction.response.edit_message(
                content="⚠️ **Warning:** This item has passives or upgrades. Are you sure you want to discard it?",
                embed=None,
                view=confirm_view,
            )
            self.message = await interaction.original_response()
        else:
            # 2. Not valuable, delete immediately
            await self.finalize_discard(interaction)

    async def finalize_discard(self, interaction: Interaction):
        """Performs the actual DB deletion and returns to list via a brief flash."""
        if self._processing:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return
        self._processing = True

        if not interaction.response.is_done():
            await interaction.response.defer()

        itype = self._get_db_type()

        # --- [FEED LOGIC] — pool XP for manual distribution via Companions view ---
        xp_msg = ""
        total_xp_val = CompanionMechanics.calculate_feed_xp(self.item)
        if total_xp_val > 0:
            await self.bot.database.users.add_pending_companion_cookies(
                self.user_id, total_xp_val
            )
            xp_msg = f"\n🐾 **+{total_xp_val:,} XP** added to your Companion XP pool."

        # Discard DB
        await self.bot.database.equipment.discard(self.item.item_id, itype)

        # Weapon refinement rune refund
        rune_msg = ""
        if isinstance(self.item, Weapon) and self.item.refinement_lvl > 0:
            runes_back = max(0, int(self.item.refinement_lvl - 6 * 0.8))
            if self.item.attack > 0 and self.item.defence > 0 and self.item.rarity > 0:
                runes_back += 1
            if runes_back > 0:
                await self.bot.database.users.modify_currency(
                    self.user_id, "refinement_runes", runes_back
                )
                rune_msg = f"\n🔮 Recovered **{runes_back}** Refinement Rune(s)."

        # Update List State
        self.parent.items = [
            i for i in self.parent.items if i.item_id != self.item.item_id
        ]
        self.parent.total_pages = max(
            1,
            (len(self.parent.items) + self.parent.items_per_page - 1)
            // self.parent.items_per_page,
        )
        if self.parent.current_page >= self.parent.total_pages:
            self.parent.current_page = max(0, self.parent.total_pages - 1)
        self.parent.update_buttons()

        # Brief Popup (Replaces the annoying ephemeral followup)
        temp_embed = discord.Embed(title="Item Discarded", color=discord.Color.red())
        temp_embed.description = (
            f"🗑️ **{self.item.name}** was dismantled.{xp_msg}{rune_msg}"
        )

        await interaction.edit_original_response(
            content=None, embed=temp_embed, view=None
        )
        await asyncio.sleep(1.0)  # Wait 1.5s

        # Return to List View
        embed = await self.parent.get_current_embed(interaction.user.display_name)
        await interaction.edit_original_response(embed=embed, view=self.parent)

    async def go_back(self, interaction: Interaction):
        self.parent.update_buttons()
        embed = await self.parent.get_current_embed(interaction.user.display_name)
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.message = await interaction.original_response()

    def _get_db_type(self) -> str:
        if isinstance(self.item, Weapon):
            return "weapon"
        if isinstance(self.item, Armor):
            return "armor"
        if isinstance(self.item, Accessory):
            return "accessory"
        if isinstance(self.item, Glove):
            return "glove"
        if isinstance(self.item, Boot):
            return "boot"
        if isinstance(self.item, Helmet):
            return "helmet"
        return "weapon"
