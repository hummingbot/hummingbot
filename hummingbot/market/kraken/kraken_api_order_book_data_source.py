#!/usr/bin/env python

import asyncio
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
import ujson
import websockets
from websockets.exceptions import ConnectionClosed
from collections import defaultdict

from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.market.kraken.kraken_order_book import KrakenOrderBook
import hummingbot.market.kraken.kraken_constants as constants


SNAPSHOT_REST_URL = "https://api.kraken.com/0/public/Depth"
DIFF_STREAM_URL = "wss://ws.kraken.com"
TICKER_URL = "https://api.kraken.com/0/public/Ticker"
ASSET_PAIRS_URL = "https://api.kraken.com/0/public/AssetPairs"


class KrakenAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _kraobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kraobds_logger is None:
            cls._kraobds_logger = logging.getLogger(__name__)
        return cls._kraobds_logger

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

            trading_pairs_response = await client.get(ASSET_PAIRS_URL)
            trading_pairs_response: aiohttp.ClientResponse = trading_pairs_response

            if trading_pairs_response.status != 200:
                raise IOError(f"Error fetching Kraken trading pairs. "
                              f"HTTP status is {trading_pairs_response.status}.")

            trading_pairs_data: Dict[str, Any] = await trading_pairs_response.json()
            trading_pairs_data["result"] = {
                pair: details for pair, details in trading_pairs_data["result"].items() if "." not in pair}

            wsname_dict: Dict[str, str] = {pair: details["wsname"]
                                           for pair, details in trading_pairs_data["result"].items()}
            trading_pairs: Dict[str, Any] = {pair: {"baseAsset": wsname_dict[pair].split("/")[0],
                                                    "quoteAsset": wsname_dict[pair].split("/")[1],
                                                    "wsname": wsname_dict[pair]}
                                             for pair in trading_pairs_data["result"]}

            trading_pairs_str: str = ','.join(trading_pairs.keys())

            market_response = await client.get(f"{TICKER_URL}?pair={trading_pairs_str}")
            market_response: aiohttp.ClientResponse = market_response

            if market_response.status != 200:
                raise IOError(f"Error fetching Kraken markets information. "
                              f"HTTP status is {market_response.status}.")

            market_data = await market_response.json()

            market_data: List[Dict[str, Any]] = [{"pair": pair, **market_data["result"][pair], **trading_pairs[pair]}
                                                 for pair in market_data["result"]
                                                 if pair in trading_pairs]

            # Build the data frame.
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="pair")
            all_markets["lastPrice"] = all_markets.c.map(lambda x: x[0]).astype("float")
            all_markets.loc[:, "volume"] = all_markets.v.map(lambda x: x[1]).astype("float")

            price_dict: Dict[str, float] = await cls.get_prices_from_df(all_markets)

            usd_volume: List[float] = [
                (
                    baseVolume * price_dict[baseAsset] if baseAsset in price_dict else -1
                )
                for baseAsset, baseVolume in zip(all_markets.baseAsset,
                                                 all_markets.volume)]
            all_markets.loc[:, "USDVolume"] = usd_volume

            return all_markets.sort_values("USDVolume", ascending=False)

    @staticmethod
    async def get_prices_from_df(df: pd.DataFrame) -> Dict[str, float]:
        row_dict: Dict[str, Dict[str, pd.Series]] = defaultdict(dict)
        for (i, row) in df.iterrows():
            row_dict[row.baseAsset][row.quoteAsset] = row

        price_dict: Dict[str, float] = {base: None for base in row_dict}

        quote_prices: Dict[str, float] = {
            quote: row_dict[quote]["USD"].lastPrice for quote in constants.CRYPTO_QUOTES
        }

        def get_price(base, depth=0) -> float:
            if price_dict.get(base) is not None:
                return price_dict[base]
            elif base == "USD":
                return 1.
            elif "USD" in row_dict[base]:
                return row_dict[base]["USD"].lastPrice
            else:
                for quote in row_dict[base]:
                    if quote in quote_prices:
                        return quote_prices[quote] * row_dict[base][quote].lastPrice

        for base in price_dict:
            price_dict[base] = get_price(base)

        return price_dict

    async def get_trading_pairs(self) -> Optional[List[str]]:
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
            except Exception:
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str, limit: int = 1000) -> Dict[str, Any]:
        original_trading_pair: str = trading_pair
        params: Dict[str, str] = {"count": str(limit), "pair": trading_pair} if limit != 0 else {"pair": trading_pair}
        async with client.get(SNAPSHOT_REST_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Kraken market snapshot for {original_trading_pair}. "
                              f"HTTP status is {response.status}.")
            response_json = await response.json()
            if len(response_json["error"]) > 0:
                raise IOError(f"Error fetching Kraken market snapshot for {original_trading_pair}. "
                              f"Error is {response_json['error']}.")
            data: Dict[str, Any] = next(iter(response_json["result"].values()))
            data = {"trading_pair": trading_pair, **data}
            data["latest_update"] = max([*map(lambda x: x[2], data["bids"] + data["asks"])], default=0.)

            # Need to add the symbol into the snapshot message for the Kafka message queue.
            # Because otherwise, there'd be no way for the receiver to know which market the
            # snapshot belongs to.

            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, OrderBookTrackerEntry] = {}

            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = KrakenOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                    retval[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_timestamp, order_book)
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")
                    # Each 1000 limit snapshot costs 10 requests and Binance rate limit is 20 requests per second.
                    await asyncio.sleep(1.0)
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5.0)
            return retval

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    if ((msg != "{\"event\":\"heartbeat\"}" and
                         "\"event\":\"systemStatus\"" not in msg and
                         "\"event\":\"subscriptionStatus\"" not in msg)):
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
                ws_message: str = await self.get_ws_subscription_message("trade")

                async with websockets.connect(DIFF_STREAM_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    await ws.send(ws_message)
                    async for raw_msg in self._inner_messages(ws):
                        msg: List[Any] = ujson.loads(raw_msg)
                        trades: List[Dict[str, Any]] = [{"pair": msg[-1], "trade": trade} for trade in msg[1]]
                        for trade in trades:
                            trade_msg: OrderBookMessage = KrakenOrderBook.trade_message_from_exchange(trade)
                            output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws_message: str = await self.get_ws_subscription_message("book")
                async with websockets.connect(DIFF_STREAM_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    await ws.send(ws_message)
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)

                        msg_dict = {"trading_pair": msg[-1],
                                    "asks": msg[1].get("a", []) or msg[1].get("as", []) or [],
                                    "bids": msg[1].get("b", []) or msg[1].get("bs", []) or []}
                        msg_dict["update_id"] = max([*map(lambda x: float(x[2]), msg_dict["bids"] + msg_dict["asks"])],
                                                    default=0.)
                        if "as" in msg[1] and "bs" in msg[1]:
                            order_book_message: OrderBookMessage = KrakenOrderBook.snapshot_ws_message_from_exchange(
                                msg_dict, time.time())
                        else:
                            order_book_message: OrderBookMessage = KrakenOrderBook.diff_message_from_exchange(
                                msg_dict, time.time())
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
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = KrakenOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error. ", exc_info=True)
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error. ", exc_info=True)
                await asyncio.sleep(5.0)

    async def get_ws_subscription_message(self, subscription_type: str):
        # all_markets: pd.DataFrame = await self.get_active_exchange_markets()
        trading_pairs: List[str] = []
        for tp in self._trading_pairs:
            base, quote = self.split_to_base_quote(tp)
            trading_pairs.append(f"{base}/{quote}")

        ws_message_dict: Dict[str, Any] = {"event": "subscribe",
                                           "pair": trading_pairs,
                                           "subscription": {"name": subscription_type, "depth": 1000}}

        ws_message: str = ujson.dumps(ws_message_dict)

        return ws_message

    @staticmethod
    def split_to_base_quote(exchange_trading_pair: str) -> (Optional[str], Optional[str]):
        base, quote = None, None
        for quote_asset in constants.QUOTES:
            if quote_asset == exchange_trading_pair[-len(quote_asset):]:
                base, quote = exchange_trading_pair[:-len(quote_asset)], exchange_trading_pair[-len(quote_asset):]
                break
        return base, quote
