import discord
import random
from discord.ext import commands, tasks
from discord import app_commands, Interaction
from core.events.views import RandomEventView

class Events(commands.Cog, name="events"):
    def __init__(self, bot):
        self.bot = bot
        self.event_definitions = {
            "leprechaun": {
                "image": "https://i.imgur.com/fZTCt8S.png",
                "desc": "A leprechaun appears! Click the button to reach into his... uh..."
            },
            "meteorite": {
                "image": "https://i.imgur.com/QeBaabP.png",
                "desc": "A meteorite crashes nearby! Miners required!"
            },
            "dryad": {
                "image": "https://i.imgur.com/8CQGsmf.png",
                "desc": "A giant dryad appears! Foresters required!"
            },
            "high_tide": {
                "image": "https://i.imgur.com/cgl89Ei.png",
                "desc": "The High Tide rises! Trawlers required!"
            }
        }

    async def cog_load(self):
        pass
        # self.random_event_loop.start()

    async def cog_unload(self):
        self.random_event_loop.cancel()

    @app_commands.command(name="setup_events", description="Set the channel for random events.")
    @commands.has_permissions(administrator=True)
    async def setup_events(self, interaction: Interaction):
        """Sets the current channel as the event spawn location."""
        guild_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        
        await self.bot.database.settings.set_event_channel(guild_id, channel_id)
        
        await interaction.response.send_message(
            f"✅ Random events will now spawn in {interaction.channel.mention}.", 
            ephemeral=True
        )

    @tasks.loop(minutes=120)
    async def random_event_loop(self):
        """Triggers a random event in all configured channels."""
        # 50% chance to trigger globally per cycle (or you can make this per-guild logic)
        if random.random() > 0.5:
            return

        event_type = random.choice(list(self.event_definitions.keys()))
        event_data = self.event_definitions[event_type]
        
        # 1. Fetch all configured channels from DB
        configs = await self.bot.database.settings.get_all_event_channels()
        
        self.bot.logger.info(f"Triggering {event_type} for {len(configs)} guilds.")

        for guild_id, channel_id in configs:
            try:
                # 2. Resolve Channel
                # Note: We use fetch_channel or get_channel depending on cache reliability
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(int(channel_id))
                    except (discord.NotFound, discord.Forbidden):
                        self.bot.logger.warning(f"Could not access event channel {channel_id} in guild {guild_id}")
                        continue

                # 3. Create UI
                embed = discord.Embed(
                    title="🌟 Random Event!",
                    description=event_data["desc"],
                    color=0xFFD700
                )
                embed.set_image(url=event_data["image"])
                
                view = RandomEventView(self.bot, event_type)
                
                # 4. Send
                message = await channel.send(embed=embed, view=view)
                view.message = message # Link message to view for updates

            except Exception as e:
                self.bot.logger.error(f"Error sending event to guild {guild_id}: {e}")

    @random_event_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Events(bot))