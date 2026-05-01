from datetime import datetime, timezone

import discord

from core.maw.mechanics import (
    DAMAGE_CAP,
    boost_available,
    boost_remaining_seconds,
    calculate_rewards,
    get_cycle_end_ts,
    get_next_cycle_id,
    is_collection_window,
    is_cycle_active,
    reward_potential_pct,
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
    fake_global_damage: int,
    record: dict | None,
    pending_record: dict | None,
) -> discord.Embed:
    embed = discord.Embed(
        title="🌑 The Maw of Infinity",
        color=0x1a0033,
    )

    cycle_end = get_cycle_end_ts(cycle_id)
    next_cycle = get_next_cycle_id(cycle_id)

    if is_cycle_active(cycle_id, now_ts):
        time_remaining = cycle_end - now_ts
        embed.description = (
            "An ancient, infinite horror tears at the fabric of reality. "
            "Warriors across the realm strike it endlessly — but it cannot be killed.\n\n"
            f"**Cycle ends in:** {_fmt_time(time_remaining)}\n"
            f"**Participants this cycle:** {participant_count:,}\n"
            f"**Total damage dealt:** {fake_global_damage:,}"
        )
    elif is_collection_window(cycle_id, now_ts):
        time_until_next = next_cycle - now_ts
        embed.description = (
            "The Maw retreats into the void... for now.\n\n"
            f"**Next cycle in:** {_fmt_time(time_until_next)}\n"
            f"**Participants last cycle:** {participant_count:,}\n"
            f"**Total damage dealt:** {fake_global_damage:,}"
        )
    else:
        time_until_start = cycle_id - now_ts
        embed.description = (
            "The Maw stirs in the deep. Warriors ready themselves.\n\n"
            f"**Next cycle in:** {_fmt_time(time_until_start)}"
        )

    if pending_record and not pending_record["rewards_collected"]:
        dmg = pending_record["damage_dealt"]
        curios, puzzle_box = calculate_rewards(dmg)
        pct = reward_potential_pct(dmg)
        reward_lines = [f"**{pct:.1f}%** reward potential reached ({dmg:,} / {DAMAGE_CAP:,} damage)"]
        if puzzle_box:
            reward_lines.append("Reward: **Curio Puzzle Box** + **Curios x{curios}**".format(curios=curios))
        else:
            reward_lines.append(f"Reward: **Curios x{curios}**")
        embed.add_field(
            name="⚠️ Uncollected Rewards",
            value="\n".join(reward_lines),
            inline=False,
        )

    if record:
        dmg = record["damage_dealt"]
        pct = reward_potential_pct(dmg)
        curios, puzzle_box = calculate_rewards(dmg)

        progress_bar = _progress_bar(pct / 100)
        contribution_lines = [
            f"**Damage dealt:** {dmg:,} / {DAMAGE_CAP:,}",
            f"**Reward potential:** {pct:.1f}%",
            progress_bar,
        ]
        if puzzle_box:
            contribution_lines.append("On track for: **Curio Puzzle Box** + **Curios x{c}**".format(c=curios))
        elif curios > 0:
            contribution_lines.append(f"On track for: **Curios x{curios}**")
        else:
            contribution_lines.append("On track for: *No reward yet (need 10%)*")

        boost_ts = record.get("boost_used_at")
        if boost_available(boost_ts, now_ts):
            contribution_lines.append("**Boost:** Ready")
        else:
            remaining = boost_remaining_seconds(boost_ts, now_ts)
            contribution_lines.append(f"**Boost:** Available in {_fmt_time(remaining)}")

        embed.add_field(
            name="Your Contribution",
            value="\n".join(contribution_lines),
            inline=False,
        )

    embed.set_footer(text="Damage cap: 500,000 · Boost cooldown: 20h · Cycle resets every Sunday 12:00 UTC")
    return embed


def _progress_bar(fraction: float, length: int = 10) -> str:
    filled = round(fraction * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}]`"
