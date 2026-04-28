from typing import Any, Dict

import discord

from core.models import Monster, Player


def get_hp_display(current: int, max_hp: int, ward: int) -> str:
    """Formats HP string, e.g., '100/100 ❤️ (50 🔮)'"""
    display = f"{current}/{max_hp} ❤️"
    if ward > 0:
        display += f" ({ward} 🔮)"
    return display


def create_combat_embed(
    player: Player,
    monster: Monster,
    logs: Dict[str, str] = None,
    title_override: str = None,
) -> discord.Embed:
    logs = logs or {}
    is_uber = getattr(monster, "is_uber", False)

    from core.combat.calcs import calculate_hit_chance, calculate_monster_hit_chance

    p_hit = int(calculate_hit_chance(player, monster) * 100)
    m_hit = int(calculate_monster_hit_chance(player, monster) * 100)

    mod_text = ""
    if monster.modifiers:
        mod_text = "\n__Modifiers:__ " + ", ".join(
            f"**{m}**" for m in monster.modifiers
        )

    description = (
        f"A level **{monster.level}** {monster.name} approaches!\n"
        f"{mod_text}\n\n"
        f"~{p_hit}% to hit | ~{m_hit}% to be hit"
    )

    # UBER OVERRIDES
    is_essence = getattr(monster, "is_essence", False)
    if is_uber:
        title = "🌌 UBER ENCOUNTER: Celestial Apex"
        color = 0xFFD700  # Gold
    elif is_essence:
        title = (
            title_override
            if title_override
            else f"Witness {player.name} (Level {player.level})"
        )
        color = 0xFFFFFF  # White — Calcified monster
    else:
        title = (
            title_override
            if title_override
            else f"Witness {player.name} (Level {player.level})"
        )
        color = 0x00FF00  # Green

    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_image(url=monster.image)

    embed.add_field(name="🐲 HP", value=f"{monster.hp}/{monster.max_hp}", inline=True)
    embed.add_field(
        name="❤️ HP",
        value=get_hp_display(
            player.current_hp, player.total_max_hp, player.combat_ward
        ),
        inline=True,
    )

    for name, message in logs.items():
        if message:
            embed.add_field(name=name, value=message, inline=False)

    return embed


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
    embed.set_thumbnail(url="https://i.imgur.com/jr5PUj5.png")
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
        "warding": ("✦ Essence of Unyielding", "🧱"),
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
        _PART_LABELS = {
            "head": "Head", "torso": "Torso",
            "right_arm": "Right Arm", "left_arm": "Left Arm",
            "right_leg": "Right Leg", "left_leg": "Left Leg",
            "cheeks": "Cheeks", "organs": "Organs",
        }
        slot, mname, hp = rewards["body_part"]
        label = _PART_LABELS.get(slot, slot)
        loot_lines.append(f"🫀 {mname}'s **{label}** (+{hp} Max HP)")

    # Add single Loot field
    if loot_lines:
        embed.add_field(name="✨__Loot__✨", value="\n".join(loot_lines), inline=False)
    else:
        embed.add_field(name="✨__Loot__✨", value="None", inline=False)

    return embed


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
    embed.set_thumbnail(url="https://i.imgur.com/kqGzbvb.png")
    return embed
