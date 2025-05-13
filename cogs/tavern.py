import discord
from discord.ext import commands
from discord.ext.commands import Context
from datetime import datetime, timedelta
import asyncio
import random
import pytz

class Tavern(commands.Cog, name="tavern"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.est_tz = pytz.timezone('America/New_York')  # Define EST timezone

    @commands.hybrid_command(
        name="shop",
        description="Visit the tavern shop to buy items."
    )
    async def shop(self, context: Context) -> None:
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)

        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return

        user_level = existing_user[4]
        additional_cost = 0
        if (user_level >= 20):
            additional_cost = int(user_level / 10) * 100

        gold = existing_user[6] 
        potions = existing_user[16]


        embed = discord.Embed(
            title="Tavern Shop 🏪",
            description="Welcome to the shop! Here are the items you can buy:",
            color=0xFFCC00,
        )
        cost = 200 + additional_cost
        embed.add_field(name="Potion 🍹", value=f"Cost: {cost} gold", inline=False)
        embed.add_field(name="Potion 🍹 x5", value=f"Cost: {cost * 5} gold", inline=False)
        embed.add_field(name="Potion 🍹 x10", value=f"Cost: {cost * 10} gold", inline=False)
        message = await context.send(embed=embed)

        reactions = ["🍹", "5️⃣", "🔟"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def check(reaction, user):
            return user == context.author and reaction.message.id == message.id

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)

            if str(reaction.emoji) == "🍹" or str(reaction.emoji) == "5️⃣" or str(reaction.emoji) == "🔟":
                if str(reaction.emoji) == "🍹":
                    times = 1
                elif str(reaction.emoji) == "5️⃣":
                    times = 5
                elif str(reaction.emoji) == "🔟":
                    times = 10
                success = 0
                for i in range(times):
                    if gold < cost:
                        embed.add_field(name="Purchase",
                                        value="You peer at your money pouch. You are too broke to afford a potion.", 
                                        inline=False)
                        await message.edit(embed=embed)
                        break

                    if potions > 20:
                        embed.add_field(name="Purchase",
                                        value="You glance at your potion pouch. It's full.", 
                                        inline=False)
                        await message.edit(embed=embed)
                        break

                    gold -= cost
                    await self.bot.database.add_gold(user_id, -cost)
                    await self.bot.database.increase_potion_count(user_id) 
                    success += 1
                if success > 0:
                    if times == 1:
                        embed.add_field(name="Purchase",
                                        value=f"You purchase a potion. Your remaining 💰 is **{gold:,}**.", 
                                        inline=False)
                        await message.edit(embed=embed)
                    else:
                        embed.add_field(name="Purchase",
                                        value=f"You buy some potions. Your remaining 💰 is **{gold:,}**.", 
                                        inline=False)
                        await message.edit(embed=embed)
            await message.clear_reactions()
            await asyncio.sleep(5)
            await message.delete()
        except asyncio.TimeoutError:
            embed.add_field(name="Close",
                            value=(f"The tavern keeper sighs and closes his shop. "
                                    "Come back when you have made up your mind."), 
                            inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
            await message.delete()

    @commands.hybrid_command(
        name="rest",
        description="Rest your weary body and mind for the adventure ahead."
    )
    async def rest(self, context: Context) -> None:
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)

        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return

        user_level = existing_user[4]
        current_hp = existing_user[11]  
        max_hp = existing_user[12]
        gold = existing_user[6]
        last_rest_time = existing_user[13]

        if current_hp == max_hp:
            confirm_embed = discord.Embed(
                    title="The Tavern 🛏️",
                    description=("You are already fully rested."),
                    color=0xFFCC00
                )
            message = await context.send(embed=confirm_embed)
            await asyncio.sleep(10)
            await message.delete()
            return

        cooldown_duration = timedelta(hours=2)
        if last_rest_time == None:
            await self.bot.database.update_player_hp(user_id, max_hp)
            await self.bot.database.update_rest_time(user_id)
            desc = f"You have rested and regained your health! Current HP is now **{max_hp}**."
            confirm_embed = discord.Embed(
                    title="The Tavern 🛏️",
                    description=desc,
                    color=0xFFCC00
                )
            message = await context.send(embed=confirm_embed)
            return
        try:
            last_rest_time_dt = datetime.fromisoformat(last_rest_time)
            time_since_rest = datetime.now() - last_rest_time_dt
        except ValueError:
            await context.send("There was an error with your last rest time. Please contact the admin.")
            return
        except TypeError:
            await context.send("Your last rest time format is invalid. Please contact the admin.")
            return

        if time_since_rest >= cooldown_duration:
            await self.bot.database.update_player_hp(user_id, max_hp)  # Set current HP to max HP
            await self.bot.database.update_rest_time(user_id)  # Reset last rest time
            desc = (f"You have rested and regained your health! Current HP: **{max_hp}**.")
            confirm_embed = discord.Embed(
                    title="The Tavern 🛏️",
                    description=desc,
                    color=0xFFCC00
                )
            message = await context.send(embed=confirm_embed)
            return
        else:
            # Not enough time has passed since the last rest
            remaining_time = cooldown_duration - time_since_rest
            desc = (f"You need to wait **{remaining_time.seconds // 3600} hours"
                    f" and {(remaining_time.seconds // 60) % 60} minutes** before the tavern lets you rest for free again.")
            confirm_embed = discord.Embed(
                    title="The Tavern 🛏️",
                    description=desc,
                    color=0xFFCC00
                )
            message = await context.send(embed=confirm_embed)

            # If player has more than 400 gold or their scaled amount, offer bypass
            if (user_level >= 20):
                cost = (int(user_level / 10) * 100) + 400
            else:
                cost = 400
            if gold >= cost:
                skip_msg = (f"The tavern-keeper offers you a room for **{cost} gold** if you want to rest again immediately.\n"
                            f"Do you wish to do so?")
                confirm_embed.add_field(name="Pay for a room", value=skip_msg, inline=False)
                await message.edit(embed=confirm_embed)
                await message.add_reaction("✅")  # Confirm
                await message.add_reaction("❌")  # Cancel

                def check(reaction, user):
                    return user == context.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == message.id

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                    if str(reaction.emoji) == "✅":
                        # Deduct gold and update current HP to max HP
                        new_gold = gold - cost
                        await self.bot.database.update_player_hp(user_id, max_hp)  # Update HP to max
                        await self.bot.database.update_user_gold(user_id, new_gold)  # Update gold
                        pay_msg = f"You have rested and regained your health! Current HP: **{max_hp}**."
                        confirm_embed.add_field(name="Paid!", value=pay_msg, inline=False)
                        await message.clear_reactions()
                        await message.edit(embed=confirm_embed)
                    else:
                        #await context.send("Resting cancelled.")
                        await message.delete()
                except asyncio.TimeoutError:
                    #await context.send("You took too long to respond. Resting cancelled.")
                    await message.delete()


    @commands.hybrid_command(name="gamble", description="Gamble your gold in the tavern!")
    @commands.cooldown(1, 60, commands.BucketType.user)  # 1 minute
    async def gamble(self, context: Context, amount: int) -> None:
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        
        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)

        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return
        
        if self.bot.state_manager.is_active(user_id):
            await context.send("You are currently busy with another operation. Please finish that first.")
            return
        
        self.bot.state_manager.set_active(user_id, "gamble")

        player_gold = existing_user[6]

        # Check if the amount is valid
        if amount <= 0 or amount > player_gold:
            await context.send("Invalid gambling amount. You must gamble an amount between 1 and your current gold.")
            return

        # Create the gambling embed
        embed = discord.Embed(
            title="The Tavern Casino 🎲",
            description="Pick your poison:",
            color=0xFFC107,
        )
        embed.add_field(name="🃏 Blackjack", value="1v1 showdown with the Tavern keeper (x2)", inline=False)
        embed.add_field(name="🎰 Slot Machine", value="Spin the machine and may luck be in your favor (x7)", inline=False)
        embed.add_field(name="🎡 Roulette", value="Bet it all on black (x2 - x35)", inline=False)
        
        gambling_message = await context.send(embed=embed)

        # Add reactions for game selection
        await gambling_message.add_reaction("🃏")  # Blackjack
        await gambling_message.add_reaction("🎰")  # Slot Machine
        await gambling_message.add_reaction("🎡")  # Roulette

        def check(reaction, user):
            return (user == context.author and 
                    reaction.message.id == gambling_message.id and 
                    str(reaction.emoji) in ["🃏", "🎰", "🎡"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

            if str(reaction.emoji) == "🃏":
                await self.play_blackjack(context, player_gold, amount, gambling_message, embed)
            elif str(reaction.emoji) == "🎰":
                await self.play_slot_machine(context, player_gold, amount, gambling_message, embed)
            elif str(reaction.emoji) == "🎡":
                await self.play_roulette(context, player_gold, amount, gambling_message, embed)
        except asyncio.TimeoutError:
            await context.send("You took too long to decide. The gambling options have been closed.")
        finally:
            self.bot.state_manager.clear_active(user_id)

    async def play_blackjack(self, context: Context, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a Blackjack game against the house."""
        
        player_hand = [random.randint(1, 10), random.randint(1, 10)]
        house_hand = [random.randint(1, 10), random.randint(1, 10)]
        player_gold -= bet_amount
        await self.bot.database.update_user_gold(context.author.id, player_gold)  # Update gold in DB

        def calculate_hand_value(hand):
            """Calculate the total value of a hand, adjusting for Aces to achieve the best score possible without going over 21."""
            total = sum(hand)
            aces_count = hand.count(1)  # Count Aces as 1

            # Iterate over the number of Aces we have and attempt to treat them as 11
            while aces_count > 0 and total + 10 <= 21: 
                total += 10  # Treat one Ace as 11 instead of 1
                aces_count -= 1

            return total

        # The player's turn
        while True:
            player_value = calculate_hand_value(player_hand)
            
            # Update the embed with current game state
            embed.description = (
                f"You drew: **{player_hand}** for a total of **{player_value}**\n"
                f"The house shows: **{house_hand[0]}**"
            )
            embed.clear_fields()  # Clear fields for new options
            embed.add_field(name="Options", value="React with: 🃏 to Draw another card or ✋ to Hold", inline=False)
            await message.edit(embed=embed)

            await message.clear_reactions()
            await message.add_reaction("🃏")  # Draw another card
            await message.add_reaction("✋")  # Hold

            def check(reaction, user):
                return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["🃏", "✋"]

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                if str(reaction.emoji) == "🃏":  # Player chooses to draw another card
                    new_card = random.randint(1, 10)  # Drawing a new card
                    player_hand.append(new_card)
                    player_value = calculate_hand_value(player_hand)
                    if player_value > 21:
                        embed.add_field(name="Result", 
                                        value=(f"You drew a **{new_card}** and your hand is now **{player_hand}**."
                                               f"Total: **{player_value}**. You went bust! "
                                               f"The tavern keeper smirks and takes your 💰 **{bet_amount:,}**."), inline=False)
                        await message.edit(embed=embed)
                        return

                elif str(reaction.emoji) == "✋":  # Player chooses to hold
                    break  # Exit the drawing loop, go to the house's turn

            except asyncio.TimeoutError:
                await context.send("You took too long to respond. The game has ended.")
                return
            finally:
                self.bot.state_manager.clear_active(context.author.id)

        # The house's turn
        house_value = calculate_hand_value(house_hand)
        while house_value < 17:  # House always hits until reaching 17 or higher
            new_card = random.randint(1, 10)  # House draws a card
            house_hand.append(new_card)
            house_value = calculate_hand_value(house_hand)

        # Determine the result
        embed.clear_fields()
        final_player_value = calculate_hand_value(player_hand)
        final_house_value = house_value

        embed.add_field(name="Final Hands", value=f"Your Hand: **{player_hand}** (Total: **{final_player_value}**)\n"
                                                f"House Hand: **{house_hand}** (Total: **{final_house_value}**)")

        if final_player_value > 21:
            embed.add_field(name="Result", value="You went bust! You lose your bet.", inline=False)
        elif final_house_value > 21 or final_player_value > final_house_value:
            player_gold += bet_amount * 2  # Player wins, doubling their bet
            embed.add_field(name="Result", value=f"You win! You double your initial {bet_amount:,} and now have 💰 {bet_amount * 2:,}!", inline=False)
        elif final_player_value < final_house_value:
            embed.add_field(name="Result", value=f"You lose! The tavern keeper smirks and takes your 💰 {bet_amount:,}", inline=False)
        else:
            player_gold += bet_amount  # Player wins, doubling their bet
            embed.add_field(name="Result", value="It's a tie. Nothing interesting happens.", inline=False)

        await message.edit(embed=embed)
        await self.bot.database.update_user_gold(context.author.id, player_gold)  # Update gold in DB
        self.bot.state_manager.clear_active(context.author.id)
        await asyncio.sleep(10)
        await message.delete()


    async def play_slot_machine(self, context: Context, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a simple Slot Machine game."""
        emojis = ["🍒", "🔔", "⭐"]
        
        # Simulate the slot machine rolls
        reel_results = [random.choices(emojis, k=5) for _ in range(5)]
        
        # Prepare the results for the embed
        results_message = "\n".join([f"| {' | '.join(line)} |" for line in reel_results])
        
        # Create a counter for line matches
        line_matches = 0

        # Check for horizontal matches
        for row in reel_results:
            if len(set(row)) == 1:  # All items in the row are the same
                line_matches += 1

        # Check for vertical matches
        for col in range(5):
            if len(set(reel_results[row][col] for row in range(5))) == 1:  # All items in the column are the same
                line_matches += 1

        # Check for diagonal matches
        if len(set(reel_results[i][i] for i in range(5))) == 1:  # Top-left to bottom-right
            line_matches += 1
        if len(set(reel_results[i][4 - i] for i in range(5))) == 1:  # Top-right to bottom-left
            line_matches += 1

        # Determine if there was a win based on line matches
        win = line_matches > 0

        # Update the embed with the rolled results
        embed.clear_fields()
        embed.title = "Slot Machine Results 🎰"
        embed.description = f"**Results:**\n{results_message}\n\n"

        if win:
            player_gold += bet_amount * (line_matches) * 7
            embed.add_field(name="Congratulations!", value=(f"You won {line_matches} lines!\n" 
                                                            f"Your new balance: 💰 **{player_gold:,}**"), inline=False)
        else:
            player_gold -= bet_amount  # Lose the bet
            embed.add_field(name="Oh no!", value=f"You lost! Your new balance: 💰 **{player_gold:,}**", inline=False)

        await message.edit(embed=embed)
        await self.bot.database.update_user_gold(context.author.id, player_gold)  # Update gold in DB
        self.bot.state_manager.clear_active(context.author.id)
        await asyncio.sleep(10)
        await message.delete()

    async def play_roulette(self, context: Context, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a simple Roulette game."""
        embed.clear_fields()
        await message.clear_reactions()
        player_gold -= bet_amount  # Lose the bet
        await self.bot.database.update_user_gold(context.author.id, player_gold)  # Update gold in DB
        # Present color choice
        embed.title = "Roulette 🎡"
        embed.description = "Choose a color:\n🟥 Red\n⬛ Black"
        await message.edit(embed=embed)

        # Add reactions for color choice
        await message.add_reaction("🟥")  # Red
        await message.add_reaction("⬛")  # Black

        def color_check(reaction, user):
            return user == context.author and reaction.message.id == message.id and str(reaction.emoji) in ["🟥", "⬛"]

        try:
            color_response = await self.bot.wait_for('reaction_add', timeout=60.0, check=color_check)
            chosen_color = "red" if str(color_response[0].emoji) == "🟥" else "black"

            # Ask for a number
            embed.description = f"Enter a number between 1 and 36:\nRed = Even\nBlack = Odd"
            await message.edit(embed=embed)

            def number_check(m):
                return m.author == context.author and m.channel == context.channel and m.content.isdigit() and 1 <= int(m.content) <= 36

            number_response = await self.bot.wait_for('message', timeout=60.0, check=number_check)
            chosen_number = int(number_response.content)

            # Spin the roulette
            is_white = random.randint(0, 100)
            if (is_white > 97):
                result_color = "white"
                result_number = 0
            else:
                roulettes_numbers = random.sample(range(1, 37), 36)  # Randomly shuffle numbers from 1 to 36
                result_number = random.choice(roulettes_numbers)
                result_color = "red" if result_number % 2 == 0 else "black"  # Simplified color determination
            
            # Update the embed with results
            embed.title = "Roulette Results 🎡"
            embed.description = f"The wheel spins...\nResult: **{result_number}** - Color: **{result_color}**"
            
            if result_color == chosen_color:
                # Color was guessed right, check number
                if result_number == chosen_number:
                    # Both color and number match
                    player_gold += bet_amount * 35  # x35 payout
                    embed.add_field(name="🎊 Congratulations! 🎊", 
                                    value=f"You won {bet_amount * 35:,}! Your new balance: 💰 **{player_gold:,}**", 
                                    inline=False)
                else:
                    # Only color matched
                    player_gold += bet_amount * 2  # Double the bet
                    embed.add_field(name="Win 🎉", 
                                    value=f"You won {bet_amount * 2:,}! Your new balance: 💰 **{player_gold:,}**", 
                                    inline=False)
            else:
                # House wins
                # player_gold -= bet_amount  # Lose the bet
                embed.add_field(name="Loss 😞", 
                                value=f"You lost {bet_amount:,}! Your new balance: 💰 **{player_gold:,}**", inline=False)

            await message.edit(embed=embed)
            # player_gold -= bet_amount  # Lose the bet
            await self.bot.database.update_user_gold(context.author.id, player_gold)  # Update gold in DB
            await asyncio.sleep(10)
            await message.delete()
            await number_response.delete()
        except asyncio.TimeoutError:
            await context.send("You took too long to respond. The roulette game has ended.")
            await message.delete()
        finally:
            self.bot.state_manager.clear_active(context.author.id)


    @commands.hybrid_command(
        name="checkin",
        description="Check in at the tavern and receive a daily bonus!"
    )
    async def checkin(self, context: Context) -> None:
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return

        last_checkin_time = existing_user[18]  # Assuming last_checkin_time is at index 13
        current_time = datetime.now()
        current_time = datetime.now(self.est_tz)  # Get the current time in EST

        if last_checkin_time is None:
            # First time checking in
            bonus = random.randint(1000, 2000)
            await self.bot.database.add_gold(user_id, bonus)
            await self.bot.database.update_checkin_time(user_id)
            await context.send(f"You have successfully checked in and received **{bonus:,} gold**!")
            return

        try:
            last_checkin_time_dt = datetime.fromisoformat(last_checkin_time).replace(tzinfo=self.est_tz)
        except ValueError:
            await context.send("There was an error processing your last check-in time. Please contact an admin.")
            return

        # Check if enough time has passed since the last check-in
        next_checkin_time = last_checkin_time_dt + timedelta(hours=18)

        # Calculate the next check-in time considering the reset at 3 AM EST
        if current_time < next_checkin_time:
            # User is trying to check in before the next available check-in time
            remaining_time = next_checkin_time - current_time
            await context.send(f"You need to wait **{remaining_time.seconds // 3600} hours and {(remaining_time.seconds // 60) % 60} minutes** before you can check in again.")
            return

        # Proceed with the check-in
        bonus = random.randint(1000, 2000)
        await self.bot.database.add_gold(user_id, bonus)
        await self.bot.database.update_checkin_time(user_id)

        await context.send(f"You have successfully checked in and received **{bonus} gold**!")


async def setup(bot) -> None:
    await bot.add_cog(Tavern(bot))
