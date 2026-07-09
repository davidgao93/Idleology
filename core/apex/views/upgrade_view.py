"""
core/apex/views/upgrade_view.py — Soul Stone slot upgrade flow.

Lets the player select a filled slot (T1–T4) and attempt to upgrade it one tier.
Upgrade costs scale with tier; T3+ requires Rift Shards as a co-cost.
Meta shards modify outcomes: Engorged Heart (lucky success), Condensed Blood (no downgrade).
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Select

from core.apex.data import PASSIVE_SHARD_MAP, UPGRADE_COSTS
from core.apex.mechanics import ApexMechanics
from core.apex.models import MetaShardInventory, ShardInventory, SoulStone
from core.base_view import BaseView
from core.emojis import APEX_SHARD_EMOJI, CONDENSED_BLOOD, ENGORGED_HEART, RIFT_SHARD
from core.images import APEX_UPGRADE


class UpgradeView(BaseView):
    """
    Upgrade flow: select a soul stone slot → see costs/outcomes → confirm upgrade.
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

        self._selected_slot: int | None = None
        self._selected_slot_obj = None

        # Toggle state: default ON if the player owns the shard
        self._use_heart: bool = False
        self._use_blood: bool = False

        self._build_select()

    # ------------------------------------------------------------------

    def _build_select(self):
        """Builds the slot-selection dropdown."""
        self.clear_items()

        upgradeable = [
            (i + 1, s)
            for i, s in enumerate(self.soul_stone.slots)
            if not s.is_empty and (s.tier or 0) < 5
        ]
        if not upgradeable:
            return

        options = []
        for slot_num, slot in upgradeable:
            passive_display = slot.passive.replace("-", " ").replace("_", " ").title()
            shard_type = PASSIVE_SHARD_MAP.get(slot.passive, "fortune")
            cost = UPGRADE_COSTS.get(slot.tier, {})
            cost_str = f"{cost.get('matching', 0)}x {shard_type.title()}"
            if cost.get("rift", 0) > 0:
                cost_str += f" + {cost['rift']}x Rift"
            options.append(
                discord.SelectOption(
                    label=f"Slot {slot_num}: {passive_display} T{slot.tier}",
                    value=str(slot_num),
                    description=f"Cost: {cost_str} → T{slot.tier + 1}",
                    emoji="⬆️",
                )
            )

        if not options:
            return

        select = Select(
            placeholder="Choose a slot to upgrade…",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

        cancel = Button(label="Cancel", style=ButtonStyle.secondary)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _on_select(self, interaction: Interaction):
        await interaction.response.defer()
        slot_num = int(interaction.data["values"][0])
        slot_obj = self.soul_stone.slots[slot_num - 1]

        self._selected_slot = slot_num
        self._selected_slot_obj = slot_obj

        # Default toggles to ON if the player owns the shard
        self._use_heart = bool(self.meta.engorged_heart)
        self._use_blood = bool(self.meta.condensed_blood)

        embed = self._build_confirm_embed()
        self._rebuild_confirm_view()
        await interaction.edit_original_response(embed=embed, view=self)

    # ------------------------------------------------------------------
    # Confirm-screen view builder
    # ------------------------------------------------------------------

    def _rebuild_confirm_view(self):
        """Rebuilds the confirm-screen buttons: row 0 = Upgrade + Back; row 1 = meta toggles."""
        self.clear_items()

        confirm = Button(label="Upgrade", style=ButtonStyle.success, emoji="⬆️", row=0)
        confirm.callback = self._confirm_upgrade
        self.add_item(confirm)

        back = Button(label="Back", style=ButtonStyle.secondary, row=0)
        back.callback = self._cancel
        self.add_item(back)

        if self.meta.engorged_heart:
            heart_btn = Button(
                label=f"Engorged Heart (have {self.meta.engorged_heart})",
                emoji=ENGORGED_HEART,
                style=ButtonStyle.success if self._use_heart else ButtonStyle.secondary,
                row=1,
            )
            heart_btn.callback = self._toggle_heart
            self.add_item(heart_btn)

        if self.meta.condensed_blood:
            blood_btn = Button(
                label=f"Condensed Blood (have {self.meta.condensed_blood})",
                emoji=CONDENSED_BLOOD,
                style=ButtonStyle.success if self._use_blood else ButtonStyle.secondary,
                row=1,
            )
            blood_btn.callback = self._toggle_blood
            self.add_item(blood_btn)

    async def _toggle_heart(self, interaction: Interaction):
        await interaction.response.defer()
        self._use_heart = not self._use_heart
        embed = self._build_confirm_embed()
        self._rebuild_confirm_view()
        await interaction.edit_original_response(embed=embed, view=self)

    async def _toggle_blood(self, interaction: Interaction):
        await interaction.response.defer()
        self._use_blood = not self._use_blood
        embed = self._build_confirm_embed()
        self._rebuild_confirm_view()
        await interaction.edit_original_response(embed=embed, view=self)

    # ------------------------------------------------------------------

    def _build_confirm_embed(self) -> discord.Embed:
        slot = self._selected_slot_obj
        passive_display = slot.passive.replace("-", " ").replace("_", " ").title()
        shard_type = PASSIVE_SHARD_MAP.get(slot.passive, "fortune")
        cost = UPGRADE_COSTS.get(slot.tier or 1, {})
        matching_cost = cost.get("matching", 0)
        rift_cost = cost.get("rift", 0)

        heart = self._use_heart
        blood = self._use_blood

        suc, stay, down = ApexMechanics.upgrade_outcomes_display(
            slot.tier, heart, blood
        )

        have_matching = self.shards.get(shard_type)
        have_rift = self.shards.rift
        can_afford = (have_matching >= matching_cost) and (have_rift >= rift_cost)

        embed = discord.Embed(
            title=f"Upgrade: {passive_display} T{slot.tier} → T{slot.tier + 1}",
            description=f"Soul Stone — Slot {self._selected_slot}",
            color=0x00CC44 if can_afford else 0xCC0000,
        )
        embed.set_thumbnail(url=APEX_UPGRADE)

        # Cost
        shard_emoji = APEX_SHARD_EMOJI.get(shard_type, "🔮")
        cost_lines = [
            f"{shard_emoji} {matching_cost}x {shard_type.title()} Shard (have: **{have_matching}**)"
        ]
        if rift_cost > 0:
            cost_lines.append(
                f"{RIFT_SHARD} {rift_cost}x Rift Shard (have: **{have_rift}**)"
            )
        if not can_afford:
            cost_lines.append("⚠️ **Insufficient shards!**")
        embed.add_field(name="💰 Cost", value="\n".join(cost_lines), inline=False)

        # Outcomes
        outcome_lines = [
            f"✅ Success (T{slot.tier + 1}): **{suc}%**",
            f"⏺️ Stay (T{slot.tier}): **{stay}%**",
        ]
        if down > 0:
            outcome_lines.append(f"⬇️ Downgrade (T{max(1, slot.tier - 1)}): **{down}%**")
        embed.add_field(
            name="📊 Outcomes", value="\n".join(outcome_lines), inline=False
        )

        # Active meta shards (reflect current toggle state)
        if heart:
            embed.add_field(
                name=f"{ENGORGED_HEART} Engorged Heart (have: {self.meta.engorged_heart})",
                value="Lucky upgrade — success odds boosted!",
                inline=True,
            )
        if blood:
            embed.add_field(
                name=f"{CONDENSED_BLOOD} Condensed Blood (have: {self.meta.condensed_blood})",
                value="Downgrade prevented on failure.",
                inline=True,
            )

        return embed

    async def _confirm_upgrade(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        if not self._selected_slot or not self._selected_slot_obj:
            self._processing = False
            return

        slot = self._selected_slot_obj
        shard_type = PASSIVE_SHARD_MAP.get(slot.passive, "fortune")
        cost = UPGRADE_COSTS.get(slot.tier or 1, {})
        matching_cost = cost.get("matching", 0)
        rift_cost = cost.get("rift", 0)

        heart = self._use_heart
        blood = self._use_blood

        # Attempt shard deduction
        paid = await self.bot.database.apex.deduct_upgrade_cost(
            self.user_id, self.server_id, shard_type, matching_cost, rift_cost
        )
        if not paid:
            error_embed = discord.Embed(
                title="⚠️ Insufficient Shards",
                description="You don't have enough shards to attempt this upgrade.",
                color=0xCC0000,
            )
            error_embed.set_thumbnail(url=APEX_UPGRADE)
            self.clear_items()
            back_btn = Button(label="← Back", style=ButtonStyle.secondary)
            back_btn.callback = self._return_to_soul_stone
            self.add_item(back_btn)
            self._processing = False
            await interaction.edit_original_response(embed=error_embed, view=self)
            return

        # Consume only the meta shards the player chose to use
        if heart:
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, "engorged_heart", -1
            )
        if blood:
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, "condensed_blood", -1
            )

        # Roll outcome
        outcome = ApexMechanics.roll_upgrade(slot.tier, heart, blood)
        passive_display = slot.passive.replace("-", " ").replace("_", " ").title()

        if outcome == "success":
            new_tier = slot.tier + 1
            await self.bot.database.apex.upgrade_slot_tier(
                self.user_id, self.server_id, self._selected_slot, new_tier
            )
            result_title = "✅ Upgrade Successful!"
            result_desc = f"**{passive_display}** is now **T{new_tier}**!"
            color = 0x00CC44

        elif outcome == "stay":
            result_title = "⏺️ Upgrade Failed — No Change"
            result_desc = (
                f"**{passive_display}** remains at **T{slot.tier}**. No regression."
            )
            color = 0xFFAA00

        else:  # downgrade
            new_tier = max(1, slot.tier - 1)
            await self.bot.database.apex.upgrade_slot_tier(
                self.user_id, self.server_id, self._selected_slot, new_tier
            )
            result_title = "⬇️ Upgrade Failed — Tier Dropped"
            result_desc = (
                f"**{passive_display}** dropped to **T{new_tier}**.\n"
                "*(Use Condensed Blood next time to prevent this.)*"
            )
            color = 0xCC0000

        embed = discord.Embed(title=result_title, description=result_desc, color=color)
        embed.set_thumbnail(url=APEX_UPGRADE)
        consumed_parts = []
        if heart:
            consumed_parts.append(f"{ENGORGED_HEART} Engorged Heart")
        if blood:
            consumed_parts.append(f"{CONDENSED_BLOOD} Condensed Blood")
        if consumed_parts:
            embed.add_field(
                name="🔘 Consumed",
                value="\n".join(consumed_parts),
                inline=False,
            )

        # "Done" button returns to soul stone
        self.clear_items()
        done_btn = Button(label="Done", style=ButtonStyle.secondary)
        done_btn.callback = self._return_to_soul_stone
        self.add_item(done_btn)

        await interaction.edit_original_response(embed=embed, view=self)

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

    def build_embed(self) -> discord.Embed:
        """Builds the initial upgrade overview embed."""
        upgradeable = [
            (i + 1, s)
            for i, s in enumerate(self.soul_stone.slots)
            if not s.is_empty and (s.tier or 0) < 5
        ]
        embed = discord.Embed(
            title="⬆️ Upgrade Soul Stone Slot",
            description=(
                "Select a slot to upgrade. Higher tiers increase passive effectiveness.\n"
                "**T3+** requires Rift Shards as a co-cost."
            ),
            color=0x00CC44,
        )

        heart = bool(self.meta.engorged_heart)
        blood = bool(self.meta.condensed_blood)

        for slot_num, slot in upgradeable:
            passive_display = slot.passive.replace("-", " ").replace("_", " ").title()
            shard_type = PASSIVE_SHARD_MAP.get(slot.passive, "fortune")
            cost = UPGRADE_COSTS.get(slot.tier, {})
            matching_cost = cost.get("matching", 0)
            rift_cost = cost.get("rift", 0)
            suc, stay, down = ApexMechanics.upgrade_outcomes_display(
                slot.tier, heart, blood
            )

            cost_str = f"{APEX_SHARD_EMOJI.get(shard_type, '🔮')} {matching_cost}x {shard_type.title()}"
            if rift_cost > 0:
                cost_str += f" + {RIFT_SHARD} {rift_cost}x Rift"
            have_matching = self.shards.get(shard_type)
            can_afford = have_matching >= matching_cost and (
                rift_cost == 0 or self.shards.rift >= rift_cost
            )
            afford_icon = "✅" if can_afford else "⚠️"

            value = (
                f"T{slot.tier} → T{slot.tier + 1} | {afford_icon} Cost: {cost_str}\n"
                f"Odds: ✅{suc}% / ⏺️{stay}% / ⬇️{down}%"
            )
            embed.add_field(
                name=f"Slot {slot_num}: {passive_display}",
                value=value,
                inline=False,
            )

        # Show active meta shard bonuses
        if heart or blood:
            meta_lines = []
            if heart:
                meta_lines.append(
                    f"{ENGORGED_HEART} Engorged Heart (have {self.meta.engorged_heart}) — Lucky success odds"
                )
            if blood:
                meta_lines.append(
                    f"{CONDENSED_BLOOD} Condensed Blood (have {self.meta.condensed_blood}) — No downgrade on failure"
                )
            embed.add_field(
                name="🔮 Active Meta Bonuses",
                value="\n".join(meta_lines),
                inline=False,
            )

        # Shard Inventory / Meta Shards — only shown here and in ImprintView, not
        # on the Soul Stone hub itself (only relevant once you're spending shards).
        from core.apex.views.soul_stone_view import (
            add_meta_shards_field,
            add_shard_inventory_field,
        )

        add_shard_inventory_field(embed, self.shards)
        add_meta_shards_field(embed, self.meta)

        embed.set_thumbnail(url=APEX_UPGRADE)
        return embed

    async def _cancel(self, interaction: Interaction):
        await self._return_to_soul_stone(interaction)
