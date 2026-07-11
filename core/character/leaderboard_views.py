import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.emojis import GOLD_COIN
from core.images import LEADERBOARD_HUB


class LeaderboardHubView(BaseView):
    def __init__(self, bot, user_id: str, active_tab: str = "levels"):
        super().__init__(bot, user_id)
        self.active_tab = active_tab
        self._processing = False
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        tabs = [
            ("levels", "Highest Levels", "🏆"),
            ("ascensions", "Top Ascensions", "🌟"),
            ("wealth", "Wealthiest", GOLD_COIN),
            ("slayer", "Top Slayers", "💀"),
            ("ideologies", "Ideologies", "💡"),
            ("duels", "Top Duelists", "⚔️"),
        ]

        for tab_id, label, emoji in tabs:
            style = (
                ButtonStyle.primary
                if self.active_tab == tab_id
                else ButtonStyle.secondary
            )
            btn = ui.Button(label=label, emoji=emoji, style=style, custom_id=tab_id)
            btn.callback = self.handle_tab_switch
            self.add_item(btn)

        # Hall of Firsts is a Components V2 screen, not an embed tab — it
        # hands off to a fresh message rather than switching active_tab.
        hof_btn = ui.Button(
            label="Hall of Firsts", emoji="🏛️", style=ButtonStyle.secondary
        )
        hof_btn.callback = self.handle_hall_of_firsts
        self.add_item(hof_btn)

    async def handle_hall_of_firsts(self, interaction: Interaction) -> None:
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        from core.combat.ui.combat_embed import handoff_to_layout
        from core.hall_of_firsts.views import HallOfFirstsListView

        await interaction.response.defer()
        view = HallOfFirstsListView(self.bot, self.user_id)
        await view.load()
        await handoff_to_layout(interaction.message, view)
        self.stop()

    async def handle_tab_switch(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        tab_id = interaction.data["custom_id"]
        if tab_id == self.active_tab:
            return await interaction.response.defer()
        self._processing = True
        self.active_tab = tab_id
        self.update_buttons()
        await interaction.response.defer()

        embed = await self.build_embed()
        self._processing = False
        await interaction.edit_original_response(embed=embed, view=self)

    async def build_embed(self) -> discord.Embed:
        if self.active_tab == "levels":
            data = await self.bot.database.users.get_leaderboard(10)
            embed = discord.Embed(title="Hiscores: Highest Levels 🏆", color=0x00FF00)
            lines = [
                f"**{i + 1}. {row['name']}** - Level {row['level']} (Ascension {row['ascension']} 🌟)"
                for i, row in enumerate(data)
            ]

        elif self.active_tab == "ascensions":
            data = await self.bot.database.users.get_ascension_leaderboard(10)
            embed = discord.Embed(
                title="Hiscores: Highest Ascent Stage 🌟", color=0xFF8C00
            )
            lines = [
                f"**{i + 1}. {row['name']}** - Stage {row['highest_ascension_stage']} 🌟 (Level {row['level']})"
                for i, row in enumerate(data)
            ]

        elif self.active_tab == "wealth":
            data = await self.bot.database.users.get_wealth_leaderboard(10)
            embed = discord.Embed(
                title=f"Hiscores: Wealthiest {GOLD_COIN}", color=0xFFD700
            )
            lines = [
                f"**{i + 1}. {row['name']}** - {row['gold']:,} GP"
                for i, row in enumerate(data)
            ]

        elif self.active_tab == "slayer":
            data = await self.bot.database.slayer.get_leaderboard(10)
            embed = discord.Embed(title="Hiscores: Top Slayers 💀", color=0x8B0000)
            lines = [
                f"**{i + 1}. {row['name']}** - Level {row['level']} ({row['xp']:,} XP)"
                for i, row in enumerate(data)
            ]

        elif self.active_tab == "ideologies":
            data = await self.bot.database.social.get_ideology_leaderboard(10)
            embed = discord.Embed(
                title="Hiscores: Dominant Ideologies 💡", color=0x00BFFF
            )
            lines = [
                f"**{i + 1}. {row['name']}** - {row['followers']:,} Followers"
                for i, row in enumerate(data)
            ]

        elif self.active_tab == "duels":
            data = await self.bot.database.duels.get_leaderboard(10)
            embed = discord.Embed(title="Hiscores: Top Duelists ⚔️", color=0xFFD700)
            lines = []
            for i, (user_id, wins, losses) in enumerate(data):
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    name = user.display_name
                except Exception:
                    name = f"Unknown ({user_id})"
                wl = f"{wins}W / {losses}L"
                lines.append(f"**{i + 1}. {name}** - {wl}")

        embed.description = "\n".join(lines) if lines else "No data found."
        embed.set_thumbnail(url=LEADERBOARD_HUB)
        return embed
