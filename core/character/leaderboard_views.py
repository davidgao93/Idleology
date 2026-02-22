import discord
from discord import ui, ButtonStyle, Interaction

class LeaderboardHubView(ui.View):
    def __init__(self, bot, active_tab: str = "levels"):
        super().__init__(timeout=120)
        self.bot = bot
        self.active_tab = active_tab
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        
        tabs = [
            ("levels", "Highest Levels", "🏆"),
            ("wealth", "Wealthiest", "💰"),
            ("slayer", "Top Slayers", "💀"),
            ("ideologies", "Ideologies", "💡")
        ]
        
        for tab_id, label, emoji in tabs:
            style = ButtonStyle.primary if self.active_tab == tab_id else ButtonStyle.secondary
            btn = ui.Button(label=label, emoji=emoji, style=style, custom_id=tab_id)
            btn.callback = self.handle_tab_switch
            self.add_item(btn)

    async def handle_tab_switch(self, interaction: Interaction):
        tab_id = interaction.data["custom_id"]
        if tab_id == self.active_tab:
            return await interaction.response.defer()
            
        self.active_tab = tab_id
        self.update_buttons()
        await interaction.response.defer()
        
        embed = await self.build_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    async def build_embed(self) -> discord.Embed:
        if self.active_tab == "levels":
            data = await self.bot.database.users.get_leaderboard(10)
            embed = discord.Embed(title="Hiscores: Highest Levels 🏆", color=0x00FF00)
            lines = [f"**{i+1}. {row[3]}** - Level {row[4]} (Ascension {row[15]} 🌟)" for i, row in enumerate(data)]
            
        elif self.active_tab == "wealth":
            data = await self.bot.database.users.get_wealth_leaderboard(10)
            embed = discord.Embed(title="Hiscores: Wealthiest 💰", color=0xFFD700)
            lines = [f"**{i+1}. {row[0]}** - {row[1]:,} GP" for i, row in enumerate(data)]
            
        elif self.active_tab == "slayer":
            data = await self.bot.database.slayer.get_leaderboard(10)
            embed = discord.Embed(title="Hiscores: Top Slayers 💀", color=0x8B0000)
            lines = [f"**{i+1}. {row[0]}** - Level {row[1]} ({row[2]:,} XP)" for i, row in enumerate(data)]
            
        elif self.active_tab == "ideologies":
            data = await self.bot.database.social.get_ideology_leaderboard(10)
            embed = discord.Embed(title="Hiscores: Dominant Ideologies 💡", color=0x00BFFF)
            lines = [f"**{i+1}. {row[0]}** - {row[1]:,} Followers" for i, row in enumerate(data)]

        embed.description = "\n".join(lines) if lines else "No data found."
        return embed