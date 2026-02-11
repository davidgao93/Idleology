import discord
import random
import asyncio
import json
from datetime import datetime, timedelta
from discord.ext import commands
from discord import app_commands, Interaction, Message

# Core Imports
from core.models import Player, Monster
from core.items.factory import load_player
from core.combat import engine, ui
from core.combat.gen_mob import generate_ascent_monster, get_modifier_description

class Ascent(commands.Cog, name="ascent"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.ASCENT_COOLDOWN = timedelta(minutes=10)

    def load_exp_table(self):
        with open('assets/exp.json') as file:
            return json.load(file)


    async def _check_cooldown(self, interaction: Interaction, user_id: str, existing_user: tuple) -> bool:
        """Calculates dynamic cooldown for Ascent."""
        temp_cooldown_reduction = 0
        equipped_boot = await self.bot.database.equipment.get_equipped(user_id, "boot")
        if equipped_boot and equipped_boot[9] == "speedster":
            temp_cooldown_reduction = equipped_boot[12] * 20 

        current_duration = self.ASCENT_COOLDOWN - timedelta(seconds=temp_cooldown_reduction)
        current_duration = max(timedelta(seconds=10), current_duration)

        last_combat_str = existing_user[24] # Reusing generic combat timer
        if last_combat_str:
            try:
                last_combat_dt = datetime.fromisoformat(last_combat_str)
                if datetime.now() - last_combat_dt < current_duration:
                    remaining = current_duration - (datetime.now() - last_combat_dt)
                    await interaction.response.send_message(
                        f"Please slow down. Try again in {remaining.seconds // 60}m {remaining.seconds % 60}s.",
                        ephemeral=True
                    )
                    return False
            except ValueError:
                pass
        return True

    @app_commands.command(name="ascent", description="Begin your ascent against increasingly powerful foes (Lvl 100+).")
    async def ascent(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return
        
        if existing_user[4] < 100:
            await interaction.response.send_message("The path of ascent is brutal. Come back at level 100.", ephemeral=True)
            return

        if not await self._check_cooldown(interaction, user_id, existing_user): return

        # Set Active & Update Timer
        self.bot.state_manager.set_active(user_id, "ascent")
        await self.bot.database.users.update_timer(user_id, 'last_combat')

        # 2. Initialize Player
        # We fetch a fresh object every stage to reset transient combat stats, 
        # but we need to persist HP updates between stages manually.
        base_player = await load_player(user_id, existing_user, self.bot.database)
        player = await load_player(user_id, existing_user, self.bot.database)
        
        # Ascent State Variables
        ascent_stage = 1
        current_monster_level = player.level + player.ascension + 3
        cumulative_xp = 0
        cumulative_gold = 0
        
        # Initial Response
        await interaction.response.send_message(embed=discord.Embed(title="Ascent Begins...", description="Preparing stage 1...", color=discord.Color.gold()))
        message = await interaction.original_response()

        # --- THE ASCENT LOOP ---
        while True:
            player.base_attack = base_player.base_attack
            player.base_defence = base_player.base_defence
            player.max_hp = base_player.max_hp
            # Generate Monster for this stage
            monster = Monster(name="", level=0, hp=0, max_hp=0, xp=0, attack=0, defence=0, modifiers=[], image="", flavor="", is_boss=True)
            
            # Logic: +1 normal mod every stage, +1 boss mod every 5 stages
            n_mods = 5 + (ascent_stage // 2)
            b_mods = 1 + (ascent_stage // 5)
            monster = await generate_ascent_monster(player, monster, current_monster_level, n_mods, b_mods)

            # Apply Start-of-Combat effects
            # Note: We reset player ward/transient stats by reloading or resetting them here
            player.combat_ward = player.get_combat_ward_value() 
            engine.apply_stat_effects(player, monster)
            start_logs = engine.apply_combat_start_passives(player, monster)

            # UI Setup for Stage
            embed = ui.create_combat_embed(player, monster, start_logs, 
                                         title_override=f"Ascent Stage {ascent_stage} | {player.name}")
            await message.edit(embed=embed)
            
            # Reactions management
            reactions = ["⚔️", "🩹", "⏩", "🏃"]
            # Clear previous reactions if loop restarted
            try:
                await message.clear_reactions()
            except: pass
            
            await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

            # --- COMBAT LOOP (Single Stage) ---
            stage_complete = False
            while player.current_hp > 0 and monster.hp > 0:
                def check(r, u):
                    return u == interaction.user and r.message.id == message.id and str(r.emoji) in reactions

                try:
                    reaction, _ = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
                    await message.remove_reaction(reaction.emoji, interaction.user)
                    emoji = str(reaction.emoji)
                    logs = {}

                    if emoji == "⚔️":
                        logs[player.name] = engine.process_player_turn(player, monster)
                        if monster.hp > 0:
                            logs[monster.name] = engine.process_monster_turn(player, monster)
                    
                    elif emoji == "🩹":
                        logs["Heal"] = engine.process_heal(player)

                    elif emoji == "⏩": # Auto-battle current stage
                        while player.current_hp > int(player.max_hp * 0.2) and monster.hp > 0:
                            atk = engine.process_player_turn(player, monster)
                            def_msg = ""
                            if monster.hp > 0:
                                def_msg = engine.process_monster_turn(player, monster)
                            
                            # Optional: Update UI periodically
                            if monster.hp <= 0 or player.current_hp <= 0:
                                logs[player.name] = atk
                                logs[monster.name] = def_msg
                        
                        if player.current_hp <= int(player.max_hp * 0.2) and monster.hp > 0:
                            logs["Auto-Battle"] = "Paused: Low HP protection!"

                    elif emoji == "🏃":
                        await self._handle_retreat(user_id, player, message, ascent_stage, cumulative_xp, cumulative_gold)
                        return

                    # Update UI
                    embed = ui.create_combat_embed(player, monster, logs, 
                                                 title_override=f"Ascent Stage {ascent_stage} | {player.name}")
                    await message.edit(embed=embed)

                except asyncio.TimeoutError:
                    await self._handle_retreat(user_id, player, message, ascent_stage, cumulative_xp, cumulative_gold)
                    return

            # --- POST STAGE CHECKS ---
            if player.current_hp <= 0:
                await self._handle_defeat(user_id, player, message, monster, ascent_stage)
                return

            if monster.hp <= 0:
                # --- STAGE CLEARED LOGIC ---
                xp_gain = monster.xp
                gold_gain = int((monster.level ** 1.5) * (1 + ascent_stage/10))
                
                cumulative_xp += xp_gain
                cumulative_gold += gold_gain
                
                # Update local player state
                player.exp += xp_gain
                
                # --- LEVEL UP CHECK (ASCENSION) ---
                level_up_msgs = []
                exp_table = self.load_exp_table()
                # Threshold for level 100 (Ascension uses fixed threshold usually, or scales based on current level 100 cap)
                exp_threshold = exp_table["levels"].get(str(player.level), 999999999)
                
                # Loop in case of massive XP gain triggering multiple levels
                levels_gained = 0
                while player.exp >= exp_threshold:
                    player.ascension += 1
                    player.exp -= exp_threshold
                    levels_gained += 1
                    # Grant Passive Points (Immediate DB update not strictly necessary as we save player obj below, 
                    # but currency uses specific method)
                    await self.bot.database.users.modify_currency(user_id, 'passive_points', 2)

                if levels_gained > 0:
                    level_up_msgs.append(f"🌟 **ASCENDED x{levels_gained}!** (Ascension {player.ascension})")
                    level_up_msgs.append(f"✨ Gained **{levels_gained * 2}** Passive Points!")

                # --- DB COMMITS ---
                await self.bot.database.users.modify_gold(user_id, gold_gain)
                # This saves new XP, Ascension count, and HP
                await self.bot.database.users.update_from_player_object(player)

                # Special Rewards Check (Every 3 stages)
                special_loot = []
                if ascent_stage % 3 == 0:
                    if random.random() < 0.25:
                        await self.bot.database.users.modify_currency(user_id, 'curios', 1)
                        special_loot.append("Curious Curio")

                # --- BUILD UI ---
                clear_embed = discord.Embed(title=f"Stage {ascent_stage} Cleared!", color=discord.Color.green())
                
                # Rewards Field
                rewards_text = f"XP: {xp_gain:,}\nGold: {gold_gain:,}"
                if level_up_msgs:
                    rewards_text += "\n\n" + "\n".join(level_up_msgs)
                clear_embed.add_field(name="Rewards", value=rewards_text, inline=False)
                
                if special_loot:
                    clear_embed.add_field(name="Special Drops", value=", ".join(special_loot), inline=False)
                
                clear_embed.add_field(name="Status", value=f"HP: {player.current_hp}/{player.max_hp}\nNext stage starting in 3 seconds...", inline=False)
                await message.edit(embed=clear_embed)
                
                # Prepare next stage
                ascent_stage += 1
                current_monster_level += 2
                await asyncio.sleep(3)

    async def _handle_retreat(self, user_id, player, message, stage, total_xp, total_gold):
        embed = discord.Embed(title="Ascent Ended", description="You fled from the spire.", color=discord.Color.light_grey())
        embed.add_field(name="Highest Stage", value=str(stage), inline=True)
        embed.add_field(name="Total Earnings", value=f"XP: {total_xp:,}\nGold: {total_gold:,}", inline=False)
        await message.edit(embed=embed)
        await message.clear_reactions()
        await self._cleanup(user_id, player)

    async def _handle_defeat(self, user_id, player, message, monster, stage):
        xp_loss = int(player.exp * 0.10)
        player.exp = max(0, player.exp - xp_loss)
        player.current_hp = 1
        
        embed = ui.create_defeat_embed(player, monster, xp_loss)
        embed.title = f"Defeated on Stage {stage}"
        await message.edit(embed=embed)
        await message.clear_reactions()
        await self._cleanup(user_id, player)

    async def _cleanup(self, user_id, player):
        self.bot.state_manager.clear_active(user_id)
        await self.bot.database.users.update_from_player_object(player)

async def setup(bot) -> None:
    await bot.add_cog(Ascent(bot))