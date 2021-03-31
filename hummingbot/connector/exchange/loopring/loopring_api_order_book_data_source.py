#!/usr/bin/env python

import asyncio
import aiohttp
import logging
from typing import AsyncIterable, Dict, List, Optional, Any
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

# from hummingbot.core.utils import async_ttl_cache
# from hummingbot.core.utils.async_utils import safe_gather
# from hummingbot.connector.exchange.loopring.loopring_active_order_tracker import LoopringActiveOrderTracker
from hummingbot.connector.exchange.loopring.loopring_order_book import LoopringOrderBook
# from hummingbot.connector.exchange.loopring.loopring_order_book_tracker_entry import LoopringOrderBookTrackerEntry
from hummingbot.connector.exchange.loopring.loopring_api_token_configuration_data_source import LoopringAPITokenConfigurationDataSource
from hummingbot.connector.exchange.loopring.loopring_utils import convert_from_exchange_trading_pair, get_ws_api_key
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
# from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
# from hummingbot.connector.exchange.loopring.loopring_order_book_message import LoopringOrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


MARKETS_URL = "/api/v3/exchange/markets"
TICKER_URL = "/api/v3/ticker?market=:markets"
SNAPSHOT_URL = "/api/v3/depth?market=:trading_pair"
TOKEN_INFO_URL = "/api/v3/exchange/tokens"
WS_URL = "wss://ws.api3.loopring.io/v3/ws"
LOOPRING_PRICE_URL = "https://api3.loopring.io/api/v3/ticker"


class LoopringAPIOrderBookDataSource(OrderBookTrackerDataSource):

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
        self.token_configuration: LoopringAPITokenConfigurationDataSource = token_configuration

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"https://api3.loopring.io{TICKER_URL}".replace(":markets", ",".join(trading_pairs)))
            resp_json = await resp.json()
            return {x[0]: float(x[7]) for x in resp_json.get("tickers", [])}

    @property
    def order_book_class(self) -> LoopringOrderBook:
        return LoopringOrderBook

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str, level: int = 0) -> Dict[str, any]:
        async with client.get(f"https://api3.loopring.io{SNAPSHOT_URL}&level={level}".replace(":trading_pair", trading_pair)) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(
                    f"Error fetching loopring market snapshot for {trading_pair}. " f"HTTP status is {response.status}."
                )
            data: Dict[str, Any] = await response.json()
            data["market"] = trading_pair
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000)
            snapshot["data"] = {"bids": snapshot["bids"], "asks": snapshot["asks"]}
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = LoopringOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
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
                async with client.get(f"https://api3.loopring.io{MARKETS_URL}", timeout=5) as response:
                    if response.status == 200:
                        all_trading_pairs: Dict[str, Any] = await response.json()
                        valid_trading_pairs: list = []
                        for item in all_trading_pairs["markets"]:
                            valid_trading_pairs.append(item["market"])
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in valid_trading_pairs:
                            converted_trading_pair: Optional[str] = convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                        return trading_pair_list
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for loopring trading pairs
            pass

        return []

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                topics: List[dict] = [{"topic": "trade", "market": pair} for pair in self._trading_pairs]
                subscribe_request: Dict[str, Any] = {
                    "op": "sub",
                    "topics": topics
                }

                ws_key: str = await get_ws_api_key()
                async with websockets.connect(f"{WS_URL}?wsApiKey={ws_key}") as ws:
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
                ws_key: str = await get_ws_api_key()
                async with websockets.connect(f"{WS_URL}?wsApiKey={ws_key}") as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in self._trading_pairs:
                        topics: List[dict] = [{"topic": "orderbook", "market": pair, "level": 0}]
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
                ws_key: str = await get_ws_api_key()
                async with websockets.connect(f"{WS_URL}?wsApiKey={ws_key}") as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in self._trading_pairs:
                        topics: List[dict] = [{"topic": "orderbook", "market": pair, "level": 0, "count": 50, "snapshot": True}]
                        subscribe_request: Dict[str, Any] = {
                            "op": "sub",
                            "topics": topics,
                        }

                        await ws.send(ujson.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        if len(raw_msg) > 4:
                            msg = ujson.loads(raw_msg)
                            if ("topic" in msg.keys()):
                                order_msg: OrderBookMessage = LoopringOrderBook.snapshot_message_from_exchange(msg, msg["ts"])
                                output.put_nowait(order_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
