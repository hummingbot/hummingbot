#!/usr/bin/env python

import asyncio
import json
import aiohttp
import logging
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
import time
import websockets
from websockets.exceptions import ConnectionClosed
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.market.kucoin.kucoin_order_book_tracker_entry import KucoinOrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.market.kucoin.kucoin_order_book import KucoinOrderBook
from hummingbot.market.kucoin.kucoin_active_order_tracker import KucoinActiveOrderTracker


SNAPSHOT_REST_URL = "https://api.kucoin.com/api/v2/market/orderbook/level2"
DIFF_STREAM_URL = ""
TICKER_PRICE_CHANGE_URL = "https://api.kucoin.com/api/v1/market/allTickers"
EXCHANGE_INFO_URL = "https://api.kucoin.com/api/v1/symbols"


class KucoinAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _kaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kaobds_logger is None:
            cls._kaobds_logger = logging.getLogger(__name__)
        return cls._kaobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._order_book_create_function = lambda: OrderBook()

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have trading_pair as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:

            market_response, exchange_response = await safe_gather(
                client.get(TICKER_PRICE_CHANGE_URL),
                client.get(EXCHANGE_INFO_URL)
            )
            market_response: aiohttp.ClientResponse = market_response
            exchange_response: aiohttp.ClientResponse = exchange_response

            if market_response.status != 200:
                raise IOError(f"Error fetching Kucoin markets information. "
                              f"HTTP status is {market_response.status}.")
            if exchange_response.status != 200:
                raise IOError(f"Error fetching Kucoin exchange information. "
                              f"HTTP status is {exchange_response.status}.")

            market_data = await market_response.json()
            exchange_data = await exchange_response.json()

            attr_name_map = {"baseCurrency": "baseAsset", "quoteCurrency": "quoteAsset"}

            trading_pairs: Dict[str, Any] = {item["symbol"]: {attr_name_map[k]: item[k] for k in ["baseCurrency", "quoteCurrency"]}
                                             for item in exchange_data["data"]
                                             if item["enableTrading"] == True}

            market_data: List[Dict[str, Any]] = [{**item, **trading_pairs[item["symbol"]]}
                                                 for item in market_data["data"]["ticker"]
                                                 if item["symbol"] in trading_pairs]

            # Build the data frame.
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="symbol")
            # calculating the correct USDVolume by multiplying or diving with necessary USD pair
            for row in all_markets.itertuples():
                product_name: str = row.Index
                if product_name.startswith("USDT"):
                    all_markets.loc[product_name, "USDVolume"] = 1 / float(row.volValue)
                elif product_name.endswith("USDT"):
                    all_markets.loc[product_name, "USDVolume"] = float(row.volValue)
                else:
                    quote_currency: str = product_name.split('-')[1]
                    mul: str = quote_currency + "-USDT"
                    div: str = "USDT-" + quote_currency
                    if mul in all_markets.index:
                        all_markets.loc[product_name, "USDVolume"] = float(row.volValue) * float(all_markets.loc[mul, "last"])
                    elif div in all_markets.index:
                        all_markets.loc[product_name, "USDVolume"] = float(row.volValue) / float(all_markets.loc[div, "last"])
            all_markets.loc[:, "volume"] = all_markets.vol
            return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> List[str]:
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
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        params: Dict = {"symbol": trading_pair}
        async with client.get(SNAPSHOT_REST_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Kucoin market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, OrderBookTrackerEntry] = {}

            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = KucoinOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"symbol": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    active_order_tracker: KucoinActiveOrderTracker = KucoinActiveOrderTracker()
                    bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
                    retval[trading_pair] = KucoinOrderBookTrackerEntry(trading_pair, snapshot_timestamp, order_book, active_order_tracker)
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")
                    # Kucoin rate limit is 100 https requests per 10 seconds
                    await asyncio.sleep(0.4)
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5)
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

    # get required data to create a websocket request
    async def ws_connect_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.kucoin.com/api/v1/bullet-public', data=b'') as resp:
                response: aiohttp.ClientResponse = resp
                if response.status != 200:
                    raise IOError(f"Error fetching Kucoin websocket connection data."
                                  f"HTTP status is {response.status}.")
                data: Dict[str, Any] = await response.json()
                return data

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        websocket_data: Dict[str, Any] = await self.ws_connect_data()
        kucoin_ws_uri: str = websocket_data["data"]["instanceServers"][0]["endpoint"] + "?token=" + websocket_data["data"]["token"] + "&acceptUserMessage=true"
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(kucoin_ws_uri) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "id": int(time.time()),
                            "type": "subscribe",
                            "topic": f"/market/match:{trading_pair}",
                            "privateChannel": False,
                            "response": True
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if msg["type"] == "pong" or msg["type"] == "ack":
                            pass
                        elif msg["type"] == "message":
                            trading_pair = msg["data"]["symbol"]
                            data = msg["data"]
                            trade_message: OrderBookMessage = KucoinOrderBook.trade_message_from_exchange(
                                data, metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(trade_message)
                        else:
                            self.logger().debug(f"Unrecognized message received from Kucoin websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        websocket_data: Dict[str, Any] = await self.ws_connect_data()
        kucoin_ws_uri: str = websocket_data["data"]["instanceServers"][0]["endpoint"] + "?token=" + websocket_data["data"]["token"] + "&acceptUserMessage=true"
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(kucoin_ws_uri) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "id": int(time.time()),
                            "type": "subscribe",
                            "topic": f"/market/level2:{trading_pair}",
                            "response": True
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if msg["type"] == "pong" or msg["type"] == "ack":
                            pass
                        elif msg["type"] == "message":
                            order_book_message: OrderBookMessage = KucoinOrderBook.diff_message_from_exchange(msg)
                            output.put_nowait(order_book_message)
                        else:
                            self.logger().debug(f"Unrecognized message received from Kucoin websocket: {msg}")
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
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = KucoinOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"symbol": trading_pair}
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
