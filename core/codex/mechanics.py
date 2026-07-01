import random
from dataclasses import dataclass, field

from core.models import Player


@dataclass
class CodexChapter:
    id: int  # 1–5 (chapter position in the run)
    name: str  # Generated name e.g. "Savage Spire of Blindness"
    flavor: str
    signature_label: str  # Display name (same as name for generated chapters)
    signature_description: str  # e.g. "Enemies: +30% DMG | -40% Crit Chance"
    level_offset: int  # Monster base level = player_level + ascension + level_offset
    difficulty: int  # 1–5, affects modifier counts and wave scaling
    player_mods: list[tuple[str, float]] = field(default_factory=list)
    monster_mods: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class CodexBoon:
    type: str
    label: str
    description: str
    value: float  # Rolled stat value; 0.0 for flag boons (sig_nullify)
    downside_type: str | None = (
        None  # 'atk_penalty' | 'def_penalty' | 'crit_penalty' | 'hp_penalty' | 'atk_def_penalty'
    )
    downside_value: float = 0.0
    downside_label: str = ""


# ---------------------------------------------------------------------------
# Chapter generation word pools
# ---------------------------------------------------------------------------

_NOUNS = [
    "Spire",
    "Void",
    "Gate",
    "Citadel",
    "Archive",
    "Throne",
    "Bastion",
    "Summit",
    "Maw",
    "Sanctum",
    "Rift",
    "Forge",
    "Nexus",
    "Pinnacle",
    "Abyss",
]

# Player debuff types: (type, suffix_word, (diff1_val, diff2_val, diff3_val, diff4_val, diff5_val))
# None values table means effect is binary (ward_disable)
_PLAYER_DEBUFFS: list[tuple[str, str, tuple | None]] = [
    ("atk_pct", "Weakness", (0.20, 0.25, 0.30, 0.35, 0.40)),
    ("def_pct", "Ruin", (0.20, 0.25, 0.30, 0.35, 0.40)),
    ("max_hp_pct", "Decay", (0.15, 0.20, 0.25, 0.30, 0.40)),
    ("ward_disable", "Corruption", None),
    ("crit_pct", "Blindness", (20.0, 25.0, 30.0, 35.0, 40.0)),
    ("hit_flat", "Haze", (8.0, 10.0, 12.0, 14.0, 18.0)),
    ("crit_dmg_pct", "Dullness", (0.20, 0.25, 0.30, 0.35, 0.40)),
    ("pdr_pct", "the Flayed", (0.20, 0.25, 0.30, 0.35, 0.40)),
    ("ward_gen_pct", "the Fractured", (0.25, 0.30, 0.40, 0.50, 0.60)),
    ("hp_entry_pct", "the Wounded", (0.20, 0.25, 0.30, 0.35, 0.40)),
]

# Ward disable only available at difficulty 3+
_WARD_DISABLE_MIN_DIFF = 3

# Monster buff types: (modifier_name, prefix_word, (diff1_tier, diff2_tier, diff3_tier, diff4_tier, diff5_tier))
_MONSTER_BUFFS: list[tuple[str, str, tuple]] = [
    ("Savage", "Savage", (1, 2, 3, 3, 4)),
    ("Ironclad", "Ironclad", (1, 2, 3, 3, 4)),
    ("Lethal", "Lethal", (1, 2, 3, 3, 4)),
    ("Fortified", "Fortified", (1, 2, 3, 3, 4)),
    ("Titanic", "Titanic", (1, 2, 3, 3, 4)),
    ("Veiled", "Veiled", (1, 2, 3, 3, 4)),
    ("Vampiric", "Vampiric", (1, 2, 3, 3, 4)),
    ("Enraged", "Enraged", (1, 2, 3, 3, 4)),
]

# Per-position modifier budget: (min_total, max_total, max_player, max_monster)
_MOD_BUDGET = [
    (1, 2, 2, 0),  # position 1: intro — player debuffs only
    (1, 2, 2, 1),  # position 2: light mix
    (2, 3, 2, 1),  # position 3: pressured
    (2, 3, 2, 2),  # position 4: heavy
    (2, 4, 2, 2),  # position 5: peak difficulty
]

_DIFFICULTIES = [1, 2, 3, 4, 5]
_LEVEL_OFFSETS = [5, 7, 10, 14, 18]


# ---------------------------------------------------------------------------
# Description helpers
# ---------------------------------------------------------------------------


def _desc_player_mod(mod_type: str, value: float) -> str:
    if mod_type == "atk_pct":
        return f"-{int(value * 100)}% ATK"
    if mod_type == "def_pct":
        return f"-{int(value * 100)}% DEF"
    if mod_type == "max_hp_pct":
        return f"-{int(value * 100)}% Max HP"
    if mod_type == "ward_disable":
        return "Ward disabled"
    if mod_type == "crit_pct":
        return f"-{int(value)} crit chance"
    if mod_type == "hit_flat":
        return f"-{int(value)} hit chance"
    if mod_type == "crit_dmg_pct":
        return f"-{int(value * 100)}% crit DMG"
    if mod_type == "pdr_pct":
        return f"-{int(value * 100)}% PDR"
    if mod_type == "ward_gen_pct":
        return f"-{int(value * 100)}% ward gen"
    if mod_type == "hp_entry_pct":
        return f"Enter each fight at {int((1 - value) * 100)}% HP"
    # Fix 7: unknown/removed modifier types (e.g. potion_count on pre-patch runs)
    # show a neutral description rather than the raw DB key.
    return "Modified run"


def _desc_monster_mod(modifier_name: str, tier: int) -> str:
    from core.combat.mobgen.modifier_data import MODIFIER_DEFINITIONS

    defn = MODIFIER_DEFINITIONS.get(modifier_name)
    if defn and tier > 0 and tier <= len(defn.tiers):
        return f"Enemies: {defn.description(defn.tiers[tier - 1])}"
    return f"Enemies: {modifier_name}"


# ---------------------------------------------------------------------------
# Chapter generation
# ---------------------------------------------------------------------------


def generate_codex_chapter(position: int) -> CodexChapter:
    """Generates a random CodexChapter for the given run position (1–5)."""
    pos_idx = position - 1
    difficulty = _DIFFICULTIES[pos_idx]
    diff_idx = difficulty - 1
    level_offset = _LEVEL_OFFSETS[pos_idx]

    min_mods, max_mods, max_player, max_monster = _MOD_BUDGET[pos_idx]
    total_mods = random.randint(min_mods, max_mods)

    # Guarantee at least 1 player debuff; fill remaining slots with monster buffs up to budget
    n_monster = random.randint(0, min(max_monster, total_mods - 1))
    n_player = min(total_mods - n_monster, max_player)
    n_monster = total_mods - n_player

    # Pick player debuffs (exclude ward_disable below minimum difficulty)
    available_player = [
        entry
        for entry in _PLAYER_DEBUFFS
        if entry[0] != "ward_disable" or difficulty >= _WARD_DISABLE_MIN_DIFF
    ]
    selected_player = random.sample(
        available_player, min(n_player, len(available_player))
    )

    player_mods: list[tuple[str, float]] = []
    suffix_words: list[str] = []
    for mod_type, word, vals in selected_player:
        value = float(vals[diff_idx]) if vals is not None else 1.0
        player_mods.append((mod_type, value))
        suffix_words.append(word)

    # Pick monster buffs
    selected_monster = random.sample(
        _MONSTER_BUFFS, min(n_monster, len(_MONSTER_BUFFS))
    )

    monster_mods: list[tuple[str, int]] = []
    prefix_words: list[str] = []
    for mod_name, word, tiers in selected_monster:
        monster_mods.append((mod_name, tiers[diff_idx]))
        prefix_words.append(word)

    # Build chapter name
    noun = random.choice(_NOUNS)
    if prefix_words and suffix_words:
        suffix_part = " and ".join(suffix_words)
        name = f"{' '.join(prefix_words)} {noun} of {suffix_part}"
    elif prefix_words:
        name = f"{' '.join(prefix_words)} {noun}"
    elif suffix_words:
        name = f"{noun} of {' and '.join(suffix_words)}"
    else:
        name = noun

    # Build signature description
    desc_parts = [_desc_monster_mod(n, t) for n, t in monster_mods]
    desc_parts += [_desc_player_mod(t, v) for t, v in player_mods]
    description = " | ".join(desc_parts)

    return CodexChapter(
        id=position,
        name=name,
        flavor="",
        signature_label=name,
        signature_description=description,
        level_offset=level_offset,
        difficulty=difficulty,
        player_mods=player_mods,
        monster_mods=monster_mods,
    )


# ---------------------------------------------------------------------------
# Boon Pool
# ---------------------------------------------------------------------------

_BOON_DEFINITIONS = [
    # type              label template              description template                                   weight  range
    (
        "atk_boost",
        "+{v:.0f}% ATK",
        "+{v:.0f}% ATK this run",
        25,
        (12.0, 22.0),
    ),
    (
        "def_boost",
        "+{v:.0f}% DEF",
        "+{v:.0f}% DEF this run",
        25,
        (12.0, 22.0),
    ),
    (
        "heal",
        "Restore {v:.0f}% HP",
        "Restores {v:.0f}% of your max HP",
        25,
        (15.0, 35.0),
    ),
    (
        "crit_boost",
        "+{v:.0f}% crit",
        "Crit Chance +{v:.0f} this run",
        20,
        (3.0, 8.0),
    ),
    (
        "fdr_boost",
        "+{v:.0f} FDR",
        "+{v:.0f} FDR this run",
        15,
        (20.0, 80.0),
    ),
    (
        "ward_boost",
        "+{v:.0f}% Ward",
        "+{v:.0f}% Max HP as ward this run",
        15,
        (8.0, 30.0),
    ),
    (
        "page_rate_boost",
        "+{v:.0f}% Page Rate",
        "+{v:.0f}% increased Codex Page drop chance on chapter clear",
        12,
        (15.0, 50.0),
    ),
    (
        "fragment_boost",
        "+{v:.0f}% Fragments",
        "+{v:.0f}% Codex fragment gain this run",
        12,
        (25.0, 60.0),
    ),
    (
        "big_heal",
        "Restore {v:.0f}% HP",
        "Restores {v:.0f}% of your max HP",
        5,
        (40.0, 60.0),
    ),
    (
        "max_hp_boost",
        "+{v:.0f}% Max HP",
        "+{v:.0f}% max HP for the rest of this run",
        5,
        (10.0, 20.0),
    ),
    (
        "sig_nullify",
        "Nullify Signature",
        "Cancels the next chapter's signature modifier",
        2,
        None,
    ),
    (
        "page_drop",
        "Guaranteed Page",
        "Guarantees a Codex Page if this chapter is cleared without dying",
        1,
        None,
    ),
]


def select_run_chapters(count: int = 5) -> list[CodexChapter]:
    """Generates `count` chapters ordered by ascending difficulty (positions 1–count)."""
    return [generate_codex_chapter(p) for p in range(1, count + 1)]


_PAGE_RATE_BOOST_DOWNSIDES = [
    ("atk_penalty", lambda v: round(v * 0.5), "-{:.0f}% ATK"),
    ("def_penalty", lambda v: round(v * 0.5), "-{:.0f}% DEF"),
    ("crit_penalty", lambda v: round(v * 0.7), "-{:.0f}% Crit"),
]

_FRAGMENT_BOOST_DOWNSIDES = [
    ("hp_penalty", lambda v: round(v * 0.35), "-{:.0f}% Max HP"),
    ("atk_def_penalty", lambda v: round(v * 0.25), "-{:.0f}% ATK & DEF"),
    ("crit_penalty", lambda v: round(v * 0.5), "-{:.0f}% Crit Chance"),
]


def _roll_downside(boon_type: str, boon_value: float) -> tuple[str | None, float, str]:
    """Returns (downside_type, downside_value, downside_label) for boons that carry a cost."""
    if boon_type == "page_rate_boost":
        dt, scale_fn, label_tmpl = random.choice(_PAGE_RATE_BOOST_DOWNSIDES)
        dv = float(scale_fn(boon_value))
        return dt, dv, label_tmpl.format(dv)
    if boon_type == "fragment_boost":
        dt, scale_fn, label_tmpl = random.choice(_FRAGMENT_BOOST_DOWNSIDES)
        dv = float(scale_fn(boon_value))
        return dt, dv, label_tmpl.format(dv)
    return None, 0.0, ""


def roll_boons(count: int = 2) -> list[CodexBoon]:
    """
    Weighted-random sample of `count` distinct boon types.
    Returns CodexBoon instances with values already rolled.
    Rarity and fragment boons carry an attached downside penalty.
    """
    pool = list(_BOON_DEFINITIONS)
    chosen = []

    while len(chosen) < count and pool:
        total_weight = sum(d[3] for d in pool)
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        for i, defn in enumerate(pool):
            cumulative += defn[3]
            if r <= cumulative:
                chosen.append(defn)
                pool.pop(i)
                break

    boons = []
    for defn in chosen:
        boon_type, label_tmpl, desc_tmpl, _, value_range = defn
        if value_range is None:
            value = 0.0
            label = label_tmpl
            description = desc_tmpl
        else:
            value = round(random.uniform(*value_range), 1)
            label = label_tmpl.format(v=value)
            description = desc_tmpl.format(v=value)
        downside_type, downside_value, downside_label = _roll_downside(boon_type, value)
        boons.append(
            CodexBoon(
                type=boon_type,
                label=label,
                description=description,
                value=value,
                downside_type=downside_type,
                downside_value=downside_value,
                downside_label=downside_label,
            )
        )
    return boons


# ---------------------------------------------------------------------------
# Clean Stats Snapshot
# ---------------------------------------------------------------------------


def restore_clean_stats(player: Player) -> None:
    """
    Resets per-chapter bonus stats at chapter boundaries so that the outgoing
    chapter's signature and boon effects don't carry into the next chapter.
    run_* fields are permanent for the whole codex run and are NOT touched here.
    """
    player.bonus_rarity = 0
    player.boon_fdr = 0  # re-applied immediately by apply_per_wave_boons
    player.reset_combat_bonus()  # zeros bonus_atk/def/crit/max_hp, multipliers, chapter fields


# ---------------------------------------------------------------------------
# Signature Modifier Application
# ---------------------------------------------------------------------------


def apply_signature_modifier(player: Player, chapter: CodexChapter) -> None:
    """
    Applies all of the chapter's player_mods to the player.
    Must be called AFTER restore_clean_stats and BEFORE apply_per_wave_boons.
    HP reductions go into bonus_max_hp so max_hp stays immutable.
    Ward generation reduction also scales back the current starting ward.

    atk_multiplier/def_multiplier are additive accumulators here (1.0 + net %),
    matching Player.get_total_attack/defence's stat model — every ATK/DEF % source
    across the whole game sums into one pool instead of compounding. Always use
    += / -= on these fields, never *=.
    """
    _ward_immune = player.get_helmet_corrupted_essence() == "aphrodite"

    for mod_type, value in chapter.player_mods:
        if mod_type == "atk_pct":
            player.atk_multiplier -= value

        elif mod_type == "def_pct":
            player.def_multiplier -= value

        elif mod_type == "max_hp_pct":
            player.bonus_max_hp -= int(player.max_hp * value)
            player.current_hp = min(player.current_hp, player.total_max_hp)

        elif mod_type == "ward_disable":
            if not _ward_immune:
                player.combat_ward = 0

        elif mod_type == "crit_pct":
            player.bonus_crit -= int(value)

        elif mod_type == "hit_flat":
            player.chapter_hit_penalty += int(value)

        elif mod_type == "crit_dmg_pct":
            player.chapter_crit_dmg_reduction = min(
                0.80, player.chapter_crit_dmg_reduction + value
            )

        elif mod_type == "pdr_pct":
            player.chapter_pdr_reduction = min(
                0.80, player.chapter_pdr_reduction + value
            )

        elif mod_type == "ward_gen_pct":
            mult = 1 - value
            player.chapter_ward_gen_mult *= mult
            # Also reduce the starting ward that was already computed
            player.combat_ward = int(player.combat_ward * mult)

        elif mod_type == "hp_entry_pct":
            player.chapter_hp_entry_pct = value
            player.current_hp = min(
                player.current_hp, int(player.total_max_hp * (1 - value))
            )


# ---------------------------------------------------------------------------
# Per-Wave Boon Application
# ---------------------------------------------------------------------------


def apply_per_wave_boons(player: Player, active_boons: list[CodexBoon]) -> None:
    """
    Re-applies accumulated per-wave stat boons after restore + signature.
    Must be called AFTER apply_signature_modifier so boons layer on top.

    atk_multiplier/def_multiplier are additive accumulators (see
    apply_signature_modifier) — two +20% ATK boons sum to +40%, not 1.2×1.2=+44%.
    """
    for boon in active_boons:
        t, v = boon.type, boon.value
        if t == "atk_boost":
            player.atk_multiplier += v / 100
        elif t == "def_boost":
            player.def_multiplier += v / 100
        elif t == "crit_boost":
            player.bonus_crit += int(v)
        elif t == "ward_boost":
            player.combat_ward += int(player.total_max_hp * (v / 100))
        elif t == "page_rate_boost":
            # Downside only — the page rate bonus itself is applied at chapter clear time
            dt, dv = boon.downside_type, boon.downside_value
            if dt == "atk_penalty":
                player.atk_multiplier -= dv / 100
            elif dt == "def_penalty":
                player.def_multiplier -= dv / 100
            elif dt == "crit_penalty":
                player.bonus_crit -= int(dv)
        elif t == "fdr_boost":
            player.boon_fdr += int(v)


def apply_respite_boon(
    player: Player,
    boon: CodexBoon,
    active_boons: list[CodexBoon],
    run_state: dict,
) -> str:
    """
    Processes the boon chosen at a respite point.

    One-shot boons (heal, big_heal, max_hp_boost, fragment_boost, sig_nullify) take
    effect immediately and are NOT stored in active_boons.

    Per-wave boons are appended to active_boons so they are re-applied every wave.

    Returns a short result message for the UI.
    """
    t, v = boon.type, boon.value

    # --- One-shot: healing ---
    if t in ("heal", "big_heal"):
        healed = int(player.total_max_hp * (v / 100))
        player.current_hp = min(player.total_max_hp, player.current_hp + healed)
        return f"Restored **{healed:,} HP** ({player.current_hp:,}/{player.total_max_hp:,})"

    # --- One-shot: permanent run max HP boost ---
    if t == "max_hp_boost":
        gained = int(player.total_max_hp * (v / 100))
        player.run_max_hp_bonus += gained
        return f"Max HP increased by **{gained:,}** → **{player.total_max_hp:,}**"

    # --- One-shot: fragment multiplier (with permanent run downside) ---
    if t == "fragment_boost":
        run_state["fragment_multiplier"] = run_state.get("fragment_multiplier", 1.0) * (
            1 + v / 100
        )
        dt, dv = boon.downside_type, boon.downside_value
        if dt == "hp_penalty":
            # Permanent run penalty — scales off current total_max_hp
            penalty = int(player.total_max_hp * (dv / 100))
            player.run_max_hp_bonus -= penalty
            player.current_hp = min(player.current_hp, player.total_max_hp)
        elif dt == "atk_def_penalty":
            # Permanent penalty for this run — subtracted in get_total_attack/defence
            player.run_atk_penalty += int(player.flat_atk * (dv / 100))
            player.run_def_penalty += int(player.flat_def * (dv / 100))
        elif dt == "crit_penalty":
            player.run_crit_penalty += int(dv)
        suffix = f" (Cost: {boon.downside_label})" if boon.downside_label else ""
        return f"Fragment gain boosted by **+{v:.0f}%** this run{suffix}"

    # --- One-shot: nullify next chapter signature ---
    if t == "sig_nullify":
        run_state["sig_nullify_next"] = True
        return "The next chapter's signature modifier will be **nullified**"

    # --- One-shot: guarantee page drop on chapter clear (if no death this chapter) ---
    if t == "page_drop":
        run_state["guaranteed_page_this_chapter"] = True
        return "A Codex Page is **guaranteed** if you clear this chapter without dying"

    # --- Per-wave boon: store and apply immediately for current wave ---
    active_boons.append(boon)
    apply_per_wave_boons(player, [boon])
    return f"**{boon.label}** active for all remaining waves"


# ---------------------------------------------------------------------------
# Wave Scaling
# ---------------------------------------------------------------------------

# Per-wave level step from chapter (index 0 = wave 1, index 6 = wave 7 boss)
_WAVE_LEVEL_STEPS = [5, 5, 8, 8, 10, 10, 20]

# normal modifier count per wave
_WAVE_NORMAL_MODS = [3, 4, 4, 5, 5, 6, 6]


def calculate_wave_monster_level(
    player: Player, chapter: CodexChapter, wave_num: int
) -> int:
    """
    wave_num is 1-indexed (1–7).
    Level = player_level + ascension + chapter_offset + per-wave_step.
    """
    return (
        player.level
        + player.ascension
        + chapter.level_offset
        + _WAVE_LEVEL_STEPS[wave_num - 1]
    )


def get_wave_modifier_counts(wave_num: int, chapter_difficulty: int) -> tuple[int, int]:
    """
    Returns (normal_mods, boss_mods) for the given wave and chapter difficulty.
    Wave 7 always has at least 1 boss mod; difficulty 4–5 chapters give it 2.
    """
    normal = _WAVE_NORMAL_MODS[wave_num - 1] + (chapter_difficulty - 1)
    boss = 1 if chapter_difficulty >= 4 else 1
    if wave_num == 7:
        boss = 3 if chapter_difficulty >= 4 else 1
    return normal, boss


def calculate_run_fragments(
    chapters_cleared: int,
    is_perfect: bool,
    fragment_multiplier: float,
    deaths: int = 0,
) -> int:
    """
    Fragment reward scales with how many chapters were cleared.
    Perfect run (all 5 chapters cleared with no deaths) gives a 50% bonus.
    Each death penalises the final tally by 10%, capped at 50%.
    fragment_multiplier comes from accumulated fragment_boost boons.
    """
    base = chapters_cleared * 6  # 6 per chapter base
    if is_perfect and chapters_cleared == 5:
        base = int(base * 1.5)
    death_penalty = min(0.50, deaths * 0.10)
    return max(1, int(base * fragment_multiplier * (1 - death_penalty)))
