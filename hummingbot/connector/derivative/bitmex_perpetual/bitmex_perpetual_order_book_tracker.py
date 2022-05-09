import asyncio
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_api_order_book_data_source import (
    BitmexPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class BitmexPerpetualOrderBookTracker(OrderBookTracker):
    _bpobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobt_logger is None:
            cls._bpobt_logger = logging.getLogger(__name__)
        return cls._bpobt_logger

    def __init__(self,
                 trading_pairs: Optional[List[str]] = None,
                 domain: str = "bitmex_perpetual",
                 throttler: Optional[AsyncThrottler] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__(data_source=BitmexPerpetualAPIOrderBookDataSource(
            trading_pairs=trading_pairs,
            domain=domain,
            throttler=throttler,
            api_factory=api_factory),
            trading_pairs=trading_pairs,
            domain=domain
        )

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

    def stop(self):
        self._order_book_stream_listener_task and self._order_book_stream_listener_task.cancel()
        self._order_book_funding_info_listener_task and self._order_book_funding_info_listener_task.cancel()
        super().stop()
