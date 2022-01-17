#!/usr/bin/env python
import asyncio
import logging
from typing import Any, Dict, List, Optional

import ujson

import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.connector.exchange.bitmart.bitmart_order_book import BitmartOrderBook
from hummingbot.connector.exchange.bitmart.bitmart_utils import convert_from_exchange_trading_pair, \
    convert_to_exchange_trading_pair, \
    convert_snapshot_message_to_order_book_row, \
    build_api_factory, \
    decompress_ws_message
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BitmartAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 10.0
    SNAPSHOT_TIMEOUT = 60 * 60  # expressed in seconds
    PING_TIMEOUT = 2.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 throttler: Optional[AsyncThrottler] = None,
                 trading_pairs: List[str] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__(trading_pairs)
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory()
        self._rest_assistant = None
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        throttler = cls._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.GET_LAST_TRADING_PRICES_PATH_URL):
            result = {}

            request = RESTRequest(
                method=RESTMethod.GET,
                url=f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_LAST_TRADING_PRICES_PATH_URL}",
            )
            rest_assistant = await build_api_factory().get_rest_assistant()
            response = await rest_assistant.call(request=request, timeout=10)

            response_json = await response.json()
            for ticker in response_json["data"]["tickers"]:
                t_pair = convert_from_exchange_trading_pair(ticker["symbol"])
                if t_pair in trading_pairs and ticker["last_price"]:
                    result[t_pair] = float(ticker["last_price"])
            return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        throttler = BitmartAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.GET_TRADING_PAIRS_PATH_URL):

            request = RESTRequest(
                method=RESTMethod.GET,
                url=f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_TRADING_PAIRS_PATH_URL}",
            )
            rest_assistant = await build_api_factory().get_rest_assistant()
            response = await rest_assistant.call(request=request, timeout=10)

            if response.status == 200:
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

            request = RESTRequest(
                method=RESTMethod.GET,
                url=f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}?size=200&symbol="
                    f"{convert_to_exchange_trading_pair(trading_pair)}",
            )
            rest_assistant = await build_api_factory().get_rest_assistant()
            response = await rest_assistant.call(request=request, timeout=10)

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
        bids, asks = convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

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
                ws: WSAssistant = await self._api_factory.get_ws_assistant()
                try:
                    await ws.connect(ws_url=CONSTANTS.WSS_URL,
                                     message_timeout=self.MESSAGE_TIMEOUT,
                                     ping_timeout=self.PING_TIMEOUT)
                except RuntimeError:
                    self.logger().info("BitMart WebSocket already connected.")

                for trading_pair in self._trading_pairs:
                    ws_message: WSRequest = WSRequest({
                        "op": "subscribe",
                        "args": [f"spot/trade:{convert_to_exchange_trading_pair(trading_pair)}"]
                    })
                    await ws.send(ws_message)
                while True:
                    try:
                        async for raw_msg in ws.iter_messages():
                            messages = decompress_ws_message(raw_msg.data)
                            if messages is None:
                                continue

                            messages = ujson.loads(messages)

                            if "errorCode" in messages.keys() or \
                               "data" not in messages.keys() or \
                               "table" not in messages.keys():
                                continue

                            if messages["table"] != "spot/trade":
                                # Not a trade message
                                continue

                            for msg in messages["data"]:        # data is a list
                                msg_timestamp: float = float(msg["s_t"] * 1000)
                                t_pair = convert_from_exchange_trading_pair(msg["symbol"])

                                trade_msg: OrderBookMessage = BitmartOrderBook.trade_message_from_exchange(
                                    msg=msg,
                                    timestamp=msg_timestamp,
                                    metadata={"trading_pair": t_pair})

                                output.put_nowait(trade_msg)
                            break
                    except asyncio.exceptions.TimeoutError:
                        # Check whether connection is really dead
                        await ws.ping()
            except asyncio.CancelledError:
                raise
            except asyncio.exceptions.TimeoutError:
                self.logger().warning("WebSocket ping timed out. Going to reconnect...")
                await ws.disconnect()
                await asyncio.sleep(30.0)
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await ws.disconnect()
                await self._sleep(5.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel(all messages are snapshots)
        """
        while True:
            try:
                ws: WSAssistant = await self._api_factory.get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.WSS_URL,
                                 message_timeout=self.MESSAGE_TIMEOUT,
                                 ping_timeout=self.PING_TIMEOUT)

                for trading_pair in self._trading_pairs:
                    ws_message: WSRequest = WSRequest({
                        "op": "subscribe",
                        "args": [f"spot/depth400:{convert_to_exchange_trading_pair(trading_pair)}"]
                    })
                    await ws.send(ws_message)

                while True:
                    try:
                        async for raw_msg in ws.iter_messages():
                            messages = decompress_ws_message(raw_msg.data)
                            if messages is None:
                                continue

                            messages = ujson.loads(messages)

                            if "errorCode" in messages.keys() or \
                               "data" not in messages.keys() or \
                               "table" not in messages.keys():
                                continue

                            if messages["table"] != "spot/depth5":
                                # Not an order book message
                                continue

                            for msg in messages["data"]:        # data is a list
                                msg_timestamp: float = float(msg["ms_t"])
                                t_pair = convert_from_exchange_trading_pair(msg["symbol"])

                                snapshot_msg: OrderBookMessage = BitmartOrderBook.snapshot_message_from_exchange(
                                    msg=msg,
                                    timestamp=msg_timestamp,
                                    metadata={"trading_pair": t_pair}
                                )
                                output.put_nowait(snapshot_msg)
                        break
                    except asyncio.exceptions.TimeoutError:
                        # Check whether connection is really dead
                        await ws.ping()
            except asyncio.CancelledError:
                raise
            except asyncio.exceptions.TimeoutError:
                self.logger().warning("WebSocket ping timed out. Going to reconnect...")
                await ws.disconnect()
                await asyncio.sleep(30.0)
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                await ws.disconnect()
                await self._sleep(30.0)
            finally:
                await ws.disconnect()

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
