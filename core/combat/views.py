# core/combat/views.py

import asyncio
import random
from datetime import datetime, timedelta

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.combat import engine
from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.combat_log import CombatLogger
from core.combat.config import (
    NEET_VOID_KEY_CHANCE,
    XP_LOSS_ON_DEFEAT,
)
from core.combat.economy import uber_rewards
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.victory import apply_victory_rewards
from core.combat.gen.gen_mob import generate_boss
from core.combat.views_lucifer import LuciferChoiceView
from core.images import (
    VICTORY_APHRODITE_GEMINI,
    VICTORY_LUCIFER,
    VICTORY_NEET,
)
from core.models import Monster, Player

# ---------------------------------------------------------------------------
# Boss-specific victory embed configuration
# Drives thumbnail and extra field injection for named boss encounters.
# NEET and Lucifer still need procedural handling (DB writes / view swap),
# but their embed appearance is fully determined by this table.
# ---------------------------------------------------------------------------
_BOSS_VICTORY_CFG: dict[str, dict] = {
    "Aphrodite": {"thumbnail_url": VICTORY_APHRODITE_GEMINI},
    "Gemini": {"thumbnail_url": VICTORY_APHRODITE_GEMINI},
    "NEET": {"thumbnail_url": VICTORY_NEET},
    "Lucifer": {
        "thumbnail_url": VICTORY_LUCIFER,
        "extra_fields": [
            {
                "name": "❤️‍🔥 A Soul Core manifests...",
                "value": (
                    "**Choose how to absorb its power:**\n"
                    "❤️‍🔥 **Enraged:** Modifies Attack (-1 to +2)\n"
                    "💙 **Solidified:** Modifies Defence (1- to +2)\n"
                    "💔 **Unstable:** Shuffles Stats towards equilibrium\n"
                    "💞 **Inverse:** Swaps Attack and Defence values\n"
                    "🖤 **Keep:** Store a singular Soul Core"
                ),
                "inline": False,
            }
        ],
    },
}


def _boss_victory_cfg(monster_name: str) -> dict:
    for key, cfg in _BOSS_VICTORY_CFG.items():
        if key in monster_name:
            return cfg
    return {}


_COMBAT_COOLDOWN = timedelta(minutes=10)


class PostCombatView(BaseView):
    """Shown after a regular victory. Has a Fight Again button when stamina > 0,
    or no buttons when stamina is empty (the embed field carries the cooldown info)."""

    def __init__(self, bot, user_id: str, server_id: str, player, stamina: int, rematch_callback):
        super().__init__(bot, user_id, server_id, timeout=120)
        self.player = player
        self.rematch_callback = rematch_callback
        self._stamina = stamina

        if stamina > 0:
            btn = discord.ui.Button(
                label=f"Fight Again  ⚡{stamina}",
                style=discord.ButtonStyle.green,
            )
            btn.callback = self._fight_again
            self.add_item(btn)

    async def _fight_again(self, interaction: Interaction):
        await interaction.response.defer()

        # Re-fetch to guard against any race (stamina may have changed)
        existing_user = await self.bot.database.users.get(self.user_id, self.server_id)
        if existing_user["combat_stamina"] <= 0:
            await interaction.followup.send("No stamina remaining!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True

        self.bot.state_manager.set_active(self.user_id, "combat")
        await self.rematch_callback(interaction, self.user_id, self.server_id, existing_user, self.player)
        self.stop()


class CombatView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        monster: Monster,
        initial_logs: dict,
        combat_phases=None,
        post_combat_view=None,
        rematch_callback=None,
    ):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.monster = monster
        self.logs = initial_logs or {}
        self.post_combat_view = post_combat_view
        self.rematch_callback = rematch_callback

        _je.reset_jewel_charges(player)

        # Boss / Chain Handling
        self.combat_phases = combat_phases or []  # List of dicts
        self.current_phase_index = 0
        self._auto_running = False
        self._was_auto = False
        self.killing_blow = 0

        self.combat_logger = CombatLogger(player, monster)
        self.combat_logger.log_combat_start(player, monster)

        self.update_buttons()

    async def on_timeout(self):
        # Only trigger flee logic if the fight is still active
        if self.player.current_hp > 0 and self.monster.hp > 0:
            self.logs["Timeout"] = (
                "You hesitated too long! You failed to step up to the challenge."
            )

            self.update_buttons()

            embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)
            embed.set_footer(text="Combat ended due to timeout.")

            try:
                await self.message.edit(embed=embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                pass

            # Save state (HP/XP changes if any occurred prior)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)

        self.combat_logger.log_combat_end(self.player, self.monster, "timeout")
        await super().on_timeout()

    def update_buttons(self):
        # Toggle buttons based on current state (Enabled if both alive, Disabled if one dead)
        is_over = self.player.current_hp <= 0 or self.monster.hp <= 0
        for child in self.children:
            child.disabled = is_over or self._auto_running
        if not is_over and not self._auto_running:
            self.heal_btn.disabled = self.player.potions <= 0

    def _do_monster_turn(self) -> str:
        hp_before = self.player.current_hp
        log = engine.process_monster_turn(self.player, self.monster)
        self.killing_blow = hp_before - max(0, self.player.current_hp)
        self.combat_logger.log_monster_turn(log, self.player)
        return log

    def _apply_phase_image_transition(self):
        """Permanently swap monster to image2 once HP drops to or below 50% (one-way)."""
        if self.monster.image2 and self.monster.hp * 2 <= self.monster.max_hp:
            self.monster.image = self.monster.image2
            self.monster.image2 = ""

    async def refresh_embed(self, interaction: Interaction):
        self._apply_phase_image_transition()
        embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)

        # Check if we have already deferred or responded (e.g. via Fast Auto)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️")
    async def attack_btn(self, interaction: Interaction, button: ui.Button):
        # 1. Player Turn
        p_log = engine.process_player_turn(self.player, self.monster)
        self.combat_logger.log_player_turn(p_log, self.monster)
        self.logs = {self.player.name: p_log}

        # 2. Monster Turn (if alive)
        if self.monster.hp > 0:
            m_log = self._do_monster_turn()
            self.logs[self.monster.name] = m_log

        # 3. Check End State
        await self.check_combat_state(interaction)

    @ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹")
    async def heal_btn(self, interaction: Interaction, button: ui.Button):
        h_log = engine.process_heal(self.player, self.monster)
        self.logs = {"Heal": h_log}

        # Monster still hits you when you potion
        if self.monster.hp > 0:
            m_log = self._do_monster_turn()
            self.logs[self.monster.name] = m_log

        await self.check_combat_state(interaction)

    @ui.button(label="Auto", style=ButtonStyle.primary, emoji="⏩")
    async def auto_btn(self, interaction: Interaction, button: ui.Button):
        # Simple Auto: Process turns in a loop.
        # For bosses: run all the way through without HP protection.
        # For regular enemies: pause at < 20% HP.
        await interaction.response.defer()

        hp_threshold = self.player.total_max_hp * 0.2

        self._auto_running = True
        message = interaction.message

        self.update_buttons()
        await message.edit(view=self)

        while True:
            # Inner loop: fight the current phase to completion
            while self.player.current_hp > hp_threshold and self.monster.hp > 0:
                p_log = engine.process_player_turn(self.player, self.monster)
                self.combat_logger.log_player_turn(p_log, self.monster)
                m_log = ""
                if self.monster.hp > 0:
                    m_log = self._do_monster_turn()

                self.logs = {self.player.name: p_log, self.monster.name: m_log}

                self._apply_phase_image_transition()
                embed = combat_ui.create_combat_embed(
                    self.player, self.monster, self.logs
                )
                await message.edit(embed=embed, view=self)
                await asyncio.sleep(1.0)

            was_auto = self._auto_running
            self._auto_running = False

            # Low HP pause — applies to all fight types including bosses
            if (
                0 < self.player.current_hp <= (self.player.total_max_hp * 0.2)
                and self.monster.hp > 0
            ):
                self.logs["Auto-Battle"] = "🛑 Paused: Low HP Protection triggered!"
                self.update_buttons()
                embed = combat_ui.create_combat_embed(
                    self.player, self.monster, self.logs
                )
                await message.edit(embed=embed, view=self)
                await message.channel.send(
                    f"<@{self.user_id}> ⚠️ Low HP Protection triggered — auto paused!",
                    delete_after=15,
                )
                break

            # Handle end state (victory, defeat, or phase transition)
            self._was_auto = was_auto
            player_was_alive = self.player.current_hp > 0
            await self.handle_end_state(message, interaction)

            # Phase transition: handle_end_state replaces self.monster with the next
            # phase boss (hp > 0) and returns without stopping the view.
            # In all other cases (final victory, defeat) self.monster.hp stays 0.
            if was_auto and self.monster.hp > 0 and player_was_alive:
                self._auto_running = True  # Resume auto for the new phase
                continue
            break

    @ui.button(label="Flee", style=ButtonStyle.secondary, emoji="🏃")
    async def flee_btn(self, interaction: Interaction, button: ui.Button):
        self.logs["Flee"] = "You managed to escape safely!"
        self.update_buttons()  # Disable all

        embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)
        await interaction.response.edit_message(embed=embed, view=None)

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)
        self.stop()

    @ui.button(label="10 Turns", style=ButtonStyle.secondary, emoji="⚡", row=1)
    async def fast_auto_btn(self, interaction: Interaction, button: ui.Button):
        if self.player.level < 20:
            return await interaction.response.send_message(
                "This unlocks at Level 20!", ephemeral=True
            )

        await interaction.response.defer()
        turns_processed = 0

        for _ in range(10):
            if (
                self.player.current_hp <= (self.player.total_max_hp * 0.2)
                or self.monster.hp <= 0
            ):
                break

            p_log = engine.process_player_turn(self.player, self.monster)
            self.combat_logger.log_player_turn(p_log, self.monster)
            m_log = ""
            if self.monster.hp > 0:
                m_log = self._do_monster_turn()

            self.logs = {self.player.name: p_log, self.monster.name: m_log}
            turns_processed += 1

        status_msg = (
            f"⚡ You flash forward in time, **{turns_processed}** turns have gone by."
        )

        # Ensure HP is strictly greater than 0 to append the pause message
        low_hp_triggered = (
            0 < self.player.current_hp <= (self.player.total_max_hp * 0.2)
            and self.monster.hp > 0
        )
        if low_hp_triggered:
            status_msg += "\n🛑 Paused: Low HP Protection triggered!"

        self.logs["System"] = status_msg

        # Update UI / Check Win/Loss
        if self.player.current_hp <= 0 or self.monster.hp <= 0:
            await self.handle_end_state(interaction.message, interaction)
        else:
            if low_hp_triggered:
                await interaction.message.channel.send(
                    f"<@{self.user_id}> ⚠️ Low HP Protection triggered — auto paused!",
                    delete_after=15,
                )
            await self.check_combat_state(interaction)

    async def check_combat_state(self, interaction: Interaction):
        """Checks if player died or monster died."""
        if self.player.current_hp <= 0 or self.monster.hp <= 0:
            self.update_buttons()  # Disable buttons

            # We use a separate handler because Auto-battle defers interactions,
            # while clicking Attack usually does not.
            if interaction.response.is_done():
                await self.handle_end_state(interaction.message, interaction)
            else:
                await self.refresh_embed(interaction)  # Show final hit
                await self.handle_end_state(interaction.message, interaction)
        else:
            await self.refresh_embed(interaction)

    async def handle_end_state(self, message, interaction: Interaction):
        """Processes victory or defeat, including phase transitions for boss chains."""

        # --- UBER ENCOUNTERS ---
        if getattr(self.monster, "is_uber", False):
            await uber_rewards.handle_uber_end_state(self, message, interaction)
            return

        # --- DEFEAT ---
        if self.player.current_hp <= 0:
            self.combat_logger.log_combat_end(self.player, self.monster, "defeat")
            base_loss = int(self.player.exp * XP_LOSS_ON_DEFEAT)
            xp_loss = await ExperienceManager.remove_experience(
                self.bot, self.user_id, self.player, base_loss
            )
            self.player.current_hp = 1
            embed = combat_ui.create_defeat_embed(
                self.player, self.monster, xp_loss, killing_blow=self.killing_blow
            )
            await message.edit(embed=embed, view=None)
            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)
            self.stop()
            return

        # --- PHASE TRANSITION ---
        if self.current_phase_index < len(self.combat_phases) - 1:
            self.current_phase_index += 1
            next_phase_data = self.combat_phases[self.current_phase_index]

            self.player.reset_combat_bonus()
            self.player.is_invulnerable_this_combat = False

            self.monster = await generate_boss(
                self.player, self.monster, next_phase_data, self.current_phase_index
            )
            self.monster.is_boss = True

            engine.apply_stat_effects(self.player, self.monster)
            new_logs = engine.apply_combat_start_passives(self.player, self.monster)
            self.logs = new_logs

            trans_embed = discord.Embed(
                title="Phase Complete!",
                description=f"**{self.monster.name}** rises from the ashes...",
                color=discord.Color.orange(),
            )
            trans_embed.set_thumbnail(url=self.monster.image)
            await message.edit(embed=trans_embed, view=None)
            await asyncio.sleep(2)

            if not self._was_auto:
                self.update_buttons()

            embed = combat_ui.create_combat_embed(
                self.player,
                self.monster,
                new_logs,
                title_override=f"⚔️ BOSS PHASE {self.current_phase_index+1}",
            )
            await message.edit(embed=embed, view=self)
            return  # Keep view alive for next phase

        # --- FINAL VICTORY ---
        self.combat_logger.log_combat_end(self.player, self.monster, "victory")

        reward_data = await apply_victory_rewards(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.monster,
            message,
            self.combat_logger,
        )

        embed = combat_ui.create_victory_embed(
            self.player, self.monster, reward_data,
            cfg=_boss_victory_cfg(self.monster.name),
        )

        # NEET: conditional void key — DB write and loot field, then regular edit
        if "NEET" in self.monster.name and random.random() < NEET_VOID_KEY_CHANCE:
            embed.add_field(name="Loot", value="Found a **Void Key**.", inline=False)
            await self.bot.database.users.modify_currency(self.user_id, "void_keys", 1)

        # Lucifer: soul core choice view takes over the interaction
        if "Lucifer" in self.monster.name:
            ping_msg = await message.channel.send(
                f"<@{self.user_id}> A Soul Core has manifested — make your choice!\n\n"
                f"Battle: {message.jump_url}"
            )
            await ping_msg.delete(delay=45)
            contract_choice_view = LuciferChoiceView(
                self.bot, self.user_id, self.player
            )
            await message.edit(embed=embed, view=contract_choice_view)
            contract_choice_view.message = message
            return  # LuciferChoiceView takes over

        # Soulreap: restore HP to full after every successful encounter
        if self.player.get_weapon_infernal() == "soulreap":
            self.player.current_hp = self.player.total_max_hp

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)

        # Build post-combat view (Fight Again button or stamina cooldown field)
        stamina_data = await self.bot.database.users.get_stamina(self.user_id)
        stamina = stamina_data["combat_stamina"]

        if stamina == 0:
            equipped_boot = await self.bot.database.equipment.get_equipped(self.user_id, "boot")
            speedster_reduction = 0
            if equipped_boot and equipped_boot["passive"] == "speedster":
                speedster_reduction = equipped_boot["passive_lvl"] * 60
            cooldown = max(timedelta(seconds=10), _COMBAT_COOLDOWN - timedelta(seconds=speedster_reduction))
            last_combat_str = await self.bot.database.users.get_timer(self.user_id, "last_combat")
            time_str = "soon"
            if last_combat_str:
                try:
                    elapsed = datetime.now() - datetime.fromisoformat(last_combat_str)
                    remaining = cooldown - elapsed
                    if remaining.total_seconds() > 0:
                        mins = int(remaining.total_seconds()) // 60
                        secs = int(remaining.total_seconds()) % 60
                        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                    else:
                        time_str = "now"
                except ValueError:
                    pass
            embed.add_field(name="⚡ Stamina", value=f"Out of stamina — next combat in **{time_str}**", inline=False)

        post_view = PostCombatView(
            self.bot, self.user_id, self.server_id, self.player, stamina, self.rematch_callback
        ) if self.rematch_callback else None

        await message.edit(embed=embed, view=post_view)
        self.stop()
