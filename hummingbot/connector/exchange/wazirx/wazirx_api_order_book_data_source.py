#!/usr/bin/env python
import asyncio
import logging
import time
import aiohttp
import websockets
import simplejson
import ujson

from websockets.exceptions import ConnectionClosed
from hummingbot.connector.exchange.wazirx import wazirx_constants as CONSTANTS
from decimal import Decimal
from typing import Optional, List, Dict, AsyncIterable, Any
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from . import wazirx_utils
from .wazirx_active_order_tracker import WazirxActiveOrderTracker
from .wazirx_order_book import WazirxOrderBook
from .wazirx_utils import ms_timestamp_to_s


class WazirxAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

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
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        result = {}
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.GET_TICKER_24H}")
            resp_json = await resp.json()
            for t_pair in trading_pairs:
                last_trade = [float(o["lastPrice"]) for o in resp_json if o["symbol"] == wazirx_utils.convert_to_exchange_trading_pair(t_pair)]
                if last_trade and last_trade[0] is not None:
                    result[t_pair] = last_trade[0]
        return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.GET_EXCHANGE_INFO}", timeout=10) as response:
                if response.status == 200:
                    try:
                        data: Dict[str, Any] = await response.json()
                        return [str(item["baseAsset"]).upper() + '-' + str(item["quoteAsset"]).upper()
                                for item in data["symbols"]
                                if item["isSpotTradingAllowed"] is True]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                return []

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        async with aiohttp.ClientSession() as client:
            orderbook_response = await client.get(
                f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.GET_ORDERBOOK}?limit=100&symbol="
                f"{wazirx_utils.convert_to_exchange_trading_pair(trading_pair)}"
            )

            if orderbook_response.status != 200:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                    f"HTTP status is {orderbook_response.status}."
                )

            orderbook_data: List[Dict[str, Any]] = await safe_gather(orderbook_response.json())

        return orderbook_data[0]

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = WazirxOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: WazirxActiveOrderTracker = WazirxActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                async with websockets.connect(CONSTANTS.WSS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    streams = [wazirx_utils.convert_to_exchange_trading_pair(pair) + "@trades" for pair in self._trading_pairs]
                    subscribe_request: Dict[str, Any] = {
                        "event": "subscribe",
                        "streams": streams
                    }
                    await ws.send(ujson.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg = simplejson.loads(raw_msg, parse_float=Decimal)
                        if "stream" in msg:
                            if "@trades" in msg["stream"]:
                                for trade in msg["data"]["trades"]:
                                    trade: Dict[Any] = trade
                                    trade_timestamp: int = ms_timestamp_to_s(trade["E"])
                                    trade_msg: OrderBookMessage = WazirxOrderBook.trade_message_from_exchange(
                                        trade,
                                        trade_timestamp,
                                        metadata={"trading_pair": wazirx_utils.convert_from_exchange_trading_pair(trade["s"])}
                                    )
                                    output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().warning("WebSocket ping timed out. Reconnecting after 5 seconds...")
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "5 seconds...", exc_info=True)
            finally:
                await asyncio.sleep(5)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                async with websockets.connect(CONSTANTS.WSS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    streams = [wazirx_utils.convert_to_exchange_trading_pair(pair) + "@depth" for pair in self._trading_pairs]
                    subscribe_request: Dict[str, Any] = {
                        "event": "subscribe",
                        "streams": streams
                    }
                    await ws.send(ujson.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg = simplejson.loads(raw_msg, parse_float=Decimal)
                        if "stream" in msg:
                            if "@depth" in msg["stream"]:
                                data = msg["data"]
                                snapshot_timestamp: int = ms_timestamp_to_s(data["E"])
                                _msg = {
                                    'asks': [list(map(float, item)) for item in data['a']],
                                    'bids': [list(map(float, item)) for item in data['b']],
                                }
                                snapshot_msg: OrderBookMessage = WazirxOrderBook.snapshot_message_from_exchange(
                                    _msg,
                                    snapshot_timestamp,
                                    {"trading_pair": wazirx_utils.convert_from_exchange_trading_pair(data["s"])}
                                )
                                output.put_nowait(snapshot_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(30.0)
