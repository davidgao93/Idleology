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


def build_status_text(player: Player, monster: Monster | None = None) -> str:
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

    # --- Alchemy: next-attack buffs (consumed on use) ---
    if player.alchemy_guaranteed_hit:
        lines.append("⚔️ Bottled Courage  **ready**")
    if player.alchemy_hit_boost_pct > 0:
        lines.append(
            f"⚡ Quickening Draught  +{int(player.alchemy_hit_boost_pct * 100)}% Hit  {player.alchemy_hit_boost_turns}t left"
        )
    if player.alchemy_atk_boost_pct > 0:
        lines.append(
            f"💪 Battle Draft  +{int(player.alchemy_atk_boost_pct * 100)}% ATK  **ready**"
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

    # --- Hematurgy passive states ---
    hp = getattr(player, "hematurgy_passives", None)
    if hp:
        cs = player.cs

        if "iron_momentum" in hp and cs.hema_momentum_stacks > 0:
            lines.append(f"⚡ Iron Momentum  {cs.hema_momentum_stacks}/5")

        if "serrated" in hp and cs.hema_serrated_total > 0:
            lines.append(f"🔪 Serrated  −{cs.hema_serrated_total} ATK")

        if "haemorrhage" in hp and cs.hema_bleed_total > 0:
            lines.append(f"🩸 Bleed Pool  {cs.hema_bleed_total:,}")

        if "chain_reaction" in hp and cs.hema_chain_stacks > 0:
            lines.append(f"⛓️ Chain Reaction  {cs.hema_chain_stacks}/5")

        if "phantom_reflex" in hp and cs.hema_phantom_stacks > 0:
            lines.append(f"🌀 Phantom Reflex  {cs.hema_phantom_stacks}/2")

        if "executioners_rite" in hp and monster is not None:
            if monster.max_hp > 0 and monster.hp / monster.max_hp < 0.30:
                lines.append("⚔️ Executioner's Rite  ACTIVE")

        if "fevered_strike" in hp and cs.hema_fevered_count > 0:
            lines.append(f"🔥 Fevered Strike  ×{cs.hema_fevered_count} potions")

        if "predators_mark" in hp and cs.hema_predators_mark:
            lines.append("🎯 Predator's Mark  MARKED")

        if "flash_frost" in hp and cs.hema_frost_misses > 0:
            from core.hematurgy.mechanics import tier_val as _hema_tv

            threshold = int(_hema_tv("flash_frost", hp["flash_frost"]))
            lines.append(f"❄️ Flash Frost  {cs.hema_frost_misses}/{threshold}")

        if "spectral_waltz" in hp and cs.hema_blade_count > 0:
            lines.append(f"👻 Spectral Blades  ×{cs.hema_blade_count}")

        if "defiance" in hp and cs.hema_defiance_triggered:
            lines.append("💪 Defiance  ACTIVE")

        if "puncture" in hp and cs.hema_puncture_bleed > 0:
            lines.append(f"💉 Puncture Pool  {cs.hema_puncture_bleed:,}")

    return "\n".join(lines)


def build_afflictions_text(player: Player, monster: Monster) -> str:
    """Returns a string of active player-facing debuffs from monster modifiers.
    Only shows entries relevant to the player (risk indicators / stat penalties)."""
    lines: list[str] = []

    if monster.has_modifier("Flashfire") and monster.flashfire_charges > 0:
        lines.append(f"🔥 Flashfire  {monster.flashfire_charges}/8")

    if monster.has_modifier("Hemorrhage") and monster.bleed_stacks > 0:
        v = monster.get_modifier_value("Hemorrhage")
        bleed_per_turn = int(player.total_max_hp * v * monster.bleed_stacks)
        lines.append(
            f"🩸 Hemorrhage  {monster.bleed_stacks} stacks  ({bleed_per_turn:,}/turn)"
        )

    if monster.has_modifier("Pressure Surge") and monster.pressure_stacks > 0:
        lines.append(f"⚡ Pressure  {monster.pressure_stacks}/10")

    if monster.has_modifier("Corrosion") and monster.corrode_stacks > 0:
        pdr_loss = monster.corrode_stacks * int(monster.get_modifier_value("Corrosion"))
        lines.append(f"🧪 Corroded  {monster.corrode_stacks} stacks  (−{pdr_loss} PDR)")

    if monster.has_modifier("Impending Doom") and monster.doom_stacks > 0:
        doom_threshold = int(monster.get_modifier_value("Impending Doom"))
        lines.append(f"☠️ Doom  {monster.doom_stacks}/{doom_threshold}")

    if monster.has_modifier("Temporal Collapse") and monster.temporal_window_damage > 0:
        lines.append(f"⏳ Temporal  {monster.temporal_window_damage:,} pending")

    if (
        monster.has_modifier("Death Rattle")
        and monster.death_rattle_triggered
        and monster.death_rattle_countdown > 0
    ):
        lines.append(f"☠️ Death Rattle  {monster.death_rattle_countdown} turns")

    if monster.has_modifier("Undying Resolve") and monster.undying_immune_turns > 0:
        lines.append(f"💀 Undying  immune {monster.undying_immune_turns}t")

    return "\n".join(lines)


def create_combat_embed(
    player: Player,
    monster: Monster,
    logs: Dict[str, str] = None,
    title_override: str = None,
    compact: bool = False,
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

    p_atk = player.get_total_attack()
    p_def = player.get_total_defence()

    description = f"A level **{monster.level}** {monster.name} approaches!{mod_text}"

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

    embed.add_field(
        name=f"🐲 {monster.name}",
        value=(
            f"{monster.hp:,}/{monster.max_hp:,} ❤️\n"
            f"⚔️ ATK {monster.attack:,} | 🛡️ DEF {monster.defence:,}\n"
            f"~{m_hit}% to hit"
        ),
        inline=True,
    )
    embed.add_field(
        name=f"❤️ {player.name}",
        value=(
            f"{get_hp_display(player.current_hp, player.total_max_hp, player.combat_ward)}\n"
            f"⚔️ ATK {p_atk:,} | 🛡️ DEF {p_def:,}\n"
            f"~{p_hit}% to hit"
        ),
        inline=True,
    )

    embed.add_field(
        name="⚙️ Status", value=build_status_text(player, monster), inline=False
    )

    afflictions = build_afflictions_text(player, monster)
    if afflictions:
        embed.add_field(name="⚠️ Afflictions", value=afflictions, inline=False)

    for name, message in logs.items():
        if message:
            # In compact mode use the condensed log (no flavor text); fall back to full log
            if compact:
                text = getattr(message, "compact_log", None) or str(message)
            else:
                text = str(message)
            embed.add_field(name=name, value=text, inline=False)
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
