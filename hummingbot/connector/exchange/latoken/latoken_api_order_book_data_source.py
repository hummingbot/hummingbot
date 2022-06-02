import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import ujson
from bidict import bidict

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
import hummingbot.connector.exchange.latoken.latoken_stomper as stomper
from hummingbot.connector.exchange.latoken import latoken_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.event.events import TradeType
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class LatokenAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, bidict[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(self,
                 trading_pairs: List[str],
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__(trading_pairs)
        self._time_synchronizer = time_synchronizer
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
        )
        self._order_book_create_function = lambda: OrderBook()
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._ws_assistant: Optional[WSAssistant] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        return logging.getLogger(__name__) if cls._logger is None else cls._logger

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
        :param domain: which Latoken domain we are connecting to (the default value is 'com')
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
            time_synchronizer=time_synchronizer) for t_pair in
            trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    def trading_pair_symbol_map_ready(cls, domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized
        :param domain: the domain of the exchange being used. Public default is "com"
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
    ) -> bidict[str, str]:
        """
        Returns the internal map used to translate trading pairs from and to the exchange notation.
        In general this should not be used. Instead call the methods `exchange_symbol_associated_to_pair` and
        `trading_pair_associated_to_exchange_symbol`

        :param domain: the domain of the exchange being used. Public default is "com"
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
                    await cls._init_trading_pair_symbols(domain, api_factory, throttler, time_synchronizer)

        return cls._trading_pair_symbol_map[domain]

    @staticmethod
    async def exchange_symbol_associated_to_pair(
            trading_pair: str,
            domain=CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None,
    ) -> str:
        """
        Used to translate a trading pair from the client notation to the exchange notation
        :param trading_pair: trading pair in client notation
        :param domain: the domain of the exchange being used. Public default is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: trading pair in exchange notation
        """
        symbol_map = await LatokenAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            api_factory=api_factory,
            throttler=throttler,
            time_synchronizer=time_synchronizer)
        return symbol_map.inverse[trading_pair]

    @staticmethod
    async def trading_pair_associated_to_exchange_symbol(
            symbol: str,
            domain=CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None) -> str:
        """
        Used to translate a trading pair from the exchange notation to the client notation
        :param symbol: trading pair in exchange notation
        :param domain: the domain of the exchange being used. Public default is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: trading pair in client notation
        """
        symbol_map = await LatokenAPIOrderBookDataSource.trading_pair_symbol_map(
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

        :param domain: the domain of the exchange being used ("com"). Default value is "com"
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :param time_synchronizer: the synchronizer instance being used to keep track of the time difference with the
            exchange

        :return: list of trading pairs in client notation
        """
        symbol_map = await LatokenAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            throttler=throttler,
            api_factory=api_factory,
            time_synchronizer=time_synchronizer,
        )
        return list(symbol_map.values())

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Creates a local instance of the exchange order book for a particular trading pair
        :param trading_pair: the trading pair for which the order book has to be retrieved
        :return: a local copy of the current order book in the exchange
        """
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair)
        snapshot_timestamp: int = time.time_ns()
        timestamp_seconds = snapshot_timestamp * 1e-9

        content = {
            "asks": web_utils.get_book_side(snapshot.pop("ask")),
            "bids": web_utils.get_book_side(snapshot.pop("bid")),
            "update_id": timestamp_seconds,
            "trading_pair": trading_pair}
        # content.update(snapshot)
        msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp=timestamp_seconds)

        order_book = self.order_book_create_function()
        order_book.apply_snapshot(msg.bids, msg.asks, msg.update_id)
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
                msg = await message_queue.get()

                symbol = msg['headers']['destination'].replace('/v1/trade/', '')

                trading_pair = await LatokenAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    symbol=symbol,
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler,
                    time_synchronizer=self._time_synchronizer)

                body = ujson.loads(msg["body"])
                payload = body["payload"]
                timestamp = time.time_ns()
                for trade in payload:  # body_timestamp = body['timestamp']
                    ts_seconds = timestamp * 1e-9
                    trade_type = float(TradeType.BUY.value) if trade["makerBuyer"] else float(TradeType.SELL.value)
                    content = {
                        "trading_pair": trading_pair,
                        "trade_type": trade_type,
                        "trade_id": trade["timestamp"] * 1e-3,  # could also use msg['headers']['message-id'] ?
                        "update_id": ts_seconds,  # do we need body_timestamp here???
                        "price": trade["price"],
                        "amount": trade["quantity"]}
                    trade_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, content, ts_seconds)
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
                msg = await message_queue.get()
                symbol = msg['headers']['destination'].replace('/v1/book/', '')
                trading_pair = await LatokenAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    symbol=symbol,
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler,
                    time_synchronizer=self._time_synchronizer)
                body = ujson.loads(msg["body"])
                payload = body["payload"]
                timestamp_ns = time.time_ns()
                timestamp_seconds = timestamp_ns * 1e-9
                content = {
                    "trading_pair": trading_pair,
                    "first_update_id": body["timestamp"],  # could also use msg['headers']['message-id'] ?
                    "update_id": timestamp_seconds,
                    "bids": web_utils.get_book_side(payload["bid"]),
                    "asks": web_utils.get_book_side(payload["ask"])}
                order_book_message = OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp_seconds)
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
                        snapshot_timestamp: int = time.time_ns()
                        ts_seconds = snapshot_timestamp * 1e-9
                        content = {
                            "asks": web_utils.get_book_side(snapshot.pop("ask")),
                            "bids": web_utils.get_book_side(snapshot.pop("bid")),
                            "update_id": ts_seconds,
                            "trading_pair": trading_pair}
                        # content.update(snapshot)
                        snapshot_msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp=ts_seconds)
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().error(
                            f"Unexpected error fetching order book snapshot for {trading_pair}.", exc_info=True)
                        await self._sleep(5.0)
                await self._sleep(CONSTANTS.HOUR)
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
        while True:
            try:
                if self._ws_assistant is None:
                    self._ws_assistant: WSAssistant = await self._api_factory.get_ws_assistant()
                await self._ws_assistant.connect(ws_url=web_utils.ws_url(self._domain),
                                                 ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

                msg_out = stomper.Frame()
                msg_out.cmd = "CONNECT"
                msg_out.headers.update({
                    "accept-version": "1.1",
                    "heart-beat": "0,0"
                })
                connect_request: WSRequest = WSRequest(payload=msg_out.pack(), is_auth_required=True)
                await self._ws_assistant.send(connect_request)
                _ = await self._ws_assistant.receive()
                await self._subscribe_channels(self._ws_assistant)

                async for ws_response in self._ws_assistant.iter_messages():
                    msg_in = stomper.Frame()
                    data = msg_in.unpack(ws_response.data.decode())

                    event_type = int(data['headers']['subscription'].split('_')[0])

                    if event_type == CONSTANTS.SUBSCRIPTION_ID_BOOKS:
                        self._message_queue[CONSTANTS.DIFF_EVENT_TYPE].put_nowait(data)
                    elif event_type == CONSTANTS.SUBSCRIPTION_ID_TRADES:
                        self._message_queue[CONSTANTS.TRADE_EVENT_TYPE].put_nowait(data)
                    else:
                        self.logger().error(f"Unsubscribed id {event_type} packet received {msg_in}")

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(5.0)
            finally:
                self._ws_assistant and await self._ws_assistant.disconnect()

    async def get_snapshot(
            self,
            trading_pair: str,
            limit: int = CONSTANTS.SNAPSHOT_LIMIT_SIZE) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved
        :param limit: the depth of the order book to retrieve

        :return: the response from the exchange (JSON dictionary)
        """
        params = {}
        if limit != 0:
            params["limit"] = str(limit)

        symbol = await self.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer)

        data = await web_utils.api_request(
            path=f"{CONSTANTS.BOOK_PATH_URL}/{symbol}",
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            params=params,
            method=RESTMethod.GET,
            return_err=False,
            limit_id=CONSTANTS.BOOK_PATH_URL
        )

        return data

    async def _subscribe_channels(self, client: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param client: the websocket assistant used to connect to the exchange
        """
        try:
            subscriptions = []
            for trading_pair in self._trading_pairs:
                symbol = await self.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair,
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler,
                    time_synchronizer=self._time_synchronizer)

                path_params = {'symbol': symbol}
                msg_subscribe_books = stomper.subscribe(CONSTANTS.BOOK_STREAM.format(**path_params),
                                                        f"{CONSTANTS.SUBSCRIPTION_ID_BOOKS}_{trading_pair}", ack="auto")
                msg_subscribe_trades = stomper.subscribe(CONSTANTS.TRADES_STREAM.format(**path_params),
                                                         f"{CONSTANTS.SUBSCRIPTION_ID_TRADES}_{trading_pair}",
                                                         ack="auto")

                subscriptions.append(client.subscribe(WSRequest(payload=msg_subscribe_books)))
                subscriptions.append(client.subscribe(WSRequest(payload=msg_subscribe_trades)))

            _ = await safe_gather(*subscriptions)

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
    async def _get_last_traded_price(cls,
                                     trading_pair: str,
                                     domain: str,
                                     api_factory: WebAssistantsFactory,
                                     throttler: AsyncThrottler,
                                     time_synchronizer: TimeSynchronizer) -> float:
        symbol = await cls.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair, domain=domain, throttler=throttler)
        resp_json = await web_utils.api_request(
            path=f"{CONSTANTS.TICKER_PATH_URL}/{symbol}",
            api_factory=api_factory,
            throttler=throttler,
            time_synchronizer=time_synchronizer,
            domain=domain,
            method=RESTMethod.GET,
            return_err=True,
            limit_id=CONSTANTS.TICKER_PATH_URL)
        return float(resp_json["lastPrice"])

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
            tickers = await web_utils.api_request(
                path=CONSTANTS.TICKER_PATH_URL,
                api_factory=api_factory,
                throttler=throttler,
                time_synchronizer=time_synchronizer,
                domain=domain,
                method=RESTMethod.GET,
                return_err=True)

            for ticker in tickers:
                trading_pair = ticker["symbol"].replace('/', '-')
                # if trading_pair in cls._trading_pairs: # fix this!
                mapping[f"{ticker['baseCurrency']}/{ticker['quoteCurrency']}"] = trading_pair

        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({ex})")

        cls._trading_pair_symbol_map[domain] = mapping
