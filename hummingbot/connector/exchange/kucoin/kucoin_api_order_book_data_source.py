#!/usr/bin/env python

import asyncio
import json
import aiohttp
import logging
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
    DefaultDict,
    Set,
)
from collections import defaultdict
from enum import Enum
from async_timeout import timeout
import time
from decimal import Decimal
import requests
import cachetools.func
import websockets
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.kucoin.kucoin_order_book import KucoinOrderBook
from hummingbot.connector.exchange.kucoin.kucoin_active_order_tracker import KucoinActiveOrderTracker
from hummingbot.core.utils.async_utils import safe_ensure_future

SNAPSHOT_REST_URL = "https://api.kucoin.com/api/v2/market/orderbook/level2"
DIFF_STREAM_URL = ""
TICKER_PRICE_CHANGE_URL = "https://api.kucoin.com/api/v1/market/allTickers"
EXCHANGE_INFO_URL = "https://api.kucoin.com/api/v1/symbols"


def secs_until_next_oclock():
    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
    delta: float = next_hour.timestamp() - time.time()
    return delta


class StreamType(Enum):
    Depth = "depth"
    Trade = "trade"


class KucoinAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    PING_INTERVAL = 15
    SYMBOLS_PER_CONNECTION = 100

    _kaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kaobds_logger is None:
            cls._kaobds_logger = logging.getLogger(__name__)
        return cls._kaobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self._tasks: DefaultDict[StreamType, Dict[int, Dict[str, Any]]] = defaultdict(dict)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        async with aiohttp.ClientSession() as client:
            resp = await client.get(TICKER_PRICE_CHANGE_URL)
            resp_json = await resp.json()
            for trading_pair in trading_pairs:
                resp_record = [o for o in resp_json["data"]["ticker"] if o["symbolName"] == trading_pair][0]
                results[trading_pair] = float(resp_record["last"])
        return results

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                self._trading_pairs = await self.fetch_trading_pairs()
            except Exception:
                self._trading_pairs = []
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg="Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    @staticmethod
    @cachetools.func.ttl_cache(ttl=10)
    def get_mid_price(trading_pair: str) -> Optional[Decimal]:
        resp = requests.get(url=TICKER_PRICE_CHANGE_URL)
        records = resp.json()
        result = None
        for record in records["data"]["ticker"]:
            if trading_pair == record["symbolName"] and record["buy"] is not None and record["sell"] is not None:
                result = (Decimal(record["buy"]) + Decimal(record["sell"])) / Decimal("2")
                break
        return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(EXCHANGE_INFO_URL, timeout=5) as response:
                if response.status == 200:
                    try:
                        data: Dict[str, Any] = await response.json()
                        all_trading_pairs = data.get("data", [])
                        return [item["symbol"] for item in all_trading_pairs if item["enableTrading"] is True]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        params: Dict = {"symbol": trading_pair}
        async with client.get(SNAPSHOT_REST_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Kucoin market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = KucoinOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"symbol": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            active_order_tracker: KucoinActiveOrderTracker = KucoinActiveOrderTracker()
            bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                async with timeout(self.MESSAGE_TIMEOUT):
                    yield await ws.recv()
        except asyncio.TimeoutError:
            self.logger().warning("Message recv() timed out. Going to reconnect...")
            raise

    # get required data to create a websocket request
    async def ws_connect_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.kucoin.com/api/v1/bullet-public', data=b'') as resp:
                response: aiohttp.ClientResponse = resp
                if response.status != 200:
                    raise IOError(f"Error fetching Kucoin websocket connection data."
                                  f"HTTP status is {response.status}.")
                data: Dict[str, Any] = await response.json()
                return data

    async def _send_ping(self, interval_secs: int, ws: websockets.WebSocketClientProtocol):
        ping_msg: Dict[str, Any] = {"id": 0, "type": "ping"}
        while True:
            try:
                if not ws.closed:
                    await ws.ensure_open()
                    ping_msg["id"] = int(time.time())
                    await ws.send(json.dumps(ping_msg))
            except websockets.exceptions.ConnectionClosedError:
                pass
            except asyncio.CancelledError:
                raise
            except Exception:
                raise
            await asyncio.sleep(interval_secs)

    async def get_markets_per_ws_connection(self) -> List[str]:
        # Fetch the  markets and split per connection
        all_symbols: List[str] = await self.get_trading_pairs()
        market_subsets: List[str] = []

        for i in range(0, len(all_symbols), self.SYMBOLS_PER_CONNECTION):
            symbols_section: List[str] = all_symbols[i: i + self.SYMBOLS_PER_CONNECTION]
            symbol: str = ','.join(symbols_section)
            market_subsets.append(symbol)

        return market_subsets

    async def _start_update_tasks(self, stream_type: StreamType, output: asyncio.Queue):
        self._stop_update_tasks(stream_type)
        market_assignments = await self.get_markets_per_ws_connection()

        task_dict: Dict[int, Dict[str, Any]] = {}
        for task_index, market_subset in enumerate(market_assignments):
            task_dict[task_index] = {"markets": set(market_subset.split(',')),
                                     "task": safe_ensure_future(self._outer_messages(stream_type,
                                                                                     task_index,
                                                                                     output))}
        self._tasks[stream_type] = task_dict

    async def _refresh_subscriptions(self, stream_type: StreamType):
        """
        modifies the subscription list (market pairs) for each connection to track changes in active markets
        :param stream_type: whether diffs or trades
        :param output: the output queue
        """
        all_symbols: List[str] = await self.get_trading_pairs()
        all_symbols_set: Set[str] = set(all_symbols)

        # removals
        # remove any markets in current connections that are not present in the new master set
        for task_index in self._tasks[stream_type]:
            self._tasks[stream_type][task_index]["markets"] &= all_symbols_set

        # additions
        # from the new set of trading pairs, delete any items that are in the connections already
        for task_index in self._tasks[stream_type]:
            all_symbols_set -= self._tasks[stream_type][task_index]["markets"]

        # now all_symbols_set contains just the additions, add each of those to the shortest connection list
        for market in all_symbols_set:
            smallest_index = 0
            smallest_set_size = self.SYMBOLS_PER_CONNECTION + 1
            for task_index in self._tasks[stream_type]:
                if len(self._tasks[stream_type][task_index]["markets"]) < smallest_set_size:
                    smallest_index = task_index
                    smallest_set_size = len(self._tasks[stream_type][task_index]["markets"])
            self._tasks[stream_type][smallest_index]["markets"].add(market)

    def _stop_update_tasks(self, stream_type: StreamType):
        if stream_type in self._tasks:
            for task_index in self._tasks[stream_type]:
                if not self._tasks[stream_type][task_index]["task"].done():
                    self._tasks[stream_type][task_index]["task"].cancel()
            del self._tasks[stream_type]

    async def _outer_messages(self, stream_type: StreamType, task_index: int, output: asyncio.Queue):
        websocket_data: Dict[str, Any] = await self.ws_connect_data()
        kucoin_ws_uri: str = websocket_data["data"]["instanceServers"][0]["endpoint"] + "?token=" + \
            websocket_data["data"]["token"] + "&acceptUserMessage=true"
        ping_task: Optional[asyncio.Task] = None
        # connects and writes data to the output queue
        while True:
            try:
                market_set: set = self._tasks[stream_type][task_index]["markets"]
                async with websockets.connect(kucoin_ws_uri) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    ping_task = safe_ensure_future(self._send_ping(KucoinAPIOrderBookDataSource.PING_INTERVAL, ws))

                    # initial market list for this connection
                    market_string = ','.join(str(s) for s in market_set)
                    await self._subscribe(ws, stream_type, market_string)

                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if msg["type"] in ("ack", "welcome", "pong"):
                            pass
                        elif msg["type"] == "message":
                            if stream_type == StreamType.Depth:
                                order_book_message: OrderBookMessage = KucoinOrderBook.diff_message_from_exchange(msg)
                            else:
                                trading_pair = msg["data"]["symbol"]
                                data = msg["data"]
                                order_book_message: OrderBookMessage = \
                                    KucoinOrderBook.trade_message_from_exchange(data,
                                                                                metadata={"trading_pair": trading_pair})
                            output.put_nowait(order_book_message)
                        else:
                            # self.logger().error(f"Unrecognized message received from Kucoin websocket: {msg}")
                            self.logger().debug(f"Unrecognized message received from Kucoin websocket: {msg}")

                        # unsubscribe from any unneeded markets
                        markets_to_unsubscribe: set = market_set - self._tasks[stream_type][task_index]["markets"]
                        for market in markets_to_unsubscribe:
                            await self._unsubscribe(ws, stream_type, market)
                        market_set -= markets_to_unsubscribe

                        # subscribe to any new markets
                        markets_to_subscribe: set = self._tasks[stream_type][task_index]["markets"] - market_set
                        for market in markets_to_subscribe:
                            await self._subscribe(ws, stream_type, market)
                        market_set |= markets_to_subscribe

            except asyncio.CancelledError:
                self.logger().info("Task Cancelled")
                raise
            except asyncio.TimeoutError:
                self.logger().error("Timeout error with WebSocket connection. Retrying after 5 seconds...",
                                    exc_info=True)
                await asyncio.sleep(5.0)
                await self._start_update_tasks(StreamType.Depth, output)  # restart from scratch
                await self._start_update_tasks(StreamType.Trade, output)
                continue
            finally:
                if ping_task is not None and not ping_task.done():
                    ping_task.cancel()

    async def _update_subscription(self, ws: websockets.WebSocketClientProtocol, stream_type: StreamType, market: str,
                                   subscribe: bool):
        subscribe_request: dict
        if stream_type == StreamType.Depth:
            subscribe_request = {
                "id": int(time.time()),
                "type": "subscribe" if subscribe else "unsubscribe",
                "topic": f"/market/level2:{market}",
                "response": True
            }
        else:
            subscribe_request: Dict[str, Any] = {
                "id": int(time.time()),
                "type": "subscribe" if subscribe else "unsubscribe",
                "topic": f"/market/match:{market}",
                "privateChannel": False,
                "response": True
            }
        await ws.send(json.dumps(subscribe_request))
        await asyncio.sleep(0.2)  # watch out for the rate limit

    async def _subscribe(self, ws: websockets.WebSocketClientProtocol, stream_type: StreamType, market: str):
        await self._update_subscription(ws, stream_type, market, True)

    async def _unsubscribe(self, ws: websockets.WebSocketClientProtocol, stream_type: StreamType, market: str):
        await self._update_subscription(ws, stream_type, market, False)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                await self._start_update_tasks(StreamType.Trade, output)
                while True:
                    await asyncio.sleep(secs_until_next_oclock())
                    await self._refresh_subscriptions(StreamType.Trade)
            except asyncio.CancelledError:
                raise
            finally:
                self._stop_update_tasks(StreamType.Trade)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                await self._start_update_tasks(StreamType.Depth, output)
                while True:
                    await asyncio.sleep(secs_until_next_oclock())
                    await self._refresh_subscriptions(StreamType.Depth)
            except asyncio.CancelledError:
                raise
            finally:
                self._stop_update_tasks(StreamType.Depth)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with aiohttp.ClientSession() as client:
                    for trading_pair in self._trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = KucoinOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"symbol": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5.0)
                    await asyncio.sleep(secs_until_next_oclock())
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
