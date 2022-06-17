import asyncio
import copy
import logging
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

from bidict import bidict

import hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_utils as utils
import hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.coinflex_perpetual.constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class CoinflexPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _cfpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
            self,
            trading_pairs: List[str] = None,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            throttler: Optional[AsyncThrottler] = None,
            api_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__(trading_pairs)
        self._domain = domain
        self._throttler = throttler
        self._api_factory: WebAssistantsFactory = api_factory or web_utils.build_api_factory(throttler=self._throttler)
        self._funding_info: Dict[str, FundingInfo] = {}

        self._message_queue: Dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)

    @property
    def funding_info(self) -> Dict[str, FundingInfo]:
        return copy.deepcopy(self._funding_info)

    def is_funding_info_initialized(self) -> bool:
        return all(trading_pair in self._funding_info for trading_pair in self._trading_pairs)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cfpobds_logger is None:
            cls._cfpobds_logger = logging.getLogger(__name__)
        return cls._cfpobds_logger

    @classmethod
    async def get_last_traded_prices(cls,
                                     trading_pairs: List[str],
                                     domain: str = CONSTANTS.DEFAULT_DOMAIN,
                                     api_factory: Optional[WebAssistantsFactory] = None,
                                     throttler: Optional[AsyncThrottler] = None) -> Dict[str, float]:
        """
        Return a dictionary the trading_pair as key and the current price as value for each trading pair passed as
        parameter
        :param trading_pairs: list of trading pairs to get the prices for
        :param domain: which CoinFLEX domain we are connecting to (the default value is 'com')
        :param api_factory: the instance of the web assistant factory to be used when doing requests to the server.
        If no instance is provided then a new one will be created.
        :param throttler: the instance of the throttler to use to limit request to the server. If it is not specified
        the function will create a new one.
        :return: Dictionary of associations between token pair and its latest price
        """

        resp = await web_utils.api_request(
            path=CONSTANTS.TICKER_PRICE_CHANGE_URL,
            api_factory=api_factory,
            throttler=throttler,
            domain=domain,
            method=RESTMethod.GET,
        )

        results = {}

        for t_pair in trading_pairs:
            symbol = await cls.convert_to_exchange_trading_pair(
                hb_trading_pair=t_pair,
                domain=domain,
                throttler=throttler)
            matched_ticker = [t for t in resp if t.get("marketCode") == symbol]
            if not (len(matched_ticker) and "last" in matched_ticker[0]):
                raise IOError(f"Error fetching last traded prices for {t_pair}. "
                              f"Response: {resp}.")
            results[t_pair] = float(matched_ticker[0]["last"])

        return results

    @classmethod
    def trading_pair_symbol_map_ready(cls, domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized
        :param domain: the domain of the exchange being used
        :return: True if the mapping has been initialized, False otherwise
        """
        return domain in cls._trading_pair_symbol_map and len(cls._trading_pair_symbol_map[domain]) > 0

    @classmethod
    async def trading_pair_symbol_map(
            cls,
            domain: Optional[str] = CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None
    ):
        """
        Returns the internal map used to translate trading pairs from and to the exchange notation.
        In general this should not be used. Instead call the methods `convert_to_exchange_trading_pair` and
        `convert_from_exchange_trading_pair`
        :param domain: the domain of the exchange being used
        :param api_factory: the web assistant factory to use in case the symbols information has to be requested
        :param throttler: the throttler instance to use in case the symbols information has to be requested
        :return: bidirectional mapping between trading pair exchange notation and client notation
        """
        if not cls.trading_pair_symbol_map_ready(domain=domain):
            async with cls._mapping_initialization_lock:
                # Check condition again (could have been initialized while waiting for the lock to be released)
                if not cls.trading_pair_symbol_map_ready(domain=domain):
                    await cls.init_trading_pair_symbols(
                        domain=domain,
                        api_factory=api_factory,
                        throttler=throttler)

        return cls._trading_pair_symbol_map[domain]

    @classmethod
    async def init_trading_pair_symbols(
            cls,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None):
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation
        """
        mapping = bidict()

        try:
            data = await web_utils.api_request(
                path=CONSTANTS.EXCHANGE_INFO_URL,
                api_factory=api_factory,
                throttler=throttler,
                domain=domain,
                method=RESTMethod.GET,
            )

            for symbol_data in filter(utils.is_exchange_information_valid, data["data"]):
                mapping[symbol_data["marketCode"]] = f"{symbol_data['contractValCurrency']}-{symbol_data['marginCurrency']}"
        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")

        cls._trading_pair_symbol_map[domain] = mapping

    @staticmethod
    async def fetch_trading_pairs(
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            throttler: Optional[AsyncThrottler] = None,
            api_factory: Optional[WebAssistantsFactory] = None) -> List[str]:
        """
        Returns a list of all known trading pairs enabled to operate with
        :param domain: the domain of the exchange being used
        :return: list of trading pairs in client notation
        """
        mapping = await CoinflexPerpetualAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            throttler=throttler,
            api_factory=api_factory,
        )
        return list(mapping.values())

    @classmethod
    async def convert_from_exchange_trading_pair(
            cls,
            exchange_trading_pair: str,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            throttler: Optional[AsyncThrottler] = None,
            api_factory: Optional[WebAssistantsFactory] = None) -> str:

        symbol_map = await cls.trading_pair_symbol_map(
            domain=domain,
            throttler=throttler,
            api_factory=api_factory)
        try:
            pair = symbol_map[exchange_trading_pair]
        except KeyError:
            raise ValueError(f"There is no symbol mapping for exchange trading pair {exchange_trading_pair}")

        return pair

    @classmethod
    async def convert_to_exchange_trading_pair(
            cls,
            hb_trading_pair: str,
            domain=CONSTANTS.DEFAULT_DOMAIN,
            throttler: Optional[AsyncThrottler] = None,
            api_factory: Optional[WebAssistantsFactory] = None) -> str:

        symbol_map = await cls.trading_pair_symbol_map(
            domain=domain,
            throttler=throttler,
            api_factory=api_factory)
        try:
            symbol = symbol_map.inverse[hb_trading_pair]
        except KeyError:
            raise ValueError(f"There is no symbol mapping for trading pair {hb_trading_pair}")

        return symbol

    async def get_snapshot(
            self,
            trading_pair: str,
            limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved
        :param limit: the depth of the order book to retrieve

        :return: the response from the exchange (JSON dictionary)
        """
        exchange_trading_pair = await self.convert_to_exchange_trading_pair(
            hb_trading_pair=trading_pair,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler)

        response = await web_utils.api_request(
            path=CONSTANTS.SNAPSHOT_REST_URL.format(exchange_trading_pair, limit),
            api_factory=self._api_factory,
            throttler=self._throttler,
            domain=self._domain,
            method=RESTMethod.GET,
            limit_id=CONSTANTS.SNAPSHOT_REST_URL,
        )

        if not ("data" in response and
                "event" in response and
                len(response.get("data", [{}])[0].get("asks", []))):
            raise IOError(f"Error fetching market snapshot for {trading_pair}. "
                          f"Response: {response}.")
        return response["data"][0]

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Creates a local instance of the exchange order book for a particular trading pair
        :param trading_pair: the trading pair for which the order book has to be retrieved
        :return: a local copy of the current order book in the exchange
        """
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair, 1000)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = self.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def _get_funding_info_from_exchange(self, trading_pair: str) -> FundingInfo:
        """
        Fetches the funding information of the given trading pair from the exchange REST API. Parses and returns the
        respsonse as a FundingInfo data object.

        :param trading_pair: Trading pair of which its Funding Info is to be fetched
        :type trading_pair: str
        :return: Funding Information of the given trading pair
        :rtype: FundingInfo
        """
        resp = await web_utils.api_request(
            path=CONSTANTS.TICKER_PRICE_CHANGE_URL,
            api_factory=self._api_factory,
            throttler=self._throttler,
            domain=self._domain,
            method=RESTMethod.GET,
        )

        symbol = await self.convert_to_exchange_trading_pair(
            hb_trading_pair=trading_pair,
            domain=self._domain,
            throttler=self._throttler)

        matched_tickers = [t for t in resp if t.get("marketCode") == symbol]

        if not (len(matched_tickers) and "markPrice" in matched_tickers[0]):
            raise IOError(f"Error fetching funding for {trading_pair}. "
                          f"Response: {resp}.")

        params = {"instrumentId": symbol}

        try:
            data = await web_utils.api_request(
                path=CONSTANTS.MARK_PRICE_URL,
                api_factory=self._api_factory,
                throttler=self._throttler,
                domain=self._domain,
                params=params,
                method=RESTMethod.GET)
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            self.logger().exception(f"There was a problem getting funding info from exchange. Error: {exception}")
            return None

        matched_ticker = matched_tickers[0]
        last_funding = data[0]
        next_fund_ts = datetime.strptime(last_funding["timestamp"], "%Y-%m-%d %H:%M:%S").timestamp() + CONSTANTS.ONE_HOUR

        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(matched_ticker["last"]),
            mark_price=Decimal(matched_ticker["markPrice"]),
            next_funding_utc_timestamp=next_fund_ts,
            rate=Decimal(last_funding["fundingRate"]),
        )

        return funding_info

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Returns the FundingInfo of the specified trading pair. If it does not exist, it will query the REST API.
        """
        if trading_pair not in self._funding_info:
            self._funding_info[trading_pair] = await self._get_funding_info_from_exchange(trading_pair)
        return self._funding_info[trading_pair]

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            trade_params = []
            depth_params = []
            for trading_pair in self._trading_pairs:
                symbol = await self.convert_to_exchange_trading_pair(
                    hb_trading_pair=trading_pair,
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                trade_params.append(f"trade:{symbol}")
                depth_params.append(f"depth:{symbol}")

            payload: Dict[str, str] = {
                "op": "subscribe",
                "args": trade_params + depth_params,
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._api_factory.get_ws_assistant()
                await ws.connect(ws_url=web_utils.websocket_url(domain=self._domain),
                                 ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                await self._subscribe_channels(ws)

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if "success" in data:
                        continue
                    event_type = data.get("table")
                    if event_type in [CONSTANTS.DIFF_STREAM_ID, CONSTANTS.TRADE_STREAM_ID]:
                        self._message_queue[event_type].put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Websocket connection. Retrying after 30 seconds...", exc_info=True
                )
                await self._sleep(30.0)
            finally:
                ws and await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Reads the order diffs events queue. For each event creates a diff message instance and adds it to the
        output queue
        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created diff messages
        """
        message_queue = self._message_queue[CONSTANTS.DIFF_STREAM_ID]
        while True:
            try:
                json_msg = await message_queue.get()
                if "success" in json_msg:
                    continue
                trading_pair = await CoinflexPerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                    exchange_trading_pair=json_msg["data"][0]["instrumentId"],
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                order_book_message: OrderBookMessage = self.diff_message_from_exchange(
                    json_msg, time.time(), {"trading_pair": trading_pair})
                output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public order book updates from exchange")

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Reads the trade events queue. For each event creates a trade message instance and adds it to the output queue
        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created trade messages
        """
        message_queue = self._message_queue[CONSTANTS.TRADE_STREAM_ID]
        while True:
            try:
                message_data = await message_queue.get()

                if "success" in message_data:
                    continue

                trades_data = message_data.get("data", [])

                for json_msg in trades_data:
                    trading_pair = await CoinflexPerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                        exchange_trading_pair=json_msg["marketCode"],
                        domain=self._domain,
                        api_factory=self._api_factory,
                        throttler=self._throttler)
                    trade_msg: OrderBookMessage = self.trade_message_from_exchange(
                        json_msg, {"trading_pair": trading_pair})
                    output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public trade updates from exchange")

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
                        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair=trading_pair)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = self.snapshot_message_from_exchange(
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
                delta = CONSTANTS.ONE_HOUR - time.time() % CONSTANTS.ONE_HOUR
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds...", exc_info=True
                )
                await self._sleep(5.0)

    def snapshot_message_from_exchange(self,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": int(msg["timestamp"]),
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp)

    def diff_message_from_exchange(self,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a diff message with the changes in the order book received from the exchange
        :param msg: the changes in the order book
        :param timestamp: the timestamp of the difference
        :param metadata: a dictionary with extra information to add to the difference data
        :return: a diff message with the changes in the order book notified by the exchange
        """
        data = msg["data"][0]
        if metadata:
            data.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": data["trading_pair"],
            "first_update_id": int(data["seqNum"]),
            "update_id": int(data["timestamp"]),
            "bids": data["bids"],
            "asks": data["asks"]
        }, timestamp=timestamp)

    def trade_message_from_exchange(self, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
        ts = int(msg["timestamp"])
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.SELL.value) if msg["side"] == TradeType.SELL.name.upper() else float(TradeType.BUY.value),
            "trade_id": msg["tradeId"],
            "update_id": ts,
            "price": msg["price"],
            "amount": msg["quantity"]
        }, timestamp=ts * 1e-3)
