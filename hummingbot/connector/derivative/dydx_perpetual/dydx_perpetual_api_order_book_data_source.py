#!/usr/bin/env python

import asyncio
import logging
import time

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Any

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book import DydxPerpetualOrderBook
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_utils import build_api_factory
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
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

    def __init__(self, trading_pairs: List[str] = None, api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__(trading_pairs)

        self._api_factory: WebAssistantsFactory = api_factory or build_api_factory()
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        api_factory = build_api_factory()
        rest_assistant = await api_factory.get_rest_assistant()

        retval = {}
        for pair in trading_pairs:
            url = f"{CONSTANTS.DYDX_REST_URL}{CONSTANTS.TICKER_URL}/{pair}"
            request = RESTRequest(
                method=RESTMethod.GET,
                url=url,
            )
            resp = await rest_assistant.call(request=request)
            resp_json = await resp.json()
            retval[pair] = float(resp_json["markets"][pair]["close"])
        return retval

    @classmethod
    async def fetch_trading_pairs(cls) -> List[str]:
        try:
            api_factory = build_api_factory()
            rest_assistant = await api_factory.get_rest_assistant()

            url = f"{CONSTANTS.DYDX_REST_URL}{CONSTANTS.MARKETS_URL}"
            request = RESTRequest(
                method=RESTMethod.GET,
                url=url,
            )

            response = await rest_assistant.call(request=request)
            if response.status == 200:
                all_trading_pairs: Dict[str, Any] = await response.json()
                valid_trading_pairs: list = []
                for key, val in all_trading_pairs["markets"].items():
                    if val["status"] == "ONLINE":
                        valid_trading_pairs.append(key)
                return valid_trading_pairs
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for dydx trading pairs
            pass

        return []

    @property
    def order_book_class(self) -> DydxPerpetualOrderBook:
        return DydxPerpetualOrderBook

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def get_snapshot(self, trading_pair: str) -> Dict[str, any]:
        rest_assistant = await self._get_rest_assistant()
        url = f"{CONSTANTS.DYDX_REST_URL}{CONSTANTS.SNAPSHOT_URL}/{trading_pair}"
        request = RESTRequest(
            method=RESTMethod.GET,
            url=url,
        )
        response = await rest_assistant.call(request=request)

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
            snapshot, snapshot_timestamp, metadata={"id": trading_pair, "rest": True}
        )
        order_book: OrderBook = self.order_book_create_function()
        bids = [
            ClientOrderBookRow(Decimal(bid["price"]), Decimal(bid["amount"]), snapshot_msg.update_id)
            for bid in snapshot_msg.bids
        ]
        asks = [
            ClientOrderBookRow(Decimal(ask["price"]), Decimal(ask["amount"]), snapshot_msg.update_id)
            for ask in snapshot_msg.asks
        ]
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for pair in self._trading_pairs:
                subscribe_orderbook_request: WSRequest = WSRequest({
                    "type": "subscribe",
                    "channel": self.ORDERBOOK_CHANNEL,
                    "id": pair,
                })
                subscribe_trade_request: WSRequest = WSRequest({
                    "type": "subscribe",
                    "channel": self.TRADE_CHANNEL,
                    "id": pair,
                })
                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_trade_request)
            self.logger().info("Subscribed to public orderbook and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.DYDX_WS_URL, ping_timeout=self.HEARTBEAT_INTERVAL)
                await self._subscribe_channels(ws)

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    channel = data.get("channel", "")
                    if channel in [self.ORDERBOOK_CHANNEL, self.TRADE_CHANNEL]:
                        self._message_queue[channel].put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

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
                                trade_msg: OrderBookMessage = DydxPerpetualOrderBook.trade_message_from_exchange(
                                    data, msg
                                )
                                output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with WebSocket connection. Retrying after 30 seconds...", exc_info=True
                )
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
                        order_msg: OrderBookMessage = DydxPerpetualOrderBook.diff_message_from_exchange(
                            msg["contents"], ts, msg
                        )
                        output.put_nowait(order_msg)
                    elif msg["type"] == "subscribed":
                        msg["rest"] = False
                        ts = time.time()
                        order_msg: OrderBookMessage = DydxPerpetualOrderBook.snapshot_message_from_exchange(
                            msg["contents"], ts, msg
                        )
                        output.put_nowait(order_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with WebSocket connection. Retrying after 30 seconds...", exc_info=True
                )
                await self._sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
