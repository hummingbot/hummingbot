#!/usr/bin/env python
import asyncio
import logging
import hummingbot.market.bitcoin_com.bitcoin_com_constants as constants
# import time

from collections import defaultdict, deque
from typing import Optional, Dict, List, Deque
# from typing import Optional, Dict, List, Deque, Set
from hummingbot.core.data_type.order_book_message import BitcoinComOrderBookMessage
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker, OrderBookTrackerDataSourceType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
# from hummingbot.core.data_type.order_book_tracker_entry import BitcoinComOrderBookTrackerEntry
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.market.bitcoin_com.bitcoin_com_active_order_tracker import BitcoinComActiveOrderTracker
from hummingbot.market.bitcoin_com.bitcoin_com_api_order_book_data_source import BitcoinComAPIOrderBookDataSource
from hummingbot.market.bitcoin_com.bitcoin_com_order_book import BitcoinComOrderBook


class BitcoinComOrderBookTracker(OrderBookTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
        symbols: Optional[List[str]] = None,
    ):
        super().__init__(data_source_type=data_source_type)

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[OrderBookTrackerDataSource] = None
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_trade_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, BitcoinComOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[BitcoinComOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, BitcoinComActiveOrderTracker] = defaultdict(BitcoinComActiveOrderTracker)
        self._symbols: Optional[List[str]] = symbols
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None
        self._order_book_trade_listener_task: Optional[asyncio.Task] = None

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        """
        Initializes an order book data source (Either from live API or from historical database)
        :return: OrderBookTrackerDataSource
        """
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.EXCHANGE_API:
                self._data_source = BitcoinComAPIOrderBookDataSource(symbols=self._symbols)
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        Name of the current exchange
        """
        return constants.EXCHANGE_NAME

    async def start(self):
        """
        Start all listeners and tasks
        """
        await super().start()

        self._order_book_trade_listener_task = safe_ensure_future(
            self.data_source.listen_for_trades(self._ev_loop, self._order_book_trade_stream)
        )
        self._order_book_diff_listener_task = safe_ensure_future(
            self.data_source.listen_for_order_book_diffs(self._ev_loop, self._order_book_diff_stream)
        )
        self._order_book_snapshot_listener_task = safe_ensure_future(
            self.data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )

        self._refresh_tracking_task = safe_ensure_future(
            self._refresh_tracking_loop()
        )
        self._order_book_diff_router_task = safe_ensure_future(
            self._order_book_diff_router()
        )
        self._order_book_snapshot_router_task = safe_ensure_future(
            self._order_book_snapshot_router()
        )
