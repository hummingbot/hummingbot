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
from itertools import chain

from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.market.kraken.kraken_order_book import KrakenOrderBook


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

            trading_pairs: Dict[str, Any] = {pair: {f"{k}Asset": trading_pairs_data["result"][pair][k] for k in ["base", "quote"]}
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
            all_markets["lastPrice"] = all_markets.c.map(lambda x: x[0])
            quotes: Dict[str, List[str]] = {}
            quotes["usdt"] = ["ETH", "XBT", "DAI", "USDC"]
            quotes["usdt_r"] = ["ZUSD", "EUR", "CAD", "GBP"]
            quotes["xeth_r"] = ["ZJPY"]
            quotes["eth_r"] = ["CHF"]
            quotes_all: List[str] = chain([quotes[currency] for currency in quotes])
            price: Dict[str, float] = {}
            for quote in quotes["usdt"]:
                price[quote] = float(all_markets.loc[f"{quote}USDT"].lastPrice)
            for quote in quotes["usdt_r"]:
                price[quote] = 1./float(all_markets.loc[f"USDT{quote}"].lastPrice)
            for quote in quotes["eth_r"]:
                price[quote] = price["ETH"]/float(all_markets.loc[f"ETH{quote}"].lastPrice)
            for quote in quotes["xeth_r"]:
                price[quote] = price["ETH"]/float(all_markets.loc[f"XETH{quote}"].lastPrice)
            usd_volume: float = [
                (
                    quoteVolume * price[quote] if trading_pair[-3:] in quotes_all else
                    quoteVolume * price[quote] if trading_pair[-4:] in quotes_all else
                    quoteVolume
                )
                for trading_pair, quoteVolume in zip(all_markets.index,
                                                     all_markets.v.map(lambda x: x[1]).astype("float"))]
            all_markets.loc[:, "USDVolume"] = usd_volume
            all_markets.loc[:, "volume"] = all_markets.v.map(lambda x: x[1])

            return all_markets.sort_values("USDVolume", ascending=False)

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
        params: Dict[str, str] = {"count": str(limit), "pair": trading_pair} if limit != 0 else {"pair": trading_pair}
        async with client.get(SNAPSHOT_REST_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Kraken market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            response_json = await response.json()
            data: Dict[str, Any] = response_json["result"][trading_pair]
            data = {"trading_pair": trading_pair, **data}
            data["latest_update"] = max([*map(lambda x: x[2], data["bids"] + data["asks"])])

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
                    if msg != "{\"event\":\"heartbeat\"}":
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

                async with websockets.connect(stream_url) as ws:
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

                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        order_book_message: OrderBookMessage = KrakenOrderBook.diff_message_from_exchange(
                            msg, time.time())
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
                            snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
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
        market: pd.DataFrame = await self.get_active_exchange_markets()
        trading_pairs: List[str] = market[["base", "quote"]].agg("/".join, axis=1).tolist()
        stream_url: str = f"{DIFF_STREAM_URL}"

        ws_message_dict: Dict[str, Any] = {
                                        "event": "subscribe",
                                        "pair": trading_pairs,
                                        "subscription": {"name": subscription_type}
                                        }

        ws_message: str = ujson.dumps(ws_message_dict)

        return ws_message
