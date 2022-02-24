import logging
import asyncio

from typing import Optional, List, Deque, Dict
from collections import deque, defaultdict

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source import (
    BinancePerpetualAPIOrderBookDataSource,
)


class BinancePerpetualOrderBookTracker(OrderBookTracker):
    _bpobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobt_logger is None:
            cls._bpobt_logger = logging.getLogger(__name__)
        return cls._bpobt_logger

    def __init__(self,
                 trading_pairs: Optional[List[str]] = None,
                 domain: str = "binance_perpetual",
                 throttler: Optional[AsyncThrottler] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__(data_source=BinancePerpetualAPIOrderBookDataSource(trading_pairs=trading_pairs,
                                                                            domain=domain,
                                                                            throttler=throttler,
                                                                            api_factory=api_factory),
                         trading_pairs=trading_pairs, domain=domain)

        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._saved_messages_queues: Dict[str, Deque[OrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._domain = domain

        self._order_book_stream_listener_task: Optional[asyncio.Task] = None
        self._order_book_funding_info_listener_task: Optional[asyncio.Task] = None

    def is_funding_info_initialized(self) -> bool:
        return self._data_source.is_funding_info_initialized()

    @property
    def exchange_name(self) -> str:
        return self._domain

    def start(self):
        super().start()
        self._order_book_stream_listener_task = safe_ensure_future(
            self._data_source.listen_for_subscriptions()
        )
        self._order_book_funding_info_listener_task = safe_ensure_future(
            self._data_source.listen_for_funding_info())

    def stop(self):
        self._order_book_stream_listener_task and self._order_book_stream_listener_task.cancel()
        self._order_book_funding_info_listener_task and self._order_book_funding_info_listener_task.cancel()
        super().stop()
