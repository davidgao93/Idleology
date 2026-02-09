import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, Message
import asyncio
import random
import json

"""
Index	Attribute Description
0	Unique ID
1	User ID
2	Server ID
3	Player Name
4	Level
5	Experience
6	Gold
7	Image URL (for player image)
8	Ideology
9	Attack
10	Defense
11	Current HP
12	Maximum HP
13	Last Rest Time
14	Last Propagate Time
15	Ascension Level
16	Potion Count
17	Last Checkin Time
18  Created at
19  Refinement runes
20  Passive Points
21  Potential runes
22  Curios
23  Curious purchased
24  Last Combat
25  Dragon Key
26  Angel Key
27  Imbue runes
28  Soul Cores
29  Void Fragments
30  Void Keys
31  Shatter Runes
"""
class Character(commands.Cog, name="character"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.active_users = {}  # Dictionary to track active users
        
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_hp.is_running():
            self.bot.logger.info('Starting player health regen task')
            self.check_hp.start()

    @tasks.loop(minutes=15)
    async def check_hp(self):
        """Check and increment current_hp for all users every 15m."""
        # Fetch all users from the database
        users = await self.bot.database.users.get_all()
        self.bot.logger.info(f'Healing all users')
        for user in users:
            user_id = user[1] 
            current_hp = user[11]
            max_hp = user[12]
            scaling = int(max_hp / 30)
            if current_hp < max_hp:
                new_hp = current_hp + 1 + scaling
                if (new_hp > max_hp):
                    new_hp = max_hp
                await self.bot.database.users.update_hp(user_id, new_hp)


    @app_commands.command(name="stats", description="Get your character's stats.")
    async def get_stats(self, interaction: Interaction) -> None:
        """Fetch and display the character's stats."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if existing_user:
            ascension = existing_user[15]
            if ascension > 0:
                title = f"{existing_user[3]} (Ascension {ascension} 🌟)"
            else:
                title = f"{existing_user[3]}"

            # Create the embed with the constructed title
            embed = discord.Embed(
                title=title,
                color=0x00FF00,
            )
            embed.set_thumbnail(url=existing_user[7]) # user portrait
            equipped_item = await self.bot.database.get_equipped_weapon(user_id)
            equipped_accessory = await self.bot.database.get_equipped_accessory(user_id)
            equipped_armor = await self.bot.database.get_equipped_armor(user_id)
            equipped_glove = await self.bot.database.get_equipped_glove(user_id)
            equipped_boot = await self.bot.database.get_equipped_boot(user_id)
            # Calculate base attack and defense
            base_attack = existing_user[9]
            base_defense = existing_user[10]
            
            add_atk = 0
            add_def = 0
            add_rar = 0
            crit = 0
            ward = 0
            block = 0
            evasion = 0
            pdr = 0
            fdr = 0
            weapon_passive = ""
            pinnacle_passive = ""
            utmost_passive = ""
            acc_passive = ""
            armor_passive = ""
            glove_passive = ""
            boot_passive = ""
            passive_list = ""

            if equipped_item:
                add_atk += equipped_item[4]
                add_def += equipped_item[5]
                add_rar += equipped_item[6]
                weapon_passive = equipped_item[7]
                pinnacle_passive = equipped_item[12]
                utmost_passive = equipped_item[13]
                weapon_passives = [weapon_passive.title()]
                if pinnacle_passive != "none":
                    weapon_passives.append(pinnacle_passive.title())
                if utmost_passive != "none":
                    weapon_passives.append(utmost_passive.title())
                passive_list += "Weapon: " + ", ".join(weapon_passives) + "\n"
            if equipped_accessory:
                add_atk += equipped_accessory[4]
                add_def += equipped_accessory[5]
                add_rar += equipped_accessory[6]
                # Add crit and ward if they exist
                crit += equipped_accessory[8]
                ward += equipped_accessory[7]
                acc_passive = equipped_accessory[9]
                passive_list += "Accessory: " + (acc_passive if acc_passive else "None") + "\n"
            if equipped_armor:
                ward += equipped_armor[6]
                block += equipped_armor[4]
                evasion += equipped_armor[5]
                pdr += equipped_armor[11]
                fdr += equipped_armor[12]
                armor_passive = equipped_armor[7]
                passive_list += "Armor: " + (armor_passive if armor_passive else "None") + "\n"
            if equipped_glove:
                add_atk += equipped_glove[4]
                add_def += equipped_glove[5]
                ward += equipped_glove[6]
                pdr += equipped_glove[7]
                fdr += equipped_glove[8]
                glove_passive = equipped_glove[9]
                passive_list += "Gloves: " + (glove_passive.title() if glove_passive else "None") + "\n"
            if equipped_boot:
                add_atk += equipped_boot[4]
                add_def += equipped_boot[5]
                ward += equipped_boot[6]
                pdr += equipped_boot[7]
                fdr += equipped_boot[8]
                boot_passive = equipped_boot[9]
                passive_list += "Boots: " + (boot_passive.title() if boot_passive else "None")

            # Fetch experience table
            with open('assets/exp.json') as file:
                exp_table = json.load(file)

            current_level = existing_user[4]  # Assuming level is at index 4
            current_exp = existing_user[5]      # Current experience
            exp_needed = exp_table["levels"].get(str(current_level), 0)  # Fetch the necessary EXP for this level

            # Calculate experience percentage
            if exp_needed > 0:
                exp_percentage = (current_exp / exp_needed) * 100
            else:
                exp_percentage = 100  # Full EXP if already max level or no exp required
            # Add the character stats to the embed
            embed.add_field(name="Level ⭐", value=existing_user[4], inline=True)
            embed.add_field(name="Experience ✨", value=f"{current_exp:,} ({exp_percentage:.2f}%)", inline=True)
            embed.add_field(name="HP ❤️", value=f"{existing_user[11]}/{existing_user[12]}", inline=True)
            attack_display = f"{base_attack} (+{add_atk})" if add_atk > 0 else f"{base_attack}"
            embed.add_field(name="Attack ⚔️", value=attack_display, inline=True)
            defense_display = f"{base_defense} (+{add_def})" if add_def > 0 else f"{base_defense}"
            embed.add_field(name="Defense 🛡️", value=defense_display, inline=True)
            if (add_rar > 0):
                embed.add_field(name="Rarity 🪄", value=f"{add_rar}%", inline=True)
            if (crit > 0):
                embed.add_field(name="Crit 🗡️", value=f"{crit}%", inline=True)
            if (block > 0): 
                embed.add_field(name="Block 🧱", value=f"{block}", inline=True)
            if (evasion > 0): 
                embed.add_field(name="Evasion 🏃‍♂️", value=f"{evasion}", inline=True)
            if (ward > 0): 
                embed.add_field(name="Ward 🔮", value=f"{ward}% ({int(existing_user[12]*ward/100)})", inline=True)
            pdr_fdr_info = []
            if pdr > 0: 
                pdr_fdr_info.append(f"{pdr}%")
            if fdr > 0: 
                pdr_fdr_info.append(f"{fdr}")
            if pdr_fdr_info:
                embed.add_field(name="Damage Reduction 🔺", value=" / ".join(pdr_fdr_info), inline=True)
            if (passive_list):
                embed.add_field(name="__Passives__", value=f"{passive_list}", inline=False)

            await interaction.response.send_message(embed=embed)
            message: Message = await interaction.original_response()
            await asyncio.sleep(10)
            await message.delete()
        else:
            if not await self.bot.check_user_registered(interaction, existing_user):
                return

    @app_commands.command(name="inventory", description="Check your inventory status.")
    async def inventory(self, interaction: Interaction) -> None:
        """Fetch and display the user's inventory status."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        # Fetching inventory data
        weapons_count = await self.bot.database.equipment.get_count(user_id, 'weapon')
        accessories_count = await self.bot.database.equipment.get_count(user_id, 'accessories')
        arms = await self.bot.database.equipment.get_all(user_id, 'armor')
        gloves = await self.bot.database.equipment.get_count(user_id, 'glove')
        boots = await self.bot.database.equipment.get_count(user_id, 'boot')
        runes_of_potential = existing_user[21]  # index for runes of potential
        runes_of_refinement = existing_user[19]  # index for runes of refinement
        runes_of_imbuing = existing_user[27] # imbue runes
        potions_count = existing_user[16]  # index for potion count
        dragon_keys = existing_user[25] # dragon keys
        angel_keys = existing_user[26]
        soul_cores = existing_user[28] # soul cores
        void_frags = existing_user[29]
        void_keys = existing_user[30]
        shatter_runes = existing_user[31]
        curio_count = existing_user[22]
        gold_count = existing_user[6]  # index for gold

        # Create an embed to display inventory information
        embed = discord.Embed(
            title=(f"{existing_user[3]}'s Inventory\n"
                    f"💰 Gold: **{gold_count:,}**\n"
                    f"🧪 Potions: **{potions_count:,}**"),
            color=0x00FF00,
        )
        embed.set_thumbnail(url=existing_user[7]) # user portrait
        embed.add_field(name="", value="", inline=False)
        # Grouped fields for Weapons, Accessories, and Armors
        embed.add_field(name="👑 **Equipment**", 
                        value=(
                            f"⚔️ Weapons: {weapons_count:,}\n"
                            f"💍 Accessories: {accessories_count:,}\n"
                            f"👘 Armors: {len(arms):,}\n"
                            f"🧤 Gloves: {gloves:,}\n"
                            f"👢 Boots: {boots:,}"
                        ), inline=True)

        # Grouped fields for Runes
        embed.add_field(name="💫 **Runes**", 
                        value=(
                            f"💎 Potential: {runes_of_potential:,}\n"
                            f"🔨 Refinement: {runes_of_refinement:,}\n"
                            f"🔅 Imbuing: {runes_of_imbuing:,}\n"
                            f"💥 Shatter: {shatter_runes:,}"
                        ), inline=True)

        # Grouped fields for Keys and Soul Cores
        embed.add_field(name="🔑 **Boss Keys**", 
                        value=(
                            f"🐉 Draconic: {dragon_keys:,}\n"
                            f"🪽 Angelic: {angel_keys:,}\n"
                            f"❤️‍🔥 Soul Core: {soul_cores:,}\n"
                            f"🟣 Void Fragments: {void_frags:,}"
                        ), inline=True)

        # Curios
        embed.add_field(name="✨ **Misc**", 
                value=(
                    f"🎁 Curios: {curio_count:,}\n"
                    f"🗝️ Void Keys: {void_keys:,}\n"
                ), inline=True)

        # Send the embed
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        await asyncio.sleep(20)
        await message.delete()

    '''
    
    MISCELLANEOUS COMMANDS
    
    '''

    @app_commands.command(name="leaderboard", description="Show the top adventurers sorted by level.")
    async def leaderboard(self, interaction: Interaction) -> None:
        """Fetch and display the top 10 adventurers sorted by level."""
        top_users = await self.bot.database.users.get_leaderboard(limit=10)

        if not top_users:
            await interaction.response.send_message("No adventurers found.")
            return

        # Create an embed for the leaderboard
        embed = discord.Embed(
            title="Hiscores 🏆",
            color=0x00FF00
        )

        # Construct the leaderboard information
        leaderboard_lines = []
        for idx, user in enumerate(top_users, start=1):
            user_name = user[3]  # Assuming player name is at index 3
            user_level = user[4]  # Assuming level is at index 4
            user_asc = user[15] # Ascension level

            # Build leaderboard line with the appropriate emoji
            if idx == 1:
                leaderboard_lines.append(f"🥇 **{user_name}** - Level {user_level} - (Ascension {user_asc} 🌟)")
            elif idx == 2:
                leaderboard_lines.append(f"🥈 **{user_name}** - Level {user_level} - (Ascension {user_asc} 🌟)")
            elif idx == 3:
                leaderboard_lines.append(f"🥉 **{user_name}** - Level {user_level} - (Ascension {user_asc} 🌟)")
            else:
                leaderboard_lines.append(f"**{idx}: {user_name}** - Level {user_level} - (Ascension {user_asc} 🌟)")

        leaderboard_text = "\n".join(leaderboard_lines)
        embed.add_field(name="Top Adventurers:", value=leaderboard_text, inline=False)

        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()


    @app_commands.command(name="passives", description="Allocate your passive points.")
    async def passives(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Fetch the sender's user data
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # Fetch user's current passive points
        passive_points = await self.bot.database.users.get_currency(user_id, 'passive_points')
        if passive_points <= 0:
            await interaction.response.send_message("You do not have any passive points to allocate.")
            return
        
        embed = discord.Embed(
            title="Allocate Passive Points",
            description="Choose a stat to allocate a passive point to.",
            color=0x00FF00
        )
        embed.add_field(name="Points remaining: ", value=f"{passive_points}", inline=True)
        embed.add_field(name="Current Stats", 
                value=(f"Attack: {existing_user[9]}\n"
                f"Defense: {existing_user[10]}\n"
                f"HP: {existing_user[12]}"), inline=False)
        embed.add_field(name="**WARNING**", 
                value=(f"All choices are **final**, no take-backsies! You have been warned."), inline=False)
        # embed.add_field(name="Attack", value="⚔️", inline=False)
        # embed.add_field(name="Defense", value="🛡️", inline=True)
        # embed.add_field(name="HP", value="❤️", inline=True)

        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "stats")
        def check(reaction, user):
            return (user == interaction.user and 
                    str(reaction.emoji) in ["⚔️", "🛡️", "❤️", "❌"] and 
                    reaction.message.id == message.id)
        await message.add_reaction("⚔️")  # Attack
        await message.add_reaction("🛡️")  # Defense
        await message.add_reaction("❤️")  # HP
        await message.add_reaction("❌") # Leave

        while passive_points > 0:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=180.0, check=check)
                if str(reaction.emoji) == "⚔️":
                    # Increment attack and decrement passive points
                    await self.bot.database.users.modify_stat(user_id, 'attack', 1)
                elif str(reaction.emoji) == "🛡️":
                    # Increment defense and decrement passive points
                    await self.bot.database.users.modify_stat(user_id, 'defence', 1)
                elif str(reaction.emoji) == "❤️":
                    # Increment HP and decrement passive points
                    await self.bot.database.users.modify_stat(user_id, 'max_hp', 1)
                elif str(reaction.emoji) == "❌":
                    await message.delete()
                    break

                await message.remove_reaction(reaction.emoji, user)
                passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
                # Update passive points
                if passive_points > 0:
                    passive_points -= 1
                    self.bot.logger.info("-1 passive pt")
                    await self.bot.database.users.set_passive_points(user_id, server_id, passive_points)
                else:
                    self.bot.logger.info('Invalid passive points')
                # Edit the embed to show current allocations
                embed.clear_fields()
                existing_user = await self.bot.database.users.get(user_id, server_id)
                embed.add_field(name="Points remaining: ", value=f"{passive_points}", inline=True)
                embed.add_field(name="Current Stats", 
                                value=(f"Attack ⚔️: {existing_user[9]}\n"
                                f"Defense 🛡️: {existing_user[10]}\n"
                                f"HP ❤️: {existing_user[12]}"), inline=False)
                # embed.add_field(name="Attack", value="⚔️", inline=True)
                # embed.add_field(name="Defense", value="🛡️", inline=True)
                # embed.add_field(name="HP", value="❤️", inline=True)
                await message.edit(embed=embed)
            
            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)  
                break

        self.bot.state_manager.clear_active(user_id)
        # await message.clear_reactions()
        if (passive_points == 0):
            embed.add_field(name="All points allocated", value="You have allocated all your passive points.", inline=False)
            await message.edit(embed=embed)
            await message.clear_reactions()


async def setup(bot) -> None:
    await bot.add_cog(Character(bot))