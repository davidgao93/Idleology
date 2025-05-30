import random
import discord
from discord.ext import commands
from discord.ext.tasks import asyncio
from discord import app_commands, Interaction, Message
from datetime import datetime, timedelta
import json
import csv
import os
import re
from combat_view import CombatView, AscensionView, DuelView, DuelActionView  # Import the view classes

class Combat(commands.Cog, name="combat"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.prefixes = self.load_list("assets/items/pref.txt")
        self.weapon_types = self.load_list("assets/items/wep.txt")
        self.suffixes = self.load_list("assets/items/suff.txt")
        self.accessory_types = self.load_list("assets/items/acc.txt")
        self.monster_modifiers = [
            "Steel-born",  # 10% boost to monster_defence
            "All-seeing",  # 10% boost to monster accuracy
            "Mirror Image",  # 20% chance to deal double damage
            "Volatile",  # Explodes after combat, reducing player_hp to 1
            "Glutton",  # Doubles monster HP, no extra XP
            "Enfeeble",  # Decrease player's attack by 10%
            "Venomous",  # Deal 1 damage on every miss
            "Strengthened", # +3 monster max hit
            "Hellborn", # +2 each successful hit
            "Lucifer-touched", # Lucky attacks
            "Titanium", # Player damage reduced by 10%
            "Ascended", #+10 Attack, +10 defence
            "Summoner", # minions echo hits for 1/6 the monster hit
            "Shield-breaker", # player has no ward
            "Impenetrable", # player cannot crit
            "Unblockable", # player cannot block
            "Unavoidable" #player has no additional evade chance
        ]

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
    

    async def generate_armor(self, user_id: str, server_id: str, encounter_level: int, drop_rune: bool) -> str:
        """Generate a unique armor item."""
        prefix = random.choice(self.prefixes)
        armor_type = random.choice(self.load_list('assets/items/armor.txt'))  # Load names from armor.txt
        suffix = random.choice(self.suffixes)
        armor_name = f"{prefix} {armor_type} {suffix}"

        modifiers = []
        block_modifier = 0
        evasion_modifier = 0
        ward_modifier = 0

        if drop_rune:
            randroll = random.randint(0, 100)
        else:
            randroll = random.randint(0, 90)
        print(f"Armor attribute roll: {randroll}")
        if randroll <= 30:  # 30% chance for block roll
            block_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
            modifiers.append(f"+{block_modifier} Block")
        elif randroll > 30 and randroll <= 60:  # 30% chance for evasion roll
            evasion_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5)))
            modifiers.append(f"+{evasion_modifier} Evasion")
        elif randroll > 60 and randroll <= 90:  # 30% chance for ward roll
            ward_modifier = max(1, random.randint(int(encounter_level // 7), int(encounter_level // 5))) * 2
            modifiers.append(f"+{ward_modifier}% Ward")
        else:
            await self.bot.database.update_imbuing_runes(user_id, 1)  # Increment runes
            armor_description = "**Rune of Imbuing**!"
            armor_name = "rune"
            return armor_name, armor_description

        if modifiers:
            armor_description = armor_name + f"\n" + f"\n".join(modifiers)
        else:
            armor_description = armor_name

        return armor_name, armor_description


    @app_commands.command(name="combat", description="Engage in combat.")
    async def combat(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        if not await self.bot.check_is_active(interaction, user_id):
            return

        # if not await self.bot.is_maintenance(interaction, user_id):
        #     return

        player_name = existing_user[3]
        last_combat_time = existing_user[24]
        checkin_remaining = None
        combat_duration = timedelta(minutes=10)
        if last_combat_time:
            last_combat_time_dt = datetime.fromisoformat(last_combat_time)
            time_since_combat = datetime.now() - last_combat_time_dt
            if time_since_combat < combat_duration:
                checkin_remaining = combat_duration - time_since_combat
        else:
            if user_id != str(866408616873820180):
                await self.bot.database.update_combat_time(user_id)

        if checkin_remaining:
            value = (f"{player_name} isn't yet ready.\n"
                     f"{(checkin_remaining.seconds // 60) % 60} minutes "
                     f"{(checkin_remaining.seconds % 60)} seconds "
                     f"remaining until they can engage in combat again.")
            await interaction.response.send_message(value, ephemeral=True)
            return
        else:
            if user_id != str(866408616873820180):
                await self.bot.database.update_combat_time(user_id)
                self.bot.state_manager.set_active(user_id, "combat")
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
            player_block = 0
            player_eva = 0
            current_passive = ""
            accessory_passive = ""
            armor_passive = ""
            accessory_lvl = 0
            followers_count = await self.bot.database.fetch_followers(player_ideology)
            equipped_item = await self.bot.database.get_equipped_item(user_id)
            equipped_accessory = await self.bot.database.get_equipped_accessory(user_id)
            equipped_armor = await self.bot.database.get_equipped_armor(user_id)
            invulnerable = False
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
            if equipped_armor:
                armor_passive = equipped_armor[7]
                player_ward += int((equipped_armor[6] / 100) * player_max_hp)  # Ward from armor
                player_block += equipped_armor[4]  # Block
                player_eva += equipped_armor[5]  # Evasion treated as rarity boost
                print(f'Stats from equipped armor: {player_block} block {player_eva} evasion {equipped_armor[6]} ward')
                print(f'Armor grants {armor_passive}')

            # Check for Door of Ascension
            is_boss_encounter = False
            is_heaven_door = False
            if (user_level >= 20 and existing_user[25] > 0 and existing_user[26] > 0 and
                    random.random() < 0.2):
                is_heaven_door = True
                embed = discord.Embed(
                    title="Door of Ascension",
                    description="Your angelic and draconic keys tremble with anticipation, "
                                "do you wish to challenge the heavens?",
                    color=0x00FF00,
                )
                embed.set_image(url="https://i.imgur.com/PXOhTbX.png")
                view = AscensionView(user_id)
                await interaction.response.send_message(embed=embed, view=view)
                message = await interaction.original_response()

                try:
                    await view.wait()
                    if view.action == "accept":
                        is_boss_encounter = True
                        await self.bot.database.add_dragon_key(user_id, -1)
                        await self.bot.database.add_angel_key(user_id, -1)
                    elif view.action == "decline":
                        await message.edit(embed=discord.Embed(
                            title="Door of Ascension",
                            description="You declined the challenge.",
                            color=0xFF0000), view=None)
                        self.bot.state_manager.clear_active(user_id)
                        return
                    else:  # Timeout
                        await message.edit(embed=discord.Embed(
                            title="Door of Ascension",
                            description="You hesitated, and the opportunity fades.",
                            color=0xFF0000), view=None)
                        self.bot.state_manager.clear_active(user_id)
                        return
                except Exception as e:
                    print(f"Ascension view error: {e}")
                    await message.edit(embed=discord.Embed(
                        title="Door of Ascension",
                        description="An error occurred while processing your choice.",
                        color=0xFF0000), view=None)
                    self.bot.state_manager.clear_active(user_id)
                    return
                
            if is_boss_encounter:
                await self.handle_boss_encounter(
                    interaction, user_id, server_id, player_name, user_level,
                    player_ideology, player_attack, player_defence, player_hp,
                    player_max_hp, ascension_level, potions, player_rar,
                    player_crit, player_ward, player_block, player_eva,
                    current_passive, accessory_passive, armor_passive,
                    accessory_lvl, followers_count, equipped_item,
                    equipped_accessory, equipped_armor, invulnerable
                )
                self.bot.state_manager.clear_active(user_id)
                return
                
            # Treasure Hunter: +5% chance to turn the monster into a loot encounter
            is_treasure = False
            treasure_hunter = False
            treasure_chance = 0.01
            if armor_passive == "Treasure Hunter" and random.random() < 0.05:
                treasure_chance += 0.05
                print("Treasure Hunter passive: Increased treasure encounter chance by 5%")
            if random.random() < treasure_chance:
                encounter_level, monster_attack, monster_defence, monster_modifiers = self.generate_encounter(user_level, is_treasure=True)
                monster_attack = 0
                monster_defence = 0
                treasure_hunter = True
                is_treasure = True
            else:
                encounter_level, monster_attack, monster_defence, monster_modifiers = self.generate_encounter(user_level, is_treasure=False)

            # Omnipotent: 20% chance to set monster's attack and defense to 0
            if armor_passive == "Omnipotent" and random.random() < 0.2:
                monster_attack = 0
                monster_defence = 0
                print("Omnipotent passive: Monster attack and defense set to 0")

            # Unlimited Wealth: 20% chance to 5x player rarity stat
            greed_good = False
            if armor_passive == "Unlimited Wealth" and random.random() < 0.2:
                player_rar *= 5
                print(f"Unlimited Wealth passive: Player rarity multiplied by 5 to {player_rar}")
                greed_good = True

            if user_level == 1:
                monster_hp = 10
            elif user_level > 1 and user_level <= 5:
                monster_hp = max(10, random.randint(1, 4) + int(7 * (encounter_level ** random.uniform(1.05, 1.15))))
            else:
                monster_hp = random.randint(0, 9) + int(10 * (encounter_level ** random.uniform(1.25, 1.35)))
            award_xp = monster_hp
            if "Glutton" in monster_modifiers:
                monster_hp *= 2
                print(f"Glutton modifier applied: Monster HP doubled to {monster_hp}")
            if "Enfeeble" in monster_modifiers:
                effective_player_attack = int(player_attack * 0.9)
                print(f"Enfeeble modifier applied: Player attack reduced to {effective_player_attack}")
            player_rar += len(monster_modifiers) * 30
            print(f"Player rarity boosted by {(len(monster_modifiers) * 30)} from monster mods")
            attack_message = ""
            monster_message = ""
            heal_message = ""
            opportunity_message = ""
            pause_message = ""
            opportunity = False
            print(f"player_hp: {player_hp} | follower_count: {followers_count} | ascension: {ascension_level} | "
                  f"p.atk: {player_attack} | p.def: {player_defence}")
            print(f"m.lvl: {encounter_level} | m.atk: {monster_attack} | m.def: {monster_defence} | m.hp: {monster_hp} | modifiers: {monster_modifiers}")

            if is_treasure:
                monster_name, image_url, flavor_txt = await self.fetch_monster_image(999)
            else:
                monster_name, image_url, flavor_txt = await self.fetch_monster_image(encounter_level)
            monster_full_name = monster_name
            if monster_modifiers:
                modifier_prefix = ", ".join(monster_modifiers)
                monster_full_name = f"**{modifier_prefix}** {monster_name}"
            print(f"Generated {monster_name} with image_url: {image_url}")

            start_combat = False
            try:
                modifier_descriptions = []
                for modifier in monster_modifiers:
                    if modifier == "Steel-born":
                        modifier_descriptions.append("**Steel-born**: 10% boost to monster defense")
                    elif modifier == "All-seeing":
                        modifier_descriptions.append("**All-seeing**: 10% boost to monster accuracy")
                    elif modifier == "Mirror Image":
                        modifier_descriptions.append("**Mirror Image**: 20% chance to deal double damage")
                    elif modifier == "Volatile":
                        modifier_descriptions.append("**Volatile**: Explodes after combat, reducing player HP to 1")
                    elif modifier == "Glutton":
                        modifier_descriptions.append("**Glutton**: Doubles monster HP, no extra XP")
                    elif modifier == "Enfeeble":
                        modifier_descriptions.append("**Enfeeble**: Decreases player's attack by 10%")
                    elif modifier == "Venomous":
                        modifier_descriptions.append("**Venomous**: Deals 1 damage on every miss")
                    elif modifier == "Strengthened":
                        modifier_descriptions.append("**Strengthened**: +3 monster max hit")
                    elif modifier == "Hellborn":
                        modifier_descriptions.append("**Hellborn**: +2 each successful hit")
                    elif modifier == "Lucifer-touched":
                        modifier_descriptions.append("**Lucifer-touched**: Lucky attacks")
                    elif modifier == "Titanium":
                        modifier_descriptions.append("**Titanium**: Player damage reduced by 10%")
                    elif modifier == "Ascended":
                        modifier_descriptions.append("**Ascended**: +10 Attack, +10 Defence")
                    elif modifier == "Summoner":
                        modifier_descriptions.append("**Summoner**: Minions echo hits for 1/6 the monster hit")
                    elif modifier == "Shield-breaker":
                        modifier_descriptions.append("**Shield-breaker**: Player has no ward")
                    elif modifier == "Impenetrable":
                        modifier_descriptions.append("**Impenetrable**: Player cannot crit")
                    elif modifier == "Unblockable":
                        modifier_descriptions.append("**Unblockable**: Player cannot block")
                    elif modifier == "Unavoidable":
                        modifier_descriptions.append("**Unavoidable**: Player has no additional evade chance")
            
                if "Shield-breaker" in monster_modifiers:
                    player_ward = 0
                    print(f"Shield-breaker modifier applied: player ward is now 0")

                if "Impenetrable" in monster_modifiers:
                    player_crit += 200
                    print(f"Impenetrable applied: beat {player_crit} to crit")

                if "Unblockable" in monster_modifiers:
                    player_block = 0
                    print(f"Unblockable applied: {player_block} to 0")

                if "Unavoidable" in monster_modifiers:
                    player_eva = 0
                    print(f"Unavoidable applied: {player_eva} to 0")    

                embed = discord.Embed(
                    title=f"Witness {player_name}",
                    description=(f"A level {encounter_level} {monster_full_name} approaches! ({int(award_xp * 1.4)} xp)\n" +
                                 ("\n".join(modifier_descriptions) if modifier_descriptions else "")),
                    color=0x00FF00,
                )
                embed.set_image(url=image_url)
                embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
                if player_ward > 0:
                    embed.add_field(name="❤️ HP", value=f"{player_hp} ({player_ward} 🔮)", inline=True)
                else:
                    embed.add_field(name="❤️ HP", value=player_hp, inline=True)
                items = await self.bot.database.fetch_user_items(user_id)
                accs = await self.bot.database.fetch_user_accessories(user_id)
                arms = await self.bot.database.fetch_user_armors(user_id)
                if len(items) > 60:
                    embed.add_field(name="🚫 WARNING 🚫", value="Weapon pouch is full! Weapons can't drop.", inline=False)
                if len(accs) > 60:
                    embed.add_field(name="🚫 WARNING 🚫", value="Accessory pouch is full! Accessories can't drop.", inline=False)
                if len(arms) > 60:
                    embed.add_field(name="🚫 WARNING 🚫", value="Armor pouch is full! Armor can't drop.", inline=False)

                # Check armor passives that affect the start of combat
                if armor_passive == "Treasure Hunter" and treasure_hunter == True:
                    embed.add_field(name="Armor Passive",
                        value="The **Treasure Hunter** armor imbues with power! A mysterious being appears.",
                        inline=False)

                if armor_passive == "Invulnerable" and random.random() < 0.2:
                    embed.add_field(name="Armor Passive",
                                    value="The **Invulnerable** armor imbues with power!",
                                    inline=False)
                    invulnerable = True

                if armor_passive == "Omnipotent" and monster_attack == 0 and monster_defence == 0:
                    embed.add_field(name="Armor Passive",
                                    value=f"The **Omnipotent** armor imbues with power! The {monster_name} trembles in **terror**.",
                                    inline=False)
                    
                if armor_passive == "Unlimited Wealth" and greed_good:
                    embed.add_field(name="Armor Passive",
                                    value=f"The **Unlimited Wealth** armor imbues with power! {player_name}'s greed knows no bounds.",
                                    inline=False)

                # Existing passive checks (Absorb, Polished, Sturdy, Accuracy)
                if accessory_passive == "Absorb":
                    absorb_chance = accessory_lvl * 2
                    if random.randint(1, 100) <= absorb_chance:
                        monster_stats = monster_attack + monster_defence
                        absorb_amount = int(monster_stats * 0.10)
                        player_attack += int(absorb_amount / 2)
                        player_defence += int(absorb_amount / 2)
                        embed.add_field(name="Accessory passive",
                                        value=f"The accessory's 🌀 **Absorb ({accessory_lvl})** activates! "
                                              f"⚔️ boosted by **{player_attack}**\n"
                                              f"🛡️ boosted by **{player_defence}**",
                                        inline=False)
                polished_passives = ["polished", "honed", "gleaming", "tempered", "flaring"]
                if current_passive in polished_passives:
                    value = polished_passives.index(current_passive)
                    defence_reduction = (value + 1) * 5
                    monster_defence_reduction = int(monster_defence * defence_reduction / 100)
                    embed.add_field(name="Weapon passive",
                                    value=f"The **{current_passive}** weapon 💫 shines with anticipation!\n"
                                          f"It reduces the {monster_name}'s defence by {defence_reduction}%.",
                                    inline=False)
                    monster_defence -= monster_defence_reduction
                sturdy_passives = ["sturdy", "reinforced", "thickened", "impregnable", "impenetrable"]
                if current_passive in sturdy_passives:
                    value = sturdy_passives.index(current_passive)
                    defence_bonus = (1 + value) * 3
                    embed.add_field(name="Weapon passive",
                                    value=f"The **{current_passive}** weapon strengthens resolve!\n"
                                          f"🛡️ boosted by **{defence_bonus}**!",
                                    inline=False)
                    player_defence += defence_bonus
                view = CombatView(user_id)
                if is_heaven_door:
                    message: Message = await interaction.followup.send(embed=embed, view=view)
                else:
                    await interaction.response.send_message(embed=embed, view=view)
                    message: Message = await interaction.original_response()
                start_combat = True
            except Exception as e:
                print(e)
                await interaction.response.send_message("The servers are busy handling another request. Try again.")
                self.bot.state_manager.clear_active(user_id)
                return

            if start_combat:
                while True:
                    try:
                        await view.wait()
                        action = view.action
                        view = CombatView(user_id)  # Create new view for next iteration

                        if action == "attack":
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
                                                                                accessory_lvl,
                                                                                armor_passive,
                                                                                monster_modifiers)

                            if monster_hp > 0:
                                player_hp, monster_message, player_ward = await self.monster_turn(embed,
                                                                                                 monster_attack,
                                                                                                 player_hp,
                                                                                                 player_defence,
                                                                                                 followers_count,
                                                                                                 monster_name,
                                                                                                 user_id,
                                                                                                 current_passive,
                                                                                                 flavor_txt,
                                                                                                 player_ward,
                                                                                                 monster_modifiers,
                                                                                                 invulnerable,
                                                                                                 player_block,
                                                                                                 player_eva)

                            await self.bot.database.update_player_hp(user_id, player_hp)
                            if player_hp <= 0:
                                total_damage_dealt = award_xp - monster_hp
                                embed.add_field(name=player_name, value=attack_message, inline=False)
                                embed.add_field(name=monster_name, value=monster_message, inline=False)
                                await self.handle_defeat(user_id, message, monster_name,
                                                         total_damage_dealt, player_name, award_xp, server_id,
                                                         monster_modifiers)
                                self.bot.state_manager.clear_active(user_id)
                                break
                            overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
                            if current_passive in overwhelm_passives:
                                culling_multiplier = overwhelm_passives.index(current_passive)
                                culling_strike = (culling_multiplier + 1) * 5
                                if monster_hp <= (award_xp * culling_strike / 100):
                                    embed.add_field(name=player_name, value=attack_message, inline=False)
                                    embed.add_field(name=monster_name, value=monster_message, inline=False)
                                    await self.handle_victory(encounter_level, user_id, server_id,
                                                             player_name, monster_name, interaction,
                                                             award_xp, player_rar, player_hp,
                                                             message, user_level, True,
                                                             accessory_passive, accessory_lvl,
                                                             monster_modifiers, armor_passive)
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
                                                             accessory_passive, accessory_lvl,
                                                             monster_modifiers, armor_passive)
                                    self.bot.state_manager.clear_active(user_id)
                                    break

                        elif action == "auto":
                            print('Start auto battle')
                            pause_message = ""
                            end_battle, end_php, end_mhp = await self.auto_battle(
                                embed, interaction, encounter_level,
                                player_attack, monster_hp, monster_attack,
                                monster_defence, player_defence,
                                followers_count, player_name, user_id,
                                server_id, monster_name, player_hp,
                                message, award_xp, ascension_level,
                                player_rar, current_passive, user_level,
                                flavor_txt, player_max_hp, player_crit,
                                player_ward, accessory_passive, accessory_lvl,
                                monster_modifiers, armor_passive, invulnerable,
                                player_block, player_eva)
                            if end_battle:
                                print('End auto battle')
                                self.bot.state_manager.clear_active(user_id)
                                break
                            else:
                                print('Pause auto battle')
                                player_hp = end_php
                                monster_hp = end_mhp
                                pause_message = "Player HP < 20%, auto-battle paused!"
                        elif action == "heal":
                            if player_ward > 0:
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
                                    new_player_hp = max(1, player_hp - damage_taken)
                                    player_hp = new_player_hp
                                    await self.bot.database.update_player_hp(user_id, player_hp)
                                    opportunity_message = f"The monster took an opportunity strike, dealing **{damage_taken}** 💥 damage!"
                                    embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                                    embed.set_field_at(1, name="❤️ HP", value=player_hp, inline=True)
                            await message.edit(embed=embed, view=view)

                        elif action == "run":
                            if random.random() < 0.5:
                                opportunity = True
                                if user_level <= 10:
                                    damage_taken = random.randint(1, 2)
                                else:
                                    damage_taken = random.randint(1, 6)
                                new_player_hp = max(1, player_hp - damage_taken)
                                player_hp = new_player_hp
                                await self.bot.database.update_player_hp(user_id, player_hp)
                                opportunity_message = (f"As {player_name} runs away, the {monster_name} savagely swipes, "
                                                       f"grazing for **{damage_taken}** 💥 damage!")
                                embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                                embed.set_field_at(1, name="❤️ HP", value=player_hp, inline=True)
                                await message.edit(embed=embed, view=None)
                            else:
                                embed.add_field(name="Escape", value="Got away safely!", inline=False)
                                await message.edit(embed=embed, view=None)
                            self.bot.state_manager.clear_active(user_id)
                            break

                        embed.clear_fields()
                        embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
                        if player_ward > 0:
                            embed.add_field(name="❤️ HP", value=f"{player_hp} ({player_ward} 🔮)", inline=True)
                        else:
                            embed.add_field(name="❤️ HP", value=player_hp, inline=True)
                        if attack_message:
                            embed.add_field(name=player_name, value=attack_message, inline=False)
                        if monster_message:
                            embed.add_field(name=monster_name, value=monster_message, inline=False)
                        if heal_message:
                            embed.add_field(name="Heal", value=heal_message, inline=False)
                        if pause_message:
                            embed.add_field(name="Auto battle", value=pause_message, inline=False)
                        if opportunity:
                            embed.add_field(name=f"{monster_name}", value=opportunity_message, inline=False)
                        await message.edit(embed=embed, view=view)

                    except asyncio.TimeoutError:
                        if random.random() < 0.5:
                            opportunity = True
                            damage_taken = random.randint(1, 6)
                            new_player_hp = max(1, player_hp - damage_taken)
                            player_hp = new_player_hp
                            await self.bot.database.update_player_hp(user_id, player_hp)
                            opportunity_message = (f"The {monster_name} loses interest, "
                                                   f"lazily grazing for **{damage_taken}** damage before leaving.")
                            embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                            if player_ward > 0:
                                embed.set_field_at(1, name="❤️ HP", value=f"{player_hp} ({player_ward} 🔮)", inline=True)
                            else:
                                embed.set_field_at(1, name="❤️ HP", value=player_hp, inline=True)
                            await message.edit(embed=embed, view=None)
                        else:
                            embed.add_field(name=monster_name,
                                            value=f"The {monster_name} loses interest.\n"
                                                  f"{player_name} failed to grasp the moment.",
                                            inline=False)
                            await message.edit(embed=embed, view=None)
                        self.bot.state_manager.clear_active(user_id)
                        break
    
    async def handle_boss_encounter(self, interaction, user_id, server_id, player_name,
                                   user_level, player_ideology, player_attack, player_defence,
                                   player_hp, player_max_hp, ascension_level, potions, player_rar,
                                   player_crit, player_ward, player_block, player_eva,
                                   current_passive, accessory_passive, armor_passive,
                                   accessory_lvl, followers_count, equipped_item,
                                   equipped_accessory, equipped_armor, invulnerable):
        """Handle the three-phase boss encounter with Aphrodite."""
        phases = [
            {"name": "Aphrodite, Heaven's Envoy", "level": 886, "modifiers_count": 3, "hp_multiplier": 1.5},
            {"name": "Aphrodite, the Eternal", "level": 887, "modifiers_count": 6, "hp_multiplier": 2},
            {"name": "Aphrodite, Harbinger of Destruction", "level": 888, "modifiers_count": 9, "hp_multiplier": 2.5},
        ]
        current_hp = player_hp
        current_ward = player_ward

        for phase in phases:
            print(f'On phase {phase}')
            # Generate encounter
            encounter_level, monster_attack, monster_defence, monster_modifiers = self.generate_encounter(user_level)
            # Override with phase-specific modifiers
            available_modifiers = self.monster_modifiers.copy()
            monster_modifiers = []
            for _ in range(phase["modifiers_count"]):
                if available_modifiers:
                    modifier = random.choice(available_modifiers)
                    monster_modifiers.append(modifier)
                    available_modifiers.remove(modifier)
            if "Ascended" in monster_modifiers:
                monster_attack += 10
                monster_defence += 10
            if "Steel-born" in monster_modifiers:
                monster_defence = int(monster_defence * 1.1)

            # Calculate monster HP
            monster_hp = random.randint(0, 9) + int(10 * (encounter_level ** random.uniform(1.25, 1.35)))
            monster_hp = int(monster_hp * phase["hp_multiplier"])
            award_xp = monster_hp
            if "Glutton" in monster_modifiers:
                monster_hp *= 2
                print(f"Glutton modifier applied: Monster HP doubled to {monster_hp}")

            # Apply Enfeeble modifier
            effective_player_attack = player_attack
            if "Enfeeble" in monster_modifiers:
                effective_player_attack = int(player_attack * 0.9)
                print(f"Enfeeble modifier applied: Player attack reduced to {effective_player_attack}")

            # Apply other modifiers
            if "Shield-breaker" in monster_modifiers:
                current_ward = 0
            if "Impenetrable" in monster_modifiers:
                player_crit += 200
            if "Unblockable" in monster_modifiers:
                player_block = 0
            if "Unavoidable" in monster_modifiers:
                player_eva = 0

            # Fetch monster details
            monster_name, image_url, flavor_txt = await self.fetch_monster_image(phase["level"])
            monster_full_name = f"**{', '.join(monster_modifiers)}** {monster_name}" if monster_modifiers else monster_name

            # Setup embed
            embed = discord.Embed(
                title=f"Witness {player_name}",
                description=(f"🐉**{monster_name}**🪽 descends upon you!\n" +
                             "\n".join([f"**{m}**: {self.get_modifier_description(m)}" for m in monster_modifiers])),
                color=0x00FF00,
            )
            embed.set_image(url=image_url)
            embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
            embed.add_field(name="❤️ HP", value=f"{current_hp} ({current_ward} 🔮)" if current_ward > 0 else current_hp, inline=True)
            items = await self.bot.database.fetch_user_items(user_id)
            accs = await self.bot.database.fetch_user_accessories(user_id)
            arms = await self.bot.database.fetch_user_armors(user_id)
            if len(items) > 60:
                embed.add_field(name="🚫 WARNING 🚫", value="Weapon pouch is full! Weapons can't drop.", inline=False)
            if len(accs) > 60:
                embed.add_field(name="🚫 WARNING 🚫", value="Accessory pouch is full! Accessories can't drop.", inline=False)
            if len(arms) > 60:
                embed.add_field(name="🚫 WARNING 🚫", value="Armor pouch is full! Armor can't drop.", inline=False)

            view = CombatView(user_id, timeout=120.0)
            await interaction.edit_original_response(embed=embed, view=view)
            message = await interaction.original_response()

            # Combat loop
            while monster_hp > 0 and current_hp > 0:
                try:
                    await view.wait()
                    action = view.action
                    view = CombatView(user_id, timeout=120.0)  # Create new view for next iteration
                    attack_message = ""
                    monster_message = ""
                    heal_message = ""
                    opportunity_message = ""
                    pause_message = ""
                    opportunity = False

                    if action == "attack":
                        print('attack')
                        monster_hp, attack_message = await self.player_turn(
                            embed, effective_player_attack, monster_hp, monster_defence,
                            followers_count, player_name, ascension_level, monster_name,
                            current_passive, player_crit, accessory_passive, accessory_lvl,
                            armor_passive, monster_modifiers)
                        if monster_hp > 0:
                            current_hp, monster_message, current_ward = await self.monster_turn(
                                embed, monster_attack, current_hp, player_defence, followers_count,
                                monster_name, user_id, current_passive, flavor_txt, current_ward,
                                monster_modifiers, invulnerable, player_block, player_eva)
                        await self.bot.database.update_player_hp(user_id, current_hp)
                        
                        if current_hp <= 0:
                            total_damage_dealt = award_xp - monster_hp
                            embed.add_field(name=player_name, value=attack_message, inline=False)
                            embed.add_field(name=monster_name, value=monster_message, inline=False)
                            await self.handle_boss_defeat(user_id, message, monster_name,
                                                         total_damage_dealt, player_name, award_xp,
                                                         server_id, monster_modifiers)
                            return
                        overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
                        if current_passive in overwhelm_passives:
                            culling_multiplier = overwhelm_passives.index(current_passive)
                            culling_strike = (culling_multiplier + 1) * 5
                            if monster_hp <= (award_xp * culling_strike / 100):
                                embed.add_field(name=player_name, value=attack_message, inline=False)
                                embed.add_field(name=monster_name, value=monster_message, inline=False)
                                if phase == phases[-1]:
                                    print(f'Won phase {phase} vs {phases[-1]} with -1')
                                    await self.handle_boss_victory(
                                        encounter_level, user_id, server_id, player_name, monster_name,
                                        interaction, award_xp, player_rar, current_hp, message, user_level,
                                        True, accessory_passive, accessory_lvl, monster_modifiers, armor_passive)
                                    return
                                break
                        else:
                            if monster_hp <= 0:
                                embed.add_field(name=player_name, value=attack_message, inline=False)
                                embed.add_field(name=monster_name, value=monster_message, inline=False)
                                if phase == phases[-1]:
                                    print(f'Won phase {phase} vs {phases[-1]} with -1')
                                    await self.handle_boss_victory(
                                        encounter_level, user_id, server_id, player_name, monster_name,
                                        interaction, award_xp, player_rar, current_hp, message, user_level,
                                        False, accessory_passive, accessory_lvl, monster_modifiers, armor_passive)
                                    return
                                if "Volatile" in monster_modifiers and current_hp > 1:
                                    current_hp = 1
                                    await self.bot.database.update_player_hp(user_id, current_hp)
                                    print(f"Volatile modifier triggered: Player HP set to {current_hp}")
                                break

                    elif action == "auto":
                        print('Start auto battle')
                        end_battle, end_php, end_mhp = await self.boss_auto_battle(
                            embed, interaction, encounter_level, effective_player_attack, monster_hp,
                            monster_attack, monster_defence, player_defence, followers_count,
                            player_name, user_id, server_id, monster_name, current_hp, message,
                            award_xp, ascension_level, player_rar, current_passive, user_level,
                            flavor_txt, player_max_hp, player_crit, current_ward, accessory_passive,
                            accessory_lvl, monster_modifiers, armor_passive, invulnerable,
                            player_block, player_eva)
                        if end_battle:
                            print('Battle ended')
                            if end_php <= 0:
                                await self.handle_boss_defeat(user_id, message, monster_name,
                                                             award_xp - monster_hp, player_name, award_xp,
                                                             server_id, monster_modifiers)
                            elif phase == phases[-1]:
                                print(f'Won every phase {phase} vs {phases[-1]} with -1')
                                await self.handle_boss_victory(
                                    encounter_level, user_id, server_id, player_name, monster_name,
                                    interaction, award_xp, player_rar, current_hp, message, user_level,
                                    False, accessory_passive, accessory_lvl, monster_modifiers, armor_passive)
                                return
                            else:
                                print(f'end_battle: {end_battle}, mhp: {end_mhp}, php: {end_php}')
                                current_hp = end_php
                                if "Volatile" in monster_modifiers and current_hp > 1:
                                    current_hp = 1
                                    await self.bot.database.update_player_hp(user_id, current_hp)
                                    print(f"Volatile modifier triggered: Player HP set to {current_hp}")
                                break
                        else:
                            print('Pause auto battle')
                            current_hp = end_php
                            monster_hp = end_mhp
                            pause_message = "Player HP < 20%, auto-battle paused!"

                    elif action == "heal":
                        if current_ward > 0 or current_hp >= player_max_hp:
                            heal_message = "Full hp!"
                        else:
                            current_hp, potions, heal_message = await self.heal(
                                await self.bot.database.fetch_user(user_id, server_id), current_hp, potions,
                                user_id, server_id, interaction, embed, player_name)
                        await message.edit(embed=embed, view=view)

                    embed.clear_fields()
                    embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
                    embed.add_field(name="❤️ HP", value=f"{current_hp} ({current_ward} 🔮)" if current_ward > 0 else current_hp, inline=True)
                    if attack_message:
                        embed.add_field(name=player_name, value=attack_message, inline=False)
                    if monster_message:
                        embed.add_field(name=monster_name, value=monster_message, inline=False)
                    if heal_message:
                        embed.add_field(name="Heal", value=heal_message, inline=False)
                    if pause_message:
                        embed.add_field(name="Auto battle",value=pause_message, inline=False)
                    await message.edit(embed=embed, view=view)

                except asyncio.TimeoutError:
                    if random.random() < 0.5:
                        damage_taken = random.randint(1, 6)
                        current_hp = max(1, current_hp - damage_taken)
                        await self.bot.database.update_player_hp(user_id, current_hp)
                        opportunity_message = (f"{monster_name} loses interest, "
                                              f"lazily grazing for **{damage_taken}** damage before leaving.")
                        embed.add_field(name=monster_name, value=opportunity_message, inline=False)
                        embed.set_field_at(1, name="❤️ HP", value=f"{current_hp} ({current_ward} 🔮)" if current_ward > 0 else current_hp, inline=True)
                        await message.edit(embed=embed, view=None)
                    else:
                        embed.add_field(name=monster_name,
                                        value=f"{monster_name} loses interest.\n"
                                              f"{player_name} failed to grasp the moment.",
                                        inline=False)
                        await message.edit(embed=embed, view=None)
                    return

            if current_hp <= 0:
                return  # Defeat handled in combat loop

    async def player_turn(self, embed, 
                          player_attack, monster_hp,
                          monster_defence, followers_count, 
                          player_name, ascension_level,
                          monster_name, current_passive,
                          player_crit, accessory_passive, 
                          accessory_lvl, armor_passive,
                          monster_modifiers):
        attack_message = ""
        echo_damage = 0
        echo_hit = False
        passive_message = ""
        attack_multiplier = 1
        if accessory_passive == "Obliterate":
            double_damage_chance = accessory_lvl * 2
            if random.randint(1, 100) <= double_damage_chance:
                passive_message = f"**Obliterate ({accessory_lvl})** activates, doubling 💥 damage dealt!\n"
                attack_multiplier = 2

        hit_chance = self.calculate_hit_chance(player_attack, monster_defence)
        miss_chance = 100 - (hit_chance * 100)
        attack_roll = random.randint(0, 100)
        acc_value = 0
        accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
        if current_passive in accuracy_passives:
            acc_value = (1 + accuracy_passives.index(current_passive)) * 3
            passive_message = f"The **{current_passive}** weapon boosts 🎯 accuracy by **{acc_value}%**!\n"
            attack_roll += acc_value

        if accessory_passive == "Lucky Strikes":
            lucky_chance = accessory_lvl * 10
            if random.randint(1, 100) <= lucky_chance:
                attack_roll2 = random.randint(0, 100)
                attack_roll = max(attack_roll, attack_roll2)
                passive_message = f"**Lucky Strikes ({accessory_lvl})** activates!\nHit chance is now 🍀 lucky!\n"

        adjusted_value = 0
        crit_passives = ["piercing", "keen", "incisive", "puncturing", "penetrating"]
        if current_passive in crit_passives:
            value = crit_passives.index(current_passive)
            adjusted_value = (value + 1) * 3

        if (attack_roll - acc_value) > (player_crit - adjusted_value):
            max_hit = player_attack
            actual_hit = (random.randint(1, max_hit) * 2) * attack_multiplier
            # Mystical Might: 20% chance to deal 10x damage
            if armor_passive == "Mystical Might" and random.random() < 0.2:
                actual_hit *= 10
                passive_message += "The **Mystical Might** armor imbues with power!\n"
            if actual_hit > monster_hp:
                actual_hit = monster_hp
            monster_hp -= actual_hit
            attack_message = (
                (f"The **{current_passive}** weapon glimmers with power!\n" if adjusted_value > 0 else '') +
                f"Critical! {player_name} 🗡️ pierces through monster's defenses!\n"
                f"Damage: 💥 **{actual_hit}**"
            )
            attack_message = passive_message + attack_message
        elif attack_roll >= miss_chance:
            burning_passives = ["burning", "flaming", "scorching", "incinerating", "carbonising"]
            if current_passive in burning_passives:
                value = burning_passives.index(current_passive)
                burning_damage = value + 1
                rolls = [random.randint(1, 6) for _ in range(burning_damage)]
                final_burn_dmg = sum(rolls)
                max_hit = player_attack + final_burn_dmg
                attack_message = f"The **{current_passive}** weapon 🔥 burns bright!\nAttack boosted by **{final_burn_dmg}**\n"
            else:
                max_hit = player_attack

            sparking_passives = ["sparking", "shocking", "discharging", "electrocuting", "vapourising"]
            if current_passive in sparking_passives:
                value = sparking_passives.index(current_passive)
                sparking_damage = value + 1
                rolls = [random.randint(1, 6) for _ in range(sparking_damage)]
                final_spark_damage = sum(rolls)
                attack_message = f"The **{current_passive}** weapon surges with ⚡ lightning!\nLightning damage: **{final_spark_damage}**"
                min_damage = max(final_spark_damage, 1)
                if monster_hp <= min_damage:
                    actual_hit = monster_hp
                else:
                    actual_hit = (random.randint(min_damage, max_hit + min_damage)) * attack_multiplier
                    # Mystical Might: 20% chance to deal 10x damage
                    if armor_passive == "Mystical Might" and random.random() < 0.2:
                        actual_hit *= 10
                        passive_message += "The **Mystical Might** armor imbues with power!\n"
                    if actual_hit > monster_hp:
                        actual_hit = monster_hp
            else:
                echo_hit = False
                if "Titanium" in monster_modifiers:
                    print(f"Titanium modifier applied: actual hit reduced")
                    actual_hit = int(random.randint(1, max_hit) * 0.9)
                else:
                    actual_hit = random.randint(1, max_hit)
                    
                echo_passives = ["echo", "echoo", "echooo", "echoooo", "echoes"]
                if current_passive in echo_passives:
                    value = echo_passives.index(current_passive)
                    echo_multiplier = (value + 1) / 10
                    echo_damage = (1 + int(actual_hit * echo_multiplier)) * attack_multiplier
                    actual_hit = (actual_hit + echo_damage) * attack_multiplier
                    echo_hit = True
                # Mystical Might: 20% chance to deal 10x damage
                if armor_passive == "Mystical Might" and random.random() < 0.2:
                    actual_hit *= 10
                    passive_message += "The **Mystical Might** imbues with power!\n"
                if actual_hit > monster_hp:
                    actual_hit = monster_hp

            attack_message += f"Hit! Damage: 💥 **{actual_hit - echo_damage}**"
            attack_message = passive_message + attack_message
            if echo_hit:
                attack_message += f"\nThe **{current_passive}** weapon 🎶 echoes the hit!\nEcho damage: **{echo_damage}**"
            monster_hp -= actual_hit
        else:
            poisonous_passives = ["poisonous", "noxious", "venomous", "toxic", "lethal"]
            if current_passive in poisonous_passives:
                value = poisonous_passives.index(current_passive)
                poison_damage_dice = value + 3
                poison_rolls = [random.randint(1, 6) for _ in range(poison_damage_dice)]
                total_poison_damage = sum(poison_rolls)
                if total_poison_damage >= monster_hp:
                    total_poison_damage = monster_hp
                monster_hp -= total_poison_damage
                attack_message = f"Miss!\n The **{current_passive}** deals {total_poison_damage} poison 🐍 damage."
            else:
                attack_message = f"Miss!"

        embed.add_field(name=player_name, value=attack_message, inline=False)
        return monster_hp, attack_message


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

    async def monster_turn(self, embed, monster_attack, player_hp,
                           player_defence, followers_count,
                           monster_name, user_id, current_passive,
                           flavor_txt, player_ward, monster_modifiers,
                           invulnerable, player_block, player_eva):
        if invulnerable == True:
            #print("Invulnerable passive active: No damage taken")
            monster_message = f"The {monster_name} {flavor_txt}, but the **Invulnerable** armor absorbs all damage!"
            embed.add_field(name=monster_name, value=monster_message, inline=False)
            return player_hp, monster_message, player_ward
        
        evade_chance = player_eva / 100 * 25
        #print(f'{evade_chance} evasion added to monster_miss_chance')
        monster_miss_chance = (100 + evade_chance) - int(self.calculate_monster_hit_chance(monster_attack, player_defence) * 100)
        monster_attack_roll = random.randint(0, 100)
        if "Lucifer-touched" in monster_modifiers:
                monster_attack_roll2 = random.randint(0, 100)
                monster_attack_roll = max(monster_attack_roll, monster_attack_roll2)
                print(f"Lucifer-touched modifier applied: lucky attack roll")
        if "All-seeing" in monster_modifiers:
            monster_attack_roll = int(monster_attack_roll * 1.1)
            print(f"All-seeing modifier applied: Monster attack roll boosted to {monster_attack_roll}")

        if monster_attack_roll >= monster_miss_chance:
            damage_taken = self.calculate_damage_taken(monster_attack, player_defence, monster_modifiers)
            if "Hellborn" in monster_modifiers:
                damage_taken += 2
                print(f"Hellborn modifier applied: Damage taken boosted")
            minion_dmg = 0
            if "Summoner" in monster_modifiers:
                minion_dmg = int(damage_taken / 6)
                print(f"Summoner modifier applied: calculated minion_dmg: {minion_dmg}")
            #print(f"{damage_taken} pre block")
            blocked_damage = player_block / 400
            if (random.random() < blocked_damage):
                damage_taken = 0
                #print(f"all damage blocked")
            if "Mirror Image" in monster_modifiers and random.randint(1, 100) <= 20:
                damage_taken *= 2
                print(f"Mirror Image modifier applied: Damage doubled to {damage_taken}")
            if player_ward > 0:
                # print(f"Original ward: {player_ward}")
                player_ward -= damage_taken
                # print(f"New ward: {player_ward}")
                if player_ward < 0:
                    # print(f"No ward, Player HP ({player_hp}) ({player_ward}) ward")
                    player_hp += player_ward
            else:
                player_hp -= damage_taken
            monster_message = f"{monster_name} {flavor_txt}.\nDamage: 💥 **{damage_taken}**"
            if (minion_dmg > 0):
                monster_message += f"\nTheir minions attack!\nDamage: 💥 **{minion_dmg}**"
        else:
            if "Venomous" in monster_modifiers:
                player_hp = max(1, player_hp - 1)
                monster_message = f"{monster_name} misses, but their **Venomous** aura deals **1** 🐍 damage!"
            else:
                monster_message = f"{monster_name} misses!"

        embed.add_field(name=monster_name, value=monster_message, inline=False)
        return player_hp, monster_message, player_ward

    async def auto_battle(self, embed, interaction, encounter_level,
                         player_attack, monster_hp, monster_attack,
                         monster_defence, player_defence,
                         followers_count, player_name, user_id,
                         server_id, monster_name, player_hp,
                         message, award_xp, ascension_level,
                         player_rar, current_passive, user_level,
                         flavor_txt, player_max_hp, player_crit,
                         player_ward, accessory_passive, accessory_lvl,
                         monster_modifiers, armor_passive, invulnerable,
                         player_block, player_eva):
        minimum_hp = int(player_max_hp * 0.2)
        while player_hp > minimum_hp and monster_hp > 0:
            monster_hp, attack_message = await self.player_turn(embed, player_attack, monster_hp,
                                                                monster_defence, followers_count,
                                                                player_name, ascension_level, monster_name,
                                                                current_passive, player_crit,
                                                                accessory_passive, accessory_lvl, armor_passive,
                                                                monster_modifiers)
            overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
            if current_passive in overwhelm_passives:
                value = overwhelm_passives.index(current_passive)
                culling_strike = (value + 1) * 5
                if monster_hp <= (award_xp * culling_strike / 100):
                    await self.handle_victory(encounter_level, user_id, server_id,
                                             player_name, monster_name, interaction,
                                             award_xp, player_rar, player_hp,
                                             message, user_level, True,
                                             accessory_passive, accessory_lvl,
                                             monster_modifiers, armor_passive)
                    return True, player_hp, monster_hp
            else:
                if monster_hp <= 0:
                    embed.add_field(name=monster_name, value=attack_message, inline=False)
                    await self.handle_victory(encounter_level, user_id, server_id,
                                             player_name, monster_name, interaction,
                                             award_xp, player_rar, player_hp,
                                             message, user_level, False,
                                             accessory_passive, accessory_lvl,
                                             monster_modifiers, armor_passive)
                    return True, player_hp, monster_hp

            player_hp, monster_message, player_ward = await self.monster_turn(embed,
                                                                            monster_attack, player_hp,
                                                                            player_defence, followers_count,
                                                                            monster_name, user_id, current_passive,
                                                                            flavor_txt, player_ward,
                                                                            monster_modifiers, invulnerable, 
                                                                            player_block, player_eva)
            await self.bot.database.update_player_hp(user_id, player_hp)

            if player_hp <= 0:
                total_damage_dealt = award_xp - monster_hp
                embed.add_field(name=monster_name, value=monster_message, inline=False)
                await self.handle_defeat(user_id, message,
                                        monster_name, total_damage_dealt,
                                        player_name, award_xp, server_id,
                                        monster_modifiers)
                return True, player_hp, monster_hp


            embed.clear_fields()
            embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
            if player_ward > 0:
                embed.add_field(name="❤️ HP", value=f"{player_hp} ({player_ward} 🔮)", inline=True)
            else:
                embed.add_field(name="❤️ HP", value=player_hp, inline=True)
            embed.add_field(name=player_name, value=attack_message, inline=False)
            embed.add_field(name=monster_name, value=monster_message, inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(1)
        return False, player_hp, monster_hp
    

    async def boss_auto_battle(self, embed, interaction, encounter_level,
                         player_attack, monster_hp, monster_attack,
                         monster_defence, player_defence,
                         followers_count, player_name, user_id,
                         server_id, monster_name, player_hp,
                         message, award_xp, ascension_level,
                         player_rar, current_passive, user_level,
                         flavor_txt, player_max_hp, player_crit,
                         player_ward, accessory_passive, accessory_lvl,
                         monster_modifiers, armor_passive, invulnerable,
                         player_block, player_eva):
        minimum_hp = int(player_max_hp * 0.2)
        while player_hp > minimum_hp and monster_hp > 0:
            monster_hp, attack_message = await self.player_turn(embed, player_attack, monster_hp,
                                                                monster_defence, followers_count,
                                                                player_name, ascension_level, monster_name,
                                                                current_passive, player_crit,
                                                                accessory_passive, accessory_lvl, armor_passive,
                                                                monster_modifiers)
            overwhelm_passives = ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"]
            if current_passive in overwhelm_passives:
                value = overwhelm_passives.index(current_passive)
                culling_strike = (value + 1) * 5
                if monster_hp <= (award_xp * culling_strike / 100):
                    return True, player_hp, 0

            if monster_hp <= 0:
                return True, player_hp, 0

            player_hp, monster_message, player_ward = await self.monster_turn(embed,
                                                                            monster_attack, player_hp,
                                                                            player_defence, followers_count,
                                                                            monster_name, user_id, current_passive,
                                                                            flavor_txt, player_ward,
                                                                            monster_modifiers, invulnerable, 
                                                                            player_block, player_eva)
            await self.bot.database.update_player_hp(user_id, player_hp)

            if player_hp <= 0:
                return True, player_hp, monster_hp

            embed.clear_fields()
            embed.add_field(name="🐲 HP", value=monster_hp, inline=True)
            if player_ward > 0:
                embed.add_field(name="❤️ HP", value=f"{player_hp} ({player_ward} 🔮)", inline=True)
            else:
                embed.add_field(name="❤️ HP", value=player_hp, inline=True)
            embed.add_field(name=player_name, value=attack_message, inline