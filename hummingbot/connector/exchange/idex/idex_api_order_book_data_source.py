import asyncio
import aiohttp
import logging

import cachetools.func
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
from decimal import Decimal
import time

import requests
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource

# import with change to get_last_traded_prices
from hummingbot.core.utils.async_utils import safe_gather

from hummingbot.connector.exchange.idex.idex_active_order_tracker import IdexActiveOrderTracker
from hummingbot.connector.exchange.idex.idex_order_book_tracker_entry import IdexOrderBookTrackerEntry
from hummingbot.connector.exchange.idex.idex_order_book import IdexOrderBook
from hummingbot.connector.exchange.idex.idex_resolve import get_idex_rest_url, get_idex_ws_feed
from hummingbot.connector.exchange.idex.idex_utils import DEBUG

MAX_RETRIES = 20
NaN = float("nan")


class IdexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _IDEX_REST_URL: str = None
    _IDEX_WS_FEED: str = None

    _iaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._iaobds_logger is None:
            cls._iaobds_logger = logging.getLogger(__name__)
        return cls._iaobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)

    # Found last trading price in Idex API. Utilized safe_gather to complete all tasks and append last trade prices
    # for all trading pairs on results list.
    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str], domain=None) -> Dict[str, float]:
        base_url: str = get_idex_rest_url(domain=domain)
        tasks = [cls.get_last_traded_price(t_pair, base_url) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @staticmethod
    async def get_last_traded_price(trading_pair: str, base_url: str = "https://api-eth.idex.io") -> float:
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{base_url}/v1/trades/?market={trading_pair}")
            resp_json = await resp.json()
            # based on previous GET requests to the Idex trade URL, the most recent trade is located at the -1 index
            # of the returned list of trades. This assumes pop() on the returned list is the optimal solution for
            # retrieving the latest trade.
            last_trade = resp_json[-1]
            return float(last_trade["price"])

    @classmethod
    @cachetools.func.ttl_cache(ttl=10)
    def get_mid_price(cls, trading_pair: str, domain=None) -> Optional[Decimal]:
        base_url: str = get_idex_rest_url(domain=domain)
        ticker_url: str = f"{base_url}/v1/tickers?market={trading_pair}"
        resp = requests.get(ticker_url)
        market = resp.json()
        if market.get('bid') and market.get('ask'):
            result = (Decimal(market['bid']) + Decimal(market['ask'])) / Decimal('2')
            return result

    @staticmethod
    async def fetch_trading_pairs(domain=None) -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                # ensure IDEX_REST_URL has appropriate blockchain imported (ETH or BSC)
                base_url: str = get_idex_rest_url(domain=domain)
                async with client.get(f"{base_url}/v1/tickers", timeout=5) as response:
                    if response.status == 200:
                        markets = await response.json()
                        raw_trading_pairs: List[str] = list(map(lambda details: details.get('market'), markets))
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in raw_trading_pairs:
                            trading_pair_list.append(raw_trading_pair)
                        return trading_pair_list

        except Exception:
            # Do nothing if request fails. No autocomplete for trading pairs.
            pass

        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        """
        Fetches order book snapshot for a particular trading pair from the rest API
        :returns: Response from the rest API
        """
        # idex level 2 order book is sufficient to provide required data
        base_url: str = get_idex_rest_url()
        product_order_book_url: str = f"{base_url}/v1/orderbook?market={trading_pair}&level=2"
        async with client.get(product_order_book_url) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching IDEX market snapshot for {trading_pair}."
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = IdexOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
            active_order_tracker: IdexActiveOrderTracker = IdexActiveOrderTracker()
            bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
            order_book = self.order_book_create_function()
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        """
        *required
        Initializes order books and order book trackers for the list of trading pairs
        returned by `self.fetch_trading_pairs`
        :returns: A dictionary of order book trackers for each trading pair
        """
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = self._trading_pairs
            retval: Dict[str, OrderBookTrackerEntry] = {}

            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = IdexOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    active_order_tracker: IdexActiveOrderTracker = IdexActiveOrderTracker()
                    bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = IdexOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        order_book,
                        active_order_tracker
                    )
                    self.logger().info(f"Initialized order book for {trading_pair}."
                                       f"{index + 1}/{number_of_pairs} completed.")
                    await asyncio.sleep(0.6)
                except IOError:
                    self.logger().network(
                        f"Error getting snapshot for {trading_pair}.",
                        exc_info=True,
                        app_warning_msg=f"Error getting snapshot for {trading_pair}. Check network connection."
                    )
                except Exception:
                    self.logger().error(f"Error initializing order book for {trading_pair}.", exc_info=True)
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
            self.logger().warning("Websock ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to trade channel via Idex WebSocket and keep the connection open for incoming messages.

        WebSocket trade subscription response example:
            {
            "type": "trades",
            "data": {
                    "m": "ETH-USDC",
                    "i": "a0b6a470-a6bf-11ea-90a3-8de307b3b6da",
                    "p": "202.74900000",
                    "q": "10.00000000",
                    "Q": "2027.49000000",
                    "t": 1590394500000,
                    "s": "sell",
                    "u": 848778
                    }
            }

        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            idex_ws_feed = get_idex_ws_feed()
            if DEBUG:
                self.logger().info("IOB.listen_for_trades new connection to ws: %s", idex_ws_feed)
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(idex_ws_feed) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscription_request: Dict[str, Any] = {
                        "method": "subscribe",
                        "markets": trading_pairs,
                        "subscriptions": ["trades"]
                    }
                    await ws.send(ujson.dumps(subscription_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("type", None)
                        if DEBUG:
                            self.logger().info('<<<<< ws msg: %s', msg)
                        if msg_type is None:
                            raise ValueError(f"Idex Websocket message does not contain a type - {msg}")
                        elif msg_type == "error":
                            raise ValueError(f"Idex Websocket received error message - {msg['data']['message']}")
                        elif msg_type == "trades":
                            trade_timestamp: float = pd.Timestamp(msg["data"]["t"], unit="ms").timestamp()
                            trade_msg: OrderBookMessage = IdexOrderBook.trade_message_from_exchange(msg,
                                                                                                    trade_timestamp)
                            output.put_nowait(trade_msg)
                        elif msg_type == "subscriptions":
                            self.logger().info("subscription to trade received")
                        else:
                            raise ValueError(f"Unrecognized Idex WebSocket message received - {msg}")
                        await asyncio.sleep(0)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f'{"Unexpected error with WebSocket connection."}',
                    exc_info=True,
                    app_warning_msg=f'{"Unexpected error with Websocket connection. Retrying in 30 seconds..."}'
                                    f'{"Check network connection."}'
                )
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to  channel via web socket, and keep the connection open for incoming messages

        WebSocket trade subscription response example:
            {
                "type": "l2orderbook",
                "data": {
                        "m": "ETH-USDC",
                        "t": 1590393540000,
                        "u": 71228110,
                        "b": [["202.00100000", "10.00000000", 1]],
                        "a": []
                        }
            }
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            idex_ws_feed = get_idex_ws_feed()
            if DEBUG:
                self.logger().info("IOB.listen_for_order_book_diffs new connection to ws: %s", idex_ws_feed)
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(idex_ws_feed) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscription_request: Dict[str, Any] = {
                        "method": "subscribe",
                        "markets": trading_pairs,
                        "subscriptions": ["l2orderbook"]
                    }
                    await ws.send(ujson.dumps(subscription_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("type", None)
                        if DEBUG:
                            self.logger().info('<<<<< ws msg: %s', msg)
                        if msg_type is None:
                            raise ValueError(f"Idex WebSocket message does not contain a type - {msg}")
                        elif msg_type == "error":
                            raise ValueError(f"Idex WebSocket message received error message - "
                                             f"{msg['data']['message']}")
                        elif msg_type == "l2orderbook":
                            diff_timestamp: float = pd.Timestamp(msg["data"]["t"], unit="ms").timestamp()
                            order_book_message: OrderBookMessage = \
                                IdexOrderBook.diff_message_from_exchange(msg, diff_timestamp)
                            output.put_nowait(order_book_message)
                        elif msg_type == "subscriptions":
                            self.logger().info("subscription to l2orderbook received")
                        else:
                            raise ValueError(f"Unrecognized Idex WebSocket message received - {msg}")
                        await asyncio.sleep(0)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f'{"Unexpected error with WebSocket connection."}',
                    exc_info=True,
                    app_warning_msg=f'{"Unexpected error with WebSocket connection. Retrying in 30 seconds."}'
                                    f'{"Check network connection."}'
                )
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with aiohttp.ClientSession() as client:
                    for trading_pair in self._trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            if DEBUG:
                                self.logger().info('<<<<< aiohttp snapshot response: %s', snapshot)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = IdexOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            if DEBUG:
                                self.logger().info(f"Saved orderbook snapshot for {trading_pair}")
                            # Be careful not to go above API rate limits
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
