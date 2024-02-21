import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bitrue import bitrue_constants as CONSTANTS, bitrue_web_utils as web_utils
from hummingbot.connector.exchange.bitrue.bitrue_order_book import BitrueOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitrue.bitrue_exchange import BitrueExchange


class BitrueAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "BitrueExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs=trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory
        self._message_id_generator = NonceCreator.for_microseconds()
        self._last_connection_check_message_sent = -1
        self._diff_messages_queue_key = CONSTANTS.ORDERBOOK_CHANNEL_SUFFIX

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_ticker(self, trading_pair: str) -> OrderBookMessage:
        ticker_data = await self._get_ticker_data(trading_pair=trading_pair)
        ticker_timestamp: float = self._time()
        update_id = int(ticker_timestamp * 1e3)
        ticker_msg: OrderBookMessage = BitrueOrderBook.ticker_message_from_rest_endpoint(
            msg=ticker_data,
            timestamp=ticker_timestamp,
            metadata={"trading_pair": trading_pair, "update_id": update_id},
        )
        return ticker_msg

    async def _get_ticker_data(self, trading_pair: str) -> Dict[str, Any]:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"symbol": symbol}
        rest_assistant = await self._api_factory.get_rest_assistant()
        ticker_result = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.TICKER_BOOK_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TICKER_BOOK_PATH_URL_SINGLE_SYMBOL_LIMIT_ID,
        )
        return ticker_result

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "limit": "1000",
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
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                params = {
                    "cb_id": symbol.lower(),
                    "channel": f"{CONSTANTS.ORDERBOOK_CHANNEL_PREFIX}"
                    f"{symbol.lower()}{CONSTANTS.ORDERBOOK_CHANNEL_SUFFIX}",
                }
                payload = {"event": "sub", "params": params}
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)
                await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTIONS_RATE_LIMIT):
            await ws.connect(ws_url=CONSTANTS.WSS_PUBLIC_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = self._time()
        snapshot_msg: OrderBookMessage = BitrueOrderBook.snapshot_message_from_exchange(
            snapshot, snapshot_timestamp, metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol = (
            raw_message["channel"]
            .replace(CONSTANTS.ORDERBOOK_CHANNEL_PREFIX, "")
            .replace(CONSTANTS.ORDERBOOK_CHANNEL_SUFFIX, "")
        )
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol.upper())
        snapshot_msg: OrderBookMessage = self.snapshot_message_from_exchange(
            msg=raw_message,
            metadata={"trading_pair": trading_pair},
        )
        message_queue.put_nowait(snapshot_msg)
        # self._last_order_book_message_latency = self._time() - timestamp

    def snapshot_message_from_exchange(self, msg: Dict[str, Any], metadata: Optional[Dict] = None) -> OrderBookMessage:

        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
        msg_ts = msg["ts"] * 1e-3
        content = {
            "trading_pair": msg["trading_pair"],
            "update_id": msg["ts"],
            "bids": msg["tick"].get("buys", []),
            "asks": msg["tick"].get("asks", []),
        }

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp=msg_ts)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = event_message.get("channel", "")
        retval = ""
        if channel.endswith(self._diff_messages_queue_key) and "tick" in event_message:
            retval = self._diff_messages_queue_key
        return retval

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        await super()._process_message_for_unknown_channel(
            event_message=event_message, websocket_assistant=websocket_assistant
        )
        if "ping" in event_message:
            # For Bitrue we consider receiving the ping message as indication the websocket is still healthy
            pong_request = WSJSONRequest(payload={"pong": event_message["ping"]})
            await websocket_assistant.send(request=pong_request)

    async def _send_connection_check_message(self, websocket_assistant: WSAssistant):
        self._connection_check_response_event.set()

    def _is_message_response_to_connection_check(self, event_message: Dict[str, Any]) -> bool:
        return False
