#!/usr/bin/env python

import asyncio

import aiohttp
import logging
import pandas as pd
import uuid
from typing import List, Optional, Dict, Any
import time
from random import randint
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.market.kyber.kyber_active_order_tracker import KyberActiveOrderTracker
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.market.kyber.kyber_order_book import KyberOrderBook
from hummingbot.market.kyber.kyber_order_book_tracker_entry import KyberOrderBookTrackerEntry
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain


class KyberAPIOrderBookDataSource(OrderBookTrackerDataSource):

    KYBER_MAINNET_REST_ENDPOINT = "https://api.kyber.network"
    KYBER_ROPSTEN_REST_ENDPOINT = "https://ropsten-api.kyber.network"
    MARKET_URL = "/market"
    BUY_RATE = "/buy_rate"
    SELL_RATE = "/sell_rate"
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    __daobds__logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.__daobds__logger is None:
            cls.__daobds__logger = logging.getLogger(__name__)
        return cls.__daobds__logger

    def __init__(self, trading_pairs: Optional[List[str]] = None, chain: EthereumChain = EthereumChain.MAIN_NET):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._active_markets = None
        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()
        if chain is EthereumChain.MAIN_NET:
            self._api_endpoint = self.KYBER_MAINNET_REST_ENDPOINT
        elif chain is EthereumChain.ROPSTEN:
            self._api_endpoint = self.KYBER_ROPSTEN_REST_ENDPOINT

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls, api_endpoint: str = KYBER_MAINNET_REST_ENDPOINT) -> pd.DataFrame:
        async with aiohttp.ClientSession() as client:
            markets_response: aiohttp.ClientResponse = await client.get(f"{api_endpoint}{cls.MARKET_URL}")
            if markets_response.status != 200:
                raise IOError(f"Error fetching active Kyber markets. HTTP status is {markets_response.status}.")
            markets_data = await markets_response.json()
            markets_data = markets_data["data"]
            field_mapping = {
                "pair": "market",
                "base_symbol": "baseAsset",
                "quote_symbol": "quoteAsset",
                "usd_24h_volume": "USDVolume",
                "base_address": "id"
            }

            all_markets: pd.DataFrame = pd.DataFrame.from_records(
                data=markets_data, index="pair", columns=list(field_mapping.keys())
            )
            all_markets.rename(field_mapping, axis="columns", inplace=True)
            return all_markets.sort_values("USDVolume", ascending=False)

    @property
    async def exchange_name(self) -> str:
        return "kyber"

    @property
    def order_book_class(self) -> KyberOrderBook:
        return KyberOrderBook

    async def fetch(url, session):
        async with session.get(url) as response:
            return await response.read()

    async def api_request(self,
                          client: aiohttp.ClientSession,
                          http_method: str,
                          url: str,
                          params: Optional[List[Any]] = None) -> Dict[str, Any]:
        async with client.request(http_method,
                                  url=url,
                                  params=params) as response:
            if response.status != 200:
                raise IOError(f"Error fetching Kyber market snapshot from {url}. HTTP status is {response.status}.")
            response_data = await response.json()

            return response_data

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, any]:
        base_address = self._active_markets.loc[trading_pair, 'id']

        bids = []
        asks = []
        buy_params = []
        sell_params = []

        # 10 is max limit for params in 1 API call to Kyber
        for i in range(10):
            buy_params.append(("id", base_address))
            buy_params.append(("qty", randint(1, 300)))

            sell_params.append(("id", base_address))
            sell_params.append(("qty", randint(1, 300)))

        url = f"{self._api_endpoint}{self.BUY_RATE}"
        buy_response = await self.api_request(client, "get", url, buy_params)

        for item in buy_response["data"]:
            bid = {"orderId": str(uuid.uuid4()),
                   "amount_base": item["dst_qty"][0],
                   "amount_quote": item["src_qty"][0],
                   "price": item["src_qty"][0] / item["dst_qty"][0]}
            bids.append(bid)

        # params: Dict = {"id": base_address, "qty": randint(1, 300)}

        url = f"{self._api_endpoint}{self.SELL_RATE}"
        sell_response = await self.api_request(client, "get", url, sell_params)

        for item in sell_response["data"]:
            ask = {"orderId": str(uuid.uuid4()),
                   "amount_base": item["src_qty"][0],
                   "amount_quote": item["dst_qty"][0],
                   "price": item["dst_qty"][0] / item["src_qty"][0]}
            asks.append(ask)
        snapshot = {"data": {"orderBook": {"marketId": base_address, "bids": bids, "asks": asks}}}
        return snapshot

    async def get_tracking_pairs(self):
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()

            retval: Dict[str, KyberOrderBookTrackerEntry] = {}

            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg = KyberOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        {"marketId": trading_pair}
                    )

                    kyber_order_book: OrderBook = self.order_book_create_function()
                    kyber_active_order_tracker: KyberActiveOrderTracker = KyberActiveOrderTracker()

                    bids, asks = kyber_active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)

                    kyber_order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
                    retval[trading_pair] = KyberOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        kyber_order_book,
                        kyber_active_order_tracker
                    )
                    return retval
                except IOError:
                    self.logger().network(
                        f"Error getting snapshot for {trading_pair}.",
                        exc_info=True,
                        app_warning_msg=f"Error getting snapshot for {trading_pair}. Check network connection."
                    )
                    await asyncio.sleep(5.0)
                except Exception:
                    self.logger().error(f"Error initializing order book for {trading_pair}.", exc_info=True)
                    await asyncio.sleep(5.0)

    async def get_trading_pairs(self) -> List[str]:
        if self._active_markets is None:
            self._active_markets: pd.DataFrame = await self.get_active_exchange_markets(self._api_endpoint)

        if not self._trading_pairs:
            try:
                self._trading_pairs = self._active_markets.index.tolist()
            except Exception:
                self._trading_pairs = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
