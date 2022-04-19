import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.binance import (
    binance_constants as CONSTANTS,
    binance_utils,
    binance_web_utils as web_utils,
)
from hummingbot.connector.exchange.binance.binance_order_book import BinanceOrderBook
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class BinanceAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    def __init__(self,
                 trading_pairs: List[str],
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__(trading_pairs)
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._time_synchronizer = time_synchronizer
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
        )
        self._order_book_create_function = lambda: OrderBook()

    @staticmethod
    @async_ttl_cache(ttl=2, maxsize=1)
    async def get_all_mid_prices(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> Dict[str, Decimal]:
        """
        Returns the mid price of all trading pairs, obtaining the information from the exchange. This functionality is
        required by the market price strategy.
        :param domain: Domain to use for the connection with the exchange (either "com" or "us"). Default value is "com"
        :return: Dictionary with the trading pair as key, and the mid price as value
        """
        api_factory = web_utils.build_api_factory(domain=domain)
        rest_assistant = await api_factory.get_rest_assistant()
        resp_json = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
        )

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

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
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
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer),
            "limit": "1000"
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

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
                    throttler=self._throttler,
                    time_synchronizer=self._time_synchronizer)
                trade_params.append(f"{symbol.lower()}@trade")
                depth_params.append(f"{symbol.lower()}@depth@100ms")
            payload = {
                "method": "SUBSCRIBE",
                "params": trade_params,
                "id": 1
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

            payload = {
                "method": "SUBSCRIBE",
                "params": depth_params,
                "id": 2
            }
            subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

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
    async def _get_last_traded_price(cls,
                                     trading_pair: str,
                                     api_factory: Optional[WebAssistantsFactory] = None,
                                     throttler: Optional[AsyncThrottler] = None,
                                     domain: Optional[str] = None,
                                     time_synchronizer: Optional[TimeSynchronizer] = None) -> float:
        domain = domain or cls._default_domain()
        throttler = throttler or web_utils.create_throttler()
        api_factory = api_factory or web_utils.build_api_factory(
            throttler=throttler,
            time_synchronizer=time_synchronizer,
            domain=domain,
        )
        params = {
            "symbol": await cls.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair,
                domain=domain,
                api_factory=api_factory,
                throttler=throttler,
                time_synchronizer=time_synchronizer)
        }

        rest_assistant = await api_factory.get_rest_assistant()
        resp_json = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
        )

        return float(resp_json["lastPrice"])

    @classmethod
    def _default_domain(cls):
        return CONSTANTS.DEFAULT_DOMAIN

    @classmethod
    async def _exchange_symbols_and_trading_pairs(
            cls,
            domain: Optional[str] = None,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None) -> Dict[str, str]:
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation
        """
        domain = domain or cls._default_domain()
        api_factory = api_factory or web_utils.build_api_factory(
            throttler=throttler,
            time_synchronizer=time_synchronizer,
            domain=domain,
        )
        mapping = {}
        rest_assistant = await api_factory.get_rest_assistant()

        try:
            data = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=domain),
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            )

            for symbol_data in filter(binance_utils.is_exchange_information_valid, data["symbols"]):
                mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseAsset"],
                                                                            quote=symbol_data["quoteAsset"])

        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")

        return mapping

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL.format(self._domain),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                symbol=raw_message["s"],
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer)
            trade_message = BinanceOrderBook.trade_message_from_exchange(
                raw_message, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                symbol=raw_message["s"],
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer)
            order_book_message: OrderBookMessage = BinanceOrderBook.diff_message_from_exchange(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            event_type = event_message.get("e")
            channel = (self._diff_messages_queue_key if event_type == CONSTANTS.DIFF_EVENT_TYPE
                       else self._trade_messages_queue_key)
        return channel
