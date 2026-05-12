"""
Paradise Jewel system UI.
Entry point: ParadiseHubView (opened from /paradise cog command).
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.paradise import mechanics as M
from core.paradise.data import (
    DUST_REROLL_TYPE,
    DUST_REROLL_VALUE,
    PASSIVE_SLOT_THRESHOLDS,
    SKILL_JEWELS,
)

# ---------------------------------------------------------------------------
# Re-fetch helper
# ---------------------------------------------------------------------------


async def _reload_hub(bot, user_id: str, server_id: str) -> "ParadiseHubView":
    data = await bot.database.paradise.get(user_id)
    uber = await bot.database.uber.get_uber_progress(user_id, server_id)
    jewel_count = uber.get("paradise_jewels", 0)
    dust = await bot.database.alchemy.get_cosmic_dust(user_id)
    return ParadiseHubView(bot, user_id, server_id, data, jewel_count, dust)


# ---------------------------------------------------------------------------
# Embed builder (stateless helper)
# ---------------------------------------------------------------------------


def _build_hub_embed(
    data: dict,
    jewel_count: int,
    dust: int,
) -> discord.Embed:
    embed = discord.Embed(
        title="💎 Jewel of Paradise",
        color=discord.Color.from_str("#b967ff"),
    )

    # Header stats
    obtained = data.get("total_jewels_obtained", 0)
    consumed = data.get("total_jewels_consumed", 0)
    embed.description = (
        f"**Uncut Jewels:** 💎 {jewel_count}\n"
        f"**Cosmic Dust:** ✨ {dust:,}\n"
        f"**Jewels Obtained:** {obtained}  •  **Cut:** {consumed}"
    )

    # Equipped skill card
    equipped = data.get("equipped_skill")
    unlocked = data.get("unlocked_skills", [])
    if equipped and equipped in SKILL_JEWELS:
        defn = SKILL_JEWELS[equipped]
        mastery = M.mastery_bonus(data)
        eff_level = M.get_effective_level(equipped, data, mastery)
        compression = M.get_compression_bonus(data)
        threshold = max(1, M.get_threshold(equipped, eff_level) - compression)
        natural_level = data["skill_levels"].get(equipped, 1)
        charges = data["skill_charges"].get(equipped, 0)

        level_display = f"Lv {natural_level}"
        if mastery > 0:
            level_display += f" (+{mastery} Mastery → Lv {eff_level} effective)"

        next_level_combats = M.combats_to_next_level(natural_level)
        if next_level_combats is not None:
            level_display += f"  *(~{next_level_combats:.0f} combats to next level)*"
        else:
            level_display += "  *(MAX)*"

        skill_lines = [
            f"{defn.emoji} **{defn.name}** — {level_display}",
            f"**Charges:** {charges} / {threshold}",
            f"*{defn.charge_trigger}*",
        ]
        skill_lines.append(f"**Unleash:** {M.format_unleash_description(equipped, eff_level)}")

        embed.add_field(
            name="⚔️ Equipped Skill",
            value="\n".join(skill_lines),
            inline=False,
        )
    elif unlocked:
        embed.add_field(
            name="⚔️ Equipped Skill",
            value="*No skill equipped — use Swap Skill to select one.*",
            inline=False,
        )
    else:
        embed.add_field(
            name="⚔️ Equipped Skill",
            value=(
                "*No skills unlocked yet.*\n"
                "Cut a Jewel of Paradise to unlock your first skill."
            ),
            inline=False,
        )

    # All unlocked skills (roster)
    if unlocked:
        rows = []
        for sk in unlocked:
            defn = SKILL_JEWELS.get(sk)
            if not defn:
                continue
            lvl = data["skill_levels"].get(sk, 1)
            equipped_marker = " ◀" if sk == equipped else ""
            rows.append(f"{defn.emoji} **{defn.name}** Lv {lvl}{equipped_marker}")
        embed.add_field(
            name=f"📖 Unlocked Skills ({len(unlocked)}/{len(SKILL_JEWELS)})",
            value="\n".join(rows),
            inline=True,
        )

    # Passive slots
    slot_count = M.get_passive_slot_count(data)
    passive_slots = data.get("passive_slots", [])
    if slot_count > 0:
        lines = []
        for i in range(slot_count):
            if i < len(passive_slots):
                lines.append(f"**[{i+1}]** {M.format_passive_slot(passive_slots[i])}")
            else:
                lines.append(f"**[{i+1}]** *Empty*")
        embed.add_field(
            name="🔮 Passive Slots",
            value="\n".join(lines),
            inline=True,
        )
    else:
        needed = M.jewels_to_next_slot(data)
        cost_str = f"{needed} jewel(s) needed" if needed else "Max slots reached"
        embed.add_field(
            name="🔮 Passive Slots",
            value=f"*No passive slots unlocked.*\n{cost_str} for Slot 1.",
            inline=True,
        )

    # Progression footer
    needed_next = M.jewels_to_next_slot(data)
    invested = data.get("passive_jewels_invested", 0)
    if needed_next and slot_count < 5:
        thres = PASSIVE_SLOT_THRESHOLDS[slot_count]
        embed.set_footer(
            text=f"Passive Slot {slot_count + 1}: {invested}/{thres} jewels invested  •  "
            f"Reroll Type: {DUST_REROLL_TYPE:,} dust  •  Reroll Value: {DUST_REROLL_VALUE:,} dust"
        )
    else:
        embed.set_footer(
            text=f"All 5 passive slots unlocked  •  "
            f"Reroll Type: {DUST_REROLL_TYPE:,} dust  •  Reroll Value: {DUST_REROLL_VALUE:,} dust"
        )

    return embed


# ---------------------------------------------------------------------------
# Main hub view
# ---------------------------------------------------------------------------


class ParadiseHubView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        data: dict,
        jewel_count: int,
        dust: int,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.data = data
        self.jewel_count = jewel_count
        self.dust = dust
        self.message = None
        self._build_buttons()

    def _build_buttons(self) -> None:
        self.clear_items()

        unlocked = self.data.get("unlocked_skills", [])
        slot_count = M.get_passive_slot_count(self.data)
        can_consume = M.can_consume_jewel(self.data) and self.jewel_count > 0

        # Row 0: Swap Skill (only if skills unlocked)
        if len(unlocked) > 1:
            swap = ui.Button(
                label="Swap Skill", style=ButtonStyle.secondary, emoji="🔄", row=0
            )
            swap.callback = self._swap_skill_callback
            self.add_item(swap)

        # Row 0: Consume Jewel
        consume = ui.Button(
            label="Consume Jewel",
            style=ButtonStyle.success if can_consume else ButtonStyle.secondary,
            emoji="💎",
            row=0,
            disabled=not can_consume,
        )
        consume.callback = self._consume_jewel_callback
        self.add_item(consume)

        # Row 0: Dust Jewel
        dust_btn = ui.Button(
            label="Dust Jewel",
            style=ButtonStyle.secondary,
            emoji="✨",
            row=0,
            disabled=self.jewel_count <= 0,
        )
        dust_btn.callback = self._dust_jewel_callback
        self.add_item(dust_btn)

        # Row 1: Reroll (only if passive slots exist)
        if slot_count > 0:
            reroll = ui.Button(
                label="Reroll Passive", style=ButtonStyle.blurple, emoji="🎲", row=1
            )
            reroll.callback = self._reroll_callback
            self.add_item(reroll)

        # Row 1: Exit
        exit_btn = ui.Button(
            label="Exit", style=ButtonStyle.secondary, emoji="✖️", row=1
        )
        exit_btn.callback = self._exit_callback
        self.add_item(exit_btn)

    def build_embed(self) -> discord.Embed:
        return _build_hub_embed(self.data, self.jewel_count, self.dust)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def _refresh(self, interaction: Interaction) -> None:
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        embed = view.build_embed()
        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()

    # ------------------------------------------------------------------
    # Exit
    # ------------------------------------------------------------------

    async def _exit_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()

    # ------------------------------------------------------------------
    # Swap Skill
    # ------------------------------------------------------------------

    async def _swap_skill_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        unlocked = self.data.get("unlocked_skills", [])
        if not unlocked:
            await interaction.followup.send("No skills unlocked.", ephemeral=True)
            return
        view = _SkillSwapView(
            self.bot, self.user_id, self.server_id, self.data, self.message
        )
        embed = discord.Embed(
            title="🔄 Swap Skill",
            description="Select the skill jewel to equip.",
            color=discord.Color.blurple(),
        )
        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()

    # ------------------------------------------------------------------
    # Consume Jewel
    # ------------------------------------------------------------------

    async def _consume_jewel_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = _ConsumeJewelView(
            self.bot, self.user_id, self.server_id, self.data, self.message
        )
        embed = view.build_embed()
        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()

    # ------------------------------------------------------------------
    # Dust Jewel
    # ------------------------------------------------------------------

    async def _dust_jewel_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        alchemy_level = await self.bot.database.alchemy.get_level(self.user_id)
        dust_gain = M.dust_from_jewel(alchemy_level)
        await self.bot.database.uber.increment_paradise_jewels(
            self.user_id, self.server_id, -1
        )
        await self.bot.database.alchemy.modify_cosmic_dust(self.user_id, dust_gain)
        # Update data tracking
        self.data["total_jewels_obtained"] = self.data.get("total_jewels_obtained", 0)
        await self.bot.database.paradise.save(self.user_id, self.data)
        await interaction.followup.send(
            f"✨ Dusted 1 Jewel of Paradise for **{dust_gain:,} Cosmic Dust**.",
            ephemeral=True,
        )
        await self._refresh(interaction)

    # ------------------------------------------------------------------
    # Reroll Passive
    # ------------------------------------------------------------------

    async def _reroll_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = _RerollSelectView(
            self.bot, self.user_id, self.server_id, self.data, self.dust, self.message
        )
        embed = view.build_embed()
        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()


# ---------------------------------------------------------------------------
# Skill Swap view
# ---------------------------------------------------------------------------


class _SkillSwapView(ui.View):
    def __init__(self, bot, user_id, server_id, data, message):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.data = data
        self.message = message

        unlocked = data.get("unlocked_skills", [])
        equipped = data.get("equipped_skill")
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
            placeholder="Choose a skill to equip…",
            options=options[:25],
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="◀️")
        back.callback = self._on_back
        self.add_item(back)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def _on_select(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        skill_key = interaction.data["values"][0]
        self.data["equipped_skill"] = skill_key
        if skill_key not in self.data.get("skill_charges", {}):
            self.data.setdefault("skill_charges", {})[skill_key] = 0
        await self.bot.database.paradise.save(self.user_id, self.data)
        defn = SKILL_JEWELS[skill_key]
        await interaction.followup.send(
            f"{defn.emoji} Equipped **{defn.name}**.", ephemeral=True
        )
        await self._back_to_hub(interaction)

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        await self._back_to_hub(interaction)

    async def _back_to_hub(self, interaction: Interaction) -> None:
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()


# ---------------------------------------------------------------------------
# Consume Jewel view
# ---------------------------------------------------------------------------


class _ConsumeJewelView(ui.View):
    def __init__(self, bot, user_id, server_id, data, message):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.data = data
        self.message = message
        self._build_buttons()

    def _build_buttons(self) -> None:
        self.clear_items()
        unlocked = self.data.get("unlocked_skills", [])
        remaining_skills = [sk for sk in SKILL_JEWELS if sk not in unlocked]
        slot_count = M.get_passive_slot_count(self.data)

        if remaining_skills:
            skill_btn = ui.Button(
                label="Unlock Skill", style=ButtonStyle.success, emoji="📖", row=0
            )
            skill_btn.callback = self._unlock_skill_callback
            self.add_item(skill_btn)

        if slot_count < 5:
            needed = M.jewels_to_next_slot(self.data)
            invest_btn = ui.Button(
                label=f"Invest in Passive Slot ({needed} needed)",
                style=ButtonStyle.blurple,
                emoji="🔮",
                row=0,
            )
            invest_btn.callback = self._invest_passive_callback
            self.add_item(invest_btn)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="◀️", row=1)
        back.callback = self._back_callback
        self.add_item(back)

    def build_embed(self) -> discord.Embed:
        unlocked = self.data.get("unlocked_skills", [])
        slot_count = M.get_passive_slot_count(self.data)
        remaining_skills = [sk for sk in SKILL_JEWELS if sk not in unlocked]
        needed = M.jewels_to_next_slot(self.data)

        embed = discord.Embed(
            title="💎 Consume Jewel of Paradise",
            color=discord.Color.from_str("#b967ff"),
        )
        lines = ["Choose how to spend one Jewel of Paradise:\n"]
        if remaining_skills:
            skill_list = ", ".join(
                f"**{SKILL_JEWELS[sk].name}**" for sk in remaining_skills[:5]
            )
            if len(remaining_skills) > 5:
                skill_list += f" and {len(remaining_skills)-5} more"
            lines.append(
                f"📖 **Unlock Skill** — Add a new skill jewel to your roster.\n   *Available: {skill_list}*"
            )
        if slot_count < 5:
            invested = self.data.get("passive_jewels_invested", 0)
            thres = PASSIVE_SLOT_THRESHOLDS[slot_count]
            lines.append(
                f"🔮 **Invest in Passive Slot** — Progress toward Slot {slot_count+1}.\n"
                f"   *{invested}/{thres} invested ({needed} more needed)*"
            )
        embed.description = "\n".join(lines)
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def _unlock_skill_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        unlocked = self.data.get("unlocked_skills", [])
        remaining = [sk for sk in SKILL_JEWELS if sk not in unlocked]
        if not remaining:
            await interaction.followup.send(
                "All skills already unlocked.", ephemeral=True
            )
            return
        view = _SkillPickView(
            self.bot, self.user_id, self.server_id, self.data, remaining, self.message
        )
        embed = discord.Embed(
            title="📖 Unlock a Skill",
            description="Select a skill jewel to permanently unlock.",
            color=discord.Color.green(),
        )
        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()

    async def _invest_passive_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        slot_unlocked, msg = M.consume_jewel_invest_passive(self.data)
        await self.bot.database.uber.increment_paradise_jewels(
            self.user_id, self.server_id, -1
        )
        await self.bot.database.paradise.save(self.user_id, self.data)
        await interaction.followup.send(f"🔮 {msg}", ephemeral=True)
        await self._back_to_hub(interaction)

    async def _back_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        await self._back_to_hub(interaction)

    async def _back_to_hub(self, interaction: Interaction) -> None:
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()


# ---------------------------------------------------------------------------
# Skill pick view (choose which skill to unlock)
# ---------------------------------------------------------------------------


class _SkillPickView(ui.View):
    def __init__(self, bot, user_id, server_id, data, remaining_skills, message):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.data = data
        self.message = message

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
        )
        select.callback = self._on_select
        self.add_item(select)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="◀️")
        back.callback = self._on_back
        self.add_item(back)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def _on_select(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        skill_key = interaction.data["values"][0]
        err = M.consume_jewel_unlock_skill(self.data, skill_key)
        if err:
            await interaction.followup.send(f"❌ {err}", ephemeral=True)
            await self._back_to_hub(interaction)
            return
        await self.bot.database.uber.increment_paradise_jewels(
            self.user_id, self.server_id, -1
        )
        await self.bot.database.paradise.save(self.user_id, self.data)
        defn = SKILL_JEWELS[skill_key]
        await interaction.followup.send(
            f"{defn.emoji} **{defn.name}** has been unlocked!", ephemeral=True
        )
        await self._back_to_hub(interaction)

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        await self._back_to_hub(interaction)

    async def _back_to_hub(self, interaction: Interaction) -> None:
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()


# ---------------------------------------------------------------------------
# Reroll Passive view — pick slot then type or value
# ---------------------------------------------------------------------------


class _RerollSelectView(ui.View):
    def __init__(self, bot, user_id, server_id, data, dust, message):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.data = data
        self.dust = dust
        self.message = message

        slot_count = M.get_passive_slot_count(data)
        passive_slots = data.get("passive_slots", [])
        options = []
        for i in range(slot_count):
            if i < len(passive_slots):
                label = M.format_passive_slot(passive_slots[i])
            else:
                label = f"Slot {i+1} (Empty)"
            options.append(
                discord.SelectOption(label=f"Slot {i+1}: {label}"[:100], value=str(i))
            )

        select = ui.Select(
            placeholder="Choose a passive slot to reroll…",
            options=options[:25],
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_slot_select
        self.add_item(select)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="◀️", row=1)
        back.callback = self._on_back
        self.add_item(back)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎲 Reroll Passive",
            color=discord.Color.blurple(),
        )
        lines = [
            f"**Cosmic Dust:** ✨ {self.dust:,}",
            "",
            f"**Reroll Type** — {DUST_REROLL_TYPE:,} dust (new passive type + new value)",
            f"**Reroll Value** — {DUST_REROLL_VALUE:,} dust (same type, new value)",
        ]
        embed.description = "\n".join(lines)
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def _on_slot_select(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        slot_idx = int(interaction.data["values"][0])
        view = _RerollActionView(
            self.bot,
            self.user_id,
            self.server_id,
            self.data,
            slot_idx,
            self.dust,
            self.message,
        )
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()


class _RerollActionView(ui.View):
    def __init__(self, bot, user_id, server_id, data, slot_idx, dust, message):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.data = data
        self.slot_idx = slot_idx
        self.dust = dust
        self.message = message

        can_type = dust >= DUST_REROLL_TYPE
        can_value = dust >= DUST_REROLL_VALUE

        type_btn = ui.Button(
            label=f"Reroll Type ({DUST_REROLL_TYPE:,} dust)",
            style=ButtonStyle.blurple,
            emoji="🔀",
            disabled=not can_type,
        )
        type_btn.callback = self._reroll_type_callback
        self.add_item(type_btn)

        val_btn = ui.Button(
            label=f"Reroll Value ({DUST_REROLL_VALUE:,} dust)",
            style=ButtonStyle.secondary,
            emoji="🎯",
            disabled=not can_value,
        )
        val_btn.callback = self._reroll_value_callback
        self.add_item(val_btn)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="◀️", row=1)
        back.callback = self._on_back
        self.add_item(back)

    def build_embed(self) -> discord.Embed:
        slots = self.data.get("passive_slots", [])
        slot_desc = (
            M.format_passive_description(slots[self.slot_idx])
            if self.slot_idx < len(slots)
            else "*Empty*"
        )
        embed = discord.Embed(
            title=f"🎲 Reroll Slot {self.slot_idx + 1}",
            description=(
                f"**Current:** {slot_desc}\n"
                f"**Cosmic Dust:** ✨ {self.dust:,}\n\n"
                f"**Reroll Type** costs {DUST_REROLL_TYPE:,} dust.\n"
                f"**Reroll Value** costs {DUST_REROLL_VALUE:,} dust."
            ),
            color=discord.Color.blurple(),
        )
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def _reroll_type_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        success, msg, cost = M.reroll_passive_type(self.data, self.slot_idx)
        if not success:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            return
        await self.bot.database.alchemy.modify_cosmic_dust(self.user_id, -cost)
        await self.bot.database.paradise.save(self.user_id, self.data)
        await interaction.followup.send(f"🔀 {msg}", ephemeral=True)
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()

    async def _reroll_value_callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        success, msg, cost = M.reroll_passive_value(self.data, self.slot_idx)
        if not success:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
            return
        await self.bot.database.alchemy.modify_cosmic_dust(self.user_id, -cost)
        await self.bot.database.paradise.save(self.user_id, self.data)
        await interaction.followup.send(f"🎯 {msg}", ephemeral=True)
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = await _reload_hub(self.bot, self.user_id, self.server_id)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        self.stop()
