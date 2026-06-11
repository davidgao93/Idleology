"""
core/combat/ui/victory_screen.py — Victory screen embed builder.

Provides:
  create_victory_embed — Builds the post-combat victory embed with loot summary.
"""

import json
import os
from typing import Any, Dict, Optional

import discord

from core.images import COMBAT_VICTORY

_EXP_TABLE: dict = {}


def _load_exp_table() -> dict:
    global _EXP_TABLE
    if not _EXP_TABLE:
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "exp.json")
        with open(path, encoding="utf-8") as f:
            _EXP_TABLE = json.load(f)["levels"]
    return _EXP_TABLE


def _exp_progress_str(level: int, exp: int) -> str:
    if level >= 100:
        return "MAX"
    table = _load_exp_table()
    needed = table.get(str(level), 0)
    if needed <= 0:
        return ""
    pct = min(99.9, exp / needed * 100)
    return f"{pct:.1f}% to Lv.{level + 1}"
from core.items.models import _PART_SLOT_LABELS
from core.models import Monster, Player


def create_victory_embed(
    player: Player,
    monster: Monster,
    rewards: Dict[str, Any],
    *,
    cfg: Optional[Dict[str, Any]] = None,
) -> discord.Embed:
    """
    Generates the Victory screen with consolidated Loot.

    cfg — Optional overrides dict.  Recognised keys:

      "title"         str   Override the default "Victory! 🎉" title.
      "thumbnail_url" str   Override the default COMBAT_VICTORY thumbnail.
      "image_url"     str   Set the embed's main image (no default).
      "extra_fields"  list  Each item is {"name": ..., "value": ..., "inline": bool}
                            appended after the Loot field.  Use for boss-specific
                            follow-up prompts (e.g. Lucifer's Soul Core choice).
    """
    cfg = cfg or {}

    embed = discord.Embed(
        title=cfg.get("title", "Victory! 🎉"),
        description=f"{player.name} has slain the {monster.name} with {player.current_hp} ❤️ remaining!",
        color=0x00FF00,
    )
    embed.set_thumbnail(url=cfg.get("thumbnail_url") or COMBAT_VICTORY)
    if img := cfg.get("image_url"):
        embed.set_image(url=img)
    # Passive Proc Messages (Prosper, Infinite Wisdom, etc) — all compiled into one field
    if rewards.get("msgs"):
        embed.add_field(name="Bonus", value="\n".join(rewards["msgs"]), inline=False)

    _xp_progress = _exp_progress_str(player.level, player.exp)
    _xp_suffix = f"\n*{_xp_progress}*" if _xp_progress else ""
    embed.add_field(
        name="📚 Experience",
        value=f"+{rewards.get('xp', 0):,} XP{_xp_suffix}",
        inline=True,
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
    for item_desc in rewards.get("items", []):
        loot_lines.append(f"💠 {item_desc}")

    # 5. Apex Shard drops (from apex hunt victory)
    if rewards.get("apex_shards"):
        _SHARD_EMOJIS = {
            "pyre": "🔥",
            "tempest": "⚡",
            "bulwark": "🏰",
            "verdant": "🌿",
            "fortune": "💰",
            "rift": "🌀",
        }
        shard_type = rewards["apex_shards"]["shard_type"]
        shard_amt = rewards["apex_shards"]["shard_amount"]
        emoji = _SHARD_EMOJIS.get(shard_type, "💎")
        loot_lines.append(
            f"{emoji} **{shard_amt}x {shard_type.title()} Shard{'s' if shard_amt > 1 else ''}**"
        )
    if rewards.get("apex_meta"):
        from core.apex.data import META_SHARD_DISPLAY

        for meta_key, count in rewards["apex_meta"].items():
            display_name, _ = META_SHARD_DISPLAY.get(
                meta_key, (f"✨ {meta_key.replace('_', ' ').title()}", "")
            )
            for _ in range(count):
                loot_lines.append(display_name)
    if rewards.get("soul_fragments"):
        frags = rewards["soul_fragments"]
        loot_lines.append(f"🔘 **{frags}x Soul Fragment{'s' if frags > 1 else ''}**")

    # 6. Monster Body Part Drop
    if rewards.get("body_part"):
        slot, mname, hp = rewards["body_part"]
        label = _PART_SLOT_LABELS.get(slot, slot)
        loot_lines.append(f"🫀 {mname}'s **{label}** (+{hp} Max HP)")

    embed.add_field(
        name="✨__Loot__✨",
        value="\n".join(loot_lines) if loot_lines else "None",
        inline=False,
    )

    # Extra fields from cfg (e.g. Lucifer's Soul Core prompt)
    for field in cfg.get("extra_fields", []):
        embed.add_field(
            name=field["name"],
            value=field["value"],
            inline=field.get("inline", False),
        )

    return embed
