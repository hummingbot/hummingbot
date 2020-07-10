import asyncio
import logging
from typing import Dict, List, Optional

import aiohttp
import pandas as pd

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger

PERPETUAL_BASE_URL = "https://fapi.binance.com/fapi/v1"
SNAPSHOT_REST_URL = PERPETUAL_BASE_URL + ""
DIFF_STREAM_URL = PERPETUAL_BASE_URL + ""
TICKER_PRICE_CHANGE_URL = PERPETUAL_BASE_URL + "/ticker/24hr"
EXCHANGE_INFO_URL = PERPETUAL_BASE_URL + "/exchangeInfo"


class BinancePerpetualOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._order_book_create_function = lambda: OrderBook()

    _bpobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobds_logger is None:
            cls._bpobds_logger = logging.getLogger(__name__)
        return cls._bpobds_logger

    @classmethod
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have trading_pair as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:
            market_response, exchange_response = await safe_gather(
                client.get(TICKER_PRICE_CHANGE_URL),
                client.get(EXCHANGE_INFO_URL)
            )
            market_response: aiohttp.ClientResponse = market_response
            exchange_response: aiohttp.ClientResponse = exchange_response

            if market_response.status != 200:
                raise IOError(f"Error fetching Binance Perpetual markets information. "
                              f"HTTP status is {market_response.status}.")
            if exchange_response.status != 200:
                raise IOError(f"Error fetching Binance Perpetual exchange information. "
                              f"HTTP status is {exchange_response.status}.")
            # market_data = await market_response.json()
            # exchange_data = await exchange_response.json()

    async def get_trading_pairs(self) -> List[str]:
        raise NotImplementedError

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        raise NotImplementedError

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        raise NotImplementedError

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        raise NotImplementedError

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        raise NotImplementedError
