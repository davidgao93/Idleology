"""
core/apex/views/imprint_view.py — Passive extraction (imprint) flow.

Shows the player's extractable (max-rank) passives from equipped gear, with full item
details and meta shard opt-in toggles, then lets them confirm the extraction.

Navigation:
  Select screen → "← Back" returns to SoulStoneView
  Confirm screen → "← Back" returns to select; "Extract" shows result
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


class ImprintView(BaseView):
    """
    Imprint flow: select a max-rank passive from equipped gear → see item details +
    extraction chances → toggle meta shard usage → confirm extraction.
    """

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

        self._candidates = self._gather_candidates()
        self._selected_passive: str | None = None
        self._selected_item_name: str | None = None
        self._selected_item = None
        self._selected_passive_count: int = 0
        self._selected_has_corrupted: bool = False

        # Meta shard toggles — initialised when a passive is chosen
        self._use_fang: bool = False
        self._use_primal: bool = False
        self._use_vessel: bool = False

        self._build_select()

    # ------------------------------------------------------------------
    # Candidate gathering
    # ------------------------------------------------------------------

    def _gather_candidates(self) -> list[dict]:
        """Returns all max-rank extractable passives from equipped gear,
        excluding any passive already imprinted in the soul stone."""
        # Build the set of passives already occupying a soul stone slot
        already_imprinted: set[str] = set()
        if self.soul_stone:
            already_imprinted = {
                s.passive for s in self.soul_stone.slots if not s.is_empty
            }

        candidates = []
        gear_items = [
            (self.player.equipped_weapon, "Weapon"),
            (self.player.equipped_armor, "Armor"),
            (self.player.equipped_accessory, "Accessory"),
            (self.player.equipped_glove, "Glove"),
            (self.player.equipped_boot, "Boot"),
            (self.player.equipped_helmet, "Helmet"),
        ]
        for item, item_type in gear_items:
            if not item:
                continue
            passives = ApexMechanics.get_extractable_passives(item)
            if not passives:
                continue  # no max-rank passives — skip this item entirely
            # passive_count for extraction chance = ALL non-empty passives (investment measure)
            all_passive_attrs = (
                "passive",
                "p_passive",
                "u_passive",
                "infernal_passive",
                "celestial_passive",
                "void_passive",
            )
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
                    continue  # already imprinted — not eligible
                candidates.append(
                    {
                        "passive": p,
                        "item_type": item_type,
                        "item": item,
                        "item_name": getattr(item, "name", item_type),
                        "passive_count": passive_count,
                        "has_corrupted": has_corrupted,
                    }
                )
        return candidates

    # ------------------------------------------------------------------
    # State 1 — Select screen
    # ------------------------------------------------------------------

    def _build_select(self):
        """Builds the item/passive selection dropdown."""
        self.clear_items()

        if not self._candidates:
            return

        options = []
        seen: set[str] = set()
        for c in self._candidates[:25]:
            key = f"{c['passive']}_{c['item_type']}"
            if key in seen:
                continue
            seen.add(key)
            passive_display = c["passive"].replace("-", " ").replace("_", " ").title()
            item = c["item"]
            item_level = getattr(item, "level", "?")
            item_name = c.get("item_name") or c["item_type"]
            options.append(
                discord.SelectOption(
                    label=f"{c['item_type']}: {item_name[:40]}",
                    value=key,
                    description=f"Extract: {passive_display} (Lv.{item_level})",
                    emoji="💎",
                )
            )

        if not options:
            return

        select = Select(
            placeholder="Choose an item to extract from…",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

        back = Button(label="← Back", style=ButtonStyle.secondary)
        back.callback = self._return_to_soul_stone
        self.add_item(back)

    async def _on_select(self, interaction: Interaction):
        await interaction.response.defer()
        sel_key = interaction.data["values"][0]

        for c in self._candidates:
            key = f"{c['passive']}_{c['item_type']}"
            if key == sel_key:
                self._selected_passive = c["passive"]
                self._selected_item_name = c.get("item_name") or c["item_type"]
                self._selected_item = c["item"]
                self._selected_passive_count = c["passive_count"]
                self._selected_has_corrupted = c["has_corrupted"]
                break

        if not self._selected_passive:
            return

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

        # Row 0 — primary actions
        confirm = Button(label="Extract", style=ButtonStyle.danger, emoji="🔏", row=0)
        confirm.callback = self._confirm_extract
        self.add_item(confirm)

        back = Button(label="← Back", style=ButtonStyle.secondary, row=0)
        back.callback = self._back_to_select
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

        embed = discord.Embed(
            title=f"Extract: {passive_display}",
            description=f"From: **{self._selected_item_name}**",
            color=0x9900CC,
        )
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

        # Full item stats
        from core.inventory.inventory import InventoryUI

        item_level = getattr(self._selected_item, "level", "?")
        stats_str = InventoryUI._build_equipped_stats(self._selected_item)
        embed.add_field(
            name=f"📦 {self._selected_item_name} (Lv.{item_level})",
            value=stats_str or "No stats",
            inline=False,
        )

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

        embed.add_field(name="🔮 Shard Type", value=shard_type.title(), inline=True)
        embed.add_field(name="⚡ Category", value=cat.capitalize(), inline=True)
        embed.add_field(name="📍 Target Slot", value=f"Slot {first_empty}", inline=True)

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
            meta_hint = "Toggle meta shards below to adjust how they're applied."
            embed.set_footer(text=meta_hint)

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

    async def _back_to_select(self, interaction: Interaction):
        """Returns from confirm back to the passive selection dropdown."""
        await interaction.response.defer()
        self._selected_passive = None
        self._selected_item_name = None
        self._selected_item = None
        self._build_select()
        embed = await self.build_embed()
        await interaction.edit_original_response(embed=embed, view=self)

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
        item_destroyed = False
        if vessel:
            # Consume the vessel; item survives no matter what
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, "soul_vessel", -1
            )
        else:
            # No vessel — item is destroyed on any attempt (success or failure)
            item_destroyed = True
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
                f"The passive could not be extracted.\n"
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
        item_id = getattr(item, "id", None)
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

        from core.items.factory import load_player
        from core.apex.models import (
            soul_stone_from_db,
            shards_from_db,
            meta_shards_from_db,
        )
        from core.apex.views.soul_stone_view import (
            SoulStoneView,
            _build_soul_stone_embed,
        )

        # Reload player to reflect any item destruction that occurred
        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        player = await load_player(self.user_id, user_row, self.bot.database)

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

        view = SoulStoneView(self.bot, self.user_id, self.server_id, player)
        embed = _build_soul_stone_embed(soul_stone, shards, meta, player.name)
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = await interaction.original_response()
        self.stop()

    # ------------------------------------------------------------------
    # Initial overview embed (State 1)
    # ------------------------------------------------------------------

    async def build_embed(self) -> discord.Embed:
        if not self._candidates:
            embed = discord.Embed(
                title="🔏 Imprint — No Eligible Passives",
                description=(
                    "None of your equipped items have passives at the required max rank for extraction, "
                    "or all eligible passives are already imprinted in your Soul Stone.\n\n"
                    "**Requirements:**\n"
                    "• Weapon: passive at Tier 5 (e.g. Burning 5)\n"
                    "• Armor: any rank (single-tier passives always eligible)\n"
                    "• Accessory / Jewelry: passive Lv.10\n"
                    "• Glove / Helmet: passive Lv.5\n"
                    "• Boot: passive Lv.6"
                ),
                color=0xCC6600,
            )
            embed.set_thumbnail(url=APEX_IMPRINT)
            return embed

        embed = discord.Embed(
            title="🔏 Imprint",
            description=(
                "Select an item to extract its max-rank passive into the Soul Stone.\n\n"
                "**⚠️ The item is destroyed** on the extraction attempt "
                "(unless Soul Vessel is active — it preserves the item regardless of outcome)."
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

        # Active meta shard summary
        meta_parts = []
        if self.meta.sharpened_fang:
            meta_parts.append(f"🦷 Sharpened Fang ×{self.meta.sharpened_fang}")
        if self.meta.primal_essence:
            meta_parts.append(f"✨ Primal Essence ×{self.meta.primal_essence}")
        if self.meta.soul_vessel:
            meta_parts.append(f"🏺 Soul Vessel ×{self.meta.soul_vessel}")
        if meta_parts:
            embed.add_field(
                name="🔮 Available Meta Shards",
                value="\n".join(meta_parts) + "\n*Toggle usage on the confirm screen.*",
                inline=False,
            )

        return embed
