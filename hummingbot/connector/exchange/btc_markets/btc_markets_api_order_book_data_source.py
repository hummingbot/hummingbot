#!/usr/bin/env python
import asyncio
import logging
import time
import aiohttp
import pandas as pd
import hummingbot.connector.exchange.btc_markets.btc_markets_constants as constants


from typing import Optional, List, Dict, Any
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger

from .btc_markets_active_order_tracker import BtcMarketsActiveOrderTracker
from .btc_markets_order_book import BtcMarketsOrderBook
from .btc_markets_websocket import BtcMarketsWebsocket
from .btc_markets_utils import str_date_to_ts


class BtcMarketsAPIOrderBookDataSource(OrderBookTrackerDataSource):
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
            for t_pair in trading_pairs:
                resp = await client.get(f"{constants.REST_URL}/"
                                        f"{constants.MARKETS_URL}/"
                                        f"{t_pair}/trades")
                if resp.status != 200:
                    raise IOError(
                        f"Error fetching last traded prices at {constants.REST_URL}/{constants.MARKETS_URL}/"
                        f"{t_pair}/trades. "
                        f"HTTP status is {resp.status}."
                    )
                resp_json = await resp.json()
                results = resp_json
                # last trade is the most recent trade
                result[t_pair] = float(results[-1].get("price"))

        return result

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{constants.REST_URL}/"f"{constants.MARKETS_URL}/", timeout=10) as response:
                if response.status == 200:
                    try:
                        all_trading_pairs: Dict[str, Any] = await response.json()
                        trading_pair_list: List[str] = []
                        for all_trading_pair in all_trading_pairs:
                            trading_pair_list.append(all_trading_pair.get('marketId'))
                        return trading_pair_list
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
            orderbook_response = await client.get(
                f"{constants.REST_URL}/"
                f"{constants.MARKETS_URL}/"
                f"{trading_pair}/orderbook"
            )

            if orderbook_response.status != 200:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {constants.EXCHANGE_NAME}. "
                    f"HTTP status is {orderbook_response.status}."
                )

            orderbook_data: List[Dict[str, Any]] = await safe_gather(orderbook_response.json())
            orderbook_data = orderbook_data[0]

        return orderbook_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BtcMarketsOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: BtcMarketsActiveOrderTracker = BtcMarketsActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                ws = BtcMarketsWebsocket()
                await ws.connect()
                await ws.subscribe_marketIds(['trade'], list(map(lambda pair: f"{pair}", self._trading_pairs)))

                async for response in ws.on_message():
                    # print(f"WS_SOCKET: {response}")
                    if "trade" in response:
                        continue

                    trade: Dict[Any] = response
                    trade_timestamp: int = str_date_to_ts(trade["timestamp"])
                    trade_msg: OrderBookMessage = BtcMarketsOrderBook.trade_message_from_exchange(
                        trade,
                        trade_timestamp,
                        metadata={"trading_pair": trade["marketId"]}
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
        Listen for orderbook diffs using websocket orderbookUpdate channel
        https://api.btcmarkets.net/doc/v3#section/OrderbookUpdate-event
        """
        while True:
            try:
                ws = BtcMarketsWebsocket()
                await ws.connect()
                await ws.subscribe_marketIds(['orderbookUpdate'], list(map(lambda pair: f"{pair}", self._trading_pairs)))

                async for response in ws.on_message():
                    # print(f"WS_SOCKET: {response}")
                    if "snapshot" in response:
                        order_book_data = response
                        order_timestamp: int = str_date_to_ts(order_book_data["timestamp"])

                        # remove the Snapshot=true key so subsequent diff messages don't break
                        del order_book_data["snapshot"]

                        # The initial orderbookUpdate snapshot message covers all bids/asks represented as arrays of
                        # [price, volume, count] tuples as well as snapshot:true attribute
                        # so we need to convert it into an order book snapshot.

                        orderbook_msg: OrderBookMessage = BtcMarketsOrderBook.snapshot_message_from_exchange(
                            order_book_data,
                            order_timestamp,
                            metadata={"trading_pair": (response["marketId"])}
                        )
                        output.put_nowait(orderbook_msg)
                        continue
                    else:
                        order_book_data = response
                        order_timestamp: int = str_date_to_ts(order_book_data["timestamp"])
                        orderbook_msg: OrderBookMessage = BtcMarketsOrderBook.diff_message_from_exchange(
                            order_book_data,
                            order_timestamp,
                            metadata={"trading_pair": (response["marketId"])})
                        output.put_nowait(orderbook_msg)
                        continue

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
                        # snapshot_timestamp: int = ms_timestamp_to_s(snapshot["t"])
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = BtcMarketsOrderBook.snapshot_message_from_exchange(
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
