"""
core/combat/ui/defeat_screen.py — Defeat screen embed builder.

Provides:
  create_defeat_embed — Builds the post-combat defeat embed.
"""

import discord

from core.character.prestige_display import format_prestige_name
from core.images import COMBAT_REDEMPTION
from core.models import Monster, Player


def create_defeat_embed(
    player: Player,
    monster: Monster,
    lost_xp: int,
    *,
    title: str | None = None,
    description_extra: str = "",
    curios_gained: int = 0,
    dmg_frac: float = 0.0,
    killing_blow: int = 0,
) -> discord.Embed:
    """
    Build the defeat embed.

    title            — Override the default title.  When omitted, Uber encounters
                       automatically get "The Apex Remains Unbroken"; all others
                       get "Oh dear...".
    description_extra — Text appended to the base description (use for system-
                       specific context, e.g. best-floor in Ascent).
    """
    total_damage_dealt = monster.max_hp - monster.hp
    killing_blow_str = (
        f" (**{killing_blow:,}** killing blow)" if killing_blow > 0 else ""
    )
    prestige_name = format_prestige_name(
        player.name, player.prestige_title, player.prestige_emblem
    )
    description = (
        f"The {monster.name} deals a fatal blow{killing_blow_str}!\n"
        f"{prestige_name} has been defeated after dealing {total_damage_dealt:,} damage.\n"
        f"The {monster.name} leaves with {monster.hp:,} health remaining.\n"
        f"Death 💀 takes away {lost_xp:,} XP from your essence..." + description_extra
    )

    is_uber = getattr(monster, "is_uber", False)
    if title is not None:
        embed_title = title
    elif is_uber:
        embed_title = "The Apex Remains Unbroken"
    else:
        embed_title = "Oh dear..."

    embed = discord.Embed(title=embed_title, description=description, color=0xFF0000)

    if is_uber:
        embed.add_field(
            name="Combat Assessment",
            value=(
                f"You survived long enough to deal **{dmg_frac * 100:.1f}%** damage.\n"
                f"Extracted **{curios_gained}** Curious Curios from the fray."
            ),
            inline=False,
        )

    embed.add_field(
        name="🪽 Redemption 🪽",
        value=f"({prestige_name} revives with 1 HP.)",
        inline=False,
    )
    embed.set_thumbnail(url=COMBAT_REDEMPTION)
    return embed
