"""
core/apex/views/soul_stone_view.py — Soul Stone management hub.

Shows the three soul stone slots, active resonance, and routes to Imprint/Upgrade/Clear.
All sub-views replace the current message in-place (no ephemeral pop-overs).
"""

from __future__ import annotations

from collections import Counter

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.apex.data import RESONANCE_TABLE
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
from core.emojis import (
    APEX_IMPRINT_EMOJI,
    APEX_SHARD_EMOJI,
    SOUL_FRAGMENT,
    SOUL_RESONANCE,
    SOUL_SLOT,
    SOUL_STONE,
)
from core.images import APEX_SOUL_STONE

_CAT_EMOJI: dict[str, str] = {
    "offensive": "🔥",
    "defensive": "🛡️",
    "mixed": "⚖️",
    "utility": "💰",
}
_ALL_CATEGORIES = ("offensive", "defensive", "mixed", "utility")


def add_shard_inventory_field(embed: discord.Embed, shards: ShardInventory) -> None:
    """Adds a '💠 Shard Inventory' field listing every shard type count.

    Shared by ImprintView and UpgradeView — the Soul Stone hub itself no longer
    shows this (only relevant once you're spending shards)."""
    shard_parts = []
    for key, emoji in APEX_SHARD_EMOJI.items():
        if key == "soul_fragments":
            continue
        count = shards.get(key)
        shard_parts.append(f"{emoji} {key.title()}: **{count}**")
    shard_parts.append(f"{SOUL_FRAGMENT} Soul Fragments: **{shards.soul_fragments}**")
    embed.add_field(
        name="💠 Shard Inventory", value="\n".join(shard_parts), inline=True
    )


def add_meta_shards_field(embed: discord.Embed, meta: MetaShardInventory) -> None:
    """Adds a '🔮 Meta Shards' field listing every meta shard type count.

    Shared by ImprintView and UpgradeView — the Soul Stone hub itself no longer
    shows this (only relevant once you're spending shards)."""
    from core.apex.data import META_SHARD_DISPLAY

    meta_parts = []
    for key, (display, _) in META_SHARD_DISPLAY.items():
        count = meta.get(key)
        meta_parts.append(
            f"{display.split(' ', 1)[0]} {key.replace('_', ' ').title()}: **{count}**"
        )
    embed.add_field(name="🔮 Meta Shards", value="\n".join(meta_parts), inline=True)


def _resonance_hint_text(soul_stone: SoulStone) -> str | None:
    """
    Returns a resonance hint string shown when no resonance is currently active.

    • 0 passives → None  (caller shows generic blurb)
    • 1 passive  → current-category progression + full T2/T3 table
    • 2 passives → which T2 options are still reachable with the last slot
    • 3 passives → all-different nudge to clear and reconfigure
    """
    filled = [s for s in soul_stone.slots if not s.is_empty and s.category]
    if not filled:
        return None

    cat_counts: Counter[str] = Counter(s.category for s in filled)
    lines: list[str] = []

    if len(filled) == 1:
        cat = next(iter(cat_counts))
        em = _CAT_EMOJI.get(cat, "✨")
        t2 = RESONANCE_TABLE.get(f"{cat}_2")
        t3 = RESONANCE_TABLE.get(f"{cat}_3")

        lines.append(f"Your **{cat.title()}** passive can lead to:")
        if t2:
            lines.append(f"  {em} **2× {cat.title()}** → **{t2[0]}** — *{t2[1]}*")
        if t3:
            lines.append(f"  {em} **3× {cat.title()}** → **{t3[0]}** — *{t3[1]}*")

        lines.append("")
        lines.append("**All resonances** *(T2 = 2 matching slots · T3 = all 3 slots):*")
        for c in _ALL_CATEGORIES:
            cem = _CAT_EMOJI.get(c, "✨")
            t2r = RESONANCE_TABLE.get(f"{c}_2")
            t3r = RESONANCE_TABLE.get(f"{c}_3")
            if t2r and t3r:
                lines.append(f"{cem} **{c.title()}:** {t2r[0]} / {t3r[0]}")

    elif len(filled) == 2:
        # No resonance with 2 slots means they hold two different categories.
        lines.append(
            "**1 slot remaining** — add a matching category to unlock a resonance:"
        )
        for cat in cat_counts:
            em = _CAT_EMOJI.get(cat, "✨")
            t2 = RESONANCE_TABLE.get(f"{cat}_2")
            if t2:
                lines.append(f"  {em} Add **{cat.title()}** → **{t2[0]}** — *{t2[1]}*")
        lines.append("")
        lines.append(
            "*T3 resonance is no longer reachable — it requires all 3 slots to match.*"
        )

    elif len(filled) == 3:
        # All slots filled with three different categories — no resonance possible.
        lines.append("All 3 slots are filled but no category has a majority.")
        lines.append(
            "Clear a slot and replace it so at least 2 slots share a category."
        )

    return "\n".join(lines) if lines else None


def _build_soul_stone_embed(
    soul_stone: SoulStone,
    shards: ShardInventory,
    meta: MetaShardInventory,
    player_name: str,
) -> discord.Embed:
    """Builds the main Soul Stone display embed."""
    embed = discord.Embed(
        title=f"{SOUL_STONE} Soul Stone",
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
            desc = ApexMechanics.get_soul_stone_passive_description(
                slot.passive, slot.tier or 1
            )
            desc_line = f"*{desc}*" if desc else "*(not yet active in combat)*"
            slot_lines.append(
                f"**Slot {i}:** {passive_display} T{slot.tier} {stars}\n"
                f"  ↳ Category: *{cat}*\n"
                f"  ↳ {desc_line}"
            )
    embed.add_field(
        name=f"{SOUL_SLOT} Slots", value="\n".join(slot_lines), inline=False
    )

    # --- Resonance ---
    res = ApexMechanics.get_resonance(soul_stone)
    if res:
        res_name, res_desc = res
        embed.add_field(
            name=f"{SOUL_RESONANCE} Resonance — {res_name}",
            value=res_desc,
            inline=False,
        )
    else:
        hint = _resonance_hint_text(soul_stone)
        if hint:
            embed.add_field(
                name=f"{SOUL_RESONANCE} Resonance Paths", value=hint, inline=False
            )
        else:
            # No passives yet — brief intro so the player knows the system exists.
            embed.add_field(
                name=f"{SOUL_RESONANCE} Resonance",
                value=(
                    "*No resonance active. Fill 2 or 3 slots with the same category "
                    "(Offensive / Defensive / Mixed / Utility) to unlock a permanent combat bonus.*"
                ),
                inline=False,
            )

    embed.set_thumbnail(url=APEX_SOUL_STONE)
    embed.set_footer(
        text="Imprint: extract passive from gear | Upgrade: improve a slot's tier"
    )
    return embed


class SoulStoneView(BaseView):
    """Hub view for soul stone management. Has Imprint, Upgrade, Clear, and ← Lobby buttons."""

    def __init__(self, bot, user_id: str, server_id: str, player):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self._processing = False

    def apply_gating(self, soul_stone: SoulStone) -> None:
        """Disables Imprint when no slot is free and Clear Slot when nothing is filled."""
        self.imprint_btn.disabled = soul_stone.first_empty_slot is None
        self.clear_btn.disabled = not any(not s.is_empty for s in soul_stone.slots)

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

    @discord.ui.button(
        label="Imprint", style=ButtonStyle.primary, emoji=APEX_IMPRINT_EMOJI, row=0
    )
    async def imprint_btn(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        soul_stone, shards, meta = await self._load_data()

        from core.apex.views.imprint_view import ImprintView

        view = ImprintView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            soul_stone,
            shards,
            meta,
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
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            soul_stone,
            shards,
            meta,
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

    @discord.ui.button(label="← Lobby", style=ButtonStyle.secondary, emoji="🏹", row=1)
    async def lobby_btn(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.apex.models import profile_from_db
        from core.apex.views.lobby_view import ApexLobbyView

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

        lobby_view = ApexLobbyView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player.name,
            profile,
            charges,
        )
        # Handing off from a classic embed message to a Components V2
        # LayoutView on the same message: discord.py only touches fields you
        # pass explicitly, so the old embed must be nulled out here or it
        # lingers alongside the new IS_COMPONENTS_V2 flag and Discord 400s.
        await interaction.edit_original_response(
            content=None, embed=None, attachments=[], view=lobby_view
        )
        lobby_view.message = await interaction.original_response()
        self._processing = False
        self.stop()

    @discord.ui.button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=1)
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
                emoji="🗑️",
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
            passive_display = (
                self.soul_stone.slots[slot_num - 1]
                .passive.replace("-", " ")
                .replace("_", " ")
                .title()
            )

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
        from core.apex.models import (
            meta_shards_from_db,
            shards_from_db,
            soul_stone_from_db,
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
        view.apply_gating(soul_stone)
        embed = _build_soul_stone_embed(soul_stone, shards, meta, self.player.name)
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = await interaction.original_response()
        self.stop()
