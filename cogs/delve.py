import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.minigames.mechanics import DelveMechanics, DelveState
from core.minigames.delve_views import DelveView, DelveUpgradeView

class Delve(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="delve", description="Start a tactical mining expedition.")
    async def delve(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Checks
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        # 2. Get Mining Tool
        mining_data = await self.bot.database.skills.get_data(user_id, server_id, 'mining')
        pickaxe = mining_data[2] if mining_data else 'iron'

        # 3. Get Delve Stats
        delve_stats = await self.bot.database.delve.get_profile(user_id, server_id)

        # 4. Initialize State
        state = DelveState(
            max_fuel=DelveMechanics.get_max_fuel(delve_stats['fuel_lvl']),
            current_fuel=DelveMechanics.get_max_fuel(delve_stats['fuel_lvl']),
            pickaxe_tier=pickaxe
        )

        self.bot.state_manager.set_active(user_id, "delve")
        
        # 5. Launch View
        view = DelveView(self.bot, user_id, server_id, state, delve_stats)
        embed = view.build_embed("Systems online. Ready to drill.")
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="delve_shop", description="Upgrade your delve equipment.")
    async def delve_shop(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return

        delve_stats = await self.bot.database.delve.get_profile(user_id, server_id)
        
        embed = discord.Embed(title="🛠️ Delve Workshop", color=discord.Color.dark_orange())
        embed.description = f"💎 **Obsidian Shards:** {delve_stats['shards']}"
        embed.add_field(name="Upgrades", value="Use Shards to improve your specialized equipment.", inline=False)
        
        view = DelveUpgradeView(self.bot, user_id, server_id, delve_stats)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Delve(bot))