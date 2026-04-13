import random
from dataclasses import dataclass

from core.models import Player


@dataclass
class CodexChapter:
    id: int
    name: str
    flavor: str
    signature_key: str
    signature_label: str
    signature_description: str
    level_offset: int  # Monster base level = player_level + ascension + level_offset
    difficulty: int  # 1–5, affects modifier counts and run ordering


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
# Chapter Pool  (15 entries — no two runs will share all 5 chapters)
# ---------------------------------------------------------------------------

CHAPTER_POOL: list[CodexChapter] = [
    CodexChapter(
        id=1,
        name="The Iron Horde",
        flavor="Steel-born warriors march in endless formation.",
        signature_key="weakened",
        signature_label="Weakened",
        signature_description="-30% base ATK",
        level_offset=5,
        difficulty=1,
    ),
    CodexChapter(
        id=2,
        name="Blighted Wastes",
        flavor="Venomous creatures swarm from the rotting earth.",
        signature_key="decaying",
        signature_label="Decaying",
        signature_description="-30% max HP",
        level_offset=5,
        difficulty=1,
    ),
    CodexChapter(
        id=3,
        name="The Hollow Court",
        flavor="Nobles who sold their souls leer from crumbling thrones.",
        signature_key="exposed",
        signature_label="Exposed",
        signature_description="Ward is disabled at the start of each combat",
        level_offset=7,
        difficulty=2,
    ),
    CodexChapter(
        id=4,
        name="Unending Hunger",
        flavor="Titanic creatures bloated on ruin and excess.",
        signature_key="depleted",
        signature_label="Depleted",
        signature_description="-40% base DEF",
        level_offset=7,
        difficulty=2,
    ),
    CodexChapter(
        id=5,
        name="Celestial Tribunal",
        flavor="Celestial arbiters pass judgment without mercy.",
        signature_key="humbled",
        signature_label="Humbled",
        signature_description="-20% base ATK and -20% base DEF",
        level_offset=9,
        difficulty=2,
    ),
    CodexChapter(
        id=6,
        name="The Void Rift",
        flavor="Reality tears apart. Shield-breakers pour through the cracks.",
        signature_key="unravelled",
        signature_label="Unravelled",
        signature_description="Ward disabled and -20% base DEF",
        level_offset=9,
        difficulty=3,
    ),
    CodexChapter(
        id=7,
        name="Storm's Eye",
        flavor="Lightning blinds. Thunder deafens. The Mighty rise.",
        signature_key="blinded",
        signature_label="Blinded",
        signature_description="Crit target +40 (critical hits are far harder to land)",
        level_offset=11,
        difficulty=3,
    ),
    CodexChapter(
        id=8,
        name="The Ashen Field",
        flavor="A battlefield scorched clean of all hope.",
        signature_key="scorched",
        signature_label="Scorched",
        signature_description="-30% base DEF and -20% base ATK",
        level_offset=11,
        difficulty=3,
    ),
    CodexChapter(
        id=9,
        name="Midnight Spire",
        flavor="Ancient curses nest in the dark, feeding on vitality.",
        signature_key="cursed",
        signature_label="Cursed",
        signature_description="-40% max HP",
        level_offset=13,
        difficulty=4,
    ),
    CodexChapter(
        id=10,
        name="Crimson Tide",
        flavor="Ascended legions spill across the horizon in an endless wave.",
        signature_key="frenzied",
        signature_label="Frenzied",
        signature_description="-30% base DEF and crit target +30",
        level_offset=13,
        difficulty=4,
    ),
    CodexChapter(
        id=11,
        name="The Abyssal Gate",
        flavor="Something from the abyss gazes back. It is not impressed.",
        signature_key="abyss_taint",
        signature_label="Abyss-Tainted",
        signature_description="-40% base ATK and -40% base DEF",
        level_offset=15,
        difficulty=4,
    ),
    CodexChapter(
        id=12,
        name="Shattered Realm",
        flavor="Laws of reality buckle under impossible weight.",
        signature_key="broken",
        signature_label="Broken",
        signature_description="Ward disabled and -30% base DEF",
        level_offset=15,
        difficulty=4,
    ),
    CodexChapter(
        id=13,
        name="The Final Theorem",
        flavor="Numbers made flesh. Perfection made enemy.",
        signature_key="absolute_zero",
        signature_label="Absolute Zero",
        signature_description="-50% base ATK and crit target +40",
        level_offset=17,
        difficulty=5,
    ),
    CodexChapter(
        id=14,
        name="Apex Convergence",
        flavor="Every threat converges into one merciless point.",
        signature_key="convergence",
        signature_label="Convergence",
        signature_description="-30% base ATK, -30% base DEF, ward disabled",
        level_offset=20,
        difficulty=5,
    ),
    CodexChapter(
        id=15,
        name="The Eternal Archive",
        flavor="The archive catalogues your failures. You are just another entry.",
        signature_key="erased",
        signature_label="Erased",
        signature_description="-50% base ATK and -50% base DEF",
        level_offset=22,
        difficulty=5,
    ),
]


# ---------------------------------------------------------------------------
# Boon Pool
# Each entry: (type, label_template, description_template, weight, value_range)
# value_range is (min, max) float, or None for flag boons.
# ---------------------------------------------------------------------------

_BOON_DEFINITIONS = [
    # type              label template              description template                                   weight  range
    (
        "atk_boost",
        "+{v:.0f}% ATK",
        "+{v:.0f}% base ATK for remaining waves",
        25,
        (12.0, 22.0),
    ),
    (
        "def_boost",
        "+{v:.0f}% DEF",
        "+{v:.0f}% base DEF for remaining waves",
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
        "-{v:.0f} Crit Target",
        "Crit target reduced by {v:.0f} for remaining waves",
        20,
        (3.0, 8.0),
    ),
    (
        "fdr_boost",
        "+{v:.0f} FDR",
        "+{v:.0f} flat damage reduction per wave",
        15,
        (2.0, 8.0),
    ),
    (
        "ward_boost",
        "+{v:.0f}% Ward",
        "+{v:.0f}% of max HP added as ward per wave",
        15,
        (8.0, 18.0),
    ),
    (
        "rarity_boost",
        "+{v:.0f}% Rarity",
        "+{v:.0f}% base rarity for remaining waves",
        12,
        (15.0, 35.0),
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
]


def select_run_chapters(count: int = 5) -> list[CodexChapter]:
    """
    Sample `count` unique chapters from the pool and sort them by ascending difficulty
    (with a random tiebreaker so same-difficulty chapters vary in order).
    """
    selected = random.sample(CHAPTER_POOL, min(count, len(CHAPTER_POOL)))
    selected.sort(key=lambda c: (c.difficulty, random.random()))
    return selected


_RARITY_BOOST_DOWNSIDES = [
    ("atk_penalty", lambda v: round(v * 0.5), "-{:.0f}% ATK per wave"),
    ("def_penalty", lambda v: round(v * 0.5), "-{:.0f}% DEF per wave"),
    ("crit_penalty", lambda v: round(v * 0.7), "+{:.0f} Crit Target per wave"),
]

_FRAGMENT_BOOST_DOWNSIDES = [
    ("hp_penalty", lambda v: round(v * 0.35), "-{:.0f}% Max HP (permanent)"),
    ("atk_def_penalty", lambda v: round(v * 0.25), "-{:.0f}% ATK & DEF (permanent)"),
    ("crit_penalty", lambda v: round(v * 0.5), "+{:.0f} Crit Target (permanent)"),
]


def _roll_downside(boon_type: str, boon_value: float) -> tuple[str | None, float, str]:
    """Returns (downside_type, downside_value, downside_label) for boons that carry a cost."""
    if boon_type == "rarity_boost":
        dt, scale_fn, label_tmpl = random.choice(_RARITY_BOOST_DOWNSIDES)
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


def snapshot_clean_stats(player: Player) -> dict:
    """
    Captures the player's mutable base stats before any wave modifiers are applied.
    Store this once at run start (and update max_hp if max_hp_boost boon is taken).
    """
    return {
        "attack": player.base_attack,
        "defence": player.base_defence,
        "crit_target": player.base_crit_chance_target,
        "max_hp": player.max_hp,
        "rarity": player.base_rarity,
    }


def restore_clean_stats(player: Player, clean_stats: dict) -> None:
    """
    Resets base stats to the clean snapshot taken at run start.
    Called only at chapter boundaries (wave_num == 1) so that the outgoing
    chapter's signature modifier doesn't compound into the next chapter.
    Stats and HP are otherwise permanent throughout the run.
    """
    player.base_attack = clean_stats["attack"]
    player.base_defence = clean_stats["defence"]
    player.base_crit_chance_target = clean_stats["crit_target"]
    player.max_hp = clean_stats["max_hp"]
    player.base_rarity = clean_stats["rarity"]
    player.boon_fdr = 0  # re-applied immediately by apply_per_wave_boons


# ---------------------------------------------------------------------------
# Signature Modifier Application
# ---------------------------------------------------------------------------


def apply_signature_modifier(player: Player, chapter: CodexChapter) -> None:
    """
    Applies the chapter's signature modifier to the player.
    Must be called AFTER restore_clean_stats and BEFORE apply_per_wave_boons.
    HP-capping is enforced so current_hp never exceeds a reduced max_hp.
    """
    key = chapter.signature_key
    # Helper: only zero ward if Aphrodite helmet corrupted essence is not active
    _ward_immune = player.get_helmet_corrupted_essence() == "aphrodite"

    if key == "weakened":
        player.base_attack = int(player.base_attack * 0.70)

    elif key == "decaying":
        player.max_hp = int(player.max_hp * 0.70)
        player.current_hp = min(player.current_hp, player.max_hp)

    elif key == "exposed":
        if not _ward_immune:
            player.combat_ward = 0

    elif key == "depleted":
        player.base_defence = int(player.base_defence * 0.60)

    elif key == "humbled":
        player.base_attack = int(player.base_attack * 0.80)
        player.base_defence = int(player.base_defence * 0.80)

    elif key == "unravelled":
        if not _ward_immune:
            player.combat_ward = 0
        player.base_defence = int(player.base_defence * 0.80)

    elif key == "blinded":
        player.base_crit_chance_target += 40

    elif key == "scorched":
        player.base_defence = int(player.base_defence * 0.70)
        player.base_attack = int(player.base_attack * 0.80)

    elif key == "cursed":
        player.max_hp = int(player.max_hp * 0.60)
        player.current_hp = min(player.current_hp, player.max_hp)

    elif key == "frenzied":
        player.base_defence = int(player.base_defence * 0.70)
        player.base_crit_chance_target += 30

    elif key == "abyss_taint":
        player.base_attack = int(player.base_attack * 0.60)
        player.base_defence = int(player.base_defence * 0.60)

    elif key == "broken":
        if not _ward_immune:
            player.combat_ward = 0
        player.base_defence = int(player.base_defence * 0.70)

    elif key == "absolute_zero":
        player.base_attack = int(player.base_attack * 0.50)
        player.base_crit_chance_target += 40

    elif key == "convergence":
        player.base_attack = int(player.base_attack * 0.70)
        player.base_defence = int(player.base_defence * 0.70)
        if not _ward_immune:
            player.combat_ward = 0

    elif key == "erased":
        player.base_attack = int(player.base_attack * 0.50)
        player.base_defence = int(player.base_defence * 0.50)


# ---------------------------------------------------------------------------
# Per-Wave Boon Application
# ---------------------------------------------------------------------------


def apply_per_wave_boons(player: Player, active_boons: list[CodexBoon]) -> None:
    """
    Re-applies accumulated per-wave stat boons after restore + signature.
    Must be called AFTER apply_signature_modifier so boons layer on top.
    """
    for boon in active_boons:
        t, v = boon.type, boon.value
        if t == "atk_boost":
            player.base_attack = int(player.base_attack * (1 + v / 100))
        elif t == "def_boost":
            player.base_defence = int(player.base_defence * (1 + v / 100))
        elif t == "crit_boost":
            player.base_crit_chance_target = max(
                1, player.base_crit_chance_target - int(v)
            )
        elif t == "ward_boost":
            player.combat_ward += int(player.max_hp * (v / 100))
        elif t == "rarity_boost":
            player.base_rarity = int(player.base_rarity * (1 + v / 100))
            dt, dv = boon.downside_type, boon.downside_value
            if dt == "atk_penalty":
                player.base_attack = int(player.base_attack * (1 - dv / 100))
            elif dt == "def_penalty":
                player.base_defence = int(player.base_defence * (1 - dv / 100))
            elif dt == "crit_penalty":
                player.base_crit_chance_target += int(dv)
        elif t == "fdr_boost":
            player.boon_fdr += int(v)


def apply_respite_boon(
    player: Player,
    boon: CodexBoon,
    active_boons: list[CodexBoon],
    clean_stats: dict,
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
        healed = int(player.max_hp * (v / 100))
        player.current_hp = min(player.max_hp, player.current_hp + healed)
        return f"Restored **{healed:,} HP** ({player.current_hp:,}/{player.max_hp:,})"

    # --- One-shot: permanent run max HP boost ---
    if t == "max_hp_boost":
        old_max = player.max_hp
        new_max = int(player.max_hp * (1 + v / 100))
        gained = new_max - old_max
        player.max_hp = new_max
        # Persist through clean-stat resets for the rest of the run
        clean_stats["max_hp"] = new_max
        return f"Max HP increased by **{gained:,}** → **{player.max_hp:,}**"

    # --- One-shot: fragment multiplier (with permanent downside applied to clean_stats) ---
    if t == "fragment_boost":
        run_state["fragment_multiplier"] = run_state.get("fragment_multiplier", 1.0) * (
            1 + v / 100
        )
        dt, dv = boon.downside_type, boon.downside_value
        if dt == "hp_penalty":
            new_max = int(clean_stats["max_hp"] * (1 - dv / 100))
            clean_stats["max_hp"] = new_max
            player.max_hp = new_max
            player.current_hp = min(player.current_hp, new_max)
        elif dt == "atk_def_penalty":
            clean_stats["attack"] = int(clean_stats["attack"] * (1 - dv / 100))
            clean_stats["defence"] = int(clean_stats["defence"] * (1 - dv / 100))
        elif dt == "crit_penalty":
            clean_stats["crit_target"] = clean_stats["crit_target"] + int(dv)
        suffix = f" (Cost: {boon.downside_label})" if boon.downside_label else ""
        return f"Fragment gain boosted by **+{v:.0f}%** this run{suffix}"

    # --- One-shot: nullify next chapter signature ---
    if t == "sig_nullify":
        run_state["sig_nullify_next"] = True
        return "The next chapter's signature modifier will be **nullified**"

    # --- Per-wave boon: store and apply immediately for current wave ---
    active_boons.append(boon)
    apply_per_wave_boons(player, [boon])
    return f"**{boon.label}** active for all remaining waves"


# ---------------------------------------------------------------------------
# Wave Scaling
# ---------------------------------------------------------------------------

# Per-wave level step from chapter base (index 0 = wave 1, index 6 = wave 7 boss)
_WAVE_LEVEL_STEPS = [0, 1, 2, 3, 4, 5, 8]

# Base normal modifier count per wave
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
    boss = 0
    if wave_num == 7:
        boss = 2 if chapter_difficulty >= 4 else 1
    return normal, boss


def calculate_run_fragments(
    chapters_cleared: int,
    is_perfect: bool,
    fragment_multiplier: float,
) -> int:
    """
    Base fragment reward scales with how many chapters were cleared.
    Perfect run (all 5 cleared with no deaths mid-run) gives a 50% bonus.
    fragment_multiplier comes from accumulated fragment_boost boons.
    """
    base = chapters_cleared * 6  # 6 per chapter base
    if is_perfect and chapters_cleared == 5:
        base = int(base * 1.5)
    return max(1, int(base * fragment_multiplier))
