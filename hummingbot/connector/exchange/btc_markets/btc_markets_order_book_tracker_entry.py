from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.connector.exchange.btc_markets.btc_markets_active_order_tracker import BtcMarketsActiveOrderTracker


class BtcMarketsOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook,
            active_order_tracker: BtcMarketsActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(BtcMarketsOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"BtcMarketsOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> BtcMarketsActiveOrderTracker:
        return self._active_order_tracker
