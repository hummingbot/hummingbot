#!/usr/bin/env python

import aiohttp
import asyncio
import cachetools.func
import logging
import requests
import time

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS

from collections import defaultdict
from decimal import Decimal
from typing import AsyncIterable, Dict, List, Optional, Any

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book import DydxPerpetualOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.logger import HummingbotLogger


class DydxPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    TRADE_CHANNEL = "v3_trades"
    ORDERBOOK_CHANNEL = "v3_orderbook"

    HEARTBEAT_INTERVAL = 30.0  # seconds

    __daobds__logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.__daobds__logger is None:
            cls.__daobds__logger = logging.getLogger(__name__)
        return cls.__daobds__logger

    def __init__(self, trading_pairs: List[str] = None, shared_client: Optional[aiohttp.ClientSession] = None):
        super().__init__(trading_pairs)
        self.order_book_create_function = lambda: OrderBook()

        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()

        self._shared_client = shared_client
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        async with aiohttp.ClientSession() as client:
            retval = {}
            for pair in trading_pairs:
                resp = await client.get(f"{CONSTANTS.DYDX_REST_URL}{CONSTANTS.TICKER_URL}/{pair}")
                resp_json = await resp.json()
                retval[pair] = float(resp_json["markets"][pair]["close"])
            return retval

    @property
    def order_book_class(self) -> DydxPerpetualOrderBook:
        return DydxPerpetualOrderBook

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    def _get_shared_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def get_snapshot(self, trading_pair: str) -> Dict[str, any]:
        async with self._get_shared_client().get(f"{CONSTANTS.DYDX_REST_URL}{CONSTANTS.SNAPSHOT_URL}/{trading_pair}") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(
                    f"Error fetching dydx market snapshot for {trading_pair}. " f"HTTP status is {response.status}."
                )
            data: Dict[str, Any] = await response.json()
            data["trading_pair"] = trading_pair
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = DydxPerpetualOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"id": trading_pair, "rest": True}
        )
        order_book: OrderBook = self.order_book_create_function()
        bids = [ClientOrderBookRow(Decimal(bid["price"]), Decimal(bid["amount"]), snapshot_msg.update_id) for bid in snapshot_msg.bids]
        asks = [ClientOrderBookRow(Decimal(ask["price"]), Decimal(ask["amount"]), snapshot_msg.update_id) for ask in snapshot_msg.asks]
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    @staticmethod
    @cachetools.func.ttl_cache(ttl=10)
    def get_mid_price(trading_pair: str) -> Optional[Decimal]:
        resp = requests.get(url=f"{CONSTANTS.DYDX_REST_URL}{CONSTANTS.TICKER_URL}/{trading_pair}")
        record = resp.json()
        data = record["markets"][trading_pair]
        mid_price = (Decimal(data['high']) + Decimal(data['low'])) / 2

        return mid_price

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{CONSTANTS.DYDX_REST_URL}{CONSTANTS.MARKETS_URL}", timeout=5) as response:
                    if response.status == 200:
                        all_trading_pairs: Dict[str, Any] = await response.json()
                        valid_trading_pairs: list = []
                        for key, val in all_trading_pairs["markets"].items():
                            if val['status'] == "ONLINE":
                                valid_trading_pairs.append(key)
                        return valid_trading_pairs
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for dydx trading pairs
            pass

        return []

    async def _create_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize sets up the websocket connection with a CryptoComWebsocket object.
        """
        try:
            ws = await self._get_shared_client().ws_connect(url=CONSTANTS.DYDX_WS_URL,
                                                            heartbeat=self.HEARTBEAT_INTERVAL,
                                                            autoping=False)
            return ws
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured connecting to {CONSTANTS.EXCHANGE_NAME} WebSocket API. "
                                  f"({e})")
            raise

    async def _subscribe_channels(self, ws: aiohttp.ClientWebSocketResponse):
        try:
            for pair in self._trading_pairs:
                subscribe_orderbook_request: Dict[str, Any] = {
                    "type": "subscribe",
                    "channel": self.ORDERBOOK_CHANNEL,
                    "id": pair
                }
                subscribe_trade_request: Dict[str, Any] = {
                    "type": "subscribe",
                    "channel": self.TRADE_CHANNEL,
                    "id": pair
                }
                await ws.send_json(subscribe_orderbook_request)
                await ws.send_json(subscribe_trade_request)
            self.logger().info("Subscribed to public orderbook and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    async def _iter_messages(self, ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[aiohttp.WSMessage]:
        try:
            while True:
                msg: aiohttp.WSMessage = await ws.receive()
                yield msg
        except Exception as e:
            self.logger().network(f"Unexpected error occurred when parsing websocket payload. "
                                  f"Error: {e}")
            raise
        finally:
            await ws.close()

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws: aiohttp.ClientWebSocketResponse = await self._create_websocket_connection()
                await self._subscribe_channels(ws)

                async for raw_msg in self._iter_messages(ws):
                    if raw_msg.type == aiohttp.WSMsgType.PING:
                        self.logger().debug("Received PING frame. Sending PONG frame...")
                        await ws.pong()
                        continue
                    if raw_msg.type == aiohttp.WSMsgType.PONG:
                        self.logger().debug("Received PONG frame.")
                        continue
                    msg = raw_msg.json()
                    channel = msg.get("channel", "")
                    if channel in [self.ORDERBOOK_CHANNEL, self.TRADE_CHANNEL]:
                        self._message_queue[channel].put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        msg_queue = self._message_queue[self.TRADE_CHANNEL]
        while True:
            try:
                msg = await msg_queue.get()
                if "contents" in msg:
                    if "trades" in msg["contents"]:
                        if msg["type"] == "channel_data":
                            for data in msg["contents"]["trades"]:
                                msg["ts"] = time.time()
                                trade_msg: OrderBookMessage = DydxPerpetualOrderBook.trade_message_from_exchange(data, msg)
                                output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        msg_queue = self._message_queue[self.ORDERBOOK_CHANNEL]
        while True:
            try:
                msg = await msg_queue.get()
                if "contents" in msg:
                    msg["trading_pair"] = msg["id"]
                    if msg["type"] == "channel_data":
                        ts = time.time()
                        order_msg: OrderBookMessage = DydxPerpetualOrderBook.diff_message_from_exchange(msg["contents"], ts, msg)
                        output.put_nowait(order_msg)
                    elif msg["type"] == "subscribed":
                        msg["rest"] = False
                        ts = time.time()
                        order_msg: OrderBookMessage = DydxPerpetualOrderBook.snapshot_message_from_exchange(msg["contents"], ts, msg)
                        output.put_nowait(order_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
