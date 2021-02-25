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
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
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
        tasks = [cls._get_last_traded_price(t_pair) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def _get_last_traded_price(cls, pair: str) -> float:
        result = await AsyncIdexClient().market.get_tickers(
            market=await to_idex_pair(pair)
        )
        if result:
            return float(result[0].close or 0)

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        client = AsyncIdexClient()
        snapshot = await client.market.get_orderbook(
            market=trading_pair,
            limit=1000
        )
        timestamp = time.time()
        snapshot_message = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": snapshot.sequence,
            "bids": snapshot.bids,
            "asks": snapshot.asks
        }, timestamp=timestamp)

        order_book = self.order_book_create_function()
        order_book.apply_snapshot(
            snapshot_message.bids,
            snapshot_message.asks,
            snapshot_message.update_id
        )
        return order_book

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                client = AsyncIdexClient()
                async for message in client.subscribe(
                        subscriptions=["l2orderbook"],
                        markets=(await get_markets())):
                    # Filter all none WebSocketResponseL2OrderBookShort types
                    if not isinstance(message, WebSocketResponseL2OrderBookShort):
                        continue
                    timestamp = message.t
                    order_book_message = OrderBookMessage(OrderBookMessageType.DIFF, {
                        "trading_pair": message.m,
                        "update_id": message.u,
                        "bids": message.b,
                        "asks": message.a
                    }, timestamp=timestamp)
                    output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                    exc_info=True
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

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                client = AsyncIdexClient()
                async for message in client.subscribe(
                        subscriptions=["trades"],
                        markets=[(await to_idex_pair(pair)) for pair in self._trading_pairs]):

                    # Filter any none WebSocketResponseTradeShort types
                    if not isinstance(message, WebSocketResponseTradeShort):
                        continue

                    timestamp = message.t
                    trade_message = OrderBookMessage(OrderBookMessageType.TRADE, {
                        "trading_pair": message.m,
                        "trade_type": from_idex_trade_type(message.s),
                        "trade_id": message.i,
                        "update_id": message.u,
                        "price": message.p,
                        "amount": message.q
                    }, timestamp=timestamp * 1e-3)
                    output.put_nowait(trade_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)  # TODO: sleep timeout ?

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        return [
            market.market for market in (await AsyncIdexClient().public.get_markets())
        ]
