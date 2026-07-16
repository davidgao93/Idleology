from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import discord
from discord import ButtonStyle, Interaction, ui

from core.emojis import UBER_EMOJI
from core.images import PARTNERS_BOSS_PARTY, PARTNERS_HUB
from core.models import Partner
from core.partners.data import PARTNER_DATA
from core.partners.mechanics import get_sig_dispatch_effect_text, get_skill_effect_text
from core.partners.resources import (
    _rarity_colour,
    _sig_display_name,
    _skill_display_name,
    _stars,
)
from core.partners.ui import _build_partner_embed
from core.partners.views._helpers import (
    _TASK_LABELS,
    PartnerBaseView,
    _apply_dispatch_rewards,
)

# ---------------------------------------------------------------------------
# DispatchReplaceConfirmView
# ---------------------------------------------------------------------------


class DispatchReplaceConfirmView(PartnerBaseView):
    """Asks the player to collect the current dispatch and replace it with a new partner."""

    def __init__(
        self,
        bot,
        user_id: str,
        new_partner: Partner,
        active_partner: Partner,
        items: dict,
        detail_view,
    ):
        super().__init__(bot, user_id)
        self.new_partner = new_partner
        self.active_partner = active_partner
        self.items = items
        self.detail_view = detail_view

        collect_btn = ui.Button(label="Collect & Dispatch", style=ButtonStyle.success)
        collect_btn.callback = self._collect_and_dispatch
        self.add_item(collect_btn)

        cancel_btn = ui.Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    def build_embed(self) -> discord.Embed:
        from core.partners.dispatch import elapsed_hours, get_cap_hours

        ap = self.active_partner
        cap = get_cap_hours(ap)
        elapsed = (
            elapsed_hours(ap.dispatch_start_time) if ap.dispatch_start_time else 0.0
        )
        task_label = _TASK_LABELS.get(ap.dispatch_task or "", ap.dispatch_task or "?")
        return discord.Embed(
            title="📋 Replace Dispatch?",
            description=(
                f"{_stars(ap.rarity)} **{ap.name}** is currently on **{task_label}** "
                f"({min(elapsed, cap):.1f}/{cap:.0f}h accumulated).\n\n"
                f"Collect their rewards and send "
                f"{_stars(self.new_partner.rarity)} **{self.new_partner.name}** instead?"
            ),
            colour=_rarity_colour(self.new_partner.rarity),
        )

    async def _collect_and_dispatch(self, interaction: Interaction):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        await _apply_dispatch_rewards(
            self.bot, self.user_id, server_id, self.active_partner
        )
        self.items = await self.bot.database.partners.get_items(self.user_id)
        view = DispatchTaskSelectView(
            self.bot, self.user_id, self.new_partner, self.items, self.detail_view
        )
        view.message = self.message
        embed = discord.Embed(
            title=f"Dispatch — {self.new_partner.name}",
            description="Choose a task to dispatch this partner on.",
            colour=_rarity_colour(self.new_partner.rarity),
        )
        embed.set_image(url=f"{self.new_partner.image_url}")
        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()

    async def _cancel(self, interaction: Interaction):
        embed = _build_partner_embed(self.new_partner, self.items)
        self.detail_view._update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.detail_view)
        self.stop()


# ---------------------------------------------------------------------------
# DispatchTaskSelectView
# ---------------------------------------------------------------------------


class DispatchTaskSelectView(PartnerBaseView):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, detail_view):
        super().__init__(bot, user_id)
        self.partner = partner
        self.items = items
        self.detail_view = detail_view
        for task, label in _TASK_LABELS.items():
            btn = ui.Button(label=label, style=ButtonStyle.secondary)
            btn.callback = self._make_callback(task)
            self.add_item(btn)
        back_btn = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._cancel
        self.add_item(back_btn)

    def _make_callback(self, task: str):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            await self.bot.database.partners.set_dispatch(
                self.user_id, self.partner.partner_id, task, now_str
            )
            self.partner.is_dispatched = True
            self.partner.dispatch_task = task
            self.partner.dispatch_start_time = now_str
            self.detail_view._update_buttons()
            embed = _build_partner_embed(self.partner, self.items)
            embed.colour = discord.Colour.blue()
            embed.description = (
                embed.description or ""
            ) + f"\n\n📋 Dispatched on **{task}**!"
            await interaction.edit_original_response(embed=embed, view=self.detail_view)
            self.stop()

        return callback

    async def _cancel(self, interaction: Interaction):
        embed = _build_partner_embed(self.partner, self.items)
        await interaction.response.edit_message(embed=embed, view=self.detail_view)
        self.stop()


# ---------------------------------------------------------------------------
# DispatchView
# ---------------------------------------------------------------------------


class DispatchView(PartnerBaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        partners: List[Partner],
        items: dict,
        main_view,
    ):
        super().__init__(bot, user_id)
        self.partners = partners
        self.items = items
        self.main_view = main_view
        self.selected_partner: Optional[Partner] = None
        self._processing = False
        self._refresh()

    def _get_active_dispatch(self) -> Optional[Partner]:
        return next(
            (
                p
                for p in self.partners
                if p.is_dispatched
                and p.dispatch_task
                and p.dispatch_task != "boss_party"
            ),
            None,
        )

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="📋 Dispatch", colour=0x8BC34A)
        embed.set_thumbnail(url=PARTNERS_HUB)
        active = self._get_active_dispatch()
        if active:
            from core.partners.dispatch import elapsed_hours, get_cap_hours

            cap = get_cap_hours(active)
            elapsed = (
                elapsed_hours(active.dispatch_start_time)
                if active.dispatch_start_time
                else 0.0
            )
            task_label = _TASK_LABELS.get(
                active.dispatch_task or "", active.dispatch_task or "?"
            )
            embed.add_field(
                name="⏱️ Currently Dispatched",
                value=(
                    f"{_stars(active.rarity)} **{active.name}** on **{task_label}**\n"
                    f"⏱️ {min(elapsed, cap):.1f}/{cap:.0f}h accumulated"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="⏱️ Currently Dispatched",
                value="*No active dispatch*",
                inline=False,
            )

        if self.selected_partner:
            p = self.selected_partner
            lines = []
            for i, (key, lvl) in enumerate(p.dispatch_skills, 1):
                if key:
                    lines.append(
                        f"`S{i}` **{_skill_display_name(key)}** Lv.{lvl} — {get_skill_effect_text(key, lvl)}"
                    )
                else:
                    lines.append(f"`S{i}` *Empty*")
            if p.rarity >= 6 and p.sig_dispatch_key:
                lines.append(
                    f"`SIG` **{_sig_display_name(p.sig_dispatch_key)}** Lv.{p.sig_dispatch_lvl} — "
                    f"{get_sig_dispatch_effect_text(p.partner_id, p.sig_dispatch_lvl)}"
                )
            embed.add_field(
                name=f"Selected: {_stars(p.rarity)} {p.name} Lv.{p.level}",
                value=(
                    f"⚔️ {p.total_attack} ATK  🛡️ {p.total_defence} DEF  ❤️ {p.total_hp} HP\n"
                    + ("\n".join(lines) if lines else "*No dispatch skills*")
                ),
                inline=False,
            )
            embed.set_thumbnail(url=f"{p.image_url}")

        embed.set_footer(
            text=(
                f"{self.items.get('guild_tickets', 0)} tickets  |  "
                f"📋 {self.items.get('dispatch_skill_shards', 0)} dispatch shards"
            )
        )
        return embed

    def _refresh(self):
        self.clear_items()
        eligible = [p for p in self.partners if not p.is_active_combat]
        if eligible:
            options = []
            for rarity in (6, 5, 4):
                for p in eligible:
                    if p.rarity != rarity:
                        continue
                    if p.dispatch_task == "boss_party":
                        status = " 🔱"
                    elif p.is_dispatched:
                        status = " 📋"
                    else:
                        status = ""
                    if p.dispatch_task == "boss_party":
                        desc = "🔱 Boss Raid"
                    elif p.is_dispatched:
                        desc = f"On: {_TASK_LABELS.get(p.dispatch_task or '', p.dispatch_task or '?')}"
                    else:
                        desc = "Idle"
                    options.append(
                        discord.SelectOption(
                            label=f"{_stars(p.rarity)} {p.name} Lv.{p.level}{status}"[
                                :100
                            ],
                            value=str(p.partner_id),
                            description=desc[:100],
                        )
                    )
            if options:
                select = ui.Select(
                    placeholder="Select a partner to dispatch…",
                    options=options[:25],
                )
                select.callback = self._on_select
                self.add_item(select)
        sp = self.selected_partner
        active = self._get_active_dispatch()
        if sp is not None and sp.dispatch_task == "boss_party":
            collect_btn = ui.Button(
                label="Collect", style=ButtonStyle.primary, row=1, disabled=True
            )
            self.add_item(collect_btn)
        elif sp and active and sp.partner_id != active.partner_id:
            replace_btn = ui.Button(
                label="Replace Dispatch", style=ButtonStyle.success, row=1
            )
            replace_btn.callback = self._replace
            self.add_item(replace_btn)
        elif sp is not None and sp.is_dispatched:
            reassign_btn = ui.Button(label="Reassign", style=ButtonStyle.success, row=1)
            reassign_btn.callback = self._reassign
            self.add_item(reassign_btn)
            unassign_btn = ui.Button(label="Unassign", style=ButtonStyle.danger, row=1)
            unassign_btn.callback = self._unassign
            self.add_item(unassign_btn)
            collect_btn = ui.Button(label="Collect", style=ButtonStyle.primary, row=1)
            collect_btn.callback = self._collect
            self.add_item(collect_btn)
        else:
            another_dispatched = active is not None and (
                sp is None or active.partner_id != sp.partner_id
            )
            confirm_btn = ui.Button(label="Confirm", style=ButtonStyle.success, row=1)
            confirm_btn.callback = self._confirm
            confirm_btn.disabled = (
                sp is None or sp.is_active_combat or another_dispatched
            )
            self.add_item(confirm_btn)
            collect_btn = ui.Button(label="Collect", style=ButtonStyle.primary, row=1)
            collect_btn.callback = self._collect
            collect_btn.disabled = True
            self.add_item(collect_btn)
        boss_raid_btn = ui.Button(
            label="Boss Raid", style=ButtonStyle.danger, emoji=UBER_EMOJI, row=2
        )
        boss_raid_btn.callback = self._boss_raid
        self.add_item(boss_raid_btn)
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _replace(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        active = self._get_active_dispatch()
        if active:
            server_id = str(interaction.guild.id)
            await _apply_dispatch_rewards(self.bot, self.user_id, server_id, active)
        rows = await self.bot.database.partners.get_owned(self.user_id)
        self.partners = [
            Partner.from_row(row, PARTNER_DATA[row["partner_id"]])
            for row in rows
            if row["partner_id"] in PARTNER_DATA
        ]
        self.items = await self.bot.database.partners.get_items(self.user_id)
        sp_id = self.selected_partner.partner_id if self.selected_partner else None
        self.selected_partner = next(
            (p for p in self.partners if p.partner_id == sp_id), None
        )
        if self.selected_partner:
            task_view = DispatchTaskConfirmView(
                self.bot,
                self.user_id,
                self.selected_partner,
                self.items,
                self,
                self.partners,
            )
            task_view.message = self.message
            embed = discord.Embed(
                title=f"📋 Dispatch — {self.selected_partner.name}",
                description="Previous dispatch rewards collected.\nChoose a task for the new partner:",
                colour=_rarity_colour(self.selected_partner.rarity),
            )
            embed.set_image(url=f"{self.selected_partner.image_url}")
            await interaction.edit_original_response(embed=embed, view=task_view)
        else:
            self._refresh()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

    async def _boss_raid(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        from core.partners.views_boss_party import (
            BossPartyFormView,
            BossPartyProgressView,
            _build_form_embed,
            _build_progress_embed,
        )

        server_id = str(interaction.guild.id)
        user_data = await self.bot.database.users.get(self.user_id, server_id)
        player_level = user_data["level"] if user_data else 1

        party_row = await self.bot.database.boss_party.get_active(
            self.user_id, server_id
        )
        if party_row:
            partner_ids = {
                party_row["attacker_id"],
                party_row["tank_id"],
                party_row["healer_id"],
            }
            partners_by_id = {
                p.partner_id: p for p in self.partners if p.partner_id in partner_ids
            }
            progress_view = BossPartyProgressView(
                self.bot,
                self.user_id,
                server_id,
                party_row,
                partners_by_id,
                back_view=self,
                player_level=player_level,
            )
            progress_view.message = self.message
            embed, _ = _build_progress_embed(party_row, partners_by_id)
            await interaction.edit_original_response(embed=embed, view=progress_view)
            return

        form_view = BossPartyFormView(
            self.bot,
            self.user_id,
            server_id,
            self.partners,
            back_view=self,
            player_level=player_level,
        )
        form_view.message = self.message
        embed = _build_form_embed(form_view.slots, self.partners)
        embed.set_thumbnail(url=PARTNERS_BOSS_PARTY)
        await interaction.edit_original_response(embed=embed, view=form_view)

    async def _on_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        partner_id = int(interaction.data["values"][0])
        self.selected_partner = next(
            (p for p in self.partners if p.partner_id == partner_id), None
        )
        self._refresh()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)
        self._processing = False

    async def _confirm(self, interaction: Interaction):
        sp = self.selected_partner
        if not sp:
            await interaction.response.send_message(
                "No partner selected.", ephemeral=True
            )
            return

        active = self._get_active_dispatch()
        if active and active.partner_id != sp.partner_id:
            await interaction.response.send_message(
                f"**{active.name}** is already on dispatch. Collect their rewards before sending a new partner.",
                ephemeral=True,
            )
            return

        view = DispatchTaskConfirmView(
            self.bot, self.user_id, sp, self.items, self, self.partners
        )
        view.message = self.message
        embed = discord.Embed(
            title=f"📋 Dispatch — {sp.name}",
            description="Choose a task:",
            colour=_rarity_colour(sp.rarity),
        )
        embed.set_image(url=f"{self.selected_partner.image_url}")
        await interaction.response.edit_message(embed=embed, view=view)

    async def _collect(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        sp = self.selected_partner
        if not sp or not sp.is_dispatched:
            await interaction.response.send_message(
                "Selected partner is not dispatched.", ephemeral=True
            )
            return
        self._processing = True
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        lines = await _apply_dispatch_rewards(self.bot, self.user_id, server_id, sp)

        rows = await self.bot.database.partners.get_owned(self.user_id)
        self.partners = [
            Partner.from_row(row, PARTNER_DATA[row["partner_id"]])
            for row in rows
            if row["partner_id"] in PARTNER_DATA
        ]
        self.items = await self.bot.database.partners.get_items(self.user_id)
        self.selected_partner = next(
            (p for p in self.partners if p.partner_id == sp.partner_id), None
        )
        self._refresh()

        embed = self.build_embed()
        embed.add_field(
            name="📋 Dispatch Rewards",
            value="\n".join(lines) or "Nothing yet!",
            inline=False,
        )
        await interaction.edit_original_response(embed=embed, view=self)
        self._processing = False

    async def _unassign(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        sp = self.selected_partner
        if not sp or not sp.is_dispatched:
            await interaction.response.send_message(
                "Selected partner is not dispatched.", ephemeral=True
            )
            return
        self._processing = True
        await interaction.response.defer()
        await self.bot.database.partners.clear_dispatch(self.user_id, sp.partner_id)

        rows = await self.bot.database.partners.get_owned(self.user_id)
        self.partners = [
            Partner.from_row(row, PARTNER_DATA[row["partner_id"]])
            for row in rows
            if row["partner_id"] in PARTNER_DATA
        ]
        self.items = await self.bot.database.partners.get_items(self.user_id)
        self.selected_partner = next(
            (p for p in self.partners if p.partner_id == sp.partner_id), None
        )
        self._refresh()

        embed = self.build_embed()
        embed.add_field(
            name="✅ Unassigned",
            value=f"**{sp.name}** has been recalled. Any accumulated rewards were forfeited.",
            inline=False,
        )
        await interaction.edit_original_response(embed=embed, view=self)
        self._processing = False

    async def _reassign(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        sp = self.selected_partner
        if not sp or not sp.is_dispatched:
            await interaction.response.send_message(
                "Selected partner is not dispatched.", ephemeral=True
            )
            return
        self._processing = True
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        lines = await _apply_dispatch_rewards(self.bot, self.user_id, server_id, sp)

        rows = await self.bot.database.partners.get_owned(self.user_id)
        self.partners = [
            Partner.from_row(row, PARTNER_DATA[row["partner_id"]])
            for row in rows
            if row["partner_id"] in PARTNER_DATA
        ]
        self.items = await self.bot.database.partners.get_items(self.user_id)
        self.selected_partner = next(
            (p for p in self.partners if p.partner_id == sp.partner_id), None
        )

        task_view = DispatchTaskConfirmView(
            self.bot,
            self.user_id,
            self.selected_partner or sp,
            self.items,
            self,
            self.partners,
        )
        task_view.message = self.message
        embed = discord.Embed(
            title=f"📋 Reassign — {sp.name}",
            description=(
                "Rewards collected — choose a new task:\n\n" + "\n".join(lines)
            ),
            colour=_rarity_colour(sp.rarity),
        )
        embed.set_thumbnail(url=PARTNERS_HUB)
        await interaction.edit_original_response(embed=embed, view=task_view)

    async def _back(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        embed, items, partners = await self.main_view._fetch_fresh_data()
        await interaction.edit_original_response(embed=embed, view=self.main_view)
        self.stop()


# ---------------------------------------------------------------------------
# DispatchTaskConfirmView
# ---------------------------------------------------------------------------


class DispatchTaskConfirmView(PartnerBaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        partner: Partner,
        items: dict,
        dispatch_view: DispatchView,
        partners: List[Partner],
    ):
        super().__init__(bot, user_id)
        self.partner = partner
        self.items = items
        self.dispatch_view = dispatch_view
        self.partners = partners

        for task, label in _TASK_LABELS.items():
            btn = ui.Button(label=label, style=ButtonStyle.secondary)
            btn.callback = self._make_callback(task)
            self.add_item(btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def _make_callback(self, task: str):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            await self.bot.database.partners.set_dispatch(
                self.user_id, self.partner.partner_id, task, now_str
            )
            for p in self.partners:
                p.is_dispatched = False
            self.partner.is_dispatched = True
            self.partner.dispatch_task = task
            self.partner.dispatch_start_time = now_str

            self.dispatch_view.partners = self.partners
            self.dispatch_view.selected_partner = self.partner
            self.dispatch_view._processing = False
            self.dispatch_view._refresh()

            embed = self.dispatch_view.build_embed()
            embed.colour = discord.Colour.blue()
            await interaction.edit_original_response(
                embed=embed, view=self.dispatch_view
            )
            self.stop()

        return callback

    async def _back(self, interaction: Interaction):
        self.dispatch_view._processing = False
        await interaction.response.edit_message(
            embed=self.dispatch_view.build_embed(), view=self.dispatch_view
        )
        self.stop()
