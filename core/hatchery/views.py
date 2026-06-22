from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.hatchery.mechanics import HatcheryMechanics
from core.images import YUNA_PORTRAIT, YUNA_THUMBNAIL
from core.npc_voices import get_quip

_EGG_TIER_EMOJI = {"normal": "🥚", "rare": "🪺", "giga": "🐲"}
_EGG_TIER_LABEL = {"normal": "Normal Egg", "rare": "Rare Egg", "giga": "Giga Egg"}


def _fmt_duration(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _remaining_seconds(start_time_iso: str, duration_seconds: int) -> float:
    start = datetime.fromisoformat(start_time_iso)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    return max(0.0, duration_seconds - elapsed)


class EggQueueSelect(ui.Select):
    """Lets the player pick an egg from inventory to start incubating."""

    def __init__(self, eggs: list):
        options = []
        for egg in eggs[:25]:
            tier = egg[1]
            emoji = _EGG_TIER_EMOJI.get(tier, "🥚")
            label = f"{_EGG_TIER_LABEL.get(tier, tier)} — lvl {egg[2]} {egg[3]}"
            options.append(
                discord.SelectOption(label=label[:100], value=str(egg[0]), emoji=emoji)
            )
        super().__init__(placeholder="Choose an egg to incubate...", options=options)
        self.eggs_by_id = {str(e[0]): e for e in eggs}

    async def callback(self, interaction: Interaction):
        egg = self.eggs_by_id.get(self.values[0])
        if not egg:
            return await interaction.response.send_message(
                "Egg not found.", ephemeral=True
            )
        await interaction.response.defer()
        await self.view._start_incubation(interaction, egg)


class HatcheryView(BaseView):
    """Standalone view for the Hatchery building.

    Can be opened from BuildingDetailView (parent_view set) or directly via
    the /hatchery command (parent_view=None).  When standalone, a Close button
    replaces the Back button and clears the active state on exit.
    """

    def __init__(self, bot, user_id: str, server_id: str, building, parent_view=None):
        super().__init__(bot, user_id, server_id)
        self.building = building  # settlement Building dataclass
        self.parent_view = parent_view  # BuildingDetailView, or None if standalone
        self._incubation = None  # cached incubation dict
        self._eggs = []  # cached egg inventory

    # ------------------------------------------------------------------ #
    #  Data helpers
    # ------------------------------------------------------------------ #

    async def _load(self):
        self._incubation = await self.bot.database.eggs.get_incubation(
            self.user_id, self.server_id
        )
        self._eggs = await self.bot.database.eggs.get_eggs(self.user_id)

    # ------------------------------------------------------------------ #
    #  Embed builder
    # ------------------------------------------------------------------ #

    def build_embed(self) -> discord.Embed:
        workers = self.building.workers_assigned

        # Pick the appropriate quip — release quip if something is ready to collect
        is_ready = (
            self._incubation is not None
            and _remaining_seconds(
                self._incubation["start_time"], self._incubation["duration_seconds"]
            ) <= 0
        )
        quip = get_quip("hatchery_release") if is_ready else get_quip("hatchery")

        embed = discord.Embed(
            title="🐣 Hatchery",
            description=f"*{quip}*",
            color=0x4CAF50,
        )
        embed.set_author(name="Master Tamer Yuna", icon_url=YUNA_PORTRAIT)
        embed.set_thumbnail(url=YUNA_THUMBNAIL)

        egg_counts = {}
        for e in self._eggs:
            egg_counts[e[1]] = egg_counts.get(e[1], 0) + 1
        egg_summary = (
            "  ".join(
                f"{_EGG_TIER_EMOJI[t]} {egg_counts[t]}"
                for t in ("normal", "rare", "giga")
                if egg_counts.get(t, 0) > 0
            )
            or "No eggs"
        )
        embed.add_field(
            name="Egg Inventory",
            value=f"{egg_summary} ({len(self._eggs)}/20)",
            inline=False,
        )

        # Incubation time table based on current worker count
        rows = []
        for tier in ("normal", "rare", "giga"):
            secs = HatcheryMechanics.incubation_seconds(tier, workers)
            rows.append(
                f"{_EGG_TIER_EMOJI[tier]} **{_EGG_TIER_LABEL[tier]}** — {_fmt_duration(secs)}"
            )
        embed.add_field(
            name=f"Incubation Times (with {workers} worker{'s' if workers != 1 else ''})",
            value="\n".join(rows),
            inline=False,
        )

        if self._incubation:
            inc = self._incubation
            rem = _remaining_seconds(inc["start_time"], inc["duration_seconds"])
            emoji = _EGG_TIER_EMOJI.get(inc["egg_tier"], "🥚")
            label = _EGG_TIER_LABEL.get(inc["egg_tier"], inc["egg_tier"])
            if rem > 0:
                embed.add_field(
                    name="Incubating",
                    value=f"{emoji} **{label}** — {inc['monster_name']} (lvl {inc['monster_level']})\n⏳ {_fmt_duration(rem)} remaining",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="✨ Incubation Complete!",
                    value=(
                        f"{emoji} **{label}** — {inc['monster_name']} (lvl {inc['monster_level']})\n"
                        f"Click **Release** to queue them for your next `/combat` encounter.\n"
                        f"⚠️ *These creatures are extremely dangerous — come fully prepared!*"
                    ),
                    inline=False,
                )
        else:
            embed.add_field(
                name="Incubation Slot",
                value="*Empty — queue an egg to begin.*",
                inline=False,
            )

        return embed

    # ------------------------------------------------------------------ #
    #  Button setup (dynamic)
    # ------------------------------------------------------------------ #

    def _rebuild_buttons(self):
        self.clear_items()

        # Incubate egg button (only when no active incubation and eggs exist)
        if self._incubation is None:
            if self._eggs:
                btn_queue = ui.Button(
                    label="Incubate Egg", style=ButtonStyle.success, emoji="🥚", row=0
                )
                btn_queue.callback = self._open_egg_select
                self.add_item(btn_queue)
            else:
                btn_none = ui.Button(
                    label="No Eggs in Inventory",
                    style=ButtonStyle.secondary,
                    disabled=True,
                    row=0,
                )
                self.add_item(btn_none)
        else:
            rem = _remaining_seconds(
                self._incubation["start_time"], self._incubation["duration_seconds"]
            )
            if rem <= 0:
                btn_release = ui.Button(
                    label="Release", style=ButtonStyle.danger, emoji="🐉", row=0
                )
                btn_release.callback = self._release
                self.add_item(btn_release)
            else:
                btn_wait = ui.Button(
                    label="Incubating...",
                    style=ButtonStyle.secondary,
                    disabled=True,
                    row=0,
                )
                self.add_item(btn_wait)

        # Show Back only when opened from the settlement view
        if self.parent_view is not None:
            btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
            btn_back.callback = self._back
            self.add_item(btn_back)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        btn_close.callback = self._close
        self.add_item(btn_close)

    # ------------------------------------------------------------------ #
    #  Actions
    # ------------------------------------------------------------------ #

    async def _open_egg_select(self, interaction: Interaction):
        await interaction.response.defer()
        # Rebuild with a select to pick the egg
        self.clear_items()
        self.add_item(EggQueueSelect(self._eggs))
        btn_cancel = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=1)
        btn_cancel.callback = self._cancel_select
        self.add_item(btn_cancel)
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _cancel_select(self, interaction: Interaction):
        await interaction.response.defer()
        self._rebuild_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _start_incubation(self, interaction: Interaction, egg: tuple):
        """Called by EggQueueSelect.callback."""
        egg_id, egg_tier, monster_level, monster_name = egg[0], egg[1], egg[2], egg[3]
        workers = self.building.workers_assigned
        duration = HatcheryMechanics.incubation_seconds(egg_tier, workers)

        await self.bot.database.eggs.start_incubation(
            self.user_id,
            self.server_id,
            egg_id,
            egg_tier,
            monster_level,
            monster_name,
            duration,
        )
        await self.bot.database.eggs.delete_egg(egg_id)

        await self._load()
        self._rebuild_buttons()
        embed = self.build_embed()
        embed.set_footer(
            text=f"Incubation started! Estimated: {_fmt_duration(duration)}"
        )
        await interaction.edit_original_response(embed=embed, view=self)

    async def _release(self, interaction: Interaction):
        await interaction.response.defer()
        inc = self._incubation
        if inc is None:
            return

        rem = _remaining_seconds(inc["start_time"], inc["duration_seconds"])
        if rem > 0:
            return await interaction.followup.send(
                f"Incubation not yet complete ({_fmt_duration(rem)} remaining).",
                ephemeral=True,
            )

        await self.bot.database.eggs.queue_incubated_encounter(
            self.user_id, inc["monster_name"], inc["monster_level"], inc["egg_tier"]
        )
        await self.bot.database.eggs.complete_incubation(self.user_id, self.server_id)

        await self._load()
        self._rebuild_buttons()
        embed = self.build_embed()
        embed.set_footer(
            text="The creature has been released. It will appear in your next /combat encounter."
        )
        await interaction.edit_original_response(embed=embed, view=self)

    async def _back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.parent_view.build_embed(), view=self.parent_view
        )
        self.stop()

    async def _close(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.message.delete()
