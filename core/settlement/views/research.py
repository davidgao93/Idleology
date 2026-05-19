# core/settlement/views/research.py
"""
Settlement Research tab.

Players spend 1 Unidentified Blueprint to research a building type.
Research takes 20 hours. Once researched, the building becomes available
in the Construction menu. Only one research can be active at a time.

Researchable buildings: companion_ranch, apothecary, temple, barracks,
                        black_market, market
"""

from __future__ import annotations

from datetime import datetime, timedelta

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.images import BLUEPRINT_RESEARCH

from .base import SettlementBaseView

_RESEARCH_HOURS = 20
_RESEARCH_COST_ITEM = "unidentified_blueprint"

# Buildings that require research before they can be built.
RESEARCHABLE_BUILDINGS: dict[str, str] = {
    "companion_ranch": "Companion Ranch",
    "apothecary": "Apothecary",
    "temple": "Temple",
    "barracks": "Barracks",
    "black_market": "Black Market",
    "market": "Market",
    "hatchery": "Hatchery",
}

_BUILDING_EMOJIS: dict[str, str] = {
    "companion_ranch": "🐾",
    "apothecary": "⚗️",
    "temple": "⛪",
    "barracks": "⚔️",
    "black_market": "🕵️",
    "market": "💰",
    "hatchery": "🐣",
}

_BUILDING_DESCS: dict[str, str] = {
    "companion_ranch": "Generates XP Cookies for pets",
    "apothecary": "Increases Potion Healing",
    "temple": "Increases Propagate follower gain",
    "barracks": "Passive ATK/DEF boost per Worker",
    "black_market": "Trade resources for mystery caches",
    "market": "Generates passive Gold",
    "hatchery": "Incubate monster eggs for blood drops",
}


def _fmt_duration(td: timedelta) -> str:
    total = max(0, int(td.total_seconds()))
    h, rem = divmod(total, 3600)
    m = rem // 60
    return f"{h}h {m}m" if h > 0 else f"{m}m"


class ResearchView(SettlementBaseView):
    def __init__(self, bot, user_id: str, server_id: str, parent_view) -> None:
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.parent = parent_view

        self._select: ui.Select | None = None
        self._researched: set[str] = set()
        self._active: tuple[str, str] | None = None  # (building_type, start_time)
        self._blueprint_count: int = 0

    # ------------------------------------------------------------------
    # Data loading (call before sending)
    # ------------------------------------------------------------------

    async def load(self) -> None:
        self._researched = await self.bot.database.settlement.get_researched(
            self.user_id, self.server_id
        )
        self._active = await self.bot.database.settlement.get_active_research(
            self.user_id, self.server_id
        )
        self._blueprint_count = await self.bot.database.users.get_currency(
            self.user_id, _RESEARCH_COST_ITEM
        )
        self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        self.clear_items()

        # Select — only buildings not yet researched or active
        options = []
        for b_type, b_name in RESEARCHABLE_BUILDINGS.items():
            if b_type in self._researched:
                continue
            active_type = self._active[0] if self._active else None
            if b_type == active_type:
                continue
            emoji = _BUILDING_EMOJIS[b_type]
            options.append(
                SelectOption(
                    label=b_name,
                    value=b_type,
                    emoji=emoji,
                    description=_BUILDING_DESCS[b_type],
                )
            )

        if options:
            self._select = ui.Select(
                placeholder="Choose a building to research…",
                options=options,
                row=0,
            )
            self._select.callback = self._on_select
            self.add_item(self._select)
        else:
            self._select = None

        # Collect button — only visible when active research is done
        research_ready = False
        if self._active:
            b_type, start_str = self._active
            end = datetime.fromisoformat(start_str) + timedelta(hours=_RESEARCH_HOURS)
            research_ready = datetime.now() >= end

        collect_btn = ui.Button(
            label="Collect Research",
            style=ButtonStyle.green if research_ready else ButtonStyle.secondary,
            emoji="📜",
            row=1,
            disabled=not research_ready,
        )
        collect_btn.callback = self._on_collect
        self.add_item(collect_btn)

        start_btn = ui.Button(
            label="Begin Research",
            style=ButtonStyle.blurple,
            emoji="🔬",
            row=1,
            disabled=bool(self._active),  # one at a time
        )
        start_btn.callback = self._on_start
        self.add_item(start_btn)

        back_btn = ui.Button(
            label="Back",
            style=ButtonStyle.secondary,
            emoji="⬅️",
            row=1,
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔬 Settlement Research",
            color=discord.Color.dark_teal(),
        )
        embed.set_thumbnail(url=BLUEPRINT_RESEARCH)
        embed.description = (
            f"Research buildings before you can construct them.\n"
            f"**Cost:** 1 Unidentified Blueprint per research\n"
            f"**Duration:** {_RESEARCH_HOURS} hours\n\n"
            f"📋 **Blueprints owned:** {self._blueprint_count}"
        )

        # Active research queue
        if self._active:
            b_type, start_str = self._active
            b_name = RESEARCHABLE_BUILDINGS.get(
                b_type, b_type.replace("_", " ").title()
            )
            emoji = _BUILDING_EMOJIS.get(b_type, "🔬")
            end = datetime.fromisoformat(start_str) + timedelta(hours=_RESEARCH_HOURS)
            now = datetime.now()
            if now >= end:
                embed.add_field(
                    name="🔬 Research Queue — ✅ READY",
                    value=f"{emoji} **{b_name}** — click **Collect Research** to unlock!",
                    inline=False,
                )
            else:
                remaining = end - now
                embed.add_field(
                    name="🔬 Research Queue — ⏳ In Progress",
                    value=f"{emoji} **{b_name}**\nReady in: **{_fmt_duration(remaining)}**",
                    inline=False,
                )
        else:
            embed.add_field(
                name="🔬 Research Queue",
                value="*No active research. Select a building and click **Begin Research**.*",
                inline=False,
            )

        # Status of all researchable buildings
        lines = []
        for b_type, b_name in RESEARCHABLE_BUILDINGS.items():
            emoji = _BUILDING_EMOJIS[b_type]
            if b_type in self._researched:
                lines.append(f"✅ {emoji} **{b_name}** — Unlocked")
            elif self._active and self._active[0] == b_type:
                lines.append(f"⏳ {emoji} **{b_name}** — In Progress")
            else:
                lines.append(f"🔒 {emoji} **{b_name}** — Not Researched")
        embed.add_field(name="📖 Research Status", value="\n".join(lines), inline=False)

        return embed

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_select(self, interaction: Interaction) -> None:
        await interaction.response.defer()

    async def _on_start(self, interaction: Interaction) -> None:
        if self._select is None or not self._select.values:
            await interaction.response.send_message(
                "Select a building to research first.", ephemeral=True
            )
            return

        b_type = self._select.values[0]

        # Check blueprint
        blueprints = await self.bot.database.users.get_currency(
            self.user_id, _RESEARCH_COST_ITEM
        )
        if blueprints < 1:
            await interaction.response.send_message(
                "You need 1 **Unidentified Blueprint** to begin research.\n"
                "Blueprints drop from normal combat (1% chance, affected by special rarity).",
                ephemeral=True,
            )
            return

        # Guard: no active research started by concurrent session
        active = await self.bot.database.settlement.get_active_research(
            self.user_id, self.server_id
        )
        if active:
            await interaction.response.send_message(
                "A research is already in progress. Collect it first.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Deduct blueprint and start research
        await self.bot.database.users.modify_currency(
            self.user_id, _RESEARCH_COST_ITEM, -1
        )
        await self.bot.database.settlement.start_research(
            self.user_id, self.server_id, b_type, datetime.now().isoformat()
        )

        await self.load()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _on_collect(self, interaction: Interaction) -> None:
        active = await self.bot.database.settlement.get_active_research(
            self.user_id, self.server_id
        )
        if not active:
            await interaction.response.send_message(
                "No active research to collect.", ephemeral=True
            )
            return

        b_type, start_str = active
        end = datetime.fromisoformat(start_str) + timedelta(hours=_RESEARCH_HOURS)
        if datetime.now() < end:
            await interaction.response.send_message(
                f"Research isn't done yet — {_fmt_duration(end - datetime.now())} remaining.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        await self.bot.database.settlement.complete_research(
            self.user_id, self.server_id, b_type
        )

        b_name = RESEARCHABLE_BUILDINGS.get(b_type, b_type.replace("_", " ").title())
        emoji = _BUILDING_EMOJIS.get(b_type, "🔬")
        await self.load()
        embed = self.build_embed()
        embed.colour = discord.Color.gold()
        embed.title = f"✅ Research Complete: {emoji} {b_name}!"
        await interaction.edit_original_response(embed=embed, view=self)

    async def _on_back(self, interaction: Interaction) -> None:
        self.parent.update_grid()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
