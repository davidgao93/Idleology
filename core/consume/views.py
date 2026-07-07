import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.combat.economy.drops import _PART_SLOTS, _PART_WEIGHTS
from core.emojis import MONSTER_CHEEK
from core.images import (
    CONSUME_EGG,
    CONSUME_HUB,
    CONSUME_SLOT_IMAGES,
    RAGNA_PORTRAIT,
    RAGNA_THUMBNAIL,
)
from core.npc_voices import get_quip
from core.items.factory import create_monster_part
from core.models import MonsterPart, Player

_EGG_TIER_EMOJI = {"normal": "🥚", "rare": "🪺", "giga": "🐲"}
_EGG_TIER_LABEL = {"normal": "Normal Egg", "rare": "Rare Egg", "giga": "Giga Egg"}
_EGG_PASSIVE_POINTS = {"normal": (1, 5), "rare": (5, 10), "giga": (10, 20)}

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
    "cheeks": MONSTER_CHEEK,
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
            f"*{get_quip('consume')}*\n\n"
            f"Consume monster body parts to empower your spirit.\n"
            f"**Max HP Gained:** +{parts_hp:,}\n"
            f"**Inventory:** {len(inventory)}/20 parts"
        ),
        color=0xB22222,
    )
    embed.set_author(name="Ragna", icon_url=RAGNA_PORTRAIT)
    embed.set_thumbnail(url=RAGNA_THUMBNAIL)
    for slot in _SLOT_ORDER:
        label = _SLOT_LABELS[slot]
        emoji = _SLOT_EMOJI[slot]
        if slot in player.equipped_parts:
            data = player.equipped_parts[slot]
            embed.add_field(
                name=f"{emoji} {label}",
                value=f"{data['monster_name']}'s {label}\n+{data['hp']} Max HP",
                inline=True,
            )
        else:
            embed.add_field(
                name=f"{emoji} {label}",
                value="*Empty*",
                inline=True,
            )
    return embed


def _build_recycle_select_embed(inventory_count: int) -> discord.Embed:
    embed = discord.Embed(
        title="♻️ Recycle Monster Parts",
        description=(
            "Select **3 parts** from the dropdown to recycle.\n\n"
            "Their HP values are summed, boosted by **5%**, then divided by 3.\n"
            "The result drops into a **random slot** using standard loot odds — "
            "head and torso are common; cheeks and organs are rare.\n\n"
            f"**Inventory:** {inventory_count}/20 parts"
        ),
        color=0x8B0000,
    )
    embed.set_thumbnail(url=CONSUME_HUB)
    return embed


def _build_recycle_confirm_embed(parts: list, new_hp: int) -> discord.Embed:
    total = sum(p.hp_value for p in parts)
    boosted = round(total * 1.05)
    lines = "\n".join(
        f"{_SLOT_EMOJI.get(p.slot_type, '🫀')} {p.display_name} — +{p.hp_value:,} HP"
        for p in parts
    )
    embed = discord.Embed(
        title="♻️ Confirm Recycle",
        description=(
            f"{lines}\n\n"
            f"**Sum:** {total:,} → **+5%** → {boosted:,}\n"
            f"**÷ 3 Result: +{new_hp:,} Max HP**\n\n"
            "Slot will be assigned randomly on confirm.\n"
            "⚠️ The 3 selected parts will be **permanently destroyed**."
        ),
        color=0x8B0000,
    )
    embed.set_thumbnail(url=CONSUME_HUB)
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


class EquipConfirmView(BaseView):
    """Shown when a slot is already occupied — asks the player to confirm replacement."""

    def __init__(self, parent: "ConsumeView", part: MonsterPart):
        super().__init__(bot=parent.bot, parent=parent)
        self.parent = parent
        self.part = part

    @ui.button(label="Confirm Consume", style=ButtonStyle.danger, emoji="👄")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self._do_equip()
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        embed.set_footer(text="Forbidden power courses through you...")
        await interaction.edit_original_response(embed=embed, view=self.parent)
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()

    async def _do_equip(self):
        slot = self.part.slot_type
        await self.parent.bot.database.monster_parts.equip_and_remove_part(
            self.parent.user_id,
            self.part.id,
            slot,
            self.part.hp_value,
            self.part.monster_name,
        )
        self.parent.player.equipped_parts[slot] = {
            "hp": self.part.hp_value,
            "monster_name": self.part.monster_name,
        }
        self.parent.inventory = [
            r for r in self.parent.inventory if r["id"] != self.part.id
        ]
        self.parent.inventory_parts = [
            create_monster_part(r) for r in self.parent.inventory
        ]
        self.parent._rebuild_select()


class PartDetailView(BaseView):
    """Shown after selecting a specific part — offers Equip or Discard."""

    def __init__(self, parent: "ConsumeView", part: MonsterPart):
        super().__init__(bot=parent.bot, parent=parent)
        self.parent = parent
        self.part = part

    @ui.button(label="Consume", style=ButtonStyle.success, emoji="👄")
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
                    f"The current part will be **discarded**."
                ),
                color=0xFF6600,
            )
            confirm_embed.set_thumbnail(url=CONSUME_SLOT_IMAGES.get(slot, CONSUME_HUB))
            confirm_view = EquipConfirmView(self.parent, self.part)
            await interaction.response.edit_message(
                embed=confirm_embed, view=confirm_view
            )
            self.stop()
        else:
            # Slot empty — equip immediately
            await interaction.response.defer()
            await self.parent.bot.database.monster_parts.equip_and_remove_part(
                self.parent.user_id,
                self.part.id,
                slot,
                self.part.hp_value,
                self.part.monster_name,
            )
            self.parent.player.equipped_parts[slot] = {
                "hp": self.part.hp_value,
                "monster_name": self.part.monster_name,
            }
            self.parent.inventory = [
                r for r in self.parent.inventory if r["id"] != self.part.id
            ]
            self.parent.inventory_parts = [
                create_monster_part(r) for r in self.parent.inventory
            ]
            self.parent._rebuild_select()
            embed = _build_main_embed(self.parent.player, self.parent.inventory)
            embed.set_footer(text="Forbidden power courses through you..")
            await interaction.edit_original_response(embed=embed, view=self.parent)
            self.stop()

    @ui.button(label="Discard", style=ButtonStyle.danger, emoji="🗑️")
    async def discard(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.parent.bot.database.monster_parts.delete_part(self.part.id)
        self.parent.inventory = [
            r for r in self.parent.inventory if r["id"] != self.part.id
        ]
        self.parent.inventory_parts = [
            create_monster_part(r) for r in self.parent.inventory
        ]
        self.parent._rebuild_select()
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        embed.set_footer(text="Part discarded.")
        await interaction.edit_original_response(embed=embed, view=self.parent)
        self.stop()

    @ui.button(label="Back", style=ButtonStyle.secondary, emoji="⬅️")
    async def back(self, interaction: Interaction, button: ui.Button):
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()


class PartSelect(ui.Select):
    def __init__(self, parts: list[MonsterPart]):
        options = [
            discord.SelectOption(
                label=p.display_name.replace("**", "")[:100],
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
        embed.set_thumbnail(url=CONSUME_SLOT_IMAGES.get(part.slot_type, CONSUME_HUB))
        detail_view = PartDetailView(self.view, part)
        await interaction.response.edit_message(embed=embed, view=detail_view)


class RecycleSelect(ui.Select):
    def __init__(self, parts: list[MonsterPart]):
        options = [
            discord.SelectOption(
                label=p.display_name.replace("**", "")[:100],
                description=f"ilvl {p.ilvl} — +{p.hp_value:,} Max HP",
                value=str(p.id),
                emoji=_SLOT_EMOJI.get(p.slot_type, "🫀"),
            )
            for p in parts[:25]
        ]
        super().__init__(
            placeholder="Choose 3 parts to recycle...",
            options=options,
            min_values=3,
            max_values=3,
        )
        self.parts_by_id = {p.id: p for p in parts}

    async def callback(self, interaction: Interaction):
        selected = [self.parts_by_id[int(v)] for v in self.values]
        new_hp = max(1, round(sum(p.hp_value for p in selected) * 1.05 / 3))
        confirm_view = RecycleConfirmView(self.view, selected, new_hp)
        embed = _build_recycle_confirm_embed(selected, new_hp)
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class RecycleView(BaseView):
    """Shows a multi-select for choosing exactly 3 parts to recycle."""

    def __init__(self, parent: "ConsumeView"):
        super().__init__(bot=parent.bot, parent=parent)
        self.parent = parent
        self._rebuild_select()

    def _rebuild_select(self):
        for item in self.children[:]:
            if isinstance(item, RecycleSelect):
                self.remove_item(item)
        if len(self.parent.inventory_parts) >= 3:
            self.add_item(RecycleSelect(self.parent.inventory_parts))

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()


class RecycleConfirmView(BaseView):
    """Previews the recycle result; Confirm destroys the 3 parts and adds the new one."""

    def __init__(
        self, recycle_view: "RecycleView", selected: list[MonsterPart], new_hp: int
    ):
        super().__init__(bot=recycle_view.bot, parent=recycle_view)
        self.consume_view: "ConsumeView" = recycle_view.parent
        self.recycle_view = recycle_view
        self.selected = selected
        self.new_hp = new_hp
        self._processing = False

    @ui.button(label="Confirm Recycle", style=ButtonStyle.success, emoji="♻️")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        name = random.choice(self.selected).monster_name
        slot = random.choices(_PART_SLOTS, weights=_PART_WEIGHTS, k=1)[0]
        avg_ilvl = round(sum(p.ilvl for p in self.selected) / 3)

        async with self.bot.database.transaction():
            for part in self.selected:
                await self.bot.database.monster_parts.delete_part(part.id)

            await self.bot.database.monster_parts.add_part(
                self.consume_view.user_id, slot, name, avg_ilvl, self.new_hp
            )

        self.consume_view.inventory = (
            await self.bot.database.monster_parts.get_inventory(
                self.consume_view.user_id
            )
        )
        self.consume_view.inventory_parts = [
            create_monster_part(r) for r in self.consume_view.inventory
        ]
        self.consume_view._rebuild_select()

        slot_label = _SLOT_LABELS.get(slot, slot)
        slot_emoji = _SLOT_EMOJI.get(slot, "🫀")
        embed = _build_main_embed(self.consume_view.player, self.consume_view.inventory)
        embed.set_footer(
            text=f"Recycled into {slot_emoji} {slot_label} — +{self.new_hp:,} Max HP!"
        )
        await interaction.edit_original_response(embed=embed, view=self.consume_view)
        self.stop()

    @ui.button(label="Back", style=ButtonStyle.secondary, emoji="⬅️")
    async def back(self, interaction: Interaction, button: ui.Button):
        recycle_view = RecycleView(self.consume_view)
        embed = _build_recycle_select_embed(len(self.consume_view.inventory))
        await interaction.response.edit_message(embed=embed, view=recycle_view)
        self.stop()


class EggSelect(ui.Select):
    def __init__(self, eggs: list):
        """eggs: list of (id, egg_tier, monster_level, monster_name) rows."""
        options = []
        for egg in eggs[:25]:
            tier = egg[1]
            emoji = _EGG_TIER_EMOJI.get(tier, "🥚")
            label = f"{_EGG_TIER_LABEL.get(tier, tier)} — lvl {egg[2]} {egg[3]}"
            options.append(
                discord.SelectOption(label=label[:100], value=str(egg[0]), emoji=emoji)
            )
        super().__init__(
            placeholder="Select an egg to consume...",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.eggs_by_id = {str(e[0]): e for e in eggs}

    async def callback(self, interaction: Interaction):
        egg = self.eggs_by_id.get(self.values[0])
        if not egg:
            return await interaction.response.send_message(
                "Egg not found.", ephemeral=True
            )

        tier = egg[1]
        lo, hi = _EGG_PASSIVE_POINTS[tier]
        points = random.randint(lo, hi)

        await self.view.bot.database.eggs.delete_egg(egg[0])
        await self.view.bot.database.users.modify_currency(
            self.view.user_id, "passive_points", points
        )

        # Refresh local egg list
        self.view.eggs = await self.view.bot.database.eggs.get_eggs(self.view.user_id)
        self.view._rebuild_select()

        embed = _build_egg_consume_embed(self.view.eggs)
        embed.set_footer(
            text=f"You consumed the egg and gained {points} passive point{'s' if points != 1 else ''}!"
        )
        await interaction.response.edit_message(embed=embed, view=self.view)


def _build_egg_consume_embed(eggs: list) -> discord.Embed:
    counts = {"normal": 0, "rare": 0, "giga": 0}
    for e in eggs:
        counts[e[1]] = counts.get(e[1], 0) + 1
    embed = discord.Embed(
        title="🥚 Consume Monster Eggs",
        description=(
            "Devour monster eggs to gain passive points.\n\n"
            f"🥚 Normal: **{counts['normal']}**  "
            f"🪺 Rare: **{counts['rare']}**  "
            f"🐲 Giga: **{counts['giga']}**\n\n"
            "**Passive Points Gained:**\n"
            "🥚 Normal: 1–5  |  🪺 Rare: 5–10  |  🐲 Giga: 10–20"
        ),
        color=0xB22222,
    )
    embed.set_thumbnail(url=CONSUME_EGG)
    return embed


class EggConsumeView(BaseView):
    def __init__(self, bot, parent: "ConsumeView", eggs: list):
        super().__init__(bot, parent=parent)
        self.parent = parent
        self.eggs = eggs
        self._rebuild_select()

    def _rebuild_select(self):
        for item in self.children[:]:
            if isinstance(item, EggSelect):
                self.remove_item(item)
        if self.eggs:
            self.add_item(EggSelect(self.eggs))

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        embed = _build_main_embed(self.parent.player, self.parent.inventory)
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()


class ConsumeView(BaseView):
    def __init__(self, player: Player, inventory: list, bot, eggs: list | None = None):
        super().__init__(bot=bot, user_id=str(player.id))
        self.player = player
        self.inventory = inventory  # raw DB rows
        self.inventory_parts = [create_monster_part(r) for r in inventory]
        self.eggs = eggs or []
        self.message = None
        self._rebuild_select()

    def _rebuild_select(self):
        # Remove existing select if present
        for item in self.children[:]:
            if isinstance(item, PartSelect):
                self.remove_item(item)
        if self.inventory_parts:
            self.add_item(PartSelect(self.inventory_parts))
        # Gate Hematurgy button until level 50
        if hasattr(self, "hematurgy"):
            self.hematurgy.disabled = self.player.level < 50

    def build_embed(self) -> discord.Embed:
        return _build_main_embed(self.player, self.inventory)

    @ui.button(label="Hematurgy", style=ButtonStyle.primary, emoji="🩸", row=1)
    async def hematurgy(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        passives = await self.bot.database.hematurgy.get_all_passives(self.user_id)
        blood = await self.bot.database.hematurgy.get_blood(self.user_id)
        from core.hematurgy.views import HematurgyView, _build_hematurgy_embed

        hview = HematurgyView(self.bot, passives, blood, parent=self)
        embed = _build_hematurgy_embed(passives, blood)
        await interaction.edit_original_response(embed=embed, view=hview)

    @ui.button(label="Consume Eggs", style=ButtonStyle.success, emoji="🥚", row=1)
    async def consume_eggs(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        eggs = await self.bot.database.eggs.get_eggs(self.user_id)
        if not eggs:
            return await interaction.followup.send(
                "You have no monster eggs to consume.", ephemeral=True
            )
        egg_view = EggConsumeView(self.bot, self, eggs)
        embed = _build_egg_consume_embed(eggs)
        await interaction.edit_original_response(embed=embed, view=egg_view)

    @ui.button(label="Recycle", style=ButtonStyle.primary, emoji="♻️", row=2)
    async def recycle(self, interaction: Interaction, button: ui.Button):
        if len(self.inventory_parts) < 3:
            return await interaction.response.send_message(
                "You need at least **3 parts** in your inventory to recycle.",
                ephemeral=True,
            )
        recycle_view = RecycleView(self)
        embed = _build_recycle_select_embed(len(self.inventory))
        await interaction.response.edit_message(embed=embed, view=recycle_view)

    @ui.button(label="Bulk Discard", style=ButtonStyle.danger, emoji="🗑️", row=2)
    async def bulk_discard(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(BulkDiscardModal(self))

    @ui.button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=2)
    async def exit(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()
