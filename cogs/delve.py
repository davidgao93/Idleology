import discord
from discord.ext import commands
from discord import app_commands, Interaction
from core.minigames.mechanics import DelveMechanics, DelveState
from core.minigames.delve_views import DelveView, DelveUpgradeView, DelveEntryView

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

        # 2. Get Mining Tool & Delve Stats
        mining_data = await self.bot.database.skills.get_data(user_id, server_id, 'mining')
        pickaxe = mining_data[2] if mining_data else 'iron'
        delve_stats = await self.bot.database.delve.get_profile(user_id, server_id)

        # 3. Calculate Entry Cost
        entry_cost = DelveMechanics.get_entry_cost(delve_stats['fuel_lvl'])
        
        # Pre-check gold
        if existing_user[6] < entry_cost:
            return await interaction.response.send_message(
                f"You need **{entry_cost:,} Gold** to purchase a mining permit.", 
                ephemeral=True
            )

        self.bot.state_manager.set_active(user_id, "delve")

        # 4. Define Start Callback
        # This function is passed to the Entry View to run AFTER gold is paid
        async def start_game(inter: Interaction):
            state = DelveState(
                max_fuel=DelveMechanics.get_max_fuel(delve_stats['fuel_lvl']),
                current_fuel=DelveMechanics.get_max_fuel(delve_stats['fuel_lvl']),
                pickaxe_tier=pickaxe
            )
            
            view = DelveView(self.bot, user_id, server_id, state, delve_stats)
            embed = view.build_embed("Systems online. Permit verified.")
            
            await inter.response.edit_message(embed=embed, view=view)
            view.message = await inter.original_response()

        # 5. Show Entry View
        embed = discord.Embed(title="⛏️ Deep Delve Expedition", color=discord.Color.dark_grey())
        embed.description = (
            f"**Permit Cost:** {entry_cost:,} Gold\n"
            f"**Fuel Capacity:** {DelveMechanics.get_max_fuel(delve_stats['fuel_lvl'])}\n\n"
            "The Guild requires a permit for all deep earth operations.\n"
            "Deeper layers yield high rewards, but stability is critical.\n"
            "Once your fuel reaches 0, it's over, you lose it all.\n"
            "Extract before the mines consume you."
        )
        embed.set_thumbnail(url="https://i.imgur.com/qRyUGXU.png") 
        view = DelveEntryView(self.bot, user_id, server_id, entry_cost, start_game)
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
        embed.set_thumbnail(url="https://i.imgur.com/qRyUGXU.png") 
        embed.description = f"💎 **Obsidian Shards:** {delve_stats['shards']}"
        embed.add_field(name="Upgrades", value="Use Shards to improve your specialized equipment.", inline=False)
        
        view = DelveUpgradeView(self.bot, user_id, server_id, delve_stats)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Delve(bot))