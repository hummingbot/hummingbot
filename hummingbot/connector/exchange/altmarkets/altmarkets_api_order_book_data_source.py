#!/usr/bin/env python
import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd

import hummingbot.connector.exchange.altmarkets.altmarkets_http_utils as http_utils
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource

# from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger

from .altmarkets_active_order_tracker import AltmarketsActiveOrderTracker
from .altmarkets_constants import Constants
from .altmarkets_order_book import AltmarketsOrderBook
from .altmarkets_utils import AltmarketsAPIError, convert_from_exchange_trading_pair, convert_to_exchange_trading_pair
from .altmarkets_websocket import AltmarketsWebsocket


class AltmarketsAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 throttler: Optional[AsyncThrottler] = None,
                 trading_pairs: List[str] = None,
                 ):
        super().__init__(trading_pairs)
        self._throttler: AsyncThrottler = throttler or self._get_throttler_instance()
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}

    def _time(self):
        """ Function created to enable patching during unit tests execution.
        :return: current time
        """
        return time.time()

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(Constants.RATE_LIMITS)
        return throttler

    @classmethod
    async def get_last_traded_prices(cls,
                                     trading_pairs: List[str],
                                     throttler: Optional[AsyncThrottler] = None) -> Dict[str, Decimal]:
        throttler = throttler or cls._get_throttler_instance()
        results = {}
        if len(trading_pairs) > 3:
            tickers: List[Dict[Any]] = await http_utils.api_call_with_retries(method="GET",
                                                                              endpoint=Constants.ENDPOINT["TICKER"],
                                                                              throttler=throttler,
                                                                              limit_id=Constants.RL_ID_TICKER,
                                                                              logger=cls.logger())
        for trading_pair in trading_pairs:
            ex_pair: str = convert_to_exchange_trading_pair(trading_pair)
            if len(trading_pairs) > 3:
                ticker: Dict[Any] = tickers[ex_pair]
            else:
                url_endpoint = Constants.ENDPOINT["TICKER_SINGLE"].format(trading_pair=ex_pair)
                ticker: Dict[Any] = await http_utils.api_call_with_retries(method="GET",
                                                                           endpoint=url_endpoint,
                                                                           throttler=throttler,
                                                                           limit_id=Constants.RL_ID_TICKER,
                                                                           logger=cls.logger())
            results[trading_pair]: Decimal = Decimal(str(ticker["ticker"]["last"]))
        return results

    @classmethod
    async def fetch_trading_pairs(cls, throttler: Optional[AsyncThrottler] = None) -> List[str]:
        throttler = throttler or cls._get_throttler_instance()
        try:
            symbols: List[Dict[str, Any]] = await http_utils.api_call_with_retries(method="GET",
                                                                                   endpoint=Constants.ENDPOINT["SYMBOL"],
                                                                                   throttler=throttler,
                                                                                   logger=cls.logger())
            return [
                symbol["name"].replace("/", "-") for symbol in symbols
                if symbol['state'] == "enabled"
            ]
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for huobi trading pairs
            pass
        return []

    @classmethod
    async def get_order_book_data(cls,
                                  trading_pair: str,
                                  throttler: Optional[AsyncThrottler] = None) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        throttler = throttler or cls._get_throttler_instance()
        try:
            ex_pair = convert_to_exchange_trading_pair(trading_pair)
            endpoint = Constants.ENDPOINT["ORDER_BOOK"].format(trading_pair=ex_pair)
            orderbook_response: Dict[Any] = await http_utils.api_call_with_retries(method="GET",
                                                                                   endpoint=endpoint,
                                                                                   params={"limit": 300},
                                                                                   throttler=throttler,
                                                                                   limit_id=Constants.RL_ID_ORDER_BOOK,
                                                                                   logger=cls.logger())
            return orderbook_response
        except AltmarketsAPIError as e:
            err = e.error_payload.get('errors', e.error_payload)
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {Constants.EXCHANGE_NAME}. "
                f"HTTP status is {e.error_payload['status']}. Error is {err.get('message', str(err))}.")

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair, self._throttler)
        snapshot_timestamp: float = self._time()
        snapshot_msg: OrderBookMessage = AltmarketsOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair})
        order_book = self.order_book_create_function()
        active_order_tracker: AltmarketsActiveOrderTracker = AltmarketsActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                ws = AltmarketsWebsocket(throttler=self._throttler)

                await ws.connect()

                ws_streams = [
                    Constants.WS_SUB['TRADES'].format(trading_pair=convert_to_exchange_trading_pair(trading_pair))
                    for trading_pair in self._trading_pairs
                ]
                await ws.subscribe(ws_streams)

                async for response in ws.on_message():
                    if response is not None:
                        for msg_key in list(response.keys()):
                            split_key = msg_key.split(Constants.WS_METHODS['TRADES_UPDATE'], 1)
                            if len(split_key) != 2:
                                # Debug log output for pub WS messages
                                self.logger().info(f"Unrecognized message received from Altmarkets websocket: {response}")
                                continue
                            trading_pair = convert_from_exchange_trading_pair(split_key[0])
                            for trade in response[msg_key]["trades"]:
                                trade_timestamp: int = int(trade.get('date', self._time()))
                                trade_msg: OrderBookMessage = AltmarketsOrderBook.trade_message_from_exchange(
                                    trade,
                                    trade_timestamp,
                                    metadata={"trading_pair": trading_pair})
                                output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Trades: Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(Constants.MESSAGE_TIMEOUT)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        while True:
            try:
                ws = AltmarketsWebsocket(throttler=self._throttler)
                await ws.connect()

                ws_streams = [
                    Constants.WS_SUB['ORDERS'].format(trading_pair=convert_to_exchange_trading_pair(trading_pair))
                    for trading_pair in self._trading_pairs
                ]
                await ws.subscribe(ws_streams)

                async for response in ws.on_message():
                    if response is not None:
                        for msg_key in list(response.keys()):
                            # split_key = msg_key.split(Constants.WS_METHODS['TRADES_UPDATE'], 1)
                            if Constants.WS_METHODS['ORDERS_UPDATE'] in msg_key:
                                order_book_msg_cls = AltmarketsOrderBook.diff_message_from_exchange
                                split_key = msg_key.split(Constants.WS_METHODS['ORDERS_UPDATE'], 1)
                            elif Constants.WS_METHODS['ORDERS_SNAPSHOT'] in msg_key:
                                order_book_msg_cls = AltmarketsOrderBook.snapshot_message_from_exchange
                                split_key = msg_key.split(Constants.WS_METHODS['ORDERS_SNAPSHOT'], 1)
                            else:
                                # Debug log output for pub WS messages
                                self.logger().info(f"Unrecognized message received from Altmarkets websocket: {response}")
                                continue
                            order_book_data: str = response.get(msg_key, None)
                            timestamp: int = int(self._time())
                            trading_pair: str = convert_from_exchange_trading_pair(split_key[0])

                            orderbook_msg: OrderBookMessage = order_book_msg_cls(
                                order_book_data,
                                timestamp,
                                metadata={"trading_pair": trading_pair})
                            output.put_nowait(orderbook_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.", exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection.")
                await self._sleep(30.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair,
                                                                              throttler=self._throttler)
                    snapshot_timestamp: int = int(snapshot["timestamp"])
                    snapshot_msg: OrderBookMessage = AltmarketsOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    output.put_nowait(snapshot_msg)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - self._time()
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error occurred listening for orderbook snapshots. Retrying in 5 secs...")
                self.logger().network(
                    "Unexpected error occured listening for orderbook snapshots. Retrying in 5 secs...", exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                    "Check network connection.")
                await self._sleep(5.0)

    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        # This connector does not use this base class method and needs a refactoring
        pass
