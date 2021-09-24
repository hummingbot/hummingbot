#!/usr/bin/env python
import asyncio
import logging
import aiohttp
import ujson
import websockets
import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS

from typing import Optional, List, Dict, Any, AsyncIterable
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.bitmart import bitmart_utils
from hummingbot.connector.exchange.bitmart.bitmart_order_book import BitmartOrderBook
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BitmartAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 10.0
    SNAPSHOT_TIMEOUT = 60 * 60  # expressed in seconds
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, throttler: Optional[AsyncThrottler] = None, trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._throttler = throttler or self._get_throttler_instance()
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        throttler = cls._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.GET_LAST_TRADING_PRICES_PATH_URL):
            result = {}
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_LAST_TRADING_PRICES_PATH_URL}", timeout=10) as response:
                    response_json = await response.json()
                    for ticker in response_json["data"]["tickers"]:
                        t_pair = bitmart_utils.convert_from_exchange_trading_pair(ticker["symbol"])
                        if t_pair in trading_pairs and ticker["last_price"]:
                            result[t_pair] = float(ticker["last_price"])
            return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        throttler = BitmartAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.GET_TRADING_PAIRS_PATH_URL):
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_TRADING_PAIRS_PATH_URL}", timeout=10) as response:
                    if response.status == 200:
                        from hummingbot.connector.exchange.bitmart.bitmart_utils import \
                            convert_from_exchange_trading_pair
                        try:
                            response_json: Dict[str, Any] = await response.json()
                            return [convert_from_exchange_trading_pair(symbol) for symbol in response_json["data"]["symbols"]]
                        except Exception:
                            pass
                            # Do nothing if the request fails -- there will be no autocomplete for bitmart trading pairs
                    return []

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        throttler = BitmartAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.GET_ORDER_BOOK_PATH_URL):
            async with aiohttp.ClientSession() as client:
                async with client.get(
                    f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}?size=200&symbol="
                    f"{bitmart_utils.convert_to_exchange_trading_pair(trading_pair)}"
                ) as response:
                    if response.status != 200:
                        raise IOError(
                            f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                            f"HTTP status is {response.status}."
                        )

                    orderbook_data: Dict[str, Any] = await response.json()
                    orderbook_data = orderbook_data["data"]

                    return orderbook_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = float(snapshot["timestamp"])
        snapshot_msg: OrderBookMessage = BitmartOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        bids, asks = bitmart_utils.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    msg = bitmart_utils.decompress_ws_message(msg)
                    yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except websockets.exceptions.ConnectionClosed:
            return
        finally:
            await ws.close()

    async def _create_websocket_connection(self) -> websockets.WebSocketClientProtocol:
        """
        Initialize WebSocket client
        """
        try:
            ws = await websockets.connect(uri=CONSTANTS.WSS_URL)
            return ws
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network(f"Unexpected error occurred during {CONSTANTS.EXCHANGE_NAME} WebSocket Connection "
                                  f"({ex})")
            raise

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                ws: websockets.WebSocketClientProtocol = await self._create_websocket_connection()

                for trading_pair in self._trading_pairs:
                    params: Dict[str, Any] = {
                        "op": "subscribe",
                        "args": [f"spot/trade:{bitmart_utils.convert_to_exchange_trading_pair(trading_pair)}"]
                    }
                    await ws.send(ujson.dumps(params))

                async for raw_msg in self._inner_messages(ws):
                    messages = ujson.loads(raw_msg)
                    if messages is None:
                        continue
                    if "errorCode" in messages or "data" not in messages:
                        # Error/Unrecognized response from "depth400" channel
                        continue

                    for msg in messages["data"]:        # data is a list
                        msg_timestamp: float = float(msg["s_t"] * 1000)
                        t_pair = bitmart_utils.convert_from_exchange_trading_pair(msg["symbol"])

                        trade_msg: OrderBookMessage = BitmartOrderBook.trade_message_from_exchange(
                            msg=msg,
                            timestamp=msg_timestamp,
                            metadata={"trading_pair": t_pair})
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await self._sleep(5.0)
            finally:
                await ws.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel(all messages are snapshots)
        """
        while True:
            try:
                ws: websockets.WebSocketClientProtocol = await self._create_websocket_connection()

                for trading_pair in self._trading_pairs:
                    params: Dict[str, Any] = {
                        "op": "subscribe",
                        "args": [f"spot/depth400:{bitmart_utils.convert_to_exchange_trading_pair(trading_pair)}"]
                    }
                    await ws.send(ujson.dumps(params))

                async for raw_msg in self._inner_messages(ws):
                    messages = ujson.loads(raw_msg)
                    if messages is None:
                        continue
                    if "errorCode" in messages or "data" not in messages:
                        # Error/Unrecognized response from "depth400" channel
                        continue

                    for msg in messages["data"]:        # data is a list
                        msg_timestamp: float = float(msg["ms_t"])
                        t_pair = bitmart_utils.convert_from_exchange_trading_pair(msg["symbol"])

                        snapshot_msg: OrderBookMessage = BitmartOrderBook.snapshot_message_from_exchange(
                            msg=msg,
                            timestamp=msg_timestamp,
                            metadata={"trading_pair": t_pair}
                        )
                        output.put_nowait(snapshot_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                await self._sleep(30.0)
            finally:
                await ws.close()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            await self._sleep(self.SNAPSHOT_TIMEOUT)
            try:
                for trading_pair in self._trading_pairs:
                    snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                    snapshot_timestamp: float = float(snapshot["timestamp"])
                    snapshot_msg: OrderBookMessage = BitmartOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    output.put_nowait(snapshot_msg)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error occured listening for orderbook snapshots. Retrying in 5 secs...", exc_info=True)
                await self._sleep(5.0)
