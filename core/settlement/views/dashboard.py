# core/settlement/views/dashboard.py
import asyncio
from datetime import datetime

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.companions.mechanics import CompanionMechanics
from core.images import SETTLEMENT_BUILDINGS, SETTLEMENT_MAID
from core.settlement.constants import (
    BUILDING_INFO,
    RESOURCE_DISPLAY_NAMES,
    SETTLEMENT_EVENTS,
    ZEAL_TO_DT,
)
from core.settlement.mechanics import SettlementMechanics
from core.settlement.models import Plot
from core.settlement.plots import META_BUILDINGS, get_meta_slots, render_grid
from core.settlement.turn_engine import process_next_turn
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
        self._processing = False
        self._rebuild_ui()

    # Backward-compat alias — old BuildingDetailView / TownHallView /
    # BuildConstructionView all call self.parent.update_grid()
    def update_grid(self):
        self._rebuild_ui()

    # -------------------------------------------------------------------------
    # Embed
    # -------------------------------------------------------------------------

    def build_embed(
        self,
        turn_summary: dict | None = None,
        turns_data: dict | None = None,
        zeal_data: dict | None = None,
        active_events: list | None = None,
        projects: list | None = None,
        pending_deal: dict | None = None,
    ) -> discord.Embed:
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

        total_turns = (turns_data or {}).get("total_development_turns", 0)
        zeal = (zeal_data or {}).get("settlement_zeal", 0)
        idlem = (zeal_data or {}).get("idlem", 0)
        dt_available = zeal // ZEAL_TO_DT
        zeal_leftover = zeal % ZEAL_TO_DT

        embed = discord.Embed(
            title=f"🏘️ Settlement — Day {total_turns}",
            description=grid,
            color=discord.Color.dark_green(),
        )

        # Core stats row
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

        # Zeal / DT economy
        embed.add_field(
            name="🔥 Zeal",
            value=f"{zeal:,}  ({dt_available} DT + {zeal_leftover} leftover)",
            inline=True,
        )
        embed.add_field(
            name="⚗️ Idlem",
            value=f"{idlem:,}",
            inline=True,
        )
        embed.add_field(name="​", value="​", inline=True)  # spacer

        # Active projects
        if projects:
            proj_lines = []
            for p in projects[:5]:
                bar = "█" * p["invested_turns"] + "░" * max(0, p["required_turns"] - p["invested_turns"])
                pct = int(p["invested_turns"] / max(1, p["required_turns"]) * 100)
                label = p.get("data", {}).get("building_type", p["project_type"])
                proj_lines.append(f"🔨 {label.replace('_',' ').title()} — {pct}% `{bar[:10]}`")
            if len(projects) > 5:
                proj_lines.append(f"…+{len(projects)-5} more")
            embed.add_field(name="🏗️ Active Projects", value="\n".join(proj_lines), inline=False)

        # Active events
        if active_events:
            ev_lines = []
            for ev in active_events[:4]:
                ev_def = SETTLEMENT_EVENTS.get(ev["event_key"], {})
                name = ev_def.get("name", ev["event_key"])
                if ev["event_type"] == "upcoming":
                    ev_lines.append(f"⚠️ {name} — in **{ev['turns_until']}** turn(s)")
                elif ev["event_type"] == "ongoing":
                    ev_lines.append(f"✨ {name} — **{ev['turns_remaining']}** turn(s) left")
            if ev_lines:
                embed.add_field(name="📅 Active Events", value="\n".join(ev_lines), inline=False)

        # Pending Black Market deal
        if pending_deal:
            embed.add_field(
                name="🌑 Market Deal Processing",
                value=f"Value: {pending_deal['total_value']:,} — {pending_deal['turns_remaining']} turn(s) remaining",
                inline=False,
            )

        # Turn summary (shown after Next Turn)
        if turn_summary:
            lines = []
            if turn_summary.get("projects_completed"):
                for p in turn_summary["projects_completed"]:
                    lines.append(f"✅ {p.get('label', 'Project')} completed!")
            if turn_summary.get("deal_completed"):
                lines.append("🎁 **Black Market deal returned!** Check your inventory.")
                for l in (turn_summary.get("deal_rewards") or {}).get("summary_lines", [])[:6]:
                    lines.append(f"  {l}")
            if turn_summary.get("events_fired"):
                for e in turn_summary["events_fired"]:
                    lines.append(f"🎉 Event: {e}")
            if turn_summary.get("events_expired"):
                for e in turn_summary["events_expired"]:
                    lines.append(f"⏹️ Event ended: {e}")
            if turn_summary.get("workers_from_nursery", 0) > 0:
                lines.append(f"👶 Nursery produced {turn_summary['workers_from_nursery']} worker(s).")
            if turn_summary.get("idlem_from_foundry", 0) > 0:
                lines.append(f"⚗️ Foundry produced {turn_summary['idlem_from_foundry']} Idlem.")
            if turn_summary.get("passive_zeal_added", 0) > 0:
                lines.append(f"🔥 +{turn_summary['passive_zeal_added']} passive Zeal added.")
            if lines:
                embed.add_field(
                    name=f"📜 Turn {total_turns} Summary",
                    value="\n".join(lines[:10]),
                    inline=False,
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
                # Determine whether this building type accepts any workers at all
                if b.is_meta:
                    _max_w = META_BUILDINGS.get(b.building_type, {}).get("max_workers", -1)
                    _needs_workers = _max_w != 0
                else:
                    _needs_workers = True

                if b.building_type == "black_market":
                    status_emoji = "⚫"
                    worker_desc = "Special trading post"
                elif not _needs_workers:
                    status_emoji = "🔵"   # passive/always-on — distinct from active 🟢 / idle 🔴
                    worker_desc = "Passive — always active"
                elif b.workers_assigned > 0:
                    status_emoji = "🟢"
                    worker_desc = f"Workers: {b.workers_assigned:,}"
                else:
                    status_emoji = "🔴"
                    worker_desc = "Workers: 0 — inactive"

                label_suffix = " (Meta)" if b.is_meta else f" (T{b.tier})"
                options.append(
                    SelectOption(
                        label=f"Plot {plot_num:02d} — {b.name}{label_suffix}",
                        value=str(plot_num),
                        description=worker_desc,
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

        # --- Row 1: primary actions ---
        next_turn_btn = ui.Button(
            label="Next Turn ▶",
            style=ButtonStyle.success,
            emoji="⏭️",
            row=1,
        )
        next_turn_btn.callback = self.on_next_turn
        self.add_item(next_turn_btn)

        gather_zeal_btn = ui.Button(
            label="Gather Zeal",
            style=ButtonStyle.blurple,
            emoji="🔥",
            row=1,
        )
        gather_zeal_btn.callback = self.on_gather_zeal
        self.add_item(gather_zeal_btn)

        collect_btn = ui.Button(
            label="Collect",
            style=ButtonStyle.primary,
            emoji="🚜",
            row=1,
        )
        collect_btn.callback = self.collect_resources
        self.add_item(collect_btn)

        # --- Row 2: management buttons ---
        th_btn = ui.Button(
            label=f"Town Hall (T{self.settlement.town_hall_tier})",
            style=ButtonStyle.secondary,
            emoji="🏛️",
            row=2,
        )
        th_btn.callback = self.open_town_hall
        self.add_item(th_btn)

        research_btn = ui.Button(
            label="Research",
            style=ButtonStyle.secondary,
            emoji="🔬",
            row=2,
        )
        research_btn.callback = self.open_research
        self.add_item(research_btn)

        guide_btn = ui.Button(
            label="Guide",
            style=ButtonStyle.secondary,
            emoji="📖",
            row=2,
        )
        guide_btn.callback = self.show_guide
        self.add_item(guide_btn)

        maid_btn = ui.Button(
            label="Ask the Maid",
            style=ButtonStyle.secondary,
            emoji="🎀",
            row=2,
        )
        maid_btn.callback = self.ask_the_maid
        self.add_item(maid_btn)

        # --- Row 3: close ---
        close_btn = ui.Button(
            label="Close",
            style=ButtonStyle.danger,
            row=3,
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
        dc_crafted_today = await self.bot.database.users.get_dc_crafted_today(self.user_id)
        view = TownHallView(
            self.bot, self.user_id, self.settlement, self,
            dc_count=dc_count, dc_crafted_today=dc_crafted_today,
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

        # Artisan Mastery refining bonuses (Synergy branch)
        mastery_row = await self.bot.database.skills.get_mastery(uid, sid)
        refining_bonus = 0.0
        if mastery_row:
            from core.skills.mastery import has_master_quarry, has_seasoned_timber
            if has_master_quarry(mastery_row):
                refining_bonus += 0.10
            if has_seasoned_timber(mastery_row):
                refining_bonus += 0.10

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

        # 4. Active event production bonuses
        _active_evs = await self.bot.database.settlement.get_active_events(uid, sid)
        _event_gen_bonus = 0.0
        for _ev in _active_evs:
            _ev_def = SETTLEMENT_EVENTS.get(_ev.get("event_key", ""), {})
            _event_gen_bonus += _ev_def.get("effects", {}).get("generator_bonus", 0.0)

        # 5. Per-building production
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
                mastery_converter_output_mult=refining_bonus,
                event_generator_bonus=_event_gen_bonus,
            )
            for k, v in changes.items():
                total_changes[k] = total_changes.get(k, 0) + v
                if k in raw_inv:
                    raw_inv[k] = raw_inv[k] + v  # type: ignore[assignment]

        # 6. Expedition Camp — passive DC generation (1 DC per 48 h per such plot)
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
        war_camp_stamina = 0
        if "war_camp_stamina" in total_changes:
            # Cap at 10 and convert to int — war camp never exceeds the normal stamina cap
            war_camp_stamina = min(10, int(float(total_changes.pop("war_camp_stamina"))))
            display_changes.pop("war_camp_stamina", None)

        # Market gold
        market_gold = 0
        if "market_gold" in total_changes:
            market_gold = int(total_changes.pop("market_gold"))
            display_changes["Market Gold"] = display_changes.pop("market_gold", market_gold)

        # 7. Commit to DB
        await self.bot.database.settlement.commit_production(uid, sid, total_changes)
        if market_gold > 0:
            await self.bot.database.users.modify_gold(uid, market_gold)
        if war_camp_stamina > 0:
            await self.bot.database.users.add_stamina_capped(uid, war_camp_stamina)
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
            stamina_msg = f"\n⚔️ **War Camp:** +{war_camp_stamina} Combat Stamina."

        dc_msg = ""
        if dc_earned > 0:
            dc_msg = (
                f"\n📜 **Expedition Camp:** +{dc_earned} "
                f"Development Contract{'s' if dc_earned != 1 else ''}."
            )

        # 8. Update local state
        self.settlement.timber += int(display_changes.get("timber", 0))
        self.settlement.stone  += int(display_changes.get("stone", 0))
        self.settlement.last_collection_time = now.isoformat()

        # 9. Rebuild UI and respond
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

        await interaction.edit_original_response(content=None, embed=embed, view=self)

    # build_embed() with no args still works (all optional) — keep backward compat

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        try:
            await interaction.message.delete()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Next Turn
    # -------------------------------------------------------------------------

    async def on_next_turn(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            uid, sid = self.user_id, self.server_id

            # Check Zeal; convert to DT if enough
            zeal_data = await self.bot.database.settlement.get_zeal_data(uid)
            zeal = zeal_data.get("settlement_zeal", 0)
            from core.settlement.constants import ZEAL_TO_DT
            if zeal < ZEAL_TO_DT:
                await interaction.followup.send(
                    f"You need **{ZEAL_TO_DT} Zeal** to advance a turn. "
                    f"You have **{zeal}** Zeal. Gather more from combat, quests, or passive generation!",
                    ephemeral=True,
                )
                return

            # Spend exactly ZEAL_TO_DT Zeal
            await self.bot.database.settlement.spend_zeal(uid, ZEAL_TO_DT)

            # Process the turn
            summary = await process_next_turn(
                self.bot, uid, sid, self.settlement.town_hall_tier
            )

            # Reload fresh data
            self.settlement = await self.bot.database.settlement.get_settlement(uid, sid)
            self.plots = await self.bot.database.plots.get_plots(uid, sid)
            turns_data = await self.bot.database.settlement.get_turns_data(uid, sid)
            zeal_data = await self.bot.database.settlement.get_zeal_data(uid)
            active_events = await self.bot.database.settlement.get_active_events(uid, sid)
            projects = await self.bot.database.settlement.get_projects(uid, sid)
            pending_deal = await self.bot.database.settlement.get_pending_deal(uid, sid)

            self._rebuild_ui()
            embed = self.build_embed(
                turn_summary=summary,
                turns_data=turns_data,
                zeal_data=zeal_data,
                active_events=active_events,
                projects=projects,
                pending_deal=pending_deal,
            )
            await interaction.edit_original_response(embed=embed, view=self)
        finally:
            self._processing = False

    async def on_gather_zeal(self, interaction: Interaction):
        """Collects accumulated passive Zeal into the player's Zeal balance."""
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            uid, sid = self.user_id, self.server_id
            # Also accrue passive Zeal based on hours since last collection
            turns_data = await self.bot.database.settlement.get_turns_data(uid, sid)
            pending = turns_data.get("pending_zeal", 0)

            # Also add time-based passive generation since last turn
            from core.settlement.turn_engine import passive_zeal_for_period
            if self.settlement.last_collection_time:
                try:
                    last = datetime.fromisoformat(self.settlement.last_collection_time)
                    hours = (datetime.now() - last).total_seconds() / 3600
                    extra = passive_zeal_for_period(hours, self.settlement.town_hall_tier)
                    # Cap at 12h worth so passive doesn't pile up forever
                    extra = min(extra, passive_zeal_for_period(12, self.settlement.town_hall_tier))
                    if extra > 0:
                        await self.bot.database.settlement.add_pending_zeal(uid, sid, extra)
                except Exception:
                    extra = 0

            collected = await self.bot.database.settlement.collect_pending_zeal(uid, sid)

            if collected <= 0:
                await interaction.followup.send(
                    "No passive Zeal has accumulated yet. Come back later!", ephemeral=True
                )
                return

            zeal_data = await self.bot.database.settlement.get_zeal_data(uid)
            turns_data = await self.bot.database.settlement.get_turns_data(uid, sid)
            active_events = await self.bot.database.settlement.get_active_events(uid, sid)
            projects = await self.bot.database.settlement.get_projects(uid, sid)
            pending_deal = await self.bot.database.settlement.get_pending_deal(uid, sid)

            self._rebuild_ui()
            embed = self.build_embed(
                turns_data=turns_data,
                zeal_data=zeal_data,
                active_events=active_events,
                projects=projects,
                pending_deal=pending_deal,
            )
            embed.add_field(
                name="🔥 Zeal Gathered",
                value=f"+{collected:,} Zeal collected from passive generation.",
                inline=False,
            )
            await interaction.edit_original_response(embed=embed, view=self)
        finally:
            self._processing = False

    async def ask_the_maid(self, interaction: Interaction):
        """Shows contextual help from The Maid NPC."""
        embed = discord.Embed(
            title="🎀 The Maid",
            description=(
                "Good day. Allow me to explain what's happening here.\n\n"
                "**Development Turns** are your settlement's progress unit — each costs "
                f"**{ZEAL_TO_DT} Zeal** to advance. Zeal comes from combat, quests, and "
                "passive generation over time.\n\n"
                "**Projects** queue construction, upgrades, and research to complete automatically "
                "over several turns — simply click **Next Turn** to advance them.\n\n"
                "**The Black Market** now accepts bundles of resources in exchange for "
                "curated loot packages processed over Development Turns.\n\n"
                "**The Nursery** and **Idlem Foundry** also produce resources per turn "
                "when their projects are active.\n\n"
                "Passive Zeal trickles in over time — use **Gather Zeal** to collect it. "
                "You may also receive Zeal from events and milestones.\n\n"
                "*Shall I prepare the next turn, or is there something else you need?*"
            ),
            color=discord.Color.from_rgb(255, 220, 180),
        )
        embed.set_thumbnail(url=SETTLEMENT_MAID)
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
