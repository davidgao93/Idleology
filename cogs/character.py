import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, Message
from core.items.factory import load_player
from core.character.views import PassiveAllocateView
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


    @app_commands.command(name="stats", description="Detailed character sheet.")
    async def stats(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data): return

        # Use Core Model logic to calculate totals (including gear)
        p = await load_player(user_id, data, self.bot.database)
        
        embed = discord.Embed(title=f"Stats: {p.name}", color=0x00FF00)
        embed.set_thumbnail(url=data[7])

        # Base + Bonus display
        atk_bonus = p.get_total_attack() - p.base_attack
        def_bonus = p.get_total_defence() - p.base_defence
        
        atk_str = f"{p.base_attack}" + (f" (+{atk_bonus})" if atk_bonus > 0 else "")
        def_str = f"{p.base_defence}" + (f" (+{def_bonus})" if def_bonus > 0 else "")
        
        embed.add_field(name="⚔️ Attack", value=atk_str, inline=True)
        embed.add_field(name="🛡️ Defence", value=def_str, inline=True)
        embed.add_field(name="❤️ HP", value=f"{p.current_hp}/{p.max_hp}", inline=True)
        
        # Advanced Stats
        ward = p.get_total_ward_percentage()
        if ward > 0: embed.add_field(name="🔮 Ward", value=f"{ward}%", inline=True)
        
        crit_target = p.get_current_crit_target()
        crit_chance = 100 - crit_target
        if crit_chance > 5: embed.add_field(name="🎯 Crit Chance", value=f"{crit_chance}%", inline=True)
        
        pdr = p.get_total_pdr()
        if pdr > 0: embed.add_field(name="🛡️ PDR", value=f"{pdr}%", inline=True)

        fdr = p.get_total_fdr()
        if fdr > 0: embed.add_field(name="🛡️ FDR", value=f"{fdr}", inline=True)

        rarity = p.get_total_rarity()
        if rarity > 0: embed.add_field(name="✨ Rarity", value=f"{rarity}%", inline=True)

        # Passives List
        passives = []
        
        # Weapon
        if p.equipped_weapon:
            p_list = []
            if p.equipped_weapon.passive != 'none': p_list.append(p.equipped_weapon.passive.title())
            if p.equipped_weapon.p_passive != 'none': p_list.append(p.equipped_weapon.p_passive.title())
            if p.equipped_weapon.u_passive != 'none': p_list.append(p.equipped_weapon.u_passive.title())
            if p_list: passives.append(f"**Weapon:** {', '.join(p_list)}")

        # Armor
        if p.equipped_armor and p.equipped_armor.passive != 'none':
            passives.append(f"**Armor:** {p.equipped_armor.passive.title()}")

        # Accessory
        if p.equipped_accessory and p.equipped_accessory.passive != 'none':
            lvl = p.equipped_accessory.passive_lvl
            passives.append(f"**Accessory:** {p.equipped_accessory.passive.title()} ({lvl})")

        # Glove
        if p.equipped_glove and p.equipped_glove.passive != 'none':
            lvl = p.equipped_glove.passive_lvl
            passives.append(f"**Glove:** {p.equipped_glove.passive.title()} ({lvl})")

        # Boot
        if p.equipped_boot and p.equipped_boot.passive != 'none':
            lvl = p.equipped_boot.passive_lvl
            passives.append(f"**Boot:** {p.equipped_boot.passive.title()} ({lvl})")

        # Helmet
        if p.equipped_helmet and p.equipped_helmet.passive != 'none':
            lvl = p.equipped_helmet.passive_lvl
            passives.append(f"**Helmet:** {p.equipped_helmet.passive.title()} ({lvl})")
        
        if passives:
            embed.add_field(name="__Active Passives__", value="\n".join(passives), inline=False)

        await interaction.response.send_message(embed=embed)
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


    @app_commands.command(name="passives", description="Spend passive points.")
    async def passives(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data): return
        if not await self.bot.check_is_active(interaction, user_id): return

        points = data[20]
        if points <= 0:
            return await interaction.response.send_message("You have no passive points to spend!", ephemeral=True)

        self.bot.state_manager.set_active(user_id, "passives")
        
        embed = discord.Embed(
            title="Allocate Passive Points",
            description=f"**Points Remaining:** {points}\n\nSelect a stat to upgrade.",
            color=0x00FF00
        )
        
        view = PassiveAllocateView(self.bot, user_id, data)
        view.message = await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Character(bot))