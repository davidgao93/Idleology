"""Wing-selection hub for The Rite of Convergence.

Run structure: [Entry] -> Choose Wing -> Fight -> Respite -> Choose Wing ->
Fight -> Respite -> (x5 wings) -> [Arbiter Reveal] -> Final Boss (6 phases).

Clearing the 5th wing hands off to core/rite/views/reveal_view.py, which
transitions straight into the Arbiter's 6-phase finale
(core/rite/views/arbiter_view.py). See core/rite/data.py for the writ table
and core/rite/views/writ_select_view.py for the pre-run picker.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.combat.turns import engine
from core.combat.turns import jewel_engine as _je
from core.combat.views.views import CombatView
from core.emojis import (
    RITE_KEY_CELESTIAL,
    RITE_KEY_CORRUPT,
    RITE_KEY_GEMINI,
    RITE_KEY_INFERNAL,
    RITE_KEY_VOID,
)
from core.images import (
    MONSTER_APHRODITE_REBORN,
    MONSTER_EVELYNN_REBORN,
    MONSTER_GEMINI_REBORN,
    MONSTER_LUCIFER_REBORN,
    MONSTER_NEET_REBORN,
)
from core.models import Monster, Player
from core.rite import mobgen
from core.rite.data import WRITS
from core.rite.run_state import RiteRunState
from core.rite.views.respite_view import (
    POWER_ATK_DEF_INCREMENT,
    RespiteView,
    apply_power_stacks,
)

# (key, display name, generator fn, thumbnail, entry-key emoji) — mechanic
# descriptions are computed dynamically by _wing_mechanic_text() below since
# a couple depend on active writs.
_WINGS = [
    (
        "aphrodite",
        "Aphrodite Reborn",
        mobgen.generate_wing_aphrodite,
        MONSTER_APHRODITE_REBORN,
        RITE_KEY_CELESTIAL,
    ),
    (
        "lucifer",
        "Lucifer Reborn",
        mobgen.generate_wing_lucifer,
        MONSTER_LUCIFER_REBORN,
        RITE_KEY_INFERNAL,
    ),
    (
        "gemini",
        "Castor & Pollux Reborn",
        mobgen.generate_wing_gemini,
        MONSTER_GEMINI_REBORN,
        RITE_KEY_GEMINI,
    ),
    (
        "neet",
        "NEET Reborn",
        mobgen.generate_wing_neet,
        MONSTER_NEET_REBORN,
        RITE_KEY_VOID,
    ),
    (
        "evelynn",
        "Evelynn Reborn",
        mobgen.generate_wing_evelynn,
        MONSTER_EVELYNN_REBORN,
        RITE_KEY_CORRUPT,
    ),
]
_WING_BY_KEY = {w[0]: w for w in _WINGS}

# Short button labels, matching each wing's entry-key theme — the portrait
# order (and matching emoji) already makes clear which is which.
_WING_SHORT_LABELS = {
    "aphrodite": "Dreams",
    "lucifer": "Memory",
    "gemini": "Judgment",
    "neet": "Thoughts",
    "evelynn": "Nightmares",
}


def _wing_mechanic_text(key: str, writs: list[str]) -> str:
    """Describes each wing's signature mechanic (writ-adjusted where the
    writ actually changes the number in play — see RAID-DESIGN.md)."""
    if key == "aphrodite":
        return (
            "Gains 1 **Unbreakable** charge every turn — at 150 charges, "
            "deals your full HP + Ward as true damage."
        )
    if key == "lucifer":
        return (
            "Gains 1 **Judgment** charge every hit you take — at 50 charges, "
            "deals 99% of your full HP + Ward as true damage."
        )
    if key == "gemini":
        pct = 90 if "fracture_of_balance" in writs else 80
        return (
            f"**True Reckoning** — {pct}% of every hit is unconditional true "
            "damage, bypassing PDR, FDR, and Ward entirely."
        )
    if key == "neet":
        rate = 3.0 if "hungering_void" in writs else 1.5
        return (
            f"**Void Drain** — drains {rate:g}% of your ATK/DEF every round, "
            "compounding for the whole fight."
        )
    if key == "evelynn":
        return "Every combat modifier active at once, scaled to Nightmarish difficulty."
    return ""


class RiteEndRow(discord.ui.ActionRow["RiteEndView"]):
    @discord.ui.button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
    async def close(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.view.bot.state_manager.clear_active(self.view.user_id)
        self.view.stop()


class RiteEndView(BaseLayoutView):
    """Terminal screen for the run: victory, or failure with 0 attempts
    remaining (from a wing defeat, an Arbiter defeat, or fleeing)."""

    def __init__(self, bot, user_id: str, server_id: str, embed: discord.Embed):
        super().__init__(bot, user_id, server_id)
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(RiteEndRow())


def build_rite_defeat_embed(
    player: Player, monster: Monster, killing_blow: int, run_state: RiteRunState, *, title: str
) -> discord.Embed:
    """Defeat acknowledgment shown whenever the player dies mid-Rite (a wing
    or an Arbiter phase) — mirrors the game's standard defeat screen
    (killing blow, damage dealt) instead of an instant cut back to the lobby."""
    from core.character.prestige_display import format_prestige_name

    prestige_name = format_prestige_name(
        player.name, player.prestige_title, player.prestige_emblem
    )
    total_damage_dealt = max(0, monster.max_hp - monster.hp)
    killing_blow_str = (
        f" (**{killing_blow:,}** killing blow)" if killing_blow > 0 else ""
    )
    lives = "🧠" * run_state.attempts_remaining + "⚪" * (
        run_state.max_attempts - run_state.attempts_remaining
    )
    embed = discord.Embed(
        title=title,
        description=(
            f"The **{monster.name}** deals a fatal blow{killing_blow_str}!\n"
            f"{prestige_name} dealt **{total_damage_dealt:,}** damage before falling — "
            f"it walks away with **{monster.hp:,}** health remaining.\n\n"
            f"**Lives:** {lives}"
        ),
        color=discord.Color.red(),
    )
    if monster.image:
        embed.set_thumbnail(url=monster.image)
    return embed


class RiteDefeatRow(discord.ui.ActionRow["RiteDefeatView"]):
    @discord.ui.button(label="Return to Lobby", style=ButtonStyle.secondary, emoji="↩️")
    async def return_to_lobby(self, interaction: Interaction, button: ui.Button):
        await self.view._on_return(interaction)


class RiteDefeatView(BaseLayoutView):
    """Static defeat acknowledgment for a death mid-Rite (wing or Arbiter
    phase) — shown in place of the old auto-timed frozen-frame transition, so
    a death is never an instant cut straight back to the lobby. HP is only
    restored to the room-entry snapshot once the player explicitly clicks
    Return to Lobby, not automatically."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        run_state: RiteRunState,
        embed: discord.Embed,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.run_state = run_state
        self._processing = False
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(RiteDefeatRow())

    async def _on_return(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        self.player.current_hp = self.run_state.room_entry_hp
        await self.bot.database.users.update_from_player_object(self.player)
        await self.bot.database.rite.upsert_run(
            self.user_id, self.server_id, self.run_state.to_snapshot()
        )
        hub = WingHubView(
            self.bot, self.user_id, self.server_id, self.player, self.run_state
        )
        self.bot.state_manager.set_active(self.user_id, "rite")
        await interaction.edit_original_response(embed=None, view=hub)
        hub.message = await interaction.original_response()
        self.stop()


class RiteExitConfirmRow(discord.ui.ActionRow["RiteExitConfirmView"]):
    @discord.ui.button(label="Yes, Abandon the Rite", style=ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        await self.view._on_confirm(interaction)

    @discord.ui.button(label="No, Keep Fighting", style=ButtonStyle.secondary, emoji="↩️")
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await self.view._on_cancel(interaction)


class RiteExitConfirmView(BaseLayoutView):
    """Confirmation gate before abandoning an active Rite run. The Rite has
    no save/resume — per RAID-DESIGN.md, leaving mid-run forfeits all
    progress (wings cleared, attempts spent, and the 5 consumed keys)."""

    def __init__(self, bot, hub: "WingHubView"):
        super().__init__(bot, parent=hub)
        self.hub = hub
        lives = "🧠" * hub.run_state.attempts_remaining + "⚪" * (
            hub.run_state.max_attempts - hub.run_state.attempts_remaining
        )
        embed = discord.Embed(
            title="⚠️ Abandon the Rite of Convergence?",
            description=(
                "Leaving now **forfeits this run entirely** — there is no way "
                "to save and resume. Wings cleared, attempts spent, and your "
                "5 consumed Rite keys are gone for good.\n\n"
                f"**Wings cleared:** {len(hub.run_state.wings_cleared)}/5  •  "
                f"**Lives:** {lives}"
            ),
            color=discord.Color.red(),
        )
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(RiteExitConfirmRow())

    async def _on_confirm(self, interaction: Interaction):
        await interaction.response.defer()
        await self.bot.database.rite.delete_run(self.hub.user_id, self.hub.server_id)
        self.bot.state_manager.clear_active(self.hub.user_id)
        await interaction.delete_original_response()
        self.hub.stop()
        self.stop()

    async def _on_cancel(self, interaction: Interaction):
        self.hub._sync_items()
        await interaction.response.edit_message(view=self.hub)
        self.stop()


async def _build_wing_combat_view(
    bot,
    user_id: str,
    server_id: str,
    player: Player,
    run_state: RiteRunState,
    wing_key: str,
    rite_callback,
) -> CombatView:
    """Generates a fresh encounter for `wing_key` and wraps it in a CombatView.
    Shared by the initial wing-select launch and death retries of the same wing."""
    _key, name, generate_fn, _thumb, _emoji = _WING_BY_KEY[wing_key]
    writs = run_state.writs

    # Wing hub reuses the same Player object across fights (same reason Uber
    # lobbies do — see start_uber() precedent), so leftover combat stacks/
    # buffs from a previous encounter must be cleared first.
    player.reset_combat_state()

    # Respite's "Power" choice is additive and cumulative for the rest of
    # the run — every stack picked adds another +30% ATK/DEF, applied fresh
    # at the start of every wing attempt (never reset on clear or defeat).
    apply_power_stacks(player, run_state)

    monster = Monster(
        name="",
        level=0,
        hp=0,
        max_hp=0,
        xp=0,
        attack=0,
        defence=0,
        modifiers=[],
        image="",
        flavor="",
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
        def _wing_section(key, name, thumb_url) -> discord.ui.Section:
            status = (
                "✅ Cleared"
                if key in self.run_state.wings_cleared
                else "⚔️ Not yet cleared"
            )
            mechanic = _wing_mechanic_text(key, self.run_state.writs)
            text = f"### {name}\n{mechanic}\n**Status:** {status}"
            return discord.ui.Section(
                text, accessory=discord.ui.Thumbnail(thumb_url, description=name)
            )

        sep = lambda: discord.ui.Separator(spacing=discord.SeparatorSpacing.small)

        hp_pct = int(100 * self.player.current_hp / max(1, self.player.total_max_hp))
        writs_line = ""
        if self.run_state.writs:
            names = ", ".join(WRITS[k].name for k in self.run_state.writs)
            writs_line = f"\n📜 **Active Writs:** {names}"
        lives = "🧠" * self.run_state.attempts_remaining + "⚪" * (
            self.run_state.max_attempts - self.run_state.attempts_remaining
        )
        children: list = [
            discord.ui.TextDisplay(
                "## 🕯️ The Rite of Convergence — Wing Select\n"
                f"**Lives:** {lives}  •  "
                f"**Wings cleared:** {len(self.run_state.wings_cleared)}/5\n"
                f"**HP:** {self.player.current_hp:,}/{self.player.total_max_hp:,} ({hp_pct}%)  •  "
                f"**Potions:** {self.player.potions}"
                + (
                    # round(), not int() — float multiplication (e.g.
                    # 3 * 0.30 * 100 == 89.99999999999999) truncates wrong
                    # under plain int().
                    f"\n⚔️ **Power:** +{round(self.run_state.power_stacks * POWER_ATK_DEF_INCREMENT * 100)}% "
                    f"ATK/DEF (stacked {self.run_state.power_stacks}×)"
                    if self.run_state.power_stacks > 0
                    else ""
                )
                + writs_line
                + (
                    "\n\n🕯️ **All five wings have fallen. The Arbiter awaits.**"
                    if self.run_state.is_run_complete
                    else ""
                )
            ),
            sep(),
        ]
        for key, name, _fn, thumb, _emoji in _WINGS:
            children.append(_wing_section(key, name, thumb))
        return discord.ui.Container(*children, accent_color=discord.Color.dark_purple())

    def _build_rows(self) -> list[discord.ui.ActionRow]:
        row0 = discord.ui.ActionRow()
        row1 = discord.ui.ActionRow()

        if self.run_state.is_run_complete:
            btn_arbiter = ui.Button(
                label="Challenge the Arbiter",
                style=ButtonStyle.danger,
                emoji="🕯️",
            )
            btn_arbiter.callback = self._on_challenge_arbiter
            row0.add_item(btn_arbiter)
        else:
            for key, _name, _fn, _thumb, emoji in _WINGS:
                cleared = key in self.run_state.wings_cleared
                btn = ui.Button(
                    label=_WING_SHORT_LABELS[key],
                    style=ButtonStyle.success if cleared else ButtonStyle.secondary,
                    emoji=emoji,
                    disabled=cleared,
                    custom_id=f"rite_wing_{key}",
                )
                btn.callback = self._make_start_callback(key)
                row0.add_item(btn)

        btn_close = ui.Button(
            label="Exit Raid", style=ButtonStyle.secondary, emoji="✖️"
        )
        btn_close.callback = self.close_view
        row1.add_item(btn_close)

        return [row0, row1]

    def _sync_items(self):
        self.clear_items()
        self.add_item(self._build_container())
        for row in self._build_rows():
            self.add_item(row)

    async def close_view(self, interaction: Interaction):
        confirm = RiteExitConfirmView(self.bot, self)
        await interaction.response.edit_message(view=confirm)
        confirm.message = interaction.message

    async def _on_challenge_arbiter(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # Lazy import: arbiter_view imports this module for RiteEndView/
        # WingHubView, so a module-level import here would be circular.
        from core.rite.views.arbiter_view import enter_arbiter_fight

        view = await enter_arbiter_fight(
            self.bot, self.user_id, self.server_id, self.player, self.run_state
        )
        self.bot.state_manager.set_active(self.user_id, "rite")
        await interaction.edit_original_response(embed=None, view=view)
        view.message = await interaction.original_response()
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
            self.run_state.room_entry_hp = self.player.current_hp
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
            fled = getattr(view, "fled", False)
            won = not fled and view.monster.hp <= 0 and view.player.current_hp > 0

            # Turn counter spans every wing fight and every Arbiter phase,
            # excluding respite/reveal screens — monster.combat_round is
            # incremented once per monster turn, i.e. once per round of this
            # fight, so it's an accurate per-fight turn count to accumulate.
            run_state.total_turns += view.monster.combat_round

            await view.bot.database.users.update_from_player_object(view.player)
            await _je.save_jewel_state(view.bot, view.user_id, view.player)

            if won:
                run_state.wings_cleared.add(wing_key)
                await view.bot.database.rite.upsert_run(
                    view.user_id, view.server_id, run_state.to_snapshot()
                )

                if run_state.is_run_complete:
                    # Lazy import: arbiter_view (via reveal_view) imports this
                    # module for RiteEndView, so a module-level import here
                    # would be circular.
                    from core.rite.views.reveal_view import ArbiterMaterializesView

                    materialize = ArbiterMaterializesView(
                        view.bot,
                        view.user_id,
                        view.server_id,
                        view.player,
                        run_state,
                        view.monster.name,
                    )
                    await message.edit(embed=None, view=materialize)
                    materialize.message = message
                    view.stop()
                    return

                respite = RespiteView(
                    view.bot, view.user_id, view.server_id, view.player, run_state
                )
                await message.edit(view=respite)
                respite.message = message
                view.stop()
                return

            # --- Not won: fled or died. Both cost an attempt; neither
            # retries nor clears this wing — the player picks their next
            # move freely, including tackling a different wing first to
            # bank a Respite buff before coming back. ---
            run_state.attempts_remaining -= 1

            # Neutralize the old view so an in-flight auto-battle loop (if
            # Auto was running) can't keep processing turns against this
            # now-discarded CombatView.
            view.neutralize()

            if fled:
                if run_state.attempts_remaining > 0:
                    await view.bot.database.rite.upsert_run(
                        view.user_id, view.server_id, run_state.to_snapshot()
                    )
                    hub = WingHubView(
                        view.bot, view.user_id, view.server_id, view.player, run_state
                    )
                    view.bot.state_manager.set_active(view.user_id, "rite")
                    await message.edit(embed=None, view=hub)
                    hub.message = message
                    view.stop()
                    return

                view.bot.state_manager.clear_active(view.user_id)
                await view.bot.database.rite.delete_run(view.user_id, view.server_id)
                embed = discord.Embed(
                    title="🏃 The Rite Ends — You Fled",
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
                return

            # --- Died: a static defeat acknowledgment (killing blow, damage
            # dealt, lives remaining) instead of an instant cut to the lobby.
            # HP only restores to the room-entry snapshot once the player
            # clicks Return to Lobby — see RiteDefeatView. ---
            can_retry = run_state.attempts_remaining > 0
            defeat_title = (
                "💀 You Have Fallen..."
                if can_retry
                else f"💀 The Rite Ends — Defeated by {view.monster.name}"
            )
            embed = build_rite_defeat_embed(
                view.player, view.monster, view.killing_blow, run_state, title=defeat_title
            )

            if can_retry:
                await view.bot.database.rite.upsert_run(
                    view.user_id, view.server_id, run_state.to_snapshot()
                )
                defeat_view = RiteDefeatView(
                    view.bot, view.user_id, view.server_id, view.player, run_state, embed
                )
                await message.edit(embed=None, view=defeat_view)
                defeat_view.message = message
                view.stop()
                return

            view.bot.state_manager.clear_active(view.user_id)
            await view.bot.database.rite.delete_run(view.user_id, view.server_id)
            embed.description += (
                "\n\nNo attempts remain. The Rite of Convergence has ended; "
                "your keys are spent."
            )
            end_view = RiteEndView(view.bot, view.user_id, view.server_id, embed)
            await message.edit(view=end_view)
            end_view.message = message
            view.stop()

        return _end_state
