# core/companions/views.py

import asyncio
import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.companions.engram_view import BalancedEngramView
from core.images import COMPANIONS_FUSION, YUNA_PORTRAIT, YUNA_THUMBNAIL
from core.companions.logic import CompanionLogic
from core.companions.mechanics import CompanionMechanics
from core.models import Companion
from core.npc_voices import get_quip


class RerollConfirmView(BaseView):
    def __init__(self, bot, user_id, companion, runes_owned, origin_view):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.comp = companion
        self.runes_owned = runes_owned
        self.origin_view = origin_view  # The Detail View
        self._processing = False

    @ui.button(label="Confirm Reroll", style=ButtonStyle.success, emoji="🎲")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # Double check funds just in case
        runes = await self.bot.database.users.get_currency(
            self.user_id, "partnership_runes"
        )
        if runes < 1:
            self._processing = False
            return await interaction.response.send_message(
                "You ran out of runes!", ephemeral=True
            )

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        # 1. Deduct
        await self.bot.database.users.modify_currency(
            self.user_id, "partnership_runes", -1
        )

        # 2. Logic
        old_tier = self.comp.passive_tier
        old_type = self.comp.passive_type

        # Pass current type to ensure change
        new_type, new_tier, upgraded = CompanionMechanics.reroll_passive(
            old_tier, old_type
        )

        # 3. Update DB
        await self.bot.database.companions.update_passive(
            self.comp.id, new_type, new_tier
        )

        # 4. Update Local Object
        self.comp.passive_type = new_type
        self.comp.passive_tier = new_tier

        # 5. Return to Detail View
        embed = self.origin_view.get_embed()
        embed.color = discord.Color.green()
        result = f"🎲 **Reroll Complete!**\nPrevious: T{old_tier} {old_type.upper()}\n**New:** T{new_tier} **{new_type.upper()}**"
        if upgraded:
            result += "\n🌟 **TIER UPGRADE!**"
        embed.description = (embed.description or "") + f"\n\n{result}"

        await interaction.edit_original_response(
            content=None, embed=embed, view=self.origin_view
        )
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=None, embed=self.origin_view.get_embed(), view=self.origin_view
        )
        self.stop()


class CompanionListView(BaseView):
    def __init__(
        self, bot, user_id: str, companions: list[Companion], pending_cookies: int = 0
    ):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.companions = companions
        self._pending_cookies = pending_cookies
        self.update_buttons()

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def update_buttons(self):
        self.clear_items()

        # Dropdown to select any companion (row 0)
        if self.companions:
            options = []
            for comp in self.companions:
                status = "🟢" if comp.is_active else "⚪"
                label = f"{status} {comp.name} (Lv.{comp.level})"
                balanced_str = (
                    f" | {comp.balanced_description}"
                    if comp.balanced_passive != "none"
                    else ""
                )
                desc = f"T{comp.passive_tier} {comp.description}{balanced_str}"
                options.append(
                    SelectOption(
                        label=label[:100],
                        description=desc[:100],
                        value=str(comp.id),
                    )
                )
            select = ui.Select(
                placeholder="Select a companion to view details...",
                options=options,
                row=0,
            )
            select.callback = self._on_select
            self.add_item(select)

        # Action buttons (row 1)
        collect_btn = ui.Button(
            label="Collect", style=ButtonStyle.success, emoji="💰", row=1
        )
        collect_btn.callback = self.collect_loot
        self.add_item(collect_btn)

        if self._pending_cookies > 0:
            cookies_btn = ui.Button(
                label=f"Distribute XP ({self._pending_cookies:,})",
                style=ButtonStyle.success,
                emoji="🐾",
                row=1,
            )
            cookies_btn.callback = self.open_xp_distribute
            self.add_item(cookies_btn)

        fusion_btn = ui.Button(
            label="Fusion", style=ButtonStyle.primary, emoji="🧬", row=1
        )
        fusion_btn.callback = self.open_fusion
        self.add_item(fusion_btn)

        mastery_btn = ui.Button(
            label="Mastery", style=ButtonStyle.blurple, emoji="✨", row=1
        )
        mastery_btn.callback = self.open_mastery
        self.add_item(mastery_btn)

        close_btn = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    def get_embed(self):
        embed = discord.Embed(title="🐾 Companions", color=discord.Color.blue())
        embed.set_author(name="Master Tamer Yuna", icon_url=YUNA_PORTRAIT)
        embed.set_thumbnail(url=YUNA_THUMBNAIL)
        embed.set_footer(text=f"Roster: {len(self.companions)}/20")

        if not self.companions:
            embed.description = f"*{get_quip('companions')}*\n\nYou have no companions. Fight monsters to capture one!"
            return embed

        active = [c for c in self.companions if c.is_active]
        inactive = [c for c in self.companions if not c.is_active]

        active_count = len(active)
        desc = (
            f"*{get_quip('companions')}*\n\n**Active Companions** ({active_count}/3)\n"
        )

        if active:
            desc += "\n"
            for comp in active:
                balanced_str = (
                    f"\n> ♊ T{comp.balanced_passive_tier} {comp.balanced_description}"
                    if comp.balanced_passive != "none"
                    else ""
                )
                desc += (
                    f"🟢 **{comp.name}** — {comp.species} | Lv.{comp.level}\n"
                    f"> T{comp.passive_tier} {comp.description}{balanced_str}\n\n"
                )
        else:
            desc += "\n*No active companions.*\n\n"

        if inactive:
            desc += f"**Inactive** ({len(inactive)})\n"
            desc += ", ".join(f"{c.name} (Lv.{c.level})" for c in inactive)

        embed.description = desc
        return embed

    # --- Callbacks ---
    async def _on_select(self, interaction: Interaction):
        comp_id = int(interaction.data["values"][0])
        comp = next((c for c in self.companions if c.id == comp_id), None)
        if comp is None:
            return await interaction.response.send_message(
                "Companion not found.", ephemeral=True
            )
        view = CompanionDetailView(self.bot, self.user_id, comp, self)
        await interaction.response.edit_message(embed=view.get_embed(), view=view)

    async def collect_loot(self, interaction: Interaction):
        result_msg = await CompanionLogic.collect_passive_rewards(
            self.bot, self.user_id, str(interaction.guild.id)
        )
        await interaction.response.send_message(result_msg, ephemeral=True)

    async def open_xp_distribute(self, interaction: Interaction):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)

        # Check mastery tree completeness for rune unlock
        from core.companions.mastery import get_all_nodes

        mastery = await self.bot.database.companions.get_mastery(
            self.user_id, server_id
        )
        nodes_owned = mastery.get("nodes_owned", {})
        total_nodes = len(get_all_nodes())
        tree_maxed = len(nodes_owned) >= total_nodes
        companions_maxed = bool(self.companions) and all(
            c.level >= CompanionMechanics.MAX_LEVEL for c in self.companions
        )
        is_maxed = tree_maxed and companions_maxed

        view = XPDistributeView(
            self.bot,
            self.user_id,
            server_id,
            self._pending_cookies,
            self.companions,
            is_maxed,
            parent=self,
        )
        await interaction.edit_original_response(embed=view.get_embed(), view=view)

    async def open_fusion(self, interaction: Interaction):
        from core.companions.fusion_views import FusionWizardView

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 50000:
            return await interaction.response.send_message(
                "Fusion costs **50,000 Gold**. You cannot afford it.", ephemeral=True
            )
        if len(self.companions) < 2:
            return await interaction.response.send_message(
                "You need at least **2** companions to perform fusion.", ephemeral=True
            )

        view = FusionWizardView(
            self.bot, self.user_id, self.companions, parent_list_view=self
        )
        embed = discord.Embed(
            title="🧬 Companion Fusion",
            description="Combine two companions to merge their XP and randomize their traits.\n\n**Cost:** 50,000 Gold\nSelect your **Primary** companion below.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=COMPANIONS_FUSION)
        await interaction.response.edit_message(embed=embed, view=view)

    async def open_mastery(self, interaction: Interaction):
        from core.companions.mastery_views import CompanionMasteryView

        server_id = str(interaction.guild.id)
        mastery = await self.bot.database.companions.get_mastery(
            self.user_id, server_id
        )
        view = CompanionMasteryView(
            self.bot, self.user_id, server_id, mastery, parent=self
        )
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class XPDistributeView(BaseView):
    XP_PER_KP = 1_000
    XP_PER_RUNE = 25_000

    def __init__(
        self, bot, user_id, server_id, pending_xp, companions, is_maxed, parent
    ):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.pending_xp = pending_xp
        self.companions = companions
        self.is_maxed = is_maxed
        self.parent = parent
        self._processing = False
        self._add_buttons()

    def _add_buttons(self):
        self.clear_items()
        active = [c for c in self.companions if c.is_active]

        if active and self.pending_xp > 0:
            btn = ui.Button(
                label="Level Companions", style=ButtonStyle.success, emoji="🐾", row=0
            )
            btn.callback = self.distribute_to_companions
            self.add_item(btn)

        if self.pending_xp >= self.XP_PER_KP:
            kp_count = self.pending_xp // self.XP_PER_KP
            btn = ui.Button(
                label=f"Convert to KP ({kp_count:,})",
                style=ButtonStyle.primary,
                emoji="✨",
                row=0,
            )
            btn.callback = self.convert_to_kp
            self.add_item(btn)

        if self.is_maxed and self.pending_xp >= self.XP_PER_RUNE:
            rune_count = self.pending_xp // self.XP_PER_RUNE
            btn = ui.Button(
                label=f"Buy Rune of Partnership ({rune_count})",
                style=ButtonStyle.blurple,
                emoji="🔮",
                row=1,
            )
            btn.callback = self.buy_rune
            self.add_item(btn)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    def get_embed(self):
        embed = discord.Embed(
            title="Distribute XP",
            description=f"*{get_quip('companions')}*",
            color=discord.Color.blue(),
        )
        embed.set_author(name="Master Tamer Yuna", icon_url=YUNA_PORTRAIT)
        embed.set_thumbnail(url=YUNA_THUMBNAIL)
        embed.add_field(
            name="Companion XP Pool", value=f"**{self.pending_xp:,}** XP", inline=False
        )

        active = [c for c in self.companions if c.is_active]
        lines = []
        if active and self.pending_xp > 0:
            lines.append(
                f"🐾 **Level Companions** — Split {self.pending_xp:,} XP among {len(active)} active companion(s)"
            )
        if self.pending_xp >= self.XP_PER_KP:
            lines.append(
                f"✨ **Convert to KP** — {self.XP_PER_KP:,} XP = 1 Kinship Point ({self.pending_xp // self.XP_PER_KP:,} available)"
            )
        if self.is_maxed and self.pending_xp >= self.XP_PER_RUNE:
            lines.append(
                f"🔮 **Rune of Partnership** — {self.XP_PER_RUNE:,} XP = 1 Rune ({self.pending_xp // self.XP_PER_RUNE} available)"
            )
        if not lines:
            lines.append("*Earn more XP to unlock options.*")

        embed.add_field(name="Options", value="\n".join(lines), inline=False)
        return embed

    async def distribute_to_companions(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        total_xp = await self.bot.database.users.consume_pending_companion_cookies(
            self.user_id
        )
        if total_xp <= 0:
            self._processing = False
            await interaction.followup.send("No XP to distribute.", ephemeral=True)
            return

        active = [c for c in self.companions if c.is_active]
        if not active:
            await self.bot.database.users.add_pending_companion_cookies(
                self.user_id, total_xp
            )
            self._processing = False
            await interaction.followup.send(
                "No active companions. Set one active first.", ephemeral=True
            )
            return

        xp_per = total_xp // len(active)
        from core.companions.mastery import kp_from_overflow_xp

        msgs = []
        overflow_xp = 0
        for comp in active:
            cur_lvl, cur_exp = comp.level, comp.exp
            cur_exp += xp_per
            while cur_lvl < CompanionMechanics.MAX_LEVEL:
                req = CompanionMechanics.calculate_next_level_xp(cur_lvl)
                if cur_exp >= req:
                    cur_exp -= req
                    cur_lvl += 1
                else:
                    break
            if cur_lvl >= CompanionMechanics.MAX_LEVEL:
                overflow_xp += cur_exp
                cur_exp = 0
            await self.bot.database.companions.update_stats(comp.id, cur_lvl, cur_exp)
            if cur_lvl != comp.level:
                msgs.append(f"**{comp.name}** levelled up to **{cur_lvl}**!")
            else:
                msgs.append(f"**{comp.name}** gained {xp_per:,} XP (Lv.{cur_lvl})")

        if overflow_xp > 0:
            kp_earned = kp_from_overflow_xp(overflow_xp)
            if kp_earned > 0:
                await self.bot.database.companions.add_kinship_points(
                    self.user_id, self.server_id, kp_earned
                )
                msgs.append(f"+{kp_earned} Kinship Points from overflow XP.")

        from core.items.factory import create_companion

        rows = await self.bot.database.companions.get_all(self.user_id)
        self.companions = [create_companion(r) for r in rows] if rows else []
        self.parent.companions = self.companions
        self.pending_xp = 0
        self.parent._pending_cookies = 0
        self.parent.update_buttons()

        summary = "\n".join(msgs) if msgs else "XP distributed."
        await interaction.edit_original_response(
            embed=self.parent.get_embed(), view=self.parent
        )
        await interaction.followup.send(
            f"🐾 **XP Distributed** ({total_xp:,} XP across {len(active)} companion(s))\n{summary}",
            ephemeral=True,
        )

    async def convert_to_kp(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        pending = await self.bot.database.users.get_pending_companion_cookies(
            self.user_id
        )
        kp_to_gain = pending // self.XP_PER_KP
        xp_to_spend = kp_to_gain * self.XP_PER_KP

        if kp_to_gain <= 0:
            self._processing = False
            await interaction.followup.send(
                f"Need at least {self.XP_PER_KP:,} XP to convert.", ephemeral=True
            )
            return

        all_xp = await self.bot.database.users.consume_pending_companion_cookies(
            self.user_id
        )
        remainder = all_xp - xp_to_spend
        if remainder > 0:
            await self.bot.database.users.add_pending_companion_cookies(
                self.user_id, remainder
            )
        await self.bot.database.companions.add_kinship_points(
            self.user_id, self.server_id, kp_to_gain
        )

        self.pending_xp = remainder
        self.parent._pending_cookies = remainder
        self.parent.update_buttons()
        self._processing = False
        self._add_buttons()

        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        await interaction.followup.send(
            f"✨ Converted {xp_to_spend:,} XP → **{kp_to_gain:,} Kinship Point(s)**.",
            ephemeral=True,
        )

    async def buy_rune(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        pending = await self.bot.database.users.get_pending_companion_cookies(
            self.user_id
        )
        runes_to_gain = pending // self.XP_PER_RUNE
        xp_to_spend = runes_to_gain * self.XP_PER_RUNE

        if runes_to_gain <= 0:
            self._processing = False
            await interaction.followup.send(
                f"Need at least {self.XP_PER_RUNE:,} XP.", ephemeral=True
            )
            return

        all_xp = await self.bot.database.users.consume_pending_companion_cookies(
            self.user_id
        )
        remainder = all_xp - xp_to_spend
        if remainder > 0:
            await self.bot.database.users.add_pending_companion_cookies(
                self.user_id, remainder
            )
        await self.bot.database.users.modify_currency(
            self.user_id, "partnership_runes", runes_to_gain
        )

        self.pending_xp = remainder
        self.parent._pending_cookies = remainder
        self.parent.update_buttons()
        self._processing = False
        self._add_buttons()

        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        await interaction.followup.send(
            f"🔮 Converted {xp_to_spend:,} XP → **{runes_to_gain} Rune(s) of Partnership**.",
            ephemeral=True,
        )

    async def go_back(self, interaction: Interaction):
        self.parent.update_buttons()
        await interaction.response.edit_message(
            embed=self.parent.get_embed(), view=self.parent
        )


class CompanionDetailView(BaseView):
    def __init__(self, bot, user_id, companion, parent_view):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.comp = companion
        self.parent = parent_view
        self._processing = False
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        # Toggle Active
        lbl = "Set Inactive" if self.comp.is_active else "Set Active"
        style = ButtonStyle.secondary if self.comp.is_active else ButtonStyle.success
        btn_active = ui.Button(label=lbl, style=style, row=0)
        btn_active.callback = self.toggle_active
        self.add_item(btn_active)

        # Rename
        btn_rename = ui.Button(label="Rename", style=ButtonStyle.primary, row=0)
        btn_rename.callback = self.rename_modal
        self.add_item(btn_rename)

        # Reroll
        btn_reroll = ui.Button(
            label="Reroll Passive", style=ButtonStyle.primary, emoji="🎲", row=1
        )
        btn_reroll.callback = self.reroll_passive
        self.add_item(btn_reroll)

        # Balanced Engram
        btn_engram = ui.Button(
            label="Balanced Engram", style=ButtonStyle.blurple, emoji="♊", row=1
        )
        btn_engram.callback = self.open_balanced_engram
        self.add_item(btn_engram)

        # Release
        btn_release = ui.Button(label="Release", style=ButtonStyle.danger, row=1)
        btn_release.callback = self.release_confirm
        self.add_item(btn_release)

        # Back
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    def get_embed(self):
        embed = discord.Embed(title=f"{self.comp.name}", color=discord.Color.gold())
        embed.set_thumbnail(url=self.comp.image_url)

        status = "Active 🟢" if self.comp.is_active else "Inactive ⚪"
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Level", value=f"{self.comp.level}", inline=True)

        # Cleanly display Max Level
        if self.comp.level >= CompanionMechanics.MAX_LEVEL:
            embed.add_field(name="EXP", value="Max Level", inline=True)
        else:
            next_xp = CompanionMechanics.calculate_next_level_xp(self.comp.level)
            embed.add_field(name="EXP", value=f"{self.comp.exp}/{next_xp}", inline=True)

        embed.add_field(
            name="Passive",
            value=f"T{self.comp.passive_tier} **{self.comp.description}**",
            inline=False,
        )
        if self.comp.balanced_passive != "none" and self.comp.balanced_passive_tier > 0:
            embed.add_field(
                name="Balanced Passive",
                value=f"T{self.comp.balanced_passive_tier} **{self.comp.balanced_description}**",
                inline=False,
            )
        embed.set_footer(text=f"Species: {self.comp.species}")
        return embed

    @staticmethod
    def _companion_slot_cap(level: int, ascension: int) -> int:
        """Returns the active-companion slot cap based on player progression.

        Level 40  → 1 slot
        Level 80  → 2 slots
        Ascension 20+ → 3 slots
        """
        if ascension >= 20:
            return 3
        if level >= 80:
            return 2
        if level >= 40:
            return 1
        return 0  # Companions not yet unlocked

    async def toggle_active(self, interaction: Interaction):
        # Fetch current player level/ascension to determine the slot cap
        user_row = await self.bot.database.users.get(
            self.user_id, str(interaction.guild.id)
        )
        player_level = user_row["level"] if user_row else 1
        player_ascension = user_row["ascension"] if user_row else 0
        max_slots = self._companion_slot_cap(player_level, player_ascension)

        new_state = not self.comp.is_active
        if new_state and max_slots == 0:
            return await interaction.response.send_message(
                "Companions unlock at Level 40!", ephemeral=True
            )

        success = await self.bot.database.companions.set_active(
            self.user_id, self.comp.id, new_state, max_active=max_slots
        )

        if not success:
            cap_str = "1 slot (Level 40), 2 slots (Level 80), 3 slots (Ascension 20+)"
            return await interaction.response.send_message(
                f"You've reached your companion slot cap!\n{cap_str}", ephemeral=True
            )

        if new_state:
            await self.bot.database.users.initialize_companion_timer(self.user_id)

        # Update this companion object
        self.comp.is_active = new_state

        # Update parent list state locally
        for c in self.parent.companions:
            if c.id == self.comp.id:
                c.is_active = new_state
                break

        # Rebuild the parent list buttons so icons (🟢 / ⚪) match
        self.parent.update_buttons()

        # Update this detail view’s buttons (label + styles)
        self.update_buttons()

        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def rename_modal(self, interaction: Interaction):
        modal = RenameModal(self)
        await interaction.response.send_modal(modal)

    async def reroll_passive(self, interaction: Interaction):
        # 1. Check Rune Balance
        runes = await self.bot.database.users.get_currency(
            self.user_id, "partnership_runes"
        )
        if runes < 1:
            return await interaction.response.send_message(
                "You need a **Rune of Partnership** to reroll passives.", ephemeral=True
            )

        # 2. Create Confirmation Embed
        embed = discord.Embed(
            title="🎲 Reroll Companion Passive?",
            description=f"**Companion:** {self.comp.name}\n**Current:** T{self.comp.passive_tier} {self.comp.passive_type.upper()}",
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(url=self.comp.image_url)
        embed.add_field(
            name="Cost", value=f"1 Rune of Partnership\n(Owned: {runes})", inline=True
        )
        embed.add_field(
            name="Mechanics",
            value="• Guaranteed **New Passive Type**\n• **10% Chance** to Upgrade Tier",
            inline=True,
        )

        confirm_view = RerollConfirmView(self.bot, self.user_id, self.comp, runes, self)

        # 3. Swap View
        await interaction.response.edit_message(
            content=None, embed=embed, view=confirm_view
        )

    async def open_balanced_engram(self, interaction: Interaction):
        await interaction.response.defer()

        view = BalancedEngramView(self.bot, self.user_id, self.comp, self)
        await view.render(interaction)

    async def release_confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        # Distribute flat 2000 XP to each remaining active companion
        RELEASE_XP = 2000
        xp_note = ""
        try:
            active_rows = await self.bot.database.companions.get_active(self.user_id)
            recipients = [r for r in active_rows if r[0] != self.comp.id]
            if recipients:
                leveled_names = []
                overflow_xp = 0
                for row in recipients:
                    comp_id, name, cur_lvl, cur_exp = row[0], row[2], row[5], row[6]
                    cur_exp += RELEASE_XP
                    did_level = False
                    while cur_lvl < 100:
                        req = CompanionMechanics.calculate_next_level_xp(cur_lvl)
                        if cur_exp >= req:
                            cur_exp -= req
                            cur_lvl += 1
                            did_level = True
                        else:
                            break
                    if cur_lvl >= 100:
                        overflow_xp += cur_exp
                        cur_exp = 0
                    await self.bot.database.companions.update_stats(
                        comp_id, cur_lvl, cur_exp
                    )
                    if did_level:
                        leveled_names.append(f"{name} (Lv.{cur_lvl})")

                xp_note = (
                    f"\n🐾 Remaining companions each gained **{RELEASE_XP:,} XP**."
                )
                if leveled_names:
                    xp_note += f"\n🎉 **Level Up:** {', '.join(leveled_names)}"

                if overflow_xp > 0:
                    from core.companions.mastery import kp_from_overflow_xp

                    kp_earned = kp_from_overflow_xp(overflow_xp)
                    if kp_earned > 0:
                        await self.bot.database.companions.add_kinship_points(
                            self.user_id, str(interaction.guild_id), kp_earned
                        )
                        xp_note += f"\n✨ Gained **{kp_earned} Kinship Point(s)** from overflow XP."
        except Exception:
            pass

        await self.bot.database.companions.delete_companion(self.comp.id, self.user_id)

        # Remove from parent list
        self.parent.companions = [
            c for c in self.parent.companions if c.id != self.comp.id
        ]
        self.parent.update_buttons()

        temp_embed = discord.Embed(
            title="Companion Released",
            description=f"**{self.comp.name}** has returned to the wild.{xp_note}",
            color=discord.Color.orange(),
        )
        await interaction.edit_original_response(embed=temp_embed, view=None)

        await asyncio.sleep(2.0)

        await interaction.edit_original_response(
            embed=self.parent.get_embed(), view=self.parent
        )

    async def go_back(self, interaction: Interaction):
        # Rebuild parent buttons in case active states changed
        self.parent.update_buttons()
        await interaction.response.edit_message(
            embed=self.parent.get_embed(), view=self.parent
        )


class RenameModal(ui.Modal, title="Rename Companion"):
    name = ui.TextInput(label="New Name", max_length=20)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        new_name = self.name.value
        await self.parent_view.bot.database.companions.rename(
            self.parent_view.comp.id, new_name
        )
        self.parent_view.comp.name = new_name

        await interaction.response.edit_message(
            embed=self.parent_view.get_embed(), view=self.parent_view
        )
