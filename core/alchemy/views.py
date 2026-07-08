import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.alchemy.mechanics import (
    AlchemyMechanics,
    DistillationMechanics,
    get_passive_list_desc,
    get_passive_name_emoji,
)
from core.base_view import BaseView
from core.emojis import COSMIC_DUST, GOLD_COIN, RESOURCE_EMOJI, SPIRIT_STONE
from core.images import ELYNDRA_PORTRAIT, ELYNDRA_THUMBNAIL
from core.npc_voices import get_quip
from core.skills.mastery import get_attunement_alchemy_bonus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _hub_from_db(bot, user_id: str, server_id: str) -> "AlchemyHubView":
    """Re-fetches all alchemy data from the DB and returns a fresh hub view."""
    user_row = await bot.database.users.get(user_id, server_id)
    gold = user_row["gold"] if user_row else 0
    spirit_stones = await bot.database.users.get_currency(user_id, "spirit_stones")
    cosmic_dust = await bot.database.alchemy.get_cosmic_dust(user_id)
    alchemy_level = await bot.database.alchemy.get_level(user_id)
    passives = await bot.database.alchemy.get_potion_passives(user_id)
    return AlchemyHubView(
        bot,
        user_id,
        server_id,
        alchemy_level,
        passives,
        gold,
        spirit_stones,
        cosmic_dust,
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
        cosmic_dust: int = 0,
    ):
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.passives = passives
        self.player_gold = player_gold
        self.spirit_stones = spirit_stones
        self.cosmic_dust = cosmic_dust
        self._processing = False
        if alchemy_level >= AlchemyMechanics.MAX_LEVEL:
            # Remove Level Up button at max level
            self.remove_item(self.level_up)

    def build_embed(self) -> discord.Embed:
        slot_count = AlchemyMechanics.get_slot_count(self.alchemy_level)
        level_cost = AlchemyMechanics.get_level_up_cost(self.alchemy_level)

        embed = discord.Embed(title="⚗️ Alchemy", color=discord.Color.purple())
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)
        embed.set_footer(text=get_quip("alchemy"))
        info = [
            f"**Level:** {self.alchemy_level} / {AlchemyMechanics.MAX_LEVEL}",
            f"**Spirit Stones:** {SPIRIT_STONE} {self.spirit_stones}",
            f"**Cosmic Dust:** {COSMIC_DUST} {self.cosmic_dust:,}",
            f"**Gold:** {GOLD_COIN} {self.player_gold:,}",
            f"**Passive Slots:** {slot_count} unlocked",
        ]
        if level_cost is not None:
            info.append(f"**Next Level Cost:** {SPIRIT_STONE} {level_cost} Spirit Stones")
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
                        p["passive_type"],
                        p["passive_value"],
                        p.get("passive_duration", 2.0),
                    )
                    lines.append(f"**[{s}]** {emoji} **{name}** {desc}")
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
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        from core.alchemy.synthesis_views import _build_synthesis_hub

        await interaction.response.defer()
        view = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Transmute", style=ButtonStyle.blurple, emoji="🔄", row=0)
    async def transmute(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
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
            cosmic_dust=self.cosmic_dust,
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
                f"Not enough Spirit Stones! Need {SPIRIT_STONE} **{cost}**, have **{self.spirit_stones}**.",
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
                f"*You're ready to push this further. Good.*\n\n"
                f"Upgrade from **Level {self.alchemy_level}** → **Level {new_level}**\n\n"
                f"Cost: {SPIRIT_STONE} **{cost}** Spirit Stones\n"
                f"New slot count: **{AlchemyMechanics.get_slot_count(new_level)}**\n"
                f"New transmutation ratio: **{up_r}:1** upgrade / **1:{dn_r}** downgrade\n\n"
                f"✨ The new slot will be ready for a free Distillation in the Potion Lab."
            ),
            color=discord.Color.gold(),
        )
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = interaction.message
        self.stop()

    @ui.button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=0)
    async def close(self, interaction: Interaction, button: ui.Button):
        # session-terminating Close for alchemy hub
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()


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
                f"Not enough Spirit Stones! Need {SPIRIT_STONE} {self.cost}, have {current_stones}.",
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
        current_gold = user_row["gold"] if user_row else 0
        total_gold = gold_cost_each * qty
        if current_gold < total_gold:
            max_by_gold = current_gold // gold_cost_each
            await interaction.response.send_message(
                f"Not enough gold for **{qty}** operations (need {GOLD_COIN} {total_gold:,}). "
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
                f"✅ Transmuted **{ratio * qty}×** {opt['src_name']} → **{dst_delta}×** {opt['dst_name']}!{bonus_text} "
                f"(-{GOLD_COIN} {total_gold:,})",
                ephemeral=True,
            )

        else:  # downgrade
            src_amt = await self._view.bot.database.alchemy.get_resource_amount(
                self._view.user_id, self._view.server_id, opt["skill"], opt["src_col"]
            )
            if src_amt < qty:
                await interaction.response.send_message(
                    f"Not enough **{opt['src_name']}** for **{qty}** operations "
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
                f"✅ Broke down **{qty}×** {opt['src_name']} → **{ratio * qty}×** {opt['dst_name']}! "
                f"(-{GOLD_COIN} {total_gold:,})",
                ephemeral=True,
            )


class _TransmuteSelect(ui.Select):
    def __init__(self, options_data: list):
        options = [
            discord.SelectOption(
                label=opt["label"][:100],
                description=opt["desc"][:100],
                value=str(i),
                emoji=RESOURCE_EMOJI.get(opt["src_col"]),
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
        self._mode: str = "raw"  # "raw" | "settlement"
        self._raw_direction: str = "upgrade"  # "upgrade" | "downgrade"
        self._settlement_direction: str = "upgrade"  # "upgrade" | "downgrade"

    async def _switch_mode(self, interaction: Interaction, mode: str) -> None:
        self._mode = mode
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _toggle_raw_direction(self, interaction: Interaction) -> None:
        self._raw_direction = (
            "downgrade" if self._raw_direction == "upgrade" else "upgrade"
        )
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _toggle_settlement_direction(self, interaction: Interaction) -> None:
        self._settlement_direction = (
            "downgrade" if self._settlement_direction == "upgrade" else "upgrade"
        )
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def build_embed(self) -> discord.Embed:
        self.clear_items()

        # --- Mode toggle buttons (row 0) ---
        raw_btn = ui.Button(
            label="Raw Resources",
            style=ButtonStyle.primary if self._mode == "raw" else ButtonStyle.secondary,
            emoji="⛏️",
            row=0,
        )
        raw_btn.callback = lambda i: self._switch_mode(i, "raw")
        self.add_item(raw_btn)

        sett_btn = ui.Button(
            label="Settlement Resources",
            style=(
                ButtonStyle.primary
                if self._mode == "settlement"
                else ButtonStyle.secondary
            ),
            emoji="🏗️",
            row=0,
        )
        sett_btn.callback = lambda i: self._switch_mode(i, "settlement")
        self.add_item(sett_btn)

        embed = discord.Embed(
            title="🔄 Transmute Resources", color=discord.Color.blurple()
        )
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)
        embed.set_footer(text=get_quip("alchemy"))

        if self._mode == "settlement":
            embed = await self._build_settlement_embed(embed)
            dir_btn = ui.Button(
                label=(
                    "Show Downgrades"
                    if self._settlement_direction == "upgrade"
                    else "Show Upgrades"
                ),
                style=ButtonStyle.secondary,
                emoji="🔃",
                row=2,
            )
            dir_btn.callback = self._toggle_settlement_direction
            self.add_item(dir_btn)
        else:
            embed = await self._build_raw_embed(embed)
            dir_btn = ui.Button(
                label=(
                    "Show Downgrades"
                    if self._raw_direction == "upgrade"
                    else "Show Upgrades"
                ),
                style=ButtonStyle.secondary,
                emoji="🔃",
                row=2,
            )
            dir_btn.callback = self._toggle_raw_direction
            self.add_item(dir_btn)

        confirm_btn = ui.Button(
            label="Transmute", style=ButtonStyle.green, emoji="✅", row=2
        )
        confirm_btn.callback = self._on_confirm
        self.add_item(confirm_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=2
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

        return embed

    async def _build_raw_embed(self, embed: discord.Embed) -> discord.Embed:
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

        for skill, cols in AlchemyMechanics.SKILL_TIERS.items():
            names = AlchemyMechanics.SKILL_TIER_NAMES[skill]
            if self._raw_direction == "upgrade":
                for i in range(len(cols) - 1):
                    src_col, dst_col = cols[i], cols[i + 1]
                    src_amt = amounts.get((skill, src_col), 0)
                    gold_cost = AlchemyMechanics.TRANSMUTE_UPGRADE_GOLD[i + 1]
                    self._options_data.append(
                        {
                            "type": "upgrade",
                            "skill": skill,
                            "src_col": src_col,
                            "dst_col": dst_col,
                            "src_name": names[i],
                            "dst_name": names[i + 1],
                            "label": f"↑ {names[i]} → {names[i + 1]} ({skill.title()})",
                            "desc": f"{up_ratio}× {names[i]} → 1× {names[i + 1]} | have {src_amt} | {gold_cost:,}g each",
                            "gold_cost": gold_cost,
                            "ratio": up_ratio,
                        }
                    )
            else:
                for i in range(1, len(cols)):
                    src_col, dst_col = cols[i], cols[i - 1]
                    src_amt = amounts.get((skill, src_col), 0)
                    gold_cost = AlchemyMechanics.TRANSMUTE_DOWNGRADE_GOLD[i]
                    self._options_data.append(
                        {
                            "type": "downgrade",
                            "skill": skill,
                            "src_col": src_col,
                            "dst_col": dst_col,
                            "src_name": names[i],
                            "dst_name": names[i - 1],
                            "label": f"↓ {names[i]} → {names[i - 1]} ({skill.title()})",
                            "desc": f"1× {names[i]} → {dn_ratio}× {names[i - 1]} | have {src_amt} | {gold_cost:,}g each",
                            "gold_cost": gold_cost,
                            "ratio": dn_ratio,
                        }
                    )

        self._select = _TransmuteSelect(self._options_data)
        self._select.row = 1
        self.add_item(self._select)

        if self._raw_direction == "upgrade":
            embed.description = (
                f"Upgrade raw gathering resources to the next tier.\n"
                f"**Ratio:** {up_ratio}:1 | **Gold:** {GOLD_COIN} {self.player_gold:,}\n\n"
                "Select a conversion, then press **Transmute** to enter a quantity."
            )
        else:
            embed.description = (
                f"Break down raw gathering resources into a lower tier.\n"
                f"**Ratio:** 1:{dn_ratio} | **Gold:** {GOLD_COIN} {self.player_gold:,}\n\n"
                "Select a conversion, then press **Transmute** to enter a quantity."
            )
        return embed

    async def _build_settlement_embed(self, embed: discord.Embed) -> discord.Embed:
        """Processed resources tab — upgrade or downgrade processed tiers (bar/plank/essence)."""
        _PROC_TIERS: dict[str, list[tuple[str, str]]] = {
            "mining": [
                ("iron_bar", "Iron Bar"),
                ("steel_bar", "Steel Bar"),
                ("gold_bar", "Gold Bar"),
                ("platinum_bar", "Platinum Bar"),
                ("idea_bar", "Idea Bar"),
            ],
            "woodcutting": [
                ("oak_plank", "Oak Plank"),
                ("willow_plank", "Willow Plank"),
                ("mahogany_plank", "Mahogany Plank"),
                ("magic_plank", "Magic Plank"),
                ("idea_plank", "Idea Plank"),
            ],
            "fishing": [
                ("desiccated_essence", "Desd. Essence"),
                ("regular_essence", "Reg. Essence"),
                ("sturdy_essence", "Sturdy Essence"),
                ("reinforced_essence", "Reinf. Essence"),
                ("titanium_essence", "Titan. Essence"),
            ],
        }

        # Fetch processed amounts
        proc_amounts: dict[tuple[str, str], int] = {}
        for skill, tiers in _PROC_TIERS.items():
            proc_cols = [col for col, _ in tiers]
            row = await self.bot.database.skills.get_multi_resource(
                self.user_id, self.server_id, skill, proc_cols
            )
            for i, col in enumerate(proc_cols):
                proc_amounts[(skill, col)] = row[i] if row else 0

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

        going_up = self._settlement_direction == "upgrade"
        self._options_data = []

        if going_up:
            for skill, tiers in _PROC_TIERS.items():
                skill_label = skill.title()
                for i in range(len(tiers) - 1):
                    src_col, src_name = tiers[i]
                    dst_col, dst_name = tiers[i + 1]
                    src_amt = proc_amounts.get((skill, src_col), 0)
                    gold_cost = AlchemyMechanics.TRANSMUTE_UPGRADE_GOLD.get(
                        i + 1, 7_500
                    )
                    self._options_data.append(
                        {
                            "type": "upgrade",
                            "skill": skill,
                            "src_col": src_col,
                            "dst_col": dst_col,
                            "src_name": src_name,
                            "dst_name": dst_name,
                            "label": f"↑ {src_name} → {dst_name} ({skill_label})",
                            "desc": f"{up_ratio}:1 | have {src_amt:,} {src_name} | {gold_cost:,}g",
                            "gold_cost": gold_cost,
                            "ratio": up_ratio,
                        }
                    )
        else:
            for skill, tiers in _PROC_TIERS.items():
                skill_label = skill.title()
                for i in range(len(tiers) - 1, 0, -1):
                    src_col, src_name = tiers[i]
                    dst_col, dst_name = tiers[i - 1]
                    src_amt = proc_amounts.get((skill, src_col), 0)
                    gold_cost = AlchemyMechanics.TRANSMUTE_DOWNGRADE_GOLD.get(i, 50)
                    self._options_data.append(
                        {
                            "type": "downgrade",
                            "skill": skill,
                            "src_col": src_col,
                            "dst_col": dst_col,
                            "src_name": src_name,
                            "dst_name": dst_name,
                            "label": f"↓ {src_name} → {dst_name} ({skill_label})",
                            "desc": f"1× {src_name} → {dn_ratio}× {dst_name} | have {src_amt:,} | {gold_cost:,}g",
                            "gold_cost": gold_cost,
                            "ratio": dn_ratio,
                        }
                    )

        self._select = _TransmuteSelect(self._options_data)
        self._select.row = 1
        self.add_item(self._select)

        if going_up:
            embed.description = (
                f"Upgrade processed resources to a higher tier (e.g. Iron Bar → Steel Bar).\n"
                f"**Ratio:** {up_ratio}:1 | **Gold:** {GOLD_COIN} {self.player_gold:,}\n\n"
                "Select a conversion, then press **Transmute** to enter a quantity."
            )
        else:
            embed.description = (
                f"Break down processed resources to a lower tier (e.g. Steel Bar → Iron Bar).\n"
                f"**Ratio:** 1:{dn_ratio} | **Gold:** {GOLD_COIN} {self.player_gold:,}\n\n"
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
    def __init__(self, slot_count: int, parent_view: "AlchemyPotionLabView"):
        options = [
            discord.SelectOption(label=f"Slot {s}", value=str(s), default=(s == 1))
            for s in range(1, slot_count + 1)
        ]
        super().__init__(
            placeholder="Slot 1 selected", options=options, min_values=1, max_values=1
        )
        self.chosen_slot: int = 1  # slot 1 pre-selected by default
        self._parent_view = parent_view

    async def callback(self, interaction: Interaction):
        self.chosen_slot = int(self.values[0])
        # Update the default marker in the dropdown to match the new selection
        for opt in self.options:
            opt.default = opt.value == self.values[0]
        self.placeholder = f"Slot {self.chosen_slot} selected"
        await interaction.response.edit_message(
            embed=self._parent_view.build_embed(), view=self._parent_view
        )


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
                "When you click **Distill Elixir**, three are randomly offered as the 'core' for the run. "
                "The reagents then tune its Duration Power and Value Power."
            ),
            color=discord.Color.purple(),
        )
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)

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
        cosmic_dust: int = 0,
        free_roll_used: bool = False,
    ):
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.passives = passives
        self.spirit_stones = spirit_stones
        self.cosmic_dust = cosmic_dust
        self.free_roll_used = free_roll_used
        self.message = None
        self._slot_select: _SlotSelect | None = None

        slot_count = AlchemyMechanics.get_slot_count(alchemy_level)
        if slot_count > 0:
            self._slot_select = _SlotSelect(slot_count, self)
            self.add_item(self._slot_select)

        # Distill — slot 1 is pre-selected so this is ready immediately
        self._distill_btn = ui.Button(
            label="Distill Elixir",
            style=ButtonStyle.primary,
            emoji="🧪",
            row=1,
            disabled=(slot_count == 0),
        )
        self._distill_btn.callback = self._on_distill
        self.add_item(self._distill_btn)

        # Tutorial/guide next to Distill Elixir
        guide_btn = ui.Button(
            label="Guide", style=ButtonStyle.secondary, emoji="📖", row=1
        )
        guide_btn.callback = self._on_distill_guide
        self.add_item(guide_btn)

        # Full catalog of powerful passives
        passives_btn = ui.Button(
            label="Passives", style=ButtonStyle.secondary, emoji="📜", row=1
        )
        passives_btn.callback = self._on_view_passives
        self.add_item(passives_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=2
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

        # Destroy — slot 1 pre-selected so enabled immediately (if slots exist)
        self._clear_btn = ui.Button(
            label="Destroy",
            style=ButtonStyle.danger,
            emoji="🗑️",
            row=2,
            disabled=(slot_count == 0),
        )
        self._clear_btn.callback = self._on_clear
        self.add_item(self._clear_btn)

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
        chosen = self._slot_select.chosen_slot if self._slot_select else 1

        embed = discord.Embed(title="⚗️ Potion Lab", color=discord.Color.green())
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)
        embed.set_footer(text=get_quip("alchemy"))

        embed.description = (
            f"**Level:** {self.alchemy_level} | **Spirit Stones:** {SPIRIT_STONE} {self.spirit_stones} | **Cosmic Dust:** {COSMIC_DUST} {self.cosmic_dust:,}\n\n"
            f"**Distill Elixir** ({SPIRIT_STONE} 1 Spirit Stone) crafts a powerful passive into the selected slot. "
            "Click **Guide** for distillation rules, or **Passives** to browse all possible cores.\n"
            "*If the selected slot already has a passive, you'll be offered a choice to keep the old one or take the new one after distillation completes.*"
        )

        passive_by_slot = {p["slot"]: p for p in self.passives}
        lines = []
        for s in range(1, slot_count + 1):
            arrow = "▶ " if s == chosen else "    "
            if s in passive_by_slot:
                p = passive_by_slot[s]
                name, emoji = get_passive_name_emoji(p["passive_type"])
                desc = AlchemyMechanics.format_passive(
                    p["passive_type"],
                    p["passive_value"],
                    p.get("passive_duration", 2.0),
                )
                lines.append(f"{arrow}**[{s}]** {emoji} **{name}** {desc}")
            else:
                lines.append(f"{arrow}**[{s}]** *Empty slot*")

        embed.add_field(
            name="Potion Passives",
            value="\n".join(lines) if lines else "None",
            inline=False,
        )

        return embed

    async def _on_distill(self, interaction: Interaction):
        """Launch (or resume) the new 9-step powerful distillation system."""
        # Check for an existing in-progress session before charging.
        existing = await self.bot.database.alchemy.get_distillation(
            self.user_id, self.server_id
        )
        if not existing:
            # New run — costs 1 Spirit Stone.
            current_stones = await self.bot.database.users.get_currency(
                self.user_id, "spirit_stones"
            )
            if current_stones < 1:
                await interaction.response.send_message(
                    f"You need {SPIRIT_STONE} **1 Spirit Stone** to begin a Distillation.",
                    ephemeral=True,
                )
                return
            current_dust = await self.bot.database.alchemy.get_cosmic_dust(self.user_id)
            if current_dust < 200:
                await interaction.response.send_message(
                    f"⚠️ You only have **{current_dust:,} Cosmic Dust** — you'll likely be unable to complete "
                    f"the Distillation process (200+ recommended). Return with more dust before starting.",
                    ephemeral=True,
                )
                return
            await self.bot.database.users.modify_currency(
                self.user_id, "spirit_stones", -1
            )
            self.spirit_stones = max(0, self.spirit_stones - 1)

        await interaction.response.defer()
        from core.alchemy.distillation_views import start_distillation

        # Pass the player's existing passive types so the core-choice pool excludes them.
        excluded = [p["passive_type"] for p in self.passives]
        chosen_slot = self._slot_select.chosen_slot if self._slot_select else None
        await start_distillation(
            self.bot,
            self.user_id,
            self.server_id,
            interaction,
            excluded,
            target_slot=chosen_slot,
        )

    async def _on_distill_guide(self, interaction: Interaction):
        """Show a quick guide for the Distillation system next to the button."""
        await interaction.response.defer()

        guide_embed = discord.Embed(
            title="📖 Distillation — Elyndra's Notes",
            description=(
                "*You want to understand the process before committing? Sensible. Most don't bother. "
                "They poison themselves.*\n\n"
                "Distillation combines the arcane and science to produce"
                " powerful potion passives. "
                "Choose your core wisely — it cannot be changed once the process begins.\n\n"
                "**Step 1 — Choose a Core:**\n"
                "Three passives are offered. Each shows its possible value and duration ranges. "
                "This is the passive you will receive. Everything after this point merely determines "
                "*how powerful* that passive becomes. Do not rush.\n\n"
                "**Steps 2–9 — Reagent Selection:**\n"
                "At each step, three reagents appear — each bearing a special property. "
                "Each step bears a dust cost: "
                "You cannot select what you cannot afford. "
                "After selection, your **Value Power** or **Duration Power** might change.\n\n"
                "**Reagent Temperament:**\n"
                "🟢 **Verdant** — measured, steady. Consistent gains or losses.\n"
                "🔵 **Astral** — balanced. Neither spectacular nor catastrophic.\n"
                "🔴 **Crimson** — volatile. Large swings either way. "
            ),
            color=discord.Color.purple(),
        )
        guide_embed.set_author(
            name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT
        )
        guide_embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)

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
