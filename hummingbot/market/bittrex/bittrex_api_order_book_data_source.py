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

BITTREX_REST_URL = "https://api.bittrex.com/v3"
BITTREX_EXCHANGE_INFO_PATH = "/markets"
BITTREX_MARKET_SUMMARY_PATH = "/markets/summaries"
BITTREX_TICKER_PATH = "/markets/tickers"
BITTREX_WS_FEED = "https://socket.bittrex.com/signalr"

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
        Returned data frame should have symbol as index and include USDVolume, baseAsset and quoteAsset
        """
        market_path_url = f"{BITTREX_REST_URL}{BITTREX_EXCHANGE_INFO_PATH}"
        summary_path_url = f"{BITTREX_REST_URL}{BITTREX_MARKET_SUMMARY_PATH}"
        ticker_path_url = f"{BITTREX_REST_URL}{BITTREX_TICKER_PATH}"

        async with aiohttp.ClientSession() as client:

            market_response, ticker_response, summary_response = await asyncio.gather(
                client.get(market_path_url), client.get(ticker_path_url), client.get(summary_path_url)
            )

            market_response: aiohttp.ClientResponse = market_response
            ticker_response: aiohttp.ClientResponse = ticker_response
            summary_response: aiohttp.ClientResponse = summary_response

            if market_response.status != 200:
                raise IOError(
                    f"Error fetching active Bittrex markets information. " f"HTTP status is {market_response.status}."
                )
            if ticker_response.status != 200:
                raise IOError(
                    f"Error fetching active Bittrex market tickers. " f"HTTP status is {ticker_response.status}."
                )
            if summary_response.status != 200:
                raise IOError(
                    f"Error fetching active Bittrex market summaries. " f"HTTP status is {summary_response.status}."
                )

            market_data = await market_response.json()
            ticker_data = await ticker_response.json()
            summary_data = await summary_response.json()

            ticker_data: Dict[str, Any] = {item["symbol"]: item for item in ticker_data}
            summary_data: Dict[str, Any] = {item["symbol"]: item for item in summary_data}

            market_data: List[Dict[str, Any]] = [
                {**item, **ticker_data[item["symbol"]], **summary_data[item["symbol"]]}
                for item in market_data
                if item["symbol"] in ticker_data and item["symbol"] in summary_data
            ]

            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="symbol")
            all_markets.rename(
                {"baseCurrencySymbol": "baseAsset", "quoteCurrencySymbol": "quoteAsset"}, axis="columns", inplace=True
            )

            btc_usd_price: float = float(all_markets.loc["BTC-USD"].lastTradeRate)
            eth_usd_price: float = float(all_markets.loc["ETH-USD"].lastTradeRate)

            usd_volume: List[float] = [
                (
                    volume * quote_price if symbol.endswith(("USD", "USDT")) else
                    volume * quote_price * btc_usd_price if symbol.endswith("BTC") else
                    volume * quote_price * eth_usd_price if symbol.endswith("ETH") else
                    volume
                )
                for symbol, volume, quote_price in zip(all_markets.index,
                                                       all_markets.volume.astype("float"),
                                                       all_markets.lastTradeRate.astype("float"))
            ]
            old_symbols: List[str] = [
                (
                    f"{quoteAsset}-{baseAsset}"
                )
                for baseAsset, quoteAsset in zip(all_markets.baseAsset, all_markets.quoteAsset)
            ]

            all_markets.loc[:, "USDVolume"] = usd_volume
            all_markets.loc[:, "old_symbol"] = old_symbols
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

            output: Dict[str, Any] = {"nonce": None, "results": {}}
            msg: Dict[str, Any] = ujson.loads(msg)

            if _is_snapshot(msg):
                output["results"] = _decode_message(msg["R"])
                # TODO: Refactor accordingly when V3 WebSocket details are out
                output["results"].update({
                    "M": f"{output['results']['M'].split('-')[1]}-{output['results']['M'].split('-')[0]}"
                })
                output["nonce"] = output["results"]["N"]

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
                symbol: str = decoded["results"].get("M")
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
            # TODO: Refactor accordingly when V3 WebSocket is out
            # trading_pair needs to be converted back to V1.1 convention from "Base-Quote" -> "Quote-Base"
            temp_trading_pair = f"{trading_pair.split('-')[1]}-{trading_pair.split('-')[0]}"
            try:
                snapshot: Dict[str, any] = await self.get_snapshot(temp_trading_pair)
                snapshot_timestamp: float = snapshot["nonce"]
                snapshot_msg: OrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                    snapshot["results"], snapshot_timestamp, metadata={"symbol": trading_pair}
                )
                order_book: BittrexOrderBook = BittrexOrderBook()
                active_order_tracker: BittrexActiveOrderTracker = BittrexActiveOrderTracker()

                bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
                retval[trading_pair] = BittrexOrderBookTrackerEntry(
                    trading_pair, snapshot_timestamp, order_book, active_order_tracker
                )
                self.logger().info(
                    f"Initialized order book for {trading_pair}. " f"{index + 1}/{number_of_pairs} completed."
                )
                await asyncio.sleep(0.6)
            except IOError:
                self.logger().network(
                    f"Max retries met fetching snapshot for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg=f"Error getting snapshot fro {trading_pair}. Check network connection.",
                )
            except Exception:
                self.logger().error(f"Error initiailizing order book for {trading_pair}. ", exc_info=True)
                await asyncio.sleep(5.0)
        return retval

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Trade messages are received from the order book web socket
        pass

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

        output: Dict[str, Any] = {"nonce": None, "type": None, "results": {}}
        msg: Dict[str, Any] = ujson.loads(msg)

        if _is_snapshot(msg):
            output["results"] = _decode_message(msg["R"])

            # TODO: Refactor accordingly when V3 WebSocket details are out
            output["results"].update({
                "M": f"{output['results']['M'].split('-')[1]}-{output['results']['M'].split('-')[0]}"
            })

            output["type"] = "snapshot"
            output["nonce"] = output["results"]["N"]

        elif _is_market_delta(msg):
            output["results"] = _decode_message(msg["M"][0]["A"][0])
            # TODO: Refactor accordingly when V3 WebSocket details are out
            output["results"].update({
                "M": f"{output['results']['M'].split('-')[1]}-{output['results']['M'].split('-')[0]}"
            })
            output["type"] = "update"
            output["nonce"] = output["results"]["N"]

        return output

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            connection: Optional[signalr_aio.Connection] = None
            try:
                connection = signalr_aio.Connection(BITTREX_WS_FEED, session=None)
                hub = connection.register_hub("c2")
                trading_pairs = await self.get_trading_pairs()
                for trading_pair in trading_pairs:
                    # TODO: Refactor accordingly when V3 WebSocket is out
                    # trading_pair needs to be converted back to WebSocket V1.1 convention from "Base-Quote" -> "Quote-Base"
                    trading_pair = f"{trading_pair.split('-')[1]}-{trading_pair.split('-')[0]}"

                    self.logger().info(f"Subscribed to {trading_pair}")
                    hub.server.invoke("queryExchangeState", trading_pair)

                connection.start()

                async for raw_message in self._socket_stream(connection):
                    decoded: Dict[str, Any] = await self._transform_raw_message(raw_message)
                    symbol: str = decoded["results"].get("M")
                    if not symbol:  # Ignores initial websocket response messages
                        continue

                    # TODO: Refactor accordingly when V3 WebSocket is out
                    # symbol needs to be converted back to V3 convention from "Quote-Base" -> "Base-Quote"
                    # symbol = f"{symbol.split('-')[1]}-{symbol.split('-')[0]}"

                    # Only processes snapshot messages
                    if decoded["type"] == "snapshot":
                        snapshot: Dict[str, any] = decoded
                        snapshot_timestamp = snapshot["nonce"]
                        snapshot_msg: OrderBookMessage = self.order_book_class.snapshot_message_from_exchange(
                            snapshot["results"], snapshot_timestamp, metadata={"product_id": symbol}
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
                    # TODO: Refactor accordingly when V3 WebSocket is out
                    # trading_pair needs to be converted back to V1.1 convention from "Base-Quote" -> "Quote-Base"
                    trading_pair = f"{trading_pair.split('-')[1]}-{trading_pair.split('-')[0]}"
                    self.logger().info(f"Subscribed to {trading_pair} Deltas")
                    hub.server.invoke("SubscribeToExchangeDeltas", trading_pair)

                connection.start()

                async for raw_message in self._socket_stream(connection):
                    decoded: Dict[str, Any] = await self._transform_raw_message(raw_message)
                    symbol: str = decoded["results"].get("M")

                    if not symbol:  # Ignores initial websocket response messages
                        continue

                    # Only processes snapshot messages
                    if decoded["type"] == "update":
                        diff: Dict[str, any] = decoded
                        diff_timestamp = diff["nonce"]
                        diff_msg: OrderBookMessage = self.order_book_class.diff_message_from_exchange(
                            diff["results"], diff_timestamp, metadata={"product_id": symbol}
                        )
                        output.put_nowait(diff_msg)

                # Waits for delta amount of time before getting new snapshots
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await asyncio.sleep(delta)

            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
            finally:
                connection.close()
