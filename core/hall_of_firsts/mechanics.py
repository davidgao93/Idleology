"""core/hall_of_firsts/mechanics.py — Claim + announcement logic for the Hall of Firsts.

try_claim_first is the single entry point every trigger site calls through
(see core/hall_of_firsts/triggers.py). It is safe to call speculatively —
callers do not need to check "is this already claimed" themselves.
"""

from __future__ import annotations

from datetime import datetime, timezone

import discord

from core.character.prestige_display import format_prestige_name
from core.emojis import EMBLEM_CATALOG
from core.hall_of_firsts.data import CATEGORIES_BY_KEY, HALL_ANNOUNCE_CHANNEL_ID


async def try_claim_first(bot, user_id: str, category_key: str) -> bool:
    """Attempts to claim `category_key` for `user_id`. Returns True if this call
    won the claim. Never raises — a failure here must not interrupt the
    gameplay action that triggered it."""
    try:
        category = CATEGORIES_BY_KEY[category_key]
        user_row = await bot.database.users.get_by_user_id(user_id)
        if not user_row:
            return False

        name = user_row["prestige_display_name"] or user_row["name"]
        title = user_row["prestige_title"]
        title = None if not title or title == "none" else title
        # users.prestige_emblem stores the EMBLEM_CATALOG *key* (e.g.
        # "monster_cheeks"), not the emoji itself — resolve it here so the
        # snapshot (and the announcement below) show the real emoji instead
        # of the literal key text.
        emblem_entry = EMBLEM_CATALOG.get(user_row["prestige_emblem"] or "")
        emblem = emblem_entry[1] if emblem_entry else None
        appearance = user_row["appearance"]

        won = await bot.database.hall_of_firsts.try_claim(
            category_key,
            user_id,
            datetime.now(timezone.utc).isoformat(),
            name,
            title,
            emblem,
            appearance,
        )
        if won:
            await _announce(bot, category, name, title, emblem, appearance)
        return won
    except Exception:
        try:
            bot.logger.error(
                f"hall_of_firsts.try_claim_first failed for user {user_id}, category {category_key}",
                exc_info=True,
            )
        except Exception:
            pass  # Logging must never raise
        return False


async def _announce(
    bot,
    category,
    name: str,
    title: str | None,
    emblem: str | None,
    appearance: str | None,
) -> None:
    channel = bot.get_channel(HALL_ANNOUNCE_CHANNEL_ID)
    if channel is None:
        return
    decorated = format_prestige_name(name, title or "", emblem or "")
    embed = discord.Embed(
        title=f"{category.emoji} A New Hall of Firsts Entry!",
        description=f"**{decorated}** is the first to achieve **{category.name}**!\n*{category.flavor}*",
        color=discord.Color.gold(),
    )
    if appearance:
        embed.set_thumbnail(url=appearance)
    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass
