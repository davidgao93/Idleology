# core/settlement/views/uber_shrine.py
"""
UberShrineView — Monument Hall to the Gods.

Flow:
  Main view    → slot select menu (slots 1–N, N = shrine building tier)
  Empty slot   → EmptySlotView: pick which statue type to construct
  Occupied slot → StatueSlotView: Manage Workers / Max Workers / Upgrade / Back
"""

from __future__ import annotations

import asyncio

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.emojis import GOLD_COIN
from core.settlement.constants import (
    STATUE_UPGRADE_DT,
    STATUE_UPGRADE_GOLD,
    STATUE_UPGRADE_MATERIAL_QTY,
    UBER_STATUE_DEFS,
)
from core.settlement.plots import get_effective_max_workers

from .base import SettlementBaseView

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _refresh_parent(parent) -> None:
    """Call whichever button-rebuild method the parent view exposes."""
    if hasattr(parent, "_build_buttons"):
        _refresh_parent(parent)
    elif hasattr(parent, "_rebuild_ui"):
        parent._rebuild_ui()
    elif hasattr(parent, "setup_ui"):
        parent.setup_ui()


def _next_free_slot(statue_data: dict[str, dict]) -> int:
    """Return the lowest slot index (1–5) not yet occupied by a built statue."""
    occupied = {
        d["slot_index"] for d in statue_data.values() if d.get("slot_index", 0) > 0
    }
    for i in range(1, 6):
        if i not in occupied:
            return i
    return 0  # all slots full


def _statues_by_slot(statue_data: dict[str, dict]) -> dict[int, tuple[str, dict]]:
    """Return {slot_index: (statue_type, data)} for built statues only."""
    result: dict[int, tuple[str, dict]] = {}
    for stype, d in statue_data.items():
        if d.get("is_unlocked") and d.get("slot_index", 0) > 0:
            result[d["slot_index"]] = (stype, d)
    return result


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
        data = sv.shrine_view.statue_data.get(sv.statue_type, {})
        max_w = sv._statue_worker_cap()
        if val > max_w:
            return await interaction.response.send_message(
                f"This statue can only hold **{max_w:,}** workers.", ephemeral=True
            )
        current = data.get("workers_assigned", 0)
        free = sv._free_workers()
        if val > free + current:
            return await interaction.response.send_message(
                f"Not enough free followers — only **{free + current:,}** available "
                f"(including this statue's current {current:,}).",
                ephemeral=True,
            )

        await sv.shrine_view.bot.database.settlement.set_statue_workers(
            sv.shrine_view.user_id, sv.shrine_view.server_id, sv.statue_type, val
        )
        sv.shrine_view.statue_data[sv.statue_type]["workers_assigned"] = val
        sv._rebuild_ui()
        await interaction.response.edit_message(embed=sv.build_embed(), view=sv)


# ---------------------------------------------------------------------------
# Empty slot — construct view
# ---------------------------------------------------------------------------


class EmptySlotView(SettlementBaseView):
    """Shown when a player selects an empty shrine slot; lets them pick a statue to construct."""

    def __init__(
        self, bot, user_id: str, shrine_view: "UberShrineView", slot_index: int
    ):
        super().__init__(bot, user_id)
        self.shrine_view = shrine_view
        self.slot_index = slot_index
        self.server_id = shrine_view.server_id
        self._processing = False
        self._rebuild_ui()

    def _available_types(self) -> list[str]:
        """Statue types that have a blueprint but haven't been built yet and aren't queued."""
        queued_types = {
            (p.get("data") or {}).get("statue_type")
            for p in self.shrine_view._pending_projects
            if p.get("project_type") == "uber_statue"
        }
        result = []
        for stype, d in self.shrine_view.statue_data.items():
            if (
                d.get("can_build")
                and not d.get("is_unlocked")
                and stype not in queued_types
            ):
                result.append(stype)
        return result

    def build_embed(self) -> discord.Embed:
        available = self._available_types()
        embed = discord.Embed(
            title=f"🏛️ Slot {self.slot_index} — Empty",
            color=discord.Color.dark_grey(),
        )
        if not available:
            embed.description = (
                "No statue blueprints are available for this slot.\n\n"
                "Defeat uber bosses to earn blueprints:\n"
                + "\n".join(
                    f"• {d['emoji']} **{d['name']}** — defeat **{d['boss_name']}**"
                    for d in UBER_STATUE_DEFS.values()
                    if not self.shrine_view.statue_data.get(d.get("key", ""), {}).get(
                        "is_unlocked"
                    )
                )
            )
        else:
            embed.description = (
                f"Select a statue to construct in **Slot {self.slot_index}**.\n\n"
                "Construction costs Development Turns only — no materials required."
            )
            for stype in available:
                defn = UBER_STATUE_DEFS[stype]
                embed.add_field(
                    name=f"{defn['emoji']} {defn['name']}",
                    value=(
                        f"⏱️ {defn['build_dt']} DTs\n"
                        f"Dedicated to **{defn['boss_name']}** — improves sigil drop rate."
                    ),
                    inline=False,
                )
        return embed

    def _rebuild_ui(self):
        self.clear_items()
        available = self._available_types()
        if available:
            options = [
                SelectOption(
                    label=UBER_STATUE_DEFS[stype]["name"],
                    value=stype,
                    description=f"{UBER_STATUE_DEFS[stype]['build_dt']} Development Turns to construct",
                    emoji=UBER_STATUE_DEFS[stype]["emoji"],
                )
                for stype in available
            ]
            sel = ui.Select(
                placeholder="Choose a statue to construct…", options=options, row=0
            )
            sel.callback = self._on_type_select
            self.add_item(sel)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1)
        back.callback = self._on_back
        self.add_item(back)

    async def _on_type_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        statue_type = interaction.data["values"][0]
        defn = UBER_STATUE_DEFS[statue_type]

        await interaction.response.defer()
        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.server_id,
            project_type="uber_statue",
            target_id=self.slot_index,
            required_turns=defn["build_dt"],
            data={"statue_type": statue_type, "slot_index": self.slot_index},
        )
        self.shrine_view._pending_projects = (
            await self.bot.database.settlement.get_projects(
                self.user_id, self.server_id
            )
        )
        self._processing = False

        queued_embed = discord.Embed(
            title=f"🔨 {defn['name']} — Construction Queued",
            description=(
                f"**{defn['name']}** will be constructed in **Slot {self.slot_index}**.\n\n"
                f"Completes after **{defn['build_dt']} Development Turns**.\n"
                "Use **Next Turn** on your settlement dashboard to advance it."
            ),
            color=discord.Color.orange(),
        )
        parent = self.shrine_view.parent
        await interaction.edit_original_response(embed=queued_embed, view=ui.View())
        self.shrine_view.stop()
        self.stop()
        await asyncio.sleep(3)
        _refresh_parent(parent)
        await interaction.edit_original_response(
            embed=parent.build_embed(), view=parent
        )

    async def _on_back(self, interaction: Interaction):
        self.shrine_view._rebuild_ui()
        await interaction.response.edit_message(
            embed=self.shrine_view.build_embed(), view=self.shrine_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# Statue slot sub-view (occupied slot)
# ---------------------------------------------------------------------------


class StatueSlotView(SettlementBaseView):
    """Manages a single built statue slot inside the Uber Shrine."""

    def __init__(
        self,
        bot,
        user_id: str,
        shrine_view: "UberShrineView",
        statue_type: str,
        slot_index: int,
    ):
        super().__init__(bot, user_id)
        self.shrine_view = shrine_view
        self.statue_type = statue_type
        self.slot_index = slot_index
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

    def _statue_worker_cap(self) -> int:
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
        sv = self.shrine_view
        parent = sv.parent
        dashboard = getattr(parent, "parent", parent)
        settlement = getattr(dashboard, "settlement", None)
        follower_count = getattr(parent, "follower_count", 0) or getattr(
            dashboard, "follower_count", 0
        )
        building_workers = (
            sum(b.workers_assigned for b in settlement.buildings) if settlement else 0
        )
        statue_workers = sum(
            d.get("workers_assigned", 0) for d in sv.statue_data.values()
        )
        current = self._data().get("workers_assigned", 0)
        used = building_workers + statue_workers - current
        return max(0, follower_count - used)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        defn = self._defn()
        data = self._data()
        statue_tier = data.get("tier", 1)
        workers = data.get("workers_assigned", 0)
        max_w = self._statue_worker_cap()

        upgrade_pending = any(
            p.get("project_type") == "statue_upgrade"
            and p.get("target_id") == self.slot_index
            for p in self.shrine_view._pending_projects
        )

        tier_str = f"T{statue_tier}/5"
        if upgrade_pending:
            tier_str += " *(upgrade in progress)*"

        embed = discord.Embed(
            title=f"🏛️ Slot {self.slot_index} — {defn['emoji']} {defn['name']}",
            color=discord.Color.gold(),
        )
        sv = self.shrine_view
        shrine_eff = 1.0
        eff_sources: list[str] = []
        if sv.plot_bonus_type == "sacred_ground":
            shrine_eff += 0.20
            eff_sources.append("Sacred Ground +20%")
        shrine_boost = sv.adj_bonus.get("shrine_boost", 0.0)
        if shrine_boost > 0:
            shrine_eff += shrine_boost
            eff_sources.append(f"Shrine Garden +{shrine_boost:.0%}")
        bonus_pct = workers * 0.05 * shrine_eff
        cap_pct = statue_tier * 100 * 0.05 * shrine_eff
        effect_line = (
            f"**50%** base sigil drop + **{bonus_pct:.2f}%** bonus second drop "
            f"(cap ≈ {cap_pct:.2f}% at T{statue_tier})"
        )
        if eff_sources:
            effect_line += (
                f"\n_Effectiveness ×{shrine_eff:.2f}: {', '.join(eff_sources)}_"
            )

        embed.description = (
            f"**Tier:** {tier_str}\n"
            f"**Workers:** {workers:,}/{max_w:,}\n\n"
            f"Dedicated to **{defn['boss_name']}** — improves her sigil drop rate.\n\n"
            f"⚡ **Current Effect:** {effect_line}"
        )

        if statue_tier < 5:
            next_tier = statue_tier + 1
            mat_qty = STATUE_UPGRADE_MATERIAL_QTY.get(next_tier, 0)
            gold_cost = STATUE_UPGRADE_GOLD.get(next_tier, 0)
            dt_cost = STATUE_UPGRADE_DT.get(next_tier, 0)
            embed.add_field(
                name=f"⬆️ Upgrade to T{next_tier} Cost",
                value=(
                    f"{GOLD_COIN} {gold_cost:,} | "
                    f"{defn['material_name']} ×{mat_qty} | "
                    f"⏱️ {dt_cost} DTs"
                ),
                inline=False,
            )
        else:
            embed.add_field(name="Status", value="🌟 Max Tier Reached", inline=False)

        embed.set_footer(
            text=f"Monument Hall — Slot {self.slot_index}/5  |  "
            f"Shrine T{self.shrine_view.building.tier}"
        )
        return embed

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _rebuild_ui(self):
        self.clear_items()
        data = self._data()
        statue_tier = data.get("tier", 1)

        upgrade_pending = any(
            p.get("project_type") == "statue_upgrade"
            and p.get("target_id") == self.slot_index
            for p in self.shrine_view._pending_projects
        )

        btn_workers = ui.Button(
            label="Manage Workers", style=ButtonStyle.primary, emoji="👥", row=0
        )
        btn_workers.callback = self._on_manage_workers
        self.add_item(btn_workers)

        btn_max = ui.Button(
            label="Max Workers", style=ButtonStyle.primary, emoji="⬆️", row=0
        )
        btn_max.callback = self._on_max_workers
        self.add_item(btn_max)

        if statue_tier < 5 and not upgrade_pending:
            btn_up = ui.Button(
                label=f"Upgrade to T{statue_tier + 1}",
                style=ButtonStyle.success,
                emoji="✨",
                row=0,
            )
            btn_up.callback = self._on_upgrade
            self.add_item(btn_up)
        elif upgrade_pending:
            self.add_item(
                ui.Button(
                    label="⏳ Upgrade in progress…",
                    style=ButtonStyle.secondary,
                    disabled=True,
                    row=0,
                )
            )

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1)
        back.callback = self._on_back
        self.add_item(back)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_manage_workers(self, interaction: Interaction):
        data = self._data()
        current = data.get("workers_assigned", 0)
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
        current_tier = self._data().get("tier", 1)
        target_tier = current_tier + 1

        gold_cost = STATUE_UPGRADE_GOLD.get(target_tier, 0)
        mat_qty = STATUE_UPGRADE_MATERIAL_QTY.get(target_tier, 0)
        dt_cost = STATUE_UPGRADE_DT.get(target_tier, 40)

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < gold_cost:
            self._processing = False
            return await interaction.response.send_message(
                f"Need **{gold_cost:,} gold** (you have **{gold:,}**).", ephemeral=True
            )
        _mats = await self.bot.database.settlement_materials.get_all(self.user_id)
        owned_mat = _mats.get(defn["material"], 0)
        if owned_mat < mat_qty:
            self._processing = False
            return await interaction.response.send_message(
                f"Need **{mat_qty}× {defn['material_name']}** (you have {owned_mat}).",
                ephemeral=True,
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_gold(self.user_id, -gold_cost)
        await self.bot.database.settlement_materials.modify(
            self.user_id, defn["material"], -mat_qty
        )

        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.server_id,
            project_type="statue_upgrade",
            target_id=self.slot_index,
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
        parent = self.shrine_view.parent
        await interaction.edit_original_response(embed=queued_embed, view=ui.View())
        self.shrine_view.stop()
        self.stop()
        await asyncio.sleep(3)
        _refresh_parent(parent)
        await interaction.edit_original_response(
            embed=parent.build_embed(), view=parent
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
    """Monument Hall to the Gods — main view for the Uber Shrine building."""

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
        self.parent = parent
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
        by_slot = _statues_by_slot(self.statue_data)

        # Pending constructions: slot_index → statue_type
        pending_builds: dict[int, str] = {}
        for p in self._pending_projects:
            if p.get("project_type") == "uber_statue":
                si = p.get("target_id") or (p.get("data") or {}).get("slot_index", 0)
                st = (p.get("data") or {}).get("statue_type")
                if si and st:
                    pending_builds[si] = st

        lines = []
        for slot_num in range(1, 6):
            if slot_num > shrine_tier:
                lines.append(
                    f"**Slot {slot_num}** — 🔒 *Locked (upgrade shrine to T{slot_num})*"
                )
                continue

            if slot_num in by_slot:
                stype, d = by_slot[slot_num]
                defn = UBER_STATUE_DEFS[stype]
                statue_tier = d.get("tier", 1)
                workers = d.get("workers_assigned", 0)
                max_w = get_effective_max_workers(
                    "uber_shrine",
                    statue_tier,
                    self.plot_bonus_type,
                    self.adj_bonus.get("shrine_cap_x2", False),
                    self.adj_bonus.get("has_watchtower", False),
                )
                upgrading = any(
                    p.get("project_type") == "statue_upgrade"
                    and p.get("target_id") == slot_num
                    for p in self._pending_projects
                )
                tier_str = f"T{statue_tier}" + (" *(upgrading)*" if upgrading else "")
                lines.append(
                    f"**Slot {slot_num}** — {defn['emoji']} **{defn['name']}** "
                    f"{tier_str} — {workers:,}/{max_w:,} workers"
                )
            elif slot_num in pending_builds:
                stype = pending_builds[slot_num]
                defn = UBER_STATUE_DEFS[stype]
                lines.append(
                    f"**Slot {slot_num}** — {defn['emoji']} **{defn['name']}** 🏗️ *under construction*"
                )
            else:
                lines.append(
                    f"**Slot {slot_num}** — *(empty — select to construct a statue)*"
                )

        embed = discord.Embed(
            title="🏛️ Monument Hall to the Gods",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="📖 About",
            value=(
                "Each slot houses a shrine statue dedicated to a vanquished uber boss. "
                "Construct statues to boost sigil drop chances during uber encounters. "
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
        by_slot = _statues_by_slot(self.statue_data)

        pending_builds: dict[int, str] = {}
        for p in self._pending_projects:
            if p.get("project_type") == "uber_statue":
                si = p.get("target_id") or (p.get("data") or {}).get("slot_index", 0)
                st = (p.get("data") or {}).get("statue_type")
                if si and st:
                    pending_builds[si] = st

        options = []
        for slot_num in range(1, shrine_tier + 1):
            if slot_num in by_slot:
                stype, d = by_slot[slot_num]
                defn = UBER_STATUE_DEFS[stype]
                statue_tier = d.get("tier", 1)
                workers = d.get("workers_assigned", 0)
                desc = f"T{statue_tier} — {workers:,} workers assigned"
                options.append(
                    SelectOption(
                        label=f"Slot {slot_num} — {defn['name']}",
                        value=f"occupied:{slot_num}:{stype}",
                        description=desc[:100],
                        emoji=defn["emoji"],
                    )
                )
            elif slot_num in pending_builds:
                stype = pending_builds[slot_num]
                defn = UBER_STATUE_DEFS[stype]
                options.append(
                    SelectOption(
                        label=f"Slot {slot_num} — {defn['name']}",
                        value=f"pending:{slot_num}:{stype}",
                        description="Construction in progress",
                        emoji="🏗️",
                    )
                )
            else:
                options.append(
                    SelectOption(
                        label=f"Slot {slot_num} — Empty",
                        value=f"empty:{slot_num}",
                        description="Tap to construct a statue",
                        emoji="🔲",
                    )
                )

        if options:
            sel = ui.Select(
                placeholder="Select a shrine slot to manage…", options=options, row=0
            )
            sel.callback = self._on_slot_select
            self.add_item(sel)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1)
        back.callback = self._on_back
        self.add_item(back)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_slot_select(self, interaction: Interaction):
        value = interaction.data["values"][0]
        parts = value.split(":")

        if parts[0] == "empty":
            slot_index = int(parts[1])
            view = EmptySlotView(self.bot, self.user_id, self, slot_index)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

        elif parts[0] == "occupied":
            slot_index = int(parts[1])
            statue_type = parts[2]
            view = StatueSlotView(self.bot, self.user_id, self, statue_type, slot_index)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

        elif parts[0] == "pending":
            # Construction in progress — show info only
            slot_index = int(parts[1])
            statue_type = parts[2]
            defn = UBER_STATUE_DEFS[statue_type]
            proj = next(
                (
                    p
                    for p in self._pending_projects
                    if p.get("project_type") == "uber_statue"
                    and p.get("target_id") == slot_index
                ),
                None,
            )
            remaining = (
                (proj["required_turns"] - proj["invested_turns"]) if proj else "?"
            )
            embed = discord.Embed(
                title=f"🏗️ Slot {slot_index} — {defn['name']} Under Construction",
                description=f"**{defn['name']}** is being constructed in this slot.\n\n"
                f"**Turns remaining:** {remaining}\n"
                "Use **Next Turn** on the dashboard to advance the project.",
                color=discord.Color.orange(),
            )
            self._rebuild_ui()
            await interaction.response.edit_message(embed=embed, view=self)

    async def _on_back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
