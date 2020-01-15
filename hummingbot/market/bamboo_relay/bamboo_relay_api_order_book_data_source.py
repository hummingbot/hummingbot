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
from decimal import Decimal
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.ssl_client_request import SSLClientRequest
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bamboo_relay.bamboo_relay_order_book import BambooRelayOrderBook
from hummingbot.market.bamboo_relay.bamboo_relay_active_order_tracker import BambooRelayActiveOrderTracker
from hummingbot.market.bamboo_relay.bamboo_relay_order_book_message import BambooRelayOrderBookMessage
from hummingbot.market.bamboo_relay.bamboo_relay_order_book_tracker_entry import BambooRelayOrderBookTrackerEntry
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.market.bamboo_relay.bamboo_relay_constants import (
    BAMBOO_RELAY_REST_ENDPOINT,
    BAMBOO_RELAY_TEST_ENDPOINT,
    BAMBOO_RELAY_REST_WS,
    BAMBOO_RELAY_TEST_WS
)

TRADING_PAIR_FILTER = re.compile(r"(WETH|DAI|CUSD|USDC|TUSD)$")


class BambooRelayAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _braobds_logger: Optional[HummingbotLogger] = None
    _client: Optional[aiohttp.ClientSession] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._braobds_logger is None:
            cls._braobds_logger = logging.getLogger(__name__)
        return cls._braobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None, chain: EthereumChain = EthereumChain.MAIN_NET):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._motd_done = False
        if chain is EthereumChain.ROPSTEN:
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "ropsten/0x"
            self._api_ws = BAMBOO_RELAY_REST_WS
            self._network_id = 3
        elif chain is EthereumChain.RINKEBY:
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "rinkeby/0x"
            self._api_ws = BAMBOO_RELAY_REST_WS
            self._network_id = 4
        elif chain is EthereumChain.KOVAN:
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "kovan/0x"
            self._api_ws = BAMBOO_RELAY_REST_WS
            self._network_id = 42
        elif chain is EthereumChain.ZEROEX_TEST:
            self._api_endpoint = BAMBOO_RELAY_TEST_ENDPOINT
            self._api_prefix = "testrpc/0x"
            self._api_ws = BAMBOO_RELAY_TEST_WS
            self._network_id = 1337
        else:
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "main/0x"
            self._api_ws = BAMBOO_RELAY_REST_WS
            self._network_id = 1

    @classmethod
    def http_client(cls) -> aiohttp.ClientSession:
        if cls._client is None:
            if not asyncio.get_event_loop().is_running():
                raise EnvironmentError("Event loop must be running to start HTTP client session.")
            cls._client = aiohttp.ClientSession(request_class=SSLClientRequest)
        return cls._client

    @classmethod
    async def get_all_token_info(cls,
                                 api_endpoint: str = "https://rest.bamboorelay.com/",
                                 api_prefix: str = "") -> Dict[str, any]:
        """
        Returns all token information
        """
        client: aiohttp.ClientSession = cls.http_client()
        async with client.get(f"{api_endpoint}{api_prefix}/tokens?perPage=1000") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching token info. HTTP status is {response.status}.")
            data = await response.json()
            return {d["address"]: d for d in data}

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls,
                                          api_endpoint: str = "https://rest.bamboorelay.com/",
                                          api_prefix: str = "main/0x") -> pd.DataFrame:
        """
        Returned data frame should have trading_pair as index and include usd volume, baseAsset and quoteAsset
        """
        client: aiohttp.ClientSession = cls.http_client()
        async with client.get(f"{api_endpoint}{api_prefix}/markets?perPage=1000&include=ticker,stats") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching active Bamboo Relay markets. HTTP status is {response.status}.")
            data = await response.json()
            data: List[Dict[str, any]] = [
                {**item, **{"baseAsset": item["id"].split("-")[0], "quoteAsset": item["id"].split("-")[1]}}
                for item in data
            ]
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data, index="id")

            weth_dai_price: Decimal = Decimal(ExchangeRateConversion.get_instance().convert_token_value(
                1.0, from_currency="WETH", to_currency="DAI"
            ))
            dai_usd_price: float = float(ExchangeRateConversion.get_instance().adjust_token_rate("DAI", weth_dai_price))
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

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession,
                           trading_pair: str,
                           api_endpoint: str = "https://rest.bamboorelay.com/",
                           api_prefix: str = "main/0x") -> Dict[str, any]:
        async with client.get(f"{api_endpoint}{api_prefix}/markets/{trading_pair}/book") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Bamboo Relay market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            return await response.json()

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets(self._api_endpoint, self._api_prefix)
                self._trading_pairs = active_markets.index.tolist()
            except Exception:
                self._trading_pairs = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, OrderBookTrackerEntry] = {}

            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair, self._api_endpoint, self._api_prefix)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: BambooRelayOrderBookMessage = BambooRelayOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )

                    bamboo_relay_order_book: OrderBook = self.order_book_create_function()
                    bamboo_relay_active_order_tracker: BambooRelayActiveOrderTracker = BambooRelayActiveOrderTracker()
                    bids, asks = bamboo_relay_active_order_tracker.convert_snapshot_message_to_order_book_row(
                        snapshot_msg)
                    bamboo_relay_order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = BambooRelayOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        bamboo_relay_order_book,
                        bamboo_relay_active_order_tracker
                    )
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")

                    await asyncio.sleep(0.9)

                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5.0)
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

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Trade messages are received from the order book web socket
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(self._api_ws) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    if not self._motd_done:
                        try:
                            raw_msg = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                            msg = ujson.loads(raw_msg)
                            # Print MOTD and announcements if present
                            if "motd" in msg:
                                self._motd_done = True
                                self.logger().info(f"Bamboo Relay API MOTD: {msg['motd']}")
                                if "announcements" in msg and len(msg["announcements"]):
                                    for announcement in msg["announcements"]:
                                        self.logger().info(f"Announcement: {announcement}")
                        except Exception:
                            pass
                    for trading_pair in trading_pairs:
                        request: Dict[str, str] = {
                            "type": "SUBSCRIBE",
                            "topic": "BOOK",
                            "market": trading_pair,
                            "networkId": self._network_id
                        }
                        await ws.send(ujson.dumps(request))
                    async for raw_msg in self._inner_messages(ws):
                        # Try here, else any errors cause the websocket to disconnect
                        try:
                            msg = ujson.loads(raw_msg)
                            # Valid Diff messages from BambooRelay have actions array
                            if "actions" in msg:
                                diff_msg: BambooRelayOrderBookMessage = BambooRelayOrderBook.diff_message_from_exchange(
                                    msg, time.time())
                                output.put_nowait(diff_msg)
                        except Exception:
                            pass
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
                        snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair, self._api_endpoint, self._api_prefix)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = BambooRelayOrderBook.snapshot_message_from_exchange(
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
