import time

import discord
from discord import ButtonStyle, Interaction, ui

from core.maw import mechanics
from core.maw.ui import build_maw_embed


class MawView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        cycle_id: int,
        now_ts: int,
        record: dict | None,
        pending_record: dict | None,
        prev_cycle_id: int,
        participant_count: int,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.cycle_id = cycle_id
        self.now_ts = now_ts
        self.record = record
        self.pending_record = pending_record
        self.prev_cycle_id = prev_cycle_id
        self.participant_count = participant_count
        self.message = None
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        has_pending = (
            self.pending_record and not self.pending_record["rewards_collected"]
        )
        is_signed_up = self.record is not None
        cycle_active = mechanics.is_cycle_active(self.cycle_id, self.now_ts)

        if has_pending:
            btn_collect = ui.Button(
                label="Collect Rewards", style=ButtonStyle.success, emoji="🎁", row=0
            )
            btn_collect.callback = self.collect_rewards
            self.add_item(btn_collect)
        elif cycle_active and not is_signed_up:
            btn_fight = ui.Button(
                label="Fight the Maw", style=ButtonStyle.success, emoji="⚔️", row=0
            )
            btn_fight.callback = self.fight
            self.add_item(btn_fight)

        if is_signed_up and cycle_active:
            boost_ready = mechanics.boost_available(
                self.record.get("boost_used_at"), self.now_ts
            )
            btn_boost = ui.Button(
                label="Boost",
                style=ButtonStyle.blurple,
                emoji="💥",
                row=0,
                disabled=not boost_ready,
            )
            btn_boost.callback = self.boost
            self.add_item(btn_boost)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    def build_embed(self) -> discord.Embed:
        return build_maw_embed(
            cycle_id=self.cycle_id,
            now_ts=self.now_ts,
            participant_count=self.participant_count,
            fake_global_damage=mechanics.calculate_fake_global(
                self.participant_count, self.cycle_id, self.now_ts
            ),
            record=self.record,
            pending_record=self.pending_record,
            pending_cycle_id=self.prev_cycle_id,
        )

    async def fight(self, interaction: Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "This isn't your session.", ephemeral=True
            )

        now_ts = int(time.time())
        await self.bot.database.maw.sign_up(self.user_id, self.cycle_id, now_ts)
        self.record = {
            "signup_timestamp": now_ts,
            "last_damage_check": now_ts,
            "damage_dealt": 0,
            "boost_used_at": None,
            "rewards_collected": 0,
        }
        self.now_ts = now_ts
        self.participant_count += 1
        self._build_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def boost(self, interaction: Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "This isn't your session.", ephemeral=True
            )

        now_ts = int(time.time())
        if not mechanics.boost_available(self.record.get("boost_used_at"), now_ts):
            return await interaction.response.send_message(
                "Boost is still on cooldown.", ephemeral=True
            )

        new_damage = min(
            self.record["damage_dealt"] + mechanics.BOOST_DAMAGE,
            mechanics.DAMAGE_CAP,
        )
        await self.bot.database.maw.set_boost_used(
            self.user_id, self.cycle_id, new_damage, now_ts
        )
        self.record["damage_dealt"] = new_damage
        self.record["boost_used_at"] = now_ts
        self.now_ts = now_ts
        self._build_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def collect_rewards(self, interaction: Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "This isn't your session.", ephemeral=True
            )

        dmg = self.pending_record["damage_dealt"]
        curios, puzzle_box = mechanics.calculate_rewards(dmg)

        await self.bot.database.maw.mark_rewards_collected(
            self.user_id, self.prev_cycle_id
        )

        if curios > 0:
            await self.bot.database.users.modify_currency(
                self.user_id, "curios", curios
            )

        # TODO: award puzzle box item when curio_puzzle_boxes column is added
        # if puzzle_box:
        #     await self.bot.database.users.modify_currency(self.user_id, "curio_puzzle_boxes", 1)

        self.pending_record["rewards_collected"] = 1

        reward_msg = f"Collected **{curios} Curio{'s' if curios != 1 else ''}**"
        if puzzle_box:
            reward_msg += " and a **Curio Puzzle Box** *(placeholder — coming soon)*"
        reward_msg += "!"

        self.now_ts = int(time.time())
        self._build_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
        await interaction.followup.send(reward_msg, ephemeral=True)

    async def close_view(self, interaction: Interaction):
        self.stop()
        await interaction.response.edit_message(view=None)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass
