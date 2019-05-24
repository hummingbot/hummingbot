#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import pandas as pd
from typing import (
    AsyncIterable,
    Dict,
    List,
    Optional
)
import re
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.utils import async_ttl_cache
from hummingbot.market.ddex.ddex_active_order_tracker import DDEXActiveOrderTracker
from hummingbot.market.ddex.ddex_order_book import DDEXOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_entry import (
    DDEXOrderBookTrackerEntry,
    OrderBookTrackerEntry
)
from hummingbot.core.data_type.order_book_message import DDEXOrderBookMessage

TRADING_PAIR_FILTER = re.compile(r"(TUSD|WETH|DAI)$")

REST_URL = "https://api.ddex.io/v3"
WS_URL = "wss://ws.ddex.io/v3"
TICKERS_URL = f"{REST_URL}/markets/tickers"
SNAPSHOT_URL = f"{REST_URL}/markets"
MARKETS_URL = f"{REST_URL}/markets"


class DDEXAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _raobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._raobds_logger is None:
            cls._raobds_logger = logging.getLogger(__name__)
        return cls._raobds_logger

    def __init__(self, symbols: Optional[List[str]] = None):
        super().__init__()
        self._symbols: Optional[List[str]] = symbols
        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have symbol as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:
            market_response, ticker_response = await asyncio.gather(
                client.get(MARKETS_URL),
                client.get(TICKERS_URL)
            )
            market_response: aiohttp.ClientResponse = market_response
            ticker_response: aiohttp.ClientResponse = ticker_response

            if market_response.status != 200:
                raise IOError(f"Error fetching active DDEX markets. HTTP status is {market_response.status}.")
            if ticker_response.status != 200:
                raise IOError(f"Error fetching active DDEX Ticker. HTTP status is {ticker_response.status}.")

            ticker_data = await ticker_response.json()
            market_data = await market_response.json()

            attr_name_map = {"baseToken": "baseAsset", "quoteToken": "quoteAsset"}

            market_data: Dict[str, any] = {
                item["id"]: {attr_name_map[k]: item[k] for k in ["baseToken", "quoteToken"]}
                for item in market_data["data"]["markets"]}

            ticker_data: List[Dict[str, any]] = [{**ticker_item, **market_data[ticker_item["marketId"]]}
                                                 for ticker_item in ticker_data["data"]["tickers"]
                                                 if ticker_item["marketId"] in market_data]

            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=ticker_data,
                                                                  index="marketId")

            dai_to_eth_price: float = float(all_markets.loc["DAI-WETH"].price)
            weth_to_usd_price: float = float(all_markets.loc["WETH-TUSD"].price)
            usd_volume: float = [
                (
                    quoteVolume * dai_to_eth_price * weth_to_usd_price if symbol.endswith("DAI") else
                    quoteVolume * weth_to_usd_price if symbol.endswith("WETH") else
                    quoteVolume
                )
                for symbol, quoteVolume in zip(all_markets.index,
                                               all_markets.volume.astype("float"))]
            all_markets["USDVolume"] = usd_volume
            return all_markets.sort_values("USDVolume", ascending=False)

    @property
    def order_book_class(self) -> DDEXOrderBook:
        return DDEXOrderBook

    async def get_trading_pairs(self) -> List[str]:
        if self._symbols is None:
            active_markets: pd.DataFrame = await self.get_active_exchange_markets()
            trading_pairs: List[str] = active_markets.index.tolist()
            self._symbols = trading_pairs
        else:
            trading_pairs: List[str] = self._symbols
        return trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str, level: int = 3) -> Dict[str, any]:
            params: Dict = {"level": level}
            retry: int = 3
            while retry > 0:
                try:
                    async with client.get(f"{REST_URL}/markets/{trading_pair}/orderbook", params=params) as response:
                        response: aiohttp.ClientResponse = response
                        if response.status != 200:
                            raise IOError(f"Error fetching DDex market snapshot for {trading_pair}. "
                                          f"HTTP status is {response.status}.")
                        data: Dict[str, any] = await response.json()
                        return data
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. Retrying {retry} more times.",
                                        exc_info=True)
                    await asyncio.sleep(10)
                    retry -= 1
                    if retry == 0:
                        raise

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, DDEXOrderBookTrackerEntry] = {}
            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair, 3)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: DDEXOrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        {"marketId": trading_pair}
                    )

                    ddex_order_book: DDEXOrderBook = DDEXOrderBook()
                    ddex_active_order_tracker: DDEXActiveOrderTracker = DDEXActiveOrderTracker()
                    bids, asks = ddex_active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    ddex_order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[trading_pair] = DDEXOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        ddex_order_book,
                        ddex_active_order_tracker
                    )

                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")
                    await asyncio.sleep(1.3)

                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair} in get_tracking_pairs.",
                                        exc_info=True)
                    await asyncio.sleep(5)

            self._get_tracking_pair_done_event.set()
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

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    request: Dict[str, any] = {
                        "type": "subscribe",
                        "channels": [{
                            "name": "full",
                            "marketIds": trading_pairs
                        }]
                    }
                    await ws.send(ujson.dumps(request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        # only process receive and done diff messages from DDEX
                        if msg["type"] == "receive" or msg["type"] == "done":
                            diff_msg: DDEXOrderBookMessage = self.order_book_class.diff_message_from_exchange(msg)
                            output.put_nowait(diff_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        await self._get_tracking_pair_done_event.wait()
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: DDEXOrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                {"marketId": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair} at {snapshot_timestamp}")
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
