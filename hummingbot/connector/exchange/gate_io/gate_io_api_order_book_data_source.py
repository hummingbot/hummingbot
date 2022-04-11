import asyncio
import json
import logging
import time
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

import pandas as pd
from bidict import bidict

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger

from .gate_io_order_book import GateIoOrderBook
from .gate_io_web_utils import (
    GateIoAPIError,
    GateIORESTRequest,
    api_call_with_retries,
    build_api_factory,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair
)
from .gate_io_websocket import GateIoWebsocket
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.utils import async_ttl_cache
from . import gate_io_web_utils as web_utils


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("trade_status", None) == "tradable"


class GateIoAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 trading_pairs: List[str],
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__(trading_pairs)
        self._api_factory = api_factory or build_api_factory()
        self._rest_assistant: Optional[RESTAssistant] = None
        self._throttler = throttler or self._get_throttler_instance()
        self._trading_pairs: List[str] = trading_pairs

        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @classmethod
    async def get_last_traded_prices(
            cls,
            trading_pairs: List[str],
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None) -> Dict[str, Decimal]:
        results = {}
        ticker_param = None
        if len(trading_pairs) == 1:
            ticker_param = {'currency_pair': convert_to_exchange_trading_pair(trading_pairs[0])}

        tickers = await web_utils.api_request(
            path=CONSTANTS.TICKER_PATH_URL,
            domain=domain,
            params=ticker_param,
            method=RESTMethod.GET,
            limit_id=CONSTANTS.TICKER_PATH_URL
        )
        for trading_pair in trading_pairs:
            ex_pair = convert_to_exchange_trading_pair(trading_pair)
            ticker = list([tic for tic in tickers if tic['currency_pair'] == ex_pair])[0]
            results[trading_pair] = Decimal(str(ticker["last"]))
        return results

    @staticmethod
    @async_ttl_cache(ttl=2, maxsize=1)
    async def get_all_mid_prices(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> Dict[str, Decimal]:
        """
        Returns the mid price of all trading pairs, obtaining the information from the exchange. This functionality is
        required by the market price strategy.
        :param domain: Domain to use for the connection with the exchange (either "com" or "us"). Default value is "com"
        :return: Dictionary with the trading pair as key, and the mid price as value
        """
        resp_json = await web_utils.api_request(
            path=CONSTANTS.TICKER_PATH_URL,
            domain=domain,
            method=RESTMethod.GET,
        )
        ret_val = {}
        for record in resp_json:
            try:
                pair = await GateIoAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
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
    def trading_pair_symbol_map_ready(cls, domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized
        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :return: True if the mapping has been initialized, False otherwise
        """
        return domain in cls._trading_pair_symbol_map and len(cls._trading_pair_symbol_map[domain]) > 0

    @classmethod
    async def trading_pair_symbol_map(
            cls,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None,
    ) -> Dict[str, str]:
        """
        Returns the internal map used to translate trading pairs from and to the exchange notation.
        In general this should not be used. Instead call the methods `exchange_symbol_associated_to_pair` and
        `trading_pair_associated_to_exchange_symbol`

        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: bidirectional mapping between trading pair exchange notation and client notation
        """
        if not cls.trading_pair_symbol_map_ready(domain=domain):
            async with cls._mapping_initialization_lock:
                # Check condition again (could have been initialized while waiting for the lock to be released)
                if not cls.trading_pair_symbol_map_ready(domain=domain):
                    await cls._init_trading_pair_symbols(
                        domain=domain,
                        api_factory=api_factory,
                        throttler=throttler,
                        time_synchronizer=time_synchronizer)

        return cls._trading_pair_symbol_map[domain]

    @staticmethod
    async def exchange_symbol_associated_to_pair(
            trading_pair: str,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None,
    ) -> str:
        """
        Used to translate a trading pair from the client notation to the exchange notation

        :param trading_pair: trading pair in client notation
        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: trading pair in exchange notation
        """
        symbol_map = await GateIoAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            api_factory=api_factory,
            throttler=throttler,
            time_synchronizer=time_synchronizer)
        return symbol_map.inverse[trading_pair]

    @staticmethod
    async def trading_pair_associated_to_exchange_symbol(
            symbol: str,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None) -> str:
        """
        Used to translate a trading pair from the exchange notation to the client notation

        :param symbol: trading pair in exchange notation
        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: trading pair in client notation
        """
        symbol_map = await GateIoAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            api_factory=api_factory,
            throttler=throttler,
            time_synchronizer=time_synchronizer)
        return symbol_map[symbol]

    @staticmethod
    async def fetch_trading_pairs(
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            throttler: Optional[AsyncThrottler] = None,
            api_factory: Optional[WebAssistantsFactory] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None) -> List[str]:

        mapping = await GateIoAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            throttler=throttler,
            api_factory=api_factory,
            time_synchronizer=time_synchronizer,
        )
        return list(mapping.values())

        # TODO
        rest_assistant = await api_factory.get_rest_assistant()
        try:
            async with throttler.execute_task(CONSTANTS.SYMBOL_PATH_URL):
                endpoint = CONSTANTS.SYMBOL_PATH_URL
                request = GateIORESTRequest(
                    method=RESTMethod.GET,
                    endpoint=endpoint,
                    throttler_limit_id=endpoint,
                )
                symbols = await api_call_with_retries(
                    request, rest_assistant, throttler, logging.getLogger()
                )
            trading_pairs = list([convert_from_exchange_trading_pair(sym["id"]) for sym in symbols])
            # Filter out unmatched pairs so nothing breaks
            return [sym for sym in trading_pairs if sym is not None]
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for Gate.io trading pairs
            pass
        return []

    @classmethod
    async def get_order_book_data(
        cls,
        trading_pair: str,
        throttler: Optional[AsyncThrottler] = None,
        rest_assistant: Optional[RESTAssistant] = None,
        logger: Optional[logging.Logger] = None,
    ) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        throttler = throttler or cls._get_throttler_instance()
        api_factory = build_api_factory()
        rest_assistant = rest_assistant or await api_factory.get_rest_assistant()
        logger = logger or logging.getLogger()
        try:
            ex_pair = convert_to_exchange_trading_pair(trading_pair)
            params = {"currency_pair": ex_pair, "with_id": json.dumps(True)}
            endpoint = CONSTANTS.ORDER_BOOK_PATH_URL
            request = GateIORESTRequest(
                method=RESTMethod.GET,
                endpoint=endpoint,
                params=params,
                throttler_limit_id=endpoint,
            )
            orderbook_response = await api_call_with_retries(
                request, rest_assistant, throttler, logger
            )
            return orderbook_response
        except GateIoAPIError as e:
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                f"HTTP status is {e.http_status}. Error is {e.error_message}.")

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        rest_assistant = await self._get_rest_assistant()
        snapshot: Dict[str, Any] = await self.get_order_book_data(
            trading_pair, self._throttler, rest_assistant, self.logger()
        )
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = GateIoOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair})
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_subscriptions(self):
        ws = None

        while True:
            try:
                ws = await self._subscribe_to_order_book_streams()
                async for response in ws.on_message():
                    channel: str = response.get("channel", None)
                    if response.get("event") in ["subscribe", "unsubscribe"]:
                        continue
                    self._message_queue[channel].put_nowait(response)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error occurred when listening to order book streams. "
                                    "Retrying in 5 seconds...",
                                    exc_info=True)
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def _subscribe_to_order_book_streams(self) -> GateIoWebsocket:
        try:
            ws = GateIoWebsocket(api_factory=self._api_factory)
            await ws.connect()
            await ws.subscribe(
                CONSTANTS.TRADES_ENDPOINT_NAME,
                [convert_to_exchange_trading_pair(pair) for pair in self._trading_pairs],
            )
            for pair in self._trading_pairs:
                await ws.subscribe(CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME,
                                   [convert_to_exchange_trading_pair(pair), '100ms'])
                self.logger().info(f"Subscribed to {self._trading_pairs} orderbook data streams...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams...")
            raise
        return ws

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        msg_queue = self._message_queue[CONSTANTS.TRADES_ENDPOINT_NAME]
        msg = None
        while True:
            try:
                msg = await msg_queue.get()
                trade_data: Dict[Any] = msg.get("result", None)

                pair: str = convert_from_exchange_trading_pair(trade_data.get("currency_pair", None))

                if pair is None:
                    continue

                trade_timestamp: int = trade_data['create_time']
                trade_msg: OrderBookMessage = GateIoOrderBook.trade_message_from_exchange(
                    trade_data,
                    trade_timestamp,
                    metadata={"trading_pair": pair})
                output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    f"Unexpected error while parsing ws trades message {msg}.", exc_info=True
                )
                await self._sleep(5.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        msg_queue = self._message_queue[CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME]
        msg = None
        while True:
            try:
                msg = await msg_queue.get()
                order_book_data: str = msg.get("result", None)

                timestamp: float = (order_book_data["t"]) * 1e-3
                pair: str = convert_from_exchange_trading_pair(order_book_data["s"])

                orderbook_msg: OrderBookMessage = GateIoOrderBook.diff_message_from_exchange(
                    order_book_data,
                    timestamp,
                    metadata={"trading_pair": pair}
                )
                output.put_nowait(orderbook_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    f"Unexpected error while parsing ws order book message {msg}.", exc_info=True
                )
                await self._sleep(5.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair, self._throttler)
                        snapshot_timestamp: int = int(time.time())
                        snapshot_msg: OrderBookMessage = GateIoOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")

                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.", exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection.")
                        await self._sleep(5.0)
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await self._sleep(5.0)

    @classmethod
    async def _init_trading_pair_symbols(
            cls,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None):
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation
        """
        mapping = bidict()

        try:
            data = await web_utils.api_request(
                path=CONSTANTS.SYMBOL_PATH_URL,
                api_factory=api_factory,
                throttler=throttler,
                time_synchronizer=time_synchronizer,
                domain=domain,
                method=RESTMethod.GET,
            )
            for sd in data:
                if not is_exchange_information_valid(sd):
                    continue
                mapping[sd["id"]] = combine_to_hb_trading_pair(
                    base=sd["base"],
                    quote=sd["quote"])

        except Exception as ex:
            cls.logger().exception(f"There was an error requesting exchange info ({str(ex)})")

        cls._trading_pair_symbol_map[domain] = mapping

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant
