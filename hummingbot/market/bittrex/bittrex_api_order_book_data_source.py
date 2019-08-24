#!/usr/bin/env python
import asyncio
import logging
import time
from base64 import b64decode
from typing import Optional, List, Dict, AsyncIterable, Any
from zlib import decompress, MAX_WBITS

import aiohttp
import pandas as pd
import signalr_aio
import ujson
from async_timeout import timeout

from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry, BittrexOrderBookTrackerEntry
from hummingbot.core.utils import async_ttl_cache
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bittrex.bittrex_active_order_tracker import BittrexActiveOrderTracker
from hummingbot.market.bittrex.bittrex_order_book import BittrexOrderBook

EXCHANGE_NAME = "Bittrex"

BITTREX_REST_URL = "https://api.bittrex.com/api/v1.1"
BITTREX_EXCHANGE_INFO_URL = "https://api.bittrex.com/api/v1.1/public/getmarkets"
BITTREX_MARKET_SUMMARY_URL = "https://api.bittrex.com/api/v1.1/public/getmarketsummaries"
BITTREX_WS_FEED="https://socket.bittrex.com/signalr"
SNAPSHOT_REST_URL = "https://api.bittrex.com/api/v1.1/public/getorderbook"

MAX_RETRIES = 20
MESSAGE_TIMEOUT = 30.0
NaN = float("nan")


class BittrexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _bittrexaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bittrexaobds_logger is None:
            cls._bittrexaobds_logger = logging.getLogger(__name__)
        return cls._bittrexaobds_logger

    def __init__(self, symbols: Optional[List[str]] = None):
        super().__init__()
        self._symbols: Optional[List[str]] = symbols

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have symbol as index and include usd volume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:

            market_response, summary_response = await asyncio.gather(
                client.get(BITTREX_EXCHANGE_INFO_URL),
                client.get(BITTREX_MARKET_SUMMARY_URL)
            )

            market_response: aiohttp.ClientResponse = market_response
            summary_response: aiohttp.ClientResponse = summary_response

            if market_response.status != 200:
                raise IOError(f"Error fetching active Bibttrex markets information. "
                              f"HTTP status is {market_response.status}.")
            if summary_response.status != 200:
                raise IOError(f"Error fetching active Bibttrex market summaries. "
                              f"HTTP status is {summary_response.status}.")

            market_data = (await market_response.json())["result"]
            summary_data = (await summary_response.json())["result"]

            summary_data: Dict[str, any] = {item["MarketName"]: {k: item[k] for k in ["Volume", "Last"]}
                                            for item in summary_data
                                            }

            market_data: List[Dict[str, any]] = [{**item, **summary_data[item["MarketName"]]}
                                                 for item in market_data
                                                 if item["MarketName"] in summary_data]

            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="MarketName")
            # Bittrex trading pair symbols(BTC-LTC) differs in naming convention
            all_markets.rename({"BaseCurrency": "quoteAsset", "MarketCurrency": "baseAsset"},
                               axis="columns",
                               inplace=True)

            btc_price: float = float(all_markets.loc["USDT-BTC"].Last)
            eth_price: float = float(all_markets.loc["USDT-ETH"].Last)

            usd_volume: float = [
                (
                    Volume * btc_price if MarketName.startswith("BTC") else
                    Volume * eth_price if MarketName.startswith("ETH") else
                    Volume
                )
                for MarketName, Volume in zip(all_markets.index,
                                               all_markets.Volume.astype("float"))]

            all_markets.loc[:, "USDVolume"] = usd_volume
            return all_markets.sort_values("USDVolume", ascending=False)

    @property
    def order_book_class(self) -> BittrexOrderBook:
        return BittrexOrderBook

    async def get_trading_pairs(self) -> List[str]:
        if not self._symbols:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._symbols = active_markets.index.tolist()
            except Exception:
                self._symbols = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._symbols

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, any]:
        params: Dict = {"type": str("both"), "market": trading_pair}
        async with client.get(SNAPSHOT_REST_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching {EXCHANGE_NAME} market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, any] = (await response.json())["result"]

            # Need to add the symbol into the snapshot message for the Kafka message queue.
            # Because otherwise, there'd be no way for the receiver to know which market the
            # snapshot belongs to.

            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the current active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, OrderBookTrackerEntry] = {}

            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"symbol": trading_pair}
                    )
                    order_book: BittrexOrderBook = BittrexOrderBook()
                    active_order_tracker: BittrexActiveOrderTracker = BittrexActiveOrderTracker()
                    print(snapshot_msg)
                    bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
                    retval[trading_pair] = BittrexOrderBookTrackerEntry(
                        trading_pair,
                        snapshot_timestamp,
                        order_book,
                        active_order_tracker=None
                    )
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")
                    # Bittrex Call Limits on all endpoints are limited at 60 API calls per minute.
                    # For more info, https://bittrex.github.io/api/v1-1#topic-Best-Practices
                    await asyncio.sleep(0.4)
                except:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5.0)
            return retval

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"product_id": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            # Sleep to prevent exceeding of Bittrex API Call limits(60/min)
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().network(
                                f"Unexpected error with WebSocket connection.",
                                exc_info=True,
                                app_warning_msg=f"Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                                f"Check network connection."
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


    async def _get_signalir_connection(self) -> signalr_aio.Connection:
        return signalr_aio.Connection(BITTREX_WS_FEED, session=None)

    async def _inner_messages(self, conn: signalr_aio.Connection) -> AsyncIterable[str]:
        try:
            while True:
                async with timeout(MESSAGE_TIMEOUT):
                    yield await conn.msg_queue.get()
        except asyncio.TimeoutError:
            self.logger().warning("Message recv() timed out. Going to reconnect...")
            return

    async def _transform_raw_message(self, msg, ts) -> Dict[str, Any]:
        def _decode_message(raw_message: bytes) -> Dict[str, Any]:
            try:
                decoded_msg: bytes = decompress(b64decode(raw_message, validate=True), -MAX_WBITS)
            except SyntaxError:
                decoded_msg: bytes = decompress(b64decode(raw_message, validate=True))
            except Exception:
                return {}
            decoded: Dict[str, Any] = ujson.load(decoded_msg.decode("utf-8")) or {}
            return decoded

        def _is_snapshot(msg) -> bool:
            return type(msg.get("R", False)) is not bool

        def _is_market_delta(msg) -> bool:
            return len(msg.get("M", [])) > 0 and type(msg["M"][0]) == dict and msg["M"][0].get("M", None) == "uE"

        output: Dict[str, Any] = {"E": ts, "type": None, "tick": {}}
        msg: Dict[str, Any] = ujson.loads(msg)

        if _is_snapshot(msg):
            output["tick"] = _decode_message(msg["R"])
            output["type"] = "snapshot"

        elif _is_market_delta(msg):
            output["tick"] = _decode_message(msg["M"][0]["A"][0])
            output["type"] = "update"

        return output

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()

                connection = await self._get_signalir_connection()

                hub: signalr_aio.hubs.Hub = connection.register_hub("c2")

                for symbol in trading_pairs:
                    self.logger().info(f"Subscribed to {symbol}")
                    hub.server.invoke('SubscribeToExchangeDeltas', symbol)

                # Register callbacks for all markets
                # await self._register_callbacks(trading_pairs, hub)

                connection.start()
                async for raw_message in self._inner_messages(connection):
                    received_timestamp: int = int(time.time() * 1e3)
                    msg: Dict[str, Any] = await self._transform_raw_message(raw_message, received_timestamp)
                    order_book_message: BittrexOrderBook = self.order_book_class.diff_message_from_exchange(
                        msg,
                        time.time()
                    )
                    output.put_nowait(order_book_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    f"Check network connection."
                )
                await asyncio.sleep(30.0)


