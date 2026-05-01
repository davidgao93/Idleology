import random
from datetime import datetime, timedelta, timezone


DAMAGE_CAP = 500_000
BOOST_DAMAGE = 10_000
BOOST_COOLDOWN_HOURS = 20
HOURLY_DAMAGE_POOL = [100, 1_000, 10_000]
AVG_HOURLY_DAMAGE = 3_700  # used for fake global calculation


def get_current_cycle_id(now: datetime) -> int:
    """Returns the Unix timestamp (int) of the most recent Sunday 12:00 UTC cycle start."""
    now_utc = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    days_since_sunday = (now_utc.weekday() + 1) % 7
    candidate = now_utc.replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=days_since_sunday)
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


def roll_hourly_damage(hours: int) -> int:
    return sum(random.choice(HOURLY_DAMAGE_POOL) for _ in range(hours))


def calculate_fake_global(participant_count: int, cycle_id: int, now_ts: int) -> int:
    hours_elapsed = max(0, (now_ts - cycle_id) / 3600)
    return int(participant_count * hours_elapsed * AVG_HOURLY_DAMAGE)


def calculate_rewards(damage_dealt: int) -> tuple[int, bool]:
    """Returns (curio_count, puzzle_box)."""
    pct = min(damage_dealt / DAMAGE_CAP, 1.0)
    milestones = int(pct * 10)
    puzzle_box = pct >= 0.8
    return milestones, puzzle_box


def reward_potential_pct(damage_dealt: int) -> float:
    return min(damage_dealt / DAMAGE_CAP, 1.0) * 100


def boost_available(boost_used_at: int | None, now_ts: int) -> bool:
    if boost_used_at is None:
        return True
    return (now_ts - boost_used_at) >= BOOST_COOLDOWN_HOURS * 3600


def boost_remaining_seconds(boost_used_at: int, now_ts: int) -> int:
    elapsed = now_ts - boost_used_at
    remaining = BOOST_COOLDOWN_HOURS * 3600 - elapsed
    return max(0, remaining)
