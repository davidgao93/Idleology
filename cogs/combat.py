import aiohttp
import random
import discord
from discord.ext import commands
from discord.ext.tasks import asyncio
from discord.ext import tasks
from discord import app_commands, Interaction, Message
import json
import csv
import os
import re

class Combat(commands.Cog, name="combat"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.prefixes = self.load_list("assets/items/pref.txt")
        self.weapon_types = self.load_list("assets/items/wep.txt")
        self.suffixes = self.load_list("assets/items/suff.txt")
        self.accessory_types = self.load_list("assets/items/acc.txt")

    def load_list(self, filepath: str) -> list:
        """Load a list from a text file."""
        with open(filepath, "r") as file:
            return [line.strip() for line in file.readlines()]
        
    def load_exp_table(self):
        with open('assets/exp.json') as file:
            exp_table = json.load(file)
        return exp_table
        
    async def generate_loot(self, user_id: str, server_id: str, encounter_level: int, drop_rune: bool) -> str:
        """Generate a unique loot item."""
        prefix = random.choice(self.prefixes)
        weapon_type = random.choice(self.weapon_types)
        suffix = random.choice(self.suffixes)
        item_name = f"{prefix} {weapon_type} {suffix}"

        modifiers = []
        attack_modifier = 0
        defence_modifier = 0
        rarity_modifier = 0
        if (drop_rune):
            if random.randint(0, 100) < 80:  # 80% chance for attack roll
                attack_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
                modifiers.append(f"+{attack_modifier} Attack")
        else:
            attack_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
            modifiers.append(f"+{attack_modifier} Attack")

        if random.randint(0, 100) < 50:  # 50% chance for defense roll
            defence_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
            modifiers.append(f"+{defence_modifier} Defence")

        if random.randint(0, 100) < 20:  # 20% chance for rarity roll
            rarity_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5))) * 5
            modifiers.append(f"+{rarity_modifier}% Rarity")

        loot_description = item_name + f"\n"
        if modifiers:
            loot_description += f"\n".join(modifiers)
        else:
            # Award the Rune of Refinement if there are no modifiers
            await self.bot.database.update_refinement_runes(user_id, 1)  # Increment runes
            loot_description = "**Rune of Refinement**!"
            item_name = "rune"

        return item_name, attack_modifier, defence_modifier, rarity_modifier, loot_description
    
    async def generate_accessory(self, user_id: str, server_id: str, encounter_level: int, drop_rune: bool) -> str:
        """Generate a unique accessory item."""
        prefix = random.choice(self.prefixes)
        accessory_type = random.choice(self.accessory_types)
        suffix = random.choice(self.suffixes)
        acc_name = f"{prefix} {accessory_type} {suffix}"

        modifiers = []
        attack_modifier = 0
        defence_modifier = 0
        rarity_modifier = 0
        if (drop_rune):
            randroll = random.randint(0, 100)
        else:
            randroll = random.randint(0, 90)

        if randroll <= 18:  # 18% chance for attack roll
            attack_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
            modifiers.append(f"+{attack_modifier} Attack")
        elif randroll > 18 and randroll <= 36:  # 18% chance for defense roll
            defence_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
            modifiers.append(f"+{defence_modifier} Defence")
        elif randroll > 36 and randroll <= 54:
            rarity_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5))) * 5
            modifiers.append(f"+{rarity_modifier}% Rarity")
        elif randroll > 54 and randroll <= 72:
            rarity_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5))) * 2
            modifiers.append(f"+{rarity_modifier}% Ward")
        elif randroll > 72 and randroll <= 90:
            rarity_modifier = max(1, random.randint(int(encounter_level // 10), int(encounter_level // 9)))
            modifiers.append(f"+{rarity_modifier}% Crit")

        loot_description = acc_name + f"\n"
        if modifiers:
            loot_description += f"\n".join(modifiers)
        else:
            # Award the Rune of Potential if there are no modifiers
            await self.bot.database.update_potential_runes(user_id, 1)  # Increment runes
            loot_description = "**Rune of Potential**!"
            acc_name = "rune"
            
        return acc_name, loot_description

    @app_commands.command(name="combat", description="Engage in combat.")
    @app_commands.checks.cooldown(1, 600, key=lambda i: (i.user.id))  # 1 use per 600 seconds per user
    async def combat(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        if existing_user:
            self.bot.state_manager.set_active(user_id, "combat")  # Set combat as active operation
            player_name = existing_user[3]
            user_level = existing_user[4] 
            player_ideology = existing_user[8]
            player_attack = existing_user[9]
            player_defence = existing_user[10]
            player_hp = existing_user[11]  
            player_max_hp = existing_user[12]
            ascension_level = existing_user[15]
            potions = existing_user[16]
            player_rar = 0
            player_crit = 95
            player_ward = 0
            current_passive = ""
            accessory_passive = ""
            accessory_lvl = 0
            followers_count = await self.bot.database.fetch_followers(player_ideology)
            equipped_item = await self.bot.database.get_equipped_item(user_id)
            equipped_accessory = await self.bot.database.get_equipped_accessory(user_id)
            if equipped_item:
                current_passive = equipped_item[7]
                player_attack += equipped_item[4]
                player_defence += equipped_item[5]
                player_rar += equipped_item[6]
                print(f'Stats from equipped weapon: {equipped_item[4]} atk {equipped_item[5]} def {equipped_item[6]} rar')
                print(f'Weapon grants {current_passive}')
            if equipped_accessory:
                accessory_passive = equipped_accessory[9]
                player_attack += equipped_accessory[4]
                player_defence += equipped_accessory[5]
                player_rar += equipped_accessory[6]
                player_ward += int((equipped_accessory[7] / 100) * player_max_hp)
                player_crit -= equipped_accessory[8]
                accessory_lvl = equipped_accessory[12]
                print(f'Stats from equipped acc: {equipped_accessory[4]} atk {equipped_accessory[5]} def {equipped_accessory[6]} rar')
                print(f'beat {player_crit} to crit, {player_ward} hp ward shield')
                print(f'Accessory grants {accessory_passive}')
            # Randomly determine if a treasure chest should spawn (1% chance)
            is_treasure = False
            if random.random() < 0.01:  # 1% chance
                print('Treasure mob hit')
                encounter_level, monster_attack, monster_defence = self.generate_encounter(user_level)
                monster_attack = 0
                monster_defence = 0
                is_treasure = True
            else:
                encounter_level, monster_attack, monster_defence = self.generate_encounter(user_level)

            if (user_level == 1):
                monster_hp = 10
            elif (user_level > 1 and user_level <= 5):
                monster_hp = max(10, random.randint(1, 4) + int(7 * (encounter_level ** random.uniform(1.05, 1.15))))
            else:
                monster_hp = random.randint(0, 9) + int(10 * (encounter_level ** random.uniform(1.25, 1.35)))
            award_xp = monster_hp
            attack_message = ""
            monster_message = ""
            heal_message = ""
            opportunity_message = ""
            opportunity = False
            print(f"player_hp: {player_hp} | follower_count: {followers_count} | ascension: {ascension_level} | "
                  f"p.atk: {player_attack} | p.def: {player_defence}")
            print(f"m.lvl: {encounter_level} | m.atk: {monster_attack} | m.def: {monster_defence} | m.hp: {monster_hp}")
            # Fetch the monster image
            if (is_treasure):
                monster_name, image_url, flavor_txt = await self.fetch_monster_image(999)
            else:
                monster_name, image_url, flavor_txt = await self.fetch_monster_image(encounter_level)
            
            print(f"Generated {monster_name} with image_url: {image_url}")

            start_combat = False
            try:
                embed = discord.Embed(
                    title=f"Witness {player_name}",
                    description=f"A level {encounter_level} {monster_name} approaches! ({int(monster_hp * 1.4)} xp)",
                    color=0x00FF00,
                )
                embed.set_image(url=image_url)  # Set the image fetched from the API
                embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
                if (player_ward > 0):
                    embed.add_field(name="❤️ HP", value=f"{player_hp} ({player_ward} 🛡️)", inline=True)
                else:
                    embed.add_field(name="❤️ HP", value=player_hp, inline=True)
                items = await self.bot.database.fetch_user_items(user_id)
                accs = await self.bot.database.fetch_user_accessories(user_id)
                if (len(items) > 4):
                    embed.add_field(name="🚫 WARNING 🚫", value=f"Weapon pouch is full! Weapons can't drop.",
                                    inline=False)
                if (len(accs) > 4):
                    embed.add_field(name="🚫 WARNING 🚫", value=f"Accessory pouch is full! Accessories can't drop.",
                                    inline=False)
                # CALCULATE ABSORB PASSIVE
                if accessory_passive == "Absorb":
                    #print('Absorb passive found, calculating chance to absorb stats')
                    absorb_chance = (accessory_lvl * 2)
                    if random.randint(1, 100) <= absorb_chance:
                        monster_stats = monster_attack + monster_defence  # Assuming monster_stats is a sum of the stats
                        absorb_amount = int(monster_stats * 0.10)
                        player_attack += int(absorb_amount / 2)
                        player_defence += int(absorb_amount / 2)
                        embed.add_field(name="Accessory passive", 
                                        value=(f"The accessory's 🌀 **Absorb ({accessory_lvl})** activates! "
                                                f"Boosted ⚔️: {player_attack}\n"
                                                f"Boosted 🛡️: {player_defence}"), 
                                        inline=False)                
                        #print(f'New player attack: {player_attack} | New player defence: {player_defence}')

                # CALCULATE POLISHED PASSIVE
                polished_passives = ["polished", "honed", "gleaming", "tempered", "flaring"]
                if (current_passive in polished_passives):
                    value = polished_passives.index(current_passive)
                    defence_reduction = (value + 1) * 5  # 5% defense reduction per tier
                    monster_defence_reduction = int(monster_defence * defence_reduction / 100)
                    #print(f"Polish passive reduces monster's defense by {monster_defence_reduction}.")
                    embed.add_field(name="Weapon passive", 
                                    value=(f"The **{current_passive}** weapon 💫 shines with anticipation!\n"
                                            f"It reduces the {monster_name}'s defence by {defence_reduction}%.\n"),
                                    inline=False)
                    monster_defence -= monster_defence_reduction

                # CALCULATE STURDY PASSIVE (Placeholder example for future implementation)
                sturdy_passives = ["sturdy", "reinforced", "thickened", "impregnable", "impenetrable"]
                if (current_passive in sturdy_passives):
                    value = sturdy_passives.index(current_passive)
                    # Example behavior for Sturdy (currently unspecified)
                    defence_bonus = (1 + value) * 3  # This can be defined later based on combat mechanics
                    #print(f"Sturdy passive increases defense by {defence_bonus}.")
                    embed.add_field(name="Weapon passive", 
                                    value=(f"The **{current_passive}** weapon strengthens resolve!\n"
                                            f"Boosted 🛡️: {defence_bonus}\n"),
                                    inline=False)
                    player_defence += defence_bonus

                accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
                if (current_passive in accuracy_passives):
                    value = (1 + accuracy_passives.index(current_passive)) * 4
                    embed.add_field(name="Accuracy", 
                        value=(f"The **{current_passive}** weapon glints with 🎯 precision. "
                               f"It boosts accuracy by **{value}%**!"), 
                        inline=False)

                await interaction.response.send_message(embed=embed)
                message: Message = await interaction.original_response()
                start_combat = True
            except Exception as e:
                await interaction.response.send_message(f"The servers are busy handling another request. Try again.")
                self.bot.state_manager.clear_active(user_id)
                return
            
            reactions = ["⚔️", "🩹", "⏩", "🏃"]
            await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))
            if start_combat:
                while True:
                    def check(reaction, user):
                        return (user == interaction.user 
                                and reaction.message.id == message.id 
                                and str(reaction.emoji) in ["⚔️", "🩹", "⏩", "🏃"])

                    try:
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)

                        if str(reaction.emoji) == "⚔️":
                            heal_message = ""
                            opportunity = False
                            monster_hp, attack_message = await self.player_turn(embed, 
                                                                                player_attack, 
                                                                                monster_hp, 
                                                                                monster_defence, 
                                                                                followers_count, 
                                                                                player_name, 
                                                                                ascension_level, 
                                                                                monster_name, 
                                                                                current_passive,
                                                                                player_crit, 
                                                                                accessory_passive, 
                                                                                accessory_lvl)
                            
                            player_hp, monster_message, player_ward = await self.monster_turn(embed, 
                                                                                            monster_attack, 
                                                                                            player_hp, 
                                                                                            player_defence, 
                                                                                            followers_count,
                                                                                            monster_name, 
                                                                                            user_id, 
                                                                                            current_passive, 
                                                                                            flavor_txt,
                                                                                            player_ward)
                            
                            await self.bot.database.update_player_hp(user_id, player_hp)
                            await message.remove_reaction(reaction.emoji, user)
                            # Check if the player is defeated
                            if player_hp <= 0:
                                total_damage_dealt = award_xp - monster_hp
                                embed.add_field(name=player_name, value=attack_message, inline=False)
                                embed.add_field(name=monster_name, value=monster_message, inline=False)
                                await self.handle_defeat(user_id, message, monster_name,
                                                         total_damage_dealt, player_name, award_xp, server_id)
                                self.bot.state_manager.clear_active(user_id)
                                break
                            # CALCULATE OVERWHELM PASSIVE (culling strike)
                            overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
                            # Check if the monster is defeated
                            if (current_passive in overwhelm_passives):
                                culling_multiplier = overwhelm_passives.index(current_passive)
                                culling_strike = (culling_multiplier + 1) * 5  # 5% culling per tier
                                if monster_hp <= (award_xp * culling_strike / 100):
                                    print('overwhelmed')
                                    embed.add_field(name=player_name, value=attack_message, inline=False)
                                    embed.add_field(name=monster_name, value=monster_message, inline=False)
                                    await self.handle_victory(encounter_level, user_id, server_id, 
                                                            player_name, monster_name, interaction, 
                                                            award_xp, player_rar, player_hp,
                                                            message, user_level, True,
                                                            accessory_passive, accessory_lvl)
                                    self.bot.state_manager.clear_active(user_id)
                                    break
                            else:
                                if monster_hp <= 0:
                                    embed.add_field(name=player_name, value=attack_message, inline=False)
                                    embed.add_field(name=monster_name, value=monster_message, inline=False)
                                    await self.handle_victory(encounter_level, user_id, server_id, 
                                                            player_name, monster_name, interaction, 
                                                            award_xp, player_rar, player_hp,
                                                            message, user_level, False,
                                                            accessory_passive, accessory_lvl)
                                    self.bot.state_manager.clear_active(user_id)
                                    break

                        elif str(reaction.emoji) == "⏩":
                            print('Start auto battle')
                            await message.remove_reaction(reaction.emoji, user)
                            end_battle, end_php, end_mhp = await self.auto_battle(
                                                    embed, interaction, encounter_level,
                                                    player_attack, monster_hp, monster_attack,
                                                    monster_defence, player_defence,
                                                    followers_count, player_name, user_id, 
                                                    server_id, monster_name, player_hp, 
                                                    message, award_xp, ascension_level, 
                                                    player_rar, current_passive, user_level,
                                                    flavor_txt, player_max_hp, player_crit,
                                                    player_ward, accessory_passive, accessory_lvl)
                            if end_battle:
                                print('End auto battle')
                                self.bot.state_manager.clear_active(user_id)
                                break
                            else:
                                print('Pause auto battle')
                                player_hp = end_php
                                monster_hp = end_mhp 
                                embed.add_field(name="Auto battle",
                                                value="Player HP < 20%, auto-battle paused!",
                                                inline=False)
                        elif str(reaction.emoji) == "🩹":
                            if (player_ward > 0):
                                embed.add_field(name="Heal", value="Full hp!", inline=False)
                            else:
                                player_hp, potions, heal_message = await self.heal(existing_user, player_hp, potions, 
                                                            user_id, server_id, interaction, embed,
                                                            player_name)
                                if random.random() < 0.5:
                                    opportunity = True
                                    if user_level <= 10:
                                        damage_taken = random.randint(1, 2)
                                    else:
                                        damage_taken = random.randint(1, 6) 
                                    # print(f'Monster opportune strikes for {damage_taken}')
                                    new_player_hp = max(1, player_hp - damage_taken)
                                    player_hp = new_player_hp
                                    await self.bot.database.update_player_hp(user_id, player_hp)
                                    opportunity_message = f"The monster took an opportunity strike, dealing **{damage_taken}** 💥 damage!"
                                    embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                                    embed.set_field_at(1, name="❤️ HP", value=player_hp, inline=True)
                            await message.edit(embed=embed)
                            await message.remove_reaction(reaction.emoji, user)

                        elif str(reaction.emoji) == "🏃":
                            if random.random() < 0.5:
                                opportunity = True
                                if user_level <= 10:
                                    damage_taken = random.randint(1, 2)
                                else:
                                    damage_taken = random.randint(1, 6) 
                                # print(f'Monster opportune strikes for {damage_taken}')
                                new_player_hp = max(1, player_hp - damage_taken)
                                player_hp = new_player_hp
                                await self.bot.database.update_player_hp(user_id, player_hp)
                                opportunity_message = (f"As {player_name} runs away, the {monster_name} savagely swipes, "
                                                       f" grazing for **{damage_taken}** 💥 damage!")
                                embed.add_field(name=monster_name, value=opportunity_message, inline=False)                     
                                embed.set_field_at(1, name="❤️ HP", value=player_hp, inline=True)
                                await message.edit(embed=embed)
                            else:
                                embed.add_field(name="Escape", value="Got away safely!", inline=False)
                                await message.edit(embed=embed)
                            self.bot.state_manager.clear_active(user_id)
                            await message.remove_reaction(reaction.emoji, user)
                            break

                        if len(embed.fields) > 5:
                            embed.clear_fields()
                            embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
                            if (player_ward > 0):
                                print('Positive player_ward')
                                embed.add_field(name="❤️ HP", value=f"{player_hp} ({player_ward} 🛡️)", inline=True)
                            else:         
                                print('No player ward')       
                                embed.add_field(name="❤️ HP", value=player_hp, inline=True)
                            if attack_message:
                                embed.add_field(name=player_name, value=attack_message, inline=False)
                            if monster_message:
                                embed.add_field(name=monster_name, value=monster_message, inline=False)
                            if heal_message:
                                embed.add_field(name="Heal", value=heal_message, inline=False)
                            if opportunity:
                                embed.add_field(name=f"{monster_name}", value=opportunity_message, inline=False)
                        else:
                            embed.set_field_at(0, name="🐲 HP", value=monster_hp, inline=True)
                            if (player_ward > 0):
                                embed.set_field_at(1, name="❤️ HP", value=f"{player_hp} ({player_ward} 🛡️)", inline=True)
                            else:                            
                                embed.set_field_at(1, name="❤️ HP", value=player_hp, inline=True)
                        #await message.clear_reactions()
                        await message.edit(embed=embed)

                    except asyncio.TimeoutError:
                        if random.random() < 0.5:
                            opportunity = True
                            damage_taken = random.randint(1, 6) 
                            # print(f'Monster opportune strikes for {damage_taken}')
                            new_player_hp = max(1, player_hp - damage_taken)
                            player_hp = new_player_hp
                            await self.bot.database.update_player_hp(user_id, player_hp)
                            opportunity_message = (f"The {monster_name} loses interest, "
                                                    f" lazily grazing for **{damage_taken}** damage before leaving.")
                            embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                            if (player_ward > 0):
                                embed.set_field_at(1, name="❤️ HP", value=f"{player_hp} ({player_ward} 🛡️)", inline=True)
                            else:                            
                                embed.set_field_at(1, name="❤️ HP", value=player_hp, inline=True)
                            await message.edit(embed=embed)
                        else:
                            embed.add_field(name=monster_name, 
                                            value=(f"The {monster_name} loses interest.\n"
                                                   f"{player_name} failed to grasp the moment."), 
                                            inline=False)
                            await message.edit(embed=embed)
                        self.bot.state_manager.clear_active(user_id)
                        break
                #await message.clear_reactions()

    async def player_turn(self, embed, player_attack, monster_hp, 
                          monster_defence, followers_count, player_name, 
                          ascension_level, monster_name, current_passive,
                          player_crit, accessory_passive, accessory_lvl):
        attack_message = ""
        echo_damage = 0
        echo_hit = False
        passive_message = ""
        attack_multiplier = 1
        # print(f'**** PLAYER TURN ****\n'
        #       f'P. Atk: {player_attack}\n'
        #       f'M. HP: {monster_hp}\n'
        #       f'Weapon passive: {current_passive}\n'
        #       f'Accessory passive: {accessory_passive}\n'
        #       f'Passive level: {accessory_lvl}')
        if accessory_passive == "Obliterate":
            double_damage_chance = (accessory_lvl * 2)
            #print(f'Obliterate passive found, double_damage_chance: {double_damage_chance}')
            if random.randint(1, 100) <= double_damage_chance:
                #print(f'Obliterate roll succeeded, attack multiplier set to 2')
                passive_message = (f"**Obliterate ({accessory_lvl})** activates, doubling 💥 damage dealt!\n") 
                attack_multiplier = 2
            # else:
            #     print('No modifiers to attack multiplier')
        accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
        if (current_passive in accuracy_passives):
            value = (1 + accuracy_passives.index(current_passive)) * 3
            embed.add_field(name="Accuracy", 
                value=f"The **{current_passive}** weapon boosts 🎯 accuracy by **{value}%**!", 
                inline=False)
            hit_chance = self.calculate_hit_chance(player_attack, monster_defence, value)
        else:
            hit_chance = self.calculate_hit_chance(player_attack, monster_defence, 0)
        miss_chance = 100 - (hit_chance * 100)
        attack_roll = random.randint(0, 100) # Roll between 0 and 100

        if accessory_passive == "Lucky Strikes":
            lucky_chance = (accessory_lvl * 10)
            if random.randint(1, 100) <= lucky_chance:
                attack_roll2 = random.randint(0, 100) # Roll between 0 and 100
                attack_roll = max(attack_roll, attack_roll2)
                passive_message=(f"**Lucky Strikes ({accessory_lvl})** activates!\n"
                                 "Hit chance is now 🍀 lucky!\n")
        #print(f'{miss_chance}% to miss. Player rolls {attack_roll}.')
        # CALCULATE CRIT PASSIVE
        adjusted_value = 0
        crit_passives = ["piercing", "keen", "incisive", "puncturing", "penetrating"]
        if (current_passive in crit_passives):
            value = crit_passives.index(current_passive)
            adjusted_value = (value + 1) * 3 # actual crit rate bonus

        # Main combat logic
        # Case 1: attack_roll is a critical hit
        if attack_roll > (player_crit - adjusted_value):  
            max_hit = player_attack
            actual_hit = (random.randint(1, max_hit) * 2) * attack_multiplier
            if actual_hit > monster_hp:
                actual_hit = monster_hp
            # print(f'Critical scored: {monster_hp} - critical {actual_hit}')
            monster_hp -= actual_hit
            attack_message = (
                (f"The **{current_passive}** weapon glimmers with power!\n" if adjusted_value > 0 else '') +
                f"Critical! {player_name} 🗡️ pierces through monster's defenses!\n"
                f"Damage: 💥 **{actual_hit}**"
            )

            attack_message = passive_message + attack_message
        # Case 2: A normal hit
        elif attack_roll >= miss_chance:
            # CALCULATE BURNING PASSIVE
            burning_passives = ["burning", "flaming", "scorching", "incinerating", "carbonising"]
            if (current_passive in burning_passives):
                value = burning_passives.index(current_passive)
                burning_damage = (value + 1)  # Additional d6 for burning
                rolls = [random.randint(1, 6) for _ in range(burning_damage)]
                final_burn_dmg = sum(rolls)
                # print(f"Burning passive adds {burning_damage}d6 to max hit.")
                max_hit = player_attack + final_burn_dmg
                attack_message = (f"The **{current_passive}** weapon 🔥 burns bright!\n"
                                  f"Burning damage roll(s): **{burning_damage}** \n")
                attack_message = passive_message + attack_message
            else:
                max_hit = player_attack

            # CALCULATE SPARKING PASSIVE
            sparking_damage = 0
            sparking_passives = ["sparking", "shocking", "discharging", "electrocuting", "vapourising"]
            if (current_passive in sparking_passives):
                value = sparking_passives.index(current_passive)
                sparking_damage = value + 1  # Increase minimum hit by tier
                rolls = [random.randint(1, 6) for _ in range(sparking_damage)]
                final_spark_damage = sum(rolls)
                # print(f"Shock passive adds {final_spark_damage} additional damage to lowest hit.")
                attack_message = (f"The **{current_passive}** weapon surges with ⚡ lightning!\n"
                                  f"Lightning damage: **{final_spark_damage}**")
                attack_message = passive_message + attack_message
                min_damage = max(final_spark_damage, 1)  # Minimum damage must be at least final_spark_damage
                if monster_hp <= min_damage:
                    actual_hit = monster_hp  # If applying min damage would bring it to zero, hit for remaining monster_hp
                else:
                    # Random hit within the desired range
                    actual_hit = (random.randint(min_damage, max_hit + min_damage)) * attack_multiplier  
                    if (actual_hit > monster_hp):
                        actual_hit = monster_hp
                # print(f'Lightning hit: {monster_hp} - {actual_hit}')
            else:
                echo_hit = False
                actual_hit = random.randint(1, max_hit)
                echo_passives = ["echo", "echoo", "echooo", "echoooo", "echoes"]
                if (current_passive in echo_passives):
                    value = echo_passives.index(current_passive)
                    echo_multiplier = (value + 1) / 10  # Increase minimum hit by tier
                    echo_damage = (1 + int(actual_hit * echo_multiplier)) * attack_multiplier
                    actual_hit = (actual_hit + echo_damage) * attack_multiplier
                    echo_hit = True
                if (actual_hit > monster_hp):
                    actual_hit = monster_hp

            attack_message += (f"{player_name} hits!\n"
                                f"Damage: 💥 **{actual_hit - echo_damage}**")
            attack_message = passive_message + attack_message
            if (echo_hit):
                attack_message += (f"\nThe **{current_passive}** weapon 🎶 echoes the hit!\n"
                                   f"Echo damage: **{echo_damage}**")
            # print(f'Normal hit: {monster_hp} - {actual_hit}')
            monster_hp -= actual_hit
        # Case 3: A miss
        else:
            # CALCULATE POISONOUS PASSIVE
            poisonous_passives = ["poisonous", "noxious", "venomous", "toxic", "lethal"]
            if (current_passive in poisonous_passives):
                value = poisonous_passives.index(current_passive)
                poison_damage_dice = value + 3  # Additional d6 damage on misses
                # print(f"Poison passive deals {poison_damage_dice}d6 poison damage on misses.")
                poison_rolls = [random.randint(1, 6) for _ in range(poison_damage_dice)]
                total_poison_damage = sum(poison_rolls)
                if total_poison_damage >= monster_hp:
                    total_poison_damage = monster_hp
                # print(f'Miss poison hit: {monster_hp} - {poison_damage}')
                monster_hp -= total_poison_damage
                attack_message = (f"{player_name} misses!\n" 
                                  f"{monster_name} takes {total_poison_damage} poison 🐍 damage.")
            else:
                attack_message = f"{player_name} misses!"

        embed.add_field(name=player_name, value=attack_message, inline=False)
        return monster_hp, attack_message  # Return both the updated monster HP and attack message
    
    async def monster_turn(self, embed, monster_attack, player_hp, 
                           player_defence, followers_count, 
                           monster_name, user_id, current_passive, 
                           flavor_txt, player_ward):
        # print('**** MONSTER TURN ****')
        monster_miss_chance = 100 - int(self.calculate_monster_hit_chance(monster_attack, player_defence) * 100)
        monster_attack_roll = random.randint(0, 100) # Roll between 0 and 100
        # (f'{monster_miss_chance}% to miss. Monster rolls {monster_attack_roll}.')
        if monster_attack_roll >= monster_miss_chance:  # Monster attack hits
            damage_taken = self.calculate_damage_taken(monster_attack, player_defence)
            # print(f"HIT - Take {damage_taken} damage")
            if player_ward > 0:
                # print(f"Original ward: {player_ward}")
                player_ward -= damage_taken
                # print(f"New ward: {player_ward}")
                if (player_ward < 0):
                    # print(f"No ward, Player HP ({player_hp}) ({player_ward}) ward")
                    player_hp += player_ward
            else:
                player_hp -= damage_taken
            monster_message = (f"The {monster_name} {flavor_txt}.\n"
                               f"Damage: 💥 **{damage_taken}**")
        else:
            # print(f"MISS")
            monster_message = f"The {monster_name} misses!"

        embed.add_field(name=monster_name, value=monster_message, inline=False)
        return player_hp, monster_message, player_ward  # Return the player's HP after monster attack
    
    async def heal(self, existing_user, player_hp, potions, 
                   user_id, server_id, interaction, 
                   embed, player_name):
        # print("**** HEAL ****")
        if potions <= 0:
            # print('Unable to heal, out of potions')
            heal_message = f"{player_name} has no potions left to heal!"
            embed.add_field(name=player_name, value=heal_message, inline=False)
            return player_hp, 0, heal_message

        # Calculate healing amount
        max_hp = existing_user[12]  # Assuming maximum HP is at index 12
        base_heal = int((max_hp / 10 * 3) + random.randint(1, 6))  # Heal formula
        ascension_level = existing_user[15] 
        
        total_heal = base_heal + (random.randint(1, 6) * ascension_level)
        new_hp = min(max_hp, player_hp + total_heal)  # Update current HP, max to max HP
        await self.bot.database.update_player_hp(user_id, new_hp)  # Update in DB

        # Decrease potion count
        await self.bot.database.decrease_potion_count(user_id)  # Create this method in DatabaseManager
        # print(f'Healing for {total_heal}')
        
        heal_message = (f"{player_name} heals for **{total_heal}** HP!\n"
                        f"**{potions - 1}** potions left.")
        embed.add_field(name=player_name, value=heal_message, inline=False)
        potions -= 1
        return new_hp, potions, heal_message

    async def auto_battle(self, embed, interaction, encounter_level,
                            player_attack, monster_hp, monster_attack,
                            monster_defence, player_defence,
                            followers_count, player_name, user_id, 
                            server_id, monster_name, player_hp, 
                            message, award_xp, ascension_level,
                            player_rar, current_passive, user_level,
                            flavor_txt, player_max_hp, player_crit,
                            player_ward, accessory_passive, accessory_lvl):
        # print("**** AUTO BATTLE ****")
        minimum_hp = int(player_max_hp * 0.2)
        while player_hp > minimum_hp and monster_hp > 0:
            monster_hp, attack_message = await self.player_turn(embed, player_attack, monster_hp, 
                                                monster_defence, followers_count, 
                                                player_name, ascension_level, monster_name, 
                                                current_passive, player_crit,
                                                accessory_passive, accessory_lvl)
            overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
            if (current_passive in overwhelm_passives):
                value = overwhelm_passives.index(current_passive)
                culling_strike = (value + 1) * 5  # 5% culling per tier
                if monster_hp <= (award_xp * culling_strike / 100):
                    print('Overwhelmed')
                    await self.handle_victory(encounter_level, user_id, server_id, 
                        player_name, monster_name, interaction, 
                        award_xp, player_rar, player_hp,
                        message, user_level, True, 
                        accessory_passive, accessory_lvl)
                    return True, player_hp, monster_hp
            else:
                if monster_hp <= 0:
                    embed.add_field(name=monster_name, value=attack_message, inline=False)
                    await self.handle_victory(encounter_level, user_id, server_id, 
                                            player_name, monster_name, interaction, 
                                            award_xp, player_rar, player_hp,
                                            message, user_level, False, 
                                            accessory_passive, accessory_lvl)
                    return True, player_hp, monster_hp

            player_hp, monster_message, player_ward = await self.monster_turn(embed, 
                                                    monster_attack, player_hp, 
                                                    player_defence, followers_count, 
                                                    monster_name, user_id, current_passive, 
                                                    flavor_txt, player_ward)
            #print(f'Monster turn ended, player_hp: {player_hp}, player_ward: {player_ward}')
            await self.bot.database.update_player_hp(user_id, player_hp)
            
            if player_hp <= 0:
                total_damage_dealt = award_xp - monster_hp
                embed.add_field(name=monster_name, value=monster_message, inline=False)
                await self.handle_defeat(user_id, message,
                                         monster_name, total_damage_dealt,
                                         player_name, award_xp, server_id)
                return True, player_hp, monster_hp

            if len(embed.fields) > 5:
                # print('Fields > 5, resetting...')
                embed.clear_fields()
                embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
                if (player_ward > 0):
                    #print('Positive player_ward')
                    embed.add_field(name="❤️ HP", value=f"{player_hp} ({player_ward} 🛡️)", inline=True)
                else:         
                    #print('No player ward')       
                    embed.add_field(name="❤️ HP", value=player_hp, inline=True)
                embed.add_field(name=player_name, value=attack_message, inline=False)
                embed.add_field(name=monster_name, value=monster_message, inline=False)
            else:
                embed.set_field_at(0, name="🐲 HP", value=monster_hp, inline=True)
                if (player_ward > 0):
                    embed.set_field_at(1, name="❤️ HP", value=f"{player_hp} ({player_ward} 🛡️)", inline=True)
                else:                
                    embed.set_field_at(1, name="❤️ HP", value=player_hp, inline=True)

            await message.edit(embed=embed)
            await asyncio.sleep(1)
        return False, player_hp, monster_hp

    async def handle_victory(self, encounter_level, user_id, server_id, 
                             player_name, monster_name, interaction, award_xp,
                             player_rar, player_hp, message, user_level, 
                             isCulled, accessory_passive, accessory_lvl):
        await message.clear_reactions()
        if (isCulled):
            victory_embed = discord.Embed(
                title="Overwhelming victory!  ⚰️",
                description=f"{player_name} has culled the **{monster_name}** with {player_hp} ❤️ remaining!",
                color=0x00FF00,
            )
        else:
            victory_embed = discord.Embed(
                title="Victory!  🎉",
                description=f"{player_name} has slain the **{monster_name}** with {player_hp} ❤️ remaining!",
                color=0x00FF00,
            )
        rare_monsters = ["Treasure Chest", "Random Korean Lady", "KPOP STAR", "Loot Goblin"]
        if (monster_name in rare_monsters):
            drop_chance = 0
            xp_award = 0
            reward_scale = int(user_level / 10) # Bonus rewards based on level differential
        else:
            drop_chance = 90 # normal drop chance
            #drop_chance = 0 # debug drop chance
            xp_award = int(award_xp * 1.4)
            reward_scale = (encounter_level - user_level) / 10 # Bonus rewards based on level differential
        
        rarity =  (player_rar / 100) # Player rarity
        loot_roll = random.randint(1, 100)
        acc_roll = random.randint(1, 100)
        final_loot_roll = loot_roll
        final_acc_roll = acc_roll
        if (player_rar > 0):
            final_loot_roll = int(loot_roll + (10 * rarity))
            final_acc_roll = int(acc_roll + (10 * rarity))
            print(f'User has {rarity}, multiplier on {loot_roll} to {final_loot_roll} for wep')
            print(f'User has {rarity}, multiplier on {acc_roll} to {final_acc_roll} for acc')
        
        print(f'User rolls {final_loot_roll}, beat {drop_chance} to get weapon')
        gold_award = int((encounter_level ** random.uniform(1.4, 1.6)) * (1 + (reward_scale ** 1.3)))
        if (player_rar > 0):
            final_gold_award = int(gold_award * (1.5 + rarity))
        else:
            final_gold_award = gold_award
        final_gold_award += 20
        # PROSPER PASSIVE
        if accessory_passive == "Prosper":
            double_gold_chance = (accessory_lvl * 5)
            if random.randint(1, 100) <= double_gold_chance:
                print(f'Original gold award: {final_gold_award}')
                final_gold_award *= 2
                print(f'New gold award: {final_gold_award}')
                victory_embed.add_field(name="Passive Activated", 
                                value=f"The accessory's **Prosper ({accessory_lvl})** activates, granting double gold!", 
                                inline=False)
        elif accessory_passive == "Infinite Wisdom":
            double_exp_chance = (accessory_lvl * 5)
            if random.randint(1, 100) <= double_exp_chance:
                print(f'Original xp award: {xp_award}')
                xp_award *= 2
                print(f'New xp award: {xp_award}')
                victory_embed.add_field(name="Passive Activated", 
                                value=(f"The accessory's **Infinite Wisdom ({accessory_lvl})** activates, "
                                       f"granting double experience!"), 
                                inline=False)
        victory_embed.add_field(name="📚 Experience Earned", value=f"{xp_award:,} XP")
        victory_embed.add_field(name="💰 Gold Earned", value=f"{final_gold_award:,} GP")
        items = await self.bot.database.fetch_user_items(user_id)
        accs = await self.bot.database.fetch_user_accessories(user_id)
        if (final_loot_roll >= drop_chance): # Normal drop logic
            print('Drop chance beat, generating item')
        #if (False): # Accessory only drop logic
            if (len(items) > 4):
                victory_embed.add_field(name="✨ Loot", value=f"Weapon pouch full!")
            else:
                (item_name, 
                attack_modifier, 
                defence_modifier,
                rarity_modifier, 
                loot_description) = await self.generate_loot(user_id, server_id, encounter_level, True)
                if (item_name != "rune"):
                    victory_embed.set_thumbnail(url="https://i.imgur.com/mEIV0ab.jpeg")
                    await self.bot.database.create_item(user_id, item_name, encounter_level, 
                                                        attack_modifier, defence_modifier, rarity_modifier)
                else:
                    victory_embed.set_thumbnail(url="https://i.imgur.com/aeorjQG.jpeg")
                victory_embed.add_field(name="✨ Loot", value=f"{loot_description}")
        else: # Chance to generate accessory if weapon roll fails
            # if (random.randint(1, 100) >= 0): #100% chance for accessory
            print(f'Weapon roll failed, trying for accessory with {final_acc_roll}')
            if (final_acc_roll >= 97): #beat 96, base 4% for accessory
                if (len(accs) > 4):
                    victory_embed.add_field(name="✨ Loot", value=f"Accessory pouch full!")
                else:
                    (acc_name, loot_description) = await self.generate_accessory(user_id, server_id, encounter_level, True)
                    if (acc_name != "rune"):
                        lines = loot_description.splitlines()
                        for line in lines[1:]:  # Skip the first line (the accessory name)
                                    match = re.search(r"\+(\d+)%? (\w+)", line)  # Capture value and type
                                    if match:
                                        modifier_value = match.group(1) # save the value associated with the modifier
                                        modifier_type = match.group(2) # save the value associated with the mod_type
                        await self.bot.database.create_accessory(user_id, acc_name, encounter_level, 
                                                            modifier_type, modifier_value)
                        victory_embed.set_thumbnail(url="https://i.imgur.com/KRZUDyO.jpeg")
                    else:
                        victory_embed.set_thumbnail(url="https://i.imgur.com/1tcMeSe.jpeg")
                    victory_embed.add_field(name="✨ Loot", value=f"{loot_description}")
            else:
                victory_embed.add_field(name="✨ Loot", value=f"None")
        if (drop_chance == 0):
            victory_embed.add_field(name="✨ Curious Curio", value=f"A curious curio was left behind!")
            await self.bot.database.update_curios_count(user_id, server_id, 1)
        
        await message.edit(embed=victory_embed)
        await self.update_experience(user_id, server_id, xp_award, message, victory_embed) 
        await self.bot.database.add_gold(user_id, final_gold_award)

    async def handle_defeat(self, user_id, message, 
                            monster_name, total_damage_dealt, player_name,
                            award_xp, server_id):
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        current_exp = existing_user[5]
        penalty_xp = int(current_exp * 0.1)
        new_exp = int(current_exp - penalty_xp)
        if new_exp < 0:
            new_exp = 0
        defeat_embed = discord.Embed(
            title="Oh dear...",
            description=(f"The {monster_name} deals a fatal blow!\n"
                         f"{player_name} has been defeated after dealing {total_damage_dealt} damage.\n"
                         f"The {monster_name} walks away with {award_xp - total_damage_dealt} health left.\n"
                         f"Death 💀 takes away {penalty_xp:,} xp from your essence..."),
            color=0xFF0000
        )
        defeat_embed.add_field(name="🪽 Redemption 🪽", value=f"({player_name} revives with 1 hp.)")
        await message.edit(embed=defeat_embed)
        player_hp = 1
        await self.bot.database.update_player_hp(user_id, player_hp)
        await self.bot.database.update_experience(user_id, new_exp)
    
    def calculate_max_hit(self, followers_count, attack_level, ascension_level):
        """Calculate the maximum hit based on the number of followers and attack level"""
        max_hit = attack_level
        return int(max_hit)

    def calculate_hit_chance(self, player_attack, monster_defence, accuracy):
        """Calculate the chance to hit based on the player's attack and monster's defence."""
        difference = player_attack - monster_defence
        additional_hit_chance = int(accuracy / 100)
        if player_attack <= 10:
            return 0.8
        elif player_attack > 10 and player_attack <= 20:
            return 0.7
        # If the player_attack is higher, calculate the hit chance normally
        if difference > 0:
            hit_chance = 0.6 + (difference / 100)  # Starting at 60%, increase by 1% per difference in level
            if (hit_chance >= 0.8):
                hit_chance = 0.8
            #print(f'P. Atk > M. Def, total hit chance: {hit_chance + additional_hit_chance}')
            return hit_chance + additional_hit_chance
        else:
            # If the monster's defence is higher or equal, hit chance is 60%
            #print(f'P. Atk < M. Def, total hit chance: {0.6 + additional_hit_chance}')
            return 0.6 + additional_hit_chance
    
    def calculate_monster_hit_chance(self, monster_attack, player_defence):
        """Calculate the player's chance to be hit based on stats."""
        difference = monster_attack - player_defence
        # If the monster_attack is higher, calculate the hit chance normally
        #print(f"M.ATK {monster_attack} - P.DEF {player_defence} = {difference}")
        if monster_attack <= 3:
            return 0.2
        
        if difference > 0:
            # Starting at 50%, increase based on the difference
            #print(f'M.ATK {monster_attack} > P.DEF {player_defence}. Hit chance: 0.5')
            return 0.5
        else:
            # If the monster's attack is lower
            # The lower the attack, the lower the hit chance
            hit_chance = 0.5 + (difference / 100)  # Starting at 50%, reduce by 1% until 30%
            if hit_chance <= 0.3:
                hit_chance = 0.3
            #print(f'M.ATK {monster_attack} < P.DEF {player_defence}. Hit chance: {hit_chance}')
            return hit_chance  # 50% base chance to  get hit, or the calculated hit chance, whichever is lower
        
    def calculate_damage_taken(self, monster_attack, player_defence):
        """Calculate damage taken based on monster's attack and player's defense."""
        # Calculate the difference
        difference = monster_attack - player_defence
        # print(f"M.ATK {monster_attack} - P.DEF {player_defence} = {difference}")
        if (monster_attack) <= 3:
            damage = random.randint(1,2)
            difference = 0
        elif (monster_attack) <= 20:
            damage = random.randint(1,3)
            difference = 0
        else:
            damage = random.randint(1, 6)  # Roll 1d6
        # Base damage (1d6)
        additional_d6s = 0
        additional_damage = 0
        # If the difference is positive, roll 1 additional d6 per 10 difference in levels
        if difference > 0:
            additional_d6s = int(difference / 10)  # Number of additional d6s to roll
            additional_damage = int(sum(random.randint(1, 6) for _ in range(additional_d6s)))
            damage += additional_damage
        damage_taken = random.randint(1, damage)
        # print(f'Monster rolls {additional_d6s} dice for {additional_damage} for max potential damage: {damage}')
        # print(f'Final damage taken = {damage_taken}')
        return max(0, damage_taken)
    
    def generate_encounter(self, user_level):
        """Generate an encounter with a monster based on the user's level."""
        # Randomly determine if a treasure chest should spawn (1% chance)
        if (user_level < 5):
            difficulty_multiplier = random.randint(1, 2)
        elif (user_level >= 5 and user_level <= 20):
            difficulty_multiplier = random.randint(1, 3)
        elif (user_level > 20 and user_level <= 40):
            difficulty_multiplier = random.randint(1, 4)
        elif (user_level > 40 and user_level <= 50):
            difficulty_multiplier = random.randint(1, 5)
        elif (user_level > 50 and user_level <= 60):
            difficulty_multiplier = random.randint(1, 6)
        elif (user_level > 60 and user_level <= 70):
            difficulty_multiplier = random.randint(1, 7)   
        elif (user_level > 70):
            difficulty_multiplier = random.randint(2, 7)  

        # Calculate the encounter level
        encounter_level = random.randint(user_level, user_level + difficulty_multiplier)

        if (encounter_level < 5):
            base_attack = encounter_level
            base_defence = encounter_level
        elif (encounter_level >= 5 and encounter_level <= 20):
            base_attack = encounter_level ** random.uniform(1.1, 1.2)
            base_defence = encounter_level ** random.uniform(1.1, 1.2)
        elif (encounter_level > 20 and encounter_level <= 40):
            base_attack = encounter_level ** random.uniform(1.25, 1.26)
            base_defence = encounter_level ** random.uniform(1.25, 1.26)
        elif (encounter_level > 40 and encounter_level <= 50):
            base_attack = encounter_level ** random.uniform(1.26, 1.27)
            base_defence = encounter_level ** random.uniform(1.26, 1.27)
        elif (encounter_level > 50 and encounter_level <= 60):
            base_attack = encounter_level ** random.uniform(1.27, 1.28)
            base_defence = encounter_level ** random.uniform(1.27, 1.28)
        elif (encounter_level > 60 and encounter_level <= 70):
            base_attack = encounter_level ** random.uniform(1.28, 1.29)
            base_defence = encounter_level ** random.uniform(1.28, 1.29)
        else: 
            base_attack = encounter_level ** random.uniform(1.29, 1.3)
            base_defence = encounter_level ** random.uniform(1.29, 1.3)

        # Calculate monster attack and defence based on the difficulty multiplier
        monster_attack = int(base_attack)
        monster_defence = int(base_defence)
    
        return encounter_level, monster_attack, monster_defence    
    

    async def fetch_monster_image(self, encounter_level: int):
        """Fetches a monster image from the monsters.csv file based on the encounter level."""
        # Path to the CSV file
        csv_file_path = os.path.join(os.path.dirname(__file__), '../assets/monsters.csv')
        
        monsters = []
        
        # Reading the CSV file and collecting monsters
        try:
            with open(csv_file_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    monster_name = row['name']
                    monster_url = row['url']
                    monster_level = int(row['level']) * 10
                    flavor_txt = row['flavor']
                    monsters.append((monster_name, monster_url, monster_level, flavor_txt))
        except Exception as e:
            print(f"Error reading monsters.csv: {e}")
            return "Commoner", "https://i.imgur.com/v1BrB1M.png", "stares pleadingly at"  # Fallback image
        if encounter_level == 999:
            print('Fetching rare monster image')
            selected_monsters = [monster for monster in monsters if 900 <= monster[2] <= 100000000]
            print(selected_monsters)
        else:
            min_level = max(1, encounter_level - 20)  # Select 20 levels below
            max_level = min(100, encounter_level + 20)      # Select 20 levels above
            selected_monsters = [monster for monster in monsters if min_level <= monster[2] <= max_level]
        if not selected_monsters:
            return "Commoner", "https://i.imgur.com/v1BrB1M.png", "stares pleadingly at"  # Fallback if no monsters are found

        # Randomly select a monster from the filtered list
        selected_monster = random.choice(selected_monsters)
        return selected_monster[0], selected_monster[1], selected_monster[3]  # Return the name, URL, flavor

    async def update_experience(self, user_id: str, server_id: str, xp_award: int, message, embed) -> None:
        """Update the user's experience and handle leveling up."""
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_name = existing_user[3]
        current_level = existing_user[4]
        current_exp = existing_user[5]
        current_atk = existing_user[9]
        current_def = existing_user[10]
        current_mhp = existing_user[12]
        # Experience table
        exp_table = self.load_exp_table()

        new_exp = current_exp + xp_award
        level_up = False
        #print(f'Currently level {current_level} with exp {current_exp}, new exp is {new_exp}')
        exp_threshold = exp_table["levels"][str(current_level)]
        #print(f'exp threshold is {exp_threshold}')
        if current_level < 100 and new_exp >= exp_threshold:
            # print(f'Level up')
            current_level += 1
            level_up = True

        if level_up:
            attack_increase = random.randint(1, 5)
            defence_increase = random.randint(1, 5)
            hp_increase = random.randint(1, 5)
            embed.add_field(name="Level Up! 🎉", value=f"{player_name} has reached level **{current_level}**!")
            new_atk = current_atk + attack_increase
            new_def = current_def + defence_increase
            new_mhp = current_mhp + hp_increase
            if current_level > 0 and current_level % 10 == 0 and current_level <= 100:  # Check levels 10, 20, 30, etc.
                #print('Awarding 2 passive points for this level up since it fits the criteria')
                passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
                await self.bot.database.set_passive_points(user_id, server_id, passive_points + 2)
                embed.add_field(name="2 passive points gained!", 
                            value=(f"Use /passives to allocate them."), 
                            inline=False)
            embed.add_field(name="Stat increases:", 
                                     value=(f"⚔️ **Attack:** {new_atk} (+{attack_increase})\n"
                                            f"🛡️ ** Defense:** {new_def} (+{defence_increase})\n"
                                            f"❤️ **Hit Points:** {new_mhp} (+{hp_increase})"), inline=False)
            await message.edit(embed=embed)

            # print(f'Update {user_id} stats')
            await self.bot.database.update_player_hp(user_id, 
                                                    existing_user[11] + hp_increase)  # index 11: current hp
            await self.bot.database.update_player_max_hp(user_id, 
                                                        existing_user[12] + hp_increase)  # index 12: max hp
            await self.bot.database.increase_attack(user_id, attack_increase)
            await self.bot.database.increase_defence(user_id, defence_increase)
            await self.bot.database.increase_level(user_id)
            new_exp -= exp_table["levels"][str(current_level - 1)]
            
        print(f'Update {user_id} experience to {new_exp}')
        await self.bot.database.update_experience(user_id, new_exp)


    @app_commands.command(name="duel", description="Challenge another user to a PvP duel.")
    async def pvp(self, interaction: Interaction, member: discord.Member, gold_amount: int) -> None:
        user_id = str(interaction.user.id)
        challenged_user_id = str(member.id)

        # Fetch user gold
        existing_user = await self.bot.database.fetch_user(user_id, interaction.guild.id)
        challenged_user = await self.bot.database.fetch_user(challenged_user_id, interaction.guild.id)
        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        if existing_user and challenged_user:
            challenged_gold = challenged_user[6]
            challenger_gold = existing_user[6]

            if challenger_gold < gold_amount:
                await interaction.response.send_message(
                    f"You do not have enough gold to initiate this challenge!",
                    ephemeral=True)
                return

            if challenged_gold < gold_amount:
                await interaction.response.send_message(
                    f"{member.name} does not have enough gold to accept the challenge!",
                    ephemeral=True)
                return
            
            if gold_amount <= 0:
                await interaction.response.send_message(
                    "You cannot challenge with zero or negative gold.",
                    ephemeral=True)
                return

            # Create the challenge embed
            embed = discord.Embed(
                title="PvP Challenge!",
                description=f"{interaction.user.mention} has challenged {member.mention} for **{gold_amount:,} gold**!\n"
                            f"React with ✅ to accept the challenge!",
                color=0x00FF00,
            )
            embed.set_image(url="https://i.imgur.com/z20wfJO.jpeg")
            await interaction.response.send_message(embed=embed)
            message: Message = await interaction.original_response()
            await message.add_reaction("✅")  # Accept Challenge
            await message.add_reaction("❌")  # Decline Challenge
            self.bot.state_manager.set_active(user_id, "duel")

            def check(reaction, user):
                return user == member and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == message.id

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                if str(reaction.emoji) == "✅":
                    if self.bot.state_manager.is_active(challenged_user_id):
                        await interaction.followup.send("You cannot accept this duel. Please finish all other interactions.")
                        await message.delete()
                        self.bot.state_manager.clear_active(user_id)
                        return
                else:
                    self.bot.state_manager.clear_active(user_id)
                    await message.delete()
                    return
            except asyncio.TimeoutError:
                self.bot.state_manager.clear_active(user_id)
                await message.delete()
                return

            # Start the PvP duel
            player = existing_user[3]
            opponent = challenged_user[3]
            await self.start_duel(interaction, user_id, challenged_user_id, gold_amount, member, player, opponent, message)
        else:
            await interaction.response.send_message("There was an error fetching user data.")

    async def start_duel(self, interaction: Interaction, 
                         challenger_id: str, challenged_id: str, 
                         gold_amount: int, member: discord.Member,
                         player: str, opponent: str, message) -> None:
        self.bot.state_manager.set_active(challenged_id, "duel")
        await message.clear_reactions()
        # Initial HP for both players
        challenger_hp = 100
        challenged_hp = 100
        print(f"Challenger: {challenger_id}, Challenged: {challenged_id}")
        print(f"Challenger name: {player}, Challenged name: {opponent}")
        # Determine turn order with a coin flip
        turn_order = random.choice([challenger_id, challenged_id])
        name = ''
        if turn_order == challenger_id:
            starter = challenger_id
            name = player
        else:
            starter = challenged_id
            name = opponent

        # Start the combat embed
        embed = discord.Embed(
            title="PvP Duel Begins!",
            color=0x00FF00
        )
        embed.set_thumbnail(url="https://i.imgur.com/z20wfJO.jpeg")
        embed.add_field(name=f"{name} has won the coin toss!", value="Beginning in 3...", inline=False)
        embed.add_field(name=f"{player}'s HP ❤️", value=challenger_hp, inline=True)
        embed.add_field(name=f"{opponent}'s HP ❤️", value=challenged_hp, inline=True)
        embed.add_field(name=f"Waiting for input", value="Pick an action!", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(1)
        embed.set_field_at(0, name=f"{name} has won the coin toss!", value="Beginning in 2...", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(1)
        embed.set_field_at(0, name=f"{name} has won the coin toss!", value="Beginning in 1...", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(1)
        embed.set_field_at(0, name=f"{name} has won the coin toss!", value="FIGHT!", inline=False)
        await message.edit(embed=embed)
        # Initiate combat rounds
        current_player = starter
        if (turn_order == challenger_id):
            name = player
        else:
            name = opponent

        await message.add_reaction("⚔️")  # Attack
        await message.add_reaction("💖")  # Heal

        while challenger_hp > 0 and challenged_hp > 0:
            embed.set_field_at(0, name=f"It's **{name}**'s turn!", value="Do you choose to HIT ⚔️ or HEAL 💖? ", inline=False)
            await message.edit(embed=embed)

            def action_check(reaction, user):
                return (
                    user.id == int(current_player) and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["⚔️", "💖"]
                )

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=action_check)

                if str(reaction.emoji) == "⚔️":
                    #print('Attack is picked')
                    
                    # Introduce a chance to miss
                    if random.randint(1, 100) <= 30:  # 30% chance to miss
                        response_message = f"{name}'s attack 💨 misses! "
                    else:
                        damage = self.calculate_damage(challenger_hp if current_player == challenger_id else challenged_hp)
                        if current_player == challenger_id:
                            challenged_hp -= damage
                            response_message = f"{name} attacked for 💥 **{damage}**!"
                            embed.set_field_at(2, name=f"{opponent}'s HP ❤️", value=challenged_hp, inline=True)
                        else:
                            challenger_hp -= damage
                            response_message = f"{name} attacked for 💥 **{damage}**!"
                            embed.set_field_at(1, name=f"{player}'s HP ❤️", value=challenger_hp, inline=True)
                else:
                    # Handle Heal
                    heal_amount = 20
                    if current_player == challenger_id:
                        challenger_hp = min(challenger_hp + heal_amount, 100)  # Heal up to max HP
                        response_message = f"{name} healed for **{heal_amount}**."
                        embed.set_field_at(1, name=f"{player}'s HP ❤️", value=challenger_hp, inline=True)
                    else:
                        challenged_hp = min(challenged_hp + heal_amount, 100)
                        response_message = f"{name} healed for **{heal_amount}**."
                        embed.set_field_at(2, name=f"{opponent}'s HP ❤️", value=challenged_hp, inline=True)
                await message.remove_reaction(reaction.emoji, user)
                embed.set_field_at(3, name=f"Result", value=response_message, inline=False)
                await asyncio.sleep(1)

                # Switch players
                #print(f'Switch players from {current_player}')
                current_player = challenged_id if current_player == challenger_id else challenger_id
                #print(f'to {current_player}')
                if (current_player == challenger_id):
                    name = player
                else:
                    name = opponent

            except asyncio.TimeoutError:
                timeout = (f"{name} took too long to decide. The duel has ended and they forfeit their gold.")
                embed.add_field(name=f"Timed out!", value=timeout, inline=False)
                if (current_player == challenger_id):
                    await self.bot.database.add_gold(challenged_id, gold_amount)
                    await self.bot.database.add_gold(challenger_id, -gold_amount)
                    print(f'Awarded {challenged_id} with gold')
                else: 
                    await self.bot.database.add_gold(challenger_id, gold_amount)
                    await self.bot.database.add_gold(challenged_id, -gold_amount)
                    print(f'Awarded {challenger_id} with gold')
                self.bot.state_manager.clear_active(challenger_id)
                self.bot.state_manager.clear_active(challenged_id)
                await message.edit(embed=embed)
                return

        # Duel outcome
        winner, loser = (challenger_id, challenged_id) if challenged_hp <= 0 else (challenged_id, challenger_id)
        #print(f'winner: {winner}, loser: {loser}')
        await self.bot.database.add_gold(winner, gold_amount)
        await self.bot.database.add_gold(loser, -gold_amount)
        if (winner == challenger_id):
            name = player
            loser_name = opponent
        else:
            name = opponent
            loser_name = player
        self.bot.state_manager.clear_active(challenger_id)
        self.bot.state_manager.clear_active(challenged_id)
        victory = (f"{name} slays {loser_name} with a 💥 {damage}!\nThey receive **{gold_amount * 2} gold**!")
        embed.add_field(name=f"{name} is victorious!", value=victory, inline=False)
        await message.edit(embed=embed)


    def calculate_damage(self, current_hp: int) -> int:
        """Calculate damage based on HP, using a modified version of the Dharok's effect."""
        
        if current_hp <= 0:
            return 0  # No damage if HP is 0 or less

        # Set max hit to 25 when current HP is at 100, otherwise scale normally
        if current_hp == 100:
            max_hit = 25
        else:
            max_hit = 120 * (100 - current_hp) / 100  # This scales max_hit with current HP

        # Ensure max_hit is at least 25 for calculations
        max_hit = max(25, int(max_hit))

        # Random damage is based on the new max_hit
        damage = random.randint(1, max_hit)

        return damage

async def setup(bot) -> None:
    await bot.add_cog(Combat(bot))
