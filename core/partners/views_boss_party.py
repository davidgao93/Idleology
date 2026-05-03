"""
Boss Party Dispatch UI.

Flow:
  BossPartyFormView  ──slot button──►  SlotPickerView  ──select──►  (back to form)
       ──confirm──►  BossPartyProgressView  ──collect──►  (done)
       ▲
  opened from PartnerRosterView "Boss Raid" button

Party requires one partner in each role: Attacker / Tank / Healer.
4★ partners may only hold their single main class slot.
5★/6★ hybrids (Vanguard/Paladin/Battlemage) fill two roles.
Duration: 22 hours. All three partners receive EXP on collect.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

import discord
from discord import ButtonStyle, Interaction, ui

from core.models import Partner
from core.partners.dispatch import (
    BOSS_PARTY_DURATION_HOURS,
    calculate_boss_party_rewards,
    pick_party_boss,
)
from core.partners.mechanics import (
    CLASS_ROLE_HINT,
    SLOT_LABELS,
    can_fill_slot,
    get_sig_dispatch_effect_text,
    get_skill_effect_text,
    grant_xp,
)
from core.images import PARTNERS_BOSS_PARTY, VICTORY_APHRODITE_GEMINI
from core.partners.resources import _skill_display_name, _stars

_SLOT_KEYS = ("attacker", "tank", "healer")

# HP bar length in characters
_BAR_LEN = 20


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _elapsed_hours(start_time_str: str) -> float:
    try:
        start = datetime.fromisoformat(start_time_str)
    except ValueError:
        return 0.0
    return max(0.0, (_now_utc() - start).total_seconds() / 3600.0)


def _hp_bar(current: int, maximum: int) -> str:
    pct = max(0.0, min(1.0, 1.0 - current / maximum))
    filled = int(pct * _BAR_LEN)
    return "█" * filled + "░" * (_BAR_LEN - filled)


def _build_form_embed(
    slots: Dict[str, Optional[Partner]],
    all_partners: List[Partner],
) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Boss Party — Form Your Raid",
        description=(
            "Assemble a party of three to challenge a powerful boss.\n"
            "Each role must be filled by a compatible partner.\n"
            "The raid lasts **22 hours**. All party members earn EXP on completion."
        ),
        colour=0xB22222,
    )
    embed.set_thumbnail(url=PARTNERS_BOSS_PARTY)
    for slot_key in _SLOT_KEYS:
        label = SLOT_LABELS[slot_key]
        partner = slots.get(slot_key)
        if partner:
            hint = CLASS_ROLE_HINT.get(partner.partner_class, partner.partner_class)
            value = f"{_stars(partner.rarity)} **{partner.name}** Lv.{partner.level} — *{hint}*"
        else:
            eligible = _eligible_for_slot(all_partners, slot_key, slots)
            count = len(eligible)
            value = (
                f"*Empty* — {count} eligible partner{'s' if count != 1 else ''} available"
                if eligible
                else "*No eligible partners available*"
            )
        embed.add_field(name=label, value=value, inline=False)

    return embed


def _build_progress_embed(
    party_row: dict, partners_by_id: Dict[int, Partner]
) -> discord.Embed:
    elapsed = _elapsed_hours(party_row["start_time"])
    progress_pct = min(1.0, elapsed / BOSS_PARTY_DURATION_HOURS)
    damage = int(party_row["boss_max_hp"] * progress_pct)
    remaining_hp = party_row["boss_max_hp"] - damage

    hours_left = max(0.0, BOSS_PARTY_DURATION_HOURS - elapsed)
    ready = hours_left <= 0

    bar = _hp_bar(remaining_hp, party_row["boss_max_hp"])

    embed = discord.Embed(
        title=f"⚔️ Raid in Progress — {party_row['boss_name']}",
        colour=0xB22222 if not ready else 0x2ECC71,
    )
    embed.set_thumbnail(url=PARTNERS_BOSS_PARTY)
    embed.add_field(
        name="Boss HP",
        value=f"`{bar}` {remaining_hp:,} / {party_row['boss_max_hp']:,}",
        inline=False,
    )

    if ready:
        embed.add_field(
            name="Status",
            value="✅ **Raid complete! Collect your rewards.**",
            inline=False,
        )
    else:
        h = int(hours_left)
        m = int((hours_left - h) * 60)
        embed.add_field(name="Time Remaining", value=f"⏱️ {h}h {m:02d}m", inline=False)

    party_lines = []
    for pid_key, label in [
        ("attacker_id", SLOT_LABELS["attacker"]),
        ("tank_id", SLOT_LABELS["tank"]),
        ("healer_id", SLOT_LABELS["healer"]),
    ]:
        p = partners_by_id.get(party_row[pid_key])
        if p:
            party_lines.append(f"{label}: {_stars(p.rarity)} **{p.name}** Lv.{p.level}")
        else:
            party_lines.append(f"{label}: *unknown*")
    embed.add_field(name="Party", value="\n".join(party_lines), inline=False)

    return embed, ready


def _eligible_for_slot(
    all_partners: List[Partner],
    slot_key: str,
    slots: Dict[str, Optional[Partner]],
) -> List[Partner]:
    """Partners eligible for slot_key: correct class, not dispatched, not already in another slot."""
    taken_ids = {p.partner_id for p in slots.values() if p is not None}
    return [
        p
        for p in all_partners
        if not p.is_dispatched
        and not p.is_active_combat
        and can_fill_slot(p.partner_class, slot_key)
        and p.partner_id not in taken_ids
    ]


def _build_partner_skills_text(partner: Partner) -> str:
    lines = []
    for i, (key, lvl) in enumerate(partner.dispatch_skills, 1):
        if key:
            lines.append(
                f"`S{i}` **{_skill_display_name(key)}** Lv.{lvl} — {get_skill_effect_text(key, lvl)}"
            )
        else:
            lines.append(f"`S{i}` *Empty*")
    if partner.rarity >= 6 and partner.sig_dispatch_key:
        lines.append(
            f"`SIG` **Sig** Lv.{partner.sig_dispatch_lvl} — "
            f"{get_sig_dispatch_effect_text(partner.partner_id, partner.sig_dispatch_lvl)}"
        )
    return "\n".join(lines) if lines else "*No dispatch skills*"


# ===========================================================================
# Slot picker sub-view
# ===========================================================================


class SlotPickerView(ui.View):
    """Shows eligible partners for a single slot with their dispatch skills."""

    def __init__(
        self,
        bot,
        user_id: str,
        slot_key: str,
        eligible: List[Partner],
        form_view: "BossPartyFormView",
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.slot_key = slot_key
        self.eligible = eligible
        self.form_view = form_view
        self.message: Optional[discord.Message] = None
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass

    def _build(self):
        self.clear_items()
        current = self.form_view.slots.get(self.slot_key)

        options = []
        if current:
            options.append(
                discord.SelectOption(
                    label="— Clear slot —",
                    value="__clear__",
                    description="Remove current selection",
                )
            )
        for p in self.eligible[:24]:
            hint = CLASS_ROLE_HINT.get(p.partner_class, p.partner_class)
            options.append(
                discord.SelectOption(
                    label=f"{p.name} Lv.{p.level} ({hint})"[:100],
                    value=str(p.partner_id),
                    description=f"{'★'*p.rarity}  ATK {p.total_attack}  DEF {p.total_defence}"[
                        :100
                    ],
                    default=(
                        current is not None and p.partner_id == current.partner_id
                    ),
                )
            )

        if not options:
            options = [
                discord.SelectOption(label="No eligible partners", value="__none__")
            ]

        select = ui.Select(
            placeholder=f"Choose a partner for {SLOT_LABELS[self.slot_key]}…",
            options=options,
            disabled=len(options) == 1 and options[0].value == "__none__",
        )
        select.callback = self._on_select
        self.add_item(select)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        label = SLOT_LABELS[self.slot_key]
        embed = discord.Embed(
            title=f"⚔️ Select Partner — {label}",
            colour=0xB22222,
        )
        current = self.form_view.slots.get(self.slot_key)
        if current:
            embed.add_field(
                name=f"Current: {_stars(current.rarity)} {current.name} Lv.{current.level}",
                value=_build_partner_skills_text(current),
                inline=False,
            )

        if not self.eligible:
            embed.description = "*No eligible partners available for this role.*"
            return embed

        for p in self.eligible[:10]:
            hint = CLASS_ROLE_HINT.get(p.partner_class, p.partner_class)
            embed.add_field(
                name=f"{_stars(p.rarity)} {p.name} Lv.{p.level} — {hint}",
                value=_build_partner_skills_text(p),
                inline=False,
            )
        if len(self.eligible) > 10:
            embed.set_footer(
                text=f"+{len(self.eligible) - 10} more eligible partners (use the dropdown to select)"
            )

        return embed

    async def _on_select(self, interaction: Interaction):
        await interaction.response.defer()
        val = interaction.data["values"][0]
        if val == "__clear__":
            self.form_view.slots[self.slot_key] = None
        elif val != "__none__":
            pid = int(val)
            self.form_view.slots[self.slot_key] = next(
                (p for p in self.form_view.all_partners if p.partner_id == pid), None
            )
        self.form_view._refresh()
        embed = _build_form_embed(self.form_view.slots, self.form_view.all_partners)
        await interaction.edit_original_response(embed=embed, view=self.form_view)
        self.stop()

    async def _back(self, interaction: Interaction):
        await interaction.response.defer()
        self.form_view._refresh()
        embed = _build_form_embed(self.form_view.slots, self.form_view.all_partners)
        await interaction.edit_original_response(embed=embed, view=self.form_view)
        self.stop()


# ===========================================================================
# Formation view
# ===========================================================================


class BossPartyFormView(ui.View):
    def __init__(
        self, bot, user_id: str, server_id: str, all_partners: List[Partner], back_view
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.all_partners = all_partners
        self.back_view = back_view
        self.message: Optional[discord.Message] = None
        self.slots: Dict[str, Optional[Partner]] = {
            "attacker": None,
            "tank": None,
            "healer": None,
        }
        self._refresh()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass

    def _refresh(self):
        self.clear_items()

        slot_styles = {
            "attacker": ButtonStyle.danger,
            "tank": ButtonStyle.primary,
            "healer": ButtonStyle.success,
        }

        for i, slot_key in enumerate(_SLOT_KEYS):
            current = self.slots.get(slot_key)
            label = SLOT_LABELS[slot_key]
            btn_label = f"{label}: {current.name}" if current else f"{label}: Select…"

            btn = ui.Button(
                label=btn_label[:80],
                style=slot_styles[slot_key],
                row=i,
            )
            btn.callback = self._make_slot_callback(slot_key)
            self.add_item(btn)

        all_filled = all(self.slots[k] is not None for k in _SLOT_KEYS)
        confirm_btn = ui.Button(
            label="Begin Raid",
            style=ButtonStyle.danger,
            emoji="⚔️",
            disabled=not all_filled,
            row=3,
        )
        confirm_btn.callback = self._confirm
        self.add_item(confirm_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=3)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def _make_slot_callback(self, slot_key: str):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            eligible = _eligible_for_slot(self.all_partners, slot_key, self.slots)
            picker = SlotPickerView(
                self.bot, self.user_id, slot_key, eligible, form_view=self
            )
            picker.message = self.message
            await interaction.edit_original_response(
                embed=picker.build_embed(), view=picker
            )

        return callback

    async def _confirm(self, interaction: Interaction):
        await interaction.response.defer()
        boss = pick_party_boss()
        start_time = _now_utc().isoformat()

        attacker = self.slots["attacker"]
        tank = self.slots["tank"]
        healer = self.slots["healer"]

        await self.bot.database.partners.set_boss_party_dispatch(
            self.user_id,
            attacker.partner_id,
            tank.partner_id,
            healer.partner_id,
            start_time,
        )
        await self.bot.database.boss_party.create(
            self.user_id,
            self.server_id,
            attacker.partner_id,
            tank.partner_id,
            healer.partner_id,
            boss["name"],
            boss["max_hp"],
            start_time,
        )

        for p in (attacker, tank, healer):
            p.is_dispatched = True

        progress_view = BossPartyProgressView(
            self.bot,
            self.user_id,
            self.server_id,
            party_row={
                "id": None,
                "attacker_id": attacker.partner_id,
                "tank_id": tank.partner_id,
                "healer_id": healer.partner_id,
                "boss_name": boss["name"],
                "boss_max_hp": boss["max_hp"],
                "start_time": start_time,
            },
            partners_by_id={p.partner_id: p for p in (attacker, tank, healer)},
            back_view=self.back_view,
        )
        embed, _ = _build_progress_embed(
            progress_view.party_row, progress_view.partners_by_id
        )
        await interaction.edit_original_response(embed=embed, view=progress_view)
        progress_view.message = self.message
        self.stop()

    async def _back(self, interaction: Interaction):
        await interaction.response.defer()
        self.stop()
        if self.back_view and self.message:
            await interaction.edit_original_response(
                embed=self.back_view.build_embed(), view=self.back_view
            )


# ===========================================================================
# Progress view
# ===========================================================================


class BossPartyProgressView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        party_row: dict,
        partners_by_id: Dict[int, Partner],
        back_view,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.party_row = party_row
        self.partners_by_id = partners_by_id
        self.back_view = back_view
        self.message: Optional[discord.Message] = None
        self._refresh_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass

    def _refresh_buttons(self):
        self.clear_items()
        elapsed = _elapsed_hours(self.party_row["start_time"])
        ready = elapsed >= BOSS_PARTY_DURATION_HOURS

        collect_btn = ui.Button(
            label="Collect Rewards",
            style=ButtonStyle.success,
            emoji="🎁",
            disabled=not ready,
        )
        collect_btn.callback = self._collect
        self.add_item(collect_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _collect(self, interaction: Interaction):
        await interaction.response.defer()

        elapsed = _elapsed_hours(self.party_row["start_time"])
        if elapsed < BOSS_PARTY_DURATION_HOURS:
            await interaction.followup.send("The raid isn't done yet!", ephemeral=True)
            return

        row = self.party_row
        attacker = self.partners_by_id.get(row["attacker_id"])
        tank = self.partners_by_id.get(row["tank_id"])
        healer = self.partners_by_id.get(row["healer_id"])

        if not (attacker and tank and healer):
            await interaction.followup.send(
                "Could not load party data.", ephemeral=True
            )
            return

        rewards = calculate_boss_party_rewards(attacker, tank, healer, boss_name=row["boss_name"])

        # Apply rewards
        await self.bot.database.users.modify_gold(self.user_id, rewards["gold"])

        sigil_type = rewards["sigil_type"]
        sigil_count = rewards["sigil_count"]
        _SIGIL_METHODS = {
            "celestial_sigils": self.bot.database.uber.increment_sigils,
            "infernal_sigils": self.bot.database.uber.increment_infernal_sigils,
            "void_shards": self.bot.database.uber.increment_void_shards,
            "gemini_sigils": self.bot.database.uber.increment_gemini_sigils,
        }
        sigil_fn = _SIGIL_METHODS.get(sigil_type)
        if sigil_fn:
            await sigil_fn(self.user_id, self.server_id, sigil_count)

        if rewards["guild_ticket"]:
            await self.bot.database.partners.add_tickets(self.user_id, 1)

        # Grant partner EXP to all three
        level_msgs = []
        for role, partner in [
            ("attacker", attacker),
            ("tank", tank),
            ("healer", healer),
        ]:
            xp = rewards["partner_exps"][role]
            new_level, new_exp, msgs = grant_xp(partner.level, partner.exp, xp)
            partner.level = new_level
            partner.exp = new_exp
            await self.bot.database.partners.update_exp(
                self.user_id, partner.partner_id, new_exp, new_level
            )
            if msgs:
                level_msgs.append(
                    f"🤝 **{partner.name}** reached level **{new_level}**!"
                )

        # Clear dispatch state
        await self.bot.database.partners.clear_boss_party_dispatch(
            self.user_id,
            row["attacker_id"],
            row["tank_id"],
            row["healer_id"],
        )
        await self.bot.database.boss_party.delete(self.user_id, self.server_id)

        # Build result embed
        sigil_label = sigil_type.replace("_", " ").title()
        lines = [
            f"💰 **{rewards['gold']:,}** gold",
            f"🔮 **{sigil_count}×** {sigil_label}",
        ]
        if rewards["guild_ticket"]:
            lines.append("🎫 **1×** Guild Ticket")
        for role, partner in [
            ("attacker", attacker),
            ("tank", tank),
            ("healer", healer),
        ]:
            lines.append(
                f"📚 **{partner.name}** +{rewards['partner_exps'][role]:,} EXP"
            )
        lines.extend(level_msgs)

        embed = discord.Embed(
            title=f"⚔️ Raid Complete — {row['boss_name']}",
            description="\n".join(lines),
            colour=0x2ECC71,
        )
        embed.set_image(url=VICTORY_APHRODITE_GEMINI)
        self.clear_items()
        back_btn = ui.Button(label="Back to Partners", style=ButtonStyle.secondary)
        back_btn.callback = self._back
        self.add_item(back_btn)
        await interaction.edit_original_response(embed=embed, view=self)

    async def _back(self, interaction: Interaction):
        await interaction.response.defer()
        self.stop()
        if self.back_view and self.message:
            await interaction.edit_original_response(
                embed=self.back_view.build_embed(), view=self.back_view
            )
