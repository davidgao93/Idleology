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
        hit_companion = p._get_companion_bonus("hit")
        hit_accuracy_emblem = p.get_emblem_bonus("accuracy") * 2
        hit_bonuses = hit_deadeye + hit_ascension + hit_companion + hit_accuracy_emblem
        hit_total = hit_weapon_pct + hit_bonuses
        # NEET glove corrupted essence forces accuracy to 0 in combat
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
            sr_boot = (
                p.equipped_boot.passive_lvl * 0.5
            )  # 0.5% per level, max 3% at rank 6
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
        puzzle_boxes = await bot.database.users.get_currency(
            user_id, "curio_puzzle_boxes"
        )
        items = await bot.database.partners.get_items(user_id)
        guild_tickets = items.get("guild_tickets", 0)

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
                f"🐉 Draconic Keys: {user[27]}\n🪽 Angelic Keys: {user[28]}\n🟣 Void Frags: {user[31]}\n"
                f"⚖️ Balance Frags: {k_balance}\n❤️‍🔥 Soul Cores: {user[30]}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📦 **Misc Items**",
            value=(
                f"🎁 Curios: {user[22]}\n"
                f"🎁 Puzzle Boxes: {puzzle_boxes}\n"
                f"🎫 Guild Tickets: {guild_tickets}\n"
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
                f"🔨 Refinement: {user[19]}\n✨ Potential: {user[21]}\n🔮 Imbuing: {user[29]}\n"
                f"💥 Shatter: {user[33]}\n🤝 Partnership: {r_partner}\n"
                f"🪞 Mirage (Imperfect): {mirage_imp}\n🪞 Mirage (Perfected): {mirage_perf}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🗝️ **Void Keys**",
            value=f"🗝️ Void Keys: {user[32]}",
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

        embed = discord.Embed(title="Active Timers & Cooldowns", color=0xBEBEFE)
        embed.set_thumbnail(url=user[7])

        def _fmt_ms(time_str, cooldown_td: timedelta) -> str:
            """MMm SSs remaining, for short cooldowns."""
            if not time_str:
                return "Ready!"
            try:
                total = int(
                    (
                        cooldown_td
                        - (datetime.now() - datetime.fromisoformat(time_str))
                    ).total_seconds()
                )
                if total <= 0:
                    return "Ready!"
                m, s = divmod(total, 60)
                return f"**{m}m {s:02d}s**"
            except Exception:
                return "Ready!"

        def _fmt_hms(time_str, cooldown_td: timedelta) -> str:
            """HH MMm SSs remaining."""
            if not time_str:
                return "Ready!"
            try:
                total = int(
                    (
                        cooldown_td
                        - (datetime.now() - datetime.fromisoformat(time_str))
                    ).total_seconds()
                )
                if total <= 0:
                    return "Ready!"
                h, r = divmod(total, 3600)
                m, s = divmod(r, 60)
                return f"**{h}h {m:02d}m {s:02d}s**"
            except Exception:
                return "Ready!"

        def _secs_to_hms(secs: int) -> str:
            h, r = divmod(max(0, secs), 3600)
            m, s = divmod(r, 60)
            return f"**{h}h {m:02d}m {s:02d}s**"

        # ── Section 1: Core ──────────────────────────────────────────────────
        combat_cd_mins = 10
        if p.equipped_boot and p.equipped_boot.passive == "speedster":
            combat_cd_mins -= p.equipped_boot.passive_lvl

        MAX_STAMINA = 10
        stamina_data = await bot.database.users.get_stamina(user_id)
        stamina = stamina_data["combat_stamina"]
        last_regen_str = stamina_data["last_stamina_regen"]

        if stamina >= MAX_STAMINA:
            stamina_line = f"⚡ Stamina: **{stamina}/{MAX_STAMINA}** (full)"
        else:
            regen_suffix = ""
            if last_regen_str:
                try:
                    next_regen = datetime.fromisoformat(last_regen_str) + timedelta(
                        hours=1
                    )
                    rem_secs = int((next_regen - datetime.now()).total_seconds())
                    if rem_secs > 0:
                        rm, rs = divmod(rem_secs, 60)
                        regen_suffix = f" · next regen: {rm}m {rs:02d}s"
                except Exception:
                    pass
            stamina_line = f"⚡ **{stamina}/{MAX_STAMINA}**{regen_suffix}"

        core_lines = ["⚔️ **/combat**", stamina_line]
        if stamina == 0:
            core_lines.append(
                f"Cooldown: {_fmt_ms(user[24], timedelta(minutes=combat_cd_mins))}"
            )

        core_lines.append(
            f"🛏️ **/rest** — {_fmt_hms(user[13], timedelta(hours=2))} *(free; paid has no cooldown)*"
        )

        try:
            incubation = await bot.database.eggs.get_incubation(user_id, server_id)
            if incubation:
                start_dt = datetime.fromisoformat(incubation["start_time"])
                duration = incubation["duration_seconds"]
                elapsed_secs = (datetime.utcnow() - start_dt).total_seconds()
                remaining = max(0.0, duration - elapsed_secs)
                if remaining > 0:
                    rh, rr = divmod(int(remaining), 3600)
                    rm, rs = divmod(rr, 60)
                    rem_str = f"**{rh}h {rm:02d}m {rs:02d}s**"
                else:
                    rem_str = "Ready to hatch!"
                pct = int(min(100, elapsed_secs / max(duration, 1) * 100))
                core_lines.append(
                    f"🥚 **Hatchery** — {incubation['monster_name']}: {rem_str} ({pct}%)"
                )
        except Exception:
            pass

        embed.add_field(name="⚙️ Core", value="\n".join(core_lines), inline=False)

        # ── Section 2: Daily ─────────────────────────────────────────────────
        quest_meta: dict = {}
        try:
            await bot.database.quests.ensure_meta(user_id)
            quest_meta = await bot.database.quests.get_meta(user_id)
        except Exception:
            pass
        checkin_last = quest_meta.get("checkin_last_time") if quest_meta else None

        player_level = user["level"] if isinstance(user, dict) else user[4]

        # Board reset cooldown
        board_cooldown_str = "Ready!"
        try:
            from core.quests.mechanics import get_board_cooldown_remaining
            all_contracts = await bot.database.quests.get_contracts(user_id, server_id)
            if all_contracts:
                latest = max(all_contracts, key=lambda c: c.get("locked_at", ""), default=None)
                if latest and latest.get("locked_at"):
                    rem = get_board_cooldown_remaining(latest["locked_at"])
                    if rem.total_seconds() > 0:
                        rh, rr = divmod(int(rem.total_seconds()), 3600)
                        rm, rs = divmod(rr, 60)
                        board_cooldown_str = f"**{rh}h {rm:02d}m {rs:02d}s**"
        except Exception:
            pass

        daily_lines = [
            f"💡 **/propagate** — {_fmt_hms(user[14], timedelta(hours=18))}",
            f"📋 **Quest Board** — {board_cooldown_str}",
        ]
        if player_level >= 10:
            daily_lines.insert(0, f"🛖 **/checkin** — {_fmt_hms(checkin_last, timedelta(hours=18))}")

        from core.maw.mechanics import (
            MAX_FIGHTS_PER_CYCLE,
            fight_available,
            fight_remaining_seconds,
            get_current_cycle_id,
            is_cycle_active,
        )

        now_utc = datetime.now(timezone.utc)
        now_ts = int(now_utc.timestamp())
        maw_cycle_id = get_current_cycle_id(now_utc)

        if player_level >= 20:
            if is_cycle_active(maw_cycle_id, now_ts):
                maw_record = await bot.database.maw.get_record(user_id, maw_cycle_id)
                if maw_record:
                    fights_done = maw_record["fights_this_cycle"]
                    last_fight_ts = maw_record["last_fight_ts"]
                    fights_left = max(0, MAX_FIGHTS_PER_CYCLE - fights_done)
                    if fights_done >= MAX_FIGHTS_PER_CYCLE:
                        fight_str = f"All fights used (0/{MAX_FIGHTS_PER_CYCLE} left)"
                    elif fight_available(last_fight_ts, fights_done, now_ts):
                        fight_str = f"Ready! ({fights_left}/{MAX_FIGHTS_PER_CYCLE} left)"
                    else:
                        fight_str = (
                            f"{_secs_to_hms(fight_remaining_seconds(last_fight_ts, now_ts))}"
                            f" ({fights_left}/{MAX_FIGHTS_PER_CYCLE} left)"
                        )
                    daily_lines.append(f"🌑 **Maw Fight** — {fight_str}")
                else:
                    daily_lines.append("🌑 **Maw Fight** — Not participated this cycle")
            else:
                daily_lines.append("🌑 **Maw Fight** — No active cycle")

        # DC craft daily reset
        if player_level >= 50:
            dc_crafted_today = await bot.database.users.get_dc_crafted_today(user_id)
            _dc_now = datetime.now()
            _next_midnight = _dc_now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            _dc_secs = int((_next_midnight - _dc_now).total_seconds())
            _dch, _dcr = divmod(_dc_secs, 3600)
            _dcm, _dcs = divmod(_dcr, 60)
            dc_reset_str = f"**{_dch}h {_dcm:02d}m {_dcs:02d}s**"
            _dc_remaining = max(0, 10 - dc_crafted_today)
            daily_lines.append(
                f"📜 **DC Craft** — {_dc_remaining}/10 remaining · resets in {dc_reset_str}"
            )

        embed.add_field(name="📅 Daily", value="\n".join(daily_lines), inline=False)

        # ── Section 3: Horizon ───────────────────────────────────────────────
        horizon_lines = []

        if player_level >= 50:
            settlement = await bot.database.settlement.get_settlement(user_id, server_id)
            if settlement and settlement.last_collection_time:
                try:
                    s_last = datetime.fromisoformat(settlement.last_collection_time)
                    blocks = max(0, int((datetime.now() - s_last).total_seconds() // 3600))
                    horizon_lines.append(
                        f"🏭 **Settlement** — {blocks} block(s) of production completed"
                    )
                except Exception:
                    pass

        if player_level >= 40:
            active_comps = await bot.database.companions.get_active(user_id)
            if not active_comps:
                horizon_lines.append("🐾 **Companions** — No companions deployed")
            else:
                c_time_str = await bot.database.users.get_companion_collect_time(user_id)
                if c_time_str:
                    try:
                        c_diff = (
                            datetime.now() - datetime.fromisoformat(c_time_str)
                        ).total_seconds()
                        cycles = min(48, int(c_diff // 3600))
                        if cycles >= 48:
                            horizon_lines.append(
                                "🐾 **Companions** — 48/48 adventures (ready to collect!)"
                            )
                        else:
                            horizon_lines.append(
                                f"🐾 **Companions** — {cycles}/48 adventures completed"
                            )
                    except Exception:
                        horizon_lines.append("🐾 **Companions** — Ready to deploy")
                else:
                    horizon_lines.append("🐾 **Companions** — Ready to deploy")

        from core.models import Partner
        from core.partners.data import PARTNER_DATA
        from core.partners.dispatch import (
            BOSS_PARTY_DURATION_HOURS,
            elapsed_hours,
            get_cap_hours,
        )

        if player_level >= 10:
            rows = await bot.database.partners.get_owned(user_id)
            all_partners = [
                Partner.from_row(row, PARTNER_DATA[row[2]])
                for row in rows
                if row[2] in PARTNER_DATA
            ]

            active_dispatch = next(
                (
                    partner
                    for partner in all_partners
                    if partner.is_dispatched
                    and partner.dispatch_task
                    and partner.dispatch_task != "boss_party"
                ),
                None,
            )
            # Include any partner whose task is boss_party, regardless of is_dispatched flag,
            # as long as they have a start time (covers edge cases where the flag de-synced).
            boss_party = [
                partner
                for partner in all_partners
                if partner.dispatch_task == "boss_party"
                and (partner.is_dispatched or partner.dispatch_start_time)
            ]

            if active_dispatch:
                elapsed = elapsed_hours(active_dispatch.dispatch_start_time)
                cap = get_cap_hours(active_dispatch)
                elapsed_h = min(int(cap), int(elapsed))
                task_label = (active_dispatch.dispatch_task or "unknown").title()
                if elapsed >= cap:
                    horizon_lines.append(
                        f"📋 **Partner** — {int(cap)}/{int(cap)} hours of {task_label} completed (ready!)"
                    )
                else:
                    horizon_lines.append(
                        f"📋 **Partner** — {elapsed_h}/{int(cap)} hours of {task_label} completed"
                    )
            else:
                horizon_lines.append("📋 **Partner** — No partner dispatched")
        else:
            boss_party = []

        if boss_party:
            bp_elapsed = elapsed_hours(boss_party[0].dispatch_start_time)
            bp_cap = int(BOSS_PARTY_DURATION_HOURS)
            bp_done = min(bp_cap, int(bp_elapsed))
            if bp_done >= bp_cap:
                horizon_lines.append(
                    f"🔱 **Boss Raid** — {bp_cap}/{bp_cap} hours completed (ready!)"
                )
            else:
                horizon_lines.append(
                    f"🔱 **Boss Raid** — {bp_done}/{bp_cap} hours completed"
                )

        embed.add_field(name="🌅 Horizon", value="\n".join(horizon_lines), inline=False)

        # ── Section 4: Gathering ─────────────────────────────────────────────
        # Familiarization gate timers + banked Momentum per skill.
        # Only shown when at least one skill has an active or recently-cleared gate.
        try:
            from core.skills.mechanics import SkillMechanics

            _skill_cfg = {
                "mining":      ("⛏️", "Mining"),
                "fishing":     ("🎣", "Fishing"),
                "woodcutting": ("🪓", "Woodcutting"),
            }
            gathering_lines: list[str] = []
            for sk, (emo, label) in _skill_cfg.items():
                fam_end, mom = await bot.database.skills.get_familiarization_state(
                    user_id, server_id, sk
                )
                remaining = SkillMechanics.get_familiarization_remaining_seconds(fam_end, mom)
                if remaining > 0:
                    gh, gr = divmod(remaining // 60, 60)
                    line = f"{emo} **{label}** — Familiarizing: **{gh}h {gr:02d}m**"
                    if mom:
                        line += f" *(Momentum: −{mom} min applied)*"
                    gathering_lines.append(line)
                elif fam_end:
                    # Gate recently lifted but momentum still banked
                    line = f"{emo} **{label}** — ✅ Gate lifted"
                    if mom:
                        line += f" *(+{mom} min Momentum available for next gate)*"
                    gathering_lines.append(line)

            if gathering_lines:
                embed.add_field(
                    name="⛏️ Gathering",
                    value="\n".join(gathering_lines),
                    inline=False,
                )
        except Exception:
            pass

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

        # Artisan Mastery remnants (Quality branch output)
        mastery_row = await bot.database.skills.get_mastery(user_id, server_id)
        geode_cores = mastery_row.get("geode_cores", 0) or 0
        tide_relics = mastery_row.get("tide_relics", 0) or 0
        heartwood_shards = mastery_row.get("heartwood_shards", 0) or 0

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

        mastery_value = (
            f"⛏️ **Geode Cores:** {geode_cores:,}\n"
            f"🐟 **Tide Relics:** {tide_relics:,}\n"
            f"🪵 **Heartwood Shards:** {heartwood_shards:,}"
        )
        embed.add_field(name="🌿 Artisan Mastery (Remnants)", value=mastery_value, inline=False)

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
