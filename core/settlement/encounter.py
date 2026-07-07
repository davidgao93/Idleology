"""
core/settlement/encounter.py — Repair cost lookup for settlement buildings
disabled by a crisis event (bandit_raid, fire_hazard, void_incursion).

The actual crisis "Confront" combat is handled inline by
core/settlement/views/dashboard.py: _on_confront, using the real CombatView.
"""

from __future__ import annotations

_REPAIR_COSTS: dict[int, int] = {
    1: 5_000,
    2: 10_000,
    3: 15_000,
    4: 25_000,
    5: 50_000,
}


def get_repair_cost(tier: int) -> int:
    return _REPAIR_COSTS.get(max(1, min(5, tier)), 5_000)
