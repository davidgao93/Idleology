import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import View, Button
from core.util import clear_msg
import asyncio
import random

class Weapons(commands.Cog, name="weapons"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="weapon", description="View your character's weapons and modify them.")
    async def view_weapons(self, interaction: Interaction) -> None:
        """Fetch and display the character's weapons with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Check if the user has any active operations
        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        items = await self.bot.database.fetch_user_weapons(user_id)
        
        if not items:
            await interaction.response.send_message("You peer into your weapon's pouch, it is empty.")
            return
        
        player_name = existing_user[3]
        embed = discord.Embed(
            title="⚔️",
            description=f"{player_name}'s Weapons:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/AnlbnbO.jpeg")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")

        # Pagination setup
        items_per_page = 7
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        current_page = 0

        # Store the original user for comparison
        original_user = interaction.user

        while True:
            items = await self.bot.database.fetch_user_weapons(user_id)
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1)
            embed.description = f"{player_name}'s Weapons (Page {current_page + 1}/{total_pages}):"
            if not items:
                await interaction.followup.send("You peer into your weapon's pouch, it is empty.")
                break

            equipped_item = await self.bot.database.get_equipped_weapon(user_id)
            equipped_items = [item for item in items if equipped_item and (equipped_item[0] == item[0])]
            other_items = [item for item in items if not equipped_item or (equipped_item[0] != item[0])]
            other_items.sort(key=lambda item: item[3], reverse=True)
            sorted_items = equipped_items + other_items

            items.sort(key=lambda item: item[3], reverse=True)
            start_idx = current_page * items_per_page
            items_to_display = sorted_items[start_idx:start_idx + items_per_page]
            embed.clear_fields()
            items_display_string = ""

            for index, item in enumerate(items_to_display):
                item_name = item[2]
                item_level = item[3]
                
                is_equipped = equipped_item and (equipped_item[0] == item[0])
                
                items_display_string += (
                    f"{index + 1}: "
                    f"{'[E] ' if is_equipped else ''}"
                    f"{item_name} (i{item_level})\n"
                )
            
            embed.add_field(
                name="Weapons:",
                value=items_display_string.strip(),
                inline=False
            )
                
            embed.add_field(
                name="Instructions",
                value=("Select an item to interact with.\n"
                       "Use navigation buttons to change pages or close the interface."),
                inline=False
            )

            # Create view with buttons
            view = View(timeout=60.0)
            for i in range(len(items_to_display)):
                view.add_item(Button(label=f"{i+1}", style=ButtonStyle.primary, custom_id=f"item_{i}"))
            if current_page > 0:
                view.add_item(Button(label="Previous", style=ButtonStyle.secondary, custom_id="previous"))
            if current_page < total_pages - 1:
                view.add_item(Button(label="Next", style=ButtonStyle.secondary, custom_id="next"))
            view.add_item(Button(label="Close", style=ButtonStyle.danger, custom_id="close"))

            if message:
                await message.edit(embed=embed, view=view)

            def check(button_interaction: Interaction):
                # Check if message is still valid and user matches
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
                        selected_item = items_to_display[selected_index]
                        selected_item = await self.bot.database.fetch_weapon_by_id(selected_item[0])
                        equipped_item = await self.bot.database.get_equipped_weapon(user_id)
                        if not selected_item:
                            break
                        item_name = selected_item[2]
                        item_level = selected_item[3]
                        item_attack = selected_item[4] if len(selected_item) > 4 else 0
                        item_defence = selected_item[5] if len(selected_item) > 5 else 0
                        item_rarity = selected_item[6] if len(selected_item) > 6 else 0
                        item_passive = selected_item[7]
                        item_refinement = selected_item[11]
                        is_equipped = equipped_item and (equipped_item[0] == selected_item[0])
                        embed.description = f"**{item_name}** (i{item_level}) (R{item_refinement}):"
                        embed.clear_fields()
                        if (is_equipped):
                            embed.description += "\nEquipped"
                        embed.add_field(name="Attack", value=item_attack, inline=True)
                        embed.add_field(name="Defence", value=item_defence, inline=True)
                        embed.add_field(name="Rarity", value=item_rarity, inline=True)
                        embed.add_field(name="Passive", value=item_passive.capitalize(), inline=False)
                        if item_passive != "none":
                            effect_description = self.get_passive_effect(item_passive)
                            embed.add_field(name="Effect", value=effect_description, inline=False)
                        item_guide = (
                            "Select an action:\n"
                            f"- {'Unequip' if is_equipped else 'Equip'}: {'Unequip' if is_equipped else 'Equip'} the item\n"
                            "- Forge: Attempt to forge\n"
                            "- Refine: Attempt to refine\n"
                            "- Discard: Discard item\n"
                            "- Back: Return to list"
                        )
                        embed.add_field(name="Item Guide", value=item_guide, inline=False)
                        
                        action_view = View(timeout=60.0)
                        action_view.add_item(Button(label="Unequip" if is_equipped else "Equip", style=ButtonStyle.primary, custom_id="unequip" if is_equipped else "equip"))
                        action_view.add_item(Button(label="Forge", style=ButtonStyle.primary, custom_id="forge"))
                        action_view.add_item(Button(label="Refine", style=ButtonStyle.primary, custom_id="refine"))
                        action_view.add_item(Button(label="Discard", style=ButtonStyle.danger, custom_id="discard"))
                        action_view.add_item(Button(label="Send", style=ButtonStyle.primary, custom_id="send"))
                        action_view.add_item(Button(label="Back", style=ButtonStyle.secondary, custom_id="back"))
                        
                        if message:
                            await message.edit(embed=embed, view=action_view)
                        
                        try:
                            action_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                            await action_interaction.response.defer()
                            if action_interaction.data['custom_id'] in ["equip", "unequip"]:
                                if action_interaction.data['custom_id'] == "equip":
                                    await self.bot.database.equip_weapon(user_id, selected_item[0])
                                    print('Equip player item and refresh view')
                                else:  # unequip
                                    print('Unequip player item and refresh view')
                                    await self.bot.database.unequip_weapon(user_id)
                                continue
                            elif action_interaction.data['custom_id'] == "forge":
                                await self.forge_item(action_interaction, selected_item, embed, message)
                                continue
                            elif action_interaction.data['custom_id'] == "refine":
                                await self.refine_item(action_interaction, selected_item, embed, message)
                                continue
                            elif action_interaction.data['custom_id'] == "send":
                                if is_equipped:
                                    embed.add_field(name="Error", value="You should probably unequip the weapon before sending it. Returning...", inline=False)
                                    await message.edit(embed=embed, view=action_view)
                                    await asyncio.sleep(3)
                                    break
                                embed.clear_fields()
                                embed.add_field(
                                    name="Send Weapon",
                                    value="Please mention a user (@username) to send the weapon to.",
                                    inline=False
                                )
                                await message.edit(embed=embed, view=None)
                                
                                def message_check(m: Message):
                                    return (m.author == interaction.user and 
                                            m.channel == interaction.channel and 
                                            m.mentions)
                                
                                try:
                                    user_message = await self.bot.wait_for('message', timeout=60.0, check=message_check)
                                    await user_message.delete()
                                    receiver = user_message.mentions[0]
                                    send_item = True
                                    receiver_user = await self.bot.database.fetch_user(receiver.id, server_id)
                                    if not receiver_user:
                                        send_item = False
                                        embed.add_field(name="Error", value="This person isn't a valid adventurer. Returning...", inline=False)
                                        await message.edit(embed=embed, view=None)
                                        await asyncio.sleep(3)
                                        continue

                                    # Run send_weapon logic
                                    if receiver.id == interaction.user.id:
                                        send_item = False
                                        embed.add_field(name="Error", value="You cannot send items to yourself. Returning...", inline=False)
                                        await message.edit(embed=embed, view=None)
                                        await asyncio.sleep(3)
                                        continue
                                    
                                    current_level = receiver_user[4]
                                    
                                    if (item_level - current_level) > 15:
                                        send_item = False
                                        embed.add_field(name="Error", value="Item iLvl diff too great. (< 15) Returning...", inline=False)
                                        await message.edit(embed=embed, view=None)
                                        await asyncio.sleep(3)
                                        continue
                                    
                                    receiver_items = await self.bot.database.fetch_user_weapons(str(receiver.id))
                                    if len(receiver_items) >= 58:
                                        send_item = False
                                        embed.add_field(name="Error", value=f"{receiver.mention}'s inventory is full. Returning...", inline=False)
                                        await message.edit(embed=embed, view=None)
                                        await asyncio.sleep(3)
                                        continue
                                    
                                    if send_item:
                                        confirm_embed = discord.Embed(
                                            title="Confirm Send Weapon",
                                            description=f"Send **{item_name}** to {receiver.mention}?",
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
                                                await self.bot.database.send_weapon(receiver.id, selected_item[0])
                                                confirm_embed.add_field(name="Weapon Sent", value=f"Sent **{item_name}** to {receiver.mention}! 🎉", inline=False)
                                                await message.edit(embed=confirm_embed, view=None)
                                                await asyncio.sleep(3)
                                                break  # Return to weapon list
                                            else:
                                                self.bot.state_manager.clear_active(user_id)
                                                continue
                                        
                                        except asyncio.TimeoutError:
                                            await message.delete()
                                            self.bot.state_manager.clear_active(user_id)
                                            break
                                    
                                except asyncio.TimeoutError:
                                    if message:
                                        await message.delete()
                                    self.bot.state_manager.clear_active(user_id)
                                    break
                            elif action_interaction.data['custom_id'] == "discard":
                                await self.discard(action_interaction, selected_item, message, embed)
                                continue
                            elif action_interaction.data['custom_id'] == "back":
                                break

                        except asyncio.TimeoutError:
                            if message:
                                await message.delete()
                            self.bot.state_manager.clear_active(user_id)
                            break

            except asyncio.TimeoutError:
                if message:
                    await message.delete()
                self.bot.state_manager.clear_active(user_id)
                break
        self.bot.state_manager.clear_active(user_id)

    async def discard(self, 
                     interaction: Interaction, 
                     selected_item: tuple,
                     message, embed) -> None:
        """Discard an item."""
        item_id = selected_item[0]
        item_name = selected_item[2]

        embed = discord.Embed(
            title="Confirm Discard",
            description=f"Are you sure you want to discard **{item_name}**?\n"
                        "**This action cannot be undone.**",
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

            await self.bot.database.discard_weapon(item_id)

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)

    async def forge_item(self, 
                        interaction: Interaction, 
                        selected_item: tuple, 
                        embed, 
                        message) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        item_id = selected_item[0]
        item_name = selected_item[2] 
        item_level = selected_item[3]
        forges_remaining = selected_item[9]

        if forges_remaining < 1:
            embed.add_field(name="Forging", value=f"This item cannot be forged anymore.\n"
                    "Returning...", inline=True)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        base_success_rate = 0.8
        if item_level <= 40:
            costs = {
                3: (10, 10, 10, 100),
                2: (10, 10, 10, 400),
                1: (10, 10, 10, 1000),
            }
            cost_index = 6 - forges_remaining
            success_rate = base_success_rate - (3 - forges_remaining) * 0.05
            forges_data = {
                3: ('iron', 'oak', 'desiccated'),
                2: ('coal', 'willow', 'regular'),
                1: ('gold', 'mahogany', 'sturdy'),
            }
        elif 40 < item_level <= 80:    
            costs = {
                4: (25, 25, 25, 250),
                3: (25, 25, 25, 1000),
                2: (25, 25, 25, 2500),
                1: (25, 25, 25, 5000),
            }       
            forges_data = {
                4: ('iron', 'oak', 'desiccated'),
                3: ('coal', 'willow', 'regular'),
                2: ('gold', 'mahogany', 'sturdy'),
                1: ('platinum', 'magic', 'reinforced'),
            }
            cost_index = 7 - forges_remaining
            success_rate = base_success_rate - (4 - forges_remaining) * 0.05 
        else:
            costs = {
                5: (50, 50, 50, 500),
                4: (50, 50, 50, 2000),
                3: (50, 50, 50, 5000),
                2: (50, 50, 50, 10000),
                1: (50, 50, 50, 20000),
            }
            forges_data = {
                5: ('iron', 'oak', 'desiccated'),
                4: ('coal', 'willow', 'regular'),
                3: ('gold', 'mahogany', 'sturdy'),
                2: ('platinum', 'magic', 'reinforced'),
                1: ('idea', 'idea', 'titanium'),
            }
            cost_index = 8 - forges_remaining
            success_rate = base_success_rate - (5 - forges_remaining) * 0.05

        success_rate = max(0, min(success_rate, 1))
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]
        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

        ore_cost, wood_cost, bone_cost, gp_cost = costs[forges_remaining]
        ore, logs, bones = forges_data.get(forges_remaining, (None, None, None))

        if (mining_data[cost_index] < ore_cost or
            woodcutting_data[cost_index] < wood_cost or
            fishing_data[cost_index] < bone_cost or
            player_gp < gp_cost):
            embed.add_field(name="Forging", 
                            value=(f"You do not have enough resources to forge this item.\n"
                                f"Forging costs:\n"
                                f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                                f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                                f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                                f"- GP cost: **{gp_cost}**\n"), 
                            inline=True)
            embed.set_thumbnail(url="https://i.imgur.com/jgq4aGA.jpeg")
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        
        embed = discord.Embed(
            title="Forge",
            description=(f"Attempt to forge **{item_name}**?\n"
                        f"Forging costs:\n"
                        f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                        f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                        f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                        f"- GP cost: **{gp_cost:,}**\n"
                        f"- Success rate: **{int(success_rate * 100)}%**\n"),
            color=0xFFFF00
        )
        embed.set_thumbnail(url="https://i.imgur.com/jgq4aGA.jpeg")
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_forge"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_forge"))
        
        await message.edit(embed=embed, view=confirm_view)

        def check(button_interaction: Interaction):
            return (button_interaction.user == interaction.user and 
                    button_interaction.message is not None and 
                    button_interaction.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
            await confirm_interaction.response.defer()
            
            if confirm_interaction.data['custom_id'] == "cancel_forge":
                return

            if item_level <= 40:
                await self.bot.database.update_mining_resources(user_id, server_id, {
                    'iron': -ore_cost if forges_remaining == 3 else 0,
                    'coal': -ore_cost if forges_remaining == 2 else 0,
                    'gold': -ore_cost if forges_remaining == 1 else 0,
                    'platinum': 0,
                    'idea': 0,
                })
                await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                    'oak': -ore_cost if forges_remaining == 3 else 0,
                    'willow': -ore_cost if forges_remaining == 2 else 0,
                    'mahogany': -ore_cost if forges_remaining == 1 else 0,
                    'magic': 0,
                    'idea': 0,
                })
                await self.bot.database.update_fishing_resources(user_id, server_id, {
                    'desiccated': -ore_cost if forges_remaining == 3 else 0,
                    'regular': -ore_cost if forges_remaining == 2 else 0,
                    'sturdy': -ore_cost if forges_remaining == 1 else 0,
                    'reinforced': 0,
                    'titanium': 0,
                })
            elif 40 < item_level <= 80:
                await self.bot.database.update_mining_resources(user_id, server_id, {
                    'iron': -ore_cost if forges_remaining == 4 else 0,
                    'coal': -ore_cost if forges_remaining == 3 else 0,
                    'gold': -ore_cost if forges_remaining == 2 else 0,
                    'platinum': -ore_cost if forges_remaining == 1 else 0,
                    'idea': 0,
                })
                await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                    'oak': -ore_cost if forges_remaining == 4 else 0,
                    'willow': -ore_cost if forges_remaining == 3 else 0,
                    'mahogany': -ore_cost if forges_remaining == 2 else 0,
                    'magic': -ore_cost if forges_remaining == 1 else 0,
                    'idea': 0,
                })
                await self.bot.database.update_fishing_resources(user_id, server_id, {
                    'desiccated': -ore_cost if forges_remaining == 4 else 0,
                    'regular': -ore_cost if forges_remaining == 3 else 0,
                    'sturdy': -ore_cost if forges_remaining == 2 else 0,
                    'reinforced': -ore_cost if forges_remaining == 1 else 0,
                    'titanium': 0,
                })
            else:
                await self.bot.database.update_mining_resources(user_id, server_id, {
                    'iron': -ore_cost if forges_remaining == 5 else 0,
                    'coal': -ore_cost if forges_remaining == 4 else 0,
                    'gold': -ore_cost if forges_remaining == 3 else 0,
                    'platinum': -ore_cost if forges_remaining == 2 else 0,
                    'idea': -ore_cost if forges_remaining == 1 else 0,
                })
                await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                    'oak': -ore_cost if forges_remaining == 5 else 0,
                    'willow': -ore_cost if forges_remaining == 4 else 0,
                    'mahogany': -ore_cost if forges_remaining == 3 else 0,
                    'magic': -ore_cost if forges_remaining == 2 else 0,
                    'idea': -ore_cost if forges_remaining == 1 else 0,
                })
                await self.bot.database.update_fishing_resources(user_id, server_id, {
                    'desiccated': -ore_cost if forges_remaining == 5 else 0,
                    'regular': -ore_cost if forges_remaining == 4 else 0,
                    'sturdy': -ore_cost if forges_remaining == 3 else 0,
                    'reinforced': -ore_cost if forges_remaining == 2 else 0,
                    'titanium': -ore_cost if forges_remaining == 1 else 0,
                })
            await self.bot.database.add_gold(user_id, -gp_cost)

            new_forges_remaining = forges_remaining - 1
            forge_success = random.random() <= success_rate  

            if forge_success:
                current_passive = selected_item[7]
                if current_passive == "none":
                    passives = [
                        "burning",
                        "poisonous",
                        "polished",
                        "sparking",
                        "sturdy",
                        "piercing",
                        "strengthened",
                        "accurate",
                        "echo"
                    ]
                    new_passive = random.choice(passives)
                    await self.bot.database.update_weapon_passive(item_id, new_passive)
                    embed.add_field(name="Forging success", 
                                  value=(f"🎊 Congratulations! 🎊 " 
                                         f"**{item_name}** has gained the " 
                                         f"**{new_passive.capitalize()}** passive.\nReturning..."), 
                                  inline=False)
                    await message.edit(embed=embed)
                    await asyncio.sleep(3)
                else:
                    new_passive = await self.upgrade_passive(current_passive)
                    await self.bot.database.update_weapon_passive(item_id, new_passive)
                    embed.add_field(name="Forging success", 
                                  value=(f"🎊 Congratulations! 🎊 "
                                         f"**{item_name}**'s passive upgrades from **{current_passive.capitalize()}**"
                                         f" to **{new_passive.capitalize()}**.\nReturning..."),
                                  inline=False)
                    await message.edit(embed=embed)
                    await asyncio.sleep(3)
            else:
                embed.add_field(name="Failed", 
                              value=(f"Your hand slips and you fail to strike the weapon! 💔\n"
                                     f"Better luck next time.\n"
                                     f"Returning to item menu..."),
                              inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
        
            await self.bot.database.update_weapon_forge_count(item_id, new_forges_remaining)

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)

    async def upgrade_passive(self, current_passive: str) -> str:
        """Upgrade the current passive to a stronger version."""
        passive_upgrade_table = {
            "burning": "flaming",
            "flaming": "scorching",
            "scorching": "incinerating",
            "incinerating": "carbonising",
            "poisonous": "noxious",
            "noxious": "venomous",
            "venomous": "toxic",
            "toxic": "lethal",
            "polished": "honed",
            "honed": "gleaming",
            "gleaming": "tempered",
            "tempered": "flaring",
            "sparking": "shocking",
            "shocking": "discharging",
            "discharging": "electrocuting",
            "electrocuting": "vapourising",
            "sturdy": "reinforced",
            "reinforced": "thickened",
            "thickened": "impregnable",
            "impregnable": "impenetrable",
            "piercing": "keen",
            "keen": "incisive",
            "incisive": "puncturing",
            "puncturing": "penetrating",
            "strengthened": "forceful",
            "forceful": "overwhelming",
            "overwhelming": "devastating",
            "devastating": "catastrophic",
            "accurate": "precise",
            "precise": "sharpshooter",
            "sharpshooter": "deadeye",
            "deadeye": "bullseye",
            "echo": "echoo",
            "echoo": "echooo",
            "echooo": "echoooo",
            "echoooo": "echoes"
        }
        return passive_upgrade_table.get(current_passive, current_passive)

    def get_passive_effect(self, passive: str) -> str:
        passive_messages = {
            "burning": "Increases your attack on normal hits. (8%).",
            "flaming": "Increases your attack on normal hits. (16%)",
            "scorching": "Increases your attack on normal hits. (24%)",
            "incinerating": "Increases your attack on normal hits. (32%)",
            "carbonising": "Increases your attack on normal hits. (40%)",
            "poisonous": "Additional damage on misses. (up to 10%)",
            "noxious": "Additional damage on misses. (up to 20%)",
            "venomous": "Additional damage on misses. (up to 30%)",
            "toxic": "Additional damage on misses. (up to 40%)",
            "lethal": "Additional damage on misses. (up to 50%)",
            "polished": "Reduce monster's defence. (8%)",
            "honed": "Reduce monster's defence. (16%)",
            "gleaming": "Reduce monster's defence. (24%)",
            "tempered": "Reduce monster's defence. (32%)",
            "flaring": "Reduce monster's defence. (40%)",
            "sparking": "Floor of normal hits raised. (8%)",
            "shocking": "Floor of normal hits raised. (16%)",
            "discharging": "Floor of normal hits raised. (24%)",
            "electrocuting": "Floor of normal hits raised. (32%)",
            "vapourising": "Floor of normal hits raised. (40%)",
            "sturdy": "Additional defence. (8%)",
            "reinforced": "Additional defence. (16%)",
            "thickened": "Additional defence. (24%)",
            "impregnable": "Additional defence. (32%)",
            "impenetrable": "Additional defence. (40%)",
            "piercing": "Additional crit chance. (5%)",
            "keen": "Additional crit chance. (10%)",
            "incisive": "Additional crit chance. (15%)",
            "puncturing": "Additional crit chance. (20%)",
            "penetrating": "Additional crit chance. (25%)",
            "strengthened": "Deals a near-fatal blow when monster is at threshold. (8%)",
            "forceful": "Deals a near-fatal blow when monster is at threshold. (16%)",
            "overwhelming": "Deals a near-fatal blow when monster is at threshold. (24%)",
            "devastating": "Deals a near-fatal blow when monster is at threshold. (32%)",
            "catastrophic": "Deals a near-fatal blow when monster is at threshold. (40%)",
            "accurate": "Increased accuracy. (4%)",
            "precise": "Increased accuracy. (8%)",
            "sharpshooter": "Increased accuracy. (12%)",
            "deadeye": "Increased accuracy. (16%)",
            "bullseye": "Increased accuracy. (20%)",
            "echo": "Echo normal hits. (10% dmg)",
            "echoo": "Echo normal hits. (20% dmg)",
            "echooo": "Echo normal hits. (30% dmg)",
            "echoooo": "Echo normal hits. (40% dmg)",
            "echoes": "Echo normal hits. (50% dmg)"
        }
        return passive_messages.get(passive, "No effect.")

    async def refine_item(self, 
                         interaction: Interaction, 
                         selected_item: tuple,
                         embed,
                         message) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        while True:
            selected_item = await self.bot.database.fetch_weapon_by_id(selected_item[0])
            item_id = selected_item[0]
            item_name = selected_item[2]
            item_level = selected_item[3]
            refines_remaining = selected_item[10]

            player_gold = await self.bot.database.fetch_user_gold(user_id, server_id)
            refinement_runes = await self.bot.database.fetch_refinement_runes(user_id)

            if refines_remaining <= 0:
                if refinement_runes > 0:
                    embed = discord.Embed(
                        title="Apply Rune of Refinement?",
                        description=(f"**{item_name}** has no refine attempts remaining.\n"
                                    f"Do you want to use a **Rune of Refinement** to add a refining attempt?\n"
                                    f"(You have {refinement_runes} rune(s) available)"),
                        color=0xFFCC00
                    )
                    rune_view = View(timeout=60.0)
                    rune_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_rune"))
                    rune_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_rune"))
                    
                    await message.edit(embed=embed, view=rune_view)

                    def check(button_interaction: Interaction):
                        return (button_interaction.user == interaction.user and 
                                button_interaction.message is not None and 
                                button_interaction.message.id == message.id)

                    try:
                        rune_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                        await rune_interaction.response.defer()

                        if rune_interaction.data['custom_id'] == "confirm_rune":
                            await self.bot.database.update_refinement_runes(user_id, -1)
                            await self.bot.database.update_weapon_refine_count(item_id, 1)
                            refines_remaining += 1
                        elif rune_interaction.data['custom_id'] == "cancel_rune":
                            break

                    except asyncio.TimeoutError:
                        await clear_msg(message)
                        self.bot.state_manager.clear_active(interaction.user.id)
                        break
                else:
                    embed.add_field(name="Refinement", value=f"You'll need runes of refinement to continue.\n"
                        "Returning...", inline=True)
                    await message.edit(embed=embed)
                    await asyncio.sleep(5)
                    break

            if item_level <= 40:
                refine_costs = [1000, 6000, 10000]
                cost = refine_costs[3 - refines_remaining]
            elif 40 < item_level <= 80:
                refine_costs = [5000, 15000, 25000, 50000]
                cost = refine_costs[4 - refines_remaining]
            else:
                refine_costs = [10000, 30000, 50000, 100000, 200000]
                cost = refine_costs[5 - refines_remaining]
            
            embed = discord.Embed(
                title="Confirm",
                description=f"Attempt to refine **{item_name}**?\n"
                            f"Cost: **{cost:,} GP**\n"
                            f"Refines Remaining: **{refines_remaining}**\n"
                            f"Stats are granted randomly based on the **weapon's level**.\n",
                color=0xFFCC00
            )
            embed.set_thumbnail(url="https://i.imgur.com/k8nPS3E.jpeg")
            refine_view = View(timeout=60.0)
            refine_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_refine"))
            refine_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_refine"))
            
            await message.edit(embed=embed, view=refine_view)

            def check(button_interaction: Interaction):
                return (button_interaction.user == interaction.user and 
                        button_interaction.message is not None and 
                        button_interaction.message.id == message.id)

            try:
                refine_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                await refine_interaction.response.defer()

                if refine_interaction.data['custom_id'] == "cancel_refine":
                    break

                if player_gold < cost:
                    embed.add_field(name="Refining", value=f"Not enough gold. Returning...", inline=False)
                    await message.edit(embed=embed)
                    await asyncio.sleep(2)
                    break

                await self.bot.database.update_user_gold(user_id, player_gold - cost)
                embed.add_field(name="Refining", value=f"The blacksmith carefully hones your weapon.", inline=False)
            
                attack_roll = random.randint(0, 100) < 80
                defense_roll = random.randint(0, 100) < 50
                rarity_roll = random.randint(0, 100) < 20

                attack_modifier = 0
                defense_modifier = 0
                rarity_modifier = 0
                max_range = int(item_level / 10) + 2
                if attack_roll:
                    attack_modifier = random.randint(2, max_range)
                else:
                    attack_modifier = 1
                    
            
                if defense_roll:
                    defense_modifier = random.randint(2, max_range)
                else:
                    defense_modifier = 1

                if rarity_roll:
                    rarity_modifier = random.randint(5, max_range * 5)
                    await self.bot.database.increase_weapon_rarity(item_id, rarity_modifier)

                await self.bot.database.increase_weapon_attack(item_id, attack_modifier)
                await self.bot.database.increase_weapon_defence(item_id, defense_modifier)
                await self.bot.database.update_weapon_refine_count(item_id, refines_remaining - 1)
                await self.bot.database.update_weapon_refine_lvl(item_id, 1)

                result_message = []
                if attack_modifier > 0:
                    result_message.append(f"Attack increased by **{attack_modifier}**!")
                if defense_modifier > 0:
                    result_message.append(f"Defense increased by **{defense_modifier}**!")
                if rarity_modifier > 0:
                    result_message.append(f"Rarity increased by **{rarity_modifier}**!")

                embed.add_field(name="Refining", value=("\n".join(result_message) + "\nSaving item..."), inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)
        return

async def setup(bot) -> None:
    await bot.add_cog(Weapons(bot))