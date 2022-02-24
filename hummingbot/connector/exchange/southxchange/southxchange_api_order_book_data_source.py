#!/usr/bin/env python
import asyncio
import logging
import aiohttp
import websockets
import ujson
import time
import pandas as pd
from dateutil import parser
from typing import Optional, List, Dict, Any, AsyncIterable
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.southxchange.southxchange_active_order_tracker import SouthXchangeActiveOrderTracker
from hummingbot.connector.exchange.southxchange.southxchange_order_book import SouthXchangeOrderBook
from hummingbot.connector.exchange.southxchange.southxchange_utils import convert_to_exchange_trading_pair, _get_throttler_instance_SX
from hummingbot.connector.exchange.southxchange.southxchange_constants import EXCHANGE_NAME, PUBLIC_WS_URL, REST_URL, PONG_PAYLOAD, RATE_LIMITS
from hummingbot.connector.exchange.southxchange.southxchange_utils import time_to_num, convert_bookWebSocket_to_bookApi, get_market_id
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


class SouthxchangeAPIOrderBookDataSource(OrderBookTrackerDataSource):
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

    def __init__(self, trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}
        self._idMarket = get_market_id(trading_pairs=trading_pairs)

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(RATE_LIMITS)
        return throttler

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str], client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None) -> Dict[str, float]:
        result = {}
        for trading_pair in trading_pairs:
            client = client or cls._get_session_instance()
            throttler = throttler or _get_throttler_instance_SX()
            async with throttler.execute_task("SXC"):
                resp = await client.get(f"{REST_URL}trades/{convert_to_exchange_trading_pair(trading_pair)}")
                if resp.status != 200:
                    raise IOError(
                        f"Error fetching last traded prices at {EXCHANGE_NAME}. "
                        f"HTTP status is {resp.status}."
                    )
                data: List[str] = await resp.json()
                if data.__len__() < 1:
                    continue
                # last trade is the most recent trade
                result[trading_pair] = float(data[-1].get("Price"))
        return result

    @staticmethod
    async def fetch_id_trading_pairs(trading_pair: str, client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None) -> int:
        client = client or SouthxchangeAPIOrderBookDataSource._get_session_instance()
        throttler = throttler = throttler or _get_throttler_instance_SX()
        async with throttler.execute_task("SXC"):
            resp = await client.get(f"{REST_URL}markets")
            if resp.status != 200:
                # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                return []
            data: Dict[str, Dict[str, Any]] = await resp.json()
            for item in data:
                if (f"{item[0]}-{item[1]}") == trading_pair[0]:
                    return item[2]
            return 0

    @staticmethod
    async def fetch_trading_pairs(client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None) -> List[str]:
        client = client or SouthxchangeAPIOrderBookDataSource._get_session_instance()
        throttler = throttler or SouthxchangeAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task("SXC"):
            resp = await client.get(f"{REST_URL}markets")
            if resp.status != 200:
                # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                return []

            data: Dict[str, Dict[str, Any]] = await resp.json()
            return [(f"{item[0]}-{item[1]}") for item in data]

    @staticmethod
    async def get_order_book_data(trading_pair: str, client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None) -> Dict[str, any]:
        """
        Modify SX
        Get whole orderbook
        """
        client = client or SouthxchangeAPIOrderBookDataSource._get_session_instance()
        throttler = throttler = throttler or _get_throttler_instance_SX()
        async with throttler.execute_task("SXC"):
            textUrl = f"{REST_URL}book/{convert_to_exchange_trading_pair(trading_pair)}"
            resp = await client.get(textUrl)
            if resp.status != 200:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {EXCHANGE_NAME}. "
                    f"HTTP status is {resp.status}."
                )
            data: List[Dict[str, Any]] = await safe_gather(resp.json())
            item = data[0]
            if item == "":
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {EXCHANGE_NAME}. "
                    f"Error is {data}."
                )
            return item

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_msg: OrderBookMessage = SouthXchangeOrderBook.snapshot_message_from_exchange(
            snapshot,
            get_tracking_nonce(),
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: SouthXchangeActiveOrderTracker = SouthXchangeActiveOrderTracker()
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
                    "k": "subscribe",
                    "v": self._idMarket
                }
                async with websockets.connect(PUBLIC_WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    await ws.send(ujson.dumps(payload))

                    async for raw_msg in self._inner_messages(ws):
                        try:
                            msg = ujson.loads(raw_msg)
                            if msg is None:
                                continue
                            if msg.get("k") == "trade":
                                """
                                Modify - SouthXchange
                                """
                                for trade in msg.get("v"):
                                    tradeTimeStr = str(f"{parser.parse(trade.get('d')).hour}:{parser.parse(trade.get('d')).minute}:{parser.parse(trade.get('d')).second}")
                                    trade_timestamp: int = time_to_num(tradeTimeStr)
                                    trade_msg: OrderBookMessage = SouthXchangeOrderBook.trade_message_from_exchange(
                                        trade,
                                        trade_timestamp,
                                        metadata={"trading_pair": trading_pairs}
                                    )
                                    output.put_nowait(trade_msg)
                            else:
                                continue
                        except Exception:
                            raise
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().debug(str(e))
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs = ",".join(list(
                    map(lambda trading_pair: convert_to_exchange_trading_pair(trading_pair), self._trading_pairs)
                ))
                payload = {
                    "k": "subscribe",
                    "v": self._idMarket
                }
                async with websockets.connect(PUBLIC_WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    await ws.send(ujson.dumps(payload))

                    async for raw_msg in self._inner_messages(ws):
                        try:
                            msg = ujson.loads(raw_msg)
                            if msg is None:
                                continue
                            if (msg.get("k") == "bookdelta") or (msg.get("k") == "book"):
                                msg_timestamp: int = get_tracking_nonce()
                                list_itemsBook = convert_bookWebSocket_to_bookApi(msg.get("v"))
                                order_book_message: OrderBookMessage = SouthXchangeOrderBook.diff_message_from_exchange(
                                    list_itemsBook,
                                    msg_timestamp,
                                    metadata={"trading_pair": trading_pairs}
                                )
                                output.put_nowait(order_book_message)
                            else:
                                """
                                Modify - SouthXchange
                                """
                                for trade in msg.get("v"):
                                    tradeTimeStr = str(f"{parser.parse(trade.get('d')).hour}:{parser.parse(trade.get('d')).minute}:{parser.parse(trade.get('d')).second}")
                                    trade_timestamp: int = time_to_num(tradeTimeStr)
                                    trade_msg: OrderBookMessage = SouthXchangeOrderBook.trade_message_from_exchange(
                                        trade,
                                        trade_timestamp,
                                        metadata={"trading_pair": trading_pairs}
                                    )
                                    output.put_nowait(trade_msg)
                        except Exception:
                            raise
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().debug(str(e))
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 60 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Modify SX
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                        snapshot_msg: OrderBookMessage = SouthXchangeOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            get_tracking_nonce(),
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
        ws: websockets.WebSocketClientProtocol
    ) -> AsyncIterable[str]:
        try:
            while True:
                try:
                    raw_msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield raw_msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = ws.send(ujson.dumps(PONG_PAYLOAD))
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                        self._last_recv_time = time.time()
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except websockets.ConnectionClosed:
            return
        finally:
            await ws.close()
