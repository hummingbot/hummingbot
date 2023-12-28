#!/usr/bin/env python
import asyncio
import logging
import time
from collections import namedtuple
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
import pandas as pd
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.connector.exchange.bitfinex import BITFINEX_REST_URL, BITFINEX_WS_URI, ContentEventType
from hummingbot.connector.exchange.bitfinex.bitfinex_active_order_tracker import BitfinexActiveOrderTracker
from hummingbot.connector.exchange.bitfinex.bitfinex_order_book import BitfinexOrderBook
from hummingbot.connector.exchange.bitfinex.bitfinex_order_book_message import BitfinexOrderBookMessage
from hummingbot.connector.exchange.bitfinex.bitfinex_order_book_tracker_entry import BitfinexOrderBookTrackerEntry
from hummingbot.connector.exchange.bitfinex.bitfinex_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    join_paths,
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger

BOOK_RET_TYPE = List[Dict[str, Any]]
RESPONSE_SUCCESS = 200
NaN = float("nan")
MAIN_FIAT = ("USD", "USDC", "USDS", "DAI", "PAX", "TUSD", "USDT")

Ticker = namedtuple(
    "Ticker",
    "bid bid_size ask ask_size daily_change daily_change_percent last_price volume high low"
)
BookStructure = namedtuple("Book", "price count amount")
TradeStructure = namedtuple("Trade", "id mts amount price")
# n0-n9 no documented, we dont' know, maybe later market write docs
ConfStructure = namedtuple("Conf", "n0 n1 n2 min max n5 n6 n7 n8 n9")


class BitfinexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    STEP_TIME_SLEEP = 1.0
    REQUEST_TTL = 60 * 30
    TIME_SLEEP_BETWEEN_REQUESTS = 5.0
    CACHE_SIZE = 1
    SNAPSHOT_LIMIT_SIZE = 100

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__(trading_pairs)
        self._trading_pairs: Optional[List[str]] = trading_pairs
        # Dictionary that maps Order IDs to book enties (i.e. price, amount, and update_id the
        # way it is stored in Hummingbot order book, usually timestamp)
        self._tracked_book_entries: Dict[int, OrderBookRow] = {}

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{BITFINEX_REST_URL}/conf/pub:list:pair:exchange", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        trading_pair_list: List[str] = []
                        for trading_pair in data[0]:
                            # change the following line accordingly
                            converted_trading_pair: Optional[str] = \
                                convert_from_exchange_trading_pair(trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                            else:
                                logging.getLogger(__name__).info(f"Could not parse the trading pair "
                                                                 f"{trading_pair}, skipping it...")
                        return trading_pair_list
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete available
            pass

        return []

    @staticmethod
    def _convert_volume(raw_prices: Dict[str, Any]) -> BOOK_RET_TYPE:
        converters = {}
        prices = []

        for price in [v for v in raw_prices.values() if v["quoteAsset"] in MAIN_FIAT]:
            raw_symbol = f"{price['baseAsset']}-{price['quoteAsset']}"
            symbol = f"{price['baseAsset']}{price['quoteAsset']}"
            prices.append(
                {
                    **price,
                    "symbol": symbol,
                    "USDVolume": price["volume"] * price["price"]
                }
            )
            converters[price["baseAsset"]] = price["price"]
            del raw_prices[raw_symbol]

        for raw_symbol, item in raw_prices.items():
            symbol = f"{item['baseAsset']}{item['quoteAsset']}"
            if item["baseAsset"] in converters:
                prices.append(
                    {
                        **item,
                        "symbol": symbol,
                        "USDVolume": item["volume"] * converters[item["baseAsset"]]
                    }
                )
                if item["quoteAsset"] not in converters:
                    converters[item["quoteAsset"]] = item["price"] / converters[item["baseAsset"]]
                continue

            if item["quoteAsset"] in converters:
                prices.append(
                    {
                        **item,
                        "symbol": symbol,
                        "USDVolume": item["volume"] * item["price"] * converters[item["quoteAsset"]]
                    }
                )
                if item["baseAsset"] not in converters:
                    converters[item["baseAsset"]] = item["price"] * converters[item["quoteAsset"]]
                continue

            prices.append({
                **item,
                "symbol": symbol,
                "volume": NaN})

        return prices

    @staticmethod
    def _prepare_snapshot(pair: str, raw_snapshot: List[BookStructure]) -> Dict[str, Any]:
        """
        Return structure of three elements:
            symbol: traded pair symbol
            bids: List of OrderBookRow for bids
            asks: List of OrderBookRow for asks
        """
        update_id = time.time()
        bids = [OrderBookRow(i.price, i.amount, update_id) for i in raw_snapshot if i.amount > 0]
        asks = [OrderBookRow(i.price, abs(i.amount), update_id) for i in raw_snapshot if i.amount < 0]

        return {
            "symbol": pair,
            "bids": bids,
            "asks": asks,
        }

    def _prepare_trade(self, raw_response: str) -> Optional[Dict[str, Any]]:
        *_, content = ujson.loads(raw_response)
        if content == ContentEventType.HEART_BEAT:
            return None
        try:
            trade = TradeStructure(*content)
        except Exception as err:
            self.logger().error(err)
            self.logger().error(raw_response)
        else:
            return {
                "id": trade.id,
                "mts": trade.mts,
                "amount": trade.amount,
                "price": trade.price,
            }

    async def _get_response(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                yield msg
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    def _generate_delete_message(self, symbol: str, price: float, amount: str):
        side_key = "bids" if amount == 1 else "asks"
        timestamp = time.time()
        msg = {
            "symbol": symbol,
            side_key: OrderBookRow(price, 0, timestamp),    # 0 amount will force the order to be deleted
            "update_id": time.time()  # Assume every update is incremental
        }
        return BitfinexOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp)

    def _generate_add_message(self, symbol: str, price: float, amount: float):
        side_key = "bids" if amount > 0 else "asks"
        timestamp = time.time()
        msg = {
            "symbol": symbol,
            side_key: OrderBookRow(price, abs(amount), timestamp),
            "update_id": timestamp  # Assume every update is incremental
        }
        return BitfinexOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp)

    def _parse_raw_update(self, pair: str, raw_response: str) -> OrderBookMessage:
        """
        Parses raw update, if price for a tracked order identified by ID is 0, then order is deleted
        Returns OrderBookMessage
        """

        *_, content = ujson.loads(raw_response)

        if isinstance(content, list) and len(content) == 3:
            price = content[0]
            count = content[1]
            amount = content[2]

            if count > 0:
                return self._generate_add_message(pair, price, amount)
            else:
                return self._generate_delete_message(pair, price, amount)

        return None

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        tasks = [cls.get_last_traded_price(t_pair) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str) -> float:
        async with aiohttp.ClientSession() as client:
            # https://api-pub.bitfinex.com/v2/ticker/tBTCUSD
            ticker_url: str = join_paths(BITFINEX_REST_URL, f"ticker/{convert_to_exchange_trading_pair(trading_pair)}")
            try:
                resp = await client.get(ticker_url)
                resp_json = await resp.json()
                if "error" in resp_json:
                    raise ValueError(f"There was an error requesting ticker information {trading_pair} ({resp_json})")
                ticker = Ticker(*resp_json)
                last_price = float(ticker.last_price)
            except Exception as ex:
                details = resp_json or resp
                cls.logger().error(
                    f"Error encountered requesting ticker information. The response was: {details} ({str(ex)})")
                last_price = 0.0
            return last_price

    async def get_trading_pairs(self) -> List[str]:
        """
        Get a list of active trading pairs
        (if the market class already specifies a list of trading pairs,
        returns that list instead of all active trading pairs)
        :returns: A list of trading pairs defined by the market class,
        or all active trading pairs from the rest API
        """
        if not self._trading_pairs:
            try:
                self._trading_pairs = await self.fetch_trading_pairs()
            except Exception:
                msg = "Error getting active exchange information. Check network connection."
                self._trading_pairs = []
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=msg
                )

        return self._trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        request_url: str = f"{BITFINEX_REST_URL}/book/{convert_to_exchange_trading_pair(trading_pair)}/P0"
        # by default it's = 50, 25 asks + 25 bids.
        # set 100: 100 asks + 100 bids
        # Exchange only allow: 1, 25, 100 (((
        params = {
            "len": self.SNAPSHOT_LIMIT_SIZE
        }

        async with client.get(request_url, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != RESPONSE_SUCCESS:
                raise IOError(f"Error fetching Bitfinex market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")

            raw_data: Dict[str, Any] = await response.json()
            return self._prepare_snapshot(trading_pair, [BookStructure(*i) for i in raw_data])

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = BitfinexOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp
            )
            active_order_tracker: BitfinexActiveOrderTracker = BitfinexActiveOrderTracker()
            bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
            order_book = self.order_book_create_function()
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        result: Dict[str, OrderBookTrackerEntry] = {}

        trading_pairs: List[str] = await self.get_trading_pairs()
        number_of_pairs: int = len(trading_pairs)

        async with aiohttp.ClientSession() as client:
            for idx, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = BitfinexOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp
                    )

                    order_book: OrderBook = self.order_book_create_function()
                    active_order_tracker: BitfinexActiveOrderTracker = BitfinexActiveOrderTracker()
                    order_book.apply_snapshot(
                        snapshot_msg.bids,
                        snapshot_msg.asks,
                        snapshot_msg.update_id
                    )

                    result[trading_pair] = BitfinexOrderBookTrackerEntry(
                        trading_pair, snapshot_timestamp, order_book, active_order_tracker
                    )

                    self.logger().info(
                        f"Initialized order book for {trading_pair}. "
                        f"{idx+1}/{number_of_pairs} completed."
                    )
                    await asyncio.sleep(self.STEP_TIME_SLEEP)
                except IOError:
                    self.logger().network(
                        f"Error getting snapshot for {trading_pair}.",
                        exc_info=True,
                        app_warning_msg=f"Error getting snapshot for {trading_pair}. "
                                        "Check network connection."
                    )
                except Exception:
                    self.logger().error(
                        f"Error initializing order book for {trading_pair}. ",
                        exc_info=True
                    )

        return result

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()

                for trading_pair in trading_pairs:
                    async with websockets.connect(BITFINEX_WS_URI) as ws:
                        payload: Dict[str, Any] = {
                            "event": "subscribe",
                            "channel": "trades",
                            "symbol": convert_to_exchange_trading_pair(trading_pair),
                        }
                        await ws.send(ujson.dumps(payload))
                        await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # response
                        await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # subscribe info
                        await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # snapshot

                        async for raw_msg in self._get_response(ws):
                            msg = self._prepare_trade(raw_msg)
                            if msg:
                                msg_book: OrderBookMessage = BitfinexOrderBook.trade_message_from_exchange(
                                    msg,
                                    metadata={"symbol": f"{trading_pair}"}
                                )
                                output.put_nowait(msg_book)

            except Exception as err:
                self.logger().error(err)
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. "
                                    f"Retrying in {int(self.MESSAGE_TIMEOUT)} seconds. "
                                    "Check network connection."
                )
                await asyncio.sleep(5)

    async def listen_for_order_book_diffs(self,
                                          ev_loop: asyncio.BaseEventLoop,
                                          output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()

                for trading_pair in trading_pairs:
                    async with websockets.connect(BITFINEX_WS_URI) as ws:
                        payload: Dict[str, Any] = {
                            "event": "subscribe",
                            "channel": "book",
                            "prec": "P0",
                            "symbol": convert_to_exchange_trading_pair(trading_pair),
                        }
                        await ws.send(ujson.dumps(payload))
                        await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # response
                        await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # subscribe info
                        raw_snapshot = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # snapshot
                        snapshot = self._prepare_snapshot(trading_pair, [BookStructure(*i) for i in ujson.loads(raw_snapshot)[1]])
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = BitfinexOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp
                        )
                        output.put_nowait(snapshot_msg)

                        async for raw_msg in self._get_response(ws):
                            msg = self._parse_raw_update(trading_pair, raw_msg)
                            if msg is not None:
                                output.put_nowait(msg)

            except Exception as err:
                self.logger().error(err)
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. "
                                    f"Retrying in {int(self.MESSAGE_TIMEOUT)} seconds. "
                                    "Check network connection."
                )
                await asyncio.sleep(5)

    async def listen_for_order_book_snapshots(self,
                                              ev_loop: asyncio.BaseEventLoop,
                                              output: asyncio.Queue):
        while True:
            trading_pairs: List[str] = await self.get_trading_pairs()

            try:
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = BitfinexOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")

                            await asyncio.sleep(self.TIME_SLEEP_BETWEEN_REQUESTS)
                        except asyncio.CancelledError:
                            raise
                        except Exception as err:
                            self.logger().error("Listening snapshots", err)
                            self.logger().network(
                                "Unexpected error with HTTP connection.",
                                exc_info=True,
                                app_warning_msg="Unexpected error with HTTP connection. "
                                                f"Retrying in {self.TIME_SLEEP_BETWEEN_REQUESTS} sec."
                                                "Check network connection."
                            )
                            await asyncio.sleep(self.TIME_SLEEP_BETWEEN_REQUESTS)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(
                        minute=0, second=0, microsecond=0
                    )
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.logger().error("Listening snapshots", err)
                self.logger().error("Unexpected error", exc_info=True)
                await asyncio.sleep(self.TIME_SLEEP_BETWEEN_REQUESTS)
