#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import pandas as pd
import time

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS

from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
from decimal import Decimal

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.binance.binance_order_book import BinanceOrderBook
from hummingbot.connector.exchange.binance import binance_utils


class BinanceAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2

    _baobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._baobds_logger is None:
            cls._baobds_logger = logging.getLogger(__name__)
        return cls._baobds_logger

    def __init__(self, trading_pairs: List[str], domain="com", throttler: Optional[AsyncThrottler] = None):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()

    @classmethod
    async def get_last_traded_prices(cls,
                                     trading_pairs: List[str],
                                     domain: str = "com",
                                     throttler: Optional[AsyncThrottler] = None) -> Dict[str, float]:
        throttler = throttler or cls._get_throttler_instance()
        tasks = [cls.get_last_traded_price(t_pair, domain, throttler) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str, domain: str = "com", throttler: Optional[AsyncThrottler] = None) -> float:
        throttler = throttler or cls._get_throttler_instance()
        async with aiohttp.ClientSession() as client:
            async with throttler.execute_task(limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL):
                url = binance_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain)
                resp = await client.get(f"{url}?symbol={binance_utils.convert_to_exchange_trading_pair(trading_pair)}")
                resp_json = await resp.json()
                return float(resp_json["lastPrice"])

    @staticmethod
    @async_ttl_cache(ttl=2, maxsize=1)
    async def get_all_mid_prices(domain="com") -> Optional[Decimal]:
        throttler = BinanceAPIOrderBookDataSource._get_throttler_instance()
        async with aiohttp.ClientSession() as client:
            async with throttler.execute_task(limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL):
                url = binance_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain)
                resp = await client.get(url)
                resp_json = await resp.json()
                ret_val = {}
                for record in resp_json:
                    pair = binance_utils.convert_from_exchange_trading_pair(record["symbol"])
                    ret_val[pair] = (Decimal(record.get("bidPrice", "0")) + Decimal(record.get("askPrice", "0"))) / Decimal("2")
                return ret_val

    @staticmethod
    async def fetch_trading_pairs(domain="com") -> List[str]:
        try:
            throttler = BinanceAPIOrderBookDataSource._get_throttler_instance()
            async with aiohttp.ClientSession() as client:
                async with throttler.execute_task(limit_id=CONSTANTS.EXCHANGE_INFO_PATH_URL):
                    url = binance_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=domain)
                    async with client.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            # fetch d["symbol"] for binance us/com
                            raw_trading_pairs = [d["symbol"] for d in data["symbols"] if d["status"] == "TRADING"]
                            trading_pair_targets = [
                                f"{d['baseAsset']}-{d['quoteAsset']}" for d in data["symbols"] if d["status"] == "TRADING"
                            ]
                            trading_pair_list: List[str] = []
                            for raw_trading_pair, pair_target in zip(raw_trading_pairs, trading_pair_targets):
                                trading_pair: Optional[str] = binance_utils.convert_from_exchange_trading_pair(raw_trading_pair)
                                if trading_pair is not None and trading_pair == pair_target:
                                    trading_pair_list.append(trading_pair)
                            return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for binance trading pairs
            pass

        return []

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @staticmethod
    async def get_snapshot(trading_pair: str, limit: int = 1000, domain: str = "com", throttler: Optional[AsyncThrottler] = None) -> Dict[str, Any]:
        throttler = throttler or BinanceAPIOrderBookDataSource._get_throttler_instance()
        params: Dict = {"limit": str(limit), "symbol": binance_utils.convert_to_exchange_trading_pair(trading_pair)} if limit != 0 \
            else {"symbol": binance_utils.convert_to_exchange_trading_pair(trading_pair)}
        async with aiohttp.ClientSession() as client:
            async with throttler.execute_task(limit_id=CONSTANTS.SNAPSHOT_PATH_URL):
                url = binance_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=domain)
                async with client.get(url, params=params) as response:
                    response: aiohttp.ClientResponse = response
                    if response.status != 200:
                        raise IOError(f"Error fetching market snapshot for {trading_pair}. "
                                      f"Response: {response}.")
                    data: Dict[str, Any] = await response.json()

                    return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair, 1000, self._domain, self._throttler)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def _create_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize WebSocket client for APIOrderBookDataSource
        """
        try:
            return await aiohttp.ClientSession.ws_connect(url=CONSTANTS.WSS_URL.format(self._domain),
                                                          heartbeat=30.0)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when connecting to WebSocket server. "
                                  f"Error: {e}")
            raise

    async def _iter_messages(self,
                             ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[Any]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                yield await ws.receive_json()
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws = await self._create_websocket_connection()
                payload = {
                    "method": "SUBSCRIBE",
                    "params":
                    [
                        f"{binance_utils.convert_to_exchange_trading_pair(trading_pair).lower()}@trade"
                        for trading_pair in self._trading_pairs
                    ],
                    "id": self.TRADE_STREAM_ID
                }
                await ws.send_json(payload)

                async for json_msg in self._iter_messages(ws):
                    if "result" in json_msg:
                        continue
                    trade_msg: OrderBookMessage = BinanceOrderBook.trade_message_from_exchange(json_msg)
                    output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
                await ws.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws = await self._create_websocket_connection()
                payload = {
                    "method": "SUBSCRIBE",
                    "params":
                    [
                        f"{binance_utils.convert_to_exchange_trading_pair(trading_pair).lower()}@depth"
                        for trading_pair in self._trading_pairs
                    ],
                    "id": self.DIFF_STREAM_ID
                }
                await ws.send_json(payload)

                async for json_msg in self._iter_messages(ws):
                    if "result" in json_msg:
                        continue
                    order_book_message: OrderBookMessage = BinanceOrderBook.diff_message_from_exchange(
                        json_msg, time.time())
                    output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
                await ws.close()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair=trading_pair,
                                                                           domain=self._domain,
                                                                           throttler=self._throttler)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().error(f"Unexpected error fetching order book snapshot for {trading_pair}.",
                                            exc_info=True)
                        await asyncio.sleep(5.0)
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
