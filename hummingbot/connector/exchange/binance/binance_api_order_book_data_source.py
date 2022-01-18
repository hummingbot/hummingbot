import asyncio
import logging
import time

from collections import defaultdict
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
)

from bidict import bidict

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
from hummingbot.connector.exchange.binance import binance_utils
from hummingbot.connector.exchange.binance.binance_order_book import BinanceOrderBook
from hummingbot.connector.utils import build_api_factory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTRequest,
    RESTResponse,
    WSRequest,
)
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BinanceAPIOrderBookDataSource(OrderBookTrackerDataSource):

    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(self,
                 trading_pairs: List[str],
                 domain="com",
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory()
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    async def get_last_traded_prices(cls,
                                     trading_pairs: List[str],
                                     domain: str = "com",
                                     api_factory: Optional[WebAssistantsFactory] = None,
                                     throttler: Optional[AsyncThrottler] = None) -> Dict[str, float]:
        """
        Return a dictionary the trading_pair as key and the current price as value for each trading pair passed as
        parameter
        :param trading_pairs: list of trading pairs to get the prices for
        :param domain: which Binance domain we are connecting to (the default value is 'com')
        :param api_factory: the instance of the web assistant factory to be used when doing requests to the server.
        If no instance is provided then a new one will be created.
        :param throttler: the instance of the throttler to use to limit request to the server. If it is not specified
        the function will create a new one.
        :return: Dictionary of associations between token pair and its latest price
        """
        local_api_factory = api_factory or build_api_factory()
        rest_assistant = await local_api_factory.get_rest_assistant()
        local_throttler = throttler or cls._get_throttler_instance()
        tasks = [cls._get_last_traded_price(t_pair, domain, rest_assistant, local_throttler) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @staticmethod
    @async_ttl_cache(ttl=2, maxsize=1)
    async def get_all_mid_prices(domain="com") -> Dict[str, Decimal]:
        """
        Returns the mid price of all trading pairs, obtaining the information from the exchange. This functionality is
        required by the market price strategy.
        :param domain: Domain to use for the connection with the exchange (either "com" or "us"). Default value is "com"
        :return: Dictionary with the trading pair as key, and the mid price as value
        """
        local_api_factory = build_api_factory()
        rest_assistant = await local_api_factory.get_rest_assistant()
        throttler = BinanceAPIOrderBookDataSource._get_throttler_instance()

        url = binance_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain)
        request = RESTRequest(method=RESTMethod.GET, url=url)

        async with throttler.execute_task(limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL):
            resp: RESTResponse = await rest_assistant.call(request=request)
            resp_json = await resp.json()

        ret_val = {}
        for record in resp_json:
            try:
                pair = await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    symbol=record["symbol"],
                    domain=domain)
                ret_val[pair] = ((Decimal(record.get("bidPrice", "0")) +
                                  Decimal(record.get("askPrice", "0")))
                                 / Decimal("2"))
            except KeyError:
                # Ignore results for pairs that are not tracked
                continue
        return ret_val

    @classmethod
    def trading_pair_symbol_map_ready(cls, domain: str = "com"):
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized
        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :return: True if the mapping has been initialized, False otherwise
        """
        return domain in cls._trading_pair_symbol_map and len(cls._trading_pair_symbol_map[domain]) > 0

    @classmethod
    async def trading_pair_symbol_map(
            cls,
            domain: str = "com",
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None
    ):
        """
        Returns the internal map used to translate trading pairs from and to the exchange notation.
        In general this should not be used. Instead call the methods `exchange_symbol_associated_to_pair` and
        `trading_pair_associated_to_exchange_symbol`
        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :return: bidirectional mapping between trading pair exchange notation and client notation
        """
        if not cls.trading_pair_symbol_map_ready(domain=domain):
            async with cls._mapping_initialization_lock:
                # Check condition again (could have been initialized while waiting for the lock to be released)
                if not cls.trading_pair_symbol_map_ready(domain=domain):
                    await cls._init_trading_pair_symbols(domain, api_factory, throttler)

        return cls._trading_pair_symbol_map[domain]

    @staticmethod
    async def exchange_symbol_associated_to_pair(
            trading_pair: str,
            domain="com",
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
    ) -> str:
        """
        Used to translate a trading pair from the client notation to the exchange notation
        :param trading_pair: trading pair in client notation
        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :return: trading pair in exchange notation
        """
        symbol_map = await BinanceAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            api_factory=api_factory,
            throttler=throttler)
        return symbol_map.inverse[trading_pair]

    @staticmethod
    async def trading_pair_associated_to_exchange_symbol(
            symbol: str,
            domain="com",
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None) -> str:
        """
        Used to translate a trading pair from the exchange notation to the client notation
        :param symbol: trading pair in exchange notation
        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :return: trading pair in client notation
        """
        symbol_map = await BinanceAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            api_factory=api_factory,
            throttler=throttler)
        return symbol_map[symbol]

    @staticmethod
    async def fetch_trading_pairs(domain="com") -> List[str]:
        """
        Returns a list of all known trading pairs enabled to operate with
        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :return: list of trading pairs in client notation
        """
        mapping = await BinanceAPIOrderBookDataSource.trading_pair_symbol_map(domain=domain)
        return list(mapping.values())

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Creates a local instance of the exchange order book for a particular trading pair
        :param trading_pair: the trading pair for which the order book has to be retrieved
        :return: a local copy of the current order book in the exchange
        """
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair, 1000)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Reads the trade events queue. For each event creates a trade message instance and adds it to the output queue
        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created trade messages
        """
        message_queue = self._message_queue[CONSTANTS.TRADE_EVENT_TYPE]
        while True:
            try:
                json_msg = await message_queue.get()

                if "result" in json_msg:
                    continue
                trading_pair = await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    symbol=json_msg["s"],
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                trade_msg: OrderBookMessage = BinanceOrderBook.trade_message_from_exchange(
                    json_msg, {"trading_pair": trading_pair})
                output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public trade updates from exchange")

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Reads the order diffs events queue. For each event creates a diff message instance and adds it to the
        output queue
        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created diff messages
        """
        message_queue = self._message_queue[CONSTANTS.DIFF_EVENT_TYPE]
        while True:
            try:
                json_msg = await message_queue.get()
                if "result" in json_msg:
                    continue
                trading_pair = await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    symbol=json_msg["s"],
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                order_book_message: OrderBookMessage = BinanceOrderBook.diff_message_from_exchange(
                    json_msg, time.time(), {"trading_pair": trading_pair})
                output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public order book updates from exchange")

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        This method runs continuously and request the full order book content from the exchange every hour.
        The method uses the REST API from the exchange because it does not provide an endpoint to get the full order
        book through websocket. With the information creates a snapshot messages that is added to the output queue
        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created snapshot messages
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair=trading_pair)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().error(f"Unexpected error fetching order book snapshot for {trading_pair}.",
                                            exc_info=True)
                        await self._sleep(5.0)
                await self._sleep(self.ONE_HOUR)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await self._sleep(5.0)

    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.WSS_URL.format(self._domain),
                                 ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                await self._subscribe_channels(ws)

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if "result" in data:
                        continue
                    event_type = data.get("e")
                    if event_type in [CONSTANTS.DIFF_EVENT_TYPE, CONSTANTS.TRADE_EVENT_TYPE]:
                        self._message_queue[event_type].put_nowait(data)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def get_snapshot(
            self,
            trading_pair: str,
            limit: int = 1000) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.
        :param trading_pair: the trading pair for which the order book will be retrieved
        :param limit: the depth of the order book to retrieve
        :return: the response from the exchange (JSON dictionary)
        """
        rest_assistant = await self._get_rest_assistant()
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler)
        }
        if limit != 0:
            params["limit"] = str(limit)

        url = binance_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain)
        request = RESTRequest(method=RESTMethod.GET, url=url, params=params)

        async with self._throttler.execute_task(limit_id=CONSTANTS.SNAPSHOT_PATH_URL):
            response: RESTResponse = await rest_assistant.call(request=request)
            if response.status != 200:
                raise IOError(f"Error fetching market snapshot for {trading_pair}. "
                              f"Response: {response}.")
            data = await response.json()

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            trade_params = []
            depth_params = []
            for trading_pair in self._trading_pairs:
                symbol = await self.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair,
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                trade_params.append(f"{symbol.lower()}@trade")
                depth_params.append(f"{symbol.lower()}@depth@100ms")
            payload = {
                "method": "SUBSCRIBE",
                "params": trade_params,
                "id": 1
            }
            subscribe_trade_request: WSRequest = WSRequest(payload=payload)

            payload = {
                "method": "SUBSCRIBE",
                "params": depth_params,
                "id": 2
            }
            subscribe_orderbook_request: WSRequest = WSRequest(payload=payload)

            await ws.send(subscribe_trade_request)
            await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @classmethod
    async def _get_last_traded_price(cls,
                                     trading_pair: str,
                                     domain: str,
                                     rest_assistant: RESTAssistant,
                                     throttler: AsyncThrottler) -> float:

        url = binance_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain)
        symbol = await cls.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair,
            domain=domain,
            throttler=throttler)
        request = RESTRequest(
            method=RESTMethod.GET,
            url=f"{url}?symbol={symbol}")

        async with throttler.execute_task(limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL):
            resp: RESTResponse = await rest_assistant.call(request=request)
            if resp.status == 200:
                resp_json = await resp.json()
                return float(resp_json["lastPrice"])

    @classmethod
    async def _init_trading_pair_symbols(
            cls,
            domain: str = "com",
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None):
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation
        """
        mapping = bidict()

        local_api_factory = api_factory or build_api_factory()
        rest_assistant = await local_api_factory.get_rest_assistant()
        local_throttler = throttler or cls._get_throttler_instance()
        url = binance_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=domain)
        request = RESTRequest(method=RESTMethod.GET, url=url)

        try:
            async with local_throttler.execute_task(limit_id=CONSTANTS.EXCHANGE_INFO_PATH_URL):
                response: RESTResponse = await rest_assistant.call(request=request)
                if response.status == 200:
                    data = await response.json()
                    for symbol_data in filter(binance_utils.is_exchange_information_valid, data["symbols"]):
                        mapping[symbol_data["symbol"]] = f"{symbol_data['baseAsset']}-{symbol_data['quoteAsset']}"
        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")

        cls._trading_pair_symbol_map[domain] = mapping

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
