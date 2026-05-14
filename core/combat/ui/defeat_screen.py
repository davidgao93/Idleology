"""
core/combat/ui/defeat_screen.py — Defeat screen embed builder.

Provides:
  create_defeat_embed — Builds the post-combat defeat embed.
"""

import discord

from core.images import COMBAT_REDEMPTION
from core.models import Monster, Player


def create_defeat_embed(
    player: Player,
    monster: Monster,
    lost_xp: int,
    curios_gained: int = 0,
    dmg_frac: float = 0.0,
    killing_blow: int = 0,
) -> discord.Embed:
    total_damage_dealt = monster.max_hp - monster.hp
    killing_blow_str = (
        f" (**{killing_blow:,}** killing blow)" if killing_blow > 0 else ""
    )
    description = (
        f"The {monster.name} deals a fatal blow{killing_blow_str}!\n"
        f"{player.name} has been defeated after dealing {total_damage_dealt:,} damage.\n"
        f"The {monster.name} leaves with {monster.hp:,} health remaining.\n"
        f"Death 💀 takes away {lost_xp:,} XP from your essence..."
    )

    embed = discord.Embed(title="Oh dear...", description=description, color=0xFF0000)

    # If this was an Uber fight with partial rewards
    if getattr(monster, "is_uber", False):
        embed.title = "The Apex Remains Unbroken"
        embed.add_field(
            name="Combat Assessment",
            value=f"You survived long enough to deal **{dmg_frac * 100:.1f}%** damage.\nExtracted **{curios_gained}** Curious Curios from the fray.",
            inline=False,
        )

    embed.add_field(
        name="🪽 Redemption 🪽",
        value=f"({player.name} revives with 1 HP.)",
        inline=False,
    )
    embed.set_thumbnail(url=COMBAT_REDEMPTION)
    return embed
