from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_active_order_tracker import CoinbaseProActiveOrderTracker


class CoinbaseProOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self,
                 trading_pair: str,
                 timestamp: float,
                 order_book: OrderBook,
                 active_order_tracker: CoinbaseProActiveOrderTracker):
        self._active_order_tracker = active_order_tracker
        super(CoinbaseProOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"CoinbaseProOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> CoinbaseProActiveOrderTracker:
        return self._active_order_tracker
