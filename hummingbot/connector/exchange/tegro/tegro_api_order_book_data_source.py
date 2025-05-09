import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_web_utils
from hummingbot.connector.exchange.tegro.tegro_order_book import TegroOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange


class TegroAPIOrderBookDataSource(OrderBookTrackerDataSource):
    FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 2
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'TegroExchange',
                 api_factory: WebAssistantsFactory,
                 domain: Optional[str] = CONSTANTS.DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self.trading_pairs = trading_pairs
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain: Optional[str] = domain
        self._api_factory = api_factory

    @property
    def chain_id(self):
        return self._connector._chain

    @property
    def chain(self):
        chain = 8453
        if self._domain.endswith("_testnet"):
            chain = CONSTANTS.TESTNET_CHAIN_IDS[self.chain_id]
        elif self._domain == "tegro":
            chain_id = CONSTANTS.DEFAULT_CHAIN
            # In this case tegro is default to base mainnet
            chain = CONSTANTS.MAINNET_CHAIN_IDS[chain_id]
        return chain

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        data = await self.initialize_verified_market()
        params = {
            "chain_id": self.chain,
            "market_id": data["id"],
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=tegro_web_utils.public_rest_url(CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )
        return data

    async def initialize_verified_market(self):
        data = await self.initialize_market_list()
        id = []
        for trading_pair in self._trading_pairs:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        for market in data:
            if market["chainId"] == self.chain and market["symbol"] == symbol:
                id.append(market)
        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url = tegro_web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL.format(
                self.chain, id[0]["id"]), self._domain),
            method=RESTMethod.GET,
            is_auth_required = False,
            throttler_limit_id = CONSTANTS.EXCHANGE_INFO_PATH_URL,
        )

    async def initialize_market_list(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            method=RESTMethod.GET,
            params={
                "page": 1,
                "sort_order": "desc",
                "page_size": 20,
                "verified": "true"
            },
            url = tegro_web_utils.public_rest_url(CONSTANTS.MARKET_LIST_PATH_URL.format(self.chain), self._domain),
            is_auth_required = False,
            throttler_limit_id = CONSTANTS.MARKET_LIST_PATH_URL,
        )

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            market_data = await self.initialize_market_list()
            param: str = self._process_market_data(market_data)

            payload = {
                "action": "subscribe",
                "channelId": param
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

    def _process_market_data(self, market_data):
        symbol = ""
        for market in market_data:
            s = market["symbol"]
            symb = s.split("_")
            new_symbol = f"{symb[0]}-{symb[1]}"
            if new_symbol in self._trading_pairs:
                address = str(market["base_contract_address"])
                symbol = f"{self.chain}/{address}"
                break
        return symbol

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=tegro_web_utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = TegroOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["data"]["symbol"])
            trade_message = TegroOrderBook.trade_message_from_exchange(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["data"]["symbol"])
            order_book_message: OrderBookMessage = TegroOrderBook.diff_message_from_exchange(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)
        return

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "action" in event_message:
            event_channel = event_message.get("action")
            if event_channel == CONSTANTS.TRADE_EVENT_TYPE:
                channel = self._trade_messages_queue_key
            if event_channel == CONSTANTS.DIFF_EVENT_TYPE:
                channel = self._diff_messages_queue_key
        return channel
