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
from .coinzoom_constants import Constants
from .coinzoom_active_order_tracker import CoinzoomActiveOrderTracker
from .coinzoom_order_book import CoinzoomOrderBook
from .coinzoom_websocket import CoinzoomWebsocket
from .coinzoom_utils import (
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair,
    api_call_with_retries,
    CoinzoomAPIError,
)


class CoinzoomAPIOrderBookDataSource(OrderBookTrackerDataSource):
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
        tickers: List[Dict[Any]] = await api_call_with_retries("GET", Constants.ENDPOINT["TICKER"])
        for trading_pair in trading_pairs:
            ex_pair: str = convert_to_exchange_trading_pair(trading_pair, True)
            ticker: Dict[Any] = list([tic for symbol, tic in tickers.items() if symbol == ex_pair])[0]
            results[trading_pair]: Decimal = Decimal(str(ticker["last_price"]))
        return results

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            symbols: List[Dict[str, Any]] = await api_call_with_retries("GET", Constants.ENDPOINT["SYMBOL"])
            trading_pairs: List[str] = list([convert_from_exchange_trading_pair(sym["symbol"]) for sym in symbols])
            # Filter out unmatched pairs so nothing breaks
            return [sym for sym in trading_pairs if sym is not None]
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for CoinZoom trading pairs
            pass
        return []

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        try:
            ex_pair = convert_to_exchange_trading_pair(trading_pair, True)
            ob_endpoint = Constants.ENDPOINT["ORDER_BOOK"].format(trading_pair=ex_pair)
            orderbook_response: Dict[Any] = await api_call_with_retries("GET", ob_endpoint)
            return orderbook_response
        except CoinzoomAPIError as e:
            err = e.error_payload.get('error', e.error_payload)
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {Constants.EXCHANGE_NAME}. "
                f"HTTP status is {e.error_payload['status']}. Error is {err.get('message', str(err))}.")

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = float(snapshot['timestamp'])
        snapshot_msg: OrderBookMessage = CoinzoomOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair})
        order_book = self.order_book_create_function()
        active_order_tracker: CoinzoomActiveOrderTracker = CoinzoomActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                ws = CoinzoomWebsocket()
                await ws.connect()

                for pair in self._trading_pairs:
                    await ws.subscribe({Constants.WS_SUB["TRADES"]: {'symbol': convert_to_exchange_trading_pair(pair)}})

                async for response in ws.on_message():
                    msg_keys = list(response.keys()) if response is not None else []

                    if not Constants.WS_METHODS["TRADES_UPDATE"] in msg_keys:
                        continue

                    trade: List[Any] = response[Constants.WS_METHODS["TRADES_UPDATE"]]
                    trade_msg: OrderBookMessage = CoinzoomOrderBook.trade_message_from_exchange(trade)
                    output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                raise
                await asyncio.sleep(5.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        while True:
            try:
                ws = CoinzoomWebsocket()
                await ws.connect()

                order_book_methods = [
                    Constants.WS_METHODS['ORDERS_SNAPSHOT'],
                    Constants.WS_METHODS['ORDERS_UPDATE'],
                ]

                for pair in self._trading_pairs:
                    ex_pair = convert_to_exchange_trading_pair(pair)
                    ws_stream = {
                        Constants.WS_SUB["ORDERS"]: {
                            'requestId': ex_pair,
                            'symbol': ex_pair,
                            'aggregate': False,
                            'depth': 0,
                        }
                    }
                    await ws.subscribe(ws_stream)

                async for response in ws.on_message():
                    msg_keys = list(response.keys()) if response is not None else []

                    method_key = [key for key in msg_keys if key in order_book_methods]

                    if len(method_key) != 1:
                        continue

                    method: str = method_key[0]
                    order_book_data: dict = response
                    timestamp: int = int(time.time() * 1e3)
                    pair: str = convert_from_exchange_trading_pair(response[method])

                    order_book_msg_cls = (CoinzoomOrderBook.diff_message_from_exchange
                                          if method == Constants.WS_METHODS['ORDERS_UPDATE'] else
                                          CoinzoomOrderBook.snapshot_message_from_exchange)

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
                        snapshot_msg: OrderBookMessage = CoinzoomOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot['timestamp'],
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
