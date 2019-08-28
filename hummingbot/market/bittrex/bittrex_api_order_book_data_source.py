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
BITTREX_WS_FEED = "https://socket.bittrex.com/signalr"
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
                client.get(BITTREX_EXCHANGE_INFO_URL), client.get(BITTREX_MARKET_SUMMARY_URL)
            )

            market_response: aiohttp.ClientResponse = market_response
            summary_response: aiohttp.ClientResponse = summary_response

            if market_response.status != 200:
                raise IOError(
                    f"Error fetching active Bibttrex markets information. " f"HTTP status is {market_response.status}."
                )
            if summary_response.status != 200:
                raise IOError(
                    f"Error fetching active Bibttrex market summaries. " f"HTTP status is {summary_response.status}."
                )

            market_data = (await market_response.json())["result"]
            summary_data = (await summary_response.json())["result"]

            summary_data: Dict[str, any] = {
                item["MarketName"]: {k: item[k] for k in ["Volume", "Last"]} for item in summary_data
            }

            market_data: List[Dict[str, any]] = [
                {**item, **summary_data[item["MarketName"]]}
                for item in market_data
                if item["MarketName"] in summary_data
            ]

            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="MarketName")
            # Bittrex trading pair symbols(BTC-LTC) differs in naming convention
            all_markets.rename(
                {"BaseCurrency": "quoteAsset", "MarketCurrency": "baseAsset"}, axis="columns", inplace=True
            )

            btc_price: float = float(all_markets.loc["USDT-BTC"].Last)
            eth_price: float = float(all_markets.loc["USDT-ETH"].Last)

            usd_volume: float = [
                (
                    Volume * btc_price
                    if MarketName.startswith("BTC")
                    else Volume * eth_price
                    if MarketName.startswith("ETH")
                    else Volume
                )
                for MarketName, Volume in zip(all_markets.index, all_markets.Volume.astype("float"))
            ]

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
                    app_warning_msg=f"Error getting active exchange information. Check network connection.",
                )
        return self._symbols

    @staticmethod
    async def get_snapshot(trading_pair: str) -> Dict[str, any]:
        async def _get_raw_message(conn: signalr_aio.Connection) -> AsyncIterable[str]:
            try:
                async with timeout(MESSAGE_TIMEOUT):
                    yield await conn.msg_queue.get()
            except asyncio.TimeoutError:
                return

        async def _transform_raw_message(msg) -> Dict[str, Any]:
            def _decode_message(raw_message: bytes) -> Dict[str, Any]:
                try:
                    decoded_msg: bytes = decompress(b64decode(raw_message, validate=True), -MAX_WBITS)
                except SyntaxError:
                    decoded_msg: bytes = decompress(b64decode(raw_message, validate=True))
                except Exception:
                    return {}

                return ujson.loads(decoded_msg.decode())

            def _is_snapshot(msg) -> bool:
                return type(msg.get("R", False)) is not bool

            output: Dict[str, Any] = {"nonce": None, "tick": {}}
            msg: Dict[str, Any] = ujson.loads(msg)

            if _is_snapshot(msg):
                output["tick"] = _decode_message(msg["R"])
                output["nonce"] = output["tick"]["N"]

            return output

        # Creates a new connection to obtain a single snapshot of the trading_pair
        connection: signalr_aio.Connection = signalr_aio.Connection(BITTREX_WS_FEED, session=None)
        hub: signalr_aio.hubs.Hub = connection.register_hub("c2")
        hub.server.invoke("queryExchangeState", trading_pair)
        connection.start()

        # Attempts to retrieve a snapshot a minimum of 20 times
        get_snapshot_attempts = 0
        while get_snapshot_attempts < MAX_RETRIES:
            get_snapshot_attempts += 1
            async for raw_message in _get_raw_message(connection):
                decoded: Dict[str, any] = await _transform_raw_message(raw_message)
                symbol: str = decoded["tick"].get("M")
                if not symbol:  # Re-attempt to retrieve snapshot from stream
                    continue

                connection.close()
                return decoded
        raise IOError

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the current active markets
        trading_pairs: List[str] = await self.get_trading_pairs()
        retval: Dict[str, OrderBookTrackerEntry] = {}

        number_of_pairs: int = len(trading_pairs)
        for index, trading_pair in enumerate(trading_pairs):
            try:
                snapshot: Dict[str, any] = await self.get_snapshot(trading_pair)
                snapshot_timestamp: float = snapshot["nonce"]
                snapshot_msg: OrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                    snapshot["tick"], snapshot_timestamp, metadata={"symbol": trading_pair}
                )
                order_book: BittrexOrderBook = BittrexOrderBook()
                active_order_tracker: BittrexActiveOrderTracker = BittrexActiveOrderTracker()

                bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
                retval[trading_pair] = BittrexOrderBookTrackerEntry(
                    trading_pair, snapshot_timestamp, order_book, active_order_tracker=None
                )
                self.logger().info(
                    f"Initialized order book for {trading_pair}. " f"{index + 1}/{number_of_pairs} completed."
                )
            except IOError:
                self.logger().error(f"Max retries met fetching snapshot for {trading_pair} on Bittrex.")
            except Exception:
                self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                await asyncio.sleep(5.0)
        return retval

    async def _socket_stream(self, conn: signalr_aio.Connection) -> AsyncIterable[str]:
        try:
            while True:
                async with timeout(MESSAGE_TIMEOUT):
                    yield await conn.msg_queue.get()
        except asyncio.TimeoutError:
            self.logger().warning("Message recv() timed out. Going to reconnect...")
            return

    async def _transform_raw_message(self, msg) -> Dict[str, Any]:
        def _decode_message(raw_message: bytes) -> Dict[str, Any]:
            try:
                decoded_msg: bytes = decompress(b64decode(raw_message, validate=True), -MAX_WBITS)
            except SyntaxError:
                decoded_msg: bytes = decompress(b64decode(raw_message, validate=True))
            except Exception:
                return {}

            return ujson.loads(decoded_msg.decode())

        def _is_snapshot(msg) -> bool:
            return type(msg.get("R", False)) is not bool

        def _is_market_delta(msg) -> bool:
            return len(msg.get("M", [])) > 0 and type(msg["M"][0]) == dict and msg["M"][0].get("M", None) == "uE"

        output: Dict[str, Any] = {"nonce": None, "type": None, "tick": {}}
        msg: Dict[str, Any] = ujson.loads(msg)

        if _is_snapshot(msg):
            output["tick"] = _decode_message(msg["R"])
            output["type"] = "snapshot"
            output["nonce"] = output["tick"]["N"]

        elif _is_market_delta(msg):
            output["tick"] = _decode_message(msg["M"][0]["A"][0])
            output["type"] = "update"
            output["nonce"] = output["tick"]["N"]

        return output

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            connection: Optional[signalr_aio.Connection] = None
            try:
                connection = signalr_aio.Connection(BITTREX_WS_FEED, session=None)
                hub = connection.register_hub("c2")
                trading_pairs = await self.get_trading_pairs()
                for trading_pair in trading_pairs:
                    self.logger().info(f"Subscribed to {trading_pair}")
                    hub.server.invoke("queryExchangeState", trading_pair)

                connection.start()

                async for raw_message in self._socket_stream(connection):
                    decoded: Dict[str, Any] = await self._transform_raw_message(raw_message)
                    symbol: str = decoded["tick"].get("M")
                    if not symbol:  # Ignores initial websocket response messages
                        continue

                    # Only processes snapshot messages
                    if decoded["type"] == "snapshot":
                        snapshot: Dict[str, any] = decoded
                        snapshot_timestamp = snapshot["nonce"]
                        snapshot_msg: OrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                            snapshot, snapshot_timestamp, metadata={"product_id": symbol}
                        )
                        output.put_nowait(snapshot_msg)

                # Waits for delta amount of time before getting new snapshots
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await asyncio.sleep(delta)

            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
            finally:
                connection.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            connection: Optional[signalr_aio.Connection] = None
            try:
                connection = signalr_aio.Connection(BITTREX_WS_FEED, session=None)
                hub = connection.register_hub("c2")
                trading_pairs = await self.get_trading_pairs()
                for trading_pair in trading_pairs:
                    self.logger().info(f"Subscribed to {trading_pair} Deltas")
                    hub.server.invoke("SubscribeToExchangeDeltas", trading_pair)

                connection.start()

                async for raw_message in self._socket_stream(connection):
                    decoded: Dict[str, Any] = await self._transform_raw_message(raw_message)
                    symbol: str = decoded["tick"].get("M")
                    if not symbol:  # Ignores initial websocket response messages
                        continue

                    # Only processes snapshot messages
                    if decoded["type"] == "update":
                        snapshot: Dict[str, any] = decoded
                        snapshot_timestamp = snapshot["nonce"]
                        snapshot_msg: OrderBookMessage = self.order_book_class.diff_message_from_exchange(
                            snapshot, snapshot_timestamp, metadata={"product_id": symbol}
                        )
                        output.put_nowait(snapshot_msg)

                # Waits for delta amount of time before getting new snapshots
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await asyncio.sleep(delta)

            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
            finally:
                connection.close()
