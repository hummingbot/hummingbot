#!/usr/bin/env python
import aiohttp
import asyncio
import logging
import pandas as pd
import time
import ujson
import websockets

import hummingbot.connector.exchange.probit.probit_constants as CONSTANTS

from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.probit import probit_utils
from hummingbot.connector.exchange.probit.probit_order_book import ProbitOrderBook


class ProbitAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    SNAPSHOT_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: List[str] = None, domain: str = "com"):
        super().__init__(trading_pairs)
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str], domain: str = "com") -> Dict[str, float]:
        result = {}
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{CONSTANTS.TICKER_URL.format(domain)}") as response:
                if response.status == 200:
                    resp_json = await response.json()
                    if "data" in resp_json:
                        for market in resp_json["data"]:
                            if market["market_id"] in trading_pairs:
                                result[market["market_id"]] = float(market["last"])

        return result

    @staticmethod
    async def fetch_trading_pairs(domain: str = "com") -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{CONSTANTS.MARKETS_URL.format(domain)}") as response:
                if response.status == 200:
                    resp_json: Dict[str, Any] = await response.json()
                    return [market["id"] for market in resp_json["data"]]
                return []

    @staticmethod
    async def get_order_book_data(trading_pair: str, domain: str = "com") -> Dict[str, any]:
        """
        Get whole orderbook
        """
        async with aiohttp.ClientSession() as client:
            async with client.get(url=f"{CONSTANTS.ORDER_BOOK_URL.format(domain)}",
                                  params={"market_id": trading_pair}) as response:
                if response.status != 200:
                    raise IOError(
                        f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.ORDER_BOOK_PATH_URL.format(domain)}. "
                        f"HTTP {response.status}. Response: {await response.json()}"
                    )
                return await response.json()

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: int = int(time.time() * 1e3)
        snapshot_msg: OrderBookMessage = ProbitOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        bids, asks = probit_utils.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                yield msg
        except asyncio.TimeoutError:
            try:
                pong_waiter = await ws.ping()
                await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
            except asyncio.TimeoutError:
                raise
        except websockets.exceptions.ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_order_book_diffs_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # TODO: Combine both trades and order_book_diffs
        # params: Dict[str, Any] = {
        #                     "channel": "marketdata",
        #                     "filter": ["order_books","recent_trades"],
        #                     "interval": 100,
        #                     "market_id": trading_pair,
        #                     "type": "subscribe"
        #                 }
        pass

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                async with websockets.connect(uri=CONSTANTS.WSS_URL.format(self._domain)) as ws:
                    for trading_pair in self._trading_pairs:
                        params: Dict[str, Any] = {
                            "channel": "marketdata",
                            "filter": ["recent_trades"],
                            "interval": 100,
                            "market_id": trading_pair,
                            "type": "subscribe"
                        }
                        await ws.send(ujson.dumps(params))
                    async for raw_msg in self._inner_messages(ws):
                        msg_timestamp: int = int(time.time() * 1e3)
                        msg = ujson.loads(raw_msg)
                        if "recent_trades" not in msg:
                            # Unrecognized response from "recent_trades" channel
                            continue

                        if "reset" in msg and msg["reset"] is True:
                            # Ignores first response from "recent_trades" channel. This response details the last 100 trades.
                            continue
                        for trade_entry in msg["recent_trades"]:
                            trade_msg: OrderBookMessage = ProbitOrderBook.trade_message_from_exchange(
                                msg=trade_entry,
                                timestamp=msg_timestamp,
                                metadata={"market_id": msg["market_id"]})
                            output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                await ws.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        while True:
            try:
                async with websockets.connect(uri=CONSTANTS.WSS_URL.format(self._domain)) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in self._trading_pairs:
                        params: Dict[str, Any] = {
                            "channel": "marketdata",
                            "filter": ["order_books"],
                            "interval": 100,
                            "market_id": trading_pair,
                            "type": "subscribe"
                        }
                        await ws.send(ujson.dumps(params))
                    async for raw_msg in self._inner_messages(ws):
                        msg_timestamp: int = int(time.time() * 1e3)
                        msg: Dict[str, Any] = ujson.loads(raw_msg)
                        if "order_books" not in msg:
                            # Unrecognized response from "order_books" channel
                            continue
                        if "reset" in msg and msg["reset"] is True:
                            # First response from websocket is a snapshot. This is only when reset = True
                            snapshot_msg: OrderBookMessage = ProbitOrderBook.snapshot_message_from_exchange(
                                msg=msg,
                                timestamp=msg_timestamp,
                            )
                            output.put_nowait(snapshot_msg)
                        else:
                            diff_msg: OrderBookMessage = ProbitOrderBook.diff_message_from_exchange(
                                msg=msg,
                                timestamp=msg_timestamp,
                                metadata={"market_id": msg["market_id"]}
                            )
                            output.put_nowait(diff_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                await asyncio.sleep(30.0)
            finally:
                await ws.close()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                        snapshot_timestamp: int = int(time.time() * 1e3)
                        snapshot_msg: OrderBookMessage = ProbitOrderBook.snapshot_message_from_exchange(
                            msg=snapshot,
                            timestamp=snapshot_timestamp,
                            metadata={"market_id": trading_pair}  # Manually insert trading_pair here since API response does include trading pair
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above API rate limits.
                        await asyncio.sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection."
                        )
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
