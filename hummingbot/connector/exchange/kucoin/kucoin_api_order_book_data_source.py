from itertools import islice
import aiohttp
from aiohttp import WSMsgType
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
from urllib.parse import urlencode
from yarl import URL

from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.exchange.kucoin.kucoin_order_book import KucoinOrderBook
from hummingbot.connector.exchange.kucoin.kucoin_active_order_tracker import KucoinActiveOrderTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange.kucoin.kucoin_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
)
from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS
from hummingbot.logger import HummingbotLogger

DIFF_STREAM_URL = ""


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

    def __init__(self, stream_type: StreamType, trading_pairs: Set[str], throttler: AsyncThrottler):
        self._ping_task: Optional[asyncio.Task] = None
        self._stream_type: StreamType = stream_type
        self._trading_pairs: Set[str] = trading_pairs
        self._throttler = throttler
        self._last_nonce: int = int(time.time() * 1e3)
        self._client: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None

    def __del__(self):
        if self._client:
            safe_ensure_future(self._client.close())
            self._client = None
        if self._websocket:
            safe_ensure_future(self._websocket.close())
            self._websocket = None

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    async def ws_connection_url(self):
        if self._client is None:
            self._client = aiohttp.ClientSession()
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.PUBLIC_WS_DATA_PATH_URL
        async with self._throttler.execute_task(CONSTANTS.PUBLIC_WS_DATA_PATH_URL):
            async with self._client.post(url, data=b'') as resp:
                response: aiohttp.ClientResponse = resp
                if response.status != 200:
                    raise IOError(f"Error fetching Kucoin websocket connection data."
                                  f"HTTP status is {response.status}.")
                data: Dict[str, Any] = await response.json()

        endpoint: str = data["data"]["instanceServers"][0]["endpoint"]
        token: str = data["data"]["token"]
        ws_url: str = f"{endpoint}?token={token}&acceptUserMessage=true"
        return ws_url

    async def update_subscription(self, stream_type: StreamType, trading_pairs: Set[str], subscribe: bool):
        trading_pairs = {convert_to_exchange_trading_pair(t) for t in trading_pairs}
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
            async with self._throttler.execute_task(CONSTANTS.WS_REQUEST_LIMIT_ID):
                await self._websocket.send_json(subscribe_request)

    async def subscribe(self, stream_type: StreamType, trading_pairs: Set[str]):
        await self.update_subscription(stream_type, trading_pairs, subscribe=True)

    async def unsubscribe(self, stream_type: StreamType, trading_pairs: Set[str]):
        await self.update_subscription(stream_type, trading_pairs, subscribe=False)

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
    def websocket(self) -> Optional[aiohttp.ClientWebSocketResponse]:
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
        while True:
            if not self._websocket.closed:
                ping_msg: Dict[str, Any] = {
                    "id": self.get_nonce(),
                    "type": "ping"
                }
                async with self._throttler.execute_task(CONSTANTS.WS_REQUEST_LIMIT_ID):
                    await self._websocket.send_json(ping_msg)
            await asyncio.sleep(interval_secs)

    async def _inner_messages(self, ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can disconnect.
        try:
            while True:
                async with timeout(self.PING_TIMEOUT + self.PING_INTERVAL):
                    msg = await ws.receive()
                    if msg.type == WSMsgType.CLOSED:
                        raise ConnectionError
                    yield msg.data
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
            async with self._throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTION_LIMIT_ID):
                url = await self.ws_connection_url()
            async with self._client.ws_connect(url, autoping=True, heartbeat=CONSTANTS.WS_PING_HEARTBEAT) as ws:
                self._websocket = ws

                # Subscribe to the initial topic.
                await self.subscribe(self.stream_type, self.trading_pairs)

                # Start the ping task
                ping_task = safe_ensure_future(self._ping_loop(self.PING_INTERVAL))

                # Get messages
                async for raw_msg in self._inner_messages(self._websocket):
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

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    def __init__(
        self,
        throttler: Optional[AsyncThrottler] = None,
        trading_pairs: Optional[List[str]] = None,
        auth: Optional[KucoinAuth] = None,
    ):
        super().__init__(trading_pairs)
        self._throttler = throttler or self._get_throttler_instance()
        self._auth = auth
        self._order_book_create_function = lambda: OrderBook()
        self._tasks: DefaultDict[StreamType, Dict[int, KucoinAPIOrderBookDataSource.TaskEntry]] = defaultdict(dict)

    @classmethod
    async def get_last_traded_prices(
        cls, trading_pairs: List[str], throttler: Optional[AsyncThrottler] = None
    ) -> Dict[str, float]:
        throttler = throttler or cls._get_throttler_instance()
        results = dict()
        async with aiohttp.ClientSession() as client:
            url = CONSTANTS.BASE_PATH_URL + CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
            async with throttler.execute_task(CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL):
                async with client.get(url) as response:
                    resp_json = await response.json()
            for trading_pair in trading_pairs:
                resp_record = [
                    o for o in resp_json["data"]["ticker"]
                    if convert_from_exchange_trading_pair(o["symbol"]) == trading_pair
                ][0]
                results[trading_pair] = float(resp_record["last"])
        return results

    @classmethod
    async def fetch_trading_pairs(cls, throttler: Optional[AsyncThrottler] = None) -> List[str]:
        throttler = throttler or cls._get_throttler_instance()
        async with aiohttp.ClientSession() as client:
            url = CONSTANTS.BASE_PATH_URL + CONSTANTS.EXCHANGE_INFO_PATH_URL
            async with throttler.execute_task(CONSTANTS.EXCHANGE_INFO_PATH_URL):
                async with client.get(url, timeout=5) as response:
                    if response.status == 200:
                        try:
                            data: Dict[str, Any] = await response.json()
                            all_trading_pairs = data.get("data", [])
                            return [
                                convert_from_exchange_trading_pair(item["symbol"]) for item in all_trading_pairs
                                if item["enableTrading"] is True
                            ]
                        except Exception:
                            pass
                            # Do nothing if the request fails -- there will be no autocomplete for the trading pairs
                    return []

    @classmethod
    async def get_snapshot(
        cls,
        client: aiohttp.ClientSession,
        trading_pair: str,
        auth: KucoinAuth = None,
        throttler: Optional[AsyncThrottler] = None,
    ) -> Dict[str, Any]:
        throttler = throttler or cls._get_throttler_instance()
        params: Dict = {"symbol": convert_to_exchange_trading_pair(trading_pair)}

        if auth is not None:
            url = CONSTANTS.BASE_PATH_URL + CONSTANTS.SNAPSHOT_PATH_URL
            limit_id = CONSTANTS.SNAPSHOT_PATH_URL
        else:
            url = CONSTANTS.BASE_PATH_URL + CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL
            limit_id = CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL
        path_url = f"{URL(url).path}?{urlencode(params)}"
        headers = auth.add_auth_to_params("get", path_url) if auth else None

        async with throttler.execute_task(limit_id):
            async with client.get(url, params=params, headers=headers) as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching Kucoin market snapshot for {trading_pair}. "
                                  f"HTTP status is {response.status}.")
                data: Dict[str, Any] = await response.json()
                return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, self._auth, self._throttler)
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
        all_symbols: List[str] = self._trading_pairs if self._trading_pairs else await self.fetch_trading_pairs()
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
        all_symbols: List[str] = self._trading_pairs if self._trading_pairs else await self.fetch_trading_pairs()
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
                    stream_type, self._tasks[stream_type][task_index].trading_pairs, self._throttler
                )
                self._tasks[stream_type][task_index].message_iterator = kucoin_msg_iterator
                async for raw_msg in kucoin_msg_iterator:
                    msg_type: str = raw_msg.get("type", "")
                    if msg_type in {"ack", "welcome", "pong"}:
                        pass
                    elif msg_type == "message":
                        if stream_type == StreamType.Depth:
                            trading_pair: str = convert_from_exchange_trading_pair(raw_msg["data"]["symbol"])
                            order_book_message: OrderBookMessage = KucoinOrderBook.diff_message_from_exchange(
                                msg=raw_msg,
                                metadata={"symbol": trading_pair})
                        else:
                            trading_pair: str = convert_from_exchange_trading_pair(raw_msg["data"]["symbol"])
                            data = raw_msg["data"]
                            order_book_message: OrderBookMessage = KucoinOrderBook.trade_message_from_exchange(
                                msg=data,
                                metadata={"symbol": trading_pair}
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
                if stream_type in self._tasks:
                    if task_index in self._tasks:
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
                trading_pairs: List[str] = (
                    self._trading_pairs if self._trading_pairs else await self.fetch_trading_pairs(self._throttler)
                )
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(
                                client, trading_pair, self._auth, self._throttler
                            )
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
