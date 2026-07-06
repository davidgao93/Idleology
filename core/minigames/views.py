import asyncio

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Modal, TextInput

from core.base_view import BaseView
from core.images import TAVERN_CASINO

from .logic import BlackjackLogic, CrashLogic, HorseRaceLogic, RouletteLogic


async def check_funds(bot, user_id, amount, interaction):
    user_data = await bot.database.users.get(user_id, interaction.guild.id)
    if user_data["gold"] < amount:
        await interaction.response.send_message(
            f"Insufficient funds to restart! You need {amount:,} gold.", ephemeral=True
        )
        return False
    return True


# ==============================================================================
#  ROULETTE COMPONENTS
# ==============================================================================


class RouletteNumberModal(Modal, title="Bet on a Number"):
    number_input = TextInput(
        label="Pick a number (0-36)",
        placeholder="e.g. 7",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.number_input.value)
            if not (0 <= val <= 36):
                await interaction.response.send_message(
                    "Number must be between 0 and 36.", ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid integer.", ephemeral=True
            )
            return

        # Deduct here — after the user has confirmed their number.
        # This prevents gold loss if the modal is dismissed without submitting.
        user_data = await self.parent_view.bot.database.users.get(
            self.parent_view.user_id, interaction.guild.id
        )
        if user_data["gold"] < self.parent_view.bet_amount:
            await interaction.response.send_message(
                "Insufficient funds!", ephemeral=True
            )
            return
        await self.parent_view.bot.database.users.modify_gold(
            self.parent_view.user_id, -self.parent_view.bet_amount
        )
        await self.parent_view.run_spin(interaction, "number", str(val))


class RouletteView(BaseView):
    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(bot, user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        self.game_over = False
        self._processing = False

    async def on_timeout(self):
        if not self.game_over:
            # Only delete, do not refund yet as money is only taken on button press
            try:
                await self.original_interaction.delete_original_response()
            except Exception:
                pass
        self.bot.state_manager.clear_active(self.user_id)

    async def _deduct_and_verify(self, interaction: Interaction) -> bool:
        # Verify funds
        user_data = await self.bot.database.users.get(
            self.user_id, interaction.guild.id
        )
        if user_data["gold"] < self.bet_amount:
            await interaction.response.send_message(
                "Insufficient funds!", ephemeral=True
            )
            return False

        # Deduct
        await self.bot.database.users.modify_gold(self.user_id, -self.bet_amount)
        return True

    async def run_spin(self, interaction: Interaction, bet_type: str, bet_target: str):
        self.game_over = True

        # 1. Spin
        result_num = RouletteLogic.spin_wheel()
        result_color = RouletteLogic.get_color(result_num)
        emoji = RouletteLogic.get_color_emoji(result_color)

        # 2. Check Win
        won = RouletteLogic.check_win(bet_type, bet_target, result_num)

        # 3. Payouts
        payout = 0
        quest_msgs = []
        if won:
            multiplier = (
                35 if bet_type == "number" else 2
            )  # 35:1 for number, 1:1 (2x return) for color/parity
            payout = self.bet_amount * multiplier
            await self.bot.database.users.modify_gold(self.user_id, payout)
            net_win = payout - self.bet_amount
            if net_win > 0:
                try:
                    from core.quests.mechanics import tick_quest_progress

                    quest_msgs = await tick_quest_progress(
                        self.bot,
                        self.user_id,
                        str(interaction.guild_id),
                        "casino_win",
                        value=net_win,
                    )
                except Exception:
                    pass

        # 4. Build Embed
        color_map = {
            "red": discord.Color.red(),
            "black": discord.Color.default(),  # Dark greyish
            "green": discord.Color.green(),
        }

        embed = discord.Embed(
            title=f"Roulette Results {emoji}", color=color_map[result_color]
        )
        embed.description = (
            f"The ball lands on **{result_num} ({result_color.title()})**!"
        )

        target_display = bet_target.title() if bet_type != "number" else str(bet_target)

        if won:
            embed.add_field(
                name="Winner!",
                value=f"You bet on **{target_display}** and won **{payout:,} gold**!",
                inline=False,
            )
        else:
            embed.add_field(
                name="Loss",
                value=f"You bet on **{target_display}**. Better luck next time.",
                inline=False,
            )
        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )
        self.clear_items()
        embed.set_footer(text="Game Over")

        # Add Restart Button
        restart_btn = Button(
            label="Place Another Bet", style=ButtonStyle.primary, emoji="🔄"
        )
        restart_btn.callback = self.reset_table
        self.add_item(restart_btn)

        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

        await interaction.response.edit_message(embed=embed, view=self)

    async def reset_table(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        # Verify they still have money for the base bet size
        if not await check_funds(self.bot, self.user_id, self.bet_amount, interaction):
            self._processing = False
            return

        self.game_over = False
        self.clear_items()

        # Re-add betting buttons
        self.add_item(self.bet_red)
        self.add_item(self.bet_black)
        self.add_item(self.bet_even)
        self.add_item(self.bet_odd)
        self.add_item(self.bet_number)

        embed = discord.Embed(
            title="🎡 Roulette Table",
            description=f"Betting **{self.bet_amount:,} gold**.\nChoose your wager:",
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=TAVERN_CASINO)

        self._processing = False
        await interaction.response.edit_message(embed=embed, view=self)

    async def quit_game(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    # --- UI BUTTONS ---
    @discord.ui.button(label="Red (x2)", style=ButtonStyle.danger, row=0)
    async def bet_red(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        if await self._deduct_and_verify(interaction):
            await self.run_spin(interaction, "color", "red")
        else:
            self._processing = False

    @discord.ui.button(label="Black (x2)", style=ButtonStyle.secondary, row=0)
    async def bet_black(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        if await self._deduct_and_verify(interaction):
            await self.run_spin(interaction, "color", "black")
        else:
            self._processing = False

    @discord.ui.button(label="Even (x2)", style=ButtonStyle.primary, row=1)
    async def bet_even(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        if await self._deduct_and_verify(interaction):
            await self.run_spin(interaction, "parity", "even")
        else:
            self._processing = False

    @discord.ui.button(label="Odd (x2)", style=ButtonStyle.primary, row=1)
    async def bet_odd(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        if await self._deduct_and_verify(interaction):
            await self.run_spin(interaction, "parity", "odd")
        else:
            self._processing = False

    @discord.ui.button(label="Number (x35)", style=ButtonStyle.success, row=2)
    async def bet_number(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        await interaction.response.send_modal(RouletteNumberModal(self))


# ==============================================================================
#  BLACKJACK VIEW (Migrated from tavern.py)
# ==============================================================================


class BlackjackView(BaseView):
    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(bot, user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        self.guild_id = (
            str(parent_interaction.guild_id) if parent_interaction.guild_id else ""
        )
        self.player_hand = []
        self.dealer_hand = []
        self.deck = BlackjackLogic()
        self.game_over = False
        self._processing = False

    async def on_timeout(self):
        if not self.game_over:
            await self.bot.database.users.modify_gold(self.user_id, self.bet_amount)
            self.bot.state_manager.clear_active(self.user_id)
            try:
                await self.original_interaction.delete_original_response()
            except Exception:
                pass

    async def start_game(self):
        await self.bot.database.users.modify_gold(self.user_id, -self.bet_amount)
        self.player_hand = [self.deck.draw_card(), self.deck.draw_card()]
        self.dealer_hand = [self.deck.draw_card(), self.deck.draw_card()]

        if self.deck.calculate_score(self.player_hand) == 21:
            await self.end_game(result="blackjack")
        else:
            await self.update_table()

    async def update_table(self, interaction: Interaction = None):
        p_score = self.deck.calculate_score(self.player_hand)
        embed = discord.Embed(title="🃏 Blackjack Table", color=discord.Color.gold())
        embed.set_thumbnail(url=TAVERN_CASINO)

        if self.game_over:
            d_score = self.deck.calculate_score(self.dealer_hand)
            embed.add_field(
                name=f"Dealer's Hand ({d_score})",
                value=self.deck.format_hand(self.dealer_hand),
                inline=False,
            )
        else:
            embed.add_field(
                name="Dealer's Hand",
                value=self.deck.format_hand(self.dealer_hand, hide_second=True),
                inline=False,
            )

        embed.add_field(
            name=f"Your Hand ({p_score})",
            value=self.deck.format_hand(self.player_hand),
            inline=False,
        )
        embed.set_footer(text=f"Current Bet: {self.bet_amount:,} gold")

        # Instead of disabling all, clear items to remove Hit/Stand, we will add Restart later
        if self.game_over:
            self.clear_items()

        target = interaction.response if interaction else self.original_interaction
        if interaction:
            await target.edit_message(embed=embed, view=self)
        else:
            await target.edit_original_response(embed=embed, view=self)

    async def end_game(self, result: str, interaction: Interaction = None):
        self.game_over = True
        payout = 0
        msg = ""

        if result == "blackjack":
            payout = int(self.bet_amount * 2.5)
            msg = f"**BLACKJACK!** You win **{payout:,}** gold!"
        elif result == "win":
            payout = self.bet_amount * 2
            msg = f"**YOU WIN!** You receive **{payout:,}** gold!"
        elif result == "push":
            payout = self.bet_amount
            msg = "**PUSH!** Your bet is returned."
        elif result == "bust":
            msg = "**BUST!** You went over 21."
        elif result == "lose":
            msg = "**DEALER WINS!** Better luck next time."

        quest_msgs = []
        if payout > 0:
            await self.bot.database.users.modify_gold(self.user_id, payout)
            net_win = payout - self.bet_amount
            if net_win > 0:
                try:
                    from core.quests.mechanics import tick_quest_progress

                    guild_id = (
                        str(interaction.guild_id) if interaction else self.guild_id
                    )
                    quest_msgs = await tick_quest_progress(
                        self.bot, self.user_id, guild_id, "casino_win", value=net_win
                    )
                except Exception:
                    pass

        # Build the final embed from scratch — avoids Discord caching issues with
        # original_response() that cause stale embeds to appear after a restart.
        p_score = self.deck.calculate_score(self.player_hand)
        d_score = self.deck.calculate_score(self.dealer_hand)
        final_embed = discord.Embed(
            title="🃏 Blackjack Table",
            description=msg,
            color=discord.Color.gold(),
        )
        final_embed.set_thumbnail(url=TAVERN_CASINO)
        final_embed.add_field(
            name=f"Dealer's Hand ({d_score})",
            value=self.deck.format_hand(self.dealer_hand),
            inline=False,
        )
        final_embed.add_field(
            name=f"Your Hand ({p_score})",
            value=self.deck.format_hand(self.player_hand),
            inline=False,
        )
        if quest_msgs:
            final_embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )
        final_embed.set_footer(text=f"Bet: {self.bet_amount:,} gold")

        self.clear_items()
        # Add Restart Button
        restart_btn = Button(label="Play Again", style=ButtonStyle.primary, emoji="🔄")
        restart_btn.callback = self.restart_game
        self.add_item(restart_btn)

        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

        if interaction:
            await interaction.response.edit_message(embed=final_embed, view=self)
        else:
            await self.original_interaction.edit_original_response(
                embed=final_embed, view=self
            )

    async def restart_game(self, interaction: Interaction):
        if not await check_funds(self.bot, self.user_id, self.bet_amount, interaction):
            return

        # Create a FRESH view instance
        new_view = BlackjackView(
            self.bot, self.user_id, self.bet_amount, self.original_interaction
        )
        await interaction.response.edit_message(
            content="Shuffling deck...", embed=None, view=None
        )
        await new_view.start_game()
        self.stop()  # Kill old view

    async def quit_game(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    @discord.ui.button(label="Hit", style=ButtonStyle.primary, emoji="👊")
    async def hit_button(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.player_hand.append(self.deck.draw_card())
        self.double_button.disabled = True
        if self.deck.calculate_score(self.player_hand) > 21:
            await self.end_game("bust", interaction)
            # game over — _processing stays True (buttons cleared)
        else:
            await self.update_table(interaction)
            self._processing = False  # still in game

    @discord.ui.button(label="Stand", style=ButtonStyle.secondary, emoji="✋")
    async def stand_button(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        while self.deck.calculate_score(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.draw_card())
        p = self.deck.calculate_score(self.player_hand)
        d = self.deck.calculate_score(self.dealer_hand)
        if d > 21 or p > d:
            await self.end_game("win", interaction)
        elif p == d:
            await self.end_game("push", interaction)
        else:
            await self.end_game("lose", interaction)

    @discord.ui.button(label="Double Down", style=ButtonStyle.success, emoji="💰")
    async def double_button(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        user_data = await self.bot.database.users.get(
            self.user_id, interaction.guild.id
        )
        if user_data["gold"] < self.bet_amount:
            self._processing = False
            await interaction.response.send_message(
                "Insufficient funds.", ephemeral=True
            )
            return
        await self.bot.database.users.modify_gold(self.user_id, -self.bet_amount)
        self.bet_amount *= 2
        self.player_hand.append(self.deck.draw_card())
        if self.deck.calculate_score(self.player_hand) > 21:
            await self.end_game("bust", interaction)
        else:
            while self.deck.calculate_score(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.draw_card())
            p = self.deck.calculate_score(self.player_hand)
            d = self.deck.calculate_score(self.dealer_hand)
            if d > 21 or p > d:
                await self.end_game("win", interaction)
            elif p == d:
                await self.end_game("push", interaction)
            else:
                await self.end_game("lose", interaction)


# ==============================================================================
#  CRASH VIEW
# ==============================================================================


class CrashView(BaseView):
    # Cash Out must stay clickable while the multiplier loop runs inside
    # the start callback; this view manages its own is_running flags.
    concurrent_dispatch = True

    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(bot, user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction

        self.crash_point = CrashLogic.generate_crash_point()
        self.current_multiplier = 1.00
        self.is_running = False
        self.cashed_out = False
        self.task = None

    async def on_timeout(self):
        # If the view times out while running, we auto-lose the player (crashed while AFK)
        # unless they already cashed out.
        if self.is_running and not self.cashed_out:
            if self.task:
                self.task.cancel()
            self.bot.state_manager.clear_active(self.user_id)
            try:
                await self.original_interaction.edit_original_response(
                    content="⚠️ **Connection lost.** Rocket crashed while you were sleeping.",
                    embed=None,
                    view=None,
                )
            except Exception:
                pass
        elif not self.is_running:
            # Game didn't even start or finished cleanly
            self.bot.state_manager.clear_active(self.user_id)

    async def start_game(self):
        """Starts the game loop."""
        # Deduct Gold
        await self.bot.database.users.modify_gold(self.user_id, -self.bet_amount)

        self.is_running = True
        self.task = asyncio.create_task(self._game_loop())

    async def _game_loop(self):
        try:
            # Initial State
            embed = discord.Embed(title="🚀 Crash", color=discord.Color.blue())
            embed.description = (
                f"Current Multiplier: **1.00x**\nPotential Win: **{self.bet_amount:,}**"
            )
            embed.set_footer(
                text="⚠️ Risk increases significantly after 2.00x! Click Cash out before it crashes!"
            )

            await self.original_interaction.edit_original_response(
                embed=embed, view=self
            )
            await asyncio.sleep(1.0)  # Initial suspense

            # Instant Crash Check (1.00x)
            if self.crash_point <= 1.00:
                await self._handle_crash()
                return

            # Main Loop
            while self.is_running and not self.cashed_out:
                # Calculate next step
                # We use a fixed time step logic for simplicity in Discord
                next_multi = CrashLogic.get_next_multiplier(self.current_multiplier, 0)

                # Check for Crash
                if next_multi >= self.crash_point:
                    await self._handle_crash()
                    return

                # Update State
                self.current_multiplier = next_multi
                potential_win = int(self.bet_amount * self.current_multiplier)

                # Update UI
                # Visuals: Change color as it gets higher
                color = discord.Color.blue()
                if self.current_multiplier > 2.0:
                    color = discord.Color.gold()
                if self.current_multiplier > 5.0:
                    color = discord.Color.purple()

                embed.color = color
                embed.description = f"🚀 **{self.current_multiplier:.2f}x**\nPotential Win: **{potential_win:,}**"

                try:
                    await self.original_interaction.edit_original_response(
                        embed=embed, view=self
                    )
                except discord.NotFound:
                    self.is_running = False  # Message deleted, stop loop
                    return

                # Dynamic Sleep: Speed up updates slightly as it goes higher to create tension
                # But respect rate limits (min 1.0s safe)
                await asyncio.sleep(1.2)

        except asyncio.CancelledError:
            pass  # Task cancelled (usually via cash out)
        except Exception as e:
            self.bot.logger.error(f"Crash loop error: {e}")
            self.is_running = False
            if not self.cashed_out:
                try:
                    await self.bot.database.users.modify_gold(
                        self.user_id, self.bet_amount
                    )
                except Exception:
                    pass

    async def _add_restart_buttons(self):
        self.clear_items()

        restart_btn = Button(label="Play Again", style=ButtonStyle.primary, emoji="🔄")
        restart_btn.callback = self.restart_game
        self.add_item(restart_btn)

        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

        await self.original_interaction.edit_original_response(view=self)

    async def _handle_crash(self):
        self.is_running = False
        embed = discord.Embed(title="💥 CRASHED!", color=discord.Color.red())
        embed.description = f"The rocket crashed at **{self.crash_point:.2f}x**.\nYou lost **{self.bet_amount:,} gold**."

        await self.original_interaction.edit_original_response(
            embed=embed, view=None
        )  # clear buttons briefly
        await self._add_restart_buttons()

    @discord.ui.button(label="Cash Out", style=ButtonStyle.success, emoji="💰")
    async def cash_out_button(self, interaction: Interaction, button: Button):
        if not self.is_running or self.cashed_out:
            return await interaction.response.defer()

        self.cashed_out = True
        self.is_running = False
        if self.task:
            self.task.cancel()

        winnings = int(self.bet_amount * self.current_multiplier)
        await self.bot.database.users.modify_gold(self.user_id, winnings)
        net_win = winnings - self.bet_amount
        quest_msgs = []
        if net_win > 0:
            try:
                from core.quests.mechanics import tick_quest_progress

                quest_msgs = await tick_quest_progress(
                    self.bot,
                    self.user_id,
                    str(interaction.guild_id),
                    "casino_win",
                    value=net_win,
                )
            except Exception:
                pass

        embed = discord.Embed(title="✅ Cashed Out!", color=discord.Color.green())
        embed.description = f"You ejected at **{self.current_multiplier:.2f}x**!\n\n**Winnings:** {winnings:,} gold\n**Profit:** {winnings - self.bet_amount:,} gold"
        embed.add_field(
            name="Rocket Status",
            value=f"It would have crashed at **{self.crash_point:.2f}x**",
        )
        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )

        await interaction.response.edit_message(embed=embed, view=None)
        await self._add_restart_buttons()

    async def restart_game(self, interaction: Interaction):
        if not await check_funds(self.bot, self.user_id, self.bet_amount, interaction):
            return

        new_view = CrashView(
            self.bot, self.user_id, self.bet_amount, self.original_interaction
        )
        # Update embed to showing it's starting
        embed = discord.Embed(
            title="🚀 Preparing Launch...",
            description=f"Fueling up for a bet of **{self.bet_amount:,} gold**.",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=new_view)
        await new_view.start_game()
        self.stop()

    async def quit_game(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


# ==============================================================================
#  HORSE RACING VIEW
# ==============================================================================


class HorseRaceView(BaseView):
    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(bot, user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        self.race_logic = HorseRaceLogic()
        self.selected_horse_index = None
        self.task = None
        self._processing = False

    async def on_timeout(self):
        if not self.selected_horse_index and not self.task:
            self.bot.state_manager.clear_active(self.user_id)
            try:
                await self.original_interaction.delete_original_response()
            except Exception:
                pass

    async def start_race(self):
        # Disable buttons
        for child in self.children:
            child.disabled = True

        # Deduct Gold
        await self.bot.database.users.modify_gold(self.user_id, -self.bet_amount)

        embed = discord.Embed(title="🐎 And they're off!", color=discord.Color.green())
        embed.description = self.race_logic.get_race_string()
        await self.original_interaction.edit_original_response(
            embed=embed, view=None
        )  # Remove buttons during race

        # Animation Loop
        while not self.race_logic.advance_race():
            await asyncio.sleep(1.5)  # Update delay
            embed.description = self.race_logic.get_race_string()
            try:
                await self.original_interaction.edit_original_response(embed=embed)
            except Exception:
                # Message was deleted mid-race — refund the bet
                try:
                    await self.bot.database.users.modify_gold(
                        self.user_id, self.bet_amount
                    )
                except Exception:
                    pass
                self.bot.state_manager.clear_active(self.user_id)
                return

        # Race Finished
        winner = self.race_logic.winner
        picked_horse = self.race_logic.horses[self.selected_horse_index]

        embed.description = self.race_logic.get_race_string()
        embed.add_field(
            name="Winner",
            value=f"🏆 **{winner['name']}** {winner['emoji']} crosses the line!",
        )

        quest_msgs = []
        if winner == picked_horse:
            winnings = self.bet_amount * 4
            await self.bot.database.users.modify_gold(self.user_id, winnings)
            net_win = winnings - self.bet_amount
            if net_win > 0:
                try:
                    from core.quests.mechanics import tick_quest_progress

                    quest_msgs = await tick_quest_progress(
                        self.bot,
                        self.user_id,
                        str(self.original_interaction.guild_id),
                        "casino_win",
                        value=net_win,
                    )
                except Exception:
                    pass
            embed.color = discord.Color.gold()
            embed.add_field(
                name="Congratulations!",
                value=f"You bet on **{picked_horse['name']}** and won **{winnings:,} gold**!",
                inline=False,
            )
        else:
            embed.color = discord.Color.red()
            embed.add_field(
                name="Loss",
                value=f"You bet on **{picked_horse['name']}**. Better luck next time.",
                inline=False,
            )

        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )

        self.clear_items()

        restart_btn = Button(label="Play Again", style=ButtonStyle.primary, emoji="🔄")
        restart_btn.callback = self.restart_game
        self.add_item(restart_btn)

        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

        await self.original_interaction.edit_original_response(embed=embed, view=self)

    async def restart_game(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        if not await check_funds(self.bot, self.user_id, self.bet_amount, interaction):
            self._processing = False
            return

        # New view instance
        new_view = HorseRaceView(
            self.bot, self.user_id, self.bet_amount, self.original_interaction
        )

        # Reconstruct selection embed
        embed = discord.Embed(
            title="🐎 Horse Racing",
            description=f"Betting **{self.bet_amount:,} gold**.\nPick your champion! (4x Payout)",
            color=discord.Color.green(),
        )
        embed.add_field(name="1. Thunder Hoof 🐎", value="Balanced speed.", inline=True)
        embed.add_field(
            name="2. Lightning Bolt 🦄", value="High risk, high speed.", inline=True
        )
        embed.add_field(
            name="3. Old Reliable 🦓", value="Consistent pace.", inline=True
        )
        embed.add_field(name="4. Dark Horse 🐫", value="Unpredictable.", inline=True)

        await interaction.response.edit_message(embed=embed, view=new_view)
        self.stop()

    async def quit_game(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def _pick_horse(self, interaction: Interaction, index: int):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.selected_horse_index = index
        await interaction.response.defer()
        await self.start_race()

    @discord.ui.button(
        label="Thunder Hoof", emoji="🐎", style=ButtonStyle.primary, row=0
    )
    async def horse_1(self, interaction: Interaction, button: Button):
        await self._pick_horse(interaction, 0)

    @discord.ui.button(
        label="Lightning Bolt", emoji="🦄", style=ButtonStyle.primary, row=0
    )
    async def horse_2(self, interaction: Interaction, button: Button):
        await self._pick_horse(interaction, 1)

    @discord.ui.button(
        label="Old Reliable", emoji="🦓", style=ButtonStyle.primary, row=1
    )
    async def horse_3(self, interaction: Interaction, button: Button):
        await self._pick_horse(interaction, 2)

    @discord.ui.button(label="Dark Horse", emoji="🐫", style=ButtonStyle.primary, row=1)
    async def horse_4(self, interaction: Interaction, button: Button):
        await self._pick_horse(interaction, 3)
