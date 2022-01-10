#!/usr/bin/env python

import aiohttp
import asyncio
from aiohttp.test_utils import TestClient
import logging
import pandas as pd
import time
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.logger import HummingbotLogger


class MockAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _maobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._maobds_logger is None:
            cls._maobds_logger = logging.getLogger(__name__)
        return cls._maobds_logger

    def __init__(self, client: TestClient, order_book_class: OrderBook, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._client: TestClient = client
        self._order_book_class = order_book_class
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._diff_messages: asyncio.Queue = asyncio.Queue()
        self._snapshot_messages: asyncio.Queue = asyncio.Queue()

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                self._trading_pairs = await self.fetch_trading_pairs()
            except Exception:
                self._trading_pairs = []
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg="Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        raise NotImplementedError("Trading Pairs are required for mock data source")

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        # when type is set to "step0", the default value of "depth" is 150
        async with client.get("/mockSnapshot") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            parsed_response = await response.json()
            return parsed_response

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        trading_pairs: List[str] = await self.get_trading_pairs()
        retval: Dict[str, OrderBookTrackerEntry] = {}

        number_of_pairs: int = len(trading_pairs)
        for index, trading_pair in enumerate(trading_pairs):
            try:
                snapshot: Dict[str, Any] = await self.get_snapshot(self._client, trading_pair)
                snapshot_msg: OrderBookMessage = self._order_book_class.snapshot_message_from_exchange(
                    snapshot,
                    metadata={"trading_pair": trading_pair}
                )
                order_book: OrderBook = self.order_book_create_function()
                order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                retval[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_msg.timestamp, order_book)
                self.logger().info(f"Initialized order book for {trading_pair}. "
                                   f"{index + 1}/{number_of_pairs} completed.")
                await asyncio.sleep(0.1)
            except Exception:
                self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                await asyncio.sleep(5)
        return retval

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
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
        pass

    def inject_mock_diff_message(self, msg: Dict[str, Any]):
        self._diff_messages.put_nowait(msg)

    def inject_mock_snapshot_message(self, msg: Dict[str, Any]):
        self._snapshot_messages.put_nowait(msg)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            msg = await self._diff_messages.get()
            order_book_message: OrderBookMessage = self._order_book_class.diff_message_from_exchange(msg)
            output.put_nowait(order_book_message)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                for trading_pair in trading_pairs:
                    try:
                        snapshot: Dict[str, Any] = await self.get_snapshot(self._client, trading_pair)
                        snapshot_message: OrderBookMessage = self._order_book_class.snapshot_message_from_exchange(
                            snapshot,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_message)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
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
