# core/combat/views.py

import asyncio
import random

import discord
from discord import ButtonStyle, Interaction, ui

import core.slayer.mechanics
from core.combat import engine, rewards
from core.combat import ui as combat_ui
from core.combat.combat_log import CombatLogger
from core.combat.drops import DropManager
from core.combat.experience import ExperienceManager
from core.combat.gen_mob import generate_boss
from core.combat.views_lucifer import InfernalContractView, LuciferChoiceView
from core.companions.mechanics import CompanionMechanics
from core.models import Monster, Player


class CombatView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        monster: Monster,
        initial_logs: dict,
        combat_phases=None,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.monster = monster
        self.logs = initial_logs or {}

        # Boss / Chain Handling
        self.combat_phases = combat_phases or []  # List of dicts
        self.current_phase_index = 0
        self._auto_running = False
        self._was_auto = False
        self.killing_blow = 0

        self.combat_logger = CombatLogger(player, monster)
        self.combat_logger.log_combat_start(player, monster)

        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

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

        self.combat_logger.log_combat_end(self.player, self.monster, "timeout")
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def update_buttons(self):
        # Toggle buttons based on current state (Enabled if both alive, Disabled if one dead)
        is_over = self.player.current_hp <= 0 or self.monster.hp <= 0
        for child in self.children:
            child.disabled = is_over

    def _do_monster_turn(self) -> str:
        hp_before = self.player.current_hp
        log = engine.process_monster_turn(self.player, self.monster)
        self.killing_blow = hp_before - max(0, self.player.current_hp)
        self.combat_logger.log_monster_turn(log, self.player)
        return log

    async def refresh_embed(self, interaction: Interaction):
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

        while True:
            # Inner loop: fight the current phase to completion
            while self.player.current_hp > hp_threshold and self.monster.hp > 0:
                p_log = engine.process_player_turn(self.player, self.monster)
                self.combat_logger.log_player_turn(p_log, self.monster)
                m_log = ""
                if self.monster.hp > 0:
                    m_log = self._do_monster_turn()

                self.logs = {self.player.name: p_log, self.monster.name: m_log}

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
            return "https://i.imgur.com/V5Hd9d9.png"
        if "Aphrodite" in boss_name:
            return "https://i.imgur.com/26dzbFN.jpeg"
        if "Gemini" in boss_name:
            return "https://i.imgur.com/YL7WPXS.jpeg"
        if "Lucifer" in boss_name:
            return "https://i.imgur.com/tIcLLI1.png"
        return None

    # --- Uber encounter helpers ---

    def _uber_dmg_frac(self) -> float:
        return max(
            0.0,
            min(1.0, (self.monster.max_hp - max(0, self.monster.hp)) / self.monster.max_hp),
        )

    @staticmethod
    def _calc_uber_curios(dmg_frac: float) -> int:
        if dmg_frac >= 1.0:
            return 5
        if dmg_frac >= 0.75:
            return 4
        if dmg_frac >= 0.50:
            return 3
        if dmg_frac >= 0.25:
            return 2
        return 1

    async def _uber_defeat(self, message) -> None:
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

    async def handle_end_state(self, message, interaction: Interaction):
        """Processes victory or defeat with Phase Logic."""

        if getattr(self.monster, "is_uber", False):
            if "Lucifer" in self.monster.name:
                await self._handle_uber_lucifer_end_state(message, interaction)
            elif "NEET" in self.monster.name:
                await self._handle_uber_neet_end_state(message, interaction)
            elif "Castor" in self.monster.name:
                await self._handle_uber_gemini_end_state(message, interaction)
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

            if "Lucifer" in self.monster.name and not getattr(
                self.monster, "is_uber", False
            ):
                _, forge_workers = (
                    await self.bot.database.settlement.get_building_details(
                        self.user_id, self.server_id, "infernal_forge"
                    )
                )
                # Always drops 1 sigil; Infernal Forge shrine gives a chance at a second
                sigils_dropped = 1
                if random.random() < (forge_workers * 0.0001):
                    sigils_dropped += 1
                await self.bot.database.uber.increment_infernal_sigils(
                    self.user_id, self.server_id, sigils_dropped
                )
                reward_data["special"].extend(["Infernal Sigil"] * sigils_dropped)

            if "NEET" in self.monster.name and not getattr(
                self.monster, "is_uber", False
            ):
                _, sanctum_workers = (
                    await self.bot.database.settlement.get_building_details(
                        self.user_id, self.server_id, "void_sanctum"
                    )
                )
                # Always drops 1 shard; Void Sanctum shrine gives a chance at a second
                shards_dropped = 1
                if random.random() < (sanctum_workers * 0.0001):
                    shards_dropped += 1
                await self.bot.database.uber.increment_void_shards(
                    self.user_id, self.server_id, shards_dropped
                )
                reward_data["special"].extend(["Void Sigil"] * shards_dropped)

            if "Aphrodite" in self.monster.name and not getattr(
                self.monster, "is_uber", False
            ):
                _, shrine_workers = (
                    await self.bot.database.settlement.get_building_details(
                        self.user_id, self.server_id, "celestial_shrine"
                    )
                )
                # Always drops 1 sigil; Celestial Shrine gives a chance at a second
                sigils_dropped = 1
                if random.random() < (shrine_workers * 0.0001):
                    sigils_dropped += 1
                await self.bot.database.uber.increment_sigils(
                    self.user_id, self.server_id, sigils_dropped
                )
                reward_data["special"].extend(["Celestial Sigil"] * sigils_dropped)

            if "Gemini" in self.monster.name and not getattr(
                self.monster, "is_uber", False
            ):
                _, shrine_workers = (
                    await self.bot.database.settlement.get_building_details(
                        self.user_id, self.server_id, "twin_shrine"
                    )
                )
                # 100% base drop, shrine workers give a fractional chance at a 2nd
                total_chance = 1.0 + (shrine_workers * 0.0001)
                guaranteed = int(total_chance)
                fractional = total_chance - guaranteed
                sigils_dropped = guaranteed
                if random.random() < fractional:
                    sigils_dropped += 1
                await self.bot.database.uber.increment_gemini_sigils(
                    self.user_id, self.server_id, sigils_dropped
                )
                reward_data["special"].extend(["Gemini Sigil"] * sigils_dropped)

            # Grant Currencies based on flags
            for key, val in special_flags.items():
                if val:
                    # Mapping logic needed here or simple ifs
                    if key == "draconic_key":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "dragon_key", 1
                        )
                        reward_data["special"].append("Draconic Key")
                    elif key == "angelic_key":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "angel_key", 1
                        )
                        reward_data["special"].append("Angelic Key")
                    elif key == "soul_core":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "soul_cores", 1
                        )
                        reward_data["special"].append("Soul Core")
                    elif key == "void_frag":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "void_frags", 1
                        )
                        reward_data["special"].append("Void Fragment")
                    elif key == "balance_fragment":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "balance_fragment", 1
                        )
                        reward_data["special"].append("Fragment of Balance")
                    elif key == "curio":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "curios", 1
                        )
                        reward_data["curios"] = 1
                    # Boss/Special Runes
                    elif key == "refinement_rune":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "refinement_runes", 1
                        )
                        reward_data["special"].append("Rune of Refinement")

                    elif key == "potential_rune":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "potential_runes", 1
                        )
                        reward_data["special"].append("Rune of Potential")

                    elif key == "imbue_rune":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "imbue_runes", 1
                        )
                        reward_data["special"].append("Rune of Imbuing")

                    elif key == "shatter_rune":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "shatter_runes", 1
                        )
                        reward_data["special"].append("Rune of Shattering")

                    elif key == "partnership_rune":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "partnership_runes", 1
                        )
                        reward_data["special"].append("Rune of Partnership")
                    elif key == "magma_core":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "magma_core", 1
                        )
                        reward_data["special"].append("Magma Core")
                    elif key == "life_root":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "life_root", 1
                        )
                        reward_data["special"].append("Life Root")
                    elif key == "spirit_shard":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "spirit_shard", 1
                        )
                        reward_data["special"].append("Spirit Shard")
                    elif key == "spirit_stone":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "spirit_stones", 1
                        )
                        reward_data["special"].append("🔮 Spirit Stone")
                    elif key == "antique_tome":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "antique_tome", 1
                        )
                        reward_data["special"].append("📖 Antique Tome")
                    elif key == "pinnacle_key":
                        await self.bot.database.users.modify_currency(
                            self.user_id, "pinnacle_key", 1
                        )
                        reward_data["special"].append("🗝️ Pinnacle Key")
                    elif key == "blessed_bismuth":
                        await self.bot.database.uber.increment_blessed_bismuth(
                            self.user_id, self.server_id, 1
                        )
                        reward_data["special"].append("⚗️ Blessed Bismuth")
                    elif key == "sparkling_sprig":
                        await self.bot.database.uber.increment_sparkling_sprig(
                            self.user_id, self.server_id, 1
                        )
                        reward_data["special"].append("🌿 Sparkling Sprig")
                    elif key == "capricious_carp":
                        await self.bot.database.uber.increment_capricious_carp(
                            self.user_id, self.server_id, 1
                        )
                        reward_data["special"].append("🐟 Capricious Carp")
                    elif key == "guild_ticket":
                        await self.bot.database.partners.add_tickets(self.user_id, 1)
                        reward_data["special"].append("🎫 Guild Ticket")
                    elif key == "velour_doubled":
                        # Double all currently-queued special drops
                        reward_data["special"] = reward_data["special"] * 2
                    elif key == "yvenn_slayer_bonus" and isinstance(val, int):
                        # Bonus slayer progress (already handled in slayer block below,
                        # but store count for messaging)
                        reward_data["yvenn_slayer_bonus"] = val

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
                    # 1. Base Slayer XP + Drops
                    await self.bot.database.slayer.add_rewards(
                        self.user_id, server_id, xp=500, points=0
                    )

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
                    if heart > 0:
                        await self.bot.database.slayer.modify_materials(
                            self.user_id, server_id, "imbued_heart", heart
                        )

                    # Log additions
                    reward_data["msgs"].append("🩸 **Slayer:** +500 Slayer XP")
                    if ess > 0:
                        reward_data["msgs"].append("🩸 Found a **Violent Essence**!")
                    if heart > 0:
                        reward_data["msgs"].append("❤️ Found an **Imbued Heart**!")

                    # Taskmaster passive (e.g. 5% chance per tier for double progress)
                    prog_gain = 1
                    task_tiers = self.player.get_emblem_bonus("task_progress")
                    if task_tiers > 0 and random.random() < (task_tiers * 0.05):
                        prog_gain = 2
                        reward_data["msgs"].append(
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
                        reward_data["msgs"].append(
                            f"🏆 **Task Complete!** +{burst_xp} Slayer XP | +{burst_pts} Slayer Pts"
                        )
                    else:
                        await self.bot.database.slayer.update_task_progress(
                            self.user_id, server_id, 1
                        )
                        reward_data["msgs"].append(
                            f"📋 Progress: {new_prog}/{s_profile['active_task_amount']} {self.monster.species}"
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
                        reward_data["msgs"].append(
                            f"🎉 **Slayer Level Up!** You are now Level {new_s_lvl}."
                        )
            # --- PARTNER END REWARDS ---
            if self.player.active_partner:
                from core.combat.rewards import apply_partner_end_rewards

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
            if "Aphrodite" in self.monster.name:
                embed.set_image(url="https://i.imgur.com/wKyTFzh.jpg")
                await message.edit(embed=embed, view=None)
            elif "NEET" in self.monster.name:
                embed.set_image(url="https://i.imgur.com/7UmY4Mo.jpeg")
                embed.add_field(
                    name="Loot", value="Found a **Void Key**.", inline=False
                )
                await self.bot.database.users.modify_currency(
                    self.user_id, "void_keys", 1
                )
                await message.edit(embed=embed, view=None)
            elif "Lucifer" in self.monster.name:
                embed.set_thumbnail(url="https://i.imgur.com/oFWJLo7.jpeg")
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
                ping_content = (
                    f"<@{self.user_id}> A Soul Core has manifested — make your choice!"
                    if self._was_auto
                    else None
                )
                contract_choice_view = LuciferChoiceView(
                    self.bot, self.user_id, self.player
                )
                await message.edit(
                    content=ping_content,
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
            self.stop()

    async def _handle_uber_end_state(self, message, interaction: Interaction):
        """Uber Aphrodite."""
        curios = self._calc_uber_curios(self._uber_dmg_frac())
        await self.bot.database.users.modify_currency(self.user_id, "curios", curios)

        if self.player.current_hp <= 0:
            await self._uber_defeat(message)
            return

        reward_data = rewards.calculate_rewards(self.player, self.monster)
        reward_data["xp"] *= 2
        reward_data["gold"] *= 2
        reward_data["curios"] = curios
        reward_data["special"] = []

        if random.random() < 0.10:
            await self.bot.database.uber.increment_engrams(self.user_id, self.server_id, 1)
            reward_data["special"].append("Celestial Engram")
            reward_data["msgs"].append(
                "🌌 **A Celestial Engram materializes from Aphrodite's shattered form...**"
            )

        if random.random() < 0.10:
            u_prog = await self.bot.database.uber.get_uber_progress(self.user_id, self.server_id)
            if not u_prog["celestial_blueprint_unlocked"]:
                await self.bot.database.uber.set_blueprint_unlocked(self.user_id, self.server_id, True)
                reward_data["special"].append("Celestial Shrine Blueprint")
                reward_data["msgs"].append("📜 **You found the Celestial Shrine Blueprint!**")
            else:
                await self.bot.database.users.modify_currency(self.user_id, "celestial_stone", 1)
                reward_data["special"].append("Celestial Stone")
                reward_data["msgs"].append("🪨 **You found a Celestial Stone!**")

        await self._uber_finalize_rewards(reward_data)

        embed = combat_ui.create_victory_embed(self.player, self.monster, reward_data)
        embed.title = "🌌 Apex Shattered!"
        embed.set_image(url="https://i.imgur.com/ffu5KX0.jpeg")
        await message.edit(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def _handle_uber_lucifer_end_state(self, message, interaction: Interaction):
        """Uber Lucifer."""
        curios = self._calc_uber_curios(self._uber_dmg_frac())
        await self.bot.database.users.modify_currency(self.user_id, "curios", curios)

        if self.player.current_hp <= 0:
            await self._uber_defeat(message)
            return

        reward_data = rewards.calculate_rewards(self.player, self.monster)
        reward_data["xp"] *= 2
        reward_data["gold"] *= 2
        reward_data["curios"] = curios
        reward_data["special"] = []

        if random.random() < 0.10:
            await self.bot.database.uber.increment_infernal_engrams(self.user_id, self.server_id, 1)
            reward_data["special"].append("Infernal Engram")
            reward_data["msgs"].append(
                "🔥 **An Infernal Engram crystallises from Lucifer's shattered crown...**"
            )

        if random.random() < 0.10:
            u_prog = await self.bot.database.uber.get_uber_progress(self.user_id, self.server_id)
            if not u_prog["infernal_blueprint_unlocked"]:
                await self.bot.database.uber.set_infernal_blueprint_unlocked(self.user_id, self.server_id, True)
                reward_data["special"].append("Infernal Forge Blueprint")
                reward_data["msgs"].append("📜 **You found the Infernal Forge Blueprint!**")
            else:
                await self.bot.database.users.modify_currency(self.user_id, "infernal_cinder", 1)
                reward_data["special"].append("Infernal Cinder")
                reward_data["msgs"].append("🔥 **The forge roars. You extract an Infernal Cinder.**")

        await self._uber_finalize_rewards(reward_data)

        embed = combat_ui.create_victory_embed(self.player, self.monster, reward_data)
        embed.title = "🔥 Sovereign Shattered!"
        embed.set_image(url="https://i.imgur.com/ngTUw77.png")

        contract_view = InfernalContractView(self.bot, self.user_id, self.player, self.server_id, message)
        embed.add_field(
            name="🩸 An Infernal Contract materialises...",
            value=contract_view.contract_summary(),
            inline=False,
        )
        await message.edit(embed=embed, view=contract_view)
        self.stop()

    async def _handle_uber_neet_end_state(self, message, interaction: Interaction):
        """Uber NEET."""
        curios = self._calc_uber_curios(self._uber_dmg_frac())
        await self.bot.database.users.modify_currency(self.user_id, "curios", curios)

        if self.player.current_hp <= 0:
            await self._uber_defeat(message)
            return

        reward_data = rewards.calculate_rewards(self.player, self.monster)
        reward_data["xp"] *= 2
        reward_data["gold"] *= 2
        reward_data["curios"] = curios
        reward_data["special"] = []

        if random.random() < 0.10:
            await self.bot.database.uber.increment_void_engrams(self.user_id, self.server_id, 1)
            reward_data["special"].append("Void Engram")
            reward_data["msgs"].append(
                "⬛ **A Void Engram crystallises from the collapsing rift...**"
            )

        if random.random() < 0.10:
            u_prog = await self.bot.database.uber.get_uber_progress(self.user_id, self.server_id)
            if not u_prog["void_blueprint_unlocked"]:
                await self.bot.database.uber.set_void_blueprint_unlocked(self.user_id, self.server_id, True)
                reward_data["special"].append("Void Sanctum Blueprint")
                reward_data["msgs"].append("📜 **You found the Void Sanctum Blueprint!**")
            else:
                await self.bot.database.users.modify_currency(self.user_id, "void_crystal", 1)
                reward_data["special"].append("Void Crystal")
                reward_data["msgs"].append("🔮 **The void yields a Void Crystal.**")

        await self.bot.database.users.modify_currency(self.user_id, "void_keys", 1)
        reward_data["special"].append("Void Key")
        reward_data["msgs"].append("🗝️ **A Void Key manifests from the collapsing rift.**")

        await self._uber_finalize_rewards(reward_data)

        embed = combat_ui.create_victory_embed(self.player, self.monster, reward_data)
        embed.title = "⬛ Void Sovereign Collapsed!"
        embed.set_image(url="https://i.imgur.com/7UmY4Mo.jpeg")
        await message.edit(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def _handle_uber_gemini_end_state(self, message, interaction: Interaction):
        """Uber Gemini Twins."""
        curios = self._calc_uber_curios(self._uber_dmg_frac())
        await self.bot.database.users.modify_currency(self.user_id, "curios", curios)

        if self.player.current_hp <= 0:
            await self._uber_defeat(message)
            return

        reward_data = rewards.calculate_rewards(self.player, self.monster)
        reward_data["xp"] *= 2
        reward_data["gold"] *= 2
        reward_data["curios"] = curios
        reward_data["special"] = []

        if random.random() < 0.10:
            await self.bot.database.uber.increment_gemini_engrams(self.user_id, self.server_id, 1)
            reward_data["special"].append("Gemini Engram")
            reward_data["msgs"].append(
                "♊ **A Gemini Engram crystallises from the twins' shattered bond...**"
            )

        if random.random() < 0.10:
            u_prog = await self.bot.database.uber.get_uber_progress(self.user_id, self.server_id)
            if not u_prog["gemini_blueprint_unlocked"]:
                await self.bot.database.uber.set_gemini_blueprint_unlocked(self.user_id, self.server_id, True)
                reward_data["special"].append("Twin Shrine Blueprint")
                reward_data["msgs"].append("📜 **You found the Twin Shrine Blueprint!**")
            else:
                await self.bot.database.users.modify_currency(self.user_id, "bound_crystal", 1)
                reward_data["special"].append("Bound Crystal")
                reward_data["msgs"].append("💎 **The twins' bond yields a Bound Crystal.**")

        await self._uber_finalize_rewards(reward_data)

        embed = combat_ui.create_victory_embed(self.player, self.monster, reward_data)
        embed.title = "♊ Bound Sovereigns Defeated!"
        embed.set_image(url="https://i.imgur.com/JCl4YPE.jpeg")
        await message.edit(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
