"""
core/apex/views/imprint_view.py — Passive extraction (imprint) flow.

Browses the player's UN-EQUIPPED inventory (up to 60 items per slot) for gear
carrying a max-rank passive, then lets them extract it into the Soul Stone.

Navigation:
  Browse screen  → type select drives the item select (25 items/page); "← Back" returns to SoulStoneView
  Confirm screen → full item detail (ItemDetailView-level) + extraction chances;
                   "← Back" returns to browse; "Extract" shows result
  Result screen  → "Done" returns to SoulStoneView
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Select

from core.apex.data import PASSIVE_CATEGORY_MAP, PASSIVE_SHARD_MAP
from core.apex.mechanics import ApexMechanics
from core.apex.models import MetaShardInventory, ShardInventory, SoulStone
from core.base_view import BaseView
from core.images import APEX_IMPRINT
from core.items.factory import (
    create_accessory,
    create_armor,
    create_boot,
    create_glove,
    create_helmet,
    create_weapon,
)

# (display label, db item_type, emoji) — display order for the type select
_TYPE_DEFS: list[tuple[str, str, str]] = [
    ("Weapon", "weapon", "⚔️"),
    ("Armor", "armor", "🛡️"),
    ("Accessory", "accessory", "📿"),
    ("Glove", "glove", "🧤"),
    ("Boot", "boot", "👢"),
    ("Helmet", "helmet", "🎩"),
]

_FACTORY_FUNCS = {
    "weapon": create_weapon,
    "armor": create_armor,
    "accessory": create_accessory,
    "glove": create_glove,
    "boot": create_boot,
    "helmet": create_helmet,
}


class ImprintView(BaseView):
    """
    Imprint flow: pick an equipment type → pick a specific un-equipped item with a
    max-rank passive → see full item details + extraction chances → toggle meta
    shard usage → confirm extraction.
    """

    ITEMS_PER_PAGE = 25

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player,
        soul_stone: SoulStone,
        shards: ShardInventory,
        meta: MetaShardInventory,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.soul_stone = soul_stone
        self.shards = shards
        self.meta = meta
        self._processing = False
        self._loaded = False

        # Browse state — populated by load_candidates()
        self._by_type: dict[str, list[dict]] = {}
        self._selected_type: str | None = None
        self._item_page: int = 0

        # Confirm-screen selection
        self._selected_passive: str | None = None
        self._selected_item_name: str | None = None
        self._selected_item = None
        self._selected_passive_count: int = 0
        self._selected_has_corrupted: bool = False

        # Meta shard toggles — initialised when a passive is chosen
        self._use_fang: bool = False
        self._use_primal: bool = False
        self._use_vessel: bool = False

    # ------------------------------------------------------------------
    # Candidate gathering (async — reads unequipped inventory from the DB)
    # ------------------------------------------------------------------

    async def load_candidates(self) -> None:
        """Fetches every UN-equipped item across all 6 slots and buckets max-rank
        extractable passives by item type, excluding passives already imprinted."""
        already_imprinted: set[str] = set()
        if self.soul_stone:
            already_imprinted = {
                s.passive for s in self.soul_stone.slots if not s.is_empty
            }

        all_passive_attrs = (
            "passive",
            "p_passive",
            "u_passive",
            "infernal_passive",
            "celestial_passive",
            "void_passive",
        )

        by_type: dict[str, list[dict]] = {}
        for label, db_type, _emoji in _TYPE_DEFS:
            rows = await self.bot.database.equipment.get_all(self.user_id, db_type)
            factory_fn = _FACTORY_FUNCS[db_type]
            entries = []
            for row in rows:
                if row["is_equipped"]:
                    continue  # only unequipped items are eligible
                item = factory_fn(row)
                passives = ApexMechanics.get_extractable_passives(item)
                if not passives:
                    continue
                passive_count = sum(
                    1
                    for attr in all_passive_attrs
                    if getattr(item, attr, None) not in (None, "", "none")
                )
                has_corrupted = bool(
                    getattr(item, "corrupted_essence", None)
                    and getattr(item, "corrupted_essence", "none") not in ("none", "")
                )
                for p in passives:
                    if p in already_imprinted:
                        continue
                    entries.append(
                        {
                            "key": f"{item.item_id}:{p}",
                            "passive": p,
                            "item": item,
                            "item_name": item.name,
                            "level": item.level,
                            "passive_count": passive_count,
                            "has_corrupted": has_corrupted,
                        }
                    )
            if entries:
                by_type[label] = entries

        self._by_type = by_type
        self._build_browse_view()

    # ------------------------------------------------------------------
    # State 1 — Browse screen (type select drives item select)
    # ------------------------------------------------------------------

    def _build_browse_view(self):
        """Builds the type-select + item-select dropdowns for the browse screen."""
        self.clear_items()

        if not self._by_type:
            back = Button(label="← Back", style=ButtonStyle.secondary)
            back.callback = self._return_to_soul_stone
            self.add_item(back)
            return

        if self._selected_type not in self._by_type:
            self._selected_type = next(iter(self._by_type))
            self._item_page = 0

        type_options = [
            discord.SelectOption(
                label=f"{label} ({len(entries)} eligible)",
                value=label,
                emoji=emoji,
                default=(label == self._selected_type),
            )
            for label, _db, emoji in _TYPE_DEFS
            if (entries := self._by_type.get(label))
        ]
        type_select = Select(
            placeholder="Choose an item type…",
            options=type_options,
            min_values=1,
            max_values=1,
            row=0,
        )
        type_select.callback = self._on_type_select
        self.add_item(type_select)

        entries = self._by_type[self._selected_type]
        per_page = self.ITEMS_PER_PAGE
        total_pages = max(1, (len(entries) + per_page - 1) // per_page)
        self._item_page = max(0, min(self._item_page, total_pages - 1))
        start = self._item_page * per_page
        page_entries = entries[start : start + per_page]

        item_options = []
        for e in page_entries:
            passive_display = e["passive"].replace("-", " ").replace("_", " ").title()
            item_options.append(
                discord.SelectOption(
                    label=f"Lv.{e['level']} {e['item_name']}"[:100],
                    value=e["key"],
                    description=f"Passive: {passive_display}"[:100],
                    emoji="💎",
                )
            )
        item_select = Select(
            placeholder="Choose an item to extract from…",
            options=item_options,
            min_values=1,
            max_values=1,
            row=1,
        )
        item_select.callback = self._on_item_select
        self.add_item(item_select)

        if total_pages > 1:
            prev_btn = Button(
                label="◀ Prev",
                style=ButtonStyle.secondary,
                row=2,
                disabled=(self._item_page == 0),
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)

            page_label = Button(
                label=f"Page {self._item_page + 1}/{total_pages}",
                style=ButtonStyle.secondary,
                row=2,
                disabled=True,
            )
            self.add_item(page_label)

            next_btn = Button(
                label="Next ▶",
                style=ButtonStyle.secondary,
                row=2,
                disabled=(self._item_page >= total_pages - 1),
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)

        back = Button(label="← Back", style=ButtonStyle.secondary, row=3)
        back.callback = self._return_to_soul_stone
        self.add_item(back)

    async def _on_type_select(self, interaction: Interaction):
        await interaction.response.defer()
        self._selected_type = interaction.data["values"][0]
        self._item_page = 0
        self._build_browse_view()
        await interaction.edit_original_response(
            embed=self.build_browse_embed(), view=self
        )

    async def _prev_page(self, interaction: Interaction):
        await interaction.response.defer()
        self._item_page = max(0, self._item_page - 1)
        self._build_browse_view()
        await interaction.edit_original_response(
            embed=self.build_browse_embed(), view=self
        )

    async def _next_page(self, interaction: Interaction):
        await interaction.response.defer()
        self._item_page += 1
        self._build_browse_view()
        await interaction.edit_original_response(
            embed=self.build_browse_embed(), view=self
        )

    async def _on_item_select(self, interaction: Interaction):
        await interaction.response.defer()
        sel_key = interaction.data["values"][0]

        entries = self._by_type.get(self._selected_type, [])
        match = next((e for e in entries if e["key"] == sel_key), None)
        if not match:
            return

        self._selected_passive = match["passive"]
        self._selected_item_name = match["item_name"]
        self._selected_item = match["item"]
        self._selected_passive_count = match["passive_count"]
        self._selected_has_corrupted = match["has_corrupted"]

        # Default: opt in to any available meta shards
        self._use_fang = bool(self.meta.sharpened_fang)
        self._use_primal = bool(self.meta.primal_essence)
        self._use_vessel = bool(self.meta.soul_vessel)

        self._build_confirm_buttons()
        embed = self._build_confirm_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    # ------------------------------------------------------------------
    # State 2 — Confirm screen
    # ------------------------------------------------------------------

    def _build_confirm_buttons(self):
        """Rebuilds buttons for the confirm screen including meta shard toggles."""
        self.clear_items()

        shard_type = PASSIVE_SHARD_MAP.get(self._selected_passive, "fortune")
        has_shard = self.shards.get(shard_type) >= 1

        # Row 0 — primary actions
        confirm = Button(
            label="Extract",
            style=ButtonStyle.danger,
            emoji="🔏",
            row=0,
            disabled=not has_shard,
        )
        confirm.callback = self._confirm_extract
        self.add_item(confirm)

        back = Button(label="← Back", style=ButtonStyle.secondary, row=0)
        back.callback = self._back_to_browse
        self.add_item(back)

        # Row 1 — meta shard toggles (only shown when player has the shard)
        if self.meta.sharpened_fang:
            style = ButtonStyle.success if self._use_fang else ButtonStyle.secondary
            fang_btn = Button(
                label=f"🦷 Fang ({'ON' if self._use_fang else 'OFF'})",
                style=style,
                row=1,
            )
            fang_btn.callback = self._toggle_fang
            self.add_item(fang_btn)

        if self.meta.primal_essence:
            style = ButtonStyle.success if self._use_primal else ButtonStyle.secondary
            primal_btn = Button(
                label=f"✨ Primal ({'ON' if self._use_primal else 'OFF'})",
                style=style,
                row=1,
            )
            primal_btn.callback = self._toggle_primal
            self.add_item(primal_btn)

        if self.meta.soul_vessel:
            style = ButtonStyle.success if self._use_vessel else ButtonStyle.secondary
            vessel_btn = Button(
                label=f"🏺 Vessel ({'ON' if self._use_vessel else 'OFF'})",
                style=style,
                row=1,
            )
            vessel_btn.callback = self._toggle_vessel
            self.add_item(vessel_btn)

    def _build_confirm_embed(self) -> discord.Embed:
        from core.inventory.inventory import InventoryUI

        passive_display = (
            self._selected_passive.replace("-", " ").replace("_", " ").title()
        )
        primal_count = self.meta.primal_essence if self._use_primal else 0
        fang = self._use_fang
        vessel = self._use_vessel

        base_chance = ApexMechanics.extraction_chance(
            self._selected_passive_count,
            self._selected_has_corrupted,
            primal_count,
        )
        lucky_chance = 1.0 - (1.0 - base_chance) ** 2

        shard_type = PASSIVE_SHARD_MAP.get(self._selected_passive, "fortune")
        cat = PASSIVE_CATEGORY_MAP.get(self._selected_passive, "utility")

        # Full item detail — same builder as the gear command's Item Detail View
        embed = InventoryUI.get_item_details_embed(self._selected_item, is_equipped=False)
        embed.title = f"🔏 Extract {passive_display} — {embed.title}"
        embed.color = 0x9900CC
        embed.set_thumbnail(url=APEX_IMPRINT)

        # Check target slot early so we can warn
        first_empty = self.soul_stone.first_empty_slot
        if first_empty is None:
            embed.add_field(
                name="⚠️ No Empty Slots",
                value="All soul stone slots are occupied. Clear a slot before imprinting.",
                inline=False,
            )
            embed.color = 0xCC0000
            return embed

        # Extraction chance
        chance_lines = [f"Base: **{base_chance * 100:.1f}%**"]
        if fang:
            chance_lines.append(
                f"With Sharpened Fang: **{lucky_chance * 100:.1f}%** *(lucky roll)*"
            )
        detail_parts = [f"{self._selected_passive_count} passives"]
        if self._selected_has_corrupted:
            detail_parts.append("corrupted essence")
        if self._use_primal and self.meta.primal_essence:
            detail_parts.append(f"{self.meta.primal_essence}x Primal Essence")
        chance_lines.append(f"*Based on: {', '.join(detail_parts)}*")
        embed.add_field(
            name="📊 Extraction Chance", value="\n".join(chance_lines), inline=False
        )

        shard_owned = self.shards.get(shard_type)
        embed.add_field(
            name="💰 Cost",
            value=f"1x {shard_type.title()} Shard (Owned: {shard_owned})",
            inline=True,
        )
        embed.add_field(name="🔮 Shard Type", value=shard_type.title(), inline=True)
        embed.add_field(name="⚡ Category", value=cat.capitalize(), inline=True)
        embed.add_field(name="📍 Target Slot", value=f"Slot {first_empty}", inline=True)

        if shard_owned < 1:
            embed.add_field(
                name="⚠️ Insufficient Shards",
                value=f"You need at least 1 {shard_type.title()} Shard to begin the imprint.",
                inline=False,
            )

        destruction_note = (
            "🏺 **Soul Vessel active** — the item is preserved regardless of outcome."
            if vessel
            else "⚠️ **The item will be destroyed** on the extraction attempt."
        )
        embed.add_field(name="⚠️ Warning", value=destruction_note, inline=False)

        # Active meta shard hints
        if (
            self.meta.sharpened_fang
            or self.meta.primal_essence
            or self.meta.soul_vessel
        ):
            embed.set_footer(
                text="Toggle meta shards below to adjust how they're applied."
            )

        return embed

    async def _toggle_fang(self, interaction: Interaction):
        await interaction.response.defer()
        self._use_fang = not self._use_fang
        self._build_confirm_buttons()
        await interaction.edit_original_response(
            embed=self._build_confirm_embed(), view=self
        )

    async def _toggle_primal(self, interaction: Interaction):
        await interaction.response.defer()
        self._use_primal = not self._use_primal
        self._build_confirm_buttons()
        await interaction.edit_original_response(
            embed=self._build_confirm_embed(), view=self
        )

    async def _toggle_vessel(self, interaction: Interaction):
        await interaction.response.defer()
        self._use_vessel = not self._use_vessel
        self._build_confirm_buttons()
        await interaction.edit_original_response(
            embed=self._build_confirm_embed(), view=self
        )

    async def _back_to_browse(self, interaction: Interaction):
        """Returns from confirm back to the browse screen."""
        await interaction.response.defer()
        self._selected_passive = None
        self._selected_item_name = None
        self._selected_item = None
        self._build_browse_view()
        await interaction.edit_original_response(
            embed=self.build_browse_embed(), view=self
        )

    # ------------------------------------------------------------------
    # Extraction logic
    # ------------------------------------------------------------------

    async def _confirm_extract(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        if not self._selected_passive:
            self._processing = False
            return

        first_empty = self.soul_stone.first_empty_slot
        if first_empty is None:
            await interaction.edit_original_response(
                content="No empty slots available. Clear a slot first.",
                embed=None,
                view=None,
            )
            self.stop()
            return

        shard_type = PASSIVE_SHARD_MAP.get(self._selected_passive, "fortune")
        paid = await self.bot.database.apex.deduct_upgrade_cost(
            self.user_id, self.server_id, shard_type, 1, 0
        )
        if not paid:
            self._processing = False
            self._build_confirm_buttons()
            await interaction.edit_original_response(
                embed=self._build_confirm_embed(), view=self
            )
            return

        primal_count = self.meta.primal_essence if self._use_primal else 0
        fang = self._use_fang
        vessel = self._use_vessel

        base_chance = ApexMechanics.extraction_chance(
            self._selected_passive_count,
            self._selected_has_corrupted,
            primal_count,
        )
        success = ApexMechanics.roll_extraction(base_chance, fang)

        # Consume Sharpened Fang if toggled on
        if fang:
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, "sharpened_fang", -1
            )

        # Consume all Primal Essence stacks if toggled on
        if self._use_primal and primal_count > 0:
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, "primal_essence", -primal_count
            )

        # Item destruction / Soul Vessel handling
        # Soul Vessel protects the item regardless of success or failure — always consumed.
        if vessel:
            # Consume the vessel; item survives no matter what
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, "soul_vessel", -1
            )
        else:
            # No vessel — item is destroyed on any attempt (success or failure)
            await self._destroy_item(self._selected_item)

        # Build result embed
        if success:
            passive_key = self._selected_passive
            category = PASSIVE_CATEGORY_MAP.get(passive_key, "utility")
            await self.bot.database.apex.set_slot(
                self.user_id, self.server_id, first_empty, passive_key, 1, category
            )
            passive_display = passive_key.replace("-", " ").replace("_", " ").title()
            result_title = "✅ Extraction Successful!"
            result_desc = (
                f"**{passive_display}** (T1) has been imprinted into Slot {first_empty}!\n"
                + (
                    "🏺 Soul Vessel preserved the item."
                    if vessel
                    else "⚠️ The item was destroyed."
                )
            )
            color = 0x00CC44
        else:
            result_title = "❌ Extraction Failed"
            result_desc = (
                "The passive could not be extracted.\n"
                + (
                    "🏺 Soul Vessel preserved the item."
                    if vessel
                    else "⚠️ The item was destroyed."
                )
                + f"\n*(Base chance was {base_chance * 100:.1f}%)*"
            )
            color = 0xCC0000

        embed = discord.Embed(title=result_title, description=result_desc, color=color)
        embed.set_thumbnail(url=APEX_IMPRINT)
        embed.set_footer(text=f"1x {shard_type.title()} Shard consumed to begin the imprint.")

        # Add "Done" button to navigate back to soul stone
        self.clear_items()
        done_btn = Button(label="Done", style=ButtonStyle.secondary)
        done_btn.callback = self._return_to_soul_stone
        self.add_item(done_btn)

        await interaction.edit_original_response(embed=embed, view=self)

    # ------------------------------------------------------------------
    # Item destruction
    # ------------------------------------------------------------------

    async def _destroy_item(self, item) -> None:
        """Attempts to delete the item from the DB (best-effort)."""
        if not item:
            return
        item_id = getattr(item, "item_id", None)
        if not item_id:
            return
        _type_map = {
            "Weapon": "weapon",
            "Armor": "armor",
            "Accessory": "accessory",
            "Glove": "glove",
            "Boot": "boot",
            "Helmet": "helmet",
        }
        item_type = _type_map.get(type(item).__name__)
        if item_type:
            try:
                await self.bot.database.equipment.discard(item_id, item_type)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    async def _return_to_soul_stone(self, interaction: Interaction):
        """Rebuilds and transitions back to the SoulStoneView with fresh DB data."""
        await interaction.response.defer()

        from core.apex.models import (
            meta_shards_from_db,
            shards_from_db,
            soul_stone_from_db,
        )
        from core.apex.views.soul_stone_view import (
            SoulStoneView,
            _build_soul_stone_embed,
        )

        ss_row = await self.bot.database.apex.get_or_create_soul_stone(
            self.user_id, self.server_id
        )
        shards_row = await self.bot.database.apex.get_or_create_shards(
            self.user_id, self.server_id
        )
        meta_row = await self.bot.database.apex.get_or_create_meta_shards(
            self.user_id, self.server_id
        )
        soul_stone = soul_stone_from_db(ss_row)
        shards = shards_from_db(shards_row)
        meta = meta_shards_from_db(meta_row)

        view = SoulStoneView(self.bot, self.user_id, self.server_id, self.player)
        embed = _build_soul_stone_embed(soul_stone, shards, meta, self.player.name)
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = await interaction.original_response()
        self.stop()

    # ------------------------------------------------------------------
    # Initial overview embed (State 1 — browse screen)
    # ------------------------------------------------------------------

    async def build_embed(self) -> discord.Embed:
        """Entry point called by SoulStoneView — loads candidates once, then
        returns the browse embed."""
        if not self._loaded:
            await self.load_candidates()
            self._loaded = True
        return self.build_browse_embed()

    def build_browse_embed(self) -> discord.Embed:
        if not self._by_type:
            embed = discord.Embed(
                title="🔏 Imprint — No Eligible Passives",
                description=(
                    "None of your un-equipped items have passives at the required max rank for "
                    "extraction, or all eligible passives are already imprinted in your Soul Stone.\n\n"
                    "**Requirements:**\n"
                    "• Weapon: forged passive at Tier 5 (e.g. Burning 5)\n"
                    "• Armor: any imbued passive\n"
                    "• Accessory: enchanted to Lv.10\n"
                    "• Glove / Helmet: enchanted to Lv.5\n"
                    "• Boot: enchanted to Lv.6"
                ),
                color=0xCC6600,
            )
            embed.set_thumbnail(url=APEX_IMPRINT)
            return embed

        embed = discord.Embed(
            title="🔏 Imprint",
            description=(
                "Choose an item type, then a specific **un-equipped** item to extract its "
                "max-rank passive into the Soul Stone.\n\n"
                "**⚠️ The item is destroyed** on the extraction attempt "
                "(unless Soul Vessel is active — it preserves the item regardless of outcome).\n"
                "**💰 Costs 1 shard** of the passive's matching type to begin the imprint attempt."
            ),
            color=0x9900CC,
        )
        embed.set_thumbnail(url=APEX_IMPRINT)

        # Show current soul stone slot state
        slot_lines = []
        for i, slot in enumerate(self.soul_stone.slots, 1):
            if slot.is_empty:
                slot_lines.append(f"**Slot {i}:** *(empty — available for imprint)*")
            else:
                passive_display = (
                    slot.passive.replace("-", " ").replace("_", " ").title()
                )
                slot_lines.append(
                    f"**Slot {i}:** {passive_display} T{slot.tier} *(occupied)*"
                )
        embed.add_field(
            name="💎 Current Slots", value="\n".join(slot_lines), inline=False
        )

        # Shard Inventory / Meta Shards — only shown here and in UpgradeView, not
        # on the Soul Stone hub itself (only relevant once you're spending shards).
        from core.apex.views.soul_stone_view import (
            add_meta_shards_field,
            add_shard_inventory_field,
        )

        add_shard_inventory_field(embed, self.shards)
        add_meta_shards_field(embed, self.meta)
        embed.set_footer(text="Toggle meta shard usage on the confirm screen.")

        return embed
