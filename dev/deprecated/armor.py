import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message
import asyncio
import random


# Here we name the cog and create a new class for the cog.
class Armor(commands.Cog, name="armor"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="armor", description="View your character's armor and modify them.")
    async def armor(self, interaction: Interaction) -> None:
        """Fetch and display the character's armors with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if not await self.bot.is_maintenance(interaction, user_id):
            return

        # Check if the user has any active operations
        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        armors = await self.bot.database.fetch_user_armors(user_id)
        
        if not armors:
            await interaction.response.send_message("You peer into your armor pouch, it is empty.")
            return
        
        player_name = existing_user[3]
        embed = discord.Embed(
            title=f"🛡️",
            description=f"{player_name}'s Armors:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/NTVHFL8.png")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")  # Set inventory as active operation

        # Pagination setup
        items_per_page = 5
        total_pages = (len(armors) + items_per_page - 1) // items_per_page  # Ceiling division
        current_page = 0
        number_emojis = ["❌", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        while True:
            armors = await self.bot.database.fetch_user_armors(user_id)
            total_pages = (len(armors) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1)  # Ensure current_page is valid
            embed.description = f"{player_name}'s Armor (Page {current_page + 1}/{total_pages}):"
            if not armors:
                await interaction.followup.send("You peer into your armor pouch, it is empty.")
                break

            armors.sort(key=lambda armor: armor[3], reverse=True)  # item_level at index 3
            start_idx = current_page * items_per_page
            armors_to_display = armors[start_idx:start_idx + items_per_page]
            await message.clear_reactions()
            embed.clear_fields()
            armors_display_string = ""

            for index, armor in enumerate(armors_to_display):
                armor_name = armor[2]  # item_name at index 2
                armor_level = armor[3]  # item_level at index 3
                equipped_armor = await self.bot.database.get_equipped_armor(user_id)
                is_equipped = equipped_armor and (equipped_armor[0] == armor[0])
                
                # Append armor details to the display string
                armors_display_string += (
                    f"{number_emojis[index + 1]}: "
                    f"{armor_name} (Level {armor_level})"
                    f"{' [E]' if is_equipped else ''}\n"
                )
            
            # Add a single field for all armors
            embed.add_field(
                name="Armors:",
                value=armors_display_string.strip(),
                inline=False
            )
                
            # Add instructions and page info
            embed.add_field(
                name="Instructions",
                value=(f"[ℹ️] Select an armor to interact with.\n"
                       f"[◀️] Previous page | [▶️] Next page | [❌] Close interface."),
                inline=False
            )
            await message.edit(embed=embed)
            
            # Add reactions: number emojis for armors, navigation, and exit
            for i in range(len(armors_to_display) + 1):
                await message.add_reaction(number_emojis[i])
            if current_page > 0:
                await message.add_reaction("◀️")
            if current_page < total_pages - 1:
                await message.add_reaction("▶️")

            def check(reaction, user):
                return (user == interaction.user
                        and reaction.message.id == message.id
                        and str(reaction.emoji) in number_emojis + ["◀️", "▶️"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                reaction_str = str(reaction.emoji)
                
                if reaction_str == "◀️" and current_page > 0:
                    current_page -= 1
                    continue
                elif reaction_str == "▶️" and current_page < total_pages - 1:
                    current_page += 1
                    continue
                elif reaction_str == "❌":
                    await message.delete()
                    self.bot.state_manager.clear_active(user_id)
                    break
                
                selected_index = number_emojis.index(reaction_str) - 1
                if selected_index >= 0:
                    while True:
                        selected_armor = armors_to_display[selected_index]
                        print(f'Fetching {selected_armor} from db again for refresh')
                        selected_armor = await self.bot.database.fetch_armor_by_id(selected_armor[0])
                        if not selected_armor:
                            break
                        # Display selected armor details
                        armor_name = selected_armor[2]
                        armor_level = selected_armor[3]
                        armor_block = selected_armor[4]
                        armor_evasion = selected_armor[5]
                        armor_ward = selected_armor[6]
                        armor_passive = selected_armor[7]
                        embed.description = f"**{armor_name}** (i{armor_level}):"
                        embed.clear_fields()
                        if (armor_block > 0):
                            embed.add_field(name="Block", value=armor_block, inline=True)
                            embed.add_field(name="Effect", 
                                            value=f"{int(armor_block / 200)}% to reduce initial monster hit to 0",
                                            inline=True)
                        if (armor_evasion > 0):
                            embed.add_field(name="Evasion", value=armor_evasion, inline=True)
                            embed.add_field(name="Effect", 
                                value=f"{int(armor_evasion / 4)} flat decrease to monster accuracy",
                                inline=True)
                        if (armor_ward > 0):
                            embed.add_field(name="Ward", value=f"{armor_ward}%", inline=True)
                            embed.add_field(name="Effect", 
                                value=f"{int(armor_ward)}% additional temporary max hp",
                                inline=True)
                        if armor_passive != "none":
                            effect_description = self.get_armor_passive_effect(armor_passive)
                            embed.add_field(name="Passive", value=armor_passive, inline=False)
                            embed.add_field(name="Effect", value=effect_description, inline=False)
                        armor_guide = (
                            "🛡️ to equip.\n"
                            "🔨 to temper.\n"
                            "🔅 to imbue.\n"
                            "🗑️ to discard.\n"
                            "◀️ to go back."
                        )
                        embed.add_field(name="Armor Guide", value=armor_guide, inline=False)
                        await message.edit(embed=embed)
                        await message.clear_reactions()
                        action_reactions = ["🛡️", "🔨", "🔅", "🗑️", "◀️"]
                        for emoji in action_reactions:
                            await message.add_reaction(emoji)

                        def action_check(r, u):
                            return u == interaction.user and r.message.id == message.id and str(r.emoji) in action_reactions

                        try:
                            action_reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=action_check)
                            if str(action_reaction.emoji) == "🛡️":
                                if selected_armor[8] == 1:
                                    embed.add_field(name="But why", value=f"You already have this equipped.", inline=False)
                                    await message.edit(embed=embed)
                                else:
                                    await self.bot.database.equip_armor(user_id, selected_armor[0])
                                    embed.add_field(name="Equip", value=f"Equipped armor.", inline=False)
                                    await message.edit()
                                await asyncio.sleep(3)
                                continue
                            elif str(action_reaction.emoji) == "🔨":
                                await self.temper_armor(interaction, selected_armor, embed, message)
                                continue
                            elif str(action_reaction.emoji) == "🔅":
                                await self.imbue_armor(interaction, selected_armor, embed, message)
                                continue
                            elif str(action_reaction.emoji) == "🗑️":
                                await self.discard_armor(interaction, selected_armor, message, embed)
                                continue
                            elif str(action_reaction.emoji) == "◀️":
                                break

                        except asyncio.TimeoutError:
                            await message.delete()
                            self.bot.state_manager.clear_active(interaction.user.id)
                            break

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)
                break
        self.bot.state_manager.clear_active(user_id)


    async def temper_armor(self, 
                           interaction: Interaction, 
                           selected_armor: tuple,
                           embed, 
                           message) -> None:
        """Temper an armor piece to increase its modifier."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        armor_id = selected_armor[0]
        armor_name = selected_armor[2]
        armor_level = selected_armor[3]
        # Fetch current armor details
        armor_details = await self.bot.database.fetch_armor_by_id(armor_id)
        
        if not armor_details:
            await interaction.followup.send("Armor not found.")
            return

        # Get the current state of the armor
        tempers_remaining = armor_details[9]  # temper_remaining at index 9
        print(f'Tempers remaining for armor id {armor_id}: {tempers_remaining}')
        # Define the costs lookup based on the tempers remaining
        base_success_rate = 0.8
        if armor_level <= 40:
            costs = {
                3: (20, 20, 20, 500),
                2: (20, 20, 20, 100),
                1: (20, 20, 20, 2000),
            }
            cost_index = 6 - tempers_remaining
            success_rate = base_success_rate - (3 - tempers_remaining) * 0.05
            tempers_data = {
                3: ('iron', 'oak', 'desiccated'),
                2: ('coal', 'willow', 'regular'),
                1: ('gold', 'mahogany', 'sturdy'),
            }
        elif 40 < armor_level <= 80:    
            costs = {
                4: (50, 50, 50, 500),
                3: (50, 50, 50, 1500),
                2: (50, 50, 50, 3000),
                1: (50, 50, 50, 6000),
            }       
            tempers_data = {
                4: ('iron', 'oak', 'desiccated'),
                3: ('coal', 'willow', 'regular'),
                2: ('gold', 'mahogany', 'sturdy'),
                1: ('platinum', 'magic', 'reinforced'),
            }
            cost_index = 7 - tempers_remaining
            success_rate = base_success_rate - (4 - tempers_remaining) * 0.05 
        else:
            costs = {
                5: (100, 100, 100, 500),
                4: (100, 100, 100, 2000),
                3: (100, 100, 100, 5000),
                2: (100, 100, 100, 10000),
                1: (100, 100, 100, 20000),
            }
            tempers_data = {
                5: ('iron', 'oak', 'desiccated'),
                4: ('coal', 'willow', 'regular'),
                3: ('gold', 'mahogany', 'sturdy'),
                2: ('platinum', 'magic', 'reinforced'),
                1: ('idea', 'idea', 'titanium'),
            }
            cost_index = 8 - tempers_remaining
            success_rate = base_success_rate - (5 - tempers_remaining) * 0.05
        success_rate = max(0, min(success_rate, 1))
        # Check if there are tempers remaining
        if tempers_remaining == 0:
            embed.add_field(name="Tempering", value=f"This armor cannot be tempered anymore.", inline=True)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]  # Fetch the amount of gold from existing_user

        # Resources from the mining, woodcutting, and fishing tables
        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

        # Get the corresponding costs based on tempers remaining
        ore_cost, wood_cost, bone_cost, gp_cost = costs[tempers_remaining]
        print(f'temper will cost {ore_cost} ore, {wood_cost} logs, {bone_cost} bones, {gp_cost} gp')

        if tempers_remaining in tempers_data:
            ore, logs, bones = tempers_data[tempers_remaining]
        else:
            ore, logs, bones = None, None, None
        # Check if the user has enough resources and gold
        if (mining_data[cost_index] < ore_cost or
            woodcutting_data[cost_index] < wood_cost or
            fishing_data[cost_index] < bone_cost or
            player_gp < gp_cost):
            embed.add_field(name="Tempering", 
                            value=(f"You do not have enough resources to temper this armor.\n"
                                   f"Tempering costs:\n"
                                   f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                                   f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                                   f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                                   f"- GP cost: **{gp_cost}**\n"), 
                            inline=True)
            embed.set_thumbnail(url="https://i.imgur.com/jQeOEP7.jpeg") # Thumbnail for temper smith
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        
        embed = discord.Embed(
            title="Temper",
            description=(f"You are about to temper **{armor_name}**.\n"
                         f"Tempering costs:\n"
                         f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                         f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                         f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                         f"- GP cost: **{gp_cost:,}**\n"
                         f"- Success rate: **{int(success_rate * 100)}%**\n"
                         "Do you want to continue?"),
            color=0xFFFF00
        )
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id 
                    and str(reaction.emoji) in ["✅", "❌"])
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Cancel", value=f"Returning to armor menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        # Deduct the costs from the user's resources
        if armor_level <= 40:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if tempers_remaining == 3 else 0,
                'coal': -ore_cost if tempers_remaining == 2 else 0,
                'gold': -ore_cost if tempers_remaining == 1 else 0,
                'platinum': 0,
                'idea': 0,
            })
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -wood_cost if tempers_remaining == 3 else 0,
                'willow': -wood_cost if tempers_remaining == 2 else 0,
                'mahogany': -wood_cost if tempers_remaining == 1 else 0,
                'magic': 0,
                'idea': 0,
            })
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -bone_cost if tempers_remaining == 3 else 0,
                'regular': -bone_cost if tempers_remaining == 2 else 0,
                'sturdy': -bone_cost if tempers_remaining == 1 else 0,
                'reinforced': 0,
                'titanium': 0,
            })
        elif 40 < armor_level <= 80:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if tempers_remaining == 4 else 0,
                'coal': -ore_cost if tempers_remaining == 3 else 0,
                'gold': -ore_cost if tempers_remaining == 2 else 0,
                'platinum': -ore_cost if tempers_remaining == 1 else 0,
                'idea': 0,
            })
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -wood_cost if tempers_remaining == 4 else 0,
                'willow': -wood_cost if tempers_remaining == 3 else 0,
                'mahogany': -wood_cost if tempers_remaining == 2 else 0,
                'magic': -wood_cost if tempers_remaining == 1 else 0,
                'idea': 0,
            })
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -bone_cost if tempers_remaining == 4 else 0,
                'regular': -bone_cost if tempers_remaining == 3 else 0,
                'sturdy': -bone_cost if tempers_remaining == 2 else 0,
                'reinforced': -bone_cost if tempers_remaining == 1 else 0,
                'titanium': 0,
            })
        else:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if tempers_remaining == 5 else 0,
                'coal': -ore_cost if tempers_remaining == 4 else 0,
                'gold': -ore_cost if tempers_remaining == 3 else 0,
                'platinum': -ore_cost if tempers_remaining == 2 else 0,
                'idea': -ore_cost if tempers_remaining == 1 else 0,
            })
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -wood_cost if tempers_remaining == 5 else 0,
                'willow': -wood_cost if tempers_remaining == 4 else 0,
                'mahogany': -wood_cost if tempers_remaining == 3 else 0,
                'magic': -wood_cost if tempers_remaining == 2 else 0,
                'idea': -wood_cost if tempers_remaining == 1 else 0,
            })
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -bone_cost if tempers_remaining == 5 else 0,
                'regular': -bone_cost if tempers_remaining == 4 else 0,
                'sturdy': -bone_cost if tempers_remaining == 3 else 0,
                'reinforced': -bone_cost if tempers_remaining == 2 else 0,
                'titanium': -bone_cost if tempers_remaining == 1 else 0,
            })
        await self.bot.database.add_gold(user_id, -gp_cost)

        new_tempers_remaining = tempers_remaining - 1
        temper_success = random.random() <= success_rate  

        if temper_success:
            print('temper success')
            # Determine which stat to increase (assuming one of block, evasion, or ward is non-zero)
            if armor_details[4] > 0:  # block
                stat_to_increase = 'block'
                current_value = armor_details[4]
            elif armor_details[5] > 0:  # evasion
                stat_to_increase = 'evasion'
                current_value = armor_details[5]
            else:  # ward
                stat_to_increase = 'ward'
                current_value = armor_details[6]
                
            increase_amount = max(1, random.randint(int(armor_level // 7), int(armor_level // 5)))
            await self.bot.database.increase_armor_stat(armor_id, stat_to_increase, increase_amount)
            embed.add_field(name="Tempering success", 
                           value=(f"🎊 Congratulations! 🎊 " 
                                  f"**{armor_name}**'s {stat_to_increase.capitalize()} increased by **{increase_amount}**."),
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(7)
        else:
            print('tempering failed')
            embed.add_field(name="Tempering", 
                           value=(f"Tempering failed! "
                                  f"Better luck next time. 🥺 \n"
                                  f"Returning to armor menu..."),
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
        
        await self.bot.database.update_armor_temper_count(armor_id, new_tempers_remaining)

    async def imbue_armor(self, 
                          interaction: Interaction, 
                          selected_armor: tuple, 
                          embed, 
                          message) -> None:
        """Imbue an armor piece with a rune of imbuing for a chance to gain a passive."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        armor_id = selected_armor[0]
        armor_name = selected_armor[2]
        armor_passive = selected_armor[7]
        imbues_remaining = selected_armor[10]
        if armor_passive != "none":
            embed.add_field(name="Imbuing", 
                           value=f"This armor has been imbued with **{armor_passive}**.", 
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        
        if imbues_remaining < 1:
            embed.add_field(name="Imbuing", 
                           value=f"This armor can no longer be imbued.", 
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        imbue_runes = existing_user[27]
        if imbue_runes <= 0:
            embed.add_field(name="Imbuing", 
                           value=f"You do not have any Runes of Imbuing. Returning to armor menu...", 
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        embed = discord.Embed(
            title="Imbue Armor",
            description=(f"Use a **Rune of Imbuing** to attempt to imbue **{armor_name}** with a passive?\n"
                         f"You have **{imbue_runes}** Rune(s) of Imbuing.\n"
                         f"Success rate: **50%**\n"
                         "Do you want to continue?"),
            color=0xFFCC00
        )
        embed.set_thumbnail(url="https://i.imgur.com/MHgtUW8.png") # Thumbnail for imbue rune
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id 
                    and str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Cancel", value=f"Returning to armor menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        # Deduct one rune of imbuing
        await self.bot.database.update_imbuing_runes(user_id, -1)
        await self.bot.database.update_armor_imbue_count(armor_id, 0)
        # 50% success rate
        imbue_success = random.random() <= 0.5
        if imbue_success:
            passives = [
                "Invulnerable",
                "Mystical Might",
                "Omnipotent",
                "Treasure Hunter",
                "Unlimited Wealth",
                "Everlasting Blessing"
            ]
            new_passive = random.choice(passives)
            await self.bot.database.update_armor_passive(armor_id, new_passive)
            embed.add_field(name="Imbuing success", 
                           value=(f"🎊 Congratulations! 🎊 "
                                  f"**{armor_name}** has been imbued with **{new_passive}**."),
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(7)
        else:
            embed.add_field(name="Imbuing", 
                           value=(f"Imbuing failed! "
                                  f"Better luck next time. 🥺 \n"
                                  f"Returning to armor menu..."),
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)

    async def discard_armor(self, 
                            interaction: Interaction, 
                            selected_armor: tuple, 
                            message, embed) -> None:
        """Discard an armor piece."""
        armor_id = selected_armor[0]
        armor_name = selected_armor[2]
        embed = discord.Embed(
            title="Confirm Discard",
            description=f"Discard **{armor_name}**?\n**This action cannot be undone.**",
            color=0xFF0000,
        )
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")  # Confirm discard
        await message.add_reaction("❌")  # Cancel discard

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)
            if str(reaction.emoji) == "❌":
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        await self.bot.database.discard_armor(armor_id)

    def get_armor_passive_effect(self, passive: str) -> str:
        """Return the description of an armor passive effect."""
        passive_messages = {
            "Invulnerable": "20% chance to take no damage the entire fight.",
            "Mystical Might": "20% chance to deal 10x damage after all calculations.",
            "Omnipotent": "20% chance to set the monsters attack and defense to 0.",
            "Treasure Hunter": "5% additional chance to turn the monster into a loot encounter.",
            "Unlimited Wealth": "20% chance to 5x player rarity stat.",
            "Everlasting Blessing": "10% chance on victory to propagate your ideology."
        }
        return passive_messages.get(passive, "No effect.")


# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(Armor(bot))
