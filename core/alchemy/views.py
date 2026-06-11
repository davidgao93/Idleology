import asyncio
import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.alchemy.mechanics import (
    AlchemyMechanics,
    DistillationMechanics,
    get_passive_info,
    get_passive_name_emoji,
    get_passive_list_desc,
)
from core.base_view import BaseView
from core.images import ALCHEMY_HUB
from core.skills.mastery import get_attunement_alchemy_bonus

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
    return AlchemyHubView(
        bot, user_id, server_id, alchemy_level, passives, gold, spirit_stones
    )


# ---------------------------------------------------------------------------
# Hub View
# ---------------------------------------------------------------------------


class AlchemyHubView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        alchemy_level: int,
        passives: list,
        player_gold: int,
        spirit_stones: int,
    ):
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.passives = passives
        self.player_gold = player_gold
        self.spirit_stones = spirit_stones

    def build_embed(self) -> discord.Embed:
        slot_count = AlchemyMechanics.get_slot_count(self.alchemy_level)
        level_cost = AlchemyMechanics.get_level_up_cost(self.alchemy_level)

        embed = discord.Embed(title="⚗️ Alchemy", color=discord.Color.purple())
        embed.set_thumbnail(url=ALCHEMY_HUB)
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
                    name, emoji = get_passive_name_emoji(p["passive_type"])
                    desc = AlchemyMechanics.format_passive(
                        p["passive_type"], p["passive_value"]
                    )
                    lines.append(f"**[{s}]** {emoji} {name}: *{desc}*")
                else:
                    lines.append(f"**[{s}]** *Empty slot*")
            embed.add_field(
                name="🧪 Potion Passives", value="\n".join(lines), inline=False
            )
        else:
            embed.add_field(
                name="🧪 Potion Passives",
                value="Level up Alchemy to unlock additional passive slots.",
                inline=False,
            )

        return embed

    @ui.button(label="Synthesis", style=ButtonStyle.secondary, emoji="⚗️", row=0)
    async def synthesis(self, interaction: Interaction, button: ui.Button):
        from core.alchemy.synthesis_views import _build_synthesis_hub

        await interaction.response.defer()
        view = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Transmute", style=ButtonStyle.blurple, emoji="🔄", row=0)
    async def transmute(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        view = AlchemyTransmuteView(
            self.bot,
            self.user_id,
            self.server_id,
            self.alchemy_level,
            self.player_gold,
            self.spirit_stones,
        )
        embed = await view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Potion Lab", style=ButtonStyle.green, emoji="⚗️", row=0)
    async def potion_lab(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        free_roll_used = await self.bot.database.alchemy.get_free_roll_used(
            self.user_id
        )
        view = AlchemyPotionLabView(
            self.bot,
            self.user_id,
            self.server_id,
            self.alchemy_level,
            self.passives,
            self.spirit_stones,
            free_roll_used=free_roll_used,
        )
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Level Up", style=ButtonStyle.primary, emoji="⬆️", row=0)
    async def level_up(self, interaction: Interaction, button: ui.Button):
        cost = AlchemyMechanics.get_level_up_cost(self.alchemy_level)
        if cost is None:
            await interaction.response.send_message(
                "You are already at maximum alchemy level!", ephemeral=True
            )
            return
        if self.spirit_stones < cost:
            await interaction.response.send_message(
                f"Not enough Spirit Stones! Need 🔮 **{cost}**, have **{self.spirit_stones}**.",
                ephemeral=True,
            )
            return

        view = _LevelUpConfirmView(
            self.bot, self.user_id, self.server_id, self.alchemy_level, cost
        )
        new_level = self.alchemy_level + 1
        up_r = AlchemyMechanics.get_upgrade_ratio(new_level)
        dn_r = AlchemyMechanics.get_downgrade_ratio(new_level)

        embed = discord.Embed(
            title="⬆️ Level Up Alchemy?",
            description=(
                f"Upgrade from **Level {self.alchemy_level}** → **Level {new_level}**\n\n"
                f"Cost: 🔮 **{cost}** Spirit Stones\n"
                f"New slot count: **{AlchemyMechanics.get_slot_count(new_level)}**\n"
                f"New transmutation ratio: **{up_r}:1** upgrade / **1:{dn_r}** downgrade\n\n"
                f"✨ The new slot will be available for a free Distillation in the Potion Lab!"
            ),
            color=discord.Color.gold(),
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


class _LevelUpConfirmView(BaseView):
    def __init__(
        self, bot, user_id: str, server_id: str, current_level: int, cost: int
    ):
        super().__init__(bot, user_id, server_id)
        self.current_level = current_level
        self.cost = cost
        self._processing = False

    @ui.button(label="Confirm", style=ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        current_stones = await self.bot.database.users.get_currency(
            self.user_id, "spirit_stones"
        )
        if current_stones < self.cost:
            await interaction.followup.send(
                f"Not enough Spirit Stones! Need 🔮 {self.cost}, have {current_stones}.",
                ephemeral=True,
            )
            return

        await self.bot.database.users.modify_currency(
            self.user_id, "spirit_stones", -self.cost
        )
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
                "Please enter a positive whole number.", ephemeral=True
            )
            return

        qty = int(raw)
        opt = self._opt
        gold_cost_each = opt["gold_cost"]
        ratio = opt["ratio"]

        # Master Baiter (permanent) — one-step better ratios
        try:
            mrow = await self._view.bot.database.skills.get_mastery(
                self._view.user_id, self._view.server_id
            )
            from core.skills.mastery import has_master_baiter

            if has_master_baiter(mrow):
                # Improve the ratio by 1 step (lower number is better for upgrade)
                if opt["type"] == "upgrade":
                    ratio = max(2, ratio - 1)
                else:
                    ratio = min(5, ratio + 1)  # downgrade gives more when improved
        except Exception:
            pass

        # Validate gold
        user_row = await self._view.bot.database.users.get(
            self._view.user_id, self._view.server_id
        )
        current_gold = user_row[6] if user_row else 0
        total_gold = gold_cost_each * qty
        if current_gold < total_gold:
            max_by_gold = current_gold // gold_cost_each
            await interaction.response.send_message(
                f"Not enough gold for **{qty}** operations (need 💰 {total_gold:,}). "
                f"You can afford up to **{max_by_gold}**.",
                ephemeral=True,
            )
            return

        if opt["type"] == "upgrade":
            src_needed = ratio * qty
            src_amt = await self._view.bot.database.alchemy.get_resource_amount(
                self._view.user_id, self._view.server_id, opt["skill"], opt["src_col"]
            )
            if src_amt < src_needed:
                max_by_res = src_amt // ratio
                await interaction.response.send_message(
                    f"Not enough **{opt['src_col']}** for **{qty}** operations "
                    f"(need {src_needed}, have {src_amt}). "
                    f"You can do up to **{max_by_res}**.",
                    ephemeral=True,
                )
                return

            # Druidic Ritual (Nature's Attunement) bonus — +X% output on upgrades
            dst_delta = qty
            try:
                mrow = await self._view.bot.database.skills.get_mastery(
                    self._view.user_id, self._view.server_id
                )
                bonus = get_attunement_alchemy_bonus(mrow)
                if bonus > 0:
                    dst_delta = int(qty * (1.0 + bonus))
            except Exception:
                pass

            await self._view.bot.database.alchemy.transmute(
                self._view.user_id,
                self._view.server_id,
                opt["skill"],
                opt["src_col"],
                -(ratio * qty),
                opt["dst_col"],
                dst_delta,
            )
            await self._view.bot.database.users.modify_gold(
                self._view.user_id, -total_gold
            )
            self._view.player_gold = max(0, self._view.player_gold - total_gold)

            bonus_text = (
                f" (+{dst_delta - qty} from Druidic Ritual)" if dst_delta > qty else ""
            )
            await interaction.response.send_message(
                f"✅ Transmuted **{ratio * qty}×** {opt['src_col']} → **{dst_delta}×** {opt['dst_col']}!{bonus_text} "
                f"(-💰 {total_gold:,})",
                ephemeral=True,
            )

        else:  # downgrade
            src_amt = await self._view.bot.database.alchemy.get_resource_amount(
                self._view.user_id, self._view.server_id, opt["skill"], opt["src_col"]
            )
            if src_amt < qty:
                await interaction.response.send_message(
                    f"Not enough **{opt['src_col']}** for **{qty}** operations "
                    f"(have {src_amt}).",
                    ephemeral=True,
                )
                return
            await self._view.bot.database.alchemy.transmute(
                self._view.user_id,
                self._view.server_id,
                opt["skill"],
                opt["src_col"],
                -qty,
                opt["dst_col"],
                ratio * qty,
            )
            await self._view.bot.database.users.modify_gold(
                self._view.user_id, -total_gold
            )
            self._view.player_gold = max(0, self._view.player_gold - total_gold)
            await interaction.response.send_message(
                f"✅ Broke down **{qty}×** {opt['src_col']} → **{ratio * qty}×** {opt['dst_col']}! "
                f"(-💰 {total_gold:,})",
                ephemeral=True,
            )


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
        super().__init__(
            placeholder="Choose a transmutation…",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.options_data = options_data
        self.selected_index: int | None = None

    async def callback(self, interaction: Interaction):
        self.selected_index = int(self.values[0])
        await interaction.response.defer()


class AlchemyTransmuteView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        alchemy_level: int,
        player_gold: int,
        spirit_stones: int,
    ):
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.player_gold = player_gold
        self.spirit_stones = spirit_stones
        self._select: _TransmuteSelect | None = None
        self._options_data: list = []

    async def build_embed(self) -> discord.Embed:
        has_baiter = False
        try:
            mrow = await self.bot.database.skills.get_mastery(
                self.user_id, self.server_id
            )
            from core.skills.mastery import has_master_baiter

            has_baiter = has_master_baiter(mrow)
        except Exception:
            pass

        up_ratio = AlchemyMechanics.get_effective_upgrade_ratio(
            self.alchemy_level, has_baiter
        )
        dn_ratio = AlchemyMechanics.get_effective_downgrade_ratio(
            self.alchemy_level, has_baiter
        )

        amounts: dict[tuple, int] = {}
        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            row = await self.bot.database.skills.get_data(
                self.user_id, self.server_id, skill
            )
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
                self._options_data.append(
                    {
                        "type": "upgrade",
                        "skill": skill,
                        "src_col": src_col,
                        "dst_col": dst_col,
                        "label": f"↑ {names[i]} → {names[i + 1]} ({skill.title()})",
                        "desc": f"{up_ratio}× {names[i]} → 1× {names[i + 1]} | have {src_amt} | {gold_cost:,}g each",
                        "gold_cost": gold_cost,
                        "ratio": up_ratio,
                    }
                )

        # Downgrades
        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            names = AlchemyMechanics.SKILL_TIER_NAMES[skill]
            for i in range(1, len(cols)):
                src_col = cols[i]
                dst_col = cols[i - 1]
                src_amt = amounts.get((skill, src_col), 0)
                src_tier_idx = i
                gold_cost = AlchemyMechanics.TRANSMUTE_DOWNGRADE_GOLD[src_tier_idx]
                self._options_data.append(
                    {
                        "type": "downgrade",
                        "skill": skill,
                        "src_col": src_col,
                        "dst_col": dst_col,
                        "label": f"↓ {names[i]} → {names[i - 1]} ({skill.title()})",
                        "desc": f"1× {names[i]} → {dn_ratio}× {names[i - 1]} | have {src_amt} | {gold_cost:,}g each",
                        "gold_cost": gold_cost,
                        "ratio": dn_ratio,
                    }
                )

        self.clear_items()
        self._select = _TransmuteSelect(self._options_data)
        self.add_item(self._select)

        confirm_btn = ui.Button(label="Transmute", style=ButtonStyle.green, emoji="✅")
        confirm_btn.callback = self._on_confirm
        self.add_item(confirm_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️")
        back_btn.callback = self._on_back
        self.add_item(back_btn)

        embed = discord.Embed(
            title="🔄 Transmute Resources", color=discord.Color.blurple()
        )
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
                "Please select a transmutation first.", ephemeral=True
            )
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
        super().__init__(
            placeholder="Choose a slot…", options=options, min_values=1, max_values=1
        )
        self.chosen_slot: int | None = None

    async def callback(self, interaction: Interaction):
        self.chosen_slot = int(self.values[0])
        await interaction.response.defer()


class _ClearConfirmView(BaseView):
    def __init__(self, parent: "AlchemyPotionLabView", slot: int):
        super().__init__(parent.bot, parent.user_id, parent.server_id)
        self._parent = parent
        self._slot = slot
        self._processing = False

    @ui.button(label="Yes, clear it", style=ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await self._parent.bot.database.alchemy.delete_passive(
            self._parent.user_id, self._slot
        )
        self._parent.passives = (
            await self._parent.bot.database.alchemy.get_potion_passives(
                self._parent.user_id
            )
        )

        embed = self._parent.build_embed()

        # Add result as a field (exactly like the Synthesis Complete field)
        embed.add_field(
            name="🗑️ Destruction Complete",
            value=f"**Slot {self._slot}** passive has been discarded.",
            inline=False,
        )

        self.stop()
        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=self._parent,  # clean — no top-level content
        )

    @ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="⬅️")
    async def cancel(self, interaction: Interaction, button: ui.Button):
        embed = self._parent.build_embed()
        self.stop()
        await interaction.response.edit_message(
            content=None, embed=embed, view=self._parent
        )


class _DistillGuideBackView(BaseView):
    """Temporary view for the Distillation Guide with a Back button that restores the lab."""

    def __init__(self, parent: "AlchemyPotionLabView"):
        super().__init__(parent.bot, parent.user_id, parent.server_id)
        self._parent = parent

    @ui.button(label="Back to Lab", style=ButtonStyle.secondary, emoji="⬅️")
    async def back(self, interaction: Interaction, button: ui.Button):
        embed = self._parent.build_embed()
        await interaction.response.edit_message(embed=embed, view=self._parent)


class _DistillPassivesView(BaseView):
    """Dedicated view to show the full list of powerful distillable passives without truncation or cluttering the lab."""

    def __init__(self, parent: "AlchemyPotionLabView"):
        super().__init__(parent.bot, parent.user_id, parent.server_id)
        self._parent = parent

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📜 Possible Distilled Passives",
            description=(
                "These are all the powerful, encounter-changing potion passives obtainable via Distillation.\n"
                "When you click **Distill Elixir**, three are randomly offered as the 'core' for that 9-step run. "
                "The reagents then tune its Duration Power and Value Power."
            ),
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(url=ALCHEMY_HUB)

        powerful = DistillationMechanics.POWERFUL_PASSIVES
        for k, v in powerful.items():
            desc = get_passive_list_desc(k)
            embed.add_field(
                name=f"{v.get('emoji', '⚗️')} **{v.get('name', k)}**",
                value=desc,
                inline=False,
            )
        return embed

    @ui.button(label="Back to Lab", style=ButtonStyle.secondary, emoji="⬅️")
    async def back(self, interaction: Interaction, button: ui.Button):
        embed = self._parent.build_embed()
        await interaction.response.edit_message(embed=embed, view=self._parent)


class AlchemyPotionLabView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        alchemy_level: int,
        passives: list,
        spirit_stones: int,
        free_roll_used: bool = False,
    ):
        super().__init__(bot, user_id, server_id)
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

        # Distill powerful passives (the main system now)
        distill_btn = ui.Button(
            label="Distill Elixir", style=ButtonStyle.primary, emoji="🧪", row=1
        )
        distill_btn.callback = self._on_distill
        self.add_item(distill_btn)

        # Tutorial/guide next to Distill Elixir
        guide_btn = ui.Button(
            label="📖 Guide", style=ButtonStyle.secondary, emoji="ℹ️", row=1
        )
        guide_btn.callback = self._on_distill_guide
        self.add_item(guide_btn)

        # Full catalog of powerful passives (moved out of the main embed to avoid clutter and cutoff)
        passives_btn = ui.Button(
            label="📜 Passives", style=ButtonStyle.secondary, emoji="📜", row=1
        )
        passives_btn.callback = self._on_view_passives
        self.add_item(passives_btn)

        clear_btn = ui.Button(
            label="Destroy", style=ButtonStyle.danger, emoji="🗑️", row=1
        )
        clear_btn.callback = self._on_clear
        self.add_item(clear_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def _set_buttons_disabled(self, disabled: bool):
        """Temporarily disable or re-enable all interactive components."""
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = disabled

    def _get_random_flavor(self) -> str:
        """Random flavor text for the brewing animation."""
        flavors = [
            "Brewing potion...",
            "Tinkering with ratios...",
            "Infusing mystical essence...",
            "Distilling alchemical power...",
            "Channeling arcane energies...",
            "Mixing volatile reagents...",
            "Heating the cauldron...",
            "Alchemizing the arcane...",
        ]
        return random.choice(flavors)

    def _slot_is_empty(self, slot: int) -> bool:
        """Return True if the given slot has no passive assigned."""
        passive_by_slot = {p["slot"]: p for p in self.passives}
        return slot not in passive_by_slot

    def build_embed(self) -> discord.Embed:
        slot_count = AlchemyMechanics.get_slot_count(self.alchemy_level)
        embed = discord.Embed(title="⚗️ Potion Lab", color=discord.Color.green())

        embed.description = (
            f"**Level:** {self.alchemy_level} | **Spirit Stones:** 🔮 {self.spirit_stones}\n\n"
            "Select a slot to destroy, or click **Distill Elixir** to craft a powerful passive (assigned to an empty slot). "
            "Click **📖 Guide** for the 9-step system rules. Click **📜 Passives** to browse every possible distilled core and its ranges."
        )

        passive_by_slot = {p["slot"]: p for p in self.passives}
        lines = []
        for s in range(1, slot_count + 1):
            if s in passive_by_slot:
                p = passive_by_slot[s]
                name, emoji = get_passive_name_emoji(p["passive_type"])
                desc = AlchemyMechanics.format_passive(
                    p["passive_type"], p["passive_value"]
                )
                lines.append(f"**[{s}]** {emoji} {name}: *{desc}*")
            else:
                lines.append(f"**[{s}]** *Empty slot*")

        embed.add_field(
            name="Current Passives",
            value="\n".join(lines) if lines else "None",
            inline=False,
        )

        # The full list of possible distilled passives has been moved to its own button ("📜 Passives")
        # so it doesn't clutter the main lab screen and avoids truncation.
        return embed

    async def _on_distill(self, interaction: Interaction):
        """Launch (or resume) the new 9-step powerful distillation system."""
        await interaction.response.defer()
        from core.alchemy.distillation_views import start_distillation

        await start_distillation(self.bot, self.user_id, self.server_id, interaction)

    async def _on_distill_guide(self, interaction: Interaction):
        """Show a quick guide for the Distillation system next to the button."""
        await interaction.response.defer()

        guide_embed = discord.Embed(
            title="📖 Distillation Guide",
            description=(
                "Craft **powerful potion passives** over 9 steps using Cosmic Dust.\n\n"
                "**1. Choose Core (the 'skill'):** The three options show a brief description + the possible roll ranges (value & duration) for that powerful passive. "
                "This core stays fixed for the entire run.\n\n"
                "**2-9. Reagent steps:** At each step the three colored reagents are assigned fresh special properties drawn from a wide weighted pool (middle outcomes common, very powerful effects rare).\n"
                'The properties are **displayed in the embed** so you can see what each choice does before picking (e.g. "This step costs no dust", "double dust + slightly lucky", "will not decrease...", "all future steps free", "very lucky", etc.).\n\n'
                "Buttons show your dust balance after the choice: e.g. (68->60). You cannot select a reagent whose cost would take you below 0 dust.\n\n"
                "In the background each step resolves to: nothing / duration inc or dec / power inc or dec. The chosen property controls the roll (slightly lucky = double-roll good results and take the better; very lucky = re-roll on bad outcomes and take best-of; safe = no decreases this step, etc.).\n\n"
                "**Reagents (by their nature — no extra guide needed in the distil screen):**\n"
                "🟢 Verdant — calm and reliable, tends toward consistent Value Power gains.\n"
                "🔵 Astral — middling / balanced.\n"
                "🔴 Crimson — risky and volatile, bigger swings, more dramatic (and occasionally costly) events.\n\n"
                "Track **Duration Power** and **Value Power** accumulators (the live passive preview updates with your current power). At the end you receive a far stronger encounter-changing passive than the old system."
            ),
            color=discord.Color.purple(),
        )
        guide_embed.set_thumbnail(url=ALCHEMY_HUB)

        back_view = _DistillGuideBackView(self)
        await interaction.edit_original_response(embed=guide_embed, view=back_view)

    async def _on_view_passives(self, interaction: Interaction):
        """Show the full catalog of powerful passives in its own view (no more inline list in the lab)."""
        await interaction.response.defer()
        view = _DistillPassivesView(self)
        embed = view.build_embed()
        await interaction.edit_original_response(embed=embed, view=view)

    async def _on_clear(self, interaction: Interaction):
        slot = self._slot_select.chosen_slot if self._slot_select else None
        if slot is None:
            await interaction.response.send_message(
                "Please select a slot first.", ephemeral=True
            )
            return

        if self._slot_is_empty(slot):
            await interaction.response.send_message(
                f"Slot **{slot}** is already empty.", ephemeral=True
            )
            return

        passive_by_slot = {p["slot"]: p for p in self.passives}
        p = passive_by_slot[slot]
        name, emoji = get_passive_name_emoji(p["passive_type"])

        confirm_view = _ClearConfirmView(self, slot)
        embed = discord.Embed(
            title="🗑️ Clear Passive?",
            description=(
                f"Are you sure you want to clear **Slot {slot}**?\n\n"
                f"Current passive: {emoji} **{name}**"
            ),
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(
            content=None, embed=embed, view=confirm_view
        )

    async def _on_back(self, interaction: Interaction):
        await interaction.response.defer()
        view = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()
