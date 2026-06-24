"""
Paradise Jewel system UI.
Entry point: ParadiseHubView (opened from /paradise cog command).
"""

from __future__ import annotations

import asyncio
from typing import Optional

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import SKILL_IMAGES, SKILL_UNCUT, TESSARA_PORTRAIT
from core.npc_voices import get_quip
from core.paradise import mechanics as M
from core.paradise.data import (
    DUST_REROLL_TYPE,
    DUST_REROLL_VALUE,
    PASSIVE_SLOT_THRESHOLDS,
    PASSIVES,
    SKILL_JEWELS,
)

# ---------------------------------------------------------------------------
# Re-fetch helpers
# ---------------------------------------------------------------------------


async def _reload_hub(bot, user_id: str, server_id: str) -> "ParadiseHubView":
    data = await bot.database.paradise.get(user_id)
    uber = await bot.database.uber.get_uber_progress(user_id, server_id)
    jewel_count = uber.get("paradise_jewels", 0)
    dust = await bot.database.alchemy.get_cosmic_dust(user_id)
    return ParadiseHubView(bot, user_id, server_id, data, jewel_count, dust)


async def _fetch_passives_data(
    bot, user_id: str, server_id: str
) -> tuple[dict, int, int]:
    data = await bot.database.paradise.get(user_id)
    uber = await bot.database.uber.get_uber_progress(user_id, server_id)
    jewel_count = uber.get("paradise_jewels", 0)
    dust = await bot.database.alchemy.get_cosmic_dust(user_id)
    return data, jewel_count, dust


async def _fetch_skills_data(bot, user_id: str, server_id: str) -> tuple[dict, int]:
    data = await bot.database.paradise.get(user_id)
    uber = await bot.database.uber.get_uber_progress(user_id, server_id)
    jewel_count = uber.get("paradise_jewels", 0)
    return data, jewel_count


# ---------------------------------------------------------------------------
# Embed builders
# ---------------------------------------------------------------------------


def _skill_card_lines(data: dict, skill_key: str) -> list[str]:
    """Returns embed field lines for a skill (no charges, just threshold)."""
    defn = SKILL_JEWELS[skill_key]
    mastery = M.mastery_bonus(data)
    eff_level = M.get_effective_level(skill_key, data, mastery)
    compression = M.get_compression_bonus(data)
    threshold = max(1, M.get_threshold(skill_key, eff_level) - compression)
    natural_level = data["skill_levels"].get(skill_key, 1)

    level_display = f"Lv {natural_level}"
    if mastery > 0:
        level_display += f" (+{mastery} Mastery → Lv {eff_level} effective)"
    next_combats = M.combats_to_next_level(natural_level)
    level_display += (
        f"  *(~{next_combats:.0f} combats to next level)*"
        if next_combats
        else "  *(MAX)*"
    )

    return [
        f"{defn.emoji} **{defn.name}** — {level_display}",
        f"**Charge Threshold:** {threshold}",
        f"*{defn.charge_trigger}*",
        f"**Unleash:** {M.format_unleash_description(skill_key, eff_level)}",
    ]


def _build_hub_embed(data: dict, jewel_count: int, dust: int) -> discord.Embed:
    embed = discord.Embed(
        title="💎 Jewel of Paradise", color=discord.Color.from_str("#b967ff")
    )
    embed.set_author(name="Tessara", icon_url=TESSARA_PORTRAIT)
    embed.set_footer(text=get_quip("paradise"))

    obtained = data.get("total_jewels_obtained", 0)
    consumed = data.get("total_jewels_consumed", 0)
    embed.description = (
        f"**Uncut Jewels:** 💎 {jewel_count}\n"
        f"**Cosmic Dust:** ✨ {dust:,}\n"
        f"**Jewels Obtained:** {obtained}  •  **Cut:** {consumed}"
    )

    equipped = data.get("equipped_skill")
    unlocked = data.get("unlocked_skills", [])

    if equipped and equipped in SKILL_JEWELS:
        embed.set_thumbnail(url=SKILL_IMAGES.get(equipped, SKILL_UNCUT))
        embed.add_field(
            name="⚔️ Equipped Skill",
            value="\n".join(_skill_card_lines(data, equipped)),
            inline=False,
        )
    elif unlocked:
        embed.set_thumbnail(url=SKILL_UNCUT)
        embed.add_field(
            name="⚔️ Equipped Skill",
            value="*No skill equipped — use Manage Skills to select one.*",
            inline=False,
        )
    else:
        embed.set_thumbnail(url=SKILL_UNCUT)
        embed.add_field(
            name="⚔️ Equipped Skill",
            value="*No skills unlocked yet.*\nCut a Jewel of Paradise to unlock your first skill.",
            inline=False,
        )

    if unlocked:
        rows = []
        for sk in unlocked:
            defn = SKILL_JEWELS.get(sk)
            if not defn:
                continue
            lvl = data["skill_levels"].get(sk, 1)
            marker = " ◀" if sk == equipped else ""
            rows.append(f"{defn.emoji} **{defn.name}** Lv {lvl}{marker}")
        embed.add_field(
            name=f"📖 Unlocked Skills ({len(unlocked)}/{len(SKILL_JEWELS)})",
            value="\n".join(rows),
            inline=True,
        )

    slot_count = M.get_passive_slot_count(data)
    passive_slots = data.get("passive_slots", [])
    if slot_count > 0:
        lines = [
            (
                f"**[{i + 1}]** {M.format_passive_slot(passive_slots[i])}"
                if i < len(passive_slots)
                else f"**[{i + 1}]** *Empty*"
            )
            for i in range(slot_count)
        ]
        embed.add_field(name="🔮 Passive Slots", value="\n".join(lines), inline=True)
    else:
        needed = M.jewels_to_next_slot(data)
        embed.add_field(
            name="🔮 Passive Slots",
            value=f"*No passive slots unlocked.*\n{needed} jewel(s) needed for Slot 1.",
            inline=True,
        )

    invested = data.get("passive_jewels_invested", 0)
    needed_next = M.jewels_to_next_slot(data)
    if needed_next and slot_count < 5:
        thres = PASSIVE_SLOT_THRESHOLDS[slot_count]
        footer = f"Passive Slot {slot_count + 1}: {invested}/{thres} jewels cut  •  Reroll Type: {DUST_REROLL_TYPE:,} dust  •  Reroll Value: {DUST_REROLL_VALUE:,} dust"
    else:
        footer = f"All 5 passive slots unlocked  •  Reroll Type: {DUST_REROLL_TYPE:,} dust  •  Reroll Value: {DUST_REROLL_VALUE:,} dust"
    embed.set_footer(text=footer)
    return embed


def _build_manage_skills_embed(data: dict) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Manage Skills", color=discord.Color.from_str("#b967ff")
    )
    equipped = data.get("equipped_skill")
    unlocked = data.get("unlocked_skills", [])

    if equipped and equipped in SKILL_JEWELS:
        embed.set_thumbnail(url=SKILL_IMAGES.get(equipped, SKILL_UNCUT))
        embed.add_field(
            name="Equipped Skill",
            value="\n".join(_skill_card_lines(data, equipped)),
            inline=False,
        )
    else:
        embed.set_thumbnail(url=SKILL_UNCUT)
        embed.add_field(
            name="Equipped Skill",
            value="*No skill equipped.*" if unlocked else "*No skills unlocked yet.*",
            inline=False,
        )

    if unlocked:
        rows = []
        for sk in unlocked:
            defn = SKILL_JEWELS.get(sk)
            if not defn:
                continue
            lvl = data["skill_levels"].get(sk, 1)
            marker = " ◀" if sk == equipped else ""
            rows.append(f"{defn.emoji} **{defn.name}** Lv {lvl}{marker}")
        embed.add_field(
            name=f"📖 Unlocked Skills ({len(unlocked)}/{len(SKILL_JEWELS)})",
            value="\n".join(rows),
            inline=False,
        )
        embed.description = "Select a skill below to equip it."
    else:
        embed.description = (
            "No skills unlocked yet. Cut a Jewel to unlock your first skill."
        )

    return embed


def _build_manage_passives_embed(data: dict, dust: int) -> discord.Embed:
    embed = discord.Embed(title="🔮 Manage Passives", color=discord.Color.blurple())
    slot_count = M.get_passive_slot_count(data)
    passive_slots = data.get("passive_slots", [])

    lines = [
        f"**Cosmic Dust:** ✨ {dust:,}",
        f"**Reroll Type** — {DUST_REROLL_TYPE:,} dust (new passive type + new value)",
        f"**Reroll Value** — {DUST_REROLL_VALUE:,} dust (same type, new value)",
        "",
    ]

    if slot_count > 0:
        for i in range(slot_count):
            if i < len(passive_slots):
                desc = M.format_passive_description(passive_slots[i])
                lines.append(f"**Slot {i + 1}:** {desc}")
            else:
                lines.append(f"**Slot {i + 1}:** *Empty*")
    else:
        lines.append("*No passive slots unlocked yet.*")

    embed.description = "\n".join(lines)

    invested = data.get("passive_jewels_invested", 0)
    needed_next = M.jewels_to_next_slot(data)
    if needed_next and slot_count < 5:
        thres = PASSIVE_SLOT_THRESHOLDS[slot_count]
        embed.set_footer(
            text=f"Passive Slot {slot_count + 1}: {invested}/{thres} jewels cut"
        )
    else:
        embed.set_footer(text="All 5 passive slots unlocked")
    return embed


def _build_reroll_embed(
    data: dict, slot_idx: int, dust: int, result_msg: str = ""
) -> discord.Embed:
    slots = data.get("passive_slots", [])
    slot = slots[slot_idx] if slot_idx < len(slots) else None
    embed = discord.Embed(
        title=f"🎲 Reroll Slot {slot_idx + 1}", color=discord.Color.blurple()
    )

    lines = [f"**Cosmic Dust:** ✨ {dust:,}", ""]

    if slot:
        lines.append(f"**Current:** {M.format_passive_description(slot)}")
        lines.append("")
        defn = PASSIVES.get(slot["type"])
        lines.append(
            f"**Reroll Type** ({DUST_REROLL_TYPE:,} dust) — rolls a new random passive type and value."
        )
        if defn:
            range_str = f"{defn.min_value:.1f}–{defn.max_value:.1f}{'%' if defn.is_percent else ''}"
            lines.append(
                f"**Reroll Value** ({DUST_REROLL_VALUE:,} dust) — keeps **{defn.name}**, new value in range {range_str}."
            )
        else:
            lines.append(
                f"**Reroll Value** ({DUST_REROLL_VALUE:,} dust) — re-rolls current value."
            )
    else:
        lines.append("*Empty slot — no passive to reroll.*")

    if result_msg:
        lines += ["", f"**Result:** {result_msg}"]

    embed.description = "\n".join(lines)
    return embed


# ---------------------------------------------------------------------------
# Main hub view
# ---------------------------------------------------------------------------


class ParadiseHubView(BaseView):
    def __init__(self, bot, user_id, server_id, data, jewel_count, dust):
        super().__init__(bot, user_id, server_id)
        self.data = data
        self.jewel_count = jewel_count
        self.dust = dust
        self._build_buttons()

    def _build_buttons(self) -> None:
        self.clear_items()

        skills_btn = ui.Button(
            label="Manage Skills", style=ButtonStyle.blurple, emoji="⚔️", row=0
        )
        skills_btn.callback = self._manage_skills_callback
        self.add_item(skills_btn)

        passives_btn = ui.Button(
            label="Manage Passives", style=ButtonStyle.blurple, emoji="🔮", row=0
        )
        passives_btn.callback = self._manage_passives_callback
        self.add_item(passives_btn)

        exit_btn = ui.Button(
            label="Close", style=ButtonStyle.secondary, emoji="✖️", row=1
        )
        exit_btn.callback = self._exit_callback
        self.add_item(exit_btn)

    def build_embed(self) -> discord.Embed:
        return _build_hub_embed(self.data, self.jewel_count, self.dust)

    async def _exit_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()

    async def _manage_skills_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = _ManageSkillsView(
            self.bot,
            self.user_id,
            self.server_id,
            self.data,
            self.jewel_count,
            self.message,
        )
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()

    async def _manage_passives_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = _ManagePassivesView(
            self.bot,
            self.user_id,
            self.server_id,
            self.data,
            self.jewel_count,
            self.dust,
            self.message,
        )
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()


# ---------------------------------------------------------------------------
# Manage Skills view
# ---------------------------------------------------------------------------


class _ManageSkillsView(BaseView):
    def __init__(self, bot, user_id, server_id, data, jewel_count, message):
        super().__init__(bot, user_id, server_id)
        self.data = data
        self.jewel_count = jewel_count
        self.message = message
        self._processing = False
        self._build_items()

    def _build_items(self) -> None:
        self.clear_items()
        unlocked = self.data.get("unlocked_skills", [])
        equipped = self.data.get("equipped_skill")
        remaining = [sk for sk in SKILL_JEWELS if sk not in unlocked]

        if unlocked:
            options = [
                discord.SelectOption(
                    label=SKILL_JEWELS[sk].name,
                    description=SKILL_JEWELS[sk].description_short[:100],
                    value=sk,
                    emoji=SKILL_JEWELS[sk].emoji,
                    default=(sk == equipped),
                )
                for sk in unlocked
                if sk in SKILL_JEWELS
            ]
            select = ui.Select(
                placeholder="Equip a skill…",
                options=options[:25],
                min_values=1,
                max_values=1,
                row=0,
            )
            select.callback = self._on_skill_select
            self.add_item(select)

        if remaining and self.jewel_count > 0:
            cut_btn = ui.Button(
                label="Cut Jewel", style=ButtonStyle.success, emoji="💎", row=1
            )
            cut_btn.callback = self._cut_jewel_callback
            self.add_item(cut_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="◀️", row=1
        )
        back_btn.callback = self._back_callback
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        return _build_manage_skills_embed(self.data)

    async def _on_skill_select(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        skill_key = interaction.data["values"][0]
        self.data["equipped_skill"] = skill_key
        self.data.setdefault("skill_charges", {}).setdefault(skill_key, 0)
        await self.bot.database.paradise.save(self.user_id, self.data)
        self._build_items()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _cut_jewel_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        unlocked = self.data.get("unlocked_skills", [])
        remaining = [sk for sk in SKILL_JEWELS if sk not in unlocked]
        if not remaining:
            return
        view = _SkillPickView(
            self.bot,
            self.user_id,
            self.server_id,
            self.data,
            remaining,
            self.jewel_count,
            self.message,
        )
        embed = discord.Embed(
            title="📖 Unlock a Skill",
            description="Select a skill jewel to permanently unlock.",
            color=discord.Color.green(),
        )
        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()

    async def _back_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()


# ---------------------------------------------------------------------------
# Skill Pick view (unlock a new skill)
# ---------------------------------------------------------------------------


class _SkillPickView(BaseView):
    def __init__(
        self, bot, user_id, server_id, data, remaining_skills, jewel_count, message
    ):
        super().__init__(bot, user_id, server_id)
        self.data = data
        self.jewel_count = jewel_count
        self.message = message
        self._processing = False

        options = [
            discord.SelectOption(
                label=SKILL_JEWELS[sk].name,
                description=SKILL_JEWELS[sk].description_short[:100],
                value=sk,
                emoji=SKILL_JEWELS[sk].emoji,
            )
            for sk in remaining_skills
            if sk in SKILL_JEWELS
        ]
        select = ui.Select(
            placeholder="Choose a skill to unlock…",
            options=options[:25],
            min_values=1,
            max_values=1,
            row=0,
        )
        select.callback = self._on_select
        self.add_item(select)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="◀️", row=1)
        back.callback = self._on_back
        self.add_item(back)

    async def _on_select(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        skill_key = interaction.data["values"][0]
        err = M.consume_jewel_unlock_skill(self.data, skill_key)
        if err:
            await interaction.followup.send(f"❌ {err}", ephemeral=True)
            await self._back_to_skills(interaction)
            return
        await self.bot.database.uber.increment_paradise_jewels(
            self.user_id, self.server_id, -1
        )
        await self.bot.database.paradise.save(self.user_id, self.data)
        defn = SKILL_JEWELS[skill_key]
        result_embed = discord.Embed(
            title=f"{defn.emoji} Skill Unlocked!",
            description=f"**{defn.name}** has been added to your roster.",
            color=discord.Color.green(),
        )
        result_embed.set_thumbnail(url=SKILL_IMAGES.get(skill_key, SKILL_UNCUT))
        await interaction.edit_original_response(embed=result_embed, view=None)
        await asyncio.sleep(3)
        await self._back_to_skills(interaction)

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        await self._back_to_skills(interaction)

    async def _back_to_skills(self, interaction: Interaction) -> None:
        data, jewel_count = await _fetch_skills_data(
            self.bot, self.user_id, self.server_id
        )
        view = _ManageSkillsView(
            self.bot, self.user_id, self.server_id, data, jewel_count, self.message
        )
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()


# ---------------------------------------------------------------------------
# Manage Passives view
# ---------------------------------------------------------------------------


class _ManagePassivesView(BaseView):
    def __init__(self, bot, user_id, server_id, data, jewel_count, dust, message):
        super().__init__(bot, user_id, server_id)
        self.data = data
        self.jewel_count = jewel_count
        self.dust = dust
        self.message = message
        self._build_items()

    def _build_items(self) -> None:
        self.clear_items()
        slot_count = M.get_passive_slot_count(self.data)
        passive_slots = self.data.get("passive_slots", [])

        if slot_count > 0:
            options = []
            for i in range(slot_count):
                label = (
                    M.format_passive_slot(passive_slots[i])
                    if i < len(passive_slots)
                    else f"Slot {i + 1} (Empty)"
                )
                options.append(
                    discord.SelectOption(
                        label=f"Slot {i + 1}: {label}"[:100], value=str(i)
                    )
                )
            select = ui.Select(
                placeholder="Choose a passive slot to reroll…",
                options=options[:25],
                min_values=1,
                max_values=1,
                row=0,
            )
            select.callback = self._on_slot_select
            self.add_item(select)

        if slot_count < 5 and self.jewel_count > 0:
            cut_btn = ui.Button(
                label="Cut Jewel", style=ButtonStyle.success, emoji="💎", row=1
            )
            cut_btn.callback = self._cut_jewel_callback
            self.add_item(cut_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="◀️", row=1
        )
        back_btn.callback = self._back_callback
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        return _build_manage_passives_embed(self.data, self.dust)

    async def _on_slot_select(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        slot_idx = int(interaction.data["values"][0])
        view = _RerollActionView(
            self.bot,
            self.user_id,
            self.server_id,
            self.data,
            slot_idx,
            self.jewel_count,
            self.dust,
            self.message,
        )
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()

    async def _cut_jewel_callback(self, interaction: Interaction) -> None:
        needed = M.jewels_to_next_slot(self.data)
        modal = _PassiveInvestModal(self, needed)
        await interaction.response.send_modal(modal)

    async def _back_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()


# ---------------------------------------------------------------------------
# Passive invest modal
# ---------------------------------------------------------------------------


class _PassiveInvestModal(ui.Modal):
    def __init__(self, parent_view: "_ManagePassivesView", needed: Optional[int]):
        super().__init__(title="Invest Jewels in Passive Slot")
        self.parent_view = parent_view
        invested = parent_view.data.get("passive_jewels_invested", 0)
        slots_remaining = 5 - M.get_passive_slot_count(parent_view.data)
        total_to_max = (
            max(0, PASSIVE_SLOT_THRESHOLDS[-1] - invested) if slots_remaining > 0 else 0
        )
        max_invest = min(parent_view.jewel_count, total_to_max)
        self.amount_input = ui.TextInput(
            label="Number of jewels to invest",
            placeholder=f"1–{max_invest}",
            min_length=1,
            max_length=4,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: Interaction) -> None:
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid whole number.", ephemeral=True
            )
            return

        pv = self.parent_view
        invested_so_far = pv.data.get("passive_jewels_invested", 0)
        total_to_max = max(0, PASSIVE_SLOT_THRESHOLDS[-1] - invested_so_far)

        if amount <= 0:
            await interaction.response.send_message(
                "Amount must be at least 1.", ephemeral=True
            )
            return
        if amount > pv.jewel_count:
            await interaction.response.send_message(
                f"You only have **{pv.jewel_count}** jewel(s) available.",
                ephemeral=True,
            )
            return
        if amount > total_to_max:
            amount = total_to_max

        await interaction.response.defer()

        invested = 0
        last_msg = ""
        any_slot_unlocked = False
        for _ in range(amount):
            if M.get_passive_slot_count(pv.data) >= 5:
                break
            slot_unlocked, msg = M.consume_jewel_invest_passive(pv.data)
            invested += 1
            last_msg = msg
            if slot_unlocked:
                any_slot_unlocked = True

        if invested > 0:
            await pv.bot.database.uber.increment_paradise_jewels(
                pv.user_id, pv.server_id, -invested
            )
            await pv.bot.database.paradise.save(pv.user_id, pv.data)

        if invested == 0:
            result_title = "🔮 All Slots Unlocked"
            result_desc = "All 5 passive slots are already unlocked."
        elif any_slot_unlocked:
            result_title = "🔮 Passive Slot Unlocked!"
            result_desc = f"Cut **{invested}** jewel(s). {last_msg}"
        else:
            result_title = "💎 Jewels Cut"
            result_desc = f"Cut **{invested}** jewel(s). {last_msg}"

        result_embed = discord.Embed(
            title=result_title,
            description=result_desc,
            color=discord.Color.from_str("#b967ff"),
        )
        result_embed.set_thumbnail(url=SKILL_UNCUT)
        await interaction.edit_original_response(embed=result_embed, view=None)
        await asyncio.sleep(3)

        data, jewel_count, dust = await _fetch_passives_data(
            pv.bot, pv.user_id, pv.server_id
        )
        new_view = _ManagePassivesView(
            pv.bot, pv.user_id, pv.server_id, data, jewel_count, dust, pv.message
        )
        await interaction.edit_original_response(
            embed=new_view.build_embed(), view=new_view
        )
        pv.stop()


# ---------------------------------------------------------------------------
# Reroll Action view
# ---------------------------------------------------------------------------


class _RerollActionView(BaseView):
    def __init__(
        self, bot, user_id, server_id, data, slot_idx, jewel_count, dust, message
    ):
        super().__init__(bot, user_id, server_id)
        self.data = data
        self.slot_idx = slot_idx
        self.jewel_count = jewel_count
        self.dust = dust
        self.message = message
        self._processing = False
        self._result_msg = ""
        self._build_buttons()

    def _build_buttons(self) -> None:
        self.clear_items()
        can_type = self.dust >= DUST_REROLL_TYPE
        can_value = self.dust >= DUST_REROLL_VALUE

        type_btn = ui.Button(
            label=f"Reroll Type ({DUST_REROLL_TYPE:,} dust)",
            style=ButtonStyle.blurple,
            emoji="🔀",
            disabled=not can_type,
            row=0,
        )
        type_btn.callback = self._reroll_type_callback
        self.add_item(type_btn)

        val_btn = ui.Button(
            label=f"Reroll Value ({DUST_REROLL_VALUE:,} dust)",
            style=ButtonStyle.secondary,
            emoji="🎯",
            disabled=not can_value,
            row=0,
        )
        val_btn.callback = self._reroll_value_callback
        self.add_item(val_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="◀️", row=1
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        return _build_reroll_embed(
            self.data, self.slot_idx, self.dust, self._result_msg
        )

    async def _reroll_type_callback(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        success, msg, cost = M.reroll_passive_type(self.data, self.slot_idx)
        if not success:
            self._result_msg = f"❌ {msg}"
            self._processing = False
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )
            return
        await self.bot.database.alchemy.modify_cosmic_dust(self.user_id, -cost)
        await self.bot.database.paradise.save(self.user_id, self.data)
        self.dust -= cost
        self._result_msg = f"🔀 {msg}"
        self._build_buttons()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _reroll_value_callback(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        success, msg, cost = M.reroll_passive_value(self.data, self.slot_idx)
        if not success:
            self._result_msg = f"❌ {msg}"
            self._processing = False
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )
            return
        await self.bot.database.alchemy.modify_cosmic_dust(self.user_id, -cost)
        await self.bot.database.paradise.save(self.user_id, self.data)
        self.dust -= cost
        self._result_msg = f"🎯 {msg}"
        self._build_buttons()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        data, jewel_count, dust = await _fetch_passives_data(
            self.bot, self.user_id, self.server_id
        )
        view = _ManagePassivesView(
            self.bot,
            self.user_id,
            self.server_id,
            data,
            jewel_count,
            dust,
            self.message,
        )
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()
