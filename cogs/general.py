import re
from typing import Literal

import discord
from discord import ButtonStyle, Interaction, app_commands, ui
from discord.ext import commands

from core.base_view import BaseView
from core.character.profile_hub import ProfileHubView
from core.character.profile_ui import ProfileBuilder
from core.combat.calc.calcs import (
    WEAPON_PASSIVE_DEFS,
)
from core.combat.mobgen.modifier_data import (
    BOSS_MOD_NAMES,
    COMMON_MOD_NAMES,
    RARE_TIERED_MOD_NAMES,
    make_modifier,
)
from core.character.passive_data import (
    _ACCESSORY_PASSIVE_FUNCS,
    _ARMOR_PASSIVE_DESC,
    _BOOT_PASSIVE_FUNCS,
    _CELESTIAL_PASSIVE_DESC,
    _CORRUPTED_DESC,
    _GLOVE_PASSIVE_FUNCS,
    _HELMET_PASSIVE_FUNCS,
    _INFERNAL_PASSIVE_DESC,
    _VOID_PASSIVE_DESC,
    _WEAPON_PASSIVE_DESC,
)
from core.images import AMARA_AUTHOR, AMARA_PORTRAIT
from core.slayer.mechanics import SLAYER_PASSIVE_DEFS, SLAYER_PASSIVE_NAMES


# ---------------------------------------------------------------------------
# Monster modifier detail view — paginates Common vs Rare & Boss
# ---------------------------------------------------------------------------


class ModDetailsMonsterView(BaseView):
    """
    Direct category selection view.
    Every section is directly accessible via its own button — no Previous/Next needed.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        common_part1: list,
        common_part2: list,
        rare_tiered_lines: list,
        boss_lines: list,
    ):
        super().__init__(bot, user_id)
        self.categories = {
            "common1": ("🔵 Common Tiered — Part 1", common_part1),
            "common2": ("🔵 Common Tiered — Part 2", common_part2),
            "rare_tiered": ("🟣 Rare Tiered", rare_tiered_lines),
            "boss_uber": ("🔴 Boss & Uber", boss_lines),
        }
        self.current_category = "common1"
        self._rebuild_buttons()

    def _rebuild_buttons(self):
        self.clear_items()

        # All category buttons are always shown and directly clickable
        button_labels = {
            "common1": "Common 1",
            "common2": "Common 2",
            "rare_tiered": "Rare Tiered",
            "boss_uber": "Boss & Uber",
        }

        for key, (full_title, _) in self.categories.items():
            style = (
                ButtonStyle.primary
                if key == self.current_category
                else ButtonStyle.secondary
            )
            btn = ui.Button(label=button_labels[key], style=style, row=0)
            btn.callback = self._make_category_callback(key)
            self.add_item(btn)

    def _make_category_callback(self, category_key):
        async def callback(interaction: Interaction):
            self.current_category = category_key
            self._rebuild_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

        return callback

    def build_embed(self) -> discord.Embed:
        title, lines = self.categories[self.current_category]

        embed = discord.Embed(
            title=f"👹 Monster Modifiers — {title}",
            description="Higher monster levels unlock higher tiers.",
            color=discord.Color.blue() if "Common" in title else discord.Color.purple(),
        )

        if lines:
            # Split into ≤1024-char chunks across multiple fields
            chunks: list[str] = []
            current: list[str] = []
            current_len = 0
            for line in lines:
                line_len = len(line) + 1  # +1 for newline
                if current and current_len + line_len > 1020:
                    chunks.append("\n".join(current))
                    current = []
                    current_len = 0
                current.append(line)
                current_len += line_len
            if current:
                chunks.append("\n".join(current))
            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name="Modifiers" if i == 0 else "​",
                    value=chunk,
                    inline=False,
                )
        else:
            embed.add_field(
                name="No modifiers", value="This category is empty.", inline=False
            )

        embed.set_footer(
            text="Click any button above to jump directly to that section."
        )
        return embed


def _compact_tier_descriptions(descriptions: list[str]) -> str:
    """Collapse per-tier description strings into one line with X/Y/Z values.

    Splits each description into alternating text/number tokens; wherever the
    number varies across tiers it is replaced with slash-separated values.
    """
    if not descriptions:
        return ""
    if len(set(descriptions)) == 1:
        return descriptions[0]
    pattern = re.compile(r"(\d+(?:\.\d+)?)")
    tokenized = [pattern.split(d) for d in descriptions]
    if len({len(t) for t in tokenized}) != 1:
        return f"{descriptions[0]} → {descriptions[-1]}"
    result = []
    for i, token in enumerate(tokenized[0]):
        if i % 2 == 0:
            result.append(token)
        else:
            values = [t[i] for t in tokenized]
            if len(set(values)) == 1:
                result.append(values[0])
            else:
                def _clean(s: str) -> str:
                    return s.rstrip("0").rstrip(".") if "." in s else s
                result.append("/".join(_clean(v) for v in values))
    return "".join(result)


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
    #  HELPER: Format a {key: description} passive dict
    # ------------------------------------------------------------------
    @staticmethod
    def _format_passive_descs(passives: dict[str, str]) -> str:
        lines = []
        for key, desc in passives.items():
            name = key.title()
            lines.append(f"**{name}** - {desc}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    #  HELPER: Weapon Tiers Generation
    # ------------------------------------------------------------------
    def _generate_weapon_details(self) -> str:
        output = ""
        for key, defn in WEAPON_PASSIVE_DEFS.items():
            output += f"__**{defn.display_name}**__\n"
            for idx, label in enumerate(defn.tier_labels):
                tier = idx + 1
                desc = _WEAPON_PASSIVE_DESC.get(f"{key}_{tier}", defn.description(tier))
                output += f"`T{tier}` **{label}** - {desc}\n"
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
            "companion",
            "slayer",
            "codex",
            "essence",
            "partner",
            "paradise",
            "hematurgy",
            "alchemy",
        ],
    ):

        embed = discord.Embed(color=discord.Color.blue())
        content_added = False

        if category == "monster":
            from core.combat.mobgen.gen_mob import get_modifier_description
            from core.combat.mobgen.modifier_data import MODIFIER_DEFINITIONS

            def _tier_range(name: str) -> str:
                defn = MODIFIER_DEFINITIONS[name]
                descs = [
                    get_modifier_description(make_modifier(name, 1, force_tier=t))
                    for t in range(1, len(defn.tiers) + 1)
                ]
                return _compact_tier_descriptions(descs)

            # Build common lines (sorted alphabetically) + Ascended at end
            common_sorted = sorted(COMMON_MOD_NAMES)
            common_lines = [f"**{n}**: {_tier_range(n)}" for n in common_sorted]
            asc_t1 = make_modifier("Ascended", 10)
            asc_t_max = make_modifier("Ascended", 200, force_max_tier=True)
            common_lines.append(
                f"**Ascended**: {get_modifier_description(asc_t1)} → {get_modifier_description(asc_t_max)} *(scales with level)*"
            )

            # Split Common into two logical pages to avoid 1024 char limit
            mid = len(common_lines) // 2
            common_part1 = common_lines[:mid]
            common_part2 = common_lines[mid:]

            rare_tiered_lines = [
                f"**{n}**: {_tier_range(n)}" for n in sorted(RARE_TIERED_MOD_NAMES)
            ]
            boss_lines = [f"**{n}**: {_tier_range(n)}" for n in sorted(BOSS_MOD_NAMES)]

            user_id = str(interaction.user.id)
            view = ModDetailsMonsterView(
                self.bot,
                user_id,
                common_part1,
                common_part2,
                rare_tiered_lines,
                boss_lines,
            )
            await interaction.response.send_message(
                embed=view.build_embed(), view=view, ephemeral=True
            )
            return

        elif category == "weapon":
            embed.title = "⚔️ Weapon Passives"
            infernal_text = (
                "\n**🔥 Infernal Passives (Engram):**\n"
                + self._format_passive_descs(_INFERNAL_PASSIVE_DESC)
            )
            embed.description = self._generate_weapon_details() + infernal_text
            content_added = True

        elif category == "accessory":
            embed.title = "📿 Accessory Passive Scaling (Max Lvl 10)"
            passives = {k.title(): v for k, v in _ACCESSORY_PASSIVE_FUNCS.items()}
            void_text = (
                "\n**⬛ Void Passives (Engram):**\n"
                + self._format_passive_descs(_VOID_PASSIVE_DESC)
            )
            embed.description = self._generate_scaling_details(passives, 10) + void_text
            content_added = True

        elif category == "glove":
            embed.title = "🧤 Glove Passive Scaling (Max Lvl 5)"
            passives = {k.title(): v for k, v in _GLOVE_PASSIVE_FUNCS.items()}
            embed.description = self._generate_scaling_details(passives, 5)
            content_added = True

        elif category == "boot":
            embed.title = "👢 Boot Passive Scaling (Max Lvl 6)"
            passives = {k.title(): v for k, v in _BOOT_PASSIVE_FUNCS.items()}
            embed.description = self._generate_scaling_details(passives, 6)
            content_added = True

        elif category == "armor":
            embed.title = "🛡️ Armor Passives"
            armor_text = (
                "**Standard Passives:**\n"
                + self._format_passive_descs(_ARMOR_PASSIVE_DESC)
                + "\n\n**🌌 Celestial Passives (Engram):**\n"
                + self._format_passive_descs(_CELESTIAL_PASSIVE_DESC)
            )
            embed.description = armor_text
            content_added = True

        elif category == "helmet":
            embed.title = "🪖 Helmet Passive Scaling (Max Lvl 5)"
            passives = {k.title(): v for k, v in _HELMET_PASSIVE_FUNCS.items()}
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
                "FDR (Flat Dmg Reduction)": lambda t: (
                    f"+{5 + t * 2} Flat Damage Reduction"
                ),
                "PDR (% Dmg Reduction)": lambda t: (
                    f"+{2 + t}% Percent Damage Reduction (bypasses cap)"
                ),
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
            _deity_display = {
                "aphrodite": "💠 Essence of Aphrodite's Disciple",
                "lucifer": "💠 Essence of Lucifer's Heir",
                "gemini": "💠 Essence of Gemini's Lost Twin",
                "neet": "💠 Essence of NEET's Voidling",
            }
            corrupted_lines = ["**— Corrupted Essences (permanent) —**\n"]
            for deity in _deity_display:
                corrupted_lines.append(f"**{_deity_display[deity]}**")
                for slot in ("glove", "boot", "helmet"):
                    key = (deity, slot)
                    if key in _CORRUPTED_DESC:
                        corrupted_lines.append(
                            f"**{slot.title()}** - {_CORRUPTED_DESC[key]}"
                        )
                corrupted_lines.append("")
            corrupted_text = "\n".join(corrupted_lines).rstrip()
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
                "Rolls **+1–8%** Crit Chance.\n\n"
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
                "Removes one random occupied regular essence slot.\n\n" + corrupted_text
            )
            content_added = True

        elif category == "partner":
            embed.title = "🤝 Partner Combat Skills"
            embed.description = (
                "Partners have up to **3 combat skill slots** (unlocked at 4★/5★/6★) "
                "and **1 combat signature** (unique per partner).\n\n"
                "**— Common Combat Skills —**\n\n"
                "**Joint Attack** — % chance to attack alongside you each turn. "
                "Damage is flat based on partner ATK, unaffected by multipliers.\n\n"
                "**Heal** — Heals you for % max HP every 3 turns.\n\n"
                "**Damage Reduction** — % chance to reduce damage taken by 50% per hit.\n\n"
                "**Stat Transfer** — On combat start, adds % of partner ATK/DEF/HP as bonus stats. "
                "Shown in stat bonuses on the profile.\n\n"
                "**Monster Debuff** — On combat start, reduces monster ATK and DEF by %. "
                "Stacks additively with Debilitate (weapon) and Monster Debuff.\n\n"
                "**XP Boost** — +% XP from combat, additive with all other XP sources. Works in Codex.\n\n"
                "**Gold Boost** — +% gold from combat, additive with all other gold sources.\n\n"
                "**Special Find** — +% special rarity, additive with all other sources.\n\n"
                "**ATK from DEF** — On combat start, adds % of partner DEF to your bonus ATK.\n\n"
                "**DEF from ATK** — On combat start, adds % of partner ATK to your bonus DEF.\n\n"
                "**Curse: Damage** — On combat start, reduces monster ATK by %. "
                "Applied when raw monster damage is rolled.\n\n"
                "**Curse: Taken** — Monster takes % more damage. "
                "Applied to your final damage after all reductions (PDR/FDR).\n\n"
                "**— Rare Combat Skills —**\n\n"
                "**Crit Rate** — Flat crit chance increase. Stacks with all other crit sources.\n\n"
                "**Crit Damage** — Flat crit multiplier increase. Stacks with all other crit dmg sources.\n\n"
                "**Execute** — Culls the monster at % HP. Does NOT stack with the weapon Cull family.\n\n"
                "**Ward Regen** — Generates ward per turn regardless of hit/miss.\n\n"
                "**Ward Leech** — % of player damage dealt is gained as ward each turn.\n\n"
                "**— Combat Signatures —**\n\n"
                "**Skol — Essence Communion:** Gain N random corrupted essence buffs at combat start. "
                "Buffs are not granted for essence types the player already equips.\n\n"
                "**Eve — Final Stand:** When HP would drop to 0, survive by consuming potions and restore HP to full.\n\n"
                "**Kay — Windfall:** % chance to obtain an extra curio after each combat. "
                "Does not work in Ascent or Codex.\n\n"
                "**Sigmund — Decisive Strike:** % chance to add +100% damage on a hit. "
                "Additive with Piety, Obliterate, and all other damage bonuses.\n\n"
                "**Velour — Fortune's Tide:** % chance to double all special rarity drops.\n\n"
                "**Flora — Nature's Bounty:** Converts % of final monster gold into skilling materials. "
                "Formula: (gold ÷ 1,000) × skill yield. Doubles with NEET boot.\n\n"
                "**Yvenn — Apex Hunter:** All monsters count as slayer task monsters; "
                "grants bonus slayer progress per kill and enables slayer damage emblems."
            )
            content_added = True

        elif category == "paradise":
            embed.title = "💎 Paradise Jewel Details"
            embed.description = (
                "Each Skill Jewel charges from a specific trigger and unleashes when the charge threshold is met. "
                "Thresholds decrease as the jewel levels up.\n\n"
                "**— Skill Jewels —**\n\n"
                "⚡ **Surge** — Charged by hits. Unleash deals a lightning storm of bonus ATK damage.\n\n"
                "💥 **Cataclysm** — Charged by crits. Unleash primes the next attack as a guaranteed crit with a bonus crit multiplier.\n\n"
                "🐍 **Acrimony** — Charged by misses. Unleash deals a venom burst (% of ATK) + 25% of that as DoT over 4 turns.\n\n"
                "🛡️ **Wardforge** — Charged whenever ward is generated. Unleash grants a ward burst; the next attack gains 30% of current ward as bonus damage.\n\n"
                "🔱 **Bastion** — Charged whenever you take HP damage. Unleash reflects a multiple of the triggering hit back at the monster.\n\n"
                "💚 **Siphon** — Charged by HP regeneration (leech, heal, alchemy). Unleash burst-heals % of max HP; 50% of the heal becomes ward.\n\n"
                "🔥 **Onslaught** — Charged each turn while HP is below 50%. Unleash gives the next attack a large ATK multiplier.\n\n"
                "🧪 **Draught** — Charged by potion use. Unleash generates 0–3 potions depending on level; overflow becomes ward.\n\n"
                "**— Passives —**\n\n"
                "**Charge:** Rapid (+% extra charge chance) · Compression (−N to all thresholds)\n"
                "**Power:** Force (+% unleash strength) · Mirage (% chance to trigger twice) · Lingering (% chance to keep charges after unleash)\n"
                "**Mastery:** Savant (+% jewel leveling speed) · Mastery (+N bonus levels to all jewels)\n"
                "**Synergy:** Fury (+% to damage unleashes) · Arcane (+% ward from jewel effects) · Sustenance (+% healing from jewel effects)\n"
                "**Utility:** Fortune (% chance to duplicate Paradise Jewels found)\n"
                "**Specialization (rare):** One exists per jewel — grants a large power bonus to that jewel only."
            )
            content_added = True

        elif category == "hematurgy":
            embed.title = "🩸 Hematurgy Passives"
            embed.description = (
                "Hematurgy passives are unlocked with **Primordial Blood** and upgraded with "
                "**Evolutionary** or **Mutative Blood**. Tiers 6–7 are mutation-only.\n\n"
                "**— Main Pool (Tiers 1–5) —**\n\n"
                "**Reverberation** — Echo hits have a chance to retrigger themselves.\n\n"
                "**Soothing Venom** — Leech HP equal to a % of poison damage dealt.\n\n"
                "**Iron Momentum** — Gain +ATK per consecutive hit (max 5 stacks; resets on miss).\n\n"
                "**Serrated** — Reduce monster ATK per hit; crits apply double the reduction.\n\n"
                "**Haemorrhage** — Hits build a bleed pool equal to % of ATK; pool deals 10% of itself as damage each round.\n\n"
                "**Vital Resonance** — A % of any ward gained is simultaneously restored as HP.\n\n"
                "**Executioner's Rite** — +ATK and +crit damage while the monster is below 30% HP.\n\n"
                "**Crimson Feast** — On kill, restore a % of Max HP.\n\n"
                "**Phantom Reflex** — On miss, gain a temporary evasion bonus.\n\n"
                "**Chain Reaction** — +crit damage per consecutive crit (max 5 stacks).\n\n"
                "**Regenerative Tissue** — Heal a % of Max HP after any round where no damage was dealt.\n\n"
                "**Fevered Strike** — +ATK for each potion consumed this combat.\n\n"
                "**Predator's Mark** — Crits mark the target; the next hit deals additional bonus damage.\n\n"
                "**Counterforce** — A % of total DEF is added as flat bonus ATK.\n\n"
                "**Defiance** — Dropping below 40% HP triggers +ATK and +DEF for the rest of that combat.\n\n"
                "**— Mutated Pool (mutation-only) —**\n\n"
                "**Spectral Waltz** — Build blade stacks on each hit; crits release all stacks for % ATK damage each.\n\n"
                "**Puncture** — Crits accumulate crit-damage as a bleed; 50% of the bleed bursts on a miss.\n\n"
                "**Flash Frost** — After a set number of consecutive misses, freeze the monster for one round.\n\n"
                "**Ward Inoculation** — At combat start ward converts to DEF and Max HP is doubled; ward generated deals % of its value as damage to the monster.\n\n"
                "**Soul Fracture** — Gain +ATK for every 10% of Max HP lost during this combat."
            )
            content_added = True

        elif category == "alchemy":
            from core.alchemy.mechanics import DistillationMechanics

            embed.title = "⚗️ Alchemy Potion Passives"
            lines = []
            for key, p in DistillationMechanics.POWERFUL_PASSIVES.items():
                v_min = p["value_min"]
                v_max = p["value_max"]
                d_min = p["duration_min"]
                d_max = p["duration_max"]
                if v_min == v_max:
                    v_str = f"{v_min:.0f}"
                else:
                    v_str = f"{v_min:.0f}–{v_max:.0f}"
                if d_min == 0 and d_max == 0:
                    desc = (
                        p["desc"]
                        .replace("{value:.0f}", v_str)
                        .replace(" for {duration:.0f} turns", "")
                        .replace("{duration:.0f}", "")
                    )
                elif d_min == d_max:
                    desc = (
                        p["desc"]
                        .replace("{value:.0f}", v_str)
                        .replace("{duration:.0f}", f"{d_min:.0f}")
                    )
                else:
                    desc = (
                        p["desc"]
                        .replace("{value:.0f}", v_str)
                        .replace("{duration:.0f}", f"{d_min:.0f}–{d_max:.0f}")
                    )
                lines.append(f"{p['emoji']} **{p['name']}** — {desc}")
            embed.description = "\n\n".join(lines)
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
        embed.set_author(name="Guildmaster Amara", icon_url=AMARA_AUTHOR)
        embed.set_thumbnail(url=AMARA_PORTRAIT)

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

        w_text = (
            "\n".join([f"**ID {w['item_id']}**: {w['item_name']}" for w in weapons])
            or "None"
        )
        a_text = (
            "\n".join([f"**ID {a['item_id']}**: {a['item_name']}" for a in accs])
            or "None"
        )

        if len(w_text) > 1000:
            w_text = w_text[:950] + "..."
        if len(a_text) > 1000:
            a_text = a_text[:950] + "..."

        embed.add_field(name="Weapons", value=w_text, inline=False)
        embed.add_field(name="Accessories", value=a_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(General(bot))
