import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import View, Button
import asyncio
import random

class Gloves(commands.Cog, name="gloves"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.glove_passive_list = [
            "ward-touched", "ward-fused", "instability", 
            "deftness", "adroit", "equilibrium", "plundering"
        ]

    @app_commands.command(name="gloves", 
                         description="View your character's gloves and modify them.")
    async def view_gloves(self, interaction: Interaction) -> None:
        """Fetch and display the character's gloves with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        gloves_data = await self.bot.database.fetch_user_gloves(user_id)

        if not gloves_data:
            await interaction.response.send_message("You search your gear for gloves, but find none.")
            return

        player_name = existing_user[3]
        embed = discord.Embed(
            title="🧤", # Glove emoji
            description=f"{player_name}'s Gloves:",
            color=0x00FF00, # Green, can be changed
        )
        # You can set a thumbnail if you have one, e.g.:
        # embed.set_thumbnail(url="https://i.imgur.com/your_glove_thumbnail.png")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")

        items_per_page = 7
        total_pages = (len(gloves_data) + items_per_page - 1) // items_per_page
        current_page = 0
        original_user = interaction.user

        while True:
            gloves_data = await self.bot.database.fetch_user_gloves(user_id)
            total_pages = (len(gloves_data) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1) if total_pages > 0 else 0
            
            embed.description = f"{player_name}'s Gloves (Page {current_page + 1}/{max(1, total_pages)}):"
            
            if not gloves_data:
                await interaction.followup.send("You search your gear for gloves, but find none.")
                if message: await message.delete()
                break

            # Sort: equipped first, then by level
            equipped_glove_tuple = await self.bot.database.get_equipped_glove(user_id)
            sorted_gloves = []
            if equipped_glove_tuple:
                equipped_id = equipped_glove_tuple[0]
                for glove_item in gloves_data:
                    if glove_item[0] == equipped_id:
                        sorted_gloves.append(glove_item)
                        break
                other_gloves = [g for g in gloves_data if g[0] != equipped_id]
            else:
                other_gloves = list(gloves_data)
            
            other_gloves.sort(key=lambda g: g[3], reverse=True) # Sort by item_level (index 3)
            sorted_gloves.extend(other_gloves)


            start_idx = current_page * items_per_page
            gloves_to_display = sorted_gloves[start_idx:start_idx + items_per_page]
            embed.clear_fields()
            gloves_display_string = ""

            for index, glove_item in enumerate(gloves_to_display):
                # item_id, user_id, item_name, item_level, attack, defence, ward, pdr, fdr, passive, is_equipped, potential_remaining, passive_lvl
                glove_name = glove_item[2]
                glove_level = glove_item[3]
                glove_passive = glove_item[9]
                glove_passive_lvl = glove_item[12]
                is_equipped = glove_item[10]
                
                info_txt = ""
                if glove_passive != "none":
                    info_txt += f" - {glove_passive.replace('-', ' ').title()} {glove_passive_lvl}"

                gloves_display_string += (
                    f"{index + 1}: "
                    f"{'[E] ' if is_equipped else ''}"
                    f"{glove_name} (i{glove_level}{info_txt})\n"
                )

            embed.add_field(
                name="Gloves:",
                value=gloves_display_string.strip() if gloves_display_string else "No gloves on this page.",
                inline=False
            )

            embed.add_field(
                name="Instructions",
                value=("Select gloves to interact with.\n"
                       "Use navigation buttons to change pages or close the interface."),
                inline=False
            )

            view = View(timeout=60.0)
            for i in range(len(gloves_to_display)):
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
                elif button_interaction.data['custom_id'] == "next" and current_page < total_pages - 1:
                    current_page += 1
                elif button_interaction.data['custom_id'] == "close":
                    await message.delete()
                    self.bot.state_manager.clear_active(user_id)
                    return # Exit completely
                
                await button_interaction.response.defer() # Defer after page changes or before item action

                if button_interaction.data['custom_id'].startswith("item_"):
                    selected_index_on_page = int(button_interaction.data['custom_id'].split("_")[1])
                    
                    # Inner loop for selected glove actions
                    selected_glove_id = gloves_to_display[selected_index_on_page][0]
                    while True: 
                        # Re-fetch glove each time for up-to-date info
                        selected_glove_details = await self.bot.database.fetch_glove_by_id(selected_glove_id)
                        if not selected_glove_details:
                            await interaction.followup.send("Selected gloves no longer exist.", ephemeral=True)
                            break # Break from item action loop, go to main list loop

                        # Unpack glove details
                        # item_id (0), user_id (1), item_name (2), item_level (3), attack (4), defence (5), 
                        # ward (6), pdr (7), fdr (8), passive (9), is_equipped (10), 
                        # potential_remaining (11), passive_lvl (12)
                        g_name = selected_glove_details[2]
                        g_level = selected_glove_details[3]
                        g_attack = selected_glove_details[4]
                        g_defence = selected_glove_details[5]
                        g_ward = selected_glove_details[6]
                        g_pdr = selected_glove_details[7]
                        g_fdr = selected_glove_details[8]
                        g_passive = selected_glove_details[9]
                        g_is_equipped = selected_glove_details[10]
                        g_potential_rem = selected_glove_details[11]
                        g_passive_lvl = selected_glove_details[12]
                        
                        passive_effect_desc = self.get_glove_passive_effect(g_passive, g_passive_lvl)
                        
                        item_embed = discord.Embed(
                            title=f"🧤 {g_name} (i{g_level})",
                            description="Equipped" if g_is_equipped else "Unequipped",
                            color=0x00FFFF # Cyan, can be changed
                        )
                        if g_attack > 0: item_embed.add_field(name="Attack", value=g_attack, inline=True)
                        if g_defence > 0: item_embed.add_field(name="Defence", value=g_defence, inline=True)
                        if g_ward > 0: item_embed.add_field(name="Ward", value=f"{g_ward}%", inline=True)
                        if g_pdr > 0: item_embed.add_field(name="Percent Damage Reduction", value=f"{g_pdr}%", inline=True)
                        if g_fdr > 0: item_embed.add_field(name="Flat Damage Reduction", value=g_fdr, inline=True)

                        if g_passive != "none":
                            item_embed.add_field(name="Passive", value=f"{g_passive.replace('-', ' ').title()} (Lvl {g_passive_lvl})", inline=False)
                            item_embed.add_field(name="Effect", value=passive_effect_desc, inline=False)
                        else:
                            item_embed.add_field(name="Passive", value="Unlock to reveal!", inline=False)

                        guide_text = (
                            "Select an action:\n"
                            f"- {'Unequip' if g_is_equipped else 'Equip'}\n"
                            "- Unlock/Improve Potential\n"
                            "- Send\n"
                            "- Discard\n"
                            "- Back to list"
                        )
                        item_embed.add_field(name="Actions", value=guide_text, inline=False)

                        action_view = View(timeout=60.0)
                        action_view.add_item(Button(label="Unequip" if g_is_equipped else "Equip", style=ButtonStyle.primary, custom_id="equip_unequip"))
                        if g_potential_rem > 0:
                            action_view.add_item(Button(label="Improve Potential", style=ButtonStyle.success, custom_id="improve"))
                        action_view.add_item(Button(label="Send", style=ButtonStyle.secondary, custom_id="send"))
                        action_view.add_item(Button(label="Discard", style=ButtonStyle.danger, custom_id="discard"))
                        action_view.add_item(Button(label="Back", style=ButtonStyle.grey, custom_id="back"))

                        await message.edit(embed=item_embed, view=action_view)

                        try:
                            item_action_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                            await item_action_interaction.response.defer()

                            if item_action_interaction.data['custom_id'] == "equip_unequip":
                                if g_is_equipped:
                                    await self.bot.database.unequip_glove(user_id)
                                else:
                                    await self.bot.database.equip_glove(user_id, selected_glove_id)
                                continue # Re-render selected glove view
                            elif item_action_interaction.data['custom_id'] == "improve":
                                await self.improve_potential(item_action_interaction, selected_glove_details, message)
                                continue # Re-render
                            elif item_action_interaction.data['custom_id'] == "send":
                                if g_is_equipped:
                                    error_embed = item_embed.copy()
                                    error_embed.add_field(name="Error", value="Unequip the gloves before sending. Returning...", inline=False)
                                    await message.edit(embed=error_embed, view=None)
                                    await asyncio.sleep(3)
                                    continue
                                await self.send_glove_interaction(item_action_interaction, selected_glove_details, message, item_embed)
                                # send_glove_interaction will handle if item is sent (break) or cancelled (continue)
                                # For simplicity, we assume it handles the message and loop control.
                                # If it returns control, we re-fetch item to see if it's still there.
                                test_glove = await self.bot.database.fetch_glove_by_id(selected_glove_id)
                                if not test_glove or test_glove[1] != user_id: # Glove sent or gone
                                    break # Break from item action loop
                                continue # Glove still here, re-render
                            elif item_action_interaction.data['custom_id'] == "discard":
                                discarded = await self.discard_glove_interaction(item_action_interaction, selected_glove_details, message, item_embed)
                                if discarded:
                                    break # Break from item action loop
                                continue # Discard cancelled, re-render
                            elif item_action_interaction.data['custom_id'] == "back":
                                break # Break from item action loop, go back to list

                        except asyncio.TimeoutError:
                            await message.delete()
                            self.bot.state_manager.clear_active(user_id)
                            return # Exit command
                # After item action loop breaks (due to "back", or item gone), continue to main list loop
                continue
            
            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(user_id)
                break # Exit main pagination loop
            
        self.bot.state_manager.clear_active(user_id)


    def get_glove_passive_effect(self, passive_name: str, level: int) -> str:
        if level == 0: # Not yet improved
            return "Unlock to reveal its true power."
        if passive_name == "ward-touched":
            return f"Generate **{level * 1}%** of your hit damage as Ward."
        elif passive_name == "ward-fused":
            return f"Generate **{level * 2}%** of your critical hit damage as Ward."
        elif passive_name == "instability":
            return f"All hits deal either 50% or **{150 + (level * 10)}%** of normal damage."
        elif passive_name == "deftness":
            return f"Raises the damage floor of critical hits by **{level * 5}%** (max 75% total at L5)."
        elif passive_name == "adroit":
            return f"Raises the damage floor of normal hits by **{level * 2}%**."
        elif passive_name == "equilibrium":
            return f"Gain **{level * 5}%** of hit damage as bonus Experience."
        elif passive_name == "plundering":
            return f"Gain **{level * 10}%** of hit damage as bonus Gold."
        return "Unknown passive effect."

    async def improve_potential(self, 
                               interaction: Interaction, 
                               selected_glove: tuple, # Full glove tuple from DB
                               message: Message) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        # Unpack selected_glove for clarity
        glove_id = selected_glove[0]
        glove_name = selected_glove[2]
        current_passive = selected_glove[9]
        potential_remaining = selected_glove[11]
        current_passive_lvl = selected_glove[12]

        if potential_remaining <= 0:
            embed = discord.Embed(title="Error", description=f"**{glove_name}** has no potential remaining.", color=discord.Color.red())
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(3)
            return

        if current_passive_lvl >= 5: # Max potential level is 5
            embed = discord.Embed(title="Max Potential", description=f"**{glove_name}** is already at its maximum potential (Lvl 5).", color=discord.Color.gold())
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(3)
            return

        # Costs: 500, 1000, 2000, 3000, 4000 (for levels 0->1, 1->2, 2->3, 3->4, 4->5)
        costs_for_glove = [500, 2000, 5000, 10000, 20000]
        if current_passive_lvl >= len(costs_for_glove): # Should be caught by max level check above
             embed = discord.Embed(title="Error", description="Cost calculation error for potential.", color=discord.Color.red())
             await message.edit(embed=embed, view=None)
             await asyncio.sleep(3)
             return
        
        improvement_cost = costs_for_glove[current_passive_lvl]
        
        # Success Rate: max(75 - current_passive_lvl * 5, 30)
        # L0->1: 75% | L1->2: 70% | L2->3: 65% | L3->4: 60% | L4->5: 55%
        success_rate_percent = max(75 - current_passive_lvl * 5, 30)

        title_keyword = "Unlock" if current_passive == "none" else "Enhance"
        confirm_embed = discord.Embed(
            title=f"{title_keyword} Potential",
            description=(f"Attempt to {title_keyword.lower()} **{glove_name}**'s potential?\n"
                         f"Current Passive Level: {current_passive_lvl}\n"
                         f"Attempts left: **{potential_remaining}**\n"
                         f"Cost: **{improvement_cost:,} GP**\n"
                         f"Success Rate: **{success_rate_percent}%**"),
            color=0xFFCC00 # Gold/Yellow
        )
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_improve"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_improve"))
        
        await message.edit(embed=confirm_embed, view=confirm_view)

        def check(button_interaction: Interaction):
            return (button_interaction.user == interaction.user and 
                    button_interaction.message is not None and 
                    button_interaction.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
            # No defer here, done by caller or after DB ops
            
            if confirm_interaction.data['custom_id'] == "cancel_improve":
                await confirm_interaction.response.defer() # Defer if cancelling
                return # Back to selected glove view

            # Defer before DB operations
            await confirm_interaction.response.defer()

            player_gold = await self.bot.database.fetch_user_gold(user_id, server_id)
            if player_gold < improvement_cost:
                result_embed = discord.Embed(title="Improvement Failed", description="Not enough gold!", color=discord.Color.red())
                await message.edit(embed=result_embed, view=None)
                await asyncio.sleep(3)
                return

            await self.bot.database.update_user_gold(user_id, player_gold - improvement_cost)
            
            # No rune usage for gloves
            enhancement_success = random.random() <= (success_rate_percent / 100.0)
            new_passive_lvl = current_passive_lvl
            new_passive_name = current_passive

            result_title = ""
            result_description = ""

            if enhancement_success:
                new_passive_lvl += 1
                if current_passive == "none": # First successful improvement
                    new_passive_name = random.choice(self.glove_passive_list)
                    await self.bot.database.update_glove_passive(glove_id, new_passive_name)
                    result_title = "Potential Unlocked! 🎉"
                    result_description = (f"**{glove_name}** has gained the **{new_passive_name.replace('-', ' ').title()}** passive (Lvl {new_passive_lvl})!")
                else: # Improving existing passive
                    result_title = "Potential Enhanced! ✨"
                    result_description = (f"**{glove_name}**'s **{new_passive_name.replace('-', ' ').title()}** passive improved to Lvl {new_passive_lvl}!")
                
                await self.bot.database.update_glove_passive_lvl(glove_id, new_passive_lvl)
            else:
                result_title = "Enhancement Failed 💔"
                result_description = "The attempt to improve potential was unsuccessful. Better luck next time!"

            await self.bot.database.update_glove_potential_remaining(glove_id, potential_remaining - 1)
            
            final_embed = discord.Embed(title=result_title, description=result_description, color=discord.Color.green() if enhancement_success else discord.Color.orange())
            await message.edit(embed=final_embed, view=None)
            await asyncio.sleep(4)

        except asyncio.TimeoutError:
            await message.edit(content="Improvement confirmation timed out.", embed=None, view=None)
            await asyncio.sleep(3)
            # self.bot.state_manager.clear_active(interaction.user.id) # Let outer loop handle

    async def discard_glove_interaction(self, 
                           interaction: Interaction, 
                           selected_glove: tuple, 
                           message: Message,
                           original_embed: discord.Embed) -> bool: # True if discarded
        """Handle glove discard confirmation."""
        glove_id = selected_glove[0]
        glove_name = selected_glove[2]
        
        confirm_embed = discord.Embed(
            title="Confirm Discard",
            description=f"Discard **{glove_name}**?\n**This action cannot be undone.**",
            color=discord.Color.red(),
        )
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.danger, custom_id="confirm_discard_final"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_discard_final"))
        
        await message.edit(embed=confirm_embed, view=confirm_view)

        def check(button_interaction: Interaction):
            return (button_interaction.user == interaction.user and 
                    button_interaction.message is not None and 
                    button_interaction.message.id == message.id)

        try:
            final_confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
            # No defer here, done by caller or after DB op
            
            if final_confirm_interaction.data['custom_id'] == "confirm_discard_final":
                await final_confirm_interaction.response.defer() # Defer before DB
                await self.bot.database.discard_glove(glove_id)
                # Message will be updated by the main loop re-rendering the list
                return True 
            else: # Cancelled
                await final_confirm_interaction.response.defer()
                return False

        except asyncio.TimeoutError:
            await message.edit(content="Discard confirmation timed out.", embed=None, view=None)
            await asyncio.sleep(3)
            return False # Not discarded

    async def send_glove_interaction(self,
                                interaction: Interaction, 
                                selected_glove: tuple, 
                                message: Message,
                                original_embed: discord.Embed) -> None: # Returns None, loop control handled by caller
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        glove_id = selected_glove[0]
        glove_name = selected_glove[2]
        glove_level = selected_glove[3]

        temp_send_embed = original_embed.copy()
        temp_send_embed.clear_fields() # Clear original fields
        temp_send_embed.title = f"Send Gloves: {glove_name}"
        temp_send_embed.description = "Please mention the user (@username) to send the gloves to."
        await message.edit(embed=temp_send_embed, view=None)
        
        def message_check(m: Message):
            return (m.author == interaction.user and 
                    m.channel == interaction.channel and 
                    m.mentions)
        
        try:
            user_message = await self.bot.wait_for('message', timeout=60.0, check=message_check)
            await user_message.delete() # Delete the @mention message
            receiver = user_message.mentions[0]
            
            send_item_flag = True
            receiver_user_db = await self.bot.database.fetch_user(str(receiver.id), server_id)
            error_messages_send = []

            if not receiver_user_db:
                send_item_flag = False
                error_messages_send.append("Recipient is not a registered adventurer.")
            if str(receiver.id) == user_id:
                send_item_flag = False
                error_messages_send.append("You cannot send items to yourself.")
            
            if receiver_user_db: # Only check level and inventory if receiver is valid
                receiver_level = receiver_user_db[4] # Assuming level is at index 4
                if (glove_level - receiver_level) > 15:
                    send_item_flag = False
                    error_messages_send.append("Item iLvl difference is too great (> 15 levels above recipient).")
                
                receiver_glove_count = await self.bot.database.count_user_gloves(str(receiver.id))
                # Assuming max inventory slots, e.g., 58 (consistent with accessories example)
                if receiver_glove_count >= 58: 
                    send_item_flag = False
                    error_messages_send.append(f"{receiver.mention}'s glove pouch is full.")

            if not send_item_flag:
                err_summary = "\n".join(error_messages_send)
                error_display_embed = original_embed.copy()
                error_display_embed.add_field(name="Send Error", value=f"{err_summary}\nReturning...", inline=False)
                await message.edit(embed=error_display_embed, view=None)
                await asyncio.sleep(4)
                return # Return to selected glove view

            # Proceed to confirmation
            confirm_send_embed = discord.Embed(
                title="Confirm Send Gloves",
                description=f"Send **{glove_name}** to {receiver.mention}?",
                color=discord.Color.blue()
            )
            confirm_send_view = View(timeout=60.0)
            confirm_send_view.add_item(Button(label="Confirm Send", style=ButtonStyle.primary, custom_id="confirm_send_final"))
            confirm_send_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_send_final"))
            
            await message.edit(embed=confirm_send_embed, view=confirm_send_view)
            
            def final_send_check(btn_interaction: Interaction):
                return (btn_interaction.user == interaction.user and 
                        btn_interaction.message is not None and 
                        btn_interaction.message.id == message.id)

            try:
                final_send_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=final_send_check)
                # No defer here, done by caller or after DB
                
                if final_send_interaction.data['custom_id'] == "confirm_send_final":
                    await final_send_interaction.response.defer() # Defer before DB
                    await self.bot.database.send_glove(str(receiver.id), glove_id)
                    sent_embed = discord.Embed(title="Gloves Sent! 🧤", description=f"**{glove_name}** successfully sent to {receiver.mention}!", color=discord.Color.green())
                    await message.edit(embed=sent_embed, view=None)
                    await asyncio.sleep(3)
                    # Caller loop will break because item is gone from user
                else: # Cancelled final send
                    await final_send_interaction.response.defer()
                    # Return to selected glove view (handled by caller loop)
            
            except asyncio.TimeoutError:
                await message.edit(content="Send confirmation timed out.", embed=None, view=None)
                await asyncio.sleep(3)
                # Return to selected glove view (handled by caller loop)
        
        except asyncio.TimeoutError:
            await message.edit(content="Send gloves timed out while waiting for user mention.", embed=None, view=None)
            await asyncio.sleep(3)
            # Return to selected glove view (handled by caller loop)


async def setup(bot) -> None:
    await bot.add_cog(Gloves(bot))