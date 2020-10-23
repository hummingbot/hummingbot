#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import pandas as pd
from typing import (
    AsyncIterable,
    Dict,
    List,
    Optional,
)
import re
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.exchange.radar_relay.radar_relay_order_book import RadarRelayOrderBook
from hummingbot.connector.exchange.radar_relay.radar_relay_active_order_tracker import RadarRelayActiveOrderTracker
from hummingbot.connector.exchange.radar_relay.radar_relay_order_book_message import RadarRelayOrderBookMessage
from hummingbot.core.utils import async_ttl_cache
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage

TRADING_PAIR_FILTER = re.compile(r"(WETH|DAI)$")

REST_BASE_URL = "https://api.radarrelay.com/v3"
TOKENS_URL = f"{REST_BASE_URL}/tokens"
MARKETS_URL = f"{REST_BASE_URL}/markets"
WS_URL = "wss://ws.radarrelay.com/v3"


class RadarRelayAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _rraobds_logger: Optional[HummingbotLogger] = None
    _client: Optional[aiohttp.ClientSession] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._rraobds_logger is None:
            cls._rraobds_logger = logging.getLogger(__name__)
        return cls._rraobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)
        self.order_book_create_function = lambda: RadarRelayOrderBook()

    @classmethod
    def http_client(cls) -> aiohttp.ClientSession:
        if cls._client is None:
            if not asyncio.get_event_loop().is_running():
                raise EnvironmentError("Event loop must be running to start HTTP client session.")
            cls._client = aiohttp.ClientSession()
        return cls._client

    @classmethod
    async def get_all_token_info(cls) -> Dict[str, any]:
        """
        Returns all token information
        """
        client: aiohttp.ClientSession = cls.http_client()
        async with client.get(TOKENS_URL) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching token info. HTTP status is {response.status}.")
            data = await response.json()
            return {d["address"]: d for d in data}

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have trading pair as index and include usd volume, baseAsset and quoteAsset
        """
        client: aiohttp.ClientSession = cls.http_client()
        async with client.get(f"{MARKETS_URL}?include=ticker,stats") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching active Radar Relay markets. HTTP status is {response.status}.")
            data = await response.json()
            data: List[Dict[str, any]] = [
                {**item, **{"baseAsset": item["id"].split("-")[0], "quoteAsset": item["id"].split("-")[1]}}
                for item in data
            ]
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data, index="id")

            quote_volume: List[float] = []
            for row in all_markets.itertuples():
                base_volume: float = float(row.stats["volume24Hour"])
                quote_volume.append(base_volume)

            all_markets.loc[:, "volume"] = quote_volume
            return all_markets.sort_values("USDVolume", ascending=False)

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            trading_pairs = set()
            page_count = 1
            while True:
                async with aiohttp.ClientSession() as client:
                    async with client.get(f"{MARKETS_URL}?perPage=100&page={page_count}", timeout=10) \
                            as response:
                        if response.status == 200:
                            markets = await response.json()
                            new_trading_pairs = set(map(lambda details: details.get('id'), markets))
                            if len(new_trading_pairs) == 0:
                                break
                            else:
                                trading_pairs = trading_pairs.union(new_trading_pairs)
                            page_count += 1
                            trading_pair_list: List[str] = []
                            for raw_trading_pair in trading_pairs:
                                trading_pair_list.append(raw_trading_pair)
                            return trading_pair_list
                        else:
                            break
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for radar trading pairs
            pass

        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, any]:
        async with client.get(f"{REST_BASE_URL}/markets/{trading_pair}/book") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Radar Relay market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            return await response.json()

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: RadarRelayOrderBookMessage = RadarRelayOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )

            radar_relay_order_book: OrderBook = self.order_book_create_function()
            radar_relay_active_order_tracker: RadarRelayActiveOrderTracker = RadarRelayActiveOrderTracker()
            bids, asks = radar_relay_active_order_tracker.convert_snapshot_message_to_order_book_row(
                snapshot_msg)
            radar_relay_order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return radar_relay_order_book

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
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
        # Trade messages are received from the order book web socket
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        request: Dict[str, str] = {
                            "type": "SUBSCRIBE",
                            "topic": "BOOK",
                            "market": trading_pair
                        }
                        await ws.send(ujson.dumps(request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        # Valid Diff messages from RadarRelay have action key
                        if "action" in msg:
                            diff_msg: RadarRelayOrderBookMessage = RadarRelayOrderBook.diff_message_from_exchange(
                                msg, time.time())
                            output.put_nowait(diff_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                client: aiohttp.ClientSession = self.http_client()
                for trading_pair in trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = RadarRelayOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
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
