# core/settlement/views/detail.py
import asyncio
import discord
from discord import ButtonStyle, Interaction, ui

from core.images import SETTLEMENT_BUILDINGS
from core.settlement.constants import (
    BUILDING_INFO,
    ITEM_NAMES,
    RESOURCE_DISPLAY_NAMES,
    SPECIAL_MAP,
    UBER_BUILDINGS,
    UBER_STATUE_DEFS,
)
from core.settlement.mechanics import SettlementMechanics
from core.settlement.turn_engine import upgrade_dt_cost

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

    def build_embed(self):
        b_data = SettlementMechanics.BUILDINGS.get(self.building.building_type)
        max_w = SettlementMechanics.get_max_workers(self.building.tier)

        # Calculate Rate Safely
        base_rate = b_data.get("base_rate", 0)
        rate = base_rate * self.building.tier * self.building.workers_assigned

        _DT_HOURS = 5  # 1 Development Turn = 5 hours of production

        # Adjust description based on building type
        if b_data.get("type") == "generator":
            output_name = b_data.get("output", "goods").replace("_", " ").title()
            rate_hr = int(rate)
            rate_dt = int(rate * _DT_HOURS)
            desc = (
                f"**Tier:** {self.building.tier}/5\n"
                f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                f"**Output:** ~{rate_hr:,}/hr · ~{rate_dt:,}/turn ({output_name})"
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
                    f"  • {_rname(raw)} → {_rname(ref)}: ~{int(r):,}/hr · ~{int(r * _DT_HOURS):,}/turn"
                    for raw, ref, r in tier_rates
                )
                desc = (
                    f"**Tier:** {self.building.tier}/5\n"
                    f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                    f"**Processing Rates:**\n{rate_lines}"
                )
            else:
                desc = (
                    f"**Tier:** {self.building.tier}/5\n"
                    f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                    f"**Processing Rates:** Assign workers to start converting."
                )
        elif self.building.building_type == "black_market":
            desc = f"**Tier:** {self.building.tier}/5\n**Type:** Special"
        else:
            desc = (
                f"**Tier:** {self.building.tier}/5\n"
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

        # Check for active upgrade project
        _projects = getattr(self.parent, "projects", []) or []
        _upgrade_proj = next(
            (
                p
                for p in _projects
                if p["project_type"] == "upgrade" and p["target_id"] == self.building.id
            ),
            None,
        )

        # Upgrade Cost Preview
        next_tier = self.building.tier + 1
        if self.building.tier < 5:
            if _upgrade_proj:
                invested = _upgrade_proj["invested_turns"]
                required = _upgrade_proj["required_turns"]
                embed.add_field(
                    name="🔨 Under Construction",
                    value=f"Upgrading to Tier {next_tier} — **{invested}/{required} DT(s)** complete",
                    inline=False,
                )
            else:
                next_cost = self._get_upgrade_cost(next_tier)
                dt = upgrade_dt_cost(self.building.building_type, next_tier)
                cost_str = f"🪵 {next_cost.get('timber'):,} | 🪨 {next_cost.get('stone'):,} | 💰 {next_cost.get('gold'):,} | ⏱️ {dt} DT(s)"
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

        # Workers (not shown for special buildings that don't use workers)
        if self.building.building_type != "black_market":
            btn_workers = ui.Button(
                label="Assign Workers", style=ButtonStyle.primary, emoji="👥"
            )
            btn_workers.callback = self.manage_workers
            self.add_item(btn_workers)

            btn_max = ui.Button(label="Max Workers", style=ButtonStyle.primary, row=0)
            btn_max.callback = self.max_workers
            self.add_item(btn_max)

        # Upgrade — disabled if max tier or an upgrade is already queued
        _projects = getattr(self.parent, "projects", []) or []
        _has_upgrade = any(
            p["project_type"] == "upgrade" and p["target_id"] == self.building.id
            for p in _projects
        )
        btn_upgrade = ui.Button(
            label="Upgrade",
            style=ButtonStyle.success,
            emoji="⬆️",
            disabled=(self.building.tier >= 5 or _has_upgrade),
        )
        btn_upgrade.callback = self.upgrade_building
        self.add_item(btn_upgrade)

        if self.building.building_type == "uber_shrine":
            btn_shrine = ui.Button(
                label="Manage Statues", style=ButtonStyle.blurple, emoji="🏛️", row=1
            )
            btn_shrine.callback = self.open_uber_shrine
            self.add_item(btn_shrine)

        if self.building.building_type == "hatchery":
            btn_hatchery = ui.Button(
                label="Open Hatchery", style=ButtonStyle.success, emoji="🐣", row=1
            )
            btn_hatchery.callback = self.open_hatchery
            self.add_item(btn_hatchery)

        if self.building.building_type == "nursery":
            btn_nursery = ui.Button(
                label="Manage Nursery", style=ButtonStyle.success, emoji="👶", row=1
            )
            btn_nursery.callback = self.open_nursery
            self.add_item(btn_nursery)

        if self.building.building_type == "idlem_foundry":
            btn_foundry = ui.Button(
                label="Manage Foundry", style=ButtonStyle.blurple, emoji="⚗️", row=1
            )
            btn_foundry.callback = self.open_idlem_foundry
            self.add_item(btn_foundry)

        if self.building.building_type == "sanctum":
            btn_sanctum = ui.Button(
                label="Open Sanctum", style=ButtonStyle.blurple, emoji="🕍", row=1
            )
            btn_sanctum.callback = self.open_sanctum
            self.add_item(btn_sanctum)

        if self.building.building_type == "black_market":
            btn_bm = ui.Button(
                label="Open Market", style=ButtonStyle.danger, emoji="🌑", row=1
            )
            btn_bm.callback = self.open_black_market
            self.add_item(btn_bm)

        if self.building.building_type != "town_hall":
            btn_demo = ui.Button(label="Demolish", style=ButtonStyle.danger, row=1)
            btn_demo.callback = self.demolish_prompt
            self.add_item(btn_demo)

        # Back
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️")
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

        if hasattr(self.parent, "_processing"):
            self.parent._processing = False
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
            _mats = await self.bot.database.settlement_materials.get_all(self.user_id)
            owned = _mats.get(col, 0)

            if owned < req:
                self._processing = False
                return await interaction.response.send_message(
                    f"Missing Material: You need **{req}x {costs['special_name']}** (Owned: {owned})",
                    ephemeral=True,
                )

        await interaction.response.defer()

        # Deduct resources immediately
        changes = {
            "timber": -costs["timber"],
            "stone": -costs["stone"],
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -costs["gold"])
        if "special_key" in costs:
            await self.bot.database.settlement_materials.modify(
                self.user_id, costs["special_key"], -costs["special_qty"]
            )

        # Queue upgrade project
        dt_cost = upgrade_dt_cost(self.building.building_type, target_tier)
        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.parent.server_id,
            project_type="upgrade",
            target_id=self.building.id,
            required_turns=dt_cost,
            data={"building_type": self.building.building_type},
        )

        # Refresh parent projects cache
        self.parent.projects = await self.bot.database.settlement.get_projects(
            self.user_id, self.parent.server_id
        )

        self.parent.settlement.timber -= costs["timber"]
        self.parent.settlement.stone -= costs["stone"]

        thumb = self.THUMBNAILS.get(self.building.building_type)
        queued_embed = discord.Embed(
            title="⏳ Upgrade Queued",
            description=(
                f"**{self.building.name}** upgrade to Tier {target_tier} has been queued.\n\n"
                f"Resources deducted. The upgrade will complete after **{dt_cost} Development Turn(s)**.\n"
                f"Use **Next Turn** on your settlement dashboard to process it."
            ),
            color=discord.Color.orange(),
        )
        if thumb:
            queued_embed.set_thumbnail(url=thumb)

        self._processing = False
        if hasattr(self.parent, "_processing"):
            self.parent._processing = False
        await interaction.edit_original_response(embed=queued_embed, view=self.parent)
        self.stop()
        await asyncio.sleep(3)
        dash_embed = self.parent.build_embed()
        await interaction.edit_original_response(embed=dash_embed, view=self.parent)

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

    async def open_nursery(self, interaction: Interaction):
        await interaction.response.defer()
        from core.settlement.views.nursery_foundry import NurseryView

        view = NurseryView(
            self.bot, self.user_id, self.parent.server_id, self.building, self.parent
        )
        projects = await self.bot.database.settlement.get_projects(
            self.user_id, self.parent.server_id
        )
        await interaction.edit_original_response(
            embed=view.build_embed(projects=projects), view=view
        )

    async def open_idlem_foundry(self, interaction: Interaction):
        await interaction.response.defer()
        from core.settlement.views.nursery_foundry import IdlemFoundryView

        zeal_data = await self.bot.database.settlement.get_zeal_data(
            self.user_id, self.parent.server_id
        )
        view = IdlemFoundryView(
            self.bot, self.user_id, self.parent.server_id, self.building, self.parent
        )
        projects = await self.bot.database.settlement.get_projects(
            self.user_id, self.parent.server_id
        )
        await interaction.edit_original_response(
            embed=view.build_embed(projects=projects, idlem=zeal_data.get("idlem", 0)),
            view=view,
        )

    async def open_sanctum(self, interaction: Interaction):
        await interaction.response.defer()
        from core.settlement.views.nursery_foundry import SanctumView

        view = SanctumView(
            self.bot, self.user_id, self.parent.server_id, self.building, self
        )
        await view._load()
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    async def open_black_market(self, interaction: Interaction):
        await interaction.response.defer()
        from core.settlement.views.black_market import BlackMarketView

        view = BlackMarketView(self.bot, self.user_id, self.parent, self.building)
        pending = await self.bot.database.settlement.get_pending_deal(
            self.user_id, self.parent.server_id
        )
        zeal_data = await self.bot.database.settlement.get_zeal_data(
            self.user_id, self.parent.server_id
        )
        await interaction.edit_original_response(
            embed=view.build_embed(pending_deal=pending, zeal_data=zeal_data), view=view
        )

    def _rebuild_ui(self):
        self.setup_ui()

    async def open_uber_shrine(self, interaction: Interaction):
        from core.settlement.views.uber_shrine import (
            UberShrineView as NewUberShrineView,
        )

        await interaction.response.defer()
        view = NewUberShrineView(
            self.bot,
            self.user_id,
            self,
            self.building,
            plot=None,
            adj_bonus={},
        )
        await view._load()
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    async def go_back(self, interaction: Interaction):
        if hasattr(self.parent, "_processing"):
            self.parent._processing = False
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


# ---------------------------------------------------------------------------
# Uber Shrine statue management
# ---------------------------------------------------------------------------


class _StatueWorkerModal(ui.Modal, title="Assign Statue Workers"):
    count = ui.TextInput(label="Number of Workers", min_length=1, max_length=4)

    def __init__(self, parent: "UberShrineView", statue_type: str, max_workers: int):
        super().__init__()
        self.shrine_parent = parent
        self.statue_type = statue_type
        self.max_workers = max_workers

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.count.value)
            if val < 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Invalid number.", ephemeral=True
            )

        if val > self.max_workers:
            return await interaction.response.send_message(
                f"This statue can only hold {self.max_workers} workers.", ephemeral=True
            )

        free = await self.shrine_parent._free_followers(self.statue_type, val)
        if val > free:
            return await interaction.response.send_message(
                f"You only have {free} available followers.", ephemeral=True
            )

        await self.shrine_parent.bot.database.settlement.set_statue_workers(
            self.shrine_parent.user_id,
            self.shrine_parent.server_id,
            self.statue_type,
            val,
        )
        self.shrine_parent.statue_data[self.statue_type]["workers_assigned"] = val
        self.shrine_parent._rebuild_ui()
        await interaction.response.edit_message(
            embed=self.shrine_parent.build_embed(), view=self.shrine_parent
        )


class _StatueSelect(ui.Select):
    def __init__(self, statue_data: dict):
        options = []
        for key, defn in UBER_STATUE_DEFS.items():
            data = statue_data.get(key, {})
            status = "Unlocked" if data.get("is_unlocked") else "Locked"
            options.append(
                discord.SelectOption(
                    label=f"{defn['emoji']} {defn['name']}",
                    value=key,
                    description=status,
                )
            )
        super().__init__(
            placeholder="Select a statue to manage…", options=options, row=0
        )
        self.chosen: str | None = None

    async def callback(self, interaction: Interaction):
        self.chosen = self.values[0]
        view: "UberShrineView" = self.view  # type: ignore[assignment]
        view._rebuild_ui()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class UberShrineView(SettlementBaseView):
    """Manages per-statue worker allocation for the Uber Shrine building."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        building,
        parent_detail: BuildingDetailView,
    ):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.building = building
        self.parent_detail = parent_detail
        self.statue_data: dict = {}
        self._select: _StatueSelect = _StatueSelect({})
        self._processing = False

    async def _load(self) -> None:
        self.statue_data = await self.bot.database.settlement.get_uber_shrine_statues(
            self.user_id, self.server_id
        )
        self._select = _StatueSelect(self.statue_data)
        self._rebuild_ui()

    def _statue_worker_cap(self) -> int:
        return self.building.tier * 10

    async def _free_followers(self, statue_type: str, new_workers: int) -> int:
        settlement = self.parent_detail.parent.settlement
        total_building_workers = sum(b.workers_assigned for b in settlement.buildings)
        total_statue_workers = sum(
            d.get("workers_assigned", 0) for d in self.statue_data.values()
        )
        current_statue = self.statue_data.get(statue_type, {}).get(
            "workers_assigned", 0
        )
        follower_count = self.parent_detail.parent.follower_count
        used = total_building_workers + total_statue_workers - current_statue
        return follower_count - used

    def _rebuild_ui(self) -> None:
        self.clear_items()
        self.add_item(self._select)

        chosen = self._select.chosen
        if chosen:
            data = self.statue_data.get(chosen, {})
            defn = UBER_STATUE_DEFS[chosen]
            is_unlocked = data.get("is_unlocked", False)

            can_build = data.get("can_build", False)
            if not is_unlocked:
                if can_build:
                    btn_build = ui.Button(
                        label=f"Build ({defn['build_dt']} DT + 1x {defn['material_name']})",
                        style=ButtonStyle.success,
                        emoji="🔨",
                        row=1,
                    )

                    async def _on_build(interaction: Interaction, _t=chosen):
                        await self._build_statue(interaction, _t)

                    btn_build.callback = _on_build
                    self.add_item(btn_build)
                # else: fully locked, no button shown
            else:
                btn_workers = ui.Button(
                    label="Assign Workers", style=ButtonStyle.primary, emoji="👥", row=1
                )

                async def _on_workers(interaction: Interaction, _t=chosen):
                    cap = self._statue_worker_cap()
                    modal = _StatueWorkerModal(self, _t, cap)
                    await interaction.response.send_modal(modal)

                btn_workers.callback = _on_workers
                self.add_item(btn_workers)

                btn_max = ui.Button(
                    label="Max Workers", style=ButtonStyle.primary, row=1
                )

                async def _on_max(interaction: Interaction, _t=chosen):
                    await self._max_workers(interaction, _t)

                btn_max.callback = _on_max
                self.add_item(btn_max)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=2)

        async def _on_back(interaction: Interaction):
            if hasattr(self.parent_detail, "_processing"):
                self.parent_detail._processing = False
            await interaction.response.edit_message(
                embed=self.parent_detail.build_embed(), view=self.parent_detail
            )
            self.stop()

        btn_back.callback = _on_back
        self.add_item(btn_back)

    def build_embed(self) -> discord.Embed:
        cap = self._statue_worker_cap()
        lines = []
        for key, defn in UBER_STATUE_DEFS.items():
            data = self.statue_data.get(key, {})
            if data.get("is_unlocked"):
                w = data.get("workers_assigned", 0)
                lines.append(f"{defn['emoji']} **{defn['name']}** — {w}/{cap} workers")
            elif data.get("can_build"):
                lines.append(
                    f"{defn['emoji']} **{defn['name']}** — "
                    f"📋 Blueprint ready · {defn['build_dt']} DT + 1x {defn['material_name']}"
                )
            else:
                lines.append(
                    f"{defn['emoji']} **{defn['name']}** — "
                    f"🔒 Defeat **{defn['boss_name']}** to unlock blueprint"
                )

        chosen = self._select.chosen
        detail = ""
        if chosen:
            data = self.statue_data.get(chosen, {})
            defn = UBER_STATUE_DEFS[chosen]
            if data.get("is_unlocked"):
                w = data.get("workers_assigned", 0)
                detail = (
                    f"\n\n**Selected:** {defn['emoji']} {defn['name']}\n"
                    f"{w}/{cap} workers assigned"
                )
            elif data.get("can_build"):
                detail = (
                    f"\n\n**Selected:** {defn['emoji']} {defn['name']}\n"
                    f"📋 Blueprint unlocked — build for **{defn['build_dt']} DT** + **1x {defn['material_name']}**"
                )
            else:
                detail = (
                    f"\n\n**Selected:** {defn['emoji']} {defn['name']}\n"
                    f"🔒 Defeat **{defn['boss_name']}** to earn the blueprint"
                )

        embed = discord.Embed(
            title="🏛️ Uber Shrine — Statue Management",
            description="\n".join(lines) + detail,
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Worker Cap",
            value=f"{cap} workers per statue (Shrine Tier {self.building.tier})",
            inline=False,
        )
        return embed

    async def _build_statue(self, interaction: Interaction, statue_type: str) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        defn = UBER_STATUE_DEFS[statue_type]

        _mats = await self.bot.database.settlement_materials.get_all(self.user_id)
        owned = _mats.get(defn["material"], 0)
        if owned < defn["material_qty"]:
            self._processing = False
            return await interaction.response.send_message(
                f"You need **{defn['material_qty']}x {defn['material_name']}** to build this statue. (You have {owned})",
                ephemeral=True,
            )

        await interaction.response.defer()
        await self.bot.database.settlement_materials.modify(
            self.user_id, defn["material"], -defn["material_qty"]
        )
        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.server_id,
            project_type="uber_statue",
            target_id=None,
            required_turns=defn["build_dt"],
            data={"statue_type": statue_type},
        )
        self._processing = False
        await interaction.edit_original_response(
            content=(
                f"🔨 **{defn['name']}** construction queued! "
                f"Completes in **{defn['build_dt']} Development Turns**."
            ),
            embed=self.build_embed(),
            view=self,
        )

    async def _max_workers(self, interaction: Interaction, statue_type: str) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        cap = self._statue_worker_cap()
        current = self.statue_data.get(statue_type, {}).get("workers_assigned", 0)
        free = await self._free_followers(statue_type, 0)
        target = min(cap, free + current)

        if target == current:
            self._processing = False
            return await interaction.response.send_message(
                "Already at max capacity.", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.settlement.set_statue_workers(
            self.user_id, self.server_id, statue_type, target
        )
        self.statue_data[statue_type]["workers_assigned"] = target
        self._rebuild_ui()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)
