import random
import discord
from discord.ext import commands
from discord.ext.tasks import asyncio
from discord import app_commands, Interaction, Message
from datetime import datetime, timedelta
import json

# Data Models & Factory
from core.models import Player, Monster
from core.items.factory import load_player

# Logic Modules
from core.combat import engine, ui, rewards
from core.combat.loot import generate_weapon, generate_armor, generate_accessory, generate_glove, generate_boot, generate_helmet
from core.combat.gen_mob import generate_encounter, generate_boss
from core.skills.mechanics import SkillMechanics

class Combat(commands.Cog, name="combat"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.COMBAT_COOLDOWN_DURATION = timedelta(minutes=10) 
        self.update_combat = True
        self.skills_cog = bot.get_cog("skills")
        
    def load_exp_table(self):
        with open('assets/exp.json') as file:
            return json.load(file)

    async def _check_cooldown(self, interaction: Interaction, user_id: str, existing_user: tuple) -> bool:
        """Calculates dynamic cooldown and checks if user can fight."""
        temp_cooldown_reduction = 0
        equipped_boot = await self.bot.database.equipment.get_equipped(user_id, "boot")
        if equipped_boot and equipped_boot[9] == "speedster":
            temp_cooldown_reduction = equipped_boot[12] * 20 

        current_duration = self.COMBAT_COOLDOWN_DURATION - timedelta(seconds=temp_cooldown_reduction)
        current_duration = max(timedelta(seconds=10), current_duration)

        last_combat_str = existing_user[24]
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
                self.bot.logger.warning(f"Invalid last_combat_time for {user_id}")
        return True

    async def _handle_door_mechanic(self, interaction: Interaction, player: Player, user_data: tuple) -> tuple[bool, str]:
        """
        Checks eligibility and RNG for special boss doors.
        Returns (is_boss_fight: bool, boss_type: str)
        """
        dragon_keys = user_data[25]
        angel_keys = user_data[26]
        soul_cores = user_data[28]
        void_frags = user_data[29]

        roll = random.random()
        user_id = player.id

        # 1. Door of Ascension (Aphrodite)
        if player.level >= 20 and dragon_keys > 0 and angel_keys > 0 and roll < 0.20:
            accepted = await self._present_door_prompt(
                interaction,
                title="Door of Ascension",
                description="Your **Angelic** and **Draconic** keys tremble with anticipation.\nDo you wish to challenge the heavens?",
                image_url="https://i.imgur.com/PXOhTbX.png",
                cost_text="-1 Dragon Key, -1 Angelic Key"
            )
            if accepted:
                await self.bot.database.users.modify_currency(user_id, 'dragon_key', -1)
                await self.bot.database.users.modify_currency(user_id, 'angel_key', -1)
                return True, "aphrodite"

        # 2. Door of the Infernal (Lucifer)
        elif player.level >= 20 and soul_cores >= 5 and 0.20 <= roll < 0.40:
            accepted = await self._present_door_prompt(
                interaction,
                title="Door of the Infernal",
                description="Your soul cores tremble. Do you wish to consume **5** to challenge the depths below?",
                image_url="https://i.imgur.com/bWMAksf.png",
                cost_text="-5 Soul Cores"
            )
            if accepted:
                await self.bot.database.users.modify_currency(user_id, 'soul_cores', -5)
                return True, "lucifer"

        # 3. Sad Anime Kid (NEET)
        elif player.level >= 40 and void_frags >= 3 and 0.60 <= roll < 0.80:
            accepted = await self._present_door_prompt(
                interaction,
                title="Sad Anime Kid",
                description="You see a sad kid in the rain.\nThe **void fragments** in your pocket resonate.\nTake **3** out and investigate?",
                image_url="https://i.imgur.com/6f9OJ4s.jpeg",
                cost_text="-3 Void Fragments"
            )
            if accepted:
                await self.bot.database.users.modify_currency(user_id, 'void_frags', -3)
                return True, "NEET"

        return False, ""

    async def _present_door_prompt(self, interaction: Interaction, title: str, description: str, image_url: str, cost_text: str) -> bool:
        embed = discord.Embed(title=title, description=description, color=0x00FF00)
        if image_url: embed.set_image(url=image_url)
        embed.set_footer(text=f"Cost: {cost_text}")

        if interaction.response.is_done():
            message = await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)
            message = await interaction.original_response()

        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
            await message.clear_reactions()
            
            if str(reaction.emoji) == "✅":
                return True
            else:
                embed.description = "You hesitated, and the opportunity fades."
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                return False
        except asyncio.TimeoutError:
            await message.clear_reactions()
            embed.description = "The door vanishes into the mist..."
            embed.color = discord.Color.dark_grey()
            await message.edit(embed=embed)
            return False

    def _get_boss_phases(self, boss_type: str) -> list[dict]:
        """Returns the list of phases for a specific boss."""
        if boss_type == 'aphrodite':
            return [
                {"name": "Aphrodite, Heaven's Envoy", "level": 886, "modifiers_count": 3, "hp_multiplier": 1.5},
                {"name": "Aphrodite, the Eternal", "level": 887, "modifiers_count": 6, "hp_multiplier": 2},
                {"name": "Aphrodite, Harbinger of Destruction", "level": 888, "modifiers_count": 9, "hp_multiplier": 2.5},
            ]
        elif boss_type == 'lucifer':
            return [
                {"name": "Lucifer, Fallen", "level": 663, "modifiers_count": 2, "hp_multiplier": 1.25},
                {"name": "Lucifer, Maddened", "level": 664, "modifiers_count": 3, "hp_multiplier": 1.5},
                {"name": "Lucifer, Enraged", "level": 665, "modifiers_count": 4, "hp_multiplier": 1.75},
                {"name": "Lucifer, Unbound", "level": 666, "modifiers_count": 5, "hp_multiplier": 2},
            ]
        elif boss_type == 'NEET':
            return [
                {"name": "NEET, Sadge", "level": 444, "modifiers_count": 1, "hp_multiplier": 1.25},
                {"name": "NEET, Madge", "level": 445, "modifiers_count": 2, "hp_multiplier": 1.5},
                {"name": "NEET, REEEEEE", "level": 446, "modifiers_count": 3, "hp_multiplier": 1.75},
                {"name": "NEET, Deadge", "level": 447, "modifiers_count": 5, "hp_multiplier": 0.2},
            ]
        return []

    @app_commands.command(name="combat", description="Engage in combat.")
    async def combat(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation & Cooldowns
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return
        if not await self._check_cooldown(interaction, user_id, existing_user): return

        if self.update_combat:
            await self.bot.database.users.update_timer(user_id, 'last_combat')
        
        self.bot.state_manager.set_active(user_id, "combat")

        # 2. Initialize Player Object
        player = await load_player(user_id, existing_user, self.bot.database)
        
        # 3. Check for Boss Doors
        is_boss, boss_type = await self._handle_door_mechanic(interaction, player, existing_user)

        # 4. Determine Phases
        combat_phases = []
        if is_boss:
            combat_phases = self._get_boss_phases(boss_type)
        else:
            combat_phases = [None] # Dummy list for single iteration

        # 5. Generate Monster (Normal or Boss)
        monster = Monster(name="", level=0, hp=0, max_hp=0, xp=0, attack=0, defence=0, modifiers=[], image="", flavor="")

        # Setup Message
        if interaction.response.is_done():
            message = await interaction.original_response()
        else:
            await interaction.response.send_message(embed=discord.Embed(description="Entering combat..."))
            message = await interaction.original_response()
        
        # =========================================================================
        # MAIN COMBAT LOOP (Iterates through Phases)
        # =========================================================================
        for phase_idx, phase_data in enumerate(combat_phases):
            
            # --- GENERATION ---
            if is_boss:
                monster = await generate_boss(player, monster, phase_data, phase_idx)
                monster.is_boss = True
                phase_title = f"⚔️ BOSS PHASE {phase_idx+1}/{len(combat_phases)}: {monster.name}"
            else:
                # Normal Mob Generation
                treasure_chance = 0.02
                if player.get_armor_passive() == "Treasure Hunter": treasure_chance += 0.05
                if player.equipped_boot and player.equipped_boot.passive == "treasure-tracker":
                    treasure_chance += (player.equipped_boot.passive_lvl * 0.005)

                if random.random() < treasure_chance:
                    monster = await generate_encounter(player, monster, is_treasure=True)
                    monster.attack = 0; monster.defence = 0; monster.xp = 0; monster.hp = 10
                else:
                    monster = await generate_encounter(player, monster, is_treasure=False)
                    if monster.level <= 20: monster.xp = int(monster.xp * 2)
                    else: monster.xp = int(monster.xp * 1.3)
                
                phase_title = f"Witness {player.name} (Level {player.level})"

            # --- PRE-FIGHT SETUP ---
            engine.apply_stat_effects(player, monster)
            start_logs = engine.apply_combat_start_passives(player, monster)
            
            embed = ui.create_combat_embed(player, monster, start_logs, title_override=phase_title)
            await message.edit(embed=embed)

            reactions = ["⚔️", "🩹", "⏩", "🏃", "🕒"]
            # Re-add reactions in case they were cleared
            try:
                for emoji in reactions: await message.add_reaction(emoji)
            except: pass

            # --- TURN LOOP ---
            while player.current_hp > 0 and monster.hp > 0:
                def check(reaction, user):
                    return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in reactions

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
                    
                    elif emoji == "⏩": # Auto-battle
                        while player.current_hp > int(player.max_hp * 0.2) and monster.hp > 0:
                            atk_log = engine.process_player_turn(player, monster)
                            def_log = ""
                            if monster.hp > 0:
                                def_log = engine.process_monster_turn(player, monster)
                            
                            embed = ui.create_combat_embed(player, monster, {player.name: atk_log, monster.name: def_log}, title_override=phase_title)
                            await message.edit(embed=embed)
                            await asyncio.sleep(1)
                        if player.current_hp <= int(player.max_hp * 0.2) and monster.hp > 0:
                            logs["Auto-Battle"] = "Paused: Low HP!"

                    elif emoji == "🕒": # Giga-Auto (Skip anims)
                        turn_count = 0
                        while player.current_hp > int(player.max_hp * 0.2) and monster.hp > 0:
                            turn_count += 1
                            last_atk = engine.process_player_turn(player, monster)
                            last_def = ""
                            if monster.hp > 0:
                                last_def = engine.process_monster_turn(player, monster)
                            
                            if turn_count % 10 == 0:
                                embed = ui.create_combat_embed(player, monster, {player.name: last_atk, monster.name: last_def}, title_override=phase_title)
                                await message.edit(embed=embed)
                                await asyncio.sleep(0.5)
                        
                        logs[player.name] = "Giga-battle complete."

                    elif emoji == "🏃":
                        embed.add_field(name="Escape", value="Got away safely!", inline=False)
                        await message.edit(embed=embed)
                        await self._cleanup(user_id, player, message)
                        return

                    if player.current_hp <= 0:
                        await self.handle_defeat(message, player, monster)
                        await self._cleanup(user_id, player, message)
                        return
                    
                    if monster.hp <= 0:
                        # Break inner loop to proceed to next phase check
                        break 

                    embed = ui.create_combat_embed(player, monster, logs, title_override=phase_title)
                    await message.edit(embed=embed)

                except asyncio.TimeoutError:
                    embed.add_field(name="Timeout", value="Combat ended due to inactivity.", inline=False)
                    await message.edit(embed=embed)
                    await self._cleanup(user_id, player, message)
                    return
            
            # --- END OF TURN LOOP ---
            
            # Check if there are more phases
            if is_boss and phase_idx < len(combat_phases) - 1:
                # Transition Logic
                transition_embed = discord.Embed(
                    title="Phase Complete!", 
                    description=f"**{monster.name}** falls, but the air grows heavier...\nNext phase beginning shortly.", 
                    color=discord.Color.orange()
                )
                transition_embed.set_thumbnail(url=monster.image)
                await message.edit(embed=transition_embed)
                await message.clear_reactions()
                await asyncio.sleep(3)
                # Continue loop to next phase
            else:
                # Final Victory (Normal mob or Final Boss Phase)
                await self.handle_victory(interaction, message, player, monster)
                await self._cleanup(user_id, player, message)
                return

    async def _cleanup(self, user_id: str, player: Player, message: Message):
        self.bot.state_manager.clear_active(user_id)
        await message.clear_reactions()
        await self.bot.database.users.update_from_player_object(player)

    async def handle_defeat(self, message: Message, player: Player, monster: Monster):
        xp_loss = int(player.exp * 0.10)
        player.exp = max(0, player.exp - xp_loss)
        player.current_hp = 1
        
        embed = ui.create_defeat_embed(player, monster, xp_loss)
        await message.edit(embed=embed)

    async def handle_victory(self, interaction: Interaction, message: Message, player: Player, monster: Monster):
        user_id = player.id
        server_id = str(interaction.guild.id) # Need server_id for skills
        # 1. Rewards Calculation
        reward_data = rewards.calculate_rewards(player, monster)
        
        # 2. Special Drops & Boss Logic
        special_flags = rewards.check_special_drops(player, monster)
        reward_data['special'] = []

        if player.equipped_boot and player.equipped_boot.passive == "skiller":
            proc_chance = player.equipped_boot.passive_lvl * 0.05
            if random.random() < proc_chance:
                skill_type_roll = random.choice(['mining', 'woodcutting', 'fishing'])
                
                # Fetch tool tier
                # Note: We need to access the skills repo via bot.database
                skill_row = await self.bot.database.skills.get_data(user_id, server_id, skill_type_roll)
                
                if skill_row:
                    tool_tier = skill_row[2]
                    # Use static mechanic
                    resources = SkillMechanics.calculate_yield(skill_type_roll, tool_tier)
                    
                    # Update DB
                    await self.bot.database.skills.update_batch(user_id, server_id, skill_type_roll, resources)
                    
                    # Add to reward messages
                    msg_map = {
                        'mining': "ores", 'woodcutting': "logs", 'fishing': "fish"
                    }
                    reward_data['msgs'].append(f"👢 **Skiller ({player.equipped_boot.passive_lvl})** found extra {msg_map[skill_type_roll]}!")
        
        if special_flags.get('draconic_key'):
            await self.bot.database.users.modify_currency(user_id, 'dragon_key', 1)
            reward_data['special'].append("Draconic Key")
        if special_flags.get('angelic_key'):
            await self.bot.database.users.modify_currency(user_id, 'angel_key', 1)
            reward_data['special'].append("Angelic Key")
        if special_flags.get('soul_core'):
            await self.bot.database.users.modify_currency(user_id, 'soul_cores', 1)
            reward_data['special'].append("Soul Core")
        if special_flags.get('void_frag'):
            await self.bot.database.users.modify_currency(user_id, 'void_frags', 1)
            reward_data['special'].append("Void Fragment")
        if special_flags.get('shatter_rune'):
            await self.bot.database.users.modify_currency(user_id, 'shatter_runes', 1)
            reward_data['special'].append("Rune of Shattering")
        if special_flags.get('curio'):
            await self.bot.database.users.modify_currency(user_id, 'curios', 1)
            reward_data['curios'] = 1

        # Boss Specific Runes
        if special_flags.get('refinement_rune'):
            await self.bot.database.users.modify_currency(user_id, 'refinement_runes', 1)
            reward_data['special'].append("Rune of Refinement")
        if special_flags.get('potential_rune'):
            await self.bot.database.users.modify_currency(user_id, 'potential_runes', 1)
            reward_data['special'].append("Rune of Potential")
        if special_flags.get('imbue_rune'):
            await self.bot.database.users.modify_currency(user_id, 'imbue_runes', 1)
            reward_data['special'].append("Rune of Imbuing")

        # 3. Gear Drops
        drop_roll = random.randint(1, 100)
        drop_threshold = rewards.calculate_item_drop_chance(player)
        self.bot.logger.info(f'Player had {player.rarity}, player rolled {drop_roll} versus {drop_threshold} drop_threshold (under to drop item)')
        reward_data['items'] = []

        if drop_roll <= drop_threshold:
            item_roll = random.randint(1, 100)
            
            w_count = await self.bot.database.equipment.get_count(user_id, 'weapon')
            a_count = await self.bot.database.equipment.get_count(user_id, 'accessories')
            ar_count = await self.bot.database.equipment.get_count(user_id, 'armor')
            g_count = await self.bot.database.equipment.get_count(user_id, 'glove')
            b_count = await self.bot.database.equipment.get_count(user_id, 'boot')
            h_count = await self.bot.database.equipment.get_count(user_id, 'helmet')
            
            # Adjusted Distribution:
            # Weapon: 1-35 (35%)
            # Accessory: 36-55 (25%)
            # Armor: 56-65 (10%)
            # Gloves: 66-80 (10%)
            # Boots: 81-90 (10%)
            # Helmets: 91-100 (10%)

            if item_roll <= 35 and w_count < 60:
                item = await generate_weapon(user_id, monster.level, drop_rune=True)
                if item.name == "Rune of Refinement":
                    await self.bot.database.users.modify_currency(user_id, 'refinement_runes', 1)
                    reward_data['items'].append(f"**{item.name}**: {item.description}")
                else:
                    await self.bot.database.equipment.create_weapon(item)
                    reward_data['items'].append(item.description)
            elif item_roll <= 60 and a_count < 60:
                item = await generate_accessory(user_id, monster.level, drop_rune=True)
                if item.name == "Rune of Potential":
                    await self.bot.database.users.modify_currency(user_id, 'potential_runes', 1)
                    reward_data['items'].append(f"**{item.name}**: {item.description}")
                else:
                    await self.bot.database.equipment.create_accessory(item)
                    reward_data['items'].append(item.description)
            elif item_roll <= 70 and ar_count < 60:
                item = await generate_armor(user_id, monster.level, drop_rune=True)
                if item.name == "Rune of Imbuing":
                    await self.bot.database.users.modify_currency(user_id, 'imbue_runes', 1)
                    reward_data['items'].append(f"**{item.name}**: {item.description}")
                else:
                    await self.bot.database.equipment.create_armor(item)
                    reward_data['items'].append(item.description)
            elif item_roll <= 80 and g_count < 60:
                item = await generate_glove(user_id, monster.level)
                await self.bot.database.equipment.create_glove(item)
                reward_data['items'].append(item.description)
            elif item_roll <= 90 and b_count < 60:
                item = await generate_boot(user_id, monster.level)
                await self.bot.database.equipment.create_boot(item)
                reward_data['items'].append(item.description)
            elif item_roll <= 100 and h_count < 60:
                item = await generate_helmet(user_id, monster.level)
                await self.bot.database.equipment.create_helmet(item)
                reward_data['items'].append(item.description)

        # 4. Commit
        player.exp += reward_data['xp']
        await self.bot.database.users.modify_gold(user_id, reward_data['gold'])
        await self._handle_level_up(player, reward_data)

        embed = ui.create_victory_embed(player, monster, reward_data)

        # BOSS FINALE SCENES
        if "Aphrodite" in monster.name:
            embed.set_image(url="https://i.imgur.com/wKyTFzh.jpg")
            await message.edit(embed=embed)
            
        elif "NEET" in monster.name:
            embed.set_image(url="https://i.imgur.com/7UmY4Mo.jpeg")
            embed.add_field(name="As the tombstone crumbles...", value="You find a **Void Key**.", inline=False)
            await self.bot.database.users.modify_currency(user_id, 'void_keys', 1)
            await message.edit(embed=embed)

        elif "Lucifer" in monster.name:
            embed.set_image(url="https://i.imgur.com/x9suAGK.png")
            await message.edit(embed=embed)
            # Trigger interactive selection
            await self._handle_lucifer_choice(interaction, message, user_id, player)
        await message.edit(embed=embed)

    
    async def _handle_lucifer_choice(self, interaction: Interaction, message: Message, user_id: str, player: Player):
        """Handles the post-combat Soul Core selection for Lucifer."""
        embed = message.embeds[0]
        embed.add_field(
            name="Soul Core Selection", 
            value=(
                "Lucifer's soul shatters. Choose a core to consume:\n"
                "🩶 **Inverse**: Swap Atk/Def\n"
                "❤️‍🔥 **Enraged**: Atk -1 to +2\n"
                "💙 **Solidified**: Def -1 to +2\n"
                "💔 **Unstable**: Randomize towards equilibrium\n"
                "🖤 **Original**: Gain 1 Soul Core"
            ),
            inline=False
        )
        await message.edit(embed=embed)
        
        reactions = ["🩶", "❤️‍🔥", "💙", "💔", "🖤"]
        await asyncio.gather(*(message.add_reaction(r) for r in reactions))

        def check(r, u): 
            return u.id == int(user_id) and str(r.emoji) in reactions and r.message.id == message.id

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=60, check=check)
            emoji = str(reaction.emoji)
            
            resp = ""
            if emoji == "🩶":
                await self.bot.database.users.modify_stat(user_id, 'attack', player.base_defence - player.base_attack)
                await self.bot.database.users.modify_stat(user_id, 'defence', player.base_attack - player.base_defence)
                resp = f"Stats Swapped! Atk: {player.base_defence}, Def: {player.base_attack}"

            elif emoji == "❤️‍🔥":
                adj = random.randint(-1, 2)
                await self.bot.database.users.modify_stat(user_id, 'attack', adj)
                resp = f"Enraged! Attack changed by {adj}."

            elif emoji == "💙":
                adj = random.randint(-1, 2)
                await self.bot.database.users.modify_stat(user_id, 'defence', adj)
                resp = f"Solidified! Defence changed by {adj}."

            elif emoji == "💔":
                total = player.base_attack + player.base_defence
                new_atk = int(total * random.uniform(0.49, 0.51))
                new_def = total - new_atk
                # Calc diffs
                atk_diff = new_atk - player.base_attack
                def_diff = new_def - player.base_defence
                await self.bot.database.users.modify_stat(user_id, 'attack', atk_diff)
                await self.bot.database.users.modify_stat(user_id, 'defence', def_diff)
                resp = f"Chaos ensues! New Atk: {new_atk}, New Def: {new_def}"

            elif emoji == "🖤":
                await self.bot.database.users.modify_currency(user_id, 'soul_cores', 1)
                resp = "You pocketed a Soul Core."

            embed.add_field(name="Choice", value=resp, inline=False)
            await message.edit(embed=embed)
            await message.clear_reactions()

        except asyncio.TimeoutError:
            pass

    async def _handle_level_up(self, player: Player, reward_data: dict):
            """
            Handles Level Ups, Stat Growth, Passive Points, and Ascension.
            """
            user_id = player.id
            exp_table = self.load_exp_table()
            
            # Get threshold for current level (Default to high number if maxed/missing)
            exp_threshold = exp_table["levels"].get(str(player.level), 999999999)
            
            # --- ASCENSION LOGIC (Level 100) ---
            if player.level >= 100 and player.exp >= exp_threshold:
                player.ascension += 1
                player.exp -= exp_threshold  # Rollover XP
                
                # Grant 2 Passive Points
                # Assuming 'passive_points' is a column supported by modify_currency based on previous refactor steps
                await self.bot.database.users.modify_currency(user_id, 'passive_points', 2)
                
                reward_data['msgs'].append(f"🌟 **ASCENSION LEVEL UP!**")
                reward_data['msgs'].append(f"{player.name} has reached Ascension **{player.ascension}**!")
                reward_data['msgs'].append("✨ Gained **2** Passive Points! (Use /passives)")
                return # Process complete for this turn

            # --- STANDARD LEVEL UP LOGIC (< 100) ---
            if player.level < 100 and player.exp >= exp_threshold:
                player.level += 1
                player.exp -= exp_threshold # Rollover XP
                
                # 1. Roll Stat Increases
                atk_inc = random.randint(1, 5)
                def_inc = random.randint(1, 5)
                hp_inc = random.randint(1, 5)
                
                # 2. Update Memory Object (So Victory Embed shows correct stats/HP cap)
                player.base_attack += atk_inc
                player.base_defence += def_inc
                player.max_hp += hp_inc
                # Optional: Heal the amount gained so they don't feel weaker %-wise
                player.current_hp += hp_inc 
                
                # 3. DB Updates (Permanent Stats)
                # update_player() saves Level/Exp, but we need to save the base stats explicitly
                await self.bot.database.users.modify_stat(user_id, 'attack', atk_inc)
                await self.bot.database.users.modify_stat(user_id, 'defence', def_inc)
                await self.bot.database.users.modify_stat(user_id, 'max_hp', hp_inc)
                
                reward_data['msgs'].append(f"🎉 **LEVEL UP!** You are now level {player.level}!")
                reward_data['msgs'].append(f"📈 Stats: +{atk_inc} Atk, +{def_inc} Def, +{hp_inc} HP")

                # 4. Passive Points Milestone (Every 10 Levels)
                if player.level % 10 == 0:
                    await self.bot.database.users.modify_currency(user_id, 'passive_points', 2)
                    reward_data['msgs'].append(f"✨ **Milestone!** Gained **2** Passive Points! (Use /passives)")

async def setup(bot) -> None:
    await bot.add_cog(Combat(bot))