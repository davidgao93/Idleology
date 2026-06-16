from __future__ import annotations

from typing import List

import discord
from discord import ButtonStyle, Interaction, ui

from core.images import PARTNERS_DISPATCH
from core.models import Partner
from core.partners.data import PARTNER_DATA
from core.partners.resources import _skill_display_name, _stars
from core.partners.ui import _build_partner_embed, _build_roster_embed
from core.partners.views._helpers import _TASK_LABELS, PartnerBaseView

# ---------------------------------------------------------------------------
# PartnerRosterView
# ---------------------------------------------------------------------------


class PartnerRosterView(PartnerBaseView):
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
        self._refresh()

    def build_embed(self) -> discord.Embed:
        return _build_roster_embed(self.partners, self.items)

    def _refresh(self):
        self.clear_items()

        if self.partners:
            options = []
            for rarity in (6, 5, 4):
                for p in self.partners:
                    if p.rarity != rarity:
                        continue
                    status = (
                        " ⚔️"
                        if p.is_active_combat
                        else (" 📋" if p.is_dispatched else "")
                    )
                    options.append(
                        discord.SelectOption(
                            label=f"{_stars(p.rarity)} {p.name} Lv.{p.level}{status}"[
                                :100
                            ],
                            value=str(p.partner_id),
                            description=(
                                f"ATK {p.total_attack}  DEF {p.total_defence}  HP {p.total_hp}"
                            )[:100],
                        )
                    )

            if options:
                select = ui.Select(
                    placeholder="Choose a partner to manage…",
                    options=options[:25],
                )
                select.callback = self._on_select
                self.add_item(select)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _on_select(self, interaction: Interaction):
        from core.partners.views.detail_view import PartnerDetailView

        partner_id = int(interaction.data["values"][0])
        partner = next((p for p in self.partners if p.partner_id == partner_id), None)
        if not partner:
            await interaction.response.defer()
            return
        detail = PartnerDetailView(self.bot, self.user_id, partner, self.items, self)
        detail.message = self.message
        await interaction.response.edit_message(
            embed=_build_partner_embed(partner, self.items), view=detail
        )

    async def _open_boss_raid(self, interaction: Interaction):
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
            self.bot, self.user_id, server_id, self.partners, back_view=self,
            player_level=player_level,
        )
        form_view.message = self.message
        embed = _build_form_embed(form_view.slots, self.partners)
        await interaction.edit_original_response(embed=embed, view=form_view)

    async def _back(self, interaction: Interaction):
        await interaction.response.defer()
        embed, items, partners = await self.main_view._fetch_fresh_data()
        await interaction.edit_original_response(embed=embed, view=self.main_view)
        self.stop()


# ---------------------------------------------------------------------------
# PartnerMainView  (entry point)
# ---------------------------------------------------------------------------


class PartnerMainView(PartnerBaseView):
    def __init__(self, bot, user_id: str):
        super().__init__(bot, user_id)

    async def _fetch_fresh_data(self):
        """Re-fetch items and partners from DB. Returns (embed, items, partners)."""
        items = await self.bot.database.partners.get_items(self.user_id)
        rows = await self.bot.database.partners.get_owned(self.user_id)
        partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
        ]
        return self.build_embed(items, partners), items, partners

    def build_embed(self, items: dict, partners: List[Partner] = None) -> discord.Embed:
        embed = discord.Embed(title="🤝 Partners", colour=0xBEBEFE)
        embed.add_field(
            name="Welcome Traveler!",
            value=(
                "Recruit new Partners with 🎫 Guild Tickets!\n"
                "They can join you for ⚔️ Combat...\n"
                "Or 📋 Dispatch them for passive rewards, the choice is yours.\n"
                "Best of luck, adventurer!"
            ),
            inline=True,
        )
        active_combat = None
        active_dispatch = None
        boss_party: list = []
        if partners:
            active_combat = next((p for p in partners if p.is_active_combat), None)
            active_dispatch = next(
                (
                    p
                    for p in partners
                    if p.is_dispatched
                    and p.dispatch_task
                    and p.dispatch_task != "boss_party"
                ),
                None,
            )
            boss_party = [
                p
                for p in partners
                if p.is_dispatched and p.dispatch_task == "boss_party"
            ]

        if active_combat:
            skill_names = [
                _skill_display_name(key)
                for key, lvl in active_combat.combat_skills
                if key
            ]
            skills_text = (
                ", ".join(
                    f"{n} Lv.{lvl}"
                    for (key, lvl), n in zip(active_combat.combat_skills, skill_names)
                    if key
                )
                or "No skills"
            )
            embed.add_field(
                name="⚔️ Active Combat Partner",
                value=(
                    f"{_stars(active_combat.rarity)} **{active_combat.name}** Lv.{active_combat.level}\n"
                    f"⚔️ {active_combat.total_attack} ATK  "
                    f"🛡️ {active_combat.total_defence} DEF  "
                    f"❤️ {active_combat.total_hp} HP\n"
                    f"{skills_text}"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="⚔️ Active Combat Partner",
                value="*None — select a partner from the Roster*",
                inline=False,
            )

        if active_dispatch:
            from core.partners.dispatch import elapsed_hours, get_cap_hours

            cap = get_cap_hours(active_dispatch)
            elapsed = (
                elapsed_hours(active_dispatch.dispatch_start_time)
                if active_dispatch.dispatch_start_time
                else 0.0
            )
            task_label = _TASK_LABELS.get(
                active_dispatch.dispatch_task or "",
                active_dispatch.dispatch_task or "?",
            )
            embed.add_field(
                name="📋 Active Dispatch",
                value=(
                    f"{_stars(active_dispatch.rarity)} **{active_dispatch.name}** on **{task_label}**\n"
                    f"⏱️ {min(elapsed, cap):.1f}/{cap:.0f}h accumulated"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📋 Active Dispatch",
                value="*None — use Dispatch to send a partner on a mission*",
                inline=False,
            )

        if boss_party:
            from core.partners.dispatch import BOSS_PARTY_DURATION_HOURS, elapsed_hours

            bp_first = boss_party[0]
            elapsed = (
                elapsed_hours(bp_first.dispatch_start_time)
                if bp_first.dispatch_start_time
                else 0.0
            )
            progress_pct = min(100, int(elapsed / BOSS_PARTY_DURATION_HOURS * 100))
            names = " | ".join(f"{_stars(p.rarity)} {p.name}" for p in boss_party)
            if progress_pct >= 100:
                progress_str = "✅ Raid Complete! Collect your rewards."
            else:
                progress_str = f"⏱️ {progress_pct}% complete"
            embed.add_field(
                name="🔱 Boss Raid",
                value=f"{names}\n{progress_str}",
                inline=False,
            )

        embed.add_field(
            name="💼 Inventory",
            value=(
                f"🎫 **{items.get('guild_tickets', 0)}** Guild Tickets\n"
                f"⚔️ **{items.get('combat_skill_shards', 0)}** Combat Shards\n"
                f"📋 **{items.get('dispatch_skill_shards', 0)}** Dispatch Shards"
            ),
            inline=True,
        )
        embed.set_thumbnail(url=PARTNERS_DISPATCH)
        return embed

    @ui.button(label="Roster", style=ButtonStyle.primary, emoji="📋")
    async def roster_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        rows = await self.bot.database.partners.get_owned(self.user_id)
        items = await self.bot.database.partners.get_items(self.user_id)
        if not rows:
            await interaction.followup.send(
                "You have no partners yet! Use the **Pull** button to recruit some.",
                ephemeral=True,
            )
            return
        partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
        ]
        view = PartnerRosterView(self.bot, self.user_id, partners, items, self)
        view.message = self.message
        embed = _build_roster_embed(partners, items)
        await interaction.edit_original_response(embed=embed, view=view)

    @ui.button(label="Dispatch", style=ButtonStyle.secondary, emoji="🗺️")
    async def dispatch_btn(self, interaction: Interaction, button: ui.Button):
        from core.partners.views.dispatch_view import DispatchView

        await interaction.response.defer()
        rows = await self.bot.database.partners.get_owned(self.user_id)
        items = await self.bot.database.partners.get_items(self.user_id)
        if not rows:
            await interaction.followup.send(
                "You have no partners yet! Use the **Pull** button to recruit some.",
                ephemeral=True,
            )
            return
        partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
        ]
        view = DispatchView(self.bot, self.user_id, partners, items, self)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    @ui.button(label="Pull", style=ButtonStyle.success, emoji="🎫")
    async def pull_btn(self, interaction: Interaction, button: ui.Button):
        from core.partners.views.gacha_view import PullView

        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )

    @ui.button(label="Affinity", style=ButtonStyle.secondary, emoji="💞", row=1)
    async def affinity_btn(self, interaction: Interaction, button: ui.Button):
        from core.partners.views.affinity_view import AffinityView

        await interaction.response.defer()
        rows = await self.bot.database.partners.get_owned(self.user_id)
        items = await self.bot.database.partners.get_items(self.user_id)
        partners_6star = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA and PARTNER_DATA[row[2]]["rarity"] == 6
        ]
        view = AffinityView(self.bot, self.user_id, partners_6star, items, self)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    @ui.button(label="Close", style=ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: Interaction, button: ui.Button):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()
