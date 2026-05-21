from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.images import PARTNERS_FEMALE, PARTNERS_MALE
from core.models import Partner
from core.partners.data import PARTNER_DATA
from core.partners.mechanics import (
    MAX_COMBAT_SKILL_LEVEL,
    MAX_DISPATCH_SKILL_LEVEL,
    MAX_SIG_LEVEL,
    REROLL_COMBAT_COST,
    REROLL_DISPATCH_COST,
    get_combat_upgrade_cost,
    get_dispatch_upgrade_cost,
    get_sig_combat_effect_text,
    get_sig_dispatch_effect_text,
    get_sig_upgrade_cost,
    get_skill_effect_text,
    reroll_skill,
)
from core.partners.resources import _rarity_colour, _sig_display_name, _skill_display_name
from core.partners.ui import _build_partner_embed
from core.partners.views._helpers import PartnerBaseView, _apply_dispatch_rewards

_SKILL_SLOT_COLS = {
    "combat": [
        ("combat_slot_1", "combat_slot_1_lvl"),
        ("combat_slot_2", "combat_slot_2_lvl"),
        ("combat_slot_3", "combat_slot_3_lvl"),
    ],
    "dispatch": [
        ("dispatch_slot_1", "dispatch_slot_1_lvl"),
        ("dispatch_slot_2", "dispatch_slot_2_lvl"),
        ("dispatch_slot_3", "dispatch_slot_3_lvl"),
    ],
}


# ---------------------------------------------------------------------------
# PartnerSkillsView
# ---------------------------------------------------------------------------


class PartnerSkillsView(PartnerBaseView):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, detail_view):
        super().__init__(bot, user_id)
        self.partner = partner
        self.items = items
        self.detail_view = detail_view
        self.mode = "combat"  # "combat" or "dispatch"
        self._refresh_buttons()

    def build_embed(self) -> discord.Embed:
        p = self.partner
        embed = discord.Embed(
            title=f"⚙️ Skills — {p.name}",
            colour=_rarity_colour(p.rarity),
        )
        if self.mode == "combat":
            embed.set_thumbnail(url=PARTNERS_MALE)
        else:
            embed.set_thumbnail(url=PARTNERS_FEMALE)

        shards_key = (
            "combat_skill_shards" if self.mode == "combat" else "dispatch_skill_shards"
        )
        shards = self.items.get(shards_key, 0)
        reroll_cost = (
            REROLL_COMBAT_COST if self.mode == "combat" else REROLL_DISPATCH_COST
        )

        header = f"**{shards}** {self.mode} shards  |  Reroll costs **{reroll_cost}** shards"
        if p.rarity >= 6:
            char_shards = self.items.get("char_shards", 0)
            header += f"  |  🔷 **{char_shards}** char shards"
        lines = [header]

        slots = p.combat_skills if self.mode == "combat" else p.dispatch_skills
        max_lvl = (
            MAX_COMBAT_SKILL_LEVEL
            if self.mode == "combat"
            else MAX_DISPATCH_SKILL_LEVEL
        )

        for i, (key, lvl) in enumerate(slots, 1):
            if key:
                cost = (
                    get_combat_upgrade_cost(lvl)
                    if self.mode == "combat"
                    else get_dispatch_upgrade_cost(lvl)
                )
                cost_str = f" | Upgrade: **{cost}** shards" if cost else " | **MAX**"
                lines.append(
                    f"`S{i}` **{_skill_display_name(key)}** Lv.{lvl}/{max_lvl} — "
                    f"{get_skill_effect_text(key, lvl)}{cost_str}"
                )
            else:
                lines.append(f"`S{i}` *Empty*")

        # Signature skill section (6★ only)
        if p.rarity >= 6:
            if self.mode == "combat" and p.sig_combat_key:
                sig_lvl = p.sig_combat_lvl
                sig_cost = get_sig_upgrade_cost(sig_lvl)
                cost_str = f" | Upgrade: **{sig_cost}** 🔷" if sig_cost else " | **MAX**"
                if sig_lvl > 0:
                    lines.append(
                        f"`SIG` **{_sig_display_name(p.sig_combat_key)}** Lv.{sig_lvl}/{MAX_SIG_LEVEL} — "
                        f"{get_sig_combat_effect_text(p.partner_id, sig_lvl)}{cost_str}"
                    )
                else:
                    lines.append(
                        f"`SIG` **{_sig_display_name(p.sig_combat_key)}** — *Locked*{cost_str}"
                    )
            elif self.mode == "dispatch" and p.sig_dispatch_key:
                sig_lvl = p.sig_dispatch_lvl
                sig_cost = get_sig_upgrade_cost(sig_lvl)
                cost_str = f" | Upgrade: **{sig_cost}** 🔷" if sig_cost else " | **MAX**"
                if sig_lvl > 0:
                    lines.append(
                        f"`SIG` **{_sig_display_name(p.sig_dispatch_key)}** Lv.{sig_lvl}/{MAX_SIG_LEVEL} — "
                        f"{get_sig_dispatch_effect_text(p.partner_id, sig_lvl)}{cost_str}"
                    )
                else:
                    lines.append(
                        f"`SIG` **{_sig_display_name(p.sig_dispatch_key)}** — *Locked*{cost_str}"
                    )

        embed.description = "\n\n".join(lines)
        return embed

    def _refresh_buttons(self):
        self.clear_items()

        slots = (
            self.partner.combat_skills
            if self.mode == "combat"
            else self.partner.dispatch_skills
        )
        col_pairs = _SKILL_SLOT_COLS[self.mode]
        max_lvl = (
            MAX_COMBAT_SKILL_LEVEL
            if self.mode == "combat"
            else MAX_DISPATCH_SKILL_LEVEL
        )

        # Row 0: Upgrade buttons for regular skills (only non-maxed slots)
        for i, (key, lvl) in enumerate(slots):
            key_col, lvl_col = col_pairs[i]
            if key and lvl < max_lvl:
                upgrade_btn = ui.Button(
                    label=f"Upgrade S{i + 1}", style=ButtonStyle.primary, row=0
                )
                upgrade_btn.callback = self._make_upgrade(i, key_col, lvl_col, key, lvl)
                self.add_item(upgrade_btn)

        # Row 0: Signature upgrade button (6★ only, when sig is below max)
        if self.partner.rarity >= 6:
            sig_lvl = (
                self.partner.sig_combat_lvl
                if self.mode == "combat"
                else self.partner.sig_dispatch_lvl
            )
            sig_key = (
                self.partner.sig_combat_key
                if self.mode == "combat"
                else self.partner.sig_dispatch_key
            )
            if sig_key and sig_lvl < MAX_SIG_LEVEL:
                sig_cost = get_sig_upgrade_cost(sig_lvl)
                label = (
                    f"{'Unlock' if sig_lvl == 0 else 'Upgrade'} SIG ({sig_cost} 🔷)"
                )
                sig_btn = ui.Button(label=label, style=ButtonStyle.blurple, row=0)
                sig_btn.callback = self._make_sig_upgrade(sig_lvl)
                self.add_item(sig_btn)

        # Row 1: Reroll buttons for regular skills
        for i, (key, _) in enumerate(slots):
            key_col, lvl_col = col_pairs[i]
            reroll_btn = ui.Button(
                label=f"Reroll S{i + 1}", style=ButtonStyle.secondary, row=1
            )
            reroll_btn.callback = self._make_reroll(i, key_col, lvl_col)
            self.add_item(reroll_btn)

        # Row 2: Mode toggle + Back
        toggle_label = "Dispatch Skills" if self.mode == "combat" else "Combat Skills"
        toggle_btn = ui.Button(label=toggle_label, style=ButtonStyle.secondary, row=2)
        toggle_btn.callback = self._toggle_mode
        self.add_item(toggle_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def _make_upgrade(
        self, slot_idx: int, key_col: str, lvl_col: str, key: str, lvl: int
    ):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            if self.mode == "combat":
                cost = get_combat_upgrade_cost(lvl)
                ok = await self.bot.database.partners.spend_combat_shards(
                    self.user_id, cost
                )
            else:
                cost = get_dispatch_upgrade_cost(lvl)
                ok = await self.bot.database.partners.spend_dispatch_shards(
                    self.user_id, cost
                )
            if not ok:
                await interaction.followup.send("Not enough shards!", ephemeral=True)
                return
            new_lvl = lvl + 1
            await self.bot.database.partners.update_skill_level(
                self.user_id, self.partner.partner_id, lvl_col, new_lvl
            )
            setattr(self.partner, lvl_col, new_lvl)
            self.items = await self.bot.database.partners.get_items(self.user_id)
            self._refresh_buttons()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        return callback

    def _make_sig_upgrade(self, sig_lvl: int):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            cost = get_sig_upgrade_cost(sig_lvl)
            if cost is None:
                await interaction.followup.send(
                    "Signature is already at max level!", ephemeral=True
                )
                return
            ok = await self.bot.database.partners.spend_shard(self.user_id, 0, cost)
            if not ok:
                await interaction.followup.send(
                    "Not enough character shards!", ephemeral=True
                )
                return
            new_lvl = sig_lvl + 1
            lvl_col = "sig_combat_lvl" if self.mode == "combat" else "sig_dispatch_lvl"
            await self.bot.database.partners.update_skill_level(
                self.user_id, self.partner.partner_id, lvl_col, new_lvl
            )
            if self.mode == "combat":
                self.partner.sig_combat_lvl = new_lvl
            else:
                self.partner.sig_dispatch_lvl = new_lvl
            self.items = await self.bot.database.partners.get_items(self.user_id)
            self._refresh_buttons()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        return callback

    def _make_reroll(self, slot_idx: int, key_col: str, lvl_col: str):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            if self.mode == "combat":
                ok = await self.bot.database.partners.spend_combat_shards(
                    self.user_id, REROLL_COMBAT_COST
                )
            else:
                ok = await self.bot.database.partners.spend_dispatch_shards(
                    self.user_id, REROLL_DISPATCH_COST
                )
            if not ok:
                await interaction.followup.send("Not enough shards!", ephemeral=True)
                return
            slots = (
                self.partner.combat_skills
                if self.mode == "combat"
                else self.partner.dispatch_skills
            )
            slot_keys = [key for key, _ in slots]
            new_key = reroll_skill(self.mode, self.partner.rarity, slot_keys)
            await self.bot.database.partners.update_skill_slot(
                self.user_id,
                self.partner.partner_id,
                key_col,
                new_key,
                lvl_col,
                1,
            )
            setattr(self.partner, key_col, new_key)
            setattr(self.partner, lvl_col, 1)
            self.items = await self.bot.database.partners.get_items(self.user_id)
            self._refresh_buttons()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        return callback

    async def _toggle_mode(self, interaction: Interaction):
        self.mode = "dispatch" if self.mode == "combat" else "combat"
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _back(self, interaction: Interaction):
        embed = _build_partner_embed(self.partner, self.items)
        self.detail_view._update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.detail_view)
        self.stop()


# ---------------------------------------------------------------------------
# PartnerDetailView
# ---------------------------------------------------------------------------


class PartnerDetailView(PartnerBaseView):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, roster_view):
        super().__init__(bot, user_id)
        self.partner = partner
        self.items = items
        self.roster_view = roster_view
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        p = self.partner

        if p.is_active_combat:
            btn = ui.Button(
                label="✅ Active (Click to Remove)", style=ButtonStyle.success
            )
            btn.callback = self._deactivate
        else:
            btn = ui.Button(label="Set Active Combat", style=ButtonStyle.primary)
            btn.callback = self._set_active
        self.add_item(btn)

        skills_btn = ui.Button(
            label="Manage Skills", style=ButtonStyle.secondary, emoji="⚙️"
        )
        skills_btn.callback = self._open_skills
        self.add_item(skills_btn)

        from core.partners.mechanics import portrait_unlocked

        if p.rarity >= 6 and portrait_unlocked(
            p.affinity_encounters, p.affinity_story_seen
        ):
            portrait_label = (
                "🖼️ Alt Portrait" if p.portrait_variant == 0 else "🖼️ Default Portrait"
            )
            portrait_btn = ui.Button(
                label=portrait_label, style=ButtonStyle.secondary, row=1
            )
            portrait_btn.callback = self._toggle_portrait
            self.add_item(portrait_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _set_active(self, interaction: Interaction):
        await interaction.response.defer()
        await self.bot.database.partners.set_active_combat(
            self.user_id, self.partner.partner_id
        )
        self.partner.is_active_combat = True
        self._update_buttons()
        embed = _build_partner_embed(self.partner, self.items)
        embed.colour = discord.Colour.green()
        embed.description = (
            embed.description or ""
        ) + "\n\n✅ Set as active combat partner!"
        await interaction.edit_original_response(embed=embed, view=self)

    async def _deactivate(self, interaction: Interaction):
        await interaction.response.defer()
        await self.bot.database.partners.clear_active_combat(self.user_id)
        self.partner.is_active_combat = False
        self._update_buttons()
        embed = _build_partner_embed(self.partner, self.items)
        embed.description = (
            embed.description or ""
        ) + "\n\n❌ Removed as active combat partner."
        await interaction.edit_original_response(embed=embed, view=self)

    async def _collect_dispatch(self, interaction: Interaction):
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        lines = await _apply_dispatch_rewards(
            self.bot, self.user_id, server_id, self.partner
        )
        embed = _build_partner_embed(self.partner, self.items)
        embed.add_field(
            name="📋 Dispatch Rewards",
            value="\n".join(lines) or "Nothing yet!",
            inline=False,
        )
        await interaction.edit_original_response(embed=embed, view=self)

    async def _open_skills(self, interaction: Interaction):
        view = PartnerSkillsView(self.bot, self.user_id, self.partner, self.items, self)
        view.message = self.message
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def _toggle_portrait(self, interaction: Interaction):
        await interaction.response.defer()
        new_variant = 1 - self.partner.portrait_variant
        await self.bot.database.partners.update_portrait(
            self.user_id, self.partner.partner_id, new_variant
        )
        self.partner.portrait_variant = new_variant
        self._update_buttons()
        await interaction.edit_original_response(
            embed=_build_partner_embed(self.partner, self.items), view=self
        )

    async def _back(self, interaction: Interaction):
        from core.partners.views.roster_view import PartnerRosterView

        await interaction.response.defer()
        rows = await self.bot.database.partners.get_owned(self.user_id)
        items = await self.bot.database.partners.get_items(self.user_id)
        partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
        ]
        main_view = self.roster_view.main_view if self.roster_view else None
        new_roster = PartnerRosterView(
            self.bot, self.user_id, partners, items, main_view
        )
        new_roster.message = self.message
        from core.partners.ui import _build_roster_embed

        await interaction.edit_original_response(
            embed=_build_roster_embed(partners, items), view=new_roster
        )
        self.stop()
