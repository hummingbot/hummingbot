import asyncio
import logging
from collections import deque, defaultdict
from typing import Optional, Deque, List, Dict, Set
from hummingbot.market.dolomite.dolomite_active_order_tracker import DolomiteActiveOrderTracker
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker, OrderBookTrackerDataSourceType
from hummingbot.market.dolomite.dolomite_order_book import DolomiteOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.remote_api_order_book_data_source import RemoteAPIOrderBookDataSource
from hummingbot.market.dolomite.dolomite_api_order_book_data_source import DolomiteAPIOrderBookDataSource

from hummingbot.core.data_type.order_book_message import OrderBookMessageType, DolomiteOrderBookMessage
from hummingbot.core.data_type.order_book_tracker_entry import DolomiteOrderBookTrackerEntry


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
        symbols: Optional[List[str]] = None,
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
        self._symbols: Optional[List[str]] = symbols
        self.rest_api_url = rest_api_url
        self.websocket_url = websocket_url

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.REMOTE_API:
                self._data_source = RemoteAPIOrderBookDataSource()
            elif self._data_source_type is OrderBookTrackerDataSourceType.EXCHANGE_API:
                self._data_source = DolomiteAPIOrderBookDataSource(
                    symbols=self._symbols, rest_api_url=self.rest_api_url, websocket_url=self.websocket_url
                )
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    async def exchange_name(self) -> str:
        return "dolomite"

    async def start(self):
        self._order_book_snapshot_listener_task = asyncio.ensure_future(
            self.data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
        self._refresh_tracking_task = asyncio.ensure_future(self._refresh_tracking_loop())
        self._order_book_snapshot_router_task = asyncio.ensure_future(self._order_book_snapshot_router())

        await asyncio.gather(
            self._order_book_snapshot_listener_task, self._order_book_snapshot_router_task, self._refresh_tracking_task
        )

    async def _refresh_tracking_tasks(self):
        """
        Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.
        """
        tracking_symbols: Set[str] = set(
            [key for key in self._tracking_tasks.keys() if not self._tracking_tasks[key].done()]
        )
        available_pairs: Dict[str, DolomiteOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
        available_symbols: Set[str] = set(available_pairs.keys())
        new_symbols: Set[str] = available_symbols - tracking_symbols
        deleted_symbols: Set[str] = tracking_symbols - available_symbols

        for symbol in new_symbols:
            order_book_tracker_entry: DolomiteOrderBookTrackerEntry = available_pairs[symbol]
            self._active_order_trackers[symbol] = order_book_tracker_entry.active_order_tracker
            self._order_books[symbol] = order_book_tracker_entry.order_book
            self._tracking_message_queues[symbol] = asyncio.Queue()
            self._tracking_tasks[symbol] = asyncio.ensure_future(self._track_single_book(symbol))
            self.logger().info("Started order book tracking for %s.", symbol)

        for symbol in deleted_symbols:
            self._tracking_tasks[symbol].cancel()
            del self._tracking_tasks[symbol]
            del self._order_books[symbol]
            del self._active_order_trackers[symbol]
            del self._tracking_message_queues[symbol]
            self.logger().info("Stopped order book tracking for %s.", symbol)

    async def _track_single_book(self, symbol: str):
        message_queue: asyncio.Queue = self._tracking_message_queues[symbol]
        order_book: DolomiteOrderBook = self._order_books[symbol]
        active_order_tracker: DolomiteActiveOrderTracker = self._active_order_trackers[symbol]

        while True:
            try:
                message: DolomiteOrderBookMessage = None
                saved_messages: Deque[DolomiteOrderBookMessage] = self._saved_message_queues[symbol]
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
                    self.logger().debug("Processed order book snapshot for %s.", symbol)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error tracking order book for {symbol}.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error tracking order book. Retrying after 5 seconds.",
                )
                await asyncio.sleep(5.0)
