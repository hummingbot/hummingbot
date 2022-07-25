import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import aiohttp
import pandas as pd
from bidict import bidict

from hummingbot.connector.exchange.southxchange.southxchange_constants import (
    EXCHANGE_NAME,
    PUBLIC_WS_URL,
    RATE_LIMITS,
    REST_URL,
)
from hummingbot.connector.exchange.southxchange.southxchange_order_book import SouthXchangeOrderBook
from hummingbot.connector.exchange.southxchange.southxchange_utils import (
    build_api_factory,
    convert_bookWebSocket_to_bookApi,
    convert_string_to_datetime,
    convert_to_exchange_trading_pair,
)
from hummingbot.connector.exchange.southxchange.southxchange_web_utils import WebAssistantsFactory_SX, WSAssistant_SX
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse, WSJSONRequest
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.southxchange.southxchange_exchange import SouthxchangeExchange


class SouthxchangeAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0
    PING_TIMEOUT = 15.0

    _mapping_initialization_lock = asyncio.Lock()
    _trading_pair_symbol_map: Mapping[str, str] = None
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
            self,
            connector: 'SouthxchangeExchange',
            api_factory: Optional[WebAssistantsFactory_SX] = None,
            throttler: Optional[AsyncThrottler] = None,
            trading_pairs: List[str] = None,
    ):
        super().__init__(trading_pairs)
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory(throttler=self._throttler)
        self._trading_pairs: List[str] = trading_pairs
        self._connector = connector
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(RATE_LIMITS)
        return throttler

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str], api_factory: Optional[WebAssistantsFactory_SX] = None, throttler: Optional[AsyncThrottler] = None) -> Dict[str, float]:
        result = {}
        throttler = throttler or SouthxchangeAPIOrderBookDataSource._get_throttler_instance()
        for trading_pair in trading_pairs:
            api_factory = api_factory or build_api_factory(throttler=throttler)
            throttler = throttler or cls._get_throttler_instance()
            rest_assistant = await api_factory.get_rest_assistant()
            request = RESTRequest(method=RESTMethod.GET, url=f"{REST_URL}trades/{convert_to_exchange_trading_pair(trading_pair)}")
            async with throttler.execute_task("SXC"):
                resp: RESTResponse = await rest_assistant.call(request=request)
                if resp.status != 200:
                    raise IOError(
                        f"Error fetching last traded prices at {EXCHANGE_NAME}. "
                        f"HTTP status is {resp.status}."
                    )
                data: List[str] = await resp.json()
                if data.__len__() < 1:
                    continue
                # last trade is the most recent trade
                result[trading_pair] = float(data[-1].get("Price"))
        return result

    @staticmethod
    async def get_order_book_data(trading_pair: str, api_factory: Optional[WebAssistantsFactory_SX] = None, throttler: Optional[AsyncThrottler] = None) -> Dict[str, any]:
        """
        Modify SX
        Get whole orderbook
        """
        throttler = throttler or SouthxchangeAPIOrderBookDataSource._get_throttler_instance()
        api_factory = api_factory or build_api_factory(throttler=throttler)
        rest_assistant = await api_factory.get_rest_assistant()
        request = RESTRequest(method=RESTMethod.GET, url=f"{REST_URL}book/{convert_to_exchange_trading_pair(trading_pair)}")
        async with throttler.execute_task("SXC"):
            resp: RESTResponse = await rest_assistant.call(request=request)
            if resp.status != 200:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {EXCHANGE_NAME}. "
                    f"HTTP status is {resp.status}."
                )
            data: Dict[str, Any] = await resp.json()
            if len(data) == 0:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {EXCHANGE_NAME}. "
                    f"Error is {data}."
                )
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_msg: OrderBookMessage = SouthXchangeOrderBook.snapshot_message_from_exchange(
            snapshot,
            get_tracking_nonce(),
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Reads the trade events queue. For each event creates a trade message instance and adds it to the output queue

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created trade messages
        """
        msg_queue = self._message_queue["trade"]
        while True:
            try:
                msg = await msg_queue.get()
                if msg is None:
                    continue
                trading_pairs = ",".join(list(
                    map(lambda trading_pair: convert_to_exchange_trading_pair(trading_pair), self._trading_pairs)
                ))
                if msg.get("k") == "trade":
                    """
                    Modify - SouthXchange
                    """
                    for trade in msg.get("v"):
                        trade_timestamp = int(datetime.timestamp(convert_string_to_datetime(trade.get('d'))))
                        trade_msg: OrderBookMessage = SouthXchangeOrderBook.trade_message_from_exchange(
                            trade,
                            trade_timestamp,
                            metadata={"trading_pair": trading_pairs}
                        )
                        output.put_nowait(trade_msg)
                else:
                    continue
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Reads the order diffs events queue. For each event creates a diff message instance and adds it to the
        output queue

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created diff messages
        """
        msg_queue = self._message_queue["bookdelta"]
        while True:
            try:
                msg = await msg_queue.get()
                raw_msg = convert_bookWebSocket_to_bookApi(msg.get("v"))
                if raw_msg is None:
                    continue
                trading_pairs = ",".join(list(
                    map(lambda trading_pair: convert_to_exchange_trading_pair(trading_pair), self._trading_pairs)
                ))
                msg_timestamp: int = get_tracking_nonce()
                order_book_message: OrderBookMessage = SouthXchangeOrderBook.diff_message_from_exchange(
                    raw_msg,
                    msg_timestamp,
                    metadata={"trading_pair": trading_pairs}
                )
                output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().debug(str(e))
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await self._sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Modify SX
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                        snapshot_msg: OrderBookMessage = SouthXchangeOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            get_tracking_nonce(),
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above API rate limits.
                        await asyncio.sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection."
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

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        """
        Returns a list of all known trading pairs enabled to operate with

        :return: list of trading pairs in client notation
        """
        mapping = await SouthxchangeAPIOrderBookDataSource.trading_pair_symbol_map()
        return list(mapping.values())

    @classmethod
    def trading_pair_symbol_map_ready(cls):
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized

        :return: True if the mapping has been initialized, False otherwise
        """
        return cls._trading_pair_symbol_map is not None and len(cls._trading_pair_symbol_map) > 0

    @classmethod
    async def trading_pair_symbol_map(
            cls,
            api_factory: Optional[WebAssistantsFactory_SX] = None,
            throttler: Optional[AsyncThrottler] = None
    ):
        """
        Returns the internal map used to translate trading pairs from and to the exchange notation.
        In general this should not be used. Instead call the methods `exchange_symbol_associated_to_pair` and
        `trading_pair_associated_to_exchange_symbol`

        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested

        :return: bidirectional mapping between trading pair exchange notation and client notation
        """
        if not cls.trading_pair_symbol_map_ready():
            async with cls._mapping_initialization_lock:
                # Check condition again (could have been initialized while waiting for the lock to be released)
                if not cls.trading_pair_symbol_map_ready():
                    await cls._init_trading_pair_symbols(api_factory, throttler)

        return cls._trading_pair_symbol_map

    @classmethod
    async def _init_trading_pair_symbols(
            cls,
            api_factory: Optional[WebAssistantsFactory_SX] = None,
            throttler: Optional[AsyncThrottler] = None):
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation
        """
        mapping = bidict()

        throttler = throttler or cls._get_throttler_instance()
        api_factory = api_factory or build_api_factory(throttler=throttler)
        rest_assistant = await api_factory.get_rest_assistant()

        url = f"{REST_URL}markets"
        request = RESTRequest(method=RESTMethod.GET, url=url)

        try:
            async with throttler.execute_task(limit_id="SXC"):
                response: RESTResponse = await rest_assistant.call(request=request)
                if response.status != 200:
                    return []
                data: Dict[str, Dict[str, Any]] = await response.json()
                for symbol_data in data:
                    mapping[symbol_data[2]] = f"{symbol_data[0]}-{symbol_data[1]}"
        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")
        cls._trading_pair_symbol_map = mapping

    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        ws = None
        while True:
            try:
                ws = await self._subscribe_to_order_book_streams()
                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    event_type = data.get("k")
                    if event_type in ["bookdelta", "trade"]:
                        self._message_queue[event_type].put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error occurred when listening to order book streams. "
                                    "Retrying in 5 seconds...",
                                    exc_info=True)
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def _subscribe_to_order_book_streams(self) -> aiohttp.ClientWebSocketResponse:
        """
        Subscribes to the order book diff orders events through the provided websocket connection.
        """
        try:
            for item in self._trading_pair_symbol_map.items():
                if self._trading_pairs[0] == item[1]:
                    idMarket = item[0]
            payload = {
                "k": "subscribe",
                "v": idMarket
            }
            ws: WSAssistant_SX = await self._api_factory.get_ws_assistant()
            await ws.connect(ws_url=PUBLIC_WS_URL)

            # for payload in subscription_payloads:
            subscribe_request: WSJSONRequest = WSJSONRequest(payload)
            async with self._throttler.execute_task("SXC"):
                await ws.send(subscribe_request)

            self.logger().info(f"Subscribed to {self._trading_pairs} orderbook trading and delta streams...")

            return ws
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    @staticmethod
    async def exchange_symbol_associated_to_pair(
            trading_pair: str,
            api_factory: Optional[WebAssistantsFactory_SX] = None,
            throttler: Optional[AsyncThrottler] = None,
    ) -> str:
        """
        Used to translate a trading pair from the client notation to the exchange notation

        :param trading_pair: trading pair in client notation
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested

        :return: trading pair in exchange notation
        """
        symbol_map = await SouthxchangeAPIOrderBookDataSource.trading_pair_symbol_map(
            api_factory=api_factory,
            throttler=throttler)
        return symbol_map.inverse[trading_pair]
