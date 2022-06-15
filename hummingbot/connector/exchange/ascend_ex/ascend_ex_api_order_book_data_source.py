import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional

import aiohttp
import pandas as pd
from bidict import bidict

from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.connector.exchange.ascend_ex.ascend_ex_order_book import AscendExOrderBook
from hummingbot.connector.exchange.ascend_ex.ascend_ex_utils import build_api_factory, get_hb_id_headers
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class AscendExAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0
    PING_TIMEOUT = 15.0
    HEARTBEAT_PING_INTERVAL = 15.0

    TRADE_TOPIC_ID = "trades"
    DIFF_TOPIC_ID = "depth"
    PING_TOPIC_ID = "ping"

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Mapping[str, str] = None
    _mapping_initialization_lock = asyncio.Lock()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory(throttler=self._throttler)
        self._trading_pairs: List[str] = trading_pairs

        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    async def get_last_traded_prices(
        cls,
        trading_pairs: List[str],
        api_factory: Optional[WebAssistantsFactory] = None,
        throttler: Optional[AsyncThrottler] = None
    ) -> Dict[str, float]:
        """
        Return a dictionary the trading_pair as key and the current price as value for each trading pair passed as
        parameter

        :param trading_pairs: list of trading pairs to get the prices for
        :param api_factory: the instance of the web assistant factory to be used when doing requests to the server.
        If no instance is provided then a new one will be created.
        :param throttler: the instance of the throttler to use to limit request to the server. If it is not specified
        the function will create a new one.

        :return: Dictionary of associations between token pair and its latest price
        """
        result = {}
        throttler = throttler or AscendExAPIOrderBookDataSource._get_throttler_instance()
        for trading_pair in trading_pairs:
            api_factory = api_factory or build_api_factory(throttler=throttler)
            throttler = throttler or cls._get_throttler_instance()
            rest_assistant = await api_factory.get_rest_assistant()

            url = f"{CONSTANTS.REST_URL}/{CONSTANTS.TRADES_PATH_URL}"\
                  f"?symbol={await AscendExAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair)}"
            request = RESTRequest(method=RESTMethod.GET, url=url)

            async with throttler.execute_task(CONSTANTS.TRADES_PATH_URL):
                resp: RESTResponse = await rest_assistant.call(request=request)
            if resp.status != 200:
                raise IOError(
                    f"Error fetching last traded prices at {CONSTANTS.EXCHANGE_NAME}. "
                    f"HTTP status is {resp.status}."
                )

            resp_json = await resp.json()
            if resp_json.get("code") != 0:
                raise IOError(
                    f"Error fetching last traded prices at {CONSTANTS.EXCHANGE_NAME}. "
                    f"Error is {resp_json.message}."
                )

            trades = resp_json.get("data").get("data")

            # last trade is the most recent trade
            for trade in trades[-1:]:
                result[trading_pair] = float(trade.get("p"))

        return result

    @staticmethod
    async def get_order_book_data(trading_pair: str,
                                  api_factory: Optional[WebAssistantsFactory] = None,
                                  throttler: Optional[AsyncThrottler] = None) -> Dict[str, any]:
        """
        Get whole orderbook

        :param trading_pair: a trading pair for which the order book should be retrieved
        :param api_factory: the instance of the web assistant factory to be used when doing requests to the server.
        If no instance is provided then a new one will be created.
        :param throttler: the instance of the throttler to use to limit request to the server. If it is not specified
        the function will create a new one.

        :return: current order book for the specified trading pair
        """

        throttler = throttler or AscendExAPIOrderBookDataSource._get_throttler_instance()
        api_factory = api_factory or build_api_factory(throttler=throttler)
        rest_assistant = await api_factory.get_rest_assistant()

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}"\
              f"?symbol={await AscendExAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair)}"
        request = RESTRequest(method=RESTMethod.GET, url=url)

        async with throttler.execute_task(CONSTANTS.DEPTH_PATH_URL):
            resp: RESTResponse = await rest_assistant.call(request=request)
        if resp.status != 200:
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                f"HTTP status is {resp.status}."
            )

        data: Dict[str, Any] = await resp.json()
        if data.get("code") != 0:
            raise IOError(
                f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                f"Error is {data['reason']}."
            )

        return data["data"]

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
            api_factory: Optional[WebAssistantsFactory] = None,
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

    @staticmethod
    async def exchange_symbol_associated_to_pair(
            trading_pair: str,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
    ) -> str:
        """
        Used to translate a trading pair from the client notation to the exchange notation

        :param trading_pair: trading pair in client notation
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested

        :return: trading pair in exchange notation
        """
        symbol_map = await AscendExAPIOrderBookDataSource.trading_pair_symbol_map(
            api_factory=api_factory,
            throttler=throttler)
        return symbol_map.inverse[trading_pair]

    @staticmethod
    async def trading_pair_associated_to_exchange_symbol(
            symbol: str,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None) -> str:
        """
        Used to translate a trading pair from the exchange notation to the client notation

        :param symbol: trading pair in exchange notation
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested

        :return: trading pair in client notation
        """
        symbol_map = await AscendExAPIOrderBookDataSource.trading_pair_symbol_map(
            api_factory=api_factory,
            throttler=throttler)
        return symbol_map[symbol]

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        """
        Returns a list of all known trading pairs enabled to operate with

        :return: list of trading pairs in client notation
        """
        mapping = await AscendExAPIOrderBookDataSource.trading_pair_symbol_map()
        return list(mapping.values())

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Creates a local instance of the exchange order book for a particular trading pair

        :param trading_pair: the trading pair for which the order book has to be retrieved

        :return: a local copy of the current order book in the exchange
        """
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair,
                                                                  api_factory=self._api_factory,
                                                                  throttler=self._throttler)
        snapshot_timestamp: float = snapshot.get("data").get("ts")
        snapshot_msg: OrderBookMessage = AscendExOrderBook.snapshot_message_from_exchange(
            snapshot.get("data"),
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

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
                    if "result" in data:
                        continue
                    event_type = data.get("m")
                    if event_type in [self.TRADE_TOPIC_ID, self.DIFF_TOPIC_ID]:
                        self._message_queue[event_type].put_nowait(data)
                    if event_type in [self.PING_TOPIC_ID]:
                        await self._handle_ping_message(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error occurred when listening to order book streams. "
                                    "Retrying in 5 seconds...",
                                    exc_info=True)
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Reads the trade events queue. For each event creates a trade message instance and adds it to the output queue

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created trade messages
        """
        msg_queue = self._message_queue[self.TRADE_TOPIC_ID]
        while True:
            try:
                msg = await msg_queue.get()
                trading_pair = \
                    await AscendExAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(msg.get("symbol"))
                trades = msg.get("data")

                for trade in trades:
                    trade_timestamp: int = trade.get("ts")
                    trade_msg: OrderBookMessage = AscendExOrderBook.trade_message_from_exchange(
                        trade,
                        trade_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    output.put_nowait(trade_msg)
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
        msg_queue = self._message_queue[self.DIFF_TOPIC_ID]
        while True:
            try:
                msg = await msg_queue.get()
                msg_timestamp: int = msg.get("data").get("ts")
                trading_pair = \
                    await AscendExAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(msg.get("symbol"))
                order_book_message: OrderBookMessage = AscendExOrderBook.diff_message_from_exchange(
                    msg.get("data"),
                    msg_timestamp,
                    metadata={"trading_pair": trading_pair}
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
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair,
                                                                                  api_factory=self._api_factory,
                                                                                  throttler=self._throttler)
                        snapshot_timestamp: float = snapshot.get("data").get("ts")
                        snapshot_msg: OrderBookMessage = AscendExOrderBook.snapshot_message_from_exchange(
                            snapshot.get("data"),
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above API rate limits.
                        await self._sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection."
                        )
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
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @classmethod
    async def _init_trading_pair_symbols(
            cls,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None):
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation
        """
        mapping = bidict()

        throttler = throttler or cls._get_throttler_instance()
        api_factory = api_factory or build_api_factory(throttler=throttler)
        rest_assistant = await api_factory.get_rest_assistant()

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRODUCTS_PATH_URL}"
        request = RESTRequest(method=RESTMethod.GET, url=url)

        try:
            async with throttler.execute_task(limit_id=CONSTANTS.PRODUCTS_PATH_URL):
                response: RESTResponse = await rest_assistant.call(request=request)
                if response.status == 200:
                    data: Dict[str, Dict[str, Any]] = await response.json()
                    for symbol_data in data["data"]:
                        mapping[symbol_data["symbol"]] = f"{symbol_data['baseAsset']}-{symbol_data['quoteAsset']}"
        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")

        cls._trading_pair_symbol_map = mapping

    async def _subscribe_to_order_book_streams(self) -> aiohttp.ClientWebSocketResponse:
        """
        Subscribes to the order book diff orders events through the provided websocket connection.
        """
        try:
            trading_pairs = ",".join([
                await AscendExAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair)
                for trading_pair in self._trading_pairs
            ])
            subscription_payloads = [
                {
                    "op": CONSTANTS.SUB_ENDPOINT_NAME,
                    "ch": f"{topic}:{trading_pairs}"
                }
                for topic in [self.DIFF_TOPIC_ID, self.TRADE_TOPIC_ID]
            ]

            ws: WSAssistant = await self._api_factory.get_ws_assistant()
            url = CONSTANTS.WS_URL
            headers = get_hb_id_headers()
            await ws.connect(ws_url=url, ws_headers=headers, ping_timeout=self.HEARTBEAT_PING_INTERVAL)

            for payload in subscription_payloads:
                subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                async with self._throttler.execute_task(CONSTANTS.SUB_ENDPOINT_NAME):
                    await ws.send(subscribe_request)

            self.logger().info(f"Subscribed to {self._trading_pairs} orderbook trading and delta streams...")

            return ws
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    async def _handle_ping_message(self, ws: aiohttp.ClientWebSocketResponse):
        """
        Responds with pong to a ping message send by a server to keep a websocket connection alive
        """
        async with self._throttler.execute_task(CONSTANTS.PONG_ENDPOINT_NAME):
            payload = {
                "op": "pong"
            }
            pong_request: WSJSONRequest = WSJSONRequest(payload)
            await ws.send(pong_request)
