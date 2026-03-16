import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.items.factory import load_player
from core.combat.dummy_engine import DummyEngine
from core.combat.views_uber import UberLobbyView

class Uber(commands.Cog, name="uber"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="uber", description="Challenge the pinnacle of power.")
    async def uber(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        
        # 2. Fetch Data
        player = await load_player(user_id, existing_user, self.bot.database)
        uber_data = await self.bot.database.uber.get_uber_progress(user_id, server_id)
        
        # 3. Simulate Readiness
        readiness_text = DummyEngine.assess_readiness(player, target="aphrodite_uber")

        # 4. Launch View
        view = UberLobbyView(self.bot, user_id, server_id, player, uber_data, readiness_text)
        embed = view.build_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Uber(bot))