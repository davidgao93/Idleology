import discord
from discord import Interaction, app_commands
from discord.ext import commands, tasks

from core.character.leaderboard_views import LeaderboardHubView
from core.character.profile_hub import ProfileHubView
from core.character.profile_ui import ProfileBuilder
from core.character.views import StatInvestView
from core.combat.views.views import StatPackagePicker
from core.items.factory import load_player

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
18	Created at
19	Refinement runes
20	Passive Points
21	Potential runes
22	Curios
23	Curios purchased
24	Last Combat
25	Dragon Key
26	Angel Key
27	Imbue runes
28	Soul Cores
29	Void Fragments
30	Void Keys
31	Shatter Runes
32	Partnership Runes
33	Last Companion Collect Time
34	Balance Fragment
35	Magma Core
36	Life Root
37	Spirit Shard
38	Doors Enabled
39	Celestial Stone
40	Void Crystal
41	Infernal Cinder
42	Bound Crystal
43	Codex Fragments
44	Codex Pages
45	Codex Rerolls
46	Highest Ascension Stage
47	Spirit Stones
48	EXP Protection
49	Antique Tome
50	Pinnacle Key
51	Highest Ascension Floor
52	Prestige Border
53	Prestige Title
54	Prestige Display Name
55	Prestige Flair
56	Prestige Death Message
57	Prestige Monument
58	Curio Puzzle Boxes
"""


class Character(commands.Cog, name="character"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.active_users = {}  # Dictionary to track active users

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_hp.is_running():
            self.bot.logger.info("Starting player health regen task")
            self.check_hp.start()
        if not self.check_stamina.is_running():
            self.bot.logger.info("Starting combat stamina regen task")
            self.check_stamina.start()

    @tasks.loop(minutes=5)
    async def check_stamina(self):
        """Grant 1 combat stamina per hour to all users below the cap of 10."""
        updated = await self.bot.database.users.regen_stamina_tick()
        if updated:
            self.bot.logger.info(f"Stamina regen: granted +1 to {updated} user(s)")

    @tasks.loop(minutes=15)
    async def check_hp(self):
        """Check and increment current_hp for all users every 15m."""
        users = await self.bot.database.users.get_all()
        self.bot.logger.info("Healing all users")
        for user in users:
            user_id = user["user_id"]
            current_hp = user["current_hp"]
            player = await load_player(user_id, user, self.bot.database)
            max_hp = player.total_max_hp
            scaling = int(max_hp / 30)
            if current_hp < max_hp:
                new_hp = min(current_hp + 1 + scaling, max_hp)
                await self.bot.database.users.update_hp(user_id, new_hp)
        await self.bot.database.users.connection.commit()

    @app_commands.command(name="card", description="View your adventurer license.")
    async def card(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data):
            return

        view = ProfileHubView(self.bot, user_id, server_id, "card")
        embed = await ProfileBuilder.build_card(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="sheet", description="Detailed character sheet.")
    async def sheet(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data):
            return

        view = ProfileHubView(self.bot, user_id, server_id, "stats")
        embed = await ProfileBuilder.build_stats(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="stats", description="View your character stats.")
    async def stats(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data):
            return

        view = ProfileHubView(self.bot, user_id, server_id, "stats")
        embed = await ProfileBuilder.build_stats(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="allocate_stats",
        description="Spend pending stat packages and passive points; recover packages lost on disconnect.",
    )
    async def allocate_stats(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # Check for unspent level-up stat packages first.  These are persisted to DB
        # so a server disconnect during combat will never permanently lose them.
        pending_packages = await self.bot.database.users.get_pending_packages(
            user_id, server_id
        )
        if pending_packages:
            self.bot.state_manager.set_active(user_id, "allocate_stats")
            player = await load_player(user_id, data, self.bot.database)

            async def _on_packages_done(msg):
                done_embed = discord.Embed(
                    title="✅ Stat Packages Applied!",
                    description=(
                        "Your base stats have been updated.\n\n"
                        "Run `/allocate_stats` again to spend any passive points you've earned."
                    ),
                    color=discord.Color.green(),
                )
                self.bot.state_manager.clear_active(user_id)
                await msg.edit(embed=done_embed, view=None)

            picker = StatPackagePicker(
                self.bot,
                user_id,
                server_id,
                player,
                pending_packages,
                on_done=_on_packages_done,
            )
            await interaction.response.send_message(
                embed=picker.build_embed(), view=picker
            )
            picker.message = await interaction.original_response()
            return

        # No pending packages — show passive-point allocation as normal.
        self.bot.state_manager.set_active(user_id, "allocate_stats")
        view = StatInvestView(self.bot, user_id, server_id, data)
        await interaction.response.send_message(
            embed=view.build_embed(), view=view
        )
        view.message = await interaction.original_response()

    """
    
    MISCELLANEOUS COMMANDS
    
    """

    @app_commands.command(name="leaderboard", description="View the server hiscores.")
    async def leaderboard(self, interaction: Interaction) -> None:
        view = LeaderboardHubView(self.bot, str(interaction.user.id), "levels")
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="passives", description="View your active passives.")
    async def passives(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data):
            return

        view = ProfileHubView(self.bot, user_id, server_id, "passives")
        embed = await ProfileBuilder.build_passives(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Character(bot))
