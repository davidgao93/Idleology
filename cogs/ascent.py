from datetime import datetime, timedelta

from discord import Interaction, app_commands
from discord.ext import commands

from core.ascent.mechanics import AscentMechanics
from core.ascent.views import AscentLobbyView
from core.items.factory import load_player


class Ascent(commands.Cog, name="ascent"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.ASCENT_COOLDOWN = timedelta(minutes=10)

    async def _check_cooldown(
        self, interaction: Interaction, user_id: str, existing_user: tuple
    ) -> bool:
        temp_reduction = 0
        boot = await self.bot.database.equipment.get_equipped(user_id, "boot")
        if boot and boot[9] == "speedster":
            temp_reduction = boot[12] * 60

        duration = max(
            timedelta(seconds=10),
            self.ASCENT_COOLDOWN - timedelta(seconds=temp_reduction),
        )

        last_combat = existing_user[24]
        if last_combat:
            try:
                dt = datetime.fromisoformat(last_combat)
                if datetime.now() - dt < duration:
                    rem = duration - (datetime.now() - dt)
                    await interaction.response.send_message(
                        f"Ascent cooldown: {rem.seconds // 60}m {rem.seconds % 60}s.",
                        ephemeral=True,
                    )
                    return False
            except:
                pass
        return True

    @app_commands.command(name="ascent", description="Begin your ascent (Lvl 100+).")
    async def ascent(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validate
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if existing_user[4] < 100:
            await interaction.response.send_message(
                "Come back at level 100.", ephemeral=True
            )
            return

        pinnacle_keys = await self.bot.database.users.get_currency(user_id, "pinnacle_key")

        player = await load_player(user_id, existing_user, self.bot.database)
        best_floor = await self.bot.database.ascension.get_highest_floor(user_id)

        view = AscentLobbyView(self.bot, user_id, server_id, player, best_floor, pinnacle_keys)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot) -> None:
    await bot.add_cog(Ascent(bot))
