"""The fifth respite — the Reveal. Per RAID-DESIGN.md: the Arbiter appears as
normal, then the atmosphere destabilizes and the final boss begins
immediately with no aid granted. Implemented as a scripted transition: a
narrative embed on the existing message, a short pause, then straight into
the Arbiter's Phase 1 CombatView.
"""

import asyncio

import discord

from core.images import ARBITER_PORTRAIT, ARBITER_THUMBNAIL
from core.npc_voices import get_quip
from core.rite.run_state import RiteRunState


async def trigger_reveal_and_arbiter(bot, user_id: str, server_id: str, player, run_state: RiteRunState, message) -> None:
    # Lazy imports: arbiter_view <-> wing_hub_view/reveal_view form a small
    # import cycle at the module level otherwise.
    from core.rite.views.arbiter_view import build_arbiter_combat_view, make_arbiter_end_state_callback

    run_state.current_wing = "arbiter"
    run_state.room_entry_hp = player.current_hp
    run_state.room_entry_potions = player.potions
    await bot.database.rite.upsert_run(user_id, server_id, run_state.to_snapshot())

    reveal_embed = discord.Embed(
        title="🕯️ The Arbiter Reveals Itself",
        description=(
            f'*"{get_quip("arbiter_reveal")}"*\n\n'
            "The essences of the five defeated bosses converge. The air fractures. "
            "The Arbiter's true form emerges — the architect behind everything "
            "you have faced tonight.\n\n"
            "No respite. No aid. The final boss begins immediately."
        ),
        color=discord.Color.dark_purple(),
    )
    reveal_embed.set_author(name="The Arbiter", icon_url=ARBITER_PORTRAIT)
    reveal_embed.set_thumbnail(url=ARBITER_THUMBNAIL)

    from core.combat import ui as combat_ui

    reveal_view = discord.ui.LayoutView()
    reveal_view.add_item(combat_ui.embed_to_container(reveal_embed))
    await message.edit(view=reveal_view)
    await asyncio.sleep(3)

    arbiter_callback = make_arbiter_end_state_callback(run_state)
    combat_view = await build_arbiter_combat_view(
        bot, user_id, server_id, player, run_state, arbiter_callback
    )
    await message.edit(embed=None, view=combat_view)
    combat_view.message = message
