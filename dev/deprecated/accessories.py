import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message
import asyncio
import random

class Accessories(commands.Cog, name="accessories"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="accessory", 
                            description="View your character's accessories and modify them.")
    async def accessory(self, interaction: Interaction) -> None:
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
            title=f"📿",
            description=f"{player_name}'s Accessories:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/yzQDtNg.jpeg") # accessory pouch
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")  # Set inventory as active operation

        # Pagination setup
        items_per_page = 5
        total_pages = (len(accessories) + items_per_page - 1) // items_per_page  # Ceiling division
        current_page = 0
        number_emojis = ["❌", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        while True:
            accessories = await self.bot.database.fetch_user_accessories(user_id)
            total_pages = (len(accessories) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1)  # Ensure current_page is valid
            embed.description = f"{player_name}'s Accessories (Page {current_page + 1}/{total_pages}):"
            
            if not accessories:
                await interaction.followup.send("You check your accessory pouch, it is empty.")
                break

            accessories.sort(key=lambda acc: acc[3], reverse=True)  # Sort by item_level at index 3
            start_idx = current_page * items_per_page
            accessories_to_display = accessories[start_idx:start_idx + items_per_page]
            await message.clear_reactions()
            embed.clear_fields()
            accessories_display_string = ""

            for index, accessory in enumerate(accessories_to_display):
                accessory_name = accessory[2]  # item_name is at index 2
                accessory_level = accessory[3]  # item_level is at index 3
                is_equipped = accessory[10]  # is_equipped is at index 10

                # Append accessory details to the display string
                accessories_display_string += (
                    f"{number_emojis[index + 1]}: "
                    f"{'[E] ' if is_equipped else ''}"
                    f"{accessory_name} (i{accessory_level})\n"
                )

            # Add a single field for all accessories
            embed.add_field(
                name="Accessories:",
                value=accessories_display_string.strip(),
                inline=False
            )

            # Instructions for user
            embed.add_field(
                name="Instructions",
                value=(f"[ℹ️] Select an accessory to interact with.\n"
                       f"[◀️] Previous page | [▶️] Next page | [❌] Close interface."),
                inline=False
            )
            await message.edit(embed=embed)

            # Add reactions: number emojis for items, navigation, and exit
            for i in range(len(accessories_to_display) + 1):
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
                        selected_accessory = accessories_to_display[selected_index]
                        print(f'Fetching {selected_accessory} from db again for refresh')
                        selected_accessory = await self.bot.database.fetch_accessory_by_id(selected_accessory[0])
                        if not selected_accessory:
                            break
                        # Display selected accessory details
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

                        embed.description = f"**{accessory_name}** (Level {accessory_level}):"
                        embed.clear_fields()
                        if accessory_attack > 0:
                            embed.add_field(name="Attack", value=accessory_attack, inline=True)
                        elif accessory_defence > 0:
                            embed.add_field(name="Defense", value=accessory_defence, inline=True)
                        elif accessory_rarity > 0:
                            embed.add_field(name="Rarity", value=accessory_rarity, inline=True)
                        elif accessory_ward > 0:
                            embed.add_field(name="Ward", value=accessory_ward, inline=True)
                        elif accessory_crit > 0:
                            embed.add_field(name="Critical Chance", value=accessory_crit, inline=True)

                        if accessory_passive != "none":
                            embed.add_field(name="Passive", value=accessory_passive + f" ({potential_lvl})", inline=False)
                            embed.add_field(name="Passive Description", value=passive_effect, inline=False)
                        else:
                            embed.add_field(name="Passive", value="🪄 to unlock!", inline=False)

                        potential_guide = (
                            "💎 to equip.\n"
                            "🪄 to unlock/improve potential.\n"
                            "🗑️ to discard.\n"
                            "◀️ to go back."
                        )
                        embed.add_field(name="Accessory Guide", value=potential_guide, inline=False)
                        await message.edit(embed=embed)
                        await message.clear_reactions()

                        action_reactions = ["💎", "🪄", "🗑️", "◀️"]
                        for emoji in action_reactions:
                            await message.add_reaction(emoji)

                        def action_check(r, u):
                            return u == interaction.user and r.message.id == message.id and str(r.emoji) in action_reactions

                        try:
                            action_reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=action_check)
                            if str(action_reaction.emoji) == "💎":
                                await message.remove_reaction(action_reaction.emoji, user)
                                if selected_accessory[10] == 1:
                                    embed.add_field(name="But why", value=f"You already have this equipped.", inline=False)
                                    await message.edit(embed=embed)
                                else:
                                    await self.bot.database.equip_accessory(user_id, selected_accessory[0])
                                    embed.add_field(name="Equip", value=f"Equipped accessory.", inline=False)
                                    await message.edit(embed=embed)
                                await asyncio.sleep(3)
                                continue
                            elif str(action_reaction.emoji) == "🪄":
                                await self.improve_potential(interaction, selected_accessory, message, embed)
                                continue
                            elif str(action_reaction.emoji) == "🗑️":
                                await self.discard_accessory(interaction, selected_accessory, message, embed)
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
        accessory_id = selected_accessory[0]  # Assuming item_id is at index 0
        accessory_name = selected_accessory[2]
        embed = discord.Embed(
            title="Confirm Discard",
            description=f"Discard **{accessory_name}**?\n**This action cannot be undone.**",
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

        await self.bot.database.discard_accessory(accessory_id)


    async def improve_potential(self, 
                                interaction: Interaction, 
                                selected_accessory: tuple, 
                                message, 
                                embed) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        accessory_id = selected_accessory[0]
        accessory_name = selected_accessory[2]
        current_passive = selected_accessory[9]
        potential_remaining = selected_accessory[11]
        potential_lvl = selected_accessory[12] 
        potential_passive_list = ["Obliterate", "Absorb", "Prosper", "Infinite Wisdom", "Lucky Strikes"]
        
        if potential_remaining <= 0:
            embed.add_field(name="Error", 
                            value=f"This accessory has no potential remaining.\n"
                            "You cannot enhance it further.\n"
                            "Returning to item menu...", 
                            inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        rune_of_potential_count = await self.bot.database.fetch_potential_runes(str(interaction.user.id))
        costs = [500, 1000, 2000, 3000, 4000, 5000, 10000, 20000, 30000, 40000]
        refine_cost = costs[10 - potential_remaining]
        success_rate = max(75 - (10 - potential_remaining) * 5, 35)

        title_keyword = "Unlock" if current_passive == "none" else "Enhance"
        embed = discord.Embed(
            title=f"{title_keyword} Potential Attempt",
            description=(f"{title_keyword} **{accessory_name}**'s potential? \n"
                            f"Attempts left: **{potential_remaining}** \n"
                            f"Cost: **{refine_cost:,} GP**\n"
                            f"Success Rate: **{success_rate}%**\n"),
            color=0xFFCC00
        )
        embed.set_thumbnail(url="https://i.imgur.com/Tkikr5b.jpeg") # Thumbnail for jewel crafter
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

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
        
        player_gold = await self.bot.database.fetch_user_gold(user_id, server_id)
        if player_gold < refine_cost:
            embed.add_field(name="Refining", 
                            value=f"Not enough gold!\nReturning to item menu...", 
                            inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
            return

        await self.bot.database.update_user_gold(user_id, player_gold - refine_cost)

        if rune_of_potential_count > 0:
            embed.add_field(name="Runes of Potential", 
                            value=(f"You have **{rune_of_potential_count}** Rune(s) of Potential available.\n"
                                   f"Do you want to use one to boost your success rate to **{success_rate + 25}%**?"),
                            inline=False)
            embed.set_thumbnail(url="https://i.imgur.com/aeorjQG.jpg")
            await message.edit(embed=embed)
            await message.clear_reactions()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def check_reaction(r, user):
                return user == (interaction.user and 
                                r.message.id == message.id and 
                                str(r.emoji) in ["✅", "❌"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check_reaction)

                if str(reaction.emoji) == "✅":
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
        self.bot.state_manager.clear_active(interaction.user.id)  
        await self.bot.database.update_accessory_potential(accessory_id, potential_remaining)
        await message.edit(embed=embed)
        await asyncio.sleep(5)
        embed.clear_fields()

# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(Accessories(bot))
