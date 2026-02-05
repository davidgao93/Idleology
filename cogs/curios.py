import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View
from core.combat.loot import generate_weapon, generate_armor, generate_accessory, generate_glove, generate_boot
import random
import csv


class CurioView(View):
    def __init__(self, bot, user_id, server_id, curio_count):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.curio_count = curio_count
        self.skills_cog = bot.get_cog("skills")
        self.message = None

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
            existing_user = await self.bot.database.users.get(user_id, server_id)
            if not await self.bot.check_user_registered(interaction, existing_user):
                self.bot.state_manager.clear_active(user_id)  
                return

            # Check if the user has enough curios
            if existing_user[22] < amount:
                await interaction.response.send_message("You do not have enough curios available.", ephemeral=True)
                self.bot.state_manager.clear_active(user_id)  
                return

            # Check inventory space
            items = await self.bot.database.fetch_user_weapons(user_id)
            accs = await self.bot.database.fetch_user_accessories(user_id)
            if (len(items) + amount > 60 or len(accs) + amount > 60):
                await interaction.response.send_message(
                    "Your inventory is too full to open this many curios, check your weapons/accessories.",
                    ephemeral=True
                )
                self.bot.state_manager.clear_active(user_id)  
                return

            # Check if skills_cog is available
            if not self.skills_cog:
                await interaction.response.send_message("Error: Skills system is not available.", ephemeral=True)
                self.bot.state_manager.clear_active(user_id)  
                return

            user_level = existing_user[4]
            rewards = {
                "Level 100 Weapon": 0.002,
                "Level 100 Accessory": 0.002,
                "Level 100 Armor": 0.002,
                "Level 100 Gloves": 0.002,
                "Level 100 Boots": 0.002,
                "Rune of Imbuing": 0.005,
                "Rune of Refinement": 0.02,
                "Rune of Potential": 0.02,
                "Rune of Shattering": 0.02,
                "100k": 0.10,
                "50k": 0.10,
                "10k": 0.10,
                "5k": 0.20,
                "1k": 0.05,
                "Ore": 0.125,
                "Wood": 0.125,
                "Fish": 0.125,
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
                image_url = item_images.get(selected_reward.replace(" ", "_"))
                self.bot.logger.info(image_url)
                if image_url:
                    reward_embed.set_image(url=image_url)
            else:
                reward_embed.set_image(url="https://i.imgur.com/wKyTFzh.jpg")

            # Process each reward
            loot_descriptions = []
            for reward, count in reward_summary.items():
                self.bot.logger.info(f"Processing reward: {reward} x{count}")
                if reward == "Level 100 Weapon":
                    for _ in range(count):
                        weapon = await generate_weapon(user_id, 100, drop_rune=False)
                        await self.bot.database.create_weapon(weapon)
                        loot_descriptions.append(weapon.description)
                elif reward == "Level 100 Accessory":
                    for _ in range(count):
                        acc = await generate_accessory(user_id, 100, drop_rune=False)
                        await self.bot.database.create_accessory(acc)
                        loot_descriptions.append(acc.description)
                elif reward == "Level 100 Armor":
                    for _ in range(count):
                        armor = await generate_armor(user_id, 100, drop_rune=False)
                        await self.bot.database.create_armor(armor)
                        loot_descriptions.append(armor.description)
                elif reward == "Level 100 Gloves":
                    for _ in range(count):
                        gloves = await generate_glove(user_id, 100)
                        await self.bot.database.create_glove(gloves)
                        loot_descriptions.append(gloves.description)
                elif reward == "Level 100 Boots":
                    for _ in range(count):
                        boots = await generate_boot(user_id, 100)
                        await self.bot.database.create_boot(boots)
                        loot_descriptions.append(boots.description)
                elif reward == "Rune of Refinement":
                    await self.bot.database.users.modify_currency(user_id, 'refinement_runes', count)
                elif reward == "Rune of Potential":
                    await self.bot.database.users.modify_currency(user_id, 'potential_runes', count)
                elif reward == "Rune of Imbuing":
                    await self.bot.database.users.modify_currency(user_id, 'imbue_runes', count)
                elif reward == "Rune of Shattering":
                    await self.bot.database.users.modify_currency(user_id, 'shatter_runes', count)
                elif reward in ["100k", "50k", "10k", "5k"]:
                    amount_mapping = {"100k": 100000, "50k": 50000, "10k": 10000, "5k": 5000, "1k": 1000}
                    await self.bot.database.users.modify_gold(user_id, amount_mapping[reward] * count)
                elif reward == "Ore":
                    for _ in range(count * 5):
                        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
                        resources = await self.skills_cog.gather_mining_resources(mining_data[2])
                        await self.bot.database.update_mining_resources(user_id, server_id, resources)
                elif reward == "Wood":
                    for _ in range(count * 5):
                        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
                        resources = await self.skills_cog.gather_woodcutting_resources(woodcutting_data[2])
                        await self.bot.database.update_woodcutting_resources(user_id, server_id, resources)
                elif reward == "Fish":
                    for _ in range(count * 5):
                        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)
                        resources = await self.skills_cog.gather_fishing_resources(fishing_data[2])
                        await self.bot.database.update_fishing_resources(user_id, server_id, resources)

            # Summarize rewards
            summary_text = "\n".join(f"{count}x {reward}" for reward, count in reward_summary.items())
            if loot_descriptions:
                summary_text += "\n\n__Loot Details__\n" + "\n".join(loot_descriptions)
            reward_embed.add_field(name="Rewards", value=summary_text, inline=False)

            # Update curio count
            await self.bot.database.modify_currency(user_id, 'curios', -amount)

            # Fetch updated curio count
            updated_user = await self.bot.database.users.get(user_id, server_id)
            self.curio_count = updated_user[22]

            # If no curios left, update embed and stop
            if self.curio_count == 0:
                reward_embed.add_field(name="All done!", value="You have **0** curios available.", inline=False)
                await interaction.response.edit_message(embed=reward_embed, view=None)
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
        if interaction:
            await interaction.response.edit_message(embed=embed, view=None)  # Remove buttons
        else:
            # Handle timeout case where interaction is None
            if self.message:
                await self.message.edit(embed=embed, view=None)  # Remove buttons
        self.bot.state_manager.clear_active(str(self.user_id))
        self.stop()

    def stop(self):
        # Perform actions when the view is stopped or times out
        self.bot.state_manager.clear_active(self.user_id)  # Clear the active user
        # if self.message:  # Ensure that the message exists
        #     asyncio.create_task(self.message.delete())  # Delete the message asynchronously
        super().stop()  # Call the base class stop method
    
    async def on_timeout(self):
        # Handle the timeout scenario explicitly
        embed = discord.Embed(
            title="Your Curios",
            description=f"You have **{self.curio_count}** curio{'s' if self.curio_count != 1 else ''} available.\nMay your curios always be lucky.",
            color=0x00FF00
        )
        if self.message:
            await self.message.edit(embed=embed, view=None)  # Remove buttons
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class Curios(commands.Cog, name="curios"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.skills_cog = bot.get_cog("skills")

    @app_commands.command(name="curios", description="Open a curio for rewards.")
    async def curios(self, interaction: Interaction) -> None:
        try:  
            user_id = str(interaction.user.id)
            server_id = str(interaction.guild.id)

            existing_user = await self.bot.database.users.get(user_id, server_id)
            if not await self.bot.check_user_registered(interaction, existing_user):
                return

            if not existing_user[22]:
                await interaction.response.send_message("You do not have any curios available.", ephemeral=True)
                return
            
            if not self.skills_cog:
                print(self.skills_cog)
                await interaction.response.send_message("Please slow down and try again.", ephemeral=True)
                self.bot.state_manager.clear_active(user_id)  
                return
            
            # if not await self.bot.is_maintenance(interaction, user_id):
            #    return
            
            items = await self.bot.database.fetch_user_weapons(user_id)
            accs = await self.bot.database.fetch_user_accessories(user_id)
            arms = await self.bot.database.fetch_user_armors(user_id)
            if (len(items) > 60 or len(accs) > 60 or len(arms) > 60):
                await interaction.response.send_message(
                    "Your inventory is too full to open this curio, check your equipment.",
                    ephemeral=True
                )
                return
            
            # User level
            user_level = existing_user[4]

            # Define curio rewards and their odds
            rewards = {
                "Level 100 Weapon": 0.002,
                "Level 100 Accessory": 0.002,
                "Level 100 Armor": 0.002,
                "Level 100 Gloves": 0.002,
                "Level 100 Boots": 0.002,
                "Rune of Imbuing": 0.005,
                "Rune of Refinement": 0.02,
                "Rune of Potential": 0.02,
                "Rune of Shattering": 0.02,
                "100k": 0.10,
                "50k": 0.10,
                "10k": 0.10,
                "5k": 0.20,
                "1k": 0.05,
                "Ore": 0.125,
                "Wood": 0.125,
                "Fish": 0.125,
            }

            reward_pool = []
            for reward, odds in rewards.items():
                count = int(odds * 1000)
                reward_pool.extend([reward] * count)


            selected_reward = random.choice(reward_pool)

            item_images = {}
            with open('assets/curios.csv', mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    item_images[row['Item']] = row['URL']

            self.bot.logger.info(f"Selected reward before adjustment: {selected_reward}")
            image_url = item_images.get(selected_reward.replace(" ", "_"))
            
            # Create an embed with the reward and the corresponding image
            embed = discord.Embed(
                title="Curio Reward!",
                description=f"You opened a curio and received: **{selected_reward}**!",
                color=0x00FF00
            )

            if image_url:
                embed.set_image(url=image_url)

            # Reward handling based on selected_reward
            if selected_reward == "Level 100 Weapon":
                weapon = await generate_weapon(user_id, 100, drop_rune=False)
                await self.bot.database.create_weapon(weapon)
                embed.add_field(name="✨ Loot", value=f"{weapon.description}", inline=False)
            
            elif selected_reward == "Level 100 Accessory":
                acc = await generate_accessory(user_id, 100, drop_rune=False)
                await self.bot.database.create_accessory(acc)
                embed.add_field(name="✨ Loot", value=f"{acc.description}", inline=False)
            
            elif selected_reward == "Level 100 Armor":
                armor = await generate_armor(user_id, 100, drop_rune=False)
                await self.bot.database.create_armor(armor)
                embed.add_field(name="✨ Loot", value=f"{armor.description}", inline=False)
            
            elif reward == "Level 100 Gloves":
                gloves = await generate_glove(user_id, 100)
                await self.bot.database.create_glove(gloves)
                embed.add_field(name="✨ Loot", value=f"{gloves.description}", inline=False)

            elif reward == "Level 100 Boots":
                for _ in range(count):
                    boots = await generate_boot(user_id, 100)
                    await self.bot.database.create_boot(boots)
                    embed.add_field(name="✨ Loot", value=f"{boots.description}", inline=False)
            
            elif selected_reward == "Rune of Refinement":
                await self.bot.database.users.modify_currency(user_id, 'refinement_runes', 1)
            
            elif selected_reward == "Rune of Potential":
                await self.bot.database.users.modify_currency(user_id, 'potential_runes', 1)
            
            elif selected_reward == "Rune of Imbuing":
                await self.bot.database.users.modify_currency(user_id, 'imbuing_runes', 1)
            
            elif selected_reward in ["100k", "50k", "10k", "5k", "1k"]:
                amount_mapping = {
                    "100k": 100000,
                    "50k": 50000,
                    "10k": 10000,
                    "5k": 5000,
                    "1k": 1000
                }
                await self.bot.database.users.modify_gold(user_id, amount_mapping[selected_reward])
            
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

            await interaction.response.send_message(embed=embed)
            await self.bot.database.modify_currency(user_id, 'curios', -1)
        except discord.errors.NotFound:
            self.bot.logger.info("Failed to respond to the interaction: Interaction not found.")
        except Exception as e:
            self.bot.logger.info(f"An error occurred: {e}")  # Catch and log other potential errors


    @app_commands.command(name="bulk_curios", description="Open many curios.")
    async def bulk_curios(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        try:
            existing_user = await self.bot.database.users.get(user_id, server_id)
            if not await self.bot.check_user_registered(interaction, existing_user):
                return
            
            if not existing_user[22]:
                await interaction.response.send_message("You do not have any curios available.", ephemeral=True)
                return

            if not self.skills_cog:
                await interaction.response.send_message("Error: Skills system is not available.", ephemeral=True)
                return
            
            self.bot.state_manager.set_active(user_id, "curios")
            curio_count = existing_user[22]
            embed = discord.Embed(
                title="Your Curios",
                description=f"You have **{curio_count}** curio{'s' if curio_count != 1 else ''} available.",
                color=0x00FF00
            )

            # Create view with buttons
            view = CurioView(self.bot, user_id, server_id, curio_count)
            message = await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
            
        except discord.errors.NotFound:
            self.bot.logger.info("Failed to respond to the interaction: Interaction not found.")
        except Exception as e:
            self.bot.logger.info(f"An error occurred: {e}")

async def setup(bot) -> None:
    await bot.add_cog(Curios(bot))
