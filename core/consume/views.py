import discord
from discord import ButtonStyle, Interaction, ui

from core.items.factory import create_monster_part
from core.models import MonsterPart, Player

_SLOT_ORDER = [
    "head",
    "torso",
    "right_arm",
    "left_arm",
    "right_leg",
    "left_leg",
    "cheeks",
    "organs",
]

_SLOT_LABELS = {
    "head": "Head",
    "torso": "Torso",
    "right_arm": "Right Arm",
    "left_arm": "Left Arm",
    "right_leg": "Right Leg",
    "left_leg": "Left Leg",
    "cheeks": "Cheeks",
    "organs": "Organs",
}

_SLOT_EMOJI = {
    "head": "💀",
    "torso": "🫁",
    "right_arm": "💪",
    "left_arm": "🤜",
    "right_leg": "🦵",
    "left_leg": "🦿",
    "cheeks": "🍑",
    "organs": "🫀",
}


def _build_main_embed(player: Player, inventory: list) -> discord.Embed:
    parts_hp = (
        sum(v["hp"] for v in player.equipped_parts.values())
        if player.equipped_parts
        else 0
    )
    embed = discord.Embed(
        title=f"🫀 {player.name}'s Monster Parts",
        description=(
            f"Consume monster body parts to empower your spirit.\n"
            f"**Max HP Gained:** +{parts_hp:,}\n"
            f"**Inventory:** {len(inventory)}/20 parts"
        ),
        color=0xB22222,
    )
    for slot in _SLOT_ORDER:
        label = _SLOT_LABELS[slot]
        emoji = _SLOT_EMOJI[slot]
        if slot in player.equipped_parts:
            data = player.equipped_parts[slot]
            embed.add_field(
                name=f"{emoji} {label}",
                value=f"{data['monster_name']}'s **{label}**\n+{data['hp']} Max HP",
                inline=True,
            )
        else:
            embed.add_field(
                name=f"{emoji} {label}",
                value="*Empty*",
                inline=True,
            )
    return embed


class BulkDiscardModal(ui.Modal, title="Bulk Discard Parts"):
    ilvl_input = ui.TextInput(
        label="Discard all parts below ilvl:",
        placeholder="e.g. 50  (discards parts with ilvl < 50)",
        min_length=1,
        max_length=4,
    )

    def __init__(self, parent: "ConsumeView"):
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction: Interaction):
        try:
            threshold = int(self.ilvl_input.value)
            if threshold <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a valid positive number.", ephemeral=True
            )

        count = await self.parent.bot.database.monster_parts.delete_below_ilvl(
            self.parent.user_id, threshold
        )
        if count == 0:
            return await interaction.response.send_message(
                f"No parts found below ilvl {threshold}.", ephemeral=True
            )

        await interaction.response.defer()
        # Refresh inventory and rebuild
        self.parent.inventory = (
            await self.parent.bot.database.monster_parts.get_inventory(
                self.parent.user_id
            )
        )
        self.parent.inventory_parts = [
            create_monster_part(r) for r in self.parent.inventory
        ]
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        embed.set_footer(
            text=f"Discarded {count} part{'s' if count != 1 else ''} below ilvl {threshold}."
        )
        await interaction.edit_original_response(embed=embed, view=self.parent)


class EquipConfirmView(ui.View):
    """Shown when a slot is already occupied — asks the player to confirm replacement."""

    def __init__(self, parent: "ConsumeView", part: MonsterPart):
        super().__init__(timeout=60)
        self.parent = parent
        self.part = part

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.parent.user_id

    async def on_timeout(self):
        try:
            await self.parent.message.edit(
                embed=_build_main_embed(self.parent.player, self.parent.inventory),
                view=self.parent,
            )
        except Exception:
            pass

    @ui.button(label="Confirm Replace", style=ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self._do_equip()
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        embed.set_footer(text=f"You consumed {self.part.display_name}.")
        await interaction.edit_original_response(embed=embed, view=self.parent)
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()

    async def _do_equip(self):
        slot = self.part.slot_type
        await self.parent.bot.database.monster_parts.equip_part(
            self.parent.user_id, slot, self.part.hp_value, self.part.monster_name
        )
        await self.parent.bot.database.monster_parts.delete_part(self.part.id)
        self.parent.player.equipped_parts[slot] = {
            "hp": self.part.hp_value,
            "monster_name": self.part.monster_name,
        }
        self.parent.inventory = [
            r for r in self.parent.inventory if r[0] != self.part.id
        ]
        self.parent.inventory_parts = [
            create_monster_part(r) for r in self.parent.inventory
        ]
        self.parent._rebuild_select()


class PartDetailView(ui.View):
    """Shown after selecting a specific part — offers Equip or Discard."""

    def __init__(self, parent: "ConsumeView", part: MonsterPart):
        super().__init__(timeout=120)
        self.parent = parent
        self.part = part

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.parent.user_id

    async def on_timeout(self):
        try:
            await self.parent.message.edit(
                embed=_build_main_embed(self.parent.player, self.parent.inventory),
                view=self.parent,
            )
        except Exception:
            pass

    @ui.button(label="Equip", style=ButtonStyle.success, emoji="✅")
    async def equip(self, interaction: Interaction, button: ui.Button):
        slot = self.part.slot_type
        if slot in self.parent.player.equipped_parts:
            # Slot occupied — show confirmation
            current = self.parent.player.equipped_parts[slot]
            label = _SLOT_LABELS[slot]
            confirm_embed = discord.Embed(
                title="Consume new monster part?",
                description=(
                    f"**{slot.replace('_', ' ').title()} slot** is currently occupied:\n\n"
                    f"**Current:** {current['monster_name']}'s **{label}** — +{current['hp']} Max HP\n"
                    f"**New:** {self.part.display_name} — +{self.part.hp_value} Max HP\n\n"
                    f"The current part will be **permanently destroyed**."
                ),
                color=0xFF6600,
            )
            confirm_view = EquipConfirmView(self.parent, self.part)
            await interaction.response.edit_message(
                embed=confirm_embed, view=confirm_view
            )
            self.stop()
        else:
            # Slot empty — equip immediately
            await interaction.response.defer()
            await self.parent.bot.database.monster_parts.equip_part(
                self.parent.user_id, slot, self.part.hp_value, self.part.monster_name
            )
            await self.parent.bot.database.monster_parts.delete_part(self.part.id)
            self.parent.player.equipped_parts[slot] = {
                "hp": self.part.hp_value,
                "monster_name": self.part.monster_name,
            }
            self.parent.inventory = [
                r for r in self.parent.inventory if r[0] != self.part.id
            ]
            self.parent.inventory_parts = [
                create_monster_part(r) for r in self.parent.inventory
            ]
            self.parent._rebuild_select()
            embed = _build_main_embed(self.parent.player, self.parent.inventory)
            embed.set_footer(text=f"You consume {self.part.display_name}.")
            await interaction.edit_original_response(embed=embed, view=self.parent)
            self.stop()

    @ui.button(label="Discard", style=ButtonStyle.danger, emoji="🗑️")
    async def discard(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.parent.bot.database.monster_parts.delete_part(self.part.id)
        self.parent.inventory = [
            r for r in self.parent.inventory if r[0] != self.part.id
        ]
        self.parent.inventory_parts = [
            create_monster_part(r) for r in self.parent.inventory
        ]
        self.parent._rebuild_select()
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        embed.set_footer(text=f"Discarded {self.part.display_name}.")
        await interaction.edit_original_response(embed=embed, view=self.parent)
        self.stop()

    @ui.button(label="Back", style=ButtonStyle.secondary)
    async def back(self, interaction: Interaction, button: ui.Button):
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()


class PartSelect(ui.Select):
    def __init__(self, parts: list[MonsterPart]):
        options = [
            discord.SelectOption(
                label=p.display_name[:100],
                description=f"ilvl {p.ilvl} — +{p.hp_value} Max HP",
                value=str(p.id),
                emoji=_SLOT_EMOJI.get(p.slot_type, "🫀"),
            )
            for p in parts[:25]
        ]
        super().__init__(
            placeholder="Select a part to inspect...",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.parts_by_id = {p.id: p for p in parts}

    async def callback(self, interaction: Interaction):
        part_id = int(self.values[0])
        part = self.parts_by_id.get(part_id)
        if not part:
            return await interaction.response.send_message(
                "Part not found.", ephemeral=True
            )

        label = _SLOT_LABELS.get(part.slot_type, part.slot_type)
        embed = discord.Embed(
            title=part.display_name,
            description=(
                f"**Slot:** {label}\n"
                f"**Monster ilvl:** {part.ilvl}\n"
                f"**Max HP Bonus:** +{part.hp_value}"
            ),
            color=0xB22222,
        )
        detail_view = PartDetailView(self.view, part)
        await interaction.response.edit_message(embed=embed, view=detail_view)


class ConsumeView(ui.View):
    def __init__(self, player: Player, inventory: list, bot):
        super().__init__(timeout=120)
        self.player = player
        self.bot = bot
        self.user_id = str(player.id)
        self.inventory = inventory  # raw DB rows
        self.inventory_parts = [create_monster_part(r) for r in inventory]
        self.message = None
        self._rebuild_select()

    def _rebuild_select(self):
        # Remove existing select if present
        for item in self.children[:]:
            if isinstance(item, PartSelect):
                self.remove_item(item)
        if self.inventory_parts:
            self.add_item(PartSelect(self.inventory_parts))

    def build_embed(self) -> discord.Embed:
        return _build_main_embed(self.player, self.inventory)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    @ui.button(label="Bulk Discard", style=ButtonStyle.danger, emoji="🗑️", row=1)
    async def bulk_discard(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(BulkDiscardModal(self))

    @ui.button(label="Exit", style=ButtonStyle.secondary, row=1)
    async def exit(self, interaction: Interaction, button: ui.Button):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.edit_message(view=None)
