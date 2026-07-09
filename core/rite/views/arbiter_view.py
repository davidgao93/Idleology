"""The Arbiter — 6-phase finale. Builds Phase 1's CombatView and drives every
phase transition, final victory (loot payout), and defeat/retry through a
single rite_callback, since CombatView's own phase-transition machinery
generates monsters via the standard generate_boss() — wrong shape entirely
for the Arbiter's fixed-name/fixed-tier/equal-HP phases.
"""

import asyncio

import discord

from core.combat import ui as combat_ui
from core.combat.turns import engine
from core.combat.turns import jewel_engine as _je
from core.combat.turns.boundary import reset_for_phase_transition
from core.combat.views.views import CombatView
from core.npc_voices import get_quip
from core.rite import mobgen
from core.rite.data import compute_devotion_points
from core.rite.loot import grant_run_completion_rewards
from core.rite.run_state import RiteRunState
from core.rite.views.respite_view import POWER_ATK_DEF_MULT


def _apply_arbiter_writ_overlays(monster, writs: list[str]) -> None:
    if "trials_fury" in writs:
        monster.bonus_attack_pct += 1.0
        monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))


async def build_arbiter_combat_view(
    bot, user_id: str, server_id: str, player, run_state: RiteRunState, rite_callback
) -> CombatView:
    """Builds Phase 1's CombatView. Shared by the initial reveal transition
    and death retries, which always restart the whole Arbiter from Phase 1."""
    player.reset_combat_state()
    if run_state.pending_power_buff:
        player.cs.atk_multiplier = POWER_ATK_DEF_MULT
        player.cs.def_multiplier = POWER_ATK_DEF_MULT

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
        title_override=f"🕯️ THE ARBITER — PHASE 1: {monster.name.upper()}",
        player_avatar_url=user_row["appearance"] if user_row else None,
    )


def _build_victory_embed(
    run_state: RiteRunState, dp: int, rewards: dict
) -> discord.Embed:
    embed = discord.Embed(
        title="✨ The Rite of Convergence is Complete",
        description=(
            "The Arbiter falls. Its final edict goes unspoken.\n\n"
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
            name="🏺 Artefact",
            value=f"**{rewards['artefact_name']}** — equipped to your Artefact slot!",
            inline=False,
        )
    return embed


def make_arbiter_end_state_callback(run_state: RiteRunState):
    async def _end_state(view: CombatView, message, interaction: discord.Interaction):
        # --- Mid-run phase clear: advance to next phase, keep this CombatView alive ---
        if (
            view.monster.hp <= 0
            and view.current_phase_index < len(view.combat_phases) - 1
        ):
            view.current_phase_index += 1
            next_phase_data = view.combat_phases[view.current_phase_index]
            reset_for_phase_transition(view.player)
            view.monster = mobgen.generate_arbiter_phase(
                view.player, next_phase_data, view.current_phase_index
            )
            _apply_arbiter_writ_overlays(view.monster, run_state.writs)
            view.monster.is_boss = True

            engine.apply_stat_effects(view.player, view.monster)
            new_logs = engine.apply_combat_start_passives(view.player, view.monster)
            view.logs = new_logs

            trans_embed = discord.Embed(
                title="Phase Complete!",
                description=f"**{view.monster.name}** rises from the ashes...",
                color=discord.Color.orange(),
            )
            trans_embed.set_thumbnail(url=view.monster.image)
            view._sync_items(
                combat_ui.embed_to_container(trans_embed), interactive=False
            )
            await message.edit(view=view)
            await asyncio.sleep(2)

            if not view._was_auto:
                view.update_buttons()
            view._processing = False

            view._sync_items(
                view._build_layout(
                    title_override=(
                        f"🕯️ THE ARBITER — PHASE {view.current_phase_index + 1}: "
                        f"{view.monster.name.upper()}"
                    )
                )
            )
            await message.edit(view=view)
            return  # keep the view alive for the next phase

        # Turn counter spans every wing fight and every Arbiter phase,
        # excluding respite/reveal screens.
        run_state.total_turns += view.monster.combat_round
        won = view.monster.hp <= 0 and view.player.current_hp > 0

        await view.bot.database.users.update_from_player_object(view.player)
        await _je.save_jewel_state(view.bot, view.user_id, view.player)

        # Lazy import: wing_hub_view imports this module to trigger the
        # reveal, so a module-level import here would be circular.
        from core.rite.views.wing_hub_view import RiteEndView

        if won:
            view.bot.state_manager.clear_active(view.user_id)
            await view.bot.database.rite.set_first_clear(view.user_id, view.server_id)
            dp = compute_devotion_points(run_state.writs, run_state.total_turns)
            rewards = await grant_run_completion_rewards(
                view.bot, view.user_id, view.server_id, view.player, dp
            )
            await view.bot.database.rite.delete_run(view.user_id, view.server_id)

            embed = _build_victory_embed(run_state, dp, rewards)
            end_view = RiteEndView(view.bot, view.user_id, view.server_id, embed)
            await message.edit(view=end_view)
            end_view.message = message
            view.stop()
            return

        # --- Defeat: retry the whole Arbiter from Phase 1, or fail the run ---
        run_state.attempts_remaining -= 1

        if run_state.attempts_remaining > 0:
            view.player.current_hp = run_state.room_entry_hp
            await view.bot.database.users.update_from_player_object(view.player)
            await view.bot.database.rite.upsert_run(
                view.user_id, view.server_id, run_state.to_snapshot()
            )

            retry_view = await build_arbiter_combat_view(
                view.bot,
                view.user_id,
                view.server_id,
                view.player,
                run_state,
                make_arbiter_end_state_callback(run_state),
            )
            await message.edit(embed=None, view=retry_view)
            retry_view.message = message
            view.stop()
            return

        view.bot.state_manager.clear_active(view.user_id)
        await view.bot.database.rite.delete_run(view.user_id, view.server_id)
        embed = discord.Embed(
            title="💀 The Rite Ends — The Arbiter Prevails",
            description=(
                f'*"{get_quip("arbiter_defeat")}"*\n\n'
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
