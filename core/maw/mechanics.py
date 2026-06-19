"""
core/maw/mechanics.py — Maw of Infinity cycle logic and reward calculation.

Cycle cadence: opens every Sunday 12:00 UTC, active for 5.5 days (ends
Saturday 00:00 UTC), then a collection window until the next Sunday 12:00.

Fighting: players initiate 10-turn encounters manually. Up to 5 fights per
cycle, with a 20-hour cooldown between fights. Each fight runs a real
process_player_turn simulation against the Maw (attack=1, def=1, 99k HP
that never dies).

Rewards (manual collection during the collection window):
  - Everyone: 3 base curios + proportional pool share + 10 guild tickets
  - Pool size: 10 + 11 + 12 + ... per participant (grows with participation)
  - Top 3 by damage: also receive a Curio Puzzle Box
"""

from datetime import datetime, timedelta, timezone

FIGHT_COOLDOWN_HOURS = 20
MAX_FIGHTS_PER_CYCLE = 5
MAW_TURNS = 10

BASE_CURIOS = 3
BASE_GUILD_TICKETS = 10


# ---------------------------------------------------------------------------
# Cycle timing helpers
# ---------------------------------------------------------------------------


def get_current_cycle_id(now: datetime) -> int:
    """Returns the Unix timestamp of the most recent Sunday 12:00 UTC cycle start."""
    now_utc = (
        now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    )
    days_since_sunday = (now_utc.weekday() + 1) % 7
    candidate = now_utc.replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(
        days=days_since_sunday
    )
    if now_utc < candidate:
        candidate -= timedelta(days=7)
    return int(candidate.timestamp())


def get_cycle_end_ts(cycle_id: int) -> int:
    """Sunday 12:00 UTC + 5 days 12 hours = Saturday 00:00 UTC."""
    return cycle_id + int(timedelta(days=5, hours=12).total_seconds())


def get_next_cycle_id(cycle_id: int) -> int:
    return cycle_id + int(timedelta(days=7).total_seconds())


def get_previous_cycle_id(cycle_id: int) -> int:
    return cycle_id - int(timedelta(days=7).total_seconds())


def is_cycle_active(cycle_id: int, now_ts: int) -> bool:
    return cycle_id <= now_ts < get_cycle_end_ts(cycle_id)


def is_collection_window(cycle_id: int, now_ts: int) -> bool:
    return get_cycle_end_ts(cycle_id) <= now_ts < get_next_cycle_id(cycle_id)


# ---------------------------------------------------------------------------
# Fight availability
# ---------------------------------------------------------------------------


def fight_available(
    last_fight_ts: int | None, fights_this_cycle: int, now_ts: int
) -> bool:
    """True if the player can start a new fight right now."""
    if fights_this_cycle >= MAX_FIGHTS_PER_CYCLE:
        return False
    if not last_fight_ts:  # 0 or None → never fought
        return True
    return (now_ts - last_fight_ts) >= FIGHT_COOLDOWN_HOURS * 3600


def fight_remaining_seconds(last_fight_ts: int, now_ts: int) -> int:
    """Seconds until the fight cooldown expires. Returns 0 if already ready."""
    elapsed = now_ts - last_fight_ts
    remaining = FIGHT_COOLDOWN_HOURS * 3600 - elapsed
    return max(0, remaining)


# ---------------------------------------------------------------------------
# Reward calculation
# ---------------------------------------------------------------------------


def calculate_pool_size(participant_count: int) -> int:
    """Pool grows by 1 curio per additional participant: 10 + 11 + 12 + …"""
    n = participant_count
    return n * 10 + n * (n - 1) // 2


# ---------------------------------------------------------------------------
# Weekly weakness
# ---------------------------------------------------------------------------

# 4 weaknesses cycling through the year in ~13-week blocks.
# week_of_year (0-indexed) % 4 selects the active weakness.
_WEEKLY_WEAKNESSES = [
    {
        "key": "hit_damage",
        "name": "Temporal Fracture",
        "description": "Hit damage dealt to the Maw is amplified by **+50%**.",
        "emoji": "⚔️",
    },
    {
        "key": "crit_damage",
        "name": "Exposed Core",
        "description": "Critical hit damage dealt to the Maw is amplified by **+50%**.",
        "emoji": "💥",
    },
    {
        "key": "miss_damage",
        "name": "Phantom Strikes",
        "description": "Misses still deal **50% of normal hit damage** to the Maw.",
        "emoji": "👻",
    },
    {
        "key": "ward_to_damage",
        "name": "Void Hunger",
        "description": "Ward absorbed this fight converts to **bonus damage** dealt to the Maw.",
        "emoji": "🔮",
    },
]


def get_weekly_weakness(now: datetime | None = None) -> dict:
    """Returns the active weakness dict for the current week-of-year."""
    if now is None:
        now = datetime.now(tz=timezone.utc)
    now_utc = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    week_of_year = int(now_utc.strftime("%W"))  # 0-indexed week, Mon start
    return _WEEKLY_WEAKNESSES[week_of_year % len(_WEEKLY_WEAKNESSES)]


def calculate_rewards(
    player_damage: int,
    total_damage: int,
    participant_count: int,
    is_top3: bool,
) -> tuple[int, int, bool]:
    """Returns (curios, guild_tickets, puzzle_box).

    curios = BASE_CURIOS + proportional share of the cycle pool.
    guild_tickets = BASE_GUILD_TICKETS (flat, everyone).
    puzzle_box = True only for top-3 contributors.
    """
    pool = calculate_pool_size(participant_count)
    pct = player_damage / total_damage if total_damage > 0 else 0.0
    pool_share = round(pool * pct)
    curios = BASE_CURIOS + pool_share
    return curios, BASE_GUILD_TICKETS, is_top3


def contribution_pct(player_damage: int, total_damage: int) -> float:
    """Player's percentage share of all damage dealt this cycle."""
    if total_damage <= 0:
        return 0.0
    return player_damage / total_damage * 100
