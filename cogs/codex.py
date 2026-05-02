import discord
from discord.ext import commands
from discord import app_commands, Interaction

from core.items.factory import load_player
from core.codex.views import CodexMenuView


class Codex(commands.Cog, name="codex"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="codex", description="Enter the Codex — an onslaught of curated chapters (Lvl 100+).")
    async def codex(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild_id)

        # 1. Validate registration and state
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # 2. Level gate
        if existing_user[4] < 100:
            await interaction.response.send_message(
                "The Codex only reveals itself to those who have reached **Level 100**.",
                ephemeral=True,
            )
            return

        # 3. Load player with all gear and tomes (cooldown is checked on Begin Run, not here)
        player = await load_player(user_id, existing_user, self.bot.database)

        # 5. Load Codex currencies (fetched by column name to avoid index fragility)
        fragments    = await self.bot.database.users.get_currency(user_id, 'codex_fragments')
        pages        = await self.bot.database.users.get_currency(user_id, 'codex_pages')
        rerolls      = await self.bot.database.users.get_currency(user_id, 'codex_rerolls')
        antique_tomes = await self.bot.database.users.get_currency(user_id, 'antique_tome')

        # 6. Load chapter history for display
        try:
            chapter_history = await self.bot.database.codex.get_chapter_clears(user_id)
        except Exception:
            chapter_history = {}

        # 7. Show menu
        view = CodexMenuView(
            self.bot, user_id, player,
            fragments, pages, rerolls, chapter_history,
            antique_tomes=antique_tomes,
        )
        await interaction.response.send_message(embed=view.build_embed(), view=view)


async def setup(bot) -> None:
    await bot.add_cog(Codex(bot))
