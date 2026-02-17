import discord
import asyncio
import json
from discord import ui, ButtonStyle, Interaction

from core.models import Player, Monster
from core.combat import engine, ui as combat_ui
from core.combat.gen_mob import generate_ascent_monster
from core.ascent.mechanics import AscentMechanics

class AscentView(ui.View):
    def __init__(self, bot, user_id: str, player: Player, initial_monster: Monster, start_logs: dict, clean_stats: dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.monster = initial_monster
        self.clean_stats = clean_stats # [FIX] Store original stats
        
        # State
        self.stage = 1
        self.cumulative_xp = 0
        self.cumulative_gold = 0
        self.logs = start_logs or {}
        
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        # Auto-retreat on timeout if still alive
        if self.player.current_hp > 0:
            await self.handle_retreat(self.message if hasattr(self, 'message') else None)
        else:
            self.bot.state_manager.clear_active(self.user_id)

    def update_buttons(self):
        if self.player.current_hp <= 0:
            for child in self.children:
                child.disabled = True

    async def refresh_ui(self, interaction: Interaction = None, message: discord.Message = None):
        title = f"Ascent Stage {self.stage} | {self.player.name}"
        embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs, title_override=title)
        
        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        elif message:
            await message.edit(embed=embed, view=self)
        elif interaction:
            await interaction.edit_original_response(embed=embed, view=self)

    # --- ACTIONS ---

    @ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️")
    async def attack(self, interaction: Interaction, button: ui.Button):
        await self.execute_turn(interaction)

    @ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹")
    async def heal(self, interaction: Interaction, button: ui.Button):
        heal_log = engine.process_heal(self.player)
        self.logs = {"Heal": heal_log}
        
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.logs[self.monster.name] = m_log
            
        await self.check_state(interaction)

    @ui.button(label="Auto Stage", style=ButtonStyle.primary, emoji="⏩")
    async def auto(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        message = interaction.message
        
        # [FIX] Run batches of 10 turns
        while self.player.current_hp > (self.player.max_hp * 0.2) and self.monster.hp > 0:
            
            # Process up to 10 turns instantly
            for _ in range(10):
                if self.player.current_hp <= (self.player.max_hp * 0.2) or self.monster.hp <= 0:
                    break
                
                p_log = engine.process_player_turn(self.player, self.monster)
                m_log = ""
                if self.monster.hp > 0:
                    m_log = engine.process_monster_turn(self.player, self.monster)
                
                # Update logs continuously so the last one seen is accurate
                self.logs = {self.player.name: p_log, self.monster.name: m_log}

            # Update UI periodically (after every batch)
            if self.monster.hp > 0 and self.player.current_hp > (self.player.max_hp * 0.2):
                await self.refresh_ui(message=message)
                await asyncio.sleep(1.0) # Small delay for visual pacing
            else:
                break # Exit main loop to handle state

        # Check why loop ended
        if self.player.current_hp <= (self.player.max_hp * 0.2) and self.monster.hp > 0:
            self.logs["Auto-Battle"] = "Paused: Low HP protection!"
            await self.refresh_ui(message=message)
        else:
            # Stage cleared or dead
            await self.check_state(interaction, message)

    @ui.button(label="Retreat", style=ButtonStyle.secondary, emoji="🏃")
    async def retreat(self, interaction: Interaction, button: ui.Button):
        await self.handle_retreat(interaction)

    # --- LOGIC ---

    async def execute_turn(self, interaction: Interaction):
        p_log = engine.process_player_turn(self.player, self.monster)
        self.logs = {self.player.name: p_log}
        
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.logs[self.monster.name] = m_log
            
        await self.check_state(interaction)

    async def check_state(self, interaction: Interaction = None, message: discord.Message = None):
        if self.player.current_hp <= 0:
            await self.handle_defeat(interaction, message)
        elif self.monster.hp <= 0:
            await self.handle_stage_clear(interaction, message)
        else:
            await self.refresh_ui(interaction, message)

    async def handle_stage_clear(self, interaction: Interaction, message: discord.Message):
        # 1. Calculate Rewards
        xp_gain = self.monster.xp
        gold_gain = AscentMechanics.calculate_stage_rewards(self.monster.level, self.stage)
        
        self.cumulative_xp += xp_gain
        self.cumulative_gold += gold_gain
        self.player.exp += xp_gain
        
        # 2. Check Level Up / Ascension
        level_msgs = []
        try:
            with open('assets/exp.json') as f: exp_table = json.load(f)
            exp_threshold = exp_table["levels"].get(str(self.player.level), 999999999)
            
            gained_levels = 0
            while self.player.exp >= exp_threshold and self.player.level >= 100:
                self.player.ascension += 1
                self.player.exp -= exp_threshold
                gained_levels += 1
                await self.bot.database.users.modify_currency(self.user_id, 'passive_points', 2)
            
            if gained_levels > 0:
                level_msgs.append(f"🌟 **ASCENDED x{gained_levels}!**")
        except: pass

        # 3. DB Updates
        await self.bot.database.users.modify_gold(self.user_id, gold_gain)
        await self.bot.database.users.update_from_player_object(self.player)
        
        # Special Drops (Curios)
        special_loot = []
        if self.stage % 3 == 0:
            import random
            if random.random() < 0.25:
                await self.bot.database.users.modify_currency(self.user_id, 'curios', 1)
                special_loot.append("Curious Curio")

        # 4. Display Clear Embed
        embed = discord.Embed(title=f"Stage {self.stage} Cleared!", color=discord.Color.green())
        desc = f"**XP:** {xp_gain:,}\n**Gold:** {gold_gain:,}"
        if level_msgs: desc += "\n" + "\n".join(level_msgs)
        if special_loot: desc += "\n**Found:** " + ", ".join(special_loot)
        
        embed.description = desc
        embed.set_footer(text=f"HP: {self.player.current_hp}/{self.player.max_hp} | Next stage in 3s...")
        
        target = interaction.edit_original_response if interaction and interaction.response.is_done() else (interaction.response.edit_message if interaction else message.edit)
        await target(embed=embed, view=None) # Hide buttons during transition

        # 5. Transition
        await asyncio.sleep(3)
        await self.next_stage(interaction, message)

    async def next_stage(self, interaction, message):
        self.stage += 1
        
        # [FIX] Reset transient player stats from clean snapshot
        self.player.base_attack = self.clean_stats['attack']
        self.player.base_defence = self.clean_stats['defence']
        self.player.base_crit_chance_target = self.clean_stats['crit_target']
        
        self.player.combat_ward = self.player.get_combat_ward_value()
        self.player.is_invulnerable_this_combat = False
        
        # Generate Next Monster
        # We create a fresh monster container
        next_monster = Monster(name="", level=0, hp=0, max_hp=0, xp=0, attack=0, defence=0, modifiers=[], image="", flavor="", is_boss=True)
        
        m_level = AscentMechanics.calculate_monster_level(self.player.level, self.player.ascension, self.stage)
        n_mods, b_mods = AscentMechanics.get_modifier_counts(self.stage)
        
        next_monster = await generate_ascent_monster(self.player, next_monster, m_level, n_mods, b_mods)
        self.monster = next_monster
        
        # Apply Start Effects (these modify base stats again for this stage only)
        engine.apply_stat_effects(self.player, self.monster)
        self.logs = engine.apply_combat_start_passives(self.player, self.monster)
        
        msg_obj = message if message else (await interaction.original_response())
        
        embed = combat_ui.create_combat_embed(self.player, self.monster, self.logs, title_override=f"Ascent Stage {self.stage} | {self.player.name}")
        await msg_obj.edit(embed=embed, view=self)

    async def handle_retreat(self, interaction_or_msg):
        embed = discord.Embed(title="Ascent Ended", description="You fled from the spire.", color=discord.Color.light_grey())
        embed.add_field(name="Highest Stage", value=str(self.stage), inline=True)
        embed.add_field(name="Total Earnings", value=f"XP: {self.cumulative_xp:,}\nGold: {self.cumulative_gold:,}", inline=False)
        
        if isinstance(interaction_or_msg, Interaction):
            if not interaction_or_msg.response.is_done():
                await interaction_or_msg.response.edit_message(embed=embed, view=None)
            else:
                await interaction_or_msg.edit_original_response(embed=embed, view=None)
        elif interaction_or_msg:
            await interaction_or_msg.edit(embed=embed, view=None)
            
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def handle_defeat(self, interaction, message):
        xp_loss = AscentMechanics.calculate_xp_loss(self.player.exp)
        self.player.exp = max(0, self.player.exp - xp_loss)
        self.player.current_hp = 1
        
        embed = combat_ui.create_defeat_embed(self.player, self.monster, xp_loss)
        embed.title = f"Defeated on Stage {self.stage}"
        
        target = interaction.response.edit_message if interaction and not interaction.response.is_done() else (interaction.edit_original_response if interaction else message.edit)
        await target(embed=embed, view=None)
        
        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        self.stop()