import asyncio
import logging
from collections import deque, defaultdict
from typing import Optional, Deque, List, Dict, Set
from hummingbot.connector.exchange.dolomite.dolomite_active_order_tracker import DolomiteActiveOrderTracker
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker, OrderBookTrackerDataSourceType
from hummingbot.connector.exchange.dolomite.dolomite_order_book import DolomiteOrderBook
from hummingbot.connector.exchange.dolomite.dolomite_order_book_message import DolomiteOrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.remote_api_order_book_data_source import RemoteAPIOrderBookDataSource
from hummingbot.connector.exchange.dolomite.dolomite_api_order_book_data_source import DolomiteAPIOrderBookDataSource
from hummingbot.connector.exchange.dolomite.dolomite_order_book_tracker_entry import DolomiteOrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class DolomiteOrderBookTracker(OrderBookTracker):
    _dobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._dobt_logger is None:
            cls._dobt_logger = logging.getLogger(__name__)
        return cls._dobt_logger

    def __init__(
        self,
        data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
        trading_pairs: Optional[List[str]] = None,
        rest_api_url: str = "",
        websocket_url: str = "",
    ):
        super().__init__(data_source_type=data_source_type)
        self._order_books: Dict[str, DolomiteOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[DolomiteOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[OrderBookTrackerDataSource] = None
        self._active_order_trackers: Dict[str, DolomiteActiveOrderTracker] = defaultdict(DolomiteActiveOrderTracker)
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self.rest_api_url = rest_api_url
        self.websocket_url = websocket_url

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.REMOTE_API:
                self._data_source = RemoteAPIOrderBookDataSource()
            elif self._data_source_type is OrderBookTrackerDataSourceType.EXCHANGE_API:
                self._data_source = DolomiteAPIOrderBookDataSource(
                    trading_pairs=self._trading_pairs, rest_api_url=self.rest_api_url, websocket_url=self.websocket_url
                )
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    async def exchange_name(self) -> str:
        return "dolomite"

    async def _refresh_tracking_tasks(self):
        """
        Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.
        """
        tracking_trading_pairs: Set[str] = set(
            [key for key in self._tracking_tasks.keys() if not self._tracking_tasks[key].done()]
        )
        available_pairs: Dict[str, DolomiteOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
        available_trading_pairs: Set[str] = set(available_pairs.keys())
        new_trading_pairs: Set[str] = available_trading_pairs - tracking_trading_pairs
        deleted_trading_pairs: Set[str] = tracking_trading_pairs - available_trading_pairs

        for trading_pair in new_trading_pairs:
            order_book_tracker_entry: DolomiteOrderBookTrackerEntry = available_pairs[trading_pair]
            self._active_order_trackers[trading_pair] = order_book_tracker_entry.active_order_tracker
            self._order_books[trading_pair] = order_book_tracker_entry.order_book
            self._tracking_message_queues[trading_pair] = asyncio.Queue()
            self._tracking_tasks[trading_pair] = asyncio.ensure_future(self._track_single_book(trading_pair))
            self.logger().info("Started order book tracking for %s." % trading_pair)

        for trading_pair in deleted_trading_pairs:
            self._tracking_tasks[trading_pair].cancel()
            del self._tracking_tasks[trading_pair]
            del self._order_books[trading_pair]
            del self._active_order_trackers[trading_pair]
            del self._tracking_message_queues[trading_pair]
            self.logger().info("Stopped order book tracking for %s." % trading_pair)

    async def _track_single_book(self, trading_pair: str):
        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: DolomiteOrderBook = self._order_books[trading_pair]
        active_order_tracker: DolomiteActiveOrderTracker = self._active_order_trackers[trading_pair]

        while True:
            try:
                message: DolomiteOrderBookMessage = None
                saved_messages: Deque[DolomiteOrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    pass  # Dolomite does not use DIFF, it sticks to using SNAPSHOT

                elif message.type is OrderBookMessageType.SNAPSHOT:
                    s_bids, s_asks = active_order_tracker.convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)
                    self.logger().debug(f"Processed order book snapshot for {trading_pair}.")

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error tracking order book for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg=f'{"Unexpected error tracking order book. Retrying after 5 seconds."}',
                )
                await asyncio.sleep(5.0)
