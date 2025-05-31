import discord
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View
from datetime import datetime, timedelta
from core.loot import generate_loot, generate_armor, generate_accessory
from .skills import Skills
import asyncio
import random
import csv
import re
import math

class CurioView(View):
    def __init__(self, bot, user_id, server_id, curio_count, tavern_cog):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.curio_count = curio_count
        self.tavern_cog = tavern_cog

        # Define buttons
        self.add_button("🎁", self.open_one, 1, ButtonStyle.primary)
        self.add_button("🎁 x5", self.open_five, 5, ButtonStyle.primary)
        self.add_button("🎁 x10", self.open_ten, 10, ButtonStyle.primary)
        self.add_button("❌", self.close, 0, ButtonStyle.danger)

    def add_button(self, label, callback, curio_amount, style):
        button = Button(label=label, style=style, disabled=(self.curio_count < curio_amount and curio_amount > 0))
        button.callback = lambda interaction: callback(interaction, curio_amount)
        self.add_item(button)

    async def update_view(self, interaction: Interaction, curio_count: int, reward_embed=None):
        """Update button states and embed based on remaining curios and rewards."""
        self.curio_count = curio_count
        # Update button states
        for item in self.children:
            if isinstance(item, Button) and item.label != "❌":
                amount = int(item.label.split("x")[1]) if "x" in item.label else 1
                item.disabled = self.curio_count < amount

        # Create or update embed
        embed = discord.Embed(
            title="Your Curios",
            description=f"You have **{self.curio_count}** curio{'s' if self.curio_count != 1 else ''} available.",
            color=0x00FF00
        )
        if reward_embed:
            # Merge reward embed's fields and image into the main embed
            for field in reward_embed.fields:
                embed.add_field(name=field.name, value=field.value, inline=field.inline)
            if reward_embed.image:
                embed.set_image(url=reward_embed.image.url)

        await interaction.response.edit_message(embed=embed, view=self)

    async def open_curios(self, interaction: Interaction, amount: int):
        try:
            user_id = self.user_id
            server_id = self.server_id

            # Fetch user data
            existing_user = await self.bot.database.fetch_user(user_id, server_id)
            if not await self.bot.check_user_registered(interaction, existing_user):
                self.bot.state_manager.clear_active(user_id)  
                return

            # Check if the user has enough curios
            if existing_user[22] < amount:
                await interaction.response.send_message("You do not have enough curios available.", ephemeral=True)
                self.bot.state_manager.clear_active(user_id)  
                return

            # Check inventory space
            items = await self.bot.database.fetch_user_items(user_id)
            accs = await self.bot.database.fetch_user_accessories(user_id)
            if (len(items) + amount > 60 or len(accs) + amount > 60):
                await interaction.response.send_message(
                    "Your inventory is too full to open this many curios, check your weapons/accessories.",
                    ephemeral=True
                )
                self.bot.state_manager.clear_active(user_id)  
                return

            # Check if skills_cog is available
            if not self.tavern_cog.skills_cog:
                await interaction.response.send_message("Error: Skills system is not available.", ephemeral=True)
                self.bot.state_manager.clear_active(user_id)  
                return

            user_level = existing_user[4]
            rewards = {
                "Level 100 Weapon": 0.0045,
                "Level 100 Accessory": 0.0045,
                "Level 100 Armor": 0.001,
                "Rune of Imbuing": 0.005,
                "Rune of Refinement": 0.0175,
                "Rune of Potential": 0.0175,
                "ilvl Weapon": 0.095,
                "ilvl Accessory": 0.045,
                "ilvl Armor": 0.01,
                "100k": 0.1,
                "50k": 0.1,
                "10k": 0.1,
                "5k": 0.2,
                "Ore": 0.1,
                "Wood": 0.1,
                "Fish": 0.1,
            }

            # Prepare the reward pool
            reward_pool = []
            for reward, odds in rewards.items():
                count = int(odds * 1000)
                reward_pool.extend([reward] * count)

            # Load item images
            item_images = {}
            with open('assets/curios.csv', mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    item_images[row['Item']] = row['URL']

            # Process rewards
            selected_rewards = [random.choice(reward_pool) for _ in range(amount)]
            reward_summary = {}
            for reward in selected_rewards:
                reward_summary[reward] = reward_summary.get(reward, 0) + 1

            # Create reward embed
            reward_embed = discord.Embed(
                title="Curio Reward!",
                description=f"You opened {amount} curio{'s' if amount > 1 else ''}!",
                color=0x00FF00
            )

            # Set image based on amount
            if amount == 1:
                selected_reward = selected_rewards[0]
                if selected_reward == "ilvl Weapon":
                    selected_reward = f"Level {user_level} Weapon"
                elif selected_reward == "ilvl Accessory":
                    selected_reward = f"Level {user_level} Accessory"
                elif selected_reward == "ilvl Armor":
                    selected_reward = f"Level {user_level} Armor"
                image_url = item_images.get(selected_reward.replace(" ", "_"))
                self.bot.logger.info(image_url)
                if image_url:
                    reward_embed.set_image(url=image_url)
            else:
                reward_embed.set_image(url="https://i.imgur.com/wKyTFzh.jpg")

            # Process each reward
            loot_descriptions = []
            for reward, count in reward_summary.items():
                self.bot.logger.info(f"[DEBUG] Processing reward: {reward} x{count}")
                if reward == "Level 100 Weapon":
                    for _ in range(count):
                        item_name, attack_modifier, defence_modifier, rarity_modifier, loot_description = await generate_loot(100, drop_rune=False)
                        await self.bot.database.create_item(user_id, item_name, 100, attack_modifier, defence_modifier, rarity_modifier)
                        loot_descriptions.append(loot_description)
                elif reward == "Level 100 Accessory":
                    for _ in range(count):
                        acc_name, loot_description = await generate_accessory(100, drop_rune=False)
                        lines = loot_description.splitlines()
                        for line in lines[1:]:
                            match = re.search(r"\+(\d+)%? (\w+)", line)
                            if match:
                                modifier_value = match.group(1)
                                modifier_type = match.group(2)
                        await self.bot.database.create_accessory(user_id, acc_name, 100, modifier_type, modifier_value)
                        loot_descriptions.append(loot_description)
                elif reward == "Level 100 Armor":
                    for _ in range(count):
                        armor_name, loot_description = await generate_armor(100, drop_rune=False)
                        lines = loot_description.splitlines()
                        block_modifier = evasion_modifier = ward_modifier = 0
                        for line in lines[1:]:
                            match = re.search(r"\+(\d+)%? (\w+)", line)
                            if match:
                                modifier_value = int(match.group(1))
                                modifier_type = match.group(2).lower()
                                if modifier_type == "block":
                                    block_modifier = modifier_value
                                elif modifier_type == "evasion":
                                    evasion_modifier = modifier_value
                                elif modifier_type == "ward":
                                    ward_modifier = modifier_value
                        await self.bot.database.create_armor(user_id, armor_name, 100, block_modifier, evasion_modifier, ward_modifier)
                        loot_descriptions.append(loot_description)
                elif reward == "ilvl Weapon":
                    for _ in range(count):
                        item_name, attack_modifier, defence_modifier, rarity_modifier, loot_description = await generate_loot(user_level, drop_rune=False)
                        await self.bot.database.create_item(user_id, item_name, user_level, attack_modifier, defence_modifier, rarity_modifier)
                        loot_descriptions.append(loot_description)
                elif reward == "ilvl Accessory":
                    for _ in range(count):
                        acc_name, loot_description = await generate_accessory(user_level, drop_rune=False)
                        lines = loot_description.splitlines()
                        for line in lines[1:]:
                            match = re.search(r"\+(\d+)%? (\w+)", line)
                            if match:
                                modifier_value = match.group(1)
                                modifier_type = match.group(2)
                        await self.bot.database.create_accessory(user_id, acc_name, user_level, modifier_type, modifier_value)
                        loot_descriptions.append(loot_description)
                elif reward == "ilvl Armor":
                    for _ in range(count):
                        armor_name, loot_description = await generate_armor(user_level, drop_rune=False)
                        lines = loot_description.splitlines()
                        block_modifier = evasion_modifier = ward_modifier = 0
                        for line in lines[1:]:
                            match = re.search(r"\+(\d+)%? (\w+)", line)
                            if match:
                                modifier_value = int(match.group(1))
                                modifier_type = match.group(2).lower()
                                if modifier_type == "block":
                                    block_modifier = modifier_value
                                elif modifier_type == "evasion":
                                    evasion_modifier = modifier_value
                                elif modifier_type == "ward":
                                    ward_modifier = modifier_value
                        await self.bot.database.create_armor(user_id, armor_name, user_level, block_modifier, evasion_modifier, ward_modifier)
                        loot_descriptions.append(loot_description)
                elif reward == "Rune of Refinement":
                    await self.bot.database.update_refinement_runes(user_id, count)
                elif reward == "Rune of Potential":
                    await self.bot.database.update_potential_runes(user_id, count)
                elif reward == "Rune of Imbuing":
                    await self.bot.database.update_imbuing_runes(user_id, count)
                elif reward in ["100k", "50k", "10k", "5k"]:
                    amount_mapping = {"100k": 100000, "50k": 50000, "10k": 10000, "5k": 5000}
                    await self.bot.database.add_gold(user_id, amount_mapping[reward] * count)
                elif reward == "Ore":
                    for _ in range(count * 5):
                        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
                        resources = await self.tavern_cog.skills_cog.gather_mining_resources(mining_data[2])
                        await self.bot.database.update_mining_resources(user_id, server_id, resources)
                elif reward == "Wood":
                    for _ in range(count * 5):
                        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
                        resources = await self.tavern_cog.skills_cog.gather_woodcutting_resources(woodcutting_data[2])
                        await self.bot.database.update_woodcutting_resources(user_id, server_id, resources)
                elif reward == "Fish":
                    for _ in range(count * 5):
                        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)
                        resources = await self.tavern_cog.skills_cog.gather_fishing_resources(fishing_data[2])
                        await self.bot.database.update_fishing_resources(user_id, server_id, resources)

            # Summarize rewards
            summary_text = "\n".join(f"{count}x {reward}" for reward, count in reward_summary.items())
            if loot_descriptions:
                summary_text += "\n\n**Loot Details:**\n" + "\n".join(loot_descriptions)
            reward_embed.add_field(name="Rewards", value=summary_text, inline=False)

            # Update curio count
            await self.bot.database.update_curios_count(user_id, server_id, -amount)

            # Fetch updated curio count
            updated_user = await self.bot.database.fetch_user(user_id, server_id)
            self.curio_count = updated_user[22]

            # If no curios left, update embed and stop
            if self.curio_count == 0:
                reward_embed.add_field(name="All done!", value="You have **0** curios available.", inline=False)
                await interaction.response.edit_message(embed=reward_embed)
                self.stop()
                self.bot.state_manager.clear_active(user_id)  
                return

            # Update the existing message with the new embed
            await self.update_view(interaction, self.curio_count, reward_embed)

        except discord.errors.NotFound:
            self.bot.state_manager.clear_active(user_id)  
            self.bot.logger.info("Failed to respond to the interaction: Interaction not found.")
        except Exception as e:
            self.bot.state_manager.clear_active(user_id)
            self.bot.logger.info(f"An error occurred: {e}")

    async def open_one(self, interaction: Interaction, amount: int):
        await self.open_curios(interaction, amount)

    async def open_five(self, interaction: Interaction, amount: int):
        await self.open_curios(interaction, amount)

    async def open_ten(self, interaction: Interaction, amount: int):
        await self.open_curios(interaction, amount)

    async def close(self, interaction: Interaction, amount: int):
        embed = discord.Embed(
            title="Your Curios",
            description=f"You have **{self.curio_count}** curio{'s' if self.curio_count != 1 else ''} available.\nMay your curios always be lucky.",
            color=0x00FF00
        )
        await interaction.response.edit_message(embed=embed, view=None)
        # self.bot.logger.info(interaction.user.id)
        self.bot.state_manager.clear_active(str(interaction.user.id))
        self.stop()

    def stop(self):
        # Perform actions when the view is stopped or times out
        self.bot.state_manager.clear_active(self.user_id)  # Clear the active user
        if self.message:  # Ensure that the message exists
            asyncio.create_task(self.message.delete())  # Delete the message asynchronously
        super().stop()  # Call the base class stop method
    
    async def on_timeout(self):
        # Handle the timeout scenario explicitly
        self.stop()  # Call stop() to handle cleanup
        # await self.message.edit(content="This action has timed out.", embed=None, view=None)  # Optionally edit the message to indicate timeout


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

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
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
        embed.add_field(name="Potion 🍹 x1 / x5 / x10", value=f"Cost: {cost} / {cost * 5} / {cost * 10} gold", inline=False)

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

        reactions = ["🍹", "5️⃣", "🔟", "🎁", "❌"]  # Added ❌ reaction for closing shop
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        def check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id

        try:
            self.bot.state_manager.set_active(user_id, "shop") 
            while True:
                existing_user = await self.bot.database.fetch_user(user_id, server_id)
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

                if str(reaction.emoji) in ["🍹", "5️⃣", "🔟"]:
                    times = 1 if str(reaction.emoji) == "🍹" else (5 if str(reaction.emoji) == "5️⃣" else 10)

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
                    await self.bot.database.add_gold(user_id, -cost)
                    await self.bot.database.increase_potion_count(user_id)
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
                    await self.bot.database.add_gold(user_id, -curio_cost)
                    await self.bot.database.update_curios_count(user_id, server_id, 1)
                    await self.bot.database.update_curios_bought(user_id, server_id, 1)

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
        await self.bot.database.update_user_gold(user_id, gold)  # Update the user's gold in DB


    @app_commands.command(
        name="rest",
        description="Rest your weary body and mind for the adventure ahead."
    )
    async def rest(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
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
            await self.bot.database.update_player_hp(user_id, max_hp)
            await self.bot.database.update_rest_time(user_id)
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
            await self.bot.database.update_player_hp(user_id, max_hp)  # Set current HP to max HP
            await self.bot.database.update_rest_time(user_id)  # Reset last rest time
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
                        await self.bot.database.update_player_hp(user_id, max_hp)  # Update HP to max
                        await self.bot.database.update_user_gold(user_id, new_gold)  # Update gold
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
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
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
        await self.bot.database.update_user_gold(interaction.user.id, player_gold)  # Update gold in DB

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
        await self.bot.database.update_user_gold(interaction.user.id, player_gold)  # Update gold in DB
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
        await self.bot.database.update_user_gold(interaction.user.id, player_gold)  # Update gold in DB
        #await asyncio.sleep(10)
        #await message.delete()

    async def play_roulette(self, interaction: Interaction, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a simple Roulette game."""
        embed.clear_fields()
        
        player_gold -= bet_amount  # Deduct the bet
        await self.bot.database.update_user_gold(interaction.user.id, player_gold)  # Update gold in DB
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
            await self.bot.database.update_user_gold(interaction.user.id, player_gold)  # Update gold in DB
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
        await self.bot.database.update_user_gold(interaction.user.id, player_gold)  # Update gold in DB
        #await asyncio.sleep(10)
        #await message.delete()

    async def play_crash(self, interaction: Interaction, player_gold: int, bet_amount: int, message, embed) -> None:
        """Simulate a Crash game."""
        player_gold -= bet_amount  # Deduct the bet
        await self.bot.database.update_user_gold(interaction.user.id, player_gold)  # Update gold in DB

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
            await self.bot.database.update_user_gold(interaction.user.id, player_gold)  # Update gold in DB
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
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        last_checkin_time = existing_user[17]
        checkin_remaining = None
        checkin_duration = timedelta(hours=18)
        if last_checkin_time:
            last_checkin_time_dt = datetime.fromisoformat(last_checkin_time)
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
            await self.bot.database.update_checkin_time(user_id)
            existing_user = await self.bot.database.fetch_user(user_id, server_id)
            last_checkin_time = existing_user[17]
            await self.bot.database.update_curios_count(user_id, server_id, 1)
            await self.bot.database.update_curios_bought(user_id, server_id, -existing_user[23])  # Resetting to 0
            await interaction.response.send_message((f"You have successfully checked in and received a **Curious Curio**!\n"
                                                     f"Use /curios to open it!"),
                                                     ephemeral=True)


    @app_commands.command(name="curios", description="Open a curio for rewards.")
    async def curios(self, interaction: Interaction) -> None:
        try:  
            user_id = str(interaction.user.id)
            server_id = str(interaction.guild.id)

            # Fetch user data
            existing_user = await self.bot.database.fetch_user(user_id, server_id)
            if not await self.bot.check_user_registered(interaction, existing_user):
                return

            # Check if the user has a curio
            if not existing_user[22]:
                await interaction.response.send_message("You do not have any curios available.")
                return
            
            # if not await self.bot.is_maintenance(interaction, user_id):
            #    return
            
            items = await self.bot.database.fetch_user_items(user_id)
            accs = await self.bot.database.fetch_user_accessories(user_id)

            if (len(items) > 60 or len(accs) > 60):
                await interaction.response.send_message(
                    "Your inventory is too full to open this curio, check your weapons/accessories.",
                    ephemeral=True
                )
                return
            # User level
            user_level = existing_user[4]

            # Define curio rewards and their odds
            rewards = {
                "Level 100 Weapon": 0.0045,
                "Level 100 Accessory": 0.0045,
                "Level 100 Armor": 0.001,
                "Rune of Imbuing": 0.005,
                "Rune of Refinement": 0.0175,
                "Rune of Potential": 0.0175,
                "ilvl Weapon": 0.095,
                "ilvl Accessory": 0.045,
                "ilvl Armor": 0.01,
                "100k": 0.1,
                "50k": 0.1,
                "10k": 0.1,
                "5k": 0.2,
                "Ore": 0.1,
                "Wood": 0.1,
                "Fish": 0.1,
            }

            # Prepare the reward pool based on the odds.
            reward_pool = []
            for reward, odds in rewards.items():
                # Using a more explicit calculation for determining how many times to repeat each reward
                count = int(odds * 1000)  # Scale odds to make selection easier.
                reward_pool.extend([reward] * count)

            # Selection of a reward
            selected_reward = random.choice(reward_pool)
            # Load item images from the provided CSV file
            item_images = {}
            with open('assets/curios.csv', mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    item_images[row['Item']] = row['URL']
            # Debug message for selected reward
            self.bot.logger.info(f"[DEBUG] Selected reward before adjustment: {selected_reward}")
            image_url = item_images.get(selected_reward.replace(" ", "_"))  # Replace spaces with underscores
            # Adjust the ilvl rewards to match user's level
            if selected_reward == "ilvl Weapon":
                selected_reward = f"Level {user_level} Weapon"
                image_url = item_images.get("ilvl Weapon".replace(" ", "_"))  # Replace spaces with underscores
            elif selected_reward == "ilvl Accessory":
                selected_reward = f"Level {user_level} Accessory"
                image_url = item_images.get("ilvl Accessory".replace(" ", "_"))  # Replace spaces with underscores
            elif selected_reward == "ilvl Armor": 
                selected_reward = f"Level {user_level} Armor"
                image_url = item_images.get("ilvl Armor".replace(" ", "_"))  # Replace spaces with underscores
            
            # Create an embed with the reward and the corresponding image
            embed = discord.Embed(
                title="Curio Reward!",
                description=f"You opened a curio and received: **{selected_reward}**!",
                color=0x00FF00
            )

            # Add the image if it exists in item_images
            if image_url:
                embed.set_image(url=image_url)

            # Reward handling based on selected_reward
            if selected_reward == "Level 100 Weapon":
                    (item_name, 
                    attack_modifier, 
                    defence_modifier,
                    rarity_modifier, 
                    loot_description) = await generate_loot(100, drop_rune=False)
                    await self.bot.database.create_item(user_id, item_name, 100, 
                                                            attack_modifier, defence_modifier, rarity_modifier)
                    embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == "Level 100 Accessory":
                (acc_name, loot_description) = await generate_accessory(100, drop_rune=False)
                lines = loot_description.splitlines()
                for line in lines[1:]:  # Skip the first line (the accessory name)
                            match = re.search(r"\+(\d+)%? (\w+)", line)  # Capture value and type
                            if match:
                                modifier_value = match.group(1) # save the value associated with the modifier
                                modifier_type = match.group(2) # save the value associated with the mod_type
                await self.bot.database.create_accessory(user_id, acc_name, 100, modifier_type, modifier_value)
                embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == "Level 100 Armor":
                armor_name, loot_description = await generate_armor(100, drop_rune=False)
                lines = loot_description.splitlines()
                block_modifier = 0
                evasion_modifier = 0
                ward_modifier = 0
                for line in lines[1:]:
                    match = re.search(r"\+(\d+)%? (\w+)", line)
                    if match:
                        modifier_value = int(match.group(1))
                        modifier_type = match.group(2).lower()
                        if modifier_type == "block":
                            block_modifier = modifier_value
                        elif modifier_type == "evasion":
                            evasion_modifier = modifier_value
                        elif modifier_type == "ward":
                            ward_modifier = modifier_value
                await self.bot.database.create_armor(user_id, armor_name, 100, block_modifier, evasion_modifier, ward_modifier)
                embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == f"Level {user_level} Weapon":
                    (item_name, 
                    attack_modifier, 
                    defence_modifier,
                    rarity_modifier, 
                    loot_description) = await generate_loot(user_level, drop_rune=False)
                    await self.bot.database.create_item(user_id, item_name, user_level, 
                                                            attack_modifier, defence_modifier, rarity_modifier)
                    embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == f"Level {user_level} Accessory":
                (acc_name, loot_description) = await generate_accessory(user_level, drop_rune=False)
                lines = loot_description.splitlines()
                for line in lines[1:]:  # Skip the first line (the accessory name)
                            match = re.search(r"\+(\d+)%? (\w+)", line)  # Capture value and type
                            if match:
                                modifier_value = match.group(1) # save the value associated with the modifier
                                modifier_type = match.group(2) # save the value associated with the mod_type
                await self.bot.database.create_accessory(user_id, acc_name, user_level, modifier_type, modifier_value)
                embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == f"Level {user_level} Armor":
                armor_name, loot_description = await generate_armor(user_level, drop_rune=False)
                lines = loot_description.splitlines()
                block_modifier = 0
                evasion_modifier = 0
                ward_modifier = 0
                for line in lines[1:]:
                    match = re.search(r"\+(\d+)%? (\w+)", line)
                    if match:
                        modifier_value = int(match.group(1))
                        modifier_type = match.group(2).lower()
                        if modifier_type == "block":
                            block_modifier = modifier_value
                        elif modifier_type == "evasion":
                            evasion_modifier = modifier_value
                        elif modifier_type == "ward":
                            ward_modifier = modifier_value
                await self.bot.database.create_armor(user_id, armor_name, user_level, block_modifier, evasion_modifier, ward_modifier)
                embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == "Rune of Refinement":
                await self.bot.database.update_refinement_runes(user_id, 1)
            elif selected_reward == "Rune of Potential":
                await self.bot.database.update_potential_runes(user_id, 1)
            elif selected_reward == "Rune of Imbuing":
                await self.bot.database.update_imbuing_runes(user_id, 1)
            elif selected_reward in ["100k", "50k", "10k", "5k"]:
                amount_mapping = {
                    "100k": 100000,
                    "50k": 50000,
                    "10k": 10000,
                    "5k": 5000,
                }
                await self.bot.database.add_gold(user_id, amount_mapping[selected_reward])
            elif selected_reward == "Ore":
                for _ in range(5):
                    mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
                    resources = await self.skills_cog.gather_mining_resources(mining_data[2])  # fetching pickaxe tier
                    await self.bot.database.update_mining_resources(user_id, server_id, resources)

            elif selected_reward == "Wood":
                for _ in range(5):
                    woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
                    resources = await self.skills_cog.gather_woodcutting_resources(woodcutting_data[2])  # fetching axe type
                    await self.bot.database.update_woodcutting_resources(user_id, server_id, resources)

            elif selected_reward == "Fish":
                for _ in range(5):
                    fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)
                    resources = await self.skills_cog.gather_fishing_resources(fishing_data[2])  # fetching fishing rod
                    await self.bot.database.update_fishing_resources(user_id, server_id, resources)
            # Send the embed
            await interaction.response.send_message(embed=embed)
            await self.bot.database.update_curios_count(user_id, server_id, -1)
        except discord.errors.NotFound:
            self.bot.logger.info("Failed to respond to the interaction: Interaction not found.")
        except Exception as e:
            self.bot.logger.info(f"An error occurred: {e}")  # Catch and log other potential errors


    @app_commands.command(name="bulk_curios", description="Open many curios.")
    async def bulk_curios(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        self.bot.logger.info(f'Check if {user_id} is active')
        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        try:
            # Fetch user data
            existing_user = await self.bot.database.fetch_user(user_id, server_id)
            if not await self.bot.check_user_registered(interaction, existing_user):
                return

            # Check if skills_cog is available
            if not self.skills_cog:
                await interaction.response.send_message("Error: Skills system is not available.", ephemeral=True)
                return
            
            # if not await self.bot.is_maintenance(interaction, user_id):
            #     return
            self.bot.logger.info('Set active')
            self.bot.state_manager.set_active(user_id, "curios")
            # Create embed showing curio count
            curio_count = existing_user[22]
            embed = discord.Embed(
                title="Your Curios",
                description=f"You have **{curio_count}** curio{'s' if curio_count != 1 else ''} available.",
                color=0x00FF00
            )

            # If no curios, send embed without buttons
            if curio_count == 0:
                await interaction.response.send_message(embed=embed)
                return

            # Create view with buttons
            view = CurioView(self.bot, user_id, server_id, curio_count, self)
            await interaction.response.send_message(embed=embed, view=view)
            
        except discord.errors.NotFound:
            self.bot.logger.info("Failed to respond to the interaction: Interaction not found.")
        except Exception as e:
            self.bot.logger.info(f"An error occurred: {e}")

async def setup(bot) -> None:
    await bot.add_cog(Tavern(bot))