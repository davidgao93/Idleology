from discord import Interaction, app_commands
from discord.ext import commands, tasks

from core.first_use import TutorialGateView
from core.nether_market.mechanics import NetherMarketMechanics
from core.nether_market.views import build_hub_view

_LEVEL_GATE = 10  # matches Trade's gate — both are player-vs-player economy systems


class NetherMarket(commands.Cog, name="nether_market"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.rotate_markets.is_running():
            self.bot.logger.info("Starting Nether Market hourly rotation task")
            self.rotate_markets.start()

    @tasks.loop(hours=1)
    async def rotate_markets(self):
        """Rolls a fresh rotation (3 active offers) for every server the bot is in."""
        try:
            rolled_count = 0
            for guild in self.bot.guilds:
                server_id = str(guild.id)
                rolled = NetherMarketMechanics.roll_rotation()
                await self.bot.database.nether_market.save_rotation(server_id, **rolled)
                rolled_count += 1
            if rolled_count:
                self.bot.logger.info(f"Nether Market: rotated {rolled_count} server(s)")
        except Exception:
            self.bot.logger.error("rotate_markets task error", exc_info=True)

    @rotate_markets.error
    async def rotate_markets_error(self, error):
        self.bot.logger.error(f"rotate_markets task crashed: {error}", exc_info=True)

    @app_commands.command(
        name="nether",
        description="Visit the Nether Market — buy/sell curiosities, browse targets, and plunder.",
    )
    async def nether(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if existing_user["level"] < _LEVEL_GATE:
            return await interaction.response.send_message(
                f"The Nether Market unlocks at Level {_LEVEL_GATE}.", ephemeral=True
            )
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "nether_market")

        async def _build():
            view = await build_hub_view(self.bot, user_id, server_id)
            return view.build_embed(), view

        if not await self.bot.database.tutorials.has_seen(user_id, "nether_market"):
            await self.bot.database.tutorials.mark_seen(user_id, "nether_market")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "nether_market", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(NetherMarket(bot))
