import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import Button, View
import asyncio
import random
import uuid

# Here we name the cog and create a new class for the cog.
class ArmorView(commands.Cog, name="armorview"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="view_armor", description="View your character's armor and modify them.")
    async def armor(self, interaction: Interaction) -> None:
        """Fetch and display the character's armors with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if not await self.bot.is_maintenance(interaction, user_id):
            return

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
            title="🛡️ Armors",
            description=f"{player_name}'s Armors:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/NTVHFL8.png")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")

        # Pagination setup
        items_per_page = 5
        total_pages = (len(armors) + items_per_page - 1) // items_per_page
        current_page = 0

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
                equipped_armor = await self.bot.database.get_equipped_armor(user_id)
                is_equipped = equipped_armor and (equipped_armor[0] == armor[0])
                armors_display_string += (
                    f"{index + 1}: "
                    f"{'[E] ' if is_equipped else ''}"
                    f"{armor_name} (i{armor_level})\n"
                    
                )
            
            embed.add_field(
                name="Armors:",
                value=armors_display_string.strip(),
                inline=False
            )
                
            embed.add_field(
                name="Instructions",
                value=("Select an armor to interact with.\n"
                       "Use navigation buttons to chance pages or Close to exit."),
                inline=False
            )

            # Create view with buttons
            view = View(timeout=60.0)
            for index in range(len(armors_to_display)):
                button = Button(label=f"{index + 1}", style=ButtonStyle.primary, custom_id=f"armor_{index}")
                view.add_item(button)
            
            if current_page > 0:
                view.add_item(Button(label="Previous", style=ButtonStyle.secondary, custom_id="prev_page"))
            if current_page < total_pages - 1:
                view.add_item(Button(label="Next", style=ButtonStyle.secondary, custom_id="next_page"))
            view.add_item(Button(label="Close", style=ButtonStyle.danger, custom_id="close"))

            await message.edit(embed=embed, view=view)

            def check(interaction_check: Interaction):
                return (interaction_check.user == interaction.user and
                        interaction_check.message.id == message.id)

            try:
                interaction_response = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                custom_id = interaction_response.data['custom_id']
                
                if custom_id == "prev_page" and current_page > 0:
                    current_page -= 1
                    await interaction_response.response.defer()
                    continue
                elif custom_id == "next_page" and current_page < total_pages - 1:
                    current_page += 1
                    await interaction_response.response.defer()
                    continue
                elif custom_id == "close":
                    await message.delete()
                    self.bot.state_manager.clear_active(user_id)
                    break
                
                if custom_id.startswith("armor_"):
                    selected_index = int(custom_id.split("_")[1])
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
                        embed.description = f"**{armor_name}** (i{armor_level}):"
                        embed.clear_fields()
                        if armor_block > 0:
                            embed.add_field(name="Block", value=armor_block, inline=True)
                            embed.add_field(name="Effect", 
                                            value=f"{(armor_block / 2)}% chance to reduce initial monster hit to 0",
                                            inline=False)
                        if armor_evasion > 0:
                            embed.add_field(name="Evasion", value=armor_evasion, inline=True)
                            embed.add_field(name="Effect", 
                                value=f"Monster accuracy roll decreased by {int(armor_evasion / 4)}",
                                inline=False)
                        if armor_ward > 0:
                            embed.add_field(name="Ward", value=f"{armor_ward}%", inline=True)
                            embed.add_field(name="Effect", 
                                value=f"{int(armor_ward)}% additional temporary max hp at start of encounter",
                                inline=False)
                        if armor_passive != "none":
                            effect_description = self.get_armor_passive_effect(armor_passive)
                            embed.add_field(name="Passive", value=armor_passive, inline=False)
                            embed.add_field(name="Effect", value=effect_description, inline=False)
                        armor_guide = (
                            "Select an action:\n"
                            "- Equip: Equip the armor\n"
                            "- Temper: Upgrade armor stats\n"
                            "- Imbue: Add a passive effect\n"
                            "- Discard: Delete the armor\n"
                            "- Back: Return to armor list"
                        )
                        embed.add_field(name="Armor Actions", value=armor_guide, inline=False)

                        view = View(timeout=60.0)
                        view.add_item(Button(label="Equip", style=ButtonStyle.primary, custom_id="equip"))
                        view.add_item(Button(label="Temper", style=ButtonStyle.primary, custom_id="temper"))
                        view.add_item(Button(label="Imbue", style=ButtonStyle.primary, custom_id="imbue"))
                        view.add_item(Button(label="Discard", style=ButtonStyle.danger, custom_id="discard"))
                        view.add_item(Button(label="Back", style=ButtonStyle.secondary, custom_id="back"))

                        await message.edit(embed=embed, view=view)

                        try:
                            action_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=check)
                            await interaction_response.response.defer()
                            action_id = action_interaction.data['custom_id']
                            
                            if action_id == "equip":
                                if selected_armor[8] == 1:
                                    embed.add_field(name="Error", value="You already have this equipped.", inline=False)
                                    await message.edit(embed=embed, view=view)
                                else:
                                    await self.bot.database.equip_armor(user_id, selected_armor[0])
                                    embed.add_field(name="Equip", value="Equipped armor.", inline=False)
                                    await message.edit(embed=embed, view=view)
                                await asyncio.sleep(3)
                                continue
                            elif action_id == "temper":
                                await self.temper_armor(action_interaction, selected_armor, embed, message)
                                continue
                            elif action_id == "imbue":
                                await self.imbue_armor(action_interaction, selected_armor, embed, message)
                                continue
                            elif action_id == "discard":
                                await self.discard_armor(action_interaction, selected_armor, message, embed)
                                continue
                            elif action_id == "back":
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
            embed.add_field(name="Tempering", value="This armor cannot be tempered anymore.", inline=True)
            await interaction.response.edit_message(embed=embed)
            await asyncio.sleep(3)
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]
        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

        ore_cost, wood_cost, bone_cost, gp_cost = costs[tempers_remaining]
        ore, logs, bones = tempers_data[tempers_remaining]

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
            await interaction.response.edit_message(embed=embed)
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
        view = View(timeout=60.0)
        view.add_item(Button(label="Confirm", style=ButtonStyle.success, custom_id="confirm_temper"))
        view.add_item(Button(label="Cancel", style=ButtonStyle.danger, custom_id="cancel_temper"))
        await interaction.response.edit_message(embed=embed, view=view)

        def confirm_check(interaction_check: Interaction):
            return (interaction_check.user == interaction.user and
                    interaction_check.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=confirm_check)
            if confirm_interaction.data['custom_id'] == "cancel_temper":
                embed.add_field(name="Cancel", value="Returning to armor menu...", inline=False)
                await confirm_interaction.response.edit_message(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(user_id)
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
            if armor_details[4] > 0:
                stat_to_increase = 'block'
                current_value = armor_details[4]
            elif armor_details[5] > 0:
                stat_to_increase = 'evasion'
                current_value = armor_details[5]
            else:
                stat_to_increase = 'ward'
                current_value = armor_details[6]
                
            increase_amount = max(1, random.randint(int(armor_level // 7), int(armor_level // 5)))
            await self.bot.database.increase_armor_stat(armor_id, stat_to_increase, increase_amount)
            embed.add_field(name="Tempering success", 
                           value=(f"Congratulations! "
                                  f"**{armor_name}**'s {stat_to_increase.capitalize()} increased by **{increase_amount}**."),
                           inline=False)
            await confirm_interaction.response.edit_message(embed=embed)
            await asyncio.sleep(7)
        else:
            embed.add_field(name="Tempering", 
                           value=(f"Tempering failed! "
                                  f"Better luck next time.\n"
                                  f"Returning to armor menu..."),
                           inline=False)
            await confirm_interaction.response.edit_message(embed=embed)
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
            await interaction.response.edit_message(embed=embed)
            await asyncio.sleep(3)
            return
        
        if imbues_remaining < 1:
            embed.add_field(name="Imbuing", 
                           value=f"This armor can no longer be imbued.", 
                           inline=False)
            await interaction.response.edit_message(embed=embed)
            await asyncio.sleep(3)
            return
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        imbue_runes = existing_user[27]
        if imbue_runes <= 0:
            embed.add_field(name="Imbuing", 
                           value=f"You do not have any Runes of Imbuing. Returning to armor menu...", 
                           inline=False)
            await interaction.response.edit_message(embed=embed)
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
        view = View(timeout=60.0)
        view.add_item(Button(label="Confirm", style=ButtonStyle.success, custom_id="confirm_imbue"))
        view.add_item(Button(label="Cancel", style=ButtonStyle.danger, custom_id="cancel_imbue"))
        await interaction.response.edit_message(embed=embed, view=view)

        def confirm_check(interaction_check: Interaction):
            return (interaction_check.user == interaction.user and
                    interaction_check.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=confirm_check)
            if confirm_interaction.data['custom_id'] == "cancel_imbue":
                embed.add_field(name="Cancel", value="Returning to armor menu...", inline=False)
                await confirm_interaction.response.edit_message(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(user_id)
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
                           value=(f"Congratulations! "
                                  f"**{armor_name}** has been imbued with **{new_passive}**."),
                           inline=False)
            await confirm_interaction.response.edit_message(embed=embed)
            await asyncio.sleep(7)
        else:
            embed.add_field(name="Imbuing", 
                           value=(f"Imbuing failed! "
                                  f"Better luck next time.\n"
                                  f"Returning to armor menu..."),
                           inline=False)
            await confirm_interaction.response.edit_message(embed=embed)
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
        view = View(timeout=60.0)
        view.add_item(Button(label="Confirm", style=ButtonStyle.success, custom_id="confirm_discard"))
        view.add_item(Button(label="Cancel", style=ButtonStyle.danger, custom_id="cancel_discard"))
        await interaction.response.edit_message(embed=embed, view=view)

        def confirm_check(interaction_check: Interaction):
            return (interaction_check.user == interaction.user and
                    interaction_check.message.id == message.id)

        try:
            confirm_interaction = await self.bot.wait_for('interaction', timeout=60.0, check=confirm_check)
            if confirm_interaction.data['custom_id'] == "cancel_discard":
                await confirm_interaction.response.defer()
                return
            await self.bot.database.discard_armor(armor_id)
            await confirm_interaction.response.edit_message(embed=embed, view=None)

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)

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

async def setup(bot) -> None:
    await bot.add_cog(ArmorView(bot))