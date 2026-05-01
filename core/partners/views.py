from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import List, Optional

import discord
from discord import ButtonStyle, Interaction, ui

from core.models import Partner
from core.partners.data import AFFINITY_STORIES, PARTNER_DATA
from core.partners.dispatch import calculate_rewards, calculate_sigmund_rewards
from core.partners.mechanics import (
    MAX_COMBAT_SKILL_LEVEL,
    MAX_DISPATCH_SKILL_LEVEL,
    REROLL_COMBAT_COST,
    REROLL_DISPATCH_COST,
    generate_skill_slots,
    get_combat_upgrade_cost,
    get_dispatch_upgrade_cost,
    get_sig_dispatch_effect_text,
    get_skill_effect_text,
    next_available_story,
    portrait_unlocked,
    reroll_skill,
    roll_single,
    roll_ten,
)
from core.partners.resources import _rarity_colour, _sig_display_name, _skill_display_name, _stars
from core.partners.ui import _build_partner_embed, _build_roster_embed


async def _delete_on_timeout(view) -> None:
    if view.message:
        try:
            await view.message.delete()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Dispatch item routing helpers
# ---------------------------------------------------------------------------

_MINING_ITEMS = frozenset({"iron", "coal", "gold", "platinum", "idea"})
_WOODCUTTING_ITEMS = frozenset(
    {"oak_logs", "willow_logs", "mahogany_logs", "magic_logs", "idea_logs"}
)
_FISHING_ITEMS = frozenset(
    {
        "desiccated_bones",
        "regular_bones",
        "sturdy_bones",
        "reinforced_bones",
        "titanium_bones",
    }
)
_GATHERING_ITEMS = _MINING_ITEMS | _WOODCUTTING_ITEMS | _FISHING_ITEMS

_RUNE_CURRENCY_MAP = {
    "refinement_rune": "refinement_runes",
    "potential_rune": "potential_runes",
    "shatter_rune": "shatter_runes",
}
_BOSS_KEY_TYPES = [
    "draconic_key",
    "angelic_key",
    "soul_core",
    "void_frag",
    "balance_fragment",
]

# ---------------------------------------------------------------------------
# Task labels
# ---------------------------------------------------------------------------

_TASK_LABELS = {"combat": "⚔️ Combat", "gathering": "⛏️ Gathering"}


# ---------------------------------------------------------------------------
# Dispatch reward helper (shared between PartnerDetailView and DispatchView)
# ---------------------------------------------------------------------------


async def _apply_dispatch_rewards(
    bot, user_id: str, server_id: str, partner: Partner
) -> list:
    """Apply all dispatch reward DB side-effects. Returns a list of result lines."""
    is_sigmund = (
        partner.sig_combat_key == "sig_co_sigmund"
        and partner.sig_dispatch_lvl >= 1
        and partner.dispatch_task_2 is not None
    )
    if is_sigmund:
        result = calculate_sigmund_rewards(partner)
    else:
        result = calculate_rewards(partner, partner.dispatch_start_time or "")

    gold = result.get("gold", 0)
    exp = result.get("exp", 0)
    rolls = result.get("rolls", 0)
    items_got = result.get("items", {})

    if gold > 0:
        await bot.database.users.modify_gold(user_id, gold)
    if exp > 0:
        from core.partners.mechanics import grant_xp as _grant_xp

        new_level, new_exp, _ = _grant_xp(partner.level, partner.exp, exp)
        partner.level = new_level
        partner.exp = new_exp
        await bot.database.partners.update_exp(
            user_id, partner.partner_id, new_exp, new_level
        )

    if items_got:
        mining_batch: dict = {}
        woodcutting_batch: dict = {}
        fishing_batch: dict = {}

        for item_key, qty in items_got.items():
            if item_key in _MINING_ITEMS:
                mining_batch[item_key] = mining_batch.get(item_key, 0) + qty
            elif item_key in _WOODCUTTING_ITEMS:
                woodcutting_batch[item_key] = woodcutting_batch.get(item_key, 0) + qty
            elif item_key in _FISHING_ITEMS:
                fishing_batch[item_key] = fishing_batch.get(item_key, 0) + qty
            elif item_key in ("magma_core", "life_root", "spirit_shard"):
                await bot.database.users.modify_currency(user_id, item_key, qty)
            elif item_key == "celestial_sigils":
                await bot.database.uber.increment_sigils(user_id, server_id, qty)
            elif item_key == "infernal_sigils":
                await bot.database.uber.increment_infernal_sigils(
                    user_id, server_id, qty
                )
            elif item_key == "void_shards":
                await bot.database.uber.increment_void_shards(user_id, server_id, qty)
            elif item_key == "gemini_sigils":
                await bot.database.uber.increment_gemini_sigils(user_id, server_id, qty)
            elif item_key == "boss_key":
                for _ in range(qty):
                    for key_type in _BOSS_KEY_TYPES:
                        if random.random() < 0.20:
                            await bot.database.users.modify_currency(
                                user_id, key_type, 1
                            )
            elif item_key in _RUNE_CURRENCY_MAP:
                await bot.database.users.modify_currency(
                    user_id, _RUNE_CURRENCY_MAP[item_key], qty
                )
            elif item_key == "guild_ticket":
                await bot.database.partners.add_tickets(user_id, qty)
            elif item_key in ("antique_tome", "pinnacle_key"):
                await bot.database.users.modify_currency(user_id, item_key, qty)
            elif item_key == "blessed_bismuth":
                await bot.database.uber.increment_blessed_bismuth(
                    user_id, server_id, qty
                )
            elif item_key == "sparkling_sprig":
                await bot.database.uber.increment_sparkling_sprig(
                    user_id, server_id, qty
                )
            elif item_key == "capricious_carp":
                await bot.database.uber.increment_capricious_carp(
                    user_id, server_id, qty
                )
            elif item_key == "spirit_stone":
                await bot.database.users.modify_currency(user_id, "spirit_stones", qty)
            elif item_key == "essence":
                from database.repositories.essences import (
                    COMMON_ESSENCE_TYPES,
                    RARE_ESSENCE_TYPES,
                )

                pool = list(COMMON_ESSENCE_TYPES) + list(RARE_ESSENCE_TYPES)
                for _ in range(qty):
                    await bot.database.essences.add(user_id, random.choice(pool), 1)
            elif item_key == "slayer_drop":
                try:
                    await bot.database.slayer.add_rewards(user_id, server_id, 0, qty)
                except Exception:
                    pass

        if mining_batch:
            try:
                await bot.database.skills.update_batch(
                    user_id, server_id, "mining", mining_batch
                )
            except Exception:
                pass
        if woodcutting_batch:
            try:
                await bot.database.skills.update_batch(
                    user_id, server_id, "woodcutting", woodcutting_batch
                )
            except Exception:
                pass
        if fishing_batch:
            try:
                await bot.database.skills.update_batch(
                    user_id, server_id, "fishing", fishing_batch
                )
            except Exception:
                pass

    now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    await bot.database.partners.reset_dispatch_timer(
        user_id, partner.partner_id, now_str
    )
    if is_sigmund:
        await bot.database.partners.reset_dispatch_timer_2(
            user_id, partner.partner_id, now_str
        )

    lines = [f"⏱️ **{rolls:.1f}** reward rolls collected"]
    if gold:
        lines.append(f"💰 **{gold:,}** gold")
    if exp:
        lines.append(f"📚 **{exp:,}** Partner EXP")
    for item_key, qty in items_got.items():
        lines.append(f"📦 {qty}× **{item_key.replace('_', ' ').title()}**")
    return lines


# ---------------------------------------------------------------------------
# PartnerDetailView
# ---------------------------------------------------------------------------


class PartnerDetailView(ui.View):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, roster_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.items = items
        self.roster_view = roster_view
        self.message = None
        self._update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        await _delete_on_timeout(self)

    def _update_buttons(self):
        self.clear_items()
        p = self.partner

        # Set / Remove Active Combat
        if p.is_active_combat:
            btn = ui.Button(label="✅ Active (Click to Remove)", style=ButtonStyle.success)
            btn.callback = self._deactivate
        else:
            btn = ui.Button(label="Set Active Combat", style=ButtonStyle.primary)
            btn.callback = self._set_active
        self.add_item(btn)

        # Manage Skills
        skills_btn = ui.Button(
            label="Manage Skills", style=ButtonStyle.secondary, emoji="⚙️"
        )
        skills_btn.callback = self._open_skills
        self.add_item(skills_btn)

        # Switch Portrait (6★ with maxed affinity)
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

        # Back
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
        await interaction.edit_original_response(
            embed=_build_roster_embed(partners, items), view=new_roster
        )
        self.stop()


# ---------------------------------------------------------------------------
# DispatchReplaceConfirmView  (used from PartnerDetailView when another is dispatched)
# ---------------------------------------------------------------------------


class DispatchReplaceConfirmView(ui.View):
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
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.new_partner = new_partner
        self.active_partner = active_partner
        self.items = items
        self.detail_view = detail_view
        self.message = None

        collect_btn = ui.Button(label="Collect & Dispatch", style=ButtonStyle.success)
        collect_btn.callback = self._collect_and_dispatch
        self.add_item(collect_btn)

        cancel_btn = ui.Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

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
        # Re-fetch items after collection
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
# DispatchTaskSelectView  (used from PartnerDetailView)
# ---------------------------------------------------------------------------


class DispatchTaskSelectView(ui.View):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, detail_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.items = items
        self.detail_view = detail_view
        self.message = None
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

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)


# ---------------------------------------------------------------------------
# PartnerSkillsView
# ---------------------------------------------------------------------------

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


class PartnerSkillsView(ui.View):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, detail_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.items = items
        self.detail_view = detail_view
        self.message = None
        self.mode = "combat"  # "combat" or "dispatch"
        self._refresh_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

    def build_embed(self) -> discord.Embed:
        p = self.partner
        embed = discord.Embed(
            title=f"⚙️ Skills — {p.name}",
            colour=_rarity_colour(p.rarity),
        )
        if self.mode == "combat":
            embed.set_thumbnail(url="https://i.imgur.com/hRAMSPh.jpeg")
        else:
            embed.set_thumbnail(url="https://i.imgur.com/2fMB2JI.jpeg")
        shards_key = (
            "combat_skill_shards" if self.mode == "combat" else "dispatch_skill_shards"
        )
        shards = self.items.get(shards_key, 0)
        reroll_cost = (
            REROLL_COMBAT_COST if self.mode == "combat" else REROLL_DISPATCH_COST
        )

        lines = [
            f"**{shards}** {self.mode} shards  |  Reroll costs **{reroll_cost}** shards"
        ]
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

        for i, (key, lvl) in enumerate(slots):
            key_col, lvl_col = col_pairs[i]
            if key and lvl < max_lvl:
                upgrade_btn = ui.Button(
                    label=f"Upgrade S{i + 1}", style=ButtonStyle.primary
                )
                upgrade_btn.callback = self._make_upgrade(i, key_col, lvl_col, key, lvl)
                self.add_item(upgrade_btn)

        for i, (key, _) in enumerate(slots):
            key_col, lvl_col = col_pairs[i]
            reroll_btn = ui.Button(
                label=f"Reroll S{i + 1}", style=ButtonStyle.secondary
            )
            reroll_btn.callback = self._make_reroll(i, key_col, lvl_col)
            self.add_item(reroll_btn)

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
# PartnerRosterView  (full list with Select dropdown, no pagination)
# ---------------------------------------------------------------------------


class PartnerRosterView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        partners: List[Partner],
        items: dict,
        main_view,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partners = partners
        self.items = items
        self.main_view = main_view
        self.message = None
        self._refresh()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

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
            )
            progress_view.message = self.message
            embed, _ = _build_progress_embed(party_row, partners_by_id)
            await interaction.edit_original_response(embed=embed, view=progress_view)
            return

        form_view = BossPartyFormView(
            self.bot, self.user_id, server_id, self.partners, back_view=self
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
# DispatchView  (top-level dispatch management)
# ---------------------------------------------------------------------------


class DispatchView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        partners: List[Partner],
        items: dict,
        main_view,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partners = partners
        self.items = items
        self.main_view = main_view
        self.selected_partner: Optional[Partner] = None
        self.message = None
        self._refresh()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

    def _get_active_dispatch(self) -> Optional[Partner]:
        return next(
            (p for p in self.partners if p.is_dispatched and p.dispatch_task != "boss_party"),
            None,
        )

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="📋 Dispatch", colour=0x8BC34A)
        embed.set_thumbnail(url="https://i.imgur.com/AlEM3ov.jpeg")
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
                f"🎫 {self.items.get('guild_tickets', 0)} tickets  |  "
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
                    status = " 📋" if p.is_dispatched else ""
                    options.append(
                        discord.SelectOption(
                            label=f"{_stars(p.rarity)} {p.name} Lv.{p.level}{status}"[
                                :100
                            ],
                            value=str(p.partner_id),
                            description=(
                                f"On: {p.dispatch_task}" if p.is_dispatched else "Idle"
                            )[:100],
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
        if sp and active and sp.partner_id != active.partner_id:
            # NEW: Replace option when another dispatch is active and a different partner is selected
            replace_btn = ui.Button(
                label="Replace Dispatch", style=ButtonStyle.success, row=1
            )
            replace_btn.callback = self._replace
            self.add_item(replace_btn)
        elif sp is not None and sp.is_dispatched:
            # Selected partner is currently out — offer Reassign and Unassign
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
            # Normal flow: Confirm to start a new dispatch
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
            label="Boss Raid", style=ButtonStyle.danger, emoji="🔱", row=2
        )
        boss_raid_btn.callback = self._boss_raid
        self.add_item(boss_raid_btn)
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _replace(self, interaction: Interaction):
        """Collect rewards from the current active dispatch, then switch to task selection
        for the newly selected partner (exactly as requested)."""
        await interaction.response.defer()
        active = self._get_active_dispatch()
        if active:
            server_id = str(interaction.guild.id)
            await _apply_dispatch_rewards(self.bot, self.user_id, server_id, active)
        # Refresh data
        rows = await self.bot.database.partners.get_owned(self.user_id)
        self.partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
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
            # Fallback (should not happen)
            self._refresh()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

    async def _boss_raid(self, interaction: Interaction):
        """Boss Raid entry point – moved from PartnerMainView to DispatchView."""
        await interaction.response.defer()
        from core.partners.views_boss_party import (
            BossPartyFormView,
            BossPartyProgressView,
            _build_form_embed,
            _build_progress_embed,
        )

        server_id = str(interaction.guild.id)

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
                back_view=self,  # returns to DispatchView (logical new context)
            )
            progress_view.message = self.message
            embed, _ = _build_progress_embed(party_row, partners_by_id)
            await interaction.edit_original_response(embed=embed, view=progress_view)
            return

        form_view = BossPartyFormView(
            self.bot, self.user_id, server_id, self.partners, back_view=self
        )
        form_view.message = self.message
        embed = _build_form_embed(form_view.slots, self.partners)
        embed.set_thumbnail(url="https://i.imgur.com/Q4SzClS.jpeg")
        await interaction.edit_original_response(embed=embed, view=form_view)

    async def _on_select(self, interaction: Interaction):
        await interaction.response.defer()
        partner_id = int(interaction.data["values"][0])
        self.selected_partner = next(
            (p for p in self.partners if p.partner_id == partner_id), None
        )
        self._refresh()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

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
        sp = self.selected_partner
        if not sp or not sp.is_dispatched:
            await interaction.response.send_message(
                "Selected partner is not dispatched.", ephemeral=True
            )
            return
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        lines = await _apply_dispatch_rewards(self.bot, self.user_id, server_id, sp)

        rows = await self.bot.database.partners.get_owned(self.user_id)
        self.partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
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

    async def _unassign(self, interaction: Interaction):
        """Recall the selected partner immediately — no rewards collected."""
        sp = self.selected_partner
        if not sp or not sp.is_dispatched:
            await interaction.response.send_message(
                "Selected partner is not dispatched.", ephemeral=True
            )
            return
        await interaction.response.defer()
        await self.bot.database.partners.clear_dispatch(self.user_id, sp.partner_id)

        rows = await self.bot.database.partners.get_owned(self.user_id)
        self.partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
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

    async def _reassign(self, interaction: Interaction):
        """Collect current rewards then open task selection to re-dispatch."""
        sp = self.selected_partner
        if not sp or not sp.is_dispatched:
            await interaction.response.send_message(
                "Selected partner is not dispatched.", ephemeral=True
            )
            return
        await interaction.response.defer()
        server_id = str(interaction.guild.id)
        lines = await _apply_dispatch_rewards(self.bot, self.user_id, server_id, sp)

        rows = await self.bot.database.partners.get_owned(self.user_id)
        self.partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
        ]
        self.items = await self.bot.database.partners.get_items(self.user_id)
        self.selected_partner = next(
            (p for p in self.partners if p.partner_id == sp.partner_id), None
        )

        # Open task selection
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
        embed.set_thumbnail(url="https://i.imgur.com/AlEM3ov.jpeg")
        await interaction.edit_original_response(embed=embed, view=task_view)

    async def _back(self, interaction: Interaction):
        await interaction.response.defer()
        embed, items, partners = await self.main_view._fetch_fresh_data()
        await interaction.edit_original_response(embed=embed, view=self.main_view)
        self.stop()


# ---------------------------------------------------------------------------
# DispatchTaskConfirmView  (task selection inside DispatchView flow)
# ---------------------------------------------------------------------------


class DispatchTaskConfirmView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        partner: Partner,
        items: dict,
        dispatch_view: DispatchView,
        partners: List[Partner],
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.items = items
        self.dispatch_view = dispatch_view
        self.partners = partners
        self.message = None

        for task, label in _TASK_LABELS.items():
            btn = ui.Button(label=label, style=ButtonStyle.secondary)
            btn.callback = self._make_callback(task)
            self.add_item(btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

    def _make_callback(self, task: str):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            await self.bot.database.partners.set_dispatch(
                self.user_id, self.partner.partner_id, task, now_str
            )
            # Update in-memory partner states
            for p in self.partners:
                p.is_dispatched = False
            self.partner.is_dispatched = True
            self.partner.dispatch_task = task
            self.partner.dispatch_start_time = now_str

            self.dispatch_view.partners = self.partners
            self.dispatch_view.selected_partner = self.partner
            self.dispatch_view._refresh()

            embed = self.dispatch_view.build_embed()
            embed.colour = discord.Colour.blue()
            await interaction.edit_original_response(
                embed=embed, view=self.dispatch_view
            )
            self.stop()

        return callback

    async def _back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.dispatch_view.build_embed(), view=self.dispatch_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# PullResultView  (shown after a pull)
# ---------------------------------------------------------------------------


class PullResultView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        pull_view,
        new_partners: List[dict],
        highest_dup: Optional[dict] = None,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.pull_view = pull_view
        self.new_partners = new_partners  # list of {"partner": PartnerData, "rarity": int, "static": dict}
        self.highest_dup = highest_dup  # fallback for all-duplicates case
        self.current_index = 0
        self.message = None
        self._update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

    def _update_buttons(self):
        self.clear_items()

        if len(self.new_partners) > 1:
            left = ui.Button(
                emoji="⬅️", style=ButtonStyle.gray, disabled=self.current_index == 0
            )
            left.callback = self._prev
            self.add_item(left)

            right = ui.Button(
                emoji="➡️",
                style=ButtonStyle.gray,
                disabled=self.current_index == len(self.new_partners) - 1,
            )
            right.callback = self._next
            self.add_item(right)

        # Pull Again buttons
        again1 = ui.Button(
            label="Pull Again (1 ticket)", style=ButtonStyle.primary, row=1
        )
        again1.callback = self._pull_again
        self.add_item(again1)

        again10 = ui.Button(
            label="Pull ×10 (10 tickets)", style=ButtonStyle.success, row=1
        )
        again10.callback = self._pull_ten
        self.add_item(again10)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back.callback = self._back
        self.add_item(back)

    def _build_embed(self) -> discord.Embed:
        if self.new_partners:
            data = self.new_partners[self.current_index]
            static = data["static"]
            rarity = data["rarity"]
            title = f"🎫 New Partner! {_stars(rarity)} {static['name']}"
        else:
            # All duplicates fallback
            static = self.highest_dup["static"]
            rarity = self.highest_dup["rarity"]
            title = f"🎫 Pull Results — {_stars(rarity)} {static['name']} (Duplicate)"

        embed = discord.Embed(
            title=title,
            description=static.get("pull_message", "A new ally joins the fray!"),
            colour=_rarity_colour(rarity),
        )
        embed.set_image(url=static["image_url"])

        # Progress indicator
        if len(self.new_partners) > 1:
            embed.set_footer(
                text=f"New partner {self.current_index + 1}/{len(self.new_partners)} • "
                f"Use arrows to browse"
            )
        else:
            embed.set_footer(text="Pull complete!")

        return embed

    async def _prev(self, interaction: Interaction):
        self.current_index = max(0, self.current_index - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _next(self, interaction: Interaction):
        self.current_index = min(len(self.new_partners) - 1, self.current_index + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _pull_again(self, interaction: Interaction):
        await self.pull_view._do_pull(interaction, count=1)
        self.stop()

    async def _pull_ten(self, interaction: Interaction):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    async def _back(self, interaction: Interaction):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self.pull_view.main_view)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# PullView
# ---------------------------------------------------------------------------

_RARITY_EMOJIS = {4: "💙", 5: "💛", 6: "❤️"}


class PullView(ui.View):
    def __init__(self, bot, user_id: str, main_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.main_view = main_view
        self.message = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

    def build_embed(self, items: dict) -> discord.Embed:
        embed = discord.Embed(
            title="🎫 Partner Pull",
            colour=0xFFD700,
        )
        embed.description = (
            "Spend **Guild Tickets** to recruit new partners!\n\n"
            "**Rates:**\n88% ★★★★\n11% ★★★★★\n1% ★★★★★★\n"
            "10-pull guarantees a 5★ partner."
        )
        embed.add_field(
            name="Your Tickets",
            value=f"🎫 **{items.get('guild_tickets', 0)}** tickets",
        )
        embed.add_field(
            name="Pity",
            value=f"**{items.get('pity_counter', 0)}/100**",
        )
        embed.set_image(url="https://i.imgur.com/Vmjfyj5.jpeg")
        return embed

    @ui.button(label="Pull ×1 (1 ticket)", style=ButtonStyle.primary)
    async def pull_one(self, interaction: Interaction, button: ui.Button):
        await self._do_pull(interaction, count=1)

    @ui.button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success)
    async def pull_ten(self, interaction: Interaction, button: ui.Button):
        await self._do_pull(interaction, count=10)

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        embed, items, partners = await self.main_view._fetch_fresh_data()
        await interaction.edit_original_response(embed=embed, view=self.main_view)
        self.stop()

    async def _do_pull(self, interaction: Interaction, count: int):
        ticket_cost = count
        ok = await self.bot.database.partners.spend_tickets(self.user_id, ticket_cost)
        if not ok:
            await interaction.response.send_message(
                f"Not enough tickets! You need **{ticket_cost}** 🎫.", ephemeral=True
            )
            return

        await interaction.response.defer()

        items = await self.bot.database.partners.get_items(self.user_id)
        pity = items["pity_counter"]

        if count == 1:
            rarity, new_pity = roll_single(pity)
            rarities = [rarity]
        else:
            rarities, new_pity = roll_ten(pity)

        await self.bot.database.partners.update_pity(self.user_id, new_pity)

        max_rarity = max(rarities)
        banner_urls = {
            4: "https://i.imgur.com/NpUHE2b.jpeg",
            5: "https://i.imgur.com/OUrwCWk.jpeg",
            6: "https://i.imgur.com/Kfmq9Pg.jpeg",
        }
        banner_embed = discord.Embed(
            title="🎫 Recruiting...",
            description="The clerk hands you a scroll, you unfurl it...",
            colour=_rarity_colour(max_rarity),
        )
        banner_embed.set_image(url=banner_urls.get(max_rarity))
        await interaction.edit_original_response(embed=banner_embed, view=None)

        await asyncio.sleep(3)

        all_partners_by_rarity = {
            4: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 4],
            5: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 5],
            6: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 6],
        }

        result_lines = []
        shards_combat = 0
        shards_dispatch = 0
        char_shards_gained: dict[int, int] = {}
        MAX_SIG_TIER = 5
        MAX_TICKET_GRANT = 10

        new_partners: List[Partner] = []
        highest_dup_rarity = 0
        highest_dup_static = None

        for rarity in rarities:
            pool = all_partners_by_rarity.get(rarity, all_partners_by_rarity[4])
            partner_id = random.choice(pool)
            static = PARTNER_DATA[partner_id]
            emoji = _RARITY_EMOJIS.get(rarity, "💙")

            already_owned = await self.bot.database.partners.owns_partner(
                self.user_id, partner_id
            )

            if not already_owned:
                co_slots = generate_skill_slots(rarity, "combat")
                di_slots = generate_skill_slots(rarity, "dispatch")
                await self.bot.database.partners.add_partner(
                    self.user_id, partner_id, co_slots, di_slots
                )
                result_lines.append(
                    f"{emoji} **NEW** — {_stars(rarity)} **{static['name']}**!"
                )

                row = await self.bot.database.partners.get_partner(
                    self.user_id, partner_id
                )
                if row:
                    partner_obj = Partner.from_row(row, static)
                    new_partners.append(partner_obj)
            else:
                # Duplicate handling
                if rarity == 6:
                    cur_sig = await _get_sig_lvl(self.bot, self.user_id, partner_id)
                    if cur_sig >= MAX_SIG_TIER:
                        await self.bot.database.partners.add_tickets(
                            self.user_id, MAX_TICKET_GRANT
                        )
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** (Sig MAX) → +{MAX_TICKET_GRANT} 🎫"
                        )
                    else:
                        char_shards_gained[partner_id] = (
                            char_shards_gained.get(partner_id, 0) + 1
                        )
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 signature skill shard"
                        )
                elif rarity == 5:
                    if random.random() < 0.5:
                        shards_combat += 3
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +3 combat skill shards ⚔️"
                        )
                    else:
                        shards_dispatch += 3
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +3 dispatch skill shards 📋"
                        )
                else:
                    if random.random() < 0.5:
                        shards_combat += 1
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 combat skill shard ⚔️"
                        )
                    else:
                        shards_dispatch += 1
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 dispatch skill shard 📋"
                        )

                if rarity > highest_dup_rarity:
                    highest_dup_rarity = rarity
                    highest_dup_static = static

        # Apply rewards
        if shards_combat > 0:
            await self.bot.database.partners.add_combat_shards(
                self.user_id, shards_combat
            )
        if shards_dispatch > 0:
            await self.bot.database.partners.add_dispatch_shards(
                self.user_id, shards_dispatch
            )
        total_char_shards = sum(char_shards_gained.values())
        if total_char_shards > 0:
            await self.bot.database.partners.add_shard(self.user_id, 0, total_char_shards)

        items_after = await self.bot.database.partners.get_items(self.user_id)

        # === STAGE 2: Recap / Quote stage ===
        if count == 1:
            if new_partners:
                # 1x NEW → quote
                partner = new_partners[0]
                quote_embed = discord.Embed(
                    title="A partner has answered your call!",
                    description=f"{partner.pull_message}",
                    colour=_rarity_colour(partner.rarity),
                )
                if partner.display_image:
                    quote_embed.set_image(url=partner.display_image)
                await interaction.edit_original_response(embed=quote_embed, view=None)
            else:
                # 1x DUPLICATE
                dup_embed = discord.Embed(
                    title=f"Duplicate — {_stars(highest_dup_rarity)} {highest_dup_static['name']}",
                    description="This partner has already joined you.",
                    colour=_rarity_colour(highest_dup_rarity),
                )
                dup_embed.set_image(url=highest_dup_static["image_url"])
                dup_embed.add_field(
                    name="Reward",
                    value="\n".join(result_lines[-1:]) or "Shard obtained",
                    inline=False,
                )
                await interaction.edit_original_response(embed=dup_embed, view=None)
        else:
            # 10x → plethora recap
            plethora_embed = discord.Embed(
                title="A plethora of partners have answered your call!",
                description="\n".join(result_lines) or "No results.",
                colour=0xFFD700,
            )
            plethora_embed.set_footer(
                text=f"Pity: {new_pity}/100  |  🎫 {items_after.get('guild_tickets', 0)} tickets"
            )
            await interaction.edit_original_response(embed=plethora_embed, view=None)

        await asyncio.sleep(2.5)

        # === STAGE 3: Final view ===
        if new_partners:
            # At least one new partner → show full detail / browser
            if count == 1:
                final_view = SinglePullDetailView(
                    self.bot, self.user_id, new_partners[0], self
                )
            else:
                final_view = NewPartnersBrowserView(
                    self.bot, self.user_id, new_partners, self
                )
            final_view.message = self.message
            await interaction.edit_original_response(
                embed=final_view.build_embed(), view=final_view
            )
        else:
            # NO new partners (1x duplicate OR 10x all duplicates)
            if count == 1:
                # 1x duplicate → keep the nice duplicate embed + add pull buttons
                recap_view = PullRecapView(self.bot, self.user_id, self)
                recap_view.message = self.message
                await interaction.edit_original_response(
                    embed=dup_embed, view=recap_view
                )
            else:
                # 10x all duplicates → keep plethora recap + pull buttons
                recap_view = PullRecapView(self.bot, self.user_id, self)
                recap_view.message = self.message
                await interaction.edit_original_response(
                    embed=plethora_embed, view=recap_view
                )


async def _get_sig_lvl(bot, user_id: str, partner_id: int) -> int:
    row = await bot.database.partners.get_partner(user_id, partner_id)
    if not row:
        return 0
    return row[11]  # sig_combat_lvl column index


# ---------------------------------------------------------------------------
# SinglePullDetailView - used for 1x NEW pulls (full stats + skills)
# ---------------------------------------------------------------------------


class SinglePullDetailView(ui.View):
    def __init__(self, bot, user_id: str, partner: Partner, pull_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.pull_view = pull_view
        self.message = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

    def build_embed(self) -> discord.Embed:
        return _build_partner_embed(self.partner, {})  # items dict not needed here

    @ui.button(label="Pull Again (1 ticket)", style=ButtonStyle.primary, row=1)
    async def pull_one(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=1)
        self.stop()

    @ui.button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success, row=1)
    async def pull_ten(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self.pull_view.main_view)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# NewPartnersBrowserView - used for 10x (and 1x new) - browsable full details
# ---------------------------------------------------------------------------


class NewPartnersBrowserView(ui.View):
    def __init__(self, bot, user_id: str, new_partners: List[Partner], pull_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.new_partners = new_partners
        self.pull_view = pull_view
        self.current_index = 0
        self.message = None
        self._update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

    def _update_buttons(self):
        self.clear_items()

        if len(self.new_partners) > 1:
            left = ui.Button(
                emoji="⬅️", style=ButtonStyle.gray, disabled=self.current_index == 0
            )
            left.callback = self._prev
            self.add_item(left)

            right = ui.Button(
                emoji="➡️",
                style=ButtonStyle.gray,
                disabled=self.current_index == len(self.new_partners) - 1,
            )
            right.callback = self._next
            self.add_item(right)

        # Pull again buttons
        one = ui.Button(label="Pull Again (1 ticket)", style=ButtonStyle.primary, row=1)
        one.callback = self._pull_one
        self.add_item(one)

        ten = ui.Button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success, row=1)
        ten.callback = self._pull_ten
        self.add_item(ten)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back.callback = self._back
        self.add_item(back)

    def build_embed(self) -> discord.Embed:
        partner = self.new_partners[self.current_index]
        embed = _build_partner_embed(partner, {})
        embed.title = (
            f"🎫 New Partner Acquired! {_stars(partner.rarity)} {partner.name}"
        )
        if len(self.new_partners) > 1:
            embed.set_footer(
                text=f"New partner {self.current_index + 1}/{len(self.new_partners)} • Use arrows to browse"
            )
        return embed

    async def _prev(self, interaction: Interaction):
        self.current_index = max(0, self.current_index - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _next(self, interaction: Interaction):
        self.current_index = min(len(self.new_partners) - 1, self.current_index + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _pull_one(self, interaction: Interaction):
        await self.pull_view._do_pull(interaction, count=1)
        self.stop()

    async def _pull_ten(self, interaction: Interaction):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    async def _back(self, interaction: Interaction):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self.pull_view.main_view)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# PullRecapView - used for 10x pulls with ZERO new partners
# Keeps the "plethora" recap visible and allows immediate re-pulls
# ---------------------------------------------------------------------------


class PullRecapView(ui.View):
    def __init__(self, bot, user_id: str, pull_view):
        super().__init__(timeout=600)  # 10 minutes
        self.bot = bot
        self.user_id = user_id
        self.pull_view = pull_view
        self.message = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

    @ui.button(label="Pull Again (1 ticket)", style=ButtonStyle.primary, row=1)
    async def pull_one(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=1)
        self.stop()

    @ui.button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success, row=1)
    async def pull_ten(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self.pull_view.main_view)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# AffinityView / AffinityStoryView
# ---------------------------------------------------------------------------


class AffinityStoryView(ui.View):
    def __init__(
        self, bot, user_id: str, partner: Partner, story_idx: int, affinity_view
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.story_idx = story_idx
        self.affinity_view = affinity_view
        self.message = None
        read_btn = ui.Button(label="Acknowledge", style=ButtonStyle.success)
        read_btn.callback = self._acknowledge
        self.add_item(read_btn)
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        story_data = AFFINITY_STORIES.get(
            (self.partner.partner_id, self.story_idx),
            {
                "title": f"Story {self.story_idx}/4",
                "text": "*(Story placeholder — content coming soon.)*",
                "image_url": None,
            },
        )

        embed = discord.Embed(
            title=f"💞 {self.partner.name} — {story_data['title']}",
            description=story_data["text"],
            colour=_rarity_colour(self.partner.rarity),
        )

        # Use story-specific image if available, otherwise fall back to partner image
        image_url = story_data.get("image_url")
        if image_url:
            embed.set_image(url=image_url)
        elif self.partner.display_image:
            embed.set_thumbnail(url=self.partner.display_image)

        return embed

    async def _acknowledge(self, interaction: Interaction):
        await interaction.response.defer()
        await self.bot.database.partners.update_affinity_story_seen(
            self.user_id, self.partner.partner_id, self.story_idx
        )
        self.partner.affinity_story_seen = self.story_idx
        for p in self.affinity_view.partners:
            if p.partner_id == self.partner.partner_id:
                p.affinity_story_seen = self.story_idx
        self.affinity_view._refresh()
        embed = self.affinity_view.build_embed()
        if portrait_unlocked(self.partner.affinity_encounters, self.story_idx):
            embed.add_field(
                name="🖼️ Portrait Unlocked!",
                value=f"Use **Switch Portrait** on {self.partner.name}'s detail page to toggle their new portrait.",
                inline=False,
            )
        else:
            embed.set_footer(text=f"The bond with {self.partner.name} grows stronger.")
        await interaction.edit_original_response(embed=embed, view=self.affinity_view)

    async def _back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.affinity_view.build_embed(), view=self.affinity_view
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)


class AffinityView(ui.View):
    def __init__(self, bot, user_id: str, partners_6star: list, items: dict, main_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.partners = partners_6star
        self.items = items
        self.main_view = main_view
        self.message = None
        self._refresh()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        await _delete_on_timeout(self)

    def _refresh(self):
        self.clear_items()
        if self.partners:
            options = []
            for p in self.partners:
                story_idx = next_available_story(
                    p.affinity_encounters, p.affinity_story_seen
                )
                indicator = " ✨" if story_idx else ""
                portrait_tag = (
                    " 🖼️"
                    if portrait_unlocked(p.affinity_encounters, p.affinity_story_seen)
                    else ""
                )
                options.append(
                    discord.SelectOption(
                        label=f"{p.name}{indicator}",
                        value=str(p.partner_id),
                        description=f"{p.affinity_encounters} encounters | {p.affinity_story_seen}/4 stories{portrait_tag}",
                    )
                )
            select = ui.Select(
                placeholder="Select a partner to view their story…", options=options
            )
            select.callback = self._on_select
            self.add_item(select)
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="💞 Partner Affinity", colour=0xFF6B6B)
        embed.set_thumbnail(url="https://i.imgur.com/Qz6oh3J.jpeg")
        lines = []
        for p in self.partners:
            story_idx = next_available_story(
                p.affinity_encounters, p.affinity_story_seen
            )
            portrait_tag = (
                " 🖼️"
                if portrait_unlocked(p.affinity_encounters, p.affinity_story_seen)
                else ""
            )
            new_tag = " ✨ **New story!**" if story_idx else ""
            lines.append(
                f"{_stars(6)} **{p.name}** — {p.affinity_encounters} encounters "
                f"({p.affinity_story_seen}/4 stories){portrait_tag}{new_tag}"
            )
        embed.description = (
            "\n".join(lines) if lines else "You have no 6★ partners yet."
        )
        embed.set_footer(text="✨ = new story available  |  🖼️ = alt portrait unlocked")
        return embed

    async def _on_select(self, interaction: Interaction):
        await interaction.response.defer()
        partner_id = int(interaction.data["values"][0])
        partner = next((p for p in self.partners if p.partner_id == partner_id), None)
        if not partner:
            return
        story_idx = next_available_story(
            partner.affinity_encounters, partner.affinity_story_seen
        )
        if not story_idx:
            await interaction.followup.send(
                f"No new stories available for **{partner.name}** yet. "
                f"Take them into more combat encounters!",
                ephemeral=True,
            )
            return
        view = AffinityStoryView(self.bot, self.user_id, partner, story_idx, self)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    async def _back(self, interaction: Interaction):
        await interaction.response.defer()
        embed, items, partners = await self.main_view._fetch_fresh_data()
        await interaction.edit_original_response(embed=embed, view=self.main_view)


# ---------------------------------------------------------------------------
# PartnerMainView  (entry point)
# ---------------------------------------------------------------------------


class PartnerMainView(ui.View):
    def __init__(self, bot, user_id: str):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.message = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        await _delete_on_timeout(self)

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

        active_combat = None
        active_dispatch = None
        boss_party: list = []
        if partners:
            active_combat = next((p for p in partners if p.is_active_combat), None)
            active_dispatch = next(
                (p for p in partners if p.is_dispatched and p.dispatch_task != "boss_party"),
                None,
            )
            boss_party = [p for p in partners if p.is_dispatched and p.dispatch_task == "boss_party"]

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
            from core.partners.dispatch import elapsed_hours

            bp_first = boss_party[0]
            elapsed = (
                elapsed_hours(bp_first.dispatch_start_time)
                if bp_first.dispatch_start_time
                else 0.0
            )
            names = " | ".join(
                f"{_stars(p.rarity)} {p.name}" for p in boss_party
            )
            embed.add_field(
                name="🔱 Boss Raid",
                value=f"{names}\n⏱️ {elapsed:.1f}h accumulated",
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
        embed.set_thumbnail(url="https://i.imgur.com/agWsjri.jpeg")
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
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )

    @ui.button(label="Affinity", style=ButtonStyle.secondary, emoji="💞", row=1)
    async def affinity_btn(self, interaction: Interaction, button: ui.Button):
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
