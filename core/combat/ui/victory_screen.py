"""
core/combat/ui/victory_screen.py — Victory screen embed builder.

Provides:
  create_victory_embed — Builds the post-combat victory embed with loot summary.
"""

from typing import Any, Dict

import discord

from core.images import COMBAT_VICTORY
from core.items.models import _PART_SLOT_LABELS
from core.models import Monster, Player


def create_victory_embed(
    player: Player, monster: Monster, rewards: Dict[str, Any]
) -> discord.Embed:
    """
    Generates the Victory screen with consolidated Loot.
    """
    embed = discord.Embed(
        title="Victory! 🎉",
        description=f"{player.name} has slain the {monster.name} with {player.current_hp} ❤️ remaining!",
        color=0x00FF00,
    )
    embed.set_thumbnail(url=COMBAT_VICTORY)
    # Passive Proc Messages (Prosper, Infinite Wisdom, etc)
    if rewards.get("msgs"):
        for msg in rewards["msgs"]:
            embed.add_field(name="Bonus", value=msg, inline=False)

    embed.add_field(
        name="📚 Experience", value=f"{rewards.get('xp', 0):,} XP", inline=True
    )
    embed.add_field(name="💰 Gold", value=f"{rewards.get('gold', 0):,} GP", inline=True)

    # --- LOOT COMPILATION ---
    loot_lines = []

    # 1. Curios
    if rewards.get("curios", 0) > 0:
        count = rewards["curios"]
        loot_lines.append(f"🎁 **{count}** Curious Curio{'s' if count > 1 else ''}")

    # 2. Specials (Keys & Runes) - Mapped to emojis
    special_map = {
        "Draconic Key": "🐉",
        "Angelic Key": "🪽",
        "Soul Core": "❤️‍🔥",
        "Void Fragment": "🟣",
        "Void Key": "🗝️",
        "Rune of Potential": "💎",
        "Rune of Refinement": "🔨",
        "Rune of Imbuing": "🔅",
        "Rune of Shattering": "💥",
        "Fragment of Balance": "⚖️",
        "Magma Core": "🔥",
        "Life Root": "🌿",
        "Spirit Shard": "👻",
        "Rune of Partnership": "🤝",
        "Celestial Sigil": "🌌",
        "Infernal Sigil": "🔥",
        "Void Sigil": "🟣",
        "Gemini Sigil": "⚖️",
    }

    for item_name in rewards.get("special", []):
        emoji = special_map.get(item_name, "✨")
        loot_lines.append(f"{emoji} **{item_name}**")

    # 3. Essence Drops
    _ESSENCE_DISPLAY = {
        "power": ("✦ Essence of Power", "🔆"),
        "protection": ("✦ Essence of Protection", "🛡️"),
        "insight": ("✦ Essence of Insight", "👁️"),
        "evasion": ("✦ Essence of Evasion", "💨"),
        "blocking": ("✦ Essence of Blocking", "🧱"),
        "deftness": ("✦ Essence of Deftness", "⚡"),
        "precision": ("✦ Essence of Precision", "🎯"),
        "gluttony": ("✦ Essence of Gluttony", "🩸"),
        "cleansing": ("✦ Essence of Cleansing", "🌊"),
        "chaos": ("✦ Essence of Chaos", "🌀"),
        "annulment": ("✦ Essence of Annulment", "✂️"),
        "aphrodite": ("✦ Essence of Aphrodite's Disciple", "💎"),
        "lucifer": ("✦ Essence of Lucifer's Heir", "💎"),
        "gemini": ("✦ Essence of Gemini's Lost Twin", "💎"),
        "neet": ("✦ Essence of NEET's Voidling", "💎"),
    }
    for essence_type in rewards.get("essences", []):
        label, emoji = _ESSENCE_DISPLAY.get(
            essence_type, (f"✦ Essence of {essence_type.title()}", "✨")
        )
        loot_lines.append(f"{emoji} **{label}**")

    # 4. Equipment Drops
    # We heuristic match the description text since we don't have the object type here
    for item_desc in rewards.get("items", []):
        # Default to Weapon
        emoji = "💠"

        loot_lines.append(f"{emoji} {item_desc}")

    # 5. Monster Body Part Drop
    if rewards.get("body_part"):
        slot, mname, hp = rewards["body_part"]
        label = _PART_SLOT_LABELS.get(slot, slot)
        loot_lines.append(f"🫀 {mname}'s **{label}** (+{hp} Max HP)")

    # Add single Loot field
    if loot_lines:
        embed.add_field(name="✨__Loot__✨", value="\n".join(loot_lines), inline=False)
    else:
        embed.add_field(name="✨__Loot__✨", value="None", inline=False)

    return embed
