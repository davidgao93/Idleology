# core/settlement/ui.py
"""
Stateless embed builders for the settlement system.
No DB calls, no view state — pure functions that take data and return Embeds.
"""

from __future__ import annotations

import discord

from core.emojis import GOLD_COIN
from core.settlement.constants import RESOURCE_DISPLAY_NAMES
from core.settlement.plots import PLOT_BONUS_TABLE


def build_building_list_embed() -> discord.Embed:
    _GENERATORS = [
        ("🪵 Logging Camp", "Hybrid · Timber · Produces passively and each turn"),
        ("🪨 Quarry", "Hybrid · Stone · Produces passively and each turn"),
        (f"{GOLD_COIN} Market", "Hybrid · Gold · Produces passively and each turn"),
        (
            "🐾 Companion Ranch",
            "Hybrid · Companion cookies (XP) · Produces passively and each turn",
        ),
        (
            "🏕️ War Camp",
            "Passive · Combat Stamina · Produces passively, capped at 10 on Collect",
        ),
    ]
    _CONVERTERS = [
        (
            "🔥 Foundry",
            "Hybrid · Ore → Bars (used for high level refines/reinforces)· Produces passively and each turn",
        ),
        (
            "🌲 Sawmill",
            "Hybrid · Logs → Planks (used for high level refines/reinforces)· Produces passively and each turn",
        ),
        (
            "🦴 Reliquary",
            "Hybrid · Bones → Essences (used for high level refines/reinforces)· Produces passively and each turn",
        ),
    ]
    _PASSIVES = [
        ("⚔️ Barracks", "Passive · +% Flat Attack & Defence as Bonus Attack & Defence"),
        ("⛪ Temple", "Passive · +% Propagate follower gain"),
        ("💊 Apothecary", "Passive · +Flat HP effectiveness of potions"),
        ("🔮 Uber Shrine", "Passive · Shrine statues for uber boss sigil drops"),
    ]
    _SPECIALS = [
        ("🌑 Black Market", "Special · Submit unwanted resources for loot"),
        ("🥚 Hatchery", "Special · Incubates eggs for Hematurgy blood drops · Lv50"),
        ("👶 Nursery", "Project · Produces workers per turn"),
        (
            "⚗️ Idlem Foundry",
            "Project · Produces Idlem per turn · powers the Black Market passive tree",
        ),
    ]

    def _fmt(entries):
        return "\n".join(f"**{n}** — {d}" for n, d in entries)

    embed = discord.Embed(title="📖 Regular Buildings", color=discord.Color.blue())
    embed.add_field(name="⚡ Generators", value=_fmt(_GENERATORS), inline=False)
    embed.add_field(name="🔄 Converters", value=_fmt(_CONVERTERS), inline=False)
    embed.add_field(name="🛡️ Passives", value=_fmt(_PASSIVES), inline=False)
    embed.add_field(name="✨ Special / Project", value=_fmt(_SPECIALS), inline=False)
    embed.set_footer(
        text="Hybrid buildings produce passively over time AND award a 5× burst each Development Turn."
    )
    return embed


def build_meta_buildings_embed() -> discord.Embed:
    _META = [
        ("🏠 Servant's Quarters", "Adjacent generator buildings gain +20% output."),
        ("📦 Supply Depot", "Adjacent converter buildings are 15% more effective."),
        (
            "⛪ Grand Cathedral",
            "Adjacent shrine buildings can have twice as many workers.",
        ),
        (
            "🏯 Watchtower",
            "Each regular building's worker cap is increased by +1% per its own tier (T1 → +1%, T5 → +5%). Global effect.",
        ),
        ("🏗️ Foreman's Post", "Adjacent buildings gain +25% output rate."),
        ("🌸 Shrine Garden", "Adjacent shrine buildings are 15% more effective."),
        ("⛺ Encampment", "Adjacent War Camp generates +0.5 Combat Stamina/hr."),
        (
            "💊 Apothecary Annex",
            "Adjacent Apothecary heals +40% more flat HP per potion use.",
        ),
    ]
    lines = "\n".join(f"**{n}** — {d}" for n, d in _META)
    embed = discord.Embed(
        title="⚙️ Meta Buildings",
        description=(
            "Meta buildings provide powerful passive bonuses to neighbouring plots. "
            "All meta buildings require no workers to activate. "
            "Your meta building capacity is determined by your Town Hall tier.\n\n"
            + lines
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Build meta buildings from any empty developed plot.")
    return embed


def build_plot_bonuses_embed() -> discord.Embed:
    lines = []
    for bonus_type, data in PLOT_BONUS_TABLE.items():
        emoji = data.get("emoji", "")
        label = data.get("label", bonus_type)
        desc = data.get("description", "")
        lines.append(f"{emoji} **{label}** — {desc}")

    embed = discord.Embed(
        title="🗺️ Plot Terrain Bonuses",
        description=(
            "Each developed plot has a terrain bonus rolled when first revealed. "
            "Bonuses apply to whichever building occupies that plot. **Ley Line** is special: "
            "a meta building built on a Ley Line plot projects 50% stronger bonuses to its neighbours.\n\n"
            + "\n".join(lines)
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(
        text="Use a Diviner's Rod on any plot to reroll its terrain bonus."
    )
    return embed


_COLLECTION_EMOJI: dict[str, str] = {
    "timber": "🪵 ",
    "stone": "🪨 ",
    "Market Gold": f"{GOLD_COIN} ",
}


def format_collection_changes(changes: dict) -> str:
    """Formats a production changes dict into a human-readable string."""
    positive_items: list[str] = []
    for key, value in changes.items():
        if not isinstance(value, (int, float)) or value <= 0:
            continue
        name = RESOURCE_DISPLAY_NAMES.get(
            key, key if " " in key else key.replace("_", " ").title()
        )
        emoji = _COLLECTION_EMOJI.get(key, "")
        val_str = (
            f"{int(value):,}"
            if isinstance(value, int) or float(value) == int(value)
            else f"{value:.4g}"
        )
        positive_items.append(f"{emoji}{name}: +{val_str}")

    if not positive_items:
        return "No resources produced (no workers, generators, or raw materials)."
    return "\n".join(positive_items)
