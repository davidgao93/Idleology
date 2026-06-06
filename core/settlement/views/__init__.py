# core/settlement/views/__init__.py
"""Settlement UI views package — clean public API."""

from .base import SettlementBaseView
from .black_market import BlackMarketView, BMPassiveTreeView, OfferBuilderView
from .construction import BuildConstructionView
from .dashboard import SettlementDashboardView
from .detail import BuildingDetailView, WorkerModal
from .plot_detail import MetaBuildingConstructionView, PlotDetailView
from .town_hall import DCCraftModal, TownHallView

__all__ = [
    "SettlementBaseView",
    "BlackMarketView",
    "BMPassiveTreeView",
    "OfferBuilderView",
    "TownHallView",
    "DCCraftModal",
    "BuildConstructionView",
    "BuildingDetailView",
    "WorkerModal",
    "SettlementDashboardView",
    "PlotDetailView",
    "MetaBuildingConstructionView",
]
