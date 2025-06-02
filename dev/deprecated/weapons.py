import discord
from discord.ext import commands
from discord import app_commands, Interaction, Message
import asyncio
import random

class Weapons(commands.Cog, name="weapons"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="weapons", description="View your character's weapons and modify them.")
    async def weapons(self, interaction: Interaction) -> None:
        """Fetch and display the character's weapons with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Check if the user has any active operations
        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        # if not await self.bot.is_maintenance(interaction, user_id):
        #     return
        
        items = await self.bot.database.fetch_user_weapons(user_id)
        
        if not items:
            await interaction.response.send_message("You peer into your weapon's pouch, it is empty.")
            return
        
        player_name = existing_user[3]
        embed = discord.Embed(
            title=f"📦",
            description=f"{player_name}'s Weapons:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/AnlbnbO.jpeg") # Thumbnail for weapon pouch
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")  # Set inventory as active operation

        # Pagination setup
        items_per_page = 5
        total_pages = (len(items) + items_per_page - 1) // items_per_page  # Ceiling division
        current_page = 0
        number_emojis = ["❌", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        while True:
            items = await self.bot.database.fetch_user_weapons(user_id)
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1)  # Ensure current_page is valid
            embed.description = f"{player_name}'s Weapons (Page {current_page + 1}/{total_pages}):"
            if not items:
                await interaction.followup.send("You peer into your weapon's pouch, it is empty.")
                break

            items.sort(key=lambda item: item[2], reverse=True)  # item_level at index 2
            start_idx = current_page * items_per_page
            items_to_display = items[start_idx:start_idx + items_per_page]
            await message.clear_reactions()
            embed.clear_fields()
            items_display_string = ""

            for index, item in enumerate(items_to_display):
                item_name = item[1]  # index 1: item name
                item_level = item[2]  # index 2: item level
                equipped_item = await self.bot.database.get_equipped_weapon(user_id)
                is_equipped = equipped_item and (equipped_item[0] == item[0])
                
                # Append item details to the display string
                items_display_string += (
                    f"{number_emojis[index + 1]}: "
                    f"{item_name} (Level {item_level})"
                    f"{' [E]' if is_equipped else ''}\n"
                )
            
            # Add a single field for all items
            embed.add_field(
                name="Weapons:",
                value=items_display_string.strip(),
                inline=False
            )
                
            # Add instructions and page info
            embed.add_field(
                name="Instructions",
                value=(f"[ℹ️] Select an item to interact with.\n"
                       f"[◀️] Previous page | [▶️] Next page | [❌] Close interface."),
                inline=False
            )
            await message.edit(embed=embed)
            
            # Add reactions: number emojis for items, navigation, and exit
            for i in range(len(items_to_display) + 1):
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
                
                selected_index = number_emojis.index(reaction_str) - 1 # -1 since exit is the first emoji
                if selected_index >= 0:
                    while True:
                        selected_item = items_to_display[selected_index]
                        print(f'Fetching {selected_item} from db again for refresh')
                        selected_item = await self.bot.database.fetch_weapon_by_id(selected_item[0])
                        if not selected_item:
                            break
                        # Display selected item details
                        item_name = selected_item[2]
                        item_level = selected_item[3]
                        item_attack = selected_item[4] if len(selected_item) > 4 else 0
                        item_defence = selected_item[5] if len(selected_item) > 5 else 0
                        item_rarity = selected_item[6] if len(selected_item) > 6 else 0
                        item_passive = selected_item[7]
                        embed.description = f"**{item_name}** (i{item_level}):"
                        embed.clear_fields()
                        embed.add_field(name="Attack", value=item_attack, inline=True)
                        embed.add_field(name="Defence", value=item_defence, inline=True)
                        embed.add_field(name="Rarity", value=item_rarity, inline=True)
                        embed.add_field(name="Passive", value=item_passive.capitalize(), inline=False)
                        if item_passive != "none":
                            effect_description = self.get_passive_effect(item_passive)
                            embed.add_field(name="Effect", value=effect_description, inline=False)
                        item_guide = (
                            "⚔️ to equip.\n"
                            "🔨 to forge.\n"
                            "⚙️ to refine.\n"
                            "🗑️ to discard.\n"
                            "◀️ to go back."
                        )
                        embed.add_field(name="Item Guide", value=item_guide, inline=False)
                        await message.edit(embed=embed)
                        await message.clear_reactions()
                        action_reactions = ["⚔️", "🔨", "⚙️", "🗑️", "◀️"]
                        for emoji in action_reactions:
                            await message.add_reaction(emoji)
                        def action_check(reaction, user):
                            return (user == interaction.user and 
                                    reaction.message.id == message.id and 
                                    str(reaction.emoji) in action_reactions)
                        
                        try:
                            action_reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=action_check)
                            if str(action_reaction.emoji) == "⚔️":
                                await message.remove_reaction(action_reaction.emoji, user)
                                if selected_item[8] == 1:
                                    embed.add_field(name="But why", value=f"You already have this equipped.", inline=False)
                                    await message.edit(embed=embed)
                                else:
                                    await self.bot.database.equip_weapon(user_id, selected_item[0])
                                    embed.add_field(name="Equip", value=f"Equipped weapon.", inline=False)
                                    await message.edit(embed=embed)
                                continue
                            elif str(action_reaction.emoji) == "🔨":
                                await self.forge_item(interaction, selected_item, embed, message)
                                continue
                            elif str(action_reaction.emoji) == "⚙️":
                                await self.refine_item(interaction, selected_item, embed, message)
                                continue
                            elif str(action_reaction.emoji) == "🗑️":
                                await self.discard(interaction, selected_item, message, embed)
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

        await self.bot.database.discard_weapon(item_id)


    async def forge_item(self, 
                         interaction: Interaction, 
                         selected_item: tuple, 
                         embed, 
                         message) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        item_id = selected_item[0] # unique id of item
        item_name = selected_item[2] 
        item_level = selected_item[3]

        # Get the current state of the item
        forges_remaining = selected_item[9]  # Index where `forges_remaining` is stored
        print(f'Forges remaining for item id {item_id}: {forges_remaining}')

        if forges_remaining < 1:
            embed.add_field(name="Forging", value=f"This item cannot be forged anymore.\n"
                    "Returning to main menu...", inline=True)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        # Define the costs lookup based on the forges remaining
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
        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]  # Fetch the amount of gold from existing_user

        # Resources from the mining, woodcutting, and fishing tables
        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

        # Get the corresponding costs based on forges remaining
        ore_cost, wood_cost, bone_cost, gp_cost = costs[forges_remaining]
        print(mining_data)
        print(woodcutting_data)
        print(fishing_data)
        print(f'forge will cost {ore_cost} ore, {wood_cost} logs, {bone_cost} bones, {gp_cost} gp')
        print(f'mining_data[cost_index]: {mining_data[cost_index]}')

        if forges_remaining in forges_data:
            ore, logs, bones = forges_data[forges_remaining]
        else:
            ore, logs, bones = None, None, None
        # Check if the user has enough resources and gold
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
        embed.set_thumbnail(url="https://i.imgur.com/jgq4aGA.jpeg") # thumbnail for forge
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
                embed.add_field(name="Cancel", value=f"Returning to item menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        # Deduct the costs from the user's resources
        print('subtracting ore')
        if item_level <= 40:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if forges_remaining == 3 else 0,
                'coal': -ore_cost if forges_remaining == 2 else 0,
                'gold': -ore_cost if forges_remaining == 1 else 0,
                'platinum': 0,
                'idea': 0,
            })
        elif 40 < item_level <= 80:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if forges_remaining == 4 else 0,
                'coal': -ore_cost if forges_remaining == 3 else 0,
                'gold': -ore_cost if forges_remaining == 2 else 0,
                'platinum': -ore_cost if forges_remaining == 1 else 0,
                'idea': 0,
            })
        else:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if forges_remaining == 5 else 0,
                'coal': -ore_cost if forges_remaining == 4 else 0,
                'gold': -ore_cost if forges_remaining == 3 else 0,
                'platinum': -ore_cost if forges_remaining == 2 else 0,
                'idea': -ore_cost if forges_remaining == 1 else 0,
            })

        print('subtracting wood')
        if item_level <= 40:
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -ore_cost if forges_remaining == 3 else 0,
                'willow': -ore_cost if forges_remaining == 2 else 0,
                'mahogany': -ore_cost if forges_remaining == 1 else 0,
                'magic': 0,
                'idea': 0,
            })
        elif 40 < item_level <= 80:
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -ore_cost if forges_remaining == 4 else 0,
                'willow': -ore_cost if forges_remaining == 3 else 0,
                'mahogany': -ore_cost if forges_remaining == 2 else 0,
                'magic': -ore_cost if forges_remaining == 1 else 0,
                'idea': 0,
            })
        else:
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -ore_cost if forges_remaining == 5 else 0,
                'willow': -ore_cost if forges_remaining == 4 else 0,
                'mahogany': -ore_cost if forges_remaining == 3 else 0,
                'magic': -ore_cost if forges_remaining == 2 else 0,
                'idea': -ore_cost if forges_remaining == 1 else 0,
            })

        print('subtracting bones')
        if item_level <= 40:
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -ore_cost if forges_remaining == 3 else 0,
                'regular': -ore_cost if forges_remaining == 2 else 0,
                'sturdy': -ore_cost if forges_remaining == 1 else 0,
                'reinforced': 0,
                'titanium': 0,
            })
        elif 40 < item_level <= 80:
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -ore_cost if forges_remaining == 4 else 0,
                'regular': -ore_cost if forges_remaining == 3 else 0,
                'sturdy': -ore_cost if forges_remaining == 2 else 0,
                'reinforced': -ore_cost if forges_remaining == 1 else 0,
                'titanium': 0,
            })
        else:
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -ore_cost if forges_remaining == 5 else 0,
                'regular': -ore_cost if forges_remaining == 4 else 0,
                'sturdy': -ore_cost if forges_remaining == 3 else 0,
                'reinforced': -ore_cost if forges_remaining == 2 else 0,
                'titanium': -ore_cost if forges_remaining == 1 else 0,
            })
        print('subtracting gold')
        await self.bot.database.add_gold(user_id, -gp_cost)

        new_forges_remaining = forges_remaining - 1
        forge_success = random.random() <= success_rate  

        if forge_success:
            print('forge success')
            current_passive = selected_item[7]  # Index where `passive` is stored
            
            if current_passive == "none":
                print('item has no passive')
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
                print(f'Assigning {new_passive} to item {item_id}')
                await self.bot.database.update_weapon_passive(item_id, new_passive)
                embed.add_field(name="Forging success", 
                                value=(f"🎊 Congratulations! 🎊 " 
                                    f"**{item_name}** has gained the " 
                                    f"**{new_passive.capitalize()}** passive."), 
                                inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(7)
            else:
                print('item has passive, upgrade it')
                new_passive = await self.upgrade_passive(current_passive)
                print(f'new passive is {new_passive}')
                await self.bot.database.update_weapon_passive(item_id, new_passive)
                embed.add_field(name="Forging success", 
                                value=(f"🎊 Congratulations! 🎊 "
                                    f"**{item_name}**'s passive upgrades from **{current_passive.capitalize()}**"
                                    f" to **{new_passive.capitalize()}**."),
                                inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(7)
        else:
            embed.add_field(name="Failed", 
                            value=(f"Your hand slips and you fail to strike the weapon! 💔\n"
                                f"Better luck next time.\n"
                                f"Returning to item menu..."),
                            inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
        
        await self.bot.database.update_weapon_forge_count(item_id, new_forges_remaining)

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
        return passive_upgrade_table.get(current_passive, current_passive)  # Return current if maxed out
    
    def get_passive_effect(self, passive: str) -> str:
        passive_messages = {
            "burning": "Increases your maximum hit (1d6).",
            "flaming": "Increases your maximum hit. (2d6)",
            "scorching": "Increases your maximum hit. (3d6)",
            "incinerating": "Increases your maximum hit. (4d6)",
            "carbonising": "Increases your maximum hit. (5d6)",
            
            "poisonous": "Additional damage on misses. (3d6)",
            "noxious": "Additional damage on misses. (4d6)",
            "venomous": "Additional damage on misses. (5d6)",
            "toxic": "Additional damage on misses. (6d6)",
            "lethal": "Additional damage on misses. (7d6)",
            
            "polished": "Reduce monster's defence. (5%)",
            "honed": "Reduce monster's defence. (10%)",
            "gleaming": "Reduce monster's defence. (15%)",
            "tempered": "Reduce monster's defence. (20%)",
            "flaring": "Reduce monster's defence. (25%)",
            
            "sparking": "Additional damage on normal hits. (1d6)",
            "shocking": "Additional damage on normal hits. (2d6)",
            "discharging": "Additional damage on normal hits. (3d6)",
            "electrocuting": "Additional damage on normal hits. (4d6)",
            "vapourising": "Additional damage on normal hits. (5d6)",
            
            "sturdy": "Additional defence. (+3)",
            "reinforced": "Additional defence. (+6)",
            "thickened": "Additional defence. (+9)",
            "impregnable": "Additional defence. (+12)",
            "impenetrable": "Additional defence. (+15)",
            
            "piercing": "Additional crit chance. (3%)",
            "keen": "Additional crit chance. (6%)",
            "incisive": "Additional crit chance. (9%)",
            "puncturing": "Additional crit chance. (12%)",
            "penetrating": "Additional crit chance. (15%)",
            
            "strengthened": "Culling strike. (5%)",
            "forceful": "Culling strike. (10%)",
            "overwhelming": "Culling strike. (15%)",
            "devastating": "Culling strike. (20%)",
            "catastrophic": "Culling strike. (25%)",
            
            "accurate": "Increased accuracy. (3%)",
            "precise": "Increased accuracy. (6%)",
            "sharpshooter": "Increased accuracy. (9%)",
            "deadeye": "Increased accuracy. (12%)",
            "bullseye": "Increased accuracy. (15%)",
            
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
                await message.clear_reactions()
                await message.edit(embed=embed)

                await message.add_reaction("✅")
                await message.add_reaction("❌")

                def confirm_check(reaction, user):
                    return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

                    if str(reaction.emoji) == "✅":
                        await self.bot.database.update_refinement_runes(user_id, -1)
                        await self.bot.database.update_weapon_refine_count(item_id, 1)
                        embed.add_field(name="Rune of Refinement",
                                       value=(f"You have successfully applied a **Rune of Refinement**!\n"
                                              f"{item_name} now has **1** refine remaining. Returning to item menu..."),
                                       inline=False)
                        embed.set_thumbnail(url="https://i.imgur.com/1tcMeSe.jpg") # Thumbnail for Rune of Refine
                        refines_remaining = 1
                        await message.edit(embed=embed)
                        await asyncio.sleep(5)
                    elif str(reaction.emoji) == "❌":
                        return

                except asyncio.TimeoutError:
                    self.bot.state_manager.clear_active(interaction.user.id)  
                    return
            return

        # Determine cost of the refinement
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
        embed.set_thumbnail(url="https://i.imgur.com/k8nPS3E.jpeg") # Thumbnail for refinesmith
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return
        
        if player_gold < cost:
            embed.add_field(name="Refining", value=f"You do not have enough gold. Returning to item menu...", inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
            return

        await self.bot.database.update_user_gold(user_id, player_gold - cost)
        embed.add_field(name="Refining", value=f"The blacksmith carefully hones your weapon.", inline=False)
        await message.edit(embed=embed)
        
        attack_roll = random.randint(0, 100) < 80
        defense_roll = random.randint(0, 100) < 50
        rarity_roll = random.randint(0, 100) < 20

        attack_modifier = 0
        defense_modifier = 0
        rarity_modifier = 0
        max_range = int(item_level / 10) + 2
        if attack_roll:
            attack_modifier = random.randint(2, max_range)
            await self.bot.database.increase_weapon_rarity(item_id, attack_modifier) 
        else:
            attack_modifier = 1
            await self.bot.database.increase_weapon_rarity(item_id, attack_modifier) 
        
        if defense_roll:
            defense_modifier = random.randint(2, max_range)
            await self.bot.database.increase_weapon_rarity(item_id, defense_modifier) 
        else:
            defense_modifier = 1
            await self.bot.database.increase_weapon_rarity(item_id, defense_modifier)  

        if rarity_roll:
            rarity_modifier = random.randint(5, max_range * 5)
            await self.bot.database.increase_weapon_rarity(item_id, rarity_modifier)

        await self.bot.database.update_weapon_refine_count(item_id, refines_remaining - 1)

        result_message = []
        if attack_modifier > 0:
            result_message.append(f"Attack increased by **{attack_modifier}**!")
        if defense_modifier > 0:
            result_message.append(f"Defense increased by **{defense_modifier}**!")
        if rarity_modifier > 0:
            result_message.append(f"Rarity increased by **{rarity_modifier}**!")

        embed.add_field(name="Refining", value=("\n".join(result_message) + "\nReturning to item menu..."), inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(5)


async def setup(bot) -> None:
    await bot.add_cog(Weapons(bot))