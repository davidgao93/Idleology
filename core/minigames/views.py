import discord
from discord import Interaction, ButtonStyle, TextStyle
from discord.ui import View, Button, Modal, TextInput
from .logic import BlackjackLogic, RouletteLogic, CrashLogic, HorseRaceLogic
import asyncio 
# ==============================================================================
#  ROULETTE COMPONENTS
# ==============================================================================

class RouletteNumberModal(Modal, title="Bet on a Number"):
    number_input = TextInput(
        label="Pick a number (0-36)", 
        placeholder="e.g. 7", 
        min_length=1, 
        max_length=2,
        required=True
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.number_input.value)
            if 0 <= val <= 36:
                await interaction.response.defer()
                await self.parent_view.run_spin(interaction, "number", str(val))
            else:
                await interaction.response.send_message("Number must be between 0 and 36.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter a valid integer.", ephemeral=True)

class RouletteView(View):
    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = str(user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        self.game_over = False

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if not self.game_over:
            # Only delete, do not refund yet as money is only taken on button press
            try: await self.original_interaction.delete_original_response()
            except: pass
        self.bot.state_manager.clear_active(self.user_id)

    async def _deduct_and_verify(self, interaction: Interaction) -> bool:
        # Verify funds
        user_data = await self.bot.database.users.get(self.user_id, interaction.guild.id)
        if user_data[6] < self.bet_amount:
            await interaction.response.send_message("Insufficient funds!", ephemeral=True)
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
        if won:
            multiplier = 35 if bet_type == "number" else 2 # 35:1 for number, 1:1 (2x return) for color/parity
            payout = self.bet_amount * multiplier
            await self.bot.database.users.modify_gold(self.user_id, payout)

        # 4. Build Embed
        color_map = {
            "red": discord.Color.red(),
            "black": discord.Color.default(), # Dark greyish
            "green": discord.Color.green()
        }
        
        embed = discord.Embed(title=f"Roulette Results {emoji}", color=color_map[result_color])
        embed.description = f"The ball lands on **{result_num} ({result_color.title()})**!"
        
        target_display = bet_target.title() if bet_type != "number" else str(bet_target)
        
        if won:
            embed.add_field(name="Winner!", value=f"You bet on **{target_display}** and won **{payout:,} gold**!", inline=False)
        else:
            embed.add_field(name="Loss", value=f"You bet on **{target_display}**. Better luck next time.", inline=False)
            
        embed.set_footer(text="Game Over")
        
        # Clear buttons
        await self.original_interaction.edit_original_response(embed=embed, view=None)
        
        # If this was called via Modal (interaction is deferred), use followup
        # If called via Button (interaction is direct), use response check
        if not interaction.response.is_done():
            await interaction.response.defer() # Just acknowledge button press if handled above

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
        if await self._deduct_and_verify(interaction):
            # Launch Modal
            await interaction.response.send_modal(RouletteNumberModal(self))

# ==============================================================================
#  BLACKJACK VIEW (Migrated from tavern.py)
# ==============================================================================

class BlackjackView(View):
    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = str(user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        self.player_hand = []
        self.dealer_hand = []
        self.deck = BlackjackLogic()
        self.game_over = False

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if not self.game_over:
            await self.bot.database.users.modify_gold(self.user_id, self.bet_amount)
            self.bot.state_manager.clear_active(self.user_id)
            try: await self.original_interaction.delete_original_response()
            except: pass

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
        embed.set_thumbnail(url="https://i.imgur.com/D8HlsQX.jpeg")
        
        if self.game_over:
            d_score = self.deck.calculate_score(self.dealer_hand)
            embed.add_field(name=f"Dealer's Hand ({d_score})", value=self.deck.format_hand(self.dealer_hand), inline=False)
        else:
            embed.add_field(name="Dealer's Hand", value=self.deck.format_hand(self.dealer_hand, hide_second=True), inline=False)

        embed.add_field(name=f"Your Hand ({p_score})", value=self.deck.format_hand(self.player_hand), inline=False)
        embed.set_footer(text=f"Current Bet: {self.bet_amount:,} gold")

        if self.game_over:
            for child in self.children: child.disabled = True
        
        target = interaction.response if interaction else self.original_interaction
        if interaction: await target.edit_message(embed=embed, view=self)
        else: await target.edit_original_response(embed=embed, view=self)

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
        elif result == "bust": msg = "**BUST!** You went over 21."
        elif result == "lose": msg = "**DEALER WINS!** Better luck next time."

        if payout > 0:
            await self.bot.database.users.modify_gold(self.user_id, payout)

        await self.update_table(interaction)
        
        final_embed = (await self.original_interaction.original_response()).embeds[0]
        final_embed.description = msg
        if result in ["win", "blackjack"]: final_embed.color = discord.Color.green()
        elif result == "push": final_embed.color = discord.Color.light_grey()
        else: final_embed.color = discord.Color.red()
        
        target_func = interaction.edit_original_response if interaction else self.original_interaction.edit_original_response
        await target_func(embed=final_embed, view=self)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    @discord.ui.button(label="Hit", style=ButtonStyle.primary, emoji="👊")
    async def hit_button(self, interaction: Interaction, button: Button):
        self.player_hand.append(self.deck.draw_card())
        self.double_button.disabled = True
        if self.deck.calculate_score(self.player_hand) > 21: await self.end_game("bust", interaction)
        else: await self.update_table(interaction)

    @discord.ui.button(label="Stand", style=ButtonStyle.secondary, emoji="✋")
    async def stand_button(self, interaction: Interaction, button: Button):
        while self.deck.calculate_score(self.dealer_hand) < 17: self.dealer_hand.append(self.deck.draw_card())
        p = self.deck.calculate_score(self.player_hand)
        d = self.deck.calculate_score(self.dealer_hand)
        if d > 21 or p > d: await self.end_game("win", interaction)
        elif p == d: await self.end_game("push", interaction)
        else: await self.end_game("lose", interaction)

    @discord.ui.button(label="Double Down", style=ButtonStyle.success, emoji="💰")
    async def double_button(self, interaction: Interaction, button: Button):
        user_data = await self.bot.database.users.get(self.user_id, interaction.guild.id)
        if user_data[6] < self.bet_amount:
            await interaction.response.send_message("Insufficient funds.", ephemeral=True)
            return
        await self.bot.database.users.modify_gold(self.user_id, -self.bet_amount)
        self.bet_amount *= 2
        self.player_hand.append(self.deck.draw_card())
        if self.deck.calculate_score(self.player_hand) > 21: await self.end_game("bust", interaction)
        else:
            while self.deck.calculate_score(self.dealer_hand) < 17: self.dealer_hand.append(self.deck.draw_card())
            p = self.deck.calculate_score(self.player_hand)
            d = self.deck.calculate_score(self.dealer_hand)
            if d > 21 or p > d: await self.end_game("win", interaction)
            elif p == d: await self.end_game("push", interaction)
            else: await self.end_game("lose", interaction)


# ==============================================================================
#  CRASH VIEW
# ==============================================================================

class CrashView(View):
    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = str(user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        
        self.crash_point = CrashLogic.generate_crash_point()
        self.current_multiplier = 1.00
        self.is_running = False
        self.cashed_out = False
        self.task = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        # If the view times out while running, we auto-lose the player (crashed while AFK)
        # unless they already cashed out.
        if self.is_running and not self.cashed_out:
            if self.task: self.task.cancel()
            self.bot.state_manager.clear_active(self.user_id)
            try:
                await self.original_interaction.edit_original_response(
                    content="⚠️ **Connection lost.** Rocket crashed while you were sleeping.", 
                    embed=None, view=None
                )
            except: pass
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
            embed.description = f"Current Multiplier: **1.00x**\nPotential Win: **{self.bet_amount:,}**"
            embed.set_footer(text="Click 'Cash Out' before it crashes!")
            
            await self.original_interaction.edit_original_response(embed=embed, view=self)
            await asyncio.sleep(1.0) # Initial suspense

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
                if self.current_multiplier > 2.0: color = discord.Color.gold()
                if self.current_multiplier > 5.0: color = discord.Color.purple()
                
                embed.color = color
                embed.description = f"🚀 **{self.current_multiplier:.2f}x**\nPotential Win: **{potential_win:,}**"
                
                try:
                    await self.original_interaction.edit_original_response(embed=embed, view=self)
                except discord.NotFound:
                    self.is_running = False # Message deleted, stop loop
                    return
                
                # Dynamic Sleep: Speed up updates slightly as it goes higher to create tension
                # But respect rate limits (min 1.0s safe)
                await asyncio.sleep(1.2)

        except asyncio.CancelledError:
            pass # Task cancelled (usually via cash out)
        except Exception as e:
            self.bot.logger.error(f"Crash loop error: {e}")
            self.is_running = False

    async def _handle_crash(self):
        self.is_running = False
        embed = discord.Embed(title="💥 CRASHED!", color=discord.Color.red())
        embed.description = f"The rocket crashed at **{self.crash_point:.2f}x**.\nYou lost **{self.bet_amount:,} gold**."
        #embed.set_thumbnail(url="https://i.imgur.com/P9721k6.png") # Explosion/Crash icon
        
        # Disable button
        self.cash_out_button.disabled = True
        self.cash_out_button.label = "Crashed"
        self.cash_out_button.style = ButtonStyle.danger
        
        await self.original_interaction.edit_original_response(embed=embed, view=self)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    @discord.ui.button(label="Cash Out", style=ButtonStyle.success, emoji="💰")
    async def cash_out_button(self, interaction: Interaction, button: Button):
        if not self.is_running or self.cashed_out:
            return await interaction.response.defer() # Ignore clicks if ended

        self.cashed_out = True
        self.is_running = False
        if self.task: self.task.cancel() # Stop the loop immediately

        # Calculate Winnings
        # Use current_multiplier
        winnings = int(self.bet_amount * self.current_multiplier)
        await self.bot.database.users.modify_gold(self.user_id, winnings)

        # UI Update
        embed = discord.Embed(title="✅ Cashed Out!", color=discord.Color.green())
        embed.description = f"You ejected at **{self.current_multiplier:.2f}x**!\n\n**Winnings:** {winnings:,} gold\n**Profit:** {winnings - self.bet_amount:,} gold"
        embed.add_field(name="Rocket Status", value=f"It would have crashed at **{self.crash_point:.2f}x**")
        
        button.disabled = True
        button.label = "Claimed"
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


# ==============================================================================
#  MAIN CASINO MENU
# ==============================================================================

class CasinoMenuView(View):
    def __init__(self, bot, user_id, bet_amount, parent_cog):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = str(user_id)
        self.bet_amount = bet_amount
        self.parent_cog = parent_cog
        self.response = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        if self.response:
            try: await self.response.delete()
            except: pass

    async def _verify_funds(self, interaction: Interaction) -> bool:
        user_data = await self.bot.database.users.get(self.user_id, interaction.guild.id)
        if user_data[6] < self.bet_amount:
            await interaction.response.edit_message(content="Insufficient funds!", embed=None, view=None)
            return False
        return True

    @discord.ui.button(label="Blackjack", emoji="🃏", style=ButtonStyle.primary, row=0)
    async def blackjack_btn(self, interaction: Interaction, button: Button):
        if not await self._verify_funds(interaction): return
        await interaction.response.edit_message(content=f"Starting **Blackjack** ({self.bet_amount:,})...", embed=None, view=None)
        await self.parent_cog.start_blackjack(interaction, self.bet_amount)

    @discord.ui.button(label="Roulette", emoji="🎡", style=ButtonStyle.danger, row=0)
    async def roulette_btn(self, interaction: Interaction, button: Button):
        if not await self._verify_funds(interaction): return
        # Don't delete embed yet, pass control to RouletteView
        await self.parent_cog.start_roulette(interaction, self.bet_amount)

    @discord.ui.button(label="Crash", emoji="🚀", style=ButtonStyle.success, row=1)
    async def crash_btn(self, interaction: Interaction, button: Button):
        if not await self._verify_funds(interaction): return
        # await interaction.response.edit_message(content=f"Starting **Crash** ({self.bet_amount:,})...", embed=None, view=None)
        await self.parent_cog.start_crash(interaction, self.bet_amount)

    @discord.ui.button(label="Horse Racing", emoji="🐎", style=ButtonStyle.secondary, row=1)
    async def horse_btn(self, interaction: Interaction, button: Button):
        if not await self._verify_funds(interaction): return
        # await interaction.response.edit_message(content=f"Starting **Horse Racing** ({self.bet_amount:,})...", embed=None, view=None)
        await self.parent_cog.start_horse_race(interaction, self.bet_amount)

    @discord.ui.button(label="Cancel", emoji="❌", style=ButtonStyle.gray, row=2)
    async def cancel_btn(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

# ==============================================================================
#  HORSE RACING VIEW
# ==============================================================================

class HorseRaceView(View):
    def __init__(self, bot, user_id, bet_amount, parent_interaction):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = str(user_id)
        self.bet_amount = bet_amount
        self.original_interaction = parent_interaction
        self.race_logic = HorseRaceLogic()
        self.selected_horse_index = None
        self.task = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if not self.selected_horse_index and not self.task:
            self.bot.state_manager.clear_active(self.user_id)
            try: await self.original_interaction.delete_original_response()
            except: pass

    async def start_race(self):
        # Disable buttons
        for child in self.children:
            child.disabled = True
        
        # Deduct Gold
        await self.bot.database.users.modify_gold(self.user_id, -self.bet_amount)
        
        embed = discord.Embed(title="🐎 And they're off!", color=discord.Color.green())
        embed.description = self.race_logic.get_race_string()
        await self.original_interaction.edit_original_response(embed=embed, view=None) # Remove buttons during race

        # Animation Loop
        while not self.race_logic.advance_race():
            await asyncio.sleep(1.5) # Update delay
            embed.description = self.race_logic.get_race_string()
            try:
                await self.original_interaction.edit_original_response(embed=embed)
            except: return # Message deleted

        # Race Finished
        winner = self.race_logic.winner
        picked_horse = self.race_logic.horses[self.selected_horse_index]
        
        embed.description = self.race_logic.get_race_string()
        embed.add_field(name="Winner", value=f"🏆 **{winner['name']}** {winner['emoji']} crosses the line!")

        if winner == picked_horse:
            winnings = self.bet_amount * 4
            await self.bot.database.users.modify_gold(self.user_id, winnings)
            embed.color = discord.Color.gold()
            embed.add_field(name="Congratulations!", value=f"You bet on **{picked_horse['name']}** and won **{winnings:,} gold**!", inline=False)
        else:
            embed.color = discord.Color.red()
            embed.add_field(name="Loss", value=f"You bet on **{picked_horse['name']}**. Better luck next time.", inline=False)

        await self.original_interaction.edit_original_response(embed=embed)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def _pick_horse(self, interaction: Interaction, index: int):
        self.selected_horse_index = index
        await interaction.response.defer()
        await self.start_race()

    @discord.ui.button(label="Thunder Hoof", emoji="🐎", style=ButtonStyle.primary, row=0)
    async def horse_1(self, interaction: Interaction, button: Button):
        await self._pick_horse(interaction, 0)

    @discord.ui.button(label="Lightning Bolt", emoji="🦄", style=ButtonStyle.primary, row=0)
    async def horse_2(self, interaction: Interaction, button: Button):
        await self._pick_horse(interaction, 1)

    @discord.ui.button(label="Old Reliable", emoji="🦓", style=ButtonStyle.primary, row=1)
    async def horse_3(self, interaction: Interaction, button: Button):
        await self._pick_horse(interaction, 2)

    @discord.ui.button(label="Dark Horse", emoji="🐫", style=ButtonStyle.primary, row=1)
    async def horse_4(self, interaction: Interaction, button: Button):
        await self._pick_horse(interaction, 3)