"""
core/combat/ui/combat_embed.py — In-fight embed builders.

Provides:
  get_hp_display      — Formats HP string for display
  build_status_text   — Player status sidebar (potions, buffs, stacks)
  create_combat_embed — Main battle embed shown each turn
"""

from typing import Dict

import discord

from core.models import Monster, Player


def get_hp_display(current: int, max_hp: int, ward: int) -> str:
    """Formats HP string, e.g., '100/100 ❤️ (50 🔮)'"""
    display = f"{current}/{max_hp} ❤️"
    if ward > 0:
        display += f" ({ward} 🔮)"
    return display


def build_status_text(player: Player) -> str:
    lines: list[str] = []

    # --- Paradise Jewel ---
    jop = getattr(player, "jewel_of_paradise", None)
    if jop and jop.get("equipped_skill"):
        from core.paradise import mechanics as M
        from core.paradise.data import SKILL_JEWELS

        skill_key = jop["equipped_skill"]
        defn = SKILL_JEWELS.get(skill_key)
        charges = jop.get("skill_charges", {}).get(skill_key, 0)
        mastery = M.mastery_bonus(jop)
        eff_lvl = M.get_effective_level(skill_key, jop, mastery)
        compression = M.get_compression_bonus(jop)
        threshold = max(1, M.get_threshold(skill_key, eff_lvl) - compression)
        emoji = defn.emoji if defn else "💎"
        name = defn.name if defn else skill_key.title()
        lines.append(f"{emoji} **{name}**  {charges} / {threshold}")

        if skill_key == "cataclysm" and player.jewel_cataclysm_primed:
            lines.append("💥 Cataclysm  **PRIMED**")
        if skill_key == "onslaught" and player.jewel_onslaught_primed:
            lines.append(
                f"🔥 Onslaught  **PRIMED** (+{player.jewel_onslaught_bonus_pct:.0f}%)"
            )
        if skill_key == "wardforge" and player.jewel_wardforge_bonus_dmg > 0:
            lines.append(f"🛡️ Wardforge  +{player.jewel_wardforge_bonus_dmg:,} pending")
        if skill_key == "acrimony" and player.jewel_acrimony_dot > 0:
            lines.append(
                f"🐍 Acrimony DoT  {player.jewel_acrimony_dot_dmg:,}/turn"
                f"  · {player.jewel_acrimony_dot}t left"
            )

    # --- Potions (always shown) ---
    lines.append(f"🧪 Potions  {player.potions}")

    # --- Alchemy: next-attack buffs (consumed on use) ---
    if player.alchemy_guaranteed_hit:
        lines.append("⚔️ Bottled Courage  **ready**")
    if player.alchemy_atk_boost_pct > 0:
        lines.append(
            f"💪 Warrior's Draft  +{int(player.alchemy_atk_boost_pct * 100)}% ATK  **ready**"
        )

    # --- Alchemy: timed buffs ---
    if player.alchemy_def_boost_turns > 0:
        lines.append(
            f"🛡️ Iron Skin  +{int(player.alchemy_def_boost_pct * 100)}%"
            f"  · {player.alchemy_def_boost_turns}t"
        )
    if player.alchemy_dmg_reduction_turns > 0:
        lines.append(
            f"🩹 Dulled Pain  -{int(player.alchemy_dmg_reduction_pct * 100)}%"
            f"  · {player.alchemy_dmg_reduction_turns}t"
        )
    if player.alchemy_linger_turns > 0:
        lines.append(
            f"🌿 Linger  {player.alchemy_linger_hp:,}/turn"
            f"  · {player.alchemy_linger_turns}t"
        )
    if player.alchemy_overcap_hp > 0:
        lines.append(f"💥 Temp HP  {player.alchemy_overcap_hp:,}")

    # --- Weapon / accessory stacks ---
    if player.voracious_stacks > 0:
        lines.append(f"🔥 Voracious  ×{player.voracious_stacks}")
    if player.gaze_stacks > 0:
        lines.append(f"👁️ Void Gaze  {player.gaze_stacks}/30")
    if player.hunger_stacks > 0:
        lines.append(f"⬛ Hunger  {player.hunger_stacks}/10")

    # --- Lucifer PDR burst (ward-shatter bonus) ---
    if player.lucifer_pdr_burst > 0:
        lines.append(f"🔥 PDR Burst  +{player.lucifer_pdr_burst}%")

    return "\n".join(lines)


def create_combat_embed(
    player: Player,
    monster: Monster,
    logs: Dict[str, str] = None,
    title_override: str = None,
) -> discord.Embed:
    logs = logs or {}
    is_uber = getattr(monster, "is_uber", False)

    from core.combat.calc.hit_calc import (
        calculate_hit_chance,
        calculate_monster_hit_chance,
    )

    p_hit = int(calculate_hit_chance(player, monster) * 100)
    m_hit = int(calculate_monster_hit_chance(player, monster) * 100)

    mod_text = ""
    if monster.modifiers:
        mod_text = "\n__Modifiers:__ " + ", ".join(
            f"**{m}**" for m in monster.display_modifiers
        )

    description = (
        f"A level **{monster.level}** {monster.name} approaches!\n"
        f"{mod_text}\n\n"
        f"~{p_hit}% to hit | ~{m_hit}% to be hit"
    )

    # UBER OVERRIDES
    is_essence = getattr(monster, "is_essence", False)
    if is_uber:
        title = "UBER ENCOUNTER"
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

    embed.add_field(name="⚙️ Status", value=build_status_text(player), inline=False)

    for name, message in logs.items():
        if message:
            embed.add_field(name=name, value=str(message), inline=False)
            # Partner per-turn effects are stored on PlayerTurnResult
            if (
                hasattr(message, "partner_log")
                and message.partner_log
                and hasattr(message, "partner_name")
                and message.partner_name
            ):
                embed.add_field(
                    name=message.partner_name,
                    value=message.partner_log,
                    inline=False,
                )

    return embed
