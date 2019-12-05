#!/usr/bin/env python

import aiohttp
import asyncio
import gzip
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
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.market.kraken.kraken_order_book import KrakenOrderBook

KRAKEN_SYMBOLS_URL = "https://api.kraken.com/0/public/Assets"
KRAKEN_MARKETS_URL = "https://api.kraken.com/0/public/AssetPairs"
KRAKEN_TICKER_URL = "https://api.kraken.com/0/public/Ticker"
KRAKEN_DEPTH_URL = "https://api.kraken.com/0/public/Depth"
KRAKEN_WS_URI = "wss://ws.kraken.com"


class KrakenAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _haobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._haobds_logger is None:
            cls._haobds_logger = logging.getLogger(__name__)
        return cls._haobds_logger

    def __init__(self, symbols: Optional[List[str]] = None):
        super().__init__()
        self._symbols: Optional[List[str]] = symbols

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    
    async def get_active_exchange_markets(self) -> pd.DataFrame:
        # limits = await fetch_min_order_amounts()
        async with aiohttp.ClientSession() as client:
            exchange_response = await client.get(KRAKEN_MARKETS_URL)
            exchange_response: aiohttp.ClientResponse = exchange_response
            if exchange_response.status != 200:
                raise IOError(f"Error fetching Kraken exchange information. "
                            f"HTTP status is {exchange_response.status}.")
            exchange_data = await exchange_response.json()
            pairs = []
            trading_pairs = {}
            keys = list(exchange_data['result'].keys())
            for i in range(0, len(keys)):
                id = keys[i]
                market = exchange_data['result'][id]
                baseId = market['base']
                quoteId = market['quote']
                base = baseId
                quote = quoteId
                symbol = market['altname']
                trading_pairs[id] = {'symbol': symbol, "baseAsset": base, "quoteAsset": quote, 'altname': market['altname']}
                pairs.append(market['altname'])
            params = '&pair='
            params +=','.join(pairs)
            exchange_data_ = []
            exchange_data_.append(exchange_data['result'])
            market_response = await client.request(url=KRAKEN_TICKER_URL,params=params,method='GET')
            market_data = await market_response.json()
            if market_response.status != 200:
                raise IOError(f"Error fetching Kraken markets information. "
                            f"HTTP status is {market_response.status}.")
            market_data: List[Dict[str, Any]] = [
                {**item[1], **trading_pairs[item[0]]}
                for item in market_data['result'].items()
                    if item[0] in trading_pairs
            ]
            for colum in market_data:
                colum['quoteVolume'] = colum['v'][1]
                colum.pop('v')
                colum.pop('a')
                colum.pop('b')
                colum['close'] = colum['c'][0]
                colum.pop('c')
                colum['hcolumgh']= colum['h'][0]
                colum.pop('h')
                colum['low'] = colum['l'][0]
                colum.pop('l')
                colum['open'] = colum['o'][0]
                colum.pop('o')
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="symbol")
            btc_price: float = float(all_markets.loc["XBTUSD"]["close"])
            eth_price: float = float(all_markets.loc["ETHUSD"]["close"])
            usd_volume: float = [(
                    quoteVolume * btc_price if symbol.endswith("BTC") else
                    quoteVolume * eth_price if symbol.endswith("ETH") else
                    quoteVolume
                )
                for symbol, quoteVolume in zip(all_markets.index,
                                            all_markets.quoteVolume.astype("float"))]
            all_markets.loc[:, "USDVolume"] = usd_volume
        return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> List[str]:
        if not self._symbols:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._symbols = active_markets.index.tolist()
            except Exception:
                self._symbols = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._symbols

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
                    snapshot_msg: OrderBookMessage = KrakenOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"symbol": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                    retval[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_msg.timestamp, order_book)
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index + 1}/{number_of_pairs} completed.")
                    # Kraken rate limit is 100 https requests per 10 seconds
                    await asyncio.sleep(0.4)
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5)
            return retval

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        # when type is set to "step0", the default value of "depth" is 150
        params: Dict = {"pair": trading_pair.replace("/", "")}
        async with client.get(KRAKEN_DEPTH_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Kraken market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            api_data = await response.read()
            data: Dict[str, Any] = json.loads(api_data)
            return list(data['result'].values())[0]

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
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(KRAKEN_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "event": "subscribe",
                            "pair": [trading_pair],
                            "subscription": {"name": "trade"}
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if "pong" in msg:
                            await ws.send({"event": "ping"})
                        if type(msg) is list:
                            if len(msg) == 4:
                                for data in msg[1]:
                                    trade_message: OrderBookMessage = KrakenOrderBook.trade_message_from_exchange(data, metadata={"symbol": msg[3]})
                                    output.put_nowait(trade_message)
                        # Server heartbeat sent if no subscription traffic within 1 second (approximately)
                        elif msg["event"] == 'heartbeat':
                            continue
                        else:
                            self.logger().debug(f"Unrecognized message received from Kraken websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Orderbooks Diffs and Snapshots are handled by listen_for_order_book_stream()
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Orderbooks Diffs and Snapshots are handled by listen_for_order_book_stream()
        pass

    async def listen_for_order_book_stream(self,
                                           ev_loop: asyncio.BaseEventLoop,
                                           snapshot_queue: asyncio.Queue,
                                           diff_queue: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(KRAKEN_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    # for trading_pair in trading_pairs:
                    subscribe_request: Dict[str, Any] = {
                        "event": "subscribe",
                        "pair": trading_pairs,
                        "subscription": {"name": "book"}
                    }
                    await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if type(msg) is list:
                            if (len(msg) == 4 or len(msg) == 5) and ('a' in msg[1] or 'b' in msg[1]):
                                order_book_message: OrderBookMessage = KrakenOrderBook.diff_message_from_exchange(
                                    msg,
                                    time.time())
                                diff_queue.put_nowait(order_book_message)
                            elif len(msg) == 4 and 'as' in msg[1] and 'bs' in msg[1]:
                                order_book_message = KrakenOrderBook.snapshot_message_from_exchange(
                                    msg,
                                    time.time())
                                snapshot_message: Order
                                snapshot_queue.put_nowait(order_book_message)
                        elif msg["event"] == "heartbeat":
                            continue
                        elif len(msg) != 4:
                            self.logger().debug(f"Unrecognized message received from Kraken websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
