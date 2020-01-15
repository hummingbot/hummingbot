#!/usr/bin/env python

import asyncio
from decimal import Decimal

import aiohttp
import logging
import pandas as pd
import math

from typing import AsyncIterable, Dict, List, Optional, Any

import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.utils import async_ttl_cache
# from hummingbot.market.dolomite.dolomite_active_order_tracker import DolomiteActiveOrderTracker
# from hummingbot.market.dolomite.dolomite_order_book import DolomiteOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger

from hummingbot.core.data_type.order_book_tracker_entry import DolomiteOrderBookTrackerEntry, OrderBookTrackerEntry

from hummingbot.core.data_type.order_book_message import DolomiteOrderBookMessage

REST_URL = "https://api.bancor.network/0.1"
MARKET_URL = "/currencies/tokens?limit=1000&skip=0&fromCurrencyCode=USD&includeTotal=true&orderBy=liquidityDepth&sortOrder=desc"
GET_PAIR_URL = "/currencies/convertiblePairs"


class BancorAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    __daobds__logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.__daobds__logger is None:
            cls.__daobds__logger = logging.getLogger(__name__)
        return cls.__daobds__logger

    def __init__(self, trading_pairs: Optional[List[str]] = None, rest_api_url=""):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self.REST_URL = rest_api_url
        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        async with aiohttp.ClientSession() as client:
            markets_response: aiohttp.ClientResponse = await client.get(f"{REST_URL}{MARKET_URL}")
            if markets_response.status != 200:
                raise IOError(f"Error fetching active Bancor markets. HTTP status is {markets_response.status}.")
            markets_data = await markets_response.json()
            markets_data = markets_data["data"]
            field_mapping = {
                "market": "market",
                "primary_token": "baseAsset",
                "primary_ticker_decimal_places": "int",
                "secondary_token": "quoteAsset",
                "secondary_ticker_price_decimal_places": "int",
                "period_volume": "volume",
                "period_volume_usd": "USDVolume",
            }

            all_markets: pd.DataFrame = pd.DataFrame.from_records(
                data=markets_data, index="market", columns=list(field_mapping.keys())
            )

            def obj_to_decimal(c):
                return Decimal(c["amount"]) / math.pow(10, c["currency"]["precision"])

            all_markets.rename(field_mapping, axis="columns", inplace=True)
            all_markets["USDVolume"] = all_markets["USDVolume"].map(obj_to_decimal)
            all_markets["volume"] = all_markets["volume"].map(obj_to_decimal)

            return all_markets.sort_values("USDVolume", ascending=False)

    @property
    async def exchange_name(self) -> str:
        return "bancor"

    async def get_tracking_pairs(self):
        pass

    async def get_trading_pairs(self):
        async with aiohttp.ClientSession() as client:
            markets_response: aiohttp.ClientResponse = await client.get(f"{REST_URL}{GET_PAIR_URL}")
            if markets_response.status != 200:
                raise IOError(f"Error fetching active Bancor markets. HTTP status is {markets_response.status}.")
            trading_pairs = await markets_response.json()
            trading_pairs = trading_pairs["data"]
            pairs = []
            for key, value in trading_pairs.items():
                pairs.append(f"{key}-{value}")
            return pairs

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
