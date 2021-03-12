#!/usr/bin/env python
from itertools import islice

import aiohttp
import asyncio
from async_timeout import timeout
from collections import defaultdict
from enum import Enum
import json
import logging
import pandas as pd
import time
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
    DefaultDict,
    Set,
    Tuple,
)
import websockets
from websockets.client import Connect as WSConnectionContext

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


class KucoinWSConnectionIterator:
    """
    A message iterator that automatically manages the auto-ping requirement from Kucoin, and returns all JSON-decoded
    messages from a Kucoin websocket connection

    Instances of this class are intended to be used with an `async for msg in <iterator>: ...` block. The iterator does
    the following:

     1. At the beginning of the loop, connect to Kucoin's public websocket data stream, and subscribe to topics matching
        its constructor arguments.
     2. Start an automatic ping background task, to keep the websocket connection alive.
     3. Yield any messages received from Kucoin, after JSON decode. Note that this means all messages, include ACK and
        PONG messages, are returned.
     4. Raises `asyncio.TimeoutError` if no message have been heard from Kucoin for more than
       `PING_TIMEOUT + PING_INTERVAL`.
     5. If the iterator exits for any reason, including any failures or timeout - stop and clean up the automatic ping
        task.

    The trading pairs subscription can be updated dynamically by assigning into the `trading_pairs` property.

    Note that this iterator does NOT come with any error handling logic or built-in resilience by itself. It is expected
    that the caller of the iterator should handle all errors from the iterator.
    """
    PING_TIMEOUT = 10.0
    PING_INTERVAL = 5

    _kwsci_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._kwsci_logger is None:
            cls._kwsci_logger = logging.getLogger(__name__)
        return cls._kwsci_logger

    def __init__(self, stream_type: StreamType, trading_pairs: Set[str]):
        self._ping_task: Optional[asyncio.Task] = None
        self._stream_type: StreamType = stream_type
        self._trading_pairs: Set[str] = trading_pairs
        self._last_nonce: int = int(time.time() * 1e3)
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None

    @staticmethod
    async def get_ws_connection_context() -> WSConnectionContext:
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.kucoin.com/api/v1/bullet-public', data=b'') as resp:
                response: aiohttp.ClientResponse = resp
                if response.status != 200:
                    raise IOError(f"Error fetching Kucoin websocket connection data."
                                  f"HTTP status is {response.status}.")
                data: Dict[str, Any] = await response.json()

        endpoint: str = data["data"]["instanceServers"][0]["endpoint"]
        token: str = data["data"]["token"]
        ws_url: str = f"{endpoint}?token={token}&acceptUserMessage=true"
        return WSConnectionContext(ws_url)

    @staticmethod
    async def update_subscription(ws: websockets.WebSocketClientProtocol,
                                  stream_type: StreamType,
                                  trading_pairs: Set[str],
                                  subscribe: bool):
        # Kucoin has a limit of 100 subscription per 10 seconds
        it = iter(trading_pairs)
        trading_pair_chunks: List[Tuple[str]] = list(iter(lambda: tuple(islice(it, 100)), ()))
        subscribe_requests: List[Dict[str, Any]] = []
        if stream_type == StreamType.Depth:
            for trading_pair_chunk in trading_pair_chunks:
                market_str: str = ",".join(sorted(trading_pair_chunk))
                subscribe_requests.append({
                    "id": int(time.time()),
                    "type": "subscribe" if subscribe else "unsubscribe",
                    "topic": f"/market/level2:{market_str}",
                    "response": True
                })
        else:
            for trading_pair_chunk in trading_pair_chunks:
                market_str: str = ",".join(sorted(trading_pair_chunk))
                subscribe_requests.append({
                    "id": int(time.time()),
                    "type": "subscribe" if subscribe else "unsubscribe",
                    "topic": f"/market/match:{market_str}",
                    "privateChannel": False,
                    "response": True
                })
        for i, subscribe_request in enumerate(subscribe_requests):
            await ws.send(json.dumps(subscribe_request))
            if i != len(subscribe_requests) - 1:  # only sleep between requests
                await asyncio.sleep(10)

        await asyncio.sleep(0.2)  # watch out for the rate limit

    async def subscribe(self, stream_type: StreamType, trading_pairs: Set[str]):
        await KucoinWSConnectionIterator.update_subscription(self.websocket, stream_type, trading_pairs, True)

    async def unsubscribe(self, stream_type: StreamType, trading_pairs: Set[str]):
        await KucoinWSConnectionIterator.update_subscription(self.websocket, stream_type, trading_pairs, False)

    @property
    def stream_type(self) -> StreamType:
        return self._stream_type

    @property
    def trading_pairs(self) -> Set[str]:
        return self._trading_pairs.copy()

    @trading_pairs.setter
    def trading_pairs(self, trading_pairs: Set[str]):
        prev_trading_pairs = self._trading_pairs
        self._trading_pairs = trading_pairs.copy()

        if prev_trading_pairs != trading_pairs and self._websocket is not None:
            async def update_subscriptions_func():
                unsubscribe_set: Set[str] = prev_trading_pairs - trading_pairs
                subscribe_set: Set[str] = trading_pairs - prev_trading_pairs
                if len(unsubscribe_set) > 0:
                    await self.unsubscribe(self.stream_type, unsubscribe_set)
                if len(subscribe_set) > 0:
                    await self.subscribe(self.stream_type, subscribe_set)
            safe_ensure_future(update_subscriptions_func())

    @property
    def websocket(self) -> Optional[websockets.WebSocketClientProtocol]:
        return self._websocket

    @property
    def ping_task(self) -> Optional[asyncio.Task]:
        return self._ping_task

    def get_nonce(self) -> int:
        now_ms: int = int(time.time() * 1e3)
        if now_ms <= self._last_nonce:
            now_ms = self._last_nonce + 1
        self._last_nonce = now_ms
        return now_ms

    async def _ping_loop(self, interval_secs: float):
        ws: websockets.WebSocketClientProtocol = self.websocket

        while True:
            try:
                if not ws.closed:
                    await ws.ensure_open()
                    ping_msg: Dict[str, Any] = {
                        "id": self.get_nonce(),
                        "type": "ping"
                    }
                    await ws.send(json.dumps(ping_msg))
            except websockets.exceptions.ConnectionClosedError:
                pass
            except asyncio.CancelledError:
                raise
            except Exception:
                raise
            await asyncio.sleep(interval_secs)

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can disconnect.
        try:
            while True:
                async with timeout(self.PING_TIMEOUT + self.PING_INTERVAL):
                    yield await ws.recv()
        except asyncio.TimeoutError:
            self.logger().warning(f"Message recv() timed out. "
                                  f"Stream type = {self.stream_type},"
                                  f"Trading pairs = {self.trading_pairs}.")
            raise

    async def __aiter__(self) -> AsyncIterable[Dict[str, any]]:
        if self._websocket is not None:
            raise EnvironmentError("Iterator already in use.")

        # Get connection info and connect to Kucoin websocket.
        ping_task: Optional[asyncio.Task] = None

        try:
            async with (await self.get_ws_connection_context()) as ws:
                self._websocket = ws

                # Subscribe to the initial topic.
                await self.subscribe(self.stream_type, self.trading_pairs)

                # Start the ping task
                ping_task = safe_ensure_future(self._ping_loop(self.PING_INTERVAL))

                # Get messages
                async for raw_msg in self._inner_messages(ws):
                    msg: Dict[str, any] = json.loads(raw_msg)
                    yield msg
        finally:
            # Clean up.
            if ping_task is not None:
                ping_task.cancel()


class KucoinAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    PING_INTERVAL = 15
    SYMBOLS_PER_CONNECTION = 100
    SLEEP_BETWEEN_SNAPSHOT_REQUEST = 5.0

    _kaobds_logger: Optional[HummingbotLogger] = None

    class TaskEntry:
        __slots__ = ("__weakref__", "_trading_pairs", "_task", "_message_iterator")

        def __init__(self, trading_pairs: Set[str], task: asyncio.Task):
            self._trading_pairs: Set[str] = trading_pairs.copy()
            self._task: asyncio.Task = task
            self._message_iterator: Optional[KucoinWSConnectionIterator] = None

        @property
        def trading_pairs(self) -> Set[str]:
            return self._trading_pairs.copy()

        @property
        def task(self) -> asyncio.Task:
            return self._task

        @property
        def message_iterator(self) -> Optional[KucoinWSConnectionIterator]:
            return self._message_iterator

        @message_iterator.setter
        def message_iterator(self, msg_iter: KucoinWSConnectionIterator):
            self._message_iterator = msg_iter

        def update_trading_pairs(self, trading_pairs: Set[str]):
            self._trading_pairs = trading_pairs.copy()
            if self._message_iterator is not None:
                self._message_iterator.trading_pairs = self._trading_pairs

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kaobds_logger is None:
            cls._kaobds_logger = logging.getLogger(__name__)
        return cls._kaobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self._tasks: DefaultDict[StreamType, Dict[int, KucoinAPIOrderBookDataSource.TaskEntry]] = defaultdict(dict)

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
        market_assignments: List[str] = await self.get_markets_per_ws_connection()

        for task_index, market_subset in enumerate(market_assignments):
            await self._start_single_update_task(stream_type,
                                                 output,
                                                 task_index,
                                                 market_subset)

    async def _start_single_update_task(self,
                                        stream_type: StreamType,
                                        output: asyncio.Queue,
                                        task_index: int,
                                        market_subset: str):
        self._tasks[stream_type][task_index] = self.TaskEntry(
            set(market_subset.split(',')),
            safe_ensure_future(self._collect_and_decode_messages_loop(stream_type, task_index, output))
        )

    async def _refresh_subscriptions(self, stream_type: StreamType, output: asyncio.Queue):
        """
        modifies the subscription list (market pairs) for each connection to track changes in active markets
        :param stream_type: whether diffs or trades
        :param output: the output queue
        """
        all_symbols: List[str] = await self.get_trading_pairs()
        all_symbols_set: Set[str] = set(all_symbols)
        pending_trading_pair_updates: Dict[Tuple[StreamType, int], Set[str]] = {}

        # removals
        # remove any markets in current connections that are not present in the new master set
        for task_index in self._tasks[stream_type]:
            update_key: Tuple[StreamType, int] = (stream_type, task_index)
            if update_key not in pending_trading_pair_updates:
                pending_trading_pair_updates[update_key] = self._tasks[stream_type][task_index].trading_pairs
            pending_trading_pair_updates[update_key] &= all_symbols_set

        # additions
        # from the new set of trading pairs, delete any items that are in the connections already
        for task_index in self._tasks[stream_type]:
            all_symbols_set -= self._tasks[stream_type][task_index].trading_pairs

        # now all_symbols_set contains just the additions, add each of those to the shortest connection list
        for market in all_symbols_set:
            smallest_index: int = 0
            smallest_set_size: int = self.SYMBOLS_PER_CONNECTION + 1
            for task_index in self._tasks[stream_type]:
                if len(self._tasks[stream_type][task_index].trading_pairs) < smallest_set_size:
                    smallest_index = task_index
                    smallest_set_size = len(self._tasks[stream_type][task_index].trading_pairs)
            if smallest_set_size < self.SYMBOLS_PER_CONNECTION:
                update_key: Tuple[StreamType, int] = (stream_type, smallest_index)
                if update_key not in pending_trading_pair_updates:
                    pending_trading_pair_updates[update_key] = self._tasks[stream_type][smallest_index].trading_pairs
                pending_trading_pair_updates[update_key].add(market)
            else:
                new_index: int = len(self._tasks[stream_type])
                await self._start_single_update_task(stream_type=stream_type,
                                                     output=output,
                                                     task_index=new_index,
                                                     market_subset=market)

        # update the trading pairs set for all task entries that have pending updates.
        for (stream_type, task_index), trading_pairs in pending_trading_pair_updates.items():
            self._tasks[stream_type][task_index].update_trading_pairs(trading_pairs)

    def _stop_update_tasks(self, stream_type: StreamType):
        if stream_type in self._tasks:
            for task_index in self._tasks[stream_type]:
                if not self._tasks[stream_type][task_index].task.done():
                    self._tasks[stream_type][task_index].task.cancel()
            del self._tasks[stream_type]

    async def _collect_and_decode_messages_loop(self, stream_type: StreamType, task_index: int, output: asyncio.Queue):
        while True:
            try:
                kucoin_msg_iterator: KucoinWSConnectionIterator = KucoinWSConnectionIterator(
                    stream_type, self._tasks[stream_type][task_index].trading_pairs
                )
                self._tasks[stream_type][task_index].message_iterator = kucoin_msg_iterator
                async for raw_msg in kucoin_msg_iterator:
                    msg_type: str = raw_msg.get("type", "")
                    if msg_type in {"ack", "welcome", "pong"}:
                        pass
                    elif msg_type == "message":
                        if stream_type == StreamType.Depth:
                            order_book_message: OrderBookMessage = KucoinOrderBook.diff_message_from_exchange(raw_msg)
                        else:
                            trading_pair: str = raw_msg["data"]["symbol"]
                            data = raw_msg["data"]
                            order_book_message: OrderBookMessage = \
                                KucoinOrderBook.trade_message_from_exchange(
                                    data,
                                    metadata={"trading_pair": trading_pair}
                                )
                        output.put_nowait(order_book_message)
                    elif msg_type == "error":
                        self.logger().error(f"WS error message from Kucoin: {raw_msg}")
                    else:
                        self.logger().warning(f"Unrecognized message type from Kucoin: {msg_type}. "
                                              f"Message = {raw_msg}.")
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().error("Timeout error with WebSocket connection. Retrying after 5 seconds...",
                                    exc_info=True)
                await asyncio.sleep(5.0)
            except Exception:
                self.logger().error("Unexpected exception with WebSocket connection. Retrying after 5 seconds...",
                                    exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                self._tasks[stream_type][task_index].message_iterator = None

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                await self._start_update_tasks(StreamType.Trade, output)
                while True:
                    await asyncio.sleep(secs_until_next_oclock())
                    await self._refresh_subscriptions(StreamType.Trade, output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error. {e}", exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                self._stop_update_tasks(StreamType.Trade)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                await self._start_update_tasks(StreamType.Depth, output)
                while True:
                    await asyncio.sleep(secs_until_next_oclock())
                    await self._refresh_subscriptions(StreamType.Depth, output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error. {e}", exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                self._stop_update_tasks(StreamType.Depth)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
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
                            await asyncio.sleep(self.SLEEP_BETWEEN_SNAPSHOT_REQUEST)
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
