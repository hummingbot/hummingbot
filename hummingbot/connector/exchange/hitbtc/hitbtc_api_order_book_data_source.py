#!/usr/bin/env python
import asyncio
import logging
import time
import pandas as pd
from decimal import Decimal
from typing import Optional, List, Dict, Any
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from .hitbtc_constants import Constants
from .hitbtc_active_order_tracker import HitbtcActiveOrderTracker
from .hitbtc_order_book import HitbtcOrderBook
from .hitbtc_websocket import HitbtcWebsocket
from .hitbtc_utils import (
    str_date_to_ts,
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair,
    api_call_with_retries,
    HitbtcAPIError,
)


class HitbtcAPIOrderBookDataSource(OrderBookTrackerDataSource):
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

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, Decimal]:
        results = {}
        if len(trading_pairs) > 1:
            tickers: List[Dict[Any]] = await api_call_with_retries("GET", Constants.ENDPOINT["TICKER"])
        for trading_pair in trading_pairs:
            ex_pair: str = convert_to_exchange_trading_pair(trading_pair)
            if len(trading_pairs) > 1:
                ticker: Dict[Any] = list([tic for tic in tickers if tic['symbol'] == ex_pair])[0]
            else:
                url_endpoint = Constants.ENDPOINT["TICKER_SINGLE"].format(trading_pair=ex_pair)
                ticker: Dict[Any] = await api_call_with_retries("GET", url_endpoint)
            results[trading_pair]: Decimal = Decimal(str(ticker["last"]))
        return results

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            symbols: List[Dict[str, Any]] = await api_call_with_retries("GET", Constants.ENDPOINT["SYMBOL"])
            trading_pairs: List[str] = list([convert_from_exchange_trading_pair(sym["id"]) for sym in symbols])
            # Filter out unmatched pairs so nothing breaks
            return [sym for sym in trading_pairs if sym is not None]
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for HitBTC trading pairs
            pass
        return []

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        try:
            ex_pair = convert_to_exchange_trading_pair(trading_pair)
            orderbook_response: Dict[Any] = await api_call_with_retries("GET", Constants.ENDPOINT["ORDER_BOOK"],
                                                                        params={"limit": 150, "symbols": ex_pair})
            return orderbook_response[ex_pair]
        except HitbtcAPIError as e:
            err = e.error_payload.get('error', e.error_payload)
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {Constants.EXCHANGE_NAME}. "
                f"HTTP status is {e.error_payload['status']}. Error is {err.get('message', str(err))}.")

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = HitbtcOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair})
        order_book = self.order_book_create_function()
        active_order_tracker: HitbtcActiveOrderTracker = HitbtcActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                ws = HitbtcWebsocket()
                await ws.connect()

                for pair in self._trading_pairs:
                    await ws.subscribe(Constants.WS_SUB["TRADES"], convert_to_exchange_trading_pair(pair))

                async for response in ws.on_message():
                    method: str = response.get("method", None)
                    trades_data: str = response.get("params", None)

                    if trades_data is None or method != Constants.WS_METHODS['TRADES_UPDATE']:
                        continue

                    pair: str = convert_from_exchange_trading_pair(response["params"]["symbol"])

                    for trade in trades_data["data"]:
                        trade: Dict[Any] = trade
                        trade_timestamp: int = str_date_to_ts(trade["timestamp"])
                        trade_msg: OrderBookMessage = HitbtcOrderBook.trade_message_from_exchange(
                            trade,
                            trade_timestamp,
                            metadata={"trading_pair": pair})
                        output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        while True:
            try:
                ws = HitbtcWebsocket()
                await ws.connect()

                order_book_methods = [
                    Constants.WS_METHODS['ORDERS_SNAPSHOT'],
                    Constants.WS_METHODS['ORDERS_UPDATE'],
                ]

                for pair in self._trading_pairs:
                    await ws.subscribe(Constants.WS_SUB["ORDERS"], convert_to_exchange_trading_pair(pair))

                async for response in ws.on_message():
                    method: str = response.get("method", None)
                    order_book_data: str = response.get("params", None)

                    if order_book_data is None or method not in order_book_methods:
                        continue

                    timestamp: int = str_date_to_ts(order_book_data["timestamp"])
                    pair: str = convert_from_exchange_trading_pair(order_book_data["symbol"])

                    order_book_msg_cls = (HitbtcOrderBook.diff_message_from_exchange
                                          if method == Constants.WS_METHODS['ORDERS_UPDATE'] else
                                          HitbtcOrderBook.snapshot_message_from_exchange)

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
                await ws.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                        snapshot_timestamp: int = str_date_to_ts(snapshot["timestamp"])
                        snapshot_msg: OrderBookMessage = HitbtcOrderBook.snapshot_message_from_exchange(
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
