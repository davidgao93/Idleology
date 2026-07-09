"""Pre-run Writs of Devotion selection. Locked until the player's first full
clear (rite.has_first_clear) — cogs/rite.py only shows this view when that
flag is set.
"""

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_layout_view import BaseLayoutView
from core.rite.data import ATTEMPTS_WRIT_KEYS, SPEED_WRIT_KEYS, TOGGLE_WRIT_KEYS, WRITS
from core.rite.data import compute_devotion_points

_NONE_VALUE = "__none__"


class WritSelectView(BaseLayoutView):
    def __init__(self, bot, user_id: str, server_id: str, player, on_confirm):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.selected: set[str] = set()
        # async fn(interaction, writ_keys: list[str]) -> None
        self.on_confirm = on_confirm
        self._processing = False
        self._sync_items()

    def _build_container(self) -> discord.ui.Container:
        # DP preview assumes speed writs land (best case) — the real total is
        # only known once total_turns is measured at run completion.
        preview_dp = compute_devotion_points(sorted(self.selected), total_turns=0)
        lines = [
            "## 📜 Writs of Devotion",
            "Optional modifiers that increase this run's difficulty and its "
            "Devotion Points — DP gates Artefact tier access and boosts loot.",
            "",
        ]
        for key in TOGGLE_WRIT_KEYS + SPEED_WRIT_KEYS + ATTEMPTS_WRIT_KEYS:
            w = WRITS[key]
            mark = "✅" if key in self.selected else "▫️"
            lines.append(f"{mark} **{w.name}** (+{w.dp} DP) — {w.effect}")
        lines.append("")
        lines.append(f"**Preview Devotion Points:** {preview_dp}+ *(speed writ DP only counts if you hit the deadline)*")
        return discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)), accent_color=discord.Color.dark_gold()
        )

    def _build_rows(self) -> list[discord.ui.ActionRow]:
        row1 = discord.ui.ActionRow()
        opts1 = [
            SelectOption(
                label=WRITS[k].name, value=k, description=f"+{WRITS[k].dp} DP",
                default=(k in self.selected),
            )
            for k in TOGGLE_WRIT_KEYS
        ]
        sel1 = ui.Select(
            placeholder="Independent writs (pick any)...",
            options=opts1, min_values=0, max_values=len(opts1),
        )
        sel1.callback = self._on_toggle_select
        row1.add_item(sel1)

        row2 = discord.ui.ActionRow()
        speed_selected = next((k for k in SPEED_WRIT_KEYS if k in self.selected), None)
        opts2 = [SelectOption(label="None", value=_NONE_VALUE, default=speed_selected is None)]
        opts2 += [
            SelectOption(
                label=WRITS[k].name, value=k, description=f"+{WRITS[k].dp} DP",
                default=(k == speed_selected),
            )
            for k in SPEED_WRIT_KEYS
        ]
        sel2 = ui.Select(placeholder="Speed writ (pick one)...", options=opts2, min_values=1, max_values=1)
        sel2.callback = self._on_speed_select
        row2.add_item(sel2)

        row3 = discord.ui.ActionRow()
        attempts_selected = next((k for k in ATTEMPTS_WRIT_KEYS if k in self.selected), None)
        opts3 = [SelectOption(label="None", value=_NONE_VALUE, default=attempts_selected is None)]
        opts3 += [
            SelectOption(
                label=WRITS[k].name, value=k, description=f"+{WRITS[k].dp} DP",
                default=(k == attempts_selected),
            )
            for k in ATTEMPTS_WRIT_KEYS
        ]
        sel3 = ui.Select(placeholder="Attempts writ (pick one)...", options=opts3, min_values=1, max_values=1)
        sel3.callback = self._on_attempts_select
        row3.add_item(sel3)

        row4 = discord.ui.ActionRow()
        btn_confirm = ui.Button(label="Begin the Rite", style=ButtonStyle.danger, emoji="🕯️")
        btn_confirm.callback = self._on_confirm
        row4.add_item(btn_confirm)

        btn_skip = ui.Button(label="Skip Writs", style=ButtonStyle.secondary)
        btn_skip.callback = self._on_skip
        row4.add_item(btn_skip)

        return [row1, row2, row3, row4]

    def _sync_items(self):
        self.clear_items()
        self.add_item(self._build_container())
        for row in self._build_rows():
            self.add_item(row)

    async def _on_toggle_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        chosen = set(interaction.data["values"])
        self.selected -= set(TOGGLE_WRIT_KEYS)
        self.selected |= chosen
        self._sync_items()
        await interaction.response.edit_message(view=self)
        self._processing = False

    async def _on_speed_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        value = interaction.data["values"][0]
        self.selected -= set(SPEED_WRIT_KEYS)
        if value != _NONE_VALUE:
            self.selected.add(value)
        self._sync_items()
        await interaction.response.edit_message(view=self)
        self._processing = False

    async def _on_attempts_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        value = interaction.data["values"][0]
        self.selected -= set(ATTEMPTS_WRIT_KEYS)
        if value != _NONE_VALUE:
            self.selected.add(value)
        self._sync_items()
        await interaction.response.edit_message(view=self)
        self._processing = False

    async def _on_confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await self.on_confirm(interaction, sorted(self.selected))
        self.stop()

    async def _on_skip(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await self.on_confirm(interaction, [])
        self.stop()
