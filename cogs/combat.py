import aiohttp
import random
import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.tasks import asyncio
from discord.ext import tasks
import math
import csv
import os

class Combat(commands.Cog, name="combat"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.prefixes = self.load_list("assets/items/pref.txt")
        self.weapon_types = self.load_list("assets/items/wep.txt")
        self.suffixes = self.load_list("assets/items/suff.txt")

    def load_list(self, filepath: str) -> list:
        """Load a list from a text file."""
        with open(filepath, "r") as file:
            return [line.strip() for line in file.readlines()]
        
    async def generate_loot(self, user_id: str, server_id: str, encounter_level: int) -> str:
        """Generate a unique loot item."""
        prefix = random.choice(self.prefixes)
        weapon_type = random.choice(self.weapon_types)
        suffix = random.choice(self.suffixes)
        item_name = f"{prefix} {weapon_type} {suffix}"

        modifiers = []
        attack_modifier = 0
        defence_modifier = 0
        rarity_modifier = 0

        if random.randint(0, 100) < 80:  # 80% chance for attack roll
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

    @commands.hybrid_command(name="combat", description="Engage in combat.")
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def combat(self, context: Context):
        await context.defer()
        user_id = str(context.author.id)
        server_id = str(context.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)

        if existing_user:
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
            current_passive = ""
            followers_count = await self.bot.database.fetch_followers(player_ideology)
            equipped_item = await self.bot.database.get_equipped_item(user_id)
            if equipped_item:
                current_passive = equipped_item[7]
                player_attack += equipped_item[4]
                player_defence += equipped_item[5]
                player_rar += equipped_item[6]

            encounter_level, monster_attack, monster_defence = self.generate_encounter(user_level)
            if (user_level < 5):
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
                embed.add_field(name="Monster HP", value=monster_hp, inline=True)
                embed.add_field(name="Your HP", value=player_hp, inline=True)
                # CALCULATE POLISHED PASSIVE
                polished_passives = ["polished", "honed", "gleaming", "tempered", "flaring"]
                if (current_passive in polished_passives):
                    value = polished_passives.index(current_passive)
                    defence_reduction = (value + 1) * 5  # 5% defense reduction per tier
                    monster_defence_reduction = int(monster_defence * defence_reduction / 100)
                    print(f"Polish passive reduces monster's defense by {monster_defence_reduction}.")
                    embed.add_field(name="Weapon passive", 
                                    value=(f"Your **{current_passive}** weapon shines with anticipation!\n"
                                            f"It reduces the {monster_name}'s defence by {defence_reduction}%.\n"),
                                    inline=False)
                    monster_defence -= monster_defence_reduction

                # CALCULATE STURDY PASSIVE (Placeholder example for future implementation)
                sturdy_passives = ["sturdy", "reinforced", "thickened", "impregnable", "impenetrable"]
                if (current_passive in sturdy_passives):
                    value = sturdy_passives.index(current_passive)
                    # Example behavior for Sturdy (currently unspecified)
                    defence_bonus = (1 + value) * 3  # This can be defined later based on combat mechanics
                    print(f"Sturdy passive increases defense by {defence_bonus}.")
                    embed.add_field(name="Weapon passive", 
                                    value=(f"Your **{current_passive}** weapon strengthens your resolve!\n"
                                            f"You gain {defence_bonus} defence.\n"),
                                    inline=False)
                    player_defence += defence_bonus

                accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
                if (current_passive in accuracy_passives):
                    has_passive = True
                    value = (1 + accuracy_passives.index(current_passive)) * 3
                    embed.add_field(name="Accuracy", 
                        value=(f"Your **{current_passive}** weapon glints with precision. "
                               f"It boosts your accuracy by **{value}%**!"), 
                        inline=False)

                message = await context.send(embed=embed)
                start_combat = True
            except Exception as e:
                await context.send(f"The servers are busy handling another request. Try again.")
                return

            if start_combat:
                while True:
                    await message.clear_reactions()
                    reactions = ["⚔️", "🩹", "⏩", "🏃"]
                    await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))

                    def check(reaction, user):
                        return (user == context.author 
                                and reaction.message.id == message.id 
                                and str(reaction.emoji) in ["⚔️", "🩹", "⏩", "🏃"])

                    try:
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)

                        if str(reaction.emoji) == "⚔️":
                            heal_message = ""
                            opportunity = False
                            monster_hp, attack_message = await self.player_turn(embed, player_attack, monster_hp, 
                                                                                monster_defence, followers_count, player_name, 
                                                                                ascension_level, monster_name, current_passive)
                            player_hp, monster_message = await self.monster_turn(embed, monster_attack, player_hp, 
                                                                                player_defence, followers_count, monster_name, 
                                                                                user_id, current_passive, flavor_txt)
                            await self.bot.database.update_player_hp(user_id, player_hp)

                            # Check if the player is defeated
                            if player_hp <= 0:
                                total_damage_dealt = award_xp - monster_hp
                                embed.add_field(name=player_name, value=attack_message, inline=False)
                                embed.add_field(name=monster_name, value=monster_message, inline=False)
                                await self.handle_defeat(user_id, message, monster_name,
                                                         total_damage_dealt, player_name, award_xp, server_id)
                                break
                            # CALCULATE OVERWHELM PASSIVE (culling strike)
                            overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
                            # Check if the monster is defeated
                            if (current_passive in overwhelm_passives):
                                value = overwhelm_passives.index(current_passive)
                                culling_strike = (value + 1) * 5  # 5% culling per tier
                                if monster_hp <= (award_xp * culling_strike / 100):
                                    print('overwhelmed')
                                    embed.add_field(name=player_name, value=attack_message, inline=False)
                                    embed.add_field(name=monster_name, value=monster_message, inline=False)
                                    await self.handle_victory(encounter_level, user_id, server_id, 
                                                            player_name, monster_name, context, 
                                                            award_xp, player_rar, player_hp,
                                                            message, user_level, True)
                                    break
                            else:
                                if monster_hp <= 0:
                                    embed.add_field(name=player_name, value=attack_message, inline=False)
                                    embed.add_field(name=monster_name, value=monster_message, inline=False)
                                    await self.handle_victory(encounter_level, user_id, server_id, 
                                                            player_name, monster_name, context, 
                                                            award_xp, player_rar, player_hp,
                                                            message, user_level, False)
                                    break

                        elif str(reaction.emoji) == "⏩":
                            end_battle, end_php, end_mhp = await self.auto_battle(
                                                    embed, context, encounter_level,
                                                    player_attack, monster_hp, monster_attack,
                                                    monster_defence, player_defence,
                                                    followers_count, player_name, user_id, 
                                                    server_id, monster_name, player_hp, 
                                                    message, award_xp, ascension_level, 
                                                    player_rar, current_passive, user_level,
                                                    flavor_txt, player_max_hp)
                            if end_battle:
                                break
                            else:
                                player_hp = end_php
                                monster_hp = end_mhp 
                                embed.add_field(name="Auto battle",
                                                value="Player HP < 10%, auto-battle paused!",
                                                inline=False)
                        elif str(reaction.emoji) == "🩹":
                            player_hp, potions, heal_message = await self.heal(existing_user, player_hp, potions, 
                                                        user_id, server_id, context, embed,
                                                        player_name)
                            if random.random() < 0.5:
                                opportunity = True
                                damage_taken = random.randint(1, 6) 
                                # print(f'Monster opportune strikes for {damage_taken}')
                                new_player_hp = max(1, player_hp - damage_taken)
                                player_hp = new_player_hp
                                await self.bot.database.update_player_hp(user_id, player_hp)
                                opportunity_message = f"The monster took an opportunity strike, dealing **{damage_taken}** damage!"
                                embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                                embed.set_field_at(1, name="Your ❤️ HP", value=player_hp, inline=True)
                                await message.edit(embed=embed)
                            
                        elif str(reaction.emoji) == "🏃":
                            if random.random() < 0.5:
                                opportunity = True
                                damage_taken = random.randint(1, 6) 
                                # print(f'Monster opportune strikes for {damage_taken}')
                                new_player_hp = max(1, player_hp - damage_taken)
                                player_hp = new_player_hp
                                await self.bot.database.update_player_hp(user_id, player_hp)
                                opportunity_message = (f"As you run away, the {monster_name} savagely swipes, "
                                                       f" grazing you for **{damage_taken}** damage!")
                                embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                                embed.set_field_at(1, name="Your ❤️ HP", value=player_hp, inline=True)
                                await message.edit(embed=embed)
                            else:
                                embed.add_field(name="Escape", value="You get away safely!", inline=False)
                                await message.edit(embed=embed)
                            break

                        if len(embed.fields) > 5:
                            embed.clear_fields()
                            embed.add_field(name="Monster 🐲 HP", value=monster_hp, inline=True)
                            embed.add_field(name="Your ❤️ HP", value=player_hp, inline=True)
                            if attack_message:
                                embed.add_field(name=player_name, value=attack_message, inline=False)
                            if monster_message:
                                embed.add_field(name=monster_name, value=monster_message, inline=False)
                            if heal_message:
                                embed.add_field(name="Heal", value=heal_message, inline=False)
                            if opportunity:
                                embed.add_field(name=f"{monster_name}", value=opportunity_message, inline=False)
                        else:
                            embed.set_field_at(0, name="Monster 🐲 HP", value=monster_hp, inline=True)
                            embed.set_field_at(1, name="Your ❤️ HP", value=player_hp, inline=True)
                        await message.clear_reactions()
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
                                                    f" lazily grazing you for **{damage_taken}** damage before leaving.")
                            embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                            embed.set_field_at(1, name="Your ❤️ HP", value=player_hp, inline=True)
                            await message.edit(embed=embed)
                        else:
                            embed.add_field(name=monster_name, 
                                            value=f"The {monster_name} loses interest, you failed to grasp the moment.", 
                                            inline=False)
                            await message.edit(embed=embed)
                        break
                await message.clear_reactions()
        else:
            await context.send("You are not registered with the 🏦 Adventurer's guild. Please /register first before engaging in combat.")

    async def player_turn(self, embed, player_attack, monster_hp, 
                          monster_defence, followers_count, player_name, 
                          ascension_level, monster_name, current_passive):
        attack_message = ""
        echo_damage = 0
        has_passive = False
        accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
        if (current_passive in accuracy_passives):
            has_passive = True
            value = (1 + accuracy_passives.index(current_passive)) * 3
            embed.add_field(name="Accuracy", 
                value=f"Your **{current_passive}** passive boosts your accuracy by **{value}%**!", 
                inline=False)
            hit_chance = self.calculate_hit_chance(player_attack, monster_defence, value)
        else:
            hit_chance = self.calculate_hit_chance(player_attack, monster_defence, 0)
        miss_chance = 100 - (hit_chance * 100)
        attack_roll = random.randint(0, 100) # Roll between 0 and 100
        # print(f'{miss_chance}% to miss. Player rolls {attack_roll}.')
        # CALCULATE CRIT PASSIVE
        adjusted_value = 0
        crit_passives = ["piercing", "keen", "incisive", "puncturing", "penetrating"]
        if (current_passive in crit_passives):
            has_passive = True
            value = crit_passives.index(current_passive)
            adjusted_value = (value + 1) * 3 # actual crit rate bonus
        if attack_roll > (95 - adjusted_value):  # Critical hit chance
            max_hit = self.calculate_max_hit(followers_count, player_attack, ascension_level)
            actual_hit = random.randint(1, max_hit) * 2
            if actual_hit > monster_hp:
                actual_hit = monster_hp
            # print(f'Critical scored: {monster_hp} - critical {actual_hit}')
            monster_hp -= actual_hit
            if (adjusted_value > 0):
                attack_message = (f"Your **{current_passive}** weapon allows you to 🗡️ slip through its defenses.\n" 
                                  f"You crit for 💥 **{actual_hit}** damage!")
            else:
                attack_message = f"Critical! You 🗡️ pierce through monster's defenses, hitting for 💥 **{actual_hit}** damage!"
        elif attack_roll >= miss_chance:
            # CALCULATE BURNING PASSIVE
            burning_passives = ["burning", "flaming", "scorching", "incinerating", "carbonising"]
            if (current_passive in burning_passives):
                has_passive = True
                value = burning_passives.index(current_passive)
                burning_damage = value + 1  # Additional d6 for burning
                # print(f"Burning passive adds {burning_damage}d6 to max hit.")
                max_hit = self.calculate_max_hit(followers_count, player_attack + burning_damage, ascension_level)
                attack_message = (f"Your **{current_passive}** weapon burns bright!\n"
                                  f"It adds **{burning_damage}** roll(s) to your attack.\n")
                                  
            else:
                max_hit = self.calculate_max_hit(followers_count, player_attack, ascension_level)

            # CALCULATE SPARKING PASSIVE
            sparking_damage = 0
            sparking_passives = ["sparking", "shocking", "discharging", "electrocuting", "vapourising"]
            if (current_passive in sparking_passives):
                has_passive = True
                value = sparking_passives.index(current_passive)
                sparking_damage = value + 1  # Increase minimum hit by tier
                rolls = [random.randint(1, 6) for _ in range(sparking_damage)]
                final_spark_damage = sum(rolls)
                # print(f"Shock passive adds {final_spark_damage} additional damage to lowest hit.")
                attack_message = (f"Your **{current_passive}** weapon surges with lightning!\n"
                                  f"It adds **{final_spark_damage}** damage to your hit.\n")
                
                min_damage = max(final_spark_damage, 1)  # Minimum damage must be at least final_spark_damage
                if monster_hp <= min_damage:
                    actual_hit = monster_hp  # If applying min damage would bring it to zero, hit for remaining monster_hp
                else:
                    actual_hit = random.randint(min_damage, max_hit + min_damage)  # Random hit within the desired range
                    if (actual_hit > monster_hp):
                        actual_hit = monster_hp
                # print(f'Lightning hit: {monster_hp} - {actual_hit}')
            else:
                echo_hit = False
                actual_hit = random.randint(1, max_hit)
                echo_passives = ["echo", "echoo", "echooo", "echoooo", "echoes"]
                if (current_passive in echo_passives):
                    has_passive = True
                    value = echo_passives.index(current_passive)
                    echo_multiplier = (value + 1) / 10  # Increase minimum hit by tier
                    echo_damage = 1 + int(actual_hit * echo_multiplier)
                    actual_hit += echo_damage
                    echo_hit = True
                if (actual_hit > monster_hp):
                    actual_hit = monster_hp

            attack_message += f"You ⚔️ hit the {monster_name} for 💥 **{actual_hit - echo_damage}** damage!"
            if (echo_hit):
                attack_message += f"\nYour {current_passive} weapon echoes the hit, dealing an additional {echo_damage} damage."
            # print(f'Normal hit: {monster_hp} - {actual_hit}')
            monster_hp -= actual_hit

        else:
            # CALCULATE POISONOUS PASSIVE
            poisonous_passives = ["poisonous", "noxious", "venomous", "toxic", "lethal"]
            if (current_passive in poisonous_passives):
                has_passive = True
                value = poisonous_passives.index(current_passive)
                poison_damage_dice = value + 3  # Additional d6 damage on misses
                # print(f"Poison passive deals {poison_damage_dice}d6 poison damage on misses.")
                poison_rolls = [random.randint(1, 6) for _ in range(poison_damage_dice)]
                total_poison_damage = sum(poison_rolls)
                if total_poison_damage >= monster_hp:
                    total_poison_damage = monster_hp
                # print(f'Miss poison hit: {monster_hp} - {poison_damage}')
                monster_hp -= total_poison_damage
                attack_message = f"You miss, but your weapon still inflicts {total_poison_damage} poison 🐍 damage."
            else:
                attack_message = "Your attack 💨 misses!"

        embed.add_field(name=player_name, value=attack_message, inline=False)
        return monster_hp, attack_message  # Return both the updated monster HP and attack message
    
    async def monster_turn(self, embed, monster_attack, player_hp, 
                           player_defence, followers_count, 
                           monster_name, user_id, current_passive, flavor_txt):
        monster_miss_chance = 100 - int(self.calculate_monster_hit_chance(monster_attack, player_defence) * 100)
        monster_attack_roll = random.randint(0, 100) # Roll between 0 and 100
        # (f'{monster_miss_chance}% to miss. Monster rolls {monster_attack_roll}.')
        if monster_attack_roll >= monster_miss_chance:  # Monster attack hits
            damage_taken = self.calculate_damage_taken(monster_attack, player_defence)
            # print(f"Monster hits, player takes damage: {player_hp} - {damage_taken}")
            player_hp -= damage_taken
            monster_message = f"The {monster_name} ⚔️ {flavor_txt} you for 💥 **{damage_taken}** damage!"
        else:
            # print(f"Monster misses")
            monster_message = f"The {monster_name} 💨 missed!"

        embed.add_field(name=monster_name, value=monster_message, inline=False)
        return player_hp, monster_message  # Return the player's HP after monster attack
    
    async def heal(self, existing_user, player_hp, potions, 
                   user_id, server_id, context, 
                   embed, player_name):

        if potions <= 0:
            # print('Unable to heal, out of potions')
            heal_message = "You have no potions left to heal!"
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
        
        heal_message = f"You healed for **{total_heal}** HP! You have {potions - 1} potions left."
        embed.add_field(name=player_name, value=heal_message, inline=False)
        potions -= 1
        return new_hp, potions, heal_message

    async def auto_battle(self, embed, context, encounter_level,
                            player_attack, monster_hp, monster_attack,
                            monster_defence, player_defence,
                            followers_count, player_name, user_id, 
                            server_id, monster_name, player_hp, 
                            message, award_xp, ascension_level,
                            player_rar, current_passive, user_level,
                            flavor_txt, player_max_hp):
        minimum_hp = int(player_max_hp / 10)
        while player_hp > minimum_hp and monster_hp > 0:
            monster_hp, attack_message = await self.player_turn(embed, player_attack, monster_hp, 
                                                monster_defence, followers_count, 
                                                player_name, ascension_level, monster_name, 
                                                current_passive)
            overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
            if (current_passive in overwhelm_passives):
                value = overwhelm_passives.index(current_passive)
                culling_strike = (value + 1) * 5  # 5% culling per tier
                if monster_hp <= (award_xp * culling_strike / 100):
                    print('overwhelmed')
                    await self.handle_victory(encounter_level, user_id, server_id, 
                        player_name, monster_name, context, 
                        award_xp, player_rar, player_hp,
                        message, user_level, True)
                    return True, player_hp, monster_hp
            else:
                if monster_hp <= 0:
                    embed.add_field(name=monster_name, value=attack_message, inline=False)
                    await self.handle_victory(encounter_level, user_id, server_id, 
                                            player_name, monster_name, context, 
                                            award_xp, player_rar, player_hp,
                                            message, user_level, False)
                    return True, player_hp, monster_hp

            player_hp, monster_message = await self.monster_turn(embed, monster_attack, player_hp, 
                                                player_defence, followers_count, 
                                                monster_name, user_id, current_passive, flavor_txt)
            await self.bot.database.update_player_hp(user_id, player_hp)
            
            if player_hp <= 0:
                total_damage_dealt = award_xp - monster_hp
                embed.add_field(name=monster_name, value=monster_message, inline=False)
                await self.handle_defeat(user_id, message,
                                         monster_name, total_damage_dealt,
                                         player_name, award_xp, server_id)
                return True, player_hp, monster_hp

            if len(embed.fields) > 5:
                embed.clear_fields()
                embed.add_field(name="Monster 🐲 HP", value=monster_hp, inline=True)
                embed.add_field(name="Your ❤️ HP", value=player_hp, inline=True)
                embed.add_field(name=player_name, value=attack_message, inline=False)
                embed.add_field(name=monster_name, value=monster_message, inline=False)
            else:
                embed.set_field_at(0, name="Monster 🐲 HP", value=monster_hp, inline=True)
                embed.set_field_at(1, name="Your ❤️ HP", value=player_hp, inline=True)

            await message.edit(embed=embed)
            await asyncio.sleep(1)
        return False, player_hp, monster_hp
        #await message.clear_reactions()

    async def handle_victory(self, encounter_level, user_id, server_id, 
                             player_name, monster_name, context, award_xp,
                             player_rar, player_hp, message, user_level, isCulled):
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
        reward_scale = (encounter_level - user_level) / 10 # Bonus rewards based on level differential
        rarity =  (player_rar / 100) # Player rarity
        xp_award = int(award_xp * 1.4)
        drop_chance = 90 # Base 10% drop chance
        loot_roll = random.randint(1, 100)
        final_loot_roll = loot_roll
        if (player_rar > 0):
            final_loot_roll = int(loot_roll + (10 * rarity))
            print(f'User has {rarity}, multiplier on {loot_roll} to {final_loot_roll}')
        
        print(f'User rolls {final_loot_roll}, beat {drop_chance} to get item')
        gold_award = int((encounter_level ** random.uniform(1.4, 1.6)) * (1 + (reward_scale ** 1.3)))
        if (player_rar > 0):
            final_gold_award = int(gold_award * (1.5 + rarity))
        else:
            final_gold_award = gold_award
        victory_embed.add_field(name="📚 Experience Earned", value=f"{xp_award:,} XP")
        victory_embed.add_field(name="💰 Gold Earned", value=f"{final_gold_award:,} GP")
        items = await self.bot.database.fetch_user_items(user_id)
        if (final_loot_roll >= drop_chance):
            if (len(items) > 5):
                victory_embed.add_field(name="✨ Loot", value=f"Inventory full!")
            else:
                (item_name, attack_modifier, 
                defence_modifier, rarity_modifier, 
                loot_description) = await self.generate_loot(user_id, server_id, encounter_level)
                if (item_name != "rune"):
                    await self.bot.database.create_item(user_id, item_name, encounter_level, 
                                                        attack_modifier, defence_modifier, rarity_modifier)
                victory_embed.add_field(name="✨ Loot", value=f"{loot_description}")
        else:
            victory_embed.add_field(name="✨ Loot", value=f"None")
        
        await message.edit(embed=victory_embed)
        await self.update_experience(user_id, server_id, xp_award, context) 
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
        defeat_embed.add_field(name="🪽 Redemption 🪽", value="(You find yourself revived with 1 hp.)")
        await message.edit(embed=defeat_embed)
        player_hp = 1
        await self.bot.database.update_player_hp(user_id, player_hp)
        await self.bot.database.update_experience(user_id, new_exp)
    
    def calculate_max_hit(self, followers_count, attack_level, ascension_level):
        """Calculate the maximum hit based on the number of followers and attack level"""
        #rolls_count = max(1, followers_count // 100) + (ascension_level * 10)
        #print(f"{followers_count} followers for {rolls_count} additional rolls of dmg")
        #random_rolls = [random.randint(1, 6) for _ in range(rolls_count)]
        #total_follower_bonus = sum(random_rolls)
        max_hit = attack_level
        #print(f"Max hit is Attack level: {attack_level} + {total_follower_bonus} = {max_hit}")
        return int(max_hit)

    def calculate_hit_chance(self, player_attack, monster_defence, accuracy):
        """Calculate the chance to hit based on the player's attack and monster's defence."""
        difference = player_attack - monster_defence
        additional_hit_chance = int(accuracy / 100)
        # If the player_attack is higher, calculate the hit chance normally
        if difference > 0:
            hit_chance = 0.6 + (difference / 100)  # Starting at 60%, increase by 1% per difference in level
            if (hit_chance >= 0.8):
                hit_chance = 0.8
            # print(f'Player attack higher than monster defence, hit chance: {hit_chance}')
            return hit_chance + additional_hit_chance
        else:
            # If the monster's defence is higher or equal, hit chance is 60%
            # print(f'Monster defence higher than player attack, hit chance: {hit_chance}')
            return 0.6 + additional_hit_chance
    
    def calculate_monster_hit_chance(self, monster_attack, player_defence):
        """Calculate the player's chance to be hit based on stats."""
        difference = monster_attack - player_defence
        # If the monster_attack is higher, calculate the hit chance normally
        # print(f"M.ATK {monster_attack} - P.DEF {player_defence} = {difference}")
        if difference > 0:
            # Starting at 50%, increase based on the difference
            # print(f'Positive monster hit chance: {hit_chance}')
            return 0.5
        else:
            # If the monster's attack is lower
            # The lower the attack, the lower the hit chance
            hit_chance = 0.5 - (difference / 100)  # Starting at 50%, reduce by 1% until 30%
            if hit_chance <= 0.3:
                hit_chance = 0.3
            # print(f'Negative monster hit chance: {hit_chance}')
            return hit_chance  # 50% base chance to  get hit, or the calculated hit chance, whichever is lower
        
    def calculate_damage_taken(self, monster_attack, player_defence):
        """Calculate damage taken based on monster's attack and player's defense."""
        # Calculate the difference
        difference = monster_attack - player_defence
        # print(f"M.ATK {monster_attack} - P.DEF {player_defence} = {difference}")

        # Base damage (1d6)
        damage = random.randint(1, 6)  # Roll 1d6
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
            return "Commoner", "https://i.imgur.com/v1BrB1M.png"  # Fallback image

        # Define level range for filtering
        min_level = max(1, encounter_level - 20)  # Select 20 levels below
        max_level = min(100, encounter_level + 20)      # Select 20 levels above
        selected_monsters = [monster for monster in monsters if min_level <= monster[2] <= max_level]
        #print(selected_monsters)
        if not selected_monsters:
            return "Commoner", "https://i.imgur.com/v1BrB1M.png"  # Fallback if no monsters are found

        # Randomly select a monster from the filtered list
        selected_monster = random.choice(selected_monsters)
        return selected_monster[0], selected_monster[1], selected_monster[3]  # Return the name, URL, flavor

    async def update_experience(self, user_id: str, server_id: str, xp_award: int, context) -> None:
        """Update the user's experience and handle leveling up."""
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_name = existing_user[3]
        current_level = existing_user[4]
        current_exp = existing_user[5]
        current_atk = existing_user[9]
        current_def = existing_user[10]
        current_mhp = existing_user[12]
        # Experience table
        exp_table = {
            1:42,
            2:111,
            3:143,
            4:181,
            5:219,
            6:708,
            7:802,
            8:907,
            9:1012,
            10:1122,
            11:1555,
            12:1705,
            13:1843,
            14:1994,
            15:2162,
            16:2298,
            17:2461,
            18:2652,
            19:2790,
            20:3535,
            21:4200,
            22:4354,
            23:4577,
            24:4784,
            25:5042,
            26:5241,
            27:5437,
            28:5652,
            29:5918,
            30:6144,
            31:7405,
            32:7659,
            33:7978,
            34:8243,
            35:8531,
            36:8751,
            37:9022,
            38:9345,
            39:9648,
            40:9869,
            41:12007,
            42:12298,
            43:12655,
            44:12999,
            45:13312,
            46:13675,
            47:13992,
            48:14336,
            49:14697,
            50:15060,
            51:19639,
            52:20070,
            53:20543,
            54:21008,
            55:21405,
            56:21894,
            57:22296,
            58:22810,
            59:23256,
            60:23694,
            61:36968,
            62:37589,
            63:38333,
            64:39005,
            65:39755,
            66:40493,
            67:41144,
            68:41872,
            69:42529,
            70:57664,
            71:60563,
            72:61556,
            73:62633,
            74:63634,
            75:64458,
            76:65585,
            77:66476,
            78:67431,
            79:68528,
            80:69530,
            81:105771,
            82:107433,
            83:108770,
            84:110381,
            85:111938,
            86:113409,
            87:114975,
            88:116456,
            89:117942,
            90:199204,
            91:222140,
            92:245453,
            93:269362,
            94:293812,
            95:318657,
            96:343708,
            97:392048,
            98:440898,
            99:890804,
            100:902440,
        }

        new_exp = current_exp + xp_award
        level_up = False
        # print(f'Currently level {current_level} with exp {current_exp}, new exp is {new_exp}')
        exp_threshold = exp_table[current_level + 1]
        # print(f'exp threshold is {exp_threshold}')
        if current_level < 100 and new_exp >= exp_threshold:
            # print(f'Level up')
            current_level += 1
            level_up = True

        if level_up:
            attack_increase = random.randint(1, 5)
            defence_increase = random.randint(1, 5)
            hp_increase = random.randint(1, 5)

            level_up_embed = discord.Embed(
                title="Level Up! 🎉",
                description=f"{player_name} has reached level **{current_level}**!",
                color=0x00FF00
            )
            new_atk = current_atk + attack_increase
            new_def = current_def + defence_increase
            new_mhp = current_mhp + hp_increase
            if current_level > 0 and current_level % 10 == 0 and current_level <= 100:  # Check levels 10, 20, 30, etc.
                passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
                await self.bot.database.set_passive_points(user_id, server_id, passive_points + 2)
            level_up_embed.add_field(name="Stat increases:", 
                                     value=(f"⚔️ **Attack:** {new_atk} (+{attack_increase})\n"
                                            f"🛡️ ** Defense:** {new_def} (+{defence_increase})\n"
                                            f"❤️ **Hit Points:** {new_mhp} (+{hp_increase})"), inline=False)
            await context.send(embed=level_up_embed)

            # print(f'Update {user_id} stats')
            await self.bot.database.update_player_hp(user_id, 
                                                    existing_user[11] + hp_increase)  # index 11: current hp
            await self.bot.database.update_player_max_hp(user_id, 
                                                        existing_user[12] + hp_increase)  # index 12: max hp
            await self.bot.database.increase_attack(user_id, attack_increase)
            await self.bot.database.increase_defence(user_id, defence_increase)
            await self.bot.database.increase_level(user_id)
            new_exp -= exp_table[current_level]
            
        # print(f'Update {user_id} experience')
        await self.bot.database.update_experience(user_id, new_exp)


async def setup(bot) -> None:
    await bot.add_cog(Combat(bot))
