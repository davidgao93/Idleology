import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.pvp.views import ChallengeView

class Duels(commands.Cog, name="duels"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="duel", description="Challenge another player to a gold duel.")
    @app_commands.describe(amount="Amount of gold to wager")
    async def duel(self, interaction: Interaction, opponent: discord.Member, amount: int):
        challenger_id = str(interaction.user.id)
        target_id = str(opponent.id)
        server_id = str(interaction.guild.id)

        # 1. Basic Checks
        if opponent.bot or challenger_id == target_id:
            return await interaction.response.send_message("You cannot duel bots or yourself.", ephemeral=True)
        
        if amount <= 0:
            return await interaction.response.send_message("Wager must be positive.", ephemeral=True)

        # 2. State & Registration Checks
        # Check Challenger
        c_data = await self.bot.database.users.get(challenger_id, server_id)
        if not await self.bot.check_user_registered(interaction, c_data): return
        if not await self.bot.check_is_active(interaction, challenger_id): return

        # Check Target (Silent check for reg, verify funds later)
        t_data = await self.bot.database.users.get(target_id, server_id)
        if not t_data:
            return await interaction.response.send_message(f"{opponent.display_name} is not registered.", ephemeral=True)

        # 3. Gold Checks
        if c_data[6] < amount:
            return await interaction.response.send_message("You don't have enough gold!", ephemeral=True)
        
        if t_data[6] < amount:
            return await interaction.response.send_message(f"{opponent.display_name} doesn't have enough gold!", ephemeral=True)

        # 4. Initiate Challenge
        self.bot.state_manager.set_active(challenger_id, "duel_challenge")
        
        embed = discord.Embed(
            title="⚔️ Duel Challenge!",
            description=f"{interaction.user.mention} challenges {opponent.mention} to a duel for **{amount:,} gold**!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://i.imgur.com/z20wfJO.jpeg")
        
        view = ChallengeView(self.bot, challenger_id, target_id, amount)
        await interaction.response.send_message(content=opponent.mention, embed=embed, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Duels(bot))