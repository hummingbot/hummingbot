import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from bidict import bidict

from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_utils as utils,
    kucoin_web_utils as web_utils,
)
from hummingbot.connector.exchange.kucoin.kucoin_order_book import KucoinOrderBook
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class KucoinAPIOrderBookDataSource(OrderBookTrackerDataSource):
    FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 60 * 60

    _kaobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, bidict[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kaobds_logger is None:
            cls._kaobds_logger = logging.getLogger(__name__)
        return cls._kaobds_logger

    def __init__(
            self,
            trading_pairs: List[str],
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None,
    ):
        super().__init__(trading_pairs)
        self._time_synchronizer = time_synchronizer
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
        )
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._last_ws_message_sent_timestamp = 0

    @classmethod
    async def get_last_traded_prices(cls,
                                     trading_pairs: List[str],
                                     domain: str = CONSTANTS.DEFAULT_DOMAIN,
                                     api_factory: Optional[WebAssistantsFactory] = None,
                                     throttler: Optional[AsyncThrottler] = None,
                                     time_synchronizer: Optional[TimeSynchronizer] = None) -> Dict[str, float]:
        """
        Return a dictionary the trading_pair as key and the current price as value for each trading pair passed as
        parameter

        :param trading_pairs: list of trading pairs to get the prices for
        :param domain: which domain we are connecting to (the default value is 'main')
        :param api_factory: the instance of the web assistant factory to be used when doing requests to the server.
            If no instance is provided then a new one will be created.
        :param throttler: the instance of the throttler to use to limit request to the server. If it is not specified
            the function will create a new one.
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: Dictionary of associations between token pair and its latest price
        """
        tasks = [cls._get_last_traded_price(
            trading_pair=t_pair,
            domain=domain,
            api_factory=api_factory,
            throttler=throttler,
            time_synchronizer=time_synchronizer) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    def trading_pair_symbol_map_ready(cls, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> bool:
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized

        :param domain: the domain of the exchange being used (either "main" or "testnet"). Default value is "main"

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

        :param domain: the domain of the exchange being used (either "main" or "testnet"). Default value is "main"
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
        :param domain: the domain of the exchange being used (either "main" or "testnet"). Default value is "main"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: trading pair in exchange notation
        """
        symbol_map = await KucoinAPIOrderBookDataSource.trading_pair_symbol_map(
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
        :param domain: the domain of the exchange being used (either "main" or "testnet"). Default value is "main"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: trading pair in client notation
        """
        symbol_map = await KucoinAPIOrderBookDataSource.trading_pair_symbol_map(
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
        """
        Returns a list of all known trading pairs enabled to operate with

        :param domain: the domain of the exchange being used (either "com" or "us"). Default value is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: list of trading pairs in client notation
        """
        mapping = await KucoinAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            throttler=throttler,
            api_factory=api_factory,
            time_synchronizer=time_synchronizer,
        )
        return list(mapping.values())

    async def get_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler)
        }

        data = await web_utils.api_request(
            path=CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            params=params,
            method=RESTMethod.GET,
        )

        return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Creates a local instance of the exchange order book for a particular trading pair

        :param trading_pair: the trading pair for which the order book has to be retrieved

        :return: a local copy of the current order book in the exchange
        """
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair)
        snapshot_timestamp: float = snapshot["data"]["time"] * 1e-3
        snapshot_msg: OrderBookMessage = KucoinOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book: OrderBook = self.order_book_create_function()
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

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=json_msg["data"]["symbol"],
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                trade_msg: OrderBookMessage = KucoinOrderBook.trade_message_from_exchange(
                    json_msg["data"], {"trading_pair": trading_pair})
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

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=json_msg["data"]["symbol"],
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                order_book_message: OrderBookMessage = KucoinOrderBook.diff_message_from_exchange(
                    json_msg, self._time(), {"trading_pair": trading_pair})
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
                await self._take_full_order_book_snapshot(trading_pairs=self._trading_pairs, snapshot_queue=output)
                await self._sleep(self.FULL_ORDER_BOOK_RESET_DELTA_SECONDS)
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
                connection_info = await web_utils.api_request(
                    path=CONSTANTS.PUBLIC_WS_DATA_PATH_URL,
                    api_factory=self._api_factory,
                    throttler=self._throttler,
                    domain=self._domain,
                    method=RESTMethod.POST,
                )

                ws_url = connection_info["data"]["instanceServers"][0]["endpoint"]
                ping_interval = int(int(connection_info["data"]["instanceServers"][0]["pingInterval"]) * 0.8 * 1e-3)
                token = connection_info["data"]["token"]

                ws: WSAssistant = await self._api_factory.get_ws_assistant()
                await ws.connect(ws_url=f"{ws_url}?token={token}", message_timeout=ping_interval)
                await self._subscribe_channels(ws)
                self._last_ws_message_sent_timestamp = self._time()

                while True:
                    try:
                        seconds_until_next_ping = ping_interval - (self._time() - self._last_ws_message_sent_timestamp)
                        await asyncio.wait_for(self._process_ws_messages(websocket_assistant=ws),
                                               timeout=seconds_until_next_ping)
                    except asyncio.TimeoutError:
                        payload = {
                            "id": web_utils.next_message_id(),
                            "type": "ping",
                        }
                        ping_request = WSRequest(payload=payload)
                        self._last_ws_message_sent_timestamp = self._time()
                        await ws.send(request=ping_request)

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

    @classmethod
    async def _get_last_traded_price(cls,
                                     trading_pair: str,
                                     domain: str,
                                     api_factory: WebAssistantsFactory,
                                     throttler: AsyncThrottler,
                                     time_synchronizer: TimeSynchronizer) -> float:

        ticker_data = await web_utils.api_request(
            path=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            api_factory=api_factory,
            throttler=throttler,
            time_synchronizer=time_synchronizer,
            domain=domain,
            params={"symbol": await cls.exchange_symbol_associated_to_pair(trading_pair)},
            method=RESTMethod.GET,
        )

        return float(ticker_data["data"]["price"])

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
                path=CONSTANTS.EXCHANGE_INFO_PATH_URL,
                api_factory=api_factory,
                throttler=throttler,
                time_synchronizer=time_synchronizer,
                domain=domain,
                method=RESTMethod.GET,
            )

            pairs_info = data.get("data", [])
            for symbol_data in filter(utils.is_pair_information_valid, pairs_info):
                mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseCurrency"],
                                                                            quote=symbol_data["quoteCurrency"])

        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")

        cls._trading_pair_symbol_map[domain] = mapping

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            symbols = ",".join([await self.exchange_symbol_associated_to_pair(
                trading_pair=pair,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer) for pair in self._trading_pairs])

            trades_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": f"/market/match:{symbols}",
                "privateChannel": False,
                "response": False,
            }
            subscribe_trade_request: WSRequest = WSRequest(payload=trades_payload)

            order_book_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": f"/market/level2:{symbols}",
                "privateChannel": False,
                "response": False,
            }
            subscribe_orderbook_request: WSRequest = WSRequest(payload=order_book_payload)

            await ws.send(subscribe_trade_request)
            await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    async def _take_full_order_book_snapshot(self, trading_pairs: List[str], snapshot_queue: asyncio.Queue):
        for trading_pair in trading_pairs:
            try:
                snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair=trading_pair)
                snapshot_timestamp = float(snapshot["data"]["time"]) * 1e-3
                snapshot_msg: OrderBookMessage = KucoinOrderBook.snapshot_message_from_exchange(
                    snapshot,
                    snapshot_timestamp,
                    metadata={"trading_pair": trading_pair}
                )
                snapshot_queue.put_nowait(snapshot_msg)
                self.logger().debug(f"Saved order book snapshot for {trading_pair}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(f"Unexpected error fetching order book snapshot for {trading_pair}.",
                                    exc_info=True)

    async def _process_ws_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if data.get("type") == "message":
                event_type = data.get("subject")
                if event_type in [CONSTANTS.DIFF_EVENT_TYPE, CONSTANTS.TRADE_EVENT_TYPE]:
                    self._message_queue[event_type].put_nowait(data)

    def _time(self):
        return time.time()
