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

    @app_commands.command(name="weapons", description="View your character's weapons and modify them.")
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
            items = await self.bot.database.fetch_user_weapons(user_id) # Re-fetch for potential changes
            if not items: # If all items were discarded, for example
                if message: # If original message exists
                    try:
                        await message.edit(content="You peer into your weapon's pouch, it is empty.", embed=None, view=None)
                    except discord.NotFound: # Message might have been deleted by "close"
                        pass
                else: # If somehow message is None but items became empty (e.g. initial send failed then items removed)
                    await interaction.followup.send("You peer into your weapon's pouch, it is empty.")
                self.bot.state_manager.clear_active(user_id)
                break
            
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            if total_pages == 0: # Handle case where total_pages becomes 0 after items are gone
                total_pages = 1 
            current_page = min(current_page, total_pages - 1) if total_pages > 0 else 0


            equipped_item_tuple = await self.bot.database.get_equipped_weapon(user_id)
            
            # Sort items: equipped first, then by item level
            sorted_items = []
            if equipped_item_tuple:
                # Find the equipped item in the full list and add it first
                equipped_id = equipped_item_tuple[0]
                for item in items:
                    if item[0] == equipped_id:
                        sorted_items.append(item)
                        break
                # Add other items, excluding the already added equipped one
                other_items = [item for item in items if item[0] != equipped_id]
            else:
                other_items = list(items)

            other_items.sort(key=lambda item: item[3], reverse=True) # Sort by item_level
            sorted_items.extend(other_items)


            start_idx = current_page * items_per_page
            items_to_display = sorted_items[start_idx:start_idx + items_per_page]
            
            embed.clear_fields()
            embed.description = f"{player_name}'s Weapons (Page {current_page + 1}/{total_pages}):"
            items_display_string = ""

            for index, item_tuple in enumerate(items_to_display):
                item_name = item_tuple[2]
                item_level = item_tuple[3]
                
                is_equipped_flag = equipped_item_tuple and (equipped_item_tuple[0] == item_tuple[0])
                
                items_display_string += (
                    f"{index + 1}: "
                    f"{'[E] ' if is_equipped_flag else ''}"
                    f"{item_name} (i{item_level})\n"
                )
            
            if not items_display_string:
                 items_display_string = "No weapons on this page."


            embed.add_field(
                name="Weapons:",
                value=items_display_string.strip() if items_display_string else "None",
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
                try:
                    await message.edit(embed=embed, view=view)
                except discord.NotFound:
                    self.bot.state_manager.clear_active(user_id)
                    return # Message was deleted, can't continue

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
                    selected_index_in_page = int(button_interaction.data['custom_id'].split("_")[1])
                    # selected_item_tuple_preview = items_to_display[selected_index_in_page]
                    await button_interaction.response.defer()

                    # This inner loop handles actions for a single selected item
                    # It re-fetches the item each time to ensure data is current
                    current_selected_item_id = items_to_display[selected_index_in_page][0]

                    while True: 
                        # Re-fetch user data for void key check, and item data for current stats
                        # existing_user is from the outer scope, could be stale for void keys if they change mid-session.
                        # For button display, it's okay. For actual consumption, it's handled in void_forge_item.
                        refetched_existing_user = await self.bot.database.fetch_user(user_id, server_id)
                        selected_item = await self.bot.database.fetch_weapon_by_id(current_selected_item_id)
                        
                        if not selected_item: # Item might have been discarded/sent by another process
                            await interaction.followup.send("The selected item no longer exists.", ephemeral=True)
                            break # Break from item action loop, will go to main weapon list loop

                        equipped_item_tuple = await self.bot.database.get_equipped_weapon(user_id) # Re-fetch for accurate equipped status

                        item_name = selected_item[2]
                        item_level = selected_item[3]
                        item_attack = selected_item[4]
                        item_defence = selected_item[5]
                        item_rarity = selected_item[6]
                        item_passive = selected_item[7]
                        forges_remaining = selected_item[9]
                        # refines_remaining = selected_item[10]
                        item_refinement = selected_item[11]
                        item_pinnacle_passive = selected_item[12]
                        item_utmost_passive = selected_item[13]
                        
                        is_equipped = equipped_item_tuple and (equipped_item_tuple[0] == selected_item[0])

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
                        
                        if item_pinnacle_passive != 'none':
                            embed.add_field(name="Pinnacle Passive", value=item_pinnacle_passive.capitalize(), inline=False)
                            pinnacle_effect_description = self.get_passive_effect(item_pinnacle_passive)
                            embed.add_field(name="Pinnacle Effect", value=pinnacle_effect_description, inline=False)

                        if item_utmost_passive != 'none':
                            embed.add_field(name="Utmost Passive", value=item_utmost_passive.capitalize(), inline=False)
                            utmost_effect_description = self.get_passive_effect(item_utmost_passive)
                            embed.add_field(name="Utmost Effect", value=utmost_effect_description, inline=False)

                        item_guide_lines = [
                            "Select an action:",
                            f"- {'Unequip' if is_equipped else 'Equip'}: {'Unequip' if is_equipped else 'Equip'} the item",
                            "- Forge: Attempt to forge",
                            "- Refine: Attempt to refine"
                        ]
                        # Voidforge condition check for guide
                        void_keys = refetched_existing_user[30] if len(refetched_existing_user) > 30 and refetched_existing_user[30] is not None else 0
                        if void_keys > 0 and is_equipped and item_utmost_passive == 'none':
                            item_guide_lines.append("- Voidforge: Attempt to voidforge (Requires Void Key)")
                        
                        item_guide_lines.extend([
                            "- Discard: Discard item",
                            "- Send: Send item to another player",
                            "- Back: Return to list"
                        ])
                        embed.add_field(name="Item Guide", value="\n".join(item_guide_lines), inline=False)
                        
                        action_view = View(timeout=60.0)
                        action_view.add_item(Button(label="Unequip" if is_equipped else "Equip", style=ButtonStyle.primary, custom_id="unequip" if is_equipped else "equip"))
                        if forges_remaining > 0:
                            action_view.add_item(Button(label="Forge", style=ButtonStyle.primary, custom_id="forge"))
                        action_view.add_item(Button(label="Refine", style=ButtonStyle.primary, custom_id="refine"))
                        
                        # Add Voidforge button conditionally
                        if void_keys > 0 and is_equipped and item_utmost_passive == 'none':
                            action_view.add_item(Button(label="Voidforge", style=ButtonStyle.primary, custom_id="voidforge")) # Using primary, purple not available

                        action_view.add_item(Button(label="Discard", style=ButtonStyle.danger, custom_id="discard"))
                        if (refetched_existing_user[31] > 0):
                            action_view.add_item(Button(label="Shatter", style=ButtonStyle.primary, custom_id="shatter"))
                        action_view.add_item(Button(label="Send", style=ButtonStyle.primary, custom_id="send"))
                        action_view.add_item(Button(label="Back", style=ButtonStyle.secondary, custom_id="back"))
                        
                        if message:
                            await message.edit(embed=embed, view=action_view)
                        
                        try:
                            action_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check) # `check` still uses original_user
                            await action_interaction.response.defer()

                            if action_interaction.data['custom_id'] in ["equip", "unequip"]:
                                if action_interaction.data['custom_id'] == "equip":
                                    await self.bot.database.equip_weapon(user_id, selected_item[0])
                                else:  # unequip
                                    await self.bot.database.unequip_weapon(user_id)
                                continue # Re-fetch and re-display item details
                            elif action_interaction.data['custom_id'] == "forge":
                                await self.forge_item(action_interaction, selected_item, embed, message)
                                continue
                            elif action_interaction.data['custom_id'] == "refine":
                                await self.refine_item(action_interaction, selected_item, embed, message)
                                continue
                            elif action_interaction.data['custom_id'] == "voidforge":
                                # Pass the most up-to-date selected_item and user data
                                await self.void_forge_item(action_interaction, selected_item, message, refetched_existing_user)
                                continue # Re-fetch and re-display item details
                            elif action_interaction.data['custom_id'] == "send":
                                if is_equipped:
                                    # Create a temporary embed for the error to avoid clearing fields
                                    error_embed = embed.copy()
                                    error_embed.add_field(name="Error", value="You should probably unequip the weapon before sending it. Returning...", inline=False)
                                    await message.edit(embed=error_embed, view=None) # Remove buttons during error
                                    await asyncio.sleep(3)
                                    # No continue here, will re-render the item view with buttons below
                                    # Actually, we want to break to go back to item list or continue to re-render item details
                                    # If we `continue` here, it re-renders the item, which is correct.
                                    continue

                                temp_send_embed = embed.copy() # Use a copy to avoid permanent changes if timeout
                                temp_send_embed.clear_fields() # Clear for the prompt
                                temp_send_embed.add_field(
                                    name="Send Weapon",
                                    value="Please mention a user (@username) to send the weapon to.",
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
                                    send_item_flag = True # Renamed from send_item to avoid conflict
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
                                        if (item_level - current_level_receiver) > 15:
                                            send_item_flag = False
                                            error_messages_send.append("Item iLvl diff too great. (< 15)")
                                        
                                        receiver_items_count = await self.bot.database.count_user_weapons(str(receiver.id))
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
                                            await self.bot.database.send_weapon(str(receiver.id), selected_item[0])
                                            confirm_embed.clear_fields()
                                            confirm_embed.add_field(name="Weapon Sent", value=f"Sent **{item_name}** to {receiver.mention}! 🎉", inline=False)
                                            await message.edit(embed=confirm_embed, view=None)
                                            await asyncio.sleep(3)
                                            break  # Return to weapon list (main pagination loop)
                                        else: # Cancel send
                                            # self.bot.state_manager.clear_active(user_id) # Don't clear, just go back to item view
                                            continue # Back to item details view
                                    
                                    except asyncio.TimeoutError:
                                        # Timeout on confirm send, edit message and then let item loop continue
                                        await message.edit(content="Send confirmation timed out.", embed=None, view=None)
                                        await asyncio.sleep(3)
                                        # self.bot.state_manager.clear_active(user_id) # No, stay in item view
                                        continue # Back to item details view (will re-render)
                                    
                                except asyncio.TimeoutError: # Timeout on waiting for user mention
                                    await message.edit(content="Send weapon timed out while waiting for user mention.", embed=None, view=None)
                                    await asyncio.sleep(3)
                                    # self.bot.state_manager.clear_active(user_id)
                                    continue # Back to item details view (will re-render)
                            elif action_interaction.data['custom_id'] == "discard":
                                # discard returns True if item was discarded, False if cancelled
                                discarded = await self.discard(action_interaction, selected_item, message, embed)
                                if discarded:
                                    break # Item gone, go back to main weapon list
                                else:
                                    continue # Cancelled discard, re-render item details
                            elif action_interaction.data['custom_id'] == "shatter":
                                shattered = await self.shatter(action_interaction, selected_item, message, embed)
                                if shattered:
                                    break # Item gone, go back to main weapon list
                                else:
                                    continue # Cancelled shattered, re-render item details
                            elif action_interaction.data['custom_id'] == "back":
                                break # Break from item action loop, go to main weapon list loop

                        except asyncio.TimeoutError: # Timeout on item action buttons
                            if message:
                                try:
                                    await message.delete()
                                except discord.NotFound: pass
                            self.bot.state_manager.clear_active(user_id)
                            return # Exit command entirely

            except asyncio.TimeoutError: # Timeout on main pagination buttons (item#, prev, next, close)
                if message:
                    try:
                        await message.delete()
                    except discord.NotFound: pass
                self.bot.state_manager.clear_active(user_id)
                break # Exit main pagination loop
        
        #This clear active is important if the while loop breaks normally (e.g. close button)
        self.bot.state_manager.clear_active(user_id)


    async def discard(self, 
                     interaction: Interaction, 
                     selected_item: tuple,
                     message: Message, 
                     embed: discord.Embed) -> bool: # Return True if discarded, False otherwise
        """Discard an item."""
        item_id = selected_item[0]
        item_name = selected_item[2]

        confirm_embed = discord.Embed( # Create new embed for discard
            title="Confirm Discard",
            description=f"Are you sure you want to discard **{item_name}**?\n"
                        "**This action cannot be undone.**",
            color=0xFF0000,
        )
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.danger, custom_id="confirm_discard"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_discard"))
        
        await message.edit(embed=confirm_embed, view=confirm_view)

        def check(button_interaction: Interaction):
            return (button_interaction.user == interaction.user and 
                    button_interaction.message is not None and 
                    button_interaction.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
            await confirm_interaction.response.defer()
            
            if confirm_interaction.data['custom_id'] == "confirm_discard":
                await self.bot.database.discard_weapon(item_id)
                # Don't send a message here, the main loop will refresh
                return True # Discarded
            else: # Cancelled discard
                return False # Not discarded

        except asyncio.TimeoutError:
            # Timeout on discard confirmation
            await message.edit(content="Discard confirmation timed out.", embed=None, view=None) # Clear embed and view
            await asyncio.sleep(3)
            # self.bot.state_manager.clear_active(interaction.user.id) # Don't clear, let outer loop handle
            return False # Not discarded
        


    async def shatter(self, 
                     interaction: Interaction, 
                     selected_item: tuple,
                     message: Message, 
                     embed: discord.Embed) -> bool: # Return True if discarded, False otherwise
        """Discard an item."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        item_id = selected_item[0]
        item_name = selected_item[2]
        runes_back = (selected_item[11] * 0.8)
        confirm_embed = discord.Embed( # Create new embed for discard
            title="Confirm Shatter",
            description=f"Are you sure you want to shatter **{item_name}**?\n"
                        f"You will get **{runes_back}** runes of refinement back.\n"
                        "**This action cannot be undone.**",
            color=0xFF0000,
        )
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.danger, custom_id="confirm_shatter"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_shatter"))
        
        await message.edit(embed=confirm_embed, view=confirm_view)

        def check(button_interaction: Interaction):
            return (button_interaction.user == interaction.user and 
                    button_interaction.message is not None and 
                    button_interaction.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
            await confirm_interaction.response.defer()
            
            if confirm_interaction.data['custom_id'] == "confirm_shatter":
                await self.bot.database.discard_weapon(item_id)
                await self.bot.database.update_refinement_runes(user_id, runes_back)
                await self.bot.database.update_shatter_runes(user_id, -1)
                return True # Discarded
            else: # Cancelled discard
                return False # Not discarded

        except asyncio.TimeoutError:
            # Timeout on discard confirmation
            await message.edit(content="Discard confirmation timed out.", embed=None, view=None) # Clear embed and view
            await asyncio.sleep(3)
            # self.bot.state_manager.clear_active(interaction.user.id) # Don't clear, let outer loop handle
            return False # Not discarded
        

    async def void_forge_item(self,
                              interaction: Interaction,
                              equipped_weapon: tuple,
                              message: Message,
                              existing_user_data: tuple) -> None:
        user_id = str(interaction.user.id)
        # server_id = str(interaction.guild.id) # Not needed here unless DB calls require it
        equipped_weapon_id = equipped_weapon[0]
        equipped_weapon_name = equipped_weapon[2]

        # 1. Fetch sacrificeable weapons
        sacrifice_candidates = await self.bot.database.fetch_void_forge_weapons(user_id)
        
        temp_embed = discord.Embed(title=f"Voidforging **{equipped_weapon_name}**", color=discord.Color.purple())

        if not sacrifice_candidates:
            temp_embed.description = "Searching for eligible weapons..."
            await message.edit(embed=temp_embed, view=None)
            await asyncio.sleep(1.5) # Simulate search
            temp_embed.add_field(name="No Eligible Weapons", 
                                 value="You have no weapons suitable for voidforging sacrifice.\n"
                                       "Eligible weapons must have refinement level >= 5, 0 forges remaining, and not be equipped.", 
                                 inline=False)
            await message.edit(embed=temp_embed, view=None)
            await asyncio.sleep(5)
            return # Returns to item action loop, which will re-render the item details

        # 2. Display sacrificeable weapons and prompt for ID
        display_embed = discord.Embed(
            title=f"Voidforge: Sacrifice for {equipped_weapon_name}",
            description="**Type** the ID of the weapon you wish to sacrifice. This weapon will be __**destroyed**__.\n\n"
            "**WARNING**: Passives of the same type will NOT both work during combat, only the highest level will.\n"
            "Type __'cancel'__ to go back.",
            color=discord.Color.purple()
        )
        display_embed.set_thumbnail(url="https://i.imgur.com/rZnRu0R.jpeg")
        
        sacrifice_display_string = ""
        valid_sacrifice_ids = []
        for i, sac_weapon in enumerate(sacrifice_candidates):
            sac_id = sac_weapon[0]
            sac_name = sac_weapon[2]
            sac_passive = sac_weapon[7] # passive
            sac_passive_effect = self.get_passive_effect(sac_passive)
            sacrifice_display_string += f"**ID: {sac_id}** - {sac_name}\n"
            sacrifice_display_string += f"  Passive: {sac_passive.capitalize()} - {sac_passive_effect}\n\n"
            valid_sacrifice_ids.append(str(sac_id))

        display_embed.add_field(name="Sacrificeable Weapons", value=sacrifice_display_string[:1020] + "..." if len(sacrifice_display_string) > 1024 else sacrifice_display_string, inline=False)
        # Add pagination here if sacrifice_candidates can be very long. For now, truncating.
        
        await message.edit(embed=display_embed, view=None)

        # 3. Wait for user message (sacrifice ID)
        def sacrifice_check(m: Message):
            return m.author == interaction.user and m.channel == interaction.channel

        selected_sacrifice_weapon_data = None
        while True:
            try:
                user_input_msg = await self.bot.wait_for('message', timeout=60.0, check=sacrifice_check)
                try:
                    await user_input_msg.delete()
                except discord.NotFound: pass
                
                content = user_input_msg.content.strip()
                if content.lower() == 'cancel':
                    return # Back to item action loop

                if content in valid_sacrifice_ids:
                    sac_id_to_fetch = int(content)
                    for sac_w in sacrifice_candidates:
                        if sac_w[0] == sac_id_to_fetch:
                            selected_sacrifice_weapon_data = sac_w
                            break
                    if selected_sacrifice_weapon_data:
                        break 
                else:
                    await interaction.followup.send(f"Invalid ID: '{content}'. Please enter a valid weapon ID from the list or type 'cancel'.", ephemeral=True)
            
            except asyncio.TimeoutError:
                await message.edit(content="Voidforge timed out while waiting for sacrifice ID. Returning to item menu.", embed=None, view=None)
                await asyncio.sleep(3)
                return

        if not selected_sacrifice_weapon_data:
            return # Should be caught by timeout or cancel

        # 4. Confirmation step
        sac_weapon_id = selected_sacrifice_weapon_data[0]
        sac_weapon_name = selected_sacrifice_weapon_data[2]
        sac_weapon_passive = selected_sacrifice_weapon_data[7]
        sac_weapon_passive_effect = self.get_passive_effect(sac_weapon_passive)

        confirm_embed = discord.Embed(
            title="Confirm Voidforge",
            description="Are you sure you want to proceed? The sacrificed weapon will be __**destroyed**__ no matter what happens.\n"
            "You estimate you have a **25%** chance to succeed, and a **25%** chance for something horrible to happen...",
            color=discord.Color.orange() # discord.py color
        )
        eq_name = equipped_weapon[2]
        eq_level = equipped_weapon[3]
        eq_attack = equipped_weapon[4]
        eq_defence = equipped_weapon[5]
        eq_rarity = equipped_weapon[6]
        eq_passive = equipped_weapon[7]
        eq_pinnacle = equipped_weapon[12]
        # eq_utmost = equipped_weapon[13] # Utmost is 'none' at this stage

        eq_details = f"**{eq_name}** (i{eq_level})\n"
        eq_details += f"Atk: {eq_attack}, Def: {eq_defence}, Rarity: {eq_rarity}\n"
        eq_details += f"Passive: {eq_passive.capitalize()} - {self.get_passive_effect(eq_passive)}\n"
        if eq_pinnacle != 'none':
            eq_details += f"Pinnacle: {eq_pinnacle.capitalize()} - {self.get_passive_effect(eq_pinnacle)}\n"
        confirm_embed.add_field(name="Equipped Weapon (Recipient)", value=eq_details.strip(), inline=False)

        sac_details = f"**{sac_weapon_name}**\n"
        sac_details += f"Passive: {sac_weapon_passive.capitalize()} - {sac_weapon_passive_effect}\n"
        confirm_embed.add_field(name="Sacrifice Weapon (To be destroyed)", value=sac_details.strip(), inline=False)
        
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm Voidforge", style=ButtonStyle.danger, custom_id="confirm_voidforge"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_voidforge"))

        await message.edit(embed=confirm_embed, view=confirm_view)

        original_user_obj = interaction.user 

        def confirm_button_check(btn_interaction: Interaction):
            return (btn_interaction.user == original_user_obj and 
                    btn_interaction.message is not None and 
                    btn_interaction.message.id == message.id)
        
        try:
            confirm_button_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=confirm_button_check)
            await confirm_button_interaction.response.defer()

            if confirm_button_interaction.data['custom_id'] == "cancel_voidforge":
                return # Back to item action loop
            
            if confirm_button_interaction.data['custom_id'] == "confirm_voidforge":
                await self.bot.database.add_void_keys(user_id, -1)

                roll = random.random()
                outcome_message = ""
                
                equipped_weapon_pinnacle_passive = equipped_weapon[12]

                if roll < 0.25: # Outcome 1: Add passive (25%)
                    if equipped_weapon_pinnacle_passive == 'none':
                        await self.bot.database.update_item_pinnacle_passive(equipped_weapon_id, sac_weapon_passive)
                        outcome_message = (f"Success! The essence of **{sac_weapon_name}** was imbued into **{equipped_weapon_name}**, "
                                           f"granting it the Pinnacle Passive: **{sac_weapon_passive.capitalize()}**!")
                    else: # Pinnacle exists, utmost is 'none' (button condition), so write to utmost
                        await self.bot.database.update_item_utmost_passive(equipped_weapon_id, sac_weapon_passive)
                        outcome_message = (f"Astounding Success! The essence of **{sac_weapon_name}** was deeply imbued into **{equipped_weapon_name}**, "
                                           f"granting it the Utmost Passive: **{sac_weapon_passive.capitalize()}**!")
                elif roll < 0.50: # Outcome 2: Overwrite passive (25%)
                    await self.bot.database.update_weapon_passive(equipped_weapon_id, sac_weapon_passive)
                    outcome_message = (f"Disaster strikes! The voidforge howls with fury, the passive of **{equipped_weapon_name}** has been overwritten by **{sac_weapon_name}**'s essence, "
                                       f"now possessing: **{sac_weapon_passive.capitalize()}**!")
                    if equipped_weapon_pinnacle_passive != 'none':
                        await self.bot.database.update_item_pinnacle_passive(equipped_weapon_id, 'none')
                        outcome_message += f"\nIts Pinnacle Passive was consumed in the chaotic process."
                else: # Outcome 3: Failure (50%)
                    outcome_message = (f"Your hand slips! The voidforging process fails for **{equipped_weapon_name}**. "
                                       f"The essence of **{sac_weapon_name}** dissipates harmlessly into the void.")

                await self.bot.database.discard_weapon(sac_weapon_id)

                final_embed = discord.Embed(
                    title="Voidforge Complete",
                    description=f"The Void Key crumbles to dust...\n\n{outcome_message}",
                    color=discord.Color.green() if "Success" in outcome_message or "fusion" in outcome_message else discord.Color.red()
                )
                await message.edit(embed=final_embed, view=None)
                await asyncio.sleep(8)
                return # Back to item action loop, will re-render item

        except asyncio.TimeoutError:
            await message.edit(content="Voidforge confirmation timed out. Returning to item menu.", embed=None, view=None)
            await asyncio.sleep(3)
            return # Back to item action loop


    async def forge_item(self, 
                        interaction: Interaction, 
                        selected_item: tuple, 
                        embed: discord.Embed, # embed is passed but should be managed carefully
                        message: Message) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        while True:
            # Re-fetch item to ensure data is current before forging
            print('Fetching item to forge')
            current_item_state = await self.bot.database.fetch_weapon_by_id(selected_item[0])
            if not current_item_state:
                # Item might have been removed by another process
                # Create a temporary embed for the error
                error_embed = discord.Embed(title="Error", description="Item not found. It may have been removed.", color=discord.Color.red())
                await message.edit(embed=error_embed, view=None)
                await asyncio.sleep(3)
                return # Return to item action loop

            item_id = current_item_state[0]
            item_name = current_item_state[2] 
            item_level = current_item_state[3]
            forges_remaining = current_item_state[9]

            # Create a new embed for forging process to avoid modifying shared embed directly
            forge_embed = discord.Embed(title=f"Forging: {item_name}", color=0xFFFF00)
            forge_embed.set_thumbnail(url="https://i.imgur.com/jgq4aGA.jpeg")


            if forges_remaining < 1:
                forge_embed.description = "This item cannot be forged anymore.\nReturning..."
                await message.edit(embed=forge_embed, view=None)
                await asyncio.sleep(1)
                return

            base_success_rate = 0.8
            if item_level <= 40:
                costs = {
                    3: (10, 10, 10, 100), 2: (10, 10, 10, 400), 1: (10, 10, 10, 1000),
                }
                cost_index_map = {3: 3, 2: 4, 1: 5} # Maps forges_remaining to resource index (iron=3, coal=4, gold=5, plat=6, idea=7)
                success_rate = base_success_rate - (3 - forges_remaining) * 0.05
                forges_data = {
                    3: ('iron', 'oak', 'desiccated'), 2: ('coal', 'willow', 'regular'), 1: ('gold', 'mahogany', 'sturdy'),
                }
            elif 40 < item_level <= 80:    
                costs = {
                    4: (25, 25, 25, 250), 3: (25, 25, 25, 1000), 2: (25, 25, 25, 2500), 1: (25, 25, 25, 5000),
                }       
                cost_index_map = {4: 3, 3: 4, 2: 5, 1: 6}
                forges_data = {
                    4: ('iron', 'oak', 'desiccated'), 3: ('coal', 'willow', 'regular'), 2: ('gold', 'mahogany', 'sturdy'), 1: ('platinum', 'magic', 'reinforced'),
                }
                success_rate = base_success_rate - (4 - forges_remaining) * 0.05 
            else: # item_level > 80
                costs = {
                    5: (50, 50, 50, 500), 4: (50, 50, 50, 2000), 3: (50, 50, 50, 5000), 2: (50, 50, 50, 10000), 1: (50, 50, 50, 20000),
                }
                cost_index_map = {5: 3, 4: 4, 3: 5, 2: 6, 1: 7}
                forges_data = {
                    5: ('iron', 'oak', 'desiccated'), 4: ('coal', 'willow', 'regular'), 3: ('gold', 'mahogany', 'sturdy'), 2: ('platinum', 'magic', 'reinforced'), 1: ('idea', 'idea', 'titanium'), # Assuming 'idea' for ore/wood
                }
                success_rate = base_success_rate - (5 - forges_remaining) * 0.05

            success_rate = max(0.05, min(success_rate, 0.95)) # Ensure success rate is within a reasonable bound
            existing_user = await self.bot.database.fetch_user(user_id, server_id)
            player_gp = existing_user[6]
            mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
            woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
            fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

            if forges_remaining not in costs: # Should not happen if logic is correct
                forge_embed.description = "Error determining forge costs. Returning..."
                await message.edit(embed=forge_embed, view=None)
                await asyncio.sleep(3)
                return

            ore_cost, wood_cost, bone_cost, gp_cost = costs[forges_remaining]
            ore_type, log_type, bone_type = forges_data.get(forges_remaining, (None, None, None))
            
            # Determine resource index (3 for iron/oak/desiccated, 4 for coal/willow/regular etc.)
            # This mapping needs to be robust. The `cost_index_map` is an attempt.
            # Example: if forges_remaining = 3 (for item_level <= 40), ore_type is 'iron'. 'iron' is index 3 in mining table.
            # mining_data: user_id, server_id, pickaxe_tier, iron, coal, gold, platinum, idea
            # Indices:         0,         1,              2,    3,    4,    5,        6,    7
            # fishing_data: user_id, server_id, fishing_rod, desiccated_bones, regular_bones, sturdy_bones, reinforced_bones, titanium_bones
            # Indices:          0,         1,           2,                  3,             4,            5,                6,              7
            # woodcutting_data: user_id, server_id, axe_type, oak_logs, willow_logs, mahogany_logs, magic_logs, idea_logs
            # Indices:            0,         1,          2,        3,           4,             5,          6,         7
            
            # Resource name to index mapping
            ore_to_idx = {'iron': 3, 'coal': 4, 'gold': 5, 'platinum': 6, 'idea': 7}
            log_to_idx = {'oak': 3, 'willow': 4, 'mahogany': 5, 'magic': 6, 'idea': 7}
            bone_to_idx = {'desiccated': 3, 'regular': 4, 'sturdy': 5, 'reinforced': 6, 'titanium': 7}

            actual_ore_owned = mining_data[ore_to_idx[ore_type]] if ore_type and ore_type in ore_to_idx else 0
            actual_logs_owned = woodcutting_data[log_to_idx[log_type]] if log_type and log_type in log_to_idx else 0
            actual_bones_owned = fishing_data[bone_to_idx[bone_type]] if bone_type and bone_type in bone_to_idx else 0


            if (actual_ore_owned < ore_cost or
                actual_logs_owned < wood_cost or
                actual_bones_owned < bone_cost or
                player_gp < gp_cost):
                forge_embed.description = (f"You do not have enough resources to forge this item.\n"
                                        f"Forging costs:\n"
                                        f"- **{ore_type.capitalize()}** {'Ore' if ore_type != 'coal' else ''} : **{ore_cost}** (You have: {actual_ore_owned})\n"
                                        f"- **{log_type.capitalize()}** Logs: **{wood_cost}** (You have: {actual_logs_owned})\n"
                                        f"- **{bone_type.capitalize()}** Bones: **{bone_cost}** (You have: {actual_bones_owned})\n"
                                        f"- GP cost: **{gp_cost:,}** (You have: {player_gp:,})\nReturning...")
                await message.edit(embed=forge_embed, view=None)
                await asyncio.sleep(3)
                return
            
            forge_embed.description=(f"Attempt to forge **{item_name}**?\n"
                                    f"Forging costs:\n"
                                    f"- **{ore_type.capitalize()}** {'Ore' if ore_type != 'coal' else ''} : **{ore_cost}**\n"
                                    f"- **{log_type.capitalize()}** Logs: **{wood_cost}**\n"
                                    f"- **{bone_type.capitalize()}** Bones: **{bone_cost}**\n"
                                    f"- GP cost: **{gp_cost:,}**\n"
                                    f"- Success rate: **{int(success_rate * 100)}%**\n")
            confirm_view = View(timeout=60.0)
            confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_forge"))
            confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_forge"))
            
            await message.edit(embed=forge_embed, view=confirm_view)

            def check(button_interaction: Interaction):
                return (button_interaction.user == interaction.user and 
                        button_interaction.message is not None and 
                        button_interaction.message.id == message.id)

            try:
                confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                await confirm_interaction.response.defer()
                
                if confirm_interaction.data['custom_id'] == "cancel_forge":
                    return # Return to item action loop

                mining_deduction = {'iron': 0, 'coal': 0, 'gold': 0, 'platinum': 0, 'idea': 0}
                if ore_type in mining_deduction: # Ensure ore_type is a valid key
                    mining_deduction[ore_type] = -ore_cost
                else:
                    print(f"ERROR: Invalid ore_type '{ore_type}' for mining deduction.")
                    # Handle error appropriately, e.g., show message and return
                    forge_embed.description = f"Internal error: Invalid resource type for deduction ({ore_type})."
                    await message.edit(embed=forge_embed, view=None)
                    await asyncio.sleep(3)
                    return
                await self.bot.database.update_mining_resources(user_id, server_id, mining_deduction)

                woodcutting_deduction = {'oak': 0, 'willow': 0, 'mahogany': 0, 'magic': 0, 'idea': 0}
                if log_type in woodcutting_deduction: # Ensure log_type is a valid key
                    woodcutting_deduction[log_type] = -wood_cost
                else:
                    print(f"ERROR: Invalid log_type '{log_type}' for woodcutting deduction.")
                    forge_embed.description = f"Internal error: Invalid resource type for deduction ({log_type})."
                    await message.edit(embed=forge_embed, view=None)
                    await asyncio.sleep(3)
                    return
                await self.bot.database.update_woodcutting_resources(user_id, server_id, woodcutting_deduction)

                fishing_deduction = {'desiccated': 0, 'regular': 0, 'sturdy': 0, 'reinforced': 0, 'titanium': 0}
                if bone_type in fishing_deduction: # Ensure bone_type is a valid key
                    fishing_deduction[bone_type] = -bone_cost
                else:
                    print(f"ERROR: Invalid bone_type '{bone_type}' for fishing deduction.")
                    forge_embed.description = f"Internal error: Invalid resource type for deduction ({bone_type})."
                    await message.edit(embed=forge_embed, view=None)
                    await asyncio.sleep(3)
                    return
                await self.bot.database.update_fishing_resources(user_id, server_id, fishing_deduction)

                await self.bot.database.add_gold(user_id, -gp_cost)

                new_forges_remaining = forges_remaining - 1
                forge_success = random.random() <= success_rate  

                forge_embed.clear_fields() # Clear previous description if any

                if forge_success:
                    current_passive = current_item_state[7]
                    if current_passive == "none":
                        passives = ["burning", "poisonous", "polished", "sparking", "sturdy", "piercing", "strengthened", "accurate", "echo"]
                        new_passive = random.choice(passives)
                        await self.bot.database.update_weapon_passive(item_id, new_passive)
                        forge_embed.description = (f"🎊 Congratulations! 🎊\n" 
                                                f"**{item_name}** has gained the " 
                                                f"**{new_passive.capitalize()}** passive.\nReturning...")
                    else:
                        new_passive = await self.upgrade_passive(current_passive)
                        await self.bot.database.update_weapon_passive(item_id, new_passive)
                        forge_embed.description = (f"🎊 Congratulations! 🎊\n"
                                                f"**{item_name}**'s passive upgrades from **{current_passive.capitalize()}**"
                                                f" to **{new_passive.capitalize()}**.\nReturning...")
                else:
                    forge_embed.description = (f"Your hand slips and you fail to strike the weapon! 💔\n"
                                            f"Better luck next time.\n"
                                            f"Returning to item menu...")
            
                await self.bot.database.update_weapon_forge_count(item_id, new_forges_remaining)
                await message.edit(embed=forge_embed, view=None)
                await asyncio.sleep(4)

            except asyncio.TimeoutError:
                # Timeout on forge confirmation
                await message.edit(content="Forge confirmation timed out.", embed=None, view=None)
                await asyncio.sleep(3)
                # self.bot.state_manager.clear_active(interaction.user.id) # Let item action loop handle this
                return

    async def upgrade_passive(self, current_passive: str) -> str:
        """Upgrade the current passive to a stronger version."""
        passive_upgrade_table = {
            "burning": "flaming", "flaming": "scorching", "scorching": "incinerating", "incinerating": "carbonising", "carbonising": "carbonising", # Maxed
            "poisonous": "noxious", "noxious": "venomous", "venomous": "toxic", "toxic": "lethal", "lethal": "lethal",
            "polished": "honed", "honed": "gleaming", "gleaming": "tempered", "tempered": "flaring", "flaring": "flaring",
            "sparking": "shocking", "shocking": "discharging", "discharging": "electrocuting", "electrocuting": "vapourising", "vapourising": "vapourising",
            "sturdy": "reinforced", "reinforced": "thickened", "thickened": "impregnable", "impregnable": "impenetrable", "impenetrable": "impenetrable",
            "piercing": "keen", "keen": "incisive", "incisive": "puncturing", "puncturing": "penetrating", "penetrating": "penetrating",
            "strengthened": "forceful", "forceful": "overwhelming", "overwhelming": "devastating", "devastating": "catastrophic", "catastrophic": "catastrophic",
            "accurate": "precise", "precise": "sharpshooter", "sharpshooter": "deadeye", "deadeye": "bullseye", "bullseye": "bullseye",
            "echo": "echoo", "echoo": "echooo", "echooo": "echoooo", "echoooo": "echoes", "echoes": "echoes"
        }
        return passive_upgrade_table.get(current_passive, current_passive)

    def get_passive_effect(self, passive: str) -> str:
        passive_messages = {
            "burning": "Increases your attack on normal hits. (8%).", "flaming": "Increases your attack on normal hits. (16%)", "scorching": "Increases your attack on normal hits. (24%)", "incinerating": "Increases your attack on normal hits. (32%)", "carbonising": "Increases your attack on normal hits. (40%)",
            "poisonous": "Additional damage on misses. (up to 10%)", "noxious": "Additional damage on misses. (up to 20%)", "venomous": "Additional damage on misses. (up to 30%)", "toxic": "Additional damage on misses. (up to 40%)", "lethal": "Additional damage on misses. (up to 50%)",
            "polished": "Reduce monster's defence. (8%)", "honed": "Reduce monster's defence. (16%)", "gleaming": "Reduce monster's defence. (24%)", "tempered": "Reduce monster's defence. (32%)", "flaring": "Reduce monster's defence. (40%)",
            "sparking": "Floor of normal hits raised. (8%)", "shocking": "Floor of normal hits raised. (16%)", "discharging": "Floor of normal hits raised. (24%)", "electrocuting": "Floor of normal hits raised. (32%)", "vapourising": "Floor of normal hits raised. (40%)",
            "sturdy": "Additional defence. (8%)", "reinforced": "Additional defence. (16%)", "thickened": "Additional defence. (24%)", "impregnable": "Additional defence. (32%)", "impenetrable": "Additional defence. (40%)",
            "piercing": "Additional crit chance. (5%)", "keen": "Additional crit chance. (10%)", "incisive": "Additional crit chance. (15%)", "puncturing": "Additional crit chance. (20%)", "penetrating": "Additional crit chance. (25%)",
            "strengthened": "Deals a near-fatal blow when monster is at threshold. (8%)", "forceful": "Deals a near-fatal blow when monster is at threshold. (16%)", "overwhelming": "Deals a near-fatal blow when monster is at threshold. (24%)", "devastating": "Deals a near-fatal blow when monster is at threshold. (32%)", "catastrophic": "Deals a near-fatal blow when monster is at threshold. (40%)",
            "accurate": "Increased accuracy. (4%)", "precise": "Increased accuracy. (8%)", "sharpshooter": "Increased accuracy. (12%)", "deadeye": "Increased accuracy. (16%)", "bullseye": "Increased accuracy. (20%)",
            "echo": "Echo normal hits. (10% dmg)", "echoo": "Echo normal hits. (20% dmg)", "echooo": "Echo normal hits. (30% dmg)", "echoooo": "Echo normal hits. (40% dmg)", "echoes": "Echo normal hits. (50% dmg)"
        }
        return passive_messages.get(passive, "No defined effect.")

    async def refine_item(self, 
                         interaction: Interaction, 
                         selected_item_tuple_initial: tuple, # Renamed to avoid conflict
                         embed_ref: discord.Embed, # Passed embed, be careful with modifications
                         message: Message) -> None:
        user_id = str(interaction.user.id)
        # server_id = str(interaction.guild.id) # Not used directly here

        # This loop allows for using a rune and then re-attempting refinement immediately
        while True: 
            # Re-fetch item each iteration to get the latest state, especially after using a rune
            current_item_state = await self.bot.database.fetch_weapon_by_id(selected_item_tuple_initial[0])
            if not current_item_state:
                # Item might have been removed by another process
                error_embed = discord.Embed(title="Error", description="Item not found. It may have been removed.", color=discord.Color.red())
                await message.edit(embed=error_embed, view=None)
                await asyncio.sleep(3)
                return # Return to item action loop

            item_id = current_item_state[0]
            item_name = current_item_state[2]
            item_level = current_item_state[3]
            refines_remaining = current_item_state[10]

            player_gold = await self.bot.database.fetch_user_gold(user_id, interaction.guild.id) # server_id needed for fetch_user_gold
            refinement_runes = await self.bot.database.fetch_refinement_runes(user_id)
            
            # Create a new embed for refinement process to avoid modifying shared embed directly
            refine_embed = discord.Embed(title=f"Refining: {item_name}", color=0xFFCC00)
            refine_embed.set_thumbnail(url="https://i.imgur.com/k8nPS3E.jpeg")


            if refines_remaining <= 0:
                if refinement_runes > 0:
                    refine_embed.title = "Apply Rune of Refinement?"
                    refine_embed.description = (f"**{item_name}** has no refine attempts remaining.\n"
                                                f"Do you want to use a **Rune of Refinement** to add a refining attempt?\n"
                                                f"(You have {refinement_runes} rune(s) available)")
                    rune_view = View(timeout=60.0)
                    rune_view.add_item(Button(label="Confirm Use Rune", style=ButtonStyle.primary, custom_id="confirm_rune"))
                    rune_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_rune"))
                    
                    await message.edit(embed=refine_embed, view=rune_view)

                    def check(button_interaction: Interaction):
                        return (button_interaction.user == interaction.user and 
                                button_interaction.message is not None and 
                                button_interaction.message.id == message.id)
                    try:
                        rune_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                        await rune_interaction.response.defer()

                        if rune_interaction.data['custom_id'] == "confirm_rune":
                            await self.bot.database.update_refinement_runes(user_id, -1)
                            await self.bot.database.update_weapon_refine_count(item_id, 1) # Adds 1 attempt
                            # refines_remaining += 1 # Don't modify local, re-fetch in next loop iteration
                            continue # Re-start the refine logic with the new attempt
                        elif rune_interaction.data['custom_id'] == "cancel_rune":
                            return # Cancelled rune usage, back to item action menu
                    except asyncio.TimeoutError:
                        await message.edit(content="Rune usage timed out.", embed=None, view=None)
                        await asyncio.sleep(3)
                        # self.bot.state_manager.clear_active(interaction.user.id) # Let item action loop handle
                        return # Back to item action menu
                else: # No refines left and no runes
                    refine_embed.description = (f"**{item_name}** has no refine attempts remaining.\n"
                                                "You also have no Runes of Refinement.\nReturning...")
                    await message.edit(embed=refine_embed, view=None)
                    await asyncio.sleep(5)
                    return # Back to item action menu

            # Determine cost based on updated refines_remaining
            if item_level <= 40:
                refine_costs_list = [10000, 6000, 1000] # Cost for 1, 2, 3 refines left
                cost = refine_costs_list[refines_remaining -1] if 1 <= refines_remaining <= 3 else refine_costs_list[0] # Default to highest if out of bounds
            elif 40 < item_level <= 80:
                refine_costs_list = [50000, 25000, 15000, 5000] # For 1, 2, 3, 4 refines left
                cost = refine_costs_list[refines_remaining -1] if 1 <= refines_remaining <= 4 else refine_costs_list[0]
            else: # item_level > 80
                refine_costs_list = [200000, 100000, 50000, 30000, 10000] # For 1, 2, 3, 4, 5 refines left
                cost = refine_costs_list[refines_remaining -1] if 1 <= refines_remaining <= 5 else refine_costs_list[0]
            
            refine_embed.title = f"Refining: {item_name}" # Reset title if it was "Apply Rune"
            refine_embed.description=(f"Attempt to refine **{item_name}**?\n"
                                      f"Cost: **{cost:,} GP** (You have: {player_gold:,})\n"
                                      f"Refines Remaining: **{refines_remaining}**\n"
                                      f"Stats are granted randomly based on the **weapon's level**.\n")
            
            refine_confirm_view = View(timeout=60.0)
            refine_confirm_view.add_item(Button(label="Confirm Refine", style=ButtonStyle.primary, custom_id="confirm_refine"))
            refine_confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_refine"))
            
            await message.edit(embed=refine_embed, view=refine_confirm_view)

            def refine_button_check(button_interaction: Interaction): # New check function for this scope
                return (button_interaction.user == interaction.user and 
                        button_interaction.message is not None and 
                        button_interaction.message.id == message.id)

            try:
                refine_action_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=refine_button_check)
                await refine_action_interaction.response.defer()

                if refine_action_interaction.data['custom_id'] == "cancel_refine":
                    return # Back to item action menu

                if player_gold < cost:
                    refine_embed.description += f"\n\nNot enough gold. Returning..."
                    await message.edit(embed=refine_embed, view=None)
                    await asyncio.sleep(3)
                    return # Back to item action menu

                await self.bot.database.update_user_gold(user_id, player_gold - cost) # Use specific update, not add
                
                refine_embed.description = f"The blacksmith carefully hones your weapon..."
                await message.edit(embed=refine_embed, view=None) # Show progress
                await asyncio.sleep(1) # Simulate work

                attack_roll_success = random.randint(0, 100) < 80 # 80% chance to get any attack
                defense_roll_success = random.randint(0, 100) < 50 # 50% chance to get any defense
                rarity_roll_success = random.randint(0, 100) < 20 # 20% chance to get any rarity

                attack_modifier = 0
                defense_modifier = 0
                rarity_modifier = 0
                
                # Max stat gain per refine attempt, scales with item level
                # e.g. iLvl 10 -> max_range = 1+2=3. iLvl 100 -> max_range = 10+2=12
                max_stat_gain = int(item_level / 10) + 2 
                min_stat_gain = 1 # Always gain at least 1 if the roll for the stat type is successful

                if attack_roll_success:
                    attack_modifier = random.randint(min_stat_gain, max(min_stat_gain, max_stat_gain)) # Ensure max_stat_gain >= min_stat_gain
                
                if defense_roll_success:
                    defense_modifier = random.randint(min_stat_gain, max(min_stat_gain, max_stat_gain))

                if rarity_roll_success:
                    # Rarity gain can be higher, e.g., 1 to 5 times the normal stat gain range
                    min_rarity_gain = random.randint(1, 5) 
                    max_rarity_gain = max(min_rarity_gain, max_stat_gain * 5)
                    rarity_modifier = random.randint(min_rarity_gain, max_rarity_gain)
                    await self.bot.database.increase_weapon_rarity(item_id, rarity_modifier)

                # Always increase by at least 1 if the type was rolled, otherwise 0 if type failed.
                # The problem statement implies always getting *some* atk/def, let's adjust:
                attack_modifier = random.randint(1, max(1, max_stat_gain // (2 if not attack_roll_success else 1) )) # Higher if successful roll
                defense_modifier = random.randint(1, max(1, max_stat_gain // (2 if not defense_roll_success else 1) ))


                await self.bot.database.increase_weapon_attack(item_id, attack_modifier)
                await self.bot.database.increase_weapon_defence(item_id, defense_modifier)
                await self.bot.database.update_weapon_refine_count(item_id, refines_remaining - 1)
                await self.bot.database.update_weapon_refine_lvl(item_id, 1) # Increment refinement_lvl by 1

                result_message_parts = []
                if attack_modifier > 0:
                    result_message_parts.append(f"Attack increased by **{attack_modifier}**!")
                if defense_modifier > 0:
                    result_message_parts.append(f"Defense increased by **{defense_modifier}**!")
                if rarity_modifier > 0: # This was already applied
                    result_message_parts.append(f"Rarity increased by **{rarity_modifier}**!")
                
                if not result_message_parts: # Should not happen with current logic but as fallback
                    result_message_parts.append("The weapon's properties were subtly altered.")

                refine_embed.description = ("\n".join(result_message_parts) + "\n\nItem saved.")
                await message.edit(embed=refine_embed, view=None)
                await asyncio.sleep(2)
                #return # Successfully refined, back to item action menu
                
            except asyncio.TimeoutError: # Timeout on refine confirmation buttons
                await message.edit(content="Refine confirmation timed out.", embed=None, view=None)
                await asyncio.sleep(3)
                # self.bot.state_manager.clear_active(interaction.user.id) # Let item action loop handle
                return # Back to item action menu
        # Fallthrough from while loop if something unexpected happens (should be caught by returns)
        return


async def setup(bot) -> None:
    await bot.add_cog(Weapons(bot))