import asyncio

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from database.repositories.loadouts import SLOT_COSTS

from ._slot_defs import SLOT_EMOJIS as _SLOT_EMOJIS, SLOT_LABELS as _SLOT_LABELS, SLOT_ORDER as _SLOT_ORDER

MAX_SLOTS = 10


def _fmt_gold(amount: int) -> str:
    if amount >= 1_000_000_000:
        return f"{amount // 1_000_000_000}B"
    return f"{amount // 1_000_000}M"


class RenameLoadoutModal(discord.ui.Modal, title="Rename Loadout"):
    new_name = discord.ui.TextInput(
        label="New Name",
        max_length=20,
        min_length=1,
        placeholder="Enter a name for this loadout...",
    )

    def __init__(self, parent_view: "LoadoutView", slot_index: int, current_name: str):
        super().__init__()
        self.parent_view = parent_view
        self.slot_index = slot_index
        self.new_name.default = current_name

    async def on_submit(self, interaction: Interaction):
        name = self.new_name.value.strip()
        await self.parent_view.bot.database.loadouts.rename(
            self.parent_view.user_id, self.slot_index, name
        )
        await self.parent_view._reload()
        self.parent_view.update_components()
        await interaction.response.edit_message(
            embed=self.parent_view.build_embed(interaction.user.display_name),
            view=self.parent_view,
        )
        self.parent_view.message = await interaction.original_response()


class LoadoutView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        loadouts: list,
        slots_unlocked: int,
        item_names_by_slot: dict,
        *,
        mode: str = "standalone",
        parent_view=None,
    ):
        super().__init__(bot, user_id, server_id=server_id)
        self.loadouts = loadouts
        self.slots_unlocked = slots_unlocked
        self.item_names_by_slot = item_names_by_slot  # {slot_index: {slot_type: name|None}}
        self.mode = mode
        self.parent_view = parent_view
        self.selected_slot_index = None
        self._processing = False
        self.update_components()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    async def create(
        cls,
        bot,
        user_id: str,
        server_id: str,
        *,
        mode: str = "standalone",
        parent_view=None,
    ) -> "LoadoutView":
        slots_unlocked = await bot.database.loadouts.get_slots_unlocked(user_id)
        await bot.database.loadouts.ensure_default_rows(user_id, slots_unlocked)
        loadouts = await bot.database.loadouts.get_all(user_id)
        item_names_by_slot = {}
        for row in loadouts:
            item_names_by_slot[row["slot_index"]] = await bot.database.loadouts.get_item_names(row)
        return cls(
            bot, user_id, server_id, loadouts, slots_unlocked, item_names_by_slot,
            mode=mode, parent_view=parent_view,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_selected(self):
        if self.selected_slot_index is None:
            return None
        for row in self.loadouts:
            if row["slot_index"] == self.selected_slot_index:
                return row
        return None

    @staticmethod
    def _is_empty(loadout_row) -> bool:
        return all(
            loadout_row[col] is None
            for col in ("weapon_id", "armor_id", "helmet_id", "glove_id", "boot_id", "accessory_id")
        )

    async def _reload(self):
        self.slots_unlocked = await self.bot.database.loadouts.get_slots_unlocked(self.user_id)
        self.loadouts = await self.bot.database.loadouts.get_all(self.user_id)
        self.item_names_by_slot = {}
        for row in self.loadouts:
            self.item_names_by_slot[row["slot_index"]] = await self.bot.database.loadouts.get_item_names(row)

    # ------------------------------------------------------------------
    # Component builder
    # ------------------------------------------------------------------

    def update_components(self):
        self.clear_items()
        anything_selected = self.selected_slot_index is not None

        # Row 0 — Loadout select
        if self.loadouts:
            options = [
                discord.SelectOption(
                    label=row["name"],
                    value=str(row["slot_index"]),
                    description=f"Slot {row['slot_index']}",
                    default=(row["slot_index"] == self.selected_slot_index),
                )
                for row in self.loadouts
            ]
            select = discord.ui.Select(
                placeholder="Choose a loadout to manage...",
                options=options,
                row=0,
            )
            async def _on_select(interaction: Interaction, s=select):
                await self._handle_select(interaction, s)
            select.callback = _on_select
            self.add_item(select)

        # Row 1 — Context buttons
        apply_btn = Button(
            label="✅ Apply Loadout",
            style=ButtonStyle.success,
            disabled=not anything_selected,
            row=1,
        )
        apply_btn.callback = self._apply_callback
        self.add_item(apply_btn)

        save_btn = Button(
            label="💾 Save Current Gear",
            style=ButtonStyle.primary,
            disabled=not anything_selected,
            row=1,
        )
        save_btn.callback = self._save_callback
        self.add_item(save_btn)

        rename_btn = Button(
            label="✏️ Rename",
            style=ButtonStyle.secondary,
            disabled=not anything_selected,
            row=1,
        )
        rename_btn.callback = self._rename_callback
        self.add_item(rename_btn)

        # Row 4 — Navigation
        next_slot = self.slots_unlocked + 1
        at_max = self.slots_unlocked >= MAX_SLOTS
        cost = SLOT_COSTS.get(next_slot, 0)
        buy_label = (
            "Max Slots Reached"
            if at_max
            else f"🔓 Buy Slot {next_slot} ({_fmt_gold(cost)} gold)"
        )
        buy_btn = Button(label=buy_label, style=ButtonStyle.secondary, disabled=at_max, row=4)
        buy_btn.callback = self._buy_slot_callback
        self.add_item(buy_btn)

        if self.mode == "from_gear":
            back_btn = Button(label="⬅️ Go Back", style=ButtonStyle.secondary, row=4)
            back_btn.callback = self._go_back_callback
            self.add_item(back_btn)

        close_btn = Button(label="Close", style=ButtonStyle.secondary, row=4)
        close_btn.callback = self._close_callback
        self.add_item(close_btn)

    # ------------------------------------------------------------------
    # Embed builder
    # ------------------------------------------------------------------

    def build_embed(self, user_name: str) -> discord.Embed:
        embed = discord.Embed(
            title="📦 Gear Loadouts",
            description=(
                f"**{user_name}** · {self.slots_unlocked} slot{'s' if self.slots_unlocked != 1 else ''}\n"
                "Select a loadout to apply, save your current gear to it, or rename it."
            ),
            color=discord.Color.blurple(),
        )

        for row in self.loadouts:
            slot_idx = row["slot_index"]
            names = self.item_names_by_slot.get(slot_idx, {})

            lines = []
            for slot_type in _SLOT_ORDER:
                emoji = _SLOT_EMOJIS[slot_type]
                name = names.get(slot_type)
                display = name if name is not None else "—"
                lines.append(f"{emoji} {display}")

            field_name = row["name"]
            if slot_idx == self.selected_slot_index:
                field_name = f"▶ {field_name} ◀"

            embed.add_field(name=field_name, value="\n".join(lines), inline=True)

        return embed

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _handle_select(self, interaction: Interaction, select: discord.ui.Select):
        self.selected_slot_index = int(select.values[0])
        self.update_components()
        await interaction.response.edit_message(
            embed=self.build_embed(interaction.user.display_name), view=self
        )
        self.message = await interaction.original_response()

    async def _apply_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        selected = self._get_selected()
        if selected is None:
            self._processing = False
            return

        if self._is_empty(selected):
            self._processing = False
            await interaction.followup.send(
                "This loadout is empty. Use **💾 Save Current Gear** to save your equipped items first.",
                ephemeral=True,
            )
            return

        skipped = await self.bot.database.equipment.apply_loadout(self.user_id, selected)

        await self._reload()
        self.update_components()
        await interaction.edit_original_response(
            embed=self.build_embed(interaction.user.display_name), view=self
        )

        msg = f"✅ **{selected['name']}** applied!"
        if skipped:
            labels = ", ".join(_SLOT_LABELS[s] for s in skipped)
            msg += f"\n⚠️ {len(skipped)} piece(s) were missing and unequipped: **{labels}**."
        await interaction.followup.send(msg, ephemeral=True)
        self._processing = False

    async def _save_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        selected = self._get_selected()
        if selected is None:
            self._processing = False
            return

        rows = await asyncio.gather(
            *[self.bot.database.equipment.get_equipped(self.user_id, slot) for slot in _SLOT_ORDER]
        )
        equipped = {slot: (row["item_id"] if row else None) for slot, row in zip(_SLOT_ORDER, rows)}

        await self.bot.database.loadouts.save(
            self.user_id,
            self.selected_slot_index,
            equipped["weapon"],
            equipped["armor"],
            equipped["helmet"],
            equipped["glove"],
            equipped["boot"],
            equipped["accessory"],
        )

        await self._reload()
        self.update_components()
        await interaction.edit_original_response(
            embed=self.build_embed(interaction.user.display_name), view=self
        )
        refreshed = self._get_selected()
        saved_name = refreshed["name"] if refreshed else selected["name"]
        await interaction.followup.send(
            f"💾 Current gear saved to **{saved_name}**!", ephemeral=True
        )
        self._processing = False

    async def _rename_callback(self, interaction: Interaction):
        selected = self._get_selected()
        if selected is None:
            return
        await interaction.response.send_modal(
            RenameLoadoutModal(self, selected["slot_index"], selected["name"])
        )

    async def _buy_slot_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        if self.slots_unlocked >= MAX_SLOTS:
            self._processing = False
            return

        next_slot = self.slots_unlocked + 1
        cost = SLOT_COSTS.get(next_slot, 0)

        success = await self.bot.database.users.deduct_gold_atomic(self.user_id, cost)
        if not success:
            self._processing = False
            await interaction.followup.send(
                f"You need **{cost:,}** gold to unlock Slot {next_slot}.", ephemeral=True
            )
            return

        await self.bot.database.loadouts.unlock_slot(self.user_id)
        await self.bot.database.loadouts.ensure_default_rows(self.user_id, next_slot)
        await self._reload()
        self.update_components()
        await interaction.edit_original_response(
            embed=self.build_embed(interaction.user.display_name), view=self
        )
        await interaction.followup.send(
            f"🔓 Slot {next_slot} unlocked for **{cost:,}** gold!", ephemeral=True
        )
        self._processing = False

    async def _go_back_callback(self, interaction: Interaction):
        if self.parent_view is not None and hasattr(self.parent_view, "_processing"):
            self.parent_view._processing = False
        await interaction.response.edit_message(
            embed=self.parent_view.build_embed(interaction.user.display_name),
            view=self.parent_view,
        )
        self.message = await interaction.original_response()

    async def _close_callback(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
