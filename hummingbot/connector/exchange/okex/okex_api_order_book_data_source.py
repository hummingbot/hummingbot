#!/usr/bin/env python

import aiohttp
import asyncio

import json
import logging
import pandas as pd
import time
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.okex.okex_order_book import OkexOrderBook
from hummingbot.connector.exchange.okex.constants import (
    OKEX_INSTRUMENTS_URL,
    OKEX_DEPTH_URL,
    OKEX_TICKERS_URL,
    OKEX_WS_URI_PUBLIC,
)

from dateutil.parser import parse as dataparse


class OkexAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _okexaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._okexaobds_logger is None:
            cls._okexaobds_logger = logging.getLogger(__name__)
        return cls._okexaobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        # Returns a List of str, representing each active trading pair on the exchange.
        async with aiohttp.ClientSession() as client:
            async with client.get(OKEX_INSTRUMENTS_URL) as products_response:

                products_response: aiohttp.ClientResponse = products_response
                if products_response.status != 200:
                    raise IOError(f"Error fetching active OKEx markets. HTTP status is {products_response.status}.")

                data = await products_response.json()
                data = data['data']

                trading_pairs = []
                for item in data:
                    # I couldn't find where to check if it's online in OKEx API doc
                    if item['state'] == 'live':
                        trading_pairs.append(item['instId'])

        return trading_pairs

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)

            snapshot_msg: OrderBookMessage = OkexOrderBook.snapshot_message_from_exchange(
                snapshot,
                trading_pair,
                timestamp=snapshot['ts'],
                metadata={"trading_pair": trading_pair})
            order_book: OrderBook = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    # Move this to OrderBookTrackerDataSource or this needs a whole refactor?
    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        async with aiohttp.ClientSession() as client:
            async with client.get(OKEX_TICKERS_URL) as products_response:

                products_response: aiohttp.ClientResponse = products_response
                if products_response.status != 200:
                    raise IOError(f"Error fetching active OKEx markets. HTTP status is {products_response.status}.")

                data = await products_response.json()
                data = data['data']
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data)
                all_markets.set_index('instId', inplace=True)

                out: Dict[str, float] = {}

                for trading_pair in trading_pairs:
                    out[trading_pair] = float(all_markets['last'][trading_pair])

                return out

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                self._trading_pairs = await self.fetch_trading_pairs()
            except Exception:
                self._trading_pairs = []
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg="Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        """Fetches order book snapshot for a particular trading pair from the exchange REST API."""
        params = {}
        async with client.get(OKEX_DEPTH_URL.format(trading_pair=trading_pair), params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching OKEX market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            api_data = await response.read()
            data: Dict[str, Any] = json.loads(api_data)['data'][0]
            data['ts'] = int(data['ts'])

            return data

    @classmethod
    def iso_to_timestamp(cls, date: str):
        return dataparse(date).timestamp()

    async def listen_for_trades(self, ev_loop: Optional[asyncio.BaseEventLoop], output: asyncio.Queue):
        """Subscribes to the trade channel of the exchange. Adds incoming messages(of filled orders) to the output queue, to be processed by"""

        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(OKEX_WS_URI_PUBLIC) as ws:
                    ws: websockets.WebSocketClientProtocol = ws

                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "op": "subscribe",
                            "args": [
                                {
                                    "channel": "trades",
                                    "instType": "SPOT",
                                    "instId": trading_pair,
                                }
                            ]
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        decoded_msg: str = raw_msg

                        self.logger().debug("decode menssage:" + decoded_msg)

                        if '"event":"subscribe"' in decoded_msg:
                            self.logger().debug(f"Subscribed to channel, full message: {decoded_msg}")
                        elif '"channel": "orders"' in decoded_msg:
                            self.logger().debug(f"Received new trade: {decoded_msg}")

                            for data in json.loads(decoded_msg)['data']:
                                trading_pair = data['instId']
                                trade_message: OrderBookMessage = OkexOrderBook.trade_message_from_exchange(
                                    data, data['uTime'], metadata={"trading_pair": trading_pair}
                                )
                                self.logger().debug(f"Putting msg in queue: {str(trade_message)}")
                                output.put_nowait(trade_message)
                        else:
                            self.logger().debug(f"Unrecognized message received from OKEx websocket: {decoded_msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_order_book_diffs(self, ev_loop: Optional[asyncio.BaseEventLoop], output: asyncio.Queue):
        """Fetches or Subscribes to the order book snapshots for each trading pair. Additionally, parses the incoming message into a OrderBookMessage and appends it into the output Queue."""
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(OKEX_WS_URI_PUBLIC) as ws:
                    ws: websockets.WebSocketClientProtocol = ws

                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "op": "subscribe",
                            "args": [
                                {
                                    "channel": "books",
                                    "instId": trading_pair
                                }
                            ]
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        decoded_msg: str = raw_msg

                        if '"event":"subscribe"' in decoded_msg:
                            self.logger().debug(f"Subscribed to channel, full message: {decoded_msg}")
                        elif '"action":"update"' in decoded_msg:
                            msg = json.loads(decoded_msg)
                            for data in msg['data']:
                                order_book_message: OrderBookMessage = OkexOrderBook.diff_message_from_exchange(data, int(data['ts']), msg['arg'])
                                output.put_nowait(order_book_message)
                        else:
                            self.logger().debug(f"Unrecognized message received from OKEx websocket: {decoded_msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """Fetches or Subscribes to the order book deltas(diffs) for each trading pair. Additionally, parses the incoming message into a OrderBookMessage and appends it into the output Queue."""
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_msg: OrderBookMessage = OkexOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                trading_pair,
                                timestamp=snapshot['ts'],
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
