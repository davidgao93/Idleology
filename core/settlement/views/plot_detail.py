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

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.emojis import DEVELOPMENT_CONTRACT, DIVINER_ROD, GOLD_COIN, RESOURCE_EMOJI
from core.images import SETTLEMENT_BUILDINGS, SETTLEMENT_CONSTRUCTION
from core.settlement.constants import (
    BUILDING_INFO,
    RESOURCE_DISPLAY_NAMES,
)
from core.settlement.encounter import get_repair_cost
from core.settlement.mechanics import (
    SettlementMechanics,
    execute_building_upgrade,
    execute_diviners_rod,
)
from core.settlement.models import Building, Plot
from core.settlement.plots import (
    META_BUILDINGS,
    PLOT_BONUS_AFFECTED,
    PLOT_BONUS_TABLE,
    SHRINE_BUILDING_TYPES,
    get_effective_max_workers,
    render_mini_grid,
    roll_plot_bonus,
)
from core.settlement.turn_engine import (
    meta_construction_dt_cost,
    upgrade_dt_cost,
)

from .base import SettlementBaseView

# ---------------------------------------------------------------------------
# Building detail helpers  (output / effect display for PlotDetailView)
# ---------------------------------------------------------------------------

_OUTPUT_DISPLAY: dict[str, tuple[str, str]] = {
    "timber": ("🪵", "Timber"),
    "stone": ("🪨", "Stone"),
    "market_gold": (GOLD_COIN, "Gold"),
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
    return eff, extra_rate


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
        _append_passive_effect(embed, b, plot_bonus_type, adj)
    # "special" (black_market, hatchery) and "core" (town_hall) — no output field


def _append_generator(embed, b, b_data: dict, plot_bonus_type, adj: dict) -> None:
    workers = b.workers_assigned
    base_rate: float = b_data["base_rate"]
    output_key: str = b_data["output"]

    eff, _ = _gen_effectiveness(b.building_type, plot_bonus_type, adj)
    if b.building_type == "war_camp":
        rate = base_rate * workers * eff
    else:
        rate = base_rate * b.tier * workers * eff

    emoji, label = _OUTPUT_DISPLAY.get(
        output_key, ("📦", output_key.replace("_", " ").title())
    )

    if workers == 0:
        value = _NO_WORKERS
    elif output_key == "war_camp_stamina":
        flat_bonus = adj.get("flat_stamina_per_hr", 0.0)
        total_rate = rate + flat_bonus
        value = f"{emoji} **{label}:** ~{total_rate:.2f}/hr"
        if flat_bonus > 0:
            value += f"\n_+{flat_bonus:.1f}/hr from Encampment_"
    elif output_key == "companion_cookie":
        value = f"{emoji} **{label}:** ~{int(rate):,}/hr"
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
        raw_name = RESOURCE_DISPLAY_NAMES.get(
            raw_key, raw_key.replace("_", " ").title()
        )
        ref_name = RESOURCE_DISPLAY_NAMES.get(
            refined_key, refined_key.replace("_", " ").title()
        )
        lines.append(f"• {raw_name} → {ref_name}: ~**{adjusted:,}**/hr")

    if eff > 1.0:
        lines.append(f"_×{eff:.2f} effectiveness from bonuses_")

    embed.add_field(
        name=f"📊 Conversions (T{b.tier} — {len(rates)} active slot{'s' if len(rates) != 1 else ''})",
        value="\n".join(lines),
        inline=False,
    )


def _append_passive_effect(
    embed, b, plot_bonus_type: str | None = None, adj: dict | None = None
) -> None:
    workers = b.workers_assigned
    btype = b.building_type
    adj = adj or {}

    if workers == 0:
        embed.add_field(
            name="⚡ Current Effect",
            value="_No workers assigned — passive is inactive._",
            inline=False,
        )
        return

    if btype == "barracks":
        pct = workers / 100
        # Natural cap: T5 (500 workers) = 5%; Watchtower can add ~0.25% more
        value = f"+**{pct:.1f}%** ATK & DEF (cap ≈ {b.tier}% at T{b.tier})"

    elif btype == "temple":
        pct = workers * 5 / 100
        value = f"+**{pct:.1f}%** Propagate follower gain (cap ≈ {b.tier * 5}% at T{b.tier})"

    elif btype == "apothecary":
        # Actual formula in player_turn.py:
        #   flat_bonus = int(workers * 0.2 * (1 + apothecary_boost_pct))
        # apothecary_boost comes from the adj dict (Apothecary Annex adjacency).
        boost_pct = adj.get("apothecary_boost", 0.0)
        flat = int(workers * 0.2 * (1.0 + boost_pct))
        cap_flat = int(b.tier * 100 * 0.2)
        if boost_pct > 0:
            value = (
                f"+**{flat:,} flat HP** per potion use "
                f"_(×{1.0 + boost_pct:.2f} from Apothecary Annex)_\n"
                f"_(base cap ≈ +{cap_flat:,} HP at T{b.tier})_"
            )
        else:
            value = (
                f"+**{flat:,} flat HP** per potion use "
                f"(cap ≈ +{cap_flat:,} HP at T{b.tier})"
            )

    elif btype in SHRINE_BUILDING_TYPES and btype != "temple":
        # Drop formula: 50% base + workers * 0.0001 * shrine_eff chance for second sigil.
        # shrine_eff incorporates sacred_ground (+20%) and Shrine Garden adjacency (+15%).
        shrine_eff = 1.0
        bonus_sources: list[str] = []
        if plot_bonus_type == "sacred_ground":
            shrine_eff += 0.20
            bonus_sources.append("Sacred Ground +20%")
        shrine_boost = adj.get("shrine_boost", 0.0)
        if shrine_boost > 0:
            shrine_eff += shrine_boost
            bonus_sources.append(f"Shrine Garden +{shrine_boost:.0%}")
        bonus_chance = workers * 0.05 * shrine_eff  # expressed as %
        cap_chance = b.tier * 100 * 0.05 * shrine_eff
        value = (
            f"**50%** base sigil drop + **{bonus_chance:.2f}%** bonus second drop "
            f"(cap ≈ {cap_chance:.2f}% at T{b.tier})"
        )
        if bonus_sources:
            value += f"\n_Effectiveness ×{shrine_eff:.2f}: {', '.join(bonus_sources)}_"

    else:
        value = "Passive effect active."

    embed.add_field(name="⚡ Current Effect", value=value, inline=False)


def _append_meta_effect(embed, b) -> None:
    meta_data = META_BUILDINGS.get(b.building_type, {})
    btype = b.building_type

    if btype == "watchtower":
        embed.add_field(
            name="⚙️ Global Effect",
            value=(
                "Each regular building's worker cap is increased by **+1% per its own tier** "
                "(T1 → +1 worker per 100, T5 → +5). Settlement-wide, passive."
            ),
            inline=False,
        )
        return

    if btype == "servants_quarters":
        value = "+**20%** output to adjacent generator buildings"
    elif btype == "supply_depot":
        value = "+**15%** conversion rate to adjacent converter buildings"
    elif btype == "grand_cathedral":
        value = "Adjacent shrine buildings get **×2** worker cap"
    elif btype == "foremans_post":
        value = "+**25%** output to all adjacent buildings"
    elif btype == "shrine_garden":
        value = "+**15%** effectiveness to adjacent shrine buildings"
    elif btype == "encampment":
        value = "+**0.5 stamina/hr** to adjacent War Camps"
    elif btype == "apothecary_annex":
        value = "Adjacent Apothecary: +**40% flat** HP healed per potion"
    else:
        value = meta_data.get("description", "Meta building effect active.")

    embed.add_field(name="⚙️ Adjacency Effect", value=value, inline=False)


# ---------------------------------------------------------------------------
# Worker management modal (plot-aware)
# ---------------------------------------------------------------------------

# Plots unlocked for free at settlement creation (adjacent to Town Hall).
# New layout inner ring: P01=(2,1) left, P03=(1,2) above, P05=(2,3) right, P07=(3,2) below.
# They count toward total_developed for pricing, but paid_developed is tracked
# separately so the DC cost curve still totals 210 across all 16 purchasable plots.
_FREE_PLOT_INDICES: frozenset[int] = frozenset({1, 3, 5, 7})
# DCs the free plots would have cost in the original curve (1+2+3+4 = 10).
# Redistributed as +1 on each of the first 10 paid unlocks.
_FREE_PLOTS_RECOVERED: int = sum(range(1, len(_FREE_PLOT_INDICES) + 1))  # 10


def _compute_dc_cost(plots: list, projects: list | None = None) -> int:
    """
    DC cost to develop the next undeveloped plot.

    Base: total_developed + 1  (free TH-adjacent plots count, raising the floor).
    Recovery: +1 on each of the first _FREE_PLOTS_RECOVERED paid unlocks so the
    full 16-plot curve totals 210 DCs, identical to the original 20-plot curve.
    Pending excavation projects count as already committed toward the cost curve.
    """
    total_developed = sum(1 for p in plots if p.is_developed)
    paid_developed = sum(
        1 for p in plots if p.is_developed and p.plot_index not in _FREE_PLOT_INDICES
    )
    # Count in-progress excavations so queuing multiple excavations ratchets cost up
    if projects:
        for proj in projects:
            if proj.get("project_type") == "plot_develop":
                pi = (proj.get("data") or {}).get("plot_index")
                if pi is not None:
                    total_developed += 1
                    if pi not in _FREE_PLOT_INDICES:
                        paid_developed += 1
    extra = 1 if paid_developed < _FREE_PLOTS_RECOVERED else 0
    return total_developed + 1 + extra


class PlotWorkerModal(ui.Modal, title="Manage Workforce"):
    def __init__(self, parent_view: "PlotDetailView"):
        super().__init__()
        self.parent_view = parent_view

        pv = parent_view
        b = pv.building
        adj = pv.adj_bonus or {}
        max_w = get_effective_max_workers(
            building_type=b.building_type,
            tier=b.tier,
            plot_bonus_type=pv.plot.bonus_type if pv.plot else None,
            adj_shrine_cap_x2=adj.get("shrine_cap_x2", False),
            has_watchtower=adj.get("has_watchtower", False),
        )
        total_assigned = sum(
            bld.workers_assigned for bld in pv.parent.settlement.buildings
        )
        free = pv.parent.follower_count - (total_assigned - b.workers_assigned)

        self.count = ui.TextInput(
            label=f"Workers (0–{max_w:,} cap, {free:,} available)",
            placeholder=f"Currently {b.workers_assigned:,} assigned — enter new amount",
            min_length=1,
            max_length=6,
        )
        self.add_item(self.count)

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
                    f"This building can only hold **{max_w:,}** workers.",
                    ephemeral=True,
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

            await interaction.response.edit_message(embed=pv.build_embed(), view=pv)
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
        pending_construction: str | None = None,
        event_effects: dict | None = None,
    ):
        super().__init__(bot, user_id)
        self.plot = plot
        self.building = building
        self.parent = parent  # SettlementDashboardView
        # server_id is a static guild ID — store it directly so BaseView's
        # assignment in __init__ is overridden cleanly (no property needed).
        self.server_id = parent.server_id
        self.adj_bonus = adj_bonus or {}
        self.event_effects: dict = event_effects or {}
        self.pending_construction: str | None = pending_construction
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
        if p.is_developed and p.bonus_type:
            _affected = PLOT_BONUS_AFFECTED.get(p.bonus_type, "")
            bonus_label = (
                f"{bonus_data.get('emoji', '')} **{bonus_data['label']}**\n"
                f"{bonus_data['description']}"
                + (
                    f"\n-# Affects: {_affected}"
                    if _affected and _affected != "None"
                    else ""
                )
            )
        else:
            bonus_label = ""

        if not p.is_developed and self.pending_construction == "__excavating__":
            embed = discord.Embed(
                title=f"📍 Plot {p.plot_index} — ⛏️ Excavation in Progress",
                color=discord.Color.orange(),
            )
            embed.set_thumbnail(url=SETTLEMENT_CONSTRUCTION)
            embed.description = (
                "This plot is being excavated.\n\n"
                "Click **Next Turn** on the dashboard to advance the project.\n"
                "Once complete, a terrain bonus will be revealed and you can build here."
            )
        elif not p.is_developed:
            embed = discord.Embed(
                title=f"📍 Plot {p.plot_index} — Undeveloped",
                color=discord.Color.dark_grey(),
            )
            embed.description = (
                "This plot has not been developed yet.\n\n"
                "Develop it to unlock a permanent terrain bonus and build here."
            )
        elif self.building is None and self.pending_construction:
            b_name = self.pending_construction.replace("_", " ").title()
            embed = discord.Embed(
                title=f"📍 Plot {p.plot_index} — 🏗️ Under Construction",
                color=discord.Color.orange(),
            )
            embed.set_thumbnail(url=SETTLEMENT_CONSTRUCTION)
            embed.description = (
                (f"**Terrain Bonus:** {bonus_label}\n\n" if bonus_label else "")
                + f"**{b_name}** is queued for construction here.\n\n"
                "Click **Next Turn** on the dashboard to advance the project."
            )
        elif self.building is None:
            embed = discord.Embed(
                title=f"📍 Plot {p.plot_index} — Empty",
                color=discord.Color.green(),
            )
            embed.description = (
                f"**Terrain Bonus:** {bonus_label}\n\n" if bonus_label else ""
            ) + "This plot is ready for construction."
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
            embed = discord.Embed(
                title=f"📍 Plot {p.plot_index} — {b.name}",
                color=discord.Color.red() if b.is_disabled else discord.Color.gold(),
            )
            is_passive_meta = (
                b.is_meta
                and META_BUILDINGS.get(b.building_type, {}).get("max_workers", 1) == 0
            )
            if b.building_type == "uber_shrine":
                desc = f"**Tier:** {b.tier}/5\n🏛️ Workers are managed per statue — open Monument Hall to assign them."
            elif b.building_type == "black_market":
                desc = f"**Tier:** {b.tier}/5\n💱 Special trading post — no workers required."
            elif b.is_meta:
                if is_passive_meta:
                    desc = "**Meta Building** *(Passive — no workers needed)*"
                else:
                    desc = f"**Meta Building**\n**Workers:** {b.workers_assigned:,}/{max_w:,}"
            else:
                desc = f"**Tier:** {b.tier}/5\n**Workers:** {b.workers_assigned:,}/{max_w:,}"
            if b.is_disabled:
                repair_cost = get_repair_cost(b.tier)
                desc += f"\n\n🚧 **DISABLED** — damaged by a crisis event.\nRepair cost: **{repair_cost:,} gold**"
            if bonus_label:
                desc += f"\n\n**Terrain Bonus:** {bonus_label}"
            _b_cat = b_data.get("type", "")
            if _b_cat == "generator" and adj.get("production_mult"):
                desc += f"\n🔗 **Adjacency Bonus:** +{adj['production_mult']:.0%} effectiveness"
            elif _b_cat == "converter" and adj.get("converter_mult"):
                desc += f"\n🔗 **Adjacency Bonus:** +{adj['converter_mult']:.0%} effectiveness"
            if adj.get("shrine_boost"):
                desc += (
                    f"\n🌺 **Shrine Garden:** +{adj['shrine_boost']:.0%} effectiveness"
                )
            embed.description = desc

            # Description + quantitative output / effect
            _append_building_detail_fields(embed, b, p.bonus_type, self.adj_bonus)

            # Building thumbnail
            thumb = SETTLEMENT_BUILDINGS.get(b.building_type)
            if thumb:
                embed.set_thumbnail(url=thumb)

            # Upgrade cost preview (meta buildings are T1-only, no upgrades)
            if b.tier < 5 and not b.is_meta:
                target_t = b.tier + 1
                _projects = getattr(self.parent, "projects", []) or []
                _upgrade_proj = next(
                    (
                        p
                        for p in _projects
                        if p["project_type"] == "upgrade" and p["target_id"] == b.id
                    ),
                    None,
                )
                if _upgrade_proj:
                    invested = _upgrade_proj["invested_turns"]
                    required = _upgrade_proj["required_turns"]
                    embed.add_field(
                        name="🔨 Under Construction",
                        value=f"Upgrading to Tier {target_t} — **{invested}/{required} DT(s)** complete",
                        inline=False,
                    )
                else:
                    cost = SettlementMechanics.get_upgrade_cost(b.building_type, b.tier)
                    dt_display = upgrade_dt_cost(
                        b.building_type, target_t, self.event_effects
                    )
                    cost_str = (
                        f"🪵 {cost.get('timber', 0):,} | "
                        f"🪨 {cost.get('stone', 0):,} | "
                        f"{GOLD_COIN} {cost.get('gold', 0):,} | "
                        f"⏱️ {dt_display} DTs"
                    )
                    if self.event_effects.get("construction_dt_halved"):
                        cost_str += " _(Inspiration Surge — halved!)_"
                    if "specials" in cost:
                        for s in cost["specials"]:
                            s_emoji = RESOURCE_EMOJI.get(s["key"], "✨")
                            cost_str += f" | {s_emoji} {s['name']} ×{s['qty']}"
                    elif "special_name" in cost:
                        sp_emoji = RESOURCE_EMOJI.get(cost.get("special_key"), "✨")
                        cost_str += (
                            f" | {sp_emoji} {cost['special_name']} ×{cost['special_qty']}"
                        )
                    embed.add_field(
                        name="Next Upgrade Cost", value=cost_str, inline=False
                    )

        embed.add_field(
            name="Surrounding Plots",
            value=render_mini_grid(
                p.plot_index,
                self.parent.plots,
                self.parent.settlement.buildings,
                self.parent.projects,
            ),
            inline=False,
        )

        embed.set_footer(text=f"Settlement Plot {p.plot_index}/20")
        return embed

    # ------------------------------------------------------------------
    # Button layout
    # ------------------------------------------------------------------

    def _build_buttons(self):
        self.clear_items()
        p = self.plot

        if not p.is_developed and self.pending_construction == "__excavating__":
            btn = ui.Button(
                label="⛏️ Excavation in Progress",
                style=ButtonStyle.secondary,
                disabled=True,
                row=0,
            )
            self.add_item(btn)
        elif not p.is_developed:
            self._add_develop_button()
        elif self.building is None and self.pending_construction:
            # Show an inert indicator — no build actions while construction is queued
            lbl = self.pending_construction.replace("_", " ").title()
            btn = ui.Button(
                label=f"🏗️ {lbl} — construction queued",
                style=ButtonStyle.secondary,
                disabled=True,
                row=0,
            )
            self.add_item(btn)
        elif self.building is None:
            self._add_build_buttons()
        else:
            self._add_manage_buttons()

        if p.is_developed:
            self._add_diviners_rod_button()

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1)
        back.callback = self._go_back
        self.add_item(back)

    def _add_develop_button(self):
        dc_cost = _compute_dc_cost(self.parent.plots, self.parent.projects)
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

        # Pre-compute whether this building already has an upgrade queued.
        _projects = getattr(self.parent, "projects", []) or []
        _has_upgrade = any(
            p["project_type"] == "upgrade" and p["target_id"] == b.id for p in _projects
        )

        # --- Special case: Black Market opens its own dedicated view ---
        if b.building_type == "black_market":
            if b.is_disabled:
                repair_cost = get_repair_cost(b.tier)
                btn_repair = ui.Button(
                    label=f"Repair ({repair_cost:,}g)",
                    style=ButtonStyle.danger,
                    emoji="🔧",
                    row=0,
                )
                btn_repair.callback = self._repair_building
                self.add_item(btn_repair)
            else:
                btn_bm = ui.Button(
                    label="Open Black Market",
                    style=ButtonStyle.blurple,
                    emoji="⚫",
                    row=0,
                )
                btn_bm.callback = self._open_black_market
                self.add_item(btn_bm)

            if b.tier < 5:
                btn_up = ui.Button(
                    label=f"Upgrade to T{b.tier + 1}",
                    style=ButtonStyle.success,
                    emoji="⬆️",
                    row=0,
                    disabled=_has_upgrade,
                )
                btn_up.callback = self._upgrade_building
                self.add_item(btn_up)

            btn_demo = ui.Button(
                label="Demolish", style=ButtonStyle.danger, emoji="💥", row=1
            )
            btn_demo.callback = self._demolish_confirm
            self.add_item(btn_demo)
            return

        # --- Special case: Uber Shrine opens Monument Hall view ---
        if b.building_type == "uber_shrine":
            if b.is_disabled:
                repair_cost = get_repair_cost(b.tier)
                btn_repair = ui.Button(
                    label=f"Repair ({repair_cost:,}g)",
                    style=ButtonStyle.danger,
                    emoji="🔧",
                    row=0,
                )
                btn_repair.callback = self._repair_building
                self.add_item(btn_repair)
            else:
                btn_shrine = ui.Button(
                    label="Open Monument Hall",
                    style=ButtonStyle.blurple,
                    emoji="🏛️",
                    row=0,
                )
                btn_shrine.callback = self._open_uber_shrine
                self.add_item(btn_shrine)

            if b.tier < 5 and not b.is_meta:
                btn_up = ui.Button(
                    label=f"Upgrade to T{b.tier + 1}",
                    style=ButtonStyle.success,
                    emoji="⬆️",
                    row=0,
                    disabled=_has_upgrade,
                )
                btn_up.callback = self._upgrade_building
                self.add_item(btn_up)

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

        # Workers button (all buildings that accept workers) — row 0
        needs_workers = (
            not b.is_meta
            or META_BUILDINGS.get(b.building_type, {}).get("max_workers", 0) > 0
        )
        if needs_workers:
            btn_workers = ui.Button(
                label="Manage",
                style=ButtonStyle.primary,
                emoji="👥",
                row=0,
            )
            btn_workers.callback = self._manage_workers
            self.add_item(btn_workers)

            btn_max = ui.Button(
                label="Max",
                style=ButtonStyle.primary,
                emoji="⬆️",
                row=0,
            )
            btn_max.callback = self._max_workers
            self.add_item(btn_max)

        # Upgrade button — row 0 alongside Manage (meta buildings are T1-only, no upgrade)
        if b.tier < 5 and not b.is_meta:
            btn_up = ui.Button(
                label=f"Upgrade to T{b.tier + 1}",
                style=ButtonStyle.success,
                emoji="⬆️",
                row=0,
                disabled=_has_upgrade,
            )
            btn_up.callback = self._upgrade_building
            self.add_item(btn_up)

        if b.is_disabled:
            repair_cost = get_repair_cost(b.tier)
            btn_repair = ui.Button(
                label=f"Repair ({repair_cost:,}g)",
                style=ButtonStyle.success,
                emoji="🔧",
                row=0,
            )
            btn_repair.callback = self._repair_building
            self.add_item(btn_repair)

        # Demolish button — row 1
        btn_demo = ui.Button(
            label="Demolish",
            style=ButtonStyle.danger,
            emoji="💥",
            row=1,
        )
        btn_demo.callback = self._demolish_confirm
        self.add_item(btn_demo)

    # ------------------------------------------------------------------
    # Callbacks — special building launchers
    # ------------------------------------------------------------------

    async def _open_black_market(self, interaction: Interaction):
        from core.settlement.views.black_market import BlackMarketView

        await interaction.response.defer()
        pending_deal = await self.bot.database.settlement.get_pending_deal(
            self.user_id, self.server_id
        )
        zeal_data = await self.bot.database.settlement.get_zeal_data(
            self.user_id, self.server_id
        )
        view = BlackMarketView(
            self.bot,
            self.user_id,
            self,
            self.building,
            has_pending_deal=bool(pending_deal),
        )
        await interaction.edit_original_response(
            embed=view.build_embed(pending_deal=pending_deal, zeal_data=zeal_data),
            view=view,
        )

    async def _open_uber_shrine(self, interaction: Interaction):
        from core.settlement.views.uber_shrine import UberShrineView

        await interaction.response.defer()
        view = UberShrineView(
            self.bot,
            self.user_id,
            self,
            self.building,
            self.plot,
            self.adj_bonus,
        )
        await view._load()
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

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
        await interaction.edit_original_response(embed=hview.build_embed(), view=hview)

    # ------------------------------------------------------------------
    # Callbacks — develop
    # ------------------------------------------------------------------

    async def _develop_plot(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        dc_cost = _compute_dc_cost(self.parent.plots, self.parent.projects)

        dcs = await self.bot.database.settlement.get_development_contracts(
            self.user_id, self.server_id
        )
        if dcs < dc_cost:
            self._processing = False
            return await interaction.response.send_message(
                f"You need **{dc_cost}** {DEVELOPMENT_CONTRACT} Development Contract(s) (you have **{dcs}**).",
                ephemeral=True,
            )

        await interaction.response.defer()

        # Roll bonus type and deduct DCs immediately
        bonus_type = roll_plot_bonus()
        await self.bot.database.settlement.modify_development_contracts(
            self.user_id, self.server_id, -dc_cost
        )

        # DT cost: 5 for first paid plot, +1 for each subsequent (including pending)
        paid_developed = sum(
            1
            for p in self.parent.plots
            if p.is_developed and p.plot_index not in _FREE_PLOT_INDICES
        )
        paid_pending = sum(
            1
            for proj in self.parent.projects
            if proj.get("project_type") == "plot_develop"
            and (proj.get("data") or {}).get("plot_index") not in _FREE_PLOT_INDICES
        )
        dt_cost = 5 + paid_developed + paid_pending

        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.parent.server_id,
            project_type="plot_develop",
            target_id=self.plot.plot_index,
            required_turns=dt_cost,
            data={
                "plot_index": self.plot.plot_index,
                "bonus_type": bonus_type,
                "display_label": f"Plot {self.plot.plot_index} Excavation",
            },
        )

        # Refresh parent projects cache so grid + select menu update immediately
        self.parent.projects = await self.bot.database.settlement.get_projects(
            self.user_id, self.parent.server_id
        )
        self.parent._rebuild_ui()

        queued_embed = discord.Embed(
            title="⛏️ Excavation Queued",
            description=(
                f"**Plot {self.plot.plot_index}** excavation has been queued.\n\n"
                f"{DEVELOPMENT_CONTRACT} Development Contracts deducted. The plot will be ready after "
                f"**{dt_cost} Development Turn(s)**.\n"
                f"Use **Next Turn** on your settlement dashboard to process it."
            ),
            color=discord.Color.orange(),
        )
        queued_embed.set_thumbnail(url=SETTLEMENT_CONSTRUCTION)
        await interaction.edit_original_response(
            content=None, embed=queued_embed, view=discord.ui.View()
        )

        await asyncio.sleep(3)

        self._processing = False
        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()

    # ------------------------------------------------------------------
    # Callbacks — build regular building
    # ------------------------------------------------------------------

    async def _load_event_effects(self) -> dict:
        """Load active ongoing event effects for this settlement."""
        from core.settlement.constants import SETTLEMENT_EVENTS

        active_events = await self.bot.database.settlement.get_active_events(
            self.user_id, self.parent.server_id
        )
        effects: dict = {}
        for ev in active_events:
            if ev["event_type"] == "ongoing":
                ev_def = SETTLEMENT_EVENTS.get(ev["event_key"], {})
                ev_data = ev.get("data") or {}
                for _k, _v in ev_def.get("effects", {}).items():
                    if _v == "band":
                        _v = ev_data.get("band", 0)
                    elif _v == "neg_band":
                        _v = -ev_data.get("band", 0)
                    effects[_k] = _v
        return effects

    async def _open_construction(self, interaction: Interaction):
        from core.settlement.views.construction import BuildConstructionView

        uber_prog, researched, user_data, event_effects = await asyncio.gather(
            self.bot.database.uber.get_uber_progress(
                self.user_id, self.parent.server_id
            ),
            self.bot.database.settlement.get_researched(
                self.user_id, self.parent.server_id
            ),
            self.bot.database.users.get(self.user_id, self.parent.server_id),
            self._load_event_effects(),
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
            player_level=user_data["level"] if user_data else 0,
            event_effects=event_effects,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    # ------------------------------------------------------------------
    # Callbacks — build meta building
    # ------------------------------------------------------------------

    async def _open_meta_construction(self, interaction: Interaction):
        event_effects, researched = await asyncio.gather(
            self._load_event_effects(),
            self.bot.database.settlement.get_researched(
                self.user_id, self.parent.server_id
            ),
        )
        view = MetaBuildingConstructionView(
            bot=self.bot,
            user_id=self.user_id,
            plot_index=self.plot.plot_index,
            parent_view=self.parent,
            return_to_detail=self,
            event_effects=event_effects,
            researched=researched,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    # ------------------------------------------------------------------
    # Callbacks — manage existing building
    # ------------------------------------------------------------------

    async def _manage_workers(self, interaction: Interaction):
        modal = PlotWorkerModal(self)
        await interaction.response.send_modal(modal)

    async def _max_workers(self, interaction: Interaction):
        await interaction.response.defer()
        b = self.building
        p = self.plot
        adj = self.adj_bonus or {}
        building_cap = get_effective_max_workers(
            b.building_type,
            b.tier,
            p.bonus_type if p else None,
            adj.get("shrine_cap_x2", False),
            adj.get("has_watchtower", False),
        )
        # Available = total followers minus workers assigned to every other building
        total_assigned = sum(bld.workers_assigned for bld in self.settlement.buildings)
        available = self.follower_count - (total_assigned - b.workers_assigned)
        assign = max(0, min(building_cap, available))
        await self.bot.database.settlement.assign_workers(b.id, assign)
        b.workers_assigned = assign
        self._build_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _upgrade_building(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        b = self.building

        # Guard: reject if an upgrade project for this building already exists.
        _projects = getattr(self.parent, "projects", []) or []
        if any(
            p["project_type"] == "upgrade" and p["target_id"] == b.id for p in _projects
        ):
            self._processing = False
            return await interaction.response.send_message(
                "This building already has an upgrade queued.", ephemeral=True
            )

        target_tier = b.tier + 1

        # Cost computation (pure)
        if b.is_meta:
            meta_base = META_BUILDINGS.get(b.building_type, {}).get("cost", {})
            cost = {
                "timber": meta_base.get("timber", 0) * target_tier,
                "stone": meta_base.get("stone", 0) * target_tier,
                "gold": meta_base.get("gold", 0) * target_tier,
            }
        else:
            cost = SettlementMechanics.get_upgrade_cost(b.building_type, b.tier)
            plot_bonus = self.plot.bonus_type if self.plot else None
            if plot_bonus == "gold_vein":
                cost["gold"] = int(cost.get("gold", 0) * 0.65)
            if plot_bonus == "ancient_foundation":
                cost["timber"] = int(cost.get("timber", 0) * 0.70)
                cost["stone"] = int(cost.get("stone", 0) * 0.70)

        # Fast resource validation (before defer)
        stl = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )
        self.parent.settlement = stl
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

        if "specials" in cost:
            _mats = await self.bot.database.settlement_materials.get_all(self.user_id)
            for s in cost["specials"]:
                if _mats.get(s["key"], 0) < s["qty"]:
                    self._processing = False
                    return await interaction.response.send_message(
                        f"Need {s['qty']}× {s['name']}!", ephemeral=True
                    )
        elif "special_key" in cost:
            _mats = await self.bot.database.settlement_materials.get_all(self.user_id)
            if _mats.get(cost["special_key"], 0) < cost["special_qty"]:
                self._processing = False
                return await interaction.response.send_message(
                    f"Need {cost['special_qty']}× {cost['special_name']}!",
                    ephemeral=True,
                )

        await interaction.response.defer()

        result = await execute_building_upgrade(
            self.bot, self.user_id, self.parent.server_id, b, cost
        )
        self.parent.projects = result["projects"]
        self.parent.settlement = result["settlement"]
        dt_cost = result["dt_cost"]

        thumb = SETTLEMENT_BUILDINGS.get(b.building_type)
        queued_embed = discord.Embed(
            title="⏳ Upgrade Queued",
            description=(
                f"**{b.name}** upgrade to Tier {target_tier} has been queued.\n\n"
                f"Resources deducted. The upgrade will complete after **{dt_cost} Development Turn(s)**.\n"
                "Use **Next Turn** on your settlement dashboard to process it."
            ),
            color=discord.Color.orange(),
        )
        if thumb:
            queued_embed.set_thumbnail(url=thumb)

        self._processing = False
        await interaction.edit_original_response(embed=queued_embed, view=ui.View())
        self.stop()
        await asyncio.sleep(3)
        dash_embed = self.parent.build_embed()
        await interaction.edit_original_response(embed=dash_embed, view=self.parent)

    async def _repair_building(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        b = self.building
        repair_cost = get_repair_cost(b.tier)
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < repair_cost:
            self._processing = False
            return await interaction.response.send_message(
                f"You need **{repair_cost:,} gold** to repair this building (you have **{gold:,}**).",
                ephemeral=True,
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_gold(self.user_id, -repair_cost)
        await self.bot.database.settlement.repair_building(b.id)

        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )
        self.building = next(
            (x for x in self.parent.settlement.buildings if x.id == b.id), self.building
        )
        self._processing = False
        self._build_buttons()
        embed = self.build_embed()
        embed.title = f"📍 Plot {self.plot.plot_index} — 🔧 {b.name} Repaired!"
        embed.color = discord.Color.green()
        await interaction.edit_original_response(embed=embed, view=self)

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
    # Callbacks — Diviner's Rod
    # ------------------------------------------------------------------

    def _add_diviners_rod_button(self):
        btn = ui.Button(
            label="Use Diviner's Rod",
            style=ButtonStyle.secondary,
            emoji=DIVINER_ROD,
            row=1,
        )
        btn.callback = self._use_diviners_rod
        self.add_item(btn)

    async def _use_diviners_rod(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # Validate rod ownership before deferring so the error is ephemeral
        mats = await self.bot.database.settlement_materials.get_all(self.user_id)
        if mats.get("diviners_rod", 0) < 1:
            self._processing = False
            return await interaction.response.send_message(
                f"You don't have any {DIVINER_ROD} **Diviner's Rods**! They can drop from combat.",
                ephemeral=True,
            )

        await interaction.response.defer()

        result = await execute_diviners_rod(
            self.bot,
            self.user_id,
            self.parent.server_id,
            self.plot.plot_index,
            self.plot.bonus_type,
        )
        self.parent.plots = result["plots"]
        self.plot = next(
            (p for p in self.parent.plots if p.plot_index == self.plot.plot_index),
            self.plot,
        )

        self._processing = False
        self._build_buttons()
        embed = self.build_embed()

        if not result["changed"]:
            embed.title = f"📍 Plot {self.plot.plot_index} — {DIVINER_ROD} Power Fails to Bind"
            embed.color = discord.Color.dark_grey()
            embed.add_field(
                name="The Diviner's Rod fizzles...",
                value=(
                    "The rod's power attempted to reshape the terrain, "
                    "but the land resisted and returned to the same state. "
                    "The rod was consumed with no effect."
                ),
                inline=False,
            )
        else:
            embed.title = f"📍 Plot {self.plot.plot_index} — {DIVINER_ROD} Terrain Rerolled!"
            embed.color = discord.Color.purple()

        await interaction.edit_original_response(content=None, embed=embed, view=self)

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

        self.origin.parent.settlement = (
            await self.bot.database.settlement.get_settlement(
                self.origin.user_id, self.origin.parent.server_id
            )
        )
        self.origin.building = None
        self.origin._build_buttons()

        embed = self.origin.build_embed()
        embed.title = f"📍 Plot {self.origin.plot.plot_index} — ✅ {b.name} Demolished"
        await interaction.response.edit_message(
            content=None, embed=embed, view=self.origin
        )
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


_META_CATEGORIES: dict[str, dict] = {
    "production": {
        "label": "Production",
        "emoji": "⚙️",
        "keys": ["servants_quarters", "supply_depot", "foremans_post"],
    },
    "combat": {
        "label": "Combat",
        "emoji": "⚔️",
        "keys": ["encampment", "apothecary_annex", "grand_cathedral", "shrine_garden"],
    },
    "global": {
        "label": "Global",
        "emoji": "🌐",
        "keys": ["watchtower"],
    },
}


class MetaBuildingConstructionView(SettlementBaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        plot_index: int,
        parent_view,
        return_to_detail,
        event_effects: dict | None = None,
        researched: set | None = None,
    ):
        super().__init__(bot, user_id)
        self.plot_index = plot_index
        self.parent = parent_view
        self.return_to = return_to_detail
        self.event_effects: dict = event_effects or {}
        self.researched: set = researched or set()
        self._processing = False
        self._category = "production"
        self._rebuild()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pending_meta_types(self) -> set[str]:
        return {
            proj["data"].get("building_type", "")
            for proj in self.parent.projects
            if proj.get("project_type") == "construction"
            and proj.get("data", {}).get("building_type") in META_BUILDINGS
        }

    def _sorted_keys(self, cat: str) -> list[str]:
        """Keys in this category sorted by gold cost ascending."""
        keys = _META_CATEGORIES[cat]["keys"]
        return sorted(
            keys, key=lambda k: META_BUILDINGS.get(k, {}).get("cost", {}).get("gold", 0)
        )

    # ------------------------------------------------------------------
    # UI rebuild
    # ------------------------------------------------------------------

    def _make_category_callback(self, cat_key: str):
        async def _cb(interaction: Interaction):
            await self._switch_category(interaction, cat_key)

        return _cb

    def _rebuild(self):
        from core.settlement.views.research import RESEARCHABLE_BUILDINGS

        self.clear_items()

        # Row 0: category toggle buttons
        for cat_key, cat_data in _META_CATEGORIES.items():
            active = self._category == cat_key
            btn = ui.Button(
                label=f"{cat_data['emoji']} {cat_data['label']}",
                style=ButtonStyle.blurple if active else ButtonStyle.secondary,
                disabled=active,
                row=0,
            )
            btn.callback = self._make_category_callback(cat_key)
            self.add_item(btn)

        # Row 1: building select for current category
        existing_types = {
            b.building_type for b in self.parent.settlement.buildings if b.is_meta
        }
        pending_types = self._pending_meta_types()
        keys = self._sorted_keys(self._category)
        options = []
        for key in keys:
            if key in existing_types or key in pending_types:
                continue
            # Gate meta buildings that require research
            if key in RESEARCHABLE_BUILDINGS and key not in self.researched:
                continue
            data = META_BUILDINGS[key]
            cost = data["cost"]
            dt = meta_construction_dt_cost(key, self.event_effects)
            desc = (
                f"💰{cost.get('gold', 0):,}g  🪵{cost.get('timber', 0):,}  "
                f"🪨{cost.get('stone', 0):,}  ⏱️{dt} DTs"
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
                placeholder=f"Select {_META_CATEGORIES[self._category]['label']} meta building...",
                options=options,
                row=1,
            )
            sel.callback = self._on_select
            self.add_item(sel)
        else:
            self.add_item(
                ui.Button(
                    label="All buildings in this category already built/queued",
                    style=ButtonStyle.secondary,
                    disabled=True,
                    row=1,
                )
            )

        cancel = ui.Button(label="Cancel", style=ButtonStyle.danger, row=2)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _switch_category(self, interaction: Interaction, cat_key: str):
        self._category = cat_key
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        from core.settlement.views.research import (
            RESEARCHABLE_BUILDINGS,
            RESEARCH_PREREQUISITES,
        )

        cat_data = _META_CATEGORIES[self._category]
        embed = discord.Embed(
            title=f"⚙️ Build Meta Building — {cat_data['emoji']} {cat_data['label']}",
            description=(
                "Meta buildings provide powerful adjacency or global bonuses.\n"
                "Construction costs Development Turns based on building value.\n\n"
                f"**{cat_data['emoji']} {cat_data['label']} Buildings:**"
            ),
            color=discord.Color.blurple(),
        )
        existing_types = {
            b.building_type for b in self.parent.settlement.buildings if b.is_meta
        }
        pending_types = self._pending_meta_types()
        keys = self._sorted_keys(self._category)
        for key in keys:
            data = META_BUILDINGS[key]
            cost = data["cost"]
            dt = meta_construction_dt_cost(key, self.event_effects)
            cost_str = (
                f"{GOLD_COIN} {cost.get('gold', 0):,} | "
                f"🪵 {cost.get('timber', 0):,} | "
                f"🪨 {cost.get('stone', 0):,} | "
                f"⏱️ {dt} DTs"
            )
            affects = data.get("affects", "")
            needs_research = (
                key in RESEARCHABLE_BUILDINGS and key not in self.researched
            )
            if key in existing_types:
                suffix = " *(already built)*"
            elif key in pending_types:
                suffix = " *(under construction)*"
            elif needs_research:
                prereq = RESEARCH_PREREQUISITES.get(key)
                if prereq and prereq not in self.researched:
                    prereq_name = RESEARCHABLE_BUILDINGS.get(
                        prereq, prereq.replace("_", " ").title()
                    )
                    suffix = f" *(🔒 Research **{prereq_name}** first)*"
                else:
                    own_name = RESEARCHABLE_BUILDINGS.get(
                        key, key.replace("_", " ").title()
                    )
                    suffix = f" *(🔒 Research **{own_name}** first)*"
            else:
                suffix = ""
            value = data["description"]
            if affects:
                value += f"\n-# Affects: {affects}"
            if not needs_research:
                value += f"\n*Cost: {cost_str}*"
            embed.add_field(
                name=f"{data['emoji']} {data['label']}{suffix}",
                value=value,
                inline=False,
            )
        return embed

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        key = interaction.data["values"][0]
        data = META_BUILDINGS[key]
        cost = data["cost"]
        dt_cost = meta_construction_dt_cost(key, self.event_effects)

        gold = await self.bot.database.users.get_gold(self.user_id)
        stl = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )
        self.parent.settlement = stl
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

        # Deduct resources
        changes = {
            "timber": -cost.get("timber", 0),
            "stone": -cost.get("stone", 0),
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -cost.get("gold", 0))

        # Queue construction project
        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.parent.server_id,
            project_type="construction",
            target_id=self.plot_index,
            required_turns=dt_cost,
            data={
                "building_type": key,
                "plot_index": self.plot_index,
                "is_meta": True,
            },
        )

        self.parent.projects = await self.bot.database.settlement.get_projects(
            self.user_id, self.parent.server_id
        )
        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )

        queued_embed = discord.Embed(
            title=f"📍 Plot {self.plot_index} — 🏗️ {data['label']} Queued",
            description=(
                f"**{data['label']}** construction has been queued.\n\n"
                f"Resources deducted. Construction will complete after **{dt_cost} Development Turn(s)**.\n"
                "Use **Next Turn** on your settlement dashboard to process it."
            ),
            color=discord.Color.orange(),
        )
        queued_embed.set_thumbnail(url=SETTLEMENT_CONSTRUCTION)

        self._processing = False
        await interaction.edit_original_response(
            content=None, embed=queued_embed, view=ui.View()
        )
        self.stop()
        await asyncio.sleep(3)
        self.parent._rebuild_ui()
        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )

    async def _cancel(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.return_to.build_embed(), view=self.return_to
        )
        self.stop()
