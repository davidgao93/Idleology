"""Main CombatView and post-combat / phase / auto-battle orchestration.

Extends BaseView. Delegates embeds to core.combat.ui, victory rewards to economy.victory,
and turn processing to core.combat.turns.engine + player_turn/monster_turn.
"""

import asyncio
import random
from datetime import datetime, timedelta

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.combat_log import CombatLogger
from core.combat.economy import uber_rewards
from core.combat.economy.config import (
    NEET_VOID_KEY_CHANCE,
    XP_LOSS_ON_DEFEAT,
)
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.victory import apply_victory_rewards
from core.combat.mobgen.gen_mob import generate_boss
from core.combat.turns.boundary import (
    fire_on_victory_effects,
    reset_for_phase_transition,
)
from core.combat.turns import engine
from core.combat.views.views_lucifer import LuciferChoiceView
from core.combat.views.views_prestige_boss import PrestigeBossHarvestView
from core.images import (
    VICTORY_APHRODITE_GEMINI,
    VICTORY_LUCIFER,
    VICTORY_NEET,
)
from core.items.factory import load_player
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
                    "💙 **Solidified:** Modifies Defence (-1 to +2)\n"
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

    def __init__(
        self, bot, user_id: str, server_id: str, player, stamina: int, rematch_callback
    ):
        super().__init__(bot, user_id, server_id, timeout=120)
        self.player = player
        self.rematch_callback = rematch_callback
        self._stamina = stamina
        self._launching = False  # Re-entry guard

        if stamina > 0:
            btn = discord.ui.Button(
                label=f"Fight Again  ⚡{stamina:g}",
                style=discord.ButtonStyle.green,
            )
            btn.callback = self._fight_again
            self.add_item(btn)

    async def on_timeout(self) -> None:
        """Expire the Fight Again button without touching active state.
        The player was already freed at victory time; calling clear_active here
        would incorrectly interrupt any new fight they started within this window."""
        if self.message:
            try:
                await self.message.edit(view=None)
            except (discord.NotFound, discord.HTTPException):
                pass
        self.stop()

    async def _fight_again(self, interaction: Interaction):
        # Synchronous guard — assigned before the first await, so the event loop
        # cannot schedule a second invocation while this one is still running.
        if self._launching:
            await interaction.response.defer()
            return
        self._launching = True

        await interaction.response.defer()

        # Disable the button right away so Discord shows it as locked.
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        if self.bot.state_manager.is_active(self.user_id):
            await interaction.followup.send(
                "You're already in an activity.", ephemeral=True
            )
            self.stop()  # View is unusable (buttons disabled); stop to cancel the timeout.
            return

        # Re-fetch user and reload player so any changes (rest, gear swaps, etc.) are reflected.
        existing_user = await self.bot.database.users.get(self.user_id, self.server_id)
        if existing_user["combat_stamina"] <= 0:
            await interaction.followup.send("No stamina remaining!", ephemeral=True)
            self.stop()
            return

        fresh_player = await load_player(self.user_id, existing_user, self.bot.database)
        self.bot.state_manager.set_active(self.user_id, "combat")
        await self.rematch_callback(
            interaction, self.user_id, self.server_id, existing_user, fresh_player
        )
        self.stop()


class StatPackagePicker(BaseView):
    """Post-combat view that presents 3 stat-package options for the player to pick.

    One instance handles all pending level-up packages for a single fight: after
    the player chooses a package it pops it from the queue and either presents the
    next one or fires the ``on_done`` callback so the caller can show the
    post-combat view.

    ``on_done`` is an async callable that receives ``(message)`` — the Discord
    message object — and is responsible for the final transition.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player,
        pending_packages: list,
        *,
        on_done,
    ):
        super().__init__(bot, user_id, server_id, timeout=300)
        self.player = player
        self.pending = pending_packages  # list of package-sets (list of 3 dicts each)
        self.on_done = on_done
        self._processing = False
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        current_set = self.pending[0]  # 3 packages for the current level-up
        styles = [
            discord.ButtonStyle.blurple,
            discord.ButtonStyle.green,
            discord.ButtonStyle.secondary,
        ]
        for i, pkg in enumerate(current_set):
            label = f"⚔️ +{pkg['atk']}  🛡️ +{pkg['def']}  ❤️ +{pkg['hp']}"
            btn = discord.ui.Button(label=label, style=styles[i % len(styles)], row=0)
            btn.callback = self._make_callback(pkg)
            self.add_item(btn)

    def _make_callback(self, pkg):
        async def callback(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            # Apply selected package to DB
            await self.bot.database.users.modify_stat(
                self.user_id, "attack", pkg["atk"]
            )
            await self.bot.database.users.modify_stat(
                self.user_id, "defence", pkg["def"]
            )
            await self.bot.database.users.modify_stat(self.user_id, "max_hp", pkg["hp"])

            # Apply to player object in memory
            self.player.base_attack += pkg["atk"]
            self.player.base_defence += pkg["def"]
            self.player.max_hp += pkg["hp"]
            self.player.current_hp = self.player.total_max_hp  # Full heal
            self.player.compute_flat_stats()

            # Pop the chosen package set and update DB
            self.pending.pop(0)
            await self.bot.database.users.set_pending_packages(
                self.user_id, self.server_id, self.pending or None
            )
            # Persist updated stats (level was already saved; we need max_hp etc.)
            await self.bot.database.users.update_from_player_object(self.player)

            if self.pending:
                # Another level-up package remains — show it
                self._processing = False
                self._build_buttons()
                await interaction.edit_original_response(
                    embed=self.build_embed(), view=self
                )
            else:
                self.stop()
                await self.on_done(interaction.message)

        return callback

    def build_embed(self) -> discord.Embed:
        remaining = len(self.pending)
        current_set = self.pending[0]

        suffix = (
            f" *({remaining} level-up{'s' if remaining != 1 else ''} remaining)*"
            if remaining > 1
            else ""
        )

        cur_atk = self.player.base_attack
        cur_def = self.player.base_defence
        cur_hp = self.player.max_hp

        embed = discord.Embed(
            title="🎉 Level Up! Choose a Stat Package",
            description=(
                f"Select one of the packages below to permanently apply to your character.{suffix}\n\n"
                f"**Current base stats:** ⚔️ {cur_atk} ATK  🛡️ {cur_def} DEF  ❤️ {cur_hp} HP\n\n"
                "Each package has **15 points** distributed across ATK, DEF, and HP. "
                "Packages are weighted toward whichever stat is furthest behind."
            ),
            color=discord.Color.gold(),
        )
        for i, pkg in enumerate(current_set):
            embed.add_field(
                name=f"Option {i + 1}",
                value=(
                    f"⚔️ **+{pkg['atk']}** ATK → {cur_atk + pkg['atk']}\n"
                    f"🛡️ **+{pkg['def']}** DEF → {cur_def + pkg['def']}\n"
                    f"❤️ **+{pkg['hp']}** HP → {cur_hp + pkg['hp']}"
                ),
                inline=True,
            )
        return embed


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
        hard_mode: int = 0,
        combat_streak: int = 0,
        crisis_callback=None,
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
        self.crisis_callback = crisis_callback
        self.hard_mode = (
            hard_mode  # int: 0=off, 1=hard, 2=extreme, 3=nightmarish, 4=delirious
        )
        self.combat_streak = combat_streak  # streak at start of this fight

        _je.reset_jewel_charges(player)

        # Per-encounter reset for Verdant Snare flag (rematch paths reuse the Player object;
        # fresh load_player paths get a default False via dataclass anyway).
        # Prestige phase chains use lighter reset_combat_bonus for other transients.
        player.cs.is_snared = False

        # Boss / Chain Handling
        self.combat_phases = combat_phases or []  # List of dicts
        self.current_phase_index = 0
        self._auto_running = False
        self._was_auto = False
        self.killing_blow = 0
        self._processing = (
            False  # Re-entry guard for mutating actions (Free Yourself, etc.)
        )

        self.combat_logger = CombatLogger(player, monster)
        self.combat_logger.log_combat_start(player, monster)

        self.update_buttons()

        # Free Yourself is only relevant during a Verdant Colossus encounter.
        # Remove it entirely for every other fight so it never appears.
        if "Verdant Colossus" not in monster.name:
            self.remove_item(self.free_yourself_btn)

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
        is_snared = getattr(self.player.cs, "is_snared", False)

        for child in self.children:
            child.disabled = is_over or self._auto_running

        # Free Yourself is only in self.children during Verdant Colossus encounters
        # (removed in __init__ for all other fights).
        snare_locks_combat = False
        if self.free_yourself_btn in self.children:
            if is_snared and not is_over and not self._auto_running:
                # Player is snared — only Free Yourself is usable, lock everything else.
                self.attack_btn.disabled = True
                self.heal_btn.disabled = True
                self.flee_btn.disabled = True
                self.auto_btn.disabled = True
                self.fast_auto_btn.disabled = True
                self.free_yourself_btn.disabled = False
                snare_locks_combat = True
            else:
                self.free_yourself_btn.disabled = True

        # Always update potion count on the heal button label.
        # Re-enable heal normally if combat is ongoing and player isn't locked by a snare.
        self.heal_btn.label = f"Heal ({self.player.potions}/20)"
        if not is_over and not self._auto_running and not snare_locks_combat:
            self.heal_btn.disabled = self.player.potions <= 0

    def _do_monster_turn(self, *, context_note: str = "") -> str:
        hp_before = self.player.current_hp
        log = engine.process_monster_turn(
            self.player, self.monster, context_note=context_note
        )
        self.killing_blow = hp_before - max(0, self.player.current_hp)
        self.combat_logger.log_monster_turn(log, self.player)
        return log

    def _apply_phase_image_transition(self):
        """Permanently swap monster to image2 once HP drops to or below 50% (one-way)."""
        if self.monster.image2 and self.monster.hp * 2 <= self.monster.max_hp:
            self.monster.image = self.monster.image2
            self.monster.image2 = ""

    def _streak_footer(self) -> str:
        """Returns a footer string showing the active combat streak bonus (if any)."""
        if self.combat_streak <= 0:
            return ""
        streak_pct = min(50, self.combat_streak // 10)
        if streak_pct <= 0:
            return f"🔥 Streak: {self.combat_streak}"
        return f"🔥 Streak: {self.combat_streak}  (+{streak_pct}% EXP & Gold)"

    async def refresh_embed(self, interaction: Interaction):
        self._apply_phase_image_transition()
        embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)

        # Append streak info to footer
        streak_txt = self._streak_footer()
        if streak_txt:
            existing = embed.footer.text or ""
            embed.set_footer(
                text=f"{streak_txt}  •  {existing}" if existing else streak_txt
            )

        # Check if we have already deferred or responded (e.g. via Fast Auto)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️")
    async def attack_btn(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # 1. Player Turn
        p_log = engine.process_player_turn(self.player, self.monster)
        self.combat_logger.log_player_turn(p_log, self.monster)
        self.logs = {self.player.name: p_log}

        # 2. Monster Turn (if alive)
        if self.monster.hp > 0:
            m_log = self._do_monster_turn()
            self.logs[self.monster.name] = m_log

        # 3. Check End State
        # If cull delivered the killing blow, show the result for 3 s before transitioning.
        if p_log.cull_fired and self.monster.hp <= 0:
            self.update_buttons()
            await self.refresh_embed(interaction)
            await asyncio.sleep(3)
            await self.handle_end_state(interaction.message, interaction)
        else:
            # Only release the guard when the fight is still ongoing.
            # If combat is over, handle_end_state (called inside check_combat_state)
            # stops the view, so holding the guard until then prevents double-rewards.
            if self.player.current_hp > 0 and self.monster.hp > 0:
                self._processing = False
            await self.check_combat_state(interaction)

    @ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹")
    async def heal_btn(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        h_log = engine.process_heal(self.player, self.monster)
        self.logs = {"Heal": h_log}

        # Monster still hits you when you potion (retaliation turn)
        if self.monster.hp > 0:
            m_log = self._do_monster_turn(context_note="(retaliation to heal/potion)")
            self.logs[self.monster.name] = m_log

        if self.player.current_hp > 0 and self.monster.hp > 0:
            self._processing = False
        await self.check_combat_state(interaction)

    @ui.button(label="Free Yourself", style=ButtonStyle.secondary, emoji="🌿", row=1)
    async def free_yourself_btn(self, interaction: Interaction, button: ui.Button):
        # Re-entry guard (mandatory for any button that mutates combat state per AGENTS.md)
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        if not getattr(self.player.cs, "is_snared", False):
            await interaction.response.send_message(
                "You are not currently snared.", ephemeral=True
            )
            self._processing = False
            return

        await interaction.response.defer()

        self.player.cs.is_snared = False
        snare_source = getattr(self.monster, "name", "the enemy")
        self.logs = {"Free Yourself": f"You break free from {snare_source}'s snare!"}

        # Monster gets a free retaliation turn after you free yourself (per design)
        if self.monster.hp > 0:
            m_log = self._do_monster_turn(
                context_note="(retaliation after breaking snare)"
            )
            self.logs[self.monster.name] = m_log

        if self.player.current_hp > 0 and self.monster.hp > 0:
            self._processing = False
        await self.check_combat_state(interaction)

    @ui.button(label="Auto", style=ButtonStyle.primary, emoji="⏩")
    async def auto_btn(self, interaction: Interaction, button: ui.Button):
        # Simple Auto: Process turns in a loop.
        # For bosses: run all the way through without HP protection.
        # For regular enemies: pause at < 20% HP.
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

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
                    self.player, self.monster, self.logs, compact=True
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
                self._processing = False
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
        self.player.cs.is_snared = (
            False  # Clean up any transient snare before leaving the fight
        )
        self.logs["Flee"] = "You managed to escape safely!"
        self.update_buttons()  # Disable all

        embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)
        await interaction.response.edit_message(embed=embed, view=None)

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)

        # Treat fleeing as a failure for crisis combat (same as defeat)
        if self.crisis_callback:
            try:
                await self.crisis_callback(False)
            except Exception:
                pass

        self.stop()

    @ui.button(label="10 Turns", style=ButtonStyle.secondary, emoji="⚡", row=1)
    async def fast_auto_btn(self, interaction: Interaction, button: ui.Button):
        if self.player.level < 20:
            return await interaction.response.send_message(
                "This unlocks at Level 20!", ephemeral=True
            )

        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

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
            if self.player.current_hp > 0 and self.monster.hp > 0:
                self._processing = False
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
            self.update_buttons()
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
            # Reset combat streak on any death
            await self.bot.database.users.reset_combat_streak(self.user_id)

            _DIFFICULTY_NAMES = ["", "Hard", "Extreme", "Nightmarish", "Delirious"]
            _DIFFICULTY_EMOJIS = ["", "☠️", "💀", "👁️", "🌀"]
            exp_protected = await self.bot.database.users.get_exp_protection(
                self.user_id
            )
            if self.hard_mode > 0 and not exp_protected:
                # Any difficulty mode: wipe ALL current-level EXP instead of the standard % loss
                xp_loss = self.player.exp
                self.player.exp = 0
            else:
                base_loss = int(self.player.exp * XP_LOSS_ON_DEFEAT)
                xp_loss = await ExperienceManager.remove_experience(
                    self.bot, self.user_id, self.player, base_loss
                )
            self.player.current_hp = 1
            embed = combat_ui.create_defeat_embed(
                self.player, self.monster, xp_loss, killing_blow=self.killing_blow
            )
            if self.hard_mode > 0:
                diff_name = f"{_DIFFICULTY_EMOJIS[self.hard_mode]} {_DIFFICULTY_NAMES[self.hard_mode]} Mode"
                embed.add_field(
                    name=f"{diff_name}",
                    value="Your EXP for this level has been wiped. Combat streak reset.",
                    inline=False,
                )
            elif self.combat_streak > 0:
                embed.add_field(
                    name="💀 Streak Lost",
                    value=f"Your {self.combat_streak}-win streak has ended.",
                    inline=False,
                )
            await message.edit(embed=embed, view=None)
            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)
            if self.crisis_callback:
                try:
                    await self.crisis_callback(False)
                except Exception:
                    pass
            self.stop()
            return

        # --- PHASE TRANSITION ---
        if self.current_phase_index < len(self.combat_phases) - 1:
            self.current_phase_index += 1
            next_phase_data = self.combat_phases[self.current_phase_index]

            reset_for_phase_transition(self.player)

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
                title_override=f"⚔️ BOSS PHASE {self.current_phase_index + 1}",
            )
            await message.edit(embed=embed, view=self)
            return  # Keep view alive for next phase

        # --- FINAL VICTORY ---
        self.combat_logger.log_combat_end(self.player, self.monster, "victory")

        # Streak bonus is based on the pre-fight streak (what was shown in the footer
        # during combat), so the player always receives exactly what was advertised.
        _DIFFICULTY_REWARD_PCT = [0, 50, 75, 100, 150]
        _DIFFICULTY_NAMES_V = ["", "Hard", "Extreme", "Nightmarish", "Delirious"]
        _DIFFICULTY_EMOJIS_V = ["", "☠️", "💀", "👁️", "🌀"]
        streak_pct = min(50, self.combat_streak // 10)
        hard_mode_pct = _DIFFICULTY_REWARD_PCT[self.hard_mode] if self.hard_mode else 0
        total_bonus_pct = streak_pct + hard_mode_pct

        reward_data = await apply_victory_rewards(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.monster,
            message,
            self.combat_logger,
        )

        # Increment streak after base rewards are applied (avoids DB write ordering issues).
        new_streak = await self.bot.database.users.increment_combat_streak(self.user_id)

        # Apply streak + hard mode bonus XP and gold on top of base rewards.
        bonus_xp = 0
        bonus_gold = 0
        if total_bonus_pct > 0:
            bonus_xp = int(reward_data["xp"] * total_bonus_pct / 100)
            bonus_gold = int(reward_data["gold"] * total_bonus_pct / 100)
            if bonus_xp > 0:
                bonus_exp_changes = await ExperienceManager.add_experience(
                    self.bot,
                    self.user_id,
                    self.player,
                    bonus_xp,
                    server_id=self.server_id,
                )
                reward_data["msgs"].extend(bonus_exp_changes["msgs"])
            if bonus_gold > 0:
                await self.bot.database.users.modify_gold(self.user_id, bonus_gold)

        embed = combat_ui.create_victory_embed(
            self.player,
            self.monster,
            reward_data,
            cfg=_boss_victory_cfg(self.monster.name),
        )

        # Streak / hard mode bonus field (shown when any bonus applied this fight)
        if total_bonus_pct > 0:
            bonus_parts = []
            if hard_mode_pct > 0:
                diff_emoji = _DIFFICULTY_EMOJIS_V[self.hard_mode]
                diff_name = _DIFFICULTY_NAMES_V[self.hard_mode]
                bonus_parts.append(f"{diff_emoji} {diff_name} Mode +{hard_mode_pct}%")
            if streak_pct > 0:
                bonus_parts.append(f"🔥 Streak +{streak_pct}%")
            embed.add_field(
                name=f"🎯 Bonus Rewards (+{total_bonus_pct}%)",
                value=(
                    f"{' | '.join(bonus_parts)}\n"
                    f"+{bonus_xp:,} XP  •  +{bonus_gold:,} Gold"
                ),
                inline=False,
            )

        # Victory embed footer: show updated streak so the player knows where they stand.
        if new_streak > 0:
            new_streak_pct = min(50, new_streak // 10)
            footer_txt = f"🔥 Streak: {new_streak}"
            if new_streak_pct > 0:
                footer_txt += f"  (+{new_streak_pct}% bonus next fight)"
            embed.set_footer(text=footer_txt)

        # NEET: conditional void key — DB write and loot field, then regular edit
        if "NEET" in self.monster.name and random.random() < NEET_VOID_KEY_CHANCE:
            embed.add_field(name="Loot", value="Found a **Void Key**.", inline=False)
            await self.bot.database.users.modify_currency(self.user_id, "void_keys", 1)

        # Lucifer: soul core choice view takes over the interaction
        if "Lucifer" in self.monster.name:
            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)
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
            self.stop()
            return  # LuciferChoiceView takes over

        # Prestige Gathering Boss (Artisan Mastery Phase 2) — custom harvest view
        prestige_type = getattr(self.monster, "prestige_boss_type", None)
        if prestige_type in ("golem", "leviathan", "colossus"):
            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)
            harvest_view = PrestigeBossHarvestView(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                self.monster,
                prestige_type,
                self.rematch_callback,
            )
            await message.edit(embed=embed, view=harvest_view)
            harvest_view.message = message
            self.stop()
            return  # Harvest view takes over the interaction

        fire_on_victory_effects(self.player)

        # Save player state and clear combat lock before any callback so the
        # callback can freely set a new active state (e.g. returning to settlement).
        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)

        if self.crisis_callback:
            try:
                await self.crisis_callback(True)
            except Exception:
                pass
            self.stop()
            return  # Caller handles the view transition; skip normal post-combat UI

        # Build post-combat view (Fight Again button or stamina cooldown field)
        stamina_data = await self.bot.database.users.get_stamina(self.user_id)
        stamina = stamina_data["combat_stamina"]

        if stamina == 0:
            equipped_boot = await self.bot.database.equipment.get_equipped(
                self.user_id, "boot"
            )
            speedster_reduction = 0
            if equipped_boot and equipped_boot["passive"] == "speedster":
                speedster_reduction = equipped_boot["passive_lvl"] * 60
            cooldown = max(
                timedelta(seconds=10),
                _COMBAT_COOLDOWN - timedelta(seconds=speedster_reduction),
            )
            last_combat_str = await self.bot.database.users.get_timer(
                self.user_id, "last_combat"
            )
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
            embed.add_field(
                name="⚡ Stamina",
                value=f"Out of stamina — next combat in **{time_str}**",
                inline=False,
            )

        # If the player levelled up during this fight, show the stat-package picker
        # before the Fight Again button.  The picker's on_done callback fires the
        # final post-combat edit, so we return early here.
        pending_packages = await self.bot.database.users.get_pending_packages(
            self.user_id, self.server_id
        )
        if pending_packages:
            _victory_embed = embed  # captured for the on_done closure
            _stamina = stamina
            _rematch = self.rematch_callback

            async def _after_packages(msg):
                """Transition to the post-combat view once all packages are chosen."""
                post_view = (
                    PostCombatView(
                        self.bot,
                        self.user_id,
                        self.server_id,
                        self.player,
                        _stamina,
                        _rematch,
                    )
                    if _rematch
                    else None
                )
                await msg.edit(embed=_victory_embed, view=post_view)
                if post_view:
                    post_view.message = msg

            picker = StatPackagePicker(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                pending_packages,
                on_done=_after_packages,
            )
            await message.edit(embed=picker.build_embed(), view=picker)
            picker.message = message
            self.stop()
            return

        post_view = (
            PostCombatView(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                stamina,
                self.rematch_callback,
            )
            if self.rematch_callback
            else None
        )

        await message.edit(embed=embed, view=post_view)
        if post_view:
            post_view.message = message
        self.stop()
