"""
core/maw/views.py — Maw of Infinity lobby view.

Handles sign-up, fight launch, reward collection, and close.
Fight button replaces the old Boost button: launches a 10-turn
MawEncounterView. Cooldown is 20 hours, cap is 5 fights per cycle.
"""

import time

import discord
from discord import ButtonStyle, Interaction, ui

from core.apex.models import soul_stone_from_db
from core.base_view import BaseView
from core.combat import jewel_engine as _je
from core.items.factory import load_player
from core.maw import mechanics
from core.maw.ui import build_maw_embed


class MawView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        cycle_id: int,
        now_ts: int,
        record: dict | None,
        pending_record: dict | None,
        prev_cycle_id: int,
        participant_count: int,
        total_cycle_damage: int = 0,
        pending_total_damage: int = 0,
        pending_participant_count: int = 0,
    ):
        super().__init__(bot=bot, user_id=user_id, server_id=server_id)
        self.cycle_id = cycle_id
        self.now_ts = now_ts
        self.record = record
        self.pending_record = pending_record
        self.prev_cycle_id = prev_cycle_id
        self.participant_count = participant_count
        self.total_cycle_damage = total_cycle_damage
        self.pending_total_damage = pending_total_damage
        self.pending_participant_count = pending_participant_count
        self.message = None
        self._processing = False
        self._build_buttons()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_buttons(self):
        self.clear_items()

        has_pending = (
            self.pending_record and not self.pending_record["rewards_collected"]
        )
        cycle_active = mechanics.is_cycle_active(self.cycle_id, self.now_ts)

        # Collect Rewards — only during collection window
        if has_pending:
            btn_collect = ui.Button(
                label="Collect Rewards", style=ButtonStyle.success, emoji="🎁", row=0
            )
            btn_collect.callback = self.collect_rewards
            self.add_item(btn_collect)

        # Fight button — only during active cycle
        if cycle_active:
            last_fight_ts = self.record.get("last_fight_ts") if self.record else None
            fights_done = self.record.get("fights_this_cycle", 0) if self.record else 0
            can_fight = mechanics.fight_available(
                last_fight_ts, fights_done, self.now_ts
            )
            fights_left = max(0, mechanics.MAX_FIGHTS_PER_CYCLE - fights_done)

            if fights_done >= mechanics.MAX_FIGHTS_PER_CYCLE:
                label = f"Fight the Maw (0/{mechanics.MAX_FIGHTS_PER_CYCLE} left)"
            elif not can_fight and last_fight_ts:
                secs = mechanics.fight_remaining_seconds(last_fight_ts, self.now_ts)
                h, rem = divmod(secs, 3600)
                m = rem // 60
                time_str = f"{h}h {m}m" if h > 0 else f"{m}m"
                label = f"Fight the Maw ({time_str} · {fights_left} left)"
            else:
                label = f"Fight the Maw ({fights_left}/{mechanics.MAX_FIGHTS_PER_CYCLE} left)"

            btn_fight = ui.Button(
                label=label,
                style=ButtonStyle.danger if can_fight else ButtonStyle.secondary,
                emoji="⚔️",
                row=0,
                disabled=not can_fight,
            )
            btn_fight.callback = self.fight
            self.add_item(btn_fight)

        btn_close = ui.Button(
            label="Close", style=ButtonStyle.secondary, emoji="✖️", row=1
        )
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    def build_embed(self) -> discord.Embed:
        return build_maw_embed(
            cycle_id=self.cycle_id,
            now_ts=self.now_ts,
            participant_count=self.participant_count,
            total_cycle_damage=self.total_cycle_damage,
            record=self.record,
            pending_record=self.pending_record,
            pending_cycle_id=self.prev_cycle_id,
            pending_total_damage=self.pending_total_damage,
            pending_participant_count=self.pending_participant_count,
        )

    # ------------------------------------------------------------------
    # Fight
    # ------------------------------------------------------------------

    async def fight(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        now_ts = int(time.time())

        # Sign up on first fight
        if not self.record:
            await self.bot.database.maw.sign_up(self.user_id, self.cycle_id, now_ts)
            self.record = {
                "signup_timestamp": now_ts,
                "last_fight_ts": 0,
                "damage_dealt": 0,
                "rewards_collected": 0,
                "fights_this_cycle": 0,
            }
            self.participant_count += 1

        # Load player with full gear + soul stone
        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        player = await load_player(self.user_id, user_row, self.bot.database)

        ss_row = await self.bot.database.apex.get_or_create_soul_stone(
            self.user_id, self.server_id
        )
        player.soul_stone = soul_stone_from_db(ss_row)

        # Reset jewel charges before the encounter (same rule as /combat)
        _je.reset_jewel_charges(player)

        from core.maw.encounter_view import MawEncounterView

        encounter = MawEncounterView(
            bot=self.bot,
            player=player,
            user_id=self.user_id,
            server_id=self.server_id,
            cycle_id=self.cycle_id,
        )
        self._processing = False
        self.stop()
        await interaction.edit_original_response(
            embed=encounter.build_embed(), view=encounter
        )
        encounter.message = await interaction.original_response()

    # ------------------------------------------------------------------
    # Collect Rewards
    # ------------------------------------------------------------------

    async def collect_rewards(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # Fetch final cycle totals at collection time (stable after cycle ends)
        total_damage = await self.bot.database.maw.get_cycle_total_damage(
            self.prev_cycle_id
        )
        participant_count = await self.bot.database.maw.count_participants(
            self.prev_cycle_id
        )
        top3 = await self.bot.database.maw.get_top_n(self.prev_cycle_id, 3)
        is_top3 = self.user_id in top3

        player_damage = self.pending_record["damage_dealt"]
        curios, guild_tickets, puzzle_box = mechanics.calculate_rewards(
            player_damage, total_damage, participant_count, is_top3
        )

        await self.bot.database.maw.mark_rewards_collected(
            self.user_id, self.prev_cycle_id
        )

        if curios > 0:
            await self.bot.database.users.modify_currency(
                self.user_id, "curios", curios
            )
        if guild_tickets > 0:
            await self.bot.database.partners.add_tickets(self.user_id, guild_tickets)
        if puzzle_box:
            await self.bot.database.users.modify_currency(
                self.user_id, "curio_puzzle_boxes", 1
            )

        self.pending_record["rewards_collected"] = 1

        reward_parts = [f"**{curios} Curio{'s' if curios != 1 else ''}**"]
        reward_parts.append(
            f"**{guild_tickets} Guild Ticket{'s' if guild_tickets != 1 else ''}**"
        )
        if puzzle_box:
            reward_parts.append("**Curio Puzzle Box** 🏆 *(Top 3)*")
        reward_msg = "Collected: " + ", ".join(reward_parts) + "!"

        self.now_ts = int(time.time())
        self._processing = False
        self._build_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)
        await interaction.followup.send(reward_msg, ephemeral=True)

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
