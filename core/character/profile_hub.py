from datetime import datetime, timedelta

import discord
from discord import ButtonStyle, Interaction, ui

from core.items.factory import load_player

# ── Passive description tables ───────────────────────────────────────────────

_WEAPON_PASSIVE_DESC: dict[str, str] = {
    # Burning family (Atk +%)
    "burning": "Atk +8%", "flaming": "Atk +16%", "scorching": "Atk +24%",
    "incinerating": "Atk +32%", "carbonising": "Atk +40%",
    # Poisonous family (Miss Dmg)
    "poisonous": "Miss deals up to 8% Atk", "noxious": "Miss deals up to 16% Atk",
    "venomous": "Miss deals up to 24% Atk", "toxic": "Miss deals up to 32% Atk",
    "lethal": "Miss deals up to 40% Atk",
    # Polished family (Def Shred)
    "polished": "Enemy Def -8%", "honed": "Enemy Def -16%", "gleaming": "Enemy Def -24%",
    "tempered": "Enemy Def -32%", "flaring": "Enemy Def -40%",
    # Sparking family (Min Dmg)
    "sparking": "Min Dmg floor 8% of max", "shocking": "Min Dmg floor 16% of max",
    "discharging": "Min Dmg floor 24% of max", "electrocuting": "Min Dmg floor 32% of max",
    "vapourising": "Min Dmg floor 40% of max",
    # Sturdy family (Def Boost)
    "sturdy": "Def +8%", "reinforced": "Def +16%", "thickened": "Def +24%",
    "impregnable": "Def +32%", "impenetrable": "Def +40%",
    # Piercing family (Crit Rate)
    "piercing": "Crit Rolls +5 (easier crits)", "keen": "Crit Rolls +10",
    "incisive": "Crit Rolls +15", "puncturing": "Crit Rolls +20",
    "penetrating": "Crit Rolls +25",
    # Strengthened family (Cull)
    "strengthened": "Instantly kill if enemy HP < 8%",
    "forceful": "Instantly kill if enemy HP < 16%",
    "overwhelming": "Instantly kill if enemy HP < 24%",
    "devastating": "Instantly kill if enemy HP < 32%",
    "catastrophic": "Instantly kill if enemy HP < 40%",
    # Accurate family (Hit Bonus)
    "accurate": "Flat Accuracy +4", "precise": "Flat Accuracy +8",
    "sharpshooter": "Flat Accuracy +12", "deadeye": "Flat Accuracy +16",
    "bullseye": "Flat Accuracy +20",
    # Echo family (Double Hit)
    "echo": "Extra hit 10% Dmg", "echoo": "Extra hit 20% Dmg",
    "echooo": "Extra hit 30% Dmg", "echoooo": "Extra hit 40% Dmg",
    "echoes": "Extra hit 50% Dmg",
}

_INFERNAL_PASSIVE_DESC: dict[str, str] = {
    "soulreap": "Restore HP to full after every successful encounter",
    "inverted edge": "At combat start, swap weapon Attack and Defence",
    "gilded hunger": "Gain Attack equal to 10% of weapon rarity",
    "cursed precision": "+20% Crit Chance; your critical damage is unlucky",
    "diabolic pact": "At combat start, lose 90% max HP and double Attack",
    "perdition": "Missed attacks deal 75% weapon Attack",
    "voracious": "Each non-crit adds a stack; each stack reduces crit threshold by 5",
    "last rites": "Critical hits deal an additional 10% of enemy current HP",
}

_ARMOR_PASSIVE_DESC: dict[str, str] = {
    "invulnerable": "20% chance to take 0 damage for the whole fight",
    "mystical might": "20% chance to deal 10× damage at combat start",
    "omnipotent": "50% chance to double Atk, Def, and gain Max HP as Ward at combat start",
    "treasure hunter": "+5% chance to encounter Treasure Mobs",
    "unlimited wealth": "20% chance to multiply Rarity ×5 at combat start",
    "everlasting blessing": "10% chance on victory to trigger Ideology Propagation",
}

_CELESTIAL_PASSIVE_DESC: dict[str, str] = {
    "celestial ghostreaver": "Generate 50–200 Ward every turn",
    "celestial glancing blows": "Doubles Block Chance; blocked hits deal 50% damage",
    "celestial wind dancer": "Triples Evasion Chance; disables Helmet entirely",
    "celestial sanctity": "Enemies roll final damage twice, apply the lower result",
    "celestial vow": "Once per combat, survive a fatal blow at 1 HP, gain 50% Max HP as Ward",
    "celestial fortress": "+1% PDR per 5% missing HP",
}

_VOID_PASSIVE_DESC: dict[str, str] = {
    "entropy": "At combat start, 20% of weapon ATK added to DEF and vice versa",
    "void echo": "At combat start, 15% of weapon Attack copied to accessory",
    "unravelling": "At combat start, reduce monster Defence by 20%",
    "void gaze": "On crit, reduce monster Attack by 3% per stack (up to 30 stacks)",
    "fracture": "On crit, 5% chance to instantly kill",
    "nullfield": "15% chance to completely absorb incoming damage",
    "eternal hunger": "At 10 hit stacks, deal 10% of monster max HP and restore full HP",
    "oblivion": "Missed attacks still deal 50% of total attack damage",
}

_ACCESSORY_PASSIVE_FUNCS: dict = {
    "obliterate": lambda l: f"{l * 2}% chance to deal Double Damage",
    "absorb": lambda l: f"{l * 10}% chance to steal 10% of Monster ATK & DEF",
    "prosper": lambda l: f"{l * 10}% chance to Double Gold",
    "infinite wisdom": lambda l: f"{l * 5}% chance to Double XP",
    "lucky strikes": lambda l: f"{l * 10}% chance for Lucky Hits",
}

_GLOVE_PASSIVE_FUNCS: dict = {
    "ward-touched": lambda l: f"Gain {l}% of Hit Dmg as Ward",
    "ward-fused": lambda l: f"Gain {l * 2}% of Crit Dmg as Ward",
    "instability": lambda l: f"Hits are 50% OR {150 + l * 10}% damage",
    "deftness": lambda l: f"Crit Floor raised by {l * 5}%",
    "adroit": lambda l: f"Normal Hit Floor raised by {l * 2}%",
    "equilibrium": lambda l: f"Gain {l * 5}% of Dmg as Bonus XP",
    "plundering": lambda l: f"Gain {l * 10}% of Dmg as Bonus Gold",
}

_BOOT_PASSIVE_FUNCS: dict = {
    "speedster": lambda l: f"Cooldown reduced by {l}m",
    "skiller": lambda l: f"{l * 5}% chance for extra skill materials",
    "treasure-tracker": lambda l: f"Treasure Mob chance +{l * 0.5:.1f}%",
    "hearty": lambda l: f"Max HP +{l * 5}%",
    "cleric": lambda l: f"Potions heal {l * 10}% extra",
    "thrill-seeker": lambda l: f"Special Drop Chance +{l}%",
}

_HELMET_PASSIVE_FUNCS: dict = {
    "juggernaut": lambda l: f"Gain {l * 4}% of Base Def as Atk",
    "insight": lambda l: f"Crit Dmg Multiplier +{l * 0.1:.1f}× (total: {2.0 + l * 0.1:.1f}×)",
    "volatile": lambda l: f"Deal {l * 100}% of Max HP as Dmg on ward break",
    "divine": lambda l: f"Converts {l * 100}% of Potion Overheal to Ward",
    "frenzy": lambda l: f"{l * 0.5:.1f}% increased damage per 1% missing HP",
    "leeching": lambda l: f"Heal {l * 2}% of base damage dealt",
    "thorns": lambda l: f"Reflect {l * 100}% of blocked damage",
    "ghosted": lambda l: f"Gain {l * 10} Ward on Dodge",
}

_ESSENCE_TYPE_DESC: dict = {
    "power": lambda v: f"+{int(v)} flat Atk",
    "protection": lambda v: f"+{int(v)} PDR & FDR",
    "insight": lambda v: f"+{int(v)} Crit Chance",
    "evasion": lambda v: f"+{int(v)}% Evasion",
    "unyielding": lambda v: f"+{int(v)}% Block",
}

_CORRUPTED_DESC: dict[tuple, str] = {
    ("aphrodite", "glove"): "Ward-affecting hits count as ward-breaking",
    ("aphrodite", "boot"): "Equipment drop chance is lucky",
    ("aphrodite", "helmet"): "Ward cannot be forcibly disabled",
    ("lucifer", "glove"): "Attacks deal flat dmg equal to 15% of current ward pool",
    ("lucifer", "boot"): "Gold drops +10% per monster modifier (max +50%)",
    ("lucifer", "helmet"): "On ward break, gain 15% PDR for remainder of combat",
    ("gemini", "glove"): "Crits strike twice; 2nd hit deals 40–60% of the first",
    ("gemini", "boot"): "Pet drop chance doubled",
    ("gemini", "helmet"): "Damage splits between ward and HP; damage taken halved",
    ("voidling", "glove"): "Normal hits become misses; only crits deal direct damage",
    ("voidling", "boot"): "Skilling resources gained in combat are duplicated",
    ("voidling", "helmet"): "Ward gained is doubled",
}

_SLAYER_EMBLEM_NAMES: dict[str, str] = {
    "slayer_dmg": "Slayer Target Damage",
    "boss_dmg": "Boss Damage",
    "combat_dmg": "Normal Monster Damage",
    "slayer_def": "Slayer Target Defence",
    "crit_dmg": "Crit Damage",
    "accuracy": "Accuracy",
    "gold_find": "Gold Find",
    "xp_find": "XP Find",
    "task_progress": "Double Task Progress",
    "slayer_drops": "Slayer Drop Rate",
}

_SLAYER_EMBLEM_FUNCS: dict = {
    "slayer_dmg": lambda t: f"+{t * 5}% damage vs assigned slayer species",
    "boss_dmg": lambda t: f"+{t * 5}% damage vs bosses",
    "combat_dmg": lambda t: f"+{t * 2}% damage vs normal monsters",
    "slayer_def": lambda t: f"+{t * 2}% defence vs assigned slayer species",
    "crit_dmg": lambda t: f"+{t * 5}% critical hit damage",
    "accuracy": lambda t: f"+{t * 2} flat accuracy",
    "gold_find": lambda t: f"+{t * 3}% gold from combat",
    "xp_find": lambda t: f"+{t * 3}% XP from combat",
    "task_progress": lambda t: f"{t * 5}% chance for a kill to count twice",
    "slayer_drops": lambda t: f"{t * 5}% chance for extra slayer drops",
}

_CODEX_TOME_INFO: dict = {
    "vitality": ("🌿 Vitality", lambda v: f"+{v}% Max HP"),
    "wrath": ("🔥 Wrath", lambda v: f"+{v}% of base DEF as bonus ATK"),
    "bastion": ("🛡️ Bastion", lambda v: f"+{v}% of base ATK as bonus DEF"),
    "tenacity": ("⚡ Tenacity", lambda v: f"{v}% chance per hit to halve damage"),
    "bloodthirst": ("🩸 Bloodthirst", lambda v: f"Heal {v}% of critical hit damage"),
    "providence": ("✨ Providence", lambda v: f"+{v}% more to total rarity"),
    "precision": ("🎯 Precision", lambda v: f"+{v} flat crit chance"),
    "insight": ("🎯 Insight", lambda v: f"+{v} flat crit chance"),
    "affluence": ("💰 Affluence", lambda v: f"+{v}% XP and Gold from combat"),
    "bulwark": ("🪨 Bulwark", lambda v: f"+{v}% Percent Damage Reduction"),
    "resilience": ("🔒 Resilience", lambda v: f"+{v} Flat Damage Reduction"),
}


# ── Passive formatting helpers ────────────────────────────────────────────────

def _desc_fixed(table: dict, name: str) -> str:
    return table.get(name.lower(), name.title())


def _desc_scaled(table: dict, name: str, level: int) -> str:
    fn = table.get(name.lower())
    return fn(level) if fn else name.title()


def _format_essence_slot(etype: str, val: float) -> str:
    key = etype.lower()
    for k, fn in _ESSENCE_TYPE_DESC.items():
        if k in key:
            return f"{k.title()} Essence — {fn(val)}"
    return f"{etype.title()} Essence — {val}"


def _format_corrupted(etype: str, slot: str) -> str:
    key = (etype.lower(), slot.lower())
    desc = _CORRUPTED_DESC.get(key, etype.title())
    display = etype.replace("_", " ").title()
    return f"Corrupted ({display}) — {desc}"


def _build_gear_passive_text(p) -> str:
    lines: list[str] = []

    if p.equipped_weapon:
        w = p.equipped_weapon
        wlines: list[str] = []
        if w.passive != "none":
            wlines.append(f"• Forge: {w.passive.title()} — {_desc_fixed(_WEAPON_PASSIVE_DESC, w.passive)}")
        if w.p_passive != "none":
            wlines.append(f"• Pinnacle: {w.p_passive.title()} — {_desc_fixed(_WEAPON_PASSIVE_DESC, w.p_passive)}")
        if w.u_passive != "none":
            wlines.append(f"• Utmost: {w.u_passive.title()} — {_desc_fixed(_WEAPON_PASSIVE_DESC, w.u_passive)}")
        if w.infernal_passive != "none":
            wlines.append(f"• Infernal: {w.infernal_passive.title()} — {_desc_fixed(_INFERNAL_PASSIVE_DESC, w.infernal_passive)}")
        if wlines:
            lines.append("**⚔️ Weapon**")
            lines.extend(wlines)

    if p.equipped_armor:
        a = p.equipped_armor
        alines: list[str] = []
        if a.passive != "none":
            alines.append(f"• {a.passive.title()} — {_desc_fixed(_ARMOR_PASSIVE_DESC, a.passive)}")
        if a.celestial_passive != "none":
            alines.append(f"• {a.celestial_passive.title()} — {_desc_fixed(_CELESTIAL_PASSIVE_DESC, a.celestial_passive)}")
        if alines:
            lines.append("**🛡️ Armor**")
            lines.extend(alines)

    if p.equipped_accessory:
        acc = p.equipped_accessory
        acclines: list[str] = []
        if acc.passive != "none":
            desc = _desc_scaled(_ACCESSORY_PASSIVE_FUNCS, acc.passive, acc.passive_lvl)
            acclines.append(f"• {acc.passive.title()} L{acc.passive_lvl} — {desc}")
        if acc.void_passive != "none":
            acclines.append(f"• {acc.void_passive.title()} — {_desc_fixed(_VOID_PASSIVE_DESC, acc.void_passive)}")
        if acclines:
            lines.append("**📿 Accessory**")
            lines.extend(acclines)

    for item, label, slot_name, pfuncs in (
        (p.equipped_glove, "**🧤 Glove**", "glove", _GLOVE_PASSIVE_FUNCS),
        (p.equipped_boot, "**👢 Boot**", "boot", _BOOT_PASSIVE_FUNCS),
        (p.equipped_helmet, "**🪖 Helmet**", "helmet", _HELMET_PASSIVE_FUNCS),
    ):
        if not item:
            continue
        ilines: list[str] = []
        if item.passive != "none":
            desc = _desc_scaled(pfuncs, item.passive, item.passive_lvl)
            ilines.append(f"• {item.passive.title()} L{item.passive_lvl} — {desc}")
        for etype, val in (
            (item.essence_1, item.essence_1_val),
            (item.essence_2, item.essence_2_val),
            (item.essence_3, item.essence_3_val),
        ):
            if etype != "none":
                ilines.append(f"• {_format_essence_slot(etype, val)}")
        if item.corrupted_essence != "none":
            ilines.append(f"• {_format_corrupted(item.corrupted_essence, slot_name)}")
        if ilines:
            lines.append(label)
            lines.extend(ilines)

    return "\n".join(lines)


def _build_slayer_codex_text(p) -> str:
    lines: list[str] = []

    emblem_lines: list[str] = []
    for slot_key in ("slot_1", "slot_2", "slot_3", "slot_4", "slot_5"):
        slot = p.slayer_emblem.get(slot_key)
        if not slot:
            continue
        etype = slot.get("type")
        tier = slot.get("tier", 0)
        if etype and etype != "none" and tier and tier > 0:
            name = _SLAYER_EMBLEM_NAMES.get(etype, etype.replace("_", " ").title())
            fn = _SLAYER_EMBLEM_FUNCS.get(etype)
            desc = fn(tier) if fn else f"T{tier}"
            emblem_lines.append(f"• {name} T{tier} — {desc}")
    if emblem_lines:
        lines.append("**🗡️ Slayer Emblems**")
        lines.extend(emblem_lines)

    tome_lines: list[str] = []
    for tome in p.codex_tomes:
        if tome.tier <= 0:
            continue
        info = _CODEX_TOME_INFO.get(tome.passive_type)
        val = int(round(tome.value))
        if info:
            display_name, desc_fn = info
            tome_lines.append(f"• {display_name} T{tome.tier} ({val}) — {desc_fn(val)}")
        else:
            tome_lines.append(f"• {tome.passive_type.title()} T{tome.tier} ({val})")
    if tome_lines:
        lines.append("**📖 Codex Tomes**")
        lines.extend(tome_lines)

    return "\n".join(lines)


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
        embed.add_field(name="🛡️ Defence", value=def_val, inline=True)

        # ── HP ───────────────────────────────────────────────────────────────
        total_hp = p.total_max_hp
        hp_bonuses = total_hp - p.max_hp
        hp_val = f"**{p.current_hp:,} / {total_hp:,}**\n↳ Base: {p.max_hp:,}"
        if hp_bonuses:
            hp_val += f"\n↳ Bonuses: {hp_bonuses:+,}"
        embed.add_field(name="❤️ HP", value=hp_val, inline=True)

        # ── Ward ─────────────────────────────────────────────────────────────
        ward = p.get_total_ward_percentage()
        if ward > 0:
            ward_hp = p.get_combat_ward_value()
            embed.add_field(name="🔮 Ward", value=f"**{ward}%** (= {ward_hp:,} HP)", inline=True)

        # ── Crit Chance ──────────────────────────────────────────────────────
        crit_acc = p.equipped_accessory.crit if p.equipped_accessory else 0
        # Weapon crit (no weapon.crit field yet; piercing passive shown in Gear Passives)
        crit_weapon = 0
        total_crit = p.get_current_crit_chance()
        crit_other = total_crit - crit_acc - crit_weapon
        crit_val = f"**Total: {total_crit}**\n↳ Weapon: {crit_weapon}\n↳ Accessory: {crit_acc}"
        if crit_other:
            crit_val += f"\n↳ Bonuses: {crit_other:+}"
        embed.add_field(name="🎯 Crit Chance", value=crit_val, inline=True)

        # ── Crit Multiplier ──────────────────────────────────────────────────
        crit_multi = 2.0
        if p.equipped_helmet and p.equipped_helmet.passive.lower() == "insight":
            crit_multi += p.equipped_helmet.passive_lvl * 0.1
        embed.add_field(name="✨ Crit Multiplier", value=f"**{crit_multi:.1f}×**", inline=True)

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
        pdr_str = f"**{capped_pdr}%**" + (f" ({raw_pdr}% uncapped)" if raw_pdr > 80 else "")
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
            embed.add_field(
                name="🔒 FDR",
                value=f"**{total_fdr}**\n↳ Equipment: {fdr_equip}\n↳ Other: {fdr_other}",
                inline=True,
            )

        # ── Rarity ───────────────────────────────────────────────────────────
        gear_rarity = p.rarity
        total_rarity = p.get_total_rarity()
        rarity_bonuses = total_rarity - gear_rarity
        if total_rarity > 0:
            rar_val = f"**{total_rarity}%**\n↳ Equipment: {gear_rarity}%"
            if rarity_bonuses:
                rar_val += f"\n↳ Bonuses: {rarity_bonuses:+}%"
            embed.add_field(name="✨ Rarity", value=rar_val, inline=True)

        # ── Gear Passives ─────────────────────────────────────────────────────
        gear_text = _build_gear_passive_text(p)
        if gear_text:
            if len(gear_text) > 1020:
                gear_text = gear_text[:1020] + "…"
            embed.add_field(name="⚡ Gear Passives", value=gear_text, inline=False)

        # ── Slayer & Codex ────────────────────────────────────────────────────
        other_text = _build_slayer_codex_text(p)
        if other_text:
            if len(other_text) > 1020:
                other_text = other_text[:1020] + "…"
            embed.add_field(name="🗡️ Slayer & Codex", value=other_text, inline=False)

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
        r_partner = await bot.database.users.get_currency(user_id, "partnership_runes")
        antique_tomes = await bot.database.users.get_currency(user_id, "antique_tome")
        pinnacle_keys = await bot.database.users.get_currency(user_id, "pinnacle_key")
        uber_data = await bot.database.uber.get_uber_progress(user_id, server_id)

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
            name="💎 **Runes**",
            value=(
                f"🔨 Refinement: {user[19]}\n✨ Potential: {user[21]}\n🔮 Imbuing: {user[27]}\n"
                f"💥 Shatter: {user[31]}\n🤝 Partnership: {r_partner}"
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
                f"🗝️ Void Keys: {user[30]}\n🎁 Curios: {user[22]}\n"
                f"📖 Antique Tomes: {antique_tomes}\n🗝️ Pinnacle Keys: {pinnacle_keys}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🌀 **Elemental Keys**",
            value=(
                f"⚗️ Blessed Bismuth: {uber_data['blessed_bismuth']}\n"
                f"🌿 Sparkling Sprig: {uber_data['sparkling_sprig']}\n"
                f"🐟 Capricious Carp: {uber_data['capricious_carp']}"
            ),
            inline=True,
        )

        return embed

    @staticmethod
    async def build_cooldowns(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, user, bot.database)

        # 1. Combat Cooldown (Calculate Speedster Passive)
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
            except:
                return "Ready!"

        embed = discord.Embed(title="Active Timers & Cooldowns", color=0xBEBEFE)
        embed.set_thumbnail(url=user[7])

        # Standard Cooldowns
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

        # 2. Settlement Production
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

        # 3. Companion Adventures
        active_comps = await bot.database.companions.get_active(user_id)
        if not active_comps:
            embed.add_field(
                name="🐾 Companions",
                value="No active companions deployed.",
                inline=False,
            )
        else:
            # Fetch the collection timer specifically
            cursor = await bot.database.connection.execute(
                "SELECT last_companion_collect_time FROM users WHERE user_id = ?",
                (user_id,),
            )
            res = await cursor.fetchone()
            c_time_str = res[0] if res else None

            if c_time_str:
                try:
                    c_last = datetime.fromisoformat(c_time_str)
                    c_diff = (datetime.now() - c_last).total_seconds()

                    cycles = int(c_diff // 1800)  # 30 mins per cycle

                    if cycles >= 48:
                        embed.add_field(
                            name="🐾 Companions",
                            value="**48/48** adventures completed! (MAXED)\nWaiting to be collected.",
                            inline=False,
                        )
                    else:
                        next_cycle_rem = 1800 - (c_diff % 1800)
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

        return embed

    @staticmethod
    async def build_resources(bot, user_id: str, server_id: str) -> discord.Embed:
        settlement = await bot.database.settlement.get_settlement(user_id, server_id)

        async with bot.database.connection.execute(
            "SELECT iron, coal, gold, platinum, idea FROM mining WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as c:
            ores = await c.fetchone() or (0, 0, 0, 0, 0)
        async with bot.database.connection.execute(
            "SELECT oak_logs, willow_logs, mahogany_logs, magic_logs, idea_logs FROM woodcutting WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as c:
            logs = await c.fetchone() or (0, 0, 0, 0, 0)
        async with bot.database.connection.execute(
            "SELECT desiccated_bones, regular_bones, sturdy_bones, reinforced_bones, titanium_bones FROM fishing WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as c:
            bones = await c.fetchone() or (0, 0, 0, 0, 0)
        async with bot.database.connection.execute(
            "SELECT iron_bar, steel_bar, gold_bar, platinum_bar, idea_bar FROM mining WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as c:
            ingots = await c.fetchone() or (0, 0, 0, 0, 0)
        async with bot.database.connection.execute(
            "SELECT oak_plank, willow_plank, mahogany_plank, magic_plank, idea_plank FROM woodcutting WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as c:
            planks = await c.fetchone() or (0, 0, 0, 0, 0)
        async with bot.database.connection.execute(
            "SELECT desiccated_essence, regular_essence, sturdy_essence, reinforced_essence, titanium_essence FROM fishing WHERE user_id=? AND server_id=?",
            (user_id, server_id),
        ) as c:
            essence = await c.fetchone() or (0, 0, 0, 0, 0)
        async with bot.database.connection.execute(
            "SELECT magma_core, life_root, spirit_shard FROM users WHERE user_id=?",
            (user_id,),
        ) as c:
            rares = await c.fetchone() or (0, 0, 0)

        embed = discord.Embed(
            title="Storage Warehouse", color=discord.Color.dark_orange()
        )
        embed.add_field(
            name="🏭 Settlement",
            value=f"🪵 Timber: {settlement.timber:,}\n🪨 Stone: {settlement.stone:,}",
            inline=False,
        )
        embed.add_field(
            name="⛏️ Ores",
            value=f"Iron Ore: {ores[0]:,}\nCoal: {ores[1]:,}\nGold Ore: {ores[2]:,}\nPlatinum Ore: {ores[3]:,}\nIdea Ore: {ores[4]:,}",
            inline=True,
        )
        embed.add_field(
            name="🪓 Logs",
            value=f"Oak Logs: {logs[0]:,}\nWillow Logs: {logs[1]:,}\nMahogany Logs: {logs[2]:,}\nMagic Logs: {logs[3]:,}\nIdea Logs: {logs[4]:,}",
            inline=True,
        )
        embed.add_field(
            name="🎣 Bones",
            value=f"Desiccated Bones: {bones[0]:,}\nRegular Bones: {bones[1]:,}\nSturdy Bones: {bones[2]:,}\nReinforced Bones: {bones[3]:,}\nTitanium Bones: {bones[4]:,}",
            inline=True,
        )
        embed.add_field(
            name="🧱 Ingots",
            value=f"Iron: {ingots[0]:,}\nSteel: {ingots[1]:,}\nGold: {ingots[2]:,}\nPlat: {ingots[3]:,}\nIdea: {ingots[4]:,}",
            inline=True,
        )
        embed.add_field(
            name="🪵 Planks",
            value=f"Oak: {planks[0]:,}\nWillow: {planks[1]:,}\nMahog: {planks[2]:,}\nMagic: {planks[3]:,}\nIdea: {planks[4]:,}",
            inline=True,
        )
        embed.add_field(
            name="⚗️ Essence",
            value=f"Desic: {essence[0]:,}\nReg: {essence[1]:,}\nSturdy: {essence[2]:,}\nReinf: {essence[3]:,}\nTitan: {essence[4]:,}",
            inline=True,
        )
        embed.add_field(
            name="✨ Rare Materials",
            value=f"🔥 Magma Core: {rares[0]}\n🌿 Life Root: {rares[1]}\n👻 Spirit Shard: {rares[2]}",
            inline=False,
        )
        return embed

    @staticmethod
    async def build_uber(bot, user_id: str, server_id: str) -> discord.Embed:
        uber_data = await bot.database.uber.get_uber_progress(user_id, server_id)

        async with bot.database.connection.execute(
            "SELECT celestial_stone, infernal_cinder, void_crystal, bound_crystal FROM users WHERE user_id=?",
            (user_id,),
        ) as c:
            specials = await c.fetchone() or (0, 0, 0, 0)

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

        return embed

    @staticmethod
    async def build_essences(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)

        # Fetch essence inventory
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

        # Safely parse the database return, ignoring primary/foreign keys
        items = {}
        if hasattr(essence_data, "keys"):  # Dict or aiosqlite.Row
            items = {
                k: v
                for k, v in dict(essence_data).items()
                if k not in ("user_id", "server_id", "id")
            }

        if not items:
            embed.add_field(name="Empty", value="No essence data available.")
            return embed

        # Format lines dynamically (Showing ALL essences, including 0s)
        lines = []
        for e_type, count in items.items():
            safe_count = count if count is not None else 0
            name = str(e_type).replace("_", " ").title()
            lines.append(f"✦ **{name}**: {safe_count:,}")

        # Split into columns to make it look clean (12 items per column)
        chunk_size = 12
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i : i + chunk_size]
            # Use an invisible character for the title if there are multiple columns
            embed.add_field(
                name="Stored Essences" if i == 0 else "\u200b",
                value="\n".join(chunk),
                inline=True,
            )

        return embed


class ProfileHubView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, active_tab: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.active_tab = active_tab
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        try:
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)
        except:
            pass

    def update_buttons(self):
        self.clear_items()

        tabs = [
            ("card", "Card", "👤"),
            ("stats", "Stats", "📊"),
            ("inventory", "Inventory", "🎒"),
            ("cooldowns", "Cooldowns", "⏰"),
            ("resources", "Resources", "📦"),
            ("uber", "Uber", "⚔️"),
            ("essences", "Essences", "💎"),
        ]

        for tab_id, label, emoji in tabs:
            style = (
                ButtonStyle.primary
                if self.active_tab == tab_id
                else ButtonStyle.secondary
            )
            btn = ui.Button(label=label, emoji=emoji, style=style, custom_id=tab_id)
            btn.callback = self.handle_tab_switch
            self.add_item(btn)

    async def handle_tab_switch(self, interaction: Interaction):
        tab_id = interaction.data["custom_id"]
        if tab_id == self.active_tab:
            return await interaction.response.defer()

        self.active_tab = tab_id
        self.update_buttons()
        await interaction.response.defer()

        # Build new embed based on selected tab
        embed = None
        if tab_id == "card":
            embed = await ProfileBuilder.build_card(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "stats":
            embed = await ProfileBuilder.build_stats(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "inventory":
            embed = await ProfileBuilder.build_inventory(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "cooldowns":
            embed = await ProfileBuilder.build_cooldowns(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "resources":
            embed = await ProfileBuilder.build_resources(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "uber":
            embed = await ProfileBuilder.build_uber(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "essences":
            embed = await ProfileBuilder.build_essences(
                self.bot, self.user_id, self.server_id
            )

        await interaction.edit_original_response(embed=embed, view=self)
