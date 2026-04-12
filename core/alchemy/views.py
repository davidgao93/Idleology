import discord
from discord import ui, ButtonStyle, Interaction

from core.alchemy.mechanics import AlchemyMechanics
from core.alchemy.synthesis_views import _build_synthesis_hub

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _hub_from_db(bot, user_id: str, server_id: str) -> "AlchemyHubView":
    """Re-fetches all alchemy data from the DB and returns a fresh hub view."""
    user_row = await bot.database.users.get(user_id, server_id)
    gold = user_row[6] if user_row else 0
    spirit_stones = await bot.database.users.get_currency(user_id, "spirit_stones")
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
            info.append(f"**Next Level Cost:** 🔮 {level_cost} Spirit Stones")
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
                            value="Level up Alchemy to unlock additional passive slots.", inline=False)

        return embed

    @ui.button(label="Synthesis", style=ButtonStyle.secondary, emoji="⚗️", row=0)
    async def synthesis(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        view  = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg   = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Transmute", style=ButtonStyle.blurple, emoji="🔄", row=0)
    async def transmute(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        view = AlchemyTransmuteView(self.bot, self.user_id, self.server_id,
                                    self.alchemy_level, self.player_gold, self.spirit_stones)
        embed = await view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Potion Lab", style=ButtonStyle.green, emoji="⚗️", row=0)
    async def potion_lab(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        free_roll_used = await self.bot.database.alchemy.get_free_roll_used(self.user_id)
        view = AlchemyPotionLabView(self.bot, self.user_id, self.server_id,
                                    self.alchemy_level, self.passives, self.spirit_stones,
                                    free_roll_used=free_roll_used)
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
        if self.spirit_stones < cost:
            await interaction.response.send_message(
                f"Not enough Spirit Stones! Need 🔮 **{cost}**, have **{self.spirit_stones}**.",
                ephemeral=True)
            return

        view = _LevelUpConfirmView(self.bot, self.user_id, self.server_id,
                                   self.alchemy_level, cost)
        new_level = self.alchemy_level + 1
        embed = discord.Embed(
            title="⬆️ Level Up Alchemy?",
            description=(
                f"Upgrade from **Level {self.alchemy_level}** → **Level {new_level}**\n\n"
                f"Cost: 🔮 **{cost}** Spirit Stones\n"
                f"New slot count: **{AlchemyMechanics.get_slot_count(new_level)}**\n"
                f"New transmutation ratio: **{AlchemyMechanics.get_upgrade_ratio(new_level)}:1** upgrade / "
                f"**1:{AlchemyMechanics.get_downgrade_ratio(new_level)}** downgrade\n\n"
                f"✨ The new slot will be available for a free roll in the Potion Lab!"
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
        await interaction.response.defer()
        await interaction.delete_original_response()


# ---------------------------------------------------------------------------
# Level-Up Confirm View
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
        current_stones = await self.bot.database.users.get_currency(self.user_id, "spirit_stones")
        if current_stones < self.cost:
            await interaction.followup.send(
                f"Not enough Spirit Stones! Need 🔮 {self.cost}, have {current_stones}.",
                ephemeral=True)
            return

        await self.bot.database.users.modify_currency(self.user_id, "spirit_stones", -self.cost)
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
# Transmute View — quantity modal
# ---------------------------------------------------------------------------

class _TransmuteQuantityModal(ui.Modal, title="How many to transmute?"):
    quantity = ui.TextInput(
        label="Quantity",
        placeholder="Enter a number (e.g. 5)",
        min_length=1,
        max_length=6,
    )

    def __init__(self, view: "AlchemyTransmuteView", opt: dict):
        super().__init__()
        self._view = view
        self._opt = opt

    async def on_submit(self, interaction: Interaction):
        raw = self.quantity.value.strip()
        if not raw.isdigit() or int(raw) < 1:
            await interaction.response.send_message(
                "Please enter a positive whole number.", ephemeral=True)
            return

        qty = int(raw)
        opt = self._opt
        gold_cost_each = opt["gold_cost"]
        ratio = opt["ratio"]

        # Validate gold
        user_row = await self._view.bot.database.users.get(self._view.user_id, self._view.server_id)
        current_gold = user_row[6] if user_row else 0
        total_gold = gold_cost_each * qty
        if current_gold < total_gold:
            max_by_gold = current_gold // gold_cost_each
            await interaction.response.send_message(
                f"Not enough gold for **{qty}** operations (need 💰 {total_gold:,}). "
                f"You can afford up to **{max_by_gold}**.",
                ephemeral=True)
            return

        if opt["type"] == "upgrade":
            src_needed = ratio * qty
            src_amt = await self._view.bot.database.alchemy.get_resource_amount(
                self._view.user_id, self._view.server_id, opt["skill"], opt["src_col"])
            if src_amt < src_needed:
                max_by_res = src_amt // ratio
                await interaction.response.send_message(
                    f"Not enough **{opt['src_col']}** for **{qty}** operations "
                    f"(need {src_needed}, have {src_amt}). "
                    f"You can do up to **{max_by_res}**.",
                    ephemeral=True)
                return
            await self._view.bot.database.alchemy.transmute(
                self._view.user_id, self._view.server_id, opt["skill"],
                opt["src_col"], -(ratio * qty),
                opt["dst_col"], qty,
            )
            await self._view.bot.database.users.modify_gold(self._view.user_id, -total_gold)
            self._view.player_gold = max(0, self._view.player_gold - total_gold)
            await interaction.response.send_message(
                f"✅ Transmuted **{ratio * qty}×** {opt['src_col']} → **{qty}×** {opt['dst_col']}! "
                f"(-💰 {total_gold:,})",
                ephemeral=True)

        else:  # downgrade
            src_amt = await self._view.bot.database.alchemy.get_resource_amount(
                self._view.user_id, self._view.server_id, opt["skill"], opt["src_col"])
            if src_amt < qty:
                await interaction.response.send_message(
                    f"Not enough **{opt['src_col']}** for **{qty}** operations "
                    f"(have {src_amt}).",
                    ephemeral=True)
                return
            await self._view.bot.database.alchemy.transmute(
                self._view.user_id, self._view.server_id, opt["skill"],
                opt["src_col"], -qty,
                opt["dst_col"], ratio * qty,
            )
            await self._view.bot.database.users.modify_gold(self._view.user_id, -total_gold)
            self._view.player_gold = max(0, self._view.player_gold - total_gold)
            await interaction.response.send_message(
                f"✅ Broke down **{qty}×** {opt['src_col']} → **{ratio * qty}×** {opt['dst_col']}! "
                f"(-💰 {total_gold:,})",
                ephemeral=True)


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
    def __init__(self, bot, user_id: str, server_id: str, alchemy_level: int,
                 player_gold: int, spirit_stones: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.alchemy_level = alchemy_level
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
        up_ratio = AlchemyMechanics.get_upgrade_ratio(self.alchemy_level)
        dn_ratio = AlchemyMechanics.get_downgrade_ratio(self.alchemy_level)

        amounts: dict[tuple, int] = {}
        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            row = await self.bot.database.skills.get_data(self.user_id, self.server_id, skill)
            for i, col in enumerate(cols):
                amounts[(skill, col)] = row[i + 3] if row else 0

        self._options_data = []

        # Upgrades
        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            names = AlchemyMechanics.SKILL_TIER_NAMES[skill]
            for i in range(len(cols) - 1):
                src_col = cols[i]
                dst_col = cols[i + 1]
                src_amt = amounts.get((skill, src_col), 0)
                dst_tier_idx = i + 1
                gold_cost = AlchemyMechanics.TRANSMUTE_UPGRADE_GOLD[dst_tier_idx]
                self._options_data.append({
                    "type": "upgrade",
                    "skill": skill,
                    "src_col": src_col,
                    "dst_col": dst_col,
                    "label": f"↑ {names[i]} → {names[i + 1]} ({skill.title()})",
                    "desc": f"{up_ratio}× {names[i]} → 1× {names[i + 1]} | have {src_amt} | {gold_cost:,}g each",
                    "gold_cost": gold_cost,
                    "ratio": up_ratio,
                })

        # Downgrades
        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            names = AlchemyMechanics.SKILL_TIER_NAMES[skill]
            for i in range(1, len(cols)):
                src_col = cols[i]
                dst_col = cols[i - 1]
                src_amt = amounts.get((skill, src_col), 0)
                src_tier_idx = i
                gold_cost = AlchemyMechanics.TRANSMUTE_DOWNGRADE_GOLD[src_tier_idx]
                self._options_data.append({
                    "type": "downgrade",
                    "skill": skill,
                    "src_col": src_col,
                    "dst_col": dst_col,
                    "label": f"↓ {names[i]} → {names[i - 1]} ({skill.title()})",
                    "desc": f"1× {names[i]} → {dn_ratio}× {names[i - 1]} | have {src_amt} | {gold_cost:,}g each",
                    "gold_cost": gold_cost,
                    "ratio": dn_ratio,
                })

        self.clear_items()
        self._select = _TransmuteSelect(self._options_data)
        self.add_item(self._select)

        confirm_btn = ui.Button(label="Transmute", style=ButtonStyle.green, emoji="✅")
        confirm_btn.callback = self._on_confirm
        self.add_item(confirm_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️")
        back_btn.callback = self._on_back
        self.add_item(back_btn)

        embed = discord.Embed(title="🔄 Transmute Resources", color=discord.Color.blurple())
        embed.description = (
            f"Convert resources between tiers using Alchemy.\n"
            f"**Upgrade ratio:** {up_ratio}:1 | **Downgrade ratio:** 1:{dn_ratio} "
            f"(improves with alchemy level)\n"
            f"**Gold:** 💰 {self.player_gold:,}\n\n"
            "Select a conversion, then press **Transmute** to enter a quantity."
        )
        return embed

    async def _on_confirm(self, interaction: Interaction):
        if not self._select or self._select.selected_index is None:
            await interaction.response.send_message(
                "Please select a transmutation first.", ephemeral=True)
            return
        opt = self._options_data[self._select.selected_index]
        await interaction.response.send_modal(_TransmuteQuantityModal(self, opt))

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


class _ClearConfirmView(ui.View):
    """Inline confirmation before clearing a passive slot."""

    def __init__(self, parent: "AlchemyPotionLabView", slot: int):
        super().__init__(timeout=30)
        self._parent = parent
        self._slot = slot

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self._parent.user_id

    @ui.button(label="Yes, clear it", style=ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        await self._parent.bot.database.alchemy.delete_passive(self._parent.user_id, self._slot)
        self._parent.passives = await self._parent.bot.database.alchemy.get_potion_passives(
            self._parent.user_id)
        embed = self._parent.build_embed()
        self.stop()
        await interaction.response.edit_message(
            content=f"🗑️ Slot **{self._slot}** cleared.",
            embed=embed, view=self._parent)

    @ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="⬅️")
    async def cancel(self, interaction: Interaction, button: ui.Button):
        embed = self._parent.build_embed()
        self.stop()
        await interaction.response.edit_message(content=None, embed=embed, view=self._parent)


class AlchemyPotionLabView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, alchemy_level: int,
                 passives: list, spirit_stones: int, free_roll_used: bool = False):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.alchemy_level = alchemy_level
        self.passives = passives
        self.spirit_stones = spirit_stones
        self.free_roll_used = free_roll_used
        self.message = None
        self._slot_select: _SlotSelect | None = None

        slot_count = AlchemyMechanics.get_slot_count(alchemy_level)
        if slot_count > 0:
            self._slot_select = _SlotSelect(slot_count)
            self.add_item(self._slot_select)

        roll_btn = ui.Button(label="Synthesize", style=ButtonStyle.primary, emoji="🌟", row=1)
        roll_btn.callback = self._on_roll
        self.add_item(roll_btn)

        clear_btn = ui.Button(label="Destroy", style=ButtonStyle.danger, emoji="🗑️", row=1)
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
            f"**Level:** {self.alchemy_level} | **Spirit Stones:** 🔮 {self.spirit_stones}\n\n"
            "Select a slot, then synthesize or destroy it."
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
            f"{v['emoji']} **{v['name']}**: {AlchemyMechanics.format_passive_range(k)}"
            for k, v in all_passives.items()
        )
        embed.add_field(name="Possible Passives", value=passive_list[:1024], inline=False)
        return embed

    async def _on_roll(self, interaction: Interaction):
        slot = self._slot_select.chosen_slot if self._slot_select else None
        if slot is None:
            await interaction.response.send_message("Please select a slot first.", ephemeral=True)
            return

        # Free roll: one-time global grant, tracked in DB regardless of which slot
        if not self.free_roll_used:
            is_free = True
        else:
            is_free = False
            cost = AlchemyMechanics.REROLL_COST
            current_stones = await self.bot.database.users.get_currency(self.user_id, "spirit_stones")
            if current_stones < cost:
                await interaction.response.send_message(
                    f"Not enough Spirit Stones to synthesize! Need 🔮 {cost}, have {current_stones}.",
                    ephemeral=True)
                return
            await self.bot.database.users.modify_currency(self.user_id, "spirit_stones", -cost)
            self.spirit_stones = max(0, self.spirit_stones - cost)

        if is_free:
            await self.bot.database.alchemy.set_free_roll_used(self.user_id)
            self.free_roll_used = True

        passive_type, passive_value = AlchemyMechanics.roll_passive(self.alchemy_level)
        await self.bot.database.alchemy.set_passive(self.user_id, slot, passive_type, passive_value)
        self.passives = await self.bot.database.alchemy.get_potion_passives(self.user_id)

        info = AlchemyMechanics.PASSIVES.get(passive_type, {})
        name = info.get("name", passive_type)
        emoji = info.get("emoji", "⚗️")
        desc = AlchemyMechanics.format_passive(passive_type, passive_value)

        embed = self.build_embed()
        await interaction.response.edit_message(
            content=f"🌟 **Your potion has gained {emoji} **{name}** — *{desc}*!",
            embed=embed, view=self)

    async def _on_clear(self, interaction: Interaction):
        slot = self._slot_select.chosen_slot if self._slot_select else None
        if slot is None:
            await interaction.response.send_message("Please select a slot first.", ephemeral=True)
            return

        if self._slot_is_empty(slot):
            await interaction.response.send_message(
                f"Slot **{slot}** is already empty.", ephemeral=True)
            return

        passive_by_slot = {p["slot"]: p for p in self.passives}
        p = passive_by_slot[slot]
        info = AlchemyMechanics.PASSIVES.get(p["passive_type"], {})
        name = info.get("name", p["passive_type"])
        emoji = info.get("emoji", "⚗️")

        confirm_view = _ClearConfirmView(self, slot)
        embed = discord.Embed(
            title="🗑️ Clear Passive?",
            description=(
                f"Are you sure you want to clear **Slot {slot}**?\n\n"
                f"Current passive: {emoji} **{name}**"
            ),
            color=discord.Color.red()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=confirm_view)

    async def _on_back(self, interaction: Interaction):
        await interaction.response.defer()
        view = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()
