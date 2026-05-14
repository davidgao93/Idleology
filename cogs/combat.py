# cogs/combat.py

import asyncio
import random
from datetime import datetime, timedelta

import discord
from discord import ButtonStyle, Interaction, app_commands
from discord.ext import commands
from discord.ui import Button

from core.base_view import BaseView
from core.combat import engine, ui
from core.combat.gen.encounters import EncounterManager
from core.combat.gen.gen_mob import (
    generate_boss,
    generate_corrupted_encounter,
    generate_encounter,
)
from core.combat.views import CombatView
from core.combat.views_dojo import DummyConfigView
from core.combat.warning_views import CorruptedEncounterGateView, LowHealthWarningView
from core.items.factory import load_player
from core.models import Monster


class DoorPromptView(BaseView):
    def __init__(self, bot, user_id, cost_dict, boss_type):
        super().__init__(bot, user_id)
        self.cost_dict = cost_dict
        self.boss_type = boss_type
        self.accepted = False

    @discord.ui.button(label="Enter", style=ButtonStyle.danger)
    async def enter(self, interaction: Interaction, button: Button):
        self.accepted = True
        for currency, amount in self.cost_dict.items():
            await self.bot.database.users.modify_currency(
                self.user_id, currency, -amount
            )

        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Leave", style=ButtonStyle.secondary)
    async def leave(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        self.stop()


class Combat(commands.Cog, name="combat"):
    def __init__(self, bot):
        self.bot = bot
        self.COMBAT_COOLDOWN = timedelta(minutes=10)

    async def _check_cooldown(
        self, interaction: Interaction, user_id: str, existing_user: tuple
    ) -> bool:
        """Calculates dynamic cooldown and checks if user can fight."""
        temp_cooldown_reduction = 0
        equipped_boot = await self.bot.database.equipment.get_equipped(user_id, "boot")
        if equipped_boot and equipped_boot["passive"] == "speedster":
            temp_cooldown_reduction = equipped_boot["passive_lvl"] * 60

        current_duration = self.COMBAT_COOLDOWN - timedelta(
            seconds=temp_cooldown_reduction
        )
        current_duration = max(timedelta(seconds=10), current_duration)

        last_combat_str = existing_user["last_combat"]
        if last_combat_str:
            try:
                last_combat_dt = datetime.fromisoformat(last_combat_str)
                if datetime.now() - last_combat_dt < current_duration:
                    remaining = current_duration - (datetime.now() - last_combat_dt)
                    await interaction.response.send_message(
                        f"Please slow down. Try again in {remaining.seconds // 60}m {remaining.seconds % 60}s.",
                        ephemeral=True,
                    )
                    return False
            except ValueError:
                self.bot.logger.warning(f"Invalid last_combat_time for {user_id}")
        return True

    @app_commands.command(name="combat", description="Engage in combat.")
    async def combat(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return
        if not await self._check_cooldown(interaction, user_id, existing_user):
            return

        self.bot.state_manager.set_active(user_id, "combat")

        # 2. Load Player
        player = await load_player(user_id, existing_user, self.bot.database)

        # 3. Health Check Interceptor
        if player.current_hp < (player.total_max_hp * 0.25):
            view = LowHealthWarningView(
                self.bot,
                user_id,
                server_id,
                existing_user,
                player,
                self._execute_combat,
            )
            await interaction.response.send_message(embed=view.build_embed(), view=view)
            view.message = await interaction.original_response()
            return  # Pause execution here. The view will call _execute_combat if they proceed.

        # If health is fine, proceed immediately. We defer because the logic below can take a moment.
        await interaction.response.defer()
        await self._execute_combat(
            interaction, user_id, server_id, existing_user, player
        )

    async def _execute_combat(
        self,
        interaction: Interaction,
        user_id: str,
        server_id: str,
        existing_user: tuple,
        player,
    ):
        """The actual combat generation and UI loading logic. Called directly or via the Warning View."""
        is_boss = False
        is_corrupted = False
        combat_phases = []

        # 3a. Corrupted encounter roll — resolves first (level 100+)
        if player.level >= 100:
            corrupted_chance = 0.01 + player.get_emblem_bonus("corrupted_find") * 0.002
            if random.random() < corrupted_chance:
                gate_view = CorruptedEncounterGateView(self.bot, user_id)
                await interaction.edit_original_response(
                    content=None,
                    embed=gate_view.build_embed(),
                    view=gate_view,
                )
                await gate_view.wait()
                is_corrupted = gate_view.accepted
                if not is_corrupted:
                    # Player fled — clear gate message, fall through to boss door check
                    await interaction.edit_original_response(
                        content="*The corrupted presence fades... for now.*",
                        embed=None,
                        view=None,
                    )
                    await asyncio.sleep(1.0)

        # 3b. Boss door check — skipped entirely if a corrupted encounter was accepted
        triggered = False
        if not is_corrupted:
            doors_enabled = await self.bot.database.users.get_doors_enabled(user_id)
            if doors_enabled:
                currencies = {
                    "dragon_key": existing_user["dragon_key"],
                    "angel_key": existing_user["angel_key"],
                    "soul_cores": existing_user["soul_cores"],
                    "void_frags": existing_user["void_frags"],
                    "balance_fragment": await self.bot.database.users.get_currency(
                        user_id, "balance_fragment"
                    ),
                }
                triggered, boss_type, cost_dict = EncounterManager.check_boss_door(
                    player.level, currencies
                )

            if triggered:
                details = EncounterManager.get_door_details(boss_type)
                embed = discord.Embed(
                    title=details["title"], description=details["desc"], color=0x00FF00
                )
                if details["img"]:
                    embed.set_image(url=details["img"])
                embed.set_footer(text=f"Cost: {details['cost_str']}")

                view = DoorPromptView(self.bot, user_id, cost_dict, boss_type)
                await interaction.edit_original_response(
                    content=None, embed=embed, view=view
                )
                await view.wait()

                if view.accepted:
                    is_boss = True
                    combat_phases = EncounterManager.get_boss_phases(boss_type)
                    await self.bot.database.users.update_timer(user_id, "last_combat")
                else:
                    await interaction.edit_original_response(
                        content="*You turn away from the ominous presence...*",
                        embed=None,
                        view=None,
                    )
                    await asyncio.sleep(1.0)

        if not is_boss:
            await self.bot.database.users.update_timer(user_id, "last_combat")

        # 4. Generate Initial Monster
        slayer_profile = await self.bot.database.slayer.get_profile(user_id, server_id)
        task_species = slayer_profile["active_task_species"]

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
        )

        if is_boss:
            monster = await generate_boss(player, monster, combat_phases[0], 0)
            monster.is_boss = True
        elif is_corrupted:
            monster = generate_corrupted_encounter(player, monster)
            combat_phases = [None]
        else:
            treasure_chance = 1.0
            if player.get_boot_passive() == "treasure-tracker":
                treasure_chance += player.equipped_boot.passive_lvl * 0.5
            is_treasure = random.random() * 100 < treasure_chance
            monster = await generate_encounter(
                player, monster, is_treasure=is_treasure, task_species=task_species
            )
            combat_phases = [None]

        # 5. Apply Start Effects
        engine.apply_stat_effects(player, monster)
        start_logs = engine.apply_combat_start_passives(player, monster)
        engine.log_combat_debug(player, monster, self.bot.logger)
        # 6. Launch View
        title = "⚔️ BOSS PHASE 1" if is_boss else None
        embed = ui.create_combat_embed(
            player, monster, start_logs, title_override=title
        )
        view = CombatView(
            self.bot,
            user_id,
            server_id,
            player,
            monster,
            start_logs,
            combat_phases if is_boss else None,
        )

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="dojo", description="Test your DPS against a customizable dummy."
    )
    async def dojo(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "dojo")

        # 2. Load Player
        from core.items.factory import load_player

        player = await load_player(user_id, existing_user, self.bot.database)

        # 3. Launch View
        view = DummyConfigView(self.bot, user_id, player)
        embed = view.build_embed()

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Combat(bot))
