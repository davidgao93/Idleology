"""
core/character/profile_ui_combat.py
Embed builders for the stats and passives tabs of the Profile Hub.
"""

import discord

from core.character.passive_data import (
    _ACCESSORY_PASSIVE_FUNCS,
    _ARMOR_PASSIVE_DESC,
    _BOOT_PASSIVE_FUNCS,
    _CELESTIAL_PASSIVE_DESC,
    _CODEX_TOME_INFO,
    _GLOVE_PASSIVE_FUNCS,
    _HELMET_PASSIVE_FUNCS,
    _HEMATURGY_SHORT_FUNCS,
    _INFERNAL_PASSIVE_DESC,
    _SLAYER_EMBLEM_FUNCS,
    _SLAYER_EMBLEM_NAMES,
    _VOID_PASSIVE_DESC,
    _WEAPON_PASSIVE_DESC,
)
from core.character.passive_formatters import (
    _compute_combat_bonuses,
    _desc_fixed,
    _desc_scaled,
    _format_corrupted,
    _format_weapon_passive,
    _get_piercing_crit_bonus,
    _normalize,
)
from core.items.factory import load_player


class CombatProfileBuilder:
    """Embed builders for the stats and passives profile tabs."""

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
        hit_companion = p._get_companion_bonus("hit")
        hit_accuracy_emblem = p.get_emblem_bonus("accuracy") * 2
        hit_bonuses = hit_deadeye + hit_ascension + hit_companion + hit_accuracy_emblem
        hit_total = hit_weapon_pct + hit_bonuses
        if p.get_glove_corrupted_essence() == "neet":
            hit_val = "**Total: 0%**\n↳ *(NEET Glove — always misses)*"
        else:
            hit_val = f"**Total: {hit_total}%**\n↳ Weapon: {hit_weapon_pct}%"
            if hit_bonuses:
                hit_val += f"\n↳ Bonuses: +{hit_bonuses} flat"
        embed.add_field(name="🎯 Hit Chance", value=hit_val, inline=True)

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
        weapon_base_multi = p.equipped_weapon.crit_multi if p.equipped_weapon else 2.0
        crit_multi_total = p.get_weapon_crit_multi()
        cm_val = f"**{crit_multi_total:.2f}×**\n↳ Weapon: {weapon_base_multi:.2f}×"
        crit_multi_bonus = round(crit_multi_total - weapon_base_multi, 4)
        if crit_multi_bonus > 0:
            cm_val += f"\n↳ Bonuses: +{crit_multi_bonus:.2f}×"
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

        # ── Evasion ───────────────────────────────────────────────────────────
        evasion_armor = p.equipped_armor.evasion if p.equipped_armor else 0
        evasion_essence = 0
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                evasion_essence += compute_essence_stat_bonus(_item).get("evasion", 0)
        total_evasion = evasion_armor + evasion_essence
        if total_evasion > 0:
            eva_val = f"**{total_evasion}%**\n↳ Armor: {evasion_armor}%"
            if evasion_essence:
                eva_val += f"\n↳ Essences: +{evasion_essence}%"
            embed.add_field(name="💨 Evasion", value=eva_val, inline=True)

        # ── Block ─────────────────────────────────────────────────────────────
        block_armor = p.equipped_armor.block if p.equipped_armor else 0
        block_essence = 0
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                block_essence += compute_essence_stat_bonus(_item).get("block", 0)
        total_block = block_armor + block_essence
        if total_block > 0:
            blk_val = f"**{total_block}%**\n↳ Armor: {block_armor}%"
            if block_essence:
                blk_val += f"\n↳ Essences: +{block_essence}%"
            embed.add_field(name="🧱 Block", value=blk_val, inline=True)

        # ── Rarity ───────────────────────────────────────────────────────────
        gear_rarity = p.rarity
        comp_rarity_pct = p._get_companion_bonus("rarity")
        prov_pct = p.get_tome_bonus("providence")
        combined_more_pct = comp_rarity_pct + prov_pct
        total_rarity = p.get_total_rarity()
        if total_rarity > 0:
            rar_val = f"**{total_rarity}%**\n↳ Equipment: {gear_rarity}%"
            if combined_more_pct > 0 and gear_rarity > 0:
                after_more = int(gear_rarity * (1 + combined_more_pct / 100))
                gain = after_more - gear_rarity
                rar_val += f"\n↳ +{combined_more_pct:.1f}% more (+{gain})"
                if comp_rarity_pct > 0:
                    rar_val += f"\n  ↳ Companion: {comp_rarity_pct:.1f}%"
                if prov_pct > 0:
                    rar_val += f"\n  ↳ Providence: {prov_pct:.1f}%"
            else:
                after_more = gear_rarity
            codex_bonus = total_rarity - after_more
            if codex_bonus:
                rar_val += f"\n↳ Codex: +{codex_bonus}"
            embed.add_field(name="✨ Rarity", value=rar_val, inline=True)

        # ── Special Rarity ────────────────────────────────────────────────────
        sr_boot = 0.0
        if p.equipped_boot and p.equipped_boot.passive == "thrill-seeker":
            sr_boot = p.equipped_boot.passive_lvl * 0.5
        sr_armor = (
            3
            if (p.equipped_armor and p.equipped_armor.passive == "Treasure Hunter")
            else 0
        )
        sr_companion = p._get_companion_bonus("s_rarity")
        sr_partner_combat = cb["special_rarity"]
        sr_total = min(20.0, sr_boot + sr_armor + sr_companion + sr_partner_combat)
        sr_val = f"**{sr_total:.1f}%** (cap: 20%)"
        if sr_armor or sr_boot:
            sr_val += f"\n↳ Equipment: +{sr_armor + sr_boot:.1f}%"
        if sr_companion or sr_partner_combat:
            sr_bonus = sr_companion + sr_partner_combat
            sr_val += f"\n↳ Bonuses: {sr_bonus:.1f}%"
        embed.add_field(name="⭐ Special Rarity", value=sr_val, inline=True)

        return embed

    @staticmethod
    async def build_passives(bot, user_id: str, server_id: str) -> discord.Embed:
        from core.hematurgy.mechanics import HematurgyMechanics

        data = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, data, bot.database)

        embed = discord.Embed(title="Active Passives", color=0x7B68EE)
        embed.set_thumbnail(url=data[7])

        has_any = False

        def _add(name: str, lines: list[str]) -> None:
            nonlocal has_any
            if not lines:
                return
            body = "\n".join(lines)
            if len(body) > 1020:
                body = body[:1020] + "…"
            embed.add_field(name=name, value=body, inline=False)
            has_any = True

        # ── Weapon ───────────────────────────────────────────────────────────
        if p.equipped_weapon:
            w = p.equipped_weapon
            lines: list[str] = []
            if w.passive not in ("none", ""):
                lines.append(
                    f"• **Forge:** {_format_weapon_passive(w.passive)} — {_WEAPON_PASSIVE_DESC.get(w.passive, '?')}"
                )
            if w.p_passive not in ("none", ""):
                lines.append(
                    f"• **Pinnacle:** {_format_weapon_passive(w.p_passive)} — {_WEAPON_PASSIVE_DESC.get(w.p_passive, '?')}"
                )
            if w.u_passive not in ("none", ""):
                lines.append(
                    f"• **Utmost:** {_format_weapon_passive(w.u_passive)} — {_WEAPON_PASSIVE_DESC.get(w.u_passive, '?')}"
                )
            if w.infernal_passive not in ("none", ""):
                lines.append(
                    f"• **Infernal:** {w.infernal_passive.replace('_', ' ').title()} — {_desc_fixed(_INFERNAL_PASSIVE_DESC, w.infernal_passive)}"
                )
            _add("⚔️ Weapon", lines)

        # ── Armor ─────────────────────────────────────────────────────────────
        if p.equipped_armor:
            a = p.equipped_armor
            lines = []
            if a.passive not in ("none", ""):
                desc = _ARMOR_PASSIVE_DESC.get(_normalize(a.passive), "Unknown effect")
                lines.append(
                    f"• **Imbue:** {a.passive.replace('_', ' ').title()} — {desc}"
                )
            if a.celestial_passive not in ("none", ""):
                lines.append(
                    f"• **Celestial:** {a.celestial_passive.replace('_', ' ').title()} — {_desc_fixed(_CELESTIAL_PASSIVE_DESC, a.celestial_passive)}"
                )
            _add("🛡️ Armor", lines)

        # ── Accessory ─────────────────────────────────────────────────────────
        if p.equipped_accessory:
            acc = p.equipped_accessory
            lines = []
            if acc.passive != "none":
                desc = _desc_scaled(
                    _ACCESSORY_PASSIVE_FUNCS, acc.passive, acc.passive_lvl
                )
                lines.append(
                    f"• **Enchant:** {acc.passive.replace('_', ' ').title()} L{acc.passive_lvl} — {desc}"
                )
            if acc.void_passive != "none":
                lines.append(
                    f"• **Void:** {acc.void_passive.replace('_', ' ').title()} — {_desc_fixed(_VOID_PASSIVE_DESC, acc.void_passive)}"
                )
            _add("📿 Accessory", lines)

        # ── Glove / Boot / Helmet ─────────────────────────────────────────────
        for icon, slot_label, slot_name, item, pfuncs in (
            ("🧤", "Glove", "glove", p.equipped_glove, _GLOVE_PASSIVE_FUNCS),
            ("👢", "Boot", "boot", p.equipped_boot, _BOOT_PASSIVE_FUNCS),
            ("🪖", "Helmet", "helmet", p.equipped_helmet, _HELMET_PASSIVE_FUNCS),
        ):
            if not item:
                continue
            lines = []
            if item.passive != "none":
                desc = _desc_scaled(pfuncs, item.passive, item.passive_lvl)
                lines.append(
                    f"• **Enchant:** {item.passive.replace('_', ' ').title()} L{item.passive_lvl} — {desc}"
                )
            if item.corrupted_essence != "none":
                lines.append(
                    f"• {_format_corrupted(item.corrupted_essence, slot_name)}"
                )
            _add(f"{icon} {slot_label}", lines)

        # ── Slayer Emblem ─────────────────────────────────────────────────────
        if p.slayer_emblem:
            lines = []
            for slot_key in sorted(p.slayer_emblem.keys()):
                slot_data = p.slayer_emblem.get(slot_key)
                if not slot_data:
                    continue
                ptype = slot_data.get("type")
                if not ptype or ptype.lower() == "none":
                    continue
                tier = slot_data.get("tier", 1)
                e_name = _SLAYER_EMBLEM_NAMES.get(
                    ptype, ptype.replace("_", " ").title()
                )
                fn = _SLAYER_EMBLEM_FUNCS.get(ptype)
                desc = fn(tier) if fn else "?"
                lines.append(f"• **{e_name}** (T{tier}) — {desc}")
            _add("🩸 Slayer Emblem", lines)

        # ── Codex Tomes ───────────────────────────────────────────────────────
        if p.codex_tomes:
            lines = []
            for tome in p.codex_tomes:
                info = _CODEX_TOME_INFO.get(tome.passive_type)
                if info:
                    t_name, t_fn = info
                    lines.append(f"• **{t_name}** (T{tome.tier}) — {t_fn(tome.value)}")
            _add("📚 Codex Tomes", lines)

        # ── Hematurgy ─────────────────────────────────────────────────────────
        if p.hematurgy_passives:
            lines = []
            for pid, tier in p.hematurgy_passives.items():
                h_name = HematurgyMechanics.passive_display_name(pid)
                fn = _HEMATURGY_SHORT_FUNCS.get(pid)
                h_desc = fn(tier) if fn else "?"
                lines.append(f"• **{h_name}** (T{tier}) — {h_desc}")
            chunk = 10
            for i in range(0, len(lines), chunk):
                field_name = "💉 Hematurgy" if i == 0 else "​"
                _add(field_name, lines[i : i + chunk])

        if not has_any:
            embed.description = "No active passives found."

        return embed
