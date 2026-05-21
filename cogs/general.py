from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from core.character.profile_hub import ProfileHubView
from core.character.profile_ui import ProfileBuilder
from core.combat.calc.calcs import (
    ACCESSORY_PASSIVE_DESCS,
    BOOT_PASSIVE_DESCS,
    GLOVE_PASSIVE_DESCS,
    HELMET_PASSIVE_DESCS,
    WEAPON_PASSIVE_DEFS,
)
from core.combat.gen.modifier_data import (
    BOSS_MOD_NAMES,
    COMMON_MOD_NAMES,
    RARE_FLAT_MOD_NAMES,
    RARE_TIERED_MOD_NAMES,
    make_modifier,
)
from core.images import TAVERN_KEEPER
from core.slayer.mechanics import SLAYER_PASSIVE_DEFS, SLAYER_PASSIVE_NAMES


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

    async def remove_spoilers(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
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

    async def grab_id(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        embed = discord.Embed(
            description=f"The ID of {user.mention} is `{user.id}`.",
            color=0xBEBEFE,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    #  HELPER: Weapon Tiers Generation
    # ------------------------------------------------------------------
    def _generate_weapon_details(self) -> str:
        output = ""
        for defn in WEAPON_PASSIVE_DEFS.values():
            output += f"__**{defn.display_name}**__\n"
            for idx, label in enumerate(defn.tier_labels):
                val = defn.description(idx + 1)
                output += f"`T{idx+1}` **{label}**: {val}\n"
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

    @app_commands.command(
        name="mod_details",
        description="Shows progression details for modifiers or passives.",
    )
    @app_commands.describe(
        category="Choose the category of modifiers/passives to view."
    )
    async def mod_details(
        self,
        interaction: discord.Interaction,
        category: Literal[
            "monster",
            "weapon",
            "accessory",
            "helmet",
            "armor",
            "glove",
            "boot",
            "uber",
            "companion",
            "slayer",
            "codex",
            "essence",
        ],
    ):

        embed = discord.Embed(color=discord.Color.blue())
        content_added = False

        if category == "monster":
            embed.title = "👹 Monster Modifier Details"
            embed.description = (
                "Higher monster levels unlock higher tiers. "
                "Boss modifiers only appear on bosses and ascent monsters.\n​"
            )

            from core.combat.gen.gen_mob import get_modifier_description

            def _tier_range(name: str) -> str:
                """Return a T1→T5 value string for display."""
                t1 = make_modifier(name, 1)  # force T1 by using level 1
                t5 = make_modifier(name, 200)  # force T5 by using level 200
                d1 = get_modifier_description(t1)
                d5 = get_modifier_description(t5)
                if d1 == d5:
                    return d1
                return f"{d1} → {d5}"

            def _flat_desc(name: str) -> str:
                return get_modifier_description(make_modifier(name, 50))

            # Common pool — split into two fields to stay under 1024 chars
            common_sorted = sorted(COMMON_MOD_NAMES)
            mid = len(common_sorted) // 2
            common_a = [f"**{n}**: {_tier_range(n)}" for n in common_sorted[:mid]]
            common_b = [f"**{n}**: {_tier_range(n)}" for n in common_sorted[mid:]]
            # Ascended special appended to second half
            asc_t1 = make_modifier("Ascended", 10)
            asc_t5 = make_modifier("Ascended", 200)
            common_b.append(
                f"**Ascended**: {get_modifier_description(asc_t1)} → {get_modifier_description(asc_t5)} *(scales with level)*"
            )
            embed.add_field(
                name="🔵 Common *(I–V)* — A to K",
                value="\n".join(common_a),
                inline=False,
            )
            embed.add_field(
                name="🔵 Common *(I–V)* — L to Z",
                value="\n".join(common_b),
                inline=False,
            )

            # Rare tiered pool
            rare_tiered_lines = []
            for name in sorted(RARE_TIERED_MOD_NAMES):
                rare_tiered_lines.append(f"**{name}**: {_tier_range(name)}")
            # Rare flat pool
            rare_flat_lines = []
            for name in sorted(RARE_FLAT_MOD_NAMES):
                rare_flat_lines.append(f"**{name}**: {_flat_desc(name)}")
            embed.add_field(
                name="🟣 Rare Tiered *(I–V)*",
                value="\n".join(rare_tiered_lines),
                inline=False,
            )
            embed.add_field(
                name="🟣 Rare Flat",
                value="\n".join(rare_flat_lines),
                inline=False,
            )

            # Boss pool
            boss_lines = []
            for name in sorted(BOSS_MOD_NAMES):
                boss_lines.append(f"**{name}**: {_flat_desc(name)}")
            embed.add_field(
                name="🔴 Boss Only",
                value="\n".join(boss_lines),
                inline=False,
            )
            content_added = True

        elif category == "weapon":
            embed.title = "⚔️ Weapon Passives"
            infernal_text = (
                "\n**🔥 Infernal Passives (Engram):**\n"
                "**Soulreap**: Restore HP to full after every successful encounter.\n"
                "**Inverted Edge**: At combat start, swap weapon Attack and Defence.\n"
                "**Gilded Hunger**: Gain Attack equal to 10% of weapon rarity.\n"
                "**Cursed Precision**: +20% Crit Chance. Your critical damage is unlucky.\n"
                "**Diabolic Pact**: At combat start, lose 90% maximum HP and double your Attack.\n"
                "**Perdition**: On miss, deal 75% of your weapon Attack.\n"
                "**Voracious**: On hit, gain a voracity stack. Each stack increases crit chance by 5 and resets voracity on crit.\n"
                "**Last Rites**: Critical hits deal an additional 5% of the enemy's current HP."
            )
            embed.description = self._generate_weapon_details() + infernal_text
            content_added = True

        elif category == "accessory":
            embed.title = "📿 Accessory Passive Scaling (Max Lvl 10)"
            passives = {k.title(): v for k, v in ACCESSORY_PASSIVE_DESCS.items()}
            void_text = (
                "\n**⬛ Void Passives (Engram):**\n"
                "**Entropy**: At combat start, 20% of weapon ATK is added to DEF and vice versa.\n"
                "**Void Echo**: At combat start, 15% of weapon ATK is added to your accessory.\n"
                "**Unravelling**: At combat start, reduce monster Defence by 20%.\n"
                "**Void Gaze**: On crit, reduce monster ATK by 3% per stack (up to 30 stacks).\n"
                "**Fracture**: On crit, 5% chance to instantly kill (does not work on Uber bosses).\n"
                "**Nullfield**: 15% chance to completely absorb incoming damage.\n"
                "**Eternal Hunger**: On hit, gain a hunger stack. At 10 stacks, deal 10% of monster max HP and heal to max HP.\n"
                "**Oblivion**: On miss, deal 50% of your total ATK as damage."
            )
            embed.description = self._generate_scaling_details(passives, 10) + void_text
            content_added = True

        elif category == "glove":
            embed.title = "🧤 Glove Passive Scaling (Max Lvl 5)"
            passives = {k.title(): v for k, v in GLOVE_PASSIVE_DESCS.items()}
            embed.description = self._generate_scaling_details(passives, 5)
            content_added = True

        elif category == "boot":
            embed.title = "👢 Boot Passive Scaling (Max Lvl 6)"
            passives = {k.title(): v for k, v in BOOT_PASSIVE_DESCS.items()}
            embed.description = self._generate_scaling_details(passives, 6)
            content_added = True

        elif category == "armor":
            embed.title = "🛡️ Armor Passives"
            armor_text = (
                "**Standard Passives:**\n"
                "**Impregnable**: Raises your PDR cap from 80% to 90% during combat.\n"
                "**Piety**: Attacks have a 10% chance to deal 7× damage.\n"
                "**Transcendence**: On Combat Start, gain 20% of your total ATK and DEF as bonus ATK.\n"
                "**Treasure Hunter**: +3% Special Drop Chance.\n"
                "**Unlimited Wealth**: 20% chance to multiply Player Rarity by 5x (2x vs Bosses).\n"
                "**Alchemist**: 30% chance to not consume a potion when using one in combat.\n\n"
                "**🌌 Celestial Passives (Engram):**\n"
                "**Celestial Ghostreaver**: Generate 50-200 Ward every turn.\n"
                "**Celestial Glancing Blows**: Doubles Block Chance, Blocked hits deal 50% damage.\n"
                "**Celestial Wind Dancer**: Triples Evasion Chance, but entirely disables your Helmet.\n"
                "**Celestial Sanctity**: Enemies roll their final damage twice and apply the lower result.\n"
                "**Celestial Vow**: Once per combat, survive a fatal blow at 1 HP and gain 50% Max HP as Ward.\n"
                "**Celestial Fortress**: Gain +1% Percent Damage Reduction for every 5% missing HP."
            )
            embed.description = armor_text
            content_added = True

        elif category == "helmet":
            embed.title = "🪖 Helmet Passive Scaling (Max Lvl 5)"
            passives = {k.title(): v for k, v in HELMET_PASSIVE_DESCS.items()}
            embed.description = self._generate_scaling_details(passives, 5)
            content_added = True

        elif category == "companion":
            embed.title = "🐾 Companion Passive Scaling (Tiers 1–5)"
            comp_passives = {
                "ATK (+% Attack)": lambda t: f"+{4 + t}% Attack",
                "DEF (+% Defence)": lambda t: f"+{4 + t}% Defence",
                "HIT (Flat Hit Chance)": lambda t: f"+{t} Hit Chance",
                "CRIT (Flat Crit Chance)": lambda t: f"+{t} Crit Chance",
                "WARD (+% HP as Ward)": lambda t: f"+{t * 5}% HP as Ward",
                "RARITY (+% Rarity)": lambda t: f"+{t * 3}% Rarity",
                "S_RARITY (+% Special Drop Rate)": lambda t: f"+{t}% Special Drop Rate",
                "FDR (Flat Dmg Reduction)": lambda t: f"+{5 + t * 2} Flat Damage Reduction",
                "PDR (% Dmg Reduction)": lambda t: f"+{2 + t}% Percent Damage Reduction (bypasses cap)",
            }
            comp_text = self._generate_scaling_details(comp_passives, 5)
            comp_text += (
                "\n**Balanced Passive:** A companion's secondary passive, unlocked via Awakening. "
                "Uses the same types and tier scaling as the primary passive."
            )
            embed.description = comp_text
            content_added = True

        elif category == "slayer":
            embed.title = "🗡️ Slayer Emblem Passive Scaling (Tiers 1–5)"
            slayer_passives = {
                SLAYER_PASSIVE_NAMES[k]: v
                for k, v in SLAYER_PASSIVE_DEFS.items()
                if k in SLAYER_PASSIVE_NAMES
            }
            embed.description = self._generate_scaling_details(slayer_passives, 5)
            content_added = True

        elif category == "uber":
            embed.title = "⚔️ Uber Boss Modifier Details"
            uber_text = (
                "Each Uber boss carries **fixed signature modifiers** plus one random boss modifier.\n\n"
                "**Aphrodite, Celestial Apex**\n"
                "**Radiant Protection**: Reduces all incoming damage by 60%.\n\n"
                "**Lucifer, Infernal Sovereign**\n"
                "**Infernal Protection**: Reduces all incoming damage by 60%.\n"
                "**Hell's Fury**: Deals triple damage on every hit.\n\n"
                "**NEET, the Void Sovereign**\n"
                "**Void Protection**: Reduces all incoming damage by 60%.\n"
                "**Void Aura**: Siphons 1.5% of your ATK and DEF each round, regardless of hit.\n\n"
                "**Castor & Pollux, Bound Sovereigns**\n"
                "**Balanced Protection**: Reduces all incoming damage by 60%.\n"
                "**Balanced Strikes**: Every even round, a second coordinated blow lands at 50% damage — bypasses ward and cannot be blocked or evaded.\n\n"
                "**Random Boss Modifier (one per encounter)**\n"
                "**Overwhelming**: Always deals double damage; −25 to hit rolls.\n"
                "**Inevitable**: Always hits; deals 50% damage.\n"
                "**Sundering**: 25% of each hit bypasses your ward directly to HP.\n"
                "**Unerring**: Accuracy is lucky.\n"
            )
            embed.description = uber_text
            content_added = True

        elif category == "codex":
            embed.title = "📖 Codex Tome Passives"
            embed.description = (
                "**Vitality** — +% Max HP\n"
                "Stacks additively with Gluttony (armor) and Hearty (boot). Applies in all game modes.\n\n"
                "**Wrath** — +% of base DEF as bonus ATK\n"
                "Calculated from base + equipment DEF. Stacks with all other ATK sources.\n\n"
                "**Bastion** — +% of base ATK as bonus DEF\n"
                "Calculated from base + equipment ATK. Stacks with all other DEF sources.\n\n"
                "**Tenacity** — Chance per incoming hit to halve the damage\n"
                "Applies at the final damage value, before ward. Does not trigger on dodged attacks.\n\n"
                "**Bloodthirst** — Heal % of critical hit damage dealt\n"
                "Triggers after all damage bonuses. Stacks with Leeching.\n\n"
                "**Providence** — +% more to total rarity\n"
                "Sums additively with companion % more rarity, applied together to gear rarity.\n\n"
                "**Insight** — Flat crit chance increase\n"
                "Stacks with all other flat crit sources.\n\n"
                "**Affluence** — +% XP and Gold from all combat\n"
                "Additive with XP/Gold find emblems. Applies in Codex.\n\n"
                "**Bulwark** — +% Percent Damage Reduction\n"
                "Adds to the PDR pool. Subject to the 80% PDR cap.\n\n"
                "**Resilience** — +Flat Damage Reduction\n"
                "Additive with all other FDR sources."
            )
            content_added = True

        elif category == "essence":
            embed.title = "💎 Essence Details"
            embed.description = (
                "Essences are applied to **Gloves**, **Boots**, and **Helmets**. "
                "Each item has **3 regular slots** and **1 corrupted slot**.\n"
                "Regular slots can be cleansed, rerolled, or annulled. "
                "Corrupted slots are **permanent** once applied.\n\n"
                "**— Regular Essences —**\n\n"
                "**🔆 Essence of Power**\n"
                "Boosts the item's primary offensive stat. "
                "Rolls **20–100%** of the item's base ATK (Glove/Boot) or base DEF+WARD% (Helmet) as a flat bonus.\n\n"
                "**🛡️ Essence of Protection**\n"
                "Amplifies existing damage reduction on the item. "
                "Rolls **20–80%** of the item's base PDR and FDR values as a flat bonus to each.\n\n"
                "**👁️ Essence of Insight**\n"
                "Grants a flat crit chance increase. "
                "Rolls **+1–10%** Crit Chance.\n\n"
                "**💨 Essence of Evasion**\n"
                "Grants a flat evasion chance bonus. "
                "Rolls **+1–8%** Evasion.\n\n"
                "**🧱 Essence of Unyielding**\n"
                "Grants a flat block chance bonus. "
                "Rolls **+1–8%** Block Chance.\n\n"
                "**— Utility Essences (consumed on use) —**\n\n"
                "**🌊 Essence of Cleansing**\n"
                "Removes all 3 regular essence slots from the item, resetting them to empty.\n\n"
                "**🌀 Essence of Chaos**\n"
                "Rerolls the stat values on all occupied regular essence slots. Types are preserved.\n\n"
                "**✂️ Essence of Annulment**\n"
                "Removes one random occupied regular essence slot.\n\n"
                "**— Corrupted Essences (permanent) —**\n\n"
                "**💠 Essence of Aphrodite's Disciple**\n"
                "**Glove:** All ward-affecting hits count as ward-breaking.\n"
                "**Boot:** Your equipment drop chance is lucky.\n"
                "**Helmet:** Your ward cannot be forcibly disabled.\n\n"
                "**💠 Essence of Lucifer's Heir**\n"
                "**Glove:** Each attack deals bonus flat damage equal to 15% of your current ward pool (only while ward > 0).\n"
                "**Boot:** Gold drops are increased by 10% per modifier on the monster, up to a maximum of +50%.\n"
                "**Helmet:** When your ward is fully broken, gain 15% PDR for the remainder of that combat.\n\n"
                "**💠 Essence of Gemini's Lost Twin**\n"
                "**Glove:** Critical hits strike twice — the second strike deals 40–60% of the first hit's damage.\n"
                "**Boot:** Pet drop chance is doubled (5% → 10% from normal enemies; 3% → 6% from bosses).\n"
                "**Helmet:** Incoming damage splits evenly between ward and HP simultaneously. Your damage taken is halved.\n\n"
                "**💠 Essence of NEET's Voidling**\n"
                "**Glove:** Your normal hits are now misses — only critical hits deal direct damage. Miss-triggered effects (Perdition, Oblivion, Poison) still apply.\n"
                "**Boot:** Whenever you receive skilling resources during combat, gain it again.\n"
                "**Helmet:** When you gain ward, gain twice the amount instead."
            )
            content_added = True

        if not content_added:
            embed.description = "No details available."

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="help", description="List Idleology's commands by category."
    )
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
                ("unregister", "Delete your character (Permanent!)"),
            ],
            "🐾 Companions": [
                ("companions", "Manage your companion roster"),
                ("partner", "Recruit and manage partners"),
            ],
            "⚔️ Combat": [
                ("combat", "Fight monsters for XP and loot"),
                ("ascent", "Tower of Ascension (Lvl 100+)"),
                ("codex", "Tome of Power (Lvl 100+)"),
                ("duel", "PvP against another player"),
                ("uber", "Challenge the pinnacle of power"),
                ("maw", "Challenge the Maw of Infinity"),
            ],
            "🎒 Equipment": [
                ("weapons", "Manage weapons"),
                ("armor", "Manage armor"),
                ("accessory", "Manage accessories"),
                ("gloves", "Manage gloves"),
                ("boots", "Manage boots"),
                ("helmet", "Manage helmets"),
                ("gear", "Manage gear"),
            ],
            "🌲 Skills": [
                ("mining", "Check ores and upgrade pickaxe"),
                ("delve", "Mining mini-game"),
                ("fishing", "Check fish and upgrade rod"),
                ("fish", "Fishing mini-game"),
                ("woodcutting", "Check logs and upgrade axe"),
                ("chop", "Woodcutting mini-game"),
                ("slayer", "Manage your slayer task and emblem"),
                ("alchemy", "Manage your alchemy skill"),
            ],
            "🏙️ Social & Economy": [
                ("shop", "Buy potions"),
                ("settlement", "Manage your settlement"),
                ("resources", "Check your settlement resources"),
                ("checkin", "Daily reward"),
                ("rest", "Heal up at the tavern"),
                ("ideology", "View server ideologies"),
                ("propagate", "Spread your ideology"),
                ("leaderboard", "View top players"),
                ("curios", "Open a curio or puzzle box"),
            ],
            "📦 Trading": [
                ("trade", "Send Items/Gold to another player"),
            ],
            "🎉 Fun": [
                ("poe", "Path of Exile Trivia Game"),
                ("gamble", "Play casino games and win gold"),
            ],
        }

        embed = discord.Embed(
            title="Idleology Help Menu",
            description="Welcome to **Idleology**! 💡\nUse `/register` to start your journey.",
            color=0xBEBEFE,
        )
        embed.set_thumbnail(url=TAVERN_KEEPER)

        for category, cmds in categories.items():
            command_list = []
            for name, desc in cmds:
                command_list.append(f"`{prefix}{name}` - {desc}")

            embed.add_field(name=category, value="\n".join(command_list), inline=False)

        embed.set_footer(text="Use /mod_details to learn about gear passives!")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="getstarted", description="Get information and tips for playing Idleology."
    )
    async def info(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Welcome to Idleology!",
            description="Here's a quick guide to help you get started.",
            color=0x00FF00,
        )
        embed.add_field(
            name="How to Play",
            value=(
                "**1. Register:** `/register <name>`\n"
                "**2. Fight:** `/combat` (Every 10m)\n"
                "**3. Gear Up:** Check `/weapons`, `/armor`, etc.\n"
                "**4. Skills:** `/gather`, `/alchemy`, `/slayer`\n"
                "**5. Help menu:** `/help` for a full list of commands."
            ),
            inline=False,
        )
        embed.set_footer(text="It's all in the mind.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="cooldowns", description="Check your current cooldowns.")
    async def cooldowns(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        view = ProfileHubView(self.bot, user_id, server_id, "cooldowns")
        embed = await ProfileBuilder.build_cooldowns(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="ids", description="Fetch your user ID and all item IDs."
    )
    async def ids(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)

        weapons = await self.bot.database.equipment.get_all(user_id, "weapon")
        accs = await self.bot.database.equipment.get_all(user_id, "accessory")

        embed = discord.Embed(title="IDs for Trading", color=0xBEBEFE)
        embed.add_field(name="User ID", value=user_id, inline=False)

        w_text = "\n".join([f"**ID {w['item_id']}**: {w['item_name']}" for w in weapons]) or "None"
        a_text = "\n".join([f"**ID {a['item_id']}**: {a['item_name']}" for a in accs]) or "None"

        if len(w_text) > 1000:
            w_text = w_text[:950] + "..."
        if len(a_text) > 1000:
            a_text = a_text[:950] + "..."

        embed.add_field(name="Weapons", value=w_text, inline=False)
        embed.add_field(name="Accessories", value=a_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(General(bot))
