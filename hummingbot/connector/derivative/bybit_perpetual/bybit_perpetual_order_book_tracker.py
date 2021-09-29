import asyncio
import logging

from typing import List, Optional

import aiohttp

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import BybitPerpetualAPIOrderBookDataSource

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class BybitPerpetualOrderBookTracker(OrderBookTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 session: aiohttp.ClientSession,
                 throttler: Optional[AsyncThrottler] = None,
                 trading_pairs: Optional[List[str]] = None,
                 domain: Optional[str] = None):
        super().__init__(BybitPerpetualAPIOrderBookDataSource(throttler, trading_pairs, domain, session), trading_pairs, domain)

        self._domain = domain
        self._order_book_event_listener_task: Optional[asyncio.Task] = None
        self._order_book_instruments_info_listener_task: Optional[asyncio.Task] = None

    async def trading_pair_symbol(self, trading_pair: str) -> str:
        trading_pairs_map = await BybitPerpetualAPIOrderBookDataSource.trading_pair_symbol_map(self._domain)
        symbols = [symbol for symbol, map_trading_pair in trading_pairs_map.items() if trading_pair == map_trading_pair]
        if symbols:
            symbol = symbols[0]
        else:
            raise ValueError(f"The symbol representing trading pair {trading_pair} could not be found")
        return symbol

    def is_funding_info_initialized(self) -> bool:
        return self._data_source.is_funding_info_initialized()

    def start(self):
        super().start()
        self._order_book_event_listener_task = safe_ensure_future(self._data_source.listen_for_subscriptions())
        self._order_book_instruments_info_listener_task = safe_ensure_future(
            self._data_source.listen_for_instruments_info())

    def stop(self):
        if self._order_book_event_listener_task is not None:
            self._order_book_event_listener_task.cancel()
            self._order_book_event_listener_task = None
        if self._order_book_instruments_info_listener_task is not None:
            self._order_book_instruments_info_listener_task.cancel()
            self._order_book_instruments_info_listener_task = None
        super().stop()
