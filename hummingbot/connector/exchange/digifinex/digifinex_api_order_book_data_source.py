#!/usr/bin/env python
import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import aiohttp

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger

from . import digifinex_constants as CONSTANTS, digifinex_utils
from .digifinex_active_order_tracker import DigifinexActiveOrderTracker
from .digifinex_order_book import DigifinexOrderBook
from .digifinex_websocket import DigifinexWebsocket


class DigifinexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0

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
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._ws: Optional[DigifinexWebsocket] = None

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        result = {}
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{CONSTANTS.REST_URL}/ticker")
            resp_json = await resp.json()
            for t_pair in trading_pairs:
                last_trade = [o["last"] for o in resp_json["ticker"] if o["symbol"] ==
                              digifinex_utils.convert_to_exchange_trading_pair(t_pair)]
                if last_trade and last_trade[0] is not None:
                    result[t_pair] = last_trade[0]
        return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{CONSTANTS.REST_URL}/ticker", timeout=10) as response:
                if response.status == 200:
                    try:
                        data: Dict[str, Any] = await response.json()
                        return [digifinex_utils.convert_from_exchange_trading_pair(item["symbol"]) for item in data["ticker"]]
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
                f"{CONSTANTS.REST_URL}/order_book?limit=150&symbol="
                f"{digifinex_utils.convert_to_exchange_trading_pair(trading_pair)}"
            )

            if orderbook_response.status != 200:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                    f"HTTP status is {orderbook_response.status}."
                )

            orderbook_data: List[Dict[str, Any]] = await safe_gather(orderbook_response.json())
            orderbook_data = orderbook_data[0]
        return orderbook_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = DigifinexOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: DigifinexActiveOrderTracker = DigifinexActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        message_queue: asyncio.Queue = self._message_queue[CONSTANTS.ORDER_BOOK_TRADE_CHANNEL]
        while True:
            try:
                ws_message = await message_queue.get()
                data = ws_message["params"]
                symbol = data[2]
                for trade in data[1]:
                    trade_timestamp: int = trade["time"]
                    trade_msg: OrderBookMessage = DigifinexOrderBook.trade_message_from_exchange(
                        trade,
                        trade_timestamp,
                        metadata={"trading_pair": digifinex_utils.convert_from_ws_trading_pair(symbol)}
                    )
                    output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error parsing orderbook depth message. ({str(e)})",
                    exc_info=True,
                )

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        message_queue: asyncio.Queue = self._message_queue[CONSTANTS.ORDER_BOOK_DEPTH_CHANNEL]
        while True:
            try:
                ws_message = await message_queue.get()
                data = ws_message["params"]
                symbol = data[2]
                order_book_data = data[1]
                timestamp: float = time.time()

                if data[0] is True:
                    orderbook_msg: OrderBookMessage = DigifinexOrderBook.snapshot_message_from_exchange(
                        order_book_data,
                        timestamp,
                        metadata={"trading_pair": digifinex_utils.convert_from_ws_trading_pair(symbol)}
                    )
                else:
                    orderbook_msg: OrderBookMessage = DigifinexOrderBook.diff_message_from_exchange(
                        order_book_data,
                        timestamp,
                        metadata={"trading_pair": digifinex_utils.convert_from_ws_trading_pair(symbol)}
                    )
                output.put_nowait(orderbook_msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error parsing orderbook depth message. ({str(e)})",
                    exc_info=True,
                )

    async def _subscribe_channels(self, websocket: DigifinexWebsocket):
        try:
            trading_pairs: List[str] = [digifinex_utils.convert_to_ws_trading_pair(pair)
                                        for pair in self._trading_pairs]
            await websocket.subscribe("depth", trading_pairs)
            await websocket.subscribe("trades", trading_pairs)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Unexpected error occured subscribing to Digifinex public channels. ({str(e)})")
            raise

    async def listen_for_subscriptions(self):
        while True:
            try:
                self._ws = DigifinexWebsocket()
                await self._ws.connect()
                trading_pairs: List[str] = [digifinex_utils.convert_to_ws_trading_pair(pair)
                                            for pair in self._trading_pairs]
                await self._ws.subscribe("depth", trading_pairs)
                await self._ws.subscribe("trades", trading_pairs)

                async for msg in self._ws.iter_messages():
                    if msg is None or "params" not in msg or "method" not in msg:
                        continue

                    channel = msg["method"]
                    if channel == CONSTANTS.ORDER_BOOK_DEPTH_CHANNEL:
                        self._message_queue[CONSTANTS.ORDER_BOOK_DEPTH_CHANNEL].put_nowait(msg)
                    elif channel == CONSTANTS.ORDER_BOOK_TRADE_CHANNEL:
                        self._message_queue[CONSTANTS.ORDER_BOOK_TRADE_CHANNEL].put_nowait(msg)

            except asyncio.CancelledError:
                raise
            except aiohttp.ClientConnectionError:
                self.logger().warning("Attemping re-connection with Websocket Public channels...")
            except Exception as e:
                self.logger().error(
                    f"Unexpected error with WebSocket connection. {str(e)}",
                    exc_info=True
                )
            finally:
                self._ws and await self._ws.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        # NOTE: DigiFinex WS Server is periodically (~1min) closing the ws connection. This forces us to reconnect to
        #       the orderbook channel. Considering that we receive an orderbook snapshot every time we subscribe to the
        #       orderbook channel, this task would not be neccesary.
        #       Essentially, we have a snapshot message every minute or so.
        pass
