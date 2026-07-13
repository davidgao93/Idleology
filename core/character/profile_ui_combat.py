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
    _POTION_PASSIVE_DESCS,
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
    _normalize,
    group_contributions,
    render_bucket_lines,
)
from core.emojis import (
    ACCESSORY_SLOT,
    ARMOR_SLOT,
    BOOT_SLOT,
    CRIT_MULTI,
    DODGE_EVASION,
    GLOVE_SLOT,
    HELMET_SLOT,
    HEMATURGY_ICON,
    RARITY,
    STAT_ATK,
    STAT_BLOCK,
    STAT_DEF,
    STAT_FDR,
    STAT_HP,
    STAT_PDR,
    STAT_WARD,
    WEAPON_SLOT,
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
        embed.set_thumbnail(url=data["appearance"])

        cb = _compute_combat_bonuses(p)

        # ── Attack ───────────────────────────────────────────────────────────
        # Total/contributions come straight from get_total_attack(explain=True) —
        # the exact same call the combat log uses — so the "Total" here always
        # matches the log's turn-1 baseline modulo the "Combat Start" preview
        # (see _compute_combat_bonuses docstring for what that preview can't see).
        gear_atk = 0
        if p.equipped_weapon:
            gear_atk += p.equipped_weapon.attack
        if p.equipped_accessory:
            gear_atk += p.equipped_accessory.attack
        if p.equipped_glove:
            gear_atk += p.equipped_glove.attack
        if p.equipped_boot:
            gear_atk += p.equipped_boot.attack
        essence_atk = 0
        for _item in (p.equipped_glove, p.equipped_boot):
            if _item:
                essence_atk += compute_essence_stat_bonus(_item).get("attack", 0)
        total_atk, atk_contribs = p.get_total_attack(explain=True)
        barracks_atk = p.flat_atk - p.base_attack - gear_atk - essence_atk
        atk_buckets = group_contributions(atk_contribs[1:])  # skip merged flat entry
        atk_buckets["Base"] = p.base_attack
        atk_buckets["Equipment"] = gear_atk
        if barracks_atk:
            atk_buckets["Barracks"] = barracks_atk
        if essence_atk:
            atk_buckets["Essences"] = atk_buckets.get("Essences", 0) + essence_atk
        total_atk_display = total_atk + cb["atk"]
        atk_lines = [f"**Total: {total_atk_display:,}**"] + render_bucket_lines(
            atk_buckets
        )
        if cb["atk"]:
            atk_lines.append(f"↳ Combat Start: {cb['atk']:+,}")
        embed.add_field(
            name=f"{STAT_ATK} Attack", value="\n".join(atk_lines), inline=True
        )

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
        essence_def = 0
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                essence_def += compute_essence_stat_bonus(_item).get("defence", 0)
        total_def, def_contribs = p.get_total_defence(explain=True)
        barracks_def = p.flat_def - p.base_defence - gear_def - essence_def
        def_buckets = group_contributions(def_contribs[1:])
        def_buckets["Base"] = p.base_defence
        def_buckets["Equipment"] = gear_def
        if barracks_def:
            def_buckets["Barracks"] = barracks_def
        if essence_def:
            def_buckets["Essences"] = def_buckets.get("Essences", 0) + essence_def
        total_def_display = total_def + cb["def"]
        def_lines = [f"**Total: {total_def_display:,}**"] + render_bucket_lines(
            def_buckets
        )
        if cb["def"]:
            def_lines.append(f"↳ Combat Start: {cb['def']:+,}")
        embed.add_field(
            name=f"{STAT_DEF} Defence", value="\n".join(def_lines), inline=True
        )

        # ── HP ───────────────────────────────────────────────────────────────
        total_hp, hp_contribs = p.get_total_max_hp(explain=True)
        hp_buckets = group_contributions(hp_contribs)
        total_hp_display = total_hp + cb["hp"]
        hp_lines = [
            f"**{p.current_hp:,} / {total_hp_display:,}**"
        ] + render_bucket_lines(hp_buckets)
        if cb["hp"]:
            hp_lines.append(f"↳ Combat Start: {cb['hp']:+,}")
        embed.add_field(name=f"{STAT_HP} HP", value="\n".join(hp_lines), inline=True)

        # ── Ward ─────────────────────────────────────────────────────────────
        total_ward, ward_contribs = p.get_total_ward_percentage(explain=True)
        if total_ward > 0:
            ward_hp = p.get_combat_ward_value()
            ward_buckets = group_contributions(ward_contribs)
            ward_lines = [
                f"**{total_ward}%** (= {ward_hp:,} Ward)"
            ] + render_bucket_lines(ward_buckets, suffix="%")
            embed.add_field(
                name=f"{STAT_WARD} Ward", value="\n".join(ward_lines), inline=True
            )

        # ── Hit Chance ───────────────────────────────────────────────────────
        _HIT_BASE_PCT = 60
        hit_weapon_pct = (
            int(p.equipped_weapon.hit_chance * 100)
            if p.equipped_weapon
            else _HIT_BASE_PCT
        )
        hit_essence = 0
        for _item in (p.equipped_glove, p.equipped_boot, p.equipped_helmet):
            if _item:
                hit_essence += compute_essence_stat_bonus(_item).get("hit_pct", 0)
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
        hit_total = hit_weapon_pct + hit_essence + hit_bonuses
        if p.get_glove_corrupted_essence() == "neet":
            hit_val = "**Total: 0%**\n↳ *(NEET Glove — always misses)*"
        else:
            hit_val = f"**Total: {hit_total}%**\n↳ Weapon: {hit_weapon_pct}%"
            if hit_essence:
                hit_val += f"\n↳ Essences: +{hit_essence}%"
            if hit_bonuses:
                hit_val += f"\n↳ Bonuses: +{hit_bonuses}%"
        embed.add_field(name="🎯 Hit Chance", value=hit_val, inline=True)

        # ── Crit Chance ──────────────────────────────────────────────────────
        # Note: Piercing (weapon "piercing_N"), Voracious stacks, and partner
        # co_crit_rate are added on top of get_current_crit_chance() by
        # calculate_crit_chance() (see calc/hit_calc.py) to form the *effective*
        # crit used in combat resolution. The combat log's own STAT BREAKDOWN
        # tracks get_current_crit_chance() only (see combat_log.py _STAT_GETTERS),
        # so Total here intentionally excludes them too, for exact log parity.
        total_crit, crit_contribs = p.get_current_crit_chance(explain=True)
        crit_buckets = group_contributions(crit_contribs)
        total_crit_display = total_crit + cb["crit"]
        crit_lines = [f"**Total: {total_crit_display}%**"] + render_bucket_lines(
            crit_buckets, suffix="%"
        )
        if cb["crit"]:
            crit_lines.append(f"↳ Combat Start: {cb['crit']:+}%")
        embed.add_field(
            name="🗡️ Crit Chance", value="\n".join(crit_lines), inline=True
        )

        # ── Crit Multiplier ──────────────────────────────────────────────────
        total_multi, multi_contribs = p.get_weapon_crit_multi(explain=True)
        multi_buckets = group_contributions(multi_contribs)
        cm_lines = [f"**{total_multi:.2f}×**"] + render_bucket_lines(
            multi_buckets, suffix="×", decimals=2
        )
        embed.add_field(
            name=f"{CRIT_MULTI} Crit Multiplier",
            value="\n".join(cm_lines),
            inline=True,
        )

        # ── PDR ──────────────────────────────────────────────────────────────
        total_pdr, pdr_contribs = p.get_total_pdr(explain=True)
        raw_note = ""
        for label, delta in pdr_contribs:
            if label.startswith("Hard Cap"):
                raw_note = f" ({total_pdr - delta}% uncapped)"
                break
        pdr_buckets = group_contributions(pdr_contribs)
        pdr_lines = [f"**{total_pdr}%**{raw_note}"] + render_bucket_lines(
            pdr_buckets, suffix="%"
        )
        embed.add_field(name=f"{STAT_PDR} PDR", value="\n".join(pdr_lines), inline=True)

        # ── FDR ──────────────────────────────────────────────────────────────
        total_fdr, fdr_contribs = p.get_total_fdr(explain=True)
        if total_fdr > 0:
            fdr_buckets = group_contributions(fdr_contribs)
            fdr_lines = [f"**{total_fdr:,}**"] + render_bucket_lines(fdr_buckets)
            embed.add_field(
                name=f"{STAT_FDR} FDR", value="\n".join(fdr_lines), inline=True
            )

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
            embed.add_field(name=f"{DODGE_EVASION} Evasion", value=eva_val, inline=True)

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
            embed.add_field(name=f"{STAT_BLOCK} Block", value=blk_val, inline=True)

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
                if comp_rarity_pct > 0 and prov_pct > 0:
                    # Two sources — show the combined total plus a per-source breakdown.
                    rar_val += f"\n↳ +{combined_more_pct:.1f}% more (+{gain})"
                    rar_val += f"\n  ↳ Companion: {comp_rarity_pct:.1f}%"
                    rar_val += f"\n  ↳ Providence: {prov_pct:.1f}%"
                elif comp_rarity_pct > 0:
                    rar_val += f"\n↳ Companion: {gain}%"
                else:
                    rar_val += f"\n↳ Providence: {gain}%"
            else:
                after_more = gear_rarity
            codex_bonus = total_rarity - after_more
            if codex_bonus:
                rar_val += f"\n↳ Codex: +{codex_bonus}"
            embed.add_field(name=f"{RARITY} Rarity", value=rar_val, inline=True)

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
    async def build_gear_passives(bot, user_id: str, server_id: str) -> discord.Embed:
        data = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, data, bot.database)

        embed = discord.Embed(title="Gear Passives", color=0x7B68EE)
        embed.set_thumbnail(url=data["appearance"])

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
            _add(f"{WEAPON_SLOT} Weapon", lines)

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
            _add(f"{ARMOR_SLOT} Armor", lines)

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
            _add(f"{ACCESSORY_SLOT} Accessory", lines)

        # ── Glove / Boot / Helmet ─────────────────────────────────────────────
        for icon, slot_label, slot_name, item, pfuncs in (
            (GLOVE_SLOT, "Glove", "glove", p.equipped_glove, _GLOVE_PASSIVE_FUNCS),
            (BOOT_SLOT, "Boot", "boot", p.equipped_boot, _BOOT_PASSIVE_FUNCS),
            (HELMET_SLOT, "Helmet", "helmet", p.equipped_helmet, _HELMET_PASSIVE_FUNCS),
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

        if not has_any:
            embed.description = "No gear passives active."

        return embed

    @staticmethod
    async def build_misc_passives(bot, user_id: str, server_id: str) -> discord.Embed:
        from core.hematurgy.mechanics import HematurgyMechanics

        data = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, data, bot.database)

        embed = discord.Embed(title="Other Passives", color=0x7B68EE)
        embed.set_thumbnail(url=data["appearance"])

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
                field_name = f"{HEMATURGY_ICON} Hematurgy" if i == 0 else "​"
                _add(field_name, lines[i : i + chunk])

        # ── Alchemy Potion Passives ───────────────────────────────────────────
        if p.potion_passives:
            lines = []
            for entry in p.potion_passives:
                ptype = entry.get("passive_type", "")
                pval = entry.get("passive_value", 0)
                pdur = entry.get("passive_duration", 0)
                info = _POTION_PASSIVE_DESCS.get(ptype)
                if info:
                    label, fn = info
                    lines.append(f"• {label} — {fn(pval, pdur)}")
                else:
                    lines.append(f"• {ptype.replace('_', ' ').title()} ({pval:.0f})")
            _add("⚗️ Alchemy Passives", lines)

        if not has_any:
            embed.description = "No other passives active."

        return embed
