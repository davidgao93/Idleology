import random

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import Button, Select

from core.combat.calc.calcs import fmt_weapon_passive
from core.images import UPGRADE_VOIDFORGE
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.factory import create_weapon
from core.models import Weapon


class VoidforgeView(BaseUpgradeView):
    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self.candidates = []
        self.gold_cost = 0
        self.selected_target = None
        self._processing = False

    async def render(self, interaction: Interaction):
        self.selected_target = None

        self.gold_cost = 5_000_000 if self.item.p_passive == "none" else 10_000_000
        user_gold = await self.bot.database.users.get_gold(self.user_id)

        raw_rows = await self.bot.database.equipment.fetch_void_forge_candidates(
            self.user_id
        )
        self.candidates = [
            create_weapon(r) for r in raw_rows if r["item_id"] != self.item.item_id
        ]

        if not self.candidates:
            return await interaction.response.send_message(
                "No eligible sacrifice weapons found.\nRequires: Unequipped, Must have an active passive.",
                ephemeral=True,
            )

        if user_gold < self.gold_cost:
            return await interaction.response.send_message(
                f"Insufficient funds! You need **{self.gold_cost:,} gold** to initiate a Voidforge.",
                ephemeral=True,
            )

        options = []
        for w in self.candidates[:25]:
            lbl = f"Lv{w.level} {w.name} (+{w.refinement_lvl})"
            desc = f"Passive: {fmt_weapon_passive(w.passive)}"
            options.append(
                SelectOption(label=lbl, description=desc, value=str(w.item_id))
            )

        select = Select(placeholder="Select Sacrifice Weapon...", options=options)
        select.callback = self.select_callback

        self.clear_items()
        self.add_item(select)
        self.add_back_button()

        embed = discord.Embed(
            title="🌌 Voidforge",
            description=(
                f"Select a weapon to sacrifice.\n"
                f"**Cost:** 1 Void Key & {self.gold_cost:,} Gold\n\n"
                "**Effects:**\n"
                "25%: Add Passive as Pinnacle/Utmost\n"
                "25%: Overwrite Main Passive\n"
                "50%: Failure (Item Lost)"
            ),
            color=discord.Color.dark_purple(),
        )
        embed.set_author(name="Master Smith Harlan", icon_url=UPGRADE_VOIDFORGE)

        await self._send_render(interaction, embed)

    async def select_callback(self, interaction: Interaction):
        """Displays the confirmation prompt before executing."""
        target_id = int(interaction.data["values"][0])
        self.selected_target = next(
            (w for w in self.candidates if w.item_id == target_id), None
        )

        if not self.selected_target:
            return

        self.clear_items()

        confirm_btn = Button(
            label="CONFIRM SACRIFICE", style=ButtonStyle.danger, emoji="⚠️"
        )
        confirm_btn.callback = self.execute_voidforge
        self.add_item(confirm_btn)

        cancel_btn = Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self.cancel_confirmation
        self.add_item(cancel_btn)

        embed = discord.Embed(
            title="⚠️ Confirm Voidforge Sacrifice",
            description=(
                f"You are about to sacrifice:\n"
                f"🗡️ **{self.selected_target.name}** (Lv{self.selected_target.level})\n"
                f"✨ **Passive:** {fmt_weapon_passive(self.selected_target.passive)}\n\n"
                f"**Cost:** 1 Void Key & {self.gold_cost:,} Gold\n\n"
                "**This item will be PERMANENTLY DESTROYED regardless of success or failure.**"
            ),
            color=discord.Color.red(),
        )
        embed.set_author(name="Master Smith Harlan", icon_url=UPGRADE_VOIDFORGE)

        await interaction.response.edit_message(embed=embed, view=self)

    async def cancel_confirmation(self, interaction: Interaction):
        """Returns to the selection menu without sacrificing."""
        await self.render(interaction)

    async def execute_voidforge(self, interaction: Interaction):
        """Handles the actual deduction and RNG roll."""
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        target = self.selected_target
        if not target:
            self._processing = False
            return

        user_gold = await self.bot.database.users.get_gold(self.user_id)
        if user_gold < self.gold_cost:
            self._processing = False
            return await interaction.response.send_message(
                "You no longer have enough gold!", ephemeral=True
            )

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        await self.bot.database.users.modify_gold(self.user_id, -self.gold_cost)
        await self.bot.database.users.modify_currency(self.user_id, "void_keys", -1)

        await self.bot.database.equipment.discard(target.item_id, "weapon")

        inventory_view = self.parent_view.parent
        inventory_view.items = [
            i for i in inventory_view.items if i.item_id != target.item_id
        ]

        inventory_view.total_pages = max(
            1,
            (len(inventory_view.items) + inventory_view.items_per_page - 1)
            // inventory_view.items_per_page,
        )
        if inventory_view.current_page >= inventory_view.total_pages:
            inventory_view.current_page = max(0, inventory_view.total_pages - 1)
        inventory_view.update_buttons()

        roll = random.random()
        res_txt = ""
        color = discord.Color.dark_grey()

        if roll < 0.25:
            slot = (
                "pinnacle_passive"
                if self.item.p_passive == "none"
                else "utmost_passive"
            )
            await self.bot.database.equipment.update_passive(
                self.item.item_id, "weapon", target.passive, slot
            )

            if slot == "pinnacle_passive":
                self.item.p_passive = target.passive
            else:
                self.item.u_passive = target.passive

            res_txt = f"🌌 **Success!**\n{fmt_weapon_passive(target.passive)} added as {slot.replace('_', ' ').title()}."
            color = discord.Color.purple()

        elif roll < 0.50:
            await self.bot.database.equipment.update_passive(
                self.item.item_id, "weapon", target.passive
            )
            self.item.passive = target.passive
            res_txt = f"🔄 **Chaos!**\nMain passive overwritten with {fmt_weapon_passive(target.passive)}."
            color = discord.Color.orange()
        else:
            res_txt = "❌ **Failure.**\nThe essence dissipated into the void."

        embed = discord.Embed(
            title="Voidforge Result", description=res_txt, color=color
        )
        embed.set_author(name="Master Smith Harlan", icon_url=UPGRADE_VOIDFORGE)

        self.clear_items()
        self.add_back_button()

        await interaction.edit_original_response(embed=embed, view=self)
        self.message = await interaction.original_response()
