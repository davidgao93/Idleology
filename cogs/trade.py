import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.trade.views import TradeRootView

class Trade(commands.Cog, name="trade"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="trade", description="Open the trading menu with another player.")
    async def trade(self, interaction: Interaction, player: discord.User):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Basic Validations
        if player.id == interaction.user.id:
            return await interaction.response.send_message("You cannot trade with yourself.", ephemeral=True)
        if player.bot:
            return await interaction.response.send_message("Bots have no need for material possessions.", ephemeral=True)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        # Level Gate
        if existing_user[4] < 10:
            return await interaction.response.send_message("Trading unlocks at Level 10.", ephemeral=True)

        # 2. State & View
        self.bot.state_manager.set_active(user_id, "trade")
        
        embed = discord.Embed(
            title="🤝 Trade Request", 
            description=f"Initiating trade with {player.mention}...\nSelect a category below.",
            color=discord.Color.blue()
        )
        
        view = TradeRootView(self.bot, user_id, player, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

async def setup(bot) -> None:
    await bot.add_cog(Trade(bot))