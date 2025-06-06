import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
from datetime import datetime, timedelta
from discord import app_commands, Interaction, Message
from discord.ext.tasks import asyncio
from core.gen_mob import get_modifier_description
from typing import Literal


def get_weapon_passive_effect_mock(passive_name: str, level: int = 5) -> str:
    # This function would replicate the logic from your Weapons cog's get_passive_effect
    # For brevity, I'll include a few examples. You'd need to fill this out.
    effects = {
        "carbonising": "Increases your attack on normal hits. (40%)",
        "lethal": "Additional damage on misses. (up to 50%)",
        "flaring": "Reduce monster's defence. (40%)",
        "vapourising": "Floor of normal hits raised. (40%)",
        "impenetrable": "Additional defence. (40%)", # Weapon passive 'impenetrable'
        "penetrating": "Additional crit chance. (25%)",
        "catastrophic": "Deals a near-fatal blow when monster is at threshold. (40%)",
        "bullseye": "Increased accuracy. (20%)",
        "echoes": "Echo normal hits. (50% dmg)"
    }
    base_passive = passive_name.split(" ")[0].lower() # Get base name if tiered
    return effects.get(base_passive, effects.get(passive_name, "Effect details not available for this weapon passive."))

def get_accessory_passive_effect_mock(passive_name: str, level: int = 5) -> str:
    # Replicate from Accessories cog
    if level == 0: level = 5 # Assume max level for display
    effects = {
        "Obliterate": f"**{level * 2}%** chance to deal double damage.",
        "Absorb": f"**{level * 10}%** chance to absorb 10% of the monster's stats and add them to your own.",
        "Prosper": f"**{level * 10}%** chance to double gold earned.",
        "Infinite Wisdom": f"**{level * 5}%** chance to double experience earned.",
        "Lucky Strikes": f"**{level * 10}%** chance to roll lucky hit chance."
    }
    return effects.get(passive_name, "Effect details not available for this accessory passive.")

def get_armor_passive_effect_mock(passive_name: str, level: int = 1) -> str: # Armor passives aren't leveled in your current example
    # Replicate from Armor cog
    effects = {
        "Invulnerable": "20% chance to take no damage the entire fight.",
        "Mystical Might": "20% chance to deal 10x damage after all calculations.",
        "Omnipotent": "50% chance to double your stats at start of combat (Atk, Def, HP).",
        "Treasure Hunter": "5% additional chance to turn the monster into a loot encounter.",
        "Unlimited Wealth": "20% chance to 5x (2x on bosses) player rarity stat.",
        "Everlasting Blessing": "10% chance on victory to propagate your ideology."
    }
    return effects.get(passive_name, "Effect details not available for this armor passive.")

def get_glove_passive_effect_mock(passive_name: str, level: int = 5) -> str:
    # Replicate from Gloves cog (assuming max level 5 for display)
    if level == 0: level = 5
    effects = {
        "ward-touched": f"Generate **{level * 1}%** of your hit damage as Ward.",
        "ward-fused": f"Generate **{level * 2}%** of your critical hit damage as Ward.",
        "instability": f"All hits deal either 50% or **{150 + (level * 10)}%** of normal damage.",
        "deftness": f"Raises the damage floor of critical hits by **{level * 5}%** (max 75% total at L5).",
        "adroit": f"Raises the damage floor of normal hits by **{level * 2}%**.",
        "equilibrium": f"Gain **{level * 5}%** of hit damage as bonus Experience.",
        "plundering": f"Gain **{level * 10}%** of hit damage as bonus Gold."
    }
    return effects.get(passive_name, "Effect details not available for this glove passive.")

def get_boot_passive_effect_mock(passive_name: str, level: int = 6) -> str:
    # Replicate from Boots cog (assuming max level 6 for display)
    if level == 0: level = 6
    effects = {
        "speedster": f"Combat cooldown reduced by **{level * 20}** seconds.",
        "skiller": f"Grants **{level * 5}%** chance to find extra skill materials on victory.",
        "treasure-tracker": f"Treasure mob chance increased by **{level * 0.5}%**.",
        "hearty": f"Increases maximum HP by **{level * 5}%**.",
        "cleric": f"Potions heal for an additional **{level * 10}%** of their base amount.",
        "thrill-seeker": f"Increases chance for special drops (keys, runes) by **{level * 1}%**."
    }
    return effects.get(passive_name, "Effect details not available for this boot passive.")

class General(commands.Cog, name="general"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.context_menu_user = app_commands.ContextMenu(
            name="Grab ID", callback=self.grab_id
        )
        self.bot.tree.add_command(self.context_menu_user)
        self.context_menu_message = app_commands.ContextMenu(
            name="Remove spoilers", callback=self.remove_spoilers
        )
        self.bot.tree.add_command(self.context_menu_message)
        self.weapon_passives_base = [
            "burning", "poisonous", "polished", "sparking", "sturdy", 
            "piercing", "strengthened", "accurate", "echo"
        ]
        self.weapon_final_tier_map = {
            "burning": "carbonising", "poisonous": "lethal", "polished": "flaring", "sparking": "vapourising",
            "sturdy": "impenetrable", "piercing": "penetrating", "strengthened": "catastrophic",
            "accurate": "bullseye", "echo": "echoes"
        }
        self.accessory_passives = [
            "Obliterate", "Absorb", "Prosper", "Infinite Wisdom", "Lucky Strikes"
        ]
        self.armor_passives = [
            "Invulnerable", "Mystical Might", "Omnipotent", 
            "Treasure Hunter", "Unlimited Wealth", "Everlasting Blessing"
        ]
        self.glove_passives = [
            "ward-touched", "ward-fused", "instability", 
            "deftness", "adroit", "equilibrium", "plundering"
        ]
        self.boot_passives = [
            "speedster", "skiller", "treasure-tracker", 
            "hearty", "cleric", "thrill-seeker"
        ]
        self.monster_modifiers = [ # Sourced from your provided files
            "Steel-born", "All-seeing", "Mirror Image", "Glutton", 
            "Enfeeble", "Venomous", "Strengthened", "Hellborn", "Lucifer-touched", 
            "Titanium", "Ascended", "Summoner", "Shield-breaker", "Impenetrable",
            "Unblockable", "Unavoidable", "Built-different", "Multistrike", "Mighty",
            "Shields-up", "Executioner", "Time Lord", "Suffocator", "Celestial Watcher",
            "Unlimited Blade Works", "Hell's Fury", "Absolute", "Infernal Legion", "Overwhelm",
            "Penetrator", "Clobberer", "Smothering", "Dodgy", "Prescient", "Vampiric"
        ]

    # Message context menu command
    async def remove_spoilers(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """
        Removes the spoilers from the message. This command requires the MESSAGE_CONTENT intent to work properly.

        :param interaction: The application command interaction.
        :param message: The message that is being interacted with.
        """
        spoiler_attachment = None
        for attachment in message.attachments:
            if attachment.is_spoiler():
                spoiler_attachment = attachment
                break
        embed = discord.Embed(
            title="Message without spoilers",
            description=message.content.replace("||", ""),
            color=0xBEBEFE,
        )
        if spoiler_attachment is not None:
            embed.set_image(url=attachment.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # User context menu command
    async def grab_id(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """
        Grabs the ID of the user.

        :param interaction: The application command interaction.
        :param user: The user that is being interacted with.
        """
        embed = discord.Embed(
            description=f"The ID of {user.mention} is `{user.id}`.",
            color=0xBEBEFE,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="help", description="List Idleology's commands"
    )
    async def help(self, interaction: Interaction) -> None:
        # Brief description of Idleology
        game_description = (
            "Welcome to **Idleology**! 💡\n"
            "Once you're /registered, use any of the commands below."
        )

        prefix = "/"
        embed = discord.Embed(
            title="Help",
            description=game_description,
            color=0xBEBEFE
        )

        # Iterate through all cogs
        for cog_name in self.bot.cogs:
            if cog_name == "owner" and not (await self.bot.is_owner(interaction.user)):
                continue
            cog = self.bot.get_cog(cog_name)
            if cog is None:
                self.bot.logger.warning(f"Cog '{cog_name}' not found or not properly initialized.")
                continue

            # Collect hybrid/prefix commands
            hybrid_commands = cog.get_commands()
            command_data = []

            # Add hybrid commands
            for command in hybrid_commands:
                description = command.description.partition("\n")[0] or "No description"
                command_data.append(f"{prefix}{command.name} - {description}")

            # Collect slash commands from the cog
            # Note: Slash commands are stored in the bot's tree, so we filter by cog
            for tree_command in self.bot.tree.get_commands():
                # Check if the command belongs to this cog
                # This assumes slash commands are defined as methods in the cog
                if hasattr(tree_command, "binding") and tree_command.binding == cog:
                    description = tree_command.description or "No description"
                    if isinstance(tree_command, app_commands.Command):
                        command_data.append(f"{prefix}{tree_command.name} - {description}")
                    elif isinstance(tree_command, app_commands.ContextMenu):
                        command_data.append(f"Context: {tree_command.name} - {description}")

            # If there are commands to display, add them to the embed
            if command_data:
                help_text = "\n".join(command_data)
                embed.add_field(
                    name=cog_name.capitalize(),
                    value=f"```{help_text}```",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="getstarted", description="Get information and tips for playing Idleology.")
    async def info(self, interaction: Interaction) -> None:
        """Sends an information embed with gameplay and command instructions."""
        
        embed = discord.Embed(
            title="Welcome to Idleology!",
            description="Here's a quick guide to help you get started.",
            color=0x00FF00
        )
        
        embed.add_field(
            name="How to Play Idleology",
            value=(
                "Idleology is a simple text RPG where you can register with the adventurer's guild, engage in combat, "
                "level up and spread your ideology to progress through the world. "
                "Use the commands below to get started!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Getting Started",
            value=(
                "**1. Register Your Character:**"
                "Use `/register <character_name>` to register with the 🏦 Adventurer's Guild and start your journey!\n"
                "**2. View Your Stats:**"
                "Check your character's stats using `/stats` to track your progress.\n"
                "**3. Choose Your Ideology:**"
                "Create an ideology that best fits you. Use `/ideology` to see the followers leaderboard.\n"
                "**4. Engage in Combat:**"
                "Fight enemies using `/combat` to gain experience and level up!\n"
                "**5. And much more!**\n"
                "Use `/help` for the full list of commands!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Gaining Experience and Leveling Up",
            value=(
                f"In combat, you can earn experience points (XP). "
                f"To level up, keep battling enemies.\n\n"
                f"Here are some points to remember:\n"
                f"- Engage in combat every 10 minutes using the `/combat` command.\n"
                f"- ⚔️ to attack, 🩹 to heal (if you have potions, buy with /shop),"
                f" ⏩ to auto-batle (stops at <20% hp), 🏃 to run\n"
                f" 🕒 to skip to the end (stops at <20% hp)\n"
                f"- Leveling up increases your stats\n"
                f"- You gain some passive points every 10 levels\n"
                f"- The tavern is a great place to rest and make (or lose) some quick cash!\n"
                f"- You also heal over time if you're down on your luck.\n"
                f"- Check your skills with the /skills, /mining, /fishing, /woodcutting commands!"
            ),
            inline=False
        )

        embed.add_field(
            name="Forging and refining weapons",
            value=(
                f"When you win your combats, you have a chance of dropping loot.\n"
                f"Loot drops in the form of weapons, accessories, or equipment\n\n"
                f"Here are some points to remember:\n"
                f"- Weapons can be forged with skilling materials.\n"
                f"- Weapons can be refined with gold.\n"
                f"- Weapons can gain powerful passives via forging.\n"
                f"- Weapons can gain more stats with refining.\n"
                f"- Check your weapons with the /weapons command!"
            ),
            inline=False
        )

        embed.add_field(
            name="Unlocking accessory potential",
            value=(
                f"When you obtain an accessory, you can unlock its potential to gain a passive.\n\n"
                f"Here are some points to remember:\n"
                f"- You are limited to 10 attempts to improve an accessory's potential.\n"
                f"- Each attempt will cost more gold.\n"
                f"- You can increase the success rate with Runes of Potential.\n"
                f"- Check your accessories with the /accessory command!"
            ),
            inline=False
        )

        embed.add_field(
            name="Equipment can gain various bonuses",
            value=(
                f"When you obtain pieces of equipment, they each have their own upgrade system.\n\n"
                f"Check them out with the various equipment commands!"
            ),
            inline=False
        )

        embed.add_field(
            name="Trading with other players",
            value=(
                f"When you have items to trade, use the /ids command to get the ID of the item you want to send.\n\n"
                f"Here are some points to remember:\n"
                f"- This is a trust based system, only trade with those you trust!\n"
                f"- You can send items and gold with their respective commands.\n"
                f"- Report scammers to the admin to get their character deleted and a refund!\n"
            ),
            inline=False
        )

        embed.add_field(
            name="Miscellaneous tips",
            value=(
                f"- Use /cooldowns to see how long until major cooldown commands.\n"
                f"- You passively obtain skilling materials over time, make sure to upgrade your tools on occasion!\n"
                f"- You passively heal over time, make sure to take advantage!\n"
                f"- Be on the lookout for random events, you might be able to score some extra loot.\n"
            ),
            inline=False
        )

        embed.set_footer(text="It's all in the mind.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="cooldowns", description="Check your current cooldowns for various commands.")
    async def cooldowns(self, interaction: Interaction) -> None:
        """Check the cooldowns of /combat, /rest, /checkin, and /propagate commands."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Get user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await interaction.response.send_message(
                "Please /register with the 🏦 Adventurer's Guild first.",
                ephemeral=True
            )
            return

        # Check cooldown for /rest
        last_rest_time = existing_user[13]  # Assuming last_rest_time is at index 13

        cooldown_duration = timedelta(hours=2)
        rest_remaining = None
        if last_rest_time:
            last_rest_time_dt = datetime.fromisoformat(last_rest_time)
            time_since_rest = datetime.now() - last_rest_time_dt
            if time_since_rest < cooldown_duration:
                remaining_time = cooldown_duration - time_since_rest
                rest_remaining = remaining_time
        else:
            # If last_rest_time is None, the user can immediately rest
            rest_remaining = timedelta(0)

        # Check cooldown for /checkin
        last_checkin_time = existing_user[17]
        checkin_remaining = None
        checkin_duration = timedelta(hours=18)
        if last_checkin_time:
            last_checkin_time_dt = datetime.fromisoformat(last_checkin_time)
            if (last_checkin_time_dt > datetime.now()):
                print(f"{last_checkin_time_dt} vs {datetime.now()}")
                checkin_remaining = last_checkin_time_dt - datetime.now()
            else:
                time_since_checkin = datetime.now() - last_checkin_time_dt
                if time_since_checkin < checkin_duration:
                    remaining_time = checkin_duration - time_since_checkin
                    checkin_remaining = remaining_time


        # Check cooldown for /propagate
        last_propagate_time = existing_user[14]  # Index for last_propagate_time (update if necessary)
        propagate_remaining = None
        propagate_duration = timedelta(hours=18)

        if last_propagate_time:
            last_propagate_time_dt = datetime.fromisoformat(last_propagate_time)
            time_since_propagate = datetime.now() - last_propagate_time_dt
            if time_since_propagate < propagate_duration:
                remaining_time = propagate_duration - time_since_propagate
                propagate_remaining = remaining_time
        else:
            propagate_remaining = timedelta(0)  # First propagate

    
        last_combat_time = existing_user[24]
        combat_remaining = None
        combat_duration = timedelta(minutes=10)
        if last_combat_time:
            last_combat_time_dt = datetime.fromisoformat(last_combat_time)
            time_since_combat = datetime.now() - last_combat_time_dt
            if time_since_combat < combat_duration:
                remaining_time = combat_duration - time_since_combat
                combat_remaining = remaining_time
        else:
            combat_remaining = timedelta(0)

        # Creating the embed
        embed = discord.Embed(
            title="Timers",
            color=0x00FF00
        )
        embed.set_thumbnail(url="https://i.imgur.com/I3JPD8R.jpeg")
        # Building the embed fields
        if combat_remaining:
            embed.add_field(name="/combat ⚔️", value=f"**{(combat_remaining.seconds // 60) % 60} minutes "
                                                            f"{(combat_remaining.seconds % 60)} seconds** remaining.")
        else:
            embed.add_field(name="/combat ⚔️", value="Available now!", inline=True)

        if rest_remaining:
            embed.add_field(name="/rest 🛏️", value=f"**{rest_remaining.seconds // 3600} hours "
                                                        f"{(rest_remaining.seconds // 60) % 60} minutes** remaining. (Pay gp to bypass)")
        else:
            embed.add_field(name="/rest 🛏️", value="Available now!", inline=True)

        if checkin_remaining:
            embed.add_field(name="/checkin 🛖", value=f"**{checkin_remaining.seconds // 3600} hours "
                                                            f"{(checkin_remaining.seconds // 60) % 60} minutes** remaining.")
        else:
            embed.add_field(name="/checkin 🛖", value="Available now!", inline=True)

        if propagate_remaining:
            embed.add_field(name="/propagate 💡", value=f"**{propagate_remaining.seconds // 3600} hours "
                                                            f"{(propagate_remaining.seconds // 60) % 60} minutes** remaining.")
        else:
            embed.add_field(name="/propagate 💡", value="Available now!", inline=True)

        # Send the embed message
        await interaction.response.send_message(embed=embed, ephemeral=True)
        message: Message = await interaction.original_response()
        await asyncio.sleep(10)
        await message.delete()


    @app_commands.command(name="ids", description="Fetch your user ID and all item IDs.")
    async def ids(self, interaction: Interaction) -> None:
        """Fetch and display the user's ID along with IDs of their items."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await interaction.response.send_message(
                            "Please /register with the 🏦 Adventurer's Guild first.",
                            ephemeral=True
                        )
            return

        # Fetch user item data
        user_items = await self.bot.database.fetch_user_weapons(user_id)
        user_accs = await self.bot.database.fetch_user_accessories(user_id)
        user_arms = await self.bot.database.fetch_user_armors(user_id)
        # Construct the embed to show information
        embed = discord.Embed(
            title="User ID and Item IDs",
            color=0xBEBEFE
        )
        embed.add_field(name="User ID", value=user_id, inline=False)

        if user_items:
            items_description = "\n".join([f"**ID:** {item[0]} - **Name:** {item[2]}" for item in user_items])
            embed.add_field(name="Your Weapons", value=items_description, inline=False)
            acc_desc = "\n".join([f"**ID:** {acc[0]} - **Name:** {acc[2]}" for acc in user_accs])
            embed.add_field(name="Your Accessories", value=acc_desc, inline=False)
        else:
            embed.add_field(name="Your Items", value="You have no weapons or accessories.", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="mod_details", description="Shows details for specific types of modifiers or passives.")
    @app_commands.describe(category="Choose the category of modifiers/passives to view.")
    async def mod_details(self, interaction: Interaction, 
                          category: Literal['monster', 'weapon', 'accessory', 'armor', 'glove', 'boot']):
        
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_footer(text="Effects for gear passives are generally shown at their maximum potential/level.")
        
        content_added = False

        if category == 'monster':
            embed.title = "👹 Monster Modifier Details"
            mod_text = ""
            for mod_name in sorted(self.monster_modifiers): # Sort for consistent order
                desc = get_modifier_description(mod_name) 
                mod_text += f"**{mod_name}**: {desc}\n"
            if mod_text:
                embed.description = mod_text
                content_added = True
            else:
                embed.description = "No monster modifier details available."

        elif category == 'weapon':
            embed.title = "⚔️ Weapon Passive Details (Max Tier Effects)"
            weapon_text = ""
            for base_passive in sorted(self.weapon_passives_base):
                max_tier_passive = self.weapon_final_tier_map.get(base_passive, base_passive)
                effect = get_weapon_passive_effect_mock(max_tier_passive, 5)
                weapon_text += f"**{max_tier_passive.capitalize()}**: {effect}\n"
            if weapon_text:
                embed.description = weapon_text
                content_added = True
            else:
                embed.description = "No weapon passive details available."

        elif category == 'accessory':
            embed.title = "📿 Accessory Passive Details (Lvl 5 Effects)"
            acc_text = ""
            for passive in sorted(self.accessory_passives):
                effect = get_accessory_passive_effect_mock(passive, 5)
                acc_text += f"**{passive.replace('-', ' ').title()}**: {effect}\n"
            if acc_text:
                embed.description = acc_text
                content_added = True
            else:
                embed.description = "No accessory passive details available."

        elif category == 'armor':
            embed.title = "🛡️ Armor Passive Details"
            armor_text = ""
            for passive in sorted(self.armor_passives):
                effect = get_armor_passive_effect_mock(passive)
                armor_text += f"**{passive.replace('-', ' ').title()}**: {effect}\n"
            if armor_text:
                embed.description = armor_text
                content_added = True
            else:
                embed.description = "No armor passive details available."
                
        elif category == 'glove':
            embed.title = "🧤 Glove Passive Details (Lvl 5 Effects)"
            glove_text = ""
            for passive in sorted(self.glove_passives):
                effect = get_glove_passive_effect_mock(passive, 5)
                glove_text += f"**{passive.replace('-', ' ').title()}**: {effect}\n"
            if glove_text:
                embed.description = glove_text
                content_added = True
            else:
                embed.description = "No glove passive details available."

        elif category == 'boot':
            embed.title = "👢 Boot Passive Details (Lvl 6 Effects)"
            boot_text = ""
            for passive in sorted(self.boot_passives):
                effect = get_boot_passive_effect_mock(passive, 6)
                boot_text += f"**{passive.replace('-', ' ').title()}**: {effect}\n"
            if boot_text:
                embed.description = boot_text
                content_added = True
            else:
                embed.description = "No boot passive details available."
        
        else: # Should not be reached due to Literal choices
            embed.title = "Error"
            embed.description = "Invalid category selected."

        if not content_added and not embed.description: # Fallback if a category somehow has no text
             embed.description = f"No details available for category: {category}."

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot) -> None:
    await bot.add_cog(General(bot))