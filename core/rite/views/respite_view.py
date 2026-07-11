"""The Arbiter's Aid — respite screen shown after clearing a wing.

The Devout's Burden writ removes one of the 3 options at random (rolled once
per respite, not re-rolled if the view is redrawn).
"""

import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.images import ARBITER_THUMBNAIL
from core.npc_voices import get_quip
from core.rite.run_state import RiteRunState

RESPITE_HEAL_PCT = 0.40
RESPITE_POTIONS = 2
EMERGENCY_POTIONS = 8
MAX_POTIONS = 20
# Additive per-stack ATK/DEF bonus for Respite's "Power" choice — cumulative
# and permanent for the rest of the run (see RiteRunState.power_stacks).
POWER_ATK_DEF_INCREMENT = 0.30
# Additive per-stack Max HP % bonus for Respite's "Respite" choice — same
# persistence rules as Power (see RiteRunState.respite_hp_stacks).
RESPITE_MAX_HP_INCREMENT = 0.30


def apply_respite_buffs(player, run_state: RiteRunState) -> None:
    """Applies both of Respite's cumulative buffs (Power's ATK/DEF
    multiplier, Respite's Max HP %) to player.cs — must be called fresh at
    the start of every wing attempt and every Arbiter phase, since
    reset_combat_state()/reset_combat_bonus() both zero these back out.
    No-op for whichever buff hasn't been picked yet."""
    if run_state.power_stacks > 0:
        power_mult = 1.0 + POWER_ATK_DEF_INCREMENT * run_state.power_stacks
        player.cs.atk_multiplier = power_mult
        player.cs.def_multiplier = power_mult
    if run_state.respite_hp_stacks > 0:
        player.cs.respite_hp_pct = (
            RESPITE_MAX_HP_INCREMENT * 100 * run_state.respite_hp_stacks
        )


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
        # round(), not int() — float multiplication (e.g. 3 * 0.30 * 100 ==
        # 89.99999999999999) truncates wrong under plain int().
        if self._omitted_option != "power":
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
            cur_hp_pct = round(
                self.run_state.respite_hp_stacks * RESPITE_MAX_HP_INCREMENT * 100
            )
            next_hp_pct = round(
                (self.run_state.respite_hp_stacks + 1) * RESPITE_MAX_HP_INCREMENT * 100
            )
            lines.append(
                f"💚 **Respite** — restore ~{int(RESPITE_HEAL_PCT * 100)}% HP + "
                f"{RESPITE_POTIONS} potions, and permanently "
                f"+{round(RESPITE_MAX_HP_INCREMENT * 100)}% Max HP "
                f"(currently +{cur_hp_pct}% → +{next_hp_pct}%)"
            )
        if self._omitted_option != "emergency":
            lines.append(
                f"✨ **Emergency** — full HP restore + {EMERGENCY_POTIONS} potions"
            )
        return discord.ui.Container(
            discord.ui.Section(
                "\n".join(lines),
                accessory=discord.ui.Thumbnail(ARBITER_THUMBNAIL, description="The Arbiter"),
            ),
            accent_color=discord.Color.gold(),
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
        # Keep player.cs in sync with the run's persistent stacks regardless
        # of which option was picked — it may be stale from before the last
        # fight's reset_combat_bonus() zeroed it, and total_max_hp reads
        # cs.respite_hp_pct directly for the hub's HP display.
        apply_respite_buffs(self.player, self.run_state)

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
        self.run_state.respite_hp_stacks += 1
        # Apply the new Max HP stack before computing the heal, so this
        # pick's own buff is reflected in the amount restored.
        apply_respite_buffs(self.player, self.run_state)
        heal = int(self.player.total_max_hp * RESPITE_HEAL_PCT)
        self.player.current_hp = min(
            self.player.total_max_hp, self.player.current_hp + heal
        )
        self.player.potions = min(MAX_POTIONS, self.player.potions + RESPITE_POTIONS)
        await self._apply_and_continue(interaction)

    async def _on_emergency(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        # Re-sync any already-accumulated Respite Max HP stacks first — cs
        # may still be stale/zeroed from the last fight's reset_combat_bonus(),
        # and a full heal should restore to the player's true current max.
        apply_respite_buffs(self.player, self.run_state)
        self.player.current_hp = self.player.total_max_hp
        self.player.potions = min(MAX_POTIONS, self.player.potions + EMERGENCY_POTIONS)
        await self._apply_and_continue(interaction)
