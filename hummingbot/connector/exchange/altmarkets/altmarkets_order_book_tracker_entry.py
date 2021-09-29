from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.connector.exchange.altmarkets.altmarkets_active_order_tracker import AltmarketsActiveOrderTracker


class AltmarketsOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: AltmarketsActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(AltmarketsOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"AltmarketsOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> AltmarketsActiveOrderTracker:
        return self._active_order_tracker
