#!/usr/bin/env python

import asyncio
import logging
import time
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
import pandas as pd
import ujson
import websockets
from hummingbot.connector.exchange.coinex import coinex_constants as Constants
from hummingbot.connector.exchange.coinex import coinex_utils
from hummingbot.connector.exchange.coinex.coinex_active_order_tracker import \
    CoinexActiveOrderTracker
from hummingbot.connector.exchange.coinex.coinex_order_book import \
    CoinexOrderBook
from hummingbot.connector.exchange.coinex.coinex_order_book_tracker_entry import \
    CoinexOrderBookTrackerEntry
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import \
    OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import \
    OrderBookTrackerEntry
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.healthcheck import healthcheck
from hummingbot.logger import HummingbotLogger
from websockets.legacy.client import Connect as WSConnectionContext

COINEX_REST_URL = "https://api.coinex.com/v1/"
COINEX_WS_FEED = "wss://socket.coinex.com"
MAX_RETRIES = 20
HTTP_TIMEOUT = 10.0
NaN = float("nan")


class CoinexAPIOrderBookDataSource(OrderBookTrackerDataSource):

    PING_TIMEOUT = 61.0
    PING_INTERVAL = 55.00

    _cbpaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpaobds_logger is None:
            cls._cbpaobds_logger = logging.getLogger(__name__)
        return cls._cbpaobds_logger

    def __init__(self, trading_pairs: List[str]):
        self._ping_task: Optional[asyncio.Task] = None
        self._last_nonce: int = int(time.time() * 1e3)
        self._last_recv_time: float = 0
        self._trading_pairs = trading_pairs
        self._websocket_connection: Optional[WSConnectionContext] = None
        super().__init__(trading_pairs)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        tasks = [cls.get_last_traded_price(coinex_utils.convert_to_exchange_trading_pair(t_pair)) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str) -> float:
        # See: https://github.com/coinexcom/coinex_exchange_api/wiki/021ticker
        async with aiohttp.ClientSession() as client:
            # TODO: Review / cleanup using constants
            ticker_url: str = f"{Constants.TICKER_URL}?market={trading_pair}"
            resp = await client.get(ticker_url, timeout=HTTP_TIMEOUT)
            resp_json = await resp.json()
            # cls.logger().error(f"{resp_json}")
            return float(resp_json["data"][0]["price"])

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        # TODO: Review / cleanup using constants
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(Constants.MARKETS_URL, timeout=HTTP_TIMEOUT) as response:
                    if response.status == 200:
                        data: Dict[str, Any] = await response.json()
                        return [coinex_utils.convert_from_exchange_trading_pair(item) for item in data["data"]]

        except Exception as e:
            print(f"{e}")
            # Do nothing if the request fails -- there will be no autocomplete for coinex trading pairs
            pass

        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        """
        Fetches order book snapshot for a particular trading pair from the rest API
        :returns: Response from the rest API
        """
        # TODO: Review / cleanup using constants
        market_order_book_url: str = Constants.ORDER_BOOK_URL
        params = {
            "market": coinex_utils.convert_to_exchange_trading_pair(trading_pair),
            "merge": "0",
            "limit": int(50),
        }
        async with client.get(market_order_book_url, params=params, timeout=HTTP_TIMEOUT) as response:
            resp: aiohttp.ClientResponse = response
            if resp.status != 200:
                raise IOError(f"Error fetching CoinEx market snapshot for {trading_pair}. "
                              f"HTTP status is {resp.status}.")
            data: Dict[str, Any] = await resp.json()
            return data['data']  # type: ignore

    @property
    def ping_task(self) -> Optional[asyncio.Task]:
        return self._ping_task

    def get_nonce(self) -> int:
        now_ms: int = int(time.time() * 1e3)
        if now_ms <= self._last_nonce:
            now_ms = self._last_nonce + 1
        self._last_nonce = now_ms
        return now_ms

    async def get_ws_connection(self) -> WSConnectionContext:
        self.logger().debug("Connecting Websocket")
        # TODO: Review / cleanup using constants
        return WSConnectionContext(COINEX_WS_FEED, ping_interval=None, ping_timeout=None)

    async def _subscribe_topic(self, topic_params: List) -> None:
        # TODO: Review / cleanup using constants
        subscribe_request: Dict[str, Any] = {
            "method": "depth.subscribe_multi",
            "params": topic_params,
            "id": self.get_nonce(),
        }
        self.logger().debug("Sending Depth Subscribe Request")
        await self._websocket_connection.send(ujson.dumps(subscribe_request))
        self.logger().debug("Received Depth Subscribe Response")

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = CoinexOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
            # self.logger().info(f"{snapshot_msg}") TODO REMOVE
            active_order_tracker: CoinexActiveOrderTracker = CoinexActiveOrderTracker()
            bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
            order_book = self.order_book_create_function()
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        """
        *required
        Initializes order books and order book trackers for the list of trading pairs
        returned by `self.get_trading_pairs`
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
                    snapshot_msg: OrderBookMessage = CoinexOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    active_order_tracker: CoinexActiveOrderTracker = CoinexActiveOrderTracker()
                    bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = CoinexOrderBookTrackerEntry(
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

    # TODO: We can support this....
    # Trade messages are received from the order book web socket
    # see: https://github.com/coinexcom/coinex_exchange_api/wiki/045deals
    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> None:
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> None:
        """
        *required
        Subscribe to diff channel via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        healthcheck_last: dict = {"orderbook": time.time()}
        await healthcheck("orderbook", time.time())
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                # Initialize Websocket Connection
                self.logger().info("Initialize Websocket Connection")
                async with (await self.get_ws_connection()) as ws:
                    self._websocket_connection = ws
                    # We need to build a list of lists for the subscribe_multi method
                    # per: https://github.com/coinexcom/coinex_exchange_api/wiki/044depth#subscribe-market-depth-support-multi-market-in-websocket-subscription
                    params_construct: List = list()
                    for trading_pair in trading_pairs:
                        _trading_pair = coinex_utils.convert_to_exchange_trading_pair(trading_pair)
                        params_construct.append([_trading_pair, int(50), "0"])

                    # Subscribe Depth (Multi)
                    self.logger().info("Subscribing Topics")
                    await self._subscribe_topic(params_construct)

                    # Ping / pong loop
                    self.logger().info("Setting Up Ping / Pong Loop")
                    if self._ping_task is None:
                        self._ping_task = safe_ensure_future(self._ping_loop())
                        self.logger().info("Setup Ping / Pong Loop")
                    self.logger().info("Waiting For Messages")

                    async for message in self._inner_messages():
                        # self.logger().info(f"Message Received: {message}")
                        error = message.get("error", None)
                        result = message.get("result", None)
                        method = message.get("method", None)
                        # Check for errors and results in message (we want to continue loop as these can be ignored)
                        if (error is not None) or (result is not None):
                            if error is not None:
                                self.logger().error(f"Error in message: {message}")
                                continue  # TODO: Do we want to continue or raise?
                            elif "status" in result and result['status'] == "success":
                                self.logger().info(f"Result was successful: {message}")
                                continue
                            elif result == 'pong':
                                self.logger().info(f"Received pong: {message}")
                                continue
                            else:
                                self.logger().info(f"Weird, not something we handle: {message}")
                        # We only want to pass useful messages to the event loop.
                        elif method == "depth.update":
                            # TODO: Handle if params[0] == True?
                            # "params": [
                            #   false,                    #Boolean, true: for complete result，false: for update based on latest retrun result
                            #   {                         #Update info
                            #       "bids": [             #Depth of Buy
                            #           [
                            #           "12.25",          #Buy in price
                            #           "0.0588"          #Buy in count
                            #           ]
                            #       ],
                            #       "asks": [             #Depth of Sell
                            #           [
                            #           "12.94",          #Sell out price
                            #           "0.1524"          #Sell out count
                            #           ]
                            #       ],
                            #       "checksum": 21658179
                            #   }
                            # ]
                            params = message.get("params", None)
                            if params is not None:
                                bot_trading_pair: Optional[str] = coinex_utils.convert_from_exchange_trading_pair(str(params[2]), None)
                                order_book_message: OrderBookMessage = CoinexOrderBook.diff_message_from_exchange(params[1], metadata={"trading_pair": bot_trading_pair})
                                output.put_nowait(order_book_message)
                                if (time.time() - healthcheck_last['orderbook']) >= 3.0:
                                    await healthcheck('orderbook', time.time())
                                    healthcheck_last['orderbook'] = time.time()
                        else:
                            raise ValueError(f"Unrecognized CoinEx Websocket message received - {message}")
            except asyncio.CancelledError:
                raise
            except websockets.exceptions.ConnectionClosed as e:
                self.logger().error(f"Websocket connection closed: {e}")
            except websockets.exceptions.ConnectionClosedError as e:
                self.logger().error(f"Websocket had a connection issue: {e}")
            except IOError as e:
                self.logger().error(e, exc_info=True)
            except Exception as e:
                self.logger().error(f"Unexpected error occurred! {e} {message}", exc_info=True)
            finally:
                if self._websocket_connection is not None:
                    await self._websocket_connection.close()
                    self._websocket_connection = None
                if self._ping_task is not None:
                    self._ping_task.cancel()
                    self._ping_task = None

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> None:
        """
        *required
        Fetches order book snapshots for each trading pair, and use them to update the local order book
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = CoinexOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            # Be careful not to go above API rate limits.
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().network(
                                f'{"Unexpected error with WebSocket connection."}',
                                exc_info=True,
                                app_warning_msg=f'{"Unexpected error with WebSocket connection. Retrying in 5 seconds. "}'
                                                f'{"Check network connection."}'
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

    async def _ping_loop(self) -> None:
        self.logger().info("Called Ping Loop")
        while True:
            # TODO: Review / cleanup using constants
            try:
                ping_msg: Dict[str, Any] = {
                    "method": "server.ping",
                    "params": [],
                    "id": self.get_nonce(),
                }
                self.logger().info("Sending Ping")
                await self._websocket_connection.send(ujson.dumps(ping_msg))
                self.logger().info("Pong Received")
                self.logger().info("Waiting For Next Ping")
                await asyncio.sleep(self.PING_INTERVAL)
            except asyncio.TimeoutError:
                self.logger().warning("Ping timeout, going to reconnect...")
                break
            except asyncio.CancelledError:
                self.logger().error("Ping loop has been cancelled.")
                raise
            except Exception as e:
                self.logger().error(f"Ping loop had unhandled exception: {e}")
                raise

    # TODO: Review how to properly exit from AsyncIterable
    async def _inner_messages(self) -> AsyncIterable[dict]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        while True:
            try:
                self.logger().debug("In Message Loop, Awaiting")
                raw_msg = await self._websocket_connection.recv()
                # self.logger().debug(f"Loop Message Received Yielding: {raw_msg}")
                self._last_recv_time = time.time()
                message = ujson.loads(raw_msg)
                yield message
            except asyncio.TimeoutError:
                self.logger().warning("Userstream websocket timeout, going to reconnect...")
                return
