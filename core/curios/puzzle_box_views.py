import asyncio

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.curios.puzzle_box_logic import (
    PUZZLE_BOX_IMAGE,
    REWARD_EMOJIS,
    claim_rewards,
    format_slot_display,
    roll_all_slots,
    roll_slot,
)
from core.emojis import CURIO, PUZZLE_BOX


class PuzzleBoxView(BaseView):
    def __init__(self, bot, user_id: str, server_id: str):
        # timeout=60 is load-bearing: it's what makes discord.py actually call
        # on_timeout() after 60s, which is what performs the auto-claim. Every
        # dispatched interaction (e.g. a reroll) refreshes this window, mirrored
        # below by restarting the display countdown in _restart_countdown().
        super().__init__(bot=bot, user_id=user_id, server_id=server_id, timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.slots: list[tuple[str, int]] = roll_all_slots()
        self.claimed = False
        self.message = None
        self._reward_lines: list[str] = []
        self._remaining_seconds: int = 60
        self._build_buttons()
        self._countdown_task = asyncio.create_task(self._countdown_loop())

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

    async def _countdown_loop(self):
        for i in range(6):
            await asyncio.sleep(10)
            self._remaining_seconds = max(0, 60 - (i + 1) * 10)
            if self.claimed or not self.message:
                return
            try:
                await self.message.edit(embed=self.build_embed())
            except Exception:
                return

    def _restart_countdown(self):
        """Keeps the displayed countdown in sync with discord.py's real timeout,
        which silently refreshes to a fresh 60s window on every dispatched
        interaction (see discord.ui.View._scheduled_task)."""
        self._countdown_task.cancel()
        self._remaining_seconds = 60
        self._countdown_task = asyncio.create_task(self._countdown_loop())

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{PUZZLE_BOX} Curio Puzzle Box",
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

        embed.set_footer(
            text=f"⏳ {self._remaining_seconds}s remaining · Auto-claims on expiry"
        )
        return embed

    def build_claimed_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{PUZZLE_BOX} Puzzle Box Opened!",
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

        used = {rtype for i, (rtype, _) in enumerate(self.slots) if i != slot_index}
        self.slots[slot_index] = roll_slot(exclude=used)
        self._restart_countdown()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _claim(self, interaction: Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "This isn't your session.", ephemeral=True
            )
        if self.claimed:
            return
        self.claimed = True  # Set before defer to prevent concurrent double-claims

        await interaction.response.defer()
        await self._do_claim()
        claimed_view = _ClaimedPuzzleBoxView(self.bot, self.user_id, self.server_id)
        await interaction.edit_original_response(
            embed=self.build_claimed_embed(), view=claimed_view
        )
        claimed_view.message = await interaction.original_response()
        self.stop()

    async def _do_claim(self):
        self.claimed = True
        self._countdown_task.cancel()
        self._reward_lines = await claim_rewards(
            self.bot, self.user_id, self.server_id, self.slots
        )
        self.bot.state_manager.clear_active(self.user_id)

    async def on_timeout(self):
        if self.claimed or not self.message:
            # Already claimed or no message reference; let BaseView do normal cleanup.
            await super().on_timeout()
            return
        try:
            await self._do_claim()
            # By the time this runs, discord.py has already marked `self` as
            # finished and dropped it from the interaction dispatch store (see
            # View._dispatch_timeout), so reusing `self` here would render a
            # "Back to Curios" button that looks clickable but silently fails.
            # A fresh view is required to actually be dispatchable.
            claimed_view = _ClaimedPuzzleBoxView(self.bot, self.user_id, self.server_id)
            await self.message.edit(embed=self.build_claimed_embed(), view=claimed_view)
            claimed_view.message = self.message
        except (discord.NotFound, discord.HTTPException):
            pass
        self.stop()


class _ClaimedPuzzleBoxView(BaseView):
    """Shown after a puzzle box has been claimed, manually or via auto-claim timeout."""

    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(bot=bot, user_id=user_id, server_id=server_id)
        btn_back = ui.Button(
            label="Back to Curios", style=ButtonStyle.secondary, emoji=CURIO, row=0
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
        cur = await self.bot.database.users.get_all_currencies(user_id)
        curio_count = cur["curios"]
        puzzle_box_count = cur["curio_puzzle_boxes"]

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
