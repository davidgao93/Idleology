"""
core/alchemy/synthesis_views.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Synthesis hub: disenchant boss keys into Cosmic Dust via a timed queue,
and spend Cosmic Dust (+ gold) to synthesize new keys.

Layout
------
AlchemySynthesisHubView   — main screen; shows queue status, dust balance, key table
  └─ _DisenchantSelectView  — key-type picker + quantity modal → queues a task
  └─ _SynthesizeSelectView  — key-type picker + inline confirm → instant craft
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import discord
from discord import ui, ButtonStyle, Interaction

from core.alchemy.mechanics import AlchemyMechanics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_duration(td: timedelta) -> str:
    """Convert a timedelta into a short human-readable string."""
    total = max(0, int(td.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


async def _build_synthesis_hub(bot, user_id: str, server_id: str) -> AlchemySynthesisHubView:
    """Fetch fresh DB state and return a new AlchemySynthesisHubView."""
    alchemy_level = await bot.database.alchemy.get_level(user_id)
    cosmic_dust   = await bot.database.alchemy.get_cosmic_dust(user_id)
    queue_row     = await bot.database.alchemy.get_synthesis_queue(user_id)
    player_gold   = await bot.database.users.get_gold(user_id)
    return AlchemySynthesisHubView(
        bot, user_id, server_id,
        alchemy_level, cosmic_dust, queue_row, player_gold,
    )


# ---------------------------------------------------------------------------
# Synthesis Hub
# ---------------------------------------------------------------------------

class AlchemySynthesisHubView(ui.View):
    """
    Main synthesis screen. Shows cosmic dust, active queue, and key reference table.
    Buttons: Disenchant Keys | Collect Dust | Synthesize Key | Back
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        alchemy_level: int,
        cosmic_dust: int,
        queue_row,           # (item_type, quantity, start_time) or None
        player_gold: int,
    ):
        super().__init__(timeout=120)
        self.bot           = bot
        self.user_id       = user_id
        self.server_id     = server_id
        self.alchemy_level = alchemy_level
        self.cosmic_dust   = cosmic_dust
        self.queue_row     = queue_row
        self.player_gold   = player_gold
        self.message       = None

        # Determine whether a task is complete so we can style the Collect button.
        queue_ready = False
        if queue_row:
            _, qty, start_str = queue_row
            mins = AlchemyMechanics.get_disenchant_minutes(alchemy_level)
            end  = datetime.fromisoformat(start_str) + timedelta(minutes=mins * qty)
            queue_ready = datetime.now() >= end

        disenchant_btn = ui.Button(
            label    = "Disenchant Keys",
            style    = ButtonStyle.blurple,
            emoji    = "🔨",
            row      = 0,
            disabled = bool(queue_row),   # locked while a task is active
        )
        disenchant_btn.callback = self._on_disenchant
        self.add_item(disenchant_btn)

        collect_btn = ui.Button(
            label    = "Collect Dust",
            style    = ButtonStyle.green if queue_ready else ButtonStyle.secondary,
            emoji    = "✨",
            row      = 0,
            disabled = not queue_ready,
        )
        collect_btn.callback = self._on_collect
        self.add_item(collect_btn)

        synth_btn = ui.Button(
            label = "Synthesize Key",
            style = ButtonStyle.primary,
            emoji = "🔑",
            row   = 0,
        )
        synth_btn.callback = self._on_synthesize
        self.add_item(synth_btn)

        back_btn = ui.Button(
            label = "Back",
            style = ButtonStyle.secondary,
            emoji = "⬅️",
            row   = 1,
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    # ------------------------------------------------------------------
    # Checks / lifecycle
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        level    = self.alchemy_level
        mins     = AlchemyMechanics.get_disenchant_minutes(level)
        discount = level   # 1 % per level

        embed = discord.Embed(title="⚗️ Synthesis", color=discord.Color.teal())
        embed.description = (
            f"**Cosmic Dust:** ✨ {self.cosmic_dust:,}\n"
            f"**Gold:** 💰 {self.player_gold:,}\n"
            f"**Alchemy Lv {level}** — {mins}m per key · {discount}% synthesis discount"
        )

        # --- Queue status ---
        if self.queue_row:
            item_type, qty, start_str = self.queue_row
            total_mins = AlchemyMechanics.get_disenchant_minutes(self.alchemy_level) * qty
            end        = datetime.fromisoformat(start_str) + timedelta(minutes=total_mins)
            now        = datetime.now()
            name       = AlchemyMechanics.KEY_DISPLAY_NAMES[item_type]
            emoji      = AlchemyMechanics.KEY_EMOJIS[item_type]
            total_dust = AlchemyMechanics.DUST_YIELD[item_type] * qty

            if now >= end:
                embed.add_field(
                    name  = "🔨 Disenchant Queue — ✅ READY",
                    value = (
                        f"{emoji} **{qty}× {name}**\n"
                        f"Yield: ✨ **{total_dust:,} Cosmic Dust** — click **Collect Dust** to claim!"
                    ),
                    inline = False,
                )
            else:
                remaining = end - now
                embed.add_field(
                    name  = "🔨 Disenchant Queue — ⏳ In Progress",
                    value = (
                        f"{emoji} **{qty}× {name}**\n"
                        f"Yield: ✨ {total_dust:,} Cosmic Dust\n"
                        f"Ready in: **{_fmt_duration(remaining)}**"
                    ),
                    inline = False,
                )
        else:
            embed.add_field(
                name   = "🔨 Disenchant Queue",
                value  = "*No active task. Queue up boss keys to convert them into Cosmic Dust.*",
                inline = False,
            )

        # --- Key reference table ---
        lines = []
        for col, name in AlchemyMechanics.KEY_DISPLAY_NAMES.items():
            emoji      = AlchemyMechanics.KEY_EMOJIS[col]
            yield_val  = AlchemyMechanics.DUST_YIELD[col]
            synth_cost = AlchemyMechanics.get_synthesis_dust_cost(level, col)
            lines.append(
                f"{emoji} **{name}** — disenchant: {yield_val} ✨  |  synthesize: {synth_cost} ✨ + 💰 100k"
            )
        embed.add_field(name="📋 Key Rates", value="\n".join(lines), inline=False)

        return embed

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _on_disenchant(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = _DisenchantSelectView(
            self.bot, self.user_id, self.server_id, self.alchemy_level,
        )
        embed = await view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    async def _on_collect(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        # Re-fetch queue in case of concurrent sessions.
        queue_row = await self.bot.database.alchemy.get_synthesis_queue(self.user_id)
        if not queue_row:
            await interaction.followup.send("No active disenchant queue.", ephemeral=True)
            return

        item_type, qty, start_str = queue_row
        mins = AlchemyMechanics.get_disenchant_minutes(self.alchemy_level)
        end  = datetime.fromisoformat(start_str) + timedelta(minutes=mins * qty)
        if datetime.now() < end:
            await interaction.followup.send(
                f"Not ready yet — {_fmt_duration(end - datetime.now())} remaining.",
                ephemeral=True,
            )
            return

        total_dust = AlchemyMechanics.DUST_YIELD[item_type] * qty
        await self.bot.database.alchemy.modify_cosmic_dust(self.user_id, total_dust)
        await self.bot.database.alchemy.clear_synthesis_queue(self.user_id)

        name  = AlchemyMechanics.KEY_DISPLAY_NAMES[item_type]
        emoji = AlchemyMechanics.KEY_EMOJIS[item_type]

        view  = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        embed.colour = discord.Color.gold()
        embed.title  = f"✨ Collected {total_dust:,} Cosmic Dust!"
        embed.description = (
            f"{emoji} **{qty}× {name}** successfully disenchanted.\n\n"
        ) + (embed.description or "")
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    async def _on_synthesize(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view  = _SynthesizeSelectView(
            self.bot, self.user_id, self.server_id,
            self.alchemy_level, self.cosmic_dust, self.player_gold,
        )
        embed = view.build_embed()
        msg   = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    async def _on_back(self, interaction: Interaction) -> None:
        from core.alchemy.views import _hub_from_db
        await interaction.response.defer()
        view  = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg   = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()


# ---------------------------------------------------------------------------
# Disenchant — key-type select + quantity modal
# ---------------------------------------------------------------------------

class _DisenchantQuantityModal(ui.Modal, title="How many keys to disenchant?"):
    quantity = ui.TextInput(
        label       = "Quantity",
        placeholder = "Enter a number (e.g. 5)",
        min_length  = 1,
        max_length  = 4,
    )

    def __init__(self, parent: _DisenchantSelectView, item_type: str, owned: int):
        super().__init__()
        self._parent    = parent
        self._item_type = item_type
        self._owned     = owned

    async def on_submit(self, interaction: Interaction) -> None:
        raw = self.quantity.value.strip()
        if not raw.isdigit() or int(raw) < 1:
            await interaction.response.send_message(
                "Please enter a positive whole number.", ephemeral=True)
            return

        qty = int(raw)
        if qty > self._owned:
            name = AlchemyMechanics.KEY_DISPLAY_NAMES[self._item_type]
            await interaction.response.send_message(
                f"You only have **{self._owned}** {name}.", ephemeral=True)
            return

        # Guard: no active queue already (race-condition safety).
        existing = await self._parent.bot.database.alchemy.get_synthesis_queue(
            self._parent.user_id)
        if existing:
            await interaction.response.send_message(
                "You already have an active disenchant queue. Collect it first.",
                ephemeral=True)
            return

        await interaction.response.defer()

        # Deduct keys and queue the task.
        await self._parent.bot.database.users.modify_currency(
            self._parent.user_id, self._item_type, -qty)
        await self._parent.bot.database.alchemy.start_disenchant(
            self._parent.user_id, self._item_type, qty, datetime.now().isoformat())

        level      = self._parent.alchemy_level
        total_mins = AlchemyMechanics.get_disenchant_minutes(level) * qty
        total_dust = AlchemyMechanics.DUST_YIELD[self._item_type] * qty
        name       = AlchemyMechanics.KEY_DISPLAY_NAMES[self._item_type]
        emoji      = AlchemyMechanics.KEY_EMOJIS[self._item_type]

        view  = await _build_synthesis_hub(
            self._parent.bot, self._parent.user_id, self._parent.server_id)
        embed = view.build_embed()
        embed.colour = discord.Color.blurple()
        embed.title  = f"🔨 Disenchant queued: {qty}× {name}"
        embed.description = (
            f"{emoji} **{qty}× {name}** sent to the disenchant queue.\n"
            f"⏳ Ready in **{total_mins} minutes** · Yield: ✨ **{total_dust:,} Cosmic Dust**\n\n"
        ) + (embed.description or "")
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self._parent.stop()


class _DisenchantKeySelect(ui.Select):
    def __init__(self, options_data: list[dict]) -> None:
        opts = [
            discord.SelectOption(
                label       = d["name"][:100],
                description = d["select_desc"][:100],
                value       = d["col"],
                emoji       = d["emoji"],
            )
            for d in options_data
            if d["owned"] > 0
        ]
        if not opts:
            opts = [discord.SelectOption(label="No keys owned", value="_none")]
        super().__init__(placeholder="Select a key type to disenchant…", options=opts)
        self._data_by_col = {d["col"]: d for d in options_data}
        self.selected: str | None = None

    async def callback(self, interaction: Interaction) -> None:
        if self.values[0] == "_none":
            await interaction.response.send_message(
                "You have no boss keys to disenchant.", ephemeral=True)
            return
        self.selected = self.values[0]
        await interaction.response.defer()


class _DisenchantSelectView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, alchemy_level: int) -> None:
        super().__init__(timeout=120)
        self.bot           = bot
        self.user_id       = user_id
        self.server_id     = server_id
        self.alchemy_level = alchemy_level
        self.message       = None
        self._options_data: list[dict] = []
        self._select: _DisenchantKeySelect | None = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def build_embed(self) -> discord.Embed:
        """Fetch live key counts, rebuild the select menu, and return the embed."""
        mins = AlchemyMechanics.get_disenchant_minutes(self.alchemy_level)

        self._options_data = []
        for col, name in AlchemyMechanics.KEY_DISPLAY_NAMES.items():
            owned = await self.bot.database.users.get_currency(self.user_id, col)
            self._options_data.append({
                "col":         col,
                "name":        name,
                "emoji":       AlchemyMechanics.KEY_EMOJIS[col],
                "owned":       owned,
                "select_desc": f"Own: {owned}  ·  {AlchemyMechanics.DUST_YIELD[col]} ✨/key  ·  {mins}m/key",
            })

        self.clear_items()
        self._select = _DisenchantKeySelect(self._options_data)
        self.add_item(self._select)

        confirm_btn = ui.Button(
            label = "Queue Disenchant", style = ButtonStyle.green, emoji = "🔨", row = 1)
        confirm_btn.callback = self._on_confirm
        self.add_item(confirm_btn)

        back_btn = ui.Button(
            label = "Back", style = ButtonStyle.secondary, emoji = "⬅️", row = 1)
        back_btn.callback = self._on_back
        self.add_item(back_btn)

        embed = discord.Embed(title="🔨 Disenchant Keys", color=discord.Color.blurple())
        lines = []
        for d in self._options_data:
            owned_str = f"**{d['owned']}** owned" if d["owned"] > 0 else "*none owned*"
            lines.append(
                f"{d['emoji']} **{d['name']}** — {owned_str}  ·  "
                f"✨ {AlchemyMechanics.DUST_YIELD[d['col']]} dust/key  ·  ⏳ {mins}m/key"
            )
        embed.description = (
            f"Select a key type, enter a quantity, and queue them for disenchanting.\n"
            f"Each key takes **{mins} minutes** at Alchemy Level {self.alchemy_level}.\n\n"
            + "\n".join(lines)
        )
        return embed

    async def _on_confirm(self, interaction: Interaction) -> None:
        if not self._select or not self._select.selected:
            await interaction.response.send_message(
                "Please select a key type first.", ephemeral=True)
            return
        col  = self._select.selected
        data = next(d for d in self._options_data if d["col"] == col)
        if data["owned"] == 0:
            await interaction.response.send_message(
                "You don't have any of those keys.", ephemeral=True)
            return
        await interaction.response.send_modal(
            _DisenchantQuantityModal(self, col, data["owned"]))

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view  = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg   = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()


# ---------------------------------------------------------------------------
# Synthesize — key-type select + inline confirm
# ---------------------------------------------------------------------------

class _SynthesizeKeySelect(ui.Select):
    def __init__(self, options_data: list[dict]) -> None:
        opts = [
            discord.SelectOption(
                label       = d["name"][:100],
                description = d["select_desc"][:100],
                value       = d["col"],
                emoji       = d["emoji"],
            )
            for d in options_data
        ]
        super().__init__(placeholder="Select a key to synthesize…", options=opts)
        self.selected: str | None = None

    async def callback(self, interaction: Interaction) -> None:
        self.selected = self.values[0]
        await interaction.response.defer()


class _SynthesizeConfirmView(ui.View):
    """Inline confirm/cancel shown after the player picks a key to synthesize."""

    def __init__(self, parent: _SynthesizeSelectView, item_type: str, dust_cost: int) -> None:
        super().__init__(timeout=30)
        self._parent    = parent
        self._item_type = item_type
        self._dust_cost = dust_cost

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self._parent.user_id

    @ui.button(label="Confirm", style=ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()

        # Re-validate live balances before committing.
        cosmic_dust = await self._parent.bot.database.alchemy.get_cosmic_dust(
            self._parent.user_id)
        gold = await self._parent.bot.database.users.get_gold(self._parent.user_id)

        if cosmic_dust < self._dust_cost:
            await interaction.followup.send(
                f"Not enough Cosmic Dust! Need ✨ **{self._dust_cost:,}**, "
                f"have **{cosmic_dust:,}**.",
                ephemeral=True)
            return
        if gold < AlchemyMechanics.SYNTHESIS_GOLD_COST:
            await interaction.followup.send(
                f"Not enough gold! Need 💰 **{AlchemyMechanics.SYNTHESIS_GOLD_COST:,}**, "
                f"have **{gold:,}**.",
                ephemeral=True)
            return

        await self._parent.bot.database.alchemy.modify_cosmic_dust(
            self._parent.user_id, -self._dust_cost)
        await self._parent.bot.database.users.modify_gold(
            self._parent.user_id, -AlchemyMechanics.SYNTHESIS_GOLD_COST)
        await self._parent.bot.database.users.modify_currency(
            self._parent.user_id, self._item_type, 1)

        name  = AlchemyMechanics.KEY_DISPLAY_NAMES[self._item_type]
        emoji = AlchemyMechanics.KEY_EMOJIS[self._item_type]

        view  = await _build_synthesis_hub(
            self._parent.bot, self._parent.user_id, self._parent.server_id)
        embed = view.build_embed()
        embed.colour = discord.Color.gold()
        embed.title  = f"🔑 Synthesized: {emoji} {name}!"
        embed.description = (
            f"You spent ✨ **{self._dust_cost:,} Cosmic Dust** + 💰 **100,000 Gold** "
            f"and received **1× {emoji} {name}**.\n\n"
        ) + (embed.description or "")
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self._parent.stop()
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="⬅️")
    async def cancel(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        embed = self._parent.build_embed()
        await interaction.edit_original_response(embed=embed, view=self._parent)
        self.stop()


class _SynthesizeSelectView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        alchemy_level: int,
        cosmic_dust: int,
        player_gold: int,
    ) -> None:
        super().__init__(timeout=120)
        self.bot           = bot
        self.user_id       = user_id
        self.server_id     = server_id
        self.alchemy_level = alchemy_level
        self.cosmic_dust   = cosmic_dust
        self.player_gold   = player_gold
        self.message       = None

        options_data = []
        for col, name in AlchemyMechanics.KEY_DISPLAY_NAMES.items():
            dust_cost = AlchemyMechanics.get_synthesis_dust_cost(alchemy_level, col)
            options_data.append({
                "col":         col,
                "name":        name,
                "emoji":       AlchemyMechanics.KEY_EMOJIS[col],
                "dust_cost":   dust_cost,
                "select_desc": f"{dust_cost} ✨ + 100k 💰 → 1× {name}",
            })
        self._options_data = options_data

        self._select = _SynthesizeKeySelect(options_data)
        self.add_item(self._select)

        confirm_btn = ui.Button(
            label = "Synthesize", style = ButtonStyle.primary, emoji = "🔑", row = 1)
        confirm_btn.callback = self._on_confirm
        self.add_item(confirm_btn)

        back_btn = ui.Button(
            label = "Back", style = ButtonStyle.secondary, emoji = "⬅️", row = 1)
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    def build_embed(self) -> discord.Embed:
        level    = self.alchemy_level
        discount = level   # 1 % per level

        embed = discord.Embed(title="🔑 Synthesize Key", color=discord.Color.purple())
        embed.description = (
            f"**Cosmic Dust:** ✨ {self.cosmic_dust:,}  |  **Gold:** 💰 {self.player_gold:,}\n"
            f"**Synthesis Discount:** {discount}% (Alchemy Level {level})\n\n"
            "Select a key type, then press **Synthesize** to confirm."
        )

        lines = []
        for d in self._options_data:
            dust_cost   = AlchemyMechanics.get_synthesis_dust_cost(level, d["col"])
            can_afford  = (
                self.cosmic_dust  >= dust_cost
                and self.player_gold >= AlchemyMechanics.SYNTHESIS_GOLD_COST
            )
            status = "✅" if can_afford else "❌"
            lines.append(
                f"{status} {d['emoji']} **{d['name']}** — ✨ {dust_cost:,}  +  💰 100,000"
            )
        embed.add_field(name="Available Syntheses", value="\n".join(lines), inline=False)
        return embed

    async def _on_confirm(self, interaction: Interaction) -> None:
        if not self._select.selected:
            await interaction.response.send_message(
                "Please select a key type first.", ephemeral=True)
            return

        col       = self._select.selected
        dust_cost = AlchemyMechanics.get_synthesis_dust_cost(self.alchemy_level, col)
        name      = AlchemyMechanics.KEY_DISPLAY_NAMES[col]
        emoji     = AlchemyMechanics.KEY_EMOJIS[col]

        confirm_view = _SynthesizeConfirmView(self, col, dust_cost)
        embed = discord.Embed(
            title       = "🔑 Confirm Synthesis",
            description = (
                f"Synthesize **1× {emoji} {name}**?\n\n"
                f"Cost: ✨ **{dust_cost:,} Cosmic Dust**  +  💰 **100,000 Gold**\n"
                f"You have: ✨ {self.cosmic_dust:,}  |  💰 {self.player_gold:,}"
            ),
            color = discord.Color.gold(),
        )
        await interaction.response.edit_message(embed=embed, view=confirm_view)

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view  = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg   = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()
