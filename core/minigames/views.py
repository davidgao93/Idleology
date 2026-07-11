import asyncio
import random

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Modal, TextInput

from core.base_view import BaseView
from core.emojis import GOLD_COIN
from core.hall_of_firsts import triggers as hof_triggers
from core.images import CASINO_AUTHOR, TAVERN_CASINO
from core.npc_voices import get_quip
from core.pvp.engine import PvPEngine

from .logic import BlackjackLogic, CrashLogic, HorseRaceLogic, RouletteLogic


async def check_funds(bot, user_id, amount, interaction):
    user_data = await bot.database.users.get(user_id, interaction.guild.id)
    if user_data["gold"] < amount:
        await interaction.response.send_message(
            f"Insufficient funds to restart! You need {amount:,} gold.", ephemeral=True
        )
        return False
    return True


def casino_lobby_button(bot, user_id, bet_amount, row=None) -> Button:
    """A 'Casino Lobby' button shared by every game's end-of-round screen."""

    async def _callback(interaction: Interaction):
        # Deferred import: core.tavern.views imports this module at load
        # time, so importing it back at module scope here would be circular.
        from core.tavern.views import CasinoMenuView, build_casino_lobby_embed

        embed = build_casino_lobby_embed(bet_amount)
        view = CasinoMenuView(bot, user_id, bet_amount)
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    btn = Button(label="Casino Lobby", style=ButtonStyle.secondary, emoji="🎰", row=row)
    btn.callback = _callback
    return btn


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
            await hof_triggers.check_all_in(self.bot, self.user_id, payout)
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
        embed.add_field(
            name="Vespera",
            value=get_quip("casino_roulette_win" if won else "casino_roulette_loss"),
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
        self.add_item(casino_lobby_button(self.bot, self.user_id, self.bet_amount))

        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

        await interaction.response.edit_message(embed=embed, view=self)

    async def reset_table(self, interaction: Interaction):
        # Verify they still have money for the base bet size
        if not await check_funds(self.bot, self.user_id, self.bet_amount, interaction):
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

        await interaction.response.edit_message(embed=embed, view=self)

    async def quit_game(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    # --- UI BUTTONS ---
    @discord.ui.button(label="Red (x2)", style=ButtonStyle.danger, row=0)
    async def bet_red(self, interaction: Interaction, button: Button):
        if await self._deduct_and_verify(interaction):
            await self.run_spin(interaction, "color", "red")

    @discord.ui.button(label="Black (x2)", style=ButtonStyle.secondary, row=0)
    async def bet_black(self, interaction: Interaction, button: Button):
        if await self._deduct_and_verify(interaction):
            await self.run_spin(interaction, "color", "black")

    @discord.ui.button(label="Even (x2)", style=ButtonStyle.primary, row=1)
    async def bet_even(self, interaction: Interaction, button: Button):
        if await self._deduct_and_verify(interaction):
            await self.run_spin(interaction, "parity", "even")

    @discord.ui.button(label="Odd (x2)", style=ButtonStyle.primary, row=1)
    async def bet_odd(self, interaction: Interaction, button: Button):
        if await self._deduct_and_verify(interaction):
            await self.run_spin(interaction, "parity", "odd")

    @discord.ui.button(label="Number (x35)", style=ButtonStyle.success, row=2)
    async def bet_number(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(RouletteNumberModal(self))


# ==============================================================================
#  BLACKJACK VIEW (Migrated from tavern.py)
# ==============================================================================


class BlackjackView(BaseView):
    RESULT_LABELS = {
        "blackjack": "🂡 BLACKJACK!",
        "win": "✅ WIN",
        "push": "➖ PUSH",
        "lose": "❌ LOSE",
        "bust": "💥 BUST",
    }

    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(bot, user_id)
        self.bet_amount = (
            bet_amount  # original table stake; used for insurance math + rebets
        )
        self.original_interaction = parent_interaction
        self.guild_id = (
            str(parent_interaction.guild_id) if parent_interaction.guild_id else ""
        )
        self.deck = BlackjackLogic()
        self.dealer_hand = []
        self.hands = []
        self.active_hand = 0
        self.has_split = False
        self.insurance_bet = 0
        self.insurance_result = None
        self.insurance_profit = 0
        self.game_over = False

        self.hit_button = Button(label="Hit", style=ButtonStyle.primary, emoji="👊")
        self.hit_button.callback = self._on_hit
        self.stand_button = Button(
            label="Stand", style=ButtonStyle.secondary, emoji="✋"
        )
        self.stand_button.callback = self._on_stand
        self.double_button = Button(
            label="Double Down", style=ButtonStyle.success, emoji=GOLD_COIN
        )
        self.double_button.callback = self._on_double
        self.split_button = Button(label="Split", style=ButtonStyle.success, emoji="✂️")
        self.split_button.callback = self._on_split

    async def on_timeout(self):
        if not self.game_over:
            # Nothing has been settled yet — every gold amount deducted so far
            # (main bet(s) + insurance) is still "at risk" and must be refunded.
            at_risk = sum(h["bet"] for h in self.hands) + self.insurance_bet
            if at_risk:
                await self.bot.database.users.modify_gold(self.user_id, at_risk)
            self.bot.state_manager.clear_active(self.user_id)
            try:
                await self.original_interaction.delete_original_response()
            except Exception:
                pass

    async def start_game(self):
        await self.bot.database.users.modify_gold(self.user_id, -self.bet_amount)
        self.dealer_hand = [self.deck.draw_card(), self.deck.draw_card()]
        self.hands = [
            {
                "cards": [self.deck.draw_card(), self.deck.draw_card()],
                "bet": self.bet_amount,
                "done": False,
                "is_split_aces": False,
                "result": None,
            }
        ]

        if self.dealer_hand[0][0] == "A":
            await self._offer_insurance()
        else:
            await self._check_naturals()

    # --- Insurance ---

    async def _offer_insurance(self):
        self.clear_items()
        insure_btn = Button(
            label=f"Insurance ({self.bet_amount // 2:,})",
            style=ButtonStyle.secondary,
            emoji="🛡️",
        )
        insure_btn.callback = self._insurance_yes
        decline_btn = Button(label="No Insurance", style=ButtonStyle.secondary)
        decline_btn.callback = self._insurance_no
        self.add_item(insure_btn)
        self.add_item(decline_btn)

        hand = self.hands[0]
        embed = discord.Embed(title="🃏 Blackjack Table", color=discord.Color.gold())
        embed.set_thumbnail(url=TAVERN_CASINO)
        embed.add_field(
            name="Dealer's Hand",
            value=self.deck.format_hand(self.dealer_hand, hide_second=True),
            inline=False,
        )
        embed.add_field(
            name=f"Your Hand ({self.deck.calculate_score(hand['cards'])})",
            value=self.deck.format_hand(hand["cards"]),
            inline=False,
        )
        embed.add_field(
            name="Dealer shows an Ace!",
            value=(
                f"Insure your hand for **{self.bet_amount // 2:,} gold**? "
                "Pays 2:1 if the dealer has Blackjack."
            ),
            inline=False,
        )
        await self.original_interaction.edit_original_response(embed=embed, view=self)

    async def _insurance_yes(self, interaction: Interaction):
        cost = self.bet_amount // 2
        user_data = await self.bot.database.users.get(
            self.user_id, interaction.guild.id
        )
        if user_data["gold"] < cost:
            await interaction.response.send_message(
                "Insufficient funds for insurance.", ephemeral=True
            )
            return
        await self.bot.database.users.modify_gold(self.user_id, -cost)
        self.insurance_bet = cost
        await self._check_naturals(interaction)

    async def _insurance_no(self, interaction: Interaction):
        await self._check_naturals(interaction)

    # --- Natural blackjack check (dealer's hole card is "peeked" here, before
    # any player action, matching standard casino rules) ---

    async def _check_naturals(self, interaction: Interaction = None):
        dealer_natural = self.deck.calculate_score(self.dealer_hand) == 21
        player_natural = self.deck.calculate_score(self.hands[0]["cards"]) == 21

        if self.insurance_bet > 0:
            if dealer_natural:
                await self.bot.database.users.modify_gold(
                    self.user_id, self.insurance_bet * 3
                )
                self.insurance_result = "won"
                self.insurance_profit = self.insurance_bet * 2
            else:
                self.insurance_result = "lost"
                self.insurance_profit = -self.insurance_bet

        if dealer_natural or player_natural:
            if dealer_natural and player_natural:
                self.hands[0]["result"] = "push"
            elif player_natural:
                self.hands[0]["result"] = "blackjack"
            else:
                self.hands[0]["result"] = "lose"
            self.hands[0]["done"] = True
            await self._settle_round(interaction)
        else:
            await self._start_playing(interaction)

    # --- Player turn ---

    def _can_split(self) -> bool:
        if self.has_split or len(self.hands) != 1:
            return False
        cards = self.hands[0]["cards"]
        return len(cards) == 2 and cards[0][0] == cards[1][0]

    async def _start_playing(self, interaction: Interaction = None):
        self.clear_items()
        hand = self.hands[self.active_hand]
        self.add_item(self.hit_button)
        self.add_item(self.stand_button)
        if len(hand["cards"]) == 2 and not hand["is_split_aces"]:
            self.add_item(self.double_button)
        if self._can_split():
            self.add_item(self.split_button)
        await self._render_table(interaction)

    async def _render_table(self, interaction: Interaction = None):
        embed = discord.Embed(title="🃏 Blackjack Table", color=discord.Color.gold())
        embed.set_thumbnail(url=TAVERN_CASINO)
        embed.add_field(
            name="Dealer's Hand",
            value=self.deck.format_hand(self.dealer_hand, hide_second=True),
            inline=False,
        )
        multi = len(self.hands) > 1
        for idx, hand in enumerate(self.hands):
            score = self.deck.calculate_score(hand["cards"])
            marker = (
                " 👈" if multi and idx == self.active_hand and not hand["done"] else ""
            )
            label = (
                f"Hand {idx + 1} ({score}){marker}" if multi else f"Your Hand ({score})"
            )
            embed.add_field(
                name=label, value=self.deck.format_hand(hand["cards"]), inline=multi
            )
        total_bet = sum(h["bet"] for h in self.hands)
        footer = f"Current Bet: {total_bet:,} gold"
        if self.insurance_bet:
            footer += f" (+{self.insurance_bet:,} insurance)"
        embed.set_footer(text=footer)

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(
                embed=embed, view=self
            )

    async def _advance_or_resolve(self, interaction: Interaction):
        self.active_hand += 1
        if (
            self.active_hand < len(self.hands)
            and not self.hands[self.active_hand]["done"]
        ):
            await self._start_playing(interaction)
        else:
            await self._play_dealer(interaction)

    async def _on_hit(self, interaction: Interaction):
        hand = self.hands[self.active_hand]
        hand["cards"].append(self.deck.draw_card())
        if self.deck.calculate_score(hand["cards"]) > 21:
            hand["done"] = True
            hand["result"] = "bust"
            await self._advance_or_resolve(interaction)
        else:
            await self._start_playing(interaction)

    async def _on_stand(self, interaction: Interaction):
        self.hands[self.active_hand]["done"] = True
        await self._advance_or_resolve(interaction)

    async def _on_double(self, interaction: Interaction):
        hand = self.hands[self.active_hand]
        user_data = await self.bot.database.users.get(
            self.user_id, interaction.guild.id
        )
        if user_data["gold"] < hand["bet"]:
            await interaction.response.send_message(
                "Insufficient funds to double down.", ephemeral=True
            )
            return
        await self.bot.database.users.modify_gold(self.user_id, -hand["bet"])
        hand["bet"] *= 2
        hand["cards"].append(self.deck.draw_card())
        hand["done"] = True
        if self.deck.calculate_score(hand["cards"]) > 21:
            hand["result"] = "bust"
        await self._advance_or_resolve(interaction)

    async def _on_split(self, interaction: Interaction):
        hand = self.hands[self.active_hand]
        user_data = await self.bot.database.users.get(
            self.user_id, interaction.guild.id
        )
        if user_data["gold"] < hand["bet"]:
            await interaction.response.send_message(
                "Insufficient funds to split.", ephemeral=True
            )
            return
        await self.bot.database.users.modify_gold(self.user_id, -hand["bet"])

        card_a, card_b = hand["cards"]
        # Split aces are dealt exactly one card each and forced to stand —
        # standard rule, prevents chaining aces into multiple blackjacks.
        is_aces = card_a[0] == "A"
        self.hands = [
            {
                "cards": [card_a, self.deck.draw_card()],
                "bet": hand["bet"],
                "done": is_aces,
                "is_split_aces": is_aces,
                "result": None,
            },
            {
                "cards": [card_b, self.deck.draw_card()],
                "bet": hand["bet"],
                "done": is_aces,
                "is_split_aces": is_aces,
                "result": None,
            },
        ]
        self.has_split = True
        self.active_hand = 0

        if is_aces:
            await self._play_dealer(interaction)
        else:
            await self._start_playing(interaction)

    # --- Resolution ---

    DEALER_DRAW_DELAY = 1.5

    async def _play_dealer(self, interaction: Interaction):
        any_alive = any(h["result"] != "bust" for h in self.hands)
        if not any_alive:
            # Every hand already busted — the dealer's hand can't change the
            # outcome, so skip straight to settling (no animation needed).
            await self._settle_round(interaction)
            return

        self.clear_items()  # no input accepted while the dealer plays out
        await self._render_dealer_turn(interaction)
        await asyncio.sleep(self.DEALER_DRAW_DELAY)
        while self.deck.calculate_score(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.draw_card())
            await self._render_dealer_turn()
            await asyncio.sleep(self.DEALER_DRAW_DELAY)

        await self._settle_round()

    async def _render_dealer_turn(self, interaction: Interaction = None):
        dealer_score = self.deck.calculate_score(self.dealer_hand)
        embed = discord.Embed(title="🃏 Blackjack Table", color=discord.Color.gold())
        embed.set_thumbnail(url=TAVERN_CASINO)
        embed.add_field(
            name=f"Dealer's Hand ({dealer_score})",
            value=self.deck.format_hand(self.dealer_hand),
            inline=False,
        )
        multi = len(self.hands) > 1
        for idx, hand in enumerate(self.hands):
            score = self.deck.calculate_score(hand["cards"])
            label = f"Hand {idx + 1} ({score})" if multi else f"Your Hand ({score})"
            embed.add_field(
                name=label, value=self.deck.format_hand(hand["cards"]), inline=multi
            )
        embed.set_footer(
            text="Dealer is drawing..." if dealer_score < 17 else "Dealer stands."
        )

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(
                embed=embed, view=self
            )

    async def _settle_round(self, interaction: Interaction = None):
        self.game_over = True
        dealer_score = self.deck.calculate_score(self.dealer_hand)

        payout = 0
        for hand in self.hands:
            if hand["result"] is None:
                p_score = self.deck.calculate_score(hand["cards"])
                if dealer_score > 21 or p_score > dealer_score:
                    hand["result"] = "win"
                elif p_score == dealer_score:
                    hand["result"] = "push"
                else:
                    hand["result"] = "lose"

            if hand["result"] == "blackjack":
                payout += int(hand["bet"] * 2.5)
            elif hand["result"] == "win":
                payout += hand["bet"] * 2
            elif hand["result"] == "push":
                payout += hand["bet"]

        if payout > 0:
            await self.bot.database.users.modify_gold(self.user_id, payout)
            await hof_triggers.check_all_in(self.bot, self.user_id, payout)

        total_wagered = sum(h["bet"] for h in self.hands)
        net_win = (payout - total_wagered) + self.insurance_profit

        quest_msgs = []
        if net_win > 0:
            try:
                from core.quests.mechanics import tick_quest_progress

                guild_id = str(interaction.guild_id) if interaction else self.guild_id
                quest_msgs = await tick_quest_progress(
                    self.bot, self.user_id, guild_id, "casino_win", value=net_win
                )
            except Exception:
                pass

        embed = self._build_result_embed(dealer_score, net_win, quest_msgs)
        self._add_result_buttons()

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(
                embed=embed, view=self
            )

    def _build_result_embed(self, dealer_score, net_win, quest_msgs):
        embed = discord.Embed(title="🃏 Blackjack Table", color=discord.Color.gold())
        embed.set_thumbnail(url=TAVERN_CASINO)
        embed.add_field(
            name=f"Dealer's Hand ({dealer_score})",
            value=self.deck.format_hand(self.dealer_hand),
            inline=False,
        )

        multi = len(self.hands) > 1
        for idx, hand in enumerate(self.hands):
            score = self.deck.calculate_score(hand["cards"])
            label = f"Hand {idx + 1} ({score})" if multi else f"Your Hand ({score})"
            tag = self.RESULT_LABELS.get(hand["result"], "")
            value = (
                f"{self.deck.format_hand(hand['cards'])}\n{tag} — bet {hand['bet']:,}"
            )
            embed.add_field(name=label, value=value, inline=multi)

        if self.insurance_bet:
            if self.insurance_result == "won":
                embed.add_field(
                    name="🛡️ Insurance",
                    value=f"Dealer had Blackjack! Insurance paid **{self.insurance_bet * 2:,}** gold profit.",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🛡️ Insurance",
                    value=f"Dealer didn't have Blackjack. Lost the **{self.insurance_bet:,}** gold insurance stake.",
                    inline=False,
                )

        summary = (
            f"**Net Profit:** {net_win:,} gold"
            if net_win >= 0
            else f"**Net Loss:** {-net_win:,} gold"
        )
        embed.add_field(name="Result", value=summary, inline=False)

        if net_win != 0:
            embed.add_field(
                name="Vespera",
                value=get_quip(
                    "casino_blackjack_win" if net_win > 0 else "casino_blackjack_loss"
                ),
                inline=False,
            )

        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )

        total_bet = sum(h["bet"] for h in self.hands) + self.insurance_bet
        embed.set_footer(text=f"Total Wagered: {total_bet:,} gold")
        return embed

    def _add_result_buttons(self):
        self.clear_items()

        same_btn = Button(
            label="Play Again", style=ButtonStyle.primary, emoji="🔄", row=0
        )
        same_btn.callback = self._rebet_same
        self.add_item(same_btn)

        half_btn = Button(
            label="Half Bet", style=ButtonStyle.secondary, emoji="🔽", row=0
        )
        half_btn.callback = self._rebet_half
        self.add_item(half_btn)

        double_btn = Button(
            label="Double Bet", style=ButtonStyle.secondary, emoji="🔼", row=0
        )
        double_btn.callback = self._rebet_double
        self.add_item(double_btn)

        max_btn = Button(label="Max Bet", style=ButtonStyle.danger, emoji="💯", row=0)
        max_btn.callback = self._rebet_max
        self.add_item(max_btn)

        self.add_item(
            casino_lobby_button(self.bot, self.user_id, self.bet_amount, row=1)
        )

        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=1)
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

    # --- Rebet flow ---

    async def _rebet(self, interaction: Interaction, amount: int):
        if not await check_funds(self.bot, self.user_id, amount, interaction):
            return
        new_view = BlackjackView(
            self.bot, self.user_id, amount, self.original_interaction
        )
        await interaction.response.defer()
        await new_view.start_game()
        self.stop()

    async def _rebet_same(self, interaction: Interaction):
        await self._rebet(interaction, self.bet_amount)

    async def _rebet_half(self, interaction: Interaction):
        await self._rebet(interaction, max(1, self.bet_amount // 2))

    async def _rebet_double(self, interaction: Interaction):
        await self._rebet(interaction, self.bet_amount * 2)

    async def _rebet_max(self, interaction: Interaction):
        user_data = await self.bot.database.users.get(
            self.user_id, interaction.guild.id
        )
        gold = user_data["gold"]
        if gold <= 0:
            await interaction.response.send_message(
                "You have no gold to bet.", ephemeral=True
            )
            return
        await self._rebet(interaction, gold)

    async def quit_game(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


# ==============================================================================
#  CRASH VIEW
# ==============================================================================

_FLIGHT_TRACK_WIDTH = 12
_FLIGHT_STAR_POSITIONS = (2, 5, 9)


def _build_flight_track(multiplier: float, crashed: bool = False) -> str:
    """A small emoji lane depicting the rocket's flight, in the same style as
    the horse race track. There's no fixed finish line — the crash point is
    hidden and unbounded — so the rocket just loops across an infinite
    starfield, moving further per tick as the multiplier (and pace of growth)
    climbs. On crash, the rocket's frame is swapped for an explosion."""
    progress = int((multiplier - 1.0) * 7) % _FLIGHT_TRACK_WIDTH
    lane = ["➖"] * _FLIGHT_TRACK_WIDTH
    for idx in _FLIGHT_STAR_POSITIONS:
        if idx != progress:
            lane[idx] = "✨"
    lane[progress] = "💥" if crashed else "🚀"
    return "`" + "".join(lane) + "`"


def _validate_auto_cashout_target(raw: str):
    """Returns (target, None) on success or (None, error_message) on failure."""
    try:
        target = float(raw)
    except ValueError:
        return None, "Please enter a valid number, e.g. 2.5"
    if target <= 1.0:
        return None, "Target must be greater than 1.00x."
    return round(min(target, 100.0), 2), None


class PreLaunchAutoCashOutModal(Modal, title="Set Auto Cash-Out"):
    target_input = TextInput(
        label="Target multiplier (e.g. 2.50)",
        placeholder="2.50",
        min_length=1,
        max_length=6,
        required=True,
    )

    def __init__(self, parent_view: "CrashLaunchView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        target, error = _validate_auto_cashout_target(self.target_input.value)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        self.parent_view.auto_cashout = target
        await interaction.response.edit_message(
            embed=self.parent_view._build_embed(), view=self.parent_view
        )


class CrashLaunchView(BaseView):
    """Pre-launch pad: lets the player arm an Auto Cash-Out target before the
    multiplier starts climbing, since fumbling with a modal mid-flight is
    exactly the friction this screen exists to avoid."""

    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(bot, user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        self.auto_cashout = None

    async def on_timeout(self):
        # No gold has been taken yet — nothing to refund, just tidy up.
        self.bot.state_manager.clear_active(self.user_id)
        try:
            await self.original_interaction.delete_original_response()
        except Exception:
            pass

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🚀 Crash — Launch Pad",
            description=(
                f"Betting **{self.bet_amount:,} gold**.\n{_build_flight_track(1.0)}"
            ),
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=TAVERN_CASINO)
        if self.auto_cashout:
            embed.add_field(
                name="🎯 Auto Cash-Out",
                value=f"Armed at **{self.auto_cashout:.2f}x**",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎯 Auto Cash-Out",
                value="Not set — you'll need to Cash Out manually.",
                inline=False,
            )
        embed.set_footer(
            text="Set an optional Auto Cash-Out target, then Launch when ready."
        )
        return embed

    @discord.ui.button(
        label="Set Auto Cash-Out", style=ButtonStyle.secondary, emoji="🎯"
    )
    async def set_auto(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(PreLaunchAutoCashOutModal(self))

    @discord.ui.button(label="Launch", style=ButtonStyle.success, emoji="🚀")
    async def launch(self, interaction: Interaction, button: Button):
        if not await check_funds(self.bot, self.user_id, self.bet_amount, interaction):
            return

        view = CrashView(
            self.bot, self.user_id, self.bet_amount, self.original_interaction
        )
        view.auto_cashout = self.auto_cashout
        embed = discord.Embed(
            title="🚀 Preparing Launch...",
            description=f"Fueling up for a bet of **{self.bet_amount:,} gold**.",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)
        await view.start_game()
        self.stop()

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class CrashView(BaseView):
    # Cash Out must stay clickable while the multiplier loop runs inside
    # the start callback; this view manages its own is_running flags.
    concurrent_dispatch = True

    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(bot, user_id)
        self.original_bet = bet_amount  # never mutated; used for profit accounting
        self.bet_amount = bet_amount  # remaining at-risk stake (shrinks on Bank Half)
        self.original_interaction = parent_interaction
        self.guild_id = (
            str(parent_interaction.guild_id) if parent_interaction.guild_id else ""
        )

        self.crash_point = CrashLogic.generate_crash_point()
        self.current_multiplier = 1.00
        self.is_running = False
        self.cashed_out = False
        self.task = None

        self.auto_cashout = None
        self.banked_half = False
        self.banked_winnings = 0

        # concurrent_dispatch bypasses BaseView's central re-entry guard, so
        # every mutating button here needs its own manual guard.
        self._restarting = False
        self._closing = False

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
                f"Current Multiplier: **1.00x**\n"
                f"{_build_flight_track(1.0)}\n"
                f"Potential Win: **{self.bet_amount:,}**"
            )
            if self.auto_cashout:
                footer = (
                    f"🎯 Auto Cash-Out armed at {self.auto_cashout:.2f}x. "
                    "Bank Half anytime for extra safety."
                )
            else:
                footer = (
                    "⚠️ Risk increases significantly after 2.00x! Cash out before "
                    "it crashes — or Bank Half for extra safety."
                )
            embed.set_footer(text=footer)

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

                if self.auto_cashout and self.current_multiplier >= self.auto_cashout:
                    await self._finalize_cashout(self.current_multiplier, auto=True)
                    return

                potential_win = int(self.bet_amount * self.current_multiplier)

                # Update UI
                # Visuals: Change color as it gets higher
                color = discord.Color.blue()
                if self.current_multiplier > 2.0:
                    color = discord.Color.gold()
                if self.current_multiplier > 5.0:
                    color = discord.Color.purple()

                embed.color = color
                embed.description = (
                    f"🚀 **{self.current_multiplier:.2f}x**\n"
                    f"{_build_flight_track(self.current_multiplier)}\n"
                    f"Potential Win: **{potential_win:,}**"
                )

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
        self.add_item(casino_lobby_button(self.bot, self.user_id, self.original_bet))

        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

        await self.original_interaction.edit_original_response(view=self)

    async def _handle_crash(self):
        self.is_running = False

        # Anything already banked via Bank Half stays safe even though the
        # remaining ride crashed — only self.bet_amount (the remainder) is lost.
        net_result = self.banked_winnings - self.original_bet
        quest_msgs = []
        if net_result > 0:
            try:
                from core.quests.mechanics import tick_quest_progress

                quest_msgs = await tick_quest_progress(
                    self.bot,
                    self.user_id,
                    self.guild_id,
                    "casino_win",
                    value=net_result,
                )
            except Exception:
                pass

        embed = discord.Embed(title="💥 CRASHED!", color=discord.Color.red())
        lines = [
            f"The rocket crashed at **{self.crash_point:.2f}x**.",
            _build_flight_track(self.crash_point, crashed=True),
            f"You lost **{self.bet_amount:,} gold**.",
        ]
        if self.banked_winnings:
            lines.append(
                f"You had already banked **{self.banked_winnings:,} gold** earlier — that stays safe."
            )
            lines.append(f"**Net Result:** {net_result:+,} gold")
        embed.description = "\n".join(lines)
        embed.add_field(
            name="Vespera", value=get_quip("casino_crash_loss"), inline=False
        )
        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )

        await self.original_interaction.edit_original_response(
            embed=embed, view=None
        )  # clear buttons briefly
        await self._add_restart_buttons()

    async def _finalize_cashout(
        self, multiplier: float, interaction: Interaction = None, auto: bool = False
    ):
        self.cashed_out = True
        self.is_running = False

        winnings = int(self.bet_amount * multiplier)
        await self.bot.database.users.modify_gold(self.user_id, winnings)
        await hof_triggers.check_all_in(self.bot, self.user_id, winnings)

        total_payout = winnings + self.banked_winnings
        net_win = total_payout - self.original_bet
        quest_msgs = []
        if net_win > 0:
            try:
                from core.quests.mechanics import tick_quest_progress

                guild_id = str(interaction.guild_id) if interaction else self.guild_id
                quest_msgs = await tick_quest_progress(
                    self.bot, self.user_id, guild_id, "casino_win", value=net_win
                )
            except Exception:
                pass

        title = "🎯 Auto Cash-Out!" if auto else "✅ Cashed Out!"
        embed = discord.Embed(title=title, color=discord.Color.green())
        lines = [
            f"You ejected at **{multiplier:.2f}x**!",
            _build_flight_track(multiplier),
            "",
        ]
        if self.banked_winnings:
            lines.append(f"**Banked Earlier:** {self.banked_winnings:,} gold")
            lines.append(f"**Final Cash-Out:** {winnings:,} gold")
            lines.append(f"**Total Winnings:** {total_payout:,} gold")
        else:
            lines.append(f"**Winnings:** {winnings:,} gold")
        lines.append(f"**Profit:** {net_win:,} gold")
        embed.description = "\n".join(lines)
        embed.add_field(
            name="Rocket Status",
            value=f"It would have crashed at **{self.crash_point:.2f}x**",
        )
        embed.add_field(
            name="Vespera", value=get_quip("casino_crash_win"), inline=False
        )
        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )

        self.clear_items()
        if interaction:
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await self.original_interaction.edit_original_response(
                embed=embed, view=None
            )
        await self._add_restart_buttons()

    @discord.ui.button(label="Cash Out", style=ButtonStyle.success, emoji=GOLD_COIN)
    async def cash_out_button(self, interaction: Interaction, button: Button):
        if not self.is_running or self.cashed_out:
            return await interaction.response.defer()

        if self.task:
            self.task.cancel()
        await self._finalize_cashout(self.current_multiplier, interaction=interaction)

    @discord.ui.button(label="Bank Half", style=ButtonStyle.secondary, emoji="🏦")
    async def bank_half_button(self, interaction: Interaction, button: Button):
        if not self.is_running or self.cashed_out or self.banked_half:
            return await interaction.response.defer()
        self.banked_half = True  # close the race window before any await

        secured_stake = self.bet_amount // 2
        payout = int(secured_stake * self.current_multiplier)
        self.bet_amount -= secured_stake
        self.banked_winnings += payout

        await self.bot.database.users.modify_gold(self.user_id, payout)
        await hof_triggers.check_all_in(self.bot, self.user_id, payout)

        self.bank_half_button.disabled = True
        self.bank_half_button.label = "Halved ✅"

        await interaction.response.send_message(
            f"🏦 Banked **{secured_stake:,} gold** of your stake at "
            f"**{self.current_multiplier:.2f}x** for **{payout:,} gold**. "
            f"Riding the remaining **{self.bet_amount:,} gold** stake.",
            ephemeral=True,
        )

    async def restart_game(self, interaction: Interaction):
        if self._restarting:
            return await interaction.response.defer()
        self._restarting = True

        if not await check_funds(
            self.bot, self.user_id, self.original_bet, interaction
        ):
            self._restarting = False
            return

        # Back to the launch pad, not straight into a new run — same reasoning
        # as the initial entry point: let the player arm Auto Cash-Out calmly
        # instead of forcing it into the live, ticking screen.
        launch_view = CrashLaunchView(
            self.bot, self.user_id, self.original_bet, self.original_interaction
        )
        await interaction.response.edit_message(
            embed=launch_view._build_embed(), view=launch_view
        )
        self.stop()

    async def quit_game(self, interaction: Interaction):
        if self._closing:
            return await interaction.response.defer()
        self._closing = True

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
        embed.description = self.race_logic.get_race_string(self.selected_horse_index)
        await self.original_interaction.edit_original_response(
            embed=embed, view=None
        )  # Remove buttons during race

        # Animation Loop
        while not self.race_logic.advance_race():
            await asyncio.sleep(1.5)  # Update delay
            embed.description = self.race_logic.get_race_string(
                self.selected_horse_index
            )
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

        embed.description = self.race_logic.get_race_string(self.selected_horse_index)
        embed.add_field(
            name="Winner",
            value=f"🏆 **{winner['name']}** {winner['emoji']} crosses the line!",
        )

        quest_msgs = []
        if winner == picked_horse:
            winnings = self.bet_amount * 4
            await self.bot.database.users.modify_gold(self.user_id, winnings)
            await hof_triggers.check_all_in(self.bot, self.user_id, winnings)
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

        embed.add_field(
            name="Vespera",
            value=get_quip(
                "casino_horse_win" if winner == picked_horse else "casino_horse_loss"
            ),
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
        self.add_item(casino_lobby_button(self.bot, self.user_id, self.bet_amount))

        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

        await self.original_interaction.edit_original_response(embed=embed, view=self)

    async def restart_game(self, interaction: Interaction):
        if not await check_funds(self.bot, self.user_id, self.bet_amount, interaction):
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


# ==============================================================================
#  1V1 VIEW
# ==============================================================================


class OneVOneView(BaseView):
    """Solo push-your-luck brawl against Vespera, the casino dealer. Damage
    scales with the attacker's OWN missing HP for both sides (lower HP =
    harder hits), reusing core/pvp/engine.py's duel formula. Vespera never
    eats — she always swings — while the player has a limited number of Eat
    charges to out-sustain her."""

    MAX_EATS = 3
    MISS_CHANCE = 30  # percent, matches core/pvp's duel convention
    OPPONENT_NAME = "Vespera"

    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(bot, user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        self.guild_id = (
            str(parent_interaction.guild_id) if parent_interaction.guild_id else ""
        )

        self.player_hp = 100
        self.opponent_hp = 100
        self.eats_used = 0
        self.game_over = False
        self.log = get_quip("casino_1v1")

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
        await self._render()

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="⚔️ 1v1", color=discord.Color.dark_red())
        embed.set_author(name="Vespera", icon_url=CASINO_AUTHOR)
        embed.set_thumbnail(url=TAVERN_CASINO)
        embed.add_field(name="You", value=f"❤️ {self.player_hp} HP", inline=True)
        embed.add_field(
            name=self.OPPONENT_NAME, value=f"❤️ {self.opponent_hp} HP", inline=True
        )
        embed.add_field(name="Log", value=self.log, inline=False)
        embed.set_footer(
            text=(
                f"Bet: {self.bet_amount:,} gold | "
                f"Eats remaining: {self.MAX_EATS - self.eats_used}"
            )
        )
        return embed

    async def _render(self, interaction: Interaction = None):
        self.eat_button.disabled = self.eats_used >= self.MAX_EATS
        embed = self._build_embed()
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(
                embed=embed, view=self
            )

    def _resolve_attack(self, attacker_hp: int):
        """Returns (missed, damage). Damage scales with the attacker's own
        current HP — the lower it is, the harder they swing (Dharok-style)."""
        if random.randint(1, 100) <= self.MISS_CHANCE:
            return True, 0
        return False, PvPEngine.calculate_damage(attacker_hp)

    async def _process_round(self, interaction: Interaction, action: str):
        logs = []

        if action == "hit":
            missed, dmg = self._resolve_attack(self.player_hp)
            if missed:
                logs.append("💨 You swing and miss!")
            else:
                self.opponent_hp = max(0, self.opponent_hp - dmg)
                logs.append(
                    f"💥 You hit **{self.OPPONENT_NAME}** for **{dmg}** damage!"
                )
        else:  # eat
            self.eats_used += 1
            heal = PvPEngine.calculate_heal()
            old_hp = self.player_hp
            self.player_hp = min(100, self.player_hp + heal)
            healed = self.player_hp - old_hp
            eats_left = self.MAX_EATS - self.eats_used
            logs.append(f"🍗 You eat, healing **{healed}** HP. ({eats_left} eats left)")

        if self.opponent_hp <= 0:
            await self._end_game(interaction, won=True, logs=logs)
            return

        # The opponent never eats — it always swings, no matter its own HP.
        missed, dmg = self._resolve_attack(self.opponent_hp)
        if missed:
            logs.append(f"💨 **{self.OPPONENT_NAME}** swings and misses!")
        else:
            self.player_hp = max(0, self.player_hp - dmg)
            logs.append(f"🩸 **{self.OPPONENT_NAME}** hits you for **{dmg}** damage!")

        self.log = "\n".join(logs)

        if self.player_hp <= 0:
            await self._end_game(interaction, won=False, logs=logs)
            return

        await self._render(interaction)

    async def _end_game(self, interaction: Interaction, won: bool, logs: list):
        self.game_over = True
        quest_msgs = []

        if won:
            payout = self.bet_amount * 2
            await self.bot.database.users.modify_gold(self.user_id, payout)
            net_win = payout - self.bet_amount
            logs.append(
                f"🏆 **{self.OPPONENT_NAME} falls!** You win **{payout:,} gold**!"
            )
            logs.append(get_quip("casino_1v1_win"))
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
        else:
            logs.append(
                f"💀 **You fall!** You lose your **{self.bet_amount:,} gold** bet."
            )
            logs.append(get_quip("casino_1v1_loss"))

        self.log = "\n".join(logs)
        embed = self._build_embed()
        embed.color = discord.Color.gold() if won else discord.Color.red()
        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )

        self.clear_items()
        same_btn = Button(label="Play Again", style=ButtonStyle.primary, emoji="🔄")
        same_btn.callback = self._rebet_same
        self.add_item(same_btn)
        self.add_item(casino_lobby_button(self.bot, self.user_id, self.bet_amount))
        quit_btn = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        quit_btn.callback = self.quit_game
        self.add_item(quit_btn)

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.original_interaction.edit_original_response(
                embed=embed, view=self
            )

    @discord.ui.button(label="Hit", style=ButtonStyle.danger, emoji="⚔️")
    async def hit_button(self, interaction: Interaction, button: Button):
        await self._process_round(interaction, "hit")

    @discord.ui.button(label="Eat", style=ButtonStyle.success, emoji="🍗")
    async def eat_button(self, interaction: Interaction, button: Button):
        if self.eats_used >= self.MAX_EATS:
            return await interaction.response.defer()
        await self._process_round(interaction, "eat")

    async def _rebet_same(self, interaction: Interaction):
        if not await check_funds(self.bot, self.user_id, self.bet_amount, interaction):
            return
        new_view = OneVOneView(
            self.bot, self.user_id, self.bet_amount, self.original_interaction
        )
        await interaction.response.defer()
        await new_view.start_game()
        self.stop()

    async def quit_game(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
