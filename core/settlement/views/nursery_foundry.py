"""
core/settlement/views/nursery_foundry.py
Detail views for the Nursery, Idlem Foundry, and Sanctum buildings.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.images import SETTLEMENT_BUILDINGS, YUNA_PORTRAIT, YUNA_THUMBNAIL
from core.npc_voices import get_quip
from core.settlement.constants import (
    IDLEM_PER_TURN_BASE,
    WORKERS_PER_TURN_BASE,
)
from core.settlement.views.base import SettlementBaseView


class NurseryView(SettlementBaseView):
    """
    Detail view for the Nursery building.
    Each "Produce Workers" click queues a 1-turn project.
    On Next Turn, the project completes and adds workers.
    """

    def __init__(self, bot, user_id: str, server_id: str, building, parent_view):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.building = building
        self.parent = parent_view
        self._processing = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.clear_items()

        produce_btn = ui.Button(
            label="Queue Worker Production",
            style=ButtonStyle.success,
            emoji="👶",
            row=0,
        )
        produce_btn.callback = self._on_queue
        self.add_item(produce_btn)

        back_btn = ui.Button(
            label="Back",
            style=ButtonStyle.secondary,
            emoji="⬅️",
            row=1,
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def _workers_per_turn(self) -> float:
        """Worker output per turn, scaling with Nursery tier and worker assignment."""
        tier = self.building.tier
        workers = max(1, self.building.workers_assigned)
        base = WORKERS_PER_TURN_BASE
        return base * tier * (1 + workers / 500)

    def build_embed(self, projects: list | None = None) -> discord.Embed:
        embed = discord.Embed(
            title="👶 Nursery",
            description=(
                f"*{get_quip('nursery')}*\n\n"
                "The Nursery produces new workers for your settlement "
                "through Development Turns. Each queued project completes "
                "in **1 turn**, adding workers to your ideology.\n\n"
                f"**Output per turn:** ~{self._workers_per_turn():.1f} workers\n"
                f"**Tier:** {self.building.tier} | "
                f"**Workers assigned:** {self.building.workers_assigned:,}"
            ),
            color=discord.Color.green(),
        )
        embed.set_author(name="Master Tamer Yuna", icon_url=YUNA_PORTRAIT)
        embed.set_thumbnail(url=YUNA_THUMBNAIL)

        if projects:
            nursery_proj = [p for p in projects if p["project_type"] == "nursery"]
            if nursery_proj:
                embed.add_field(
                    name="🏗️ Production Queue",
                    value=f"{len(nursery_proj)} batch(es) queued — advance turns to complete.",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🏗️ Production Queue",
                    value="No batches queued. Click **Queue Worker Production** to start one.",
                    inline=False,
                )

        return embed

    async def _on_queue(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            workers_this_turn = self._workers_per_turn()

            await self.bot.database.settlement.upsert_project(
                user_id=self.user_id,
                server_id=self.server_id,
                project_type="nursery",
                target_id=None,
                required_turns=1,
                data={"workers_per_turn": workers_this_turn},
            )

            projects = await self.bot.database.settlement.get_projects(
                self.user_id, self.server_id
            )
            embed = self.build_embed(projects=projects)
            embed.add_field(
                name="✅ Queued",
                value="Worker production batch queued! Advance **1 Development Turn** to collect.",
                inline=False,
            )
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            self.bot.logger.error(f"_on_queue exception: {e}", exc_info=True)
            raise
        finally:
            self._processing = False

    async def _on_back(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.parent._rebuild_ui()
        if hasattr(self.parent, "_processing"):
            self.parent._processing = False
        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


# ---------------------------------------------------------------------------
# Idlem Foundry
# ---------------------------------------------------------------------------


class IdlemFoundryView(SettlementBaseView):
    """
    Detail view for the Idlem Foundry building.
    Each "Produce Idlem" click queues a 1-turn project.
    On Next Turn, the project completes and grants Idlem.
    """

    def __init__(self, bot, user_id: str, server_id: str, building, parent_view):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.building = building
        self.parent = parent_view
        self._processing = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.clear_items()

        produce_btn = ui.Button(
            label="Queue Idlem Production",
            style=ButtonStyle.blurple,
            emoji="⚗️",
            row=0,
        )
        produce_btn.callback = self._on_queue
        self.add_item(produce_btn)

        back_btn = ui.Button(
            label="Back",
            style=ButtonStyle.secondary,
            emoji="⬅️",
            row=1,
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def _idlem_per_turn(self) -> float:
        """Base Idlem per turn (1–2 range, scaled by tier). Variance applied on completion."""
        tier = self.building.tier
        base = IDLEM_PER_TURN_BASE
        return (
            base * tier
        )  # stored as base; actual grant has +0/+1 variance on completion

    def build_embed(
        self, projects: list | None = None, idlem: int = 0
    ) -> discord.Embed:
        embed = discord.Embed(
            title="⚗️ Idlem Foundry",
            description=(
                "The Idlem Foundry distills the settlement's ambient energy "
                "into **Idlem** — the scarce resource powering the Black Market "
                "passive tree.\n\n"
                f"**Output per turn:** ~{self._idlem_per_turn():.1f} Idlem\n"
                f"**Tier:** {self.building.tier} | "
                f"**Your Idlem:** {idlem:,}"
            ),
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(
            url=SETTLEMENT_BUILDINGS.get(
                "idlem_foundry", SETTLEMENT_BUILDINGS["foundry"]
            )
        )

        if projects:
            foundry_proj = [p for p in projects if p["project_type"] == "foundry_idlem"]
            if foundry_proj:
                embed.add_field(
                    name="🏗️ Production Queue",
                    value=f"{len(foundry_proj)} batch(es) queued — advance turns to collect.",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🏗️ Production Queue",
                    value="No batches queued. Click **Queue Idlem Production** to start one.",
                    inline=False,
                )

        return embed

    async def _on_queue(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            idlem_this_turn = self._idlem_per_turn()

            await self.bot.database.settlement.upsert_project(
                user_id=self.user_id,
                server_id=self.server_id,
                project_type="foundry_idlem",
                target_id=None,
                required_turns=1,
                data={"idlem_per_turn": idlem_this_turn},
            )

            zeal_data = await self.bot.database.settlement.get_zeal_data(
                self.user_id, self.server_id
            )
            projects = await self.bot.database.settlement.get_projects(
                self.user_id, self.server_id
            )
            embed = self.build_embed(projects=projects, idlem=zeal_data.get("idlem", 0))
            embed.add_field(
                name="✅ Queued",
                value="Idlem production batch queued! Advance **1 Development Turn** to collect.",
                inline=False,
            )
            await interaction.edit_original_response(embed=embed, view=self)
        finally:
            self._processing = False

    async def _on_back(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.parent._rebuild_ui()
        if hasattr(self.parent, "_processing"):
            self.parent._processing = False
        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


# ---------------------------------------------------------------------------
# Sanctum
# ---------------------------------------------------------------------------


class _SanctumWorkerModal(ui.Modal, title="Assign Sanctum Workers"):
    count = ui.TextInput(label="Number of Workers", min_length=1, max_length=4)

    def __init__(self, parent: "SanctumView") -> None:
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction: Interaction) -> None:
        try:
            val = int(self.count.value)
            if val < 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Invalid number.", ephemeral=True
            )

        max_w = 100 * self.parent.building.tier
        if val > max_w:
            return await interaction.response.send_message(
                f"This building can only hold {max_w:,} workers.", ephemeral=True
            )

        dashboard = self.parent.parent_detail.parent
        total_assigned = sum(
            b.workers_assigned for b in dashboard.settlement.buildings
        )
        free = dashboard.follower_count - (
            total_assigned - self.parent.building.workers_assigned
        )
        if val > free:
            return await interaction.response.send_message(
                f"You only have {free:,} available followers.", ephemeral=True
            )

        await self.parent.bot.database.settlement.assign_workers(
            self.parent.building.id, val
        )
        dashboard.settlement = await self.parent.bot.database.settlement.get_settlement(
            self.parent.user_id, dashboard.server_id
        )
        for b in dashboard.settlement.buildings:
            if b.id == self.parent.building.id:
                self.parent.building = b
                break
        dashboard._rebuild_ui()

        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )


class SanctumView(SettlementBaseView):
    """
    Detail panel for the Sanctum. Displays live conversion stats and handles
    worker assignment. Navigation returns to BuildingDetailView.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        building,
        parent_detail,
    ) -> None:
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.building = building
        self.parent_detail = parent_detail  # BuildingDetailView
        self._plot_bonus: str | None = None
        self._processing = False
        self._build_ui()

    async def _load(self) -> None:
        if self.building.plot_index is not None:
            plot = await self.bot.database.plots.get_plot(
                self.user_id, self.server_id, self.building.plot_index
            )
            if plot:
                self._plot_bonus = plot["bonus_type"]

    # ------------------------------------------------------------------
    # Chance helpers
    # ------------------------------------------------------------------

    def _base_chance(self) -> float:
        return self.building.workers_assigned / 1000

    def _effective_chance(self) -> float:
        ch = self._base_chance()
        if self._plot_bonus == "sacred_ground":
            ch *= 1.20
        return min(0.95, ch)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        max_w = 100 * self.building.tier
        workers = self.building.workers_assigned
        base_pct = self._base_chance() * 100
        eff_pct = self._effective_chance() * 100
        has_sg = self._plot_bonus == "sacred_ground"

        embed = discord.Embed(
            title="🕍 Sanctum",
            description=(
                "Each combat victory has a chance to convert the fallen enemy "
                "into a devoted follower of your ideology.\n\n"
                f"**Tier {self.building.tier}/5** · "
                f"**{workers:,}/{max_w:,} workers** · "
                f"**{eff_pct:.1f}% conversion chance**"
            ),
            color=discord.Color.from_rgb(100, 70, 180),
        )

        thumb = SETTLEMENT_BUILDINGS.get("sanctum")
        if thumb:
            embed.set_thumbnail(url=thumb)

        # Conversion breakdown
        breakdown = [f"Base: {workers:,} workers ÷ 1000 = **{base_pct:.1f}%**"]
        if has_sg:
            breakdown.append("Plot bonus: **×1.20 (Sacred Ground)**")
            breakdown.append(f"→ Effective: **{eff_pct:.1f}%**")
        else:
            breakdown.append("Plot bonus: none *(Sacred Ground grants ×1.20)*")
        breakdown.append("Hard cap: **95%**")
        embed.add_field(
            name="Conversion Breakdown",
            value="\n".join(breakdown),
            inline=False,
        )

        # Per-tier reference
        tier_lines = []
        for t in range(1, 6):
            cap = 100 * t
            ch = cap / 1000
            if has_sg:
                ch = min(0.95, ch * 1.20)
            else:
                ch = min(0.95, ch)
            marker = " ← **current**" if t == self.building.tier else ""
            tier_lines.append(f"T{t} ({cap:,}w max): **{ch * 100:.0f}%**{marker}")

        if has_sg:
            tier_footer = "*Includes ×1.20 Sacred Ground bonus.*"
        else:
            tier_footer = (
                "*Place on Sacred Ground for ×1.20 multiplier.\n"
                "Bedrock plot raises worker cap by +25%.*"
            )
        embed.add_field(
            name="Max Chance per Tier",
            value="\n".join(tier_lines) + f"\n{tier_footer}",
            inline=False,
        )

        # Workers-to-next-milestone helper
        divisor = 1.20 if has_sg else 1.0
        targets = []
        for target_pct in (0.25, 0.50, 0.75, 0.95):
            needed = int((target_pct / divisor) * 1000)
            label = f"{int(target_pct * 100)}%"
            if needed <= workers:
                targets.append(f"✅ {label} — reached")
            else:
                targets.append(f"• {label} — need **{needed:,}** workers")
        embed.add_field(
            name="Milestones",
            value="\n".join(targets),
            inline=False,
        )

        return embed

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.clear_items()

        assign_btn = ui.Button(
            label="Assign Workers", style=ButtonStyle.primary, emoji="👥", row=0
        )
        assign_btn.callback = self._on_assign
        self.add_item(assign_btn)

        max_btn = ui.Button(label="Max Workers", style=ButtonStyle.primary, row=0)
        max_btn.callback = self._on_max
        self.add_item(max_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    async def _on_assign(self, interaction: Interaction) -> None:
        await interaction.response.send_modal(_SanctumWorkerModal(self))

    async def _on_max(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        max_w = 100 * self.building.tier
        dashboard = self.parent_detail.parent
        total_assigned = sum(
            b.workers_assigned for b in dashboard.settlement.buildings
        )
        free = dashboard.follower_count - (
            total_assigned - self.building.workers_assigned
        )
        target = min(max_w, free)

        if target == self.building.workers_assigned:
            self._processing = False
            return await interaction.response.send_message(
                "Already at maximum capacity.", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.settlement.assign_workers(self.building.id, target)

        dashboard.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, dashboard.server_id
        )
        for b in dashboard.settlement.buildings:
            if b.id == self.building.id:
                self.building = b
                break
        dashboard._rebuild_ui()

        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _on_back(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.parent_detail._rebuild_ui()
        if hasattr(self.parent_detail, "_processing"):
            self.parent_detail._processing = False
        await interaction.response.edit_message(
            embed=self.parent_detail.build_embed(), view=self.parent_detail
        )
        self.stop()
