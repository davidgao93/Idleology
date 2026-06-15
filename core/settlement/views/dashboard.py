# core/settlement/views/dashboard.py
from datetime import datetime

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.companions.mechanics import CompanionMechanics
from core.images import (
    CRISIS_MONSTER_IMAGES,
    MAID_AUTHOR,
    MAID_SPRITZ_PORTRAIT,
    SETTLEMENT_BUILDINGS,
)
from core.settlement.constants import (
    RESOURCE_DISPLAY_NAMES,
    SETTLEMENT_EVENTS,
    ZEAL_GATHER_CAP,
    ZEAL_TO_DT,
)
from core.settlement.mechanics import SettlementMechanics
from core.settlement.models import Plot
from core.settlement.plots import META_BUILDINGS, get_meta_slots, render_grid
from core.settlement.turn_engine import process_next_turn
from core.settlement.views.research import ResearchView
from core.settlement.views.town_hall import TownHallView

from .base import SettlementBaseView

# ---------------------------------------------------------------------------
# Settlement tutorial — narrated by Head Maid Spritz
# ---------------------------------------------------------------------------

_SPRITZ_SCENES = [
    {
        "title": "Welcome to Your Settlement",
        "text": (
            "I'm Spritz — the settlement's Head Maid. "
            "I oversee production, manage the ledgers, and chase down the administrators when the generators run dry.\n\n"
            "Your **Settlement** is your ideology's permanent home base. "
            "Found it once and it grows with you forever — buildings, workers, resources, and trade all flow from this hub.\n\n"
            "I've prepared five pages of briefing material. "
            "You'll want to read all of it. *No skipping.*"
        ),
        "color": 0xFFD6E8,
    },
    {
        "title": "Zeal and Development Turns",
        "text": (
            "Settlement progress runs on **Development Turns** — each one costs **10 Zeal** to advance.\n\n"
            "Zeal flows in from multiple sources:\n"
            "- **Combat victories** — each win grants 10 Zeal\n"
            "- **Quest completions** — 30 Zeal for 1★ contracts, 90 Zeal for 3★\n"
            "- **Passive trickle** — your Town Hall generates Zeal over time; use **Gather Zeal** to collect it\n\n"
            "Daily limits apply: gains halve beyond 600 Zeal earned today, and cap at 800.\n\n"
            "Pressing **Next Turn** spends Zeal and simultaneously advances *all* active projects. "
            "The more Turns you invest, the faster your settlement grows."
        ),
        "color": 0xFFB347,
    },
    {
        "title": "Buildings and Workers",
        "text": (
            "Buildings fall into three broad roles:\n\n"
            "🏭 **Generators** (Logging Camp, Quarry) produce Timber and Stone per turn — "
            "output scales with workers assigned.\n\n"
            "⚙️ **Converters** (Foundry, Sawmill, Reliquary) refine raw materials into finished goods "
            "automatically, as long as they're staffed. Each tier unlocks a higher material grade.\n\n"
            "🏪 **Special Buildings** offer services: the Apothecary heals, the Barracks trains fighters, "
            "the Nursery grows new followers, and the Idlem Foundry produces Idlem for the Black Market tree.\n\n"
            "Workers come from your ideology's follower count — assign them via each building's detail view. "
            "More workers means more output, up to the building's cap."
        ),
        "color": 0x4A7C59,
    },
    {
        "title": "The Black Market and Research",
        "text": (
            "The **Black Market** converts raw production into meaningful rewards.\n\n"
            "Submit a resource bundle as an offer. It processes over several Development Turns "
            "and returns curated loot — gear, runes, keys, and more. "
            "As you invest **Idlem** into the Black Market's passive tree, deals become "
            "cheaper, more valuable, and biased toward your preferred loot types.\n\n"
            "**Research** uses 📋 Unidentified Blueprints (dropped from combat) to unlock "
            "advanced buildings — the Idlem Foundry, Nursery, shrine variants, and more. "
            "Check the Research panel to see what each blueprint unlocks and what it costs."
        ),
        "color": 0x4A235A,
    },
    {
        "title": "Rare Materials and Plot Bonuses",
        "text": (
            "A few final details:\n\n"
            "🔥 **Magma Core** · 🌿 **Life Root** · 👻 **Spirit Shard** — rare construction "
            "materials dropped from combat. Certain buildings require them alongside standard resources.\n\n"
            "📋 **Unidentified Blueprints** — dropped from combat; required for research. Do not sell them.\n\n"
            "🔮 **Diviner's Rod** — use one from a plot's detail view to reroll that plot's terrain bonus. "
            "Bonuses like *Gold Vein* reduce construction gold costs and *Ancient Foundation* discounts "
            "timber and stone.\n\n"
            "Note: advanced buildings such as the **Hatchery** require higher player levels "
            "before they can be constructed. Plan your layout accordingly.\n\n"
            "*That concludes your briefing. I'll be here if you need a refresher.*"
        ),
        "color": 0x1A2A4A,
    },
]


class _MaidTutorialView(BaseView):
    """Multi-page settlement tutorial narrated by Head Maid Spritz."""

    def __init__(self, bot, parent):
        super().__init__(bot, parent=parent)
        self.index = 0
        self._rebuild()

    def build_embed(self) -> discord.Embed:
        scene = _SPRITZ_SCENES[self.index]
        embed = discord.Embed(
            title=scene["title"],
            description=scene["text"],
            color=scene["color"],
        )
        embed.set_author(name="Head Maid Spritz", icon_url=MAID_AUTHOR)
        # Thumbnail intentionally not set to MAID_AUTHOR (per request: MAID_AUTHOR is the author image)
        embed.set_footer(text=f"Page {self.index + 1} of {len(_SPRITZ_SCENES)}")
        return embed

    def _rebuild(self):
        self.clear_items()
        last = len(_SPRITZ_SCENES) - 1

        if self.index > 0:
            prev = ui.Button(label="← Back", style=ButtonStyle.secondary, row=0)
            prev.callback = self._on_prev
            self.add_item(prev)

        if self.index < last:
            nxt = ui.Button(label="Next →", style=ButtonStyle.primary, row=0)
            nxt.callback = self._on_next
            self.add_item(nxt)
        else:
            close = ui.Button(label="Close", style=ButtonStyle.secondary, row=0)
            close.callback = self._on_close
            self.add_item(close)

    async def _on_prev(self, interaction: Interaction):
        self.index -= 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_next(self, interaction: Interaction):
        self.index += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_close(self, interaction: Interaction):
        self.stop()
        await interaction.response.edit_message(
            content="*Spritz curtsies and returns to her duties.*",
            embed=None,
            view=None,
        )


class SettlementDashboardView(SettlementBaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        settlement,
        follower_count: int,
        plots: list | None = None,
        player_name: str = "",
    ):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.settlement = settlement
        self.follower_count = follower_count
        self.plots: list[Plot] = plots or []
        self.player_name = player_name
        self.projects: list = []  # cached settlement_projects rows
        self._cached_turns_data: dict = {}
        self._cached_zeal_data: dict = {}
        self._cached_active_events: list = []
        self._cached_pending_deal: dict | None = None
        self._cached_pending_zeal: int = 0
        self._processing = False
        self._rebuild_ui()

    # Backward-compat alias — old BuildingDetailView / TownHallView /
    # BuildConstructionView all call self.parent.update_grid()
    def update_grid(self):
        self._rebuild_ui()

    def _pending_by_plot(self) -> dict[int, str]:
        """Derives {plot_index: building_type} for construction projects,
        and {plot_index: '__excavating__'} for pending plot_develop projects."""
        result: dict[int, str] = {}
        for proj in self.projects:
            ptype = proj.get("project_type")
            d = proj.get("data") or {}
            if ptype == "construction":
                pi = d.get("plot_index")
                bt = d.get("building_type", "")
                if pi:
                    result[pi] = bt
            elif ptype == "plot_develop":
                pi = d.get("plot_index")
                if pi:
                    result[pi] = "__excavating__"
        return result

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
        # Update caches with any freshly-supplied data so child-view returns
        # (which call build_embed with no args) always show the latest values.
        if turns_data is not None:
            self._cached_turns_data = turns_data
            self._cached_pending_zeal = turns_data.get("pending_zeal", 0)
        if zeal_data is not None:
            self._cached_zeal_data = zeal_data
        if active_events is not None:
            self._cached_active_events = active_events
        if pending_deal is not None:
            self._cached_pending_deal = pending_deal

        # Use supplied values, falling back to cached ones
        turns_data = turns_data if turns_data is not None else self._cached_turns_data
        zeal_data = zeal_data if zeal_data is not None else self._cached_zeal_data
        active_events = (
            active_events if active_events is not None else self._cached_active_events
        )
        pending_deal = (
            pending_deal if pending_deal is not None else self._cached_pending_deal
        )

        # Merge caller-supplied projects into self.projects if provided, then
        # rebuild the select dropdown so it reflects the current construction state.
        if projects is not None:
            self.projects = projects
            self._rebuild_ui()
        grid = render_grid(developed_set, building_by_plot, self._pending_by_plot())

        workers_used = sum(b.workers_assigned for b in self.settlement.buildings)
        meta_cap = get_meta_slots(self.settlement.town_hall_tier)
        meta_used = sum(1 for b in self.settlement.buildings if b.is_meta)

        total_turns = (turns_data or {}).get("total_development_turns", 0)
        zeal = (zeal_data or {}).get("settlement_zeal", 0)
        idlem = (zeal_data or {}).get("idlem", 0)
        dt_available = zeal // ZEAL_TO_DT
        zeal_leftover = zeal % ZEAL_TO_DT

        name_str = self.player_name or "Master"
        welcome = (
            f"Welcome back, **{name_str}**. It's Day **{total_turns}**, "
            f"and here's the current status of your Settlement…"
        )
        embed = discord.Embed(
            title="🏘️ Settlement",
            description=f"{welcome}\n{grid}",
            color=discord.Color.dark_green(),
        )
        embed.set_author(name="Head Maid Spritz", icon_url=MAID_SPRITZ_PORTRAIT)

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
            value=f"{zeal:,}",
            inline=True,
        )
        embed.add_field(
            name="⚗️ Idlem",
            value=f"{idlem:,}",
            inline=True,
        )
        embed.add_field(name="​", value="​", inline=True)  # spacer

        # Active projects — always use self.projects (live cache) so returning from
        # child views doesn't blank this section.
        if self.projects:
            proj_lines = []
            for p in self.projects[:5]:
                pct = int(p["invested_turns"] / max(1, p["required_turns"]) * 100)
                filled = int(10 * p["invested_turns"] / max(1, p["required_turns"]))
                bar = "█" * filled + "░" * (10 - filled)
                _pdata = p.get("data", {})
                label = (
                    _pdata.get("display_label")
                    or _pdata.get("building_type")
                    or p["project_type"]
                )
                proj_lines.append(
                    f"🔨 {label.replace('_', ' ').title()} — {pct}% `{bar}`"
                )
            if len(self.projects) > 5:
                proj_lines.append(f"…+{len(self.projects) - 5} more")
            embed.add_field(
                name="🏗️ Active Projects", value="\n".join(proj_lines), inline=False
            )

        # Active events
        if active_events:
            ev_lines = []
            for ev in active_events[:4]:
                ev_def = SETTLEMENT_EVENTS.get(ev["event_key"], {})
                name = ev_def.get("name", ev["event_key"])
                desc = ev_def.get("description", "")
                # Substitute banded values and target building into the description.
                # Use a safe fallback dict so missing keys (e.g. old events from before
                # the rework) render as "?" rather than leaving the raw placeholder.
                ev_data_fmt = ev.get("data") or {}

                class _Fmt(dict):
                    def __missing__(self, key):
                        return "?"

                try:
                    desc = desc.format_map(_Fmt(ev_data_fmt))
                except Exception:
                    pass
                if ev["event_type"] == "upcoming":
                    ev_lines.append(
                        f"⚠️ **{name}** — arriving in **{ev['turns_until']}** turn(s)\n"
                        f"-# {desc}"
                    )
                elif ev["event_type"] == "ongoing":
                    ev_lines.append(
                        f"✨ **{name}** — **{ev['turns_remaining']}** turn(s) remaining\n"
                        f"-# {desc}"
                    )
            if ev_lines:
                embed.add_field(
                    name="📅 Active Events", value="\n".join(ev_lines), inline=False
                )

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
                for l in (turn_summary.get("deal_rewards") or {}).get(
                    "summary_lines", []
                )[:6]:
                    lines.append(f"  {l}")
            if turn_summary.get("events_fired"):
                for e in turn_summary["events_fired"]:
                    lines.append(f"🎉 Event: {e}")
            if turn_summary.get("crisis_result"):
                cr = turn_summary["crisis_result"]
                if cr.get("won"):
                    zeal = cr.get("zeal_earned", 50)
                    lines.append(
                        f"⚔️ **{cr['event_name']} repelled!** Your settlement is safe. +{zeal} Zeal awarded."
                    )
                else:
                    lines.append(
                        f"💀 **{cr['event_name']} — crisis not prevented.** Check your buildings for damage."
                    )
            if turn_summary.get("crisis_events_fired"):
                for e in turn_summary["crisis_events_fired"]:
                    lines.append(
                        f"❌ Crisis expired: **{e}** — the crisis has taken hold. Check your buildings."
                    )
            if turn_summary.get("events_expired"):
                for e in turn_summary["events_expired"]:
                    lines.append(f"⏹️ Event ended: {e}")
            if turn_summary.get("workers_from_nursery", 0) > 0:
                ideology = turn_summary.get("nursery_ideology", "")
                if ideology:
                    lines.append(
                        f"👶 Nursery produced {turn_summary['workers_from_nursery']} worker(s) → added to **{ideology}** Workforce."
                    )
                else:
                    lines.append(
                        f"👶 Nursery produced {turn_summary['workers_from_nursery']} worker(s)."
                    )
            if turn_summary.get("idlem_from_foundry", 0) > 0:
                lines.append(
                    f"⚗️ Foundry produced {turn_summary['idlem_from_foundry']} Idlem."
                )
            dt_res = turn_summary.get("dt_resources") or {}
            if dt_res:
                _ICONS = {
                    "timber": "🪵",
                    "stone": "🪨",
                    "market_gold": "💰",
                    "iron": "⛏️",
                    "coal": "⛏️",
                    "gold": "⛏️",
                    "platinum": "⛏️",
                    "idea": "⛏️",
                    "iron_bar": "🔧",
                    "steel_bar": "🔧",
                    "gold_bar": "🔧",
                    "platinum_bar": "🔧",
                    "idea_bar": "🔧",
                    "oak_logs": "🌲",
                    "willow_logs": "🌲",
                    "mahogany_logs": "🌲",
                    "magic_logs": "🌲",
                    "idea_logs": "🌲",
                    "oak_plank": "🪵",
                    "willow_plank": "🪵",
                    "mahogany_plank": "🪵",
                    "magic_plank": "🪵",
                    "idea_plank": "🪵",
                    "desiccated_essence": "✨",
                    "regular_essence": "✨",
                    "sturdy_essence": "✨",
                    "reinforced_essence": "✨",
                    "titanium_essence": "✨",
                    "war_camp_stamina": "⚔️",
                    "companion_xp": "🐾",
                }
                _LABELS = {
                    "market_gold": "Gold (Market)",
                    "war_camp_stamina": "Stamina (War Camp)",
                    "companion_xp": "Companion XP",
                }
                res_lines = []
                for k, v in dt_res.items():
                    if v <= 0:
                        continue
                    icon = _ICONS.get(k, "📦")
                    label = _LABELS.get(k) or RESOURCE_DISPLAY_NAMES.get(
                        k, k.replace("_", " ").title()
                    )
                    res_lines.append(f"{icon} +{v:,} {label}")
                if res_lines:
                    lines.append("🏭 **Buildings produced:**")
                    lines.extend(res_lines[:10])
            if lines:
                embed.add_field(
                    name=f"📜 Turn {total_turns} Summary",
                    value="\n".join(lines[:15]),
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
        pending_map = self._pending_by_plot()

        # --- Row 0: plot select (all 20 plots) ---
        options: list[SelectOption] = []
        for plot_num in range(1, 21):
            is_dev = plot_num in developed_set
            b = building_by_plot.get(plot_num)
            pending_bt = pending_map.get(plot_num)

            if not is_dev and pending_bt == "__excavating__":
                options.append(
                    SelectOption(
                        label=f"Plot {plot_num:02d} — ⛏️ Excavation in Progress",
                        value=str(plot_num),
                        description="Excavation queued — use Next Turn to complete",
                        emoji="⛏️",
                    )
                )
            elif not is_dev:
                options.append(
                    SelectOption(
                        label=f"Plot {plot_num:02d} — Undeveloped",
                        value=str(plot_num),
                        description="Develop to unlock a terrain bonus",
                        emoji="🔒",
                    )
                )
            elif b is None and pending_bt and pending_bt != "__excavating__":
                options.append(
                    SelectOption(
                        label=f"Plot {plot_num:02d} — 🏗️ Under Construction",
                        value=str(plot_num),
                        description=f"Building: {pending_bt.replace('_', ' ').title()}",
                        emoji="🏗️",
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
                    _max_w = META_BUILDINGS.get(b.building_type, {}).get(
                        "max_workers", -1
                    )
                    _needs_workers = _max_w != 0
                else:
                    _needs_workers = True

                if b.is_disabled:
                    status_emoji = "🚧"
                    worker_desc = "DISABLED — needs repair"
                elif b.building_type == "black_market":
                    status_emoji = "⚫"
                    worker_desc = "Special trading post"
                elif not _needs_workers:
                    status_emoji = (
                        "🔵"  # passive/always-on — distinct from active 🟢 / idle 🔴
                    )
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
            label="Next",
            style=ButtonStyle.success,
            emoji="⏭️",
            row=1,
        )
        next_turn_btn.callback = self.on_next_turn
        self.add_item(next_turn_btn)

        # Crisis confront button — appears when a spawn_combat event is upcoming.
        confront_event = next(
            (
                ev
                for ev in self._cached_active_events
                if SETTLEMENT_EVENTS.get(ev["event_key"], {})
                .get("effects", {})
                .get("spawn_combat")
                and ev["event_type"] == "upcoming"
            ),
            None,
        )
        if confront_event:
            ev_def = SETTLEMENT_EVENTS.get(confront_event["event_key"], {})
            enemy_name = (
                ev_def.get("effects", {})
                .get("spawn_combat", "enemy")
                .replace("_", " ")
                .title()
            )
            confront_btn = ui.Button(
                label=f"⚔️ Confront {enemy_name}",
                style=ButtonStyle.danger,
                row=1,
            )
            confront_btn.callback = lambda i, ev=confront_event: self._on_confront(
                i, ev
            )
            self.add_item(confront_btn)

        _pz = min(self._cached_pending_zeal, ZEAL_GATHER_CAP)
        gather_zeal_btn = ui.Button(
            label=f"Gather Zeal ({_pz}/{ZEAL_GATHER_CAP})"
            if _pz > 0
            else f"Gather Zeal (cap {ZEAL_GATHER_CAP})",
            style=ButtonStyle.blurple,
            emoji="🔥",
            row=1,
        )
        gather_zeal_btn.callback = self.on_gather_zeal
        self.add_item(gather_zeal_btn)

        try:
            _last_col = datetime.fromisoformat(self.settlement.last_collection_time)
            _col_hours = (datetime.now() - _last_col).total_seconds() / 3600
            _col_label = f"Collect ({_col_hours:.1f}h)"
        except Exception:
            _col_label = "Collect"
        collect_btn = ui.Button(
            label=_col_label,
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

        # --- Row 3: help / info buttons ---
        guide_btn = ui.Button(
            label="Building List",
            style=ButtonStyle.secondary,
            emoji="📖",
            row=3,
        )
        guide_btn.callback = self.show_building_list
        self.add_item(guide_btn)

        meta_btn = ui.Button(
            label="Meta Buildings",
            style=ButtonStyle.secondary,
            emoji="⚙️",
            row=3,
        )
        meta_btn.callback = self.show_meta_buildings
        self.add_item(meta_btn)

        maid_btn = ui.Button(
            label="Ask Spritz",
            style=ButtonStyle.secondary,
            emoji="🎀",
            row=3,
        )
        maid_btn.callback = self.ask_the_maid
        self.add_item(maid_btn)

        # --- Row 4: close ---
        close_btn = ui.Button(
            label="Close",
            style=ButtonStyle.secondary,
            row=4,
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

        pending_construction = self._pending_by_plot().get(plot_num)

        view = PlotDetailView(
            bot=self.bot,
            user_id=self.user_id,
            plot=plot,
            building=building,
            parent=self,
            adj_bonus=adj_bonus,
            pending_construction=pending_construction,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    # -------------------------------------------------------------------------
    # Button callbacks
    # -------------------------------------------------------------------------

    async def show_building_list(self, interaction: Interaction):
        _REGULAR = [
            ("🪵 Logging Camp", "Generator · Timber · scales with tier & workers"),
            ("🪨 Quarry", "Generator · Stone · scales with tier & workers"),
            ("🔥 Foundry", "Converter · Ore → Bars · T1 Iron → T5 Idea"),
            ("🌲 Sawmill", "Converter · Logs → Planks · T1 Oak → T5 Idea"),
            (
                "🦴 Reliquary",
                "Converter · Bones → Essences · T1 Desiccated → T5 Titanium",
            ),
            ("💰 Market", "Generator · Gold · scales with tier & workers"),
            ("⚔️ Barracks", "Passive · +% Attack & Defence in combat"),
            ("⛪ Temple", "Passive · +% Propagate follower gain"),
            ("💊 Apothecary", "Passive · +Flat HP restored per potion use"),
            (
                "🌑 Black Market",
                "Special · Submit bundles for loot · invest Idlem to improve",
            ),
            ("🐾 Companion Ranch", "Generator · Companion XP · distributed on collect"),
            ("🥚 Hatchery", "Special · Incubates eggs for Hematurgy drops · Lv50"),
            ("🏕️ War Camp", "Generator · Combat Stamina · capped at 10"),
            ("👶 Nursery", "Project Building · Workers per DT · scales with tier"),
            (
                "⚗️ Idlem Foundry",
                "Project Building · Idlem per DT · powers BM passive tree",
            ),
            ("🔮 Uber Shrine", "Passive · Houses all 5 shrine statues for sigil drops"),
        ]
        regular_lines = "\n".join(f"**{n}** — {d}" for n, d in _REGULAR)
        embed = discord.Embed(
            title="📖 Regular Buildings",
            description=regular_lines,
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Select a building in the dashboard for full details.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def show_meta_buildings(self, interaction: Interaction):
        _META = [
            (
                "🏠 Servant's Quarters",
                "+2% generator output per 10 workers to adjacent generators (cap +20%)",
            ),
            ("📦 Supply Depot", "+15% converter effectiveness to adjacent converters"),
            ("⛪ Grand Cathedral", "Doubles worker cap for adjacent shrine buildings"),
            (
                "🏯 Watchtower",
                "Global +1%×tier worker cap on all regular buildings (no workers needed)",
            ),
            ("🏗️ Foreman's Post", "+25% output to all adjacent buildings"),
            ("🌸 Shrine Garden", "+15% effectiveness to adjacent shrine buildings"),
            ("⛺ Encampment", "+0.5 stamina/hr per 100 workers to adjacent War Camps"),
            (
                "💊 Apothecary Annex",
                "+4% flat heal per 100 workers to adjacent Apothecary",
            ),
        ]
        lines = "\n".join(f"**{n}** — {d}" for n, d in _META)
        embed = discord.Embed(
            title="⚙️ Meta Buildings",
            description=(
                "Meta buildings provide powerful adjacency bonuses to neighbouring plots. "
                "Each requires full staffing to activate (Watchtower is always-on).\n\n"
                + lines
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Build meta buildings from any empty developed plot.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def open_town_hall(self, interaction: Interaction):
        dc_count = await self.bot.database.users.get_development_contracts(self.user_id)
        dc_crafted_today = await self.bot.database.users.get_dc_crafted_today(
            self.user_id
        )
        view = TownHallView(
            self.bot,
            self.user_id,
            self.settlement,
            self,
            dc_count=dc_count,
            dc_crafted_today=dc_crafted_today,
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
        wood = await self.bot.database.skills.get_data(uid, sid, "woodcutting")
        fish = await self.bot.database.skills.get_data(uid, sid, "fishing")

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
            "iron": mining[3],
            "coal": mining[4],
            "gold": mining[5],
            "platinum": mining[6],
            "idea": mining[7],
            "oak_logs": wood[3],
            "willow_logs": wood[4],
            "mahogany_logs": wood[5],
            "magic_logs": wood[6],
            "idea_logs": wood[7],
            "desiccated_bones": fish[3],
            "regular_bones": fish[4],
            "sturdy_bones": fish[5],
            "reinforced_bones": fish[6],
            "titanium_bones": fish[7],
        }

        # 2. Time elapsed
        now = datetime.now()
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
        _event_conv_bonus = 0.0
        _event_market_gold_bonus = 0.0
        for _ev in _active_evs:
            _ev_def = SETTLEMENT_EVENTS.get(_ev.get("event_key", ""), {})
            _ev_data = _ev.get("data", {})
            _effs = _ev_def.get("effects", {})

            def _rb(v):
                if v == "band":
                    return _ev_data.get("band", 0.0)
                if v == "neg_band":
                    return -_ev_data.get("band", 0.0)
                return v if isinstance(v, (int, float)) else 0.0

            if "generator_bonus" in _effs:
                _event_gen_bonus += _rb(_effs["generator_bonus"])
            if "converter_bonus" in _effs:
                _event_conv_bonus += _rb(_effs["converter_bonus"])
            if "market_gold_bonus" in _effs:
                _event_market_gold_bonus += _rb(_effs["market_gold_bonus"])

        # 5. Per-building production
        total_changes: dict[str, float] = {}
        for b in self.settlement.buildings:
            if b.is_disabled:
                continue  # disabled buildings produce nothing until repaired
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
                event_converter_bonus=_event_conv_bonus,
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
            display_changes["Companion XP"] = display_changes.pop(
                "companion_cookie", cookie_xp
            )

        # War Camp stamina
        war_camp_stamina = 0
        if "war_camp_stamina" in total_changes:
            # Cap at 10 and convert to int — war camp never exceeds the normal stamina cap
            war_camp_stamina = min(
                10, int(float(total_changes.pop("war_camp_stamina")))
            )
            display_changes.pop("war_camp_stamina", None)

        # Market gold (apply event bonus/penalty after extraction)
        market_gold = 0
        if "market_gold" in total_changes:
            market_gold = int(total_changes.pop("market_gold"))
            if _event_market_gold_bonus:
                market_gold = max(0, int(market_gold * (1 + _event_market_gold_bonus)))
            display_changes["Market Gold"] = display_changes.pop(
                "market_gold", market_gold
            )

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
        self.settlement.stone += int(display_changes.get("stone", 0))
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
                f"⏱️ Time since last collection: {hours:.2f}h\n\n📦 Yield:\n{formatted}"
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
            self.settlement = await self.bot.database.settlement.get_settlement(
                uid, sid
            )
            _user_row = await self.bot.database.users.get(uid, sid)
            if _user_row and _user_row["ideology"]:
                self.follower_count = await self.bot.database.social.get_follower_count(
                    _user_row["ideology"]
                )
            _plot_rows = await self.bot.database.plots.get_plots(uid, sid)
            self.plots = [
                Plot(plot_index=r[0], is_developed=bool(r[1]), bonus_type=r[2])
                for r in _plot_rows
            ]
            turns_data = await self.bot.database.settlement.get_turns_data(uid, sid)
            zeal_data = await self.bot.database.settlement.get_zeal_data(uid)
            active_events = await self.bot.database.settlement.get_active_events(
                uid, sid
            )
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

            # Add time-based passive generation since last Zeal gather (tracked
            # separately from resource collection so the two timers don't interfere).
            from core.settlement.turn_engine import passive_zeal_for_period

            gather_ts = (
                self.settlement.last_zeal_gather_time
                or self.settlement.last_collection_time
            )
            if gather_ts:
                try:
                    last = datetime.fromisoformat(gather_ts)
                    hours = (datetime.now() - last).total_seconds() / 3600
                    extra = passive_zeal_for_period(
                        hours, self.settlement.town_hall_tier
                    )
                    if extra > 0:
                        await self.bot.database.settlement.add_pending_zeal(
                            uid, sid, extra
                        )
                except Exception:
                    extra = 0

            # Collect up to ZEAL_GATHER_CAP from pending; passive Zeal doesn't count against
            # the daily earned cap, so we use the capped variant directly.
            collected = await self.bot.database.settlement.collect_capped_pending_zeal(
                uid, sid, ZEAL_GATHER_CAP
            )

            # Stamp the gather time NOW so repeated clicks don't re-add time-based Zeal
            new_ts = await self.bot.database.settlement.update_zeal_gather_time(
                uid, sid
            )
            self.settlement.last_zeal_gather_time = new_ts

            if collected <= 0:
                await interaction.followup.send(
                    "No passive Zeal has accumulated yet. Come back later!",
                    ephemeral=True,
                )
                return

            zeal_data = await self.bot.database.settlement.get_zeal_data(uid)
            turns_data = await self.bot.database.settlement.get_turns_data(uid, sid)
            active_events = await self.bot.database.settlement.get_active_events(
                uid, sid
            )
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
        """Launches the multi-page settlement tutorial narrated by Head Maid Spritz."""
        view = _MaidTutorialView(self.bot, parent=self)
        await interaction.response.send_message(
            embed=view.build_embed(), view=view, ephemeral=True
        )

    # -------------------------------------------------------------------------
    # Crisis encounter
    # -------------------------------------------------------------------------

    async def _on_confront(self, interaction: Interaction, event: dict) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            uid, sid = self.user_id, self.server_id

            # Allow transition from settlement state; block any other active state.
            current_op = self.bot.state_manager.active_operations.get(uid, (None, 0))[0]
            if current_op and current_op != "settlement":
                await interaction.followup.send(
                    "You're already in another activity. Finish it first.",
                    ephemeral=True,
                )
                return

            ev_def = SETTLEMENT_EVENTS.get(event["event_key"], {})
            enemy_name = (
                ev_def.get("effects", {})
                .get("spawn_combat", "enemy")
                .replace("_", " ")
                .title()
            )
            target_building_type = (event.get("data") or {}).get("target_building")

            from core.items.factory import load_player
            from core.models import Monster
            from core.combat.mobgen.gen_mob import generate_encounter
            from core.combat.turns import engine
            from core.combat.turns.boundary import reset_combat_transients
            from core.combat import ui as combat_ui
            from core.combat import jewel_engine as _je
            from core.combat.views.views import CombatView

            user_row = await self.bot.database.users.get(uid, sid)
            player = await load_player(uid, user_row, self.bot.database)

            spawn_key = ev_def.get("effects", {}).get("spawn_combat", "")
            crisis_image = CRISIS_MONSTER_IMAGES.get(spawn_key, "")

            base_monster = Monster(
                name=enemy_name,
                level=0,
                hp=0,
                max_hp=0,
                xp=0,
                attack=0,
                defence=0,
                modifiers=[],
                image=crisis_image,
                flavor="",
            )
            monster = await generate_encounter(player, base_monster, is_treasure=False)
            # Override name and image with the crisis-specific values
            monster.name = enemy_name
            if crisis_image:
                monster.image = crisis_image

            monster.reset_combat_bonuses()
            engine.apply_stat_effects(player, monster)
            start_logs = engine.apply_combat_start_passives(player, monster)
            _je.reset_jewel_charges(player)
            reset_combat_transients(player)

            combat_embed = combat_ui.create_combat_embed(
                player,
                monster,
                start_logs,
                title_override=f"⚔️ Crisis: {enemy_name}",
            )

            # Callback fires when CombatView reaches a terminal state.
            # By the time it runs, CombatView has already called clear_active.
            async def _crisis_end(won: bool) -> None:
                # Settle win/lose effects
                await self.bot.database.settlement.remove_events_by_key(
                    uid, sid, event["event_key"]
                )
                zeal_reward = 0
                if won:
                    zeal_reward = 50
                    await self.bot.database.settlement.add_zeal(uid, zeal_reward)
                else:
                    if target_building_type:
                        b = await self.bot.database.settlement.get_building_by_type(
                            uid, sid, target_building_type
                        )
                        if b:
                            await self.bot.database.settlement.disable_building(b.id)

                # Reload settlement state and transition the message back to the dashboard.
                self.settlement = await self.bot.database.settlement.get_settlement(
                    uid, sid
                )
                _plot_rows = await self.bot.database.plots.get_plots(uid, sid)
                self.plots = [
                    Plot(plot_index=r[0], is_developed=bool(r[1]), bonus_type=r[2])
                    for r in _plot_rows
                ]
                self.projects = await self.bot.database.settlement.get_projects(
                    uid, sid
                )
                self._cached_active_events = (
                    await self.bot.database.settlement.get_active_events(uid, sid)
                )
                self._rebuild_ui()
                self._processing = False
                self.bot.state_manager.set_active(uid, "settlement")
                crisis_summary = {
                    "crisis_result": {
                        "won": won,
                        "event_name": ev_def.get("name", enemy_name),
                        "zeal_earned": zeal_reward,
                    }
                }
                if self.message:
                    try:
                        await self.message.edit(
                            embed=self.build_embed(turn_summary=crisis_summary),
                            view=self,
                        )
                    except Exception:
                        pass

            # Switch active state: settlement → combat
            self.bot.state_manager.set_active(uid, "combat")

            view = CombatView(
                self.bot,
                uid,
                sid,
                player,
                monster,
                start_logs,
                combat_phases=[None],
                crisis_callback=_crisis_end,
            )

            # Transition the settlement message into the combat view (same message).
            await interaction.edit_original_response(embed=combat_embed, view=view)
            view.message = self.message

        except Exception:
            self._processing = False
            raise

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
