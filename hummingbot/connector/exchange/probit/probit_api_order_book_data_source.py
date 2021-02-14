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
from hummingbot.logger import HummingbotLogger
from . import probit_utils
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
            async with client.get(f"{constants.TICKER_PATH_URL}") as response:
                if response.status == 200:
                    resp_json = await response.json()
                    if "data" in resp_json:
                        for trading_pair in resp_json["data"]:
                            result[trading_pair["market_id"]] = trading_pair["last"]
        return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{constants.MARKETS_PATH_URL}") as response:
                if response.status == 200:
                    resp_json: Dict[str, Any] = await response.json()
                    return [market["market_id"] for market in resp_json["data"]]
                return []

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        async with aiohttp.ClientSession() as client:
            async with client.get(url=f"{constants.ORDER_BOOK_PATH_URL}",
                                  params={"market_id": trading_pair}) as response:
                if response.status != 200:
                    raise IOError(
                        f"Error fetching OrderBook for {trading_pair} at {constants.ORDER_BOOK_PATH_URL}. "
                        f"HTTP {response.status}. Response: {await response.json()}"
                    )
                return await response.json()

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = ProbitOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        bids, asks = probit_utils.convert_snapshot_message_to_order_book_row(snapshot_msg)
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

                await ws.subscribe(list(map(
                    lambda pair: f"trade.{probit_utils.convert_to_exchange_trading_pair(pair)}",
                    self._trading_pairs
                )))

                async for response in ws.on_message():
                    if response.get("result") is None:
                        continue

                    for trade in response["result"]["data"]:
                        trade: Dict[Any] = trade
                        trade_timestamp: int = ms_timestamp_to_s(trade["t"])
                        trade_msg: OrderBookMessage = ProbitOrderBook.trade_message_from_exchange(
                            trade,
                            trade_timestamp,
                            metadata={"trading_pair": probit_utils.convert_from_exchange_trading_pair(trade["i"])}
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

                await ws.subscribe(list(map(
                    lambda pair: f"book.{probit_utils.convert_to_exchange_trading_pair(pair)}.150",
                    self._trading_pairs
                )))

                async for response in ws.on_message():
                    if response.get("result") is None:
                        continue

                    order_book_data = response["result"]["data"][0]
                    timestamp: int = ms_timestamp_to_s(order_book_data["t"])
                    # data in this channel is not order book diff but the entire order book (up to depth 150).
                    # so we need to convert it into a order book snapshot.
                    # Crypto.com does not offer order book diff ws updates.
                    orderbook_msg: OrderBookMessage = ProbitOrderBook.snapshot_message_from_exchange(
                        order_book_data,
                        timestamp,
                        metadata={"trading_pair": probit_utils.convert_from_exchange_trading_pair(
                            response["result"]["instrument_name"])}
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
                        snapshot_timestamp: int = ms_timestamp_to_s(snapshot["t"])
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
