import discord
from discord import app_commands, Interaction, Message
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import random
import math


class Tavern(commands.Cog, name="tavern"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.skills_cog = bot.get_cog("skills")

    @app_commands.command(
        name="shop",
        description="Visit the tavern shop to buy items."
    )
    async def shop(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # Initial user data setup
        user_level = existing_user[4]
        additional_cost = 0
        if (user_level >= 20):
            additional_cost = int(user_level / 10) * 100

        gold = existing_user[6] 
        potions = existing_user[16]
        curios_today = existing_user[23]

        # Setup the shop embed after loading
        embed = discord.Embed(
            title="Tavern Shop 🏪",
            description="Welcome to the shop! Here are the items you can buy:",
            color=0xFFCC00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/81jN8tA.jpeg")
        embed.add_field(name="Your Gold 💰", value=f"{gold:,}", inline=False)
        cost = 200 + additional_cost
        embed.add_field(name="Potion 🧪 x1 / x5 / x10", value=f"Cost: {cost} / {cost * 5} / {cost * 10} gold", inline=False)

        # Curios Section
        curio_cost = 8000
        curio_limit = 5
        remaining_curios = curio_limit - curios_today
        if remaining_curios > 0:
            embed.add_field(name="Curious Curio 🎁",
                            value=f"Cost: **{curio_cost:,}** gold\nStock: **{remaining_curios}**", inline=False)
        else:
            embed.add_field(name="Curious Curio 🎁",
                            value="No stock left. Refreshed on next /checkin!", inline=False)
        
        # Clear the loading message and send the updated embed
        embed.add_field(name="The tavernkeeper", value=f"Hello traveler, the pickings are slim I'm afraid...", inline=False)
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()

        reactions = ["🧪", "5️⃣", "🔟", "🎁", "❌"]  # Added ❌ reaction for closing shop
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id

        try:
            self.bot.state_manager.set_active(user_id, "shop") 
            while True:
                existing_user = await self.bot.database.users.get(user_id, server_id)
                gold = existing_user[6] 
                potions = existing_user[16]
                curios_today = existing_user[23]

                reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)

                if str(reaction.emoji) == "❌":  # Exit if user wants to close the shop
                    try:
                        await message.delete()
                    except discord.errors.Forbidden:
                        await interaction.followup.send("I don't have permission to delete messages!")
                    except discord.errors.HTTPException as e:
                        await interaction.followup.send(f"Failed to delete message: {e}")
                    break

                success = 0
                times = 0

                if str(reaction.emoji) in ["🧪", "5️⃣", "🔟"]:
                    times = 1 if str(reaction.emoji) == "🧪" else (5 if str(reaction.emoji) == "5️⃣" else 10)

                # Handle potion purchases
                for _ in range(times):
                    if gold < cost:
                        embed.set_field_at(3, name="The tavernkeeper",
                                        value="It seems you have run out of coin...",
                                        inline=False)
                        await interaction.edit_original_response(embed=embed)
                        break

                    if potions > 20:
                        embed.set_field_at(3, name="The tavernkeeper",
                                        value="It would be too dangerous to hold that many potions at once...",
                                        inline=False)
                        await interaction.edit_original_response(embed=embed)
                        break
                    
                    gold -= cost
                    await self.bot.database.users.modify_gold(user_id, -cost)
                    await self.bot.database.user.modify_stat(user_id, 'potions', 1)
                    success += 1
                
                # Update the embed after every potion transaction
                embed.set_field_at(0, name="Your Gold 💰", value=f"{gold:,}", inline=False)

                if success > 0:
                    if times == 1:
                        embed.set_field_at(3, name="The tavernkeeper",
                                        value=f"One potion? Of course...", 
                                        inline=False)
                        await message.edit(embed=embed)
                    else:
                        embed.set_field_at(3, name="The tavernkeeper",
                                        value=f"Your pockets run deep traveler! Here you go...", 
                                        inline=False)
                        await interaction.edit_original_response(embed=embed)

                # Handling curios purchase
                if str(reaction.emoji) == "🎁" and remaining_curios > 0:
                    if gold < curio_cost:
                        embed.set_field_at(3, name="The tavernkeeper",
                                        value="It seems you have run out of coin...", inline=False)
                        await interaction.edit_original_response(embed=embed)
                        continue
                    
                    # Deduct cost and increment curios count
                    gold -= curio_cost
                    await self.bot.database.users.modify_gold(user_id, -curio_cost)
                    await self.bot.database.users.modify_currency(user_id, 'curios', 1)
                    await self.bot.database.users.modify_currency(user_id, 'curios_purchased_today', 1)

                    # Update user values after purchase
                    curios_today += 1  # Increment curios today for the user
                    remaining_curios = curio_limit - curios_today  # Calculate remaining curios

                    embed.set_field_at(2, name="Curious Curio 🎁",
                                    value=f"Cost: **{curio_cost:,}** gold\nStock: **{remaining_curios}**", inline=False)

                    # Update the embed with the new gold and remaining curios
                    embed.set_field_at(0, name="Your Gold 💰", value=f"{gold:,}", inline=False)

                    embed.set_field_at(3, name="The tavernkeeper",
                                    value=f"In the gambling mood are we? Very well...", 
                                    inline=False)
                    await interaction.edit_original_response(embed=embed)

                # Refresh reactions after every transaction
                await message.remove_reaction(reaction.emoji, user)

        except asyncio.TimeoutError:
            self.bot.state_manager.clear_active(user_id)
            embed.set_field_at(3, name="The tavernkeeper",
                            value=(f"Come back when you have made up your mind."), 
                            inline=False)
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(5)
            await interaction.delete_original_response()

        # Final cleanup after exiting the shop loop
        self.bot.state_manager.clear_active(user_id)
        await self.bot.database.users.set_gold(user_id, gold)  # Update the user's gold in DB


    @app_commands.command(
        name="rest",
        description="Rest your weary body and mind for the adventure ahead."
    )
    async def rest(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Fetch user data
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        if not await self.bot.check_is_active(interaction, user_id):
            return

        user_level = existing_user[4]
        current_hp = existing_user[11]  
        max_hp = existing_user[12]
        gold = existing_user[6]
        last_rest_time = existing_user[13]

        if current_hp == max_hp:
            embed = discord.Embed(
                    title="The Tavern 🛏️",
                    description=("You are already fully rested."),
                    color=0xFFCC00
                )
            embed.set_thumbnail(url="https://i.imgur.com/ZARftKJ.jpeg")
            await interaction.response.send_message(embed=embed)
            message: Message = await interaction.original_response()
            await asyncio.sleep(10)
            await message.delete()
            return

        cooldown_duration = timedelta(hours=2)
        if last_rest_time == None:
            await self.bot.database.users.update_hp(user_id, max_hp)
            await self.bot.database.users.update_timer(user_id, 'last_rest_time')
            desc = f"You have rested and regained your health! Current HP is now **{max_hp}**."
            embed = discord.Embed(
                    title="The Tavern 🛏️",
                    description=desc,
                    color=0xFFCC00
                )
            embed.set_thumbnail(url="https://i.imgur.com/ZARftKJ.jpeg")
            message = await interaction.response.send_message(embed=embed)
            return
        try:
            last_rest_time_dt = datetime.fromisoformat(last_rest_time)
            time_since_rest = datetime.now() - last_rest_time_dt
        except ValueError:
            await interaction.response.send_message("There was an error with your last rest time. Please contact the admin.")
            return
        except TypeError:
            await interaction.response.send_message("Your last rest time format is invalid. Please contact the admin.")
            return

        if time_since_rest >= cooldown_duration:
            await self.bot.database.users.update_hp(user_id, max_hp)  # Set current HP to max HP
            await self.bot.database.users.update_timer(user_id, 'last_rest_time')  # Reset last rest time
            desc = (f"You have rested and regained your health! Current HP: **{max_hp}**.")
            embed = discord.Embed(
                    title="The Tavern 🛏️",
                    description=desc,
                    color=0xFFCC00
                )
            embed.set_thumbnail(url="https://i.imgur.com/ZARftKJ.jpeg")
            message = await interaction.response.send_message(embed=embed)
            return
        else:
            # Not enough time has passed since the last rest
            remaining_time = cooldown_duration - time_since_rest
            desc = (f"You need to wait **{remaining_time.seconds // 3600} hours"
                    f" and {(remaining_time.seconds // 60) % 60} minutes** before the tavern lets you rest for free again.")
            embed = discord.Embed(
                    title="The Tavern 🛏️",
                    description=desc,
                    color=0xFFCC00
                )
            embed.set_image(url="https://i.imgur.com/NUEdC7a.jpeg")
            message = await interaction.response.send_message(embed=embed)
            message: Message = await interaction.original_response()
            # If player has more than 400 gold or their scaled amount, offer bypass
            if (user_level >= 20):
                cost = (int(user_level / 10) * 100) + 400
            else:
                cost = 400
            if gold >= cost:
                skip_msg = (f"I have an extra room available for **{cost} gold**.\n"
                            f"You can pay for it and rest immediately.")
                embed.add_field(name="The Tavernkeeper", value=skip_msg, inline=False)
                await message.edit(embed=embed)
                await message.add_reaction("✅")  # Confirm
                await message.add_reaction("❌")  # Cancel

                def check(reaction, user):
                    return user == interaction.user and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == message.id

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                    if str(reaction.emoji) == "✅":
                        # Deduct gold and update current HP to max HP
                        new_gold = gold - cost
                        await self.bot.database.users.update_hp(user_id, max_hp)  # Update HP to max
                        await self.bot.database.users.set_gold(user_id, new_gold)  # Update gold
                        pay_msg = (f"Thank you for your patronage! Enjoy your stay.\n"
                                   f"You feel refreshed, your hp is now {max_hp}!")
                        embed.add_field(name="Payment", value=pay_msg, inline=False)
                        await message.clear_reactions()
                        await message.edit(embed=embed)
                    else:
                        #await interaction.response.send_message("Resting cancelled.")
                        await message.delete()
                except asyncio.TimeoutError:
                    #await interaction.response.send_message("You took too long to respond. Resting cancelled.")
                    await message.delete()


    @app_commands.command(name="gamble", description="Gamble your gold in the tavern!")
    @commands.cooldown(1, 60, commands.BucketType.user)  # 1 minute
    async def gamble(self, interaction: Interaction, amount: int) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        # Fetch user data
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        self.bot.state_manager.set_active(user_id, "gamble")

        player_gold = existing_user[6]

        # Check if the amount is valid
        if amount <= 0 or amount > player_gold:
            await interaction.response.send_message((f"Invalid gambling amount.\n"
                                                    f"You must gamble an amount between 1 and your current gold."),
                                                    ephemeral=True)
            self.bot.state_manager.clear_active(user_id)
            return

        # Create the gambling embed
        embed = discord.Embed(
            title="The Tavern Casino 🎲",
            description="What would you like to play?",
            color=0xFFC107,
        )
        embed.set_thumbnail(url="https://i.imgur.com/D8HlsQX.jpeg")
        embed.add_field(name="🃏 Blackjack", value="1v1 showdown with the Tavern keeper (x2)", inline=False)
        embed.add_field(name="🎰 Slot Machine", value="Spin the machine and may luck be in your favor (x7)", inline=False)
        embed.add_field(name="🎡 Roulette", value="Bet it all on black (x2 - x35)", inline=False)
        embed.add_field(name="🎢 Wheel of Fortune", value="Spin the wheel for a chance at big rewards (x0 - x10)", inline=False)
        embed.add_field(name="🚀 Crash", value="Cash out before the rocket crashes (x1 - x10+)", inline=False)
        
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()

        # Add reactions for game selection
        await message.add_reaction("🃏")  # Blackjack
        await message.add_reaction("🎰")  # Slot Machine
        await message.add_reaction("🎡")  # Roulette
        await message.add_reaction("🎢")  # Wheel of Fortune
        await message.add_reaction("🚀")  # Crash

        def check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["🃏", "🎰", "🎡", "🎢", "🚀"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

            if str(reaction.emoji) == "🃏":
                await self.play_blackjack(interaction, player_gold, amount, message, embed)
            elif str(reaction.emoji) == "🎰":
                await self.play_slot_machine(interaction, player_gold, amount, message, embed)
            elif str(reaction.emoji) == "🎡":
                await self.play_roulette(interaction, player_gold, amount, message, embed)
            elif str(reaction.emoji) == "🎢":
                await self.play_wheel(interaction, player_gold, amount, message, embed)
            elif str(reaction.emoji) == "🚀":
                await self.play_crash(interaction, player_gold, amount, message, embed)
        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(user_id)
        finally:
            self.bot.state_manager.clear_active(user_id)

    async def play_blackjack(self, interaction: Interaction, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a Blackjack game against the house."""
        player_hand = [random.randint(1, 10), random.randint(1, 10)]
        house_hand = [random.randint(1, 10), random.randint(1, 10)]
        player_gold -= bet_amount
        await self.bot.database.users.set_gold(interaction.user.id, player_gold)  # Update gold in DB

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
                f"The dealer shows: **{house_hand[0]}**"
            )
            await message.edit(embed=embed)
            embed.clear_fields()  # Clear fields for new options
            embed.add_field(name="Options", value="React with: 🃏 to Draw another card or ✋ to Hold", inline=False)
            await message.edit(embed=embed)
            await message.clear_reactions()
            await message.add_reaction("🃏")  # Draw another card
            await message.add_reaction("✋")  # Hold

            def check(reaction, user):
                return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["🃏", "✋"]

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
                                               f"The dealer smirks and takes your 💰 **{bet_amount:,}**."), inline=False)
                        await message.edit(embed=embed)
                        await message.clear_reactions()
                        return

                elif str(reaction.emoji) == "✋":  # Player chooses to hold
                    break  # Exit the drawing loop, go to the house's turn

            except asyncio.TimeoutError:
                await interaction.followup.send("You took too long to respond. The game has ended.")
                await message.delete()
                return

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
            embed.add_field(name="Result", 
                            value=f"You went bust! The dealer smirks and takes your 💰 **{bet_amount:,}**",
                            inline=False)
        elif final_house_value > 21 or final_player_value > final_house_value:
            player_gold += bet_amount * 2  # Player wins, doubling their bet
            embed.add_field(name="Result", 
                            value=(f"You win! Here are your winnings: 💰 **{bet_amount * 2:,}**.\n"
                            f"You now have 💰 **{player_gold:,}**!"), inline=False)
        elif final_player_value < final_house_value:
            embed.add_field(name="Result", 
                            value=f"You lose! The dealer smirks and takes your 💰 **{bet_amount:,}**", 
                            inline=False)
        else:
            player_gold += bet_amount  # Return the bet for a tie
            embed.add_field(name="Result", 
                            value="It seems we have tied.", 
                            inline=False)

        await message.edit(embed=embed)
        await self.bot.database.users.set_gold(interaction.user.id, player_gold)  # Update gold in DB
        #await asyncio.sleep(10)
        #await message.delete()


    async def play_slot_machine(self, interaction: Interaction, player_gold: int, bet_amount: int, message, embed) -> None:
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
        await self.bot.database.users.set_gold(interaction.user.id, player_gold)  # Update gold in DB
        #await asyncio.sleep(10)
        #await message.delete()

    async def play_roulette(self, interaction: Interaction, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a simple Roulette game."""
        embed.clear_fields()
        
        player_gold -= bet_amount  # Deduct the bet
        await self.bot.database.users.set_gold(interaction.user.id, player_gold)  # Update gold in DB
        # Present color choice
        embed.title = "Roulette 🎡"
        embed.description = "Choose a color:\n🟥 Red\n⬛ Black"
        await message.edit(embed=embed)
        await message.clear_reactions()
        # Add reactions for color choice
        await message.add_reaction("🟥")  # Red
        await message.add_reaction("⬛")  # Black

        def color_check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["🟥", "⬛"]

        try:
            color_response = await self.bot.wait_for('reaction_add', timeout=60.0, check=color_check)
            chosen_color = "red" if str(color_response[0].emoji) == "🟥" else "black"

            # Ask for a number
            embed.description = f"Enter a number between 1 and 36:\nRed = Even\nBlack = Odd"
            await message.edit(embed=embed)

            def number_check(m):
                return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit() and 1 <= int(m.content) <= 36

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
                embed.add_field(name="Loss 😞", 
                                value=f"You lost {bet_amount:,}! Your new balance: 💰 **{player_gold:,}**", inline=False)

            await message.edit(embed=embed)
            await self.bot.database.users.set_gold(interaction.user.id, player_gold)  # Update gold in DB
            #await asyncio.sleep(10)
            #await message.delete()
            await number_response.delete()
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to respond. The roulette game has ended.")
            await message.delete()
        finally:
            self.bot.state_manager.clear_active(interaction.user.id)

    async def play_wheel(self, interaction: Interaction, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a Wheel of Fortune game."""
        # Define wheel segments and their weights
        segments = [
            (0, 50),   # 50% chance to lose (0x)
            (1, 30),   # 30% chance to break even (1x)
            (2, 15),   # 15% chance to double (2x)
            (5, 4),    # 4% chance for 5x
            (25, 1)    # 1% chance for 25x 
        ]
        outcomes = [multiplier for multiplier, weight in segments for _ in range(weight)]
        result_multiplier = random.choice(outcomes)

        # Calculate winnings
        player_gold -= bet_amount  # Deduct the bet
        winnings = bet_amount * result_multiplier
        player_gold += winnings

        # Update the embed with results
        embed.clear_fields()
        embed.title = "Wheel of Fortune Results 🎢"
        embed.description = f"The wheel spins...\nResult: **{result_multiplier}x** multiplier!"

        if result_multiplier > 0:
            embed.add_field(
                name="Congratulations!",
                value=f"You won 💰 **{winnings:,}**!\nYour new balance: 💰 **{player_gold:,}**",
                inline=False
            )
        else:
            embed.add_field(
                name="Oh no!",
                value=f"You lost! Your new balance: 💰 **{player_gold:,}**",
                inline=False
            )

        await message.edit(embed=embed)
        await self.bot.database.users.set_gold(interaction.user.id, player_gold)  # Update gold in DB
        #await asyncio.sleep(10)
        #await message.delete()

    async def play_crash(self, interaction: Interaction, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a Crash game."""
        player_gold -= bet_amount  # Deduct the bet
        await self.bot.database.users.set_gold(interaction.user.id, player_gold)  # Update gold in DB

        # Ask for target multiplier
        embed.clear_fields()
        embed.title = "Crash 🚀"
        embed.description = "Enter your target multiplier (e.g., 2.0, between 1.1 and 10.0):"
        await message.edit(embed=embed)
        await message.clear_reactions()

        def multiplier_check(m):
            try:
                value = float(m.content)
                return (m.author == interaction.user and 
                        m.channel == interaction.channel and 
                        1.1 <= value <= 10.0)
            except ValueError:
                return False

        try:
            multiplier_response = await self.bot.wait_for('message', timeout=60.0, check=multiplier_check)
            target_multiplier = float(multiplier_response.content)

            # Generate crash point using an exponential distribution
            # This gives a realistic spread (most crashes between 1.1x and 3x, rare high values)
            crash_point = round(min(10.0, -math.log(random.random()) / 2), 2)

            # Determine outcome
            embed.title = "Crash Results 🚀"
            embed.description = f"The rocket soared to **{crash_point}x** before crashing!"

            if crash_point >= target_multiplier:
                winnings = int(bet_amount * target_multiplier)
                player_gold += winnings
                embed.add_field(
                    name="Congratulations! 🎉",
                    value=f"You cashed out at **{target_multiplier}x**!\n"
                          f"You won 💰 **{winnings:,}**!\nYour new balance: 💰 **{player_gold:,}**",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Crash! 💥",
                    value=f"The rocket crashed at **{crash_point}x**. You lost 💰 **{bet_amount:,}**!\n"
                          f"Your new balance: 💰 **{player_gold:,}**",
                    inline=False
                )

            await message.edit(embed=embed)
            await self.bot.database.users.set_gold(interaction.user.id, player_gold)  # Update gold in DB
            #await asyncio.sleep(10)
            #await message.delete()
            await multiplier_response.delete()
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to respond. The crash game has ended.")
            await message.delete()
        finally:
            self.bot.state_manager.clear_active(interaction.user.id)


    @app_commands.command(
        name="checkin",
        description="Check in at the tavern and receive a daily bonus!"
    )
    async def checkin(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Fetch user data
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        last_checkin_time = existing_user[17]
        checkin_remaining = None
        checkin_duration = timedelta(hours=18)
        if last_checkin_time:
            last_checkin_time_dt = datetime.fromisoformat(last_checkin_time)
            if (last_checkin_time_dt > datetime.now()):
                print(f"{last_checkin_time_dt} vs {datetime.now()}")
                checkin_remaining = last_checkin_time_dt - datetime.now()
            else:
                time_since_checkin = datetime.now() - last_checkin_time_dt
                if time_since_checkin < checkin_duration:
                    remaining_time = checkin_duration - time_since_checkin
                    checkin_remaining = remaining_time


        if checkin_remaining:
            # User is trying to check in before the next available check-in time
            value=(f"**{checkin_remaining.seconds // 3600} hours "
                    f"{(checkin_remaining.seconds // 60) % 60} minutes** "
                    f"remaining until your next /checkin is available.")
            await interaction.response.send_message(value, ephemeral=True)
            return
        else:
            await self.bot.database.users.update_timer(user_id, 'last_checkin_time')
            existing_user = await self.bot.database.users.get(user_id, server_id)
            last_checkin_time = existing_user[17]
            await self.bot.database.users.modify_currency(user_id, 'curios', 1)
            await self.bot.database.update_curios_bought(user_id, server_id, -existing_user[23])  # Resetting to 0
            await interaction.response.send_message((f"You have successfully checked in and received a **Curious Curio**!\n"
                                                     f"Use /curios to open it!"),
                                                     ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(Tavern(bot))