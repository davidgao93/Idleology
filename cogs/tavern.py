import discord
from discord import app_commands, Interaction, ButtonStyle, Message
from discord.ext import commands
from discord.ui import View, Button
from datetime import datetime, timedelta
import asyncio
from core.minigames.views import CasinoMenuView, BlackjackView, RouletteView, CrashView, HorseRaceView

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
                    await self.bot.database.users.modify_stat(user_id, 'potions', 1)
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
            embed.set_image(url="https://i.imgur.com/Nv1JbrO.jpeg")
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
    @app_commands.describe(amount="The amount of gold to bet.")
    async def gamble(self, interaction: Interaction, amount: int) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return
        
        player_gold = existing_user[6]

        if amount <= 0:
            await interaction.response.send_message("You cannot bet zero or negative gold.", ephemeral=True)
            return
        
        if amount > player_gold:
            await interaction.response.send_message(f"You don't have enough gold! Current balance: **{player_gold:,}**.", ephemeral=True)
            return

        # 2. Set State & Launch Menu
        self.bot.state_manager.set_active(user_id, "gamble_menu")

        embed = discord.Embed(
            title="The Tavern Casino 🎲",
            description=f"You have placed **{amount:,} gold** on the table.\nSelect a game to play:",
            color=0xFFD700
        )
        embed.set_thumbnail(url="https://i.imgur.com/D8HlsQX.jpeg")
        
        embed.add_field(name="🃏 Blackjack", value="Beat the dealer to 21. (2x Payout)", inline=True)
        embed.add_field(name="🎡 Roulette", value="Red/Black/Parity/Number. (2x - 35x Payout)", inline=True)
        embed.add_field(name="🚀 Crash", value="Cash out before the rocket crashes! (1.0x - ???x)", inline=True)
        embed.add_field(name="🐎 Horse Racing", value="Pick the winning horse! (4x Payout)", inline=True)

        view = CasinoMenuView(self.bot, user_id, amount, self)
        
        await interaction.response.send_message(embed=embed, view=view)
        view.response = await interaction.original_response()

    # --- GAME HANDLERS ---

    async def start_blackjack(self, interaction: Interaction, amount: int):
        bj_view = BlackjackView(self.bot, interaction.user.id, amount, interaction)
        await bj_view.start_game()

    async def start_roulette(self, interaction: Interaction, amount: int):
        # Create Embed for Table
        embed = discord.Embed(title="🎡 Roulette Table", description=f"Betting **{amount:,} gold**.\nChoose your wager:", color=discord.Color.red())
        embed.set_thumbnail(url="https://i.imgur.com/D8HlsQX.jpeg")
        
        rl_view = RouletteView(self.bot, interaction.user.id, amount, interaction)
        
        # We edit the message here to transition from Menu -> Roulette
        await interaction.response.edit_message(embed=embed, view=rl_view)

    async def start_crash(self, interaction: Interaction, amount: int):
        # 1. Create View
        crash_view = CrashView(self.bot, interaction.user.id, amount, interaction)
        
        # 2. Transition Embed
        embed = discord.Embed(
            title="🚀 Preparing Launch...", 
            description=f"Fueling up for a bet of **{amount:,} gold**.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=crash_view)
        
        # 3. Start Game Logic
        await crash_view.start_game()

    async def start_horse_race(self, interaction: Interaction, amount: int):
            # 1. Create Embed
            embed = discord.Embed(
                title="🐎 Horse Racing", 
                description=f"Betting **{amount:,} gold**.\nPick your champion! (4x Payout)", 
                color=discord.Color.green()
            )
            embed.add_field(name="1. Thunder Hoof 🐎", value="Balanced speed.", inline=True)
            embed.add_field(name="2. Lightning Bolt 🦄", value="High risk, high speed.", inline=True)
            embed.add_field(name="3. Old Reliable 🦓", value="Consistent pace.", inline=True)
            embed.add_field(name="4. Dark Horse 🐫", value="Unpredictable.", inline=True)

            # 2. Create View
            race_view = HorseRaceView(self.bot, interaction.user.id, amount, interaction)
            
            # 3. Update Message
            await interaction.response.edit_message(embed=embed, view=race_view)



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
            await self.bot.database.users.modify_currency(user_id, 'curios_purchased_today', -existing_user[23])  # Resetting to 0
            await interaction.response.send_message((f"You have successfully checked in and received a **Curious Curio**!\n"
                                                     f"Use /curios to open it!"),
                                                     ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(Tavern(bot))