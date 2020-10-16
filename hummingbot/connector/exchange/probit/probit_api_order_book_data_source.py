#!/usr/bin/env python
import asyncio
import logging
import time
import aiohttp
import pandas as pd
import hummingbot.connector.exchange.probit.probit_constants as constants

from typing import Optional, List, Dict, Any
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from . import probit_utils
from .probit_active_order_tracker import ProbitActiveOrderTracker
from .probit_order_book import ProbitOrderBook
from .probit_websocket import ProbitWebsocket
from .probit_utils import ms_timestamp_to_s


class ProbitAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        result = {}
        async with aiohttp.ClientSession() as client:
            querystring = {"market_ids": trading_pairs}
            resp = await client.request("GET", url=f"{constants.REST_URL}/ticker", params=querystring)

            resp_json = await resp.json()
            for t_pair in trading_pairs:
                last_trade = [o["last"] for o in resp_json["data"] if o["market_id"] ==
                              probit_utils.convert_to_exchange_trading_pair(t_pair)]
                if last_trade and last_trade[0] is not None:
                    result[t_pair] = last_trade[0]
        return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{constants.REST_URL}/ticker", timeout=10) as response:
                if response.status == 200:
                    from hummingbot.connector.exchange.probit.probit_utils import \
                        convert_from_exchange_trading_pair
                    try:
                        data: Dict[str, Any] = await response.json()
                        return [convert_from_exchange_trading_pair(item["market_id"]) for item in data["data"]]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                return []

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        async with aiohttp.ClientSession() as client:
            querystring = {"market_id": probit_utils.convert_to_exchange_trading_pair(trading_pair)}
            orderbook_response = await client.request("GET", url=f"{constants.REST_URL}/order_book", params=querystring)

            if orderbook_response.status != 200:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {constants.EXCHANGE_NAME}. "
                    f"HTTP status is {orderbook_response.status}."
                )

            orderbook_data: List[Dict[str, Any]] = await safe_gather(orderbook_response.json())
            orderbook_data = orderbook_data["data"]

        return orderbook_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = ProbitOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: ProbitActiveOrderTracker = ProbitActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                ws = ProbitWebsocket()
                await ws.connect()

                for trading_pair in self._trading_pairs:
                    await ws.subscribe(channel="marketdata", data={
                        "market_id": probit_utils.convert_to_exchange_trading_pair(trading_pair),
                        "interval": 100,
                        "filter": ["recent_trades"]
                    })

                async for response in ws.on_message():
                    if response.get("recent_trades") is None:
                        continue

                    for trade in response["recent_trades"]:
                        trade: Dict[Any] = trade
                        trade_timestamp: int = ms_timestamp_to_s(trade["time"])
                        trade_msg: OrderBookMessage = ProbitOrderBook.trade_message_from_exchange(
                            trade,
                            trade_timestamp,
                            metadata={"trading_pair": probit_utils.convert_from_exchange_trading_pair(response["market_id"])}
                        )
                        output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        while True:
            try:
                ws = ProbitWebsocket()
                await ws.connect()

                for trading_pair in self._trading_pairs:
                    await ws.subscribe(channel="marketdata", data={
                        "market_id": probit_utils.convert_to_exchange_trading_pair(trading_pair),
                        "interval": 100,
                        "filter": ["order_books_l4"]
                    })

                async for response in ws.on_message():
                    if response.get("order_books_l4") is None:
                        continue

                    order_book_data = response["order_books_l4"]
                    timestamp: int = time.time()
                    # data in this channel is not order book diff but the entire order book (up to depth 150).
                    # so we need to convert it into a order book snapshot.
                    # Probit does not offer order book diff ws updates.
                    orderbook_msg: OrderBookMessage = ProbitOrderBook.snapshot_message_from_exchange(
                        order_book_data,
                        timestamp,
                        metadata={"trading_pair": probit_utils.convert_from_exchange_trading_pair(response["market_id"])}
                    )
                    output.put_nowait(orderbook_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                await asyncio.sleep(30.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = ProbitOrderBook.snapshot_message_from_exchange(
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
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection."
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
