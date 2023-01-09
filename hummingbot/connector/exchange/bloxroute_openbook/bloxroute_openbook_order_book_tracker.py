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


class BloxrouteOpenbookOrderBookTracker(OrderBookTracker):

    def __init__(self, data_source: OrderBookTrackerDataSource, trading_pairs: List[str], domain: Optional[str] = None):
        if not isinstance(data_source, BloxrouteOpenbookAPIOrderBookDataSource):
            raise
        super().__init__(data_source, trading_pairs, domain)
        self.process_order_book_events_task = data_source.process_order_book_events_task

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
                    app_warning_msg="Unexpected error tracking order book. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    def stop(self):
        super().stop()

        if self.process_order_book_events_task is not None:
            self.process_order_book_events_task.close()
            self.process_order_book_events_task = None

