import asyncio

import discord
from discord import Interaction

from core.companions.mechanics import CompanionMechanics


class MassDiscardModal(discord.ui.Modal, title="Mass Discard"):
    level_input = discord.ui.TextInput(
        label="Max Item Level to Discard",
        placeholder="e.g. 50 (Discards <= 50)",
        min_length=1,
        max_length=3,
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            level_limit = int(self.level_input.value)
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True
            )

        # Filter logic: Must not be equipped, must be <= requested level
        items_to_delete = [
            item
            for item in self.parent_view.items
            if not getattr(item, "is_equipped", False) and item.level <= level_limit
        ]

        if not items_to_delete:
            return await interaction.response.send_message(
                f"No unequipped items found at or below level {level_limit}.",
                ephemeral=True,
            )

        await interaction.response.defer()

        itype = self.parent_view._get_db_type()
        total_xp_val = 0

        # Execute DB Deletions
        for item in items_to_delete:
            total_xp_val += CompanionMechanics.calculate_feed_xp(item)
            await self.parent_view.bot.database.equipment.discard(item.item_id, itype)

        # Pool XP for manual distribution via Companions view
        xp_msg = ""
        if total_xp_val > 0:
            await self.parent_view.bot.database.users.modify_currency(
                self.parent_view.user_id, "companion_pet_xp", total_xp_val
            )
            xp_msg = f"\n🐾 **+{total_xp_val:,} XP** added to your Companion XP pool."

        # Update List State
        deleted_ids = {i.item_id for i in items_to_delete}
        self.parent_view.items = [
            i for i in self.parent_view.items if i.item_id not in deleted_ids
        ]

        # Recalculate pages
        self.parent_view.total_pages = max(
            1,
            (len(self.parent_view.items) + self.parent_view.items_per_page - 1)
            // self.parent_view.items_per_page,
        )
        if self.parent_view.current_page >= self.parent_view.total_pages:
            self.parent_view.current_page = max(0, self.parent_view.total_pages - 1)

        self.parent_view.update_buttons()

        # Show temporary popup
        temp_embed = discord.Embed(
            title="Mass Discard Complete", color=discord.Color.red()
        )
        temp_embed.description = f"🗑️ Dismantled **{len(items_to_delete)}** items (Level <= {level_limit}).{xp_msg}"

        await interaction.edit_original_response(
            content=None, embed=temp_embed, view=None
        )

        await asyncio.sleep(1.5)

        # Revert to List View
        list_embed = await self.parent_view.get_current_embed(
            interaction.user.display_name
        )
        await interaction.edit_original_response(
            embed=list_embed, view=self.parent_view
        )
