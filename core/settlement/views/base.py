# core/settlement/views/base.py
"""Base class for all settlement-related Discord UI views."""

from core.base_view import BaseView


class SettlementBaseView(BaseView):
    """Common base for all settlement views."""

    def __init__(self, bot, user_id: str, timeout: int = 600):
        super().__init__(bot, user_id, timeout=timeout)
