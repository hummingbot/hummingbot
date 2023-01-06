from typing import List, Optional

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_api_order_book_data_source import (
    BloxrouteOpenbookAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource


class BloxrouteOpenbookOrderBookTracker(OrderBookTracker):

    def __init__(self, data_source: OrderBookTrackerDataSource, trading_pairs: List[str],
                 domain: Optional[str] = None):
        if not isinstance(data_source, BloxrouteOpenbookAPIOrderBookDataSource):
            raise
        super().__init__(data_source, trading_pairs, domain)
        self.process_trade_events_task = data_source.process_trade_events_task
        self.process_order_book_events_task = data_source.process_order_book_events_task

    def stop(self):
        super().stop()

        if self.process_trade_events_task is not None:
            self.process_trade_events_task.close()
            self.process_trade_events_task = None

        if self.process_order_book_events_task is not None:
            self.process_order_book_events_task.close()
            self.process_order_book_events_task = None
