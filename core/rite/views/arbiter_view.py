"""The Arbiter — 7-phase finale. Builds Phase 1's CombatView and drives every
phase transition, final victory (loot payout), and defeat/retry through a
single rite_callback, since CombatView's own phase-transition machinery
generates monsters via the standard generate_boss() — wrong shape entirely
for the Arbiter's fixed-name/fixed-tier/equal-HP phases.

Phases 1-6 are the "Last Edict" arc (Amalgam limbs converging, then the
masked Arbiter reveal — see ArbiterFinalFormView). Phase 7 ("The Arbiter,
Unbound") is a second, later reveal once Phase 6 falls — same stats/
modifiers as Phase 6, only Max HP doubles — gated behind ArbiterTransformView's
dialogue + a timed GIF transition. See RAID-DESIGN.md for the narrative.
"""

import asyncio

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.combat.turns import engine
from core.combat.turns import jewel_engine as _je
from core.combat.turns.boundary import reset_for_phase_transition
from core.combat.views.views import CombatView
from core.emojis import ARTEFACT_SLOT, INNER_SANC
from core.hall_of_firsts import triggers as hof_triggers
from core.images import (
    ARBITER_PHASE_FINAL,
    ARBITER_PORTRAIT,
    ARBITER_TRANSFORM_GIF,
    RITE_CHEST_ARTEFACT,
    RITE_CHEST_NORMAL,
)
from core.npc_voices import get_quip
from core.rite import mobgen
from core.rite.data import compute_devotion_points
from core.rite.loot import grant_run_completion_rewards
from core.rite.run_state import RiteRunState
from core.rite.views.respite_view import apply_respite_buffs

# Phases 1-5 (index 0-4) are the converged, escalating "Amalgam"; the true
# Arbiter (index 5, "Arbiter, the Last Edict") only reveals itself once the
# Amalgam falls — see the phase 4->5 transition in make_arbiter_end_state_callback.
_FINAL_PHASE_INDEX = 5

# Inner Sanctum Points granted on a full Rite of Convergence clear (every
# clear, not just the first).
RITE_CLEAR_ISP_REWARD = 15

# Phase 7 (index 6) — "The Arbiter, Unbound". Reached only after Phase 6
# falls, via ArbiterTransformView's dialogue + GIF transition (see the
# upcoming_phase_index == _TRUE_FINAL_PHASE_INDEX branch below). This is the
# actual run-ending phase now — killing it is what triggers loot/victory.
_TRUE_FINAL_PHASE_INDEX = 6

# Flavor for phase-to-phase transitions, keyed by the phase index being
# entered (1-4; index 5 gets its own bespoke "Mask Slips" reveal). Each
# phase is a different LIMB of one converging being, not a boss that dies
# and rises again — the generic "rises from the ashes" line doesn't fit.
_AMALGAM_TRANSITION_TEXT: dict[int, str] = {
    1: (
        "The Left Wing crumbles to ash — but the mass beneath it convulses. "
        "A second wing tears free, hellfire licking along its length."
    ),
    2: (
        "Both wings lie shredded. From the writhing core, an arm wrenches "
        "loose, promising a balance that will not favor you."
    ),
    3: (
        "The first arm falls still. A second unfurls from the churning "
        "flesh, trailing tendrils of absolute nothing."
    ),
    4: (
        "All four limbs lie broken. What remains draws inward, folding "
        "into a single writhing mass of flesh, dream, and nightmare."
    ),
}


def _apply_arbiter_writ_overlays(monster, writs: list[str]) -> None:
    if "trials_fury" in writs:
        monster.bonus_attack_pct += 1.0
        monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))


def _arbiter_phase_title(phase_index: int, monster_name: str) -> str:
    label = "THE ARBITER" if phase_index >= _FINAL_PHASE_INDEX else "THE AMALGAM"
    return f"🕯️ {label} — PHASE {phase_index + 1}: {monster_name.upper()}"


async def build_arbiter_combat_view(
    bot, user_id: str, server_id: str, player, run_state: RiteRunState, rite_callback
) -> CombatView:
    """Builds Phase 1's CombatView. Shared by the initial reveal transition
    and death retries, which always restart the whole Arbiter from Phase 1."""
    player.reset_combat_state()
    apply_respite_buffs(player, run_state)

    phases = mobgen.get_arbiter_phases(player)
    monster = mobgen.generate_arbiter_phase(player, phases[0], 0)
    _apply_arbiter_writ_overlays(monster, run_state.writs)

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
        combat_phases=phases,
        rite_callback=rite_callback,
        disable_potions="trials_drought" in run_state.writs,
        title_override=_arbiter_phase_title(0, monster.name),
        player_avatar_url=user_row["appearance"] if user_row else None,
    )


async def _enter_final_phase(
    bot,
    user_id: str,
    server_id: str,
    player,
    run_state: RiteRunState,
    rite_callback,
) -> CombatView:
    """Builds Phase 6's (the true Arbiter's) CombatView fresh, once the
    player explicitly confirms via ArbiterFinalFormView's "Face the
    Arbiter" button — Phase 6 never auto-starts the instant the Amalgam
    falls. Ward, Arbiter's Aid buffs, and Start-of-Combat passive bonuses
    (Infernal/Void/partner/Hematurgy/Soul Stone) all carry over from Phase 5
    since the fight is still continuous (no respite between phases) and
    player.cs is never reset mid-fight — apply_respite_buffs() already set
    atk/def_multiplier back at Phase 1 start and doesn't need reapplying here."""
    reset_for_phase_transition(player)

    phases = mobgen.get_arbiter_phases(player)
    monster = mobgen.generate_arbiter_phase(
        player, phases[_FINAL_PHASE_INDEX], _FINAL_PHASE_INDEX
    )
    _apply_arbiter_writ_overlays(monster, run_state.writs)
    monster.is_boss = True

    engine.apply_stat_effects(player, monster)
    start_logs = engine.apply_combat_start_passives(player, monster)

    user_row = await bot.database.users.get(user_id, server_id)
    view = CombatView(
        bot,
        user_id,
        server_id,
        player,
        monster,
        start_logs,
        combat_phases=phases,
        rite_callback=rite_callback,
        disable_potions="trials_drought" in run_state.writs,
        title_override=_arbiter_phase_title(_FINAL_PHASE_INDEX, monster.name),
        player_avatar_url=user_row["appearance"] if user_row else None,
    )
    view.current_phase_index = _FINAL_PHASE_INDEX
    return view


class ArbiterFinalFormRow(discord.ui.ActionRow["ArbiterFinalFormView"]):
    @discord.ui.button(label="Face the Arbiter", style=ButtonStyle.danger, emoji="🕯️")
    async def confront(self, interaction: Interaction, button: ui.Button):
        await self.view._on_confirm(interaction)


class ArbiterFinalFormView(BaseLayoutView):
    """Shown once the Amalgam (phase 5) falls — the mask-slip reveal, gated
    behind an explicit button rather than an auto-timed transition into
    Phase 6."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player,
        run_state: RiteRunState,
        embed: discord.Embed,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.run_state = run_state
        self._processing = False
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(ArbiterFinalFormRow())

    async def _on_confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        arbiter_callback = make_arbiter_end_state_callback(self.run_state)
        combat_view = await _enter_final_phase(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.run_state,
            arbiter_callback,
        )
        await interaction.edit_original_response(embed=None, view=combat_view)
        combat_view.message = await interaction.original_response()
        self.stop()


async def _enter_true_final_phase(
    bot,
    user_id: str,
    server_id: str,
    player,
    run_state: RiteRunState,
    rite_callback,
) -> CombatView:
    """Builds Phase 7's (the Arbiter's true, unbound form) CombatView fresh,
    once the player has clicked through ArbiterTransformView's dialogue and
    sat through the transformation GIF. Same continuous-fight carryover
    rules as _enter_final_phase (Phase 5 -> 6): ward, Arbiter's Aid buffs,
    and Start-of-Combat passive bonuses all persist — no reset_combat_state()."""
    reset_for_phase_transition(player)

    phases = mobgen.get_arbiter_phases(player)
    monster = mobgen.generate_arbiter_phase(
        player, phases[_TRUE_FINAL_PHASE_INDEX], _TRUE_FINAL_PHASE_INDEX
    )
    _apply_arbiter_writ_overlays(monster, run_state.writs)
    monster.is_boss = True

    engine.apply_stat_effects(player, monster)
    start_logs = engine.apply_combat_start_passives(player, monster)

    user_row = await bot.database.users.get(user_id, server_id)
    view = CombatView(
        bot,
        user_id,
        server_id,
        player,
        monster,
        start_logs,
        combat_phases=phases,
        rite_callback=rite_callback,
        disable_potions="trials_drought" in run_state.writs,
        title_override=_arbiter_phase_title(_TRUE_FINAL_PHASE_INDEX, monster.name),
        player_avatar_url=user_row["appearance"] if user_row else None,
    )
    view.current_phase_index = _TRUE_FINAL_PHASE_INDEX
    return view


class ArbiterTransformRow(discord.ui.ActionRow["ArbiterTransformView"]):
    @discord.ui.button(label="Proceed", style=ButtonStyle.danger, emoji="🕯️")
    async def confront(self, interaction: Interaction, button: ui.Button):
        await self.view._on_confirm(interaction)


class ArbiterTransformView(BaseLayoutView):
    """Shown once Phase 6 ("Arbiter, the Last Edict") falls — his final
    dialogue beat before shedding that form. Gated behind an explicit
    Proceed click, same as ArbiterFinalFormView; clicking it plays a timed
    GIF transition (ARBITER_TRANSFORM_GIF, no button — auto-advances) before
    Phase 7's CombatView appears."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player,
        run_state: RiteRunState,
        embed: discord.Embed,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.run_state = run_state
        self._processing = False
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(ArbiterTransformRow())

    async def _on_confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        gif_embed = discord.Embed(
            title="🕯️ The Arbiter, Unbound",
            color=discord.Color.dark_purple(),
        )
        gif_embed.set_image(url=ARBITER_TRANSFORM_GIF)
        gif_view = discord.ui.LayoutView()
        gif_view.add_item(combat_ui.embed_to_container(gif_embed))
        await interaction.edit_original_response(embed=None, view=gif_view)
        await asyncio.sleep(5.0)

        arbiter_callback = make_arbiter_end_state_callback(self.run_state)
        combat_view = await _enter_true_final_phase(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.run_state,
            arbiter_callback,
        )
        await interaction.edit_original_response(embed=None, view=combat_view)
        combat_view.message = await interaction.original_response()
        self.stop()


class RiteLootRevealRow(discord.ui.ActionRow["RiteLootRevealView"]):
    @discord.ui.button(label="Proceed", style=ButtonStyle.success, emoji="➡️")
    async def proceed(self, interaction: Interaction, button: ui.Button):
        if self.view._processing:
            await interaction.response.defer()
            return
        self.view._processing = True
        await self.view.on_proceed(interaction)


class RiteLootRevealView(BaseLayoutView):
    """Chest-style loot reveal shown right after the Arbiter's defeat beat,
    before the itemized rewards embed (_build_victory_embed / RiteEndView) —
    a visual beat for "you cleared the whole Rite" separate from the numbers.
    Picks RITE_CHEST_ARTEFACT or RITE_CHEST_NORMAL art depending on whether
    an artefact actually dropped. `on_proceed` builds and shows RiteEndView."""

    def __init__(
        self, bot, user_id: str, server_id: str, chest_image: str, on_proceed
    ):
        super().__init__(bot, user_id, server_id)
        self._processing = False
        self.on_proceed = on_proceed
        embed = discord.Embed(
            title="🏆 The Rite of Convergence is Complete",
            color=discord.Color.gold(),
        )
        embed.set_image(url=chest_image)
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(RiteLootRevealRow())


async def enter_arbiter_fight(
    bot, user_id: str, server_id: str, player, run_state: RiteRunState
) -> CombatView:
    """Snapshots room-entry state and builds Phase 1's CombatView. Shared by
    the first-time reveal confirm (reveal_view.ArbiterConfrontView) and by
    re-entry from the wing hub's "Challenge the Arbiter" button after a
    flee/death — both start a fresh Phase 1 attempt the same way."""
    run_state.room_entry_hp = player.current_hp
    await bot.database.rite.upsert_run(user_id, server_id, run_state.to_snapshot())

    arbiter_callback = make_arbiter_end_state_callback(run_state)
    return await build_arbiter_combat_view(
        bot, user_id, server_id, player, run_state, arbiter_callback
    )


def _build_victory_embed(
    run_state: RiteRunState, dp: int, rewards: dict, is_first_clear: bool = False
) -> discord.Embed:
    if rewards.get("artefact_name"):
        loot_line = (
            "As you approach the ruined husk, something catches your eye — "
            f"**{rewards['artefact_name']}**, humming faintly amid the wreckage."
        )
    else:
        loot_line = (
            "As you approach the ruined husk, a scattering of loot glints "
            "amid the wreckage."
        )
    embed = discord.Embed(
        title="✨ The Rite of Convergence is Complete",
        description=(
            f"{loot_line}\n\n"
            '*"Well, that\'ll come in handy."*\n\n'
            f"**Total turns:** {run_state.total_turns}  •  **Devotion Points:** {dp}\n"
            f"**Loot value:** {rewards['value']:,} "
            f"(+{rewards['excess_dp_bonus_pct']:.0f}% from excess DP)"
        ),
        color=discord.Color.gold(),
    )
    if rewards.get("bm_rewards", {}).get("summary_lines"):
        embed.add_field(
            name="Rewards",
            value="\n".join(rewards["bm_rewards"]["summary_lines"][:10]) or "—",
            inline=False,
        )
    if rewards.get("artefact_name"):
        embed.add_field(
            name=f"{ARTEFACT_SLOT} Artefact",
            value=f"**{rewards['artefact_name']}** — added to your Artefact inventory!",
            inline=False,
        )
        if rewards.get("artefact_image"):
            embed.set_thumbnail(url=rewards["artefact_image"])
    elif rewards.get("artefact_inventory_full"):
        embed.add_field(
            name=f"{ARTEFACT_SLOT} Artefact",
            value=(
                "An artefact tried to catch your eye, but your Artefact "
                "inventory is full (60/60) — discard one via `/gear` to make room."
            ),
            inline=False,
        )
    if is_first_clear:
        embed.add_field(
            name=f"{INNER_SANC} Inner Sanctum",
            value=(
                f"**First clear!** Gained **{RITE_CLEAR_ISP_REWARD}** "
                "Inner Sanctum Points!"
            ),
            inline=False,
        )
    return embed


def make_arbiter_end_state_callback(run_state: RiteRunState):
    async def _end_state(view: CombatView, message, interaction: discord.Interaction):
        # --- Mid-run phase clear: advance to next phase ---
        if (
            view.monster.hp <= 0
            and view.current_phase_index < len(view.combat_phases) - 1
        ):
            upcoming_phase_index = view.current_phase_index + 1

            # The Amalgam's fall (phase 5 -> 6) is the mask-slip moment — the
            # true Arbiter was standing behind it the whole time. This one
            # gets a real stop: a static reveal screen with an explicit
            # "Face the Arbiter" button, not an auto-timed transition.
            if upcoming_phase_index == _FINAL_PHASE_INDEX:
                # Neutralize this view before handing off to a fresh one for
                # Phase 6 — an in-flight auto-battle loop on this object
                # must not keep running once we've moved on to a different
                # CombatView (see CombatView.neutralize()).
                view.neutralize()

                trans_embed = discord.Embed(
                    title="🕯️ The Mask Slips",
                    description=(
                        "As you sink your weapon into the vile being, you are "
                        "repelled back with enormous force. The Amalgam's flesh "
                        "knits shut, then peels away entirely — and the Arbiter "
                        "stands where the creature had been all along.\n\n"
                        f'*"{get_quip("arbiter_toying")}"*'
                    ),
                    color=discord.Color.dark_purple(),
                )
                trans_embed.set_author(name="The Arbiter", icon_url=ARBITER_PORTRAIT)
                trans_embed.set_thumbnail(url=ARBITER_PHASE_FINAL)

                final_form_view = ArbiterFinalFormView(
                    view.bot,
                    view.user_id,
                    view.server_id,
                    view.player,
                    run_state,
                    trans_embed,
                )
                await message.edit(embed=None, view=final_form_view)
                final_form_view.message = message
                view.stop()
                return

            # Phase 6's fall (phase 6 -> 7) is the true final transformation —
            # the Last Edict form was never his true self either. Dialogue
            # beat gated behind a Proceed click, then a timed GIF transition
            # (no button — see ArbiterTransformView._on_confirm) into Phase 7.
            if upcoming_phase_index == _TRUE_FINAL_PHASE_INDEX:
                view.neutralize()

                trans_embed = discord.Embed(
                    title="🕯️ The Mask Slips Again",
                    description=(
                        "As you strike, the Arbiter returns to his previous "
                        "form.\n\n"
                        '*"No, no this cannot be, I.. I am eternal, the '
                        "first and last of my kind, I will **NOT** be "
                        'defeated."*'
                    ),
                    color=discord.Color.dark_purple(),
                )
                trans_embed.set_author(name="The Arbiter", icon_url=ARBITER_PORTRAIT)
                trans_embed.set_thumbnail(url=ARBITER_PORTRAIT)

                transform_view = ArbiterTransformView(
                    view.bot,
                    view.user_id,
                    view.server_id,
                    view.player,
                    run_state,
                    trans_embed,
                )
                await message.edit(embed=None, view=transform_view)
                transform_view.message = message
                view.stop()
                return

            # Phases 1-4: keep continuing the same CombatView, auto-timed.
            view.current_phase_index = upcoming_phase_index
            next_phase_data = view.combat_phases[view.current_phase_index]
            reset_for_phase_transition(view.player)
            # reset_for_phase_transition no longer zeros cs.atk_multiplier/
            # def_multiplier or the bonus accumulators — they, and the Power
            # stacking buff apply_respite_buffs set at Phase 1 start, persist
            # automatically across phases now. Re-invoking apply_respite_buffs
            # here would just overwrite atk/def_multiplier and silently wipe
            # any Start-of-Combat passive that also modifies them (e.g.
            # Diabolic Pact), so it's intentionally not called again.
            view.monster = mobgen.generate_arbiter_phase(
                view.player, next_phase_data, view.current_phase_index
            )
            _apply_arbiter_writ_overlays(view.monster, run_state.writs)
            view.monster.is_boss = True

            engine.apply_stat_effects(view.player, view.monster)
            # apply_combat_start_passives is guarded by player.cs.combat_start_fired —
            # it already fired at Phase 1 start and returns {} here.
            new_logs = engine.apply_combat_start_passives(view.player, view.monster)
            view.logs = new_logs

            flavor = _AMALGAM_TRANSITION_TEXT[view.current_phase_index]
            trans_embed = discord.Embed(
                title="Phase Complete!",
                description=(
                    f"{flavor}\n\n**{view.monster.name}** prepares itself. "
                    "Brace for impact."
                ),
                color=discord.Color.orange(),
            )
            trans_embed.set_thumbnail(url=view.monster.image)

            view._sync_items(
                combat_ui.embed_to_container(trans_embed), interactive=False
            )
            await message.edit(view=view)
            await asyncio.sleep(2.0)

            if not view._was_auto:
                view.update_buttons()
            view._processing = False

            view._sync_items(
                view._build_layout(
                    title_override=_arbiter_phase_title(
                        view.current_phase_index, view.monster.name
                    )
                )
            )
            await message.edit(view=view)
            return  # keep the view alive for the next phase

        # Turn counter spans every wing fight and every Arbiter phase,
        # excluding respite/reveal screens.
        run_state.total_turns += view.monster.combat_round
        fled = getattr(view, "fled", False)
        won = not fled and view.monster.hp <= 0 and view.player.current_hp > 0

        # Leaving combat entirely (not just advancing a phase — see the
        # early return above for that case): combat-only Max HP inflation
        # (Ward Inoculation's doubling, etc.) must not leak into whatever
        # comes next (wing hub on flee/death, or persisted current_hp).
        # Same fix as wing_hub_view.py's _end_state — see that comment.
        view.player.reset_combat_state()
        apply_respite_buffs(view.player, run_state)
        view.player.current_hp = min(view.player.current_hp, view.player.total_max_hp)

        await view.bot.database.users.update_from_player_object(view.player)
        await _je.save_jewel_state(view.bot, view.user_id, view.player)

        # Lazy import: wing_hub_view imports this module to trigger the
        # reveal, so a module-level import here would be circular.
        from core.rite.views.wing_hub_view import (
            RiteDefeatView,
            RiteEndView,
            WingHubView,
            build_rite_defeat_embed,
        )

        if won:
            view.bot.state_manager.clear_active(view.user_id)
            # ISP is a one-time reward for the player's first-ever full clear —
            # check before set_first_clear flips the flag, since that call is
            # unconditional (also gates Writ selection).
            is_first_clear = not await view.bot.database.rite.has_first_clear(
                view.user_id, view.server_id
            )
            await view.bot.database.rite.set_first_clear(view.user_id, view.server_id)
            await hof_triggers.check_absolute_cinema(view.bot, view.user_id)
            dp = compute_devotion_points(run_state.writs, run_state.total_turns)
            rewards = await grant_run_completion_rewards(
                view.bot, view.user_id, view.server_id, view.player, dp
            )
            if is_first_clear:
                await view.bot.database.inner_sanctum.add_points(
                    view.user_id, view.server_id, RITE_CLEAR_ISP_REWARD
                )
            await view.bot.database.rite.delete_run(view.user_id, view.server_id)

            # Stage 1: the Arbiter's own defeat, given a beat to land before
            # the loot reveal — a run-ending kill deserves more than an
            # instant cut to a rewards embed.
            defeat_embed = discord.Embed(
                title="🕯️ The Arbiter Falls",
                description=f'*"{get_quip("arbiter_true_defeat")}"*',
                color=discord.Color.gold(),
            )
            defeat_embed.set_author(name="The Arbiter", icon_url=ARBITER_PORTRAIT)
            defeat_embed.set_thumbnail(url=view.monster.image)
            view._sync_items(
                combat_ui.embed_to_container(defeat_embed), interactive=False
            )
            await message.edit(view=view)
            await asyncio.sleep(3.5)

            # Stage 2: a chest-style loot reveal, before the itemized numbers.
            bot_, user_id_, server_id_ = view.bot, view.user_id, view.server_id
            chest_image = (
                RITE_CHEST_ARTEFACT if rewards.get("artefact_name") else RITE_CHEST_NORMAL
            )

            async def _on_loot_proceed(loot_interaction: discord.Interaction):
                victory_embed = _build_victory_embed(
                    run_state, dp, rewards, is_first_clear
                )
                victory_view = RiteEndView(
                    bot_, user_id_, server_id_, victory_embed
                )
                await loot_interaction.response.edit_message(
                    embed=None, view=victory_view
                )
                victory_view.message = await loot_interaction.original_response()

            loot_view = RiteLootRevealView(
                bot_, user_id_, server_id_, chest_image, _on_loot_proceed
            )
            await message.edit(view=loot_view)
            loot_view.message = message
            view.stop()
            return

        # --- Not won: fled or died. Both cost an attempt and return to the
        # wing lobby, which offers "Challenge the Arbiter" again since all 5
        # wings are already cleared (see WingHubView._on_challenge_arbiter). ---
        run_state.attempts_remaining -= 1

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
            else "💀 The Rite Ends — The Arbiter Prevails"
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
            f'\n\n*"{get_quip("arbiter_defeat")}"*\n\n'
            "No attempts remain. The Rite of Convergence has ended; "
            "your keys are spent."
        )
        end_view = RiteEndView(view.bot, view.user_id, view.server_id, embed)
        await message.edit(view=end_view)
        end_view.message = message
        view.stop()

    return _end_state
