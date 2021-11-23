import logging
import asyncio

from typing import Optional, List, Deque, Dict
from collections import deque, defaultdict

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_message import OrderBookMessage
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
                 throttler: Optional[AsyncThrottler] = None):
        super().__init__(data_source=BinancePerpetualAPIOrderBookDataSource(trading_pairs=trading_pairs,
                                                                            domain=domain,
                                                                            throttler=throttler),
                         trading_pairs=trading_pairs, domain=domain)

        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._saved_messages_queues: Dict[str, Deque[OrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._domain = domain

    @property
    def exchange_name(self) -> str:
        return self._domain
