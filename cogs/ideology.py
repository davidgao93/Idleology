from discord.ext import commands
from discord.ext.commands import Context
import discord
import random
from datetime import datetime, timedelta
from discord import app_commands, Interaction, Message

class Ideology(commands.Cog, name="ideology"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ideology",
        description="Current list of ideologies and follower counts.",
    )
    async def ideology(self, interaction: Interaction) -> None:
        """
        Gets a list of ideologies and their follower counts.
        """
        server_id = str(interaction.guild.id)
        ideologies = await self.bot.database.fetch_ideologies(server_id)

        if not ideologies:
            await interaction.response.send_message("No ideologies found for this server.")
            return

        # Create a list of tuples to store (ideology, followers_count)
        ideology_counts = []

        # Fetch the follower count for each ideology
        for ideology in ideologies:
            followers_count = await self.bot.database.fetch_followers(ideology)
            ideology_counts.append((ideology, followers_count))

        # Sort the list by follower counts in descending order
        ideology_counts.sort(key=lambda x: x[1], reverse=True)

        # Prepare the embed message
        ideology_info = ""
        for ideology, followers_count in ideology_counts:
            ideology_info += f"**{ideology}**: {followers_count} followers\n"

        embed = discord.Embed(
            title="Ideologies and Follower Counts",
            description=ideology_info,
            color=0x00FF00,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="propagate",
        description="Spread your ideology to gain more followers and collect their offerings."
    )
    async def propagate(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        user_ideology = existing_user[8]
        followers_count = await self.bot.database.fetch_followers(user_ideology)
        last_propagate_time = existing_user[14] 
        cooldown_duration = timedelta(hours=18)

        try:
            if last_propagate_time is not None:
                last_propagate_time_dt = datetime.fromisoformat(last_propagate_time)
                time_since_last_propagate = datetime.now() - last_propagate_time_dt
                if time_since_last_propagate < cooldown_duration:
                    remaining_time = cooldown_duration - time_since_last_propagate
                    await interaction.response.send_message(
                        f"You need to wait **{remaining_time.seconds // 3600} hours "
                        f"and {(remaining_time.seconds // 60) % 60} minutes** before propagating "
                        f"**{user_ideology}** again."
                    )
                    return
        except (ValueError, TypeError):
            await interaction.response.send_message(
                "There was an error with your last propagate time. Please contact the admin."
            )
            return

        # Calculate new follower count (exponential growth)
        base_followers = 10
        growth_factor = 1.5
        scaling_factor = 100
        if (followers_count > 1000):
            follower_increase = 100
        else:
            follower_increase = base_followers * (growth_factor ** (followers_count // scaling_factor))
        # Add random variation (±10%)
        variation = random.uniform(0.9, 1.1)
        follower_increase = int(follower_increase * variation)
        new_followers_count = followers_count + follower_increase

        # Calculate gold reward (linear)
        base_gold = 1000
        gold_per_follower = 50
        gold_reward = base_gold + (followers_count * gold_per_follower)

        # Update database
        self.bot.logger.info(f"Propogate {user_ideology}, awarding {user_id} with {gold_reward}")
        await self.bot.database.update_followers_count(user_ideology, new_followers_count)
        await self.bot.database.add_gold(user_id, gold_reward)
        await self.bot.database.update_propagate_time(user_id)

        # Send response
        await interaction.response.send_message(
            f"You advocate for **{user_ideology}** and it spreads!\n"
            f"New followers gained: **{follower_increase}** (Total: **{new_followers_count}**).\n"
            f"Gold collected from followers: **{gold_reward:,} GP**."
        )

async def setup(bot) -> None:
    await bot.add_cog(Ideology(bot))