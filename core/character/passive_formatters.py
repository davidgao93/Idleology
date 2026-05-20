"""
core/character/passive_formatters.py
Pure formatting helpers for displaying gear passives and computing
deterministic combat-start bonuses for the profile hub.
"""

from core.character.passive_data import (
    _CORRUPTED_DESC,
    _ROMAN,
)


def _normalize(name: str) -> str:
    return name.lower().replace("_", " ")


def _desc_fixed(table: dict, name: str) -> str:
    key = _normalize(name)
    return table.get(key, name.replace("_", " ").title())


def _desc_scaled(table: dict, name: str, level: int) -> str:
    fn = table.get(_normalize(name))
    return fn(level) if fn else name.replace("_", " ").title()


def _format_weapon_passive(key: str) -> str:
    """Formats 'burning_3' → 'Burning III'. Falls back gracefully for unknown formats."""
    if not key or key == "none":
        return key
    if "_" in key:
        family, _, tier_str = key.rpartition("_")
        try:
            return f"{family.title()} {_ROMAN.get(int(tier_str), tier_str)}"
        except ValueError:
            pass
    return key.title()


def _get_piercing_crit_bonus(passive: str) -> int:
    """Returns the flat crit-chance bonus from a piercing_N passive (+5 per tier)."""
    if passive and passive.startswith("piercing_"):
        try:
            return int(passive.split("_")[1]) * 5
        except (ValueError, IndexError):
            pass
    return 0


def _format_essence_slot(etype: str, raw_val: float, item) -> str:
    """Format an essence slot description, computing actual flat values from item stats."""
    key = etype.lower()
    if key == "power":
        is_helmet = type(item).__name__ == "Helmet"
        if is_helmet:
            flat_def = int(item.defence * raw_val / 100)
            flat_ward = int(item.ward * raw_val / 100)
            parts = []
            if flat_def:
                parts.append(f"+{flat_def} Def")
            if flat_ward:
                parts.append(f"+{flat_ward}% Ward")
            return f"Power Essence ({int(raw_val)}%) — {' | '.join(parts) or 'no base stats'}"
        else:
            flat_atk = int(item.attack * raw_val / 100)
            return f"Power Essence ({int(raw_val)}%) — +{flat_atk} flat Atk"
    elif key == "protection":
        flat_pdr = int(item.pdr * raw_val / 100)
        flat_fdr = int(item.fdr * raw_val / 100)
        parts = []
        if flat_pdr:
            parts.append(f"+{flat_pdr}% PDR")
        if flat_fdr:
            parts.append(f"+{flat_fdr} FDR")
        return f"Protection Essence ({int(raw_val)}%) — {' | '.join(parts) or 'no base PDR/FDR to amplify'}"
    elif key == "insight":
        return f"Insight Essence — +{int(raw_val)} Crit Chance"
    elif key == "evasion":
        return f"Evasion Essence — +{int(raw_val)}% Evasion"
    elif key == "blocking":
        return f"Blocking Essence — +{int(raw_val)}% Block"
    elif key == "deftness":
        return f"Deftness Essence — +{raw_val:.2f}× Crit Multiplier"
    elif key == "precision":
        return f"Precision Essence — +{int(raw_val)}% Hit Chance"
    elif key == "gluttony":
        return f"Gluttony Essence — +{int(raw_val)}% Max HP"
    return f"{etype.replace('_', ' ').title()} Essence — {raw_val}"


def _format_corrupted(etype: str, slot: str) -> str:
    key = (_normalize(etype), slot.lower())
    desc = _CORRUPTED_DESC.get(key, etype.replace("_", " ").title())
    display = etype.replace("_", " ").title()
    return f"Corrupted ({display}) — {desc}"


def _compute_combat_bonuses(p) -> dict:
    """Compute deterministic (non-random) combat-start stat bonuses for display."""
    from core.combat.calc.calcs import get_weapon_tier

    cb: dict = {"atk": 0, "def": 0, "hp": 0, "crit": 0, "special_rarity": 0.0}

    # Partner combat skills (deterministic only)
    if p.active_partner:
        partner = p.active_partner
        for key, lvl in partner.combat_skills:
            if not key:
                continue
            if key == "co_stat_transfer":
                cb["atk"] += int(partner.total_attack * lvl * 0.10)
                cb["def"] += int(partner.total_defence * lvl * 0.10)
                cb["hp"] += int(partner.total_hp * lvl * 0.10)
            elif key == "co_atk_from_def":
                cb["atk"] += int(partner.total_defence * lvl * 0.25)
            elif key == "co_def_from_atk":
                cb["def"] += int(partner.total_attack * lvl * 0.20)
            elif key == "co_special_rarity":
                cb["special_rarity"] += lvl * 0.1

    # Juggernaut (helmet passive — deterministic: always triggers at combat start)
    # Uses flat_def to match compute_def_as_atk_bonus() in passives.py
    if p.equipped_helmet and _normalize(p.equipped_helmet.passive) == "juggernaut":
        cb["atk"] += int(p.flat_def * p.equipped_helmet.passive_lvl * 0.04)

    # Sturdy family (weapon passive — boosts defence by a fixed %)
    idx, _ = get_weapon_tier(p, "sturdy")
    if idx >= 0:
        cb["def"] += int(p.get_total_defence() * (idx + 1) * 0.08)

    # Infernal passives (deterministic ones only)
    if p.equipped_weapon and p.equipped_weapon.infernal_passive not in ("none", ""):
        inf = _normalize(p.equipped_weapon.infernal_passive)
        if inf == "inverted edge":
            delta = p.equipped_weapon.defence - p.equipped_weapon.attack
            cb["atk"] += delta
            cb["def"] -= delta
        elif inf == "gilded hunger":
            cb["atk"] += int(p.get_total_rarity() * 0.1)
        elif inf == "cursed precision":
            cb["crit"] += 20
        elif inf == "diabolic pact":
            cb["hp"] -= int(p.max_hp * 0.90)
            cb["atk"] += p.get_total_attack()

    # Void passives (deterministic ones only)
    if p.equipped_accessory and p.equipped_accessory.void_passive not in ("none", ""):
        void_p = _normalize(p.equipped_accessory.void_passive)
        if void_p == "entropy" and p.equipped_weapon:
            atk_t = int(p.equipped_weapon.attack * 0.20)
            def_t = int(p.equipped_weapon.defence * 0.20)
            cb["atk"] += def_t - atk_t
            cb["def"] += atk_t - def_t
        elif void_p == "void echo" and p.equipped_weapon:
            cb["atk"] += int(p.equipped_weapon.attack * 0.15)

    return cb
