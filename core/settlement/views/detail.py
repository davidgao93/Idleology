# core/settlement/views/detail.py
import discord
from discord import ButtonStyle, Interaction, ui

from core.images import SETTLEMENT_BUILDINGS
from core.settlement.constants import (
    BUILDING_INFO,
    ITEM_NAMES,
    RESOURCE_DISPLAY_NAMES,
    SPECIAL_MAP,
    UBER_BUILDINGS,
    UPGRADE_MESSAGES,
)
from core.settlement.mechanics import SettlementMechanics

from .base import SettlementBaseView


class WorkerModal(ui.Modal, title="Manage Workforce"):
    count = ui.TextInput(label="Number of Workers", min_length=1, max_length=4)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.count.value)
            if val < 0:
                raise ValueError

            max_w = SettlementMechanics.get_max_workers(self.parent_view.building.tier)
            if val > max_w:
                return await interaction.response.send_message(
                    f"This building can only hold {max_w} workers.", ephemeral=True
                )

            total_assigned_global = sum(
                b.workers_assigned for b in self.parent_view.parent.settlement.buildings
            )
            currently_in_this = self.parent_view.building.workers_assigned
            free_followers = self.parent_view.parent.follower_count - (
                total_assigned_global - currently_in_this
            )

            if val > free_followers:
                return await interaction.response.send_message(
                    f"You only have {free_followers} available followers.",
                    ephemeral=True,
                )

            await self.parent_view.bot.database.settlement.assign_workers(
                self.parent_view.building.id, val
            )

            self.parent_view.parent.settlement = (
                await self.parent_view.bot.database.settlement.get_settlement(
                    self.parent_view.user_id, self.parent_view.parent.server_id
                )
            )

            for b in self.parent_view.parent.settlement.buildings:
                if b.id == self.parent_view.building.id:
                    self.parent_view.building = b
                    break

            self.parent_view.parent._rebuild_ui()

            await interaction.response.edit_message(
                embed=self.parent_view.build_embed(), view=self.parent_view
            )

        except ValueError:
            await interaction.response.send_message("Invalid number.", ephemeral=True)


class BuildingDetailView(SettlementBaseView):
    # (All the original methods go here — copy-paste them from legacy_views.py)

    SPECIAL_MAP = SPECIAL_MAP  # from constants
    ITEM_NAMES = ITEM_NAMES
    UBER_BUILDINGS = UBER_BUILDINGS
    BUILDING_INFO = BUILDING_INFO
    THUMBNAILS = SETTLEMENT_BUILDINGS  # still from main legacy for now

    def __init__(self, bot, user_id, building, parent_view):
        super().__init__(bot, user_id)
        self.building = building
        self.parent = parent_view
        self._processing = False
        self.setup_ui()

    async def on_timeout(self):
        try:
            await self.parent.message.delete()
        except Exception:
            pass
        finally:
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()

    def build_embed(self):
        b_data = SettlementMechanics.BUILDINGS.get(self.building.building_type)
        max_w = SettlementMechanics.get_max_workers(self.building.tier)

        # Calculate Rate Safely
        base_rate = b_data.get("base_rate", 0)
        rate = base_rate * self.building.tier * self.building.workers_assigned

        # Adjust description based on building type
        if b_data.get("type") == "generator":
            output_name = b_data.get("output", "goods").replace("_", " ").title()
            desc = (
                f"**Level:** {self.building.tier}/5\n"
                f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                f"**Output:** ~{rate:,}/hr ({output_name})"
            )
        elif b_data.get("type") == "converter":
            tier_rates = SettlementMechanics.get_converter_rates(
                self.building.building_type,
                self.building.tier,
                self.building.workers_assigned,
            )
            def _rname(key: str) -> str:
                return RESOURCE_DISPLAY_NAMES.get(key, key.replace("_", " ").title())

            if tier_rates:
                rate_lines = "\n".join(
                    f"  • {_rname(raw)} → {_rname(ref)}: ~{r:,}/hr"
                    for raw, ref, r in tier_rates
                )
                desc = (
                    f"**Level:** {self.building.tier}/5\n"
                    f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                    f"**Processing Rates (per hr):**\n{rate_lines}"
                )
            else:
                desc = (
                    f"**Level:** {self.building.tier}/5\n"
                    f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                    f"**Processing Rates:** Assign workers to start converting."
                )
        else:
            desc = (
                f"**Level:** {self.building.tier}/5\n"
                f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                f"**Type:** {b_data.get('type', 'Passive').title()}"
            )

        embed = discord.Embed(
            title=f"{self.building.name}", description=desc, color=discord.Color.gold()
        )

        thumb = SETTLEMENT_BUILDINGS.get(self.building.building_type)
        if thumb:
            embed.set_thumbnail(url=thumb)

        info = BUILDING_INFO.get(self.building.building_type)
        if info:
            embed.add_field(name="Function", value=info, inline=False)

        # Upgrade Cost Preview
        next_cost = self._get_upgrade_cost(self.building.tier + 1)
        if self.building.tier < 5:
            cost_str = f"🪵 {next_cost.get('timber'):,} | 🪨 {next_cost.get('stone'):,} | 💰 {next_cost.get('gold'):,}"
            if "special_name" in next_cost:
                cost_str += (
                    f" | ✨ {next_cost['special_name']} x{next_cost['special_qty']}"
                )
            embed.add_field(name="Next Upgrade Cost", value=cost_str, inline=False)
        else:
            embed.add_field(name="Status", value="🌟 Max Level Reached", inline=False)
        return embed

    def _get_upgrade_cost(self, target_tier):
        return SettlementMechanics.get_upgrade_cost(
            self.building.building_type, self.building.tier
        )

    def setup_ui(self):
        self.clear_items()

        # Workers
        btn_workers = ui.Button(
            label="Assign Workers", style=ButtonStyle.primary, emoji="👥"
        )
        btn_workers.callback = self.manage_workers
        self.add_item(btn_workers)

        btn_max = ui.Button(label="Max Workers", style=ButtonStyle.primary, row=0)
        btn_max.callback = self.max_workers
        self.add_item(btn_max)

        # Upgrade
        btn_upgrade = ui.Button(
            label="Upgrade",
            style=ButtonStyle.success,
            emoji="⬆️",
            disabled=(self.building.tier >= 5),
        )
        btn_upgrade.callback = self.upgrade_building
        self.add_item(btn_upgrade)

        if self.building.building_type == "hatchery":
            btn_hatchery = ui.Button(
                label="Open Hatchery", style=ButtonStyle.success, emoji="🐣", row=1
            )
            btn_hatchery.callback = self.open_hatchery
            self.add_item(btn_hatchery)

        if self.building.building_type != "town_hall":
            btn_demo = ui.Button(label="Demolish", style=ButtonStyle.danger, row=1)
            btn_demo.callback = self.demolish_prompt
            self.add_item(btn_demo)

        # Back
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def demolish_prompt(self, interaction: Interaction):
        """Swaps UI to ask for confirmation to prevent accidental deletion."""
        self.clear_items()

        confirm_btn = ui.Button(
            label="CONFIRM DEMOLISH", style=ButtonStyle.danger, emoji="⚠️"
        )
        confirm_btn.callback = self.execute_demolish
        self.add_item(confirm_btn)

        cancel_btn = ui.Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self.cancel_demolish
        self.add_item(cancel_btn)

        # Overwrite embed to show warning
        embed = self.build_embed()
        embed.color = discord.Color.red()
        embed.add_field(
            name="⚠️ DEMOLITION WARNING",
            value="Are you sure you want to demolish this building?\nWorkers will be returned, but **all materials spent on construction and upgrades will be permanently lost.**",
            inline=False,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def cancel_demolish(self, interaction: Interaction):
        """Reverts back to the standard building UI."""
        self.setup_ui()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def execute_demolish(self, interaction: Interaction):
        """The actual database execution after confirmation."""
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # 1. Remove from DB
        await self.bot.database.settlement.demolish_building(self.building.id)

        # 2. Update Local State
        self.parent.settlement.buildings = [
            b for b in self.parent.settlement.buildings if b.id != self.building.id
        ]

        # 3. Refresh Parent Grid
        self.parent._rebuild_ui()

        await interaction.edit_original_response(
            content=f"💥 **{self.building.name}** has been demolished. Workers returned to pool.",
            embed=self.parent.build_embed(),
            view=self.parent,
        )
        self.stop()

    async def manage_workers(self, interaction: Interaction):
        modal = WorkerModal(self)
        await interaction.response.send_modal(modal)

    async def max_workers(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # Calculate Max Possible
        cap_per_building = SettlementMechanics.get_max_workers(self.building.tier)

        total_assigned_global = sum(
            b.workers_assigned for b in self.parent.settlement.buildings
        )
        currently_in_this = self.building.workers_assigned

        # Total free people in town
        free_followers = self.parent.follower_count - (
            total_assigned_global - currently_in_this
        )

        # We can fill up to the cap, or as many as we have free
        target_amount = min(cap_per_building, free_followers)

        if target_amount == self.building.workers_assigned:
            self._processing = False
            return await interaction.response.send_message(
                "Building already at optimal capacity.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.settlement.assign_workers(
            self.building.id, target_amount
        )

        # Refresh settlement from DB to sync worker counts for all buildings
        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )

        # Refresh this building reference from the updated settlement
        for b in self.parent.settlement.buildings:
            if b.id == self.building.id:
                self.building = b
                break

        # Rebuild parent grid (so button labels & 🟢/🔴 match)
        self.parent._rebuild_ui()

        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def upgrade_building(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        target_tier = self.building.tier + 1
        costs = self._get_upgrade_cost(target_tier)

        # Check Settlement Resources
        if (
            self.parent.settlement.timber < costs["timber"]
            or self.parent.settlement.stone < costs["stone"]
        ):
            self._processing = False
            return await interaction.response.send_message(
                "Insufficient Timber or Stone!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < costs["gold"]:
            self._processing = False
            return await interaction.response.send_message(
                "Insufficient Gold!", ephemeral=True
            )

        # Check Special Items (if any) — validate before deducting
        if "special_key" in costs:
            col = costs["special_key"]
            req = costs["special_qty"]
            owned = await self.bot.database.users.get_currency(self.user_id, col)

            if owned < req:
                self._processing = False
                return await interaction.response.send_message(
                    f"Missing Material: You need **{req}x {costs['special_name']}** (Owned: {owned})",
                    ephemeral=True,
                )

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        # Deduct special material after defer
        if "special_key" in costs:
            col = costs["special_key"]
            req = costs["special_qty"]
            await self.bot.database.users.modify_currency(self.user_id, col, -req)

        # === EMBED-BASED UPGRADE ANIMATION ===
        import asyncio
        import random

        chosen_messages = random.choices(
            population=[msg for msg, _ in UPGRADE_MESSAGES],
            weights=[w for _, w in UPGRADE_MESSAGES],
            k=3,
        )

        progress_embed = discord.Embed(
            title="⬆️ Upgrade in Progress",
            color=discord.Color.orange(),
        )
        thumb = self.THUMBNAILS.get(self.building.building_type)
        if thumb:
            progress_embed.set_thumbnail(url=thumb)

        for i, msg in enumerate(chosen_messages, 1):
            progress_embed.description = f"**Step {i}/3:** {msg}"
            await interaction.edit_original_response(embed=progress_embed)
            if i < 3:
                await asyncio.sleep(2)

        # Final completion
        progress_embed.title = "✅ Upgrade Complete"
        progress_embed.description = (
            "**Upgrade complete!** The building has been strengthened."
        )
        progress_embed.color = discord.Color.green()
        await interaction.edit_original_response(embed=progress_embed)
        await asyncio.sleep(1.5)

        # === Actual upgrade logic ===
        changes = {
            "timber": -costs["timber"],
            "stone": -costs["stone"],
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -costs["gold"])

        if self.building.building_type == "town_hall":
            await self.bot.database.settlement.expand_building_slots(
                self.user_id, self.parent.server_id
            )
            self.parent.settlement.building_slots += 1

        await self.bot.database.settlement.upgrade_building_tier(self.building.id)

        self.building.tier += 1
        self.parent.settlement.timber -= costs["timber"]
        self.parent.settlement.stone -= costs["stone"]

        self._processing = False
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def open_hatchery(self, interaction: Interaction):
        await interaction.response.defer()
        from core.hatchery.views import HatcheryView
        hview = HatcheryView(
            self.bot,
            self.user_id,
            self.parent.server_id,
            self.building,
            self,
        )
        await hview._load()
        hview._rebuild_buttons()
        await interaction.edit_original_response(embed=hview.build_embed(), view=hview)

    async def go_back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
