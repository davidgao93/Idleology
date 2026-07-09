"""The Arbiter's Aid — respite screen shown after clearing a wing.

Devout's Burden (writ, Milestone 4) will remove one of the 3 options at
random; all 3 are always offered until writs land.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.rite.run_state import RiteRunState

RESPITE_HEAL_PCT = 0.40
RESPITE_POTIONS = 2
EMERGENCY_POTIONS = 1
POWER_ATK_DEF_MULT = 1.30


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
        self._sync_items()

    def _build_container(self) -> discord.ui.Container:
        hp_pct = int(
            100 * self.player.current_hp / max(1, self.player.total_max_hp)
        )
        text = (
            "## 🕯️ The Arbiter's Aid\n"
            "*\"You've earned a moment's respite, adventurer. Choose your aid.\"*\n\n"
            f"**HP:** {self.player.current_hp:,}/{self.player.total_max_hp:,} ({hp_pct}%)  •  "
            f"**Potions:** {self.player.potions}\n"
            f"**Wings cleared:** {len(self.run_state.wings_cleared)}/5  •  "
            f"**Attempts remaining:** {self.run_state.attempts_remaining}\n\n"
            f"⚔️ **Power** — +{int((POWER_ATK_DEF_MULT - 1) * 100)}% ATK and DEF for the next fight only\n"
            f"💚 **Respite** — restore ~{int(RESPITE_HEAL_PCT * 100)}% HP + {RESPITE_POTIONS} potions\n"
            f"✨ **Emergency** — full HP restore + {EMERGENCY_POTIONS} potion"
        )
        return discord.ui.Container(
            discord.ui.TextDisplay(text), accent_color=discord.Color.gold()
        )

    def _build_rows(self) -> list[discord.ui.ActionRow]:
        row = discord.ui.ActionRow()
        btn_power = ui.Button(label="Power", style=ButtonStyle.danger, emoji="⚔️")
        btn_power.callback = self._on_power
        row.add_item(btn_power)

        btn_respite = ui.Button(label="Respite", style=ButtonStyle.success, emoji="💚")
        btn_respite.callback = self._on_respite
        row.add_item(btn_respite)

        btn_emergency = ui.Button(label="Emergency", style=ButtonStyle.primary, emoji="✨")
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
        self.run_state.pending_power_buff = True
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
