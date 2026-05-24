# core/settlement/views/plot_detail.py
"""
PlotDetailView — shown when a player selects a specific grid cell.

Handles three states:
  • Undeveloped  → offer to develop (costs Development Contracts)
  • Developed + empty → offer to build regular or meta building
  • Developed + occupied → offer to manage the existing building
"""
from __future__ import annotations

import asyncio
import random

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.images import SETTLEMENT_HUB
from core.settlement.constants import (
    BUILD_MESSAGES,
    BUILDING_INFO,
    CONSTRUCTION_COSTS,
    RESOURCE_DISPLAY_NAMES,
)
from core.settlement.mechanics import SettlementMechanics
from core.settlement.models import Building, Plot, Settlement
from core.settlement.plots import (
    META_BUILDINGS,
    PLOT_BONUS_TABLE,
    SHRINE_BUILDING_TYPES,
    get_effective_max_workers,
    roll_plot_bonus,
)
from core.settlement.views.research import RESEARCHABLE_BUILDINGS

from .base import SettlementBaseView

# ---------------------------------------------------------------------------
# Building detail helpers  (output / effect display for PlotDetailView)
# ---------------------------------------------------------------------------

_OUTPUT_DISPLAY: dict[str, tuple[str, str]] = {
    "timber":           ("🪵", "Timber"),
    "stone":            ("🪨", "Stone"),
    "market_gold":      ("💰", "Gold"),
    "companion_cookie": ("🐾", "Companion XP"),
    "war_camp_stamina": ("⚔️", "Combat Stamina"),
}

_NO_WORKERS = "_No workers assigned — assign workers to begin production._"


def _gen_effectiveness(
    building_type: str,
    plot_bonus_type: str | None,
    adj: dict,
    extra_rate: float = 0.0,
) -> tuple[float, float]:
    """
    Returns (effectiveness_multiplier, effective_base_rate_addition) for a
    generator building.  Both values are additive on top of base values.
    """
    eff = 1.0
    if plot_bonus_type:
        b = PLOT_BONUS_TABLE.get(plot_bonus_type, {})
        applies = b.get("applies_to", "none")
        val = b.get("value", 0.0)
        if applies == "generator_mult":
            eff += val
        elif applies == "trade_mult" and building_type in ("market", "war_camp"):
            eff += val
    eff += adj.get("production_mult", 0.0)
    return eff, extra_rate  # extra_rate only used by war_camp


def _conv_effectiveness(plot_bonus_type: str | None, adj: dict) -> float:
    eff = 1.0
    if plot_bonus_type:
        b = PLOT_BONUS_TABLE.get(plot_bonus_type, {})
        if b.get("applies_to") == "converter_mult":
            eff += b.get("value", 0.0)
    eff += adj.get("converter_mult", 0.0)
    return eff


def _append_building_detail_fields(
    embed: discord.Embed,
    b,
    plot_bonus_type: str | None,
    adj: dict,
) -> None:
    """
    Appends an 'About' description field and an 'Output / Effect' field
    to *embed* for an occupied plot.  Operates in-place.
    """
    # ── About ───────────────────────────────────────────────────────────
    if b.is_meta:
        desc_text = META_BUILDINGS.get(b.building_type, {}).get("description", "")
    else:
        desc_text = BUILDING_INFO.get(b.building_type, "")
    if desc_text:
        embed.add_field(name="📖 About", value=desc_text, inline=False)

    # ── Output / Effect ─────────────────────────────────────────────────
    if b.is_meta:
        _append_meta_effect(embed, b)
        return

    b_data = SettlementMechanics.BUILDINGS.get(b.building_type, {})
    category = b_data.get("type", "")

    if category == "generator":
        _append_generator(embed, b, b_data, plot_bonus_type, adj)
    elif category == "converter":
        _append_converter(embed, b, b_data, plot_bonus_type, adj)
    elif category == "passive":
        _append_passive_effect(embed, b)
    # "special" (black_market, hatchery) and "core" (town_hall) — no output field


def _append_generator(embed, b, b_data: dict, plot_bonus_type, adj: dict) -> None:
    workers = b.workers_assigned
    base_rate: float = b_data["base_rate"]
    output_key: str = b_data["output"]

    if b.building_type == "war_camp":
        base_rate += adj.get("war_camp_rate", 0.0)

    eff, _ = _gen_effectiveness(b.building_type, plot_bonus_type, adj)
    rate = base_rate * b.tier * workers * eff

    emoji, label = _OUTPUT_DISPLAY.get(
        output_key, ("📦", output_key.replace("_", " ").title())
    )

    if workers == 0:
        value = _NO_WORKERS
    elif output_key == "war_camp_stamina":
        value = f"{emoji} **{label}:** ~{rate:.4f}/hr"
    elif output_key == "companion_cookie":
        value = f"{emoji} **{label}:** ~{rate:.2f}/hr"
    elif output_key == "market_gold":
        value = f"{emoji} **{label}:** ~{int(rate):,}/hr"
    else:
        value = f"{emoji} **{label}:** ~{rate:.1f}/hr"

    if workers > 0 and eff > 1.0:
        value += f"\n_×{eff:.2f} effectiveness from bonuses_"

    embed.add_field(name="📊 Output", value=value, inline=False)


def _append_converter(embed, b, b_data: dict, plot_bonus_type, adj: dict) -> None:
    workers = b.workers_assigned

    if workers == 0:
        embed.add_field(
            name=f"📊 Conversions (T{b.tier})",
            value=_NO_WORKERS,
            inline=False,
        )
        return

    eff = _conv_effectiveness(plot_bonus_type, adj)
    rates = SettlementMechanics.get_converter_rates(b.building_type, b.tier, workers)
    if not rates:
        return

    lines = []
    for raw_key, refined_key, base_hr in rates:
        adjusted = int(base_hr * eff)
        raw_name = RESOURCE_DISPLAY_NAMES.get(raw_key, raw_key.replace("_", " ").title())
        ref_name = RESOURCE_DISPLAY_NAMES.get(refined_key, refined_key.replace("_", " ").title())
        lines.append(f"• {raw_name} → {ref_name}: ~**{adjusted:,}**/hr")

    if eff > 1.0:
        lines.append(f"_×{eff:.2f} effectiveness from bonuses_")

    embed.add_field(
        name=f"📊 Conversions (T{b.tier} — {len(rates)} active slot{'s' if len(rates) != 1 else ''})",
        value="\n".join(lines),
        inline=False,
    )


def _append_passive_effect(embed, b) -> None:
    workers = b.workers_assigned
    btype = b.building_type

    if workers == 0:
        embed.add_field(
            name="⚡ Current Effect",
            value="_No workers assigned — passive is inactive._",
            inline=False,
        )
        return

    if btype == "barracks":
        pct = workers / 100
        value = f"+**{pct:.1f}%** ATK & DEF"
    elif btype == "temple":
        pct = workers * 5 / 100
        value = f"+**{pct:.1f}%** Propagate follower gain"
    elif btype == "apothecary":
        pct = workers * 0.02
        value = f"+**{pct:.1f}%** Potion healing"
    elif btype in SHRINE_BUILDING_TYPES:
        value = f"Passive sigil drop bonus — scales with Tier **T{b.tier}**"
    else:
        value = "Passive effect active."

    embed.add_field(name="⚡ Current Effect", value=value, inline=False)


def _append_meta_effect(embed, b) -> None:
    meta_data = META_BUILDINGS.get(b.building_type, {})
    workers = b.workers_assigned
    btype = b.building_type

    if btype == "watchtower":
        # Passive — no workers needed
        embed.add_field(
            name="⚙️ Adjacency Effect",
            value=(
                "Each regular building's worker cap is increased by **+1% per its own tier** "
                "(T1 → +1 worker per 100, T5 → +5). Global, passive."
            ),
            inline=False,
        )
        return

    if workers == 0:
        embed.add_field(
            name="⚙️ Adjacency Effect",
            value="_No workers assigned — adjacency effect is inactive._",
            inline=False,
        )
        return

    if btype == "servants_quarters":
        # 0.002 per worker → display as %: workers * 0.2
        bonus = min(20.0, workers * 0.2)
        value = f"+**{bonus:.0f}%** output to adjacent production buildings"
    elif btype == "supply_depot":
        value = "+**15%** conversion rate to adjacent converter buildings"
    elif btype == "grand_cathedral":
        value = "Adjacent shrine buildings get **×2** worker cap"
    elif btype == "foremans_post":
        value = "+**25%** output to all adjacent buildings"
    elif btype == "shrine_garden":
        value = "+**15%** effectiveness to adjacent shrine buildings"
    elif btype == "encampment":
        value = "Adjacent War Camps: +**0.005** Combat Stamina/hr per War Camp worker"
    elif btype == "apothecary_annex":
        # 0.0004 per worker → display as %: workers * 0.04
        bonus = workers * 0.04
        value = f"Adjacent Apothecary: +**{bonus:.2f}%** additional healing"
    else:
        value = meta_data.get("description", "Meta building effect active.")

    embed.add_field(name="⚙️ Adjacency Effect", value=value, inline=False)


# ---------------------------------------------------------------------------
# Worker management modal (plot-aware)
# ---------------------------------------------------------------------------

_DC_COST_PER_PLOT = 1  # Each plot costs (plots_developed + 1) DCs, handled dynamically


class PlotWorkerModal(ui.Modal, title="Manage Workforce"):
    count = ui.TextInput(label="Number of Workers", min_length=1, max_length=4)

    def __init__(self, parent_view: "PlotDetailView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.count.value)
            if val < 0:
                raise ValueError

            pv = self.parent_view
            building = pv.building
            adj = pv.adj_bonus or {}

            max_w = get_effective_max_workers(
                building_type=building.building_type,
                tier=building.tier,
                plot_bonus_type=pv.plot.bonus_type if pv.plot else None,
                adj_shrine_cap_x2=adj.get("shrine_cap_x2", False),
                has_watchtower=adj.get("has_watchtower", False),
            )

            if val > max_w:
                return await interaction.response.send_message(
                    f"This building can only hold **{max_w:,}** workers.", ephemeral=True
                )

            # Total settlement workforce check
            total_assigned = sum(
                b.workers_assigned for b in pv.parent.settlement.buildings
            )
            currently_here = building.workers_assigned
            free = pv.parent.follower_count - (total_assigned - currently_here)

            if val > free:
                return await interaction.response.send_message(
                    f"You only have **{free:,}** available followers.", ephemeral=True
                )

            await pv.bot.database.settlement.assign_workers(building.id, val)

            # Refresh settlement state
            pv.parent.settlement = await pv.bot.database.settlement.get_settlement(
                pv.user_id, pv.parent.server_id
            )
            for b in pv.parent.settlement.buildings:
                if b.id == building.id:
                    pv.building = b
                    break

            # Recompute adjacency bonuses — worker counts on meta buildings
            # may have changed, updating what they contribute to neighbours.
            adj_bonuses = SettlementMechanics.calculate_adjacency_bonuses(
                pv.parent.plots, pv.parent.settlement.buildings
            )
            pv.adj_bonus = adj_bonuses.get(pv.plot.plot_index, {})

            # Rebuild buttons so the worker count label is current
            pv._build_buttons()

            await interaction.response.edit_message(
                embed=pv.build_embed(), view=pv
            )
        except ValueError:
            await interaction.response.send_message("Invalid number.", ephemeral=True)


# ---------------------------------------------------------------------------
# PlotDetailView
# ---------------------------------------------------------------------------


class PlotDetailView(SettlementBaseView):
    """
    Detail view for a single settlement plot.

    Parameters
    ----------
    plot : Plot
        The plot data row.
    building : Building | None
        Building on this plot (None if empty).
    adj_bonus : dict | None
        Adjacency bonus dict for this plot from calculate_adjacency_bonuses.
    parent : SettlementDashboardView
        The dashboard to return to.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        plot: Plot,
        building: Building | None,
        parent,
        adj_bonus: dict | None = None,
    ):
        super().__init__(bot, user_id)
        self.plot = plot
        self.building = building
        self.parent = parent      # SettlementDashboardView
        # server_id is a static guild ID — store it directly so BaseView's
        # assignment in __init__ is overridden cleanly (no property needed).
        self.server_id = parent.server_id
        self.adj_bonus = adj_bonus or {}
        self._processing = False
        self._build_buttons()

    # ------------------------------------------------------------------
    # Passthrough properties (so child views like BlackMarketView that
    # expect a dashboard-like parent still work when given a PlotDetailView)
    # ------------------------------------------------------------------

    @property
    def settlement(self):
        return self.parent.settlement

    @settlement.setter
    def settlement(self, value):
        self.parent.settlement = value

    @property
    def follower_count(self) -> int:
        return self.parent.follower_count

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        p = self.plot
        bonus_data = PLOT_BONUS_TABLE.get(p.bonus_type or "", {})
        bonus_label = (
            f"{bonus_data.get('emoji', '')} **{bonus_data['label']}**\n"
            f"{bonus_data['description']}"
            if p.is_developed and p.bonus_type
            else ""
        )

        if not p.is_developed:
            embed = discord.Embed(
                title=f"📍 Plot {p.plot_index} — Undeveloped",
                color=discord.Color.dark_grey(),
            )
            embed.description = (
                "This plot has not been developed yet.\n\n"
                "Develop it to unlock a permanent terrain bonus and build here."
            )
        elif self.building is None:
            embed = discord.Embed(
                title=f"📍 Plot {p.plot_index} — Empty",
                color=discord.Color.green(),
            )
            embed.description = (
                (f"**Terrain Bonus:** {bonus_label}\n\n" if bonus_label else "")
                + "This plot is ready for construction."
            )
        else:
            b = self.building
            b_data = SettlementMechanics.BUILDINGS.get(b.building_type, {})
            adj = self.adj_bonus
            max_w = get_effective_max_workers(
                b.building_type,
                b.tier,
                p.bonus_type,
                adj.get("shrine_cap_x2", False),
                adj.get("has_watchtower", False),
            )
            tier_str = f"T{b.tier}/5" if not b.is_meta else "Meta"
            embed = discord.Embed(
                title=f"📍 Plot {p.plot_index} — {b.name}",
                color=discord.Color.gold(),
            )
            desc = (
                f"**Type:** {tier_str}\n"
                f"**Workers:** {b.workers_assigned:,}/{max_w:,}"
            )
            if bonus_label:
                desc += f"\n\n**Terrain Bonus:** {bonus_label}"
            if adj.get("production_mult") or adj.get("converter_mult"):
                eff = adj.get("production_mult", adj.get("converter_mult", 0.0))
                desc += f"\n🔗 **Adjacency Bonus:** +{eff:.0%} effectiveness"
            if adj.get("shrine_boost"):
                desc += f"\n🌺 **Shrine Garden:** +{adj['shrine_boost']:.0%} effectiveness"
            embed.description = desc

            # Description + quantitative output / effect
            _append_building_detail_fields(embed, b, p.bonus_type, self.adj_bonus)

            # Upgrade cost preview
            if not b.is_meta and b.tier < 5:
                cost = SettlementMechanics.get_upgrade_cost(b.building_type, b.tier)
                cost_str = (
                    f"🪵 {cost.get('timber', 0):,} | "
                    f"🪨 {cost.get('stone', 0):,} | "
                    f"💰 {cost.get('gold', 0):,}"
                )
                if "special_name" in cost:
                    cost_str += f" | ✨ {cost['special_name']} ×{cost['special_qty']}"
                embed.add_field(name="Next Upgrade Cost", value=cost_str, inline=False)

        embed.set_footer(text=f"Settlement Plot {p.plot_index}/20")
        return embed

    # ------------------------------------------------------------------
    # Button layout
    # ------------------------------------------------------------------

    def _build_buttons(self):
        self.clear_items()
        p = self.plot

        if not p.is_developed:
            self._add_develop_button()
        elif self.building is None:
            self._add_build_buttons()
        else:
            self._add_manage_buttons()

        back = ui.Button(label="Back", style=ButtonStyle.secondary, row=4)
        back.callback = self._go_back
        self.add_item(back)

    def _add_develop_button(self):
        total_developed = sum(1 for pl in self.parent.plots if pl.is_developed)
        dc_cost = total_developed + 1
        btn = ui.Button(
            label=f"Develop Plot ({dc_cost} Development Contract{'s' if dc_cost != 1 else ''})",
            style=ButtonStyle.success,
            emoji="🏗️",
            row=0,
        )
        btn.callback = self._develop_plot
        self.add_item(btn)

    def _add_build_buttons(self):
        btn_build = ui.Button(
            label="Build Regular Building",
            style=ButtonStyle.primary,
            emoji="🏗️",
            row=0,
        )
        btn_build.callback = self._open_construction
        self.add_item(btn_build)

        # Meta building button — only if slots available
        th_tier = self.parent.settlement.town_hall_tier
        from core.settlement.plots import get_meta_slots
        meta_cap = get_meta_slots(th_tier)
        meta_used = sum(1 for b in self.parent.settlement.buildings if b.is_meta)
        meta_available = meta_used < meta_cap

        btn_meta = ui.Button(
            label=f"Build Meta Building ({meta_used}/{meta_cap} slots used)",
            style=ButtonStyle.blurple if meta_available else ButtonStyle.secondary,
            emoji="⚙️",
            disabled=not meta_available,
            row=1,
        )
        btn_meta.callback = self._open_meta_construction
        self.add_item(btn_meta)

    def _add_manage_buttons(self):
        b = self.building

        # --- Special case: Black Market opens its own dedicated view ---
        if b.building_type == "black_market":
            btn_bm = ui.Button(
                label="Open Black Market",
                style=ButtonStyle.blurple,
                emoji="⚫",
                row=0,
            )
            btn_bm.callback = self._open_black_market
            self.add_item(btn_bm)

            btn_demo = ui.Button(
                label="Demolish", style=ButtonStyle.danger, emoji="💥", row=1
            )
            btn_demo.callback = self._demolish_confirm
            self.add_item(btn_demo)
            return

        # --- Special case: Hatchery opens its own dedicated view ---
        if b.building_type == "hatchery":
            btn_hatch = ui.Button(
                label="Open Hatchery",
                style=ButtonStyle.success,
                emoji="🐣",
                row=0,
            )
            btn_hatch.callback = self._open_hatchery
            self.add_item(btn_hatch)

        # Workers button (all buildings that accept workers)
        needs_workers = (
            not b.is_meta
            or META_BUILDINGS.get(b.building_type, {}).get("max_workers", 0) > 0
        )
        if needs_workers:
            btn_workers = ui.Button(
                label=f"Manage Workers ({b.workers_assigned:,} assigned)",
                style=ButtonStyle.primary,
                emoji="👥",
                row=0,
            )
            btn_workers.callback = self._manage_workers
            self.add_item(btn_workers)

        if not b.is_meta:
            # Upgrade button
            if b.tier < 5:
                btn_up = ui.Button(
                    label=f"Upgrade to T{b.tier + 1}",
                    style=ButtonStyle.success,
                    emoji="⬆️",
                    row=1,
                )
                btn_up.callback = self._upgrade_building
                self.add_item(btn_up)

        # Demolish button
        btn_demo = ui.Button(
            label="Demolish",
            style=ButtonStyle.danger,
            emoji="💥",
            row=2,
        )
        btn_demo.callback = self._demolish_confirm
        self.add_item(btn_demo)

    # ------------------------------------------------------------------
    # Callbacks — special building launchers
    # ------------------------------------------------------------------

    async def _open_black_market(self, interaction: Interaction):
        from core.settlement.views.black_market import BlackMarketView

        # Pass self as parent so BlackMarketView.go_back() returns here.
        # PlotDetailView exposes .settlement and .server_id as properties.
        view = BlackMarketView(self.bot, self.user_id, self, self.building)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def _open_hatchery(self, interaction: Interaction):
        await interaction.response.defer()
        from core.hatchery.views import HatcheryView

        hview = HatcheryView(
            self.bot,
            self.user_id,
            self.parent.server_id,
            self.building,
            parent_view=self,
        )
        await hview._load()
        hview._rebuild_buttons()
        await interaction.edit_original_response(
            embed=hview.build_embed(), view=hview
        )

    # ------------------------------------------------------------------
    # Callbacks — develop
    # ------------------------------------------------------------------

    async def _develop_plot(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        developed_set = {pl.plot_index for pl in self.parent.plots if pl.is_developed}
        dc_cost = len(developed_set) + 1

        dcs = await self.bot.database.users.get_development_contracts(self.user_id)
        if dcs < dc_cost:
            self._processing = False
            return await interaction.response.send_message(
                f"You need **{dc_cost}** Development Contract(s) (you have **{dcs}**).",
                ephemeral=True,
            )

        await interaction.response.defer()

        # Deduct DCs and mark plot developed with a rolled bonus
        bonus_type = roll_plot_bonus()
        await self.bot.database.users.modify_development_contracts(
            self.user_id, -dc_cost
        )
        await self.bot.database.plots.develop_plot(
            self.user_id, self.parent.server_id, self.plot.plot_index, bonus_type
        )

        # Check milestone: all 20 plots developed → award Settlement Deed
        new_developed = len(developed_set) + 1
        if new_developed == 20:
            await self.bot.database.users.modify_currency(
                self.user_id, "settlement_deed", 1
            )
            await interaction.followup.send(
                "🏆 **All 20 plots developed!** You have been awarded a **Settlement Deed**!",
                ephemeral=True,
            )

        # Refresh local state
        plot_rows = await self.bot.database.plots.get_plots(
            self.user_id, self.parent.server_id
        )
        from core.settlement.models import Plot as PlotModel
        self.parent.plots = [
            PlotModel(plot_index=r[0], is_developed=bool(r[1]), bonus_type=r[2])
            for r in plot_rows
        ]

        # Update self.plot
        self.plot = next(
            (p for p in self.parent.plots if p.plot_index == self.plot.plot_index),
            self.plot,
        )

        bonus_data = PLOT_BONUS_TABLE.get(bonus_type, {})
        bonus_emoji = bonus_data.get("emoji", "")
        bonus_label = bonus_data.get("label", bonus_type)
        self._processing = False
        self._build_buttons()
        embed = self.build_embed()
        embed.title = f"📍 Plot {self.plot.plot_index} — ✅ Developed!"
        await interaction.edit_original_response(content=None, embed=embed, view=self)

    # ------------------------------------------------------------------
    # Callbacks — build regular building
    # ------------------------------------------------------------------

    async def _open_construction(self, interaction: Interaction):
        from core.settlement.views.construction import BuildConstructionView

        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.parent.server_id
        )
        researched = await self.bot.database.settlement.get_researched(
            self.user_id, self.parent.server_id
        )
        view = BuildConstructionView(
            bot=self.bot,
            user_id=self.user_id,
            plot_index=self.plot.plot_index,
            plot_bonus_type=self.plot.bonus_type,
            parent_view=self.parent,
            uber_prog=uber_prog,
            researched=researched,
            return_to_detail=self,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    # ------------------------------------------------------------------
    # Callbacks — build meta building
    # ------------------------------------------------------------------

    async def _open_meta_construction(self, interaction: Interaction):
        view = MetaBuildingConstructionView(
            bot=self.bot,
            user_id=self.user_id,
            plot_index=self.plot.plot_index,
            parent_view=self.parent,
            return_to_detail=self,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    # ------------------------------------------------------------------
    # Callbacks — manage existing building
    # ------------------------------------------------------------------

    async def _manage_workers(self, interaction: Interaction):
        modal = PlotWorkerModal(self)
        await interaction.response.send_modal(modal)

    async def _upgrade_building(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        b = self.building
        target_tier = b.tier + 1
        cost = SettlementMechanics.get_upgrade_cost(b.building_type, b.tier)

        # Apply plot bonus discounts to upgrade cost
        plot_bonus = self.plot.bonus_type if self.plot else None
        if plot_bonus == "gold_vein":
            cost["gold"] = int(cost.get("gold", 0) * 0.65)
        if plot_bonus == "ancient_foundation":
            cost["timber"] = int(cost.get("timber", 0) * 0.70)
            cost["stone"] = int(cost.get("stone", 0) * 0.70)

        # Check resources
        stl = self.parent.settlement
        gold = await self.bot.database.users.get_gold(self.user_id)
        if (
            stl.timber < cost.get("timber", 0)
            or stl.stone < cost.get("stone", 0)
            or gold < cost.get("gold", 0)
        ):
            self._processing = False
            return await interaction.response.send_message(
                "Insufficient resources for upgrade!", ephemeral=True
            )

        if "special_key" in cost:
            owned = await self.bot.database.users.get_currency(
                self.user_id, cost["special_key"]
            )
            if owned < cost["special_qty"]:
                self._processing = False
                return await interaction.response.send_message(
                    f"Need {cost['special_qty']}× {cost['special_name']}!", ephemeral=True
                )

        await interaction.response.defer()

        # Consume resources
        changes = {
            "timber": -cost.get("timber", 0),
            "stone":  -cost.get("stone", 0),
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -cost.get("gold", 0))
        if "special_key" in cost:
            await self.bot.database.users.modify_currency(
                self.user_id, cost["special_key"], -cost["special_qty"]
            )

        await self.bot.database.settlement.upgrade_building_tier(b.id)

        # Refresh
        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )
        self.building = next(
            (x for x in self.parent.settlement.buildings if x.id == b.id), self.building
        )
        self._processing = False
        self._build_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _demolish_confirm(self, interaction: Interaction):
        view = _DemolishConfirmView(self.bot, self.user_id, self)
        embed = discord.Embed(
            title="⚠️ Confirm Demolish",
            description=(
                f"Are you sure you want to demolish **{self.building.name}**?\n"
                "This cannot be undone. The plot will remain developed."
            ),
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    # ------------------------------------------------------------------
    # Back
    # ------------------------------------------------------------------

    async def _go_back(self, interaction: Interaction):
        self.parent._rebuild_ui()
        await interaction.response.edit_message(
            content=None,
            embed=self.parent.build_embed(),
            view=self.parent,
        )
        self.stop()


# ---------------------------------------------------------------------------
# Demolish confirmation
# ---------------------------------------------------------------------------


class _DemolishConfirmView(SettlementBaseView):
    def __init__(self, bot, user_id: str, origin: PlotDetailView):
        super().__init__(bot, user_id)
        self.origin = origin

        yes = ui.Button(label="Demolish", style=ButtonStyle.danger, emoji="💥")
        yes.callback = self._do_demolish
        self.add_item(yes)

        no = ui.Button(label="Cancel", style=ButtonStyle.secondary)
        no.callback = self._cancel
        self.add_item(no)

    async def _do_demolish(self, interaction: Interaction):
        b = self.origin.building
        await self.bot.database.settlement.demolish_building(b.id)

        self.origin.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.origin.user_id, self.origin.parent.server_id
        )
        self.origin.building = None
        self.origin._build_buttons()

        embed = self.origin.build_embed()
        embed.title = f"📍 Plot {self.origin.plot.plot_index} — ✅ {b.name} Demolished"
        await interaction.response.edit_message(content=None, embed=embed, view=self.origin)
        self.stop()

    async def _cancel(self, interaction: Interaction):
        await interaction.response.edit_message(
            content=None,
            embed=self.origin.build_embed(),
            view=self.origin,
        )
        self.stop()


# ---------------------------------------------------------------------------
# Meta building construction
# ---------------------------------------------------------------------------


class MetaBuildingConstructionView(SettlementBaseView):
    def __init__(self, bot, user_id: str, plot_index: int, parent_view, return_to_detail):
        super().__init__(bot, user_id)
        self.plot_index = plot_index
        self.parent = parent_view
        self.return_to = return_to_detail
        self._processing = False
        self._build_select()

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚙️ Build Meta Building",
            description=(
                "Meta buildings provide powerful adjacency bonuses to neighbouring plots.\n"
                "They do **not** count toward your regular building slot cap.\n\n"
                "**Available Meta Buildings:**"
            ),
            color=discord.Color.blurple(),
        )
        existing_types = {b.building_type for b in self.parent.settlement.buildings if b.is_meta}
        for key, data in META_BUILDINGS.items():
            cost = data["cost"]
            cost_str = (
                f"💰 {cost.get('gold', 0):,} | "
                f"🪵 {cost.get('timber', 0):,} | "
                f"🪨 {cost.get('stone', 0):,}"
            )
            already = " *(already built)*" if key in existing_types else ""
            embed.add_field(
                name=f"{data['emoji']} {data['label']}{already}",
                value=f"{data['description']}\n*Cost: {cost_str}*",
                inline=False,
            )
        return embed

    def _build_select(self):
        self.clear_items()
        existing_types = {b.building_type for b in self.parent.settlement.buildings if b.is_meta}
        options = []
        for key, data in META_BUILDINGS.items():
            if key in existing_types:
                continue
            cost = data["cost"]
            desc = (
                f"Cost: {cost.get('gold', 0):,}g, "
                f"{cost.get('timber', 0):,} Wood, "
                f"{cost.get('stone', 0):,} Stone"
            )
            options.append(
                SelectOption(
                    label=data["label"],
                    value=key,
                    description=desc[:100],
                    emoji=data["emoji"],
                )
            )

        if options:
            sel = ui.Select(
                placeholder="Select a meta building to construct...",
                options=options,
                row=0,
            )
            sel.callback = self._on_select
            self.add_item(sel)
        else:
            self.add_item(
                ui.Button(
                    label="All meta buildings already constructed",
                    style=ButtonStyle.secondary,
                    disabled=True,
                    row=0,
                )
            )

        cancel = ui.Button(label="Cancel", style=ButtonStyle.danger, row=1)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _on_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        key = interaction.data["values"][0]
        data = META_BUILDINGS[key]
        cost = data["cost"]

        gold = await self.bot.database.users.get_gold(self.user_id)
        stl = self.parent.settlement
        if (
            gold < cost.get("gold", 0)
            or stl.timber < cost.get("timber", 0)
            or stl.stone < cost.get("stone", 0)
        ):
            self._processing = False
            return await interaction.response.send_message(
                "Insufficient resources!", ephemeral=True
            )

        await interaction.response.defer()

        # Short construction animation
        prog = discord.Embed(title="⚙️ Construction in Progress", color=discord.Color.orange())
        prog.description = "Laying the foundations for the new meta building..."
        await interaction.edit_original_response(embed=prog)
        await asyncio.sleep(2)

        # Deduct resources
        changes = {
            "timber": -cost.get("timber", 0),
            "stone":  -cost.get("stone", 0),
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -cost.get("gold", 0))

        # Build
        await self.bot.database.settlement.build_structure(
            self.user_id,
            self.parent.server_id,
            key,
            self.plot_index,
            is_meta=True,
        )

        # Refresh
        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )
        new_building = next(
            (b for b in self.parent.settlement.buildings if b.plot_index == self.plot_index),
            None,
        )
        self.return_to.building = new_building
        self.return_to._build_buttons()

        embed = self.return_to.build_embed()
        embed.title = f"📍 Plot {self.plot_index} — ✅ {data['label']} Constructed!"
        await interaction.edit_original_response(
            content=None, embed=embed, view=self.return_to
        )
        self.stop()

    async def _cancel(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.return_to.build_embed(), view=self.return_to
        )
        self.stop()
