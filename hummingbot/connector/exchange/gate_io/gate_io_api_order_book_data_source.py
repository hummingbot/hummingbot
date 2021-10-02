#!/usr/bin/env python
import asyncio
import logging
import time
import pandas as pd
from decimal import Decimal
from typing import Optional, List, Dict, Any
from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from .gate_io_active_order_tracker import GateIoActiveOrderTracker
from .gate_io_order_book import GateIoOrderBook
from .gate_io_websocket import GateIoWebsocket
from .gate_io_utils import (
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair,
    api_call_with_retries,
    GateIoAPIError,
)
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS


class GateIoAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, throttler: Optional[AsyncThrottler] = None, trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._throttler = throttler or self._get_throttler_instance()
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @classmethod
    async def get_last_traded_prices(
        cls, trading_pairs: List[str], throttler: Optional[AsyncThrottler] = None
    ) -> Dict[str, Decimal]:
        throttler = throttler or cls._get_throttler_instance()
        results = {}
        ticker_param = None
        if len(trading_pairs) == 1:
            ticker_param = {'currency_pair': convert_to_exchange_trading_pair(trading_pairs[0])}

        async with throttler.execute_task(CONSTANTS.TICKER_PATH_URL):
            tickers = await api_call_with_retries("GET", CONSTANTS.TICKER_PATH_URL, ticker_param)
        for trading_pair in trading_pairs:
            ex_pair = convert_to_exchange_trading_pair(trading_pair)
            ticker = list([tic for tic in tickers if tic['currency_pair'] == ex_pair])[0]
            results[trading_pair] = Decimal(str(ticker["last"]))
        return results

    @classmethod
    async def fetch_trading_pairs(cls, throttler: Optional[AsyncThrottler] = None) -> List[str]:
        throttler = throttler or cls._get_throttler_instance()
        try:
            async with throttler.execute_task(CONSTANTS.SYMBOL_PATH_URL):
                symbols = await api_call_with_retries("GET", CONSTANTS.SYMBOL_PATH_URL)
            trading_pairs = list([convert_from_exchange_trading_pair(sym["id"]) for sym in symbols])
            # Filter out unmatched pairs so nothing breaks
            return [sym for sym in trading_pairs if sym is not None]
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for Gate.io trading pairs
            pass
        return []

    @classmethod
    async def get_order_book_data(cls, trading_pair: str, throttler: Optional[AsyncThrottler] = None) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        throttler = throttler or cls._get_throttler_instance()
        try:
            ex_pair = convert_to_exchange_trading_pair(trading_pair)
            async with throttler.execute_task(CONSTANTS.ORDER_BOOK_PATH_URL):
                orderbook_response = await api_call_with_retries(
                    "GET", CONSTANTS.ORDER_BOOK_PATH_URL, params={"currency_pair": ex_pair, "with_id": 1}
                )
            return orderbook_response
        except GateIoAPIError as e:
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                f"HTTP status is {e.http_status}. Error is {e.error_message}.")

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair, self._throttler)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = GateIoOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair})
        order_book = self.order_book_create_function()
        active_order_tracker: GateIoActiveOrderTracker = GateIoActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        ws = None
        while True:
            try:
                ws = GateIoWebsocket()
                await ws.connect()

                await ws.subscribe(CONSTANTS.TRADES_ENDPOINT_NAME,
                                   [convert_to_exchange_trading_pair(pair) for pair in self._trading_pairs])

                async for response in ws.on_message():
                    method: str = response.get("channel", None)
                    trade_data: Dict[Any] = response.get("result", None)

                    if response.get("event") in ["subscribe", "unsubscribe"]:
                        continue
                    if trade_data is None or method != CONSTANTS.TRADES_ENDPOINT_NAME:
                        continue

                    pair: str = convert_from_exchange_trading_pair(trade_data.get("currency_pair", None))

                    if pair is None:
                        continue

                    trade_timestamp: int = trade_data['create_time']
                    trade_msg: OrderBookMessage = GateIoOrderBook.trade_message_from_exchange(
                        trade_data,
                        trade_timestamp,
                        metadata={"trading_pair": pair})
                    output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                if ws is not None:
                    await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        ws = None
        while True:
            try:
                ws = GateIoWebsocket()
                await ws.connect()

                order_book_channels = [
                    CONSTANTS.ORDER_SNAPSHOT_ENDPOINT_NAME,
                    CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME,
                ]

                for pair in self._trading_pairs:
                    await ws.subscribe(CONSTANTS.ORDER_SNAPSHOT_ENDPOINT_NAME,
                                       [convert_to_exchange_trading_pair(pair), '5', '1000ms'])
                    await ws.subscribe(CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME,
                                       [convert_to_exchange_trading_pair(pair), '100ms'])

                async for response in ws.on_message():
                    channel: str = response.get("channel", None)
                    order_book_data: str = response.get("result", None)

                    if response.get("event") in ["subscribe", "unsubscribe"]:
                        continue
                    if order_book_data is None or channel not in order_book_channels:
                        continue

                    timestamp: int = order_book_data["t"]
                    pair: str = convert_from_exchange_trading_pair(order_book_data["s"])

                    order_book_msg_cls = (GateIoOrderBook.diff_message_from_exchange
                                          if channel == CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME else
                                          GateIoOrderBook.snapshot_message_from_exchange)

                    orderbook_msg: OrderBookMessage = order_book_msg_cls(
                        order_book_data,
                        timestamp,
                        metadata={"trading_pair": pair})
                    output.put_nowait(orderbook_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.", exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection.")
                await asyncio.sleep(30.0)
            finally:
                if ws is not None:
                    await ws.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair, self._throttler)
                        snapshot_timestamp: int = int(time.time())
                        snapshot_msg: OrderBookMessage = GateIoOrderBook.snapshot_message_from_exchange(
                            snapshot,
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
                            "Unexpected error with WebSocket connection.", exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection.")
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
