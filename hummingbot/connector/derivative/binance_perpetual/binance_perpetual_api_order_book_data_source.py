import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, AsyncIterable

import aiohttp
import pandas as pd
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_order_book import BinancePerpetualOrderBook
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils import convert_to_exchange_trading_pair

from hummingbot.connector.derivative.binance_perpetual.constants import (
    PERPETUAL_BASE_URL,
    TESTNET_BASE_URL,
    DIFF_STREAM_URL,
    TESTNET_STREAM_URL
)

# API OrderBook Endpoints
SNAPSHOT_REST_URL = "{}/fapi/v1/depth"
TICKER_PRICE_URL = "{}/fapi/v1/ticker/bookTicker"
TICKER_PRICE_CHANGE_URL = "{}/fapi/v1/ticker/24hr"
EXCHANGE_INFO_URL = "{}/fapi/v1/exchangeInfo"
RECENT_TRADES_URL = "{}/fapi/v1/trades"


class BinancePerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(self, trading_pairs: List[str] = None, domain: str = "binance_perpetual"):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self._base_url = TESTNET_BASE_URL if domain == "binance_perpetual_testnet" else PERPETUAL_BASE_URL
        self._stream_url = TESTNET_STREAM_URL if domain == "binance_perpetual_testnet" else DIFF_STREAM_URL
        self._stream_url += "/stream"
        self._domain = domain

    _bpobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobds_logger is None:
            cls._bpobds_logger = logging.getLogger(__name__)
        return cls._bpobds_logger

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str], domain=None) -> Dict[str, float]:
        tasks = [cls.get_last_traded_price(t_pair, domain) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str, domain=None) -> float:
        async with aiohttp.ClientSession() as client:
            url = TESTNET_BASE_URL if domain == "binance_perpetual_testnet" else PERPETUAL_BASE_URL
            resp = await client.get(f"{TICKER_PRICE_CHANGE_URL.format(url)}?symbol={convert_to_exchange_trading_pair(trading_pair)}")
            resp_json = await resp.json()
            return float(resp_json["lastPrice"])

    """
    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
            except Exception as e:
                self._trading_pairs = []
                self.logger().network(
                    "Error getting active trading pairs.",
                    exc_info=True,
                    app_warning_msg="Error getting active trading_pairs. Check network connection."
                )
                raise e
        return self._trading_pairs
    """

    @staticmethod
    async def fetch_trading_pairs(domain=None) -> List[str]:
        try:
            from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils import convert_from_exchange_trading_pair
            BASE_URL = TESTNET_BASE_URL if domain == "binance_perpetual_testnet" else PERPETUAL_BASE_URL
            async with aiohttp.ClientSession() as client:
                async with client.get(EXCHANGE_INFO_URL.format(BASE_URL), timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        raw_trading_pairs = [d["symbol"] for d in data["symbols"] if d["status"] == "TRADING"]
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in raw_trading_pairs:
                            try:
                                trading_pair = convert_from_exchange_trading_pair(raw_trading_pair)
                                if trading_pair is not None:
                                    trading_pair_list.append(trading_pair)
                                else:
                                    continue
                            except Exception:
                                pass
                        return trading_pair_list
        except Exception:
            pass
        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str, limit: int = 1000, domain=None) -> Dict[str, Any]:
        params: Dict = {"limit": str(limit), "symbol": convert_to_exchange_trading_pair(trading_pair)} if limit != 0 \
            else {"symbol": convert_to_exchange_trading_pair(trading_pair)}
        async with client.get(SNAPSHOT_REST_URL.format(domain), params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Binance market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000, self._base_url)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
            order_book = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    """
    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            return_val: Dict[str, OrderBookTrackerEntry] = {}
            for trading_pair in trading_pairs:
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                    return_val[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_timestamp, order_book)
                    self.logger().info(f"Initialized order book for {trading_pair}. ")
                    await asyncio.sleep(1)
                except Exception as e:
                    self.logger().error(f"Error getting snapshot for {trading_pair}: {e}", exc_info=True)
                    await asyncio.sleep(5)
            return return_val
    """

    async def ws_messages(self, client: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                try:
                    raw_msg: str = await asyncio.wait_for(client.recv(), timeout=30.0)
                    yield raw_msg
                except asyncio.TimeoutError:
                    await client.pong(data=b'')
        except ConnectionClosed:
            return
        finally:
            await client.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                # trading_pairs: List[str] = await self.get_trading_pairs()
                ws_subscription_path: str = "/".join([f"{convert_to_exchange_trading_pair(trading_pair).lower()}@depth"
                                                      for trading_pair in self._trading_pairs])
                stream_url: str = f"{self._stream_url}?streams={ws_subscription_path}"
                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self.ws_messages(ws):
                        msg_json = ujson.loads(raw_msg)
                        timestamp: float = time.time()
                        order_book_message: OrderBookMessage = BinancePerpetualOrderBook.diff_message_from_exchange(
                            msg_json,
                            timestamp
                        )
                        output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Websocket connection. Retrying after 30 seconds... ",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                # trading_pairs: List[str] = await self.get_trading_pairs()
                ws_subscription_path: str = "/".join([f"{convert_to_exchange_trading_pair(trading_pair).lower()}@aggTrade"
                                                      for trading_pair in self._trading_pairs])
                stream_url = f"{self._stream_url}?streams={ws_subscription_path}"
                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self.ws_messages(ws):
                        msg_json = ujson.loads(raw_msg)
                        trade_msg: OrderBookMessage = BinancePerpetualOrderBook.trade_message_from_exchange(msg_json)
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                # trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in self._trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, domain=self._base_url)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
