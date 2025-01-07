#!/usr/bin/env python
import asyncio
import logging
from collections import defaultdict
import time
from typing import Any, Dict, List, Optional

import aiohttp
import pandas as pd

from hummingbot.connector.exchange.xago_io.xago_io_auth import XagoIoAuth
import hummingbot.connector.exchange.xago_io.xago_io_constants as CONSTANTS
import hummingbot.connector.exchange.xago_io.xago_io_utils as xago_io_utils
from hummingbot.connector.exchange.xago_io.xago_io_order_book import XagoIoOrderBook
from hummingbot.connector.exchange.xago_io.xago_io_utils import ms_timestamp_to_s
from hummingbot.connector.exchange.xago_io.xago_io_websocket import XagoIoWebsocket
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.xago_io.xago_io_utils import convert_from_exchange_trading_pair


class XagoIoAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0
    ORDER_BOOK_SNAPSHOT_DELAY = 60 * 60  # expressed in seconds

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        trading_pairs: List[str] = None,
        auth: XagoIoAuth = None,
        shared_client: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._auth = auth
        self._shared_client = shared_client
        self._snapshot_msg: Dict[str, any] = {}
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    def _get_throttler_instance(cls):
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        result = {}
        async with aiohttp.ClientSession() as client:
            for trading_pair in trading_pairs:
            #     # if trading pair string includes USD, get the spot rate from Xago rate source
            #     # this is for the Dashboard (and backend=-api) which fetches USD based rates for Portfolio calculations
                if "USDT" in trading_pair:
                        resp = await client.get(f"{CONSTANTS.EXCHANGE_REST_URL}/prices/current")
                        resp_json = await resp.json()
                        base_quote_currencies = xago_io_utils.get_base_quote_currencies(trading_pair)
                        quote_buy_key = f"buy{base_quote_currencies['base']}"
                        result[trading_pair] = float(next((item['price'] for item in resp_json[quote_buy_key] if item['currency'] == "USD"), 0))
                else:
                    resp = await client.get(f"{CONSTANTS.EXCHANGE_REST_URL}/prices/ticker" + "?currencyPair=" + xago_io_utils.convert_to_exchange_trading_pair(trading_pair))
                    resp_json = await resp.json()
                    result[trading_pair] = resp_json['lastFillPrice']
            return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        """
        Retrieves active trading pairs using the exchange's REST API.
        :param throttler: Optional AsyncThrottler used to throttle the API request
        """
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{CONSTANTS.EXCHANGE_REST_URL}/currencypairs", timeout=10) as response:
                if response.status != 200:
                    return []
                try:
                    data: Dict[str, Any] = await response.json()
                    return [
                        convert_from_exchange_trading_pair(item["pair"]) for item in data["currencyPairs"] if item["activeStatus"] == True
                    ]
                except Exception as e:
                    pass
                
                return []

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        async with aiohttp.ClientSession() as client:
            try:
                url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.GET_ORDER_BOOK_PATH_URL + xago_io_utils.convert_to_exchange_trading_pair(trading_pair)
                orderbook_response = await client.get(url)
                if orderbook_response.status != 200:
                    raise IOError(
                        f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                        f"HTTP status is {orderbook_response.status}."
                    )
                orderbook_data: List[Dict[str, Any]] = await safe_gather(orderbook_response.json())
                orderbook_data = orderbook_data[0]
                
                return orderbook_data

            except Exception as e:
                print(e)

    def _get_shared_client(self):
        """
        Retrieves the shared aiohttp.ClientSession. If no shared client is provided, create a new ClientSession.
        """
        if not self._shared_client:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = XagoIoOrderBook.snapshot_message_from_exchange_rest(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _create_websocket_connection(self) -> XagoIoWebsocket:
        """
        Initialize sets up the websocket connection with a XagoIoWebsocket object.
        """
        try:
            ws = XagoIoWebsocket(auth=self._auth, shared_client=self._shared_client)
            await ws.connect()
            return ws
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured connecting to {CONSTANTS.EXCHANGE_NAME} WebSocket API. "
                                  f"({e})")
            raise

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws = await self._create_websocket_connection()
                await ws.subscribe_to_order_book_streams(self._trading_pairs)

                async for msg in ws.iter_messages():
                    if msg.get("type") == "info":
                        continue
                    event = msg.get("type", "").split('.')[0]  # Extract the base event type
                    if event in XagoIoWebsocket.ORDERBOOK_SUBSCRIPTION_LIST:
                        self._message_queue[event].put_nowait(msg)
            except asyncio.CancelledError as e:
                print(e)
                raise
            except Exception as e:
                self.logger().error(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        msg_queue = self._message_queue[XagoIoWebsocket.DIFF_CHANNEL_ID]
        while True:
            try:
                payload = await msg_queue.get()
                if len(payload["data"]) == 0:
                    continue

                order_book_data = payload["data"]
                trading_pair = xago_io_utils.convert_from_exchange_trading_pair(payload["type"].split('.')[1])
                timestamp: float = order_book_data["timestamp"]

                orderbook_msg: OrderBookMessage = XagoIoOrderBook.diff_message_from_exchange(
                    order_book_data,
                    timestamp,
                    metadata={"trading_pair": trading_pair},
                )
                output.put_nowait(orderbook_msg)

            except asyncio.CancelledError as e:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error parsing order book diff payload. Payload: {payload}, Error: {e}",
                    exc_info=True,
                )
                await self._sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        msg_queue = self._message_queue[XagoIoWebsocket.SNAPSHOT_CHANNEL_ID]
        while True:
            try:
                payload = await msg_queue.get()
                if len(payload["data"]) == 0:
                    continue

                order_book_data = payload["data"]["orderbook"]
                trading_pair = xago_io_utils.convert_from_exchange_trading_pair(payload["type"].split('.')[1])
                timestamp: float = payload["data"]["timestamp"]

                orderbook_msg: OrderBookMessage = XagoIoOrderBook.snapshot_message_from_exchange(
                    order_book_data,
                    timestamp,
                    metadata={"trading_pair": trading_pair, "sequence": payload["data"]["sequence"]},
                )
                output.put_nowait(orderbook_msg)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error parsing order book diff payload. Payload: {payload}, Error: {e}",
                    exc_info=True,
                )
                await self._sleep(30.0)
