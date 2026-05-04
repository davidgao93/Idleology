import discord
from discord import ButtonStyle, Interaction, ui

from core.curios.puzzle_box_logic import (
    PUZZLE_BOX_IMAGE,
    REWARD_EMOJIS,
    claim_rewards,
    format_slot_display,
    roll_all_slots,
    roll_slot,
)


class PuzzleBoxView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.slots: list[tuple[str, int]] = roll_all_slots()
        self.claimed = False
        self.message = None
        self._reward_lines: list[str] = []
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        for i in range(3):
            btn = ui.Button(
                label=f"Reroll Slot {i + 1}",
                style=ButtonStyle.blurple,
                emoji="🎲",
                disabled=self.claimed,
                row=0,
                custom_id=f"reroll_{i}",
            )
            slot_index = i
            btn.callback = lambda interaction, idx=slot_index: self._reroll_slot(
                interaction, idx
            )
            self.add_item(btn)

        btn_claim = ui.Button(
            label="Claim Rewards",
            style=ButtonStyle.success,
            emoji="✅",
            disabled=self.claimed,
            row=1,
        )
        btn_claim.callback = self._claim
        self.add_item(btn_claim)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📦 Curio Puzzle Box",
            description=(
                "Three reward slots are revealed. Reroll any slot to change its type and quantity. "
                "What you see is what you get."
            ),
            color=0x9B59B6,
        )
        embed.set_thumbnail(url=PUZZLE_BOX_IMAGE)

        for i, (rtype, qty) in enumerate(self.slots, 1):
            emoji = REWARD_EMOJIS[rtype]
            display = format_slot_display(rtype, qty)
            embed.add_field(
                name=f"Slot {i}",
                value=f"{emoji} **{rtype}**\n{display}",
                inline=True,
            )

        embed.set_footer(text="60 second timeout · Auto-claims on expiry")
        return embed

    def build_claimed_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📦 Puzzle Box Opened!",
            description="\n".join(self._reward_lines),
            color=0x2ECC71,
        )
        embed.set_image(url=PUZZLE_BOX_IMAGE)
        return embed

    async def _reroll_slot(self, interaction: Interaction, slot_index: int):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "This isn't your session.", ephemeral=True
            )

        self.slots[slot_index] = roll_slot()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _claim(self, interaction: Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "This isn't your session.", ephemeral=True
            )
        if self.claimed:
            return

        await interaction.response.defer()
        await self._do_claim()
        await interaction.edit_original_response(
            embed=self.build_claimed_embed(), view=self
        )

    async def _do_claim(self):
        self.claimed = True
        self._reward_lines = await claim_rewards(
            self.bot, self.user_id, self.server_id, self.slots
        )
        self.bot.state_manager.clear_active(self.user_id)
        self.clear_items()
        btn_back = ui.Button(
            label="Back to Curios", style=ButtonStyle.secondary, emoji="🎁", row=0
        )
        btn_back.callback = self._back_to_curios
        self.add_item(btn_back)

    async def _back_to_curios(self, interaction: Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "This isn't your session.", ephemeral=True
            )

        from core.curios.views import CurioView

        user_id = self.user_id
        server_id = self.server_id
        curio_count = await self.bot.database.users.get_currency(user_id, "curios")
        puzzle_box_count = await self.bot.database.users.get_currency(
            user_id, "curio_puzzle_boxes"
        )

        if curio_count <= 0 and puzzle_box_count <= 0:
            self.stop()
            await interaction.response.edit_message(
                embed=discord.Embed(
                    description="You have no more Curios or Puzzle Boxes.",
                    color=discord.Color.dark_grey(),
                ),
                view=None,
            )
            return

        self.bot.state_manager.set_active(user_id, "curios")
        self.stop()
        view = CurioView(self.bot, user_id, server_id, curio_count, puzzle_box_count)
        await interaction.response.edit_message(embed=view.build_hub_embed(), view=view)
        view.message = await interaction.original_response()

    async def on_timeout(self):
        if self.claimed or not self.message:
            return
        try:
            await self._do_claim()
            await self.message.edit(embed=self.build_claimed_embed(), view=self)
        except (discord.NotFound, discord.HTTPException):
            pass
