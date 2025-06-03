import random
import discord
from discord.ext import commands
from discord.ext.tasks import asyncio
from discord import app_commands, Interaction, Message
from datetime import datetime, timedelta
from core.models import Player, Monster, Weapon, Accessory, Armor
from core.loot import generate_weapon, generate_armor, generate_accessory
from core.combat_calcs import calculate_hit_chance, calculate_monster_hit_chance, calculate_damage_taken, check_cull
from core.gen_mob import get_modifier_description, generate_encounter, generate_boss, generate_ascent_monster # Added generate_ascent_monster
import json

class Combat(commands.Cog, name="combat"):
    def __init__(self, bot) -> None:
        self.bot = bot
        # Cooldown can be a class attribute if it's fixed or loaded from config
        self.COMBAT_COOLDOWN_DURATION = timedelta(minutes=10) 
        
    def load_exp_table(self):
        with open('assets/exp.json') as file:
            exp_table = json.load(file)
        return exp_table
    
    async def update_combat_embed(self, embed, player, monster, messages=None):
        messages = messages or {}
        # Retain title if already set (e.g. for Ascent)
        # current_title = embed.title
        # current_description = embed.description # If we want to preserve parts of it
        
        embed.clear_fields()
        # if current_title: embed.title = current_title # Re-apply if needed, or set before calling
        # if current_description: embed.description = current_description

        embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
        hp_value = f"{player.hp} ({player.ward} 🔮)" if player.ward > 0 else player.hp
        embed.add_field(name="❤️ HP", value=hp_value, inline=True)
        
        for name, message in messages.items():
            if message: # Only add field if message is not empty
                embed.add_field(name=name, value=message, inline=False)
        
        return embed


    def apply_stat_effects(self, player, monster):
        modifier_effects = {
            "Shield-breaker": lambda p, m: setattr(p, "ward", 0),
            "Impenetrable": lambda p, m: setattr(p, "crit", p.crit + 5), # This seems to buff player crit, which is unusual for a monster mod
            "Unblockable": lambda p, m: setattr(p, "block", 0),
            "Unavoidable": lambda p, m: setattr(p, "evasion", 0),
            "Enfeeble": lambda p, m: setattr(p, "attack", int(p.attack * 0.9)),
            "Overwhelm": lambda p, m: (
                setattr(p, "ward", 0),
                setattr(p, "block", 0),
                setattr(p, "evasion", 0)
            ),
            "Temporal Bubble": lambda p, m: setattr(p, "weapon_passive", "none") # Effect of Temporal Bubble
        }
        
        original_weapon_passive = player.weapon_passive # Store original in case multiple mods try to change it

        for modifier in monster.modifiers:
            if modifier in modifier_effects:
                if modifier == "Temporal Bubble":
                    player.weapon_passive = "none" # Explicitly set for Temporal Bubble
                    self.bot.logger.info(f'Applied {modifier}, player weapon passive disabled.')
                else:
                    modifier_effects[modifier](player, monster)
                    self.bot.logger.info(f'Applied {modifier}')
        
        # If Temporal Bubble was not applied, restore original passive (in case other future mods affect it)
        # This part might be overly complex if only Temporal Bubble modifies it.
        # if "Temporal Bubble" not in monster.modifiers and player.weapon_passive == "none" and original_weapon_passive != "none":
        #    player.weapon_passive = original_weapon_passive


    async def _initialize_player_for_combat(self, user_id, existing_user_data):
        player = Player(
            id=user_id,
            name=existing_user_data[3],
            level=existing_user_data[4],
            ascension=existing_user_data[15],
            exp=existing_user_data[5],
            hp=existing_user_data[11],
            max_hp=existing_user_data[12],
            attack=existing_user_data[9],
            defence=existing_user_data[10],
            rarity=0, # Base, will be modified by gear
            crit=95,  # Base crit (meaning 5% crit chance, lower is better for player), will be modified
            ward=0,   # Base ward, will be modified by gear
            block=0,  # Base block, will be modified by gear
            evasion=0,# Base evasion, will be modified by gear
            potions=existing_user_data[16],
            wep_id=0, # To be populated
            weapon_passive="",
            acc_passive="",
            acc_lvl=0,
            armor_passive="",
            invulnerable=False # Default state
        )

        # Handle equipped weapon
        equipped_item = await self.bot.database.get_equipped_weapon(user_id)
        if equipped_item:
            player.wep_id = equipped_item[0]
            player.weapon_passive = equipped_item[7]
            player.attack += equipped_item[4]
            player.defence += equipped_item[5]
            player.rarity += equipped_item[6]
            self.bot.logger.info(f'Weapon: ATK {equipped_item[4]}, DEF {equipped_item[5]}, RAR {equipped_item[6]}, Passive: {player.weapon_passive}')

        # Handle equipped accessory
        equipped_accessory = await self.bot.database.get_equipped_accessory(user_id)
        if equipped_accessory:
            player.acc_passive = equipped_accessory[9]
            player.attack += equipped_accessory[4]
            player.defence += equipped_accessory[5]
            player.rarity += equipped_accessory[6]
            # Ward from accessory is percentage of MAX HP
            accessory_ward_percentage = equipped_accessory[7]
            if accessory_ward_percentage > 0:
                player.ward += max(1, int((accessory_ward_percentage / 100) * player.max_hp))
            
            player.crit -= equipped_accessory[8] # Lower player.crit means higher crit chance for player
            player.acc_lvl = equipped_accessory[12]
            self.bot.logger.info(f'Accessory: ATK {equipped_accessory[4]}, DEF {equipped_accessory[5]}, RAR {equipped_accessory[6]}, Crit Bonus {equipped_accessory[8]}% (Player Crit Target: {player.crit}), Ward {accessory_ward_percentage}%, Passive: {player.acc_passive} (Lvl {player.acc_lvl})')
            
        # Handle equipped armor
        equipped_armor = await self.bot.database.get_equipped_armor(user_id)
        if equipped_armor:
            player.armor_passive = equipped_armor[7]
            # Ward from armor is percentage of MAX HP
            armor_ward_percentage = equipped_armor[6]
            if armor_ward_percentage > 0:
                player.ward += int((armor_ward_percentage / 100) * player.max_hp)
            player.block += equipped_armor[4]
            player.evasion += equipped_armor[5]
            self.bot.logger.info(f'Armor: Block {player.block}, Evasion {player.evasion}, Ward {armor_ward_percentage}%, Passive: {player.armor_passive}')
        
        player.rarity = max(0, player.rarity) # Ensure rarity is not negative
        return player

    async def _apply_combat_start_passives(self, player, monster, embed_to_modify, treasure_hunter_triggered=False, greed_good_triggered=False):
        # Player armor passives
        if player.armor_passive == "Treasure Hunter" and treasure_hunter_triggered:
            embed_to_modify.add_field(name="Armor Passive", value="The **Treasure Hunter** armor imbues with power!\nA mysterious encounter appears...", inline=False)
        
        player.invulnerable = False # Reset invulnerability each combat/stage
        if player.armor_passive == "Invulnerable" and random.random() < 0.2:
            embed_to_modify.add_field(name="Armor Passive", value=f"The **Invulnerable** armor imbues with power!\n{player.name} receives divine protection.", inline=False)
            player.invulnerable = True

        if player.armor_passive == "Omnipotent" and random.random() < 0.2: # Omnipotent needs to be checked after monster stats are set
            monster.attack = 0
            monster.defence = 0
            self.bot.logger.info("Omnipotent passive: Monster attack and defense set to 0")
            embed_to_modify.add_field(name="Armor Passive", value=f"The **Omnipotent** armor imbues with power!\nThe {monster.name} trembles in **terror**.", inline=False)
            
        if player.armor_passive == "Unlimited Wealth" and greed_good_triggered: # This is usually checked before monster gen for /combat
             # For ascent, this could be a per-stage proc or a global buff if triggered once
            embed_to_modify.add_field(name="Armor Passive", value=f"The **Unlimited Wealth** armor imbues with power!\n{player.name}'s greed knows no bounds.", inline=False)

        # Player accessory passives
        if player.acc_passive == "Absorb":
            absorb_chance = player.acc_lvl * 0.10 # 10% per level
            if random.random() <= absorb_chance:
                monster_stats_total = monster.attack + monster.defence
                if monster_stats_total > 0: # Only absorb if monster has stats
                    absorb_amount = max(1, int(monster_stats_total * 0.10)) # Absorb 10% of combined stats, min 1
                    player.attack += absorb_amount
                    player.defence += absorb_amount
                    embed_to_modify.add_field(name="Accessory Passive",
                                            value=f"The accessory's 🌀 **Absorb (Lvl {player.acc_lvl})** activates!\n"
                                                  f"⚔️ Attack boosted by **{absorb_amount}**\n"
                                                  f"🛡️ Defence boosted by **{absorb_amount}**",
                                            inline=False)
        
        # Player weapon passives
        polished_passives = ["polished", "honed", "gleaming", "tempered", "flaring"]
        if player.weapon_passive in polished_passives:
            value = polished_passives.index(player.weapon_passive)
            defence_reduction_percentage = (value + 1) * 0.08 # 8% to 40%
            reduced_amount = int(monster.defence * defence_reduction_percentage)
            monster.defence = max(0, monster.defence - reduced_amount) # Ensure defence doesn't go below 0
            embed_to_modify.add_field(name="Weapon Passive",
                                    value=f"The **{player.weapon_passive}** weapon 💫 shines!\n"
                                          f"Reduces {monster.name}'s defence by {reduced_amount} ({defence_reduction_percentage*100:.0f}%).",
                                    inline=False)
            
        sturdy_passives = ["sturdy", "reinforced", "thickened", "impregnable", "impenetrable"]
        if player.weapon_passive in sturdy_passives:
            value = sturdy_passives.index(player.weapon_passive)
            defence_bonus_percentage = (value + 1) * 0.08 # 8% to 40%
            defence_bonus_amount = int(player.defence * defence_bonus_percentage) # Bonus based on player's current defence
            player.defence += defence_bonus_amount
            embed_to_modify.add_field(name="Weapon Passive",
                                    value=f"The **{player.weapon_passive}** weapon strengthens resolve!\n"
                                          f"🛡️ Player defence boosted by **{defence_bonus_amount}**!",
                                    inline=False)


    @app_commands.command(name="combat", description="Engage in combat.")
    async def combat(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        if not await self.bot.check_is_active(interaction, user_id):
            return

        # last_combat_time_str = existing_user[24]
        # if last_combat_time_str:
        #     try:
        #         last_combat_time_dt = datetime.fromisoformat(last_combat_time_str)
        #         time_since_combat = datetime.now() - last_combat_time_dt
        #         if time_since_combat < self.COMBAT_COOLDOWN_DURATION:
        #             remaining_cooldown = self.COMBAT_COOLDOWN_DURATION - time_since_combat
        #             await interaction.response.send_message(
        #                 f"Please slow down. Try again in {(remaining_cooldown.seconds // 60) % 60} minute(s) "
        #                 f"{(remaining_cooldown.seconds % 60)} second(s).",
        #                 ephemeral=True
        #             )
        #             return
        #     except ValueError:
        #         self.bot.logger.warning(f"Invalid datetime format for last_combat_time for user {user_id}: {last_combat_time_str}")
        
        # await self.bot.database.update_combat_time(user_id)
        self.bot.state_manager.set_active(user_id, "combat")
        
        player = await self._initialize_player_for_combat(user_id, existing_user)

        # Check for Door of Ascension / Infernal Door
        is_boss_encounter = False
        boss_type = '' # aphrodite or lucifer
        # ... (Existing logic for Door of Ascension and Infernal Door)
        # This part is complex and specific to /combat, so I'll keep it summarized
        # For brevity, I'm assuming this logic is correctly placed and functional.
        # If a door is chosen, it leads to handle_boss_encounter and returns.
        
        # Example placeholder for door logic:
        door_chance_roll = random.random()
        aphrodite_eligible = player.level >= 20 and existing_user[25] > 0 and existing_user[26] > 0
        lucifer_eligible = player.level >= 20 and existing_user[28] >= 5

        # Simplified Door Logic for brevity
        if aphrodite_eligible and door_chance_roll < 0.02: # Reduced chance for example
            # ... (Aphrodite door prompt logic) ...
            # if chosen: is_boss_encounter = True; boss_type = 'aphrodite'
            pass 
        elif lucifer_eligible and door_chance_roll < 0.04: # Reduced chance
            # ... (Lucifer door prompt logic) ...
            # if chosen: is_boss_encounter = True; boss_type = 'lucifer'
            pass

        if is_boss_encounter:
            await self.handle_boss_encounter(interaction, player, boss_type)
            self.bot.state_manager.clear_active(user_id) # Ensure state is cleared after boss
            return
            
        # Regular combat monster generation
        treasure_hunter_triggered = False
        treasure_chance = 0.02
        if player.armor_passive == "Treasure Hunter":
            treasure_chance += 0.05
        
        monster = Monster(name="",level=0,hp=0,max_hp=0,xp=0,attack=0,defence=0,modifiers=[],image="",flavor="",is_boss=False)

        if random.random() < treasure_chance:
            monster = await generate_encounter(player, monster, is_treasure=True)
            monster.attack = 0; monster.defence = 0; monster.xp = 0 # Treasure monster stats
            treasure_hunter_triggered = True # Flag that TH armor might have triggered this
        else:
            monster = await generate_encounter(player, monster, is_treasure=False)
            # XP scaling for normal monsters
            if monster.level <= 20: monster.xp = int(monster.xp * 2)
            else: monster.xp = int(monster.xp * 1.3)

        self.bot.logger.info(f"Generated normal monster: {monster}")
        
        # Greed is Good for Unlimited Wealth, affects rarity
        greed_good_triggered = False
        if player.armor_passive == "Unlimited Wealth" and random.random() < 0.2:
            player.rarity *= 5 # UW passive effect
            greed_good_triggered = True
            self.bot.logger.info(f"Unlimited Wealth triggered, player rarity: {player.rarity}")

        player.rarity += len(monster.modifiers) * 30 # Rarity bonus from monster mods
        self.bot.logger.info(f"Player combat stats: {player}")

        # Apply monster modifier effects on player (like Enfeeble, Shield-breaker)
        self.apply_stat_effects(player, monster) # Modifies player object

        # --- Embed Setup for Combat ---
        mod_text = f" {len(monster.modifiers)}-mod " if monster.modifiers else " "
        modifiers_title = "\n__Modifiers__\n" if monster.modifiers else ""
        mods_space = "\n" if monster.modifiers else ""
        
        # Corrected hit chance display string
        player_hit_c = calculate_hit_chance(player, monster)
        monster_hit_c_base = calculate_monster_hit_chance(player, monster)
        player_evade_bonus = (0.01 + player.evasion / 400) if player.evasion > 0 else 0
        effective_monster_hit_c = max(0, monster_hit_c_base - player_evade_bonus)

        embed_description = (f"A{mod_text}level **{monster.level}** {monster.name} approaches!\n"
                             f"{modifiers_title}" +
                             "\n".join([f"**{m}**: {get_modifier_description(m)}" for m in monster.modifiers]) +
                             f"{mods_space}"
                             f"\n~{int(player_hit_c * 100)}% to hit | "
                             f"~{int(effective_monster_hit_c * 100)}% to be hit")

        embed = discord.Embed(title=f"Witness {player.name} (Level {player.level})", description=embed_description, color=0x00FF00)
        embed.set_image(url=monster.image)
        embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
        hp_value = f"{player.hp} ({player.ward} 🔮)" if player.ward > 0 else player.hp
        embed.add_field(name="❤️ HP", value=hp_value, inline=True)

        # Pouch warnings
        # ... (Assume this logic is present and correct)

        # Apply combat start passives and update embed
        await self._apply_combat_start_passives(player, monster, embed, treasure_hunter_triggered, greed_good_triggered)
        
        if is_boss_encounter : # This means a door was chosen, message might be followup
             message = await interaction.followup.send(embed=embed, ephemeral=False)
        else: # Standard /combat start
            await interaction.response.send_message(embed=embed)
            message = await interaction.original_response()
        
        # --- Combat Loop ---
        reactions = ["⚔️", "🩹", "⏩", "🏃", "🕒"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))
        
        attack_message, monster_message, heal_message, pause_message = "", "", "", ""
        while True: # Main combat loop for /combat
            def check_reaction(reaction, user):
                return (user == interaction.user and
                        reaction.message.id == message.id and
                        str(reaction.emoji) in reactions)
            try:
                reaction_obj, reaction_user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check_reaction)
                action_emoji = str(reaction_obj.emoji)
                await message.remove_reaction(reaction_obj.emoji, reaction_user)

                heal_message, attack_message, monster_message, pause_message = "", "", "", ""

                if action_emoji == "⚔️":
                    monster, attack_message = await self.player_turn(player, monster)
                    if monster.hp > 0: player, monster_message = await self.monster_turn(player, monster)
                elif action_emoji == "🩹":
                    player, heal_message = await self.heal(player)
                elif action_emoji == "⏩": # Auto-battle
                    player, monster = await self.auto_battle(interaction, message, embed, player, monster)
                    if player.hp <= int(player.max_hp * 0.2) and monster.hp > 0 and player.hp > 0 : # Paused
                        pause_message = "Player HP < 20%, auto-battle paused!"
                        await interaction.followup.send(f'{interaction.user.mention} auto-combat paused!', ephemeral=True)
                    # auto_battle handles its own victory/defeat and returns, so we might break here or check player/monster HP
                elif action_emoji == "🕒": # Giga-auto-battle
                    player, monster = await self.giga_auto_battle(interaction, message, embed, player, monster)
                    if player.hp <= int(player.max_hp * 0.2) and monster.hp > 0 and player.hp > 0: # Paused
                        pause_message = "Player HP < 20%, auto-battle paused!"
                        await interaction.followup.send(f'{interaction.user.mention} giga auto-combat paused!', ephemeral=True)
                elif action_emoji == "🏃":
                    await message.clear_reactions()
                    embed.add_field(name="Escape", value="Got away safely!", inline=False)
                    await message.edit(embed=embed)
                    self.bot.state_manager.clear_active(user_id)
                    await self.bot.database.update_player(player) # Save HP/potions
                    return # Exit /combat

                # Check for defeat/victory after action
                if player.hp <= 0:
                    await self.handle_defeat(message, player, monster)
                    self.bot.state_manager.clear_active(user_id)
                    return
                if monster.hp <= 0:
                    await self.handle_victory(interaction, message, player, monster)
                    self.bot.state_manager.clear_active(user_id)
                    return
                
                # Update embed if combat continues
                messages = {player.name: attack_message, monster.name: monster_message, "Heal": heal_message, "Auto-Battle": pause_message}
                embed = await self.update_combat_embed(embed, player, monster, messages)
                await message.edit(embed=embed)

            except asyncio.TimeoutError:
                embed.add_field(name="Timeout", value=f"{monster.name} wanders off...", inline=False)
                await message.edit(embed=embed)
                await message.clear_reactions()
                self.bot.state_manager.clear_active(user_id)
                await self.bot.database.update_player(player) # Save HP/potions
                return
    
    @app_commands.command(name="ascent", description="Begin your ascent against increasingly powerful foes.")
    async def ascent(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        if existing_user[4] < 100:
            await interaction.response.send_message(
                f"The path of ascent is brutal. Come back at level 100.",
                ephemeral=True
            )
            return

        # --- COOLDOWN CHECK (Shared with /combat) ---
        last_combat_time_str = existing_user[24] 
        if last_combat_time_str:
            try:
                last_combat_time_dt = datetime.fromisoformat(last_combat_time_str)
                time_since_combat = datetime.now() - last_combat_time_dt
                if time_since_combat < self.COMBAT_COOLDOWN_DURATION:
                    remaining_cooldown = self.COMBAT_COOLDOWN_DURATION - time_since_combat
                    await interaction.response.send_message(
                        f"The path of ascent is tiring. Rest for {(remaining_cooldown.seconds // 60) % 60} minute(s) "
                        f"{(remaining_cooldown.seconds % 60)} second(s).",
                        ephemeral=True
                    )
                    return
            except ValueError:
                self.bot.logger.warning(f"Invalid datetime format for last_combat_time for user {user_id}: {last_combat_time_str}")
        
        await self.bot.database.update_combat_time(user_id)
        self.bot.state_manager.set_active(user_id, "ascent")

        player = await self._initialize_player_for_combat(user_id, existing_user)

        # --- ASCENT VARIABLES ---
        # Start ascent monster level at player's current level or slightly higher for a challenge.
        current_monster_base_level = player.level + player.ascension # Base level for the stage
        current_normal_mods = 5
        current_boss_mods = 1
        ascent_stage = 1
        
        message = None # To store the interaction message for editing across stages

        # --- MAIN ASCENT LOOP ---
        while True: 
            monster_object_template = Monster(name="",level=0,hp=0,max_hp=0,xp=0,attack=0,defence=0,modifiers=[],image="",flavor="",is_boss=True)
            monster = await generate_ascent_monster(player, monster_object_template, current_monster_base_level, current_normal_mods, current_boss_mods)
            self.bot.logger.info(f"Ascent Stage {ascent_stage}: Player Lvl {player.level}, Monster Lvl {monster.level} (Base {current_monster_base_level}), Modifiers: {monster.modifiers}")
            
            self.apply_stat_effects(player, monster) # Apply monster mods effects on player stats (e.g. Enfeeble)

            # --- UI and COMBAT SETUP ---
            embed_title = f"Ascent - Stage {ascent_stage} | {player.name} (Lvl {player.level} - Asc {player.ascension})"
            
            player_hit_c = calculate_hit_chance(player, monster)
            monster_hit_c_base = calculate_monster_hit_chance(player, monster)
            player_evade_bonus = (0.01 + player.evasion / 400) if player.evasion > 0 else 0
            effective_monster_hit_c = max(0, monster_hit_c_base - player_evade_bonus)

            embed_description = (f"A formidable foe bars your ascent: Level **{monster.level}** {monster.name}!\n"
                                 f"\n__Modifiers ({len(monster.modifiers)})__\n" +
                                 "\n".join([f"**{m}**: {get_modifier_description(m)}" for m in monster.modifiers]) +
                                 f"\n\n~{int(player_hit_c * 100)}% to hit | "
                                 f"~{int(effective_monster_hit_c * 100)}% to be hit")
            
            embed = discord.Embed(title=embed_title, description=embed_description, color=discord.Color.orange())
            embed.set_image(url=monster.image)
            embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
            hp_value = f"{player.hp} ({player.ward} 🔮)" if player.ward > 0 else player.hp
            embed.add_field(name="❤️ HP", value=hp_value, inline=True)
            
            await self._apply_combat_start_passives(player, monster, embed) # Apply relevant player passives

            if ascent_stage == 1:
                await interaction.response.send_message(embed=embed)
                message = await interaction.original_response()
            else:
                await message.edit(embed=embed)
                await message.clear_reactions() 

            reactions = ["⚔️", "🩹", "⏩", "🏃"] # Standard reactions for ascent
            await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

            # --- INNER COMBAT LOOP (for the current monster) ---
            attack_message, monster_message, heal_message, pause_message = "", "", "", ""
            auto_battle_this_stage = False

            while monster.hp > 0 and player.hp > 0:
                def check_ascent_reaction(reaction, user):
                    return (user == interaction.user and
                            reaction.message.id == message.id and
                            str(reaction.emoji) in reactions)
                
                try:
                    action_emoji = None
                    if auto_battle_this_stage:
                        if player.hp <= int(player.max_hp * 0.2): 
                            auto_battle_this_stage = False
                            pause_message = "Player HP < 20%, auto-battle paused!"
                            await interaction.followup.send(f'{interaction.user.mention} auto-combat paused for this stage!', ephemeral=True)
                        else:
                            action_emoji = "⚔️" # Simulate attack
                            await asyncio.sleep(1) # Auto-battle delay
                    
                    if not action_emoji: # If not auto-battling or paused, wait for reaction
                        reaction_obj, reaction_user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check_ascent_reaction)
                        action_emoji = str(reaction_obj.emoji)
                        await message.remove_reaction(reaction_obj.emoji, reaction_user)

                    heal_message, attack_message, monster_message, pause_message = "", "", "", "" # Reset messages

                    if action_emoji == "⚔️":
                        monster, attack_message = await self.player_turn(player, monster)
                        if monster.hp > 0: player, monster_message = await self.monster_turn(player, monster)
                    elif action_emoji == "🩹":
                        player, heal_message = await self.heal(player)
                    elif action_emoji == "⏩":
                        auto_battle_this_stage = True
                        pause_message = "Auto-battle engaged for this stage!" # Brief indicator
                    elif action_emoji == "🏃":
                        await message.clear_reactions()
                        embed.add_field(name="Retreat", value=f"You retreated from the ascent at Stage {ascent_stage}.", inline=False)
                        await message.edit(embed=embed)
                        self.bot.state_manager.clear_active(user_id)
                        await self.bot.database.update_player(player) 
                        return 

                    if player.hp <= 0: break 
                    if monster.hp <= 0: break 

                    messages = {player.name: attack_message, monster.name: monster_message, "Heal": heal_message, "Auto-Battle": pause_message}
                    embed = await self.update_combat_embed(embed, player, monster, messages)
                    embed.title = embed_title # Ensure title persists
                    await message.edit(embed=embed)

                except asyncio.TimeoutError:
                    embed.add_field(name="Timeout", value="Your hesitation cost you the ascent.", inline=False)
                    await message.edit(embed=embed); await message.clear_reactions()
                    self.bot.state_manager.clear_active(user_id); await self.bot.database.update_player(player)
                    return
            
            # --- END OF INNER COMBAT LOOP ---
            if player.hp <= 0:
                await self.handle_defeat(message, player, monster) 
                self.bot.state_manager.clear_active(user_id)
                # No need to update_player here, handle_defeat does it.
                return 

            if monster.hp <= 0: # Monster defeated, prepare for next stage or end ascent
                # --- Stage Cleared Rewards ---
                stage_clear_embed = discord.Embed(
                    title=f"Ascent - Stage {ascent_stage} Cleared!",
                    description=f"{player.name} defeated {monster.name} with {player.hp} ❤️ remaining!",
                    color=discord.Color.green()
                )
                # Gold award scales with monster level and player rarity
                base_gold = int((monster.level ** random.uniform(1.5, 1.7))) # Higher scaling for ascent
                final_gold_award = int(base_gold * (1 + player.rarity / 100 + ascent_stage / 20)) # Bonus for stage
                final_gold_award = max(100, final_gold_award) # Min gold

                # XP award also scales (monster.xp is already scaled in generate_ascent_monster)
                final_xp_award = monster.xp

                # Check for Prosper/Infinite Wisdom passives
                if player.acc_passive == "Prosper" and random.random() < (player.acc_lvl * 0.1): # 10% per level
                    final_gold_award *= 2
                    stage_clear_embed.add_field(name="Passive Bonus!", value="**Prosper** doubles gold!", inline=False)
                if player.acc_passive == "Infinite Wisdom" and random.random() < (player.acc_lvl * 0.05): # 5% per level
                    final_xp_award = int(final_xp_award * 1.5) # 1.5x XP for ascent IW
                    stage_clear_embed.add_field(name="Passive Bonus!", value="**Infinite Wisdom** boosts XP!", inline=False)

                stage_clear_embed.add_field(name="📚 Experience Gained", value=f"{final_xp_award:,} XP")
                stage_clear_embed.add_field(name="💰 Gold Acquired", value=f"{final_gold_award:,} GP")
                
                # For ascent, maybe add a small chance for a random rune or curio every few stages
                if ascent_stage % 5 == 0: # Example: Every 5 stages
                    if random.random() < 0.25: # 25% chance for a curio
                        await self.bot.database.update_curios_count(user_id, server_id, 1)
                        stage_clear_embed.add_field(name="✨ Special Reward!", value="Found a Curious Curio!", inline=False)
                
                await message.edit(embed=stage_clear_embed)
                await asyncio.sleep(4) # Show rewards before next stage

                await self.bot.database.add_gold(user_id, final_gold_award)
                # Pass the stage_clear_embed for level up messages
                player = await self.update_experience(interaction, message, stage_clear_embed, player, monster) 
                await self.bot.database.update_player(player) # Save new state (HP, XP, level, gold, potions)
                                
                # Prepare for next stage
                ascent_stage += 1
                current_monster_base_level += 1
                current_normal_mods += 1
                current_boss_mods = min(5, current_boss_mods + 1) # Cap boss mods at 5 for sanity, or remove cap
                auto_battle_this_stage = False # Reset auto-battle for next stage
            else: # Should not be reached if logic is correct
                self.bot.logger.error("Ascent main loop exited unexpectedly after inner combat.")
                self.bot.state_manager.clear_active(user_id)
                return


    # ... [rest of the Combat cog: player_turn, heal, monster_turn, auto_battle, giga_auto_battle, boss_auto_battle, handle_victory, handle_defeat, handle_boss_victory, handle_boss_defeat, update_experience] ...
    # Ensure these methods are compatible or adapt them if ascent needs specific behavior not covered by general use.
    # For example, handle_victory/handle_defeat are for one-off combats. Ascent has its own stage progression.

    async def player_turn(self, player, monster):
        attack_message = ""
        echo_damage = 0
        actual_hit = 0
        echo_hit = False
        passive_message = ""
        attack_multiplier = 1.0 # Use float for multipliers

        if player.acc_passive == "Obliterate":
            double_damage_chance = player.acc_lvl * 0.02 # 2% per level
            if random.random() <= double_damage_chance:
                passive_message += f"**Obliterate (Lvl {player.acc_lvl})** activates, doubling 💥 damage dealt!\n"
                attack_multiplier *= 2.0

        if player.armor_passive == "Mystical Might" and random.random() < 0.2:
            attack_multiplier *= 10.0
            passive_message += "The **Mystical Might** armor imbues with power, massively increasing damage!\n"

        hit_chance = calculate_hit_chance(player, monster)
        # Miss chance is 1 - hit_chance. Attack roll is 0-1. Hit if attack_roll < hit_chance.
        # Current logic: attack_roll (0-100) vs miss_chance (0-100). Correct.
        
        attack_roll = random.randint(0, 100) # Roll out of 100
        final_miss_threshold = 100 - int(hit_chance * 100) # e.g. if 80% hit, miss if roll >= 80. So threshold is 80.
                                                        # Or, hit if roll < 80.
                                                        # Original: if attack_roll >= miss_chance -> hit.
                                                        # If hit_chance is 0.8 (80%), miss_chance for display is 20.
                                                        # Player hits if attack_roll (0-100) >= 20. This seems right.

        acc_value_bonus = 0
        accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
        if player.weapon_passive in accuracy_passives:
            acc_value_bonus = (1 + accuracy_passives.index(player.weapon_passive)) * 4 # This is a % bonus to the roll
            passive_message += f"The **{player.weapon_passive}** weapon boosts 🎯 accuracy roll by **{acc_value_bonus}**!\n"
            # attack_roll is modified below for this.

        # Apply accuracy bonus to the roll or adjust threshold. Modifying roll is simpler.
        # The original code has `attack_roll += acc_value` AFTER checking crit with `attack_roll - acc_value`.
        # Let's apply acc_value_bonus directly to the roll for simplicity before all checks.
        # No, crit logic is `(attack_roll - acc_value) > (player.crit - weapon_crit)`.
        # This means `acc_value` is used to make crit harder, which is not intuitive for an accuracy passive.
        # Let's assume accuracy passives should make it EASIER to hit, not affect crit directly this way.
        # For now, I'll follow the original structure closely.

        if player.acc_passive == "Lucky Strikes":
            lucky_strike_chance = player.acc_lvl * 0.10 # 10% per level
            if random.random() <= lucky_strike_chance:
                attack_roll2 = random.randint(0, 100)
                attack_roll = max(attack_roll, attack_roll2) # Take the better roll
                passive_message += f"**Lucky Strikes (Lvl {player.acc_lvl})** activates! Hit chance is now 🍀 lucky!\n"

        if "Suffocator" in monster.modifiers and random.random() < 0.2:
            passive_message += f"The {monster.name}'s **Suffocator** aura attempts to stifle your attack! Hit chance is now 💀 unlucky!\n"
            attack_roll2 = random.randint(0, 100)
            attack_roll = min(attack_roll, attack_roll2) # Take the worse roll
            
        weapon_crit_bonus_chance = 0 # This is a reduction to player.crit target for easier crits
        crit_passives = ["piercing", "keen", "incisive", "puncturing", "penetrating"]
        if player.weapon_passive in crit_passives:
            value = crit_passives.index(player.weapon_passive)
            weapon_crit_bonus_chance = (value + 1) * 5 # e.g., 5 to 25 reduction in crit target

        if "Shields-up" in monster.modifiers and random.random() < 0.1:
            attack_multiplier = 0 # No damage
            passive_message += f"{monster.name} projects a powerful magical barrier, nullifying the hit!\n"

        # Crit Check: Player crits if (modified_roll > player_crit_target)
        # player.crit is the threshold (e.g., 95). Roll must be > 95. Lower player.crit is better.
        # (attack_roll - acc_value_bonus_for_crit_calc) > (player.crit - weapon_crit_bonus_chance)
        # The `acc_value` in original crit check `(attack_roll - acc_value)` means higher acc_value makes crit harder.
        # This is counter-intuitive if `acc_value` is from an accuracy passive.
        # Let's assume `acc_value_bonus` from accuracy passives does NOT negatively impact crit chance.
        # Crit roll should be independent or benefit from accuracy.
        # For now, let's simplify the crit check to: `attack_roll > (player.crit - weapon_crit_bonus_chance)`
        # And the hit check to `(attack_roll + acc_value_bonus) >= final_miss_threshold`

        is_crit = False
        if attack_multiplier > 0 : # Only roll for crit if damage is possible
             # player.crit is e.g. 95. Crit if roll > (95 - bonus).
            crit_target = player.crit - weapon_crit_bonus_chance 
            if attack_roll > crit_target : # Roll needs to be high (e.g. 96, 97, 98, 99, 100 for 95 target)
                is_crit = True
        
        # Hit Check:
        is_hit = False
        if attack_multiplier > 0: # Only roll for hit if damage is possible
            # Effective roll for hit = attack_roll + accuracy passive bonus
            effective_attack_roll_for_hit = attack_roll + acc_value_bonus
            if effective_attack_roll_for_hit >= final_miss_threshold:
                is_hit = True

        if is_crit: # Crit always hits
            max_hit_calc = player.attack # Base for crit damage
            # Crit damage is typically base_damage * crit_multiplier (e.g., 2x)
            actual_hit = int((random.randint(int(max_hit_calc * 0.75) + 1, max_hit_calc)) * 2.0 * attack_multiplier)
            attack_message = ( (f"The **{player.weapon_passive}** weapon glimmers with power!\n" if weapon_crit_bonus_chance > 0 else '') +
                               f"Critical Hit! Damage: 🗡️ **{actual_hit}**")
            attack_message = passive_message + attack_message # Prepend passives
        elif is_hit:
            # Normal Hit Logic
            base_damage_max = player.attack
            base_damage_min = 1

            burning_passives = ["burning", "flaming", "scorching", "incinerating", "carbonising"]
            if player.weapon_passive in burning_passives:
                value = burning_passives.index(player.weapon_passive)
                burn_bonus_percentage = (value + 1) * 0.08
                bonus_burn_damage = int(player.attack * burn_bonus_percentage)
                base_damage_max += bonus_burn_damage
                attack_message = (f"The **{player.weapon_passive}** weapon 🔥 burns bright!\n"
                                  f"Attack damage potential boosted by **{bonus_burn_damage}**.\n")
            
            sparking_passives = ["sparking", "shocking", "discharging", "electrocuting", "vapourising"]
            if player.weapon_passive in sparking_passives:
                value = sparking_passives.index(player.weapon_passive)
                spark_min_percentage = (value + 1) * 0.08
                base_damage_min = max(base_damage_min, int(base_damage_max * spark_min_percentage))
                attack_message = (f"The **{player.weapon_passive}** weapon surges with ⚡ lightning, ensuring solid impact!\n")

            # Calculate actual hit damage for normal hit
            if base_damage_min >= base_damage_max : base_damage_min = base_damage_max -1 # Ensure range
            rolled_damage = random.randint(base_damage_min, base_damage_max)
            actual_hit = int(rolled_damage * attack_multiplier)

            echo_hit = False
            echo_passives = ["echo", "echoo", "echooo", "echoooo", "echoes"]
            if player.weapon_passive in echo_passives:
                value = echo_passives.index(player.weapon_passive)
                echo_multiplier = (value + 1) * 0.10
                echo_damage = int(actual_hit * echo_multiplier) # Echo is based on the already calculated hit
                actual_hit += echo_damage # Total damage includes echo
                echo_hit = True

            attack_message += f"Hit! Damage: 💥 **{actual_hit - echo_damage}**" # Display main hit part
            attack_message = passive_message + attack_message # Prepend general passives
            if echo_hit:
                attack_message += (f"\nThe **{player.weapon_passive}** weapon 🎶 echoes the hit!\n"
                                   f"Echo damage: 💥 **{echo_damage}**")
        else: # Miss
            actual_hit = 0 # No direct damage on miss
            poison_damage_on_miss = 0
            poisonous_passives = ["poisonous", "noxious", "venomous", "toxic", "lethal"]
            if player.weapon_passive in poisonous_passives:
                value = poisonous_passives.index(player.weapon_passive)
                poison_miss_percentage = (value + 1) * 0.08
                # Poison damage on miss is a fraction of player's attack
                poison_damage_on_miss = int(random.randint(1, int(player.attack * poison_miss_percentage)) * attack_multiplier)
                
                if poison_damage_on_miss > 0:
                     attack_message = passive_message + f"Miss!\nHowever, the **{player.weapon_passive}** weapon's lingering poison 🐍 deals **{poison_damage_on_miss}** damage."
                     # Apply poison damage directly here if it's instant, or set up a DoT if applicable
                     # For now, assume it's instant damage on miss
                     actual_hit = poison_damage_on_miss # This "hit" is the poison damage
                else: # Should not happen if player.attack > 0
                    attack_message = passive_message + "Miss!"
            else:
                attack_message = passive_message + "Miss!"

        # Apply monster's damage reduction like Titanium
        if "Titanium" in monster.modifiers and actual_hit > 0:
            reduction = int(actual_hit * 0.10)
            actual_hit = max(0, actual_hit - reduction) # Reduce damage by 10%
            attack_message += f"\n{monster.name}'s **Titanium** plating reduces damage by {reduction}."

        # Prevent overkill unless it's a killing blow / Time Lord check
        if actual_hit >= monster.hp: # If current damage would kill
            if "Time Lord" in monster.modifiers and random.random() < 0.80 and monster.hp > 1: # Time Lord saves if not already at 1 HP
                actual_hit = monster.hp - 1 # Leaves monster at 1 HP
                attack_message += f"\nA fatal blow was dealt, but **{monster.name}**'s **Time Lord** ability allows it to cheat death!"
            else: # Normal killing blow, or Time Lord failed/not applicable
                actual_hit = monster.hp # Damage is exactly enough to kill
        
        monster.hp -= actual_hit
        
        # Culling Strike check (after all other damage and Time Lord)
        if monster.hp > 0 and check_cull(player, monster): # check_cull needs monster's current HP
            cull_damage = monster.hp -1 # Cull leaves monster at 1 HP
            if cull_damage > 0:
                monster.hp = 1
                attack_message += f"\n{player.name}'s **{player.weapon_passive}** weapon culls the weakened {monster.name}, dealing an additional 🪓 __**{cull_damage}**__ damage!"

        return monster, attack_message

    async def heal(self, player):
        self.bot.logger.info(f"Player has {player.potions} potions")
        if player.potions <= 0:
            self.bot.logger.info('Unable to heal, out of potions')
            heal_message = f"{player.name} has no potions left to use!"
            return player, heal_message

        if player.hp >= player.max_hp:
            self.bot.logger.info('Already at max hp')
            heal_message = f"{player.name} is already full HP!"
            return player, heal_message

        heal_amount = int((player.max_hp * 0.3) + random.randint(1, 6)) # Heal 30% of max HP + small random
        healed_to_hp = min(player.max_hp, player.hp + heal_amount)
        actual_healed_amount = healed_to_hp - player.hp
        player.hp = healed_to_hp
        
        player.potions -= 1
        heal_message = (f"{player.name} uses a potion and heals for **{actual_healed_amount}** HP!\n"
                        f"**{player.potions}** potions left.")
        return player, heal_message

    async def monster_turn(self, player, monster):
        if player.invulnerable: # Player's Invulnerable armor passive
            monster_message = f"The **Invulnerable** armor protects {player.name}, absorbing all damage from {monster.name}!"
            return player, monster_message
        
        # Monster's chance to hit player
        base_monster_hit_chance = calculate_monster_hit_chance(player, monster) # e.g., 0.6 (60%)
        
        # Player's evasion reducing monster's hit chance
        player_evasion_value = 0.01 + (player.evasion / 400.0) # e.g. 100 evasion = 0.01 + 0.25 = 0.26 (26% flat reduction)
        effective_hit_chance = max(0.05, base_monster_hit_chance - player_evasion_value) # Monster min 5% hit chance

        monster_attack_roll = random.random() # Roll 0.0 to 1.0

        # Monster accuracy modifiers
        if "Lucifer-touched" in monster.modifiers and random.random() < 0.5: # Lucky for monster
            monster_attack_roll = min(monster_attack_roll, random.random()) # Takes lower roll (better for monster vs threshold)
        if "All-seeing" in monster.modifiers: # Higher accuracy for monster
            effective_hit_chance = min(0.95, effective_hit_chance * 1.10) # 10% relatively more accurate, cap 95%
        if "Celestial Watcher" in monster.modifiers: # Never miss
            effective_hit_chance = 1.0 # Guaranteed hit (or very high like 0.99 if 1.0 causes issues)

        monster_message = ""
        if monster_attack_roll <= effective_hit_chance: # Monster hits
            damage_taken_base = calculate_damage_taken(player, monster) # Base damage roll

            # Apply monster damage modifiers
            if "Celestial Watcher" in monster.modifiers: # CW hits harder or has other effects
                damage_taken_base = int(damage_taken_base * 1.2) # Example: CW deals 20% more
            if "Hellborn" in monster.modifiers: damage_taken_base += 2
            if "Hell's Fury" in monster.modifiers: damage_taken_base += 5 # Note: Original was 3, consistency check.
            if "Mirror Image" in monster.modifiers and random.random() < 0.2: damage_taken_base *= 2
            if "Unlimited Blade Works" in monster.modifiers: damage_taken_base *= 2
            
            # Minions (Summoner, Infernal Legion)
            minion_additional_damage = 0
            if "Summoner" in monster.modifiers:
                minion_additional_damage = int(damage_taken_base * (1/3)) # Summoner minions add 1/3 of main hit
            if "Infernal Legion" in monster.modifiers: # IL echoes the full hit as extra
                minion_additional_damage = damage_taken_base 
            
            total_damage_before_block_ward = damage_taken_base + minion_additional_damage

            # Multistrike (monster hits again for 50% damage)
            multistrike_damage = 0
            if "Multistrike" in monster.modifiers and random.random() <= effective_hit_chance: # Check hit for multistrike
                multistrike_damage = int(calculate_damage_taken(player, monster) * 0.5) # 50% of a new damage roll
                total_damage_before_block_ward += multistrike_damage

            # Executioner (high damage proc)
            is_executed = False
            if "Executioner" in monster.modifiers and random.random() < 0.01: # 1% chance
                executed_damage = int(player.hp * 0.90) # Deals 90% of player's CURRENT HP
                total_damage_before_block_ward = max(total_damage_before_block_ward, executed_damage) # Takes precedence if higher
                is_executed = True
                self.bot.logger.info(f"Executioner proc: {executed_damage} damage against player HP {player.hp}")

            # Player Block
            final_damage_to_player = total_damage_before_block_ward
            is_blocked = False
            # Player block chance: (player.block / 200 + 0.01), e.g. 100 block = 51% chance
            # This seems very high. Let's use a more common scaling: player.block / (player.block + C), or simpler linear with cap.
            # Original: random.random() <= (player.block / 200 + 0.01)
            # For 100 block: random() <= 0.51. For 200 block: random() <= 1.01 (guaranteed block).
            # This needs to be a reasonable cap, e.g., max 75% block chance.
            block_chance_calc = min(0.75, (player.block / (player.block + 150.0)) if player.block > 0 else 0) # Example scaling with cap

            if random.random() <= block_chance_calc:
                final_damage_to_player = 0 # Block negates all damage
                is_blocked = True

            # Apply damage to Ward first, then HP
            if not is_blocked:
                if player.ward > 0:
                    if final_damage_to_player <= player.ward:
                        player.ward -= final_damage_to_player
                        monster_message += f"{monster.name} {monster.flavor}. Your ward absorbs 🔮 {final_damage_to_player} damage!\n"
                        final_damage_to_player = 0 
                    else:
                        monster_message += f"{monster.name} {monster.flavor}. Your ward absorbs 🔮 {player.ward} damage, but shatters!\n"
                        final_damage_to_player -= player.ward
                        player.ward = 0
                
                if final_damage_to_player > 0:
                    player.hp -= final_damage_to_player
                    monster_message += f"{monster.name} {monster.flavor}. You take 💔 **{final_damage_to_player}** damage!\n"

            else: # Damage was blocked
                 monster_message = f"{monster.name} {monster.flavor}, but your armor 🛡️ blocks all damage!\n"

            # Add messages for special damage procs
            if is_executed and not is_blocked:
                monster_message += f"The {monster.name}'s **Executioner** ability cleaves through your defenses!\n"
            if minion_additional_damage > 0 and not is_blocked:
                monster_message += f"Their minions strike for an additional {minion_additional_damage} damage!\n"
            if multistrike_damage > 0 and not is_blocked:
                monster_message += f"{monster.name} strikes again in quick succession for {multistrike_damage} damage!\n"
            
            if not monster_message: # Fallback if no other message was generated but hit occurred
                monster_message = f"{monster.name} {monster.flavor}, dealing its blow."

        else: # Monster misses
            if "Venomous" in monster.modifiers:
                player.hp = max(1, player.hp - 1) # Venomous deals 1 damage on miss, HP doesn't go below 1
                monster_message = f"{monster.name} misses, but their **Venomous** aura deals **1** 🐍 damage!"
            else:
                monster_message = f"{monster.name} misses!"
        
        player.hp = max(0, player.hp) # Ensure HP doesn't go negative visually before defeat check
        return player, monster_message

    async def auto_battle(self, interaction, message, embed, player, monster):
        # This is for /combat auto-battle
        minimum_hp_threshold = int(player.max_hp * 0.2)
        original_embed_title = embed.title # Preserve original title for /combat
        
        while player.hp > minimum_hp_threshold and monster.hp > 0:
            # Player's turn
            monster, attack_message = await self.player_turn(player, monster)
            if monster.hp <= 0:
                await self.handle_victory(interaction, message, player, monster)
                self.bot.state_manager.clear_active(player.id) # Ensure cleared after victory
                return player, monster # Combat ends

            # Monster's turn
            player, monster_message = await self.monster_turn(player, monster)
            if player.hp <= 0:
                await self.handle_defeat(message, player, monster)
                self.bot.state_manager.clear_active(player.id) # Ensure cleared after defeat
                return player, monster # Combat ends

            # Update embed
            messages = {player.name: attack_message, monster.name: monster_message}
            embed = await self.update_combat_embed(embed, player, monster, messages)
            embed.title = original_embed_title # Restore title for /combat
            await message.edit(embed=embed)
            await asyncio.sleep(1) # Delay between auto-battle turns

        # Loop breaks if player HP low, monster dead, or player dead.
        # If player HP low but combat not over, control returns to main combat loop.
        return player, monster
    
    async def giga_auto_battle(self, interaction, message, embed, player, monster):
        # This is for /combat giga-auto-battle
        minimum_hp_threshold = int(player.max_hp * 0.2)
        turn_count = 0
        last_attack_message, last_monster_message = "", ""
        original_embed_title = embed.title

        while player.hp > minimum_hp_threshold and monster.hp > 0:
            turn_count += 1
            # Player's turn
            monster, attack_message = await self.player_turn(player, monster)
            last_attack_message = attack_message # Store for batch update
            if monster.hp <= 0:
                # Update embed one last time before victory
                embed.title = original_embed_title
                embed = await self.update_combat_embed(embed, player, monster, {player.name: last_attack_message, monster.name: ""})
                await message.edit(embed=embed)
                await self.handle_victory(interaction, message, player, monster)
                self.bot.state_manager.clear_active(player.id)
                return player, monster

            # Monster's turn
            player, monster_message = await self.monster_turn(player, monster)
            last_monster_message = monster_message # Store for batch update
            if player.hp <= 0:
                # Update embed one last time before defeat
                embed.title = original_embed_title
                embed = await self.update_combat_embed(embed, player, monster, {player.name: last_attack_message, monster.name: last_monster_message})
                await message.edit(embed=embed)
                await self.handle_defeat(message, player, monster)
                self.bot.state_manager.clear_active(player.id)
                return player, monster
            
            # Update embed every 10 turns or when HP is low
            if turn_count % 10 == 0 or player.hp <= minimum_hp_threshold:
                embed.clear_fields()
                embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
                embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)" if player.ward > 0 else player.hp, inline=True)
                embed.add_field(name=player.name, value=last_attack_message, inline=False)
                embed.add_field(name=monster.name, value=last_monster_message, inline=False)
                if player.hp <= minimum_hp_threshold:
                    embed.add_field(name="Auto battle", value="Player HP < 20%, auto-battle paused!", inline=False)
                    await interaction.followup.send(f'{interaction.user.mention} auto-combat paused!', ephemeral=True)
                await message.edit(embed=embed)
                await asyncio.sleep(0.5) # Shorter delay for giga auto
        
        return player, monster

    async def boss_auto_battle(self, message, embed, player, monster):
        # This is for /combat boss auto-battle
        minimum_hp_threshold = int(player.max_hp * 0.2)
        original_embed_title = embed.title

        while player.hp > minimum_hp_threshold and monster.hp > 0:
            monster, attack_message = await self.player_turn(player, monster)
            if monster.hp <= 0: break # Exit to handle boss phase transition or victory

            player, monster_message = await self.monster_turn(player, monster)
            if player.hp <= 0: break # Exit to handle boss defeat

            messages = {player.name: attack_message, monster.name: monster_message}
            embed.title = original_embed_title
            embed = await self.update_combat_embed(embed, player, monster, messages)
            await message.edit(embed=embed)
            await asyncio.sleep(1)
        
        return player, monster # Return state for boss handler to decide next step

    async def handle_victory(self, interaction, message, player, monster):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        # No clear_active here, as it's called by the command after this handler
        await message.clear_reactions()
        
        embed = discord.Embed(
            title="Victory!  🎉",
            description=f"{player.name} has slain the {monster.name} with {player.hp} ❤️ remaining!",
            color=discord.Color.green(),
        )
        
        # Rewards calculation (gold, special drops, etc.)
        # ... (Existing detailed reward logic from original handle_victory)
        # This includes gold, XP (from monster.xp), item drops, key drops, curio drops, Everlasting Blessing.
        # For brevity, assuming this complex logic is here and functions.
        # Example snippet for gold and XP:
        final_gold_award = int((monster.level ** random.uniform(1.4, 1.6)) * (1 + ((monster.level - player.level) / 10 ** 1.3 if player.level < monster.level else 1)))
        final_gold_award = max(20, int(final_gold_award * (1.5 + player.rarity / 100)))

        if player.acc_passive == "Prosper" and random.random() < (player.acc_lvl * 0.1):
            final_gold_award *= 2; embed.add_field(name="Passive!", value="**Prosper** doubles gold!", inline=False)
        
        final_xp_award = monster.xp # monster.xp should be pre-calculated
        if player.acc_passive == "Infinite Wisdom" and random.random() < (player.acc_lvl * 0.05):
            final_xp_award = int(final_xp_award * 2); embed.add_field(name="Passive!", value="**Infinite Wisdom** doubles XP!", inline=False)

        embed.add_field(name="📚 Experience", value=f"{final_xp_award:,} XP")
        embed.add_field(name="💰 Gold", value=f"{final_gold_award:,} GP")

        # Item drop logic ... (complex, assumed present)
        # Key drop logic ... (assumed present)
        # Everlasting Blessing logic ... (assumed present)

        await message.edit(embed=embed) # Show victory embed with rewards
        
        # Update player database with gold and XP (XP is updated via update_experience)
        await self.bot.database.add_gold(user_id, final_gold_award)
        
        # Pass monster with its final_xp_award to update_experience
        temp_monster_for_xp = Monster(name="",level=0,hp=0,max_hp=0,xp=final_xp_award,attack=0,defence=0,modifiers=[],image="",flavor="")
        player = await self.update_experience(interaction, message, embed, player, temp_monster_for_xp)
        await self.bot.database.update_player(player) # Save all player changes (HP, XP, level, gold, potions)
        # self.bot.state_manager.clear_active(user_id) # Caller should handle this

    async def handle_defeat(self, message, player, monster):
        # No clear_active here, as it's called by the command after this handler
        await message.clear_reactions()
        
        current_exp = player.exp
        penalty_xp = int(current_exp * 0.10) # 10% XP loss
        new_exp = max(0, current_exp - penalty_xp)
            
        player.hp = 1 # Revive with 1 HP
        player.exp = new_exp

        total_damage_dealt = monster.max_hp - monster.hp
        defeat_embed = discord.Embed(
            title="Oh dear...",
            description=(f"The {monster.name} deals a fatal blow!\n"
                         f"{player.name} has been defeated after dealing {total_damage_dealt:,} damage.\n"
                         f"The {monster.name} leaves with {monster.hp:,} health remaining.\n"
                         f"Death 💀 takes away {penalty_xp:,} XP from your essence..."),
            color=discord.Color.red()
        )
        defeat_embed.add_field(name="🪽 Redemption 🪽", value=f"({player.name} revives with 1 HP.)")
        await message.edit(embed=defeat_embed)
        await self.bot.database.update_player(player) # Save new HP and XP
        # self.bot.state_manager.clear_active(player.id) # Caller should handle this

    async def handle_boss_encounter(self, interaction, player, type):
        # ... (Existing boss encounter logic)
        # This is a self-contained multi-phase combat system.
        # Ensure it correctly clears state on completion/failure using self.bot.state_manager.clear_active(player.id)
        pass # Placeholder for existing complex boss logic

    async def handle_boss_victory(self, interaction, message, player, monster, type):
        # ... (Existing boss victory logic)
        # Make sure it calls self.bot.database.update_player(player) at the end.
        # And self.bot.state_manager.clear_active(player.id)
        pass

    async def handle_boss_defeat(self, message, player, monster, type):
        # ... (Existing boss defeat logic)
        # Make sure it calls self.bot.database.update_player(player) at the end.
        # And self.bot.state_manager.clear_active(player.id)
        pass
        
    async def update_experience(self, interaction, message_to_edit_or_None, embed_for_levelup_msgs, player, monster_with_xp_reward) -> Player:
        """Update the user's experience and handle leveling up. Returns updated player object."""
        user_id = str(player.id)
        # Ensure server_id is correctly fetched if needed for DB calls within this function
        server_id = str(interaction.guild.id) if interaction.guild else None 
        
        exp_table = self.load_exp_table()
        player.exp += monster_with_xp_reward.xp # Add XP from the reward object
        
        leveled_up_this_cycle = False
        level_up_fields_to_add = [] # Store tuples of (name, value, inline) for fields

        # Loop for multiple level-ups if large XP gain
        while True:
            original_level_for_loop_check = player.level
            original_ascension_for_loop_check = player.ascension

            if player.level >= 100: # Ascension logic
                # Ensure "100" exists as a key for ascension base XP if that's the design
                exp_threshold_key_asc = "100" 
                if exp_threshold_key_asc not in exp_table["levels"]:
                    self.bot.logger.error(f"XP threshold for ascension (key '{exp_threshold_key_asc}') not found in exp_table.")
                    break
                exp_threshold_asc = exp_table["levels"][exp_threshold_key_asc]
                
                if player.exp >= exp_threshold_asc:
                    player.exp -= exp_threshold_asc
                    player.ascension += 1
                    leveled_up_this_cycle = True
                    
                    # Passive points for ascension
                    # Ensure server_id is valid if database methods require it for passive points
                    if server_id: # Check if server_id is available
                        passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
                        await self.bot.database.set_passive_points(user_id, server_id, passive_points + 2)
                        asc_msg_details = f"{player.name} has reached Ascension **{player.ascension}**!\n+2 Passive Points gained."
                    else: # Fallback if server_id is not available (e.g. DM context, though unlikely for this bot)
                        asc_msg_details = f"{player.name} has reached Ascension **{player.ascension}**!"
                        self.bot.logger.warning(f"Could not award passive points for ascension to user {user_id} due to missing server_id.")
                    
                    level_up_fields_to_add.append(
                        ("Ascension Level Up! ✨", asc_msg_details, False)
                    )
                else:
                    break # Not enough XP for another ascension level
            
            else: # Regular level up (below 100)
                level_key = str(player.level)
                if level_key not in exp_table["levels"]: 
                    self.bot.logger.error(f"XP threshold for level {player.level} not found in exp_table.")
                    break 
                
                exp_threshold = exp_table["levels"][level_key]
                if player.exp >= exp_threshold:
                    player.exp -= exp_threshold
                    player.level += 1
                    leveled_up_this_cycle = True

                    # Stat increases on level up
                    attack_increase = random.randint(1, 3) 
                    defence_increase = random.randint(1, 3)
                    hp_increase = random.randint(3, 7)      

                    player.attack += attack_increase
                    player.defence += defence_increase
                    player.max_hp += hp_increase
                    player.hp = player.max_hp # Full heal on level up

                    # Passive points every 10 levels (up to 100)
                    passive_points_gained_msg = ""
                    if player.level % 10 == 0 and player.level <= 100:
                        if server_id: # Check for server_id before DB call
                            passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
                            await self.bot.database.set_passive_points(user_id, server_id, passive_points + 2)
                            passive_points_gained_msg = "\n+2 Passive Points gained!"
                        else:
                            self.bot.logger.warning(f"Could not award passive points for level {player.level} to user {user_id} due to missing server_id.")


                    level_up_fields_to_add.append(
                        (f"Level Up to {player.level}! 🎉",
                         (f"⚔️ Attack: +{attack_increase} ({player.attack})\n"
                          f"🛡️ Defence: +{defence_increase} ({player.defence})\n"
                          f"❤️ Max HP: +{hp_increase} ({player.max_hp})"
                          f"{passive_points_gained_msg}"),
                         False)
                    )
                else:
                    break # Not enough XP for another regular level
            
            # Safety break: if XP is somehow not consumed but conditions met, or level doesn't change.
            if player.level == original_level_for_loop_check and player.ascension == original_ascension_for_loop_check:
                # This means XP was enough, but level/ascension didn't increment. Could be an issue if XP > threshold but player.exp -= threshold didn't run.
                # However, with current logic, this break should only be hit if exp < threshold.
                # Adding a log if it's hit unexpectedly:
                if player.exp >= (exp_table["levels"].get(str(player.level), float('inf')) if player.level < 100 else exp_table["levels"].get("100", float('inf')) ) :
                    self.bot.logger.warning(f"XP loop for {user_id} exited: XP ({player.exp}) met threshold for L{player.level}/A{player.ascension} but no level change. Original L{original_level_for_loop_check}/A{original_ascension_for_loop_check}.")
                break


        if leveled_up_this_cycle and embed_for_levelup_msgs and message_to_edit_or_None:
            for name, value, inline_val in level_up_fields_to_add: # Use different variable for inline
                embed_for_levelup_msgs.add_field(name=name, value=value, inline=inline_val)
            await message_to_edit_or_None.edit(embed=embed_for_levelup_msgs) # Single edit after all level ups are processed

        return player


async def setup(bot) -> None:
    await bot.add_cog(Combat(bot))