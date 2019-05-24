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

from hummingbot.market.bamboo_relay.bamboo_relay_order_book import BambooRelayOrderBook
from hummingbot.market.bamboo_relay.bamboo_relay_active_order_tracker import BambooRelayActiveOrderTracker
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry, BambooRelayOrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage, BambooRelayOrderBookMessage
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.logger import HummingbotLogger

TRADING_PAIR_FILTER = re.compile(r"(WETH|DAI|CUSD)$")

REST_BASE_URL = "https://rest.bamboorelay.com/main/0x"
TOKENS_URL = f"{REST_BASE_URL}/tokens"
MARKETS_URL = f"{REST_BASE_URL}/markets"
WS_URL = "wss://rest.bamboorelay.com/0x/ws"


class BambooRelayAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _rraobds_logger: Optional[HummingbotLogger] = None
    _client: Optional[aiohttp.ClientSession] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._rraobds_logger is None:
            cls._rraobds_logger = logging.getLogger(__name__)
        return cls._rraobds_logger

    def __init__(self, symbols: Optional[List[str]] = None):
        super().__init__()
        self._symbols: Optional[List[str]] = symbols

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
        async with client.get(f"{TOKENS_URL}?perPage=1000") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching token info. HTTP status is {response.status}.")
            data = await response.json()
            return {d["address"]: d for d in data}

    @classmethod
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have symbol as index and include usd volume, baseAsset and quoteAsset
        """
        client: aiohttp.ClientSession = cls.http_client()
        async with client.get(f"{MARKETS_URL}?include=ticker,stats") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching active Bamboo Relay markets. HTTP status is {response.status}.")
            data = await response.json()
            data: List[Dict[str, any]] = [
                {**item, **{"baseAsset": item["id"].split("-")[0], "quoteAsset": item["id"].split("-")[1]}}
                for item in data
            ]
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data, index="id")

            weth_dai_price: float = 1 / float(all_markets.loc["DAI-WETH"]["ticker"]["price"])
            dai_usd_price: float = ExchangeRateConversion.get_instance().adjust_token_rate("DAI", weth_dai_price)
            usd_volume: List[float] = []
            quote_volume: List[float] = []
            for row in all_markets.itertuples():
                product_name: str = row.Index
                base_volume: float = float(row.stats["volume24Hour"])
                quote_volume.append(base_volume)
                if product_name.endswith("WETH"):
                    usd_volume.append(dai_usd_price * base_volume)
                else:
                    usd_volume.append(base_volume)

            all_markets.loc[:, "USDVolume"] = usd_volume
            all_markets.loc[:, "volume"] = quote_volume
            return all_markets.sort_values("USDVolume", ascending=False)

    @property
    def order_book_class(self) -> BambooRelayOrderBook:
        return BambooRelayOrderBook

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, any]:
        async with client.get(f"{REST_BASE_URL}/markets/{trading_pair}/book") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Bamboo Relay market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            return await response.json()

    async def get_trading_pairs(self) -> List[str]:
        if self._symbols is None:
            active_markets: pd.DataFrame = await self.get_active_exchange_markets()
            trading_pairs: List[str] = active_markets.index.tolist()
        else:
            trading_pairs: List[str] = self._symbols
        return trading_pairs

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, OrderBookTrackerEntry] = {}

            for trading_pair in trading_pairs:
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: BambooRelayOrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"symbol": trading_pair}
                    )

                    bamboo_relay_order_book: BambooRelayOrderBook = BambooRelayOrderBook()
                    bamboo_relay_active_order_tracker: BambooRelayActiveOrderTracker = BambooRelayActiveOrderTracker()
                    bids, asks = bamboo_relay_active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    bamboo_relay_order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = BambooRelayOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        bamboo_relay_order_book,
                        bamboo_relay_active_order_tracker
                    )

                    await asyncio.sleep(0.7)

                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
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

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
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
                        # Valid Diff messages from BambooRelay have action key
                        if "action" in msg:
                            diff_msg: BambooRelayOrderBookMessage = self.order_book_class.diff_message_from_exchange(
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
                trading_pairs: List[str] = await self.get_trading_pairs()
                client: aiohttp.ClientSession = self.http_client()
                for trading_pair in trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"symbol": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().info(f"Saved order book snapshot for {trading_pair}")

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
