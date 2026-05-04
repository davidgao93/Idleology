# core/settlement/views/__init__.py
"""Settlement UI views package — clean public API."""

from .base import SettlementBaseView
from .black_market import BlackMarketView, BulkTradeModal
from .construction import BuildConstructionView
from .dashboard import SettlementDashboardView
from .detail import BuildingDetailView, WorkerModal
from .town_hall import TownHallView

__all__ = [
    "SettlementBaseView",
    "BlackMarketView",
    "BulkTradeModal",
    "TownHallView",
    "BuildConstructionView",
    "BuildingDetailView",
    "WorkerModal",
    "SettlementDashboardView",
]
