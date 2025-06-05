import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import View, Button
import asyncio
import random

class Armor(commands.Cog, name="armor"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="armor", description="View your character's armors and modify them.")
    async def view_armor(self, interaction: Interaction) -> None:
        """Fetch and display the character's armors with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # if not await self.bot.is_maintenance(interaction, user_id):
        #     return

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
            title="🛡️",
            description=f"{player_name}'s Armors:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/NTVHFL8.png")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")

        # Pagination setup
        items_per_page = 7
        total_pages = (len(armors) + items_per_page - 1) // items_per_page
        current_page = 0
        original_user = interaction.user

        while True:
            armors = await self.bot.database.fetch_user_armors(user_id)
            total_pages = (len(armors) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1)
            embed.description = f"{player_name}'s Armor (Page {current_page + 1}/{total_pages}):"
            if not armors:
                await interaction.followup.send("You peer into your armor pouch, it is empty.")
                break

            armors.sort(key=lambda armor: armor[3], reverse=True)
            start_idx = current_page * items_per_page
            armors_to_display = armors[start_idx:start_idx + items_per_page]
            embed.clear_fields()
            armors_display_string = ""

            for index, armor in enumerate(armors_to_display):
                armor_name = armor[2]
                armor_level = armor[3]
                armor_passive = armor[7]

                equipped_armor = await self.bot.database.get_equipped_armor(user_id)
                is_equipped = equipped_armor and (equipped_armor[0] == armor[0])
                info_txt = ""
                if armor_passive != "none":
                    info_txt += f" - {armor_passive}"
                armors_display_string += (
                    f"{index + 1}: "
                    f"{'[E] ' if is_equipped else ''}"
                    f"{armor_name} (i{armor_level}{info_txt})\n"
                )
            
            embed.add_field(
                name="Armors:",
                value=armors_display_string.strip(),
                inline=False
            )
                
            embed.add_field(
                name="Instructions",
                value=("Select an armor to interact with.\n"
                       "Use navigation buttons to change pages or close the interface."),
                inline=False
            )

            view = View(timeout=60.0)
            for i in range(len(armors_to_display)):
                view.add_item(Button(label=f"{i+1}", style=ButtonStyle.primary, custom_id=f"item_{i}"))
            if current_page > 0:
                view.add_item(Button(label="Previous", style=ButtonStyle.secondary, custom_id="previous"))
            if current_page < total_pages - 1:
                view.add_item(Button(label="Next", style=ButtonStyle.secondary, custom_id="next"))
            view.add_item(Button(label="Close", style=ButtonStyle.danger, custom_id="close"))

            await message.edit(embed=embed, view=view)

            def check(button_interaction: Interaction):
                return (button_interaction.user == original_user and 
                        button_interaction.message is not None and 
                        button_interaction.message.id == message.id)

            try:
                button_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                
                if button_interaction.data['custom_id'] == "previous" and current_page > 0:
                    current_page -= 1
                    await button_interaction.response.defer()
                    continue
                elif button_interaction.data['custom_id'] == "next" and current_page < total_pages - 1:
                    current_page += 1
                    await button_interaction.response.defer()
                    continue
                elif button_interaction.data['custom_id'] == "close":
                    await message.delete()
                    self.bot.state_manager.clear_active(user_id)
                    break
                
                if button_interaction.data['custom_id'].startswith("item_"):
                    selected_index = int(button_interaction.data['custom_id'].split("_")[1])
                    await button_interaction.response.defer()
                    while True:
                        selected_armor = armors_to_display[selected_index]
                        selected_armor = await self.bot.database.fetch_armor_by_id(selected_armor[0])
                        if not selected_armor:
                            break
                        armor_name = selected_armor[2]
                        armor_level = selected_armor[3]
                        armor_block = selected_armor[4]
                        armor_evasion = selected_armor[5]
                        armor_ward = selected_armor[6]
                        armor_passive = selected_armor[7]
                        armor_pdr = selected_armor[11]
                        armor_fdr = selected_armor[12]
                        embed.description = f"**{armor_name}** (i{armor_level}):"
                        
                        equipped_item_tuple = await self.bot.database.get_equipped_armor(user_id) # Re-fetch for accurate equipped status

                        is_equipped = equipped_item_tuple and (equipped_item_tuple[0] == selected_armor[0])
                        if (is_equipped):
                            embed.description += "\nEquipped"
                        embed.clear_fields()
                        if armor_block > 0:
                            embed.add_field(name="Block", value=armor_block)
                            embed.add_field(name=f"Effect",
                                        value=f"{armor_block}% chance to reduce initial monster hit to 0",
                                        inline=False)
                        if armor_evasion > 0:
                            embed.add_field(name="Dodge",value=f"{armor_evasion}")
                            embed.add_field(name="Effect", 
                                value=f"{armor_evasion}% chance to completely dodge a monster's attack",
                                inline=False)
                        if armor_ward > 0:
                            embed.add_field(name="Ward", value=f"{armor_ward}%")
                            embed.add_field(name=f"Effect", value=f"{int(armor_ward)}% additional temporary max hp at start of encounter", inline=False)
                        if armor_pdr > 0:
                            embed.add_field(name="Percentage Damage Reduction", value=f"{armor_pdr}%")
                            embed.add_field(name=f"Effect", value=f"Initial monster hit reduced by {int(armor_pdr)}%", inline=False)
                        if armor_fdr > 0:
                            embed.add_field(name="Flat Damage Reduction", value=f"{armor_fdr}")
                            embed.add_field(name=f"Effect", value=f"Initial monster hit reduced by {int(armor_fdr)}", inline=False)
                        
                        
                        if armor_passive != "none":
                            effect_description = self.get_armor_passive_effect(armor_passive)
                            embed.add_field(name="Passive", value=armor_passive)
                            embed.add_field(name=f"Effect", value=effect_description, inline=False)
                        armor_guide = (
                            "Select an action:\n"
                            "- Equip: Equip the armor\n"
                            "- Temper: Temper the armor\n"
                            "- Imbue: Apply a passive\n"
                            "- Send: Send armor\n"
                            "- Discard: Discard\n"
                            "- Back: Return to list"
                        )
                        embed.add_field(name="Armor Guide", value=armor_guide, inline=False)

                        action_view = View(timeout=60.0)
                        action_view.add_item(Button(label="Unequip" if is_equipped else "Equip", style=ButtonStyle.primary, custom_id="unequip" if is_equipped else "equip"))
                        if selected_armor[9] > 0:
                            action_view.add_item(Button(label="Temper", style=ButtonStyle.primary, custom_id="temper"))
                        if selected_armor[10] > 0:
                            action_view.add_item(Button(label="Imbue", style=ButtonStyle.primary, custom_id="imbue"))
                        action_view.add_item(Button(label="Send", style=ButtonStyle.primary, custom_id="send"))
                        action_view.add_item(Button(label="Discard", style=ButtonStyle.danger, custom_id="discard"))
                        action_view.add_item(Button(label="Back", style=ButtonStyle.secondary, custom_id="back"))

                        await message.edit(embed=embed, view=action_view)

                        try:
                            action_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                            await action_interaction.response.defer()

                            if action_interaction.data['custom_id'] in ["equip", "unequip"]:
                                if action_interaction.data['custom_id'] == "equip":
                                    await self.bot.database.equip_armor(user_id, selected_armor[0])
                                else:  # unequip
                                    await self.bot.database.unequip_armor(user_id)
                                continue # Re-fetch and re-display item details
                            elif action_interaction.data['custom_id'] == "temper":
                                await self.temper_armor(action_interaction, selected_armor, embed, message)
                                continue
                            elif action_interaction.data['custom_id'] == "imbue":
                                await self.imbue_armor(action_interaction, selected_armor, embed, message)
                                continue
                            elif action_interaction.data['custom_id'] == "send":
                                if is_equipped:
                                    # Create a temporary embed for the error to avoid clearing fields
                                    error_embed = embed.copy()
                                    error_embed.add_field(name="Error", value="You should probably unequip the armor before sending it. Returning...", inline=False)
                                    await message.edit(embed=error_embed, view=None) # Remove buttons during error
                                    await asyncio.sleep(3)
                                    continue

                                temp_send_embed = embed.copy()
                                temp_send_embed.clear_fields()
                                temp_send_embed.add_field(
                                    name="Send Armor",
                                    value="Please mention a user (@username) to send the armor to.",
                                    inline=False
                                )
                                await message.edit(embed=temp_send_embed, view=None)
                                
                                def message_check(m: Message):
                                    return (m.author == interaction.user and 
                                            m.channel == interaction.channel and 
                                            m.mentions)
                                
                                try:
                                    user_message = await self.bot.wait_for('message', timeout=60.0, check=message_check)
                                    await user_message.delete()
                                    receiver = user_message.mentions[0]
                                    send_item_flag = True
                                    receiver_user = await self.bot.database.fetch_user(receiver.id, server_id)

                                    error_messages_send = []
                                    if not receiver_user:
                                        send_item_flag = False
                                        error_messages_send.append("This person isn't a valid adventurer.")
                                    if receiver.id == interaction.user.id:
                                        send_item_flag = False
                                        error_messages_send.append("You cannot send items to yourself.")
                                    
                                    if receiver_user: # Only check level and inventory if receiver is valid
                                        current_level_receiver = receiver_user[4]
                                        if (armor_level - current_level_receiver) > 15:
                                            send_item_flag = False
                                            error_messages_send.append("Item iLvl diff too great. (< 15)")
                                        
                                        receiver_items_count = await self.bot.database.count_user_armors(str(receiver.id))
                                        if receiver_items_count >= 58: # Assuming 58 is max capacity
                                            send_item_flag = False
                                            error_messages_send.append(f"{receiver.mention}'s inventory is full.")

                                    if not send_item_flag:
                                        err_embed = embed.copy()
                                        err_embed.add_field(name="Error Sending", value="\n".join(error_messages_send) + "\nReturning...", inline=False)
                                        await message.edit(embed=err_embed, view=None)
                                        await asyncio.sleep(4)
                                        continue # Back to item details view

                                    # If all checks pass, proceed to confirmation
                                    confirm_embed = discord.Embed(
                                        title="Confirm Send Armor",
                                        description=f"Send **{armor_name}** to {receiver.mention}?",
                                        color=0x00FF00
                                    )
                                    confirm_view = View(timeout=60.0)
                                    confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_send"))
                                    confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_send"))
                                    
                                    await message.edit(embed=confirm_embed, view=confirm_view)
                                    
                                    try:
                                        confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                                        await confirm_interaction.response.defer()
                                        
                                        if confirm_interaction.data['custom_id'] == "confirm_send":
                                            await self.bot.database.send_armor(str(receiver.id), selected_armor[0])
                                            confirm_embed.clear_fields()
                                            confirm_embed.add_field(name="Armor Sent", value=f"Sent **{armor_name}** to {receiver.mention}! 🎉", inline=False)
                                            await message.edit(embed=confirm_embed, view=None)
                                            await asyncio.sleep(3)
                                            break
                                        else:
                                            continue 
                                    except asyncio.TimeoutError:
                                        await message.edit(content="Send confirmation timed out.", embed=None, view=None)
                                        await asyncio.sleep(3)
                                        continue
                                except asyncio.TimeoutError:
                                    await message.edit(content="Send armor timed out while waiting for user mention.", embed=None, view=None)
                                    await asyncio.sleep(3)
                                    continue
                            elif action_interaction.data['custom_id'] == "discard":
                                await self.discard_armor(action_interaction, selected_armor, message, embed)
                                continue
                            elif action_interaction.data['custom_id'] == "back":
                                break

                        except asyncio.TimeoutError:
                            await message.delete()
                            self.bot.state_manager.clear_active(user_id)
                            return

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(user_id)
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
        while True:
            armor_details = await self.bot.database.fetch_armor_by_id(armor_id)
            
            if not armor_details:
                await interaction.followup.send("Armor not found.")
                return

            tempers_remaining = armor_details[9]
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

            if tempers_remaining == 0:
                embed.add_field(name="Tempering", value=f"This armor cannot be tempered anymore.", inline=True)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

            existing_user = await self.bot.database.fetch_user(user_id, server_id)
            player_gp = existing_user[6]
            mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
            woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
            fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

            ore_cost, wood_cost, bone_cost, gp_cost = costs[tempers_remaining]
            ore, logs, bones = tempers_data.get(tempers_remaining, (None, None, None))

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
                embed.set_thumbnail(url="https://i.imgur.com/jQeOEP7.jpeg")
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
            confirm_view = View(timeout=60.0)
            confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_temper"))
            confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_temper"))
            
            await message.edit(embed=embed, view=confirm_view)

            def check(button_interaction: Interaction):
                return (button_interaction.user == interaction.user and 
                        button_interaction.message is not None and 
                        button_interaction.message.id == message.id)

            try:
                confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                await confirm_interaction.response.defer()
                
                if confirm_interaction.data['custom_id'] == "cancel_temper":
                    return

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)
                return

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

                if armor_details[11] > 0:
                    stat_to_increase = 'pdr'
                    increase_amount = max(1, random.randint(int(armor_level // 33), int(armor_level // 16)))
                    success_str =  f"Percentage damage reduction increased by **{increase_amount}**%"
                elif armor_details[12] > 0:
                    stat_to_increase = 'fdr'
                    increase_amount = max(1, random.randint(int(armor_level // 100), int(armor_level // 25)))
                    success_str =  f"Flat damage reduction increased by **{increase_amount}**"
                await self.bot.database.increase_armor_stat(armor_id, stat_to_increase, increase_amount)
                embed.add_field(name="Tempering success", 
                            value=(f"🎊 Congratulations! 🎊 " 
                                    f"**{armor_name}**'s {success_str}."), 
                            inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
            else:
                embed.add_field(name="Tempering", 
                            value=(f"Tempering failed! "
                                    f"Better luck next time. 🥺 \n"
                                    f"Returning to armor menu..."), 
                            inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
            
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
        embed.set_thumbnail(url="https://i.imgur.com/MHgtUW8.png")
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_imbue"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_imbue"))
        
        await message.edit(embed=embed, view=confirm_view)

        def check(button_interaction: Interaction):
            return (button_interaction.user == interaction.user and 
                    button_interaction.message is not None and 
                    button_interaction.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
            await confirm_interaction.response.defer()
            
            if confirm_interaction.data['custom_id'] == "cancel_imbue":
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)
            return

        await self.bot.database.update_imbuing_runes(user_id, -1)
        await self.bot.database.update_armor_imbue_count(armor_id, 0)
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
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.danger, custom_id="confirm_discard"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_discard"))
        
        await message.edit(embed=embed, view=confirm_view)

        def check(button_interaction: Interaction):
            return (button_interaction.user == interaction.user and 
                    button_interaction.message is not None and 
                    button_interaction.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
            await confirm_interaction.response.defer()
            
            if confirm_interaction.data['custom_id'] == "cancel_discard":
                return

            await self.bot.database.discard_armor(armor_id)

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)

    def get_armor_passive_effect(self, passive: str) -> str:
        """Return the description of an armor passive effect."""
        passive_messages = {
            "Invulnerable": "20% chance to take no damage the entire fight.",
            "Mystical Might": "20% chance to deal 10x damage after all calculations.",
            "Omnipotent": "50% chance to double your stats at start of combat (Atk, Def, HP).",
            "Treasure Hunter": "5% additional chance to turn the monster into a loot encounter.",
            "Unlimited Wealth": "20% chance to 5x (2x on bosses) player rarity stat.",
            "Everlasting Blessing": "10% chance on victory to propagate your ideology."
        }
        return passive_messages.get(passive, "No effect.")

async def setup(bot) -> None:
    await bot.add_cog(Armor(bot))