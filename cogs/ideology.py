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
        description="Spread your ideology to gain more followers."
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
                    await interaction.response.send_message(f"You need to wait **{remaining_time.seconds // 3600} hours"
                                       f" and {(remaining_time.seconds // 60) % 60} minutes** before propagating"
                                        f" **{user_ideology}** again.")
                    return
        except (ValueError, TypeError):
            await interaction.response.send_message("There was an error with your last propagate time. "
                              "Please contact the admin.")
            return

        # Calculate new follower count
        rolls_count = max(1, followers_count // 100) + 1
        total_sum = sum(random.randint(1, 20) for _ in range(rolls_count))
        new_followers_count = min(1000, followers_count + total_sum)
        # print(f"{rolls_count} number of d20's rolled with a total sum of {total_sum}")
        ascension = False
        if new_followers_count >= 1000:
            await self.bot.database.increase_ascension_level(user_id)
            new_followers_count = await self.bot.database.count_followers(user_ideology)  # Fetch user_ids of followers
            ascension = True
            await interaction.response.send_message(f"{user_ideology} has spread far and wide!\n"
                                f"As an evangelist you have done well, you gain an ascension level.\n"
                                f"Your adventure should be easier now.\n"
                                f"{user_ideology}'s follower count has been reset.")

        await self.bot.database.update_followers_count(user_ideology, new_followers_count) 
        await self.bot.database.update_propagate_time(user_id)
        if not ascension:
            await interaction.response.send_message(f"You advocate for {user_ideology} and it spreads. "
                                f"New follower count: **{new_followers_count}**.")

async def setup(bot) -> None:
    await bot.add_cog(Ideology(bot))
