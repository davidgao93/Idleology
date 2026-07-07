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
    """Formats HP string, e.g., '100/100 ❤️ (50 🔮)' or '100/100 ❤️ (~1.2k 🔮)'"""
    display = f"{current}/{max_hp} ❤️"
    if ward > 0:
        ward_str = _format_ward(ward)
        display += f" ({ward_str} 🔮)"
    return display


def _format_ward(n: int) -> str:
    """Format ward with ~ and k/m/b suffix for large values."""
    if n < 1000:
        return str(n)

    if n < 1_000_000:
        val = n / 1000
        prec = 1 if n < 10_000 else 0
        suffix = "k"
    elif n < 1_000_000_000:
        val = n / 1_000_000
        prec = 1 if n < 10_000_000 else 0
        suffix = "m"
    elif n < 1_000_000_000_000:
        val = n / 1_000_000_000
        prec = 1 if n < 10_000_000_000 else 0
        suffix = "b"
    else:
        # Extremely large (trillions+)
        return f"~{n}"

    if prec == 1:
        formatted = f"{val:.1f}"
    else:
        formatted = f"{val:.0f}"

    if formatted.endswith(".0"):
        formatted = formatted[:-2]

    return f"~{formatted}{suffix}"


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

    # --- Alchemy: timed buffs ---
    if player.alchemy_hit_boost_pct > 0:
        lines.append(
            f"⚡ Accel  +{int(player.alchemy_hit_boost_pct * 100)}% Hit  {player.alchemy_hit_boost_turns}t left"
        )
    if player.alchemy_atk_boost_pct > 0:
        lines.append(
            f"💪 Enrage  +{int(player.alchemy_atk_boost_pct * 100)}% ATK/DEF  {player.alchemy_def_boost_turns}t left"
        )
    if player.alchemy_eclipse_strikes > 0:
        bonus_str = (
            f" (+{int(player.alchemy_eclipse_bonus * 100)}% dmg)"
            if player.alchemy_eclipse_bonus > 0
            else ""
        )
        lines.append(f"🌑 Eclipse  ×{player.alchemy_eclipse_strikes} crit{bonus_str}")
    if player.alchemy_shield_hp > 0:
        dur_str = (
            f"  · {player.alchemy_shield_turns}t"
            if player.alchemy_shield_turns > 0
            else ""
        )
        lines.append(f"🛡️ Aegis  {player.alchemy_shield_hp:,} shield{dur_str}")
    if player.alchemy_enfeeble_turns > 0:
        lines.append(
            f"🌊 Enfeeble  -{int(player.alchemy_enfeeble_pct * 100)}% ATK/DEF"
            f"  · {player.alchemy_enfeeble_turns}t"
        )
    if player.alchemy_dmg_reduction_turns > 0:
        lines.append(
            f"🩹 Painkiller  -{int(player.alchemy_dmg_reduction_pct * 100)}%"
            f"  · {player.alchemy_dmg_reduction_turns} hit{'s' if player.alchemy_dmg_reduction_turns != 1 else ''}"
        )
    if player.alchemy_linger_turns > 0:
        lines.append(
            f"🍺 Quench  {player.alchemy_linger_hp:,}/turn"
            f"  · {player.alchemy_linger_turns}t"
        )
    if player.alchemy_viper_dot_turns > 0:
        lines.append(
            f"🐍 Viper DoT  {player.alchemy_viper_dot_dmg:,}/turn"
            f"  · {player.alchemy_viper_dot_turns}t"
        )
    if player.alchemy_barrier_turns > 0:
        lines.append(
            f"🔮 Barrier  +{player.alchemy_barrier_ward_per_turn:,} Ward/turn"
            f"  · {player.alchemy_barrier_turns}t"
        )
    if player.alchemy_blood_tithe_hits > 0:
        lines.append(
            f"🩸 Blood Tithe  {int(player.alchemy_blood_tithe_leech * 100)}% leech"
            f"  · {player.alchemy_blood_tithe_hits} hit{'s' if player.alchemy_blood_tithe_hits != 1 else ''}"
        )
    if player.alchemy_ailment_immunity_turns > 0:
        lines.append(f"🌿 Panacea  immune  · {player.alchemy_ailment_immunity_turns}t")

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
            lines.append(f"⚡ Momentum {cs.hema_momentum_stacks}/5")

        if "serrated" in hp and cs.hema_serrated_total > 0:
            lines.append(f"🔪 Serrated  −{cs.hema_serrated_total} Monster ATK")

        if "haemorrhage" in hp and cs.hema_bleed_total > 0:
            lines.append(f"🩸 Bleed Pool  {cs.hema_bleed_total:,}")

        if "chain_reaction" in hp and cs.hema_chain_stacks > 0:
            lines.append(f"⛓️ Chained {cs.hema_chain_stacks}/5")

        if "phantom_reflex" in hp and cs.hema_phantom_stacks > 0:
            lines.append(f"🌀 Phantom {cs.hema_phantom_stacks}/2")

        if "executioners_rite" in hp and monster is not None:
            if monster.max_hp > 0 and monster.hp / monster.max_hp < 0.30:
                lines.append("⚔️ Executioner")

        if "fevered_strike" in hp and cs.hema_fevered_count > 0:
            lines.append(f"🔥 Fevered ×{cs.hema_fevered_count}")

        if "predators_mark" in hp and cs.hema_predators_mark:
            lines.append("🎯 Marked")

        if "flash_frost" in hp and cs.hema_frost_misses > 0:
            from core.hematurgy.mechanics import tier_val as _hema_tv

            threshold = int(_hema_tv("flash_frost", hp["flash_frost"]))
            lines.append(f"❄️ Frost {cs.hema_frost_misses}/{threshold}")

        if "spectral_waltz" in hp and cs.hema_blade_count > 0:
            lines.append(f"👻 Blades ×{cs.hema_blade_count}")

        if "defiance" in hp and cs.hema_defiance_triggered:
            lines.append("💪 Defiance")

        if "puncture" in hp and cs.hema_puncture_bleed > 0:
            lines.append(f"🩸 Punctured {cs.hema_puncture_bleed:,}")

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


def static_layout_view(container: discord.ui.Container) -> discord.ui.LayoutView:
    """A bare, non-interactive LayoutView wrapping a single Container — used
    to display final content on a message with no callbacks to dispatch."""
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


async def freeze_and_handoff(
    message: discord.Message, embed: discord.Embed, next_view=None
) -> discord.Message:
    """Sends `embed` (+ `next_view`, a classic BaseView) as a NEW message,
    points `next_view.message` at it, then deletes `message`.

    Discord's IS_COMPONENTS_V2 flag can never be removed once set on a
    message, so once CombatView has rendered a message as a LayoutView, any
    hand-off to a classic BaseView-based screen (UberReturnView,
    ApexLobbyView, ...) must happen on a fresh message rather than editing
    the old one. The old message is deleted rather than left behind — it
    has no further purpose once the new one is up, and leaving it around
    (still showing its last combat frame, possibly with stale-looking
    buttons) reads as broken rather than as a deliberate transition.
    """
    new_message = await message.channel.send(embed=embed, view=next_view)
    if next_view is not None:
        next_view.message = new_message
    try:
        await message.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass
    return new_message


def embed_to_container(embed: discord.Embed) -> discord.ui.Container:
    """Wraps a classic discord.Embed's content into a single Components V2
    Container, preserving title/description/fields/thumbnail/image/footer/color.

    Discord's IS_COMPONENTS_V2 message flag is permanent once set on a
    message — every later edit to that message must supply components,
    never content/embeds. CombatView's own terminal frames (defeat/victory
    embeds built elsewhere by defeat_screen.py/victory_screen.py) still
    return classic Embeds; this adapter re-renders them for a message
    CombatView has already turned into a LayoutView, without needing to
    touch those builders.
    """
    children: list = []

    header_lines = []
    if embed.title:
        header_lines.append(f"## {embed.title}")
    if embed.description:
        header_lines.append(embed.description)
    header_text = "\n".join(header_lines) if header_lines else None

    thumb_url = embed.thumbnail.url if embed.thumbnail else None
    if header_text and thumb_url:
        children.append(
            discord.ui.Section(header_text, accessory=discord.ui.Thumbnail(thumb_url))
        )
    else:
        if header_text:
            children.append(discord.ui.TextDisplay(header_text))
        if thumb_url:
            children.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(media=thumb_url))
            )

    for field in embed.fields:
        value = field.value or ""
        children.append(discord.ui.TextDisplay(f"**{field.name}**\n{value}"))

    if embed.image and embed.image.url:
        children.append(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=embed.image.url))
        )

    if embed.footer and embed.footer.text:
        children.append(discord.ui.TextDisplay(f"-# {embed.footer.text}"))

    if not children:
        children.append(discord.ui.TextDisplay("​"))

    return discord.ui.Container(*children, accent_color=embed.color)


def create_combat_layout(
    player: Player,
    monster: Monster,
    logs: Dict[str, str] = None,
    title_override: str = None,
    compact: bool = False,
    player_avatar_url: str | None = None,
) -> discord.ui.Container:
    """Components V2 equivalent of create_combat_embed for the live in-fight
    turn HUD. Gives the player an actual portrait (Section+Thumbnail) next
    to their stats, which the classic embed had no room for since its one
    image slot is used by the monster's art.
    """
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

    p_atk = player.get_total_attack(monster)
    p_def = player.get_total_defence()
    p_crit = player.get_current_crit_chance()
    p_pdr = player.get_total_pdr()
    p_fdr = player.get_total_fdr()

    description = f"A level **{monster.level}** {monster.name} approaches!{mod_text}"

    is_essence = getattr(monster, "is_essence", False)
    if is_uber:
        title = "UBER ENCOUNTER"
        accent = discord.Color.gold()
    elif is_essence:
        title = title_override or f"Witness {player.name} (Level {player.level})"
        accent = discord.Color.from_rgb(255, 255, 255)
    else:
        title = title_override or f"Witness {player.name} (Level {player.level})"
        accent = discord.Color.green()

    children: list = [discord.ui.TextDisplay(f"## {title}\n{description}")]

    m_atk = monster.effective_attack
    if player.alchemy_enfeeble_pct > 0 and player.alchemy_enfeeble_turns > 0:
        m_atk = int(m_atk * (1.0 - player.alchemy_enfeeble_pct))

    _mit_parts = []
    if p_pdr > 0:
        _mit_parts.append(f"PDR {p_pdr}%")
    if p_fdr > 0:
        _mit_parts.append(f"FDR {p_fdr}")
    _mit_line = ("\n" + " | ".join(_mit_parts)) if _mit_parts else ""

    player_text = (
        f"### 🧠 {player.name}\n"
        f"{get_hp_display(player.current_hp, player.total_max_hp, player.combat_ward)}\n"
        f"⚔️ {p_atk:,} | 🛡️ {p_def:,}\n"
        f"🎯 ~{p_hit}% | 🗡️ {p_crit}%{_mit_line}"
    )
    if player_avatar_url:
        children.append(
            discord.ui.Section(
                player_text,
                accessory=discord.ui.Thumbnail(
                    player_avatar_url, description=player.name
                ),
            )
        )
    else:
        children.append(discord.ui.TextDisplay(player_text))

    monster_text = (
        f"### 🐲 {monster.name}\n"
        f"{monster.hp:,}/{monster.max_hp:,} ❤️\n"
        f"⚔️ {m_atk:,} | 🛡️ {monster.effective_defence:,}\n"
        f"🎯 ~{m_hit}%"
    )
    children.append(discord.ui.TextDisplay(monster_text))
    if monster.image:
        children.append(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(media=monster.image, description=monster.name)
            )
        )

    status_text = build_status_text(player, monster)
    afflictions = build_afflictions_text(player, monster)
    log_lines = []
    for name, message in logs.items():
        if message:
            text = (
                (getattr(message, "compact_log", None) or str(message))
                if compact
                else str(message)
            )
            log_lines.append(f"**{name}**\n{text}")
            if (
                hasattr(message, "partner_log")
                and message.partner_log
                and hasattr(message, "partner_name")
                and message.partner_name
            ):
                log_lines.append(f"**{message.partner_name}**\n{message.partner_log}")

    if status_text or afflictions or log_lines:
        children.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        if status_text:
            children.append(discord.ui.TextDisplay(f"**⚙️ Status**\n{status_text}"))
        if afflictions:
            children.append(discord.ui.TextDisplay(f"**⚠️ Afflictions**\n{afflictions}"))
        if log_lines:
            children.append(discord.ui.TextDisplay("\n\n".join(log_lines)))

    return discord.ui.Container(*children, accent_color=accent)


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

    p_atk = player.get_total_attack(monster)
    p_def = player.get_total_defence()
    p_crit = player.get_current_crit_chance()
    p_pdr = player.get_total_pdr()
    p_fdr = player.get_total_fdr()
    p_ward_pct = player.get_total_ward_percentage()

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

    m_atk = monster.effective_attack
    if player.alchemy_enfeeble_pct > 0 and player.alchemy_enfeeble_turns > 0:
        m_atk = int(m_atk * (1.0 - player.alchemy_enfeeble_pct))
    embed.add_field(
        name=f"🐲 {monster.name}",
        value=(
            f"{monster.hp:,}/{monster.max_hp:,} ❤️\n"
            f"⚔️ {m_atk:,} | 🛡️ {monster.effective_defence:,}\n"
            f"🎯 ~{m_hit}%"
        ),
        inline=True,
    )
    _mit_parts = []
    if p_pdr > 0:
        _mit_parts.append(f"PDR {p_pdr}%")
    if p_fdr > 0:
        _mit_parts.append(f"FDR {p_fdr}")
    _mit_line = ("\n" + " | ".join(_mit_parts)) if _mit_parts else ""

    embed.add_field(
        name=f"🧠 {player.name}",
        value=(
            f"{get_hp_display(player.current_hp, player.total_max_hp, player.combat_ward)}\n"
            f"⚔️ {p_atk:,} | 🛡️ {p_def:,}\n"
            f"🎯 ~{p_hit}% | 🗡️ {p_crit}%"
            f"🛡️ {_mit_line}"
        ),
        inline=True,
    )

    status_text = build_status_text(player, monster)
    if status_text:
        embed.add_field(name="⚙️ Status", value=status_text, inline=False)

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
