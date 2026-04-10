import discord
from discord import ui, ButtonStyle, Interaction

from core.alchemy.mechanics import AlchemyMechanics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SPIRIT_STONES_COL = 40  # index of spirit_stones in the users table row


async def _hub_from_db(bot, user_id: str, server_id: str) -> "AlchemyHubView":
    """Re-fetches all alchemy data from the DB and returns a fresh hub view."""
    user_row = await bot.database.users.get(user_id, server_id)
    gold = user_row[6] if user_row else 0
    spirit_stones = user_row[SPIRIT_STONES_COL] if user_row else 0
    alchemy_level = await bot.database.alchemy.get_level(user_id)
    passives = await bot.database.alchemy.get_potion_passives(user_id)
    return AlchemyHubView(bot, user_id, server_id, alchemy_level, passives, gold, spirit_stones)


# ---------------------------------------------------------------------------
# Hub View
# ---------------------------------------------------------------------------

class AlchemyHubView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, alchemy_level: int,
                 passives: list, player_gold: int, spirit_stones: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.alchemy_level = alchemy_level
        self.passives = passives          # [{slot, passive_type, passive_value}, ...]
        self.player_gold = player_gold
        self.spirit_stones = spirit_stones
        self.message = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    def build_embed(self) -> discord.Embed:
        slot_count = AlchemyMechanics.get_slot_count(self.alchemy_level)
        level_cost = AlchemyMechanics.get_level_up_cost(self.alchemy_level)

        embed = discord.Embed(title="⚗️ Alchemy", color=discord.Color.purple())
        embed.set_thumbnail(url="https://i.imgur.com/tPQiPaM.png")
        info = [
            f"**Level:** {self.alchemy_level} / {AlchemyMechanics.MAX_LEVEL}",
            f"**Spirit Stones:** 🔮 {self.spirit_stones}",
            f"**Gold:** 💰 {self.player_gold:,}",
            f"**Passive Slots:** {slot_count} unlocked",
        ]
        if level_cost is not None:
            info.append(f"**Next Level Cost:** 💰 {level_cost:,}")
        else:
            info.append("**Level:** ✨ MAX")
        embed.description = "\n".join(info)

        if slot_count > 0:
            passive_by_slot = {p["slot"]: p for p in self.passives}
            lines = []
            for s in range(1, slot_count + 1):
                if s in passive_by_slot:
                    p = passive_by_slot[s]
                    info_d = AlchemyMechanics.PASSIVES.get(p["passive_type"], {})
                    name = info_d.get("name", p["passive_type"])
                    emoji = info_d.get("emoji", "⚗️")
                    desc = AlchemyMechanics.format_passive(p["passive_type"], p["passive_value"])
                    lines.append(f"**[{s}]** {emoji} {name}: *{desc}*")
                else:
                    lines.append(f"**[{s}]** *Empty slot*")
            embed.add_field(name="🧪 Potion Passives", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="🧪 Potion Passives",
                            value="Level up Alchemy to unlock passive slots.", inline=False)

        embed.set_footer(text="Potions in combat trigger your passives automatically.")
        return embed

    @ui.button(label="Transmute", style=ButtonStyle.blurple, emoji="🔄", row=0)
    async def transmute(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        view = AlchemyTransmuteView(self.bot, self.user_id, self.server_id,
                                    self.player_gold, self.spirit_stones)
        embed = await view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Potion Lab", style=ButtonStyle.green, emoji="⚗️", row=0)
    async def potion_lab(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        view = AlchemyPotionLabView(self.bot, self.user_id, self.server_id,
                                    self.alchemy_level, self.passives, self.player_gold)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Level Up", style=ButtonStyle.primary, emoji="⬆️", row=0)
    async def level_up(self, interaction: Interaction, button: ui.Button):
        cost = AlchemyMechanics.get_level_up_cost(self.alchemy_level)
        if cost is None:
            await interaction.response.send_message(
                "You are already at maximum alchemy level!", ephemeral=True)
            return
        if self.player_gold < cost:
            await interaction.response.send_message(
                f"Not enough gold! Need **{cost:,}**, have **{self.player_gold:,}**.",
                ephemeral=True)
            return

        view = _LevelUpConfirmView(self.bot, self.user_id, self.server_id,
                                   self.alchemy_level, cost)
        embed = discord.Embed(
            title="⬆️ Level Up Alchemy?",
            description=(
                f"Upgrade from **Level {self.alchemy_level}** → **Level {self.alchemy_level + 1}**\n\n"
                f"Cost: 💰 **{cost:,}** gold\n"
                f"New slot count: **{AlchemyMechanics.get_slot_count(self.alchemy_level + 1)}**"
            ),
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = interaction.message
        self.stop()

    @ui.button(label="Close", style=ButtonStyle.secondary, emoji="❌", row=0)
    async def close(self, interaction: Interaction, button: ui.Button):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.edit_message(view=None)


# ---------------------------------------------------------------------------
# Level-Up Confirm View (inline mini-view)
# ---------------------------------------------------------------------------

class _LevelUpConfirmView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, current_level: int, cost: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.current_level = current_level
        self.cost = cost
        self.message = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    @ui.button(label="Confirm", style=ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        # Double-check gold
        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        if not user_row or user_row[6] < self.cost:
            await interaction.followup.send("Not enough gold!", ephemeral=True)
            return

        await self.bot.database.users.modify_gold(self.user_id, -self.cost)
        new_level = self.current_level + 1
        await self.bot.database.alchemy.set_level(self.user_id, new_level)

        view = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        embed.colour = discord.Color.gold()
        embed.title = f"✨ Alchemy leveled up to **{new_level}**!"
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="⬅️")
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        view = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()


# ---------------------------------------------------------------------------
# Transmute View
# ---------------------------------------------------------------------------

class _TransmuteSelect(ui.Select):
    def __init__(self, options_data: list):
        options = [
            discord.SelectOption(
                label=opt["label"][:100],
                description=opt["desc"][:100],
                value=str(i),
            )
            for i, opt in enumerate(options_data[:25])
        ]
        super().__init__(placeholder="Choose a transmutation…", options=options, min_values=1, max_values=1)
        self.options_data = options_data
        self.selected_index: int | None = None

    async def callback(self, interaction: Interaction):
        self.selected_index = int(self.values[0])
        await interaction.response.defer()


class AlchemyTransmuteView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, player_gold: int, spirit_stones: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player_gold = player_gold
        self.spirit_stones = spirit_stones
        self.message = None
        self._select: _TransmuteSelect | None = None
        self._options_data: list = []

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def build_embed(self) -> discord.Embed:
        """Fetch resource amounts, build select options, (re)attach to view, return embed."""
        # Fetch current resource amounts
        amounts: dict[tuple, int] = {}
        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            row = await self.bot.database.skills.get_data(self.user_id, self.server_id, skill)
            for i, col in enumerate(cols):
                amounts[(skill, col)] = row[i + 3] if row else 0

        self._options_data = []

        # Skill-tier upgrades (4 upgrades × 3 skills = 12 options)
        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            names = AlchemyMechanics.SKILL_TIER_NAMES[skill]
            for i in range(len(cols) - 1):
                src_col = cols[i]
                dst_col = cols[i + 1]
                src_amt = amounts.get((skill, src_col), 0)
                gold_cost = AlchemyMechanics.TRANSMUTE_GOLD[i]
                ratio = AlchemyMechanics.TRANSMUTE_RATIO
                self._options_data.append({
                    "type": "skill",
                    "skill": skill,
                    "src_col": src_col,
                    "dst_col": dst_col,
                    "src_tier": i,
                    "label": f"{names[i]} → {names[i + 1]} ({skill.title()})",
                    "desc": f"{ratio}× {names[i]} → 1× {names[i + 1]} | have {src_amt} | {gold_cost}g",
                    "gold_cost": gold_cost,
                    "ratio": ratio,
                })

        # Spirit-stone → resource conversions (2 tiers × 3 skills = 6 options)
        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            names = AlchemyMechanics.SKILL_TIER_NAMES[skill]
            for tier_idx, qty in AlchemyMechanics.SPIRIT_STONE_RATES.items():
                self._options_data.append({
                    "type": "spirit_stone",
                    "skill": skill,
                    "dst_col": cols[tier_idx],
                    "label": f"🔮 Stone → {qty}× {names[tier_idx]} ({skill.title()})",
                    "desc": f"1 Spirit Stone → {qty}× {names[tier_idx]} | {self.spirit_stones} stones",
                    "qty": qty,
                })

        # Rebuild items
        self.clear_items()
        self._select = _TransmuteSelect(self._options_data)
        self.add_item(self._select)

        confirm_btn = ui.Button(label="Confirm", style=ButtonStyle.green, emoji="✅")
        confirm_btn.callback = self._on_confirm
        self.add_item(confirm_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️")
        back_btn.callback = self._on_back
        self.add_item(back_btn)

        embed = discord.Embed(title="🔄 Transmute Resources", color=discord.Color.blurple())
        embed.description = (
            "Convert lower-tier skilling resources into higher ones.\n"
            f"**Ratio:** {AlchemyMechanics.TRANSMUTE_RATIO}:1 | "
            f"**Gold:** 💰 {self.player_gold:,} | **Spirit Stones:** 🔮 {self.spirit_stones}\n\n"
            "Select a conversion and press **Confirm**."
        )
        return embed

    async def _on_confirm(self, interaction: Interaction):
        if not self._select or self._select.selected_index is None:
            await interaction.response.send_message(
                "Please select a transmutation first.", ephemeral=True)
            return

        opt = self._options_data[self._select.selected_index]

        if opt["type"] == "skill":
            ratio = opt["ratio"]
            gold_cost = opt["gold_cost"]

            src_amt = await self.bot.database.alchemy.get_resource_amount(
                self.user_id, self.server_id, opt["skill"], opt["src_col"])

            if src_amt < ratio:
                await interaction.response.send_message(
                    f"Not enough **{opt['src_col']}**! Need {ratio}, have {src_amt}.",
                    ephemeral=True)
                return

            user_row = await self.bot.database.users.get(self.user_id, self.server_id)
            current_gold = user_row[6] if user_row else 0
            if current_gold < gold_cost:
                await interaction.response.send_message(
                    f"Not enough gold! Need 💰 {gold_cost:,}, have {current_gold:,}.",
                    ephemeral=True)
                return

            await self.bot.database.alchemy.transmute(
                self.user_id, self.server_id, opt["skill"],
                opt["src_col"], -ratio,
                opt["dst_col"], 1,
            )
            await self.bot.database.users.modify_gold(self.user_id, -gold_cost)
            self.player_gold = max(0, self.player_gold - gold_cost)

            await interaction.response.send_message(
                f"✅ Transmuted **{ratio}×** {opt['src_col']} → **1×** {opt['dst_col']}! "
                f"(-💰 {gold_cost:,})",
                ephemeral=True)

        elif opt["type"] == "spirit_stone":
            user_row = await self.bot.database.users.get(self.user_id, self.server_id)
            current_stones = user_row[SPIRIT_STONES_COL] if user_row else 0
            if current_stones < 1:
                await interaction.response.send_message(
                    "You have no 🔮 Spirit Stones!", ephemeral=True)
                return

            await self.bot.database.users.modify_currency(self.user_id, "spirit_stones", -1)
            self.spirit_stones = max(0, self.spirit_stones - 1)

            await self.bot.database.skills.update_batch(
                self.user_id, self.server_id, opt["skill"],
                {opt["dst_col"]: opt["qty"]}
            )

            await interaction.response.send_message(
                f"✅ Converted 🔮 Spirit Stone → **{opt['qty']}×** {opt['dst_col']}!",
                ephemeral=True)

    async def _on_back(self, interaction: Interaction):
        await interaction.response.defer()
        view = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()


# ---------------------------------------------------------------------------
# Potion Lab View
# ---------------------------------------------------------------------------

class _SlotSelect(ui.Select):
    def __init__(self, slot_count: int):
        options = [
            discord.SelectOption(label=f"Slot {s}", value=str(s))
            for s in range(1, slot_count + 1)
        ]
        super().__init__(placeholder="Choose a slot…", options=options, min_values=1, max_values=1)
        self.chosen_slot: int | None = None

    async def callback(self, interaction: Interaction):
        self.chosen_slot = int(self.values[0])
        await interaction.response.defer()


class AlchemyPotionLabView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, alchemy_level: int,
                 passives: list, player_gold: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.alchemy_level = alchemy_level
        self.passives = passives
        self.player_gold = player_gold
        self.message = None
        self._slot_select: _SlotSelect | None = None

        slot_count = AlchemyMechanics.get_slot_count(alchemy_level)
        if slot_count > 0:
            self._slot_select = _SlotSelect(slot_count)
            self.add_item(self._slot_select)

        roll_btn = ui.Button(label="Roll Passive", style=ButtonStyle.primary, emoji="🎲", row=1)
        roll_btn.callback = self._on_roll
        self.add_item(roll_btn)

        clear_btn = ui.Button(label="Clear Slot", style=ButtonStyle.danger, emoji="🗑️", row=1)
        clear_btn.callback = self._on_clear
        self.add_item(clear_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1)
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    def build_embed(self) -> discord.Embed:
        slot_count = AlchemyMechanics.get_slot_count(self.alchemy_level)
        embed = discord.Embed(title="⚗️ Potion Lab", color=discord.Color.green())

        embed.description = (
            f"**Level:** {self.alchemy_level} | **Gold:** 💰 {self.player_gold:,}\n\n"
            "**Roll Costs:** " +
            " | ".join(f"Slot {s}: {AlchemyMechanics.ROLL_COSTS[s]:,}g"
                       for s in range(1, slot_count + 1)) +
            "\n\nSelect a slot, then roll or clear it."
        )

        passive_by_slot = {p["slot"]: p for p in self.passives}
        lines = []
        for s in range(1, slot_count + 1):
            if s in passive_by_slot:
                p = passive_by_slot[s]
                info = AlchemyMechanics.PASSIVES.get(p["passive_type"], {})
                name = info.get("name", p["passive_type"])
                emoji = info.get("emoji", "⚗️")
                desc = AlchemyMechanics.format_passive(p["passive_type"], p["passive_value"])
                lines.append(f"**[{s}]** {emoji} {name}: *{desc}*")
            else:
                lines.append(f"**[{s}]** *Empty slot*")

        embed.add_field(name="Current Passives", value="\n".join(lines) if lines else "None", inline=False)

        all_passives = AlchemyMechanics.PASSIVES
        passive_list = "\n".join(
            f"{v['emoji']} **{v['name']}**: {v['desc'].format(value=0).replace(' 0', ' …')}"
            for v in all_passives.values()
        )
        embed.add_field(name="Possible Passives", value=passive_list[:1024], inline=False)
        return embed

    async def _on_roll(self, interaction: Interaction):
        slot = self._slot_select.chosen_slot if self._slot_select else None
        if slot is None:
            await interaction.response.send_message("Please select a slot first.", ephemeral=True)
            return

        cost = AlchemyMechanics.ROLL_COSTS.get(slot, 9999)
        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        current_gold = user_row[6] if user_row else 0
        if current_gold < cost:
            await interaction.response.send_message(
                f"Not enough gold for Slot {slot}! Need 💰 {cost:,}, have {current_gold:,}.",
                ephemeral=True)
            return

        passive_type, passive_value = AlchemyMechanics.roll_passive(self.alchemy_level)
        await self.bot.database.alchemy.set_passive(
            self.user_id, slot, passive_type, passive_value)
        await self.bot.database.users.modify_gold(self.user_id, -cost)
        self.player_gold = max(0, self.player_gold - cost)

        # Refresh passives list
        self.passives = await self.bot.database.alchemy.get_potion_passives(self.user_id)

        info = AlchemyMechanics.PASSIVES.get(passive_type, {})
        name = info.get("name", passive_type)
        emoji = info.get("emoji", "⚗️")
        desc = AlchemyMechanics.format_passive(passive_type, passive_value)

        embed = self.build_embed()
        await interaction.response.edit_message(
            content=f"🎲 **Slot {slot}** rolled: {emoji} **{name}** — *{desc}*! (-💰 {cost:,})",
            embed=embed, view=self)

    async def _on_clear(self, interaction: Interaction):
        slot = self._slot_select.chosen_slot if self._slot_select else None
        if slot is None:
            await interaction.response.send_message("Please select a slot first.", ephemeral=True)
            return

        await self.bot.database.alchemy.delete_passive(self.user_id, slot)
        self.passives = await self.bot.database.alchemy.get_potion_passives(self.user_id)

        embed = self.build_embed()
        await interaction.response.edit_message(
            content=f"🗑️ Slot **{slot}** cleared.",
            embed=embed, view=self)

    async def _on_back(self, interaction: Interaction):
        await interaction.response.defer()
        view = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()
