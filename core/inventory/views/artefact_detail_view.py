import asyncio

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.rite.loot import describe_artefact
from core.rite.models import Artefact


class ArtefactDiscardConfirmView(BaseView):
    """Simple Yes/No view for deleting an artefact."""

    def __init__(self, origin_view: "ArtefactDetailView"):
        super().__init__(bot=origin_view.bot, parent=origin_view)
        self.origin_view = origin_view

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.origin_view.user_id

    @discord.ui.button(label="Discard", style=ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: Interaction, button: Button):
        await self.origin_view.finalize_discard(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(
            embed=self.origin_view.build_embed(), view=self.origin_view
        )
        self.stop()


class ArtefactDetailView(BaseView):
    """Detail/actions view for a single owned Artefact — the Rite of
    Convergence's 7th gear-like slot. Deliberately separate from
    ItemDetailView (detail_view.py): artefacts have no upgrade paths, live
    in a different, server-scoped repository (bot.database.rite, not
    bot.database.equipment), and their discard has no companion-XP/rune
    refund logic to mirror.
    """

    def __init__(
        self, bot, user_id: str, server_id: str, item: Artefact, parent_view
    ):
        super().__init__(bot=bot, user_id=user_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.item = item
        self.parent = parent_view
        self.is_equipped = item.is_equipped
        self._processing = False
        self.setup_buttons()

    def build_embed(self) -> discord.Embed:
        rng = self.item.roll_1_range
        roll_line = ""
        if rng:
            roll_line = f"\n\n**Roll:** {int(self.item.roll_1)} *(range {rng[0]}-{rng[1]})*"
        embed = discord.Embed(
            title=f"🏺 {self.item.name}",
            description=(
                f"*Thematic source: {self.item.source}*\n\n"
                f"{describe_artefact(self.item.key, self.item.roll_1)}"
                f"{roll_line}"
            ),
            color=discord.Color.dark_gold(),
        )
        embed.set_thumbnail(url=self.item.image)
        embed.set_footer(text="Equipped" if self.is_equipped else "Not equipped")
        return embed

    def setup_buttons(self):
        self.clear_items()

        label = "Unequip" if self.is_equipped else "Equip"
        equip_btn = Button(label=label, style=ButtonStyle.primary, emoji="🏺")
        equip_btn.callback = self.toggle_equip
        self.add_item(equip_btn)

        discard_btn = Button(label="Discard", style=ButtonStyle.danger, emoji="🗑️")
        discard_btn.callback = self.discard_item
        self.add_item(discard_btn)

        back_btn = Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️")
        back_btn.callback = self.go_back
        self.add_item(back_btn)

    # --- Actions ---

    async def toggle_equip(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        if self.is_equipped:
            await self.bot.database.rite.unequip_artefact(self.user_id, self.server_id)
            self.parent.equipped_id = None
            self.is_equipped = False
            self.item.is_equipped = False
        else:
            await self.bot.database.rite.equip_artefact(
                self.user_id, self.server_id, self.item.item_id
            )
            # Only one artefact can be equipped at a time — reflect the
            # swap in the parent's cached list too.
            for other in self.parent.items:
                other.is_equipped = other.item_id == self.item.item_id
            self.parent.equipped_id = self.item.item_id
            self.is_equipped = True

        self._processing = False
        self.setup_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)
        self.message = await interaction.original_response()

    async def discard_item(self, interaction: Interaction):
        embed = discord.Embed(
            title="⚠️ Confirm Discard",
            description=(
                f"Are you sure you want to discard **{self.item.name}**? "
                "This cannot be undone."
            ),
            color=discord.Color.orange(),
        )
        confirm_view = ArtefactDiscardConfirmView(self)
        await interaction.response.edit_message(embed=embed, view=confirm_view)
        self.message = await interaction.original_response()

    async def finalize_discard(self, interaction: Interaction):
        if self._processing:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return
        self._processing = True
        if not interaction.response.is_done():
            await interaction.response.defer()

        await self.bot.database.rite.discard_artefact(self.item.item_id)

        self.parent.items = [
            i for i in self.parent.items if i.item_id != self.item.item_id
        ]
        if self.is_equipped:
            self.parent.equipped_id = None
        self.parent.total_pages = max(
            1,
            (len(self.parent.items) + self.parent.items_per_page - 1)
            // self.parent.items_per_page,
        )
        if self.parent.current_page >= self.parent.total_pages:
            self.parent.current_page = max(0, self.parent.total_pages - 1)
        self.parent.update_buttons()

        temp_embed = discord.Embed(
            title="Artefact Discarded", color=discord.Color.red()
        )
        temp_embed.description = f"🗑️ **{self.item.name}** was discarded."
        await interaction.edit_original_response(
            content=None, embed=temp_embed, view=None
        )
        await asyncio.sleep(1.0)

        embed = await self.parent.get_current_embed()
        await interaction.edit_original_response(embed=embed, view=self.parent)

    async def go_back(self, interaction: Interaction):
        self.parent.update_buttons()
        embed = await self.parent.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.message = await interaction.original_response()
