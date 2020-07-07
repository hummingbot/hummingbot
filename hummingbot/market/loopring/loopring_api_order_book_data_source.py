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
from hummingbot.market.loopring.loopring_active_order_tracker import LoopringActiveOrderTracker
from hummingbot.market.loopring.loopring_order_book import LoopringOrderBook
from hummingbot.market.loopring.loopring_order_book_tracker_entry import LoopringOrderBookTrackerEntry
from hummingbot.market.loopring.loopring_api_token_configuration_data_source import LoopringAPITokenConfigurationDataSource
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.market.loopring.loopring_order_book_message import LoopringOrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook


MARKETS_URL = "/api/v2/exchange/markets"
TICKER_URL = "/api/v2/ticker?market=:markets"
SNAPSHOT_URL = "/api/v2/depth?market=:trading_pair"
TOKEN_INFO_URL = "/api/v2/exchange/tokens"
WS_URL = "wss://ws.loopring.io/v2/ws"
#SNAPSHOT_WS_ROUTE = "/v1/orders/markets/-market-/depth/unmerged"
#SNAPSHOT_WS_SUBSCRIBE_ACTION = "subscribe"
#SNAPSHOT_WS_UPDATE_ACTION = "update"

class LoopringAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    __daobds__logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.__daobds__logger is None:
            cls.__daobds__logger = logging.getLogger(__name__)
        return cls.__daobds__logger

    def __init__(self, trading_pairs: Optional[List[str]] = None, rest_api_url="", websocket_url="", token_configuration=None):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self.REST_URL = rest_api_url
        self.WS_URL = websocket_url
        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()
        self.order_book_create_function = lambda: OrderBook()
        self.token_configuration: LoopringAPITokenConfigurationDataSource = token_configuration

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have trading pair as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:
            # Hard coded to use the live exchange api for auto completing markets (opposed to using testnet)
            markets_response: aiohttp.ClientResponse = await client.get(
                f"https://api.loopring.io{MARKETS_URL}"
            )

            if markets_response.status != 200:
                raise IOError(f"Error fetching active loopring markets. HTTP status is {markets_response.status}.")

            markets_data = await markets_response.json()
            markets_data_coarse = markets_data["data"]

            markets_data = [data for data in markets_data_coarse if (data["enabled"])]

            markets_string = ""
            for datum in markets_data:
                markets_string += f"{datum['market']},"

            volume_response: aiohttp.ClientResponse = await client.get(
              f"https://api.loopring.io{TICKER_URL}".replace(":markets", markets_string)
            )

            if volume_response.status != 200:
                raise IOError(f"Error fetching active loopring markets. HTTP status is {volume_response.status}.")

            volume_data = await volume_response.json()
            volume_data = volume_data["data"]

            field_mapping = {
                "market": "market",
                "baseTokenId": "baseAsset",
                "quoteTokenId": "quoteAsset",
                "precisionForPrice": "int",
                "orderbookAggLevels": "int",
                "enabled": "bool",
            }

            all_markets: pd.DataFrame = pd.DataFrame.from_records(
                data=markets_data, index="market", columns=list(field_mapping.keys())
            )

            all_markets["volume"] = [datum[3] for datum in volume_data]
            all_markets["lastPrice"] = [datum[7] for datum in volume_data]
            
            eth_price: float = float(all_markets.loc["ETH-USDT"].lastPrice)
            usd_volume: float = [
                (
                    volume * eth_price if trading_pair.endswith("ETH") else
                    volume
                )
                for trading_pair, volume in zip(all_markets.index,
                                                     all_markets.volume.astype("float"))]
            all_markets["USDVolume"] = usd_volume

            return all_markets.sort_values("USDVolume", ascending=False)

    @property
    def order_book_class(self) -> LoopringOrderBook:
        return LoopringOrderBook

    async def get_trading_pairs(self) -> List[str]:
        if self._trading_pairs is None:
            active_markets: pd.DataFrame = await self.get_active_exchange_markets()
            trading_pairs: List[str] = active_markets.index.tolist()
            self._trading_pairs = trading_pairs
        else:
            trading_pairs: List[str] = self._trading_pairs
        return trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str, level: int = 0) -> Dict[str, any]:
        async with client.get(f"https://api.loopring.io{SNAPSHOT_URL}&level={level}".replace(":trading_pair", trading_pair)) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(
                    f"Error fetching loopring market snapshot for {trading_pair}. " f"HTTP status is {response.status}."
                )
            data: Dict[str, Any] = await response.json()
            data["market"] = trading_pair
            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, LoopringOrderBookTrackerEntry] = {}
            number_of_pairs: int = len(trading_pairs)

            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                    if "topic" in snapshot:
                        snapshot["topic"]["market"] = trading_pair
                    else:
                        snapshot["topic"] = {}
                        snapshot["topic"]["market"] = trading_pair
                    snapshot_timestamp: float = time.time()

                    snapshot_msg: LoopringOrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                        snapshot, snapshot_timestamp
                    )

                    order_book: OrderBook = self.order_book_create_function()
                    loopring_active_order_tracker: LoopringActiveOrderTracker = LoopringActiveOrderTracker(self.token_configuration)

                    bids, asks = loopring_active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)

                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = LoopringOrderBookTrackerEntry(
                        trading_pair, snapshot_timestamp, order_book, loopring_active_order_tracker
                    )

                    self.logger().info(
                        f"Initialized order book for {trading_pair}. " f"{index+1}/{number_of_pairs} completed."
                    )

                    await asyncio.sleep(0.6)

                except Exception:
                    self.logger().error(
                        f"Error getting snapshot for {trading_pair} in get_tracking_pairs.", exc_info=True
                    )
                    await asyncio.sleep(5)

            self._get_tracking_pair_done_event.set()
            return retval

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                topics: List[dict] = [{"topic": "trade", "market": pair} for pair in trading_pairs]
                subscribe_request: Dict[str, Any] = {
                        "op": "sub",
                        "topics": topics
                    }
                async with websockets.connect(WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        if len(raw_msg) > 4:
                            msg = ujson.loads(raw_msg)
                            if "topic" in msg:
                                for datum in msg["data"]:
                                    trade_msg: OrderBookMessage = LoopringOrderBook.trade_message_from_exchange(datum, msg)
                                    output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()

                async with websockets.connect(WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in trading_pairs:
                        topics: List[dict] = [{"topic": "orderbook", "market": pair, "level": 0 }]
                        subscribe_request: Dict[str, Any] = {
                                "op": "sub",
                                "topics": topics,
                            }
                        await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        if len(raw_msg) > 4:
                            msg = ujson.loads(raw_msg)
                            if "topic" in msg:
                                order_msg: OrderBookMessage = LoopringOrderBook.diff_message_from_exchange(msg)
                                output.put_nowait(order_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()

                async with websockets.connect(WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in trading_pairs:
                        topics: List[dict] = [{"topic": "orderbook", "market": pair, "level": 0, "count": 50, "snapshot": True }]
                        subscribe_request: Dict[str, Any] = {
                                "op": "sub",
                                "topics": topics,
                            }
                        
                        await ws.send(ujson.dumps(subscribe_request))
                        
                    async for raw_msg in self._inner_messages(ws):
                        if len(raw_msg) > 4:
                            msg = ujson.loads(raw_msg)
                            if ("topic" in msg.keys()):
                                order_msg: OrderBookMessage = LoopringOrderBook.snapshot_message_from_exchange(msg,msg["ts"])
                                output.put_nowait(order_msg)
            except asyncio.CancelledError:                                                                                                                                                                                                      
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)