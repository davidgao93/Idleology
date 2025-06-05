# cogs/boots.py
import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import View, Button
import asyncio
import random

class Boots(commands.Cog, name="boots"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.boot_passive_list = [
            "speedster", "skiller", "treasure-tracker", 
            "hearty", "cleric", "thrill-seeker"
        ] # Use hyphens for consistency if DB stores them that way

    @app_commands.command(name="boots", 
                         description="View your character's boots and modify them.")
    async def view_boots(self, interaction: Interaction) -> None:
        """Fetch and display the character's boots with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        boots_data = await self.bot.database.fetch_user_boots(user_id)

        if not boots_data:
            await interaction.response.send_message("You check your footwear, but find no special boots.")
            return

        player_name = existing_user[3]
        embed = discord.Embed(
            title="👢", # Boot emoji
            description=f"{player_name}'s Boots:",
            color=0x964B00, # Brown, for boots
        )
        # embed.set_thumbnail(url="https://i.imgur.com/your_boot_thumbnail.png")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")

        items_per_page = 7
        total_pages = (len(boots_data) + items_per_page - 1) // items_per_page
        current_page = 0
        original_user = interaction.user

        while True:
            boots_data = await self.bot.database.fetch_user_boots(user_id)
            total_pages = (len(boots_data) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1) if total_pages > 0 else 0
            
            embed.description = f"{player_name}'s Boots (Page {current_page + 1}/{max(1, total_pages)}):"
            
            if not boots_data:
                await interaction.followup.send("You check your footwear, but find no special boots.")
                if message: await message.delete()
                break

            equipped_boot_tuple = await self.bot.database.get_equipped_boot(user_id)
            sorted_boots_data = []
            if equipped_boot_tuple:
                equipped_id = equipped_boot_tuple[0]
                for boot_item_data in boots_data:
                    if boot_item_data[0] == equipped_id:
                        sorted_boots_data.append(boot_item_data)
                        break
                other_boots_data = [b for b in boots_data if b[0] != equipped_id]
            else:
                other_boots_data = list(boots_data)
            
            other_boots_data.sort(key=lambda b: b[3], reverse=True) # Sort by item_level (index 3)
            sorted_boots_data.extend(other_boots_data)

            start_idx = current_page * items_per_page
            boots_to_display = sorted_boots_data[start_idx:start_idx + items_per_page]
            embed.clear_fields()
            boots_display_string = ""

            for index, boot_item in enumerate(boots_to_display):
                b_name = boot_item[2]
                b_level = boot_item[3]
                b_passive = boot_item[9]
                b_passive_lvl = boot_item[12]
                b_is_equipped = boot_item[10]
                
                info_txt = ""
                if b_passive != "none":
                    info_txt += f" - {b_passive.replace('-', ' ').title()} {b_passive_lvl}"

                boots_display_string += (
                    f"{index + 1}: "
                    f"{'[E] ' if b_is_equipped else ''}"
                    f"{b_name} (i{b_level}{info_txt})\n"
                )

            embed.add_field(
                name="Boots:",
                value=boots_display_string.strip() if boots_display_string else "No boots on this page.",
                inline=False
            )
            embed.add_field(
                name="Instructions",
                value=("Select boots to interact with.\n"
                       "Use navigation buttons to change pages or close the interface."),
                inline=False
            )

            view = View(timeout=60.0)
            for i in range(len(boots_to_display)):
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
                    return 
                
                await button_interaction.response.defer()

                if button_interaction.data['custom_id'].startswith("item_"):
                    selected_index_on_page = int(button_interaction.data['custom_id'].split("_")[1])
                    selected_boot_id = boots_to_display[selected_index_on_page][0]
                    
                    while True: 
                        selected_boot_details = await self.bot.database.fetch_boot_by_id(selected_boot_id)
                        if not selected_boot_details:
                            await interaction.followup.send("Selected boots no longer exist.", ephemeral=True)
                            break 

                        b_name = selected_boot_details[2]
                        b_level = selected_boot_details[3]
                        b_attack = selected_boot_details[4]
                        b_defence = selected_boot_details[5]
                        b_ward = selected_boot_details[6]
                        b_pdr = selected_boot_details[7]
                        b_fdr = selected_boot_details[8]
                        b_passive = selected_boot_details[9]
                        b_is_equipped = selected_boot_details[10]
                        b_potential_rem = selected_boot_details[11] # Schema: default 6
                        b_passive_lvl = selected_boot_details[12]
                        
                        passive_effect_desc = self.get_boot_passive_effect(b_passive, b_passive_lvl)
                        
                        item_embed = discord.Embed(
                            title=f"👢 {b_name} (i{b_level})",
                            description="Equipped" if b_is_equipped else "Unequipped",
                            color=0x8B4513 # SaddleBrown
                        )
                        if b_attack > 0: item_embed.add_field(name="Attack", value=b_attack, inline=True)
                        if b_defence > 0: item_embed.add_field(name="Defence", value=b_defence, inline=True)
                        if b_ward > 0: item_embed.add_field(name="Ward", value=f"{b_ward}%", inline=True)
                        if b_pdr > 0: item_embed.add_field(name="PDR", value=f"{b_pdr}%", inline=True)
                        if b_fdr > 0: item_embed.add_field(name="FDR", value=b_fdr, inline=True)

                        if b_passive != "none":
                            item_embed.add_field(name="Passive", value=f"{b_passive.replace('-', ' ').title()} (Lvl {b_passive_lvl})", inline=False)
                            item_embed.add_field(name="Effect", value=passive_effect_desc, inline=False)
                        else:
                            item_embed.add_field(name="Passive", value="Unlock to reveal!", inline=False)

                        guide_text = ("Select an action:\n"
                                      f"- {'Unequip' if b_is_equipped else 'Equip'}\n"
                                      "- Unlock/Improve Potential\n- Send\n- Discard\n- Back to list")
                        item_embed.add_field(name="Actions", value=guide_text, inline=False)

                        action_view = View(timeout=60.0)
                        action_view.add_item(Button(label="Unequip" if b_is_equipped else "Equip", style=ButtonStyle.primary, custom_id="equip_unequip"))
                        if b_potential_rem > 0 and b_passive_lvl < 6: # Max passive level 6 for boots
                            action_view.add_item(Button(label="Improve Potential", style=ButtonStyle.success, custom_id="improve"))
                        action_view.add_item(Button(label="Send", style=ButtonStyle.secondary, custom_id="send"))
                        action_view.add_item(Button(label="Discard", style=ButtonStyle.danger, custom_id="discard"))
                        action_view.add_item(Button(label="Back", style=ButtonStyle.grey, custom_id="back"))

                        await message.edit(embed=item_embed, view=action_view)

                        try:
                            item_action_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                            await item_action_interaction.response.defer()

                            if item_action_interaction.data['custom_id'] == "equip_unequip":
                                if b_is_equipped: await self.bot.database.unequip_boot(user_id)
                                else: await self.bot.database.equip_boot(user_id, selected_boot_id)
                                continue 
                            elif item_action_interaction.data['custom_id'] == "improve":
                                await self.improve_boot_potential(item_action_interaction, selected_boot_details, message)
                                continue 
                            elif item_action_interaction.data['custom_id'] == "send":
                                if b_is_equipped:
                                    error_embed = item_embed.copy()
                                    error_embed.add_field(name="Error", value="Unequip the boots before sending. Returning...", inline=False)
                                    await message.edit(embed=error_embed, view=None)
                                    await asyncio.sleep(3)
                                    continue
                                await self.send_boot_interaction(item_action_interaction, selected_boot_details, message, item_embed)
                                test_boot = await self.bot.database.fetch_boot_by_id(selected_boot_id)
                                if not test_boot or test_boot[1] != user_id: break 
                                continue 
                            elif item_action_interaction.data['custom_id'] == "discard":
                                discarded = await self.discard_boot_interaction(item_action_interaction, selected_boot_details, message, item_embed)
                                if discarded: break 
                                continue 
                            elif item_action_interaction.data['custom_id'] == "back":
                                break 
                        except asyncio.TimeoutError:
                            await message.delete()
                            self.bot.state_manager.clear_active(user_id)
                            return 
                continue
            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(user_id)
                break 
        self.bot.state_manager.clear_active(user_id)

    def get_boot_passive_effect(self, passive_name: str, level: int) -> str:
        if level == 0: return "Unlock to reveal its true power."
        
        effects = {
            "speedster": f"Combat cooldown reduced by **{level * 20}** seconds.",
            "skiller": f"Grants **{level * 5}%** chance to find extra skill materials on victory.",
            "treasure-tracker": f"Treasure mob chance increased by **{level * 0.5}%**.",
            "hearty": f"Increases maximum HP by **{level * 5}%**.",
            "cleric": f"Potions heal for an additional **{level * 10}%** of their base amount.",
            "thrill-seeker": f"Increases chance for special drops (keys, runes) by **{level * 1}%**."
        }
        return effects.get(passive_name, "Unknown passive effect.")

    async def improve_boot_potential(self, 
                               interaction: Interaction, 
                               selected_boot: tuple, 
                               message: Message) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        boot_id = selected_boot[0]
        boot_name = selected_boot[2]
        current_passive = selected_boot[9]
        potential_remaining = selected_boot[11] # Default 6 for boots
        current_passive_lvl = selected_boot[12]

        if potential_remaining <= 0:
            embed = discord.Embed(title="Error", description=f"**{boot_name}** has no potential remaining.", color=discord.Color.red())
            await message.edit(embed=embed, view=None); await asyncio.sleep(3); return

        if current_passive_lvl >= 6: # Max potential level 6 for boots
            embed = discord.Embed(title="Max Potential", description=f"**{boot_name}** is already at its maximum potential (Lvl 6).", color=discord.Color.gold())
            await message.edit(embed=embed, view=None); await asyncio.sleep(3); return

        # Costs for levels 0->1, 1->2, ..., 5->6
        costs_for_boots = [500, 1000, 2000, 3000, 4000, 6000] # Added a 6th tier
        improvement_cost = costs_for_boots[current_passive_lvl]
        
        success_rate_percent = max(75 - current_passive_lvl * 5, 25) # Keep floor at 25% for L5->L6 (50%)

        title_keyword = "Unlock" if current_passive == "none" else "Enhance"
        confirm_embed = discord.Embed(
            title=f"{title_keyword} Boot Potential",
            description=(f"Attempt to {title_keyword.lower()} **{boot_name}**'s potential?\n"
                         f"Current Passive Level: {current_passive_lvl}\n"
                         f"Attempts left: **{potential_remaining}**\n"
                         f"Cost: **{improvement_cost:,} GP**\n"
                         f"Success Rate: **{success_rate_percent}%**"),
            color=0xFFCC00 
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
            if confirm_interaction.data['custom_id'] == "cancel_improve":
                await confirm_interaction.response.defer(); return 
            await confirm_interaction.response.defer()

            player_gold = await self.bot.database.fetch_user_gold(user_id, server_id)
            if player_gold < improvement_cost:
                result_embed = discord.Embed(title="Improvement Failed", description="Not enough gold!", color=discord.Color.red())
                await message.edit(embed=result_embed, view=None); await asyncio.sleep(3); return

            await self.bot.database.update_user_gold(user_id, player_gold - improvement_cost)
            
            enhancement_success = random.random() <= (success_rate_percent / 100.0)
            new_passive_lvl = current_passive_lvl
            new_passive_name = current_passive
            result_title, result_description = "", ""

            if enhancement_success:
                new_passive_lvl += 1
                if current_passive == "none": 
                    new_passive_name = random.choice(self.boot_passive_list)
                    await self.bot.database.update_boot_passive(boot_id, new_passive_name)
                    result_title, result_description = "Potential Unlocked! 🎉", f"**{boot_name}** gained **{new_passive_name.replace('-', ' ').title()}** (Lvl {new_passive_lvl})!"
                else: 
                    result_title, result_description = "Potential Enhanced! ✨", f"**{boot_name}**'s **{new_passive_name.replace('-', ' ').title()}** passive improved to Lvl {new_passive_lvl}!"
                await self.bot.database.update_boot_passive_lvl(boot_id, new_passive_lvl)
            else:
                result_title, result_description = "Enhancement Failed 💔", "The attempt was unsuccessful."

            await self.bot.database.update_boot_potential_remaining(boot_id, potential_remaining - 1)
            final_embed = discord.Embed(title=result_title, description=result_description, color=discord.Color.green() if enhancement_success else discord.Color.orange())
            await message.edit(embed=final_embed, view=None); await asyncio.sleep(4)
        except asyncio.TimeoutError:
            await message.edit(content="Improvement confirmation timed out.", embed=None, view=None); await asyncio.sleep(3)

    async def discard_boot_interaction(self, interaction: Interaction, selected_boot: tuple, message: Message, original_embed: discord.Embed) -> bool:
        boot_id, _, boot_name, *_ = selected_boot
        confirm_embed = discord.Embed(title="Confirm Discard", description=f"Discard **{boot_name}**?\n**This action cannot be undone.**", color=discord.Color.red())
        confirm_view = View(timeout=60.0)
        confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.danger, custom_id="confirm_discard_final"))
        confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_discard_final"))
        await message.edit(embed=confirm_embed, view=confirm_view)
        def check(bi: Interaction): return bi.user == interaction.user and bi.message.id == message.id
        try:
            final_confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
            if final_confirm_interaction.data['custom_id'] == "confirm_discard_final":
                await final_confirm_interaction.response.defer()
                await self.bot.database.discard_boot(boot_id); return True
            else: await final_confirm_interaction.response.defer(); return False
        except asyncio.TimeoutError:
            await message.edit(content="Discard confirmation timed out.", embed=None, view=None); await asyncio.sleep(3); return False

    async def send_boot_interaction(self, interaction: Interaction, selected_boot: tuple, message: Message, original_embed: discord.Embed) -> None:
        user_id, server_id = str(interaction.user.id), str(interaction.guild.id)
        boot_id, _, boot_name, boot_level, *_ = selected_boot
        temp_send_embed = original_embed.copy(); temp_send_embed.clear_fields()
        temp_send_embed.title, temp_send_embed.description = f"Send Boots: {boot_name}", "Mention user (@username) to send boots to."
        await message.edit(embed=temp_send_embed, view=None)
        def msg_check(m: Message): return m.author == interaction.user and m.channel == interaction.channel and m.mentions
        try:
            user_msg = await self.bot.wait_for('message', timeout=60.0, check=msg_check)
            await user_msg.delete(); receiver = user_msg.mentions[0]
            send_flag, errors = True, []
            receiver_db = await self.bot.database.fetch_user(str(receiver.id), server_id)
            if not receiver_db: send_flag, errors = False, errors + ["Recipient not registered."]
            if str(receiver.id) == user_id: send_flag, errors = False, errors + ["Cannot send to yourself."]
            if receiver_db:
                if (boot_level - receiver_db[4]) > 15: send_flag, errors = False, errors + ["Item iLvl too high for recipient (>15)."]
                if await self.bot.database.count_user_boots(str(receiver.id)) >= 58: send_flag, errors = False, errors + [f"{receiver.mention}'s boot bag is full."]
            if not send_flag:
                err_disp_embed = original_embed.copy(); err_disp_embed.add_field(name="Send Error", value="\n".join(errors) + "\nReturning...", inline=False)
                await message.edit(embed=err_disp_embed, view=None); await asyncio.sleep(4); return
            confirm_send_embed = discord.Embed(title="Confirm Send Boots", description=f"Send **{boot_name}** to {receiver.mention}?", color=discord.Color.blue())
            confirm_send_view = View(timeout=60.0)
            confirm_send_view.add_item(Button(label="Confirm Send", style=ButtonStyle.primary, custom_id="csf"))
            confirm_send_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="can_sf"))
            await message.edit(embed=confirm_send_embed, view=confirm_send_view)
            def final_send_check(bi: Interaction): return bi.user == interaction.user and bi.message.id == message.id
            try:
                final_send_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=final_send_check)
                if final_send_interaction.data['custom_id'] == "csf":
                    await final_send_interaction.response.defer()
                    await self.bot.database.send_boot(str(receiver.id), boot_id)
                    sent_embed = discord.Embed(title="Boots Sent! 👢", description=f"**{boot_name}** sent to {receiver.mention}!", color=discord.Color.green())
                    await message.edit(embed=sent_embed, view=None); await asyncio.sleep(3)
                else: await final_send_interaction.response.defer()
            except asyncio.TimeoutError: await message.edit(content="Send confirmation timed out.", embed=None, view=None); await asyncio.sleep(3)
        except asyncio.TimeoutError: await message.edit(content="Send boots timed out (waiting for mention).", embed=None, view=None); await asyncio.sleep(3)

async def setup(bot) -> None:
    await bot.add_cog(Boots(bot))