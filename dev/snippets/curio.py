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
            print(f"[DEBUG] Selected reward before adjustment: {selected_reward}")
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
                    loot_description) = await self.combat_cog.generate_loot(user_id, server_id, 100, False)
                    await self.bot.database.create_item(user_id, item_name, 100, 
                                                            attack_modifier, defence_modifier, rarity_modifier)
                    embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == "Level 100 Accessory":
                (acc_name, loot_description) = await self.combat_cog.generate_accessory(user_id, server_id, 100, False)
                lines = loot_description.splitlines()
                for line in lines[1:]:  # Skip the first line (the accessory name)
                            match = re.search(r"\+(\d+)%? (\w+)", line)  # Capture value and type
                            if match:
                                modifier_value = match.group(1) # save the value associated with the modifier
                                modifier_type = match.group(2) # save the value associated with the mod_type
                await self.bot.database.create_accessory(user_id, acc_name, 100, modifier_type, modifier_value)
                embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == "Level 100 Armor":
                armor_name, loot_description = await self.combat_cog.generate_armor(user_id, server_id, 100, False)
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
                    loot_description) = await self.combat_cog.generate_loot(user_id, server_id, user_level, False)
                    await self.bot.database.create_item(user_id, item_name, user_level, 
                                                            attack_modifier, defence_modifier, rarity_modifier)
                    embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == f"Level {user_level} Accessory":
                (acc_name, loot_description) = await self.combat_cog.generate_accessory(user_id, server_id, user_level, False)
                lines = loot_description.splitlines()
                for line in lines[1:]:  # Skip the first line (the accessory name)
                            match = re.search(r"\+(\d+)%? (\w+)", line)  # Capture value and type
                            if match:
                                modifier_value = match.group(1) # save the value associated with the modifier
                                modifier_type = match.group(2) # save the value associated with the mod_type
                await self.bot.database.create_accessory(user_id, acc_name, user_level, modifier_type, modifier_value)
                embed.add_field(name="✨ Loot", value=f"{loot_description}")
            elif selected_reward == f"Level {user_level} Armor":
                armor_name, loot_description = await self.combat_cog.generate_armor(user_id, server_id, user_level, False)
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
            print("Failed to respond to the interaction: Interaction not found.")
        except Exception as e:
            print(f"An error occurred: {e}")  # Catch and log other potential errors