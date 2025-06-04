import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import View, Button
import asyncio
import random

class Accessories(commands.Cog, name="accessories"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="accessory", 
                         description="View your character's accessories and modify them.")
    async def view_accessories(self, interaction: Interaction) -> None:
        """Fetch and display the character's accessories with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # if not await self.bot.is_maintenance(interaction, user_id):
        #     return
        
        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        accessories = await self.bot.database.fetch_user_accessories(user_id)

        if not accessories:
            await interaction.response.send_message("You check your accessory pouch, it is empty.")
            return

        player_name = existing_user[3]
        embed = discord.Embed(
            title="📿",
            description=f"{player_name}'s Accessories:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/yzQDtNg.jpeg")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")

        # Pagination setup
        items_per_page = 7
        total_pages = (len(accessories) + items_per_page - 1) // items_per_page
        current_page = 0
        original_user = interaction.user

        while True:
            accessories = await self.bot.database.fetch_user_accessories(user_id)
            total_pages = (len(accessories) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1)
            embed.description = f"{player_name}'s Accessories (Page {current_page + 1}/{total_pages}):"
            
            if not accessories:
                await interaction.followup.send("You check your accessory pouch, it is empty.")
                break

            accessories.sort(key=lambda acc: acc[3], reverse=True)
            start_idx = current_page * items_per_page
            accessories_to_display = accessories[start_idx:start_idx + items_per_page]
            embed.clear_fields()
            accessories_display_string = ""

            for index, accessory in enumerate(accessories_to_display):
                accessory_name = accessory[2]
                accessory_level = accessory[3]
                is_equipped = accessory[10]

                accessories_display_string += (
                    f"{index + 1}: "
                    f"{'[E] ' if is_equipped else ''}"
                    f"{accessory_name} (i{accessory_level})\n"
                )

            embed.add_field(
                name="Accessories:",
                value=accessories_display_string.strip(),
                inline=False
            )

            embed.add_field(
                name="Instructions",
                value=("Select an accessory to interact with.\n"
                       "Use navigation buttons to change pages or close the interface."),
                inline=False
            )

            view = View(timeout=60.0)
            for i in range(len(accessories_to_display)):
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
                        selected_accessory = accessories_to_display[selected_index]
                        selected_accessory = await self.bot.database.fetch_accessory_by_id(selected_accessory[0])
                        if not selected_accessory:
                            break
                        accessory_name = selected_accessory[2]
                        accessory_level = selected_accessory[3]
                        accessory_attack = selected_accessory[4]
                        accessory_defence = selected_accessory[5]
                        accessory_rarity = selected_accessory[6]
                        accessory_ward = selected_accessory[7]
                        accessory_crit = selected_accessory[8]
                        accessory_passive = selected_accessory[9]
                        potential_lvl = selected_accessory[12]
                        passive_effect = self.get_accessory_passive_effect(accessory_passive, potential_lvl)
                        
                        equipped_item_tuple = await self.bot.database.get_equipped_accessory(user_id) # Re-fetch for accurate equipped status
                        embed.description = f"**{accessory_name}** (Level {accessory_level}):"
                        is_equipped = equipped_item_tuple and (equipped_item_tuple[0] == selected_accessory[0])
                        if (is_equipped):
                            embed.description += "\nEquipped"
                        embed.clear_fields()
                        if accessory_attack > 0:
                            embed.add_field(name="Attack", value=accessory_attack, inline=True)
                        if accessory_defence > 0:
                            embed.add_field(name="Defense", value=accessory_defence, inline=True)
                        if accessory_rarity > 0:
                            embed.add_field(name="Rarity", value=str(accessory_rarity) + "%", inline=True)
                        if accessory_ward > 0:
                            embed.add_field(name="Ward", value=str(accessory_ward) + "%", inline=True)
                        if accessory_crit > 0:
                            embed.add_field(name="Critical Chance", value=str(accessory_crit) + "%", inline=True)

                        if accessory_passive != "none":
                            embed.add_field(name="Passive", value=accessory_passive + f" ({potential_lvl})", inline=False)
                            embed.add_field(name="Passive Description", value=passive_effect, inline=False)
                        else:
                            embed.add_field(name="Passive", value="Unlock to reveal!", inline=False)

                        potential_guide = (
                            "Select an action:\n"
                            "- Equip: Equip the accessory\n"
                            "- Unlock/Improve: Unlock or improve potential\n"
                            "- Discard: Discard accessory\n"
                            "- Back: Return to list"
                        )
                        embed.add_field(name="Accessory Guide", value=potential_guide, inline=False)

                        action_view = View(timeout=60.0)
                        action_view.add_item(Button(label="Unequip" if is_equipped else "Equip", style=ButtonStyle.primary, custom_id="unequip" if is_equipped else "equip"))
                        if selected_accessory[11] > 0:
                            action_view.add_item(Button(label="Unlock/Improve", style=ButtonStyle.primary, custom_id="improve"))
                        action_view.add_item(Button(label="Discard", style=ButtonStyle.danger, custom_id="discard"))
                        action_view.add_item(Button(label="Back", style=ButtonStyle.secondary, custom_id="back"))

                        await message.edit(embed=embed, view=action_view)

                        try:
                            action_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                            await action_interaction.response.defer()
                            if action_interaction.data['custom_id'] in ["equip", "unequip"]:
                                if action_interaction.data['custom_id'] == "equip":
                                    await self.bot.database.equip_accessory(user_id, selected_accessory[0])
                                else:  # unequip
                                    await self.bot.database.unequip_accessory(user_id)
                                continue # Re-fetch and re-display item details
                            elif action_interaction.data['custom_id'] == "improve":
                                await self.improve_potential(action_interaction, selected_accessory, message, embed)
                                continue
                            elif action_interaction.data['custom_id'] == "discard":
                                await self.discard_accessory(action_interaction, selected_accessory, message, embed)
                                continue
                            elif action_interaction.data['custom_id'] == "back":
                                break

                        except asyncio.TimeoutError:
                            await message.delete()
                            self.bot.state_manager.clear_active(user_id)
                            break
                
            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(user_id)
                break
            
        self.bot.state_manager.clear_active(user_id)

    def get_accessory_passive_effect(self, passive: str, level: int) -> str:
        passive_messages = {
            "Obliterate": f"**{level * 2}%** chance to deal double damage.",
            "Absorb": f"**{level * 10}%** chance to absorb 10% of the monster's stats and add them to your own.",
            "Prosper": f"**{level * 10}%** chance to double gold earned.",
            "Infinite Wisdom": f"**{level * 5}%** chance to double experience earned.",
            "Lucky Strikes": f"**{level * 10}%** chance to roll lucky hit chance."
        }
        return passive_messages.get(passive, "No passive effect.")

    async def discard_accessory(self, 
                               interaction: Interaction, 
                               selected_accessory: tuple, 
                               message, embed) -> None:
        """Discard an accessory."""
        accessory_id = selected_accessory[0]
        accessory_name = selected_accessory[2]
        embed = discord.Embed(
            title="Confirm Discard",
            description=f"Discard **{accessory_name}**?\n**This action cannot be undone.**",
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

            await self.bot.database.discard_accessory(accessory_id)

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)

    async def improve_potential(self, 
                               interaction: Interaction, 
                               selected_accessory: tuple, 
                               message, 
                               embed) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        while True:
            selected_accessory = await self.bot.database.fetch_accessory_by_id(selected_accessory[0])
            accessory_id = selected_accessory[0]
            accessory_name = selected_accessory[2]
            current_passive = selected_accessory[9]
            potential_remaining = selected_accessory[11]
            potential_lvl = selected_accessory[12] 
            potential_passive_list = ["Obliterate", "Absorb", "Prosper", "Infinite Wisdom", "Lucky Strikes"]
            
            if potential_remaining <= 0:
                embed.add_field(name="Error", 
                            value=f"This accessory has no potential remaining.\n"
                                    f"You cannot enhance it further.\n"
                                    f"Returning to item menu...", 
                            inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(2)
                return

            rune_of_potential_count = await self.bot.database.fetch_potential_runes(str(interaction.user.id))
            costs = [500, 1000, 2000, 3000, 4000, 5000, 10000, 25000, 50000, 100000]
            refine_cost = costs[potential_lvl]
            success_rate = max(75 - potential_lvl * 5, 30)

            title_keyword = "Unlock" if current_passive == "none" else "Enhance"
            embed = discord.Embed(
                title=f"{title_keyword} Potential Attempt",
                description=(f"{title_keyword} **{accessory_name}**'s potential? \n"
                            f"Attempts left: **{potential_remaining}** \n"
                            f"Cost: **{refine_cost:,} GP**\n"
                            f"Success Rate: **{success_rate}%**\n"),
                color=0xFFCC00
            )
            embed.set_thumbnail(url="https://i.imgur.com/Tkikr5b.jpeg")
            confirm_view = View(timeout=60.0)
            confirm_view.add_item(Button(label="Confirm", style=ButtonStyle.primary, custom_id="confirm_improve"))
            confirm_view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel_improve"))
            
            await message.edit(embed=embed, view=confirm_view)

            def check(button_interaction: Interaction):
                return (button_interaction.user == interaction.user and 
                        button_interaction.message is not None and 
                        button_interaction.message.id == message.id)

            try:
                confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                await confirm_interaction.response.defer()
                
                if confirm_interaction.data['custom_id'] == "cancel_improve":
                    return

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)
                return
            
            player_gold = await self.bot.database.fetch_user_gold(user_id, server_id)
            if player_gold < refine_cost:
                embed.add_field(name="Refining", 
                            value=f"Not enough gold!\nReturning to item menu...", 
                            inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

            await self.bot.database.update_user_gold(user_id, player_gold - refine_cost)

            if rune_of_potential_count > 0:
                embed = discord.Embed(
                    title="Use Rune of Potential?",
                    description=(f"You have **{rune_of_potential_count}** Rune(s) of Potential available.\n"
                                f"Do you want to use one to boost your success rate to **{success_rate + 25}%**?"),
                    color=0xFFCC00
                )
                embed.set_thumbnail(url="https://i.imgur.com/aeorjQG.jpg")
                rune_view = View(timeout=60.0)
                rune_view.add_item(Button(label="Use", style=ButtonStyle.primary, custom_id="confirm_rune"))
                rune_view.add_item(Button(label="Skip", style=ButtonStyle.secondary, custom_id="cancel_rune"))
                
                await message.edit(embed=embed, view=rune_view)

                try:
                    rune_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                    await rune_interaction.response.defer()

                    if rune_interaction.data['custom_id'] == "confirm_rune":
                        success_rate += 25
                        await self.bot.database.update_potential_runes(str(interaction.user.id), -1)

                except asyncio.TimeoutError:
                    await message.delete()
                    self.bot.state_manager.clear_active(interaction.user.id)
                    return

            chance_to_improve = success_rate / 100
            enhancement_success = random.random() <= chance_to_improve

            if enhancement_success:
                if potential_lvl == 0:
                    passive_choice = random.choice(potential_passive_list)
                    await self.bot.database.update_accessory_passive(accessory_id, passive_choice)
                    await self.bot.database.update_accessory_passive_lvl(accessory_id, 1)
                    success_message = (f"🎉 Success!\n"
                                    f"Your accessory has gained the **{passive_choice}** passive.")
                else:
                    new_potential = potential_lvl + 1
                    await self.bot.database.update_accessory_passive_lvl(accessory_id, new_potential)
                    success_message = (f"🎉 Success!\n"
                                    f"Upgraded **{current_passive}** from level **{potential_lvl}** to **{new_potential}**.\n")
                embed.add_field(name="Enhancement Result", value=success_message + " Returning to item menu...", inline=False)
            else:
                fail_message = "💔 The enhancement failed. Unlucky.\nReturning to item menu..."
                embed.add_field(name="Enhancement Result", value=fail_message, inline=False)

            potential_remaining -= 1
            await self.bot.database.update_accessory_potential(accessory_id, potential_remaining)
            await message.edit(embed=embed)
            await asyncio.sleep(2)
            embed.clear_fields()

async def setup(bot) -> None:
    await bot.add_cog(Accessories(bot))