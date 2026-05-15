"""
core/character/profile_ui.py
Stateless embed builders for the profile hub. All methods are pure async functions
that take (bot, user_id, server_id) and return a discord.Embed.
"""

from datetime import datetime, timedelta, timezone

import discord

from core.character.passive_data import (
    _ACCESSORY_PASSIVE_FUNCS,
    _ARMOR_PASSIVE_DESC,
    _BOOT_PASSIVE_FUNCS,
    _CELESTIAL_PASSIVE_DESC,
    _GLOVE_PASSIVE_FUNCS,
    _HELMET_PASSIVE_FUNCS,
    _INFERNAL_PASSIVE_DESC,
    _VOID_PASSIVE_DESC,
    _WEAPON_PASSIVE_DESC,
)
from core.character.passive_formatters import (
    _compute_combat_bonuses,
    _desc_fixed,
    _desc_scaled,
    _format_corrupted,
    _format_essence_slot,
    _format_weapon_passive,
    _get_piercing_crit_bonus,
    _normalize,
)
from core.items.factory import load_player

# ── ProfileBuilder ────────────────────────────────────────────────────────────


class ProfileBuilder:
    """Static builder class that generates the embeds for the Profile Hub."""

    @staticmethod
    async def build_card(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        followers = await bot.database.social.get_follower_count(user[8])

        embed = discord.Embed(title="Adventurer License", color=discord.Color.gold())
        embed.set_thumbnail(url=user[7])

        embed.add_field(name="Name", value=f"**{user[3]}**", inline=True)
        embed.add_field(
            name="Level", value=f"{user[4]} (Ascension {user[15]})", inline=True
        )
        embed.add_field(name="Experience", value=f"{user[5]:,}", inline=True)

        embed.add_field(name="Ideology", value=f"{user[8]}", inline=True)
        embed.add_field(name="Followers", value=f"{followers:,}", inline=True)
        embed.add_field(name="Gold", value=f"{user[6]:,} 💰", inline=True)

        return embed

    @staticmethod
    async def build_stats(bot, user_id: str, server_id: str) -> discord.Embed:
        from core.items.essence_mechanics import compute_essence_stat_bonus

        data = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, data, bot.database)

        embed = discord.Embed(title="Combat Statistics", color=0x00FF00)
        embed.set_thumbnail(url=data[7])

        cb = _compute_combat_bonuses(p)

        # ── Attack ───────────────────────────────────────────────────────────
        gear_atk = 0
        if p.equipped_weapon:
            gear_atk += p.equipped_weapon.attack
        if p.equipped_accessory:
            gear_atk += p.equipped_accessory.attack
        if p.equipped_glove:
            gear_atk += p.equipped_glove.attack
        if p.equipped_boot:
            gear_atk += p.equipped_boot.attack
        for _item in (p.equipped_glove, p.equipped_boot):
            if _item:
                gear_atk += compute_essence_stat_bonus(_item).get("attack", 0)
        total_atk = p.get_total_attack()
        atk_bonuses = total_atk - p.base_attack - gear_atk
        atk_val = f"**Total: {total_atk:,}**\n↳ Base: {p.base_attack:,}\n↳ Equipment: {gear_atk:,}"
        if atk_bonuses:
            atk_val += f"\n↳ Bonuses: {atk_bonuses:+,}"
        if cb["atk"]:
            atk_val += f"\n↳ Combat start: {cb['atk']:+,}"
        embed.add_field(name="⚔️ Attack", value=atk_val, inline=True)

        # ── Defence ──────────────────────────────────────────────────────────
        gear_def = 0
        if p.equipped_weapon:
            gear_def += p.equipped_weapon.defence
        if p.equipped_accessory:
            gear_def += p.equipped_accessory.defence
        if p.equipped_glove:
            gear_def += p.equipped_glove.defence
        if p.equipped_boot:
            gear_def += p.equipped_boot.defence
        if p.equipped_helmet:
            gear_def += p.equipped_helmet.defence
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                gear_def += compute_essence_stat_bonus(_item).get("defence", 0)
        total_def = p.get_total_defence()
        def_bonuses = total_def - p.base_defence - gear_def
        def_val = f"**Total: {total_def:,}**\n↳ Base: {p.base_defence:,}\n↳ Equipment: {gear_def:,}"
        if def_bonuses:
            def_val += f"\n↳ Bonuses: {def_bonuses:+,}"
        if cb["def"]:
            def_val += f"\n↳ Combat start: {cb['def']:+,}"
        embed.add_field(name="🛡️ Defence", value=def_val, inline=True)

        # ── HP ───────────────────────────────────────────────────────────────
        total_hp = p.total_max_hp
        parts_hp = (
            sum(v["hp"] for v in p.equipped_parts.values()) if p.equipped_parts else 0
        )
        other_hp_bonuses = total_hp - p.max_hp - parts_hp
        hp_val = f"**{p.current_hp:,} / {total_hp:,}**\n↳ Base: {p.max_hp:,}\n↳ Parts: {parts_hp:,}"
        if other_hp_bonuses:
            hp_val += f"\n↳ Bonuses: {other_hp_bonuses:+,}"
        if cb["hp"]:
            hp_val += f"\n↳ Combat start: {cb['hp']:+,}"
        embed.add_field(name="❤️ HP", value=hp_val, inline=True)

        # ── Ward ─────────────────────────────────────────────────────────────
        ward_equip = 0
        if p.equipped_accessory:
            ward_equip += p.equipped_accessory.ward
        if p.equipped_armor:
            ward_equip += p.equipped_armor.ward
        if p.equipped_glove:
            ward_equip += p.equipped_glove.ward
        if p.equipped_boot:
            ward_equip += p.equipped_boot.ward
        if p.equipped_helmet:
            ward_equip += p.equipped_helmet.ward
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                ward_equip += compute_essence_stat_bonus(_item).get("ward", 0)
        ward_other = p._get_companion_bonus("ward")
        total_ward = ward_equip + ward_other
        if total_ward > 0:
            ward_hp = p.get_combat_ward_value()
            embed.add_field(
                name="🔮 Ward",
                value=f"**{total_ward}%** (= {ward_hp:,} Ward)\n↳ Equipment: {ward_equip}%\n↳ Other: {ward_other}%",
                inline=True,
            )

        # ── Hit Chance ───────────────────────────────────────────────────────
        _HIT_BASE_PCT = 60
        hit_weapon_pct = (
            int(p.equipped_weapon.hit_chance * 100)
            if p.equipped_weapon
            else _HIT_BASE_PCT
        )
        hit_ascension = p.get_ascension_bonuses()["hit"] if p.ascension_unlocks else 0
        hit_deadeye = 0
        if p.equipped_weapon:
            for _passive in (
                p.equipped_weapon.passive,
                p.equipped_weapon.p_passive,
                p.equipped_weapon.u_passive,
            ):
                if _passive and "deadeye" in _passive.lower():
                    try:
                        tier = int(_passive.lower().split("_")[-1])
                        hit_deadeye += tier * 4
                    except (ValueError, IndexError):
                        pass
        hit_val = f"**Base: {hit_weapon_pct}%**"
        if hit_deadeye:
            hit_val += f"\n↳ Deadeye: +{hit_deadeye} flat"
        if hit_ascension:
            hit_val += f"\n↳ Ascension: +{hit_ascension} flat"
        embed.add_field(name="🎯 Base Hit Chance", value=hit_val, inline=True)

        # ── Crit Chance ──────────────────────────────────────────────────────
        crit_weapon_template = (
            int(p.equipped_weapon.crit_chance * 100) if p.equipped_weapon else 0
        )
        crit_weapon_piercing = 0
        if p.equipped_weapon:
            for _passive in (
                p.equipped_weapon.passive,
                p.equipped_weapon.p_passive,
                p.equipped_weapon.u_passive,
            ):
                if _passive:
                    crit_weapon_piercing += _get_piercing_crit_bonus(_passive.lower())
        crit_weapon = crit_weapon_template + crit_weapon_piercing
        crit_equip = p.equipped_accessory.crit if p.equipped_accessory else 0
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                crit_equip += compute_essence_stat_bonus(_item).get("crit", 0)
        stat_crit = p.get_current_crit_chance()
        crit_bonuses = stat_crit - crit_equip - crit_weapon_template
        total_crit_display = stat_crit + crit_weapon_piercing
        crit_val = f"**Total: {total_crit_display}**\n↳ Weapon: {crit_weapon}\n↳ Equipment: {crit_equip}"
        if crit_bonuses:
            crit_val += f"\n↳ Bonuses: {crit_bonuses:+}"
        if cb["crit"]:
            crit_val += f"\n↳ Combat start: {cb['crit']:+}"
        embed.add_field(name="🎯 Crit Chance", value=crit_val, inline=True)

        # ── Crit Multiplier ──────────────────────────────────────────────────
        crit_multi_equip = 0.0
        if p.equipped_helmet and _normalize(p.equipped_helmet.passive) == "insight":
            crit_multi_equip = p.equipped_helmet.passive_lvl * 0.1
        crit_multi_total = 2.0 + crit_multi_equip
        cm_val = f"**{crit_multi_total:.1f}×**\n↳ Base: 2.0×"
        if crit_multi_equip:
            cm_val += f"\n↳ Equipment: +{crit_multi_equip:.1f}×"
        embed.add_field(name="✨ Crit Multiplier", value=cm_val, inline=True)

        # ── PDR ──────────────────────────────────────────────────────────────
        pdr_equip = 0
        if p.equipped_armor:
            pdr_equip += p.equipped_armor.pdr
        if p.equipped_glove:
            pdr_equip += p.equipped_glove.pdr
        if p.equipped_boot:
            pdr_equip += p.equipped_boot.pdr
        if p.equipped_helmet:
            pdr_equip += p.equipped_helmet.pdr
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                pdr_equip += compute_essence_stat_bonus(_item).get("pdr", 0)
        pdr_other = p._get_companion_bonus("pdr") + int(p.get_tome_bonus("bulwark"))
        if p.ascension_unlocks:
            pdr_other += p.get_ascension_bonuses()["pdr"]
        raw_pdr = pdr_equip + pdr_other
        capped_pdr = min(80, raw_pdr)
        pdr_str = f"**{capped_pdr}%**" + (
            f" ({raw_pdr}% uncapped)" if raw_pdr > 80 else ""
        )
        embed.add_field(
            name="🛡️ PDR",
            value=f"{pdr_str}\n↳ Equipment: {pdr_equip}%\n↳ Other: {pdr_other}%",
            inline=True,
        )

        # ── FDR ──────────────────────────────────────────────────────────────
        fdr_equip = 0
        if p.equipped_armor:
            fdr_equip += p.equipped_armor.fdr
        if p.equipped_glove:
            fdr_equip += p.equipped_glove.fdr
        if p.equipped_boot:
            fdr_equip += p.equipped_boot.fdr
        if p.equipped_helmet:
            fdr_equip += p.equipped_helmet.fdr
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                fdr_equip += compute_essence_stat_bonus(_item).get("fdr", 0)
        fdr_other = p._get_companion_bonus("fdr") + int(p.get_tome_bonus("resilience"))
        if p.ascension_unlocks:
            fdr_other += p.get_ascension_bonuses()["fdr"]
        total_fdr = fdr_equip + fdr_other
        if total_fdr > 0:
            fdr_val = f"**{total_fdr:,}**\n↳ Equipment: {fdr_equip}"
            if fdr_other > 0:
                fdr_val += f"\n↳ Other: {fdr_other}"
            embed.add_field(name="🔒 FDR", value=fdr_val, inline=True)

        # ── Rarity ───────────────────────────────────────────────────────────
        gear_rarity = p.rarity
        total_rarity = p.get_total_rarity()
        rarity_bonuses = total_rarity - gear_rarity
        if total_rarity > 0:
            rar_val = f"**{total_rarity}%**\n↳ Equipment: {gear_rarity}%"
            if rarity_bonuses:
                rar_val += f"\n↳ Bonuses: {rarity_bonuses:+}%"
            embed.add_field(name="✨ Rarity", value=rar_val, inline=True)

        # ── Special Rarity ────────────────────────────────────────────────────
        sr_boot = 0
        if p.equipped_boot and p.equipped_boot.passive == "thrill-seeker":
            sr_boot = p.equipped_boot.passive_lvl
        sr_armor = (
            3
            if (p.equipped_armor and p.equipped_armor.passive == "treasure hunter")
            else 0
        )
        sr_companion = p._get_companion_bonus("s_rarity")
        sr_partner_combat = cb["special_rarity"]
        sr_total = min(20, sr_boot + sr_armor + sr_companion)
        sr_val = f"**{sr_total}%** (cap: 20%)"
        sr_val += f"\n↳ Boot: {sr_boot}%"
        if sr_armor:
            sr_val += f"\n↳ Armor: +{sr_armor}%"
        sr_val += f"\n↳ Companions: {sr_companion}%"
        if sr_partner_combat:
            sr_val += f"\n↳ Partner: +{sr_partner_combat:.1f}%"
        embed.add_field(name="⭐ Special Rarity", value=sr_val, inline=True)

        return embed

    @staticmethod
    async def build_passives(bot, user_id: str, server_id: str) -> discord.Embed:
        data = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, data, bot.database)

        embed = discord.Embed(title="Active Passives & Equipment", color=0x7B68EE)
        embed.set_thumbnail(url=data[7])

        def _add_gear_field(
            icon: str, slot: str, item, stat_line: str, passive_lines: list[str]
        ):
            if not item:
                return
            body = f"**{item.name}** Lv.{item.level}\n{stat_line}"
            if passive_lines:
                body += "\n" + "\n".join(passive_lines)
            if len(body) > 1020:
                body = body[:1020] + "…"
            embed.add_field(name=f"{icon} {slot}", value=body, inline=False)

        # ── Weapon ───────────────────────────────────────────────────────────
        if p.equipped_weapon:
            w = p.equipped_weapon
            stat_line = f"ATK: {w.attack} | DEF: {w.defence} | RAR: {w.rarity}%"
            lines: list[str] = []
            if w.passive != "none":
                lines.append(
                    f"• Forge: {_format_weapon_passive(w.passive)} — {_desc_fixed(_WEAPON_PASSIVE_DESC, w.passive)}"
                )
            if w.p_passive != "none":
                lines.append(
                    f"• Pinnacle: {_format_weapon_passive(w.p_passive)} — {_desc_fixed(_WEAPON_PASSIVE_DESC, w.p_passive)}"
                )
            if w.u_passive != "none":
                lines.append(
                    f"• Utmost: {_format_weapon_passive(w.u_passive)} — {_desc_fixed(_WEAPON_PASSIVE_DESC, w.u_passive)}"
                )
            if w.infernal_passive != "none":
                lines.append(
                    f"• Infernal: {w.infernal_passive.replace('_',' ').title()} — {_desc_fixed(_INFERNAL_PASSIVE_DESC, w.infernal_passive)}"
                )
            _add_gear_field("⚔️", "Weapon", w, stat_line, lines)

        # ── Armor ─────────────────────────────────────────────────────────────
        if p.equipped_armor:
            a = p.equipped_armor
            parts = []
            if a.block:
                parts.append(f"BLOCK: {a.block}%")
            if a.evasion:
                parts.append(f"EVA: {a.evasion}%")
            if a.ward:
                parts.append(f"WARD: {a.ward}%")
            if a.pdr:
                parts.append(f"PDR: {a.pdr}%")
            if a.fdr:
                parts.append(f"FDR: {a.fdr}")
            stat_line = " | ".join(parts) or "No defensive stats"
            lines = []
            if a.passive != "none":
                lines.append(
                    f"• {a.passive.replace('_',' ').title()} — {_desc_fixed(_ARMOR_PASSIVE_DESC, a.passive)}"
                )
            if a.celestial_passive != "none":
                lines.append(
                    f"• {a.celestial_passive.replace('_',' ').title()} — {_desc_fixed(_CELESTIAL_PASSIVE_DESC, a.celestial_passive)}"
                )
            _add_gear_field("🛡️", "Armor", a, stat_line, lines)

        # ── Accessory ─────────────────────────────────────────────────────────
        if p.equipped_accessory:
            acc = p.equipped_accessory
            parts = []
            if acc.attack:
                parts.append(f"ATK: {acc.attack}")
            if acc.defence:
                parts.append(f"DEF: {acc.defence}")
            if acc.rarity:
                parts.append(f"RAR: {acc.rarity}%")
            if acc.ward:
                parts.append(f"WARD: {acc.ward}%")
            if acc.crit:
                parts.append(f"CRIT: {acc.crit}")
            stat_line = " | ".join(parts) or "No stats"
            lines = []
            if acc.passive != "none":
                desc = _desc_scaled(
                    _ACCESSORY_PASSIVE_FUNCS, acc.passive, acc.passive_lvl
                )
                lines.append(
                    f"• {acc.passive.replace('_',' ').title()} L{acc.passive_lvl} — {desc}"
                )
            if acc.void_passive != "none":
                lines.append(
                    f"• {acc.void_passive.replace('_',' ').title()} — {_desc_fixed(_VOID_PASSIVE_DESC, acc.void_passive)}"
                )
            _add_gear_field("📿", "Accessory", acc, stat_line, lines)

        # ── Glove / Boot / Helmet ─────────────────────────────────────────────
        for icon, slot_label, slot_name, item, pfuncs in (
            ("🧤", "Glove", "glove", p.equipped_glove, _GLOVE_PASSIVE_FUNCS),
            ("👢", "Boot", "boot", p.equipped_boot, _BOOT_PASSIVE_FUNCS),
            ("🪖", "Helmet", "helmet", p.equipped_helmet, _HELMET_PASSIVE_FUNCS),
        ):
            if not item:
                continue
            parts = []
            if hasattr(item, "attack") and item.attack:
                parts.append(f"ATK: {item.attack}")
            if item.defence:
                parts.append(f"DEF: {item.defence}")
            if item.ward:
                parts.append(f"WARD: {item.ward}%")
            if item.pdr:
                parts.append(f"PDR: {item.pdr}%")
            if item.fdr:
                parts.append(f"FDR: {item.fdr}")
            stat_line = " | ".join(parts) or "No stats"
            lines = []
            if item.passive != "none":
                desc = _desc_scaled(pfuncs, item.passive, item.passive_lvl)
                lines.append(
                    f"• {item.passive.replace('_',' ').title()} L{item.passive_lvl} — {desc}"
                )
            for etype, val in (
                (item.essence_1, item.essence_1_val),
                (item.essence_2, item.essence_2_val),
                (item.essence_3, item.essence_3_val),
            ):
                if etype != "none":
                    lines.append(f"• {_format_essence_slot(etype, val, item)}")
            if item.corrupted_essence != "none":
                lines.append(
                    f"• {_format_corrupted(item.corrupted_essence, slot_name)}"
                )
            _add_gear_field(icon, slot_label, item, stat_line, lines)

        if not any(
            [
                p.equipped_weapon,
                p.equipped_armor,
                p.equipped_accessory,
                p.equipped_glove,
                p.equipped_boot,
                p.equipped_helmet,
            ]
        ):
            embed.description = "No gear equipped and no active passives."

        return embed

    @staticmethod
    async def build_inventory(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)

        w_count = await bot.database.equipment.get_count(user_id, "weapon")
        a_count = await bot.database.equipment.get_count(user_id, "accessory")
        ar_count = await bot.database.equipment.get_count(user_id, "armor")
        g_count = await bot.database.equipment.get_count(user_id, "glove")
        b_count = await bot.database.equipment.get_count(user_id, "boot")
        h_count = await bot.database.equipment.get_count(user_id, "helmet")
        pet_count = await bot.database.companions.get_count(user_id)

        k_balance = await bot.database.users.get_currency(user_id, "balance_fragment")
        antique_tomes = await bot.database.users.get_currency(user_id, "antique_tome")
        pinnacle_keys = await bot.database.users.get_currency(user_id, "pinnacle_key")

        embed = discord.Embed(
            title="Inventory Summary",
            description=f"💰 **Gold:** {user[6]:,}\n🧪 **Potions:** {user[16]:,}",
            color=0x00FF00,
        )
        embed.set_thumbnail(url=user[7])

        embed.add_field(
            name="⚔️ **Gear**",
            value=(
                f"⚔️ Weapons: {w_count}/60\n🛡️ Armor: {ar_count}/60\n📿 Accessories: {a_count}/60\n"
                f"🧤 Gloves: {g_count}/60\n👢 Boots: {b_count}/60\n🪖 Helmets: {h_count}/60\n🐾 Companions: {pet_count}/20"
            ),
            inline=True,
        )

        embed.add_field(
            name="🔑 **Boss Items**",
            value=(
                f"🐉 Draconic Keys: {user[25]}\n🪽 Angelic Keys: {user[26]}\n🟣 Void Frags: {user[29]}\n"
                f"⚖️ Balance Frags: {k_balance}\n❤️‍🔥 Soul Cores: {user[28]}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📦 **Misc Items**",
            value=(
                f"🎁 Curios: {user[22]}\n"
                f"📖 Antique Tomes: {antique_tomes}\n🗝️ Pinnacle Keys: {pinnacle_keys}"
            ),
            inline=True,
        )

        return embed

    @staticmethod
    async def build_crafting(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)

        r_partner = await bot.database.users.get_currency(user_id, "partnership_runes")
        mirage_imp = await bot.database.users.get_currency(
            user_id, "mirage_runes_imperfect"
        )
        mirage_perf = await bot.database.users.get_currency(
            user_id, "mirage_runes_perfected"
        )

        essence_data = await bot.database.essences.get_all(user_id)

        embed = discord.Embed(title="⚗️ Crafting Materials", color=0x9B59B6)
        embed.set_thumbnail(url=user[7])

        embed.add_field(
            name="💎 **Runes**",
            value=(
                f"🔨 Refinement: {user[19]}\n✨ Potential: {user[21]}\n🔮 Imbuing: {user[27]}\n"
                f"💥 Shatter: {user[31]}\n🤝 Partnership: {r_partner}\n"
                f"🪞 Mirage (Imperfect): {mirage_imp}\n🪞 Mirage (Perfected): {mirage_perf}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🗝️ **Void Keys**",
            value=f"🗝️ Void Keys: {user[30]}",
            inline=True,
        )

        if essence_data:
            items = {}
            if hasattr(essence_data, "keys"):
                items = {
                    k: v
                    for k, v in dict(essence_data).items()
                    if k not in ("user_id", "server_id", "id")
                }
            if items:
                lines = []
                for e_type, count in items.items():
                    safe_count = count if count is not None else 0
                    name = str(e_type).replace("_", " ").title()
                    lines.append(f"✦ **{name}**: {safe_count:,}")
                chunk_size = 12
                for i in range(0, len(lines), chunk_size):
                    chunk = lines[i : i + chunk_size]
                    embed.add_field(
                        name="🧪 Stored Essences" if i == 0 else "​",
                        value="\n".join(chunk),
                        inline=True,
                    )

        return embed

    @staticmethod
    async def build_cooldowns(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, user, bot.database)

        combat_cd_mins = 10
        if p.equipped_boot and p.equipped_boot.passive == "speedster":
            combat_cd_mins -= p.equipped_boot.passive_lvl

        def get_remaining(time_str, cooldown_td: timedelta):
            if not time_str:
                return "Ready!"
            try:
                last = datetime.fromisoformat(time_str)
                diff = datetime.now() - last
                if diff < cooldown_td:
                    rem = cooldown_td - diff
                    return f"**{rem.seconds // 3600}h {(rem.seconds // 60) % 60}m {rem.seconds % 60}s**"
                return "Ready!"
            except Exception:
                return "Ready!"

        embed = discord.Embed(title="Active Timers & Cooldowns", color=0xBEBEFE)
        embed.set_thumbnail(url=user[7])

        embed.add_field(
            name="/combat ⚔️",
            value=get_remaining(user[24], timedelta(minutes=combat_cd_mins)),
            inline=True,
        )
        embed.add_field(
            name="/rest 🛏️",
            value=get_remaining(user[13], timedelta(hours=2)),
            inline=True,
        )
        embed.add_field(
            name="/checkin 🛖",
            value=get_remaining(user[17], timedelta(hours=18)),
            inline=True,
        )
        embed.add_field(
            name="/propagate 💡",
            value=get_remaining(user[14], timedelta(hours=18)),
            inline=True,
        )

        settlement = await bot.database.settlement.get_settlement(user_id, server_id)
        if settlement and settlement.last_collection_time:
            try:
                s_last = datetime.fromisoformat(settlement.last_collection_time)
                s_diff = datetime.now() - s_last
                s_hours = s_diff.total_seconds() / 3600
                embed.add_field(
                    name="🏭 Settlement",
                    value=f"**{s_hours:.2f}** hours of production pending.",
                    inline=False,
                )
            except Exception:
                pass

        active_comps = await bot.database.companions.get_active(user_id)
        if not active_comps:
            embed.add_field(
                name="🐾 Companions",
                value="No active companions deployed.",
                inline=False,
            )
        else:
            c_time_str = await bot.database.users.get_companion_collect_time(user_id)

            if c_time_str:
                try:
                    c_last = datetime.fromisoformat(c_time_str)
                    c_diff = (datetime.now() - c_last).total_seconds()
                    cycles = int(c_diff // 3600)

                    if cycles >= 48:
                        embed.add_field(
                            name="🐾 Companions",
                            value="**48/48** adventures completed! (MAXED)\nWaiting to be collected.",
                            inline=False,
                        )
                    else:
                        next_cycle_rem = 3600 - (c_diff % 3600)
                        next_cycle_str = f"({int(next_cycle_rem // 60)}m {int(next_cycle_rem % 60)}s until next)"
                        embed.add_field(
                            name="🐾 Companions",
                            value=f"**{cycles}/48** adventures completed.\n{next_cycle_str}",
                            inline=False,
                        )
                except Exception:
                    embed.add_field(
                        name="🐾 Companions", value="Ready to deploy.", inline=False
                    )
            else:
                embed.add_field(
                    name="🐾 Companions", value="Ready to deploy.", inline=False
                )

        from core.models import Partner
        from core.partners.data import PARTNER_DATA
        from core.partners.dispatch import (
            BOSS_PARTY_DURATION_HOURS,
            elapsed_hours,
            get_cap_hours,
        )
        from core.partners.resources import _stars

        rows = await bot.database.partners.get_owned(user_id)
        partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
        ]

        active_dispatch = next(
            (
                p
                for p in partners
                if p.is_dispatched and p.dispatch_task != "boss_party"
            ),
            None,
        )
        boss_party = [
            p for p in partners if p.is_dispatched and p.dispatch_task == "boss_party"
        ]

        if active_dispatch:
            elapsed = elapsed_hours(active_dispatch.dispatch_start_time)
            cap = get_cap_hours(active_dispatch)
            elapsed_clamped = min(elapsed, cap)
            progress_pct = int(elapsed_clamped / cap * 100)
            task_label = active_dispatch.dispatch_task or "Unknown"
            if elapsed >= cap:
                dispatch_status = "✅ Ready to collect!"
            else:
                remaining_secs = (cap - elapsed) * 3600
                h = int(remaining_secs // 3600)
                m = int((remaining_secs % 3600) // 60)
                dispatch_status = f"**{h}h {m}m** remaining ({progress_pct}%)"
            embed.add_field(
                name="📋 Partner Dispatch",
                value=(
                    f"{_stars(active_dispatch.rarity)} **{active_dispatch.name}** — {task_label.title()}\n"
                    f"{dispatch_status}"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📋 Partner Dispatch",
                value="No partner currently dispatched.",
                inline=False,
            )

        if boss_party:
            bp_first = boss_party[0]
            elapsed = elapsed_hours(bp_first.dispatch_start_time)
            progress_pct = min(100, int(elapsed / BOSS_PARTY_DURATION_HOURS * 100))
            names = " | ".join(f"{_stars(p.rarity)} {p.name}" for p in boss_party)
            if progress_pct >= 100:
                raid_status = "✅ Raid Complete! Collect your rewards."
            else:
                remaining_secs = (BOSS_PARTY_DURATION_HOURS - elapsed) * 3600
                h = int(remaining_secs // 3600)
                m = int((remaining_secs % 3600) // 60)
                raid_status = f"**{h}h {m}m** remaining ({progress_pct}%)"
            embed.add_field(
                name="🔱 Boss Raid",
                value=f"{names}\n{raid_status}",
                inline=False,
            )

        from core.maw.mechanics import (
            boost_available,
            boost_remaining_seconds,
            get_current_cycle_id,
            get_cycle_end_ts,
            get_next_cycle_id,
            is_collection_window,
            is_cycle_active,
        )

        now_utc = datetime.now(timezone.utc)
        now_ts = int(now_utc.timestamp())
        maw_cycle_id = get_current_cycle_id(now_utc)

        if is_cycle_active(maw_cycle_id, now_ts):
            cycle_end = get_cycle_end_ts(maw_cycle_id)
            ends_in = cycle_end - now_ts
            h, m = ends_in // 3600, (ends_in % 3600) // 60
            window_line = f"🟢 **Sign-up window OPEN** (ends in {h}h {m}m)"

            maw_record = await bot.database.maw.get_record(user_id, maw_cycle_id)
            if maw_record:
                boost_used_at = maw_record["boost_used_at"]
                if boost_available(boost_used_at, now_ts):
                    boost_str = "✅ Ready"
                else:
                    secs = boost_remaining_seconds(boost_used_at, now_ts)
                    bh, bm = secs // 3600, (secs % 3600) // 60
                    boost_str = f"**{bh}h {bm}m**"
                maw_value = f"{window_line}\n" f"Boost: {boost_str}"
            else:
                maw_value = f"{window_line}\nNot signed up this cycle."

        elif is_collection_window(maw_cycle_id, now_ts):
            next_ts = get_next_cycle_id(maw_cycle_id)
            next_in = next_ts - now_ts
            h, m = next_in // 3600, (next_in % 3600) // 60
            window_line = f"📦 **Collection window open** (next cycle in {h}h {m}m)"

            maw_record = await bot.database.maw.get_record(user_id, maw_cycle_id)
            if maw_record:
                collected_str = (
                    "✅ Collected"
                    if maw_record["rewards_collected"]
                    else "⏳ Not yet collected"
                )
                maw_value = f"{window_line}\n" f"Rewards: {collected_str}"
            else:
                maw_value = f"{window_line}\nDidn't participate this cycle."

        else:
            next_ts = get_next_cycle_id(maw_cycle_id)
            next_in = next_ts - now_ts
            h, m = next_in // 3600, (next_in % 3600) // 60
            maw_value = f"⏳ **Next cycle starts in {h}h {m}m**"

        embed.add_field(name="🌀 Infinite Maw", value=maw_value, inline=False)

        return embed

    @staticmethod
    async def build_resources(bot, user_id: str, server_id: str) -> discord.Embed:
        settlement = await bot.database.settlement.get_settlement(user_id, server_id)
        uber_data = await bot.database.uber.get_uber_progress(user_id, server_id)
        blueprint_count = await bot.database.users.get_currency(
            user_id, "unidentified_blueprint"
        )

        ores = await bot.database.skills.get_multi_resource(
            user_id, server_id, "mining", ["iron", "coal", "gold", "platinum", "idea"]
        )
        logs = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "woodcutting",
            ["oak_logs", "willow_logs", "mahogany_logs", "magic_logs", "idea_logs"],
        )
        bones = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "fishing",
            [
                "desiccated_bones",
                "regular_bones",
                "sturdy_bones",
                "reinforced_bones",
                "titanium_bones",
            ],
        )
        ingots = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "mining",
            ["iron_bar", "steel_bar", "gold_bar", "platinum_bar", "idea_bar"],
        )
        planks = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "woodcutting",
            [
                "oak_plank",
                "willow_plank",
                "mahogany_plank",
                "magic_plank",
                "idea_plank",
            ],
        )
        essence = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "fishing",
            [
                "desiccated_essence",
                "regular_essence",
                "sturdy_essence",
                "reinforced_essence",
                "titanium_essence",
            ],
        )
        rares = await bot.database.users.get_rare_materials(user_id)

        embed = discord.Embed(
            title="Storage Warehouse", color=discord.Color.dark_orange()
        )

        gathering_value = (
            f"**Ores:** Iron {ores[0]:,} · Coal {ores[1]:,} · Gold {ores[2]:,} · Plat {ores[3]:,} · Idea {ores[4]:,}\n"
            f"**Logs:** Oak {logs[0]:,} · Willow {logs[1]:,} · Mahog {logs[2]:,} · Magic {logs[3]:,} · Idea {logs[4]:,}\n"
            f"**Bones:** Desic {bones[0]:,} · Reg {bones[1]:,} · Sturdy {bones[2]:,} · Reinf {bones[3]:,} · Titan {bones[4]:,}\n"
            f"**Elemental Keys:** 💎 Bismuth: {uber_data['blessed_bismuth']} · 🌿 Sprig: {uber_data['sparkling_sprig']} · 🐟 Carp: {uber_data['capricious_carp']}"
        )
        embed.add_field(name="⛏️ Gathering", value=gathering_value, inline=False)

        settlement_value = (
            f"🪵 Timber: {settlement.timber:,} · 🪨 Stone: {settlement.stone:,}\n"
            f"**Ingots:** Iron {ingots[0]:,} · Steel {ingots[1]:,} · Gold {ingots[2]:,} · Plat {ingots[3]:,} · Idea {ingots[4]:,}\n"
            f"**Planks:** Oak {planks[0]:,} · Willow {planks[1]:,} · Mahog {planks[2]:,} · Magic {planks[3]:,} · Idea {planks[4]:,}\n"
            f"**Essence:** Desic {essence[0]:,} · Reg {essence[1]:,} · Sturdy {essence[2]:,} · Reinf {essence[3]:,} · Titan {essence[4]:,}\n"
            f"**Rare Materials:** 🔥 Magma Core: {rares[0]} · 🌿 Life Root: {rares[1]} · 👻 Spirit Shard: {rares[2]}\n"
            f"📋 Unidentified Blueprints: {blueprint_count}"
        )
        embed.add_field(name="🏭 Settlement", value=settlement_value, inline=False)

        return embed

    @staticmethod
    async def build_uber(bot, user_id: str, server_id: str) -> discord.Embed:
        uber_data = await bot.database.uber.get_uber_progress(user_id, server_id)
        specials = await bot.database.users.get_uber_materials(user_id)

        embed = discord.Embed(title="Uber Encounters", color=discord.Color.dark_gold())

        bp_status = (
            "✅ Unlocked" if uber_data["celestial_blueprint_unlocked"] else "🔒 Locked"
        )
        embed.add_field(
            name="**Aphrodite**",
            value=(
                f"🔮 Celestial Sigils: {uber_data['celestial_sigils']}\n"
                f"💠 Celestial Engrams: {uber_data['celestial_engrams']}\n"
                f"🪨 Celestial Stone: {specials[0]}\n"
                f"📜 Shrine Blueprint: {bp_status}"
            ),
            inline=True,
        )

        infernal_bp_status = (
            "✅ Unlocked" if uber_data["infernal_blueprint_unlocked"] else "🔒 Locked"
        )
        embed.add_field(
            name="**Lucifer**",
            value=(
                f"🔥 Infernal Sigils: {uber_data['infernal_sigils']}\n"
                f"🔴 Infernal Engrams: {uber_data['infernal_engrams']}\n"
                f"🔥 Infernal Cinder: {specials[1]}\n"
                f"📜 Infernal Forge Blueprint: {infernal_bp_status}"
            ),
            inline=True,
        )

        void_bp_status = (
            "✅ Unlocked"
            if uber_data.get("void_blueprint_unlocked", 0)
            else "🔒 Locked"
        )
        embed.add_field(
            name="**NEET**",
            value=(
                f"⬛ Void Sigils: {uber_data.get('void_shards', 0)}\n"
                f"🔮 Void Engrams: {uber_data.get('void_engrams', 0)}\n"
                f"💎 Void Crystal: {specials[2]}\n"
                f"📜 Void Sanctum Blueprint: {void_bp_status}"
            ),
            inline=True,
        )

        gemini_bp_status = (
            "✅ Unlocked"
            if uber_data.get("gemini_blueprint_unlocked", 0)
            else "🔒 Locked"
        )
        embed.add_field(
            name="**Castor & Pollux**",
            value=(
                f"♊ Gemini Sigils: {uber_data.get('gemini_sigils', 0)}\n"
                f"💠 Gemini Engrams: {uber_data.get('gemini_engrams', 0)}\n"
                f"🔷 Bound Crystal: {specials[3]}\n"
                f"📜 Twin Shrine Blueprint: {gemini_bp_status}"
            ),
            inline=True,
        )

        embed.add_field(
            name="**Evelynn**",
            value=(
                f"☠️ Corruption Sigils: {uber_data.get('corruption_sigils', 0)}\n"
                f"*(costs 3 to challenge)*"
            ),
            inline=True,
        )

        return embed

    @staticmethod
    async def build_essences(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        essence_data = await bot.database.essences.get_all(user_id)

        embed = discord.Embed(
            title="Essence Vault",
            description="Essences used to enchant and upgrade equipment.",
            color=0x9B59B6,
        )
        embed.set_thumbnail(url=user[7])

        if not essence_data:
            embed.add_field(
                name="Empty", value="No essence data found for your account."
            )
            return embed

        items = {}
        if hasattr(essence_data, "keys"):
            items = {
                k: v
                for k, v in dict(essence_data).items()
                if k not in ("user_id", "server_id", "id")
            }

        if not items:
            embed.add_field(name="Empty", value="No essence data available.")
            return embed

        lines = []
        for e_type, count in items.items():
            safe_count = count if count is not None else 0
            name = str(e_type).replace("_", " ").title()
            lines.append(f"✦ **{name}**: {safe_count:,}")

        chunk_size = 12
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i : i + chunk_size]
            embed.add_field(
                name="Stored Essences" if i == 0 else "​",
                value="\n".join(chunk),
                inline=True,
            )

        return embed
