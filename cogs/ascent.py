from datetime import datetime, timedelta

from discord import Interaction, app_commands
from discord.ext import commands

from core.ascent.mechanics import AscentMechanics
from core.ascent.views import AscentView
from core.combat import engine, ui
from core.combat.gen_mob import generate_ascent_monster
from core.items.factory import load_player
from core.models import Monster


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

        pinnacle_keys = await self.bot.database.users.get_currency(
            user_id, "pinnacle_key"
        )
        if pinnacle_keys < 1:
            await interaction.response.send_message(
                "The Ascent requires a **Pinnacle Key** to begin. "
                "Seek one from formidable foes.",
                ephemeral=True,
            )
            return

        # if not await self._check_cooldown(interaction, user_id, existing_user): return

        await self.bot.database.users.modify_currency(user_id, "pinnacle_key", -1)
        self.bot.state_manager.set_active(user_id, "ascent")
        await self.bot.database.users.update_timer(user_id, "last_combat")

        # 2. Init Player (ascension_unlocks loaded inside load_player)
        player = await load_player(user_id, existing_user, self.bot.database)

        # 3. Determine starting floor
        best_floor = await self.bot.database.ascension.get_highest_floor(user_id)
        starting_floor = AscentMechanics.calculate_starting_floor(best_floor)

        # 4. Generate starting floor monster
        m_level = AscentMechanics.calculate_floor_monster_level(starting_floor)
        n_mods, b_mods = AscentMechanics.get_floor_modifier_counts(starting_floor)

        monster = Monster(
            name="",
            level=0,
            hp=0,
            max_hp=0,
            xp=0,
            attack=0,
            defence=0,
            modifiers=[],
            image="",
            flavor="",
            is_boss=True,
        )
        monster = await generate_ascent_monster(
            player, monster, m_level, n_mods, b_mods
        )

        # 5. Apply start effects
        player.combat_ward = player.get_combat_ward_value()
        engine.apply_stat_effects(player, monster)
        start_logs = engine.apply_combat_start_passives(player, monster)
        engine.log_combat_debug(player, monster, self.bot.logger)

        # 6. Send
        embed = ui.create_combat_embed(
            player,
            monster,
            start_logs,
            title_override=f"Ascent Floor {starting_floor} | {player.name}",
        )
        view = AscentView(
            self.bot,
            user_id,
            server_id,
            player,
            monster,
            start_logs,
            starting_floor=starting_floor,
            best_floor=best_floor,
        )
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Ascent(bot))
