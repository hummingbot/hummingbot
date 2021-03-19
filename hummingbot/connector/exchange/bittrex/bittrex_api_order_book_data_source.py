#!/usr/bin/env python
import aiohttp
import asyncio
import logging
import time
from base64 import b64decode
from typing import Optional, List, Dict, AsyncIterable, Any
from zlib import decompress, MAX_WBITS

import pandas as pd
import signalr_aio
import ujson
from signalr_aio import Connection
from signalr_aio.hubs import Hub
from async_timeout import timeout

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.bittrex.bittrex_active_order_tracker import BittrexActiveOrderTracker
from hummingbot.connector.exchange.bittrex.bittrex_order_book import BittrexOrderBook


EXCHANGE_NAME = "Bittrex"

BITTREX_REST_URL = "https://api.bittrex.com/v3"
BITTREX_EXCHANGE_INFO_PATH = "/markets"
BITTREX_MARKET_SUMMARY_PATH = "/markets/summaries"
BITTREX_TICKER_PATH = "/markets/tickers"
BITTREX_WS_FEED = "https://socket-v3.bittrex.com/signalr"

MAX_RETRIES = 20
MESSAGE_TIMEOUT = 30.0
SNAPSHOT_TIMEOUT = 10.0
NaN = float("nan")


class BittrexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    PING_TIMEOUT = 10.0

    _bittrexaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bittrexaobds_logger is None:
            cls._bittrexaobds_logger = logging.getLogger(__name__)
        return cls._bittrexaobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)
        self._websocket_connection: Optional[Connection] = None
        self._websocket_hub: Optional[Hub] = None
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{BITTREX_REST_URL}{BITTREX_TICKER_PATH}")
            resp_json = await resp.json()
            for trading_pair in trading_pairs:
                resp_record = [o for o in resp_json if o["symbol"] == trading_pair][0]
                results[trading_pair] = float(resp_record["lastTradeRate"])
        return results

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = BittrexOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"marketSymbol": trading_pair}
            )
            order_book: OrderBook = self.order_book_create_function()
            active_order_tracker: BittrexActiveOrderTracker = BittrexActiveOrderTracker()
            bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

    async def websocket_connection(self) -> (signalr_aio.Connection, signalr_aio.hubs.Hub):
        if self._websocket_connection and self._websocket_hub:
            return self._websocket_connection, self._websocket_hub

        self._websocket_connection = signalr_aio.Connection(BITTREX_WS_FEED, session=None)
        self._websocket_hub = self._websocket_connection.register_hub("c3")

        trading_pairs = self._trading_pairs
        for trading_pair in trading_pairs:
            self._websocket_hub.server.invoke("Subscribe", [f"orderbook_{trading_pair}_25"])
            self._websocket_hub.server.invoke("Subscribe", [f"trade_{trading_pair}"])
            self.logger().info(f"Subscribed to {trading_pair} deltas")

        self._websocket_connection.start()
        self.logger().info("Websocket connection started...")

        return self._websocket_connection, self._websocket_hub

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{BITTREX_REST_URL}{BITTREX_EXCHANGE_INFO_PATH}", timeout=5) as response:
                    if response.status == 200:
                        all_trading_pairs: List[Dict[str, Any]] = await response.json()
                        return [item["symbol"]
                                for item in all_trading_pairs
                                if item["status"] == "ONLINE"]
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for bittrex trading pairs
            pass
        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        # Creates/Reuses connection to obtain a single snapshot of the trading_pair
        params = {"depth": 25}
        async with client.get(f"{BITTREX_REST_URL}{BITTREX_EXCHANGE_INFO_PATH}/{trading_pair}/orderbook", params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Bittrex market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            data["sequence"] = response.headers["sequence"]
            return data

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Trade messages are received as Orderbook Deltas and handled by listen_for_order_book_stream()
        # passa
        while True:
            connection, hub = await self.websocket_connection()
            try:
                async for raw_message in self._socket_stream():
                    decoded: Dict[str, Any] = self._transform_raw_message(raw_message)

                    # Processes snapshot messages
                    if decoded["type"] == "trade":
                        trades: Dict[str, any] = decoded
                        for trade in trades["results"]["deltas"]:
                            trade_msg: OrderBookMessage = BittrexOrderBook.trade_message_from_exchange(
                                trade, metadata={"trading_pair": trades["results"]["marketSymbol"],
                                                 "sequence": trades["results"]["sequence"]}, timestamp=trades["nonce"]
                            )
                            output.put_nowait(trade_msg)

            except Exception:
                self.logger().error("Unexpected error when listening on socket stream.", exc_info=True)
            finally:
                connection.close()
                self._websocket_connection = self._websocket_hub = None

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Orderbooks Deltas and Snapshots are handled by listen_for_order_book_stream()
        # pass
        while True:
            connection, hub = await self.websocket_connection()
            try:
                async for raw_message in self._socket_stream():
                    decoded: Dict[str, Any] = self._transform_raw_message(raw_message)

                    # Processes diff messages
                    if decoded["type"] == "delta":
                        diff: Dict[str, any] = decoded
                        diff_timestamp = diff["nonce"]
                        diff_msg: OrderBookMessage = BittrexOrderBook.diff_message_from_exchange(
                            diff["results"], diff_timestamp
                        )
                        output.put_nowait(diff_msg)

            except Exception:
                self.logger().error("Unexpected error when listening on socket stream.", exc_info=True)
            finally:
                connection.close()
                self._websocket_connection = self._websocket_hub = None

    async def _socket_stream(self) -> AsyncIterable[str]:
        try:
            while True:
                async with timeout(MESSAGE_TIMEOUT):  # Timeouts if not receiving any messages for 10 seconds(ping)
                    conn: signalr_aio.Connection = (await self.websocket_connection())[0]
                    yield await conn.msg_queue.get()
        except asyncio.TimeoutError:
            self.logger().warning("Message recv() timed out. Going to reconnect...")
            return

    def _transform_raw_message(self, msg) -> Dict[str, Any]:
        def _decode_message(raw_message: bytes) -> Dict[str, Any]:
            try:
                decoded_msg: bytes = decompress(b64decode(raw_message, validate=True), -MAX_WBITS)
            except SyntaxError:
                decoded_msg: bytes = decompress(b64decode(raw_message, validate=True))
            except Exception:
                return {}

            return ujson.loads(decoded_msg.decode())

        def _is_market_delta(msg) -> bool:
            return len(msg.get("M", [])) > 0 and type(msg["M"][0]) == dict and msg["M"][0].get("M", None) == "orderBook"

        def _is_market_update(msg) -> bool:
            return len(msg.get("M", [])) > 0 and type(msg["M"][0]) == dict and msg["M"][0].get("M", None) == "trade"

        output: Dict[str, Any] = {"nonce": None, "type": None, "results": {}}
        msg: Dict[str, Any] = ujson.loads(msg)
        if len(msg.get("M", [])) > 0:
            output["results"] = _decode_message(msg["M"][0]["A"][0])
            output["nonce"] = time.time() * 1000

        if _is_market_delta(msg):
            output["type"] = "delta"

        elif _is_market_update(msg):
            output["type"] = "trade"

        return output

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Technically this does not listen for snapshot, Instead it periodically queries for snapshots.
        while True:
            try:
                async with aiohttp.ClientSession() as client:
                    for trading_pair in self._trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = BittrexOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"marketSymbol": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().info(f"Saved {trading_pair} snapshots.")
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5.0)
                    # Waits for delta amount of time before getting new snapshots
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except Exception:
                self.logger().error("Unexpected error occurred invoking queryExchangeState", exc_info=True)
                await asyncio.sleep(5.0)
