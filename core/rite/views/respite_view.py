"""The Arbiter's Aid — respite screen shown after clearing a wing.

The Devout's Burden writ removes one of the 3 options at random (rolled once
per respite, not re-rolled if the view is redrawn).
"""

import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.npc_voices import get_quip
from core.rite.run_state import RiteRunState

RESPITE_HEAL_PCT = 0.40
RESPITE_POTIONS = 3
EMERGENCY_POTIONS = 1
# Additive per-stack ATK/DEF bonus for Respite's "Power" choice — cumulative
# and permanent for the rest of the run (see RiteRunState.power_stacks).
POWER_ATK_DEF_INCREMENT = 0.30


def apply_power_stacks(player, run_state: RiteRunState) -> None:
    """Applies the accumulated Power buff to player.cs — must be called
    fresh at the start of every wing attempt and every Arbiter phase, since
    reset_combat_state()/reset_combat_bonus() both zero cs.atk_multiplier/
    def_multiplier back to 1.0. No-op if no Power has been picked yet."""
    if run_state.power_stacks <= 0:
        return
    power_mult = 1.0 + POWER_ATK_DEF_INCREMENT * run_state.power_stacks
    player.cs.atk_multiplier = power_mult
    player.cs.def_multiplier = power_mult


class RespiteView(BaseLayoutView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player,
        run_state: RiteRunState,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.run_state = run_state
        self._processing = False
        self._omitted_option = (
            random.choice(["power", "respite", "emergency"])
            if "devouts_burden" in run_state.writs
            else None
        )
        self._quip = get_quip("arbiter")
        self._sync_items()

    def _build_container(self) -> discord.ui.Container:
        hp_pct = int(100 * self.player.current_hp / max(1, self.player.total_max_hp))
        lives = "🧠" * self.run_state.attempts_remaining + "⚪" * (
            self.run_state.max_attempts - self.run_state.attempts_remaining
        )
        lines = [
            "## 🕯️ The Arbiter's Aid",
            f'*"{self._quip}"*',
            "",
            f"**HP:** {self.player.current_hp:,}/{self.player.total_max_hp:,} ({hp_pct}%)  •  "
            f"**Potions:** {self.player.potions}",
            f"**Wings cleared:** {len(self.run_state.wings_cleared)}/5  •  "
            f"**Lives:** {lives}",
            "",
        ]
        if self._omitted_option:
            lines.append(
                "*The Devout's Burden weighs on this respite — one aid is unavailable.*"
            )
            lines.append("")
        if self._omitted_option != "power":
            # round(), not int() — float multiplication (e.g. 3 * 0.30 * 100
            # == 89.99999999999999) truncates wrong under plain int().
            cur_pct = round(self.run_state.power_stacks * POWER_ATK_DEF_INCREMENT * 100)
            next_pct = round(
                (self.run_state.power_stacks + 1) * POWER_ATK_DEF_INCREMENT * 100
            )
            lines.append(
                f"⚔️ **Power** — +{round(POWER_ATK_DEF_INCREMENT * 100)}% ATK and DEF, "
                f"permanently, for the rest of the run "
                f"(currently +{cur_pct}% → +{next_pct}%)"
            )
        if self._omitted_option != "respite":
            lines.append(
                f"💚 **Respite** — restore ~{int(RESPITE_HEAL_PCT * 100)}% HP + {RESPITE_POTIONS} potions"
            )
        if self._omitted_option != "emergency":
            lines.append(
                f"✨ **Emergency** — full HP restore + {EMERGENCY_POTIONS} potion"
            )
        return discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)), accent_color=discord.Color.gold()
        )

    def _build_rows(self) -> list[discord.ui.ActionRow]:
        row = discord.ui.ActionRow()
        if self._omitted_option != "power":
            btn_power = ui.Button(label="Power", style=ButtonStyle.danger, emoji="⚔️")
            btn_power.callback = self._on_power
            row.add_item(btn_power)

        if self._omitted_option != "respite":
            btn_respite = ui.Button(
                label="Respite", style=ButtonStyle.success, emoji="💚"
            )
            btn_respite.callback = self._on_respite
            row.add_item(btn_respite)

        if self._omitted_option != "emergency":
            btn_emergency = ui.Button(
                label="Emergency", style=ButtonStyle.primary, emoji="✨"
            )
            btn_emergency.callback = self._on_emergency
            row.add_item(btn_emergency)
        return [row]

    def _sync_items(self):
        self.clear_items()
        self.add_item(self._build_container())
        for row in self._build_rows():
            self.add_item(row)

    async def _apply_and_continue(self, interaction: Interaction):
        await self.bot.database.users.update_from_player_object(self.player)
        await self.bot.database.rite.upsert_run(
            self.user_id, self.server_id, self.run_state.to_snapshot()
        )

        # Lazy import: wing_hub_view imports RespiteView on wing-clear, so a
        # module-level import here would be circular.
        from core.rite.views.wing_hub_view import WingHubView

        hub = WingHubView(
            self.bot, self.user_id, self.server_id, self.player, self.run_state
        )
        await interaction.edit_original_response(view=hub)
        hub.message = await interaction.original_response()
        self.stop()

    async def _on_power(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.run_state.power_stacks += 1
        await self._apply_and_continue(interaction)

    async def _on_respite(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        heal = int(self.player.total_max_hp * RESPITE_HEAL_PCT)
        self.player.current_hp = min(
            self.player.total_max_hp, self.player.current_hp + heal
        )
        self.player.potions += RESPITE_POTIONS
        await self._apply_and_continue(interaction)

    async def _on_emergency(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.player.current_hp = self.player.total_max_hp
        self.player.potions += EMERGENCY_POTIONS
        await self._apply_and_continue(interaction)
