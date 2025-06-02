import random
import discord
from discord.ext import commands
from discord.ext.tasks import asyncio
from discord import app_commands, Interaction, Message
from datetime import datetime, timedelta
from core.models import Player, Monster, Weapon, Accessory, Armor
from core.loot import generate_weapon, generate_armor, generate_accessory
from core.combat_calcs import calculate_hit_chance, calculate_monster_hit_chance, calculate_damage_taken, check_cull
from core.gen_mob import fetch_monster_image, get_modifier_description, generate_encounter, get_monster_mods, get_boss_mods
import json
import re

class Combat(commands.Cog, name="combat"):
    def __init__(self, bot) -> None:
        self.bot = bot
        
    def load_exp_table(self):
        with open('assets/exp.json') as file:
            exp_table = json.load(file)
        return exp_table


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

        # Check if player 
        last_combat_time = existing_user[24]
        checkin_remaining = None
        combat_duration = timedelta(minutes=10)
        if last_combat_time:
            last_combat_time_dt = datetime.fromisoformat(last_combat_time)
            time_since_combat = datetime.now() - last_combat_time_dt
            if time_since_combat < combat_duration:
                remaining_time = combat_duration - time_since_combat
                checkin_remaining = remaining_time
        else:
            await self.bot.database.update_combat_time(user_id)

        if checkin_remaining:
            value = (f"Please slow down. Try again in {(checkin_remaining.seconds // 60) % 60} minute(s) "
                     f"{(checkin_remaining.seconds % 60)} second(s).")
            await interaction.response.send_message(value, ephemeral=True)
            return

        await self.bot.database.update_combat_time(user_id)
        self.bot.state_manager.set_active(user_id, "combat")
        
        # Initialize our player object
        player = Player(
            id = user_id,
            name = existing_user[3],
            level = existing_user[4],
            ascension = existing_user[15],
            exp = existing_user[5],
            hp = existing_user[11],
            max_hp = existing_user[12],
            attack = existing_user[9],
            defence = existing_user[10],
            rarity = 0,
            crit = 95,
            ward = 0,
            block = 0,
            evasion = 0,
            potions = existing_user[16],
            wep_id = 0,
            weapon_passive = "",
            acc_passive = "",
            acc_lvl = 0,
            armor_passive = "",
            invulnerable = False
        )

        # Handle equipped weapon
        equipped_item = await self.bot.database.get_equipped_weapon(user_id)
        if equipped_item:
            player.wep_id = equipped_item[0]
            player.weapon_passive = equipped_item[7]
            player.attack += equipped_item[4]
            player.defence += equipped_item[5]
            player.rarity += equipped_item[6]
            self.bot.logger.info(f'Weapon: {equipped_item[4]} ATK {equipped_item[4]} DEF {equipped_item[5]} RAR {equipped_item[7]} passive')

        equipped_accessory = await self.bot.database.get_equipped_accessory(user_id)
        if equipped_accessory:
            player.acc_passive = equipped_accessory[9]
            player.attack += equipped_accessory[4]
            player.defence += equipped_accessory[5]
            player.rarity += equipped_accessory[6]
            player.ward += max(1, int((equipped_accessory[7] / 100) * player.max_hp))
            player.crit -= equipped_accessory[8]
            player.acc_lvl = equipped_accessory[12]
            self.bot.logger.info(f'Accessory: {equipped_accessory[4]} ATK {equipped_accessory[5]} DEF {equipped_accessory[6]} RAR '
                    f'{5 + equipped_accessory[8]}% Crit, {player.ward} Ward '
                    f'{player.acc_passive} passive ({player.acc_lvl})')
            
        equipped_armor = await self.bot.database.get_equipped_armor(user_id)
        if equipped_armor:
            player.armor_passive = equipped_armor[7]
            player.ward += int((equipped_armor[6] / 100) * player.max_hp)  # Ward from armor
            player.block += equipped_armor[4]  # Block
            player.evasion += equipped_armor[5]  # Evasion treated as rarity boost
            self.bot.logger.info(f'Armor: {player.block} Block {player.evasion} Evasion {equipped_armor[6]} Ward {player.armor_passive} passive')

        # Check for Door of Ascension
        is_boss_encounter = False
        is_heaven_door = False
        is_hell_door = False
        boss_type = ''
        if (player.level >= 20 and 
            existing_user[25] > 0 and 
            existing_user[26] > 0 and
            random.random() < 0.2):
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
                    pass  # Proceed with normal combat
            except asyncio.TimeoutError: 
                await message.clear_reactions()                      
                await message.edit(embed=discord.Embed(
                    title="Door of Ascension",
                    description="You hesitated, and the opportunity fades.",
                    color=0xFF0000))
                self.bot.state_manager.clear_active(user_id)
                return
        elif (player.level >= 20 and existing_user[28] >= 5 and random.random() < 0.2):
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
            
        if is_boss_encounter:
            # Start the boss encounter with three phases
            await self.handle_boss_encounter(interaction, player, boss_type)
            self.bot.state_manager.clear_active(user_id)
            return
            
        # Treasure Hunter: +5% chance to turn the monster into a loot encounter
        treasure_hunter = False
        treasure_chance = 0.02
        if player.armor_passive == "Treasure Hunter":
            treasure_chance += 0.05
            self.bot.logger.info("Treasure Hunter passive: Increased treasure encounter chance by 5%")
        
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
            flavor=""
        )

        if random.random() < treasure_chance:
            monster = await generate_encounter(player, monster, is_treasure=True)
            monster.attack = 0
            monster.defence = 0
            monster.xp = 0
            treasure_hunter = True
        else:
            monster = await generate_encounter(player, monster, is_treasure=False)
            if monster.level <= 20:
                monster.xp *= 2
            else:
                monster.xp = int(monster.xp * 1.3)

        self.bot.logger.info(monster)

        if player.armor_passive == "Omnipotent" and random.random() < 0.2:
            monster.attack = 0
            monster.defence = 0
            self.bot.logger.info("Omnipotent passive: Monster attack and defense set to 0")

        greed_good = False
        if player.armor_passive == "Unlimited Wealth" and random.random() < 0.2:
            player.rarity *= 5
            self.bot.logger.info(f"Unlimited Wealth passive: Player rarity multiplied by 5 to {player.rarity}")
            greed_good = True

        if "Enfeeble" in monster.modifiers:
            player.attack = int(player.attack * 0.9)
            self.bot.logger.info(f"Enfeeble modifier applied: Player attack reduced to {player.attack}")

        player.rarity += len(monster.modifiers) * 30
        attack_message = ""
        monster_message = ""
        heal_message = ""
        pause_message = ""
        self.bot.logger.info(player)

        start_combat = False
        try:
            if "Shield-breaker" in monster.modifiers:
                player.ward = 0
                self.bot.logger.info(f"Shield-breaker modifier applied: player ward is now 0")

            if "Impenetrable" in monster.modifiers:
                player.crit += 5
                self.bot.logger.info(f"Impenetrable applied: beat {player.crit} to crit")

            if "Unblockable" in monster.modifiers:
                player.block = 0
                self.bot.logger.info(f"Unblockable applied: {player.block} to 0")

            if "Unavoidable" in monster.modifiers:
                player.evasion = 0
                self.bot.logger.info(f"Unavoidable applied: {player.evasion} to 0")  

            if "Temporal Bubble" in monster.modifiers:
                player.weapon_passive = "none"
                self.bot.logger.info(f"Temporal bubble applied: {player.weapon_passive} to nothing")     

            mod_text = " "
            modifiers_title = ""
            mods_space = ""
            if len(monster.modifiers) > 0:
                mod_text = f" {len(monster.modifiers)}-mod "
                modifiers_title = "\n__Modifiers__\n"
                mods_space = "\n"
            get_hit_chance = calculate_monster_hit_chance(player, monster)
            embed = discord.Embed(
                title=f"Witness {player.name} (Level {player.level})",
                description=(f"A{mod_text}level **{monster.level}** {monster.name} approaches!\n"
                                f"{modifiers_title}" +
                            "\n".join([f"**{m}**: {get_modifier_description(m)}" for m in monster.modifiers]) +
                            f"{mods_space}"
                            f"\n~{int(calculate_hit_chance(player, monster) * 100)}% to hit | "
                            f"~{int(get_hit_chance * 100) - int((player.evasion * 0.25 + 1) * get_hit_chance)}% to get hit"),
                color=0x00FF00,
            )
            embed.set_image(url=monster.image) # SET IMAGE HERE
            embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
            if player.ward > 0:
                embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)", inline=True)
            else:
                embed.add_field(name="❤️ HP", value=player.hp, inline=True)
            items = await self.bot.database.fetch_user_weapons(user_id)
            accs = await self.bot.database.fetch_user_accessories(user_id)
            arms = await self.bot.database.fetch_user_armors(user_id)
            if len(items) > 60:
                embed.add_field(name="🚫 WARNING 🚫", value="Weapon pouch is full! Weapons can't drop.", inline=False)
            if len(accs) > 60:
                embed.add_field(name="🚫 WARNING 🚫", value="Accessory pouch is full! Accessories can't drop.", inline=False)
            if len(arms) > 60:
                embed.add_field(name="🚫 WARNING 🚫", value="Armor pouch is full! Armor can't drop.", inline=False)

            # Check armor passives that affect the start of combat
            if player.armor_passive == "Treasure Hunter" and treasure_hunter == True:
                embed.add_field(name="Armor Passive",
                    value="The **Treasure Hunter** armor imbues with power! A mysterious being appears.",
                    inline=False)

            player.invulnerable = False
            if player.armor_passive == "Invulnerable" and random.random() < 0.2:
                embed.add_field(name="Armor Passive",
                                value="The **Invulnerable** armor imbues with power!",
                                inline=False)
                player.invulnerable = True

            if player.armor_passive == "Omnipotent" and monster.attack == 0 and monster.defence == 0:
                embed.add_field(name="Armor Passive",
                                value=f"The **Omnipotent** armor imbues with power! The {monster.name} trembles in **terror**.",
                                inline=False)
                
            if player.armor_passive == "Unlimited Wealth" and greed_good:
                embed.add_field(name="Armor Passive",
                                value=f"The **Unlimited Wealth** armor imbues with power! {player.name}'s greed knows no bounds.",
                                inline=False)

            # Existing passive checks (Absorb, Polished, Sturdy, Accuracy)
            if player.acc_passive == "Absorb":
                absorb_chance = player.acc_lvl * 10
                if random.randint(1, 100) <= absorb_chance:
                    monster_stats = monster.attack + monster.defence
                    absorb_amount = int(monster_stats * 0.10)
                    player.attack += absorb_amount
                    player.defence += absorb_amount
                    embed.add_field(name="Accessory passive",
                                    value=f"The accessory's 🌀 **Absorb ({player.acc_lvl})** activates!\n"
                                            f"⚔️ boosted by **{absorb_amount}**\n"
                                            f"🛡️ boosted by **{absorb_amount}**",
                                    inline=False)
            polished_passives = ["polished", "honed", "gleaming", "tempered", "flaring"]
            if player.weapon_passive in polished_passives:
                value = polished_passives.index(player.weapon_passive)
                defence_reduction = (value + 1) * 0.08
                monster.defence = int(monster.defence * (1 - defence_reduction))
                embed.add_field(name="Weapon passive",
                                value=f"The **{player.weapon_passive}** weapon 💫 shines with anticipation!\n"
                                        f"It reduces the {monster.name}'s defence by {defence_reduction}%.",
                                inline=False)
            sturdy_passives = ["sturdy", "reinforced", "thickened", "impregnable", "impenetrable"]
            if player.weapon_passive in sturdy_passives:
                value = sturdy_passives.index(player.weapon_passive)
                defence_bonus = int((1 + value) * 0.08 * player.defence)
                embed.add_field(name="Weapon passive",
                                value=f"The **{player.weapon_passive}** weapon strengthens resolve!\n"
                                        f"🛡️ boosted by **{defence_bonus}**!",
                                inline=False)
                player.defence += defence_bonus
                                        
            if (is_heaven_door or is_hell_door):
                message: Message = await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
                message: Message = await interaction.original_response()
            start_combat = True
        except Exception as e:
            self.bot.logger.info(e)
            await interaction.response.send_message("The servers are busy handling another request. Try again.")
            self.bot.state_manager.clear_active(user_id)
            return

        reactions = ["⚔️", "🩹", "⏩", "🏃", "🕒"]
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in reactions))
        if start_combat:
            while True:
                def check(reaction, user):
                    return (user == interaction.user
                            and reaction.message.id == message.id
                            and str(reaction.emoji) in ["⚔️", "🩹", "⏩", "🏃", "🕒"])

                try:
                    heal_message = ""
                    attack_message = ""
                    monster_message = ""
                    pause_message = ""

                    reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)
                    if str(reaction.emoji) == "⚔️":
                        await message.remove_reaction(reaction.emoji, user)
                        monster, attack_message = await self.player_turn(player, monster)

                        if monster.hp > 0:
                            player, monster_message = await self.monster_turn(player, monster)

                        if player.hp <= 0:
                            await self.handle_defeat(message, player, monster)
                            self.bot.state_manager.clear_active(user_id)
                            break

                        if monster.hp <= 0:
                            await self.handle_victory(interaction, message, player, monster)
                            self.bot.state_manager.clear_active(user_id)
                            break

                    elif str(reaction.emoji) == "⏩":
                        self.bot.logger.info('Start auto battle')
                        pause_message = ""
                        await message.remove_reaction(reaction.emoji, user)
                        player, monster = await self.auto_battle(interaction, message, embed, player, monster)
                        if (monster.hp > 0 or player.hp < 0):
                            self.bot.logger.info('Pause auto battle')
                            pause_message = "Player HP < 20%, auto-battle paused!"
                        else:
                            return

                    elif str(reaction.emoji) == "🕒":
                        self.bot.logger.info('Start giga-auto battle')
                        pause_message = ""
                        await message.remove_reaction(reaction.emoji, user)
                        player, monster = await self.giga_auto_battle(interaction, message, embed, player, monster)
                        if (monster.hp > 0 or player.hp < 0):
                            self.bot.logger.info('Pause giga-auto battle')
                            pause_message = "Player HP < 20%, auto-battle paused!"
                        else:
                            return

                    elif str(reaction.emoji) == "🩹":
                        await message.remove_reaction(reaction.emoji, user)
                        player, heal_message = await self.heal(player)

                    elif str(reaction.emoji) == "🏃":
                        await message.clear_reactions()
                        embed.add_field(name="Escape", value="Got away safely!", inline=False)
                        await message.edit(embed=embed)
                        self.bot.state_manager.clear_active(user_id)
                        break

                    embed.clear_fields()
                    embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
                    if player.ward > 0:
                        embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)", inline=True)
                    else:
                        embed.add_field(name="❤️ HP", value=player.hp, inline=True)

                    if attack_message:
                        embed.add_field(name=player.name, value=attack_message, inline=False)
                    if monster_message:
                        embed.add_field(name=monster.name, value=monster_message, inline=False)
                    if heal_message:
                        embed.add_field(name="Heal", value=heal_message, inline=False)
                    if pause_message:
                        embed.add_field(name="A temporary reprieve!", value=pause_message, inline=False)
                    await message.edit(embed=embed)

                except asyncio.TimeoutError:
                    embed.add_field(name=monster.name,
                                    value=f"The {monster.name} loses interest.\n"
                                            f"{player.name} failed to grasp the moment.",
                                    inline=False)
                    await message.edit(embed=embed)
                    await message.clear_reactions()
                    self.bot.state_manager.clear_active(user_id)
                    await self.bot.database.update_player(player)
                    break

    async def handle_boss_encounter(self, interaction, player, type):
        if (type == 'aphrodite'):
            phases = [
                {"name": "Aphrodite, Heaven's Envoy", "level": 886, "modifiers_count": 3, "hp_multiplier": 1.5},
                {"name": "Aphrodite, the Eternal", "level": 887, "modifiers_count": 6, "hp_multiplier": 2},
                {"name": "Aphrodite, Harbinger of Destruction", "level": 888, "modifiers_count": 9, "hp_multiplier": 2.5},
            ]
        elif (type == 'lucifer'):
            phases = [
                {"name": "Lucifer, Fallen", "level": 663, "modifiers_count": 1, "hp_multiplier": 1.25},
                {"name": "Lucifer, Maddened", "level": 664, "modifiers_count": 2, "hp_multiplier": 1.5},
                {"name": "Lucifer, Enraged", "level": 665, "modifiers_count": 3, "hp_multiplier": 1.75},
                {"name": "Lucifer, Unbound", "level": 666, "modifiers_count": 4, "hp_multiplier": 2},
            ]

        for phase in phases:
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
                flavor=""
            )
            monster = await generate_encounter(player, monster, is_treasure=False)
            self.bot.logger.info(player)
            self.bot.logger.info(monster)

            # Override with phase-specific modifiers
            available_modifiers = get_monster_mods()
            available_modifiers.remove("Glutton")
            monster.modifiers = []
            if (type == 'lucifer'):
                self.bot.logger.info('Boss specific mod')
                boss_modifiers = get_boss_mods()
                boss_mod = random.choice(boss_modifiers)
                if (boss_mod == "Celestial Watcher"):
                    available_modifiers.remove("All-seeing")
                    available_modifiers.remove("Venomous")
                elif (boss_mod == "Unlimited Blade Works"):
                    available_modifiers.remove("Mirror Image")
                elif (boss_mod == "Hell's Fury"):
                    available_modifiers.remove("Strengthened")
                elif (boss_mod == "Hell's Precision"):
                    available_modifiers.remove("Hellborn")
                elif (boss_mod == "Absolute"):
                    available_modifiers.remove("Ascended")
                elif (boss_mod == "Infernal Legion"):
                    available_modifiers.remove("Summoner")
                elif (boss_mod == "Overwhelm"):
                    available_modifiers.remove("Shield-breaker")
                    available_modifiers.remove("Unblockable")
                    available_modifiers.remove("Unavoidable")
                monster.modifiers.append(boss_mod)
            
            for _ in range(phase["modifiers_count"]):
                if available_modifiers:
                    modifier = random.choice(available_modifiers)
                    monster.modifiers.append(modifier)
                    available_modifiers.remove(modifier)
            
            if "Absolute" in monster.modifiers:
                monster.attack += 25
                monster.defence += 25
            if "Ascended" in monster.modifiers:
                monster.attack += 10
                monster.defence += 10
            if "Steel-born" in monster.modifiers:
                monster.defence = int(monster.defence * 1.1)

            # Calculate monster HP
            monster.hp = random.randint(0, 9) + int(10 * (monster.level ** random.uniform(1.25, 1.35)))
            monster.hp = int(monster.hp * phase["hp_multiplier"])
            monster.max_hp = monster.hp
            monster.xp = monster.hp

            if "Glutton" in monster.modifiers:
                monster.hp = int(monster.hp * 1.5)
                monster.max_hp = monster.hp
                self.bot.logger.info(f"Glutton modifier applied: Monster HP doubled to {monster.hp}")
            
            # Apply Enfeeble modifier
            if "Enfeeble" in monster.modifiers:
                player.attack = int(player.attack * 0.9)
                self.bot.logger.info(f"Enfeeble modifier applied: Player attack reduced to {player.attack}")

            # Apply other modifiers
            if "Shield-breaker" in monster.modifiers or "Overwhelm" in monster.modifiers:
                player.ward = 0
            if "Unblockable" in monster.modifiers or "Overwhelm" in monster.modifiers:
                player.block = 0
            if "Unavoidable" in monster.modifiers or "Overwhelm" in monster.modifiers:
                player.evasion = 0

            if "Impenetrable" in monster.modifiers:
                player.crit += 5

            # Fetch monster details
            monster = await fetch_monster_image(phase["level"], monster)
            if (type == 'aphrodite'):
                desc = f"🐉**{monster.name}**🪽 descends!\n"
            elif (type == 'lucifer'):
                desc = f"😈 **{monster.name}** 😈 ascends!\n"

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

            # Omnipotent: 20% chance to set monster's attack and defense to 0
            if player.armor_passive == "Omnipotent" and random.random() < 0.2:
                monster.attack = 0
                monster.defence = 0
                self.bot.logger.info("Omnipotent passive: Monster attack and defense set to 0")

            player.invulnerable = False
            if player.armor_passive == "Invulnerable" and random.random() < 0.2:
                embed.add_field(name="Armor Passive",
                                value="The **Invulnerable** armor imbues with power!",
                                inline=False)
                player.invulnerable = True
                    
            greed_good = False
            if player.armor_passive == "Unlimited Wealth" and random.random() < 0.2:
                player.rarity *= 2
                self.bot.logger.info(f"Unlimited Wealth passive: Player rarity multiplied by 2 to {player.rarity}")
                greed_good = True    

            if player.armor_passive == "Omnipotent" and monster.attack == 0 and monster.defence == 0:
                embed.add_field(name="Armor Passive",
                                value=f"The **Omnipotent** armor imbues with power! The {monster.name} trembles in **terror**.",
                                inline=False)

            if player.armor_passive == "Unlimited Wealth" and greed_good:
                embed.add_field(name="Armor Passive",
                                value=f"The **Unlimited Wealth** armor imbues with power! {player.name}'s greed knows no bounds.",
                                inline=False)

            embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
            embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)" if player.ward > 0 else player.hp, inline=True)                                                     
            await interaction.edit_original_response(embed=embed)
            message = await interaction.original_response()
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
                        player, monster = await self.boss_auto_battle(message, embed, player, monster)
                        self.bot.logger.info('Boss auto-battle ended')
                        if player.hp <= 0:
                            await self.handle_boss_defeat(message, player, monster, type)
                        elif monster.hp <= 0 and phase == phases[-1]:
                            self.bot.logger.info(f'Won full fight')
                            await self.handle_boss_victory(interaction, message, player, monster, type)
                            return
                        elif (monster.hp > 0):
                            self.bot.logger.info('Pause auto battle')
                            pause_message = "Player HP < 20%, auto-battle paused!"

                    elif str(reaction.emoji) == "🩹":
                        await message.remove_reaction(reaction.emoji, user)
                        player, heal_message = await self.heal(player)

                    # if len(embed.fields) > 5:
                    embed.clear_fields()
                    embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
                    embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)" if player.ward > 0 else player.hp, inline=True)
                    if attack_message:
                        embed.add_field(name=player.name, value=attack_message, inline=False)
                    if monster_message:
                        embed.add_field(name=monster.name, value=monster_message, inline=False)
                    if heal_message:
                        embed.add_field(name="Heal", value=heal_message, inline=False)
                    if pause_message:
                        embed.add_field(name="A temporary reprieve!", value=pause_message, inline=False)
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

    async def player_turn(self, player, monster):
        attack_message = ""
        echo_damage = 0
        actual_hit = 0
        echo_hit = False
        passive_message = ""
        attack_multiplier = 1

        if player.acc_passive == "Obliterate":
            double_damage_chance = player.acc_lvl * 2
            if random.randint(1, 100) <= double_damage_chance:
                passive_message += f"**Obliterate ({player.acc_lvl})** activates, doubling 💥 damage dealt!\n"
                attack_multiplier = 2

        if player.armor_passive == "Mystical Might" and random.random() < 0.2:
            attack_multiplier *= 10
            passive_message += "The **Mystical Might** armor imbues with power!\n"

        hit_chance = calculate_hit_chance(player, monster)
        miss_chance = 100 - (hit_chance * 100)
        attack_roll = random.randint(0, 100)
        acc_value = 0
        accuracy_passives = ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"]
        if player.weapon_passive in accuracy_passives:
            acc_value = (1 + accuracy_passives.index(player.weapon_passive)) * 4
            passive_message += f"The **{player.weapon_passive}** weapon boosts 🎯 accuracy by **{acc_value}%**!\n"
            attack_roll += acc_value

        if player.acc_passive == "Lucky Strikes":
            lucky_chance = player.acc_lvl / 10 # 10% per acc level
            if random.random() <= lucky_chance:
                attack_roll2 = random.randint(0, 100)
                self.bot.logger.info(f"Lucky strikes modifier applied: max of {attack_roll} and {attack_roll2}, picking max")
                attack_roll = max(attack_roll, attack_roll2)
                self.bot.logger.info(f"Lucky strikes modifier applied: picks {attack_roll}")
                passive_message += f"**Lucky Strikes ({player.acc_lvl})** activates!\nHit chance is now 🍀 lucky!\n"

        if "Suffocator" in monster.modifiers and random.random() < 0.2:
            passive_message += f"You have been suffocated!\nHit chance is now 💀 unlucky!\n"
            attack_roll2 = random.randint(0, 100)
            self.bot.logger.info(f"Suffocator modifier applied: min of {attack_roll} and {attack_roll2}, picking minimum")
            attack_roll = min(attack_roll, attack_roll2)
            self.bot.logger.info(f"Suffocator set attack_roll to {attack_roll}")
            
        weapon_crit = 0
        crit_passives = ["piercing", "keen", "incisive", "puncturing", "penetrating"]
        if player.weapon_passive in crit_passives:
            value = crit_passives.index(player.weapon_passive)
            weapon_crit = (value + 1) * 5

        if "Shields-up" in monster.modifiers and random.random() < 0.1:
            attack_multiplier = 0
            passive_message += f"{monster.name} projects a powerful magical barrier!\n"

        # Handle Crit scenario
        # Calculate actual_hit under a crit scenario
        if (attack_roll - acc_value) > (player.crit - weapon_crit):
            max_hit = player.attack
            actual_hit = (random.randint(int(max_hit / 2) + 1, max_hit) * 2) * attack_multiplier
            attack_message = (
                (f"The **{player.weapon_passive}** weapon glimmers with power!\n" if weapon_crit > 0 else '') +
                f"Critical! Damage: 🗡️ **{actual_hit}**")
            attack_message = passive_message + attack_message
        # Handle a normal hit scenario
        elif attack_roll >= miss_chance:
            #  If burning passive, max_hit increases, otherwise it's the player's attack stat
            burning_passives = ["burning", "flaming", "scorching", "incinerating", "carbonising"]
            if player.weapon_passive in burning_passives:
                value = burning_passives.index(player.weapon_passive)
                burning_damage = (value + 1) * 0.08
                max_hit = player.attack + int(player.attack * burning_damage)
                attack_message = (f"The **{player.weapon_passive}** weapon 🔥 burns bright!\n"
                                  f"Attack boosted by **{int(player.attack * burning_damage)}**\n")
            else:
                max_hit = player.attack

            # If sparking passives, min_hit increases, otherwise it's between 
            # We calculate actual_hit here
            sparking_passives = ["sparking", "shocking", "discharging", "electrocuting", "vapourising"]
            if player.weapon_passive in sparking_passives:
                value = sparking_passives.index(player.weapon_passive)
                sparking_damage = (value + 1) * 0.08
                min_damage = int(max_hit * sparking_damage)
                attack_message = (f"The **{player.weapon_passive}** weapon surges with ⚡ lightning!\n")
                actual_hit = (random.randint(min_damage, max_hit)) * attack_multiplier
            # Handle non-sparking normal hit
            else:
                actual_hit = random.randint(1, max_hit) * attack_multiplier
                echo_hit = False
                echo_passives = ["echo", "echoo", "echooo", "echoooo", "echoes"]
                if player.weapon_passive in echo_passives:
                    value = echo_passives.index(player.weapon_passive)
                    echo_multiplier = (value + 1) * 0.10
                    echo_damage = int(actual_hit * echo_multiplier)
                    actual_hit += echo_damage
                    echo_hit = True

            attack_message += f"Hit! Damage: 💥 **{actual_hit - echo_damage}**\n"
            attack_message = passive_message + attack_message
            if echo_hit:
                attack_message += (f"The **{player.weapon_passive}** weapon 🎶 echoes the hit!\n"
                                   f"Echo damage: 💥 **{echo_damage}**\n")
            
        else:
            poisonous_passives = ["poisonous", "noxious", "venomous", "toxic", "lethal"]
            if player.weapon_passive in poisonous_passives:
                value = poisonous_passives.index(player.weapon_passive)
                poison_multiplier = (value + 1) * 0.08
                poison_damage = (random.randint(1, int(player.attack * poison_multiplier))) * attack_multiplier
                if poison_damage >= monster.hp:
                    poison_damage = monster.hp
                monster.hp -= poison_damage
                attack_message = passive_message + f"Miss!\n The **{player.weapon_passive}** weapon deals {poison_damage} poison 🐍 damage."
            else:
                attack_message = passive_message + f"Miss!"

        # Finally calculate the actual damage done
        if "Titanium" in monster.modifiers:
            self.bot.logger.info(f"Titanium modifier applied: actual damage reduced")
            actual_hit = int(actual_hit * 0.9)

        # If the monster would die
        if (actual_hit > monster.hp):
            if "Time Lord" in monster.modifiers and random.random() < 0.8:
                self.bot.logger.info(f"Time Lord modifier applied: doesn't die")
                actual_hit = monster.hp - 1
                attack_message += f"\nA fatal blow was dealt, but **{monster.name}** cheats death!"
            else:
                actual_hit = monster.hp

        monster.hp -= actual_hit
        if check_cull(player, monster):
            self.bot.logger.info(f"Monster has been culled from {monster.hp}")
            attack_message += f"\n{player.name} puts everything on the line, dealing 🪓 __**{monster.hp - 1}**__ damage!"
            monster.hp = 1

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

        heal_amount = int((player.max_hp / 10 * 3) + random.randint(1, 6))  # Heal formula
        new_hp = min(player.max_hp, player.hp + heal_amount)  # Update current HP, max to max HP
        player.hp = new_hp

        heal_message = (f"{player.name} heals for **{heal_amount}** HP!\n"
                        f"**{player.potions - 1}** potions left.")
        player.potions -= 1
        return player, heal_message

    async def monster_turn(self, player, monster):
        if player.invulnerable == True:
            #self.bot.logger.info("Invulnerable passive active: No damage taken")
            monster_message = f"The **Invulnerable** armor imbues with power and absorbs all damage!"
            return player, monster_message
        
        evade_chance = 0.01 + player.evasion / 400
        # self.bot.logger.info(f'{evade_chance} evasion')
        monster_hit_chance = calculate_monster_hit_chance(player, monster)
        # self.bot.logger.info(f'monster_hit_chance = {monster_hit_chance}')
        monster_attack_roll = random.random() + evade_chance
        # self.bot.logger.info(f'monster_attack_roll = {monster_attack_roll}')
        if "Lucifer-touched" in monster.modifiers and random.random() < 0.5:
                monster_attack_roll2 = random.random()
                #self.bot.logger.info(f"Lucifer-touched modifier applied: min between {monster_attack_roll:.2f} and {monster_attack_roll2:.2f}")
                monster_attack_roll = min(monster_attack_roll, monster_attack_roll2)
                #self.bot.logger.info(f"Lucifer-touched modifier applied: attack roll is now {monster_attack_roll:.2f}")

        if "All-seeing" in monster.modifiers:
            monster_attack_roll = monster_attack_roll * 0.9
            self.bot.logger.info(f"All-seeing modifier applied: Monster attack roll reduced to {monster_attack_roll:2f}")

        if "Celestial Watcher" in monster.modifiers:
            monster_attack_roll = 0
            self.bot.logger.info(f"Celestial modifier applied: Monster attack roll is now 0")

        if monster_attack_roll <= monster_hit_chance:
            # self.bot.logger.info(f'monster_attack_roll <= monster_hit_chance, take damage')
            damage_taken = calculate_damage_taken(player, monster)

            if "Celestial Watcher" in monster.modifiers:
                damage_taken = int(damage_taken * 0.8)
                self.bot.logger.info(f"Celestial modifier applied: damage_taken reduced")
            
            if "Hellborn" in monster.modifiers:
                damage_taken += 2
                self.bot.logger.info(f"Hellborn modifier applied: Damage taken boosted")
            
            if "Hell's Fury" in monster.modifiers:
                damage_taken += 3
                self.bot.logger.info(f"Hell's Fury modifier applied: Damage taken boosted")

            minion_dmg = 0
            if "Summoner" in monster.modifiers:
                minion_dmg = int(damage_taken / 3)
                self.bot.logger.info(f"Summoner modifier applied: calculated minion_dmg: {minion_dmg}")
            if "Infernal Legion" in monster.modifiers:
                minion_dmg = int(damage_taken)
                self.bot.logger.info(f"Summoner modifier applied: calculated minion_dmg: {minion_dmg}")
            
            multi_dmg = 0
            if "Multistrike" in monster.modifiers:
                monster_attack_roll2 = random.random()
                if monster_attack_roll2 <= monster_hit_chance: 
                    multi_dmg += int(0.5 * calculate_damage_taken(player, monster))
                    damage_taken += multi_dmg
                self.bot.logger.info(f"Multistrike modifier applied")

            # self.bot.logger.info(f"{damage_taken} pre block")
            is_blocked = False
            if (random.random() <= (player.block / 200 + 0.01)):
                damage_taken = 0
                is_blocked = True
                self.bot.logger.info(f"all damage blocked")
            if "Mirror Image" in monster.modifiers and random.random() < 0.2:
                damage_taken *= 2
                self.bot.logger.info(f"Mirror Image modifier applied: Damage doubled to {damage_taken}")
            
            if "Unlimited Blade Works" in monster.modifiers:
                damage_taken *= 2
                self.bot.logger.info(f"UBW: Damage doubled to {damage_taken}")
            
            is_executed = False
            if "Executioner" in monster.modifiers and random.random() < 0.01:
                executed_damage = int(player.hp * 0.9)
                damage_taken = executed_damage
                self.bot.logger.info(f"Executioner modifier applied: Damage set to {damage_taken}")
            if player.ward > 0:
                player.ward -= damage_taken
                if player.ward < 0:
                    player.hp += player.ward
            else:
                player.hp -= damage_taken
            if is_blocked:
                monster_message = f"The {monster.name} {monster.flavor}, but your armor blocks all damage!\n"
            else:
                monster_message = f"{monster.name} {monster.flavor}.\nDamage: 💥 **{damage_taken}**"
            if is_executed:
                monster_message = (f"{monster.name} summons a monstrous executioner's axe.\n"
                                  f"It swings, shattering your very existence.\nDamage: 💥 **{damage_taken}**")
            if (minion_dmg > 0):
                monster_message += f"\nTheir minions attack!\nDamage: 💥 **{minion_dmg}**"
            if (multi_dmg > 0):
                monster_message += f"\nThe monster strikes again in succession!\nDamage: 💥 **{multi_dmg}**"
        else:
            if "Venomous" in monster.modifiers:
                player.hp = max(1, player.hp - 1)
                monster_message = f"{monster.name} misses, but their **Venomous** aura deals **1** 🐍 damage!"
            else:
                monster_message = f"{monster.name} misses!"

        return player, monster_message

    async def auto_battle(self, interaction, message, embed, player, monster):
        minimum_hp = int(player.max_hp * 0.2)
        while player.hp > minimum_hp and monster.hp > 0:
            monster, attack_message = await self.player_turn(player, monster)

            if monster.hp <= 0:
                await self.handle_victory(interaction, message, player, monster)
                return player, monster

            player, monster_message = await self.monster_turn(player, monster)

            if player.hp <= 0:
                await self.handle_defeat(message, player, monster)
                return player, monster

            embed.clear_fields()
            embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
            if player.ward > 0:
                embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)", inline=True)
            else:
                embed.add_field(name="❤️ HP", value=player.hp, inline=True)
            embed.add_field(name=player.name, value=attack_message, inline=False)
            embed.add_field(name=monster.name, value=monster_message, inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(1)
        return player, monster
    

    async def giga_auto_battle(self, interaction, message, embed, player, monster):
        minimum_hp = int(player.max_hp * 0.2)
        turn_count = 0
        last_attack_message = ""
        last_monster_message = ""

        while player.hp > minimum_hp and monster.hp > 0:
            turn_count += 1

            monster, attack_message = await self.player_turn(player, monster)
            last_attack_message = attack_message

            if monster.hp <= 0:
                await self.handle_victory(interaction, message, player, monster)
                return player, monster
            
            # Monster turn
            player, monster_message = await self.monster_turn(player, monster)
            last_monster_message = monster_message

            # Defeat check
            if player.hp <= 0:
                await self.handle_defeat(message, player, monster)
                return player, monster
            
            # Update embed every 10 turns or when HP is low
            if turn_count % 10 == 0 or player.hp <= minimum_hp:
                embed.clear_fields()
                embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
                embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)" if player.ward > 0 else player.hp, inline=True)
                embed.add_field(name=player.name, value=last_attack_message, inline=False)
                embed.add_field(name=monster.name, value=last_monster_message, inline=False)
                if player.hp <= minimum_hp:
                    embed.add_field(name="Auto battle", value="Player HP < 20%, auto-battle paused!", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(1)
        return player, monster
    

    async def boss_auto_battle(self, message, embed, player, monster):
        minimum_hp = int(player.max_hp * 0.2)
        while player.hp > minimum_hp and monster.hp > 0:
            monster, attack_message = await self.player_turn(player, monster)

            if monster.hp <= 0:
                return player, monster
            
            player, monster_message = await self.monster_turn(player, monster)

            if player.hp <= 0:
                return player, monster

            embed.clear_fields()
            embed.add_field(name="🐲 HP", value=monster.hp, inline=True)
            if player.ward > 0:
                embed.add_field(name="❤️ HP", value=f"{player.hp} ({player.ward} 🔮)", inline=True)
            else:
                embed.add_field(name="❤️ HP", value=player.hp, inline=True)
            embed.add_field(name=player.name, value=attack_message, inline=False)
            embed.add_field(name=monster.name, value=monster_message, inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(1)
        return player, monster

    # Handle normal combat victories
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
            drop_chance = 0
            reward_scale = int(player.level / 10)
        else:
            drop_chance = 90
            reward_scale = (monster.level - player.level) / 10

        rarity = player.rarity / 100
        drop_roll = random.randint(1, 100) + int(100 - player.level)
        loot_roll = random.randint(1, 100)
        acc_roll = random.randint(1, 100)
        arm_roll = random.randint(1, 100)
        final_loot_roll = loot_roll
        final_acc_roll = acc_roll
        final_arm_roll = arm_roll
        if player.rarity > 0:
            drop_roll = int(drop_roll + (10 * rarity))
            final_loot_roll = int(loot_roll + (10 * rarity))
            final_acc_roll = int(acc_roll + (10 * rarity))
            final_arm_roll = int(arm_roll + (10 * rarity))
            self.bot.logger.info(f"User has {rarity} RAR: "
                f"Rolls: {drop_roll} loot, "
                f"{final_loot_roll} wep, "
                f"{final_acc_roll} acc, "
                f"{final_arm_roll} armor")

        gold_award = int((monster.level ** random.uniform(1.4, 1.6)) * (1 + (reward_scale ** 1.3)))
        if player.rarity > 0:
            final_gold_award = int(gold_award * (1.5 + rarity))
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
        weapon_dropped = False
        acc_dropped = False
        arm_dropped = False
        if (drop_roll >= drop_chance):
            if final_loot_roll >= 90:
                weapon_dropped = True
                if len(items) > 60:
                    embed.add_field(name="✨ Loot", value="Weapon pouch full!")
                else:
                    weapon = await generate_weapon(user_id, monster.level, drop_rune=True)
                    if weapon.passive != "Rune of Refinement":
                        embed.set_thumbnail(url="https://i.imgur.com/mEIV0ab.jpeg")
                        await self.bot.database.create_weapon(weapon)
                    else:
                        embed.set_thumbnail(url="https://i.imgur.com/1tcMeSe.jpeg")
                        await self.bot.database.update_refinement_runes(user_id, 1)  # Increment runes
                    embed.add_field(name="✨ Loot", value=f"{weapon.description}", inline=False)

            if not weapon_dropped:
                if final_acc_roll >= 95:
                    acc_dropped = True
                    if len(accs) > 60:
                        embed.add_field(name="✨ Loot", value="Accessory pouch full!")
                    else:
                        acc = await generate_accessory(user_id, monster.level, drop_rune=True)
                        if acc.name != "Rune of Potential":
                            await self.bot.database.create_accessory(acc)
                            embed.set_thumbnail(url="https://i.imgur.com/KRZUDyO.jpeg")
                        else:
                            await self.bot.database.update_potential_runes(user_id, 1)  # Increment runes
                            embed.set_thumbnail(url="https://i.imgur.com/aeorjQG.jpeg")
                        embed.add_field(name="✨ Loot", value=f"{acc.description}", inline=False)

            if not weapon_dropped and not acc_dropped:
                if (len(arms) > 60):
                    embed.add_field(name="✨ Loot", value="Armor pouch full!")
                else:
                    if final_arm_roll >= 97:
                        arm_dropped = True
                        armor = await generate_armor(user_id, monster.level, drop_rune=True)
                        if armor.name != "Rune of Imbuing":
                            await self.bot.database.create_armor(armor)
                            embed.set_thumbnail(url="https://i.imgur.com/jtYg94i.png")
                        else:
                            await self.bot.database.update_imbuing_runes(user_id, 1)  # Increment runes
                            embed.set_thumbnail(url="https://i.imgur.com/MHgtUW8.png")
                        
                        embed.add_field(name="✨ Loot", value=f"{armor.description}", inline=False)

        if not weapon_dropped and not acc_dropped and not arm_dropped:
            embed.add_field(name="✨ Loot", value="None")
        if drop_chance == 0:
            embed.add_field(name="✨ Curious Curio", value="A curious curio was left behind!", 
                                    inline=False)
            await self.bot.database.update_curios_count(user_id, server_id, 1)
        if (player.level > 20):
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

        # Everlasting Blessing: Placeholder for 10% chance to propagate ideology
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
            if (followers_count > 1000):
                follower_increase = 100
            else:
                follower_increase = base_followers * (growth_factor ** (followers_count // scaling_factor))
            # Add random variation (±10%)
            variation = random.uniform(0.9, 1.1)
            follower_increase = int(follower_increase * variation)
            new_followers_count = followers_count + follower_increase

            # Calculate gold reward (linear)
            base_gold = 1000
            gold_per_follower = 50
            gold_reward = base_gold + (followers_count * gold_per_follower)

            # Update database
            await self.bot.database.update_followers_count(user_ideology, new_followers_count)
            await self.bot.database.add_gold(user_id, gold_reward)
            await self.bot.database.update_propagate_time(user_id)
            
            propagate_message = (
                f"You advocate for **{user_ideology}** and it spreads!\n"
                f"New followers gained: **{follower_increase}** (Total: **{new_followers_count}**).\n"
                f"Gold collected from followers: **{gold_reward:,} GP**."
            )
            # Send response
            embed.add_field(name=f"{user_ideology} propagated",
                        value=propagate_message,
                        inline=False)

        await message.edit(embed=embed)
        player = await self.update_experience(interaction, message, embed, player, monster)
        await self.bot.database.add_gold(user_id, final_gold_award)
        self.bot.logger.info(player)
        await self.bot.database.update_player(player)

    
    # Handle a normal combat defeat
    async def handle_defeat(self, message, player, monster):
        await message.clear_reactions()
        self.bot.state_manager.clear_active(player.id)
        current_exp = player.exp
        penalty_xp = int(current_exp * 0.1)
        new_exp = int(current_exp - penalty_xp)
        if new_exp < 0:
            new_exp = 0
            
        player.hp = 1
        player.exp = new_exp

        total_damage_dealt = monster.max_hp - monster.hp
        defeat_embed = discord.Embed(
            title="Oh dear...",
            description=f"The {monster.name} deals a fatal blow!\n"
                        f"{player.name} has been defeated after dealing {total_damage_dealt} damage.\n"
                        f"The {monster.name} leaves with {monster.hp} health left.\n"
                        f"Death 💀 takes away {penalty_xp:,} xp from your essence...",
            color=0xFF0000
        )
        defeat_embed.add_field(name="🪽 Redemption 🪽", value=f"({player.name} revives with 1 hp.)")
        await message.edit(embed=defeat_embed)
        await self.bot.database.update_player(player)
    

    # Handle a boss victory
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


    # Handle a boss defeat
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


    # Calculate the player's experience after a combat encounter
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
            await message.edit(embed=embed)
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
            await message.edit(embed=embed)
            new_exp -= exp_table["levels"][str(player.level - 1)]
            player.ascension += 1

        player.exp = new_exp
        return player


async def setup(bot) -> None:
    await bot.add_cog(Combat(bot))