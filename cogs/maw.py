import time
from datetime import datetime, timezone

from discord import app_commands, Interaction
from discord.ext import commands

from core.maw import mechanics
from core.maw.views import MawView


class Maw(commands.Cog, name="maw"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="maw", description="Face the Maw of Infinity — an endless weekly world boss.")
    async def maw(self, interaction: Interaction):
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        now_ts = int(time.time())
        now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)

        cycle_id = mechanics.get_current_cycle_id(now_dt)

        # During the collection window the just-ended cycle IS the pending cycle.
        # Otherwise look one week back.
        if mechanics.is_collection_window(cycle_id, now_ts):
            pending_cycle_id = cycle_id
            cycle_id = mechanics.get_next_cycle_id(cycle_id)  # next cycle hasn't started yet
        else:
            pending_cycle_id = mechanics.get_previous_cycle_id(cycle_id)

        pending_record = await self.bot.database.maw.get_record(user_id, pending_cycle_id)
        if pending_record and pending_record["rewards_collected"]:
            pending_record = None

        record = await self.bot.database.maw.get_record(user_id, cycle_id)

        if record and mechanics.is_cycle_active(cycle_id, now_ts):
            record, now_ts = await self._tick_damage(user_id, cycle_id, record, now_ts)

        display_cycle_id = pending_cycle_id if mechanics.is_collection_window(pending_cycle_id, now_ts) else cycle_id
        participant_count = await self.bot.database.maw.count_participants(display_cycle_id)

        view = MawView(
            bot=self.bot,
            user_id=user_id,
            cycle_id=cycle_id,
            now_ts=now_ts,
            record=record,
            pending_record=pending_record,
            prev_cycle_id=pending_cycle_id,
            participant_count=participant_count,
        )
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()

    async def _tick_damage(self, user_id: str, cycle_id: int, record: dict, now_ts: int) -> tuple[dict, int]:
        hours_elapsed = (now_ts - record["last_damage_check"]) // 3600
        if hours_elapsed <= 0:
            return record, now_ts

        new_damage = mechanics.roll_hourly_damage(hours_elapsed)
        current = record["damage_dealt"]
        added = min(new_damage, mechanics.DAMAGE_CAP - current)
        record["damage_dealt"] = current + added
        record["last_damage_check"] = now_ts

        await self.bot.database.maw.update_damage(user_id, cycle_id, record["damage_dealt"], now_ts)
        return record, now_ts


async def setup(bot):
    await bot.add_cog(Maw(bot))
