#!/usr/bin/env python

import asyncio
import logging


import hummingbot.connector.exchange.huobi.huobi_constants as CONSTANTS

from collections import defaultdict
from typing import (
    Any,
    Dict,
    List,
    Optional,
)


from hummingbot.connector.exchange.huobi.huobi_order_book import HuobiOrderBook
from hummingbot.connector.exchange.huobi.huobi_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    build_api_factory,
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse, WSRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class HuobiAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    HEARTBEAT_INTERVAL = 30.0  # seconds
    ORDER_BOOK_SNAPSHOT_DELAY = 60 * 60  # expressed in seconds

    TRADE_CHANNEL_SUFFIX = "trade.detail"
    ORDERBOOK_CHANNEL_SUFFIX = "depth.step0"

    _haobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._haobds_logger is None:
            cls._haobds_logger = logging.getLogger(__name__)
        return cls._haobds_logger

    def __init__(self,
                 trading_pairs: List[str],
                 api_factory: Optional[WebAssistantsFactory] = None,
                 ):
        super().__init__(trading_pairs)
        self._api_factory = api_factory or build_api_factory()
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        api_factory = build_api_factory()
        rest_assistant = await api_factory.get_rest_assistant()

        url = CONSTANTS.REST_URL + CONSTANTS.TICKER_URL
        request = RESTRequest(method=RESTMethod.GET,
                              url=url)
        response: RESTResponse = await rest_assistant.call(request=request)

        results = dict()
        resp_json = await response.json()
        for trading_pair in trading_pairs:
            resp_record = [o for o in resp_json["data"] if o["symbol"] == convert_to_exchange_trading_pair(trading_pair)][0]
            results[trading_pair] = float(resp_record["close"])
        return results

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            api_factory = build_api_factory()
            rest_assistant = await api_factory.get_rest_assistant()

            url = CONSTANTS.REST_URL + CONSTANTS.API_VERSION + CONSTANTS.SYMBOLS_URL
            request = RESTRequest(method=RESTMethod.GET,
                                  url=url)
            response: RESTResponse = await rest_assistant.call(request=request)

            if response.status == 200:
                all_symbol_infos: Dict[str, Any] = await response.json()
                return [f"{symbol_info['base-currency']}-{symbol_info['quote-currency']}".upper()
                        for symbol_info in all_symbol_infos["data"]
                        if symbol_info["state"] == "online"]

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for huobi trading pairs
            pass

        return []

    async def get_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        rest_assistant = await self._get_rest_assistant()
        url = CONSTANTS.REST_URL + CONSTANTS.DEPTH_URL
        # when type is set to "step0", the default value of "depth" is 150
        params: Dict = {"symbol": convert_to_exchange_trading_pair(trading_pair), "type": "step0"}
        request = RESTRequest(method=RESTMethod.GET,
                              url=url,
                              params=params)
        response: RESTResponse = await rest_assistant.call(request=request)

        if response.status != 200:
            raise IOError(f"Error fetching Huobi market snapshot for {trading_pair}. "
                          f"HTTP status is {response.status}.")
        snapshot_data: Dict[str, Any] = await response.json()
        return snapshot_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair)
        timestamp = snapshot["tick"]["ts"]
        snapshot_msg: OrderBookMessage = HuobiOrderBook.snapshot_message_from_exchange(
            msg=snapshot,
            timestamp=timestamp,
            metadata={"trading_pair": trading_pair},
        )
        order_book: OrderBook = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                subscribe_orderbook_request: WSRequest = WSRequest({
                    "sub": f"market.{convert_to_exchange_trading_pair(trading_pair)}.depth.step0",
                    "id": convert_to_exchange_trading_pair(trading_pair)
                })
                subscribe_trade_request: WSRequest = WSRequest({
                    "sub": f"market.{convert_to_exchange_trading_pair(trading_pair)}.trade.detail",
                    "id": convert_to_exchange_trading_pair(trading_pair)
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
                await ws.connect(ws_url=CONSTANTS.WS_PUBLIC_URL, ping_timeout=self.HEARTBEAT_INTERVAL)
                await self._subscribe_channels(ws)

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if "subbed" in data:
                        continue
                    if "ping" in data:
                        ping_request = WSRequest(payload={
                            "pong": data["ping"]
                        })
                        await ws.send(request=ping_request)
                    channel = data.get("ch", "")
                    if channel.endswith(self.TRADE_CHANNEL_SUFFIX):
                        self._message_queue[self.TRADE_CHANNEL_SUFFIX].put_nowait(data)
                    if channel.endswith(self.ORDERBOOK_CHANNEL_SUFFIX):
                        self._message_queue[self.ORDERBOOK_CHANNEL_SUFFIX].put_nowait(data)
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
        message_queue = self._message_queue[self.TRADE_CHANNEL_SUFFIX]
        while True:
            try:
                msg: Dict[str, Any] = await message_queue.get()
                trading_pair = msg["ch"].split(".")[1]
                timestamp = msg["tick"]["ts"]
                for data in msg["tick"]["data"]:
                    trade_message: OrderBookMessage = HuobiOrderBook.trade_message_from_exchange(
                        msg=data,
                        timestamp=timestamp,
                        metadata={"trading_pair": convert_from_exchange_trading_pair(trading_pair)}
                    )
                    output.put_nowait(trade_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        message_queue = self._message_queue[self.ORDERBOOK_CHANNEL_SUFFIX]
        while True:
            try:
                msg: Dict[str, Any] = await message_queue.get()
                timestamp = msg["tick"]["ts"]
                order_book_message: OrderBookMessage = HuobiOrderBook.diff_message_from_exchange(
                    msg=msg,
                    timestamp=timestamp
                )
                output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            await self._sleep(self.ORDER_BOOK_SNAPSHOT_DELAY)
            try:
                for trading_pair in self._trading_pairs:
                    snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair)
                    snapshot_message: OrderBookMessage = HuobiOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        timestamp=snapshot["tick"]["ts"],
                        metadata={"trading_pair": trading_pair},
                    )
                    output.put_nowait(snapshot_message)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error listening for orderbook snapshots. Retrying in 5 secs...", exc_info=True)
                await self._sleep(5.0)
