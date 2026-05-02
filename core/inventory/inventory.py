from typing import List, Union

import discord

from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon

_SLOT_EMOJIS = {
    "weapon": "⚔️",
    "armor": "🛡️",
    "helmet": "🎩",
    "glove": "🧤",
    "boot": "👢",
    "accessory": "📿",
}
_SLOT_LABELS = {
    "weapon": "Weapon",
    "armor": "Armor",
    "helmet": "Helmet",
    "glove": "Glove",
    "boot": "Boot",
    "accessory": "Accessory",
}
_SLOT_ORDER = ["weapon", "armor", "helmet", "glove", "boot", "accessory"]

_ITEM_IMAGES = {
    "weapon":    "https://i.imgur.com/OeyEXrs.jpeg",
    "armor":     "https://i.imgur.com/xhkOm99.jpeg",
    "helmet":    "https://i.imgur.com/NqYy6KH.jpeg",
    "glove":     "https://i.imgur.com/hPdjWQ8.jpeg",
    "boot":      "https://i.imgur.com/CVslwcK.jpeg",
    "accessory": "https://i.imgur.com/k4ZDJ2s.jpeg",
}

Equipment = Union[Weapon, Armor, Accessory, Glove, Boot]


# ---------------------------------------------------------------------------
# Per-type detail field builders (called by get_item_details_embed)
# ---------------------------------------------------------------------------

def _pdesc(table: dict, name: str) -> str:
    """Look up a passive description, normalizing underscores to spaces."""
    return table.get(name.lower().replace("_", " "), "")


def _add_passive_field(embed, name_label: str, passive_name: str, desc: str):
    title = passive_name.replace('_', ' ').title()
    value = desc if desc else "​"
    embed.add_field(name=f"{name_label} — {title}", value=value, inline=False)


def _weapon_fields(embed, item, passive_desc: dict, infernal_desc: dict):
    if getattr(item, "attack", 0):
        embed.add_field(name="⚔️ Attack", value=f"{item.attack:,}", inline=True)
    if getattr(item, "defence", 0):
        embed.add_field(name="🛡️ Defence", value=f"{item.defence:,}", inline=True)
    if getattr(item, "rarity", 0):
        embed.add_field(name="✨ Rarity", value=f"{item.rarity:,}%", inline=True)
    embed.add_field(name="🔧 Refinement", value=f"+{item.refinement_lvl}", inline=True)

    if item.passive not in ("none", ""):
        _add_passive_field(embed, "Passive", item.passive,
                           _pdesc(passive_desc, item.passive))
    if item.p_passive not in ("none", ""):
        _add_passive_field(embed, "Pinnacle", item.p_passive,
                           _pdesc(passive_desc, item.p_passive))
    if item.u_passive not in ("none", ""):
        _add_passive_field(embed, "Utmost", item.u_passive,
                           _pdesc(passive_desc, item.u_passive))
    inf = getattr(item, "infernal_passive", "none") or "none"
    if inf not in ("none", ""):
        _add_passive_field(embed, "🔥 Infernal", inf,
                           _pdesc(infernal_desc, inf))


def _armor_fields(embed, item, passive_desc: dict, celestial_desc: dict):
    # Main stat (ATK or DEF)
    main_stat_type = getattr(item, "main_stat_type", "def")
    main_stat = getattr(item, "main_stat", 0)
    reinforcement_lvl = getattr(item, "reinforcement_lvl", 0)
    if main_stat > 0:
        stat_label = "⚔️ ATK" if main_stat_type == "atk" else "🛡️ DEF"
        reinforce_str = f"  (+{reinforcement_lvl})" if reinforcement_lvl > 0 else ""
        embed.add_field(name=f"{stat_label}{reinforce_str}", value=f"{main_stat:,}", inline=True)

    # Secondary stat
    if getattr(item, "block", 0):
        embed.add_field(name="🛑 Block", value=f"{item.block:,}%", inline=True)
    if getattr(item, "evasion", 0):
        embed.add_field(name="💨 Evasion", value=f"{item.evasion:,}%", inline=True)
    if getattr(item, "ward", 0):
        embed.add_field(name="🔮 Ward", value=f"{item.ward:,}%", inline=True)

    # Tertiary stat
    if getattr(item, "pdr", 0):
        embed.add_field(name="🛡️ PDR", value=f"{item.pdr:,}%", inline=True)
    if getattr(item, "fdr", 0):
        embed.add_field(name="💫 FDR", value=f"{item.fdr:,}", inline=True)

    reinforces_remaining = getattr(item, "reinforces_remaining", 0)
    embed.add_field(
        name="Upgrades",
        value=(
            f"Tempers Remaining: **{item.temper_remaining}**  ·  "
            f"Imbue Attempts: **{item.imbue_remaining}**  ·  "
            f"Reinforces Remaining: **{reinforces_remaining}**"
        ),
        inline=False,
    )

    if item.passive not in ("none", ""):
        _add_passive_field(embed, "Passive", item.passive,
                           _pdesc(passive_desc, item.passive))
    cel = getattr(item, "celestial_passive", "none") or "none"
    if cel not in ("none", ""):
        _add_passive_field(embed, "🌌 Celestial", cel,
                           _pdesc(celestial_desc, cel))


def _helmet_fields(embed, item, passive_funcs: dict):
    rlvl = getattr(item, "reinforcement_lvl", 0)
    rlvl_str = f" **(+{rlvl})**" if rlvl > 0 else ""
    primary = _primary_stat_col_gear(item)
    if getattr(item, "defence", 0):
        label = f"🛡️ Defence{rlvl_str if primary == 'defence' else ''}"
        embed.add_field(name=label, value=f"{item.defence:,}", inline=True)
    if getattr(item, "ward", 0):
        label = f"🔮 Ward{rlvl_str if primary == 'ward' else ''}"
        embed.add_field(name=label, value=f"{item.ward:,}%", inline=True)
    if getattr(item, "pdr", 0):
        embed.add_field(name="🛡️ PDR", value=f"{item.pdr:,}%", inline=True)
    if getattr(item, "fdr", 0):
        embed.add_field(name="💫 FDR", value=f"{item.fdr:,}", inline=True)
    reinforces_remaining = getattr(item, "reinforces_remaining", 0)
    embed.add_field(
        name="Upgrades",
        value=f"Enchants Remaining: **{item.potential_remaining}**  ·  Reinforces Remaining: **{reinforces_remaining}**",
        inline=True,
    )

    if item.passive not in ("none", ""):
        lvl = getattr(item, "passive_lvl", 0)
        fn = passive_funcs.get(item.passive.lower())
        desc = fn(lvl) if fn and lvl > 0 else ""
        lvl_str = f" (Lv.{lvl})" if lvl > 0 else ""
        embed.add_field(
            name=f"Passive — {item.passive.replace('_', ' ').title()}{lvl_str}",
            value=desc if desc else "​",
            inline=False,
        )

    _essence_fields(embed, item)


def _primary_stat_col_gear(item) -> str:
    """Returns the column name that reinforcement bumps for Glove/Boot/Helmet."""
    if isinstance(item, (Glove, Boot)):
        if getattr(item, "attack", 0) > 0:
            return "attack"
        if getattr(item, "defence", 0) > 0:
            return "defence"
        return "ward"
    # Helmet
    if getattr(item, "defence", 0) > 0:
        return "defence"
    return "ward"


def _glove_boot_fields(embed, item, passive_funcs: dict):
    rlvl = getattr(item, "reinforcement_lvl", 0)
    rlvl_str = f" **(+{rlvl})**" if rlvl > 0 else ""
    primary = _primary_stat_col_gear(item)
    if getattr(item, "attack", 0):
        label = f"⚔️ Attack{rlvl_str if primary == 'attack' else ''}"
        embed.add_field(name=label, value=f"{item.attack:,}", inline=True)
    if getattr(item, "defence", 0):
        label = f"🛡️ Defence{rlvl_str if primary == 'defence' else ''}"
        embed.add_field(name=label, value=f"{item.defence:,}", inline=True)
    if getattr(item, "ward", 0):
        label = f"🔮 Ward{rlvl_str if primary == 'ward' else ''}"
        embed.add_field(name=label, value=f"{item.ward:,}%", inline=True)
    if getattr(item, "pdr", 0):
        embed.add_field(name="🛡️ PDR", value=f"{item.pdr:,}%", inline=True)
    if getattr(item, "fdr", 0):
        embed.add_field(name="💫 FDR", value=f"{item.fdr:,}", inline=True)
    reinforces_remaining = getattr(item, "reinforces_remaining", 0)
    embed.add_field(
        name="Upgrades",
        value=f"Enchants Remaining: **{item.potential_remaining}**  ·  Reinforces Remaining: **{reinforces_remaining}**",
        inline=True,
    )

    if item.passive not in ("none", ""):
        lvl = getattr(item, "passive_lvl", 0)
        fn = passive_funcs.get(item.passive.lower())
        desc = fn(lvl) if fn and lvl > 0 else ""
        lvl_str = f" (Lv.{lvl})" if lvl > 0 else ""
        embed.add_field(
            name=f"Passive — {item.passive.replace('_', ' ').title()}{lvl_str}",
            value=desc if desc else "​",
            inline=False,
        )

    _essence_fields(embed, item)


def _accessory_fields(embed, item, passive_funcs: dict, void_desc: dict):
    if getattr(item, "attack", 0):
        embed.add_field(name="⚔️ Attack", value=f"{item.attack:,}", inline=True)
    if getattr(item, "defence", 0):
        embed.add_field(name="🛡️ Defence", value=f"{item.defence:,}", inline=True)
    if getattr(item, "rarity", 0):
        embed.add_field(name="✨ Rarity", value=f"{item.rarity:,}%", inline=True)
    if getattr(item, "ward", 0):
        embed.add_field(name="🔮 Ward", value=f"{item.ward:,}%", inline=True)
    if getattr(item, "crit", 0):
        embed.add_field(name="🎯 Crit", value=f"{item.crit:,}", inline=True)
    embed.add_field(name="Enchants Remaining", value=str(item.potential_remaining), inline=True)

    if item.passive not in ("none", ""):
        lvl = getattr(item, "passive_lvl", 0)
        fn = passive_funcs.get(item.passive.lower())
        desc = fn(lvl) if fn and lvl > 0 else ""
        lvl_str = f" (Lv.{lvl})" if lvl > 0 else ""
        embed.add_field(
            name=f"Passive — {item.passive.replace('_', ' ').title()}{lvl_str}",
            value=desc if desc else "​",
            inline=False,
        )
    void_p = getattr(item, "void_passive", "none") or "none"
    if void_p not in ("none", ""):
        _add_passive_field(embed, "🌀 Void", void_p,
                           _pdesc(void_desc, void_p))


def _essence_fields(embed, item):
    from core.items.essence_views import ESSENCE_DISPLAY, _format_slot_value, _get_essence_brief

    lines = []
    for i in (1, 2, 3):
        t = getattr(item, f"essence_{i}", "none") or "none"
        v = getattr(item, f"essence_{i}_val", 0.0) or 0.0
        if t != "none":
            e_name, emoji = ESSENCE_DISPLAY.get(t, (t.title(), "✦"))
            stat_str = _format_slot_value(t, v, item)
            lines.append(f"**Slot {i}:** {emoji} {e_name}\n   ↳ {stat_str}")
        else:
            lines.append(f"**Slot {i}:** *— Empty —*")

    corrupted = getattr(item, "corrupted_essence", "none") or "none"
    if corrupted != "none":
        c_name, c_emoji = ESSENCE_DISPLAY.get(corrupted, (corrupted.title(), "💠"))
        slot_key = "glove" if isinstance(item, Glove) else "boot" if isinstance(item, Boot) else "helmet"
        lines.append(f"**Corrupted:** {c_emoji} {c_name}\n   ↳ {_get_essence_brief(corrupted, slot_key)}")
    else:
        lines.append("**Corrupted:** *— Empty —*")

    embed.add_field(name="💎 Essences", value="\n".join(lines), inline=False)


class InventoryUI:
    @staticmethod
    def get_list_embed(
        player_name: str,
        items: List[Equipment],
        page: int,
        total_pages: int,
        equipped_id: int = None,
        category_emoji: str = "🎒",
    ) -> discord.Embed:
        """
        Generates the inventory list embed.
        """
        embed = discord.Embed(
            title=f"{category_emoji}",
            description=f"{player_name}'s Inventory (Page {page + 1}/{total_pages})",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/Kr0xq5N.png")

        if not items:
            embed.description = "This pouch is empty."
            return embed

        display_text = ""
        for index, item in enumerate(items):
            if len(display_text) > 950:
                display_text += f"\n... and {len(items) - index} more on this page."
                break

            is_equipped = item.item_id == equipped_id
            status_icon = " [E]" if is_equipped else ""

            enhancement_str = ""
            if isinstance(item, Weapon) and item.refinement_lvl > 0:
                enhancement_str = f" **(+{item.refinement_lvl})**"
            elif isinstance(item, Armor) and getattr(item, "reinforcement_lvl", 0) > 0:
                enhancement_str = f" **(+{item.reinforcement_lvl})**"
            elif isinstance(item, (Glove, Boot, Helmet)) and getattr(item, "reinforcement_lvl", 0) > 0:
                enhancement_str = f" **(+{item.reinforcement_lvl})**"
            elif hasattr(item, "passive_lvl") and item.passive_lvl > 0:
                enhancement_str = f" **(+{item.passive_lvl} "
                if hasattr(item, "passive") and item.passive != "none":
                    enhancement_str += f"{item.passive.title()})**"
            details = []

            # 1. Armor Specifics (Block/Evasion)
            if isinstance(item, Armor):
                if item.block > 0:
                    details.append(f"{item.block}% 🛑Block")
                if item.evasion > 0:
                    details.append(f"{item.evasion}% 💨Evasion")

            # Base stats
            if hasattr(item, "attack") and item.attack > 0:
                details.append(f"{item.attack} ⚔️ATK")
            if hasattr(item, "defence") and item.defence > 0:
                details.append(f"{item.defence} 🛡️DEF")
            if hasattr(item, "rarity") and item.rarity > 0:
                details.append(f"{item.rarity}% ✨Rarity")
            # 2. Defensive Stats (PDR/FDR/Ward) - Applies to Armor, Gloves, Boots, Helmets
            if hasattr(item, "ward") and item.ward > 0:
                details.append(f"{item.ward}% HP as 🔮Ward")
            if hasattr(item, "pdr") and item.pdr > 0:
                details.append(f"{item.pdr}% 🛡️PDR")
            if hasattr(item, "fdr") and item.fdr > 0:
                details.append(f"{item.fdr} 🛡️FDR")
            if hasattr(item, "crit") and item.crit > 0:
                details.append(f"{item.crit} 🗡️Crit")

            # 3. Gear Primary Stats (Atk/Def on non-weapons)
            # if isinstance(item, (Glove, Boot, Helmet)):

            passives = []
            if isinstance(item, Weapon):
                if item.passive != "none":
                    passives.append(item.passive.title())
                if item.p_passive != "none":
                    passives.append(item.p_passive.title())
                if item.u_passive != "none":
                    passives.append(item.u_passive.title())
                if getattr(item, "infernal_passive", "none") not in ("none", ""):
                    passives.append(f"🔥{item.infernal_passive.title()}")
            if isinstance(item, Armor):
                if item.passive != "none" and item.passive != "":
                    passives.append(f"✨{item.passive.title()}")
                if getattr(item, "celestial_passive", "none") != "none":
                    passives.append(
                        f"🌌{item.celestial_passive.replace('_', ' ').title()}"
                    )
            if isinstance(item, Accessory):
                if item.passive != "none" and item.passive != "":
                    passives.append(item.passive.title())
                if getattr(item, "void_passive", "none") not in ("none", ""):
                    passives.append(f"🌀{item.void_passive.title()}")
            details_str = f" - {' | '.join(details)}" if details else ""
            passives_str = f" - {', '.join(passives)}" if passives else ""

            display_text += f"**{index + 1}.**{status_icon} lvl{item.level} {item.name}{enhancement_str}\n{details_str}\n{passives_str}\n"

        embed.add_field(name="Items", value=display_text, inline=False)
        embed.set_footer(text="Select an item number to view details/actions.")
        return embed

    @staticmethod
    def get_item_details_embed(item: Equipment, is_equipped: bool) -> discord.Embed:
        from core.character.profile_hub import (
            _WEAPON_PASSIVE_DESC,
            _INFERNAL_PASSIVE_DESC,
            _ARMOR_PASSIVE_DESC,
            _CELESTIAL_PASSIVE_DESC,
            _VOID_PASSIVE_DESC,
            _ACCESSORY_PASSIVE_FUNCS,
            _GLOVE_PASSIVE_FUNCS,
            _BOOT_PASSIVE_FUNCS,
            _HELMET_PASSIVE_FUNCS,
        )

        embed = discord.Embed(
            title=f"**{item.name}** (i{item.level:,})",
            description="**[Equipped]**" if is_equipped else "Unequipped",
            color=0x00FFFF,
        )

        if isinstance(item, Weapon):
            embed.set_thumbnail(url=_ITEM_IMAGES["weapon"])
            _weapon_fields(embed, item, _WEAPON_PASSIVE_DESC, _INFERNAL_PASSIVE_DESC)
        elif isinstance(item, Armor):
            embed.set_thumbnail(url=_ITEM_IMAGES["armor"])
            _armor_fields(embed, item, _ARMOR_PASSIVE_DESC, _CELESTIAL_PASSIVE_DESC)
        elif isinstance(item, Helmet):
            embed.set_thumbnail(url=_ITEM_IMAGES["helmet"])
            _helmet_fields(embed, item, _HELMET_PASSIVE_FUNCS)
        elif isinstance(item, Glove):
            embed.set_thumbnail(url=_ITEM_IMAGES["glove"])
            _glove_boot_fields(embed, item, _GLOVE_PASSIVE_FUNCS)
        elif isinstance(item, Boot):
            embed.set_thumbnail(url=_ITEM_IMAGES["boot"])
            _glove_boot_fields(embed, item, _BOOT_PASSIVE_FUNCS)
        elif isinstance(item, Accessory):
            embed.set_thumbnail(url=_ITEM_IMAGES["accessory"])
            _accessory_fields(embed, item, _ACCESSORY_PASSIVE_FUNCS, _VOID_PASSIVE_DESC)

        return embed

    @staticmethod
    def _build_equipped_stats(item) -> str:
        """Compact multi-line stats string for the equipped item panel in the gear embed."""
        parts = []
        if getattr(item, "attack", 0) > 0:
            parts.append(f"⚔️ ATK: {item.attack}")
        if getattr(item, "defence", 0) > 0:
            parts.append(f"🛡️ DEF: {item.defence}")
        if getattr(item, "rarity", 0) > 0:
            parts.append(f"✨ Rarity: {item.rarity}%")
        if getattr(item, "ward", 0) > 0:
            parts.append(f"🔮 Ward: {item.ward}%")
        if getattr(item, "crit", 0) > 0:
            parts.append(f"🎯 Crit: {item.crit}")
        if getattr(item, "block", 0) > 0:
            parts.append(f"🛑 Block: {item.block}%")
        if getattr(item, "evasion", 0) > 0:
            parts.append(f"💨 Eva: {item.evasion}%")
        if getattr(item, "pdr", 0) > 0:
            parts.append(f"🛡️ PDR: {item.pdr}%")
        if getattr(item, "fdr", 0) > 0:
            parts.append(f"🛡️ FDR: {item.fdr}")
        if isinstance(item, Weapon) and item.refinement_lvl > 0:
            parts.append(f"🔧 Refine: +{item.refinement_lvl}")

        passives = []
        if getattr(item, "passive", "none") not in ("none", ""):
            lvl = getattr(item, "passive_lvl", 0)
            lvl_str = f" Lv.{lvl}" if lvl > 0 else ""
            passives.append(f"{item.passive.title()}{lvl_str}")
        if isinstance(item, Weapon):
            if getattr(item, "p_passive", "none") not in ("none", ""):
                passives.append(item.p_passive.title())
            if getattr(item, "u_passive", "none") not in ("none", ""):
                passives.append(item.u_passive.title())
            if getattr(item, "infernal_passive", "none") not in ("none", ""):
                passives.append(item.infernal_passive.replace('_', ' ').title())
        if isinstance(item, Armor) and getattr(
            item, "celestial_passive", "none"
        ) not in ("none", ""):
            passives.append(f"🌌 {item.celestial_passive.replace('_', ' ').title()}")
        if isinstance(item, Accessory) and getattr(
            item, "void_passive", "none"
        ) not in ("none", ""):
            passives.append(f"🌀 {item.void_passive.replace('_', ' ').title()}")

        stat_line = " · ".join(parts)
        passive_line = ("Passives:\n" + ", ".join(passives)) if passives else ""

        if stat_line and passive_line:
            return f"{stat_line}\n{passive_line}"
        return stat_line or passive_line or "No stats"

    @staticmethod
    def get_gear_embed(
        player_name: str,
        all_items: dict,
        active_slot: str,
        equipped_ids: dict,
        current_page: int,
        total_pages: int,
    ) -> discord.Embed:
        """
        Main embed for the unified GearView.
        Shows the currently equipped item's stats and a one-line overview of all slots.
        """
        slot_emoji = _SLOT_EMOJIS.get(active_slot, "🎒")
        slot_label = _SLOT_LABELS.get(active_slot, active_slot.title())

        embed = discord.Embed(
            title=f"{slot_emoji} {player_name}'s {slot_label}s",
            color=0x2B2D31,
        )
        embed.set_thumbnail(url=_ITEM_IMAGES.get(active_slot, ""))

        # --- Equipped item panel ---
        equipped_id = equipped_ids.get(active_slot)
        equipped_item = None
        if equipped_id:
            for item in all_items.get(active_slot, []):
                if item.item_id == equipped_id:
                    equipped_item = item
                    break

        if equipped_item:
            stats = InventoryUI._build_equipped_stats(equipped_item)
            embed.add_field(
                name="Equipped",
                value=f"**{equipped_item.name}** (Lv.{equipped_item.level})\n{stats}",
                inline=False,
            )
        else:
            embed.add_field(name="Equipped", value="*— None equipped —*", inline=False)

        # --- Slot overview ---
        lines = []
        for slot in _SLOT_ORDER:
            emoji = _SLOT_EMOJIS[slot]
            label = _SLOT_LABELS[slot]
            count = len(all_items.get(slot, []))
            eid = equipped_ids.get(slot)
            e_name = "None"
            if eid:
                for item in all_items.get(slot, []):
                    if item.item_id == eid:
                        e_name = f"{item.name} (Lv.{item.level})"
                        break
            line = f"{emoji} **{label}** — {e_name} [{count} owned]"
            if slot == active_slot:
                line = f"**→ {line}**"
            lines.append(line)

        embed.add_field(name="Gear Overview", value="\n".join(lines), inline=False)

        if total_pages > 1:
            embed.set_footer(
                text=f"Page {current_page + 1}/{total_pages} · Select an item from the menu below."
            )
        else:
            embed.set_footer(text="Select an item from the menu below.")

        return embed
