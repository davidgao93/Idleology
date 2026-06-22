# core/settlement/views/uber_shrine.py
"""
UberShrineView — Monument Hall to the Gods.

Flow:
  Main view  → slot select menu (slots 1–N, where N = shrine building tier)
  Slot view  → Construct / Manage Workers / Max Workers / Upgrade Tier / Back
"""

from __future__ import annotations

import asyncio

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.settlement.constants import (
    STATUE_UPGRADE_DT,
    STATUE_UPGRADE_GOLD,
    STATUE_UPGRADE_MATERIAL_QTY,
    UBER_STATUE_DEFS,
)
from core.settlement.plots import SHRINE_BUILDING_TYPES, get_effective_max_workers

from .base import SettlementBaseView

# Ordered slot list — slot number corresponds to index + 1
_SLOT_ORDER = ["celestial", "infernal", "void", "bound", "corrupted"]


# ---------------------------------------------------------------------------
# Statue worker modal
# ---------------------------------------------------------------------------


class _StatueWorkerModal(ui.Modal, title="Assign Statue Workers"):
    def __init__(self, slot_view: "StatueSlotView", max_workers: int, current: int):
        super().__init__()
        self.slot_view = slot_view
        self.count = ui.TextInput(
            label=f"Workers (0–{max_workers:,} cap, {slot_view._free_workers():,} available)",
            placeholder=f"Currently {current:,} — enter new amount",
            min_length=1,
            max_length=6,
        )
        self.add_item(self.count)

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.count.value)
            if val < 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Invalid number.", ephemeral=True
            )

        sv = self.slot_view
        statue_type = sv.statue_type
        statue_data = sv.shrine_view.statue_data.get(statue_type, {})
        max_w = sv._statue_worker_cap()
        if val > max_w:
            return await interaction.response.send_message(
                f"This statue can only hold **{max_w:,}** workers.", ephemeral=True
            )
        free = sv._free_workers()
        current = statue_data.get("workers_assigned", 0)
        if val > free + current:
            return await interaction.response.send_message(
                f"You only have **{free + current:,}** available (including this statue's current {current:,}).",
                ephemeral=True,
            )
        if val > free and val > current:
            return await interaction.response.send_message(
                f"Not enough free followers — you have **{free:,}** available.",
                ephemeral=True,
            )

        await sv.shrine_view.bot.database.settlement.set_statue_workers(
            sv.shrine_view.user_id, sv.shrine_view.server_id, statue_type, val
        )
        sv.shrine_view.statue_data[statue_type]["workers_assigned"] = val
        sv._rebuild_ui()
        await interaction.response.edit_message(embed=sv.build_embed(), view=sv)


# ---------------------------------------------------------------------------
# Statue slot sub-view
# ---------------------------------------------------------------------------


class StatueSlotView(SettlementBaseView):
    """Manages a single statue slot inside the Uber Shrine."""

    def __init__(
        self,
        bot,
        user_id: str,
        shrine_view: "UberShrineView",
        statue_type: str,
    ):
        super().__init__(bot, user_id)
        self.shrine_view = shrine_view
        self.statue_type = statue_type
        self.server_id = shrine_view.server_id
        self._processing = False
        self._rebuild_ui()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _defn(self) -> dict:
        return UBER_STATUE_DEFS[self.statue_type]

    def _data(self) -> dict:
        return self.shrine_view.statue_data.get(self.statue_type, {})

    def _shrine_building(self):
        return self.shrine_view.building

    def _statue_worker_cap(self) -> int:
        """Effective max workers for this statue, respecting the building's plot bonus."""
        statue_tier = self._data().get("tier", 1)
        sv = self.shrine_view
        return get_effective_max_workers(
            building_type="uber_shrine",
            tier=statue_tier,
            plot_bonus_type=sv.plot_bonus_type,
            adj_shrine_cap_x2=sv.adj_bonus.get("shrine_cap_x2", False),
            has_watchtower=sv.adj_bonus.get("has_watchtower", False),
        )

    def _free_workers(self) -> int:
        """Followers available to assign to THIS statue (excluding what it already uses)."""
        sv = self.shrine_view
        parent = sv.parent  # PlotDetailView (or BuildingDetailView)
        # Resolve dashboard which has .settlement and .follower_count
        dashboard = getattr(parent, "parent", parent)
        settlement = getattr(dashboard, "settlement", None)
        follower_count = getattr(dashboard, "follower_count", 0)
        if follower_count == 0:
            follower_count = getattr(parent, "follower_count", 0)
        building_workers = sum(b.workers_assigned for b in settlement.buildings) if settlement else 0
        statue_workers = sum(d.get("workers_assigned", 0) for d in sv.statue_data.values())
        current = self._data().get("workers_assigned", 0)
        used = building_workers + statue_workers - current
        return max(0, follower_count - used)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        defn = self._defn()
        data = self._data()
        slot_num = defn["slot"]
        is_unlocked = data.get("is_unlocked", False)
        can_build = data.get("can_build", False)
        statue_tier = data.get("tier", 1)
        workers = data.get("workers_assigned", 0)
        max_w = self._statue_worker_cap() if is_unlocked else 0

        embed = discord.Embed(
            title=f"🏛️ Slot {slot_num} — {defn['emoji']} {defn['name']}",
            color=discord.Color.gold() if is_unlocked else discord.Color.dark_grey(),
        )

        if not is_unlocked and not can_build:
            embed.description = (
                f"🔒 **Locked** — defeat **{defn['boss_name']}** to earn the blueprint.\n\n"
                f"The {defn['name']} is dedicated to the gods vanquished by {defn['boss_name']}."
            )
        elif not is_unlocked:
            cost = STATUE_UPGRADE_GOLD.get(1, 0)  # no gold cost for initial build
            embed.description = (
                f"📋 **Blueprint acquired!** You can construct the {defn['name']}.\n\n"
                f"**Construction cost:** 1× {defn['material_name']} · "
                f"{defn['build_dt']} Development Turns"
            )
        else:
            # Check if upgrade is in progress
            upgrade_pending = any(
                p.get("project_type") == "statue_upgrade"
                and (p.get("data") or {}).get("statue_type") == self.statue_type
                for p in self.shrine_view._pending_projects
            )
            tier_str = f"T{statue_tier}/5"
            if upgrade_pending:
                tier_str += " *(upgrade in progress)*"

            embed.description = (
                f"**Tier:** {tier_str}\n"
                f"**Workers:** {workers:,}/{max_w:,}\n\n"
                f"Each worker assigned to this statue increases the sigil drop "
                f"chance for **{defn['boss_name']}** encounters."
            )

            if statue_tier < 5:
                next_tier = statue_tier + 1
                mat_qty = STATUE_UPGRADE_MATERIAL_QTY.get(next_tier, 0)
                gold_cost = STATUE_UPGRADE_GOLD.get(next_tier, 0)
                dt_cost = STATUE_UPGRADE_DT.get(next_tier, 0)
                embed.add_field(
                    name=f"⬆️ Upgrade to T{next_tier} Cost",
                    value=(
                        f"💰 {gold_cost:,} | "
                        f"{defn['material_name']} ×{mat_qty} | "
                        f"⏱️ {dt_cost} DTs"
                    ),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Status", value="🌟 Max Tier Reached", inline=False
                )

        embed.set_footer(
            text=f"Monument Hall — Slot {slot_num}/5  |  "
            f"Shrine T{self._shrine_building().tier}"
        )
        return embed

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _rebuild_ui(self):
        self.clear_items()
        defn = self._defn()
        data = self._data()
        is_unlocked = data.get("is_unlocked", False)
        can_build = data.get("can_build", False)
        statue_tier = data.get("tier", 1)

        # Check if build/upgrade is already pending
        build_pending = any(
            p.get("project_type") in ("uber_statue", "statue_upgrade")
            and (p.get("data") or {}).get("statue_type") == self.statue_type
            for p in self.shrine_view._pending_projects
        )

        if not is_unlocked and can_build and not build_pending:
            btn_build = ui.Button(
                label=f"Construct ({defn['build_dt']} DTs + 1× {defn['material_name']})",
                style=ButtonStyle.success,
                emoji="🔨",
                row=0,
            )
            btn_build.callback = self._on_build
            self.add_item(btn_build)
        elif not is_unlocked and build_pending:
            self.add_item(
                ui.Button(
                    label="🏗️ Construction in progress…",
                    style=ButtonStyle.secondary,
                    disabled=True,
                    row=0,
                )
            )
        elif is_unlocked:
            btn_workers = ui.Button(
                label="Manage Workers",
                style=ButtonStyle.primary,
                emoji="👥",
                row=0,
            )
            btn_workers.callback = self._on_manage_workers
            self.add_item(btn_workers)

            btn_max = ui.Button(
                label="Max Workers",
                style=ButtonStyle.primary,
                emoji="⬆️",
                row=0,
            )
            btn_max.callback = self._on_max_workers
            self.add_item(btn_max)

            if statue_tier < 5 and not build_pending:
                btn_up = ui.Button(
                    label=f"Upgrade to T{statue_tier + 1}",
                    style=ButtonStyle.success,
                    emoji="✨",
                    row=0,
                )
                btn_up.callback = self._on_upgrade
                self.add_item(btn_up)
            elif build_pending:
                self.add_item(
                    ui.Button(
                        label="⏳ Upgrade in progress…",
                        style=ButtonStyle.secondary,
                        disabled=True,
                        row=0,
                    )
                )

        back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back.callback = self._on_back
        self.add_item(back)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_build(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        defn = self._defn()
        owned = await self.bot.database.users.get_currency(
            self.user_id, defn["material"]
        )
        if owned < defn["material_qty"]:
            self._processing = False
            return await interaction.response.send_message(
                f"You need **{defn['material_qty']}× {defn['material_name']}** "
                f"to construct this statue. (You have {owned})",
                ephemeral=True,
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_currency(
            self.user_id, defn["material"], -defn["material_qty"]
        )
        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.server_id,
            project_type="uber_statue",
            target_id=defn["slot"],
            required_turns=defn["build_dt"],
            data={"statue_type": self.statue_type},
        )
        self.shrine_view._pending_projects = (
            await self.bot.database.settlement.get_projects(
                self.user_id, self.server_id
            )
        )
        self._processing = False
        self._rebuild_ui()

        queued_embed = discord.Embed(
            title=f"🔨 {defn['name']} — Construction Queued",
            description=(
                f"**{defn['name']}** construction has been queued.\n\n"
                f"1× {defn['material_name']} deducted. "
                f"Completes after **{defn['build_dt']} Development Turns**.\n"
                "Use **Next Turn** on your settlement dashboard to advance it."
            ),
            color=discord.Color.orange(),
        )
        await interaction.edit_original_response(
            embed=queued_embed, view=self.shrine_view.parent
        )
        self.shrine_view.stop()
        self.stop()
        await asyncio.sleep(3)
        self.shrine_view.parent._rebuild_ui()
        await interaction.edit_original_response(
            embed=self.shrine_view.parent.build_embed(),
            view=self.shrine_view.parent,
        )

    async def _on_manage_workers(self, interaction: Interaction):
        statue_data = self._data()
        current = statue_data.get("workers_assigned", 0)
        max_w = self._statue_worker_cap()
        modal = _StatueWorkerModal(self, max_w, current)
        await interaction.response.send_modal(modal)

    async def _on_max_workers(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        cap = self._statue_worker_cap()
        current = self._data().get("workers_assigned", 0)
        free = self._free_workers()
        target = min(cap, free + current)

        if target <= current:
            self._processing = False
            return await interaction.response.send_message(
                "Already at maximum capacity.", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.settlement.set_statue_workers(
            self.user_id, self.server_id, self.statue_type, target
        )
        self.shrine_view.statue_data[self.statue_type]["workers_assigned"] = target
        self._processing = False
        self._rebuild_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _on_upgrade(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        defn = self._defn()
        data = self._data()
        current_tier = data.get("tier", 1)
        target_tier = current_tier + 1

        gold_cost = STATUE_UPGRADE_GOLD.get(target_tier, 0)
        mat_qty = STATUE_UPGRADE_MATERIAL_QTY.get(target_tier, 0)
        dt_cost = STATUE_UPGRADE_DT.get(target_tier, 40)

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < gold_cost:
            self._processing = False
            return await interaction.response.send_message(
                f"Need **{gold_cost:,} gold** (you have **{gold:,}**).",
                ephemeral=True,
            )

        owned_mat = await self.bot.database.users.get_currency(
            self.user_id, defn["material"]
        )
        if owned_mat < mat_qty:
            self._processing = False
            return await interaction.response.send_message(
                f"Need **{mat_qty}× {defn['material_name']}** "
                f"(you have {owned_mat}).",
                ephemeral=True,
            )

        await interaction.response.defer()

        await self.bot.database.users.modify_gold(self.user_id, -gold_cost)
        await self.bot.database.users.modify_currency(
            self.user_id, defn["material"], -mat_qty
        )

        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.server_id,
            project_type="statue_upgrade",
            target_id=defn["slot"],
            required_turns=dt_cost,
            data={"statue_type": self.statue_type, "target_tier": target_tier},
        )
        self.shrine_view._pending_projects = (
            await self.bot.database.settlement.get_projects(
                self.user_id, self.server_id
            )
        )
        self._processing = False
        self._rebuild_ui()

        queued_embed = discord.Embed(
            title=f"⏳ {defn['name']} — Upgrade Queued",
            description=(
                f"**{defn['name']}** upgrade to Tier {target_tier} has been queued.\n\n"
                f"Resources deducted. Completes after **{dt_cost} Development Turns**.\n"
                "Use **Next Turn** on your settlement dashboard to advance it."
            ),
            color=discord.Color.orange(),
        )
        await interaction.edit_original_response(
            embed=queued_embed, view=self.shrine_view.parent
        )
        self.shrine_view.stop()
        self.stop()
        await asyncio.sleep(3)
        self.shrine_view.parent._rebuild_ui()
        await interaction.edit_original_response(
            embed=self.shrine_view.parent.build_embed(),
            view=self.shrine_view.parent,
        )

    async def _on_back(self, interaction: Interaction):
        self.shrine_view._rebuild_ui()
        await interaction.response.edit_message(
            embed=self.shrine_view.build_embed(), view=self.shrine_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# Main Uber Shrine view
# ---------------------------------------------------------------------------


class UberShrineView(SettlementBaseView):
    """
    Monument Hall to the Gods — main view for the Uber Shrine building.
    Presents a slot select menu (number of slots = shrine building tier).
    """

    def __init__(
        self,
        bot,
        user_id: str,
        parent,
        building,
        plot=None,
        adj_bonus: dict | None = None,
    ):
        super().__init__(bot, user_id)
        self.parent = parent  # PlotDetailView (or BuildingDetailView for legacy)
        self.building = building
        self.plot = plot
        self.adj_bonus: dict = adj_bonus or {}
        self.plot_bonus_type: str | None = plot.bonus_type if plot else None
        self.server_id: str = (
            parent.server_id
            if hasattr(parent, "server_id")
            else parent.parent.server_id
        )
        self.statue_data: dict[str, dict] = {}
        self._pending_projects: list = []
        self._processing = False

    async def _load(self) -> None:
        self.statue_data = await self.bot.database.settlement.get_uber_shrine_statues(
            self.user_id, self.server_id
        )
        self._pending_projects = await self.bot.database.settlement.get_projects(
            self.user_id, self.server_id
        )
        self._rebuild_ui()

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        shrine_tier = self.building.tier
        lines = []
        for slot_num in range(1, 6):
            statue_type = _SLOT_ORDER[slot_num - 1]
            if slot_num > shrine_tier:
                lines.append(
                    f"**Slot {slot_num}** — 🔒 *Locked (upgrade shrine to T{slot_num})*"
                )
                continue

            defn = UBER_STATUE_DEFS[statue_type]
            data = self.statue_data.get(statue_type, {})
            is_unlocked = data.get("is_unlocked", False)
            can_build = data.get("can_build", False)
            statue_tier = data.get("tier", 1)
            workers = data.get("workers_assigned", 0)

            pending_build = any(
                p.get("project_type") in ("uber_statue", "statue_upgrade")
                and (p.get("data") or {}).get("statue_type") == statue_type
                for p in self._pending_projects
            )

            if is_unlocked:
                max_w = get_effective_max_workers(
                    "uber_shrine",
                    statue_tier,
                    self.plot_bonus_type,
                    self.adj_bonus.get("shrine_cap_x2", False),
                    self.adj_bonus.get("has_watchtower", False),
                )
                tier_str = f"T{statue_tier}"
                if pending_build:
                    tier_str += " *(upgrading)*"
                lines.append(
                    f"**Slot {slot_num}** — {defn['emoji']} **{defn['name']}** "
                    f"{tier_str} — {workers:,}/{max_w:,} workers"
                )
            elif pending_build:
                lines.append(
                    f"**Slot {slot_num}** — {defn['emoji']} **{defn['name']}** "
                    f"🏗️ *construction in progress*"
                )
            elif can_build:
                lines.append(
                    f"**Slot {slot_num}** — {defn['emoji']} **{defn['name']}** "
                    f"📋 *blueprint ready — {defn['build_dt']} DTs + "
                    f"1× {defn['material_name']}*"
                )
            else:
                lines.append(
                    f"**Slot {slot_num}** — {defn['emoji']} **{defn['name']}** "
                    f"🔒 *defeat {defn['boss_name']} for the blueprint*"
                )

        embed = discord.Embed(
            title="🏛️ Monument Hall to the Gods",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="📖 About",
            value=(
                "Each statue slot houses a shrine dedicated to a vanquished uber boss. "
                "Construct statues to grant additional sigil drop chances during uber encounters. "
                "Upgrade statues to raise their worker cap and effectiveness."
            ),
            inline=False,
        )
        embed.add_field(
            name="🏛️ Shrine",
            value=f"Tier {shrine_tier}/5 · {shrine_tier} slot{'s' if shrine_tier != 1 else ''} available",
            inline=True,
        )
        if self.plot_bonus_type:
            from core.settlement.plots import PLOT_BONUS_TABLE
            bonus_data = PLOT_BONUS_TABLE.get(self.plot_bonus_type, {})
            embed.add_field(
                name="📍 Terrain Bonus",
                value=f"{bonus_data.get('emoji', '')} **{bonus_data.get('label', self.plot_bonus_type)}**",
                inline=True,
            )
        embed.set_footer(text="Select a slot to manage or construct a statue.")
        return embed

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _rebuild_ui(self):
        self.clear_items()
        shrine_tier = self.building.tier

        options = []
        for slot_num in range(1, shrine_tier + 1):
            statue_type = _SLOT_ORDER[slot_num - 1]
            defn = UBER_STATUE_DEFS[statue_type]
            data = self.statue_data.get(statue_type, {})
            is_unlocked = data.get("is_unlocked", False)
            can_build = data.get("can_build", False)
            statue_tier = data.get("tier", 1)
            workers = data.get("workers_assigned", 0)

            pending_build = any(
                p.get("project_type") in ("uber_statue", "statue_upgrade")
                and (p.get("data") or {}).get("statue_type") == statue_type
                for p in self._pending_projects
            )

            if is_unlocked:
                desc = f"T{statue_tier} — {workers:,} workers assigned"
            elif pending_build:
                desc = "Construction/upgrade in progress"
            elif can_build:
                desc = "Blueprint ready — tap to construct"
            else:
                desc = f"Defeat {defn['boss_name']} to unlock"

            options.append(
                SelectOption(
                    label=f"Slot {slot_num} — {defn['name']}",
                    value=statue_type,
                    description=desc[:100],
                    emoji=defn["emoji"],
                )
            )

        if options:
            sel = ui.Select(
                placeholder="Select a statue slot to manage…",
                options=options,
                row=0,
            )
            sel.callback = self._on_slot_select
            self.add_item(sel)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back.callback = self._on_back
        self.add_item(back)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_slot_select(self, interaction: Interaction):
        statue_type = interaction.data["values"][0]
        slot_view = StatueSlotView(self.bot, self.user_id, self, statue_type)
        await interaction.response.edit_message(
            embed=slot_view.build_embed(), view=slot_view
        )

    async def _on_back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
