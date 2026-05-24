"""
core/apex/views/soul_stone_view.py — Soul Stone management hub.

Shows the three soul stone slots, active resonance, and routes to Imprint/Upgrade/Clear.
All sub-views replace the current message in-place (no ephemeral pop-overs).
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.apex.data import RESONANCE_TABLE, ZONE_DEFS
from core.apex.mechanics import ApexMechanics
from core.apex.models import (
    MetaShardInventory,
    ShardInventory,
    SoulStone,
    meta_shards_from_db,
    shards_from_db,
    soul_stone_from_db,
)
from core.base_view import BaseView
from core.images import APEX_SOUL_STONE


def _build_soul_stone_embed(
    soul_stone: SoulStone,
    shards: ShardInventory,
    meta: MetaShardInventory,
    player_name: str,
) -> discord.Embed:
    """Builds the main Soul Stone display embed."""
    embed = discord.Embed(
        title="💎 Soul Stone",
        description=(
            f"**{player_name}**'s permanent passive lattice.\n"
            "Imprint passives extracted from your gear. Up to 3 slots available."
        ),
        color=0x9900CC,
    )

    # --- Slot display ---
    slot_lines: list[str] = []
    for i, slot in enumerate(soul_stone.slots, 1):
        if slot.is_empty:
            slot_lines.append(f"**Slot {i}:** *(empty — use Imprint to fill)*")
        else:
            passive_display = slot.passive.replace("-", " ").replace("_", " ").title()
            stars = "⭐" * (slot.tier or 0)
            cat = slot.category.capitalize() if slot.category else "?"
            slot_lines.append(
                f"**Slot {i}:** {passive_display} T{slot.tier} {stars}\n"
                f"  ↳ Category: *{cat}*"
            )
    embed.add_field(name="🔮 Slots", value="\n".join(slot_lines), inline=False)

    # --- Resonance ---
    res = ApexMechanics.get_resonance(soul_stone)
    if res:
        res_name, res_desc = res
        embed.add_field(
            name=f"✨ Resonance — {res_name}",
            value=res_desc,
            inline=False,
        )
    else:
        filled = [s for s in soul_stone.slots if not s.is_empty]
        if len(filled) < 3:
            embed.add_field(
                name="✨ Resonance",
                value=(
                    "*No resonance active. Fill 2 or 3 slots with the same category "
                    "(offensive / defensive / mixed / utility) to activate a bonus.*"
                ),
                inline=False,
            )

    # --- Shard inventory ---
    shard_parts = []
    _SHARD_EMOJIS = {
        "pyre": "🔥", "tempest": "⚡", "bulwark": "🏰",
        "verdant": "🌿", "fortune": "💰", "rift": "🌀",
    }
    for key, emoji in _SHARD_EMOJIS.items():
        count = shards.get(key)
        shard_parts.append(f"{emoji} {key.title()}: **{count}**")
    shard_parts.append(f"🔘 Soul Fragments: **{shards.soul_fragments}**")
    embed.add_field(
        name="💠 Shard Inventory",
        value="\n".join(shard_parts),
        inline=True,
    )

    # --- Meta shards ---
    from core.apex.data import META_SHARD_DISPLAY
    meta_parts = []
    for key, (display, _) in META_SHARD_DISPLAY.items():
        count = meta.get(key)
        meta_parts.append(f"{display.split(' ', 1)[0]} {key.replace('_', ' ').title()}: **{count}**")
    embed.add_field(
        name="🔮 Meta Shards",
        value="\n".join(meta_parts),
        inline=True,
    )

    embed.set_thumbnail(url=APEX_SOUL_STONE)
    embed.set_footer(text="Imprint: extract passive from gear | Upgrade: improve a slot's tier")
    return embed


class SoulStoneView(BaseView):
    """Hub view for soul stone management. Has Imprint, Upgrade, Clear, and ← Lobby buttons."""

    def __init__(self, bot, user_id: str, server_id: str, player):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self._processing = False

    async def _load_data(self):
        ss_row = await self.bot.database.apex.get_or_create_soul_stone(
            self.user_id, self.server_id
        )
        shards_row = await self.bot.database.apex.get_or_create_shards(
            self.user_id, self.server_id
        )
        meta_row = await self.bot.database.apex.get_or_create_meta_shards(
            self.user_id, self.server_id
        )
        return (
            soul_stone_from_db(ss_row),
            shards_from_db(shards_row),
            meta_shards_from_db(meta_row),
        )

    @discord.ui.button(label="Imprint", style=ButtonStyle.primary, emoji="🔏", row=0)
    async def imprint_btn(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        soul_stone, shards, meta = await self._load_data()

        from core.apex.views.imprint_view import ImprintView

        view = ImprintView(
            self.bot, self.user_id, self.server_id,
            self.player, soul_stone, shards, meta,
        )
        embed = await view.build_embed()
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = await interaction.original_response()
        self._processing = False
        self.stop()  # hand off; ImprintView will rebuild SoulStoneView on return

    @discord.ui.button(label="Upgrade", style=ButtonStyle.success, emoji="⬆️", row=0)
    async def upgrade_btn(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        soul_stone, shards, meta = await self._load_data()

        filled = [s for s in soul_stone.slots if not s.is_empty and (s.tier or 0) < 5]
        if not filled:
            # Error condition — ephemeral is acceptable here
            await interaction.followup.send(
                "⚠️ No upgradeable slots (all are empty or already Tier 5).",
                ephemeral=True,
            )
            self._processing = False
            return

        from core.apex.views.upgrade_view import UpgradeView

        view = UpgradeView(
            self.bot, self.user_id, self.server_id,
            self.player, soul_stone, shards, meta,
        )
        embed = view.build_embed()
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = await interaction.original_response()
        self._processing = False
        self.stop()

    @discord.ui.button(label="Clear Slot", style=ButtonStyle.danger, emoji="🗑️", row=0)
    async def clear_btn(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        soul_stone, _, _ = await self._load_data()

        filled = [(i + 1, s) for i, s in enumerate(soul_stone.slots) if not s.is_empty]
        if not filled:
            await interaction.followup.send(
                "⚠️ All slots are already empty.", ephemeral=True
            )
            self._processing = False
            return

        view = _ClearSlotView(
            self.bot, self.user_id, self.server_id, soul_stone, self.player
        )
        embed = discord.Embed(
            title="🗑️ Clear Soul Stone Slot",
            description="Choose a slot to clear. **This action is free and permanent.**",
            color=0xCC0000,
        )
        embed.set_thumbnail(url=APEX_SOUL_STONE)
        for slot_num, slot in filled:
            passive_display = slot.passive.replace("-", " ").replace("_", " ").title()
            embed.add_field(
                name=f"Slot {slot_num}",
                value=f"{passive_display} T{slot.tier}",
                inline=True,
            )
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = await interaction.original_response()
        self._processing = False
        self.stop()

    @discord.ui.button(label="Refresh", style=ButtonStyle.secondary, emoji="🔄", row=0)
    async def refresh_btn(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        soul_stone, shards, meta = await self._load_data()
        embed = _build_soul_stone_embed(soul_stone, shards, meta, self.player.name)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="← Lobby", style=ButtonStyle.secondary, emoji="🏹", row=1)
    async def lobby_btn(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.apex.models import profile_from_db
        from core.apex.views.lobby_view import ApexLobbyView, _build_lobby_embed

        profile_row = await self.bot.database.apex.get_or_create_profile(
            self.user_id, self.server_id
        )
        profile = profile_from_db(profile_row)
        charges, new_ts = ApexMechanics.calculate_charges(profile)
        if new_ts != profile.last_charge_time:
            await self.bot.database.apex.restore_charges(
                self.user_id, self.server_id, charges, new_ts
            )
            profile.hunt_charges = charges
            profile.last_charge_time = new_ts

        secs = ApexMechanics.seconds_until_next_charge(profile)
        lobby_view = ApexLobbyView(
            self.bot, self.user_id, self.server_id,
            self.player.name, profile, charges,
        )
        lobby_embed = _build_lobby_embed(self.player.name, profile, charges, secs)
        await interaction.edit_original_response(embed=lobby_embed, view=lobby_view)
        lobby_view.message = await interaction.original_response()
        self._processing = False
        self.stop()

    @discord.ui.button(label="Exit", style=ButtonStyle.danger, emoji="🚪", row=1)
    async def exit_btn(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()


class _ClearSlotView(BaseView):
    """Confirmation view for clearing a specific soul stone slot."""

    def __init__(self, bot, user_id, server_id, soul_stone: SoulStone, player):
        super().__init__(bot, user_id, server_id)
        self.soul_stone = soul_stone
        self.player = player
        self._processing = False

        filled = [(i + 1, s) for i, s in enumerate(soul_stone.slots) if not s.is_empty]
        for slot_num, slot in filled:
            passive_display = slot.passive.replace("-", " ").replace("_", " ").title()
            btn = Button(
                label=f"Clear Slot {slot_num} ({passive_display})",
                style=ButtonStyle.danger,
                custom_id=f"clear_{slot_num}",
            )
            btn.callback = self._make_clear_callback(slot_num)
            self.add_item(btn)

        cancel_btn = Button(label="← Back", style=ButtonStyle.secondary)
        cancel_btn.callback = self._return_to_soul_stone
        self.add_item(cancel_btn)

    def _make_clear_callback(self, slot_num: int):
        async def _callback(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()
            await self.bot.database.apex.clear_slot(
                self.user_id, self.server_id, slot_num
            )
            passive_display = self.soul_stone.slots[slot_num - 1].passive.replace("-", " ").replace("_", " ").title()

            # Show result briefly, then offer to go back
            self.clear_items()
            done_btn = Button(label="Done", style=ButtonStyle.secondary)
            done_btn.callback = self._return_to_soul_stone
            self.add_item(done_btn)

            result_embed = discord.Embed(
                title="✅ Slot Cleared",
                description=f"**Slot {slot_num}** ({passive_display}) has been cleared.",
                color=0x00CC44,
            )
            result_embed.set_thumbnail(url=APEX_SOUL_STONE)
            await interaction.edit_original_response(embed=result_embed, view=self)

        return _callback

    async def _return_to_soul_stone(self, interaction: Interaction):
        await interaction.response.defer()
        from core.apex.models import soul_stone_from_db, shards_from_db, meta_shards_from_db

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
