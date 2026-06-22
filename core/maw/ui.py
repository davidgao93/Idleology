"""
core/maw/ui.py — Stateless embed builders for the Maw of Infinity.
"""

import discord

from core.images import (
    MAW_MAIN,
    MAW_VICTORY,
    BROTHER_SOLEN_PORTRAIT,
    BROTHER_SOLEN_THUMBNAIL,
)
from core.npc_voices import get_quip
from core.maw.mechanics import (
    MAX_FIGHTS_PER_CYCLE,
    BASE_CURIOS,
    BASE_GUILD_TICKETS,
    calculate_pool_size,
    contribution_pct,
    fight_available,
    fight_remaining_seconds,
    get_cycle_end_ts,
    get_next_cycle_id,
    get_weekly_weakness,
    is_collection_window,
    is_cycle_active,
)


def _fmt_time(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def build_maw_embed(
    cycle_id: int,
    now_ts: int,
    participant_count: int,
    total_cycle_damage: int,
    record: dict | None,
    pending_record: dict | None,
    pending_cycle_id: int | None = None,
    pending_total_damage: int = 0,
    pending_participant_count: int = 0,
) -> discord.Embed:
    embed = discord.Embed(title="🌑 The Maw of Infinity", color=0x1A0033)
    embed.set_author(name="Brother Solen", icon_url=BROTHER_SOLEN_PORTRAIT)
    embed.set_footer(text=get_quip("maw"))

    cycle_end = get_cycle_end_ts(cycle_id)
    in_collection = pending_cycle_id is not None and is_collection_window(
        pending_cycle_id, now_ts
    )

    # --- Main description ---
    if is_cycle_active(cycle_id, now_ts):
        time_remaining = cycle_end - now_ts
        embed.description = (
            "An ancient, infinite horror tears at the fabric of reality. "
            "Warriors across the realm strike it endlessly — but it cannot be killed.\n\n"
            f"**Cycle ends in:** {_fmt_time(time_remaining)}\n"
            f"**Warriors this cycle:** {participant_count:,}\n"
            f"**Total damage dealt:** {total_cycle_damage:,}"
        )
    elif in_collection:
        next_cycle_start = get_next_cycle_id(pending_cycle_id)
        time_until_next = next_cycle_start - now_ts
        embed.description = (
            "The Maw retreats into the void... for now.\n\n"
            f"**Next cycle in:** {_fmt_time(time_until_next)}\n"
            f"**Warriors last cycle:** {participant_count:,}\n"
            f"**Total damage dealt:** {total_cycle_damage:,}"
        )
    else:
        time_until_start = cycle_id - now_ts
        embed.description = (
            "The Maw stirs in the deep. Warriors ready themselves.\n\n"
            f"**Next cycle in:** {_fmt_time(time_until_start)}"
        )

    # --- Uncollected rewards panel ---
    if pending_record and not pending_record["rewards_collected"]:
        player_dmg = pending_record["damage_dealt"]
        pct = contribution_pct(player_dmg, pending_total_damage)

        # Estimate rewards using pending cycle data if available
        if pending_total_damage > 0 and pending_participant_count > 0:
            pool = calculate_pool_size(pending_participant_count)
            pool_share = round(pool * pct / 100)
            curio_est = BASE_CURIOS + pool_share
            reward_lines = [
                f"**{pct:.1f}%** contribution  ({player_dmg:,} damage)",
                f"Reward: **{curio_est} Curios** + **{BASE_GUILD_TICKETS} Guild Tickets**",
                "*(Top 3 also receive a Curio Puzzle Box — collect to confirm)*",
            ]
        else:
            reward_lines = [
                f"**Damage dealt:** {player_dmg:,}",
                f"Base reward: **{BASE_CURIOS} Curios** + **{BASE_GUILD_TICKETS} Guild Tickets** + pool share",
                "*(Collect to finalise your contribution percentage)*",
            ]

        embed.add_field(
            name="⚠️ Uncollected Rewards",
            value="\n".join(reward_lines),
            inline=False,
        )

    # --- Active-cycle contribution panel ---
    if record:
        dmg = record["damage_dealt"]
        fights_done = record.get("fights_this_cycle", 0)
        fights_left = max(0, MAX_FIGHTS_PER_CYCLE - fights_done)
        last_fight_ts = record.get("last_fight_ts")
        pct = contribution_pct(dmg, total_cycle_damage)

        lines = [
            f"**Damage dealt:** {dmg:,}",
            f"**Contribution:** {pct:.1f}% of total",
            f"**Fights used:** {fights_done}/{MAX_FIGHTS_PER_CYCLE}  ({fights_left} remaining)",
        ]

        if fights_left <= 0:
            lines.append("**Status:** All fights used this cycle")
        elif fight_available(last_fight_ts, fights_done, now_ts):
            lines.append("**Next fight:** Ready! ⚔️")
        else:
            remaining = fight_remaining_seconds(last_fight_ts, now_ts)
            lines.append(f"**Next fight:** {_fmt_time(remaining)}")

        embed.add_field(name="Your Contribution", value="\n".join(lines), inline=False)

    # --- Weekly Weakness ---
    w = get_weekly_weakness()
    embed.add_field(
        name=f"{w['emoji']} Weekly Weakness — {w['name']}",
        value=w["description"],
        inline=False,
    )

    embed.set_footer(
        text=f"Up to {MAX_FIGHTS_PER_CYCLE} fights/cycle · 20h cooldown · Resets every Sunday 12:00 UTC"
    )

    if pending_record and not pending_record["rewards_collected"]:
        embed.set_image(url=MAW_VICTORY)
    else:
        embed.set_thumbnail(url=BROTHER_SOLEN_THUMBNAIL)

    return embed
