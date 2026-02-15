# core/combat/views.py

import discord
from discord import ui, ButtonStyle, Interaction
import asyncio
import random

from core.models import Player, Monster
from core.combat import engine, ui as combat_ui, rewards
from core.combat.drops import DropManager
from core.combat.gen_mob import generate_boss, generate_encounter


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
        self.stop()

    @ui.button(label="Enraged", emoji="❤️‍🔥", style=ButtonStyle.danger) 
    async def enraged(self, interaction: Interaction, button: ui.Button):
        adj = random.randint(-1, 2)
        await self.bot.database.users.modify_stat(self.user_id, 'attack', adj)
        await self._conclude(interaction, f"Enraged! Attack changed by {adj}.")

    @ui.button(label="Solidified", emoji="💙", style=ButtonStyle.primary) 
    async def solidified(self, interaction: Interaction, button: ui.Button):
        adj = random.randint(-1, 2)
        await self.bot.database.users.modify_stat(self.user_id, 'defence', adj)
        await self._conclude(interaction, f"Solidified! Defence changed by {adj}.")

    @ui.button(label="Unstable", emoji="💔", style=ButtonStyle.secondary)
    async def unstable(self, interaction: Interaction, button: ui.Button):
        total = self.player.base_attack + self.player.base_defence
        # Randomize towards equilibrium (49-51% split)
        new_atk = int(total * random.uniform(0.49, 0.51))
        new_def = total - new_atk
        
        atk_diff = new_atk - self.player.base_attack
        def_diff = new_def - self.player.base_defence
        
        await self.bot.database.users.modify_stat(self.user_id, 'attack', atk_diff)
        await self.bot.database.users.modify_stat(self.user_id, 'defence', def_diff)
        await self._conclude(interaction, f"Chaos ensues! (Atk: {new_atk}, Def: {new_def})")

    @ui.button(label="Inverse", emoji="💞", style=ButtonStyle.secondary) 
    async def inverse(self, interaction: Interaction, button: ui.Button):
        diff = self.player.base_defence - self.player.base_attack
        await self.bot.database.users.modify_stat(self.user_id, 'attack', diff)
        await self.bot.database.users.modify_stat(self.user_id, 'defence', -diff)
        await self._conclude(interaction, f"Stats Swapped! (Atk: {self.player.base_defence}, Def: {self.player.base_attack})")

    @ui.button(label="Original", emoji="🖤", style=ButtonStyle.success) 
    async def original(self, interaction: Interaction, button: ui.Button):
        await self.bot.database.users.modify_currency(self.user_id, 'soul_cores', 1)
        await self._conclude(interaction, "You pocketed a Soul Core.")


class CombatView(ui.View):
    def __init__(self, bot, user_id: str, player: Player, monster: Monster, initial_logs: dict, combat_phases=None):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.monster = monster
        self.logs = initial_logs or {}
        
        # Boss / Chain Handling
        self.combat_phases = combat_phases or [] # List of dicts
        self.current_phase_index = 0
        
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        # Optional: Edit message to show timeout/flee
        
    def update_buttons(self):
        # Disable buttons if fight is over
        if self.player.current_hp <= 0 or self.monster.hp <= 0:
            for child in self.children:
                child.disabled = True

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
        while self.player.current_hp > (self.player.max_hp * 0.2) and self.monster.hp > 0:
            p_log = engine.process_player_turn(self.player, self.monster)
            m_log = ""
            if self.monster.hp > 0:
                m_log = engine.process_monster_turn(self.player, self.monster)
            
            self.logs = {self.player.name: p_log, self.monster.name: m_log}
            
            # Update UI every turn for visual effect (slows it down but looks better)
            # Or update every 3-5 turns for speed.
            embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)
            await message.edit(embed=embed, view=self)
            await asyncio.sleep(1.0)

        # Loop finished
        if self.player.current_hp <= (self.player.max_hp * 0.2) and self.monster.hp > 0:
            self.logs["Auto-Battle"] = "🛑 Paused: Low HP Protection triggered!"
            embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)
            await message.edit(embed=embed, view=self)
        else:
            # Handle End State manually since we deferred
            await self.handle_end_state(message, interaction)

    @ui.button(label="Flee", style=ButtonStyle.secondary, emoji="🏃")
    async def flee_btn(self, interaction: Interaction, button: ui.Button):
        self.logs["Flee"] = "You managed to escape safely!"
        self.update_buttons() # Disable all
        
        embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs)
        await interaction.response.edit_message(embed=embed, view=None)
        
        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        self.stop()


    @ui.button(label="Fast Auto", style=ButtonStyle.secondary, emoji="⚡", row=1)
    async def fast_auto_btn(self, interaction: Interaction, button: ui.Button):
        # Double check level just in case
        if self.player.level < 20:
            return await interaction.response.send_message("Fast Auto unlocks at Level 20!", ephemeral=True)

        await interaction.response.defer()
        
        turns_processed = 0
        
        # Loop 10 times (Instant calculation, no sleep)
        for _ in range(10):
            # Stop conditions
            if self.player.current_hp <= (self.player.max_hp * 0.2) or self.monster.hp <= 0:
                break
            
            # Logic
            p_log = engine.process_player_turn(self.player, self.monster)
            m_log = ""
            if self.monster.hp > 0:
                m_log = engine.process_monster_turn(self.player, self.monster)
            
            # Keep only the latest log to prevent embed overflow
            self.logs = {self.player.name: p_log, self.monster.name: m_log}
            turns_processed += 1

        # Append status log
        status_msg = f"⚡ You flash forward in time, **{turns_processed}** turns have gone by."
        if self.player.current_hp <= (self.player.max_hp * 0.2) and self.monster.hp > 0:
            status_msg += "\n🛑 Paused: Low HP Protection triggered!"
            
        self.logs["System"] = status_msg

        # Update UI / Check Win/Loss
        await self.check_combat_state(interaction)

    async def check_combat_state(self, interaction: Interaction):
        """Checks if player died or monster died."""
        if self.player.current_hp <= 0 or self.monster.hp <= 0:
            self.update_buttons() # Disable buttons
            
            # We use a separate handler because Auto-battle defers interactions, 
            # while clicking Attack usually does not.
            if interaction.response.is_done():
                 await self.handle_end_state(interaction.message, interaction)
            else:
                 await self.refresh_embed(interaction) # Show final hit
                 await self.handle_end_state(interaction.message, interaction)
        else:
            await self.refresh_embed(interaction)

    async def handle_end_state(self, message, interaction: Interaction):
        """Processes victory or defeat with Phase Logic."""
        
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
                
                # Update Monster Object
                self.monster = await generate_boss(self.player, self.monster, next_phase_data, self.current_phase_index)
                self.monster.is_boss = True
                
                # Apply Start Effects again
                engine.apply_stat_effects(self.player, self.monster)
                new_logs = engine.apply_combat_start_passives(self.player, self.monster)
                
                # Transition Embed
                trans_embed = discord.Embed(
                    title="Phase Complete!", 
                    description=f"**{self.monster.name}** rises from the ashes...", 
                    color=discord.Color.orange()
                )
                trans_embed.set_thumbnail(url=self.monster.image)
                await message.edit(embed=trans_embed, view=None)
                await asyncio.sleep(2)
                
                # Restart View with new Monster
                embed = combat_ui.create_combat_embed(self.player, self.monster, new_logs, 
                                                    title_override=f"⚔️ BOSS PHASE {self.current_phase_index+1}")
                await message.edit(embed=embed, view=self)
                return # Keep View Alive

            # --- FINAL VICTORY ---
            
            reward_data = rewards.calculate_rewards(self.player, self.monster)
            
            # Special Key Logic from rewards.py
            special_flags = rewards.check_special_drops(self.player, self.monster)
            reward_data['special'] = []
            
            # Grant Currencies based on flags
            for key, val in special_flags.items():
                if val:
                    # Mapping logic needed here or simple ifs
                    if key == 'draconic_key': 
                        await self.bot.database.users.modify_currency(self.user_id, 'dragon_key', 1)
                        reward_data['special'].append("Draconic Key")
                    elif key == 'angelic_key':
                        await self.bot.database.users.modify_currency(self.user_id, 'angel_key', 1)
                        reward_data['special'].append("Angelic Key")
                    elif key == 'soul_core':
                        await self.bot.database.users.modify_currency(self.user_id, 'soul_cores', 1)
                        reward_data['special'].append("Soul Core")
                    elif key == 'void_frag':
                        await self.bot.database.users.modify_currency(self.user_id, 'void_frags', 1)
                        reward_data['special'].append("Void Fragment")
                    elif key == 'curio':
                        await self.bot.database.users.modify_currency(self.user_id, 'curios', 1)
                        reward_data['curios'] = 1
                    # Boss/Special Runes
                    elif key == 'refinement_rune':
                        await self.bot.database.users.modify_currency(self.user_id, 'refinement_runes', 1)
                        reward_data['special'].append("Rune of Refinement")
                        
                    elif key == 'potential_rune':
                        await self.bot.database.users.modify_currency(self.user_id, 'potential_runes', 1)
                        reward_data['special'].append("Rune of Potential")
                        
                    elif key == 'imbue_rune':
                        await self.bot.database.users.modify_currency(self.user_id, 'imbue_runes', 1)
                        reward_data['special'].append("Rune of Imbuing")
                        
                    elif key == 'shatter_rune':
                        await self.bot.database.users.modify_currency(self.user_id, 'shatter_runes', 1)
                        reward_data['special'].append("Rune of Shattering")

            # Process Drops
            server_id = str(interaction.guild.id)
            await DropManager.process_drops(self.bot, self.user_id, server_id, self.player, self.monster.level, reward_data)
            
            # Handle XP / Level Up
            # Note: We need to load exp table json here, or pass it. 
            # Assuming Cog passed it or we load it here.
            import json
            with open('assets/exp.json') as f: exp_table = json.load(f)
            await DropManager.handle_level_up(self.bot, self.user_id, self.player, reward_data, exp_table)

            # DB Commits
            self.player.exp += reward_data['xp']
            await self.bot.database.users.modify_gold(self.user_id, reward_data['gold'])
            
            embed = combat_ui.create_victory_embed(self.player, self.monster, reward_data)
            
            # Final Boss Scenes
            if "Aphrodite" in self.monster.name:
                embed.set_image(url="https://i.imgur.com/wKyTFzh.jpg")
                await message.edit(embed=embed, view=None)
            elif "NEET" in self.monster.name:
                embed.set_image(url="https://i.imgur.com/7UmY4Mo.jpeg")
                embed.add_field(name="Loot", value="Found a **Void Key**.", inline=False)
                await self.bot.database.users.modify_currency(self.user_id, 'void_keys', 1)
                await message.edit(embed=embed, view=None)
            elif "Lucifer" in self.monster.name:
                embed.set_image(url="https://i.imgur.com/x9suAGK.png")
                await message.edit(embed=embed, view=LuciferChoiceView(self.bot, self.user_id, self.player))
                return # Lucifer View takes over
            else:
                await message.edit(embed=embed, view=None)

            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            self.stop()