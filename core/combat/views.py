# core/combat/views.py

import asyncio
import random

import discord
from discord import ButtonStyle, Interaction, ui

import core.slayer.mechanics
from core.base_view import BaseView
from core.combat import engine, rewards
from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.combat_log import CombatLogger
from core.combat.economy.drops import (
    DropManager,
    apply_boss_sigil_drops,
    apply_corrupted_monster_drops,
)
from core.combat.economy.experience import ExperienceManager
from core.combat.gen.gen_mob import generate_boss
from core.combat.views_lucifer import InfernalContractView, LuciferChoiceView
from core.companions.mechanics import CompanionMechanics
from core.images import (
    BOSS_APHRODITE,
    BOSS_GEMINI_PET,
    BOSS_LUCIFER,
    BOSS_NEET,
    MONSTER_EVELYNN_PRECURSOR,
    VICTORY_APHRODITE_GEMINI,
    VICTORY_CELESTIAL,
    VICTORY_EVELYNN,
    VICTORY_GEMINI,
    VICTORY_INFERNAL,
    VICTORY_LUCIFER,
    VICTORY_NEET,
)
from core.models import Monster, Player

# ---------------------------------------------------------------------------
# Uber boss configuration
# Each entry drives the generic engram / blueprint / stone reward logic.
# Keys that need custom post-processing (Lucifer → contract; Evelynn → puzzle
# box + mirage runes) still use _handle_uber_engram_and_blueprint but handle
# their unique steps in their own handler.
# ---------------------------------------------------------------------------
_UBER_CONFIGS: dict[str, dict] = {
    "Aphrodite": {
        "engram_fn": "increment_engrams",
        "engram_display": "Celestial Engram",
        "engram_msg": "🌌 **A Celestial Engram materializes from Aphrodite's shattered form...**",
        "blueprint_key": "celestial_blueprint_unlocked",
        "blueprint_fn": "set_blueprint_unlocked",
        "blueprint_display": "Celestial Shrine Blueprint",
        "blueprint_msg": "📜 **You found the Celestial Shrine Blueprint!**",
        "stone_currency": "celestial_stone",
        "stone_display": "Celestial Stone",
        "stone_msg": "🪨 **You found a Celestial Stone!**",
        "victory_image": VICTORY_CELESTIAL,
        "image_fn": "set_image",
        "embed_title": "🌌 Apex Shattered!",
    },
    "Lucifer": {
        "engram_fn": "increment_infernal_engrams",
        "engram_display": "Infernal Engram",
        "engram_msg": "🔥 **An Infernal Engram crystallises from Lucifer's shattered crown...**",
        "blueprint_key": "infernal_blueprint_unlocked",
        "blueprint_fn": "set_infernal_blueprint_unlocked",
        "blueprint_display": "Infernal Forge Blueprint",
        "blueprint_msg": "📜 **You found the Infernal Forge Blueprint!**",
        "stone_currency": "infernal_cinder",
        "stone_display": "Infernal Cinder",
        "stone_msg": "🔥 **The forge roars. You extract an Infernal Cinder.**",
        "victory_image": VICTORY_INFERNAL,
        "image_fn": "set_image",
        "embed_title": "🔥 Infernal Sovereign Defeated!",
    },
    "NEET": {
        "engram_fn": "increment_void_engrams",
        "engram_display": "Void Engram",
        "engram_msg": "⬛ **A Void Engram crystallises from the collapsing rift...**",
        "blueprint_key": "void_blueprint_unlocked",
        "blueprint_fn": "set_void_blueprint_unlocked",
        "blueprint_display": "Void Sanctum Blueprint",
        "blueprint_msg": "📜 **You found the Void Sanctum Blueprint!**",
        "stone_currency": "void_crystal",
        "stone_display": "Void Crystal",
        "stone_msg": "🔮 **The void yields a Void Crystal.**",
        "victory_image": VICTORY_NEET,
        "image_fn": "set_thumbnail",
        "embed_title": "⬛ Void Sovereign Defeated!",
    },
    "Castor": {  # Gemini twins — matched by "Castor" substring
        "engram_fn": "increment_gemini_engrams",
        "engram_display": "Gemini Engram",
        "engram_msg": "♊ **A Gemini Engram crystallises from the twins' shattered bond...**",
        "blueprint_key": "gemini_blueprint_unlocked",
        "blueprint_fn": "set_gemini_blueprint_unlocked",
        "blueprint_display": "Twin Shrine Blueprint",
        "blueprint_msg": "📜 **You found the Twin Shrine Blueprint!**",
        "stone_currency": "bound_crystal",
        "stone_display": "Bound Crystal",
        "stone_msg": "💎 **The twins' bond yields a Bound Crystal.**",
        "victory_image": VICTORY_GEMINI,
        "image_fn": "set_image",
        "embed_title": "♊ Bound Sovereigns Defeated!",
    },
    "Evelynn": {
        "engram_fn": "increment_corruption_engrams",
        "engram_display": "Corruption Engram",
        "engram_msg": "☠️ **A Corruption Engram crystallises from the primordial rot...**",
        "blueprint_key": "corruption_blueprint_unlocked",
        "blueprint_fn": "set_corruption_blueprint_unlocked",
        "blueprint_display": "Shrine of Corruption Blueprint",
        "blueprint_msg": "📜 **You found the Shrine of Corruption Blueprint!**",
        "stone_currency": "corrupted_crystal",
        "stone_display": "Corrupted Crystal",
        "stone_msg": "☠️ **The corruption yields a Corrupted Crystal.**",
        "victory_image": VICTORY_EVELYNN,
        "image_fn": "set_image",
        "embed_title": "☠️ Origin of Corruption Shattered!",
    },
}


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
    ):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.monster = monster
        self.logs = initial_logs or {}
        self.post_combat_view = post_combat_view

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

    def _get_boss_pet_image(self, boss_name: str) -> str:
        if "NEET" in boss_name:
            return BOSS_NEET
        if "Aphrodite" in boss_name:
            return BOSS_APHRODITE
        if "Gemini" in boss_name:
            return BOSS_GEMINI_PET
        if "Lucifer" in boss_name:
            return BOSS_LUCIFER
        if "Evelynn" in boss_name:
            return MONSTER_EVELYNN_PRECURSOR
        return None

    # --- Uber encounter helpers ---

    def _uber_dmg_frac(self) -> float:
        return max(
            0.0,
            min(
                1.0,
                (self.monster.max_hp - max(0, self.monster.hp)) / self.monster.max_hp,
            ),
        )

    @staticmethod
    def _calc_uber_curios(dmg_frac: float) -> int:
        if dmg_frac >= 1.0:
            return 3
        if dmg_frac >= 0.66:
            return 2
        if dmg_frac >= 0.33:
            return 1
        return 0

    async def _uber_defeat(
        self, message, dmg_frac: float = 0.0, curios_gained: int = 0
    ) -> None:
        base_loss = int(self.player.exp * 0.10)
        xp_loss = await ExperienceManager.remove_experience(
            self.bot, self.user_id, self.player, base_loss
        )
        self.player.current_hp = 1
        embed = combat_ui.create_defeat_embed(
            self.player,
            self.monster,
            xp_loss,
            curios_gained=curios_gained,
            dmg_frac=dmg_frac,
            killing_blow=self.killing_blow,
        )
        await message.edit(embed=embed, view=self.post_combat_view)
        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)
        self.stop()

    async def _uber_finalize_rewards(self, reward_data: dict) -> None:
        """Apply XP, gold, soulreap, and persist player. Mutates reward_data xp field."""
        exp_changes = await ExperienceManager.add_experience(
            self.bot, self.user_id, self.player, reward_data["xp"]
        )
        reward_data["xp"] = exp_changes["xp_added"]
        reward_data["msgs"].extend(exp_changes["msgs"])
        await self.bot.database.users.modify_gold(self.user_id, reward_data["gold"])
        if self.player.get_weapon_infernal() == "soulreap":
            self.player.current_hp = self.player.total_max_hp
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)

    async def handle_end_state(self, message, interaction: Interaction):
        """Processes victory or defeat with Phase Logic."""

        if getattr(self.monster, "is_uber", False):
            if "Lucifer" in self.monster.name:
                await self._handle_uber_lucifer_end_state(message, interaction)
            elif "NEET" in self.monster.name:
                await self._handle_uber_neet_end_state(message, interaction)
            elif "Castor" in self.monster.name:
                await self._handle_uber_gemini_end_state(message, interaction)
            elif "Evelynn" in self.monster.name:
                await self._handle_uber_evelynn_end_state(message, interaction)
            else:
                await self._handle_uber_end_state(message, interaction)
            return

        if self.player.current_hp <= 0:
            # Defeat Logic (Same as before)
            self.combat_logger.log_combat_end(self.player, self.monster, "defeat")
            base_loss = int(self.player.exp * 0.10)
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

        elif self.monster.hp <= 0:
            # Victory Logic

            # --- PHASE CHECK ---
            if self.current_phase_index < len(self.combat_phases) - 1:
                # Prepare Next Phase
                self.current_phase_index += 1
                next_phase_data = self.combat_phases[self.current_phase_index]

                self.player.reset_combat_bonus()

                # Reset transients (Ward resets to base gear value, temporary invuln clears)
                # self.player.combat_ward = self.player.get_combat_ward_value()
                self.player.is_invulnerable_this_combat = False

                # Update Monster Object
                self.monster = await generate_boss(
                    self.player, self.monster, next_phase_data, self.current_phase_index
                )
                self.monster.is_boss = True

                # Apply Start Effects again
                engine.apply_stat_effects(self.player, self.monster)
                new_logs = engine.apply_combat_start_passives(self.player, self.monster)
                self.logs = new_logs

                # Transition Embed
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

                # Restart View with new Monster
                embed = combat_ui.create_combat_embed(
                    self.player,
                    self.monster,
                    new_logs,
                    title_override=f"⚔️ BOSS PHASE {self.current_phase_index+1}",
                )
                await message.edit(embed=embed, view=self)
                return  # Keep View Alive

            # --- FINAL VICTORY ---
            self.combat_logger.log_combat_end(self.player, self.monster, "victory")

            reward_data = rewards.calculate_rewards(self.player, self.monster)

            # Special Key Logic from rewards.py
            special_flags = rewards.check_special_drops(self.player, self.monster)
            reward_data["special"] = []

            await apply_boss_sigil_drops(
                self.bot, self.user_id, self.server_id, self.monster, reward_data
            )

            # --- Corrupted monster loot ---
            await apply_corrupted_monster_drops(
                self.bot, self.user_id, self.server_id, self.monster, reward_data
            )

            # Grant currencies / items based on special drop flags
            await rewards.apply_special_flags(
                self.bot, self.user_id, self.server_id, special_flags, reward_data
            )

            # Process Drops
            server_id = str(interaction.guild.id)
            await DropManager.process_drops(
                self.bot,
                self.user_id,
                server_id,
                self.player,
                self.monster.level,
                reward_data,
                monster=self.monster,
            )

            # Handle XP / Level Up
            exp_changes = await ExperienceManager.add_experience(
                self.bot, self.user_id, self.player, reward_data["xp"]
            )

            # Update reward_data so the Embed correctly shows 0 XP gained if protected
            reward_data["xp"] = exp_changes["xp_added"]
            reward_data["msgs"].extend(exp_changes["msgs"])

            self.combat_logger.log_rewards(self.player, reward_data)

            # DB Commits
            await self.bot.database.users.modify_gold(self.user_id, reward_data["gold"])

            # Companions
            current_pet_count = await self.bot.database.companions.get_count(
                self.user_id
            )
            boss_pet_triggered = False

            # 1. BOSS PET CHECK (3% Chance, Tier 3 Fixed)
            # Gemini boot: pet drop chance doubled (3% -> 6% boss, 5% -> 10% regular)
            _gemini_boot = self.player.get_boot_corrupted_essence() == "gemini"
            boss_pet_chance = 0.06 if _gemini_boot else 0.03
            regular_pet_chance = 0.10 if _gemini_boot else 0.05

            boss_img = self._get_boss_pet_image(self.monster.name)

            if self.monster.is_boss and boss_img and current_pet_count < 20:
                if random.random() < boss_pet_chance:
                    boss_pet_triggered = True

                    # Generate Tier 3 Passive
                    p_type, p_tier = CompanionMechanics.roll_boss_passive()

                    # Add to DB
                    # We strip title/epithets for the pet name (e.g. "Lucifer, Fallen" -> "Lucifer")
                    pet_name = self.monster.name.split(",")[0]

                    await self.bot.database.companions.add_companion(
                        self.user_id,
                        name=pet_name,
                        species="Boss",
                        image=boss_img,
                        p_type=p_type,
                        p_tier=p_tier,
                    )

                    # Initialize Collection Timer (Standard pet behavior)
                    await self.bot.database.users.initialize_companion_timer(
                        self.user_id
                    )

                    # --- SPECIAL EVENT: TAMING CUTSCENE ---
                    tame_embed = discord.Embed(
                        title="⚠️ ANOMALY DETECTED ⚠️",
                        description=f"The spirit of **{pet_name}** refuses to fade...\nIt binds itself to your soul!",
                        color=discord.Color.dark_theme(),  # Almost black background
                    )
                    tame_embed.set_image(url=boss_img)
                    tame_embed.add_field(
                        name="LEGENDARY TAMING",
                        value=f"You have obtained **{pet_name}** (Tier {p_tier} Passive)!",
                        inline=False,
                    )
                    tame_embed.set_footer(
                        text="A Boss Companion has joined your roster."
                    )

                    # Show the cutscene for 5 seconds
                    await message.edit(embed=tame_embed, view=None)
                    await asyncio.sleep(5)

                    reward_data["msgs"].append(
                        f"👑 **LEGENDARY:** {pet_name} joined your roster!"
                    )

            if (
                not boss_pet_triggered
                and not self.monster.is_boss
                and current_pet_count < 20
                and random.random() < regular_pet_chance
            ):
                # Roll Stats
                p_type, p_tier = CompanionMechanics.roll_new_passive(is_capture=True)

                # Add to DB
                await self.bot.database.companions.add_companion(
                    self.user_id,
                    name=self.monster.name,
                    species=self.monster.species,
                    image=self.monster.image,
                    p_type=p_type,
                    p_tier=p_tier,
                )

                # Add notification
                reward_data["msgs"].append(
                    f"🕸️ Following it's defeat, the {self.monster.name} decides to join you on your journey!"
                )
            # --- SLAYER INTEGRATION ---
            if not self.monster.is_boss:
                s_profile = await self.bot.database.slayer.get_profile(
                    self.user_id, server_id
                )

                if s_profile["active_task_species"] == self.monster.species:
                    slayer_lines = []

                    # 1. Base Slayer XP + Drops
                    await self.bot.database.slayer.add_rewards(
                        self.user_id, server_id, xp=500, points=0
                    )
                    slayer_lines.append("+500 Slayer XP")

                    ess, heart = core.slayer.mechanics.SlayerMechanics.roll_drops(
                        self.monster.level
                    )
                    # Scavenger passive (e.g. 5% chance per tier to double drops)
                    drop_bonus_tiers = self.player.get_emblem_bonus("slayer_drops")
                    if drop_bonus_tiers > 0 and random.random() < (
                        drop_bonus_tiers * 0.05
                    ):
                        ess *= 2
                        heart *= 2

                    if ess > 0:
                        await self.bot.database.slayer.modify_materials(
                            self.user_id, server_id, "violent_essence", ess
                        )
                        slayer_lines.append("Found a **Violent Essence**!")
                    if heart > 0:
                        await self.bot.database.slayer.modify_materials(
                            self.user_id, server_id, "imbued_heart", heart
                        )
                        slayer_lines.append("Found an **Imbued Heart**!")

                    # Taskmaster passive (e.g. 5% chance per tier for double progress)
                    prog_gain = 1
                    task_tiers = self.player.get_emblem_bonus("task_progress")
                    if task_tiers > 0 and random.random() < (task_tiers * 0.05):
                        prog_gain = 2
                        slayer_lines.append(
                            "⚡ **Taskmaster** granted double task progress!"
                        )

                    # Yvenn sig: +T bonus progress per kill
                    if reward_data.get("yvenn_slayer_bonus"):
                        prog_gain += reward_data["yvenn_slayer_bonus"]

                    # 2. Progress Tracker
                    new_prog = s_profile["active_task_progress"] + prog_gain

                    if new_prog >= s_profile["active_task_amount"]:
                        # Task Complete!
                        burst_xp, burst_pts = (
                            core.slayer.mechanics.SlayerMechanics.calculate_task_rewards(
                                s_profile["active_task_amount"]
                            )
                        )
                        await self.bot.database.slayer.add_rewards(
                            self.user_id, server_id, xp=burst_xp, points=burst_pts
                        )
                        await self.bot.database.slayer.clear_task(
                            self.user_id, server_id
                        )
                        slayer_lines.append(
                            f"🏆 **Task Complete!** +{burst_xp} Slayer XP | +{burst_pts} Slayer Pts"
                        )
                    else:
                        await self.bot.database.slayer.update_task_progress(
                            self.user_id, server_id, 1
                        )
                        slayer_lines.append(
                            f"Progress: {new_prog}/{s_profile['active_task_amount']} {self.monster.species}"
                        )

                    # 3. Level Up Check
                    new_s_xp = (
                        s_profile["xp"]
                        + 100
                        + (
                            burst_xp
                            if new_prog >= s_profile["active_task_amount"]
                            else 0
                        )
                    )
                    new_s_lvl = (
                        core.slayer.mechanics.SlayerMechanics.calculate_level_from_xp(
                            new_s_xp
                        )
                    )
                    if new_s_lvl > s_profile["level"]:
                        await self.bot.database.slayer.update_level(
                            self.user_id, server_id, new_s_lvl
                        )
                        slayer_lines.append(
                            f"🎉 **Slayer Level Up!** You are now Level {new_s_lvl}."
                        )

                    reward_data["msgs"].append(
                        "🩸 **Slayer Task**\n" + "\n".join(slayer_lines)
                    )
            # --- PARTNER END REWARDS ---
            if self.player.active_partner:
                from core.combat.economy.rewards import apply_partner_end_rewards

                partner = self.player.active_partner
                lvl_msgs = apply_partner_end_rewards(self.player, reward_data["xp"])
                await self.bot.database.partners.update_exp(
                    self.user_id, partner.partner_id, partner.exp, partner.level
                )
                await self.bot.database.partners.increment_affinity(
                    self.user_id, partner.partner_id
                )
                if lvl_msgs:
                    reward_data["msgs"].append(
                        f"🤝 **{partner.name}** reached level **{partner.level}**!"
                    )

            # --------------------------
            embed = combat_ui.create_victory_embed(
                self.player, self.monster, reward_data
            )

            # Final Boss Scenes
            if "Aphrodite" in self.monster.name or "Gemini" in self.monster.name:
                embed.set_thumbnail(url=VICTORY_APHRODITE_GEMINI)
                await message.edit(embed=embed, view=None)
            elif "NEET" in self.monster.name:
                embed.set_thumbnail(url=VICTORY_NEET)
                if random.random() < 0.30:
                    embed.add_field(
                        name="Loot", value="Found a **Void Key**.", inline=False
                    )
                    await self.bot.database.users.modify_currency(
                        self.user_id, "void_keys", 1
                    )
                await message.edit(embed=embed, view=None)
            elif "Lucifer" in self.monster.name:
                embed.set_thumbnail(url=VICTORY_LUCIFER)
                embed.add_field(
                    name="❤️‍🔥 A Soul Core manifests...",
                    value=(
                        "**Choose how to absorb its power:**\n"
                        "❤️‍🔥 **Enraged:** Modifies Attack (-1 to +2)\n"
                        "💙 **Solidified:** Modifies Defence (1- to +2)\n"
                        "💔 **Unstable:** Shuffles Stats towards equilibrium\n"
                        "💞 **Inverse:** Swaps Attack and Defence values\n"
                        "🖤 **Keep:** Store a singular Soul Core"
                    ),
                    inline=False,
                )
                ping_msg = await message.channel.send(
                    f"<@{self.user_id}> A Soul Core has manifested — make your choice!\n\nBattle: {message.jump_url}"
                )
                await ping_msg.delete(delay=45)
                contract_choice_view = LuciferChoiceView(
                    self.bot, self.user_id, self.player
                )
                await message.edit(
                    embed=embed,
                    view=contract_choice_view,
                )
                contract_choice_view.message = message
                return  # Lucifer View takes over
            else:
                await message.edit(embed=embed, view=None)

            # Soulreap: restore HP to full after every successful encounter
            if self.player.get_weapon_infernal() == "soulreap":
                self.player.current_hp = self.player.total_max_hp

            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)
            self.stop()

    # --- Uber helper methods ---

    async def _uber_setup(self, message) -> dict | None:
        """
        Shared first step for all uber handlers.

        Rolls damage fraction → curio count → grants curios.
        If the player is defeated, triggers the defeat flow and returns None.
        On victory, returns a fresh reward_data dict with xp/gold doubled and
        curios pre-populated — ready for handler-specific drops.
        """
        dmg_frac = self._uber_dmg_frac()
        curios = self._calc_uber_curios(dmg_frac)
        await self.bot.database.users.modify_currency(self.user_id, "curios", curios)

        if self.player.current_hp <= 0:
            await self._uber_defeat(message, dmg_frac=dmg_frac, curios_gained=curios)
            return None

        reward_data = rewards.calculate_rewards(self.player, self.monster)
        reward_data["xp"] *= 2
        reward_data["gold"] *= 2
        reward_data["curios"] = curios
        reward_data["special"] = []
        return reward_data

    async def _handle_uber_engram_and_blueprint(
        self, reward_data: dict, cfg: dict
    ) -> None:
        """
        Rolls the standard 10% engram and 10% blueprint/stone drops
        for an uber boss, driven by a config entry from _UBER_CONFIGS.
        Mutates reward_data in-place.
        """
        if random.random() < 0.10:
            engram_fn = getattr(self.bot.database.uber, cfg["engram_fn"])
            await engram_fn(self.user_id, self.server_id, 1)
            reward_data["special"].append(cfg["engram_display"])
            reward_data["msgs"].append(cfg["engram_msg"])

        if random.random() < 0.10:
            u_prog = await self.bot.database.uber.get_uber_progress(
                self.user_id, self.server_id
            )
            if not u_prog.get(cfg["blueprint_key"]):
                blueprint_fn = getattr(self.bot.database.uber, cfg["blueprint_fn"])
                await blueprint_fn(self.user_id, self.server_id, True)
                reward_data["special"].append(cfg["blueprint_display"])
                reward_data["msgs"].append(cfg["blueprint_msg"])
            else:
                await self.bot.database.users.modify_currency(
                    self.user_id, cfg["stone_currency"], 1
                )
                reward_data["special"].append(cfg["stone_display"])
                reward_data["msgs"].append(cfg["stone_msg"])

    async def _uber_complete_standard(
        self, message, cfg: dict, reward_data: dict
    ) -> None:
        """
        Finalizes rewards, builds and edits the victory embed, clears state,
        and stops the view. Used by all standard uber handlers (not Lucifer).
        """
        await self._uber_finalize_rewards(reward_data)
        embed = combat_ui.create_victory_embed(self.player, self.monster, reward_data)
        embed.title = cfg["embed_title"]
        getattr(embed, cfg["image_fn"])(url=cfg["victory_image"])
        await message.edit(embed=embed, view=self.post_combat_view)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    # --- Uber encounter end-state handlers ---

    async def _handle_uber_end_state(self, message, interaction: Interaction):
        """Uber Aphrodite (generic fallback)."""
        reward_data = await self._uber_setup(message)
        if reward_data is None:
            return
        cfg = _UBER_CONFIGS["Aphrodite"]
        await self._handle_uber_engram_and_blueprint(reward_data, cfg)
        await self._uber_complete_standard(message, cfg, reward_data)

    async def _handle_uber_lucifer_end_state(self, message, interaction: Interaction):
        """Uber Lucifer — standard engram/blueprint + Infernal Contract view."""
        reward_data = await self._uber_setup(message)
        if reward_data is None:
            return
        cfg = _UBER_CONFIGS["Lucifer"]
        await self._handle_uber_engram_and_blueprint(reward_data, cfg)
        await self._uber_finalize_rewards(reward_data)

        embed = combat_ui.create_victory_embed(self.player, self.monster, reward_data)
        embed.title = cfg["embed_title"]
        embed.set_image(url=cfg["victory_image"])
        contract_view = InfernalContractView(
            self.bot, self.user_id, self.player, self.server_id, message
        )
        embed.add_field(
            name="🩸 An Infernal Contract materialises...",
            value=contract_view.contract_summary(),
            inline=False,
        )
        await message.edit(embed=embed, view=contract_view)
        self.stop()

    async def _handle_uber_neet_end_state(self, message, interaction: Interaction):
        """Uber NEET."""
        reward_data = await self._uber_setup(message)
        if reward_data is None:
            return
        cfg = _UBER_CONFIGS["NEET"]
        await self._handle_uber_engram_and_blueprint(reward_data, cfg)
        await self._uber_complete_standard(message, cfg, reward_data)

    async def _handle_uber_gemini_end_state(self, message, interaction: Interaction):
        """Uber Gemini Twins."""
        reward_data = await self._uber_setup(message)
        if reward_data is None:
            return
        cfg = _UBER_CONFIGS["Castor"]
        await self._handle_uber_engram_and_blueprint(reward_data, cfg)
        await self._uber_complete_standard(message, cfg, reward_data)

    async def _handle_uber_evelynn_end_state(self, message, interaction: Interaction):
        """Uber Evelynn — Origin of Corruption.

        Differs from the standard pattern:
          - Guaranteed Curio Puzzle Box before the engram/blueprint rolls.
          - Extra Rune of Mirage (Imperfect) at 1% and (Perfected) at 0.1%.
        """
        reward_data = await self._uber_setup(message)
        if reward_data is None:
            return
        cfg = _UBER_CONFIGS["Evelynn"]

        # Guaranteed: Curio Puzzle Box
        await self.bot.database.users.modify_currency(
            self.user_id, "curio_puzzle_boxes", 1
        )
        reward_data["special"].append("Curio Puzzle Box")
        reward_data["msgs"].append(
            "📦 **A Curio Puzzle Box materialises from Evelynn's shattered form...**"
        )

        await self._handle_uber_engram_and_blueprint(reward_data, cfg)

        # 1% — Rune of Mirage (Imperfect)
        if random.random() < 0.01:
            await self.bot.database.users.modify_currency(
                self.user_id, "mirage_runes_imperfect", 1
            )
            reward_data["special"].append("Rune of Mirage (Imperfect)")
            reward_data["msgs"].append(
                "🪞 **A Rune of Mirage (Imperfect) fractures from the Origin's corruption...**"
            )

        # 0.1% — Rune of Mirage (Perfected)
        if random.random() < 0.001:
            await self.bot.database.users.modify_currency(
                self.user_id, "mirage_runes_perfected", 1
            )
            reward_data["special"].append("Rune of Mirage (Perfected)")
            reward_data["msgs"].append(
                "🪞 **A Rune of Mirage (Perfected) crystallises from the primordial void...**"
            )

        await self._uber_complete_standard(message, cfg, reward_data)
