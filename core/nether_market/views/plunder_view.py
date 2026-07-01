"""
core/nether_market/views/plunder_view.py — The Mastermind plunder session.

Session state (code, attempts, guess history) lives entirely in-memory on the view —
codes are single-use and never persisted or reused across sessions (see
docs/design/nether_market.md §7.2/§7.5).
"""

import time

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.nether_market.mechanics import NetherMarketMechanics as M


async def build_plunder_view(
    bot, user_id: str, server_id: str, target: dict, attacker_profile: dict
) -> "PlunderView":
    if target["kind"] == "player":
        defender_id = target["user_id"]
        defender_profile = await bot.database.nether_market.get_or_create_profile(defender_id, server_id)
        attempts, shield_seconds = M.get_session_params(
            target["tier_index"], defender_profile["mastery_nodes"], attacker_profile["mastery_nodes"]
        )
        try:
            user = await bot.fetch_user(int(defender_id))
            target_name = user.display_name
        except Exception:
            target_name = f"Unknown ({defender_id})"
    else:
        defender_profile = None
        attempts, shield_seconds = M.get_npc_session_params(target["npc"], attacker_profile["mastery_nodes"])
        target_name = target["npc"]["name"]

    code = M.generate_code()
    return PlunderView(
        bot,
        user_id,
        server_id,
        target,
        target_name,
        attacker_profile,
        defender_profile,
        code,
        attempts,
        shield_seconds,
    )


class PlunderView(BaseView):
    def __init__(
        self,
        bot,
        user_id,
        server_id,
        target: dict,
        target_name: str,
        attacker_profile: dict,
        defender_profile: dict | None,
        code: str,
        max_attempts: int,
        shield_seconds: float,
    ):
        super().__init__(bot, user_id, server_id)
        self.target = target
        self.target_display_name = target_name
        self.attacker_profile = attacker_profile
        self.defender_profile = defender_profile
        self.code = code
        self.max_attempts = max_attempts
        self.attempts_remaining = max_attempts
        self.shield_seconds = shield_seconds
        self.guess_history: list[tuple[str, int, int]] = []
        self.resolved = False
        self._processing = False
        self._build_buttons()

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="\U0001f5dd️ Crack the Code", color=discord.Color.dark_gold())
        embed.description = (
            f"Target: **{self.target_display_name}**\n"
            f"Attempts remaining: **{self.attempts_remaining} / {self.max_attempts}**"
        )
        if self.guess_history:
            lines = [f"`{g}` — ⚫{b} ⚪{w}" for g, b, w in self.guess_history]
            embed.add_field(name="Guess History (black = right digit+spot, white = right digit)", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Guess History", value="No guesses yet.", inline=False)

        if self.resolved:
            embed.add_field(name="Code Revealed", value=f"`{self.code}`", inline=False)
        return embed

    def _build_buttons(self):
        self.clear_items()
        if not self.resolved:
            guess_btn = ui.Button(label="Guess", style=ButtonStyle.primary, emoji="\U0001f3b2")
            guess_btn.callback = self.open_guess_modal
            self.add_item(guess_btn)

            giveup_btn = ui.Button(label="Give Up", style=ButtonStyle.secondary)
            giveup_btn.callback = self.give_up
            self.add_item(giveup_btn)
        else:
            back_btn = ui.Button(label="Return to Market", style=ButtonStyle.secondary)
            back_btn.callback = self.go_back
            self.add_item(back_btn)

    async def open_guess_modal(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        await interaction.response.send_modal(GuessModal(self))

    async def give_up(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        await self._resolve(interaction, success=False)

    async def handle_guess(self, interaction: Interaction, guess: str):
        black, white = M.score_guess(self.code, guess)
        self.guess_history.append((guess, black, white))
        self.attempts_remaining -= 1

        if black == 4:
            await self._resolve(interaction, success=True)
        elif self.attempts_remaining <= 0:
            await self._resolve(interaction, success=False)
        else:
            self._build_buttons()
            await interaction.edit_original_response(embed=self.build_embed(), view=self)
            self._processing = False

    async def _resolve(self, interaction: Interaction, success: bool):
        self.resolved = True
        result_lines = []
        if success:
            result_lines.append("✅ **Code cracked!**")
            if self.target["kind"] == "player":
                await self._resolve_player_success()
                result_lines.append(f"You made off with a cut of {self.target_display_name}'s holdings.")
            else:
                npc = self.target["npc"]
                await self.bot.database.nether_market.add_marks(self.user_id, self.server_id, npc["reward_marks"])
                await self.bot.database.users.modify_gold(self.user_id, npc["reward_gold"])
                result_lines.append(f"{npc['name']} pays out \U0001f536 {npc['reward_marks']} Mark(s) and \U0001f4b0 {npc['reward_gold']:,} gold.")
        else:
            result_lines.append("❌ **Out of attempts.** No penalty, no shield — just an empty haul.")

        self._build_buttons()
        embed = self.build_embed()
        embed.add_field(name="Result", value="\n".join(result_lines), inline=False)
        await interaction.edit_original_response(embed=embed, view=self)
        self._processing = False

    async def _resolve_player_success(self):
        defender_id = self.target["user_id"]
        holdings = await self.bot.database.nether_market.get_holdings(defender_id, self.server_id)
        pct = M.roll_plunder_pct(self.defender_profile["mastery_nodes"])

        attacker_cap = M.get_holdings_cap(self.attacker_profile["mastery_nodes"])
        attacker_held = await self.bot.database.nether_market.get_holdings_count(self.user_id, self.server_id)
        free_slots = max(0, attacker_cap - attacker_held)

        moved, overflow_gold = M.apply_plunder(holdings, pct, free_slots)
        for item_key, qty in moved.items():
            await self.bot.database.nether_market.modify_holdings(defender_id, self.server_id, item_key, -qty)
            await self.bot.database.nether_market.modify_holdings(self.user_id, self.server_id, item_key, qty)
        if overflow_gold:
            await self.bot.database.users.modify_gold(self.user_id, overflow_gold)

        await self.bot.database.nether_market.add_marks(self.user_id, self.server_id, 1)
        await self.bot.database.nether_market.set_shield(defender_id, self.server_id, time.time() + self.shield_seconds)
        await self.bot.database.nether_market.record_plunder_time(defender_id, self.server_id)

    async def go_back(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.hub_view import build_hub_view

        view = await build_hub_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(embed=view.build_embed(), view=view)
        view.message = msg
        self.stop()


class GuessModal(ui.Modal, title="Crack the Code"):
    guess_input = ui.TextInput(
        label="4-digit guess (0-9, repeats allowed)",
        placeholder="e.g. 1234",
        min_length=4,
        max_length=4,
        required=True,
    )

    def __init__(self, parent_view: PlunderView):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        guess = self.guess_input.value.strip()
        if not (guess.isdigit() and len(guess) == 4):
            return await interaction.response.send_message(
                "Enter exactly 4 digits (0-9).", ephemeral=True
            )
        if self.parent_view._processing:
            return await interaction.response.defer()
        self.parent_view._processing = True
        await interaction.response.defer()
        await self.parent_view.handle_guess(interaction, guess)
