#!/usr/bin/env python

import asyncio
import logging
import time
from decimal import Decimal
from typing import AsyncIterable, Dict, List, Optional

import pandas as pd

from hummingbot.connector.exchange.coinbase_pro import coinbase_pro_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_active_order_tracker import CoinbaseProActiveOrderTracker
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book import CoinbaseProOrderBook
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book_tracker_entry import (
    CoinbaseProOrderBookTrackerEntry
)
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_utils import (
    CoinbaseProRESTRequest,
    build_coinbase_pro_web_assistant_factory
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

MAX_RETRIES = 20
NaN = float("nan")


class CoinbaseProAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _cbpaobds_logger: Optional[HummingbotLogger] = None
    _shared_web_assistants_factory: Optional[WebAssistantsFactory] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpaobds_logger is None:
            cls._cbpaobds_logger = logging.getLogger(__name__)
        return cls._cbpaobds_logger

    def __init__(
        self,
        trading_pairs: Optional[List[str]] = None,
        web_assistants_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__(trading_pairs)
        self._web_assistants_factory = web_assistants_factory or build_coinbase_pro_web_assistant_factory()
        self._rest_assistant = None

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, Decimal]:
        tasks = [cls.get_last_traded_price(t_pair) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str) -> Decimal:
        factory = build_coinbase_pro_web_assistant_factory()
        rest_assistant = await factory.get_rest_assistant()
        endpoint = f"{CONSTANTS.PRODUCTS_PATH_URL}/{trading_pair}/ticker"
        request = CoinbaseProRESTRequest(RESTMethod.GET, endpoint=endpoint)
        response = await rest_assistant.call(request)
        resp_json = await response.json()
        return Decimal(resp_json["price"])

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        trading_pair_list = []
        try:
            factory = build_coinbase_pro_web_assistant_factory()
            rest_assistant = await factory.get_rest_assistant()
            request = CoinbaseProRESTRequest(RESTMethod.GET, endpoint=CONSTANTS.PRODUCTS_PATH_URL)
            response = await rest_assistant.call(request)
            if response.status == 200:
                markets = await response.json()
                raw_trading_pairs: List[str] = list(map(lambda details: details.get('id'), markets))
                trading_pair_list: List[str] = []
                for raw_trading_pair in raw_trading_pairs:
                    trading_pair_list.append(raw_trading_pair)
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for coinbase trading pairs
            pass
        return trading_pair_list

    @staticmethod
    async def get_snapshot(rest_assistant: RESTAssistant, trading_pair: str) -> Dict[str, any]:
        """
        Fetches order book snapshot for a particular trading pair from the rest API
        :returns: Response from the rest API
        """
        endpoint = f"{CONSTANTS.PRODUCTS_PATH_URL}/{trading_pair}/book?level=3"
        request = CoinbaseProRESTRequest(RESTMethod.GET, endpoint=endpoint)
        response = await rest_assistant.call(request)
        if response.status != 200:
            raise IOError(f"Error fetching Coinbase Pro market snapshot for {trading_pair}. "
                          f"HTTP status is {response.status}.")
        response_data = await response.json()
        return response_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        rest_assistant = await self._get_rest_assistant()
        snapshot: Dict[str, any] = await self.get_snapshot(rest_assistant, trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = CoinbaseProOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        active_order_tracker: CoinbaseProActiveOrderTracker = CoinbaseProActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        """
        *required
        Initializes order books and order book trackers for the list of trading pairs
        returned by `self.get_trading_pairs`
        :returns: A dictionary of order book trackers for each trading pair
        """
        # Get the currently active markets
        trading_pairs: List[str] = self._trading_pairs
        retval: Dict[str, OrderBookTrackerEntry] = {}
        rest_assistant = await self._get_rest_assistant()

        number_of_pairs: int = len(trading_pairs)
        for index, trading_pair in enumerate(trading_pairs):
            try:
                snapshot: Dict[str, any] = await self.get_snapshot(rest_assistant, trading_pair)
                snapshot_timestamp: float = time.time()
                snapshot_msg: OrderBookMessage = CoinbaseProOrderBook.snapshot_message_from_exchange(
                    snapshot,
                    snapshot_timestamp,
                    metadata={"trading_pair": trading_pair}
                )
                order_book: OrderBook = self.order_book_create_function()
                active_order_tracker: CoinbaseProActiveOrderTracker = CoinbaseProActiveOrderTracker()
                bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                retval[trading_pair] = CoinbaseProOrderBookTrackerEntry(
                    trading_pair,
                    snapshot_timestamp,
                    order_book,
                    active_order_tracker
                )
                self.logger().info(f"Initialized order book for {trading_pair}. "
                                   f"{index+1}/{number_of_pairs} completed.")
                await self._sleep(0.6)
            except IOError:
                self.logger().network(
                    f"Error getting snapshot for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg=f"Error getting snapshot for {trading_pair}. Check network connection."
                )
            except Exception:
                self.logger().error(f"Error initializing order book for {trading_pair}. ", exc_info=True)
        return retval

    async def _iter_messages(self, ws: WSAssistant) -> AsyncIterable[Dict]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            async for response in ws.iter_messages():
                msg = response.data
                yield msg
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
        finally:
            await ws.disconnect()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Trade messages are received from the order book web socket
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to diff channel via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                ws_assistant = await self._web_assistants_factory.get_ws_assistant()
                await ws_assistant.connect(CONSTANTS.WS_URL, message_timeout=CONSTANTS.WS_MESSAGE_TIMEOUT)
                subscribe_payload = {
                    "type": "subscribe",
                    "product_ids": trading_pairs,
                    "channels": [CONSTANTS.FULL_CHANNEL_NAME]
                }
                subscribe_request = WSRequest(payload=subscribe_payload)
                await ws_assistant.subscribe(subscribe_request)
                async for msg in self._iter_messages(ws_assistant):
                    msg_type: str = msg.get("type", None)
                    if msg_type is None:
                        raise ValueError(f"Coinbase Pro Websocket message does not contain a type - {msg}")
                    elif msg_type == "error":
                        raise ValueError(f"Coinbase Pro Websocket received error message - {msg['message']}")
                    elif msg_type in ["open", "match", "change", "done"]:
                        if msg_type == "done" and "price" not in msg:
                            # done messages with no price are completed market orders which can be ignored
                            continue
                        order_book_message: OrderBookMessage = CoinbaseProOrderBook.diff_message_from_exchange(msg)
                        output.put_nowait(order_book_message)
                    elif msg_type in ["received", "activate", "subscriptions"]:
                        # these messages are not needed to track the order book
                        continue
                    else:
                        raise ValueError(f"Unrecognized Coinbase Pro Websocket message received - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error with WebSocket connection."
                                    f" Retrying in {CONSTANTS.REST_API_LIMIT_COOLDOWN} seconds."
                                    f" Check network connection."
                )
                await self._sleep(CONSTANTS.WS_RECONNECT_COOLDOWN)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Fetches order book snapshots for each trading pair, and use them to update the local order book
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                rest_assistant = await self._get_rest_assistant()
                for trading_pair in trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_snapshot(rest_assistant, trading_pair)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = CoinbaseProOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"product_id": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above API rate limits.
                        await self._sleep(CONSTANTS.REST_API_LIMIT_COOLDOWN)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg=f"Unexpected error with WebSocket connection."
                                            f" Retrying in {CONSTANTS.REST_API_LIMIT_COOLDOWN} seconds."
                                            f" Check network connection."
                        )
                        await self._sleep(CONSTANTS.REST_API_LIMIT_COOLDOWN)
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await self._sleep(CONSTANTS.REST_API_LIMIT_COOLDOWN)

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        return self._rest_assistant
