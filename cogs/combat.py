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
from core.combat.loot import generate_weapon, generate_armor, generate_accessory, generate_glove, generate_boot
from core.combat.gen_mob import generate_encounter, generate_boss

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
        equipped_boot = await self.bot.database.get_equipped_boot(user_id)
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

    def _get_boss_phase_data(self, boss_type: str) -> dict:
        """Returns the Phase 1 stats for the requested boss."""
        if boss_type == "aphrodite":
            return {"name": "Aphrodite, Heaven's Envoy", "level": 886, "modifiers_count": 3, "hp_multiplier": 1.5}
        elif boss_type == "lucifer":
            return {"name": "Lucifer, Fallen", "level": 663, "modifiers_count": 2, "hp_multiplier": 1.25}
        elif boss_type == "NEET":
            return {"name": "NEET, Sadge", "level": 444, "modifiers_count": 1, "hp_multiplier": 1.25}
        # Fallback
        return {"name": "Unknown Entity", "level": 999, "modifiers_count": 1, "hp_multiplier": 1.0}

    @app_commands.command(name="combat", description="Engage in combat.")
    async def combat(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation & Cooldowns
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return
        # if not await self._check_cooldown(interaction, user_id, existing_user): return

        if self.update_combat:
            await self.bot.database.users.update_timer(user_id, 'last_combat')
        
        self.bot.state_manager.set_active(user_id, "combat")

        # 2. Initialize Player Object
        player = await load_player(user_id, existing_user, self.bot.database)
        
        # 3. Check for Boss Doors
        is_boss, boss_type = await self._handle_door_mechanic(interaction, player, existing_user)
        
        # 4. Generate Monster (Normal or Boss)
        monster = Monster(name="", level=0, hp=0, max_hp=0, xp=0, attack=0, defence=0, modifiers=[], image="", flavor="")
        
        if is_boss:
            phase_data = self._get_boss_phase_data(boss_type)
            monster = await generate_boss(player, monster, phase_data, 0)
            monster.is_boss = True
        else:
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

        # 5. Apply Combat Start Modifiers
        engine.apply_stat_effects(player, monster)
        start_logs = engine.apply_combat_start_passives(player, monster)
        
        # 6. UI Setup
        if is_boss:
            embed = ui.create_combat_embed(player, monster, start_logs, title_override=f"⚔️ BOSS: {monster.name} ⚔️")
            await interaction.edit_original_response(embed=embed)
            message = await interaction.original_response()
        else:
            embed = ui.create_combat_embed(player, monster, start_logs)
            if interaction.response.is_done():
                message = await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
                message = await interaction.original_response()

        reactions = ["⚔️", "🩹", "⏩", "🏃", "🕒"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

        # 7. Main Combat Loop
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
                        
                        embed = ui.create_combat_embed(player, monster, {player.name: atk_log, monster.name: def_log})
                        await message.edit(embed=embed)
                        await asyncio.sleep(1)
                    if player.current_hp <= int(player.max_hp * 0.2) and monster.hp > 0:
                        logs["Auto-Battle"] = "Paused: Low HP!"

                elif emoji == "🕒": # Giga-Auto
                    turn_count = 0
                    while player.current_hp > int(player.max_hp * 0.2) and monster.hp > 0:
                        turn_count += 1
                        last_atk = engine.process_player_turn(player, monster)
                        last_def = ""
                        if monster.hp > 0:
                            last_def = engine.process_monster_turn(player, monster)
                        
                        if turn_count % 10 == 0:
                            embed = ui.create_combat_embed(player, monster, {player.name: last_atk, monster.name: last_def})
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
                    await self.handle_victory(interaction, message, player, monster)
                    await self._cleanup(user_id, player, message)
                    return

                embed = ui.create_combat_embed(player, monster, logs)
                await message.edit(embed=embed)

            except asyncio.TimeoutError:
                embed.add_field(name="Timeout", value="Combat ended due to inactivity.", inline=False)
                await message.edit(embed=embed)
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
        
        # 1. Rewards
        reward_data = rewards.calculate_rewards(player, monster)
        
        # 2. Special Drops
        special_flags = rewards.check_special_drops(player, monster)
        reward_data['special'] = []
        
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
            await self.bot.database.modify_currency(user_id, interaction.guild.id, 1)
            reward_data['curios'] = 1

        # 3. Gear Drops
        drop_roll = random.randint(1, 100)
        drop_chance = rewards.calculate_item_drop_chance(player)
        reward_data['items'] = []

        if drop_roll <= drop_chance:
            item_roll = random.randint(1, 100)
            
            w_count = await self.bot.database.count_user_weapons(user_id)
            a_count = await self.bot.database.count_user_accessories(user_id)
            ar_count = await self.bot.database.count_user_armors(user_id)
            g_count = await self.bot.database.count_user_gloves(user_id)
            b_count = await self.bot.database.count_user_boots(user_id)
            
            if item_roll <= 40 and w_count < 60:
                item = await generate_weapon(user_id, monster.level, drop_rune=True)
                if item.name == "Rune of Refinement":
                    await self.bot.database.users.modify_currency(user_id, 1)
                    reward_data['items'].append(f"**{item.name}**: {item.description}")
                else:
                    await self.bot.database.create_weapon(item)
                    reward_data['items'].append(item.description)
            elif item_roll <= 60 and a_count < 60:
                item = await generate_accessory(user_id, monster.level, drop_rune=True)
                if item.name == "Rune of Potential":
                    await self.bot.database.users.modify_currency(user_id, 1)
                    reward_data['items'].append(f"**{item.name}**: {item.description}")
                else:
                    await self.bot.database.create_accessory(item)
                    reward_data['items'].append(item.description)
            elif item_roll <= 70 and ar_count < 60:
                item = await generate_armor(user_id, monster.level, drop_rune=True)
                if item.name == "Rune of Imbuing":
                    await self.bot.database.users.modify_currency(user_id, 1)
                    reward_data['items'].append(f"**{item.name}**: {item.description}")
                else:
                    await self.bot.database.create_armor(item)
                    reward_data['items'].append(item.description)
            elif item_roll <= 85 and g_count < 60:
                item = await generate_glove(user_id, monster.level)
                await self.bot.database.create_glove(item)
                reward_data['items'].append(item.description)
            elif item_roll <= 100 and b_count < 60:
                item = await generate_boot(user_id, monster.level)
                await self.bot.database.create_boot(item)
                reward_data['items'].append(item.description)

        # 4. Commit
        player.exp += reward_data['xp']
        await self.bot.database.users.modify_gold(user_id, reward_data['gold'])
        await self._handle_level_up(player, reward_data)

        embed = ui.create_victory_embed(player, monster, reward_data)
        await message.edit(embed=embed)

    async def _handle_level_up(self, player: Player, reward_data: dict):
        exp_table = self.load_exp_table()
        next_level_exp = exp_table["levels"].get(str(player.level), 999999999)
        
        if player.exp >= next_level_exp and player.level < 100:
            player.level += 1
            player.exp -= next_level_exp 
            
            atk_inc = random.randint(1, 5)
            def_inc = random.randint(1, 5)
            hp_inc = random.randint(1, 5)
            
            player.base_attack += atk_inc
            player.base_defence += def_inc
            player.max_hp += hp_inc
            
            await self.bot.database.users.modify_stat(player.id, 'attack', atk_inc)
            await self.bot.database.users.modify_stat(player.id, 'defence', def_inc)
            await self.bot.database.users.modify_stat(player.id, 'max_hp', hp_inc)
            
            reward_data['msgs'].append(f"**LEVEL UP!** You are now level {player.level}!")
            reward_data['msgs'].append(f"Stats: +{atk_inc} Atk, +{def_inc} Def, +{hp_inc} HP")

async def setup(bot) -> None:
    await bot.add_cog(Combat(bot))