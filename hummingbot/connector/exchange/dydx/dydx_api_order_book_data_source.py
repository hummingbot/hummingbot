#!/usr/bin/env python

import asyncio
from datetime import datetime
import aiohttp
import logging
from typing import AsyncIterable, Dict, List, Optional, Any
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.connector.exchange.dydx.dydx_order_book import DydxOrderBook
from hummingbot.connector.exchange.dydx.dydx_active_order_tracker import DydxActiveOrderTracker
from hummingbot.connector.exchange.dydx.dydx_api_token_configuration_data_source import DydxAPITokenConfigurationDataSource
from hummingbot.connector.exchange.dydx.dydx_utils import convert_from_exchange_trading_pair, convert_v2_pair_to_v1
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


MARKETS_URL = "/markets"
TICKER_URL = "/stats/markets"
SNAPSHOT_URL = "/orderbook"

WS_URL = "wss://api.dydx.exchange/v1/ws"
DYDX_V1_API_URL = "https://api.dydx.exchange/v1"
DYDX_V2_API_URL = "https://api.dydx.exchange/v2"
DYDX_ORDERBOOK_URL = "https://api.dydx.exchange/v1/orderbook/{}"
DYDX_MARKET_INFO_URL = "https://api.dydx.exchange/v2/markets/{}"


class DydxAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    __daobds__logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.__daobds__logger is None:
            cls.__daobds__logger = logging.getLogger(__name__)
        return cls.__daobds__logger

    def __init__(self, trading_pairs: List[str] = None, rest_api_url="", websocket_url="", token_configuration=None):
        super().__init__(trading_pairs)
        self.REST_URL = rest_api_url
        self.WS_URL = websocket_url
        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()
        self.order_book_create_function = lambda: OrderBook()
        self._token_configuration: DydxAPITokenConfigurationDataSource = token_configuration
        self.token_configuration
        self._active_order_tracker: DydxActiveOrderTracker = DydxActiveOrderTracker(self.token_configuration)

    @property
    def token_configuration(self) -> DydxAPITokenConfigurationDataSource:
        if not self._token_configuration:
            self._token_configuration = DydxAPITokenConfigurationDataSource.create()
        return self._token_configuration

    @property
    def active_order_tracker(self) -> DydxActiveOrderTracker:
        if not self._active_order_tracker:
            self._active_order_tracker = DydxActiveOrderTracker(self.token_configuration)
        return self._active_order_tracker

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{DYDX_V1_API_URL}{TICKER_URL}")
            resp_json = await resp.json()
            retval = {}
            for pair in trading_pairs:
                retval[pair] = float(resp_json["markets"][convert_v2_pair_to_v1(pair)]["last"])
            return retval

    @property
    def order_book_class(self) -> DydxOrderBook:
        return DydxOrderBook

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str, level: int = 0) -> Dict[str, any]:
        async with client.get(f"{DYDX_V1_API_URL}{SNAPSHOT_URL}/{trading_pair}") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(
                    f"Error fetching dydx market snapshot for {trading_pair}. " f"HTTP status is {response.status}."
                )
            data: Dict[str, Any] = await response.json()
            data["market"] = trading_pair
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = DydxOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"id": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            bids, asks = self.active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

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

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(DYDX_MARKET_INFO_URL.format(""), timeout=5) as response:
                    if response.status == 200:
                        all_trading_pairs: Dict[str, Any] = await response.json()
                        valid_trading_pairs: list = []
                        for item in all_trading_pairs["markets"].keys():
                            if "baseCurrency" in all_trading_pairs["markets"][item]:
                                valid_trading_pairs.append(item)
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in valid_trading_pairs:
                            converted_trading_pair: Optional[str] = convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                        return trading_pair_list
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for dydx trading pairs
            pass

        return []

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with websockets.connect(f"{WS_URL}") as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in self._trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "type": "subscribe",
                            "channel": "trades",
                            "id": pair
                        }
                        await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if "contents" in msg:
                            if "trades" in msg["contents"]:
                                for datum in msg["contents"]["trades"]:
                                    trade_msg: OrderBookMessage = DydxOrderBook.trade_message_from_exchange(datum, msg)
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
                async with websockets.connect(f"{WS_URL}") as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in self._trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "type": "subscribe",
                            "channel": "orderbook",
                            "id": pair
                        }
                        await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if "contents" in msg:
                            if "updates" in msg["contents"]:
                                ts = datetime.timestamp(datetime.now())
                                for item in msg["contents"]["updates"]:
                                    order_msg: OrderBookMessage = DydxOrderBook.diff_message_from_exchange(item, ts, msg)
                                    output.put_nowait(order_msg)
                            elif "bids" in msg["contents"]:
                                ts = datetime.timestamp(datetime.now())
                                order_msg: OrderBookMessage = DydxOrderBook.snapshot_message_from_exchange(msg["contents"], ts, msg)
                                output.put_nowait(order_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
