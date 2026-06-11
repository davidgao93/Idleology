# cogs/maw.py
import time
from datetime import datetime, timezone

from discord import Interaction, app_commands
from discord.ext import commands

from core.maw import mechanics
from core.maw.views import MawView


class Maw(commands.Cog, name="maw"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="maw",
        description="Face the Maw of Infinity — an endless weekly world boss.",
    )
    async def maw(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if existing_user["level"] < 20:
            await interaction.response.send_message(
                "The Maw of Infinity does not stir for those below **Level 20**.",
                ephemeral=True,
            )
            return

        self.bot.state_manager.set_active(user_id, "maw")
        await interaction.response.defer()

        now_ts = int(time.time())
        now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        cycle_id = mechanics.get_current_cycle_id(now_dt)

        # During the collection window the just-ended cycle IS the pending cycle.
        in_collection = mechanics.is_collection_window(cycle_id, now_ts)
        if in_collection:
            pending_cycle_id = cycle_id
            cycle_id = mechanics.get_next_cycle_id(cycle_id)
        else:
            pending_cycle_id = mechanics.get_previous_cycle_id(cycle_id)

        # Load records
        record = await self.bot.database.maw.get_record(user_id, cycle_id)
        pending_record = await self.bot.database.maw.get_record(
            user_id, pending_cycle_id
        )
        if pending_record and pending_record["rewards_collected"]:
            pending_record = None

        # The "display cycle" is the one whose stats appear in the embed description:
        # the ended cycle during collection window, or the active cycle otherwise.
        display_cycle_id = pending_cycle_id if in_collection else cycle_id
        participant_count = await self.bot.database.maw.count_participants(
            display_cycle_id
        )
        total_cycle_damage = await self.bot.database.maw.get_cycle_total_damage(
            display_cycle_id
        )

        # Separate totals for the pending-rewards preview section.
        # During collection window they're the same as the display cycle; otherwise
        # they cover the prior cycle independently.
        if in_collection:
            pending_total_damage = total_cycle_damage
            pending_participant_count = participant_count
        elif pending_record:
            pending_total_damage = await self.bot.database.maw.get_cycle_total_damage(
                pending_cycle_id
            )
            pending_participant_count = await self.bot.database.maw.count_participants(
                pending_cycle_id
            )
        else:
            pending_total_damage = 0
            pending_participant_count = 0

        view = MawView(
            bot=self.bot,
            user_id=user_id,
            server_id=server_id,
            cycle_id=cycle_id,
            now_ts=now_ts,
            record=record,
            pending_record=pending_record,
            prev_cycle_id=pending_cycle_id,
            participant_count=participant_count,
            total_cycle_damage=total_cycle_damage,
            pending_total_damage=pending_total_damage,
            pending_participant_count=pending_participant_count,
        )
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Maw(bot))
