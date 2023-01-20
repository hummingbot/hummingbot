import asyncio
from typing import List, Optional

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_api_order_book_data_source import (
    BloxrouteOpenbookAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future


class BloxrouteOpenbookOrderBookTracker(OrderBookTracker):
    def __init__(self, data_source: OrderBookTrackerDataSource, trading_pairs: List[str], domain: Optional[str] = None):
        if not isinstance(data_source, BloxrouteOpenbookAPIOrderBookDataSource):
            raise
        super().__init__(data_source, trading_pairs, domain)

    async def _track_single_book(self, trading_pair: str):
        order_book: OrderBook = self._order_books[trading_pair]
        tracking_message_queue = self._tracking_message_queues[trading_pair]

        while True:
            try:
                message: OrderBookMessage = await tracking_message_queue.get()
                if message.type is OrderBookMessageType.SNAPSHOT:
                    order_book.apply_snapshot(bids=message.bids, asks=message.asks, update_id=message.update_id)
                elif message.type is OrderBookMessageType.DIFF:
                    raise Exception(f"Bloxroute Openbook does not use orderbook diff updates")
                elif message.type is OrderBookMessageType.TRADE:
                    raise Exception(f"Bloxroute Openbook does not use trade updates")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error tracking order book for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg="Unexpected error tracking order book. Retrying after 5 seconds.",
                )
                await asyncio.sleep(5.0)

    def start(self):
        self.stop()
        self._init_order_books_task = safe_ensure_future(self._init_order_books())
        self._order_book_snapshot_listener_task = safe_ensure_future(
            self._data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
        self._order_book_stream_listener_task = safe_ensure_future(self._data_source.listen_for_subscriptions())
        self._order_book_snapshot_router_task = safe_ensure_future(self._order_book_snapshot_router())

    def _order_book_diff_router(self):
        pass

    def _emit_trade_event_loop(self):
        pass
