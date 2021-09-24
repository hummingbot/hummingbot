import aiohttp
import asyncio
import copy
import logging
import pandas as pd

from collections import defaultdict
from decimal import Decimal
from typing import (
    Dict,
    List,
    Optional, Any,
)

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils as bybit_utils
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS, \
    bybit_perpetual_utils
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_order_book import BybitPerpetualOrderBook
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_websocket_adaptor import \
    BybitPerpetualWebSocketAdaptor
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BybitPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _ORDER_BOOK_SNAPSHOT_DELAY = 60 * 60

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Dict[str, str]] = {}
    _last_traded_prices: Dict[str, Dict[str, float]] = defaultdict(dict)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 throttler: Optional[AsyncThrottler] = None,
                 trading_pairs: List[str] = None,
                 domain: Optional[str] = None,
                 session: Optional[aiohttp.ClientSession] = None):
        super().__init__(trading_pairs)
        self._throttler = throttler or self._get_throttler_instance(trading_pairs)
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._messages_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._session = session
        self._funding_info: Dict[str, FundingInfo] = {}

        self._funding_info_async_lock: asyncio.Lock = asyncio.Lock()

    @property
    def funding_info(self) -> Dict[str, FundingInfo]:
        return copy.deepcopy(self._funding_info)

    def is_funding_info_initialized(self) -> bool:
        return all(trading_pair in self._funding_info
                   for trading_pair in self._trading_pairs)

    async def _sleep(self, delay):
        """
        This function is added only to facilitate the creation of unit tests
        The intention is to mock this function if sleeps should be avoided, instead of mocking asyncio.sleep
        """
        await asyncio.sleep(delay)

    async def _get_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _create_websocket_connection(self, url: str) -> BybitPerpetualWebSocketAdaptor:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            session = await self._get_session()
            ws = await session.ws_connect(url)
            return BybitPerpetualWebSocketAdaptor(websocket=ws)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network(f"Unexpected error occurred during {CONSTANTS.EXCHANGE_NAME} WebSocket Connection "
                                  f"({ex})")
            raise

    @classmethod
    async def init_trading_pair_symbols(cls, domain: Optional[str] = None, throttler: Optional[AsyncThrottler] = None):
        """Initialize _trading_pair_symbol_map class variable
        """
        cls._trading_pair_symbol_map[domain] = {}

        endpoint = CONSTANTS.QUERY_SYMBOL_ENDPOINT
        api_path = bybit_perpetual_utils.rest_api_path_for_endpoint(endpoint=endpoint)
        endpoint_url = bybit_perpetual_utils.rest_api_url_for_endpoint(endpoint=api_path, domain=domain)
        limit_id = bybit_perpetual_utils.get_rest_api_limit_id_for_endpoint(endpoint)
        throttler = throttler or cls._get_throttler_instance()

        async with aiohttp.ClientSession() as client:
            async with throttler.execute_task(limit_id):
                async with client.get(endpoint_url, params={}) as response:
                    if response.status == 200:
                        resp_json: Dict[str, Any] = await response.json()

                        cls._trading_pair_symbol_map[domain] = {
                            instrument["name"]: f"{instrument['base_currency']}-{instrument['quote_currency']}"
                            for instrument in resp_json["result"]
                            if (instrument["status"] == "Trading"
                                and instrument["name"] == f"{instrument['base_currency']}{instrument['quote_currency']}"
                                and bybit_perpetual_utils.is_linear_perpetual(f"{instrument['base_currency']}-{instrument['quote_currency']}"))
                        }

    @classmethod
    async def trading_pair_symbol_map(cls, domain: Optional[str] = None):
        if domain not in cls._trading_pair_symbol_map or not cls._trading_pair_symbol_map[domain]:
            await cls.init_trading_pair_symbols(domain)

        return cls._trading_pair_symbol_map[domain]

    @classmethod
    async def get_last_traded_prices(
        cls, trading_pairs: List[str], domain: Optional[str] = None, throttler: Optional[AsyncThrottler] = None
    ) -> Dict[str, float]:
        if (domain in cls._last_traded_prices
                and all(trading_pair in cls._last_traded_prices[domain]
                        for trading_pair
                        in trading_pairs)):
            result = {trading_pair: cls._last_traded_prices[domain][trading_pair] for trading_pair in trading_pairs}
        else:
            result = await cls._get_last_traded_prices_from_exchange(trading_pairs, domain, throttler)
        return result

    @classmethod
    async def _get_last_traded_prices_from_exchange(
        cls, trading_pairs: List[str], domain: Optional[str] = None, throttler: Optional[AsyncThrottler] = None
    ):
        result = {}
        trading_pair_symbol_map = await cls.trading_pair_symbol_map(domain=domain)
        endpoint = CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT
        api_path = bybit_perpetual_utils.rest_api_path_for_endpoint(endpoint)
        endpoint_url = bybit_perpetual_utils.rest_api_url_for_endpoint(endpoint=api_path, domain=domain)
        limit_id = bybit_perpetual_utils.get_rest_api_limit_id_for_endpoint(endpoint)
        throttler = throttler or cls._get_throttler_instance(trading_pairs)
        async with aiohttp.ClientSession() as client:
            async with throttler.execute_task(limit_id):
                async with client.get(endpoint_url) as response:
                    if response.status == 200:
                        resp_json = await response.json()
                        if "result" in resp_json:
                            for token_pair_info in resp_json["result"]:
                                token_pair = trading_pair_symbol_map.get(token_pair_info["symbol"])
                                if token_pair is not None and token_pair in trading_pairs:
                                    result[token_pair] = float(token_pair_info["last_price"])
        return result

    @staticmethod
    async def fetch_trading_pairs(domain: Optional[str] = None) -> List[str]:
        symbols_map = await BybitPerpetualAPIOrderBookDataSource.trading_pair_symbol_map(domain=domain)
        return list(symbols_map.values())

    async def _get_order_book_data(self, trading_pair: str) -> Dict[str, any]:
        """Retrieves entire orderbook snapshot of the specified trading pair via the REST API.
        :param trading_pair: Trading pair of the particular orderbook.
        :return: Parsed API Response as a Json dictionary
        """
        symbol_map = await self.trading_pair_symbol_map(self._domain)
        symbols = [symbol for symbol, pair in symbol_map.items() if pair == trading_pair]

        if symbols:
            symbol = symbols[0]
        else:
            raise ValueError(f"There is no symbol mapping for trading pair {trading_pair}")

        params = {"symbol": symbol}

        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        api_path = bybit_perpetual_utils.rest_api_path_for_endpoint(endpoint, trading_pair)
        url = bybit_perpetual_utils.rest_api_url_for_endpoint(endpoint=api_path, domain=self._domain)
        limit_id = bybit_perpetual_utils.get_rest_api_limit_id_for_endpoint(endpoint)

        session = await self._get_session()
        async with self._throttler.execute_task(limit_id):
            async with session.get(url, params=params) as response:
                status = response.status
                if status != 200:
                    raise IOError(
                        f"Error fetching OrderBook for {trading_pair} at {url}. "
                        f"HTTP {status}. Response: {await response.json()}"
                    )

                response = await response.json()
                return response

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self._get_order_book_data(trading_pair)
        metadata = {
            "trading_pair": trading_pair,
            "data": snapshot["result"],
            "timestamp_e6": int(float(snapshot["time_now"]) * 1e6)
        }

        snapshot_msg = BybitPerpetualOrderBook.snapshot_message_from_exchange(
            msg=snapshot,
            timestamp=float(snapshot["time_now"]),
            metadata=metadata
        )
        order_book = self.order_book_create_function()

        bids, asks = snapshot_msg.bids, snapshot_msg.asks
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

        return order_book

    async def _get_funding_info_from_exchange(self, trading_pair: str) -> FundingInfo:
        symbol_map = await self.trading_pair_symbol_map(self._domain)
        symbols = [symbol for symbol, pair in symbol_map.items() if trading_pair == pair]

        if symbols:
            symbol = symbols[0]
        else:
            raise ValueError(f"There is no symbol mapping for trading pair {trading_pair}")

        params = {
            "symbol": symbol
        }
        funding_info = None
        endpoint = CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT
        api_path = bybit_perpetual_utils.rest_api_path_for_endpoint(endpoint, trading_pair)
        url = bybit_perpetual_utils.rest_api_url_for_endpoint(endpoint=api_path, domain=self._domain)
        limit_id = bybit_perpetual_utils.get_rest_api_limit_id_for_endpoint(endpoint)

        session = await self._get_session()
        async with session as client:
            async with self._throttler.execute_task(limit_id):
                response = await client.get(url=url, params=params)
                if response.status == 200:
                    resp_json = await response.json()

                    symbol_info: Dict[str, Any] = (
                        resp_json["result"][0]  # Endpoint returns a List even though 1 entry is returned
                    )
                    funding_info = FundingInfo(
                        trading_pair=trading_pair,
                        index_price=Decimal(str(symbol_info["index_price"])),
                        mark_price=Decimal(str(symbol_info["mark_price"])),
                        next_funding_utc_timestamp=int(pd.Timestamp(symbol_info["next_funding_time"]).timestamp()),
                        rate=Decimal(str(symbol_info["predicted_funding_rate"])),  # Note: no _e6 suffix from resp
                    )
        return funding_info

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Returns the FundingInfo of the specified trading pair. If it does not exist, it will query the REST API.
        """
        if trading_pair not in self._funding_info:
            self._funding_info[trading_pair] = await self._get_funding_info_from_exchange(trading_pair)
        return self._funding_info[trading_pair]

    async def _listen_for_subscriptions_on_url(self, url: str, trading_pairs: List[str]):
        """
        Subscribe to all required events and start the listening cycle.
        :param url: the wss url to connect to
        :param trading_pairs: the trading pairs for which the function should listen events
        """

        while True:
            try:
                ws_adaptor: BybitPerpetualWebSocketAdaptor = await self._create_websocket_connection(url)
                symbols_and_pairs_map = await self.trading_pair_symbol_map(self._domain)
                symbols = [symbol for symbol, pair in symbols_and_pairs_map.items() if pair in trading_pairs]

                await ws_adaptor.subscribe_to_order_book(symbols)
                await ws_adaptor.subscribe_to_trades(symbols)
                await ws_adaptor.subscribe_to_instruments_info(symbols)

                async for json_message in ws_adaptor.iter_messages():
                    if "success" in json_message:
                        if json_message["success"]:
                            self.logger().info(
                                f"Successful subscription to the topic {json_message['request']['args']} on {url}")
                        else:
                            self.logger().error(
                                "There was an error subscribing to the topic "
                                f"{json_message['request']['args']} ({json_message['ret_msg']}) on {url}")
                    else:
                        topic = json_message["topic"]
                        topic = ".".join(topic.split(".")[:-1])
                        await self._messages_queues[topic].put(json_message)

            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().network(
                    f"Unexpected error with WebSocket connection on {url} ({ex})",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                if ws_adaptor:
                    await ws_adaptor.close()
                await self._sleep(30.0)

    async def listen_for_subscriptions(self):
        """
        Subscribe to all required events and start the listening cycle.
        """
        tasks_future = None
        try:
            tasks = []
            linear_trading_pairs = []
            non_linear_trading_pairs = []
            for trading_pair in self._trading_pairs:
                if bybit_perpetual_utils.is_linear_perpetual(trading_pair):
                    linear_trading_pairs.append(trading_pair)
                else:
                    non_linear_trading_pairs.append(trading_pair)

            if linear_trading_pairs:
                tasks.append(self._listen_for_subscriptions_on_url(
                    url=bybit_perpetual_utils.wss_linear_public_url(self._domain),
                    trading_pairs=linear_trading_pairs))
            if non_linear_trading_pairs:
                tasks.append(self._listen_for_subscriptions_on_url(
                    url=bybit_perpetual_utils.wss_non_linear_public_url(self._domain),
                    trading_pairs=non_linear_trading_pairs))

            if tasks:
                tasks_future = asyncio.gather(*tasks)
                await tasks_future

        except asyncio.CancelledError:
            tasks_future and tasks_future.cancel()
            raise

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Process trade events received through the websocket channel
        """
        symbol_map = await self.trading_pair_symbol_map(self._domain)

        while True:
            try:
                trade_message = await self._messages_queues[CONSTANTS.WS_TRADES_TOPIC].get()
                for trade_entry in trade_message["data"]:
                    trade_msg: OrderBookMessage = BybitPerpetualOrderBook.trade_message_from_exchange(
                        msg=trade_entry,
                        timestamp=int(trade_entry["trade_time_ms"]) * 1e-3,
                        metadata={"trading_pair": symbol_map[trade_entry["symbol"]]})
                    output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unexpected error ({ex})", exc_info=True)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for order book diffs events received through the websocket channel
        """
        symbol_map = await self.trading_pair_symbol_map(self._domain)

        while True:
            try:
                order_book_message = await self._messages_queues[CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC].get()

                symbol = order_book_message["topic"].split(".")[-1]
                trading_pair = symbol_map[symbol]
                event_type = order_book_message["type"]

                if event_type == "snapshot":
                    snapshot_msg: OrderBookMessage = BybitPerpetualOrderBook.snapshot_message_from_exchange(
                        msg=order_book_message,
                        timestamp=int(order_book_message["timestamp_e6"]) * 1e-6,
                        metadata={"trading_pair": trading_pair})
                    output.put_nowait(snapshot_msg)

                if event_type == "delta":
                    diff_msg: OrderBookMessage = BybitPerpetualOrderBook.diff_message_from_exchange(
                        msg=order_book_message,
                        timestamp=int(order_book_message["timestamp_e6"]) * 1e-6,
                        metadata={"trading_pair": trading_pair})
                    output.put_nowait(diff_msg)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unexpected error ({ex})", exc_info=True)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Periodically polls for orderbook snapshots using the REST API.
        """
        await self._sleep(self._ORDER_BOOK_SNAPSHOT_DELAY)

        while True:
            await self._sleep(self._ORDER_BOOK_SNAPSHOT_DELAY)
            try:
                for trading_pair in self._trading_pairs:
                    response: Dict[str: Any] = await self._get_order_book_data(trading_pair)
                    metadata = {
                        "trading_pair": trading_pair,
                        "data": response["result"],
                        "timestamp_e6": int(float(response["time_now"]) * 1e6)
                    }
                    snapshot_message = BybitPerpetualOrderBook.snapshot_message_from_exchange(
                        msg=response,
                        timestamp=float(response["time_now"]),
                        metadata=metadata
                    )
                    output.put_nowait(snapshot_message)
                await self._sleep(self._ORDER_BOOK_SNAPSHOT_DELAY)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error("Unexpected error occurred listening for orderbook snapshots."
                                    f" Retrying in 5 secs. ({ex})",
                                    exc_info=True)
                await self._sleep(5.0)

    async def listen_for_instruments_info(self):
        """
        Listen for instruments information events received through the websocket channel to update last traded price
        """
        symbol_map = await self.trading_pair_symbol_map(self._domain)

        while True:
            try:
                instrument_info_message = await self._messages_queues[CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC].get()

                symbol = instrument_info_message["topic"].split(".")[-1]
                trading_pair = symbol_map[symbol]
                event_type = instrument_info_message["type"]

                entries = []
                if event_type == "snapshot":
                    entries.append(instrument_info_message["data"])
                if event_type == "delta":
                    entries.extend(instrument_info_message["data"]["update"])

                for entry in entries:
                    if "last_price_e4" in entry:
                        self._last_traded_prices[self._domain][trading_pair] = int(entry["last_price_e4"]) * 1e-4

                    # Updates funding info for the relevant domain and trading_pair
                    async with self._funding_info_async_lock:
                        if event_type == "snapshot":
                            # Snapshot messages have all the data fields required to construct a new FundingInfo.
                            current_funding_info: FundingInfo = FundingInfo(
                                trading_pair=trading_pair,
                                index_price=Decimal(str(entry["index_price"])),
                                mark_price=Decimal(str(entry["mark_price"])),
                                next_funding_utc_timestamp=int(pd.Timestamp(
                                    str(entry["next_funding_time"]),
                                    tz="UTC").timestamp()),
                                rate=Decimal(str(entry["predicted_funding_rate_e6"])) * Decimal(1e-6))
                        else:
                            # Delta messages do not necessarily have all the data required.
                            current_funding_info: FundingInfo = await self.get_funding_info(trading_pair)
                            if "index_price" in entry:
                                current_funding_info.index_price = Decimal(str(entry["index_price"]))
                            if "mark_price" in entry:
                                current_funding_info.mark_price = Decimal(str(entry["mark_price"]))
                            if "next_funding_time" in entry:
                                current_funding_info.next_funding_utc_timestamp = int(
                                    pd.Timestamp(str(entry["next_funding_time"]), tz="UTC").timestamp())
                            if "predicted_funding_rate_e6" in entry:
                                current_funding_info.rate = (
                                    Decimal(str(entry["predicted_funding_rate_e6"])) * Decimal(1e-6)
                                )
                        self._funding_info[trading_pair] = current_funding_info

            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unexpected error ({ex})", exc_info=True)

    @classmethod
    def _get_throttler_instance(cls, trading_pairs: List[str] = None) -> AsyncThrottler:
        rate_limits = bybit_utils.build_rate_limits(trading_pairs)
        throttler = AsyncThrottler(rate_limits)
        return throttler
