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

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.market.exmarkets.exmarkets_order_book import ExmarketsOrderBook

EXMARKETS_SYMBOLS_URL = "https://exmarkets.com/api/v1/general/info"
EXMARKETS_TICKER_URL = "https://exmarkets.com/api/trade/v1/market/ticker"
EXMARKETS_DEPTH_URL = "https://exmarkets.com/api/trade/v1/market/order-book"
EXMARKETS_WS_URI = "wss://exmarkets.com/ws"


class ExmarketsAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _haobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._haobds_logger is None:
            cls._haobds_logger = logging.getLogger(__name__)
        return cls._haobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._symbol_map: Dict[str, Any] = None
        self._ws_running: bool = False

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(self, cls) -> pd.DataFrame:
        """
        Returned data frame should have trading pair as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:

            market_response, exchange_response = await safe_gather(
                client.get(EXMARKETS_TICKER_URL),
                client.get(EXMARKETS_SYMBOLS_URL)
            )
            market_response: aiohttp.ClientResponse = market_response
            exchange_response: aiohttp.ClientResponse = exchange_response

            if market_response.status != 200:
                raise IOError(f"Error fetching Exmarkets markets information. "
                              f"HTTP status is {market_response.status}.")
            if exchange_response.status != 200:
                raise IOError(f"Error fetching Exmarkets exchange information. "
                              f"HTTP status is {exchange_response.status}.")

            market_data = await market_response.json()
            exchange_data = await exchange_response.json()

            symbolMap: Dict[str, Any] = {
                item["slug"]: item["id"]
                for item in exchange_data["markets"]
            }
            self._symbol_map = symbolMap

            trading_pairs: Dict[str, Any] = {
                item["slug"]: {"baseAsset": item["currency"]["code"].lower(), "quoteAsset": item["with_currency"]["code"].lower()}
                for item in exchange_data["markets"]
                if item["active"] is True
            }

            market_data: List[Dict[str, Any]] = [
                {"symbol": key.lower(), **trading_pairs[key.lower()], **market_data[key]}
                for key in market_data
                if key.lower() in trading_pairs
            ]

            # Build the data frame.
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="symbol")
            btc_price: float = float(all_markets.loc["btc-usdt"].last)
            eth_price: float = float(all_markets.loc["eth-usdt"].last)
            usd_volume: float = [
                (
                    volume * btc_price * last if trading_pair.endswith("btc") else
                    volume * eth_price * last if trading_pair.endswith("eth") else
                    volume
                )
                for trading_pair, volume, last in zip(all_markets.index,
                                                      all_markets.volume.astype("float"), all_markets.last.astype("float"))]

            all_markets.loc[:, "USDVolume"] = usd_volume
            all_markets.loc[:, "volume"] = all_markets.volume

            return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
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
        params: Dict = {"market": trading_pair, "limit": 150}
        async with client.get(EXMARKETS_DEPTH_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Exmarkets market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            api_data = await response.read()
            data: Dict[str, Any] = json.loads(api_data)

            bids = []
            for bid in data['bids']:
                bids.append([float(bid['price']), float(bid['amount'])])

            asks = []
            for ask in data['asks']:
                asks.append([float(ask['price']), float(ask['amount'])])

            data['bids'] = bids
            data['asks'] = asks

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
                    snapshot_msg: OrderBookMessage = ExmarketsOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        metadata={"market": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                    retval[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_msg.timestamp, order_book)
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index + 1}/{number_of_pairs} completed.")
                    # for rate limiting
                    await asyncio.sleep(0.5)
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

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        if (self._ws_running is False):
            self._ws_running = True
            while True:
                try:
                    trading_pairs: List[str] = await self.get_trading_pairs()
                    async with websockets.connect(EXMARKETS_WS_URI) as ws:
                        ws: websockets.WebSocketClientProtocol = ws
                        subscribe_request: Dict[str, Any] = {
                            "e": "init"
                        }
                        await ws.send(json.dumps(subscribe_request))

                        for trading_pair in trading_pairs:
                            subscribe_request: Dict[str, Any] = {
                                "e": "market",
                                "subscription": "full",
                                "chartInterval": "1m",
                                "marketId": self._symbol_map[trading_pair]
                            }
                            await ws.send(json.dumps(subscribe_request))

                        async for raw_msg in self._inner_messages(ws):
                            msg: Dict[str, Any] = json.loads(raw_msg.decode('utf-8'))
                            if "market-trade" in msg:
                                trading_pair = msg["data"]["market"]
                                trade_message: OrderBookMessage = ExmarketsOrderBook.trade_message_from_exchange(
                                    msg, metadata={"market": trading_pair}
                                )
                                output.put_nowait(trade_message)
                            elif "market-orderbook" in msg:
                                trading_pair = msg["data"]["market"]
                                order_book_message: OrderBookMessage = ExmarketsOrderBook.diff_message_from_exchange(
                                    msg, metadata={"market": trading_pair}
                                )
                                output.put_nowait(order_book_message)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                        exc_info=True)
                    await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        if (self._ws_running is False):
            self._ws_running = True
            while True:
                try:
                    trading_pairs: List[str] = await self.get_trading_pairs()
                    async with websockets.connect(EXMARKETS_WS_URI) as ws:
                        ws: websockets.WebSocketClientProtocol = ws
                        subscribe_request: Dict[str, Any] = {
                            "e": "init"
                        }
                        await ws.send(json.dumps(subscribe_request))

                        for trading_pair in trading_pairs:
                            subscribe_request: Dict[str, Any] = {
                                "e": "market",
                                "subscription": "full",
                                "chartInterval": "1m",
                                "marketId": self._symbol_map[trading_pair]
                            }
                            await ws.send(json.dumps(subscribe_request))

                        async for raw_msg in self._inner_messages(ws):
                            msg: Dict[str, Any] = json.loads(raw_msg.decode('utf-8'))
                            if "market-trade" in msg:
                                trading_pair = msg["data"]["market"]
                                trade_message: OrderBookMessage = ExmarketsOrderBook.trade_message_from_exchange(
                                    msg, metadata={"market": trading_pair}
                                )
                                output.put_nowait(trade_message)
                            elif "market-orderbook" in msg:
                                trading_pair = msg["data"]["market"]
                                order_book_message: OrderBookMessage = ExmarketsOrderBook.diff_message_from_exchange(
                                    msg, metadata={"market": trading_pair}
                                )
                                output.put_nowait(order_book_message)
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
                            snapshot_message: OrderBookMessage = ExmarketsOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                metadata={"market": trading_pair}
                            )
                            output.put_nowait(snapshot_message)
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
