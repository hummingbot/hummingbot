from hummingbot.connector.exchange.gate_io.gate_io_active_order_tracker import GateIoActiveOrderTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry


class GateIoOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: GateIoActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(GateIoOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"GateIoOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> GateIoActiveOrderTracker:
        return self._active_order_tracker
