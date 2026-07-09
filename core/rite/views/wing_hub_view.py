"""Wing-selection hub for The Rite of Convergence.

Run structure: [Entry] -> Choose Wing -> Fight -> Respite -> Choose Wing ->
Fight -> Respite -> (x5 wings) -> [Arbiter Reveal] -> Final Boss (6 phases).

The Arbiter finale (6-phase boss) is not built yet (Milestone 5) — clearing
all 5 wings currently shows a placeholder instead of the real reveal. Writs
and Devotion Points (Milestone 4) are fully wired: see core/rite/data.py for
the writ table and core/rite/views/writ_select_view.py for the pre-run picker.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.combat.turns import engine
from core.combat.turns import jewel_engine as _je
from core.combat.views.views import CombatView
from core.images import (
    MONSTER_APHRODITE,
    MONSTER_EVELYNN,
    MONSTER_GEMINI,
    MONSTER_LUCIFER,
    MONSTER_NEET,
)
from core.models import Monster, Player
from core.rite import mobgen
from core.rite.data import WRITS, compute_devotion_points
from core.rite.run_state import RiteRunState
from core.rite.views.respite_view import POWER_ATK_DEF_MULT, RespiteView

# (key, display name, subtitle, generator fn, thumbnail)
_WINGS = [
    (
        "aphrodite",
        "Aphrodite Reborn",
        "Defensive Test — Unbreakable",
        mobgen.generate_wing_aphrodite,
        MONSTER_APHRODITE,
    ),
    (
        "lucifer",
        "Lucifer Reborn",
        "Offensive Test — Judgment",
        mobgen.generate_wing_lucifer,
        MONSTER_LUCIFER,
    ),
    (
        "gemini",
        "Castor & Pollux Reborn",
        "Sustain Test — True Reckoning",
        mobgen.generate_wing_gemini,
        MONSTER_GEMINI,
    ),
    (
        "neet",
        "NEET Reborn",
        "Void Drain",
        mobgen.generate_wing_neet,
        MONSTER_NEET,
    ),
    (
        "evelynn",
        "Evelynn Reborn",
        "All Modifiers — Nightmarish",
        mobgen.generate_wing_evelynn,
        MONSTER_EVELYNN,
    ),
]
_WING_BY_KEY = {w[0]: w for w in _WINGS}


class RiteEndRow(discord.ui.ActionRow["RiteEndView"]):
    @discord.ui.button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
    async def close(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.view.bot.state_manager.clear_active(self.view.user_id)
        self.view.stop()


class RiteEndView(BaseLayoutView):
    """Terminal screen: run failed (0 attempts left), or the 5-wing reveal
    placeholder pending the real Arbiter finale (Milestone 5)."""

    def __init__(self, bot, user_id: str, server_id: str, embed: discord.Embed):
        super().__init__(bot, user_id, server_id)
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(RiteEndRow())


async def _build_wing_combat_view(
    bot, user_id: str, server_id: str, player: Player, run_state: RiteRunState,
    wing_key: str, rite_callback,
) -> CombatView:
    """Generates a fresh encounter for `wing_key` and wraps it in a CombatView.
    Shared by the initial wing-select launch and death retries of the same wing."""
    _key, name, _subtitle, generate_fn, _thumb = _WING_BY_KEY[wing_key]
    writs = run_state.writs

    # Wing hub reuses the same Player object across fights (same reason Uber
    # lobbies do — see start_uber() precedent), so leftover combat stacks/
    # buffs from a previous encounter must be cleared first.
    player.reset_combat_state()

    # Respite's "Power" choice applies for every attempt at the CURRENT wing
    # (including retries after death), and is only cleared once that wing is
    # actually cleared — see the victory branch of the end-state callback.
    if run_state.pending_power_buff:
        player.cs.atk_multiplier = POWER_ATK_DEF_MULT
        player.cs.def_multiplier = POWER_ATK_DEF_MULT

    monster = Monster(
        name="", level=0, hp=0, max_hp=0, xp=0, attack=0, defence=0,
        modifiers=[], image="", flavor="",
    )

    # Writs that change a wing's own generation logic (not just a stat overlay)
    # are passed as generator kwargs; the rest are layered on afterward below.
    if wing_key == "gemini":
        pct = 0.90 if "fracture_of_balance" in writs else 0.80
        monster = generate_fn(player, monster, true_reckoning_pct=pct)
    elif wing_key == "neet":
        rate = 0.03 if "hungering_void" in writs else 0.015
        monster = generate_fn(player, monster, void_drain_rate=rate)
    elif wing_key == "evelynn":
        monster = generate_fn(player, monster, delirious="abyssal_embrace" in writs)
    else:
        monster = generate_fn(player, monster)

    if wing_key == "aphrodite" and "unyielding_guardian" in writs:
        monster.difficulty_dr += 0.30
    if wing_key == "lucifer" and "wrathful_reckoner" in writs:
        monster.bonus_attack_pct += 0.30
        monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
    if "trials_fury" in writs:
        monster.bonus_attack_pct += 1.0
        monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))

    player.combat_ward = player.get_combat_ward_value()
    engine.apply_stat_effects(player, monster)
    start_logs = engine.apply_combat_start_passives(player, monster)

    user_row = await bot.database.users.get(user_id, server_id)
    return CombatView(
        bot,
        user_id,
        server_id,
        player,
        monster,
        start_logs,
        combat_phases=None,
        rite_callback=rite_callback,
        disable_potions="trials_drought" in writs,
        title_override=f"🕯️ RITE OF CONVERGENCE — {name.upper()}",
        player_avatar_url=user_row["appearance"] if user_row else None,
    )


class WingHubView(BaseLayoutView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        run_state: RiteRunState,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.run_state = run_state
        self._processing = False
        self._sync_items()

    def _build_container(self) -> discord.ui.Container:
        def _wing_section(key, name, subtitle, thumb_url) -> discord.ui.Section:
            status = "✅ Cleared" if key in self.run_state.wings_cleared else "⚔️ Not yet cleared"
            text = f"### {name}\n{subtitle}\n**Status:** {status}"
            return discord.ui.Section(
                text, accessory=discord.ui.Thumbnail(thumb_url, description=name)
            )

        sep = lambda: discord.ui.Separator(spacing=discord.SeparatorSpacing.small)

        hp_pct = int(100 * self.player.current_hp / max(1, self.player.total_max_hp))
        writs_line = ""
        if self.run_state.writs:
            names = ", ".join(WRITS[k].name for k in self.run_state.writs)
            writs_line = f"\n📜 **Active Writs:** {names}"
        children: list = [
            discord.ui.TextDisplay(
                "## 🕯️ The Rite of Convergence — Wing Select\n"
                f"**Attempts remaining:** {self.run_state.attempts_remaining}  •  "
                f"**Wings cleared:** {len(self.run_state.wings_cleared)}/5\n"
                f"**HP:** {self.player.current_hp:,}/{self.player.total_max_hp:,} ({hp_pct}%)  •  "
                f"**Potions:** {self.player.potions}"
                + ("\n⚔️ **Power** is active for your next fight." if self.run_state.pending_power_buff else "")
                + writs_line
            ),
            sep(),
        ]
        for key, name, subtitle, _fn, thumb in _WINGS:
            children.append(_wing_section(key, name, subtitle, thumb))
        return discord.ui.Container(*children, accent_color=discord.Color.dark_purple())

    def _build_rows(self) -> list[discord.ui.ActionRow]:
        row0 = discord.ui.ActionRow()
        row1 = discord.ui.ActionRow()
        row2 = discord.ui.ActionRow()

        for i, (key, name, _subtitle, _fn, _thumb) in enumerate(_WINGS):
            cleared = key in self.run_state.wings_cleared
            btn = ui.Button(
                label=name.split(" Reborn")[0].split(" &")[0],
                style=ButtonStyle.success if cleared else ButtonStyle.danger,
                disabled=cleared,
                custom_id=f"rite_wing_{key}",
            )
            btn.callback = self._make_start_callback(key)
            (row0 if i < 3 else row1).add_item(btn)

        btn_close = ui.Button(label="Close (Save & Exit)", style=ButtonStyle.secondary, emoji="✖️")
        btn_close.callback = self.close_view
        row2.add_item(btn_close)

        return [row0, row1, row2]

    def _sync_items(self):
        self.clear_items()
        self.add_item(self._build_container())
        for row in self._build_rows():
            self.add_item(row)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def _make_start_callback(self, wing_key: str):
        async def _start(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            # Room-entry snapshot: on death-with-attempts-remaining, HP resets
            # to this value (potions do not — any spent during a failed
            # attempt stay spent, per RAID-DESIGN.md).
            self.run_state.current_wing = wing_key
            self.run_state.room_entry_hp = self.player.current_hp
            self.run_state.room_entry_potions = self.player.potions
            await self.bot.database.rite.upsert_run(
                self.user_id, self.server_id, self.run_state.to_snapshot()
            )

            view = await _build_wing_combat_view(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                self.run_state,
                wing_key,
                self._make_end_state_callback(wing_key),
            )

            self.bot.state_manager.set_active(self.user_id, "rite")
            await interaction.edit_original_response(embed=None, view=view)
            view.message = await interaction.original_response()
            self.stop()

        return _start

    def _make_end_state_callback(self, wing_key: str):
        async def _end_state(view: CombatView, message, interaction: Interaction):
            run_state = self.run_state
            won = view.monster.hp <= 0 and view.player.current_hp > 0

            # Turn counter spans every wing fight and (Milestone 5) Arbiter
            # phase, excluding respite screens — monster.combat_round is
            # incremented once per monster turn, i.e. once per round of this
            # fight, so it's an accurate per-fight turn count to accumulate.
            run_state.total_turns += view.monster.combat_round

            await view.bot.database.users.update_from_player_object(view.player)
            await _je.save_jewel_state(view.bot, view.user_id, view.player)

            if won:
                run_state.wings_cleared.add(wing_key)
                run_state.current_wing = None
                run_state.pending_power_buff = False
                await view.bot.database.rite.upsert_run(
                    view.user_id, view.server_id, run_state.to_snapshot()
                )

                if run_state.is_run_complete:
                    view.bot.state_manager.clear_active(view.user_id)
                    dp = compute_devotion_points(run_state.writs, run_state.total_turns)
                    embed = discord.Embed(
                        title="✨ All 5 Wings Cleared",
                        description=(
                            "The Arbiter's essences begin to converge...\n\n"
                            f"**Total turns:** {run_state.total_turns}  •  "
                            f"**Devotion Points:** {dp}\n\n"
                            "*(Milestone 4 scaffolding — the real Reveal narrative "
                            "and the 6-phase Arbiter finale land in Milestone 5, "
                            "including the actual DP-scaled loot payout. Your run "
                            "is saved; close and resume with `/rite` once it's ready.)*"
                        ),
                        color=discord.Color.gold(),
                    )
                    end_view = RiteEndView(view.bot, view.user_id, view.server_id, embed)
                    await message.edit(view=end_view)
                    end_view.message = message
                    view.stop()
                    return

                respite = RespiteView(
                    view.bot, view.user_id, view.server_id, view.player, run_state
                )
                await message.edit(view=respite)
                respite.message = message
                view.stop()
                return

            # --- Defeat ---
            run_state.attempts_remaining -= 1

            if run_state.attempts_remaining > 0:
                # Retry the SAME wing: HP resets to the room-entry snapshot,
                # potions do not (any used this attempt stay spent).
                view.player.current_hp = run_state.room_entry_hp
                await view.bot.database.users.update_from_player_object(view.player)
                await view.bot.database.rite.upsert_run(
                    view.user_id, view.server_id, run_state.to_snapshot()
                )

                retry_view = await _build_wing_combat_view(
                    view.bot,
                    view.user_id,
                    view.server_id,
                    view.player,
                    run_state,
                    wing_key,
                    self._make_end_state_callback(wing_key),
                )
                await message.edit(embed=None, view=retry_view)
                retry_view.message = message
                view.stop()
                return

            # --- Run failed: no attempts remaining ---
            view.bot.state_manager.clear_active(view.user_id)
            await view.bot.database.rite.delete_run(view.user_id, view.server_id)
            embed = discord.Embed(
                title=f"💀 The Rite Ends — Defeated by {view.monster.name}",
                description=(
                    "No attempts remain. The Rite of Convergence has ended; "
                    "your keys are spent."
                ),
                color=discord.Color.red(),
            )
            end_view = RiteEndView(view.bot, view.user_id, view.server_id, embed)
            await message.edit(view=end_view)
            end_view.message = message
            view.stop()

        return _end_state
