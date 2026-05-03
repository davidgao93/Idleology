from typing import List

import discord

from core.images import PARTNERS_DISPATCH
from core.models import Partner
from core.partners.mechanics import (
    get_sig_combat_effect_text,
    get_sig_dispatch_effect_text,
    get_skill_effect_text,
)
from core.partners.resources import _rarity_colour, _sig_display_name, _skill_display_name, _stars


def _build_partner_embed(partner: Partner, items: dict) -> discord.Embed:
    """Detail embed for a single partner."""
    colour = _rarity_colour(partner.rarity)
    embed = discord.Embed(
        title=f"{_stars(partner.rarity)} {partner.name}",
        description=f"*{partner.title}*",
        colour=colour,
    )
    if partner.display_image:
        embed.set_thumbnail(url=partner.display_image)

    embed.add_field(
        name="📊 Stats",
        value=(
            f"⚔️ **{partner.total_attack}** ATK  "
            f"🛡️ **{partner.total_defence}** DEF  "
            f"❤️ **{partner.total_hp}** HP\n"
            f"Level **{partner.level}**"
        ),
        inline=False,
    )

    # Combat skills
    co_lines = []
    for i, (key, lvl) in enumerate(partner.combat_skills, 1):
        if key:
            co_lines.append(
                f"`S{i}` **{_skill_display_name(key)}** Lv.{lvl} — {get_skill_effect_text(key, lvl)}"
            )
        else:
            co_lines.append(f"`S{i}` *Empty*")
    if partner.rarity >= 6 and partner.sig_combat_key:
        co_lines.append(
            f"`SIG` **{_sig_display_name(partner.sig_combat_key)}** Lv.{partner.sig_combat_lvl} — "
            f"{get_sig_combat_effect_text(partner.partner_id, partner.sig_combat_lvl)}"
        )
    embed.add_field(
        name="⚔️ Combat Skills", value="\n".join(co_lines) or "None", inline=False
    )

    # Dispatch skills
    di_lines = []
    for i, (key, lvl) in enumerate(partner.dispatch_skills, 1):
        if key:
            di_lines.append(
                f"`S{i}` **{_skill_display_name(key)}** Lv.{lvl} — {get_skill_effect_text(key, lvl)}"
            )
        else:
            di_lines.append(f"`S{i}` *Empty*")
    if partner.rarity >= 6 and partner.sig_dispatch_key:
        di_lines.append(
            f"`SIG` **{_sig_display_name(partner.sig_dispatch_key)}** Lv.{partner.sig_dispatch_lvl} — "
            f"{get_sig_dispatch_effect_text(partner.partner_id, partner.sig_dispatch_lvl)}"
        )
    embed.add_field(
        name="📋 Dispatch Skills", value="\n".join(di_lines) or "None", inline=False
    )

    # Affinity (6★ only)
    if partner.rarity >= 6:
        embed.add_field(
            name="💞 Affinity",
            value=(
                f"Encounters: **{partner.affinity_encounters}/100** | "
                f"Stories read: **{partner.affinity_story_seen}/4**"
            ),
            inline=False,
        )

    # Status
    status_parts = []
    if partner.is_active_combat:
        status_parts.append("⚔️ Active Combat Partner")
    if partner.is_dispatched:
        task = partner.dispatch_task or "?"
        status_parts.append(f"📋 Dispatched ({task})")
    if not status_parts:
        status_parts.append("Idle")
    embed.add_field(name="Status", value=" | ".join(status_parts), inline=False)

    char_shards = items.get("char_shards", 0)
    embed.set_footer(
        text=(
            f"🎫 {items.get('guild_tickets', 0)} tickets  |  "
            f"⚔️ {items.get('combat_skill_shards', 0)} combat shards  |  "
            f"📋 {items.get('dispatch_skill_shards', 0)} dispatch shards"
            + (f"  |  🔷 {char_shards} char shards" if partner.rarity >= 6 else "")
        )
    )
    return embed


def _build_roster_embed(partners: List[Partner], items: dict) -> discord.Embed:
    """Roster embed showing all partners grouped by rarity with tier dividers."""
    embed = discord.Embed(title="🤝 Partner Roster", colour=0xBEBEFE)
    if not partners:
        embed.description = "You have no partners yet! Use **Pull** to obtain some."
        embed.set_footer(text=f"🎫 {items.get('guild_tickets', 0)} tickets")
        return embed

    lines = []
    for rarity in (6, 5, 4):
        tier_partners = [p for p in partners if p.rarity == rarity]
        if not tier_partners:
            continue
        lines.append(f"~~─── {_stars(rarity)} ───~~")
        for p in tier_partners:
            status = " ⚔️" if p.is_active_combat else (" 📋" if p.is_dispatched else "")
            lines.append(f"{_stars(p.rarity)} **{p.name}** Lv.{p.level}{status}")

    embed.description = "\n".join(lines)
    embed.set_footer(
        text=f"🎫 {items.get('guild_tickets', 0)} tickets  |  Select a partner to manage"
    )
    embed.set_thumbnail(url=PARTNERS_DISPATCH)
    return embed
