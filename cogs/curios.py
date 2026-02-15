import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.curios.views import CurioView
from core.curios.logic import CurioManager

class Curios(commands.Cog, name="curios"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="curios", description="Open your Curios for rewards.")
    async def curios(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        curio_count = existing_user[22] # Curios index
        if curio_count <= 0:
            return await interaction.response.send_message("You don't have any Curios!", ephemeral=True)

        # 2. State & View
        self.bot.state_manager.set_active(user_id, "curios")
        
        embed = discord.Embed(
            title="🎁 Curios",
            description=f"You have **{curio_count}** Curios.\nSelect an amount to open.",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://i.imgur.com/wKyTFzh.jpg") # Chest image

        view = CurioView(self.bot, user_id, server_id, curio_count)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="bulk_curios", description="Directly open multiple curios (Skip menu).")
    @app_commands.describe(amount="Amount to open")
    async def bulk_curios(self, interaction: Interaction, amount: int):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        
        owned = existing_user[22]
        if amount > owned:
            return await interaction.response.send_message(f"You only have {owned} Curios.", ephemeral=True)
        if amount <= 0:
            return await interaction.response.send_message("Invalid amount.", ephemeral=True)

        await interaction.response.defer()
        
        # Direct Logic Call
        result = await CurioManager.process_open(self.bot, user_id, server_id, amount)
        
        embed = discord.Embed(title=f"Opened {amount} Curios", color=discord.Color.green())
        summary_text = "\n".join([f"**{k}** x{v}" for k,v in result['summary'].items()])
        embed.description = summary_text
        
        await interaction.followup.send(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(Curios(bot))