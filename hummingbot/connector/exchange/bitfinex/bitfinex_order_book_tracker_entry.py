from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.connector.exchange.bitfinex.bitfinex_active_order_tracker import \
    BitfinexActiveOrderTracker


class BitfinexOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self,
                 symbol: str,
                 timestamp: float,
                 order_book: OrderBook,
                 active_order_tracker: BitfinexActiveOrderTracker):
        self._active_order_tracker = active_order_tracker
        super(BitfinexOrderBookTrackerEntry, self).__init__(symbol, timestamp,
                                                            order_book)

    def __repr__(self) -> str:
        return (
            f"BitfinexOrderBookTrackerEntry(symbol='{self._symbol}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> BitfinexActiveOrderTracker:
        return self._active_order_tracker
