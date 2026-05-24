# core/settlement/views/dashboard.py
import asyncio
from datetime import datetime

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.companions.mechanics import CompanionMechanics
from core.images import SETTLEMENT_BUILDINGS
from core.settlement.constants import BUILDING_INFO, RESOURCE_DISPLAY_NAMES
from core.settlement.mechanics import SettlementMechanics
from core.settlement.models import Plot
from core.settlement.plots import get_meta_slots, render_grid
from core.settlement.views.research import ResearchView
from core.settlement.views.town_hall import TownHallView

from .base import SettlementBaseView


class SettlementDashboardView(SettlementBaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        settlement,
        follower_count: int,
        plots: list | None = None,
    ):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.settlement = settlement
        self.follower_count = follower_count
        self.plots: list[Plot] = plots or []
        self._rebuild_ui()

    # Backward-compat alias — old BuildingDetailView / TownHallView /
    # BuildConstructionView all call self.parent.update_grid()
    def update_grid(self):
        self._rebuild_ui()

    # -------------------------------------------------------------------------
    # Embed
    # -------------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        developed_set = {p.plot_index for p in self.plots if p.is_developed}
        building_by_plot: dict[int, str] = {
            b.plot_index: b.building_type
            for b in self.settlement.buildings
            if b.plot_index is not None
        }
        grid = render_grid(developed_set, building_by_plot)

        workers_used = sum(b.workers_assigned for b in self.settlement.buildings)
        meta_cap = get_meta_slots(self.settlement.town_hall_tier)
        meta_used = sum(1 for b in self.settlement.buildings if b.is_meta)

        embed = discord.Embed(
            title="🏘️ Settlement",
            description=grid,
            color=discord.Color.dark_green(),
        )
        embed.add_field(
            name="🏛️ Town Hall",
            value=f"Tier {self.settlement.town_hall_tier}",
            inline=True,
        )
        embed.add_field(
            name="👥 Workforce",
            value=f"{workers_used:,}/{self.follower_count:,}",
            inline=True,
        )
        embed.add_field(
            name="⚙️ Meta Slots",
            value=f"{meta_used}/{meta_cap}",
            inline=True,
        )
        embed.add_field(
            name="🪵 Timber",
            value=f"{self.settlement.timber:,}",
            inline=True,
        )
        embed.add_field(
            name="🪨 Stone",
            value=f"{self.settlement.stone:,}",
            inline=True,
        )
        embed.add_field(
            name="📍 Plots",
            value=f"{len(developed_set)}/20",
            inline=True,
        )
        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["town_hall"])
        return embed

    # -------------------------------------------------------------------------
    # UI layout
    # -------------------------------------------------------------------------

    def _rebuild_ui(self):
        self.clear_items()

        building_by_plot: dict[int, object] = {
            b.plot_index: b
            for b in self.settlement.buildings
            if b.plot_index is not None
        }
        developed_set = {p.plot_index for p in self.plots if p.is_developed}

        # --- Row 0: plot select (all 20 plots) ---
        options: list[SelectOption] = []
        for plot_num in range(1, 21):
            is_dev = plot_num in developed_set
            b = building_by_plot.get(plot_num)

            if not is_dev:
                options.append(
                    SelectOption(
                        label=f"Plot {plot_num:02d} — Undeveloped",
                        value=str(plot_num),
                        description="Develop to unlock a terrain bonus",
                        emoji="🔒",
                    )
                )
            elif b is None:
                options.append(
                    SelectOption(
                        label=f"Plot {plot_num:02d} — Empty",
                        value=str(plot_num),
                        description="Ready for construction",
                        emoji="🟡",
                    )
                )
            else:
                if b.building_type == "black_market":
                    status_emoji = "⚫"
                elif b.workers_assigned > 0:
                    status_emoji = "🟢"
                else:
                    status_emoji = "🔴"
                label_suffix = " (Meta)" if b.is_meta else f" (T{b.tier})"
                options.append(
                    SelectOption(
                        label=f"Plot {plot_num:02d} — {b.name}{label_suffix}",
                        value=str(plot_num),
                        description=f"Workers: {b.workers_assigned:,}",
                        emoji=status_emoji,
                    )
                )

        if options:
            select = ui.Select(
                placeholder="Select a plot to manage...",
                options=options[:25],
                row=0,
            )
            select.callback = self._on_plot_select
            self.add_item(select)

        # --- Row 1: control buttons ---
        th_btn = ui.Button(
            label=f"Town Hall (T{self.settlement.town_hall_tier})",
            style=ButtonStyle.primary,
            emoji="🏛️",
            row=1,
        )
        th_btn.callback = self.open_town_hall
        self.add_item(th_btn)

        collect_btn = ui.Button(
            label="Collect",
            style=ButtonStyle.success,
            emoji="🚜",
            row=1,
        )
        collect_btn.callback = self.collect_resources
        self.add_item(collect_btn)

        research_btn = ui.Button(
            label="Research",
            style=ButtonStyle.blurple,
            emoji="🔬",
            row=1,
        )
        research_btn.callback = self.open_research
        self.add_item(research_btn)

        guide_btn = ui.Button(
            label="Guide",
            style=ButtonStyle.secondary,
            emoji="📖",
            row=1,
        )
        guide_btn.callback = self.show_guide
        self.add_item(guide_btn)

        # --- Row 2: close ---
        close_btn = ui.Button(
            label="Close",
            style=ButtonStyle.danger,
            row=2,
        )
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    # -------------------------------------------------------------------------
    # Select callback
    # -------------------------------------------------------------------------

    async def _on_plot_select(self, interaction: Interaction):
        plot_num = int(interaction.data["values"][0])

        plot = next((p for p in self.plots if p.plot_index == plot_num), None)
        if plot is None:
            return await interaction.response.send_message(
                "Plot data unavailable — try closing and reopening the settlement.",
                ephemeral=True,
            )

        building = next(
            (b for b in self.settlement.buildings if b.plot_index == plot_num),
            None,
        )

        adj_bonuses = SettlementMechanics.calculate_adjacency_bonuses(
            self.plots, self.settlement.buildings
        )
        adj_bonus = adj_bonuses.get(plot_num, {})

        from core.settlement.views.plot_detail import PlotDetailView

        view = PlotDetailView(
            bot=self.bot,
            user_id=self.user_id,
            plot=plot,
            building=building,
            parent=self,
            adj_bonus=adj_bonus,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    # -------------------------------------------------------------------------
    # Button callbacks
    # -------------------------------------------------------------------------

    async def show_guide(self, interaction: Interaction):
        embed = discord.Embed(title="📖 Building Guide", color=discord.Color.blue())
        for btype, info in BUILDING_INFO.items():
            embed.add_field(
                name=btype.replace("_", " ").title(),
                value=info,
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def open_town_hall(self, interaction: Interaction):
        dc_count = await self.bot.database.users.get_development_contracts(self.user_id)
        view = TownHallView(
            self.bot, self.user_id, self.settlement, self, dc_count=dc_count
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_research(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = ResearchView(self.bot, self.user_id, self.server_id, self)
        await view.load()
        msg = await interaction.edit_original_response(
            embed=view.build_embed(), view=view
        )
        view.message = msg

    async def collect_resources(self, interaction: Interaction):
        await interaction.response.defer()

        uid, sid = self.user_id, self.server_id

        # 1. Raw inventory for converter limiting
        mining = await self.bot.database.skills.get_data(uid, sid, "mining")
        wood   = await self.bot.database.skills.get_data(uid, sid, "woodcutting")
        fish   = await self.bot.database.skills.get_data(uid, sid, "fishing")

        raw_inv = {
            "iron":              mining[3], "coal":          mining[4],
            "gold":              mining[5], "platinum":      mining[6],
            "idea":              mining[7],
            "oak_logs":          wood[3],   "willow_logs":   wood[4],
            "mahogany_logs":     wood[5],   "magic_logs":    wood[6],
            "idea_logs":         wood[7],
            "desiccated_bones":  fish[3],   "regular_bones": fish[4],
            "sturdy_bones":      fish[5],   "reinforced_bones": fish[6],
            "titanium_bones":    fish[7],
        }

        # 2. Time elapsed
        now  = datetime.now()
        last = datetime.fromisoformat(self.settlement.last_collection_time)
        hours = (now - last).total_seconds() / 3600

        if hours < 0.1:
            return await interaction.followup.send(
                "Your workers haven't generated anything yet.", ephemeral=True
            )

        # 3. Adjacency bonuses (incorporates Ley Line plot check)
        adj_bonuses = SettlementMechanics.calculate_adjacency_bonuses(
            self.plots, self.settlement.buildings
        )
        plot_by_idx = {p.plot_index: p for p in self.plots}

        # 4. Per-building production
        total_changes: dict[str, float] = {}
        for b in self.settlement.buildings:
            plot = plot_by_idx.get(b.plot_index) if b.plot_index is not None else None
            plot_bonus = plot.bonus_type if plot else None
            adj = adj_bonuses.get(b.plot_index, {}) if b.plot_index is not None else {}

            changes = SettlementMechanics.calculate_production(
                building_type=b.building_type,
                tier=b.tier,
                workers=b.workers_assigned,
                hours_elapsed=hours,
                raw_inventory=raw_inv,
                plot_bonus_type=plot_bonus,
                adj_production_mult=adj.get("production_mult", 0.0),
                adj_converter_mult=adj.get("converter_mult", 0.0),
                adj_war_camp_rate=adj.get("war_camp_rate", 0.0),
            )
            for k, v in changes.items():
                total_changes[k] = total_changes.get(k, 0) + v
                if k in raw_inv:
                    raw_inv[k] = raw_inv[k] + v  # type: ignore[assignment]

        # 5. Expedition Camp — passive DC generation (1 DC per 48 h per such plot)
        expedition_count = sum(
            1
            for p in self.plots
            if p.is_developed and p.bonus_type == "expedition_camp"
        )
        dc_earned = int(hours / 48) * expedition_count

        # --- Split out special resources before committing ---
        display_changes: dict = dict(total_changes)

        # Companion cookies → XP
        cookie_xp = 0
        if "companion_cookie" in total_changes:
            cookie_xp = int(total_changes.pop("companion_cookie"))
            display_changes["Companion XP"] = display_changes.pop("companion_cookie", cookie_xp)

        # War Camp stamina
        war_camp_stamina = 0.0
        if "war_camp_stamina" in total_changes:
            war_camp_stamina = float(total_changes.pop("war_camp_stamina"))
            display_changes.pop("war_camp_stamina", None)

        # Market gold
        market_gold = 0
        if "market_gold" in total_changes:
            market_gold = int(total_changes.pop("market_gold"))
            display_changes["Market Gold"] = display_changes.pop("market_gold", market_gold)

        # 6. Commit to DB
        await self.bot.database.settlement.commit_production(uid, sid, total_changes)
        if market_gold > 0:
            await self.bot.database.users.modify_gold(uid, market_gold)
        if war_camp_stamina > 0:
            await self.bot.database.users.add_stamina_uncapped(uid, war_camp_stamina)
        if dc_earned > 0:
            await self.bot.database.users.modify_development_contracts(uid, dc_earned)
        await self.bot.database.settlement.update_collection_timer(uid, sid)

        # Companion XP distribution
        xp_msg = ""
        if cookie_xp > 0:
            active_rows = await self.bot.database.companions.get_active(self.user_id)
            if active_rows:
                xp_per_pet = cookie_xp // len(active_rows)
                for row in active_rows:
                    comp_id, cur_lvl, cur_exp = row[0], row[5], row[6]
                    cur_exp += xp_per_pet
                    while cur_lvl < 100:
                        req = CompanionMechanics.calculate_next_level_xp(cur_lvl)
                        if cur_exp >= req:
                            cur_exp -= req
                            cur_lvl += 1
                        else:
                            break
                    await self.bot.database.companions.update_stats(
                        comp_id, cur_lvl, cur_exp
                    )
                xp_msg = (
                    f"\n🐾 **Companion Ranch:** Distributed {cookie_xp:,} XP "
                    "among active pets."
                )

        stamina_msg = ""
        if war_camp_stamina > 0:
            stamina_msg = f"\n⚔️ **War Camp:** +{war_camp_stamina:.2f} Combat Stamina."

        dc_msg = ""
        if dc_earned > 0:
            dc_msg = (
                f"\n📜 **Expedition Camp:** +{dc_earned} "
                f"Development Contract{'s' if dc_earned != 1 else ''}."
            )

        # 7. Update local state
        self.settlement.timber += int(display_changes.get("timber", 0))
        self.settlement.stone  += int(display_changes.get("stone", 0))
        self.settlement.last_collection_time = now.isoformat()

        # 8. Rebuild UI and respond
        self._rebuild_ui()
        embed = self.build_embed()
        formatted = (
            self._format_changes(display_changes) + xp_msg + stamina_msg + dc_msg
        )
        embed.add_field(
            name="Last Collection",
            value=(
                f"⏱️ Time since last collection: {hours:.2f}h\n\n"
                f"📦 Yield:\n{formatted}"
            ),
            inline=False,
        )

        has_positive = (
            any(
                isinstance(v, (int, float)) and v > 0
                for v in display_changes.values()
            )
            or war_camp_stamina > 0
            or dc_earned > 0
        )
        content = "✅ **Collection Complete**" if has_positive else None

        await interaction.edit_original_response(content=content, embed=embed, view=self)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            expired_embed = discord.Embed(
                title="Settlement Session Expired",
                description=(
                    "This settlement management session has timed out.\n\n"
                    "Run the command again to reopen the dashboard."
                ),
                color=discord.Color.dark_grey(),
            )
            await self.message.edit(embed=expired_embed, view=None)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _format_changes(self, changes: dict) -> str:
        _EMOJI = {"timber": "🪵 ", "stone": "🪨 ", "Market Gold": "💰 "}
        positive_items: list[str] = []
        for key, value in changes.items():
            if not isinstance(value, (int, float)) or value <= 0:
                continue
            # Use display name; already-readable keys (contain space) stay as-is
            name = RESOURCE_DISPLAY_NAMES.get(
                key,
                key if " " in key else key.replace("_", " ").title(),
            )
            emoji = _EMOJI.get(key, "")
            val_str = (
                f"{int(value):,}"
                if isinstance(value, int) or float(value) == int(value)
                else f"{value:.4g}"
            )
            positive_items.append(f"{emoji}{name}: +{val_str}")

        if not positive_items:
            return "No resources produced (no workers, generators, or raw materials)."
        return "\n".join(positive_items)
