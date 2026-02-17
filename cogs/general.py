import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
from core.combat.gen_mob import get_modifier_description

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
                          category: Literal['monster', 'weapon', 'accessory', 'helmet', 'armor', 'glove', 'boot']):
        
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
            embed.description = self._generate_weapon_details()
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
            embed.description = self._generate_scaling_details(passives, 10)
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
            embed.title = "🛡️ Armor Passives (Unique Effects)"
            armor_text = (
                "**Invulnerable**: 20% chance to take 0 damage for the whole fight.\n\n"
                "**Mystical Might**: 20% chance to deal 10x damage (Combat Start).\n\n"
                "**Omnipotent**: 50% chance to Double Atk, Def, and gain Max HP as Ward (Combat Start).\n\n"
                "**Treasure Hunter**: +5% chance to encounter Treasure Mobs.\n\n"
                "**Unlimited Wealth**: 20% chance to multiply Player Rarity by 5x (2x vs Bosses).\n\n"
                "**Everlasting Blessing**: 10% chance on victory to trigger Ideology Propagation."
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
                ("mod_details", "View gear passive info")
            ],
            "🌲 Gathering": [
                ("mining", "Check ores and upgrade pickaxe"),
                ("fishing", "Check fish and upgrade rod"),
                ("woodcutting", "Check logs and upgrade axe")
            ],
            "🏙️ Social & Economy": [
                ("shop", "Buy potions and curios"),
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
        if not user:
            await interaction.response.send_message("Please /register first.", ephemeral=True)
            return

        # Schema indices: 13=Rest, 17=Checkin, 14=Propagate, 24=Combat
        from datetime import datetime, timedelta
        
        def get_remaining(time_str, cooldown_hours=0, cooldown_mins=0):
            if not time_str: return "Ready!"
            try:
                last = datetime.fromisoformat(time_str)
                diff = datetime.now() - last
                cd = timedelta(hours=cooldown_hours, minutes=cooldown_mins)
                if diff < cd:
                    rem = cd - diff
                    return f"**{rem.seconds // 3600}h {(rem.seconds // 60) % 60}m {rem.seconds % 60}s**"
                return "Ready!"
            except: return "Error"

        # Checkin (18h), Rest (2h), Propagate (18h), Combat (10m)
        embed = discord.Embed(title="Timers", color=0x00FF00)
        embed.add_field(name="/combat ⚔️", value=get_remaining(user[24], cooldown_mins=10))
        embed.add_field(name="/rest 🛏️", value=get_remaining(user[13], cooldown_hours=2))
        embed.add_field(name="/checkin 🛖", value=get_remaining(user[17], cooldown_hours=18))
        embed.add_field(name="/propagate 💡", value=get_remaining(user[14], cooldown_hours=18))
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

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