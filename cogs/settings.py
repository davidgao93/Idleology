from discord import Interaction, app_commands
from discord.ext import commands

from core.settings.views import SettingsView


class Settings(commands.Cog, name="player_settings"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="player_settings", description="Manage your personal game settings."
    )
    async def player_settings(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return
        self.bot.state_manager.set_active(user_id, "player_settings")
        doors_status = await self.bot.database.users.get_doors_enabled(user_id)
        exp_protection = await self.bot.database.users.get_exp_protection(user_id)
        auto_rest_pay = await self.bot.database.users.get_auto_rest_pay(user_id)
        difficulty = await self.bot.database.users.get_hard_mode(user_id)
        player_level = existing_user["level"]
        corrupted_status = (
            await self.bot.database.users.get_corrupted_encounters_enabled(user_id)
        )
        auto_potion_reload = await self.bot.database.users.get_auto_potion_reload(
            user_id
        )

        meta = await self.bot.database.quests.get_meta(user_id)
        auto_rest_unlocked = bool(meta.get("auto_rest_unlocked"))
        auto_reload_unlocked = bool(meta.get("auto_reload_unlocked"))

        # Grandfather in players who already had these enabled before the quest-shop gate
        if auto_rest_pay and not auto_rest_unlocked:
            await self.bot.database.quests.ensure_meta(user_id)
            await self.bot.database.quests.set_meta_field(
                user_id, "auto_rest_unlocked", 1
            )
            auto_rest_unlocked = True
        if auto_potion_reload and not auto_reload_unlocked:
            await self.bot.database.quests.ensure_meta(user_id)
            await self.bot.database.quests.set_meta_field(
                user_id, "auto_reload_unlocked", 1
            )
            auto_reload_unlocked = True

        view = SettingsView(
            self.bot,
            user_id,
            doors_status,
            exp_protection,
            auto_rest_pay,
            difficulty,
            player_level,
            corrupted_status,
            auto_potion_reload,
            auto_rest_unlocked,
            auto_reload_unlocked,
        )
        await interaction.response.send_message(
            embed=view.build_embed(), view=view, ephemeral=False
        )
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Settings(bot))
