import discord
from discord.ext import commands
from discord import app_commands, Interaction
from datetime import datetime, timedelta

from core.items.factory import load_player
from core.codex.views import CodexMenuView


class Codex(commands.Cog, name="codex"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.CODEX_COOLDOWN = timedelta(minutes=10)

    async def _check_cooldown(self, interaction: Interaction, user_id: str, existing_user: tuple) -> bool:
        """Reuses the last_combat timer, with speedster boot reduction."""
        temp_reduction = 0
        boot = await self.bot.database.equipment.get_equipped(user_id, "boot")
        if boot and boot[9] == "speedster":
            temp_reduction = boot[12] * 20

        duration = max(timedelta(seconds=10), self.CODEX_COOLDOWN - timedelta(seconds=temp_reduction))
        last_combat = existing_user[24]
        if last_combat:
            try:
                dt = datetime.fromisoformat(last_combat)
                if datetime.now() - dt < duration:
                    rem = duration - (datetime.now() - dt)
                    await interaction.response.send_message(
                        f"Codex cooldown: **{rem.seconds // 60}m {rem.seconds % 60}s** remaining.",
                        ephemeral=True,
                    )
                    return False
            except Exception:
                pass
        return True

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

        # 3. Cooldown (only prevents opening the run, not the menu)
        if not await self._check_cooldown(interaction, user_id, existing_user):
            return

        # 4. Load player with all gear and tomes
        player = await load_player(user_id, existing_user, self.bot.database)

        # 5. Load Codex currencies (fetched by column name to avoid index fragility)
        fragments = await self.bot.database.users.get_currency(user_id, 'codex_fragments')
        pages     = await self.bot.database.users.get_currency(user_id, 'codex_pages')
        rerolls   = await self.bot.database.users.get_currency(user_id, 'codex_rerolls')

        # 6. Load chapter history for display
        try:
            chapter_history = await self.bot.database.codex.get_chapter_clears(user_id)
        except Exception:
            chapter_history = {}

        # 7. Show menu
        view = CodexMenuView(
            self.bot, user_id, player,
            fragments, pages, rerolls, chapter_history,
        )
        await interaction.response.send_message(embed=view.build_embed(), view=view)


async def setup(bot) -> None:
    await bot.add_cog(Codex(bot))
