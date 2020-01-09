#!/usr/bin/env python
from collections import namedtuple
import logging
import time
from functools import partial

import aiohttp
import asyncio
import ujson
import pandas as pd
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
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import (
    OrderBookTrackerEntry
)
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bitfinex import BITFINEX_REST_URL, BITFINEX_WS_URI
from hummingbot.market.bitfinex.bitfinex_active_order_tracker import BitfinexActiveOrderTracker
from hummingbot.market.bitfinex.bitfinex_order_book import BitfinexOrderBook
from hummingbot.market.bitfinex.bitfinex_order_book_message import \
    BitfinexOrderBookMessage
from hummingbot.market.bitfinex.bitfinex_order_book_tracker_entry import \
    BitfinexOrderBookTrackerEntry

BOOK_RET_TYPE = List[Dict[str, Any]]
RESPONSE_SUCCESS = 200
NaN = float("nan")
MAIN_FIAT = ("USD", "USDC", "USDS", "DAI", "PAX", "TUSD", "USDT")

s_base, s_quote = slice(1, 4), slice(4, 7)

Ticker = namedtuple(
    "Ticker",
    "symbol bid bid_size ask ask_size daily_change daily_change_percent last_price volume high low"
)
BookStructure = namedtuple("Book", "order_id price amount")
TradeStructure = namedtuple("Trade", "id mts amount price")
# n0-n9 no documented, we dont' know, maybe later market write docs
ConfStructure = namedtuple("Conf", "n0 n1 n2 min max n5 n6 n7 n8 n9")

# this values ​​set by empirically way, because the bitfinex-market does not have
# these values. maybe later it will be in market-api.
bitfinex_base_increment = 1e-8
bitfinex_quote_increment = 0.01


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
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        # Dictionary that maps Order IDs to book enties (i.e. price, amount, and update_id the
        # way it is stored in Hummingbot order book, usually timestamp)
        self._tracked_book_entries: Dict[int, OrderBookRow] = {}

    @staticmethod
    def _get_prices(data, conf_data: Dict[str, ConfStructure]) -> Dict[str, Any]:
        pairs = [
            Ticker(*item)
            for item in data if item[0].startswith("t") and item[0].isalpha()
        ]

        def symbol_join_f(dash=None, item=None):
            return f"{item.symbol[s_base]}{dash}{item.symbol[s_quote]}"

        symbol_f = partial(symbol_join_f, "")
        symbol_dash_f = partial(symbol_join_f, "-")

        return {
            symbol_dash_f(item): {
                "symbol": symbol_dash_f(item),
                "baseAsset": item.symbol[s_base],
                "base_increment": bitfinex_base_increment,
                "base_max_size": conf_data[symbol_f(item)].max,
                "base_min_size": conf_data[symbol_f(item)].min,
                "display_name": symbol_f(item),
                "quoteAsset": item.symbol[s_quote],
                "quote_increment": bitfinex_quote_increment,
                "volume": item.volume,
                "price": item.last_price,
            }
            for item in pairs
        }

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

    def _get_tracked_order_by_id(self, order_id: int):
        if order_id in self._tracked_book_entries:
            return self._tracked_book_entries[order_id]
        else:
            return {"order": None, "side": None}

    def _track_order(self, order_id: int, order: OrderBookRow, side: str):
        self._tracked_book_entries[order_id] = {"order": order, "side": side}

    def _untrack_order(self, order_id):
        if order_id in self._tracked_book_entries:
            del self._tracked_book_entries[order_id]

    @classmethod
    @async_ttl_cache(ttl=REQUEST_TTL, maxsize=CACHE_SIZE)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        async with aiohttp.ClientSession() as client:
            tickers_response, exchange_conf_response = await safe_gather(
                client.get(f"{BITFINEX_REST_URL}/tickers?symbols=ALL"),
                client.get(f"{BITFINEX_REST_URL}/conf/pub:info:pair"),
            )
            tickers_response: aiohttp.ClientResponse = tickers_response
            exchange_conf_response: aiohttp.ClientResponse = exchange_conf_response

            if tickers_response.status != 200:
                raise IOError(f"Error fetching Bitfinex markets information. "
                              f"HTTP status is {tickers_response.status}.")
            if exchange_conf_response.status != 200:
                raise IOError(f"Error fetching Bitfinex exchange information. "
                              f"HTTP status is {exchange_conf_response.status}.")

            tickers_data = await tickers_response.json()
            exchange_conf_data = await exchange_conf_response.json()

            conf_data = dict((e[0], ConfStructure._make(e[1])) for e in exchange_conf_data[0])
            raw_prices = cls._get_prices(tickers_data, conf_data)
            prices = cls._convert_volume(raw_prices)

            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=prices, index="symbol")

            return all_markets.sort_values("USDVolume", ascending=False)

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
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
            except Exception:
                msg = "Error getting active exchange information. Check network connection."
                self._trading_pairs = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=msg
                )

        return self._trading_pairs

    @staticmethod
    def _prepare_snapshot(pair: str, raw_snapshot: List[BookStructure]) -> Dict[str, Any]:
        """
        Return structure of three elements:
            symbol: traded pair symbol
            bids: List of OrderBookRow for bids
            asks: List of OrderBookRow for asks
        """
        bids = [OrderBookRow(i.price, i.amount, i.order_id) for i in raw_snapshot if i.amount > 0]
        asks = [OrderBookRow(i.price, abs(i.amount), i.order_id) for i in raw_snapshot if i.amount < 0]

        return {
            "symbol": pair,
            "bids": bids,
            "asks": asks,
        }

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        request_url: str = f"{BITFINEX_REST_URL}/book/t{trading_pair}/R0"
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

    def _track_snapshot(self, snapshot: Dict[str, Any], update_id: int):
        for o in snapshot["bids"]:
            self._track_order(o.update_id, OrderBookRow(o.price, o.amount, update_id), "bids")
        for o in snapshot["asks"]:
            self._track_order(o.update_id, OrderBookRow(o.price, o.amount, update_id), "asks")

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
                        snapshot_timestamp,
                        metadata={"symbol": trading_pair}
                    )

                    # print("---------------- debug 1 =========== snapshot_msg.bids")
                    # print(snapshot)
                    # print(snapshot_msg.bids)

                    order_book: OrderBook = self.order_book_create_function()
                    active_order_tracker: BitfinexActiveOrderTracker = BitfinexActiveOrderTracker()
                    order_book.apply_snapshot(
                        snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)

                    # Track added orders so that we can identify which orders are deleted in diff messages
                    self._track_snapshot(snapshot, snapshot_msg.update_id)
                    result[trading_pair] = BitfinexOrderBookTrackerEntry(
                        trading_pair, snapshot_timestamp, order_book, active_order_tracker
                    )

                    self.logger().info(
                        "Initialized order book for {trading_pair}. "
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

    def _prepare_trade(self, raw_response: str) -> Dict[str, Any]:
        *_, content = ujson.loads(raw_response)
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

    async def _listen_trades_for_pair(self, pair: str, output: asyncio.Queue):
        while True:
            try:
                async with websockets.connect(BITFINEX_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "event": "subscribe",
                        "channel": "trades",
                        "symbol": f"t{pair}",
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                    await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # response
                    await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # subscribe info
                    await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # snapshot
                    async for raw_msg in self._get_response(ws):
                        msg = self._prepare_trade(raw_msg)
                        if msg:
                            msg_book: OrderBookMessage = BitfinexOrderBook.trade_message_from_exchange(
                                msg,
                                metadata={"symbol": f"{pair}"}
                            )
                            output.put_nowait(msg_book)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.logger().error(f"listen trades for pair {pair}", err)
                self.logger().error(
                    "Unexpected error with WebSocket connection. "
                    f"Retrying after {int(self.MESSAGE_TIMEOUT)} seconds...",
                    exc_info=True)
                await asyncio.sleep(self.MESSAGE_TIMEOUT)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        trading_pairs: List[str] = await self.get_trading_pairs()

        tasks = [
            ev_loop.create_task(self._listen_trades_for_pair(pair, output))
            for pair in trading_pairs
        ]
        await asyncio.gather(*tasks)

    async def _get_response(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    def _generate_delete_message(self, symbol: str, price: float, side: str):
        timestamp = time.time()
        msg = {
            "symbol": symbol,
            side: OrderBookRow(price, 0, timestamp)    # 0 amount will force the order to be deleted
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
            side_key: OrderBookRow(price, abs(amount), timestamp)
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
        _, content = ujson.loads(raw_response)

        if isinstance(content, list) and len(content) == 3:
            order_id = content[0]
            price = content[1]
            amount = content[2]

            os = self._get_tracked_order_by_id(order_id)
            order = os["order"]
            side = os["side"]

            if order is not None:
                # this is not a new order. Either update it or delete it
                if price == 0:
                    self._untrack_order(order_id)
                    # print("-------------- Deleted order %d" % (order_id))
                    return self._generate_delete_message(pair, order.price, side)
                else:
                    self._track_order(order_id, OrderBookRow(price, abs(amount), order.update_id), side)
                    return None
            else:
                # this is a new order unless the price is 0, just track it and create message that
                # will add it to the order book
                if price != 0:
                    # print("-------------- Add order %d" % (order_id))
                    return self._generate_add_message(pair, price, amount)
        return None

    async def _listen_order_book_for_pair(self, pair: str, output: asyncio.Queue):
        while True:
            try:
                async with websockets.connect(BITFINEX_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "event": "subscribe",
                        "channel": "book",
                        "prec": "R0",
                        "symbol": f"t{pair}",
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                    await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # response
                    await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # subscribe info
                    await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)  # snapshot

                    async for raw_msg in self._get_response(ws):
                        # print("------------- debug 3 ============== raw update message:")
                        # print(raw_msg)
                        msg = self._parse_raw_update(pair, raw_msg)

                        # print("------------- debug 3 ============== update message:")
                        # print(msg)

                        if msg is not None:
                            output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.logger().error(err)
                self.logger().network(
                    f"Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. "
                                    f"Retrying in {int(self.MESSAGE_TIMEOUT)} seconds. "
                                    "Check network connection."
                )
                await asyncio.sleep(self.MESSAGE_TIMEOUT)

    async def listen_for_order_book_diffs(self,
                                          ev_loop: asyncio.BaseEventLoop,
                                          output: asyncio.Queue):
        trading_pairs: List[str] = await self.get_trading_pairs()

        tasks = [
            self._listen_order_book_for_pair(pair, output)
            for pair in trading_pairs
        ]

        await asyncio.gather(*tasks)

    async def listen_for_order_book_snapshots(self,
                                              ev_loop: asyncio.BaseEventLoop,
                                              output: asyncio.Queue):
        while True:
            trading_pairs: List[str] = await self.get_trading_pairs()

            try:
                async with aiohttp.ClientSession() as client:
                    for pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = BitfinexOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"product_id": pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {pair}")

                            await asyncio.sleep(self.TIME_SLEEP_BETWEEN_REQUESTS)
                        except asyncio.CancelledError:
                            raise
                        except Exception as err:
                            self.logger().error("Listening snapshots", err)
                            self.logger().network(
                                f"Unexpected error with WebSocket connection.",
                                exc_info=True,
                                app_warning_msg="Unexpected error with WebSocket connection. "
                                                f"Retrying in {self.TIME_SLEEP_BETWEEN_REQUESTS} sec."
                                                f"Check network connection."
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
