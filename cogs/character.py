import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, Message
from core.items.factory import load_player
from core.character.views import PassiveAllocateView
from core.character.profile_hub import ProfileBuilder, ProfileHubView
from core.character.leaderboard_views import LeaderboardHubView

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


    @app_commands.command(name="card", description="View your adventurer license.")
    async def card(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data): return

        view = ProfileHubView(self.bot, user_id, server_id, "card")
        embed = await ProfileBuilder.build_card(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="stats", description="Detailed character sheet.")
    async def stats(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data): return

        view = ProfileHubView(self.bot, user_id, server_id, "stats")
        embed = await ProfileBuilder.build_stats(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
    '''
    
    MISCELLANEOUS COMMANDS
    
    '''

    @app_commands.command(name="leaderboard", description="View the server hiscores.")
    async def leaderboard(self, interaction: Interaction) -> None:
        view = LeaderboardHubView(self.bot, "levels")
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)


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