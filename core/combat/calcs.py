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

def calculate_hit_chance(player, monster):
    """Calculate the chance to hit based on the player's attack and monster's defence."""
    difference = player.get_total_attack() - monster.defence
    if player.get_total_attack() <= 10:
        return 0.9
    elif player.get_total_attack() <= 20:
        return 0.8
    elif player.get_total_attack() <= 30:
        return 0.7
    return min(max(0.6 + (difference / 100), 0.6), 0.8)


def calculate_monster_hit_chance(player, monster):
    """Calculate the player's chance to be hit based on stats."""
    difference = monster.attack - player.get_total_defence()
    if monster.attack <= 5:
        return 0.2
    elif monster.attack <= 10:
        return 0.3
    elif monster.attack <= 15:
        return 0.4
    return min(max(0.5 + (difference / 100), 0.3), 0.8)


def calculate_damage_taken(player, monster):
    """Calculate damage taken based on monster's attack and player's defense."""
    difference = monster.attack - player.get_total_defence()

    if "Strengthened" in monster.modifiers:
        damage_ranges = [(1, 5), (1, 6), (1, 9)]
    else:
        damage_ranges = [(1, 2), (1, 3), (1, 6)]

    if monster.attack <= 3:
        damage = random.randint(*damage_ranges[0])
        difference = 0
    elif monster.attack <= 20:
        damage = random.randint(*damage_ranges[1])
        difference = 0
    else:
        damage = random.randint(*damage_ranges[2]) + int(monster.level // 10)

    if difference > 0:
        damage += int(sum(random.randint(1, 3) for _ in range(int(difference / 10))))

    return max(0, random.randint(1, damage))


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
