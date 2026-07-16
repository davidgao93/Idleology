"""
core/character/passive_formatters.py
Pure formatting helpers for displaying gear passives and computing
deterministic combat-start bonuses for the profile hub.
"""

from core.character.passive_data import (
    _ACCESSORY_PASSIVE_FUNCS,
    _ARMOR_PASSIVE_DESC,
    _BOOT_PASSIVE_FUNCS,
    _CELESTIAL_PASSIVE_DESC,
    _CORRUPTED_DESC,
    _GLOVE_PASSIVE_FUNCS,
    _HELMET_PASSIVE_FUNCS,
    _INFERNAL_PASSIVE_DESC,
    _ROMAN,
    _VOID_PASSIVE_DESC,
    _WEAPON_PASSIVE_DESC,
)

_SCALED_PASSIVE_TABLES = {
    "accessory": _ACCESSORY_PASSIVE_FUNCS,
    "glove": _GLOVE_PASSIVE_FUNCS,
    "boot": _BOOT_PASSIVE_FUNCS,
    "helmet": _HELMET_PASSIVE_FUNCS,
}


def get_weapon_passive_description(passive: str) -> str:
    """Looks up the effect text for a weapon passive key, e.g. 'burning_3'."""
    if not passive or passive == "none":
        return ""
    return _WEAPON_PASSIVE_DESC.get(passive.lower(), "")


def get_armor_passive_description(passive: str) -> str:
    """Looks up the effect text for a fixed armor passive name, e.g. 'Impregnable'."""
    if not passive or passive == "none":
        return ""
    return _ARMOR_PASSIVE_DESC.get(_normalize(passive), "")


def get_void_passive_description(passive: str) -> str:
    """Looks up the effect text for a corrupted accessory void passive, e.g. 'void_gaze'."""
    if not passive or passive == "none":
        return ""
    return _VOID_PASSIVE_DESC.get(_normalize(passive), "")


def get_celestial_passive_description(passive: str) -> str:
    """Looks up the effect text for a Celestial armor passive, e.g. 'celestial_vow'."""
    if not passive or passive == "none":
        return ""
    return _CELESTIAL_PASSIVE_DESC.get(_normalize(passive), "")


def get_infernal_passive_description(passive: str) -> str:
    """Looks up the effect text for an Infernal weapon passive, e.g. 'diabolic_pact'."""
    if not passive or passive == "none":
        return ""
    return _INFERNAL_PASSIVE_DESC.get(_normalize(passive), "")


def get_scaled_passive_description(item_type: str, passive: str, level: int) -> str:
    """Looks up the effect text for a levelled accessory/glove/boot/helmet passive."""
    table = _SCALED_PASSIVE_TABLES.get(item_type)
    if not table or not passive or passive == "none":
        return ""
    fn = table.get(_normalize(passive))
    return fn(level) if fn else ""


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


def _format_corrupted(etype: str, slot: str) -> str:
    key = (_normalize(etype), slot.lower())
    desc = _CORRUPTED_DESC.get(key, etype.replace("_", " ").title())
    display = etype.replace("_", " ").title()
    return f"Corrupted ({display}) — {desc}"


def _compute_combat_bonuses(p) -> dict:
    """Compute deterministic (non-random) combat-start stat bonuses for display.

    Mirrors `apply_stat_effects` / `apply_combat_start_passives` (see
    core/combat/turns/passives.py) and `apply_hematurgy_start` (see
    core/hematurgy/engine.py) closely enough to preview what the "Combat bonus
    accumulator" will read at turn 1 of the player's next fight. Deliberately
    excludes RNG-gated sources (Absorb, Unlimited Wealth, the sig_co_skol
    essence-buff roll) since those can't be known before a real monster/roll
    exists — the profile page can only ever show the deterministic subset, so
    a combat log may show extra RNG-sourced deltas this preview omits.
    """
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

    # Transcendence (armor passive — 20% of flat ATK + DEF as bonus ATK)
    if p.equipped_armor and _normalize(p.equipped_armor.passive) == "transcendence":
        cb["atk"] += int((p.flat_atk + p.flat_def) * 0.20)

    # Sturdy (and Piercing) are folded directly into
    # get_total_defence()/get_current_crit_chance(), so they no longer need a
    # "combat start" preview here — the stats page already reflects them
    # permanently. Burning is an on-hit "increased damage" source (see
    # hit_calc.py build_attack_multiplier), like Piety — it never touches the
    # ATK stat, so it's intentionally absent from this preview too.

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
            cb["hp"] -= int(p.max_hp * 0.50)
            cb["atk"] += p.flat_atk

    # Void passives (deterministic ones only)
    if p.equipped_accessory and p.equipped_accessory.void_passive not in ("none", ""):
        void_p = _normalize(p.equipped_accessory.void_passive)
        if void_p == "entropy" and p.equipped_weapon:
            atk_t = int(p.equipped_weapon.attack * 0.20)
            def_t = int(p.equipped_weapon.defence * 0.20)
            cb["atk"] += def_t
            cb["def"] += atk_t
        elif void_p == "void echo" and p.equipped_weapon:
            cb["atk"] += int(p.equipped_weapon.attack * 0.30)

    # Inner Sanctum Recovery — permanent ATK malus scaling with points spent
    # in the path (see apply_stat_effects). Monster-independent, always active.
    is_nodes = getattr(p, "inner_sanctum_nodes", None)
    if is_nodes:
        from core.inner_sanctum.mechanics import get_tree_bonuses

        recovery_malus_pct = get_tree_bonuses(is_nodes)["recovery_atk_malus_pct"]
        if recovery_malus_pct > 0:
            cb["atk"] -= int(p.flat_atk * recovery_malus_pct)

    # Soul Stone combat-start passives (deterministic tiers only — Absorb and
    # Unlimited Wealth are RNG-gated and skipped, see docstring above). Each
    # is skipped if the equivalent gear passive is already active, matching
    # the "not (...)" guards in _apply_soul_stone_start.
    if p.soul_stone:
        from core.apex.data import SOUL_STONE_TIER_VALUES as _SST
        from core.apex.mechanics import ApexMechanics

        ss_transcendence = p.get_soul_stone_passive("transcendence")
        if ss_transcendence and not (
            p.equipped_armor and _normalize(p.equipped_armor.passive) == "transcendence"
        ):
            pct = _SST["transcendence"][ss_transcendence - 1]
            cb["atk"] += int((p.flat_atk + p.flat_def) * pct / 100)

        ss_juggernaut = p.get_soul_stone_passive("juggernaut")
        if ss_juggernaut and not (
            p.equipped_helmet and _normalize(p.equipped_helmet.passive) == "juggernaut"
        ):
            cb["atk"] += int(p.flat_def * ss_juggernaut * 4.0 / 100)

        res = ApexMechanics.get_resonance_multipliers(p.soul_stone)
        tyr_pct = res.get("tyr_pct", 0.0)
        if tyr_pct > 0:
            combined = int((p.flat_atk + p.flat_def) * (1 + tyr_pct))
            half = combined // 2
            cb["atk"] += max(0, half - p.flat_atk)
            cb["def"] += max(0, half - p.flat_def)

    # Hematurgy Ward Inoculation — converts the current ward pool into flat
    # DEF and doubles Max HP; both fire unconditionally whenever owned (see
    # apply_hematurgy_start).
    if p.hematurgy_passives:
        from core.hematurgy.engine import get_h
        from core.hematurgy.mechanics import tier_val

        wi_tier = get_h(p, "ward_inoculation")
        if wi_tier is not None:
            ward_val = p.get_combat_ward_value()
            if ward_val > 0:
                cb["def"] += int(ward_val * tier_val("ward_inoculation", wi_tier))
            # Doubling is anchored to the stable base (bonus_max_hp zeroed
            # out first) so the preview matches apply_hematurgy_start().
            saved_bonus = p.bonus_max_hp
            p.bonus_max_hp = 0
            cb["hp"] += p.total_max_hp
            p.bonus_max_hp = saved_bonus

    return cb


# ---------------------------------------------------------------------------
# Contribution-label categorization — shared by the profile stats page so it
# can group the exact (source_label, delta) pairs returned by every
# get_total_*(explain=True) Player getter into the same short buckets used
# here, instead of re-deriving totals by hand (see profile_ui_combat.py).
# Keeping this table in sync with new contribution labels is the only way to
# add a stat source without the profile page silently drifting from the
# combat log again.
# ---------------------------------------------------------------------------

_CATEGORY_RULES: list[tuple[str, str]] = [
    ("hematurgy", "Hematurgy"),
    ("ascension pinnacle", "Ascent"),
    ("vitality/hearty/respite", "Passives"),
    ("tome", "Codex"),
    ("codex", "Codex"),
    ("monster parts", "Parts"),
    ("stat investment", "Stats"),
    ("essence", "Essences"),
    ("corrupted", "Essences"),
    ("soul stone", "Passives"),
    ("artefact", "Passives"),
    ("slayer", "Passives"),
    ("insight helmet", "Passives"),
    (" passive", "Passives"),  # "weapon passive", "boot passive", "armor passive", ...
    ("alchemy enrage", "Passives"),
    ("partner co_", "Bonus"),
    ("companions", "Bonus"),
    ("combat bonus accumulator", "Bonus"),
    ("multiplier", "Bonus"),
    ("hard cap", "Bonus"),
    ("run penalty", "Codex"),
    ("run bonus", "Codex"),
    ("equipment", "Equipment"),
    ("weapon base crit", "Equipment"),
    ("accessory crit", "Equipment"),
    ("accessory", "Accessory"),
    ("weapon base", "Base"),
    ("base max hp", "Base"),
    ("base + equipment", "Base"),
]

# Fixed display order for grouped buckets (skipped when empty). Base/Equipment/
# Barracks are only ever populated manually by callers that split the merged
# "Base + Equipment + Essences" contribution (ATK/DEF) — every other bucket
# is reachable directly from categorize_contribution().
CATEGORY_ORDER: list[str] = [
    "Base",
    "Equipment",
    "Barracks",
    "Essences",
    "Accessory",
    "Stats",
    "Hematurgy",
    "Ascent",
    "Codex",
    "Passives",
    "Bonus",
    "Parts",
]

# Categories shown even when their value is zero (every other category is
# hidden when empty, since it's just noise once the accumulator is empty).
_ALWAYS_SHOWN_CATEGORIES = {"Base", "Equipment"}


def render_bucket_lines(
    buckets: dict[str, float],
    *,
    suffix: str = "",
    decimals: int = 0,
    label_overrides: dict[str, str] | None = None,
) -> list[str]:
    """Renders grouped buckets as '↳ Category: value' lines in CATEGORY_ORDER,
    skipping empty buckets except Base/Equipment (shown even at zero). No
    leading '+' on positive values — every line here is an accumulator
    contribution, so the sign is implied; negative deltas still show '-'.
    label_overrides optionally renames a category's displayed label (e.g. the
    "Bonus" catch-all -> "Other bonus sources" when it's nested under a
    "Bonus:" group header, to avoid the name collision)."""
    lines = []
    for cat in CATEGORY_ORDER:
        if cat not in buckets:
            continue
        val = buckets[cat]
        label = (label_overrides or {}).get(cat, cat)
        if cat in _ALWAYS_SHOWN_CATEGORIES or val:
            lines.append(f"↳ {label}: {val:,.{decimals}f}{suffix}")
    return lines


# Which display buckets belong under the "Flat" group header for each stat's
# nested Flat/Bonus/Total breakdown (see profile_ui_combat.py build_stats).
# Everything else present in a stat's buckets dict falls under "Bonus".
FLAT_BUCKET_KEYS: dict[str, set[str]] = {
    # ATK/DEF: literal gear/base/essence/barracks contributions only — every
    # %-of-flat source (Ascension pinnacle, Companions, Stat Investment,
    # Wrath/Bastion tomes, Hematurgy, ...) is a Bonus, matching flat_atk/flat_def.
    "atk": {"Base", "Equipment", "Barracks", "Essences"},
    "def": {"Base", "Equipment", "Barracks", "Essences"},
    # Max HP has no flat_hp cache and a different contribution shape: Base,
    # Codex Run Bonus, and Ascension Pinnacle/Monster Parts are literal flat
    # adds (not %), so they anchor Flat; Vitality/Hearty/Gluttony/Stat
    # Investment are all %-of-running-base multipliers, so they're Bonus.
    "hp": {"Base", "Ascent", "Parts", "Codex"},
}


def split_flat_bonus_buckets(
    buckets: dict[str, float], stat_key: str
) -> "tuple[dict[str, float], dict[str, float]]":
    """Splits a group_contributions() bucket dict into (flat_buckets,
    bonus_buckets) using FLAT_BUCKET_KEYS[stat_key]. stat_key is 'atk',
    'def', or 'hp'."""
    flat_keys = FLAT_BUCKET_KEYS.get(stat_key, set())
    flat = {k: v for k, v in buckets.items() if k in flat_keys}
    bonus = {k: v for k, v in buckets.items() if k not in flat_keys}
    return flat, bonus


def render_flat_bonus_total_lines(
    stat_key: str,
    flat_total: float,
    buckets: dict[str, float],
    baseline_total: float,
    combat_start_delta: float,
    *,
    suffix: str = "",
    decimals: int = 0,
    total_label: str = "Total",
) -> list[str]:
    """Renders the nested Total / Flat / Bonus breakdown used by the stats
    page for ATK, DEF, and Max HP — mirrors the turn-1 baseline stat
    breakdown in combat_log.py (Total = Flat + Bonus + Combat Start, where
    Combat Start is the deterministic apply_combat_start_passives() preview
    measured as a real before/after diff, never a hand-derived approximation).
    Total is rendered first (with its Flat/Bonus/Combat Start sub-lines),
    followed by the Flat and Bonus breakdowns themselves.

    flat_total: player.flat_atk / flat_def, or the Flat-bucket sum for HP.
    buckets: full group_contributions() dict for this stat (Base/Equipment/
        Barracks/Essences/Stats/Hematurgy/Ascent/Codex/Passives/Bonus/Parts).
    baseline_total: the stat's real total BEFORE combat-start bonuses are
        seeded (i.e. get_total_attack()/get_total_defence()/get_total_max_hp()
        on a freshly-loaded Player) — equals flat_total + bonus_total exactly.
    combat_start_delta: the before/after diff once combat-start bonuses are
        seeded into bonus_atk/bonus_def/bonus_max_hp.
    total_label: display label for the top-line total (e.g. "Max HP (in
        Combat)" for HP, since "Total" doesn't distinguish it from current HP).
    """
    flat_buckets, bonus_buckets = split_flat_bonus_buckets(buckets, stat_key)
    bonus_total = baseline_total - flat_total
    grand_total = baseline_total + combat_start_delta

    lines = [f"**{total_label}: {grand_total:,.{decimals}f}{suffix}**"]
    lines.append(f"↳ Flat: {flat_total:,.{decimals}f}{suffix}")
    if bonus_total:
        lines.append(f"↳ Bonus: {bonus_total:,.{decimals}f}{suffix}")
    if combat_start_delta:
        lines.append(f"↳ Combat Start: {combat_start_delta:,.{decimals}f}{suffix}")

    lines.append(f"**Flat: {flat_total:,.{decimals}f}{suffix}**")
    lines += render_bucket_lines(flat_buckets, suffix=suffix, decimals=decimals)
    lines.append(f"**Bonus: {bonus_total:,.{decimals}f}{suffix}**")
    lines += render_bucket_lines(
        bonus_buckets,
        suffix=suffix,
        decimals=decimals,
        label_overrides={"Bonus": "Other bonus sources"},
    )
    return lines


def categorize_contribution(label: str) -> str:
    """Maps a get_total_*(explain=True) contribution label to a short
    display bucket (Base, Equipment, Stats, Hematurgy, Ascent, Codex,
    Passives, Bonus, Parts, Essences)."""
    low = label.lower()
    for needle, bucket in _CATEGORY_RULES:
        if needle in low:
            return bucket
    return "Bonus"


def group_contributions(
    contributions: list[tuple[str, float]],
) -> dict[str, float]:
    """Sums a get_total_*(explain=True) contributions list into short display
    buckets, in CATEGORY_ORDER. Zero-delta entries are dropped."""
    buckets: dict[str, float] = {}
    for label, delta in contributions:
        if not delta:
            continue
        cat = categorize_contribution(label)
        buckets[cat] = buckets.get(cat, 0) + delta
    return buckets
