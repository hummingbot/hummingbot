#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.market.coinbase_pro.coinbase_pro_order_book import CoinbaseProOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils import async_ttl_cache
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.market.coinbase_pro.coinbase_pro_active_order_tracker import CoinbaseProActiveOrderTracker
from hummingbot.market.coinbase_pro.coinbase_pro_order_book_tracker_entry import CoinbaseProOrderBookTrackerEntry

COINBASE_REST_URL = "https://api.pro.coinbase.com"
COINBASE_WS_FEED = "wss://ws-feed.pro.coinbase.com"
MAX_RETRIES = 20
NaN = float("nan")


class CoinbaseProAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _cbpaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpaobds_logger is None:
            cls._cbpaobds_logger = logging.getLogger(__name__)
        return cls._cbpaobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        *required
        Returns all currently active BTC trading pairs from Coinbase Pro, sorted by volume in descending order.
        """
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{COINBASE_REST_URL}/products") as products_response:
                products_response: aiohttp.ClientResponse = products_response
                if products_response.status != 200:
                    raise IOError(f"Error fetching active Coinbase Pro markets. HTTP status is {products_response.status}.")
                data = await products_response.json()
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data, index="id")
                all_markets.rename({"base_currency": "baseAsset", "quote_currency": "quoteAsset"},
                                   axis="columns", inplace=True)
                ids: List[str] = list(all_markets.index)
                volumes: List[float] = []
                prices: List[float] = []
                for product_id in ids:
                    ticker_url: str = f"{COINBASE_REST_URL}/products/{product_id}/ticker"
                    should_retry: bool = True
                    retry_counter: int = 0
                    while should_retry:
                        async with client.get(ticker_url) as ticker_response:
                            retry_counter += 1
                            ticker_response: aiohttp.ClientResponse = ticker_response
                            if ticker_response.status == 200:
                                data: Dict[str, Any] = await ticker_response.json()
                                should_retry = False
                                volumes.append(float(data.get("volume", NaN)))
                                prices.append(float(data.get("price", NaN)))
                            elif ticker_response.status != 429 or retry_counter == MAX_RETRIES:
                                raise IOError(f"Error fetching ticker for {product_id} on Coinbase Pro. "
                                              f"HTTP status is {ticker_response.status}.")
                            await asyncio.sleep(0.5)
                all_markets["volume"] = volumes
                all_markets["price"] = prices
                btc_usd_price: float = all_markets.loc["BTC-USD"].price
                eth_usd_price: float = all_markets.loc["ETH-USD"].price
                btc_eur_price: float = all_markets.loc["BTC-EUR"].price
                btc_gbp_price: float = all_markets.loc["BTC-GBP"].price
                usd_volume: List[float] = []
                for row in all_markets.itertuples():
                    product_name: str = row.Index
                    quote_volume: float = row.volume
                    quote_price: float = row.price
                    if product_name.endswith(("USD", "USDC", "USDS", "DAI", "PAX", "TUSD", "USDT")):
                        usd_volume.append(quote_volume * quote_price)
                    elif product_name.endswith("BTC"):
                        usd_volume.append(quote_volume * quote_price * btc_usd_price)
                    elif product_name.endswith("ETH"):
                        usd_volume.append(quote_volume * quote_price * eth_usd_price)
                    elif product_name.endswith("EUR"):
                        usd_volume.append(quote_volume * quote_price * (btc_usd_price / btc_eur_price))
                    elif product_name.endswith("GBP"):
                        usd_volume.append(quote_volume * quote_price * (btc_usd_price / btc_gbp_price))
                    else:
                        usd_volume.append(NaN)
                        cls.logger().error(f"Unable to convert volume to USD for market - {product_name}.")
                all_markets["USDVolume"] = usd_volume
                return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> List[str]:
        """
        *required
        Get a list of active trading pairs
        (if the market class already specifies a list of trading pairs,
        returns that list instead of all active trading pairs)
        :returns: A list of trading pairs defined by the market class, or all active trading pairs from the rest API
        """
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
            except Exception:
                self._trading_pairs = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, any]:
        """
        Fetches order book snapshot for a particular trading pair from the rest API
        :returns: Response from the rest API
        """
        product_order_book_url: str = f"{COINBASE_REST_URL}/products/{trading_pair}/book?level=3"
        async with client.get(product_order_book_url) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Coinbase Pro market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        """
        *required
        Initializes order books and order book trackers for the list of trading pairs
        returned by `self.get_trading_pairs`
        :returns: A dictionary of order book trackers for each trading pair
        """
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, OrderBookTrackerEntry] = {}

            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = CoinbaseProOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    active_order_tracker: CoinbaseProActiveOrderTracker = CoinbaseProActiveOrderTracker()
                    bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = CoinbaseProOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        order_book,
                        active_order_tracker
                    )
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")
                    await asyncio.sleep(0.6)
                except IOError:
                    self.logger().network(
                        f"Error getting snapshot for {trading_pair}.",
                        exc_info=True,
                        app_warning_msg=f"Error getting snapshot for {trading_pair}. Check network connection."
                    )
                except Exception:
                    self.logger().error(f"Error initializing order book for {trading_pair}. ", exc_info=True)
            return retval

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
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
        """
        *required
        Subscribe to diff channel via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(COINBASE_WS_FEED) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "type": "subscribe",
                        "product_ids": trading_pairs,
                        "channels": ["full"]
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("type", None)
                        if msg_type is None:
                            raise ValueError(f"Coinbase Pro Websocket message does not contain a type - {msg}")
                        elif msg_type == "error":
                            raise ValueError(f"Coinbase Pro Websocket received error message - {msg['message']}")
                        elif msg_type in ["open", "match", "change", "done"]:
                            if msg_type == "done" and "price" not in msg:
                                # done messages with no price are completed market orders which can be ignored
                                continue
                            order_book_message: OrderBookMessage = CoinbaseProOrderBook.diff_message_from_exchange(msg)
                            output.put_nowait(order_book_message)
                        elif msg_type in ["received", "activate", "subscriptions"]:
                            # these messages are not needed to track the order book
                            continue
                        else:
                            raise ValueError(f"Unrecognized Coinbase Pro Websocket message received - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    f"Check network connection."
                )
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Fetches order book snapshots for each trading pair, and use them to update the local order book
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = CoinbaseProOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"product_id": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            # Be careful not to go above API rate limits.
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().network(
                                f"Unexpected error with WebSocket connection.",
                                exc_info=True,
                                app_warning_msg=f"Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                                f"Check network connection."
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
