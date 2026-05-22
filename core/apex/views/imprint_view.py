"""
core/apex/views/imprint_view.py — Passive extraction (imprint) flow.

Shows the player's extractable passives from equipped gear, the extraction chance,
and lets them choose which passive to extract.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Select

from core.apex.data import PASSIVE_CATEGORY_MAP, PASSIVE_SHARD_MAP, UPGRADE_COSTS
from core.apex.mechanics import ApexMechanics
from core.apex.models import MetaShardInventory, ShardInventory, SoulStone
from core.base_view import BaseView
from core.images import APEX_IMPRINT


class ImprintView(BaseView):
    """
    Imprint flow: select a passive from equipped gear → see chances → confirm extraction.
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
        *,
        parent=None,
    ):
        super().__init__(bot, parent=parent)
        self.player = player
        self.soul_stone = soul_stone
        self.shards = shards
        self.meta = meta
        self._processing = False

        self._candidates = self._gather_candidates()
        self._selected_passive: str | None = None
        self._selected_item_name: str | None = None
        self._selected_item = None

        self._build_select()

    # ------------------------------------------------------------------

    def _gather_candidates(self) -> list[dict]:
        """Returns all extractable passives from equipped gear."""
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
            # Count gear passives for extraction chance
            passive_count = len(passives)
            has_corrupted = bool(getattr(item, "corrupted_essence", None) and
                                 getattr(item, "corrupted_essence", "none") not in ("none", ""))
            for p in passives:
                candidates.append({
                    "passive": p,
                    "item_type": item_type,
                    "item": item,
                    "item_name": getattr(item, "name", item_type),
                    "passive_count": passive_count,
                    "has_corrupted": has_corrupted,
                })
        return candidates

    def _build_select(self):
        """Builds the passive-selection dropdown (max 25 options)."""
        # Clear existing children and re-add
        self.clear_items()

        if not self._candidates:
            return  # No candidates — embed will show warning

        options = []
        seen: set[str] = set()
        for c in self._candidates[:25]:
            key = f"{c['passive']}_{c['item_type']}"
            if key in seen:
                continue
            seen.add(key)
            passive_display = c["passive"].replace("-", " ").replace("_", " ").title()
            shard = PASSIVE_SHARD_MAP.get(c["passive"], "fortune")
            cat = PASSIVE_CATEGORY_MAP.get(c["passive"], "utility")
            options.append(discord.SelectOption(
                label=f"{passive_display} ({c['item_type']})",
                value=key,
                description=f"Shard: {shard.title()} | Category: {cat.capitalize()}",
                emoji="💎",
            ))

        if not options:
            return

        select = Select(
            placeholder="Choose a passive to extract…",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

        # Cancel
        cancel = Button(label="Cancel", style=ButtonStyle.secondary)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _on_select(self, interaction: Interaction):
        await interaction.response.defer()
        sel_key = interaction.data["values"][0]

        # Find the candidate matching the selection
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

        embed = self._build_confirm_embed()
        # Replace select with confirm/cancel
        self.clear_items()
        confirm = Button(label="Extract", style=ButtonStyle.danger, emoji="🔏")
        confirm.callback = self._confirm_extract
        self.add_item(confirm)
        cancel = Button(label="Back", style=ButtonStyle.secondary)
        cancel.callback = self._cancel
        self.add_item(cancel)

        await interaction.edit_original_response(embed=embed, view=self)

    def _build_confirm_embed(self) -> discord.Embed:
        passive_display = self._selected_passive.replace("-", " ").replace("_", " ").title()
        primal_count = self.meta.primal_essence
        fang = bool(self.meta.sharpened_fang)
        vessel = bool(self.meta.soul_vessel)

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

        # Check target slot
        first_empty = self.soul_stone.first_empty_slot
        if first_empty is None:
            embed.add_field(
                name="⚠️ No Empty Slots",
                value="All soul stone slots are occupied. Clear a slot before imprinting.",
                inline=False,
            )
            embed.color = 0xCC0000
            return embed

        embed.add_field(
            name="📊 Extraction Chance",
            value=(
                f"Base: **{base_chance*100:.1f}%**\n"
                + (f"With Sharpened Fang: **{lucky_chance*100:.1f}%** *(lucky)*\n" if fang else "")
                + f"\n*Based on {self._selected_passive_count} passives"
                + (" + corrupted essence" if self._selected_has_corrupted else "")
                + (f" + {primal_count}x Primal Essence" if primal_count else "")
                + "*"
            ),
            inline=False,
        )

        embed.add_field(name="🔮 Shard Type", value=shard_type.title(), inline=True)
        embed.add_field(name="⚡ Category", value=cat.capitalize(), inline=True)
        embed.add_field(name="📍 Target Slot", value=f"Slot {first_empty}", inline=True)

        destruction_note = (
            "⚠️ **The item will be destroyed** on extract attempt."
            if not vessel else
            "🏺 **Soul Vessel** — the item is preserved on success!"
        )
        embed.add_field(name="⚠️ Warning", value=destruction_note, inline=False)

        if fang:
            embed.add_field(
                name="🦷 Sharpened Fang",
                value="Will be consumed to boost extraction luck.",
                inline=False,
            )

        return embed

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
                content="No empty slots available. Clear a slot first.", embed=None, view=None
            )
            self.stop()
            return

        primal_count = self.meta.primal_essence
        fang = bool(self.meta.sharpened_fang)
        vessel = bool(self.meta.soul_vessel)

        base_chance = ApexMechanics.extraction_chance(
            self._selected_passive_count,
            self._selected_has_corrupted,
            primal_count,
        )
        success = ApexMechanics.roll_extraction(base_chance, fang)

        # Consume Sharpened Fang if used
        if fang:
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, "sharpened_fang", -1
            )

        # Consume Primal Essence (each one was counted in extraction_chance)
        if primal_count > 0:
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, "primal_essence", -primal_count
            )

        # Destroy item unless Soul Vessel succeeds
        item_destroyed = False
        if success:
            if not vessel:
                item_destroyed = True
                await self._destroy_item(self._selected_item)
            else:
                # Consume Soul Vessel
                await self.bot.database.apex.modify_meta_shard(
                    self.user_id, self.server_id, "soul_vessel", -1
                )
        else:
            # Always destroy on failure
            item_destroyed = True
            await self._destroy_item(self._selected_item)

        if success:
            passive_key = self._selected_passive
            tier = 1
            category = PASSIVE_CATEGORY_MAP.get(passive_key, "utility")
            await self.bot.database.apex.set_slot(
                self.user_id, self.server_id, first_empty, passive_key, tier, category
            )
            passive_display = passive_key.replace("-", " ").replace("_", " ").title()
            result_title = "✅ Extraction Successful!"
            result_desc = (
                f"**{passive_display}** (T1) has been imprinted into Slot {first_empty}!\n"
                + ("🏺 Soul Vessel preserved the item." if vessel else
                   ("⚠️ The item was destroyed." if item_destroyed else ""))
            )
            color = 0x00CC44
        else:
            result_title = "❌ Extraction Failed"
            result_desc = (
                f"The passive could not be extracted.\n"
                "⚠️ The item was destroyed.\n"
                f"*(Base chance was {base_chance*100:.1f}%)*"
            )
            color = 0xCC0000

        embed = discord.Embed(title=result_title, description=result_desc, color=color)
        embed.set_thumbnail(url=APEX_IMPRINT)
        await interaction.edit_original_response(embed=embed, view=None)
        self.stop()

    async def _destroy_item(self, item) -> None:
        """Attempts to delete the item from the DB (best-effort)."""
        if not item:
            return
        item_id = getattr(item, "id", None)
        if not item_id:
            return
        # Determine type from item class name
        _type_map = {
            "Weapon": "weapon", "Armor": "armor", "Accessory": "accessory",
            "Glove": "glove", "Boot": "boot", "Helmet": "helmet",
        }
        item_type = _type_map.get(type(item).__name__)
        if item_type:
            try:
                await self.bot.database.equipment.discard(item_id, item_type)
            except Exception:
                pass

    async def build_embed(self) -> discord.Embed:
        if not self._candidates:
            embed = discord.Embed(
                title="🔏 Imprint — No Extractable Passives",
                description=(
                    "None of your equipped items have passives eligible for soul stone extraction.\n\n"
                    "Eligible passives include weapon passives (burning, echo, etc.) and "
                    "named armor/accessory/glove/boot/helmet passives."
                ),
                color=0xCC6600,
            )
            embed.set_thumbnail(url=APEX_IMPRINT)
            return embed

        embed = discord.Embed(
            title="🔏 Imprint",
            description=(
                "Select a passive from your equipped gear to extract into the Soul Stone.\n\n"
                "Higher passive counts = higher extraction chance.\n"
                "**⚠️ The item is destroyed** on the extraction attempt (unless Soul Vessel is active)."
            ),
            color=0x9900CC,
        )
        embed.set_thumbnail(url=APEX_IMPRINT)
        # Show current soul stone state
        slot_lines = []
        for i, slot in enumerate(self.soul_stone.slots, 1):
            if slot.is_empty:
                slot_lines.append(f"**Slot {i}:** *(empty — available for imprint)*")
            else:
                passive_display = slot.passive.replace("-", " ").replace("_", " ").title()
                slot_lines.append(f"**Slot {i}:** {passive_display} T{slot.tier} *(occupied)*")
        embed.add_field(name="💎 Current Slots", value="\n".join(slot_lines), inline=False)
        return embed

    async def _cancel(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(
            content="Imprint cancelled.", embed=None, view=None
        )
        self.stop()
