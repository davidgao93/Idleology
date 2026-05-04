import random

# ---------------------------------------------------------------------------
# Weapon Passive Family Registry
#
# Passives are stored as 'family_tier' strings, e.g. 'burning_3' (1-indexed).
# Per-tier scale values (used by engine and player_turn):
#   burning, poison, debilitate, shocking, sturdy, cull  → 0.08 per tier
#   deadeye  → 4 flat hit chance per tier
#   piercing → 5 crit chance per tier
#   echo     → 0.10 per tier
#   arcane   → 25 ward on hit per tier
# Checked slots: weapon main passive, pinnacle, utmost.
# ---------------------------------------------------------------------------

WEAPON_PASSIVE_FAMILIES: frozenset[str] = frozenset({
    "burning",    # Atk boost
    "poison",     # Miss damage
    "debilitate", # Def shred (formerly polished)
    "shocking",   # Min damage floor
    "sturdy",     # Def boost
    "piercing",   # Crit chance
    "cull",       # Culling threshold
    "deadeye",    # Hit chance
    "echo",       # Extra hit damage
    "arcane",     # Ward on hit
})

# Per-tier scale constants — import these in engine/player_turn instead of hardcoding.
PASSIVE_SCALE: dict[str, float] = {
    "burning": 0.08,
    "poison": 0.08,
    "debilitate": 0.08,
    "shocking": 0.08,
    "sturdy": 0.08,
    "cull": 0.08,
    "deadeye": 4.0,
    "piercing": 5.0,
    "echo": 0.10,
    "arcane": 25.0,
}


_PASSIVE_ROMAN = ("I", "II", "III", "IV", "V")


def fmt_weapon_passive(passive_str: str) -> str:
    """Formats 'burning_3' → 'Burning III' for display in combat logs."""
    if not passive_str or passive_str == "none":
        return passive_str
    if "_" in passive_str:
        family, _, tier_str = passive_str.rpartition("_")
        try:
            return f"{family.title()} {_PASSIVE_ROMAN[int(tier_str) - 1]}"
        except (ValueError, IndexError):
            pass
    return passive_str.title()


def get_weapon_tier(player, key: str) -> tuple[int, str]:
    """
    Returns (tier_index 0–4, passive_string) for the highest active tier of the
    named weapon passive family, or (-1, '') if the player has none.
    Checks weapon main, pinnacle, and utmost slots.
    Passives are stored as 'family_tier' strings (e.g. 'burning_3').
    """
    prefix = f"{key}_"
    best: tuple[int, str] = (-1, "")
    for passive_str in (
        player.get_weapon_passive(),
        player.get_weapon_pinnacle(),
        player.get_weapon_utmost(),
    ):
        if passive_str and passive_str.startswith(prefix):
            try:
                tier_idx = int(passive_str[len(prefix):]) - 1  # 1-indexed → 0-indexed
                if tier_idx > best[0]:
                    best = (tier_idx, passive_str)
            except ValueError:
                continue
    return best


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

_HIT_BASE = 0.60  # hit chance at equal stats
_HIT_SENSITIVITY = 0.35  # hit chance shift per 100% stat difference
_HIT_MIN = 0.20
_HIT_MAX = 0.95

_MON_HIT_BASE = 0.50
_MON_HIT_SENSITIVITY = 0.30
_MON_HIT_MIN = 0.15
_MON_HIT_MAX = 0.80

_DMG_VARIANCE = (0.85, 1.15)


def calculate_hit_chance(player, monster) -> float:
    """Player hit chance based on attack-vs-defence ratio.
    Base is sourced from the weapon's drop template (default 60% if no weapon)."""
    hit_base = player.equipped_weapon.hit_chance if player.equipped_weapon else _HIT_BASE
    m_def = monster.defence
    if m_def <= 0:
        base = _HIT_MAX
    else:
        pct_diff = (player.get_total_attack() - m_def) / m_def
        base = min(max(hit_base + pct_diff * _HIT_SENSITIVITY, _HIT_MIN), _HIT_MAX)

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
    return min(
        max(_MON_HIT_BASE + pct_diff * _MON_HIT_SENSITIVITY, _MON_HIT_MIN), _MON_HIT_MAX
    )


def calculate_damage_taken(player, monster) -> int:
    """Raw monster damage before PDR/FDR.
    Guaranteed base from monster level, amplified/dampened by stat surplus."""
    p_def = max(player.get_total_defence(), 1)
    base_raw = 5 + monster.level * 1.5
    surplus = (monster.attack - p_def) / p_def
    surplus = max(-0.95, surplus)
    raw = base_raw * (1.0 + surplus)
    return max(1, int(raw * random.uniform(*_DMG_VARIANCE)))


def calculate_crit_chance(player) -> float:
    """Returns the effective crit chance (0–100) accounting for weapon tier and infernal."""
    idx, _ = get_weapon_tier(player, "piercing")
    chance = player.get_current_crit_chance() + ((idx + 1) * 5 if idx >= 0 else 0)
    if player.get_weapon_infernal() == "voracious" and player.voracious_stacks > 0:
        chance += player.voracious_stacks * 5
    if player.active_partner:
        for key, lvl in player.active_partner.combat_skills:
            if key == "co_crit_rate":
                chance += lvl
    return chance


# ---------------------------------------------------------------------------
# Legacy wrappers — retained for dummy_engine.py compatibility
# ---------------------------------------------------------------------------


def check_for_echo_bonus(player, actual_hit: int) -> tuple[int, bool, int]:
    """Echo weapon passive: bonus damage on hit that mirrors the strike."""
    idx, _ = get_weapon_tier(player, "echo")
    if idx < 0:
        return actual_hit, False, 0
    echo_damage = int(actual_hit * (idx + 1) * 0.10)
    return actual_hit + echo_damage, True, echo_damage


def check_for_poison_bonus(player, attack_multiplier: float) -> int:
    """Poison weapon passive: guaranteed damage on miss."""
    idx, _ = get_weapon_tier(player, "poison")
    if idx < 0:
        return 0
    poison_pct = (idx + 1) * 0.08
    return int(
        random.randint(1, int(player.get_total_attack() * poison_pct))
        * attack_multiplier
    )
