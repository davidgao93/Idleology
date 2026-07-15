import discord
from discord import ButtonStyle, Interaction

from core.emojis import RUNE_MIRAGE_IMPERFECT, RUNE_MIRAGE_PERFECT
from core.images import UPGRADE_MIRAGE
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.factory import (
    create_accessory,
    create_armor,
    create_boot,
    create_glove,
    create_helmet,
    create_weapon,
)
from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon

_FACTORIES = {
    "weapon": create_weapon,
    "armor": create_armor,
    "accessory": create_accessory,
    "glove": create_glove,
    "boot": create_boot,
    "helmet": create_helmet,
}


def _item_type_str(item) -> str:
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
    raise ValueError(f"Unknown item type: {type(item)}")


def _compute_name(source_name: str) -> str:
    base = source_name.removeprefix("Miraged ")
    return f"Miraged {base}"


def _describe_item(item, item_type: str) -> str:
    """Short stat summary for select option descriptions (max 100 chars)."""
    parts = []
    if item_type == "weapon":
        if item.attack:
            parts.append(f"ATK:{item.attack}")
        if item.defence:
            parts.append(f"DEF:{item.defence}")
        if item.rarity:
            parts.append(f"Rar:{item.rarity}%")
        if item.refinement_lvl:
            parts.append(f"+{item.refinement_lvl}")
    elif item_type == "armor":
        stat_label = "ATK" if getattr(item, "main_stat_type", "def") == "atk" else "DEF"
        if item.main_stat:
            parts.append(f"{stat_label}:{item.main_stat}")
        if item.block:
            parts.append(f"Block:{item.block}%")
        if item.evasion:
            parts.append(f"Eva:{item.evasion}%")
        if item.ward:
            parts.append(f"Ward:{item.ward}%")
        if item.reinforcement_lvl:
            parts.append(f"Reinf.Lv{item.reinforcement_lvl}")
    elif item_type == "accessory":
        if item.attack:
            parts.append(f"ATK:{item.attack}%")
        if item.defence:
            parts.append(f"DEF:{item.defence}%")
        if item.rarity:
            parts.append(f"Rar:{item.rarity}%")
        if item.ward:
            parts.append(f"Ward:{item.ward}%")
        if item.crit:
            parts.append(f"Crit:{item.crit}")
    elif item_type in ("glove", "boot"):
        if item.attack:
            parts.append(f"ATK:{item.attack}")
        if item.defence:
            parts.append(f"DEF:{item.defence}")
        if item.ward:
            parts.append(f"Ward:{item.ward}%")
        if item.pdr:
            parts.append(f"PDR:{item.pdr}%")
        if item.fdr:
            parts.append(f"FDR:{item.fdr}")
        if item.reinforcement_lvl:
            parts.append(f"Reinf.Lv{item.reinforcement_lvl}")
    elif item_type == "helmet":
        if item.defence:
            parts.append(f"DEF:{item.defence}")
        if item.ward:
            parts.append(f"Ward:{item.ward}%")
        if item.pdr:
            parts.append(f"PDR:{item.pdr}%")
        if item.fdr:
            parts.append(f"FDR:{item.fdr}")
        if item.reinforcement_lvl:
            parts.append(f"Reinf.Lv{item.reinforcement_lvl}")
    desc = " ".join(parts) or "No stats"
    return desc[:100]


def _stat_lines(item, item_type: str) -> list:
    """Returns formatted stat lines for an item to display in an embed field."""
    lines = []
    if item_type == "weapon":
        lines.append(f"ATK: {item.attack}")
        lines.append(f"DEF: {item.defence}")
        lines.append(f"Rarity: {item.rarity}%")
        lines.append(f"Refine Lv.{item.refinement_lvl}")
    elif item_type == "armor":
        stat_label = "ATK" if getattr(item, "main_stat_type", "def") == "atk" else "DEF"
        lines.append(f"{stat_label}: {item.main_stat}")
        lines.append(f"Block: {item.block}%")
        lines.append(f"Eva: {item.evasion}%")
        lines.append(f"Ward: {item.ward}%")
        lines.append(f"PDR: {item.pdr}%")
        lines.append(f"FDR: {item.fdr}")
        lines.append(f"Reinforce Lv.{item.reinforcement_lvl}")
    elif item_type == "accessory":
        lines.append(f"ATK: {item.attack}%")
        lines.append(f"DEF: {item.defence}%")
        lines.append(f"Rarity: {item.rarity}%")
        lines.append(f"Ward: {item.ward}%")
        lines.append(f"Crit: {item.crit}")
    elif item_type in ("glove", "boot"):
        lines.append(f"ATK: {item.attack}")
        lines.append(f"DEF: {item.defence}")
        lines.append(f"Ward: {item.ward}%")
        lines.append(f"PDR: {item.pdr}%")
        lines.append(f"FDR: {item.fdr}")
        lines.append(f"Reinforce Lv.{item.reinforcement_lvl}")
    elif item_type == "helmet":
        lines.append(f"DEF: {item.defence}")
        lines.append(f"Ward: {item.ward}%")
        lines.append(f"PDR: {item.pdr}%")
        lines.append(f"FDR: {item.fdr}")
        lines.append(f"Reinforce Lv.{item.reinforcement_lvl}")
    return lines


def _stat_lines_after(target, source, item_type: str, new_level: int) -> list:
    """Returns result stat lines, showing old → new for changed values."""

    def arrow(old, new, fmt=str):
        return f"{fmt(old)} → {fmt(new)}" if old != new else fmt(new)

    def pct(x):
        return f"{x}%"

    def lv(x):
        return f"Lv.{x}"

    lines = [f"Level: {arrow(target.level, new_level)}"]
    if item_type == "weapon":
        lines.append(f"ATK: {arrow(target.attack, source.attack)}")
        lines.append(f"DEF: {arrow(target.defence, source.defence)}")
        lines.append(f"Rarity: {arrow(target.rarity, source.rarity, pct)}")
        lines.append(
            f"Refine: {arrow(target.refinement_lvl, source.refinement_lvl, lv)}"
        )
    elif item_type == "armor":
        t_label = "ATK" if getattr(target, "main_stat_type", "def") == "atk" else "DEF"
        s_label = "ATK" if getattr(source, "main_stat_type", "def") == "atk" else "DEF"
        stat_label = s_label
        if t_label != s_label:
            lines.append(f"Stat type: {t_label} → {s_label}")
        lines.append(f"{stat_label}: {arrow(target.main_stat, source.main_stat)}")
        lines.append(f"Block: {arrow(target.block, source.block, pct)}")
        lines.append(f"Eva: {arrow(target.evasion, source.evasion, pct)}")
        lines.append(f"Ward: {arrow(target.ward, source.ward, pct)}")
        lines.append(f"PDR: {arrow(target.pdr, source.pdr, pct)}")
        lines.append(f"FDR: {arrow(target.fdr, source.fdr)}")
        lines.append(
            f"Reinforce: {arrow(target.reinforcement_lvl, source.reinforcement_lvl, lv)}"
        )
    elif item_type == "accessory":
        lines.append(f"ATK: {arrow(target.attack, source.attack, pct)}")
        lines.append(f"DEF: {arrow(target.defence, source.defence, pct)}")
        lines.append(f"Rarity: {arrow(target.rarity, source.rarity, pct)}")
        lines.append(f"Ward: {arrow(target.ward, source.ward, pct)}")
        lines.append(f"Crit: {arrow(target.crit, source.crit)}")
    elif item_type in ("glove", "boot"):
        lines.append(f"ATK: {arrow(target.attack, source.attack)}")
        lines.append(f"DEF: {arrow(target.defence, source.defence)}")
        lines.append(f"Ward: {arrow(target.ward, source.ward, pct)}")
        lines.append(f"PDR: {arrow(target.pdr, source.pdr, pct)}")
        lines.append(f"FDR: {arrow(target.fdr, source.fdr)}")
        lines.append(
            f"Reinforce: {arrow(target.reinforcement_lvl, source.reinforcement_lvl, lv)}"
        )
    elif item_type == "helmet":
        lines.append(f"DEF: {arrow(target.defence, source.defence)}")
        lines.append(f"Ward: {arrow(target.ward, source.ward, pct)}")
        lines.append(f"PDR: {arrow(target.pdr, source.pdr, pct)}")
        lines.append(f"FDR: {arrow(target.fdr, source.fdr)}")
        lines.append(
            f"Reinforce: {arrow(target.reinforcement_lvl, source.reinforcement_lvl, lv)}"
        )
    return lines


def _build_stat_fields(source, item_type: str) -> dict:
    """Build the DB column → value dict for the stat transfer."""
    if item_type == "weapon":
        return {
            "attack": source.attack,
            "defence": source.defence,
            "rarity": source.rarity,
            "refinement_lvl": source.refinement_lvl,
        }
    if item_type == "armor":
        return {
            "main_stat": source.main_stat,
            "main_stat_type": source.main_stat_type,
            "block": source.block,
            "evasion": source.evasion,
            "ward": source.ward,
            "pdr": source.pdr,
            "fdr": source.fdr,
            "reinforcement_lvl": source.reinforcement_lvl,
        }
    if item_type == "accessory":
        return {
            "attack": source.attack,
            "defence": source.defence,
            "rarity": source.rarity,
            "ward": source.ward,
            "crit": source.crit,
        }
    if item_type in ("glove", "boot"):
        return {
            "attack": source.attack,
            "defence": source.defence,
            "ward": source.ward,
            "pdr": source.pdr,
            "fdr": source.fdr,
            "reinforcement_lvl": source.reinforcement_lvl,
        }
    if item_type == "helmet":
        return {
            "defence": source.defence,
            "ward": source.ward,
            "pdr": source.pdr,
            "fdr": source.fdr,
            "reinforcement_lvl": source.reinforcement_lvl,
        }
    return {}


class MirageView(BaseUpgradeView):
    """
    Two-stage view for the Rune of Mirage.

    Stage 1: Player selects the source item (whose stats will be copied).
    Stage 2: Preview of the transfer with Imperfect / Perfected rune buttons.

    self.item is always the TARGET (the item being upgraded / viewed in the detail view).
    """

    def __init__(self, bot, user_id: str, item, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self.source = None
        self.candidates = []
        self.mirage_runes_imperfect = 0
        self.mirage_runes_perfected = 0
        self._processing = False

    # ------------------------------------------------------------------
    # Stage 1 — source selection
    # ------------------------------------------------------------------

    async def render(self, interaction: Interaction):
        self._processing = False
        self.source = None
        item_type = _item_type_str(self.item)
        factory = _FACTORIES[item_type]

        cur = await self.bot.database.users.get_all_currencies(self.user_id)
        self.mirage_runes_imperfect = cur["mirage_runes_imperfect"]
        self.mirage_runes_perfected = cur["mirage_runes_perfected"]

        rows = await self.bot.database.equipment.get_all(self.user_id, item_type)
        self.candidates = [
            factory(r) for r in rows if r["item_id"] != self.item.item_id
        ]

        if not self.candidates:
            await interaction.followup.send(
                "You need at least one other item of this type to use as a source.",
                ephemeral=True,
            )
            return

        options = []
        for c in self.candidates[:25]:
            equipped = getattr(c, "is_equipped", False)
            lbl = f"{'[E] ' if equipped else ''}Lv.{c.level} {c.name}"
            if len(lbl) > 100:
                lbl = lbl[:97] + "..."
            options.append(
                discord.SelectOption(
                    label=lbl,
                    value=str(c.item_id),
                    description=_describe_item(c, item_type),
                )
            )

        select = discord.ui.Select(
            placeholder="Select source item to copy stats from...",
            options=options,
        )
        select.callback = self._on_source_selected

        self.clear_items()
        self.add_item(select)
        self.add_back_button()

        rune_parts = []
        if self.mirage_runes_imperfect > 0:
            rune_parts.append(
                f"**Imperfect** x{self.mirage_runes_imperfect} — source item is destroyed"
            )
        if self.mirage_runes_perfected > 0:
            rune_parts.append(
                f"**Perfected** x{self.mirage_runes_perfected} — source item is preserved"
            )

        embed = discord.Embed(
            title=f"{RUNE_MIRAGE_PERFECT} Rune of Mirage",
            description=(
                f"**Selected:** Lv.{self.item.level} {self.item.name}\n\n"
                "Select an item to copy its **stats** onto this item.\n"
                "The target's passives and essences are untouched.\n\n"
                "**Runes available:**\n" + "\n".join(rune_parts)
            ),
            color=discord.Color.teal(),
        )
        embed.set_thumbnail(url=UPGRADE_MIRAGE)
        await self._send_render(interaction, embed)

    async def _on_source_selected(self, interaction: Interaction):
        source_id = int(interaction.data["values"][0])
        self.source = next((c for c in self.candidates if c.item_id == source_id), None)
        if not self.source:
            return
        await self._render_confirm(interaction)

    # ------------------------------------------------------------------
    # Stage 2 — preview + rune choice
    # ------------------------------------------------------------------

    async def _render_confirm(self, interaction: Interaction):
        item_type = _item_type_str(self.item)
        new_level = (self.source.level + self.item.level + 10) // 2
        new_name = _compute_name(self.source.name)

        source_field = "\n".join(_stat_lines(self.source, item_type)) or "—"
        target_field = "\n".join(_stat_lines(self.item, item_type)) or "—"
        result_field = (
            "\n".join(_stat_lines_after(self.item, self.source, item_type, new_level))
            or "—"
        )

        source_label = f"{'[E] ' if getattr(self.source, 'is_equipped', False) else ''}Lv.{self.source.level} {self.source.name}"

        embed = discord.Embed(
            title=f"{RUNE_MIRAGE_PERFECT} Rune of Mirage — Preview",
            color=discord.Color.teal(),
        )
        embed.set_thumbnail(url=UPGRADE_MIRAGE)
        embed.add_field(name=f"Source: {source_label}", value=source_field, inline=True)
        embed.add_field(
            name=f"Target: Lv.{self.item.level} {self.item.name}",
            value=target_field,
            inline=True,
        )
        embed.add_field(
            name=f"Result: {new_name} (Lv.{new_level})",
            value=result_field,
            inline=True,
        )
        embed.set_footer(text="Passives and essences on the target are preserved.")

        self.clear_items()

        if self.mirage_runes_imperfect > 0:
            btn = discord.ui.Button(
                label=f"Imperfect (x{self.mirage_runes_imperfect})",
                emoji=RUNE_MIRAGE_IMPERFECT,
                style=ButtonStyle.danger,
                row=0,
            )
            btn.callback = self._use_imperfect
            self.add_item(btn)

        if self.mirage_runes_perfected > 0:
            btn = discord.ui.Button(
                label=f"Perfected (x{self.mirage_runes_perfected})",
                emoji=RUNE_MIRAGE_PERFECT,
                style=ButtonStyle.primary,
                row=1,
            )
            btn.callback = self._use_perfected
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=2
        )
        back_btn.callback = self._back_to_stage1
        self.add_item(back_btn)  # intra-mirage stage navigation — do not clear

        await interaction.response.edit_message(embed=embed, view=self)

    async def _back_to_stage1(self, interaction: Interaction):
        await self.render(interaction)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def _use_imperfect(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        await self._apply_mirage(interaction, destroy_source=True)

    async def _use_perfected(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        await self._apply_mirage(interaction, destroy_source=False)

    async def _apply_mirage(self, interaction: Interaction, destroy_source: bool):
        item_type = _item_type_str(self.item)
        factory = _FACTORIES[item_type]

        new_level = (self.source.level + self.item.level + 10) // 2
        new_name = _compute_name(self.source.name)

        fields = _build_stat_fields(self.source, item_type)
        fields["item_level"] = new_level
        fields["item_name"] = new_name

        rune_col = (
            "mirage_runes_imperfect" if destroy_source else "mirage_runes_perfected"
        )
        async with self.bot.database.transaction():
            await self.bot.database.equipment.apply_mirage(
                self.item.item_id, item_type, fields
            )

            await self.bot.database.users.modify_currency(self.user_id, rune_col, -1)

            if destroy_source:
                if getattr(self.source, "is_equipped", False):
                    await self.bot.database.equipment.unequip(self.user_id, item_type)
                await self.bot.database.equipment.discard(
                    self.source.item_id, item_type
                )

        # Refresh self.item so the detail view shows updated stats
        new_row = await self.bot.database.equipment.get_by_id(
            self.item.item_id, item_type
        )
        self.item = factory(new_row)

        # Patch the GearView's all_items cache so the list reflects changes immediately
        inventory_view = self.parent_view.parent
        slot_list = inventory_view.all_items.get(item_type, [])
        for i, existing in enumerate(slot_list):
            if existing.item_id == self.item.item_id:
                slot_list[i] = self.item
                break
        if destroy_source:
            inventory_view.all_items[item_type] = [
                it for it in slot_list if it.item_id != self.source.item_id
            ]

        # Navigate back to a fresh detail view (interaction already deferred, so use edit_original_response)
        from core.inventory.inventory import InventoryUI
        from core.inventory.views import ItemDetailView

        new_detail = ItemDetailView(self.bot, self.user_id, self.item, inventory_view)
        await new_detail.fetch_data()

        is_equipped = self.item.item_id == inventory_view.equipped_id
        embed = InventoryUI.get_item_details_embed(self.item, is_equipped)
        await interaction.edit_original_response(
            content=None, embed=embed, view=new_detail
        )
        self.stop()
