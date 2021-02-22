#!/usr/bin/env python

import asyncio
from decimal import Decimal

import aiohttp
import logging
import pandas as pd
import math

from typing import AsyncIterable, Dict, List, Optional, Any

import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.utils import async_ttl_cache
from hummingbot.connector.exchange.dolomite.dolomite_active_order_tracker import DolomiteActiveOrderTracker
from hummingbot.connector.exchange.dolomite.dolomite_order_book import DolomiteOrderBook
from hummingbot.connector.exchange.dolomite.dolomite_order_book_tracker_entry import DolomiteOrderBookTrackerEntry
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.connector.exchange.dolomite.dolomite_order_book_message import DolomiteOrderBookMessage


MARKETS_URL = "/v1/markets"
SNAPSHOT_URL = "/v1/orders/markets/:trading_pair/depth/unmerged"
SNAPSHOT_WS_ROUTE = "/v1/orders/markets/-market-/depth/unmerged"
SNAPSHOT_WS_SUBSCRIBE_ACTION = "subscribe"
SNAPSHOT_WS_UPDATE_ACTION = "update"


class DolomiteAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    __daobds__logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.__daobds__logger is None:
            cls.__daobds__logger = logging.getLogger(__name__)
        return cls.__daobds__logger

    def __init__(self, trading_pairs: Optional[List[str]] = None, rest_api_url="", websocket_url=""):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self.REST_URL = rest_api_url
        self.WS_URL = websocket_url
        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()
        self.order_book_create_function = lambda: DolomiteOrderBook()

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have trading pair as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:
            # Hard coded to use the live exchange api for auto completing markets (opposed to using testnet)
            markets_response: aiohttp.ClientResponse = await client.get(
                f"https://exchange-api.dolomite.io{MARKETS_URL}"
            )

            if markets_response.status != 200:
                raise IOError(f"Error fetching active Dolomite markets. HTTP status is {markets_response.status}.")

            markets_data = await markets_response.json()
            markets_data = markets_data["data"]

            field_mapping = {
                "market": "market",
                "primary_token": "baseAsset",
                "primary_ticker_decimal_places": "int",
                "secondary_token": "quoteAsset",
                "secondary_ticker_price_decimal_places": "int",
                "period_volume": "volume",
                "period_volume_usd": "USDVolume",
            }

            all_markets: pd.DataFrame = pd.DataFrame.from_records(
                data=markets_data, index="market", columns=list(field_mapping.keys())
            )

            def obj_to_decimal(c):
                return Decimal(c["amount"]) / Decimal(math.pow(10, c["currency"]["precision"]))

            all_markets.rename(field_mapping, axis="columns", inplace=True)
            all_markets["USDVolume"] = all_markets["USDVolume"].map(obj_to_decimal)
            all_markets["volume"] = all_markets["volume"].map(obj_to_decimal)

            return all_markets.sort_values("USDVolume", ascending=False)

    @property
    def order_book_class(self) -> DolomiteOrderBook:
        return DolomiteOrderBook

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            from hummingbot.connector.exchange.dolomite.dolomite_utils import convert_from_exchange_trading_pair
            async with aiohttp.ClientSession() as client:
                async with client.get("https://exchange-api.dolomite.io/v1/markets", timeout=10) as response:
                    if response.status == 200:
                        all_trading_pairs: Dict[str, Any] = await response.json()
                        valid_trading_pairs: list = []
                        for item in all_trading_pairs["data"]:
                            valid_trading_pairs.append(item["market"])
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in valid_trading_pairs:
                            converted_trading_pair: Optional[str] = \
                                convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                        return trading_pair_list
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for dolomite trading pairs
            pass

        return []

    async def get_trading_pairs(self) -> List[str]:
        if self._trading_pairs is None:
            active_markets: pd.DataFrame = await self.get_active_exchange_markets()
            trading_pairs: List[str] = active_markets.index.tolist()
            self._trading_pairs = trading_pairs
        else:
            trading_pairs: List[str] = self._trading_pairs
        return trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str, level: int = 3) -> Dict[str, any]:
        async with client.get(f"{self.REST_URL}{SNAPSHOT_URL}".replace(":trading_pair", trading_pair)) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(
                    f"Error fetching Dolomite market snapshot for {trading_pair}. " f"HTTP status is {response.status}."
                )
            data: Dict[str, Any] = await response.json()
            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, DolomiteOrderBookTrackerEntry] = {}
            number_of_pairs: int = len(trading_pairs)

            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp: float = time.time()

                    snapshot_msg: DolomiteOrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                        snapshot, snapshot_timestamp, {"market": trading_pair}
                    )

                    dolomite_order_book: DolomiteOrderBook = DolomiteOrderBook()
                    dolomite_active_order_tracker: DolomiteActiveOrderTracker = DolomiteActiveOrderTracker()
                    bids, asks = dolomite_active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)

                    dolomite_order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = DolomiteOrderBookTrackerEntry(
                        trading_pair, snapshot_timestamp, dolomite_order_book, dolomite_active_order_tracker
                    )

                    self.logger().info(
                        f"Initialized order book for {trading_pair}. " f"{index+1}/{number_of_pairs} completed."
                    )

                    await asyncio.sleep(0.6)

                except Exception:
                    self.logger().error(
                        f"Error getting snapshot for {trading_pair} in get_tracking_pairs.", exc_info=True
                    )
                    await asyncio.sleep(5)

            self._get_tracking_pair_done_event.set()
            return retval

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Trade messages are received from the dolomite market event loop
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass  # Dolomite does not use DIFF, it sticks to using SNAPSHOT

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        await self._get_tracking_pair_done_event.wait()

        try:
            trading_pairs: List[str] = await self.get_trading_pairs()

            async with websockets.connect(self.WS_URL) as ws:
                ws: websockets.WebSocketClientProtocol = ws

                for trading_pair in trading_pairs:
                    orderbook_subscription_request = {
                        "action": SNAPSHOT_WS_SUBSCRIBE_ACTION,
                        "data": {"market": trading_pair},
                        "route": SNAPSHOT_WS_ROUTE,
                    }

                    await ws.send(ujson.dumps(orderbook_subscription_request))

                    async for raw_msg in self._inner_messages(ws):
                        message = ujson.loads(raw_msg)

                        if message["route"] == SNAPSHOT_WS_ROUTE and message["action"] == SNAPSHOT_WS_UPDATE_ACTION:
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: DolomiteOrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                                message, snapshot_timestamp, {"market": trading_pair}
                            )

                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair} at {snapshot_timestamp}")

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error.", exc_info=True)
            await asyncio.sleep(5.0)
