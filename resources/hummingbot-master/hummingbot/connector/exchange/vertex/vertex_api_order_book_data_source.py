import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.vertex import (
    vertex_constants as CONSTANTS,
    vertex_utils as utils,
    vertex_web_utils as web_utils,
)
from hummingbot.connector.exchange.vertex.vertex_order_book import VertexOrderBook
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.vertex.vertex_exchange import VertexExchange


class VertexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: "VertexExchange",
        api_factory: Optional[WebAssistantsFactory] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
        )
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._last_ws_message_sent_timestamp = 0
        self._ping_interval = 0

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp = utils.convert_timestamp(snapshot["data"]["timestamp"])
        snapshot_msg: OrderBookMessage = VertexOrderBook.snapshot_message_from_exchange_rest(
            snapshot, snapshot_timestamp, metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        product_id = utils.trading_pair_to_product_id(trading_pair, self._connector._exchange_market_info[self._domain])
        params = {
            "type": CONSTANTS.MARKET_LIQUIDITY_REQUEST_TYPE,
            "product_id": product_id,
            "depth": CONSTANTS.ORDER_BOOK_DEPTH,
        }
        rest_assistant = await self._api_factory.get_rest_assistant()

        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.QUERY_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.MARKET_LIQUIDITY_REQUEST_TYPE,
        )
        return data

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = utils.market_to_trading_pair(
            self._connector._exchange_market_info[self._domain][raw_message["product_id"]]["market"]
        )
        metadata = {"trading_pair": trading_pair}
        trade_message: OrderBookMessage = VertexOrderBook.trade_message_from_exchange(raw_message, metadata=metadata)
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = utils.market_to_trading_pair(
            self._connector._exchange_market_info[self._domain][raw_message["product_id"]]["market"]
        )
        metadata = {"trading_pair": trading_pair}
        order_book_message: OrderBookMessage = VertexOrderBook.diff_message_from_exchange(
            raw_message, metadata=metadata
        )
        message_queue.put_nowait(order_book_message)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """

        try:
            for trading_pair in self._trading_pairs:
                product_id = utils.trading_pair_to_product_id(
                    trading_pair, self._connector._exchange_market_info[self._domain]
                )
                trade_payload = {
                    "method": CONSTANTS.WS_SUBSCRIBE_METHOD,
                    "stream": {"type": CONSTANTS.TRADE_EVENT_TYPE, "product_id": product_id},
                    "id": product_id,
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trade_payload)

                order_book_payload = {
                    "method": CONSTANTS.WS_SUBSCRIBE_METHOD,
                    "stream": {"type": CONSTANTS.DIFF_EVENT_TYPE, "product_id": product_id},
                    "id": product_id,
                }
                subscribe_order_book_dif_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

                await websocket_assistant.send(subscribe_trade_request)
                await websocket_assistant.send(subscribe_order_book_dif_request)

                self._last_ws_message_sent_timestamp = self._time()

                self.logger().info(f"Subscribed to public trade and order book diff channels of {trading_pair}...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to trading and order book stream...", exc_info=True
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""

        if "type" in event_message:
            event_channel = event_message.get("type")
            if event_channel == CONSTANTS.TRADE_EVENT_TYPE:
                channel = self._trade_messages_queue_key
            if event_channel == CONSTANTS.DIFF_EVENT_TYPE:
                channel = self._diff_messages_queue_key

        return channel

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        while True:
            try:
                seconds_until_next_ping = self._ping_interval - (self._time() - self._last_ws_message_sent_timestamp)

                await asyncio.wait_for(
                    super()._process_websocket_messages(websocket_assistant=websocket_assistant),
                    timeout=seconds_until_next_ping,
                )
            except asyncio.TimeoutError:
                ping_time = self._time()
                await websocket_assistant.ping()
                self._last_ws_message_sent_timestamp = ping_time

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws_url = f"{CONSTANTS.WS_SUBSCRIBE_URLS[self._domain]}"

        self._ping_interval = CONSTANTS.HEARTBEAT_TIME_INTERVAL

        websocket_assistant: WSAssistant = await self._api_factory.get_ws_assistant()

        await websocket_assistant.connect(ws_url=ws_url, message_timeout=self._ping_interval)

        return websocket_assistant
