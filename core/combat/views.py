# core/combat/views.py

import asyncio
import random

import discord
from discord import ButtonStyle, Interaction, ui

import core.slayer.mechanics
from core.combat import engine, rewards
from core.combat import ui as combat_ui
from core.combat.drops import DropManager
from core.combat.gen_mob import generate_boss
from core.companions.mechanics import CompanionMechanics
from core.models import Monster, Player


class LuciferChoiceView(ui.View):
    """Specific View for Lucifer's Soul Core selection."""

    def __init__(self, bot, user_id, player):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.player = player

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def _conclude(self, interaction, msg):
        embed = interaction.message.embeds[0]
        embed.add_field(name="Choice", value=msg, inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    @ui.button(label="Enraged", emoji="❤️‍🔥", style=ButtonStyle.danger)
    async def enraged(self, interaction: Interaction, button: ui.Button):
        adj = random.randint(-1, 2)
        await self.bot.database.users.modify_stat(self.user_id, "attack", adj)
        await self._conclude(interaction, f"Enraged! Attack changed by {adj:+}.")

    @ui.button(label="Solidified", emoji="💙", style=ButtonStyle.primary)
    async def solidified(self, interaction: Interaction, button: ui.Button):
        adj = random.randint(-1, 2)
        await self.bot.database.users.modify_stat(self.user_id, "defence", adj)
        await self._conclude(interaction, f"Solidified! Defence changed by {adj:+}.")

    @ui.button(label="Unstable", emoji="💔", style=ButtonStyle.secondary)
    async def unstable(self, interaction: Interaction, button: ui.Button):
        total = self.player.base_attack + self.player.base_defence
        # Randomize towards equilibrium (49-51% split)
        new_atk = int(total * random.uniform(0.49, 0.51))
        new_def = total - new_atk

        atk_diff = new_atk - self.player.base_attack
        def_diff = new_def - self.player.base_defence

        await self.bot.database.users.modify_stat(self.user_id, "attack", atk_diff)
        await self.bot.database.users.modify_stat(self.user_id, "defence", def_diff)
        await self._conclude(
            interaction, f"Chaos ensues! (Atk: {new_atk}, Def: {new_def})"
        )

    @ui.button(label="Inverse", emoji="💞", style=ButtonStyle.secondary)
    async def inverse(self, interaction: Interaction, button: ui.Button):
        diff = self.player.base_defence - self.player.base_attack
        await self.bot.database.users.modify_stat(self.user_id, "attack", diff)
        await self.bot.database.users.modify_stat(self.user_id, "defence", -diff)
        await self._conclude(
            interaction,
            f"Stats Swapped! (Atk: {self.player.base_defence}, Def: {self.player.base_attack})",
        )

    @ui.button(label="Original", emoji="🖤", style=ButtonStyle.success)
    async def original(self, interaction: Interaction, button: ui.Button):
        await self.bot.database.users.modify_currency(self.user_id, "soul_cores", 1)
        await self._conclude(interaction, "You pocket a Soul Core.")


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
        clean_stats: dict = None,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.monster = monster
        self.logs = initial_logs or {}

        self.clean_stats = clean_stats or {
            "attack": player.base_attack,
            "defence": player.base_defence,
            "crit_target": player.base_crit_chance_target,
        }

        # Boss / Chain Handling
        self.combat_phases = combat_phases or []  # List of dicts
        self.current_phase_index = 0

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

        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def update_buttons(self):
        # Toggle buttons based on current state (Enabled if both alive, Disabled if one dead)
        is_over = self.player.current_hp <= 0 or self.monster.hp <= 0
        for child in self.children:
            child.disabled = is_over

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
        self.logs = {self.player.name: p_log}

        # 2. Monster Turn (if alive)
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.logs[self.monster.name] = m_log

        # 3. Check End State
        await self.check_combat_state(interaction)

    @ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹")
    async def heal_btn(self, interaction: Interaction, button: ui.Button):
        h_log = engine.process_heal(self.player)
        self.logs = {"Heal": h_log}

        # Monster still hits you when you potion
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.logs[self.monster.name] = m_log

        await self.check_combat_state(interaction)

    @ui.button(label="Auto", style=ButtonStyle.primary, emoji="⏩")
    async def auto_btn(self, interaction: Interaction, button: ui.Button):
        # Simple Auto: Process turns in a loop until < 20% HP or Win
        await interaction.response.defer()

        message = interaction.message
        while (
            self.player.current_hp > (self.player.max_hp * 0.2) and self.monster.hp > 0
        ):
            p_log = engine.process_player_turn(self.player, self.monster)
            m_log = ""
            if self.monster.hp > 0:
                m_log = engine.process_monster_turn(self.player, self.monster)

            self.logs = {self.player.name: p_log, self.monster.name: m_log}

            embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)
            await message.edit(embed=embed, view=self)
            await asyncio.sleep(1.0)

        # Loop finished
        if (
            0 < self.player.current_hp <= (self.player.max_hp * 0.2)
            and self.monster.hp > 0
        ):
            self.logs["Auto-Battle"] = "🛑 Paused: Low HP Protection triggered!"
            embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)
            await message.edit(embed=embed, view=self)
        else:
            # Handle End State manually (handles both victory and death)
            await self.handle_end_state(message, interaction)

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
                self.player.current_hp <= (self.player.max_hp * 0.2)
                or self.monster.hp <= 0
            ):
                break

            p_log = engine.process_player_turn(self.player, self.monster)
            m_log = ""
            if self.monster.hp > 0:
                m_log = engine.process_monster_turn(self.player, self.monster)

            self.logs = {self.player.name: p_log, self.monster.name: m_log}
            turns_processed += 1

        status_msg = (
            f"⚡ You flash forward in time, **{turns_processed}** turns have gone by."
        )

        # FIX: Ensure HP is strictly greater than 0 to append the pause message
        if (
            0 < self.player.current_hp <= (self.player.max_hp * 0.2)
            and self.monster.hp > 0
        ):
            status_msg += "\n🛑 Paused: Low HP Protection triggered!"

        self.logs["System"] = status_msg

        # Update UI / Check Win/Loss
        if self.player.current_hp <= 0 or self.monster.hp <= 0:
            await self.handle_end_state(interaction.message, interaction)
        else:
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
            return "https://i.imgur.com/LjE5VZF.png"
        if "Gemini" in boss_name:
            return "https://i.imgur.com/PqViP3D.png"
        if "Lucifer" in boss_name:
            return "https://i.imgur.com/tIcLLI1.png"
        return None

    async def handle_end_state(self, message, interaction: Interaction):
        """Processes victory or defeat with Phase Logic."""

        if getattr(self.monster, "is_uber", False):
            if "Lucifer" in self.monster.name:
                await self._handle_uber_lucifer_end_state(message, interaction)
            elif "NEET" in self.monster.name:
                await self._handle_uber_neet_end_state(message, interaction)
            else:
                await self._handle_uber_end_state(message, interaction)
            return

        if self.player.current_hp <= 0:
            # Defeat Logic (Same as before)
            xp_loss = int(self.player.exp * 0.10)
            self.player.exp = max(0, self.player.exp - xp_loss)
            self.player.current_hp = 1
            embed = combat_ui.create_defeat_embed(self.player, self.monster, xp_loss)
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

                self.player.base_attack = self.clean_stats["attack"]
                self.player.base_defence = self.clean_stats["defence"]
                self.player.base_crit_chance_target = self.clean_stats["crit_target"]

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
                total_chance = 0.10 + (forge_workers * 0.0001)
                guaranteed = int(total_chance)
                fractional = total_chance - guaranteed
                sigils_dropped = guaranteed
                if random.random() < fractional:
                    sigils_dropped += 1
                if sigils_dropped > 0:
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
                total_chance = 0.10 + (sanctum_workers * 0.0001)
                guaranteed = int(total_chance)
                fractional = total_chance - guaranteed
                shards_dropped = guaranteed
                if random.random() < fractional:
                    shards_dropped += 1
                if shards_dropped > 0:
                    await self.bot.database.uber.increment_void_shards(
                        self.user_id, self.server_id, shards_dropped
                    )
                    reward_data["special"].extend(["Void Shard"] * shards_dropped)

            if "Aphrodite" in self.monster.name and not getattr(
                self.monster, "is_uber", False
            ):
                _, shrine_workers = (
                    await self.bot.database.settlement.get_building_details(
                        self.user_id, self.server_id, "celestial_shrine"
                    )
                )

                # Base 10% chance. +1% per assigned worker.
                total_chance = 0.10 + (shrine_workers * 0.0001)
                guaranteed_sigils = int(total_chance)
                fractional_chance = total_chance - guaranteed_sigils

                sigils_dropped = guaranteed_sigils
                if random.random() < fractional_chance:
                    sigils_dropped += 1

                if sigils_dropped > 0:
                    await self.bot.database.uber.increment_sigils(
                        self.user_id, self.server_id, sigils_dropped
                    )
                    reward_data["special"].extend(["Celestial Sigil"] * sigils_dropped)

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

            # Process Drops
            server_id = str(interaction.guild.id)
            await DropManager.process_drops(
                self.bot,
                self.user_id,
                server_id,
                self.player,
                self.monster.level,
                reward_data,
            )

            # Handle XP / Level Up
            import json

            with open("assets/exp.json") as f:
                exp_table = json.load(f)
            await DropManager.handle_level_up(
                self.bot, self.user_id, self.player, reward_data, exp_table
            )

            # DB Commits
            self.player.exp += reward_data["xp"]
            await self.bot.database.users.modify_gold(self.user_id, reward_data["gold"])

            # Companions
            current_pet_count = await self.bot.database.companions.get_count(
                self.user_id
            )
            boss_pet_triggered = False

            # 1. BOSS PET CHECK (3% Chance, Tier 3 Fixed)
            boss_img = self._get_boss_pet_image(self.monster.name)

            if self.monster.is_boss and boss_img and current_pet_count < 20:
                if random.random() < 0.03:  # 3% Drop Rate
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
                and random.random() < 0.05
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
                        self.user_id, server_id, xp=100, points=0
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
                    reward_data["msgs"].append("🩸 **Slayer:** +100 Slayer XP")
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
                embed.set_image(url="https://i.imgur.com/x9suAGK.png")
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
                await message.edit(
                    embed=embed,
                    view=LuciferChoiceView(self.bot, self.user_id, self.player),
                )
                return  # Lucifer View takes over
            else:
                await message.edit(embed=embed, view=None)

            # Soulreap: restore HP to full after every successful encounter
            if self.player.get_weapon_infernal() == "soulreap":
                self.player.current_hp = self.player.max_hp

            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            self.stop()

    async def _handle_uber_end_state(self, message, interaction: Interaction):
        """Specialized logic for the Uber Aphrodite encounter."""
        max_hp = self.monster.max_hp
        rem_hp = max(0, self.monster.hp)

        dmg_frac = max(0.0, min(1.0, (max_hp - rem_hp) / max_hp))

        # 1. Curio Rewards (Scale with Damage)
        curios = 1
        if dmg_frac >= 1.0:
            curios = 5
        elif dmg_frac >= 0.75:
            curios = 4
        elif dmg_frac >= 0.50:
            curios = 3
        elif dmg_frac >= 0.25:
            curios = 2

        await self.bot.database.users.modify_currency(self.user_id, "curios", curios)

        # 2. Defeat vs Victory
        if self.player.current_hp <= 0:
            # Defeat
            xp_loss = int(self.player.exp * 0.10)
            self.player.exp = max(0, self.player.exp - xp_loss)
            self.player.current_hp = 1

            # Pass data directly into updated defeat embed
            embed = combat_ui.create_defeat_embed(
                self.player,
                self.monster,
                xp_loss,
                curios_gained=curios,
                dmg_frac=dmg_frac,
            )
            await message.edit(embed=embed, view=None)

        else:
            # Full Kill Victory
            reward_data = rewards.calculate_rewards(self.player, self.monster)

            # Double Base XP & Gold
            reward_data["xp"] *= 2
            reward_data["gold"] *= 2

            # Setup Curios and Specials for the standard Loot UI parser
            reward_data["curios"] = curios
            reward_data["special"] = []

            # 3. Celestial Engram Roll (10%)
            if random.random() < 0.10:
                await self.bot.database.uber.increment_engrams(
                    self.user_id, self.server_id, 1
                )
                reward_data["special"].append("Celestial Engram")
                reward_data["msgs"].append(
                    "🌌 **A Celestial Engram materializes from Aphrodite's shattered form...**"
                )

            # 4. Blueprint / Stone Roll (10%)
            if random.random() < 0.10:
                u_prog = await self.bot.database.uber.get_uber_progress(
                    self.user_id, self.server_id
                )
                if u_prog["celestial_blueprint_unlocked"] == 0:
                    await self.bot.database.uber.set_blueprint_unlocked(
                        self.user_id, self.server_id, True
                    )
                    reward_data["special"].append("Celestial Shrine Blueprint")
                    reward_data["msgs"].append(
                        "📜 **You found the Celestial Shrine Blueprint!**"
                    )
                else:
                    await self.bot.database.users.modify_currency(
                        self.user_id, "celestial_stone", 1
                    )
                    reward_data["special"].append("Celestial Stone")
                    reward_data["msgs"].append("🪨 **You found a Celestial Stone!**")

            # DB Commits
            self.player.exp += reward_data["xp"]
            await self.bot.database.users.modify_gold(self.user_id, reward_data["gold"])

            # Generate Standard Victory UI (It will naturally parse the specials and curios now)
            embed = combat_ui.create_victory_embed(
                self.player, self.monster, reward_data
            )
            embed.title = "🌌 DEICIDE: Apex Shattered!"
            embed.set_image(url="https://i.imgur.com/wKyTFzh.jpg")
            await message.edit(embed=embed, view=None)

        # Soulreap: restore HP to full after a successful uber kill
        if (
            self.player.get_weapon_infernal() == "soulreap"
            and self.player.current_hp > 0
        ):
            self.player.current_hp = self.player.max_hp

        # Cleanup
        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        self.stop()

    async def _handle_uber_lucifer_end_state(self, message, interaction: Interaction):
        """Specialized logic for the Uber Lucifer encounter."""
        max_hp = self.monster.max_hp
        rem_hp = max(0, self.monster.hp)
        dmg_frac = max(0.0, min(1.0, (max_hp - rem_hp) / max_hp))

        # 1. Curio Rewards (scale with damage dealt)
        curios = 1
        if dmg_frac >= 1.0:
            curios = 5
        elif dmg_frac >= 0.75:
            curios = 4
        elif dmg_frac >= 0.50:
            curios = 3
        elif dmg_frac >= 0.25:
            curios = 2

        await self.bot.database.users.modify_currency(self.user_id, "curios", curios)

        # 2. Defeat vs Victory
        if self.player.current_hp <= 0:
            xp_loss = int(self.player.exp * 0.10)
            self.player.exp = max(0, self.player.exp - xp_loss)
            self.player.current_hp = 1

            embed = combat_ui.create_defeat_embed(
                self.player,
                self.monster,
                xp_loss,
                curios_gained=curios,
                dmg_frac=dmg_frac,
            )
            await message.edit(embed=embed, view=None)
            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            self.stop()

        else:
            # Full Kill Victory
            reward_data = rewards.calculate_rewards(self.player, self.monster)
            reward_data["xp"] *= 2
            reward_data["gold"] *= 2
            reward_data["curios"] = curios
            reward_data["special"] = []

            # 3. Infernal Engram Roll (10%)
            if random.random() < 0.10:
                await self.bot.database.uber.increment_infernal_engrams(
                    self.user_id, self.server_id, 1
                )
                reward_data["special"].append("Infernal Engram")
                reward_data["msgs"].append(
                    "🔥 **An Infernal Engram crystallises from Lucifer's shattered crown...**"
                )

            # 4. Infernal Forge Blueprint / Refinement Rune Roll (10%)
            if random.random() < 0.10:
                u_prog = await self.bot.database.uber.get_uber_progress(
                    self.user_id, self.server_id
                )
                if u_prog["infernal_blueprint_unlocked"] == 0:
                    await self.bot.database.uber.set_infernal_blueprint_unlocked(
                        self.user_id, self.server_id, True
                    )
                    reward_data["special"].append("Infernal Forge Blueprint")
                    reward_data["msgs"].append(
                        "📜 **You found the Infernal Forge Blueprint!**"
                    )
                else:
                    await self.bot.database.users.modify_currency(
                        self.user_id, "infernal_cinder", 1
                    )
                    reward_data["special"].append("Infernal Cinder")
                    reward_data["msgs"].append(
                        "🔥 **The forge roars. You extract an Infernal Cinder.**"
                    )

            # DB commits
            self.player.exp += reward_data["xp"]
            await self.bot.database.users.modify_gold(self.user_id, reward_data["gold"])

            # Soulreap: restore HP to full after kill
            if self.player.get_weapon_infernal() == "soulreap":
                self.player.current_hp = self.player.max_hp

            await self.bot.database.users.update_from_player_object(self.player)

            embed = combat_ui.create_victory_embed(
                self.player, self.monster, reward_data
            )
            embed.title = "🔥 DEICIDE: Sovereign Shattered!"
            embed.set_image(url="https://i.imgur.com/x9suAGK.png")

            # Present the Infernal Contract
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
        """Specialized logic for the Uber NEET encounter."""
        max_hp = self.monster.max_hp
        rem_hp = max(0, self.monster.hp)
        dmg_frac = max(0.0, min(1.0, (max_hp - rem_hp) / max_hp))

        # 1. Curio Rewards (scale with damage dealt)
        curios = 1
        if dmg_frac >= 1.0:
            curios = 5
        elif dmg_frac >= 0.75:
            curios = 4
        elif dmg_frac >= 0.50:
            curios = 3
        elif dmg_frac >= 0.25:
            curios = 2

        await self.bot.database.users.modify_currency(self.user_id, "curios", curios)

        # 2. Defeat vs Victory
        if self.player.current_hp <= 0:
            xp_loss = int(self.player.exp * 0.10)
            self.player.exp = max(0, self.player.exp - xp_loss)
            self.player.current_hp = 1

            embed = combat_ui.create_defeat_embed(
                self.player,
                self.monster,
                xp_loss,
                curios_gained=curios,
                dmg_frac=dmg_frac,
            )
            await message.edit(embed=embed, view=None)

        else:
            # Full Kill Victory
            reward_data = rewards.calculate_rewards(self.player, self.monster)
            reward_data["xp"] *= 2
            reward_data["gold"] *= 2
            reward_data["curios"] = curios
            reward_data["special"] = []

            # 3. Void Engram Roll (10%)
            if random.random() < 0.10:
                await self.bot.database.uber.increment_void_engrams(
                    self.user_id, self.server_id, 1
                )
                reward_data["special"].append("Void Engram")
                reward_data["msgs"].append(
                    "⬛ **A Void Engram crystallises from the collapsing rift...**"
                )

            # 4. Void Sanctum Blueprint / Void Crystal Roll (10%)
            if random.random() < 0.10:
                u_prog = await self.bot.database.uber.get_uber_progress(
                    self.user_id, self.server_id
                )
                if u_prog["void_blueprint_unlocked"] == 0:
                    await self.bot.database.uber.set_void_blueprint_unlocked(
                        self.user_id, self.server_id, True
                    )
                    reward_data["special"].append("Void Sanctum Blueprint")
                    reward_data["msgs"].append(
                        "📜 **You found the Void Sanctum Blueprint!**"
                    )
                else:
                    await self.bot.database.users.modify_currency(
                        self.user_id, "void_crystal", 1
                    )
                    reward_data["special"].append("Void Crystal")
                    reward_data["msgs"].append("🔮 **The void yields a Void Crystal.**")

            # 5. Void Key (guaranteed on victory)
            await self.bot.database.users.modify_currency(self.user_id, "void_keys", 1)
            reward_data["special"].append("Void Key")
            reward_data["msgs"].append(
                "🗝️ **A Void Key manifests from the collapsing rift.**"
            )

            # DB commits
            self.player.exp += reward_data["xp"]
            await self.bot.database.users.modify_gold(self.user_id, reward_data["gold"])

            # Soulreap: restore HP to full after kill
            if self.player.get_weapon_infernal() == "soulreap":
                self.player.current_hp = self.player.max_hp

            await self.bot.database.users.update_from_player_object(self.player)

            embed = combat_ui.create_victory_embed(
                self.player, self.monster, reward_data
            )
            embed.title = "⬛ DEICIDE: Void Sovereign Collapsed!"
            embed.set_image(url="https://i.imgur.com/7UmY4Mo.jpeg")
            await message.edit(embed=embed, view=None)
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
            return

        # Soulreap on uber defeat (if player survived via vow etc.)
        if (
            self.player.get_weapon_infernal() == "soulreap"
            and self.player.current_hp > 0
        ):
            self.player.current_hp = self.player.max_hp

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        self.stop()


class InfernalContractView(ui.View):
    """Presents a randomly-generated stat contract after killing Uber Lucifer."""

    STAT_LABELS = {"attack": "⚔️ ATK", "defence": "🛡️ DEF", "hp": "❤️ HP"}

    def __init__(self, bot, user_id: str, player, server_id: str, message):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.server_id = server_id
        self.message = message

        self.contract = self._roll_contract()

    def _roll_contract(self) -> dict:
        roll = random.random()
        if roll < 0.05:  # 5%  — all positive
            signs = [1, 1, 1]
        elif roll < 0.25:  # 20% — 2 positive 1 negative
            signs = [1, 1, -1]
        else:  # 75% — 1 positive 2 negative
            signs = [1, -1, -1]

        random.shuffle(signs)
        stats = ["attack", "defence", "hp"]
        random.shuffle(stats)

        return {stat: signs[i] * random.randint(5, 20) for i, stat in enumerate(stats)}

    def contract_summary(self) -> str:
        parts = []
        for stat, delta in self.contract.items():
            sign = "+" if delta > 0 else ""
            parts.append(f"{self.STAT_LABELS[stat]}: **{sign}{delta}**")
        return (
            "\n".join(parts)
            + "\n\n*Lucifer offers a deal. Most deals are poor. This may be too.*"
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

    @ui.button(label="Accept Contract", style=discord.ButtonStyle.danger, emoji="🩸")
    async def accept(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()

        atk_delta = self.contract.get("attack", 0)
        def_delta = self.contract.get("defence", 0)
        hp_delta = self.contract.get("hp", 0)

        self.player.base_attack = max(1, self.player.base_attack + atk_delta)
        self.player.base_defence = max(1, self.player.base_defence + def_delta)
        self.player.max_hp = max(10, self.player.max_hp + hp_delta)
        self.player.current_hp = min(self.player.current_hp, self.player.max_hp)

        await self.bot.database.users.update_from_player_object(self.player)

        parts = []
        for stat, delta in self.contract.items():
            sign = "+" if delta > 0 else ""
            parts.append(f"{self.STAT_LABELS[stat]}: **{sign}{delta}**")

        embed = discord.Embed(
            title="🩸 Contract Signed",
            description="The ink dries in flame. Your soul bears the mark.\n\n"
            + "\n".join(parts),
            color=discord.Color.dark_red(),
        )
        embed.set_footer(text="There is no going back.")
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.edit_original_response(embed=embed, view=None)
        self.stop()

    @ui.button(label="Reject Contract", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def reject(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(
            title="🖤 Contract Rejected",
            description="Lucifer watches you walk away. *He will remember.*",
            color=discord.Color.dark_grey(),
        )
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.edit_original_response(embed=embed, view=None)
        self.stop()
