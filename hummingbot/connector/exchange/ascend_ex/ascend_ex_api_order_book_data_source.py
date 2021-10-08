#!/usr/bin/env python
import asyncio
import logging
import aiohttp
import ujson
import time
import pandas as pd

from typing import Optional, List, Dict, Any, AsyncIterable
from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.ascend_ex.ascend_ex_active_order_tracker import AscendExActiveOrderTracker
from hummingbot.connector.exchange.ascend_ex.ascend_ex_order_book import AscendExOrderBook
from hummingbot.connector.exchange.ascend_ex.ascend_ex_utils import convert_from_exchange_trading_pair, convert_to_exchange_trading_pair
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS


class AscendExAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0
    PING_TIMEOUT = 15.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, shared_client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None, trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._shared_client = shared_client or self._get_session_instance()
        self._throttler = throttler or self._get_throttler_instance()
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)

    @classmethod
    async def get_last_traded_prices(
        cls, trading_pairs: List[str], client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None
    ) -> Dict[str, float]:
        result = {}

        for trading_pair in trading_pairs:
            client = client or cls._get_session_instance()
            throttler = throttler or cls._get_throttler_instance()
            async with throttler.execute_task(CONSTANTS.TRADES_PATH_URL):
                resp = await client.get(
                    f"{CONSTANTS.REST_URL}/{CONSTANTS.TRADES_PATH_URL}"
                    f"?symbol={convert_to_exchange_trading_pair(trading_pair)}"
                )
            if resp.status != 200:
                raise IOError(
                    f"Error fetching last traded prices at {CONSTANTS.EXCHANGE_NAME}. "
                    f"HTTP status is {resp.status}."
                )

            resp_json = await resp.json()
            if resp_json.get("code") != 0:
                raise IOError(
                    f"Error fetching last traded prices at {CONSTANTS.EXCHANGE_NAME}. "
                    f"Error is {resp_json.message}."
                )

            trades = resp_json.get("data").get("data")
            if (len(trades) == 0):
                continue

            # last trade is the most recent trade
            result[trading_pair] = float(trades[-1].get("p"))

        return result

    @staticmethod
    async def fetch_trading_pairs(client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None) -> List[str]:
        client = client or AscendExAPIOrderBookDataSource._get_session_instance()
        throttler = throttler or AscendExAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.TICKER_PATH_URL):
            resp = await client.get(f"{CONSTANTS.REST_URL}/{CONSTANTS.TICKER_PATH_URL}")

        if resp.status != 200:
            # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
            return []

        data: Dict[str, Dict[str, Any]] = await resp.json()
        return [convert_from_exchange_trading_pair(item["symbol"]) for item in data["data"]]

    @staticmethod
    async def get_order_book_data(trading_pair: str, client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        client = client or AscendExAPIOrderBookDataSource._get_session_instance()
        throttler = throttler or AscendExAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.DEPTH_PATH_URL):
            resp = await client.get(
                f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}"
                f"?symbol={convert_to_exchange_trading_pair(trading_pair)}"
            )
        if resp.status != 200:
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                f"HTTP status is {resp.status}."
            )

        data: List[Dict[str, Any]] = await safe_gather(resp.json())
        item = data[0]
        if item.get("code") != 0:
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                f"Error is {item.message}."
            )

        return item["data"]

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair, client=self._shared_client, throttler=self._throttler)
        snapshot_timestamp: float = snapshot.get("data").get("ts")
        snapshot_msg: OrderBookMessage = AscendExOrderBook.snapshot_message_from_exchange(
            snapshot.get("data"),
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: AscendExActiveOrderTracker = AscendExActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs = ",".join(list(
                    map(lambda trading_pair: convert_to_exchange_trading_pair(trading_pair), self._trading_pairs)
                ))
                payload = {
                    "op": CONSTANTS.SUB_ENDPOINT_NAME,
                    "ch": f"trades:{trading_pairs}"
                }
                async with self._shared_client.ws_connect(CONSTANTS.WS_URL) as ws:
                    ws: aiohttp.ClientWebSocketResponse = ws
                    async with self._throttler.execute_task(CONSTANTS.SUB_ENDPOINT_NAME):
                        await ws.send_json(payload)

                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if (msg is None or msg.get("m") != "trades"):
                            continue

                        trading_pair: str = convert_from_exchange_trading_pair(msg.get("symbol"))

                        for trade in msg.get("data"):
                            trade_timestamp: int = trade.get("ts")
                            trade_msg: OrderBookMessage = AscendExOrderBook.trade_message_from_exchange(
                                trade,
                                trade_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().debug(str(e))
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs = ",".join(list(
                    map(lambda trading_pair: convert_to_exchange_trading_pair(trading_pair), self._trading_pairs)
                ))
                ch = f"depth:{trading_pairs}"
                payload = {
                    "op": CONSTANTS.SUB_ENDPOINT_NAME,
                    "ch": ch
                }
                async with self._shared_client.ws_connect(CONSTANTS.WS_URL) as ws:
                    ws: aiohttp.ClientWebSocketResponse = ws
                    async with self._throttler.execute_task(CONSTANTS.SUB_ENDPOINT_NAME):
                        await ws.send_json(payload)

                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if msg is None:
                            continue
                        if msg.get("m", '') == "ping":
                            async with self._throttler.execute_task(CONSTANTS.PONG_ENDPOINT_NAME):
                                await ws.send_json(dict(op=CONSTANTS.PONG_ENDPOINT_NAME))
                        if msg.get("m", '') == "depth":
                            msg_timestamp: int = msg.get("data").get("ts")
                            trading_pair: str = convert_from_exchange_trading_pair(msg.get("symbol"))
                            order_book_message: OrderBookMessage = AscendExOrderBook.diff_message_from_exchange(
                                msg.get("data"),
                                msg_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().debug(str(e))
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair, client=self._shared_client, throttler=self._throttler)
                        snapshot_timestamp: float = snapshot.get("data").get("ts")
                        snapshot_msg: OrderBookMessage = AscendExOrderBook.snapshot_message_from_exchange(
                            snapshot.get("data"),
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above API rate limits.
                        await asyncio.sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection."
                        )
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

    async def _inner_messages(
        self,
        ws: aiohttp.ClientWebSocketResponse
    ) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    raw_msg = await asyncio.wait_for(ws.receive(), timeout=self.MESSAGE_TIMEOUT)
                    if raw_msg.type == aiohttp.WSMsgType.CLOSED:
                        raise ConnectionError
                    yield raw_msg.data
                except asyncio.TimeoutError:
                    payload = {"op": CONSTANTS.PONG_ENDPOINT_NAME}
                    pong_waiter = ws.send_json(payload)
                    async with self._throttler.execute_task(CONSTANTS.PONG_ENDPOINT_NAME):
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    self._last_recv_time = time.time()
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        finally:
            await ws.close()
