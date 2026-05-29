from __future__ import annotations

from dsk.trade.trade_offer import TradeOffer


class TradeNetwork:
    """Bilateral trade matching across nations. No-op stub until milestone 7."""

    def __init__(self) -> None:
        self._enabled: bool = False

    def is_enabled(self, t: int) -> bool:
        return self._enabled

    def match(self, offers: list[TradeOffer]) -> list:
        return [None] * len(offers)
