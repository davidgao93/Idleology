import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
from core.combat.gen_mob import get_modifier_description
from core.character.profile_hub import ProfileBuilder, ProfileHubView

class General(commands.Cog, name="general"):
    def __init__(self, bot) -> None:
        self.bot = bot
        
        # Context Menus
        self.context_menu_user = app_commands.ContextMenu(
            name="Grab ID", callback=self.grab_id
        )
        self.bot.tree.add_command(self.context_menu_user)
        self.context_menu_message = app_commands.ContextMenu(
            name="Remove spoilers", callback=self.remove_spoilers
        )
        self.bot.tree.add_command(self.context_menu_message)

    async def remove_spoilers(self, interaction: discord.Interaction, message: discord.Message) -> None:
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

    async def grab_id(self, interaction: discord.Interaction, user: discord.User) -> None:
        embed = discord.Embed(
            description=f"The ID of {user.mention} is `{user.id}`.",
            color=0xBEBEFE,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    #  HELPER: Weapon Tiers Generation
    # ------------------------------------------------------------------
    def _generate_weapon_details(self) -> str:
        # Dictionary of Family Name -> (List of Tiers, Lambda for value calculation)
        # Value calc usually takes (index + 1) as input
        weapon_families = {
            "Burning (Atk Boost)": (
                ["burning", "flaming", "scorching", "incinerating", "carbonising"],
                lambda i: f"Atk +{int(i*0.08*100)}%"
            ),
            "Poisonous (Miss Dmg)": (
                ["poisonous", "noxious", "venomous", "toxic", "lethal"],
                lambda i: f"Miss deals up to {int(i*0.08*100)}% Atk"
            ),
            "Polished (Def Shred)": (
                ["polished", "honed", "gleaming", "tempered", "flaring"],
                lambda i: f"Enemy Def -{int(i*0.08*100)}%"
            ),
            "Sparking (Min Dmg)": (
                ["sparking", "shocking", "discharging", "electrocuting", "vapourising"],
                lambda i: f"Min Dmg Floor raised to {int(i*0.08*100)}% of Max"
            ),
            "Sturdy (Def Boost)": (
                ["sturdy", "reinforced", "thickened", "impregnable", "impenetrable"],
                lambda i: f"Player Def +{int(i*0.08*100)}%"
            ),
            "Piercing (Crit Target)": (
                ["piercing", "keen", "incisive", "puncturing", "penetrating"],
                lambda i: f"Crit Threshold reduced by {i*5} (Easier Crits)"
            ),
            "Strengthened (Cull)": (
                ["strengthened", "forceful", "overwhelming", "devastating", "catastrophic"],
                lambda i: f"Instantly kill if HP < {int(i*0.08*100)}%"
            ),
            "Accurate (Hit Bonus)": (
                ["accurate", "precise", "sharpshooter", "deadeye", "bullseye"],
                lambda i: f"Flat Accuracy Roll +{i*4}"
            ),
            "Echo (Double Hit)": (
                ["echo", "echoo", "echooo", "echoooo", "echoes"],
                lambda i: f"Extra hit dealing {int(i*0.10*100)}% Dmg"
            )
        }

        output = ""
        for family, (tiers, calc) in weapon_families.items():
            output += f"__**{family}**__\n"
            for idx, name in enumerate(tiers):
                val = calc(idx + 1) # tiers are 1-based for math
                output += f"`T{idx+1}` **{name.capitalize()}**: {val}\n"
            output += "\n"
        return output

    # ------------------------------------------------------------------
    #  HELPER: Scaling Gear Generation
    # ------------------------------------------------------------------
    def _generate_scaling_details(self, passives: dict, max_lvl: int) -> str:
        """
        passives: Dict of "Passive Name" -> Lambda(level) returning string effect
        """
        output = ""
        for name, calc in passives.items():
            output += f"__**{name}**__\n"
            # Show Level 1, Middle, and Max to save space if needed, 
            # OR loop all if list is short. Listing all for clarity here.
            levels_to_show = range(1, max_lvl + 1)
            
            lines = []
            for lvl in levels_to_show:
                effect = calc(lvl)
                lines.append(f"`L{lvl}` {effect}")
            
            output += "\n".join(lines) + "\n\n"
        return output

    @app_commands.command(name="mod_details", description="Shows progression details for modifiers or passives.")
    @app_commands.describe(category="Choose the category of modifiers/passives to view.")
    async def mod_details(self, interaction: discord.Interaction,
                          category: Literal['monster', 'weapon', 'accessory', 'helmet', 'armor', 'glove', 'boot', 'uber', 'companion', 'slayer']):
        
        embed = discord.Embed(color=discord.Color.blue())
        content_added = False

        if category == 'monster':
            embed.title = "👹 Monster Modifier Details"
            # Sourced from general.py init list
            mods = [
                "Steel-born", "All-seeing", "Mirror Image", "Glutton", 
                "Enfeeble", "Venomous", "Strengthened", "Hellborn", "Lucifer-touched", 
                "Titanium", "Ascended", "Summoner", "Shield-breaker", "Impenetrable",
                "Unblockable", "Unavoidable", "Built-different", "Multistrike", "Mighty",
                "Shields-up", "Executioner", "Time Lord", "Suffocator", "Celestial Watcher",
                "Unlimited Blade Works", "Hell's Fury", "Absolute", "Infernal Legion",
                "Penetrator", "Clobberer", "Smothering", "Dodgy", "Prescient", "Vampiric"
            ]
            mod_text = ""
            for mod_name in sorted(mods):
                desc = get_modifier_description(mod_name) 
                mod_text += f"**{mod_name}**: {desc}\n"
            
            if len(mod_text) > 4000: # Safety split
                embed.description = mod_text[:4000] + "..."
            else:
                embed.description = mod_text
            content_added = True

        elif category == 'weapon':
            embed.title = "⚔️ Weapon Passive Progression"
            infernal_text = (
                "\n**🔥 Infernal Passives (Engram):**\n"
                "**Soulreap**: Restore HP to full after every successful encounter.\n"
                "**Inverted Edge**: At combat start, swap weapon Attack and Defence.\n"
                "**Gilded Hunger**: At combat start, gain Attack equal to 50% of weapon Rarity.\n"
                "**Cursed Precision**: Crit threshold reduced by 20, but crits always roll for the lower damage result.\n"
                "**Diabolic Pact**: At combat start, lose 50% HP and double your Attack for the fight.\n"
                "**Perdition**: Missed attacks still deal 75% weapon Attack.\n"
                "**Voracious**: Each non-crit hit adds a stack; each stack reduces crit threshold by 5. Stacks reset on crit.\n"
                "**Last Rites**: Critical hits deal an additional 10% of the enemy's current HP."
            )
            embed.description = self._generate_weapon_details() + infernal_text
            content_added = True

        elif category == 'accessory':
            embed.title = "📿 Accessory Passive Scaling (Max Lvl 10)"
            passives = {
                "Obliterate": lambda l: f"**{l * 2}%** chance to deal Double Damage",
                "Absorb": lambda l: f"**{l * 10}%** chance to steal 10% stats",
                "Prosper": lambda l: f"**{l * 10}%** chance to Double Gold",
                "Infinite Wisdom": lambda l: f"**{l * 5}%** chance to Double XP",
                "Lucky Strikes": lambda l: f"**{l * 10}%** chance for Lucky Hit Rolls"
            }
            void_text = (
                "\n**⬛ Void Passives (Engram):**\n"
                "**Entropy**: At combat start, 20% of weapon ATK is transferred to DEF and vice versa.\n"
                "**Void Echo**: At combat start, gain 15% of base Attack added to accessory Attack.\n"
                "**Unravelling**: At combat start, reduce monster Defence by 20%.\n"
                "**Void Gaze**: On crit, reduce monster Attack by 1% per stack (up to 30 stacks).\n"
                "**Fracture**: On crit, 5% chance to instantly kill (disabled vs Uber bosses).\n"
                "**Nullfield**: 15% chance to completely absorb incoming damage.\n"
                "**Eternal Hunger**: Each hit adds a stack; at 10 stacks deal 10% of monster max HP and restore full HP.\n"
                "**Oblivion**: Missed attacks still deal 50% of minimum attack damage."
            )
            embed.description = self._generate_scaling_details(passives, 10) + void_text
            content_added = True

        elif category == 'glove':
            embed.title = "🧤 Glove Passive Scaling (Max Lvl 5)"
            passives = {
                "Ward-Touched": lambda l: f"Gain **{l}%** of Hit Dmg as Ward",
                "Ward-Fused": lambda l: f"Gain **{l*2}%** of Crit Dmg as Ward",
                "Instability": lambda l: f"Hits are 50% dmg OR **{150 + (l*10)}%** dmg",
                "Deftness": lambda l: f"Crit Floor raised by **{l*5}%**",
                "Adroit": lambda l: f"Normal Hit Floor raised by **{l*2}%**",
                "Equilibrium": lambda l: f"Gain **{l*5}%** of Dmg as Bonus XP",
                "Plundering": lambda l: f"Gain **{l*10}%** of Dmg as Bonus Gold"
            }
            embed.description = self._generate_scaling_details(passives, 5)
            content_added = True

        elif category == 'boot':
            embed.title = "👢 Boot Passive Scaling (Max Lvl 6)"
            passives = {
                "Speedster": lambda l: f"Cooldown reduced by **{l}m**",
                "Skiller": lambda l: f"**{l*5}%** chance for extra skill mats",
                "Treasure-Tracker": lambda l: f"Treasure Mob chance +**{l*0.5}%**",
                "Hearty": lambda l: f"Max HP +**{l*5}%**",
                "Cleric": lambda l: f"Potions heal +**{l*10}%** extra",
                "Thrill-Seeker": lambda l: f"Special Drop Chance +**{l*1}%**"
            }
            embed.description = self._generate_scaling_details(passives, 6)
            content_added = True

        elif category == 'armor':
            embed.title = "🛡️ Armor Passives"
            armor_text = (
                "**Standard Passives:**\n"
                "**Invulnerable**: 20% chance to take 0 damage for the whole fight.\n"
                "**Mystical Might**: 20% chance to deal 10x damage (Combat Start).\n"
                "**Omnipotent**: 50% chance to Double Atk, Def, and gain Max HP as Ward (Combat Start).\n"
                "**Treasure Hunter**: +5% chance to encounter Treasure Mobs.\n"
                "**Unlimited Wealth**: 20% chance to multiply Player Rarity by 5x (2x vs Bosses).\n"
                "**Everlasting Blessing**: 10% chance on victory to trigger Ideology Propagation.\n\n"
                "**🌌 Celestial Passives (Engram):**\n"
                "**Celestial Ghostreaver**: Generate 50-150 Ward every turn.\n"
                "**Celestial Glancing Blows**: Doubles Block Chance, Blocked hits deal 50% damage.\n"
                "**Celestial Wind Dancer**: Triples Evasion Chance, but entirely disables your Helmet.\n"
                "**Celestial Sanctity**: Enemies roll their final damage twice and apply the lower result.\n"
                "**Celestial Vow**: Once per combat, survive a fatal blow at 1 HP and gain 50% Max HP as Ward.\n"
                "**Celestial Fortress**: Gain +1% Percent Damage Reduction for every 5% missing HP."
            )
            embed.description = armor_text
            content_added = True

        elif category == 'helmet':
                    embed.title = "🪖 Helmet Passive Scaling (Max Lvl 5)"
                    passives = {
                        "Juggernaut": lambda l: f"Gain **{l * 4}%** of Base Def as Atk",
                        "Insight": lambda l: f"Crit Dmg Multiplier +**{l * 0.1:.1f}x** (Base 2.0x)",
                        "Volatile": lambda l: f"Deal **{l * 100}%** of Max HP as Dmg on ward break",
                        "Divine": lambda l: f"Converts **{(l * 100)}%** of Potion Overheal to Ward",
                        "Frenzy": lambda l: f"**{l * 0.5}%** Inc Dmg per 1% Missing HP",
                        "Leeching": lambda l: f"Heal for **{l * 2}%** of base damage dealt",
                        "Thorns": lambda l: f"Reflect **{l * 100}%** of blocked damage",
                        "Ghosted": lambda l: f"Gain **{l * 10}** Ward on Dodge"
                    }
                    embed.description = self._generate_scaling_details(passives, 5)
                    content_added = True

        elif category == 'companion':
            embed.title = "🐾 Companion Passive Scaling (Tiers 1–5)"
            comp_passives = {
                "ATK (+% Attack)":        lambda t: f"+**{4 + t}%** Attack",
                "DEF (+% Defence)":       lambda t: f"+**{4 + t}%** Defence",
                "HIT (Flat Hit Chance)":  lambda t: f"+**{t}** Hit Chance",
                "CRIT (Flat Crit Chance)":lambda t: f"+**{t}** Crit Chance",
                "WARD (+% HP as Ward)":   lambda t: f"+**{t * 5}%** HP as Ward",
                "RARITY (+% Rarity)":     lambda t: f"+**{t * 3}%** Rarity",
                "S_RARITY (+% Special Drop Rate)": lambda t: f"+**{t}%** Special Drop Rate",
                "FDR (Flat Dmg Reduction)": lambda t: f"+**{1 + t}** Flat Damage Reduction",
                "PDR (% Dmg Reduction)":  lambda t: f"+**{2 + t}%** Percent Damage Reduction",
            }
            comp_text = self._generate_scaling_details(comp_passives, 5)
            comp_text += (
                "\n**Balanced Passive:** A companion's secondary passive, unlocked via Awakening. "
                "Uses the same types and tier scaling as the primary passive."
            )
            embed.description = comp_text
            content_added = True

        elif category == 'slayer':
            embed.title = "🗡️ Slayer Emblem Passive Scaling (Tiers 1–5)"
            slayer_passives = {
                "Slayer Target Damage": lambda t: f"+**{t * 5}%** damage vs assigned slayer species",
                "Boss Damage":          lambda t: f"+**{t * 5}%** damage vs bosses",
                "Normal Monster Damage":lambda t: f"+**{t * 2}%** damage vs normal monsters",
                "Slayer Target Defence":lambda t: f"+**{t * 2}%** defence vs assigned slayer species",
                "Crit Damage":          lambda t: f"+**{t * 5}%** critical hit damage multiplier",
                "Accuracy":             lambda t: f"+**{t * 2}** flat accuracy roll",
                "Gold Find":            lambda t: f"+**{t * 3}%** gold from combat",
                "XP Find":              lambda t: f"+**{t * 3}%** XP from combat",
                "Double Task Progress": lambda t: f"**{t * 5}%** chance for a task kill to count twice",
                "Slayer Drop Rate":     lambda t: f"**{t * 5}%** chance for extra slayer material drops",
            }
            embed.description = self._generate_scaling_details(slayer_passives, 5)
            content_added = True

        elif category == 'uber':
            embed.title = "⚔️ Uber Boss Modifier Details"
            uber_text = (
                "**Aphrodite, Celestial Apex**\n"
                "**Radiant Protection**: Globally reduces all incoming damage by 60%.\n\n"
                "**Lucifer, Infernal Sovereign**\n"
                "**Hell's Fury**: +5 flat attack for every successful hit.\n\n"
                "**NEET, Void Sovereign**\n"
                "**Void Aura**: Siphons 5% of player ATK and DEF each round, regardless of hit.\n\n"
                "**Castor & Pollux, Bound Sovereigns**\n"
                "**Twin Strike**: Every even round, a second coordinated blow lands at 50% damage.\n\n"
                "**Shared (All Uber Bosses)**\n"
                "**Absolute**: +25 Attack, +25 Defence.\n\n"
                "**Random Boss Modifier (one per encounter)**\n"
                "**Celestial Watcher**: 100% hit chance; deals 20% increased damage.\n"
                "**Unlimited Blade Works**: Doubles all damage dealt.\n"
                "**Infernal Legion**: Minions echo every hit for full additional damage.\n"
            )
            embed.description = uber_text
            content_added = True

        if not content_added:
            embed.description = "No details available."

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="List Idleology's commands by category.")
    async def help(self, interaction: discord.Interaction) -> None:
        """
        Displays a categorized help menu.
        """
        prefix = "/"
        
        # Define Categories and their Commands manually for better UX
        categories = {
            "👤 Character": [
                ("register", "Create your adventurer profile"),
                ("card", "View your profile card"),
                ("stats", "Detailed character statistics"),
                ("inventory", "View your bag summary"),
                ("skills", "View mining/fishing/woodcutting levels"),
                ("passives", "Allocate passive points"),
                ("cooldowns", "Check command timers"),
                ("unregister", "Delete your character (Permanent!)")
            ],
            "🐾 Companions": [
                ("companions list", "Manage active pets & reroll stats"),
                ("companions collect", "Collect passive loot")
            ],
            "⚔️ Combat": [
                ("combat", "Fight monsters for XP and loot"),
                ("ascent", "Wave-based survival mode (Lvl 100+)"),
                ("duel", "PvP against another player"),
                ("dungeon", "Enter a dungeon (Coming Soon)")
            ],
            "🎒 Equipment": [
                ("weapons", "Manage weapons (Forge/Refine)"),
                ("armor", "Manage armor (Temper/Imbue)"),
                ("accessory", "Manage accessories (Potential)"),
                ("gloves", "Manage gloves"),
                ("boots", "Manage boots"),
                ("helmet", "Manage helmets"),
                ("mod_details", "View gear passive info")
            ],
            "🌲 Gathering": [
                ("mining", "Check ores and upgrade pickaxe"),
                ("fishing", "Check fish and upgrade rod"),
                ("woodcutting", "Check logs and upgrade axe")
            ],
            "🏙️ Social & Economy": [
                ("shop", "Buy potions and curios"),
                ("settlement", "Manage your settlement"),
                ("resources", "Check your settlement resources"),
                ("checkin", "Daily reward"),
                ("rest", "Heal up at the tavern"),
                ("gamble", "Play casino games"),
                ("ideology", "View server ideologies"),
                ("propagate", "Spread your ideology"),
                ("leaderboard", "View top players"),
                ("curios", "Open a curio box"),
                ("bulk_curios", "Open multiple curios")
            ],
            "📦 Trading": [
                ("send", "Send Gold to a player"),
                ("send_material", "Send Ores/Logs/Fish"),
                ("send_key", "Send Boss Keys"),
                ("ids", "Get IDs for item trading")
            ],
            "🎉 Fun": [
                ("poe", "Path of Exile Trivia Game")
            ]
        }

        embed = discord.Embed(
            title="Idleology Help Menu",
            description="Welcome to **Idleology**! 💡\nUse `/register` to start your journey.",
            color=0xBEBEFE
        )
        embed.set_thumbnail(url="https://i.imgur.com/81jN8tA.jpeg") # Tavern Keeper or Logo

        for category, cmds in categories.items():
            command_list = []
            for name, desc in cmds:
                command_list.append(f"`{prefix}{name}` - {desc}")
            
            embed.add_field(name=category, value="\n".join(command_list), inline=False)

        embed.set_footer(text="Use /mod_details to learn about gear passives!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="getstarted", description="Get information and tips for playing Idleology.")
    async def info(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Welcome to Idleology!",
            description="Here's a quick guide to help you get started.",
            color=0x00FF00
        )
        embed.add_field(
            name="How to Play",
            value=(
                "**1. Register:** `/register <name>`\n"
                "**2. Fight:** `/combat` (Every 10m)\n"
                "**3. Gear Up:** Check `/weapons`, `/armor`, etc.\n"
                "**4. Skills:** `/mining`, `/woodcutting`, `/fishing`\n"
                "**5. Shop:** `/shop` for potions."
            ),
            inline=False
        )
        embed.set_footer(text="It's all in the mind.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="cooldowns", description="Check your current cooldowns.")
    async def cooldowns(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user): return

        view = ProfileHubView(self.bot, user_id, server_id, "cooldowns")
        embed = await ProfileBuilder.build_cooldowns(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="ids", description="Fetch your user ID and all item IDs.")
    async def ids(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        
        weapons = await self.bot.database.equipment.get_all(user_id, 'weapon')
        accs = await self.bot.database.equipment.get_all(user_id, 'accessory')
        
        embed = discord.Embed(title="IDs for Trading", color=0xBEBEFE)
        embed.add_field(name="User ID", value=user_id, inline=False)
        
        w_text = "\n".join([f"**ID {w[0]}**: {w[2]}" for w in weapons]) or "None"
        a_text = "\n".join([f"**ID {a[0]}**: {a[2]}" for a in accs]) or "None"
        
        if len(w_text) > 1000: w_text = w_text[:950] + "..."
        if len(a_text) > 1000: a_text = a_text[:950] + "..."

        embed.add_field(name="Weapons", value=w_text, inline=False)
        embed.add_field(name="Accessories", value=a_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot) -> None:
    await bot.add_cog(General(bot))