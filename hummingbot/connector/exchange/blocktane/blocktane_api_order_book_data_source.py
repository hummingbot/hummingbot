#!/usr/bin/env python

import asyncio
import aiohttp
from collections import namedtuple
import logging
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
import re
import time
import ujson
import websockets

from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.blocktane.blocktane_order_book import BlocktaneOrderBook
from hummingbot.connector.exchange.blocktane.blocktane_utils import convert_to_exchange_trading_pair, convert_from_exchange_trading_pair

BLOCKTANE_REST_URL = "https://trade.blocktane.io/api/v2/xt/public"
DIFF_STREAM_URL = "wss://trade.blocktane.io/api/v2/ws/public"
TICKER_PRICE_CHANGE_URL = "https://trade.blocktane.io/api/v2/xt/public/markets/tickers"
SINGLE_MARKET_DEPTH_URL = "https://trade.blocktane.io/api/v2/xt/public/markets/{}/depth"
EXCHANGE_INFO_URL = "https://trade.blocktane.io/api/v2/xt/public/markets"

OrderBookRow = namedtuple("Book", ["price", "amount"])

API_CALL_TIMEOUT = 5


class BlocktaneAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _baobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._baobds_logger is None:
            cls._baobds_logger = logging.getLogger(__name__)
        return cls._baobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        async with aiohttp.ClientSession() as client:
            resp = await client.get(TICKER_PRICE_CHANGE_URL)
            resp_json = await resp.json()

            return {convert_from_exchange_trading_pair(market): float(data["ticker"]["last"]) for market, data in resp_json.items()
                    if convert_from_exchange_trading_pair(market) in trading_pairs}

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(EXCHANGE_INFO_URL, timeout=API_CALL_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        raw_trading_pairs = [d["id"] for d in data if d["state"] == "enabled"]
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in raw_trading_pairs:
                            converted_trading_pair: Optional[str] = convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                        return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for blocktane trading pairs
            pass

        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str, limit: int = 1000) -> Dict[str, Any]:
        request_url: str = f"{BLOCKTANE_REST_URL}/markets/{convert_to_exchange_trading_pair(trading_pair)}/depth"

        async with client.get(request_url) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching blocktane market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")

            data: Dict[str, Any] = await response.json()

            # Need to add the symbol into the snapshot message for the Kafka message queue.
            # Because otherwise, there'd be no way for the receiver to know which market the
            # snapshot belongs to.

            return _prepare_snapshot(trading_pair, data["bids"], data["asks"])

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = BlocktaneOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    def get_ws_connection(self, stream_url):
        ws = websockets.connect(stream_url)
        return ws

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        while True:
            try:
                msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                yield msg
            except asyncio.TimeoutError:
                pong_waiter = await ws.ping()
                await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws_path: str = "&stream=".join([f"{convert_to_exchange_trading_pair(trading_pair)}.trades" for trading_pair in self._trading_pairs])
                stream_url: str = f"{DIFF_STREAM_URL}/?stream={ws_path}"

                ws: websockets.WebSocketClientProtocol = await self.get_ws_connection(stream_url)
                async for raw_msg in self._inner_messages(ws):
                    msg = ujson.loads(raw_msg)
                    if (list(msg.keys())[0].endswith("trades")):
                        trade_msg: OrderBookMessage = BlocktaneOrderBook.trade_message_from_exchange(msg)
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().warning("WebSocket ping timed out. Reconnecting after 30 seconds...")
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "30 seconds...", exc_info=True)
            finally:
                await ws.close()
                await asyncio.sleep(30)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws_path: str = "&stream=".join([f"{convert_to_exchange_trading_pair(trading_pair)}.ob-inc" for trading_pair in self._trading_pairs])
                stream_url: str = f"{DIFF_STREAM_URL}/?stream={ws_path}"

                ws: websockets.WebSocketClientProtocol = await self.get_ws_connection(stream_url)
                async for raw_msg in self._inner_messages(ws):
                    msg = ujson.loads(raw_msg)
                    key = list(msg.keys())[0]
                    if ('ob-inc' in key):
                        pair = re.sub(r'\.ob-inc', '', key)
                        parsed_msg = {"pair": convert_from_exchange_trading_pair(pair),
                                      "bids": msg[key]["bids"] if "bids" in msg[key] else [],
                                      "asks": msg[key]["asks"] if "asks" in msg[key] else []}
                        order_book_message: OrderBookMessage = BlocktaneOrderBook.diff_message_from_exchange(parsed_msg, time.time())
                        output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().warning("WebSocket ping timed out. Reconnecting after 30 seconds...")
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "30 seconds...", exc_info=True)
            finally:
                await ws.close()
                await asyncio.sleep(30)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with aiohttp.ClientSession() as client:
                    for trading_pair in self._trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = BlocktaneOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            # self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            # Be careful not to go above blocktane's API rate limits.
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
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


def _prepare_snapshot(pair: str, bids: List, asks: List) -> Dict[str, Any]:
    """
    Return structure of three elements:
        symbol: traded pair symbol
        bids: List of OrderBookRow for bids
        asks: List of OrderBookRow for asks
    """

    format_bids = [OrderBookRow(i[0], i[1]) for i in bids]
    format_asks = [OrderBookRow(i[0], i[1]) for i in asks]

    return {
        "symbol": pair,
        "bids": format_bids,
        "asks": format_asks,
    }
