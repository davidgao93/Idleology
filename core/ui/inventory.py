from typing import List, Union

import discord

from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon

_SLOT_EMOJIS = {
    "weapon": "⚔️",
    "armor": "🛡️",
    "helmet": "🪖",
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

Equipment = Union[Weapon, Armor, Accessory, Glove, Boot]


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
        """
        Generates the detailed view for a single item.
        """
        embed = discord.Embed(
            title=f"**{item.name}** (i{item.level})",
            description="**[Equipped]**" if is_equipped else "Unequipped",
            color=0x00FFFF,  # Cyan
        )

        # Generic Stats
        stats = {
            "Attack": getattr(item, "attack", 0),
            "Defence": getattr(item, "defence", 0),
            "Rarity": getattr(item, "rarity", 0),
            "Ward": getattr(item, "ward", 0),
            "Crit": getattr(item, "crit", 0),
            "Block": getattr(item, "block", 0),
            "Evasion": getattr(item, "evasion", 0),
            "PDR": getattr(item, "pdr", 0),
            "FDR": getattr(item, "fdr", 0),
        }

        # Add stat fields if > 0
        for label, value in stats.items():
            if value > 0:
                val_str = (
                    f"{value}%"
                    if label in ["Rarity", "Ward", "Crit", "PDR"]
                    else str(value)
                )
                embed.add_field(name=label, value=val_str, inline=True)

        # Passives
        main_passive = getattr(item, "passive", "none")
        if main_passive != "none":
            lvl = getattr(item, "passive_lvl", 0)
            lvl_str = f" (Lvl {lvl})" if lvl > 0 else ""  # Only display level if > 0
            embed.add_field(
                name="Passive", value=f"{main_passive.title()}{lvl_str}", inline=False
            )
            # Note: Detailed effect description would require importing the 'general' logic helper or similar

        if isinstance(item, Armor):
            if getattr(item, "celestial_passive", "none") != "none":
                embed.add_field(
                    name="Celestial Passive",
                    value=f"🌌 {item.celestial_passive.replace('_', ' ').title()}",
                    inline=False,
                )

        if isinstance(item, Accessory):
            if getattr(item, "void_passive", "none") not in ("none", ""):
                embed.add_field(
                    name="Void Passive",
                    value=f"🌀 {item.void_passive.replace('_', ' ').title()}",
                    inline=False,
                )

        # Essence slots (Glove / Boot / Helmet)
        if isinstance(item, (Glove, Boot, Helmet)):
            from core.items.essence_views import ESSENCE_DISPLAY, _format_slot_value

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
                c_name, c_emoji = ESSENCE_DISPLAY.get(
                    corrupted, (corrupted.title(), "💠")
                )
                from core.items.essence_views import ESSENCE_BRIEF

                c_brief = ESSENCE_BRIEF.get(corrupted, "")
                lines.append(f"**Corrupted:** {c_emoji} {c_name}\n   ↳ {c_brief}")
            else:
                lines.append("**Corrupted:** *— Empty —*")
            embed.add_field(name="💎 Essences", value="\n".join(lines), inline=False)

        # Weapon Specifics
        if isinstance(item, Weapon):
            if item.p_passive != "none":
                embed.add_field(
                    name="Pinnacle Passive", value=item.p_passive.title(), inline=False
                )
            if item.u_passive != "none":
                embed.add_field(
                    name="Utmost Passive", value=item.u_passive.title(), inline=False
                )
            if getattr(item, "infernal_passive", "none") not in ("none", ""):
                embed.add_field(
                    name="Infernal Passive",
                    value=f"🔥 {item.infernal_passive.title()}",
                    inline=False,
                )
            embed.add_field(
                name="Refinement", value=f"+{item.refinement_lvl}", inline=True
            )

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
            passives.append(item.passive.title())
        if isinstance(item, Weapon):
            if getattr(item, "p_passive", "none") not in ("none", ""):
                passives.append(item.p_passive.title())
            if getattr(item, "u_passive", "none") not in ("none", ""):
                passives.append(item.u_passive.title())
            if getattr(item, "infernal_passive", "none") not in ("none", ""):
                passives.append(item.infernal_passive.title())
        if isinstance(item, Armor) and getattr(
            item, "celestial_passive", "none"
        ) not in ("none", ""):
            passives.append(f"🌌 {item.celestial_passive.replace('_', ' ').title()}")
        if isinstance(item, Accessory) and getattr(
            item, "void_passive", "none"
        ) not in ("none", ""):
            passives.append(f"🌀 {item.void_passive.title()}")

        stat_line = " · ".join(parts)
        passive_line = ("Passives: " + ", ".join(passives)) if passives else ""

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
