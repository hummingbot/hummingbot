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
from decimal import Decimal
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

import requests
import cachetools.func

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.exchange.idex.idex_order_book import IdexOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.exchange.idex.idex_active_order_tracker import IdexActiveOrderTracker
from hummingbot.core.utils.async_utils import safe_gather

# imports from IDEX-specific build - maintain for now until module can stand apart from them
from .client.asyncio import AsyncIdexClient
from .utils import to_idex_pair, get_markets, from_idex_trade_type
from .types.websocket.response import WebSocketResponseL2OrderBookShort, WebSocketResponseTradeShort

# Need to import selected blockchain connection
IDEX_REST_URL = f"https://api-{blockchain}.idex.io/"
IDEX_WS_FEED = f"wss://websocket-{blockchain}.idex.io/v1"
MAX_RETRIES = 20
NaN = float("nan")


class IdexAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        # trading_pairs already provided in the parameter. Require an additional GET request for prices. Will zip both lists together to product Dict.
        async with aiohttp.ClientSession() as client:
            ticker_url: str = f"{IDEX_REST_URL}/v1/tickers"
            resp = await client.get(ticker_url)
            markets = await resp.json()
            # lastFillPrice not provided in IDEX API as of 25 February 2021. "ask" price is used as stand-in value at this time.
            raw_trading_pair_prices: List[float] = list(map(lambda details: details.get('ask'), markets))
            trading_pair_price_list: List[float]
            for raw_trading_pair_price in raw_trading_pair_prices:
                trading_pair_price_list.append(raw_trading_pair_price)
            return {trading_pair: price for trading_pair, price in zip(trading_pairs, trading_pair_price_list)}

    @classmethod
    @cachetools.func.ttl_cache(ttl=10)
    def get_mid_price(trading_pair: str) -> Optional[Decimal]:
        async with aiohttp.ClientSession() as client:
            # IDEX API does not provide individual ask/bid request capability. Must search for trading_pair each time get_mid_price is called.
            ticker_url: str = str = f"{IDEX_REST_URL}/v1/tickers"
            resp = await client.get(ticker_url)
            markets = await resp.json()
            for market in markets:
                if (market.get('market') == trading_pair):
                    if (market.get('bid') and market.get('ask')):
                        result = (Decimal(market['bid']) + Decimal(market['ask'])) / Decimal("2")
                        return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                # ensure IDEX_REST_URL has appropriate blockchain imported (ETH or BSC)
                async with client.get(f"{IDEX_REST_URL}/v1/tickers", timeout=5) as response:
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
        product_order_book_url: str = f"{IDEX_REST_URL}/v1/orderbook?market={trading_pair}&level=2/"
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
            # IDEXOrderBook not yet complete as of 25 Feb 2021
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
                        # Confirm whether there is a trading
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()

                    retval[trading_pair] = IdexOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        order_book,
                        active_order_tracker
                    )
                    self.logger().info(f"Initialized order book for {trading pair}."
                                       f"{index+1}/{number_of_pairs} completed.")
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
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(IDEX_WS_FEED) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = 
                    {
                        "method": "subscribe",
                        "markets": trading_pairs,
                        "subscriptions": [
                            "trades"
                        ]
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg) 
                        msg_type: str = msg.get("type", None)
                        if msg_type is None:
                            raise ValueError(f"Idex Websocket message does not contain a type - {msg}"
                        elif msg_type == "error":
                            raise ValueError(f"Idex Websocket received error message - {msg['data']['message']}")
                        elif msg_type == "trades":
                            trade_msg: OrderBookMessage = IdexOrderBook.trade_message_from_exchange(msg)
                            output.put_nowait(trade_msg)
                        else:
                            raise ValueError(f"Unrecognized Idex WebSocket message received - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f'{"Unexpected error with WebSocket connection."}',
                    exc_info=True,
                    app_warning_msg=f'{"Unexpected error with Websocket connection. Retrying in 30 seconds..."}'
                                    f'{"Check network connection."}'
                    )

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
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(IDEX_WS_FEED) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = 
                    {
                        "method": "subscribe",
                        "markets": trading_pairs,
                        "subscriptions": [
                            "l2orderbook"
                        ]
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("type", None)
                        if msg_type is None:
                            raise ValueError(f"Idex WebSocket message does not contain a type - {msg}")
                        elif msg_type == "error":
                            raise ValueError(f"Idex WebSocket message received error message - {msg['data']['message']}")
                        elif msg_type == "l2orderbook":
                            order_book_message: OrderBookMessage = IdexOrderBook.diff_message_from_exchange(msg)
                            output.put_nowait(order_book_message)
                        else:
                            raise ValueError(f"Unrecognized Idex WebSocket message received - {msg}")
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
                client = AsyncIdexClient()
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot = await client.market.get_orderbook(
                            market=trading_pair
                        )
                        timestamp = time.time()
                        snapshot_message = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
                            "trading_pair": trading_pair,
                            "update_id": snapshot.sequence,
                            "bids": snapshot.bids,
                            "asks": snapshot.asks,
                        }, timestamp=timestamp)
                        output.put_nowait(snapshot_message)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above Binance's API rate limits.
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

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        return [
            market.market for market in (await AsyncIdexClient().public.get_markets())
        ]
