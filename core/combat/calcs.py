import random

# ---------------------------------------------------------------------------
# Tiered Weapon Passive Table
#
# Maps a family name to ([tier_1_name, ..., tier_5_name], per-tier scale).
# The scale meaning is family-specific (see engine.py for usage).
# Checked slots: weapon main (passive), pinnacle, utmost.
# ---------------------------------------------------------------------------

TIERED_WEAPON_PASSIVES: dict[str, tuple[list[str], float]] = {
    'accuracy': (["accurate",    "precise",       "sharpshooter", "deadeye",       "bullseye"],     4.0),
    'crit':     (["piercing",    "keen",          "incisive",     "puncturing",    "penetrating"],   5.0),
    'burn':     (["burning",     "flaming",       "scorching",    "incinerating",  "carbonising"],   0.08),
    'spark':    (["sparking",    "shocking",      "discharging",  "electrocuting", "vapourising"],   0.08),
    'echo':     (["echo",        "echoo",         "echooo",       "echoooo",       "echoes"],        0.10),
    'poison':   (["poisonous",   "noxious",       "venomous",     "toxic",         "lethal"],        0.08),
    'cull':     (["strengthened","forceful",      "overwhelming", "devastating",   "catastrophic"],  0.08),
    'polished': (["polished",    "honed",         "gleaming",     "tempered",      "flaring"],       0.08),
    'sturdy':   (["sturdy",      "reinforced",    "thickened",    "impregnable",   "impenetrable"],  0.08),
}


def get_weapon_tier(player, key: str) -> tuple[int, str]:
    """
    Returns (tier_index 0–4, passive_name) for the highest active tier of the
    named weapon passive family, or (-1, '') if the player has none.
    Checks weapon main, pinnacle, and utmost slots.
    """
    names, _ = TIERED_WEAPON_PASSIVES[key]
    active = [
        player.get_weapon_passive(),
        player.get_weapon_pinnacle(),
        player.get_weapon_utmost(),
    ]
    hits = [(names.index(p), p) for p in active if p in names]
    return max(hits, key=lambda x: x[0]) if hits else (-1, '')


def get_player_passive_indices(player, target_passives: list[str]) -> list[int]:
    """
    Returns indices into target_passives for each weapon-slot passive the player has.
    Checks weapon main, pinnacle, and utmost slots.
    Retained for dummy_engine.py compatibility.
    """
    active = [
        player.get_weapon_passive(),
        player.get_weapon_pinnacle(),
        player.get_weapon_utmost(),
    ]
    return [target_passives.index(p) for p in active if p in target_passives]


# ---------------------------------------------------------------------------
# Core Combat Calculations
# ---------------------------------------------------------------------------

_HIT_BASE        = 0.70   # hit chance at equal stats
_HIT_SENSITIVITY = 0.30   # hit chance shift per 100% stat difference
_HIT_MIN         = 0.20
_HIT_MAX         = 0.95

_MON_HIT_BASE        = 0.50
_MON_HIT_SENSITIVITY = 0.30
_MON_HIT_MIN         = 0.15
_MON_HIT_MAX         = 0.80

_DMG_VARIANCE = (0.85, 1.15)


def calculate_hit_chance(player, monster) -> float:
    """Player hit chance based on attack-vs-defence ratio. Equal stats → 70%."""
    m_def = monster.defence
    if m_def <= 0:
        base = _HIT_MAX
    else:
        pct_diff = (player.get_total_attack() - m_def) / m_def
        base = min(max(_HIT_BASE + pct_diff * _HIT_SENSITIVITY, _HIT_MIN), _HIT_MAX)

    if player.ascension_unlocks:
        hit_bonus = player.get_ascension_bonuses()["hit"]
        if hit_bonus:
            base = min(_HIT_MAX, base + hit_bonus * 0.01)

    return base


def calculate_monster_hit_chance(player, monster) -> float:
    """Monster hit chance based on attack-vs-defence ratio. Equal stats → 50%."""
    m_atk = monster.attack
    if m_atk <= 0:
        return _MON_HIT_MIN
    pct_diff = (m_atk - player.get_total_defence()) / m_atk
    return min(max(_MON_HIT_BASE + pct_diff * _MON_HIT_SENSITIVITY, _MON_HIT_MIN), _MON_HIT_MAX)


def calculate_damage_taken(player, monster) -> int:
    """Raw monster damage before PDR/FDR. Reaches 0 when defence ≥ attack."""
    m_atk = monster.attack
    if m_atk <= 0:
        return 0
    raw = m_atk * max(0.0, 1.0 - player.get_total_defence() / m_atk)
    if "Strengthened" in monster.modifiers:
        raw *= 1.5
    return max(0, int(raw * random.uniform(*_DMG_VARIANCE)))


# ---------------------------------------------------------------------------
# Legacy wrappers — retained for dummy_engine.py compatibility
# ---------------------------------------------------------------------------

def check_for_echo_bonus(player, actual_hit: int) -> tuple[int, bool, int]:
    """Echo weapon passive: bonus damage on hit that mirrors the strike."""
    idx, _ = get_weapon_tier(player, 'echo')
    if idx < 0:
        return actual_hit, False, 0
    echo_damage = int(actual_hit * (idx + 1) * 0.10)
    return actual_hit + echo_damage, True, echo_damage


def check_for_poison_bonus(player, attack_multiplier: float) -> int:
    """Poison weapon passive: guaranteed damage on miss."""
    idx, _ = get_weapon_tier(player, 'poison')
    if idx < 0:
        return 0
    poison_pct = (idx + 1) * 0.08
    return int(random.randint(1, int(player.get_total_attack() * poison_pct)) * attack_multiplier)
