import random
import discord
from discord.ext import commands
from discord.ext.tasks import asyncio
from discord import app_commands, Interaction, Message
from datetime import datetime, timedelta
from core.models import Player, Monster, Weapon, Accessory, Armor
from core.loot import generate_weapon, generate_armor, generate_accessory
from core.combat_calcs import calculate_hit_chance, calculate_monster_hit_chance, calculate_damage_taken, check_cull
from core.gen_mob import get_modifier_description, generate_encounter, generate_boss
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
        embed.clear_fields()

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
            )
        }
        
        for modifier in monster.modifiers:
            if modifier in modifier_effects:
                modifier_effects[modifier](player, monster)
                self.bot.logger.info(f'Applied {modifier}')


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
            crit=95,  # Base crit 5% crit chance (100-5)
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
            
            player.crit -= equipped_accessory[8]
            player.acc_lvl = equipped_accessory[12]
            self.bot.logger.info(f'Accessory: ATK {equipped_accessory[4]}, DEF {equipped_accessory[5]}, RAR {equipped_accessory[6]}, Crit Bonus {equipped_accessory[8]}%, Ward {accessory_ward_percentage}%, Passive: {player.acc_passive} (Lvl {player.acc_lvl})')
            
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

        last_combat_time_str = existing_user[24]
        if last_combat_time_str:
            try:
                last_combat_time_dt = datetime.fromisoformat(last_combat_time_str)
                time_since_combat = datetime.now() - last_combat_time_dt
                if time_since_combat < self.COMBAT_COOLDOWN_DURATION:
                    remaining_cooldown = self.COMBAT_COOLDOWN_DURATION - time_since_combat
                    await interaction.response.send_message(
                        f"Please slow down. Try again in {(remaining_cooldown.seconds // 60) % 60} minute(s) "
                        f"{(remaining_cooldown.seconds % 60)} second(s).",
                        ephemeral=True
                    )
                    return
            except ValueError:
                self.bot.logger.warning(f"Invalid datetime format for last_combat_time for user {user_id}: {last_combat_time_str}")
        
        await self.bot.database.update_combat_time(user_id)
        self.bot.state_manager.set_active(user_id, "combat")
        
        player = await self._initialize_player_for_combat(user_id, existing_user)

        # Check for Door of Ascension / Infernal Door
        is_boss_encounter = False
        boss_type = '' # aphrodite or lucifer
        door_chance_roll = random.random()
        aphrodite_eligible = player.level >= 20 and existing_user[25] > 0 and existing_user[26] > 0
        lucifer_eligible = player.level >= 20 and existing_user[28] >= 5
        neet_eligible = player.level >= 40 and existing_user[29] >= 3

        if aphrodite_eligible and door_chance_roll < 0.2: # Reduced chance for example
            is_heaven_door = True
            embed = discord.Embed(
                title="Door of Ascension",
                description="Your angelic and draconic keys tremble with anticipation, "
                            "do you wish to challenge the heavens?",
                color=0x00FF00,
            )
            embed.set_image(url="https://i.imgur.com/PXOhTbX.png")
                                            
            await interaction.response.send_message(embed=embed)
            message = await interaction.original_response()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def check(reaction, user):
                return (user == interaction.user and
                        reaction.message.id == message.id and
                        str(reaction.emoji) in ["✅", "❌"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                await message.clear_reactions()
                if str(reaction.emoji) == "✅":
                    is_boss_encounter = True
                    await self.bot.database.add_dragon_key(user_id, -1)
                    await self.bot.database.add_angel_key(user_id, -1)
                    boss_type = 'aphrodite'
                else:
                    pass
            except asyncio.TimeoutError: 
                await message.clear_reactions()                      
                await message.edit(embed=discord.Embed(
                    title="Door of Ascension",
                    description="You hesitated, and the opportunity fades.",
                    color=0xFF0000))
                self.bot.state_manager.clear_active(user_id)
                return
        elif lucifer_eligible and 0.2 < door_chance_roll < 0.4: # Reduced chance
            is_hell_door = True
            embed = discord.Embed(
                title="Door of the Infernal",
                description="Your soul cores tremble with anticipation, "
                            "do you wish to consume 5 to challenge the depths below?",
                color=0x00FF00,
            )
            embed.set_image(url="https://i.imgur.com/bWMAksf.png")
                                            
            await interaction.response.send_message(embed=embed)
            message = await interaction.original_response()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def check(reaction, user):
                return (user == interaction.user and
                        reaction.message.id == message.id and
                        str(reaction.emoji) in ["✅", "❌"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                await message.clear_reactions()
                if str(reaction.emoji) == "✅":
                    is_boss_encounter = True
                    await self.bot.database.add_soul_cores(user_id, -5)
                    boss_type = 'lucifer'
                else:
                    pass  # Proceed with normal combat
            except asyncio.TimeoutError: 
                await message.clear_reactions()                      
                await message.edit(embed=discord.Embed(
                    title="Door of the Infernal",
                    description="You hesitated, and the opportunity fades.",
                    color=0xFF0000))
                self.bot.state_manager.clear_active(user_id)
                return
        elif neet_eligible and 0.4 < door_chance_roll < 0.6: # Reduced chance
            is_neet_door = True
            embed = discord.Embed(
                title="Sad anime kid",
                description=f"You walk past a sad anime kid who looked like he just got dumped by his girlfriend.\n"
                            "The void fragments in your inventory suddenly start trembling with anticipation.",
                color=0x00FF00,
            )
            embed.set_image(url="https://i.imgur.com/6f9OJ4s.jpeg")
                                            
            await interaction.response.send_message(embed=embed)
            message = await interaction.original_response()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def check(reaction, user):
                return (user == interaction.user and
                        reaction.message.id == message.id and
                        str(reaction.emoji) in ["✅", "❌"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                await message.clear_reactions()
                if str(reaction.emoji) == "✅":
                    is_boss_encounter = True
                    await self.bot.database.add_soul_cores(user_id, -5)
                    boss_type = 'NEET'
                else:
                    pass  # Proceed with normal combat
            except asyncio.TimeoutError: 
                await message.clear_reactions()                      
                await message.edit(embed=discord.Embed(
                    title="Sad anime kid",
                    description="You hesitated, and leave the sad anime kid in the rain.",
                    color=0xFF0000))
                self.bot.state_manager.clear_active(user_id)
                return

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

        items = await self.bot.database.fetch_user_weapons(user_id)
        accs = await self.bot.database.fetch_user_accessories(user_id)
        arms = await self.bot.database.fetch_user_armors(user_id)
        if len(items) > 60:
            embed.add_field(name="🚫 WARNING 🚫", value="Weapon pouch is full! Weapons can't drop.", inline=False)
        if len(accs) > 60:
            embed.add_field(name="🚫 WARNING 🚫", value="Accessory pouch is full! Accessories can't drop.", inline=False)
        if len(arms) > 60:
            embed.add_field(name="🚫 WARNING 🚫", value="Armor pouch is full! Armor can't drop.", inline=False)


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
                    print('Won encounter')
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
        attack_roll = random.randint(0, 100) # Roll out of 100
        final_miss_threshold = 100 - int(hit_chance * 100)

        acc_value_bonus = 0
        accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
        if player.weapon_passive in accuracy_passives:
            acc_value_bonus = (1 + accuracy_passives.index(player.weapon_passive)) * 4 # This is a % bonus to the roll
            passive_message += f"The **{player.weapon_passive}** weapon boosts 🎯 accuracy roll by **{acc_value_bonus}**!\n"

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
            actual_hit = int((random.randint(int(max_hit_calc * 0.5) + 1, max_hit_calc)) * 2.0 * attack_multiplier)
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
            block_chance_calc = min(0.75, (player.block / 200) if player.block > 0 else 0)

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
                return player, monster

            # Monster's turn
            player, monster_message = await self.monster_turn(player, monster)
            last_monster_message = monster_message # Store for batch update
            if player.hp <= 0:
                return player, monster
            
            if turn_count % 10 == 0 or player.hp <= minimum_hp_threshold : # Update embed every 10 turns or if HP low
                messages = {player.name: last_attack_message, monster.name: last_monster_message}
                embed.title = original_embed_title
                embed = await self.update_combat_embed(embed, player, monster, messages)
                if player.hp <= minimum_hp_threshold and monster.hp > 0: # Add pause message if relevant
                     embed.add_field(name="Giga Auto-Battle", value="Player HP < 20%, auto-battle paused!", inline=False)
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
        self.bot.state_manager.clear_active(user_id)
        await message.clear_reactions()
        embed = discord.Embed(
            title="Victory!  🎉",
            description=f"{player.name} has slain the {monster.name} with {player.hp} ❤️ remaining!",
            color=0x00FF00,
        )
        rare_monsters = ["Treasure Chest", 
                        "Random Korean Lady", 
                        "KPOP STAR", 
                        "Loot Goblin", 
                        "Yggdrasil",
                        "Capybara Sauna"]
        
        special_drop = len(monster.modifiers) / 100
        if monster.name in rare_monsters:
            special_drop = 0.05
            reward_scale = int(player.level / 10)
        else:
            reward_scale = (monster.level - player.level) / 10

        rarity = player.rarity
        # Level-scaled drop chance: base 10%, boosted by rarity
        base_drop_chance = 10
        level_bonus = int(0.2 * (100 - player.level))
        drop_chance = base_drop_chance + (player.rarity / 10) + level_bonus
        drop_roll = random.randint(1, 100)
        self.bot.logger.info(f"Drop roll: {drop_roll}, Drop chance: {drop_chance}, Rarity: {rarity}")

        gold_award = int((monster.level ** random.uniform(1.4, 1.6)) * (1 + (reward_scale ** 1.3)))
        if player.rarity > 0:
            final_gold_award = int(gold_award * (1.5 + rarity / 100))
        else:
            final_gold_award = gold_award
        final_gold_award += 20

        if player.acc_passive == "Prosper":
            double_gold_chance = player.acc_lvl * 10
            if random.randint(1, 100) <= double_gold_chance:
                final_gold_award *= 2
                embed.add_field(name="Accessory Passive",
                                value=f"The accessory's **Prosper ({player.acc_lvl})** activates, granting double gold!",
                                inline=False)
        elif player.acc_passive == "Infinite Wisdom":
            double_exp_chance = player.acc_lvl * 5 / 100
            if random.random() <= double_exp_chance:
                monster.xp *= 2
                embed.add_field(name="Accessory Passive",
                                value=f"The accessory's **Infinite Wisdom ({player.acc_lvl})** activates, "
                                    f"granting double experience!",
                                inline=False)
        embed.add_field(name="📚 Experience", value=f"{monster.xp:,} XP")
        embed.add_field(name="💰 Gold", value=f"{final_gold_award:,} GP")

        items = await self.bot.database.fetch_user_weapons(user_id)
        accs = await self.bot.database.fetch_user_accessories(user_id)
        arms = await self.bot.database.fetch_user_armors(user_id)
        item_dropped = False

        if drop_roll <= drop_chance:
            # Weighted item type selection
            item_type_roll = random.randint(1, 100)
            if item_type_roll <= 50:  # 50% chance for weapon
                if len(items) > 60:
                    embed.add_field(name="✨ Loot", value="Weapon pouch full!")
                else:
                    item_dropped = True
                    weapon = await generate_weapon(user_id, monster.level, drop_rune=True)
                    if weapon.name != "Rune of Refinement":
                        embed.set_thumbnail(url="https://i.imgur.com/mEIV0ab.jpeg")
                        await self.bot.database.create_weapon(weapon)
                    else:
                        embed.set_thumbnail(url="https://i.imgur.com/1tcMeSe.jpeg")
                        await self.bot.database.update_refinement_runes(user_id, 1)
                    embed.add_field(name="✨ Loot", value=f"{weapon.description}", inline=False)
            elif item_type_roll <= 80:  # 30% chance for accessory (50+30)
                if len(accs) > 60:
                    embed.add_field(name="✨ Loot", value="Accessory pouch full!")
                else:
                    item_dropped = True
                    acc = await generate_accessory(user_id, monster.level, drop_rune=True)
                    if acc.name != "Rune of Potential":
                        await self.bot.database.create_accessory(acc)
                        embed.set_thumbnail(url="https://i.imgur.com/KRZUDyO.jpeg")
                    else:
                        await self.bot.database.update_potential_runes(user_id, 1)
                        embed.set_thumbnail(url="https://i.imgur.com/aeorjQG.jpeg")
                    embed.add_field(name="✨ Loot", value=f"{acc.description}", inline=False)
            else:  # 20% chance for armor (80+20)
                if len(arms) > 60:
                    embed.add_field(name="✨ Loot", value="Armor pouch full!")
                else:
                    item_dropped = True
                    armor = await generate_armor(user_id, monster.level, drop_rune=True)
                    if armor.name != "Rune of Imbuing":
                        await self.bot.database.create_armor(armor)
                        embed.set_thumbnail(url="https://i.imgur.com/jtYg94i.png")
                    else:
                        await self.bot.database.update_imbuing_runes(user_id, 1)
                        embed.set_thumbnail(url="https://i.imgur.com/MHgtUW8.png")
                    embed.add_field(name="✨ Loot", value=f"{armor.description}", inline=False)

        if not item_dropped:
            embed.add_field(name="✨ Loot", value="None")

        if monster.name in rare_monsters:
            embed.add_field(name="✨ Curious Curio", value="A curious curio was left behind!", 
                            inline=False)
            await self.bot.database.update_curios_count(user_id, server_id, 1)
        if player.level > 20:
            if random.random() < (0.03 + special_drop):
                embed.add_field(name="✨ Draconic Key", value="A draconic key was left behind!",
                                inline=False)
                embed.set_image(url="https://i.imgur.com/jPteeoT.png")
                await self.bot.database.add_dragon_key(user_id, 1)
            if random.random() < (0.03 + special_drop):
                embed.add_field(name="✨ Angelic Key", value="An angelic key was left behind!",
                                inline=False)
                embed.set_image(url="https://i.imgur.com/cpwPxjU.png")
                await self.bot.database.add_angel_key(user_id, 1)
            if random.random() < (0.08 + special_drop):
                embed.add_field(name="❤️‍🔥 Soul Core", value="A demonic soul core was left behind!",
                                inline=False)
                embed.set_image(url="https://i.imgur.com/x6QKvSy.png")
                await self.bot.database.add_soul_cores(user_id, 1)
            if random.random() < (0.05 + special_drop):
                embed.add_field(name="🟣 Void Fragment", value="A void fragment was left behind!",
                                inline=False)
                embed.set_image(url="https://i.imgur.com/T2ap5iO.png")
                await self.bot.database.add_void_frags(user_id, 1)

        if player.armor_passive == "Everlasting Blessing" and random.random() < 0.1:
            embed.add_field(name="Armor Passive",
                            value="The **Everlasting Blessing** imbues with power!",
                            inline=False)
            self.bot.logger.info("Everlasting Blessing passive")
            existing_user = await self.bot.database.fetch_user(user_id, server_id)
            user_ideology = existing_user[8]
            followers_count = await self.bot.database.fetch_followers(user_ideology)
            base_followers = 10
            growth_factor = 1.5
            scaling_factor = 100
            if followers_count > 1000:
                follower_increase = 100
            else:
                follower_increase = base_followers * (growth_factor ** (followers_count // scaling_factor))
            variation = random.uniform(0.9, 1.1)
            follower_increase = int(follower_increase * variation)
            new_followers_count = followers_count + follower_increase
            base_gold = 1000
            gold_per_follower = 50
            gold_reward = base_gold + (followers_count * gold_per_follower)
            await self.bot.database.update_followers_count(user_ideology, new_followers_count)
            await self.bot.database.add_gold(user_id, gold_reward)
            await self.bot.database.update_propagate_time(user_id)
            propagate_message = (
                f"You advocate for **{user_ideology}** and it spreads!\n"
                f"New followers gained: **{follower_increase}** (Total: **{new_followers_count}**).\n"
                f"Gold collected from followers: **{gold_reward:,} GP**."
            )
            embed.add_field(name=f"{user_ideology} propagated",
                            value=propagate_message,
                            inline=False)

        
        player = await self.update_experience(interaction, message, embed, player, monster)
        await self.bot.database.add_gold(user_id, final_gold_award)
        self.bot.logger.info(player)
        await self.bot.database.update_player(player)
        print('message.edit - victory')
        await message.edit(embed=embed)


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
        print('message.edit - defeat')
        await message.edit(embed=defeat_embed)
        await self.bot.database.update_player(player) # Save new HP and XP
        # self.bot.state_manager.clear_active(player.id) # Caller should handle this


    async def handle_boss_encounter(self, interaction, player, type):
        if (type == 'aphrodite'):
            phases = [
                {"name": "Aphrodite, Heaven's Envoy", "level": 886, "modifiers_count": 3, "hp_multiplier": 1.5},
                {"name": "Aphrodite, the Eternal", "level": 887, "modifiers_count": 6, "hp_multiplier": 2},
                {"name": "Aphrodite, Harbinger of Destruction", "level": 888, "modifiers_count": 9, "hp_multiplier": 2.5},
            ]
        elif (type == 'lucifer'):
            phases = [
                {"name": "Lucifer, Fallen", "level": 663, "modifiers_count": 2, "hp_multiplier": 1.25},
                {"name": "Lucifer, Maddened", "level": 664, "modifiers_count": 3, "hp_multiplier": 1.5},
                {"name": "Lucifer, Enraged", "level": 665, "modifiers_count": 4, "hp_multiplier": 1.75},
                {"name": "Lucifer, Unbound", "level": 666, "modifiers_count": 5, "hp_multiplier": 2},
            ]
        elif (type == 'NEET'):
            phases = [
                {"name": "NEET, Sadge", "level": 444, "modifiers_count": 1, "hp_multiplier": 1.25},
                {"name": "NEET, Madge", "level": 445, "modifiers_count": 2, "hp_multiplier": 1.5},
                {"name": "NEET, REEEEEE", "level": 446, "modifiers_count": 3, "hp_multiplier": 1.75},
                {"name": "NEET, Deadge", "level": 447, "modifiers_count": 4, "hp_multiplier": 2},
            ]

        auto_battle_active = False
        for phase_index, phase in enumerate(phases):
            self.bot.logger.info(f'On phase {phase}')
            # Generate encounter
            monster = Monster(
                name="",
                level=0,
                hp=0,
                max_hp=0,
                xp=0,
                attack=0,
                defence=0,
                modifiers=[],
                image="",
                flavor="",
                is_boss=True
            )
            monster = await generate_boss(player, monster, phase, phase_index)

            self.apply_stat_effects(player, monster)

            if "Temporal Bubble" in monster.modifiers:
                player.weapon_passive = "none"
                self.bot.logger.info(f"Temporal bubble applied: {player.weapon_passive} to nothing")  

            if (type == 'aphrodite'):
                desc = f"🐉**{monster.name}**🪽 descends!\n"
            elif (type == 'lucifer'):
                desc = f"😈 **{monster.name}** 😈 ascends!\n"
            elif (type == 'NEET'):
                desc = f"😭 **{monster.name}** 😡 approaches!\n"

            self.bot.logger.info(player)
            self.bot.logger.info(monster)

            embed = discord.Embed(
                title=f"Witness {player.name} (Level {player.level})",
                description=(desc +
                             f"\n__Modifiers__\n" +
                            "\n".join([f"**{m}**: {get_modifier_description(m)}" for m in monster.modifiers]) +
                            f"\n\n~{int(calculate_hit_chance(player, monster) * 100)}% to hit | "
                            f"~{int(calculate_monster_hit_chance(player, monster) * 100)}% to get hit"),
                color=0x00FF00,
            )
            embed.set_image(url=monster.image)

            if player.armor_passive == "Omnipotent" and random.random() < 0.2:
                monster.attack = 0
                monster.defence = 0
                self.bot.logger.info("Omnipotent passive: Monster attack and defense set to 0")
                embed.add_field(name="Armor Passive",
                value=f"The **Omnipotent** armor imbues with power! The {monster.name} trembles in **terror**.",
                inline=False)

            player.invulnerable = False
            if player.armor_passive == "Invulnerable" and random.random() < 0.2:
                embed.add_field(name="Armor Passive",
                                value="The **Invulnerable** armor imbues with power!",
                                inline=False)
                player.invulnerable = True
                    
            if player.armor_passive == "Unlimited Wealth" and random.random() < 0.2:
                player.rarity *= 2
                self.bot.logger.info(f"Unlimited Wealth passive: Player rarity multiplied by 2 to {player.rarity}")
                embed.add_field(name="Armor Passive",
                value=f"The **Unlimited Wealth** armor imbues with power! {player.name}'s greed knows no bounds.",
                inline=False)

            embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
            embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)" if player.ward > 0 else player.hp, inline=True)                                                     
            await interaction.edit_original_response(embed=embed)
            message = await interaction.original_response()

            health_percentage = player.hp / player.max_hp
            if auto_battle_active or (health_percentage > 0.20 and phase_index > 0):
                self.bot.logger.info(f"Continuing auto-battle for phase {phase_index + 1}")
                player, monster = await self.boss_auto_battle(message, embed, player, monster)
                if player.hp <= 0:
                    await self.handle_boss_defeat(message, player, monster, type)
                    return
                elif monster.hp <= 0 and phase == phases[-1]:
                    self.bot.logger.info(f'Won full fight')
                    await self.handle_boss_victory(interaction, message, player, monster, type)
                    return
                elif monster.hp <= 0:
                    continue  # Move to next phase automatically
                else:
                    auto_battle_active = False  # Pause auto-battle if HP is low
                    embed.add_field(name="A temporary reprieve!", value="Player HP < 20%, auto-battle paused!", inline=False)
                    await interaction.followup.send(f'{interaction.user.mention} auto-combat paused!', ephemeral=True)
                    print('message.edit - pause boss')
                    await message.edit(embed=embed)
            else:
                reactions = ["⚔️", "🩹", "⏩"]
                await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

            # Combat loop
            while monster.hp > 0 and player.hp > 0:
                def check(reaction, user):
                    return (user == interaction.user and
                            reaction.message.id == message.id and
                            str(reaction.emoji) in ["⚔️", "🩹", "⏩"])

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
                                                                                                                                           
                    heal_message = ""
                    attack_message = ""
                    monster_message = ""
                    pause_message = ""

                    if str(reaction.emoji) == "⚔️":
                        await message.remove_reaction(reaction.emoji, user)
                        monster, attack_message = await self.player_turn(player, monster)
                        if monster.hp > 0:
                            player, monster_message = await self.monster_turn(player, monster)
                        
                        if player.hp <= 0:
                            await self.handle_boss_defeat(message, player, monster, type)
                            return
                        
                        if monster.hp <= 0:
                            if phase == phases[-1]:
                                self.bot.logger.info(f'Won phase {phase} vs {phases[-1]} with -1')
                                await self.handle_boss_victory(interaction, message, player, monster, type)
                                return
                            break

                    elif str(reaction.emoji) == "⏩":
                        self.bot.logger.info('Start boss auto battle')
                        await message.remove_reaction(reaction.emoji, user)
                        auto_battle_active = True
                        player, monster = await self.boss_auto_battle(message, embed, player, monster)
                        self.bot.logger.info('Boss auto-battle ended')
                        if player.hp <= 0:
                            await self.handle_boss_defeat(message, player, monster, type)
                        elif monster.hp <= 0 and phase == phases[-1]:
                            self.bot.logger.info(f'Won full fight')
                            await self.handle_boss_victory(interaction, message, player, monster, type)
                            return
                        elif monster.hp <= 0:
                            break
                        else:
                            auto_battle_active = False
                            self.bot.logger.info('Pause auto battle')
                            pause_message = "Player HP < 20%, auto-battle paused!"
                            await interaction.followup.send(f'{interaction.user.mention} auto-combat paused!', ephemeral=True)

                    elif str(reaction.emoji) == "🩹":
                        await message.remove_reaction(reaction.emoji, user)
                        player, heal_message = await self.heal(player)


                    messages = {
                        player.name: attack_message,
                        monster.name: monster_message,
                        "Heal": heal_message,
                        "A temporary reprieve!": pause_message
                    }
                    embed = await self.update_combat_embed(embed, player, monster, messages)
                    await message.edit(embed=embed)

                except asyncio.TimeoutError:
                    embed.add_field(name=monster.name,
                                    value=f"{monster.name} loses interest.\n"
                                            f"{player.name} failed to grasp the moment.",
                                    inline=False)
                    await message.edit(embed=embed)
                    await message.clear_reactions()
                    self.bot.state_manager.clear_active(player.id)
                    await self.bot.database.update_player(player)
                    return

            if player.hp <= 0:
                return

    async def handle_boss_victory(self, interaction, message, player, monster, type):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        await message.clear_reactions()
            
        embed = discord.Embed(
            title=f"{type.title()} defeated! 🎉",
            description=f"{player.name} has won with {player.hp} ❤️ remaining!",
            color=0x00FF00,
        )
        self.bot.logger.info('Calculating boss rewards')
        gold_award = int(random.randint(15000, 50000) * (1 + player.rarity / 100))
        curios_award = random.randint(1, 5)
        if player.acc_passive == "Prosper":
            double_gold_chance = player.acc_lvl * 5
            if random.randint(1, 100) <= double_gold_chance:
                gold_award *= 2
                embed.add_field(name="Accessory Passive",
                                      value=f"The accessory's **Prosper ({player.acc_lvl})** activates, granting double gold!",
                                      inline=False)
        if player.acc_passive == "Infinite Wisdom":
            double_exp_chance = player.acc_lvl * 5
            if random.randint(1, 100) <= double_exp_chance:
                monster.xp *= 2
                embed.add_field(name="Accessory Passive",
                                      value=f"The accessory's **Infinite Wisdom ({player.acc_lvl})** activates, "
                                            f"granting double experience!",
                                      inline=False)

        embed.add_field(name="📚 Experience", value=f"{monster.xp:,} XP")
        embed.add_field(name="💰 Gold", value=f"{gold_award:,} GP")
        embed.add_field(name="🎁 Curios", value=f"{curios_award} Curious Curios")

        # Rune drops
        runes_dropped = []
        if type == 'aphrodite':
            if random.random() < 0.33:
                await self.bot.database.update_refinement_runes(user_id, 1)
                runes_dropped.append("Rune of Refinement")
            if random.random() < 0.33:
                await self.bot.database.update_potential_runes(user_id, 1)
                runes_dropped.append("Rune of Potential")
            if random.random() < 0.33:
                await self.bot.database.update_imbuing_runes(user_id, 1)
                runes_dropped.append("Rune of Imbuing")
        elif type == 'lucifer':
            if random.random() < 0.66:
                await self.bot.database.update_refinement_runes(user_id, 1)
                runes_dropped.append("Rune of Refinement")
            if random.random() < 0.33:
                await self.bot.database.update_potential_runes(user_id, 1)
                runes_dropped.append("Rune of Potential")
        elif type == 'NEET':
            if random.random() < 0.33:
                await self.bot.database.update_refinement_runes(user_id, 1)
                runes_dropped.append("Rune of Refinement")
            if random.random() < 0.66:
                await self.bot.database.update_potential_runes(user_id, 1)
                runes_dropped.append("Rune of Potential")
        if runes_dropped:
            embed.add_field(name="❇️ Runes Dropped", value=", ".join(runes_dropped), inline=False)
        else:
            embed.add_field(name="❇️ Runes Dropped", value="None", inline=False)

        await self.bot.database.add_gold(user_id, gold_award)
        await self.bot.database.update_curios_count(user_id, server_id, curios_award)
        player = await self.update_experience(interaction, message, embed, player, monster)
        await self.bot.database.update_player(player)

        if type == 'aphrodite':
            embed.set_image(url="https://i.imgur.com/wKyTFzh.jpg")
            await message.edit(embed=embed)
            self.bot.state_manager.clear_active(user_id)
        if type == 'NEET':
            embed.set_image(url="https://i.imgur.com/7UmY4Mo.jpeg")
            embed.add_field(name="As the tombstone crumbles away...", value="You notice a shining void key, you pocket it...", inline=False)
            await message.edit(embed=embed)
            await self.bot.database.add_void_keys(user_id, 1)
            self.bot.state_manager.clear_active(user_id)
        if type == 'lucifer':
            embed.set_image(url="https://i.imgur.com/x9suAGK.png")
            
            # Final prompt for soul cores
            soul_core_prompt = (
                "As Lucifer falls, his soul explodes into soul cores. You have a feeling you can pick just one to consume its power:\n"
                "🩶  **Inverse** Soul Core: Switches player's attack and defence stat\n"
                "❤️‍🔥  **Enraged** Soul Core: Randomly adjusts attack by -1 to +2\n"
                "💙  **Solidified** Soul Core: Randomly adjusts defence by -1 to +2\n"
                "💔  **Unstable** Soul Core: Changes your stats unpredictably towards equilibrium\n"
                "🖤  **Original** Soul Core: Grants a single soul core back to challenge Lucifer\n"
                "Select an option below:"
            )
            embed.add_field(name="Soul Core Selection", value=soul_core_prompt, inline=False)
            await message.edit(embed=embed)
            
            # Handle user selection of soul core
            def check(reaction, user):
                return user.id == interaction.user.id and str(reaction.emoji) in ["🩶", "❤️‍🔥", "💙", "💔", "🖤"]

            await message.add_reaction("🩶")
            await message.add_reaction("❤️‍🔥")
            await message.add_reaction("💙")
            await message.add_reaction("💔")
            await message.add_reaction("🖤")

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
                await message.clear_reactions()
                
                existing_user = await self.bot.database.fetch_user(user_id, server_id)
                player.attack = existing_user[9]
                player.defence = existing_user[10]
                
                if str(reaction.emoji) == "🩶":  # Inverse Soul Core
                    await self.bot.database.update_player_attack(user_id, player.defence)
                    await self.bot.database.update_player_defence(user_id, player.attack)
                    new_attack = player.defence
                    new_defence = player.attack
                    response_message = (f"You have consumed the **Inverse** Soul Core!\n"
                                        f"Attack is now {new_attack}, Defence is now {new_defence}.")
                    
                elif str(reaction.emoji) == "❤️‍🔥":  # Enraged Soul Core
                    adjustment = random.randint(-1, 2)
                    new_attack = player.attack + adjustment
                    adjustment_str = f"+{adjustment}" if adjustment > 0 else str(adjustment)
                    await self.bot.database.update_player_attack(user_id, new_attack)
                    response_message = (f"You have consumed the **Enraged** Soul Core!\n"
                                        f"Attack is now {new_attack} ({adjustment_str}).")
                    
                elif str(reaction.emoji) == "💙":  # Solidified Soul Core
                    adjustment = random.randint(-1, 2)
                    new_defence = player.defence + adjustment
                    adjustment_str = f"+{adjustment}" if adjustment > 0 else str(adjustment)
                    await self.bot.database.update_player_defence(user_id, new_defence)
                    response_message = (f"You have consumed the **Solidified** Soul Core!\n"
                                        f"Defence is now {new_defence} ({adjustment_str}).")
                    
                elif str(reaction.emoji) == "💔":  # Unstable Soul Core
                    total = player.attack + player.defence
                    new_attack = int(total * random.uniform(0.49, 0.51))  # Assign a weighted value
                    new_defence = total - new_attack
                    await self.bot.database.update_player_attack(user_id, new_attack)
                    await self.bot.database.update_player_defence(user_id, new_defence)
                    response_message = (f"You have consumed the **Unstable** Soul Core!\n"
                                        f"Attack is now {new_attack}, Defence is now {new_defence}.")
                    
                elif str(reaction.emoji) == "🖤":  # Original Soul Core
                    await self.bot.database.add_soul_cores(user_id, 1)  # Grant 1 soul core back
                    response_message = "You gain an additional soul core."

                # Update the victory embed with the response message
                embed.add_field(name="Result", value=response_message, inline=False)
                await message.edit(embed=embed)
                self.bot.state_manager.clear_active(user_id)
            except asyncio.TimeoutError:
                self.bot.state_manager.clear_active(user_id)
                await message.clear_reactions()                      
                await interaction.channel.send("You hesitated, and the moment has passed.")


    async def handle_boss_defeat(self, message, player, monster, type):
        """Handle defeat for the boss encounter."""
        await message.clear_reactions()
        self.bot.state_manager.clear_active(player.id)
        current_exp = player.exp
        penalty_xp = int(current_exp * 0.1)
        new_exp = max(0, current_exp - penalty_xp)
        player.hp = 1
        player.exp = new_exp

        if type == 'aphrodite':
            title_text = "You have failed to conquer the heavens."
        elif type == 'lucifer':
            title_text = "You have failed to conquer the infernal depths."
            
        total_damage_dealt = monster.max_hp - monster.hp
        defeat_embed = discord.Embed(
            title=title_text,
            description=f"{monster.name} deals a fatal blow!\n"
                        f"{player.name} has been defeated after dealing {total_damage_dealt} damage.\n"
                        f"{monster.name} stands triumphant with {monster.hp} health left.\n"
                        f"{monster.name} drains {penalty_xp:,} xp from your essence...",
            color=0xFF0000
        )
        defeat_embed.add_field(name="Pity...", value=f"({player.name} stumbles away with 1 hp.)")
        await message.edit(embed=defeat_embed)
        await self.bot.database.update_player(player)
        
    async def update_experience(self, interaction, message, embed, player, monster) -> None:
        """Update the user's experience and handle leveling up."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player.attack = existing_user[9]
        player.defence = existing_user[10]
        exp_table = self.load_exp_table()
        new_exp = player.exp + monster.xp
        level_up = False
        ascension = False
        self.bot.logger.info(f'Currently level {player.level} with exp {player.exp}, new exp is {new_exp}')

        exp_threshold = exp_table["levels"][str(player.level)]
        self.bot.logger.info(f'exp threshold is {exp_threshold}')

        if player.level == 100 and new_exp >= exp_threshold:
            ascension = True
            self.bot.logger.info('Ascension')

        if player.level < 100 and new_exp >= exp_threshold:
            player.level += 1
            level_up = True

        if level_up:
            attack_increase = random.randint(1, 5)
            defence_increase = random.randint(1, 5)
            hp_increase = random.randint(1, 5)
            embed.add_field(name="Level Up! 🎉", value=f"{player.name} has reached level **{player.level}**!")
            new_atk = player.attack + attack_increase
            new_def = player.defence + defence_increase
            new_mhp = player.max_hp + hp_increase
            player.attack = new_atk
            player.defence = new_def
            player.max_hp = new_mhp
            if player.level > 0 and player.level % 10 == 0 and player.level <= 100:
                self.bot.logger.info('Awarding 2 passive points for this level up since it fits the criteria')
                passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
                await self.bot.database.set_passive_points(user_id, server_id, passive_points + 2)
                embed.add_field(name="2 passive points gained!", 
                               value="Use /passives to allocate them.", 
                               inline=False)
            embed.add_field(name="Stat increases:", 
                           value=f"⚔️ **Attack:** {new_atk} (+{attack_increase})\n"
                                 f"🛡️ ** Defence:** {new_def} (+{defence_increase})\n"
                                 f"❤️ **Hit Points:** {new_mhp} (+{hp_increase})", inline=False)
            new_exp -= exp_table["levels"][str(player.level - 1)]
            await self.bot.database.increase_attack(user_id, attack_increase)
            await self.bot.database.increase_defence(user_id, defence_increase)

        if ascension:
            embed.add_field(name="Ascension Level Up! 🎉", value=f"{player.name} has reached Ascension **{player.ascension + 1}**!")
            passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
            await self.bot.database.set_passive_points(user_id, server_id, passive_points + 2)
            embed.add_field(name="2 passive points gained!", 
                            value="Use /passives to allocate them.", 
                            inline=False)
            new_exp -= exp_table["levels"][str(player.level - 1)]
            player.ascension += 1

        player.exp = new_exp
        return player


async def setup(bot) -> None:
    await bot.add_cog(Combat(bot))