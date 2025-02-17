import discord
import random
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from discord.ext.tasks import asyncio

class Skills(commands.Cog, name="skills"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.active_events = {}
        self.event_channel_id = 840020888602148914  # Store channel ID as a string

    @commands.hybrid_command(name="skills", description="Check your skills and resources.")
    async def skills(self, context: commands.Context):
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's guild. Please /register first.")
            return


        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)

        embed = discord.Embed(title=f"{existing_user[3]}'s Skills", color=0x00FF00)

        # Mining stats
        mining_fields = [
            f"**{mining_data[2].capitalize()}** Pickaxe" if mining_data[2] else "",
            f"Iron Ore: {mining_data[3]}" if mining_data[3] > 0 else "",
            f"Coal: {mining_data[4]}" if mining_data[4] > 0 else "",
            f"Gold Ore: {mining_data[5]}" if mining_data[5] > 0 else "",
            f"Platinum Ore: {mining_data[6]}" if mining_data[6] > 0 else "",
            f"Idea Ore: {mining_data[7]}" if mining_data[7] > 0 else "",
        ]

        # Filtering out empty fields
        mining_value = "\n".join(filter(None, mining_fields))

        embed.add_field(name="⛏️ Mining", value=mining_value or "No mining data available.", inline=False)

        # Fishing stats
        fishing_fields = [
            f"**{fishing_data[2].capitalize()}** Fishing Rod" if fishing_data[2] else "",
            f"Desiccated Fish Bones: {fishing_data[3]}" if fishing_data[3] > 0 else "",
            f"Regular Fish Bones: {fishing_data[4]}" if fishing_data[4] > 0 else "",
            f"Sturdy Fish Bones: {fishing_data[5]}" if fishing_data[5] > 0 else "",
            f"Reinforced Fish Bones: {fishing_data[6]}" if fishing_data[6] > 0 else "",
            f"Titanium Fish Bones: {fishing_data[7]}" if fishing_data[7] > 0 else "",
        ]

        # Filtering out empty fields
        fishing_value = "\n".join(filter(None, fishing_fields))

        embed.add_field(name="🎣 Fishing", value=fishing_value or "No fishing data available.", inline=False)

        # Woodcutting stats
        woodcutting_fields = [
            f"**{woodcutting_data[2].capitalize()}** Axe" if woodcutting_data[2] else "",
            f"Oak Logs: {woodcutting_data[3]}" if woodcutting_data[3] > 0 else "",
            f"Willow Logs: {woodcutting_data[4]}" if woodcutting_data[4] > 0 else "",
            f"Mahogany Logs: {woodcutting_data[5]}" if woodcutting_data[5] > 0 else "",
            f"Magic Logs: {woodcutting_data[6]}" if woodcutting_data[6] > 0 else "",
            f"Idea Logs: {woodcutting_data[7]}" if woodcutting_data[7] > 0 else "",
        ]

        # Filtering out empty fields
        woodcutting_value = "\n".join(filter(None, woodcutting_fields))

        embed.add_field(name="🪓 Woodcutting", value=woodcutting_value or "No woodcutting data available.", inline=False)

        message = await context.send(embed=embed)
        await asyncio.sleep(10)
        await message.delete()
    

    """ MINING SKILL """

    @commands.hybrid_command(name="mining", description="Check your mining status and resources.")
    async def mining(self, context: commands.Context):
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        # Fetch user mining data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's guild. Please /register first.")
            return

        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        if not mining_data:
            await context.send("You do not have mining data. Please start mining first.")
            return

        # Display current pickaxe tier and resources
        embed = discord.Embed(title="Mining", color=0x00FF00)
        mining_fields = [
            f"**{mining_data[2].capitalize()}** Pickaxe" if mining_data[2] else "",
            f"You can mine **iron** ore." if mining_data[2] == 'iron' else "",
            f"You can mine **iron** ore and **coal**." if mining_data[2] == 'steel' else "",
            f"You can mine **iron** ore, **coal**, and **gold** ore." if mining_data[2] == 'gold' else "",
            f"You can mine **iron** ore, **coal**, **gold** ore, and **platinum** ore." if mining_data[2] == 'platinum' else "",
            f"You can mine **all** ore types." if mining_data[2] == 'ideal' else "",
            f"Iron Ore: {mining_data[3]}" if mining_data[3] > 0 else "",
            f"Coal: {mining_data[4]}" if mining_data[4] > 0 else "",
            f"Gold Ore: {mining_data[5]}" if mining_data[5] > 0 else "",
            f"Platinum Ore: {mining_data[6]}" if mining_data[6] > 0 else "",
            f"Idea Ore: {mining_data[7]}" if mining_data[7] > 0 else "",
        ]

        # Filtering out empty fields
        mining_value = "\n".join(filter(None, mining_fields))

        embed.add_field(name="⛏️", value=mining_value or "No mining data available.", inline=False)

        message = await context.send(embed=embed)
        await self.offer_mining_upgrade(context, mining_data, embed, message)

    async def offer_mining_upgrade(self, context, mining_data, embed, message):
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]
        pickaxe_tier = mining_data[2]
        upgrade_requirements = self.get_mining_upgrade_requirements(pickaxe_tier)

        if not upgrade_requirements:
            print('Already at highest pickaxe tier, not offering an upgrade.')
            return  # Already at the highest tier
        print(f'player has {player_gp}')
        required_iron, required_coal, required_gold, required_platinum, required_gp = upgrade_requirements
        print(f'Required iron: {required_iron} | Required coal: {required_coal} '
              f'| Required gold: {required_gold} | Required plat: {required_platinum} | Required gp: {required_gp}')
        
        cost_fields = [
                f"Iron ore required: **{required_iron:,}**" if required_iron else "",
                f"Coal required: **{required_coal:,}**" if required_coal > 0 else "",
                f"Gold ore required: **{required_gold:,}**" if required_gold > 0 else "",
                f"Platinum ore required: **{required_platinum:,}**" if required_platinum > 0 else "",
                f"GP required: **{required_gp:,}**" if required_gp > 0 else "",
            ]
        cost_str = "\n".join(filter(None, cost_fields))
        embed.add_field(name="Next upgrade", value=cost_str or "No further upgrades possible.", inline=False)
        await message.edit(embed=embed)
        # Check if user can upgrade
        if (mining_data[3] >= required_iron and
            mining_data[4] >= required_coal and
            mining_data[5] >= required_gold and
            mining_data[6] >= required_platinum and
            player_gp >= required_gp):
            
            embed = discord.Embed(
                title=f"Upgrade available!",
                description=(f"Do you want to upgrade your {pickaxe_tier.title()} "
                             f"Pickaxe to {self.next_pickaxe_tier(pickaxe_tier).title()}?"),
                color=0xFFCC00
            )
            embed.add_field(name="Material costs", value=cost_str or "No further upgrades possible.", inline=False)
            message = await context.send(embed=embed)
            await message.add_reaction("✅")  # Confirm Upgrade
            await message.add_reaction("❌")  # Cancel Upgrade

            def check(reaction, user):
                return user == context.author and reaction.message.id == message.id

            try:
                reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                if str(reaction.emoji) == "✅":
                    # Upgrade the pickaxe
                    await self.upgrade_pickaxe(context.author.id, context.guild.id, pickaxe_tier, self.next_pickaxe_tier(pickaxe_tier))
                    await context.send(f"You have upgraded your pickaxe to {self.next_pickaxe_tier(pickaxe_tier).title()}!")
                else:
                    await context.send("Upgrade cancelled.")
            except asyncio.TimeoutError:
                await context.send("You took too long to respond. Upgrade cancelled.")

    async def upgrade_pickaxe(self, user_id, server_id, pickaxe_tier, new_pickaxe_tier):
        upgrade_requirements = self.get_mining_upgrade_requirements(pickaxe_tier)
        required_iron, required_coal, required_gold, required_platinum, required_gp = upgrade_requirements
        await self.bot.database.upgrade_pickaxe(user_id, server_id, 
                                                new_pickaxe_tier, 
                                                required_iron,
                                                required_coal,
                                                required_gold,
                                                required_platinum,
                                                required_gp)

    def get_mining_upgrade_requirements(self, pickaxe_tier):
        # Define upgrade requirements
        # iron, coal, gold, platinum, gp
        requirements = {
            'ideal': None,
            'iron': (100, 0, 0, 0, 1000),
            'steel': (200, 100, 0, 0, 5000),
            'gold': (300, 200, 100, 0, 10000),
            'platinum': (600, 400, 200, 100, 100000),
        }
        return requirements.get(pickaxe_tier)

    def next_pickaxe_tier(self, current_tier):
        tiers = ['iron', 'steel', 'gold', 'platinum', 'ideal']
        current_index = tiers.index(current_tier)
        next_index = current_index + 1
        return tiers[next_index] if next_index < len(tiers) else None
    

    """ WOODCUTTING SKILL """

    @commands.hybrid_command(name="woodcutting", description="Check your woodcutting status and resources.")
    async def woodcutting(self, context: commands.Context):
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's guild. Please /register first.")
            return
        
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
        if not woodcutting_data:
            await context.send("You do not have woodcutting data. Please start woodcutting first.")
            return

        # Display current axe tier and resources
        embed = discord.Embed(title="Woodcutting", color=0x00FF00)
        woodcutting_fields = [
            f"**{woodcutting_data[2].capitalize()}** Axe" if woodcutting_data[2] else "",
            f"You can chop **oak** trees." if woodcutting_data[2] == 'flimsy' else "",
            f"You can chop **oak** and **willow** trees." if woodcutting_data[2] == 'carved' else "",
            f"You can chop **oak**, **willow**, and **mahogany** trees." if woodcutting_data[2] == 'chopping' else "",
            f"You can chop **oak**, **willow**, **mahogany**, and **magic** trees." if woodcutting_data[2] == 'magic' else "",
            f"You can chop **all** tree types." if woodcutting_data[2] == 'felling' else "",
            f"Oak Logs: {woodcutting_data[3]}" if woodcutting_data[3] > 0 else "",
            f"Willow Logs: {woodcutting_data[4]}" if woodcutting_data[4] > 0 else "",
            f"Mahogany Logs: {woodcutting_data[5]}" if woodcutting_data[5] > 0 else "",
            f"Magic Logs: {woodcutting_data[6]}" if woodcutting_data[6] > 0 else "",
            f"Idea Logs: {woodcutting_data[7]}" if woodcutting_data[7] > 0 else "",
        ]

        woodcutting_value = "\n".join(filter(None, woodcutting_fields))
        embed.add_field(name="🪓", value=woodcutting_value or "No woodcutting data available.", inline=False)
        
        message = await context.send(embed=embed)
        await self.offer_wc_upgrade(context, woodcutting_data, embed, message)

    @commands.hybrid_command(name="wc", description="Check your woodcutting status and resources (alias).")
    async def wc(self, context: commands.Context, embed):
        await self.woodcutting(context)

    async def offer_wc_upgrade(self, context, wc_data, embed, message):
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]
        axe_tier = wc_data[2]
        upgrade_requirements = self.get_wc_upgrade_requirements(axe_tier)

        if not upgrade_requirements:
            print('Already at highest axe tier, not offering an upgrade.')
            return  # Already at the highest tier
        
        required_oak, required_willow, required_mahogany, required_magic, required_gp = upgrade_requirements
        cost_fields = [
            f"Oak logs required: **{required_oak:,}**" if required_oak else "",
            f"Willow logs required: **{required_willow:,}**" if required_willow > 0 else "",
            f"Mahogany logs required: **{required_mahogany:,}**" if required_mahogany > 0 else "",
            f"Magic logs required: **{required_magic:,}**" if required_magic > 0 else "",
            f"GP required: **{required_gp:,}**" if required_gp > 0 else "",
        ]
        cost_str = "\n".join(filter(None, cost_fields))
        embed.add_field(name="Next upgrade", value=cost_str or "No further upgrades possible.", inline=False)
        await message.edit(embed=embed)
        # Check if user can upgrade
        if (wc_data[3] >= required_oak and
            wc_data[4] >= required_willow and
            wc_data[5] >= required_mahogany and
            wc_data[6] >= required_magic and
            player_gp >= required_gp):
            
            embed = discord.Embed(
                title=f"Upgrade available!",
                description=(f"Do you want to upgrade your {axe_tier.title()} "
                             f"Axe to {self.next_axe_tier(axe_tier).title()}?"),
                color=0xFFCC00
            )
            embed.add_field(name="Material costs", value=cost_str or "No further upgrades possible.", inline=False)
            message = await context.send(embed=embed)
            await message.add_reaction("✅")  # Confirm Upgrade
            await message.add_reaction("❌")  # Cancel Upgrade

            def check(reaction, user):
                return user == context.author and reaction.message.id == message.id

            try:
                reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                
                if str(reaction.emoji) == "✅":
                    # Upgrade the axe
                    await self.upgrade_axe(context.author.id, context.guild.id, axe_tier, self.next_axe_tier(axe_tier))
                    await context.send(f"You have upgraded your axe to {self.next_axe_tier(axe_tier).title()}!")
                else:
                    await context.send("Upgrade cancelled.")
            except asyncio.TimeoutError:
                await context.send("You took too long to respond. Upgrade cancelled.")

    async def upgrade_axe(self, user_id, server_id, axe_tier, new_axe_tier):
        upgrade_requirements = self.get_wc_upgrade_requirements(axe_tier)
        required_oak, required_willow, required_mahogany, required_magic, required_gp = upgrade_requirements
        await self.bot.database.upgrade_axe(user_id, server_id, 
                                             new_axe_tier, 
                                             required_oak, 
                                             required_willow, 
                                             required_mahogany, 
                                             required_magic, 
                                             required_gp)

    def get_wc_upgrade_requirements(self, axe_tier):
        # Define upgrade requirements analogous to mining
        requirements = {
            'felling': None,
            'flimsy': (100, 0, 0, 0, 1000),
            'carved': (200, 100, 0, 0, 5000),
            'chopping': (300, 200, 100, 0, 10000),
            'magic': (600, 400, 200, 100, 100000),
        }
        return requirements.get(axe_tier)

    def next_axe_tier(self, current_tier):
        tiers = ['flimsy', 'carved', 'chopping', 'magic', 'felling']
        current_index = tiers.index(current_tier)
        next_index = current_index + 1
        return tiers[next_index] if next_index < len(tiers) else None



    """
    FISHING SKILL
    """
    @commands.hybrid_command(name="fishing", description="Check your fishing status and resources.")
    async def fishing(self, context: commands.Context):
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's guild. Please /register first.")
            return
        
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)
        if not fishing_data:
            await context.send("You do not have fishing data. Please start fishing first.")
            return

        # Display current fishing rod tier and resources
        embed = discord.Embed(title="Fishing", color=0x00FF00)
        fishing_fields = [
            f"**{fishing_data[2].capitalize()}** Fishing Rod" if fishing_data[2] else "",
            f"You can fish **minnows**." if fishing_data[2] == 'desiccated' else "",
            f"You can fish **minnows** and **sardines**." if fishing_data[2] == 'regular' else "",
            f"You can fish **minnows**, **sardines**, and **salmon**." if fishing_data[2] == 'sturdy' else "",
            f"You can fish **minnows**, **sardines**, **salmon**, and **sharks**." if fishing_data[2] == 'reinforced' else "",
            f"You can fish **all** fish types." if fishing_data[2] == 'titanium' else "",
            f"Fish grants their respective bones as materials.",
            f"Desiccated Fish Bones: {fishing_data[3]}" if fishing_data[3] > 0 else "",
            f"Regular Fish Bones: {fishing_data[4]}" if fishing_data[4] > 0 else "",
            f"Sturdy Fish Bones: {fishing_data[5]}" if fishing_data[5] > 0 else "",
            f"Reinforced Fish Bones: {fishing_data[6]}" if fishing_data[6] > 0 else "",
            f"Titanium Fish Bones: {fishing_data[7]}" if fishing_data[7] > 0 else "",
        ]

        fish_value = "\n".join(filter(None, fishing_fields))
        embed.add_field(name="🎣", value=fish_value or "No fishing data available.", inline=False)
        
        message = await context.send(embed=embed)
        await self.offer_fishing_upgrade(context, fishing_data, embed, message)

    async def offer_fishing_upgrade(self, context, fishing_data, embed, message):
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]
        fishing_rod_tier = fishing_data[2]
        upgrade_requirements = self.get_fishing_upgrade_requirements(fishing_rod_tier)

        if not upgrade_requirements:
            print('Already at highest fishing rod tier, not offering an upgrade.')
            return  # Already at the highest tier
        
        required_desiccated, required_regular, required_sturdy, required_reinforced, required_gp = upgrade_requirements
        cost_fields = [
                f"Desiccated Fish Bones required: **{required_desiccated:,}**" if required_desiccated else "",
                f"Regular Fish Bones required: **{required_regular:,}**" if required_regular > 0 else "",
                f"Sturdy Fish Bones required: **{required_sturdy:,}**" if required_sturdy > 0 else "",
                f"Reinforced Fish Bones required: **{required_reinforced:,}**" if required_reinforced > 0 else "",
                f"GP required: **{required_gp:,}**" if required_gp > 0 else "",
            ]
        cost_str = "\n".join(filter(None, cost_fields))
        embed.add_field(name="Next upgrade", value=cost_str or "No further upgrades possible.", inline=False)
        await message.edit(embed=embed)
        # Check if user can upgrade
        if (fishing_data[3] >= required_desiccated and
            fishing_data[4] >= required_regular and
            fishing_data[5] >= required_sturdy and
            fishing_data[6] >= required_reinforced and
            player_gp >= required_gp):
            
            embed = discord.Embed(
                title=f"Upgrade available!",
                description=(f"Do you want to upgrade your {fishing_rod_tier.title()} "
                             f"Fishing Rod to {self.next_fishing_rod_tier(fishing_rod_tier).title()}?"),
                color=0xFFCC00
            )
            embed.add_field(name="Material costs", value=cost_str or "No further upgrades possible.", inline=False)
            message = await context.send(embed=embed)
            await message.add_reaction("✅")  # Confirm Upgrade
            await message.add_reaction("❌")  # Cancel Upgrade

            def check(reaction, user):
                return user == context.author and reaction.message.id == message.id

            try:
                reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                
                if str(reaction.emoji) == "✅":
                    # Upgrade the fishing rod
                    await self.upgrade_fishing_rod(user_id, server_id, fishing_rod_tier, self.next_fishing_rod_tier(fishing_rod_tier))
                    await context.send(f"You have upgraded your fishing rod to {self.next_fishing_rod_tier(fishing_rod_tier).title()}!")
                else:
                    await context.send("Upgrade cancelled.")
            except asyncio.TimeoutError:
                await context.send("You took too long to respond. Upgrade cancelled.")

    async def upgrade_fishing_rod(self, user_id, server_id, fishing_rod_tier, new_fishing_rod_tier):
        upgrade_requirements = self.get_fishing_upgrade_requirements(fishing_rod_tier)
        required_desiccated, required_regular, required_sturdy, required_reinforced, required_gp = upgrade_requirements
        
        await self.bot.database.upgrade_fishing_rod(user_id, server_id, 
                                                     new_fishing_rod_tier, 
                                                     required_desiccated, 
                                                     required_regular,
                                                     required_sturdy, 
                                                     required_reinforced, 
                                                     required_gp)

    def get_fishing_upgrade_requirements(self, fishing_rod_tier):
        # Define upgrade requirements analogous to mining and woodcutting
        requirements = {
            'titanium': None,
            'desiccated': (100, 0, 0, 0, 1000),
            'regular': (200, 100, 0, 0, 5000),
            'sturdy': (300, 200, 100, 0, 10000),
            'reinforced': (600, 400, 200, 100, 50000),
        }
        return requirements.get(fishing_rod_tier)

    def next_fishing_rod_tier(self, current_tier):
        tiers = ['desiccated', 'regular', 'sturdy', 'reinforced', 'titanium']
        current_index = tiers.index(current_tier)
        next_index = current_index + 1
        return tiers[next_index] if next_index < len(tiers) else None


    """
    SCHEDULED TASKS HERE
    MODIFY AMOUNTS OF RESOURCES GRANTED
    """
    
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.schedule_skills.is_running():
            self.schedule_skills.start()
        
        if not self.random_event.is_running():
            self.random_event.start()
    
    @tasks.loop(hours=1)
    #@tasks.loop(seconds=60)
    async def schedule_skills(self):
        # Get users with mining skills
        mining_users = await self.bot.database.fetch_users_with_mining()
        for user_id, server_id in mining_users:
            mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
            if mining_data:
                resources = await self.gather_mining_resources(mining_data[2])  # fetching pickaxe tier
                # print(f'Granting {user_id} with mining {resources}')
                await self.bot.database.update_mining_resources(user_id, server_id, resources)

        # Get users with fishing skills
        fishing_users = await self.bot.database.fetch_users_with_fishing()
        for user_id, server_id in fishing_users:
            fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)
            if fishing_data:
                resources = await self.gather_fishing_resources(fishing_data[2])  # fetching fishing rod
                # print(f'Granting {user_id} with fishing {resources}')
                await self.bot.database.update_fishing_resources(user_id, server_id, resources)

        # Get users with woodcutting skills
        woodcutting_users = await self.bot.database.fetch_users_with_woodcutting()
        for user_id, server_id in woodcutting_users:
            woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
            if woodcutting_data:
                resources = await self.gather_woodcutting_resources(woodcutting_data[2])  # fetching axe type
                # print(f'Granting {user_id} with woodcutting {resources}')
                await self.bot.database.update_woodcutting_resources(user_id, server_id, resources)


    async def gather_mining_resources(self, pickaxe_tier):
        # Define the resource ranges for each tier of pickaxe
        resources = {
            'iron': {
                'iron': (3, 5),     # Iron pickaxe: random 1-3
                'steel': (4, 7),    # Steel pickaxe: random 2-4
                'gold': (5, 8),     # Gold pickaxe: random 3-5
                'platinum': (6, 10),  # Platinum pickaxe: random 4-7
                'ideal': (7, 12)    # Ideal pickaxe: random 5-8
            },
            'coal': {
                'iron': (0, 0),     # Iron pickaxe: cannot mine coal
                'steel': (3, 5),    # Steel pickaxe: random 0-1
                'gold': (4, 7),     # Gold pickaxe: random 1-3
                'platinum': (5, 8), # Platinum pickaxe: random 3-6
                'ideal': (6, 10)     # Ideal pickaxe: random 5-8
            },
            'gold': {
                'iron': (0, 0),     # Iron pickaxe: cannot mine gold
                'steel': (0, 0),    # Steel pickaxe: cannot mine gold
                'gold': (3, 5),     # Gold pickaxe: random 0-1
                'platinum': (4, 7), # Platinum pickaxe: random 1-3
                'ideal': (5, 8)     # Ideal pickaxe: random 3-5
            },
            'platinum': {
                'iron': (0, 0),     # Iron pickaxe: cannot mine platinum
                'steel': (0, 0),    # Steel pickaxe: cannot mine platinum
                'gold': (0, 0),     # Gold pickaxe: cannot mine platinum
                'platinum': (3, 5), # Platinum pickaxe: random 0-1
                'ideal': (4, 7)     # Ideal pickaxe: random 1-3
            },
            'idea': {
                'iron': (0, 0),     # Iron pickaxe: cannot mine idea
                'steel': (0, 0),    # Steel pickaxe: cannot mine idea
                'gold': (0, 0),     # Gold pickaxe: cannot mine idea
                'platinum': (0, 0), # Platinum pickaxe: cannot mine idea
                'ideal': (3, 5)     # Ideal pickaxe: random 0-1
            }
        }

        # Gather resources based on the pickaxe tier
        return {
            'iron': random.randint(*resources['iron'][pickaxe_tier]),
            'coal': random.randint(*resources['coal'][pickaxe_tier]),
            'gold': random.randint(*resources['gold'][pickaxe_tier]),
            'platinum': random.randint(*resources['platinum'][pickaxe_tier]),
            'idea': random.randint(*resources['idea'][pickaxe_tier])
        }

    async def gather_fishing_resources(self, fishing_rod):
        # Define the fish ranges for each type of fishing rod
        fish = {
            'desiccated': {
                'desiccated': (3, 5),  # Desiccated rod: random 1-3
                'regular': (4, 7),      # Regular rod: 2-4 desiccated fish
                'sturdy': (5, 8),       # Sturdy rod: 3-5 desiccated fish
                'reinforced': (6, 10),   # Reinforced rod:  4-7 desiccated fish
                'titanium': (7, 12)      # Titanium rod: 5-8  desiccated fish
            },
            'regular': {
                'desiccated': (0, 0),   # Desiccated rod: cannot catch regular fish
                'regular': (3, 5),       # Regular rod: random 1-3
                'sturdy': (4, 7),        # Sturdy rod: random 1-5
                'reinforced': (5, 8),    # Reinforced rod: random 3-6
                'titanium': (6, 10)       # Titanium rod: random 5-8
            },
            'sturdy': {
                'desiccated': (0, 0),   # Desiccated rod: cannot catch sturdy fish
                'regular': (0, 0),       # Regular rod: cannot catch sturdy fish
                'sturdy': (3, 5),        # Sturdy rod: random 0-1
                'reinforced': (4, 7),    # Reinforced rod: random 1-3
                'titanium': (5, 8)       # Titanium rod: random 3-6
            },
            'reinforced': {
                'desiccated': (0, 0),   # Desiccated rod: cannot catch reinforced fish
                'regular': (0, 0),       # Regular rod: cannot catch reinforced fish
                'sturdy': (0, 0),        # Sturdy rod: cannot catch reinforced fish
                'reinforced': (3, 5),    # Reinforced rod: random 0-1
                'titanium': (4, 7)       # Titanium rod: random 1-3
            },
            'titanium': {
                'desiccated': (0, 0),   # Desiccated rod: cannot catch titanium fish
                'regular': (0, 0),       # Regular rod: cannot catch titanium fish
                'sturdy': (0, 0),        # Sturdy rod: cannot catch titanium fish
                'reinforced': (0, 0),    # Reinforced rod: cannot catch titanium fish
                'titanium': (3, 5)       # Titanium rod: random 0-1
            }
        }

        # Gather fish based on the fishing rod tier
        return {
            'desiccated': random.randint(*fish['desiccated'][fishing_rod]),
            'regular': random.randint(*fish['regular'][fishing_rod]),
            'sturdy': random.randint(*fish['sturdy'][fishing_rod]),
            'reinforced': random.randint(*fish['reinforced'][fishing_rod]),
            'titanium': random.randint(*fish['titanium'][fishing_rod])
        }
    
    async def gather_woodcutting_resources(self, axe_type):
        # Define the wood ranges for each type of axe
        wood = {
            'oak': {
                'flimsy': (3, 5),     # Flimsy axe: random 1-3
                'carved': (4, 7),     # Carved axe: random 1-3
                'chopping': (5, 8),   # Chopping axe: random 2-4
                'magic': (6, 10),      # Magic axe: random 3-5
                'felling': (7, 12)     # Felling axe: random 4-6
            },
            'willow': {
                'flimsy': (0, 0),     # Flimsy axe: cannot cut willow
                'carved': (3, 5),     # Carved axe: random 0-1
                'chopping': (4, 7),    # Chopping axe: random 1-3
                'magic': (5, 8),      # Magic axe: random 2-4
                'felling': (6, 10)     # Felling axe: random 3-6
            },
            'mahogany': {
                'flimsy': (0, 0),     # Flimsy axe: cannot cut mahogany
                'carved': (0, 0),     # Carved axe: cannot cut mahogany
                'chopping': (3, 5),    # Chopping axe: random 0-1
                'magic': (4, 7),      # Magic axe: random 1-3
                'felling': (5, 8)     # Felling axe: random 3-5
            },
            'magic': {
                'flimsy': (0, 0),     # Flimsy axe: cannot cut magic trees
                'carved': (0, 0),     # Carved axe: cannot cut magic trees
                'chopping': (0, 0),    # Chopping axe: cannot cut magic trees
                'magic': (3, 5),      # Magic axe: random 0-1
                'felling': (4, 7)     # Felling axe: random 1-3
            },
            'idea': {
                'flimsy': (0, 0),     # Flimsy axe: cannot cut idea trees
                'carved': (0, 0),     # Carved axe: cannot cut idea trees
                'chopping': (0, 0),    # Chopping axe: cannot cut idea trees
                'magic': (0, 0),      # Magic axe: cannot cut idea trees
                'felling': (3, 5)     # Felling axe: random 0-1
            }
        }

        # Gather wood based on the axe type
        return {
            'oak': random.randint(*wood['oak'][axe_type]),
            'willow': random.randint(*wood['willow'][axe_type]),
            'mahogany': random.randint(*wood['mahogany'][axe_type]),
            'magic': random.randint(*wood['magic'][axe_type]),
            'idea': random.randint(*wood['idea'][axe_type])
        }

    '''
    HANDLE RANDOM EVENTS
    '''
    @tasks.loop(minutes=30)
    async def random_event(self):
        """Trigger a random event with a 50% chance every half hour."""
        if random.random() <= 0.5:  # 50% chance
            event_type = random.choice(["leprechaun", "meteorite", "dryad", "high_tide"])
            print(f'random event {event_type} triggered')
            if self.event_channel_id:  # Ensure the channel ID exists
                if self.event_channel_id:  # Ensure the channel ID exists
                    guild = self.bot.get_guild(431301983475990528)  # Replace `guild_id` with the actual guild ID
                    if guild:
                        channel = guild.get_channel(self.event_channel_id)
                        print(f'random in {self.event_channel_id} for {channel}')
                        if channel:
                            await self.trigger_event(channel, event_type)
                            print(f'channel exists, triggered {event_type}')
                        else:
                            print(f'failed to get channel info')
                    else:
                        print('Bot is not in the specified guild.')
            else:
                print('could not establish channel')
        else:
            print('no random event for now')

    async def trigger_event(self, channel: discord.TextChannel, event_type: str):
        """Trigger the specified random event and create an embed message."""
        event_info = {
            "leprechaun": {
                "emoji": "☘️",
                "image": "https://cdn.discordapp.com/attachments/699690514051629089/1340082810769379419/leprechaun.png?ex=67b110df&is=67afbf5f&hm=45f828311a51e80225c3033c0ce7b8458a1a36b68a55659836bfbc75a2c63d87&",
                "description": "A leprechaun appears! React with ☘️ to reach into his pot of gold!"
            },
            "meteorite": {
                "emoji": "⛏️",
                "image": "https://cdn.discordapp.com/attachments/699690514051629089/1340082809104236615/asteroid.png?ex=67b110df&is=67afbf5f&hm=5fb6c03a54c2d9af07bc7f27f88730c7152948577c8d175aa1d0ec173ab8f616&",
                "description": "A meteorite crashes nearby! ⛏️ to mine!"
            },
            "dryad": {
                "emoji": "🪓",
                "image": "https://cdn.discordapp.com/attachments/699690514051629089/1340082809926193223/dryad.png?ex=67b110df&is=67afbf5f&hm=733736eb3ac9e88c69adb47556d056ca44268f9cf9400d70e2ffd344bd8a2f48&",
                "description": "A giant dryad appears! 🪓 to receive his blessing!"
            },
            "high_tide": {
                "emoji": "🎣",
                "image": "https://cdn.discordapp.com/attachments/699690514051629089/1340082811465371679/tide.png?ex=67b110df&is=67afbf5f&hm=b4f15d92997efe9704cf2ffdacbdf496952c969103c927ba19703b974084d248&",
                "description": "The High Tide rises! 🎣 to gather fish resources!"
            }
        }

        event_data = event_info[event_type]  # Get the data for the current event
        embed = discord.Embed(
            title="Random Event",
            description=event_data["description"],
            color=0xFFD700
        )
        embed.set_image(url=event_data["image"])
        
        message = await channel.send(embed=embed)  # Use context to send the embed

        # Add reaction for claiming event
        await message.add_reaction(event_data["emoji"])

        self.active_events[message.id] = {
            "event_type": event_type,
            "claimed_users": set(),  # Track users who have claimed the event
            "emoji": event_data["emoji"]  # Store the emoji used for claiming
        }

        # Wait for 5 minutes before expiration
        await asyncio.sleep(300)  # 5 minutes
        await message.delete()  # Delete the message after 5 minutes
        del self.active_events[message.id]  # Clear the event entry when it expires.


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reaction additions for claiming random events."""
        if payload.message_id in self.active_events:
            user_id = payload.user_id
            server_id = payload.guild_id
            event_data = self.active_events[payload.message_id]  # Get the event data

            if user_id != self.bot.user.id:  # Ignore the bot's own reactions
                if user_id not in event_data["claimed_users"]:
                    event_type = event_data["event_type"]

                    # Fetch the channel using channel_id from payload
                    channel = self.bot.get_channel(payload.channel_id)
                    if channel is None:
                        print(f"Cannot find channel with ID: {payload.channel_id}")
                        return

                    # Fetch message using the message_id from payload
                    try:
                        message = await channel.fetch_message(payload.message_id)
                    except discord.NotFound:
                        print(f"Message not found: {payload.message_id}")
                        return

                    existing_user = await self.bot.database.fetch_user(user_id, server_id)
                    if not existing_user:
                        print("Unregistered, not proceeding.")
                        return
                        

                    if event_type == "leprechaun" and str(payload.emoji) == event_data["emoji"]:
                        gold_amount = random.randint(1000, 2000)
                        await self.bot.database.add_gold(user_id, gold_amount)
                        event_data["claimed_users"].add(user_id)

                        # Update the message embed
                        message = await channel.fetch_message(payload.message_id)
                        embed = message.embeds[0]
                        embed.add_field(name="Claimed Reward", 
                                        value=f"{existing_user[3]} has grabbed **{gold_amount:,} gold** from the pot!", 
                                        inline=False)
                        await message.edit(embed=embed)

                    elif event_type == "meteorite" and str(payload.emoji) == event_data["emoji"]:
                        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
                        if mining_data:
                            resources = await self.gather_mining_resources(mining_data[2])  # Use the mining tier from mining_data
                            await self.bot.database.update_mining_resources(user_id, server_id, resources)
                            event_data["claimed_users"].add(user_id)

                            message = await channel.fetch_message(payload.message_id)
                            embed = message.embeds[0]
                            embed.add_field(name="Claimed Reward", 
                                            value=f"{existing_user[3]} has gathered resources from the meteorite!", 
                                            inline=False)
                            await message.edit(embed=embed)

                    elif event_type == "dryad" and str(payload.emoji) == event_data["emoji"]:
                        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
                        if woodcutting_data:
                            resources = await self.gather_woodcutting_resources(woodcutting_data[2])  # Use the axe tier from woodcutting_data
                            await self.bot.database.update_woodcutting_resources(user_id, server_id, resources)
                            event_data["claimed_users"].add(user_id)

                            message = await channel.fetch_message(payload.message_id)
                            embed = message.embeds[0]
                            embed.add_field(name="Claimed Reward", 
                                            value=f"{existing_user[3]} has received the dryad's blessing!", 
                                            inline=False)
                            await message.edit(embed=embed)

                    elif event_type == "high_tide" and str(payload.emoji) == event_data["emoji"]:
                        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)
                        if fishing_data:
                            resources = await self.gather_fishing_resources(fishing_data[2])  # Use the fishing rod tier from fishing_data
                            await self.bot.database.update_fishing_resources(user_id, server_id, resources)
                            event_data["claimed_users"].add(user_id)

                            embed = await channel.fetch_message(payload.message_id)
                            embed = message.embeds[0]
                            embed.add_field(name="Claimed Reward", 
                                            value=f"{existing_user[3]} has gathered fish from the high tide!",
                                              inline=False)
                            await message.edit(embed=embed)

                    # If the user has already claimed, update the message to reflect this
                    if user_id in event_data["claimed_users"]:
                        print('Already claimed, ignoring')
                       # await payload.channel.send(f"{existing_user[3]} has already claimed this bounty!")

async def setup(bot) -> None:
    await bot.add_cog(Skills(bot))
