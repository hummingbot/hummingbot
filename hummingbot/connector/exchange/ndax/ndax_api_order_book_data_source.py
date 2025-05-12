import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_web_utils as web_utils
from hummingbot.connector.exchange.ndax.ndax_order_book import NdaxOrderBook
from hummingbot.connector.exchange.ndax.ndax_order_book_message import NdaxOrderBookEntry
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ndax.ndax_exchange import NdaxExchange


class NdaxAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(
        self,
        connector: "NdaxExchange",
        api_factory: WebAssistantsFactory,
        trading_pairs: Optional[List[str]] = None,
        domain: Optional[str] = None,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._throttler = api_factory.throttler
        self._domain: Optional[str] = domain
        self._snapshot_messages_queue_key = CONSTANTS.WS_ORDER_BOOK_CHANNEL
        self._diff_messages_queue_key = CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT
        self._trade_messages_queue_key = CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, any]:
        """Retrieves entire orderbook snapshot of the specified trading pair via the REST API.

        Args:
            trading_pair (str): Trading pair of the particular orderbook.
            domain (str): The label of the variant of the connector that is being used.
            throttler (AsyncThrottler): API-requests throttler to use.

        Returns:
            Dict[str, any]: Parsed API Response.
        """
        params = {
            "OMSId": 1,
            "InstrumentId": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "Depth": 200,
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        response_ls = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(CONSTANTS.ORDER_BOOK_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_URL,
        )
        return response_ls

    async def _connected_websocket_assistant(self) -> NdaxWebSocketAdaptor:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        url = CONSTANTS.WSS_URLS.get(self._domain or "ndax_main")
        await ws.connect(ws_url=url)
        return NdaxWebSocketAdaptor(ws)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Periodically polls for orderbook snapshots using the REST API.
        """
        snapshot: Dict[str:Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_message: OrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
            msg={"data": snapshot}, timestamp=time.time(), metadata={"trading_pair": trading_pair}
        )
        return snapshot_message

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                payload = {
                    "OMSId": 1,
                    "InstrumentId": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                    "Depth": 200,
                }

                await ws.send_request(endpoint_name=CONSTANTS.WS_ORDER_BOOK_CHANNEL, payload=payload)
            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.websocket.iter_messages():
            data: Dict[str, Any] = ws_response.data
            if data is not None:  # data will be None when the websocket is disconnected
                channel: str = self._channel_originating_message(event_message=data)
                valid_channels = self._get_messages_queue_keys()
                if channel in valid_channels:
                    self._message_queue[channel].put_nowait(data)
                else:
                    await self._process_message_for_unknown_channel(
                        event_message=data, websocket_assistant=websocket_assistant
                    )

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        payload = NdaxWebSocketAdaptor.payload_from_message(raw_message)
        msg_data: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry) for entry in payload]
        msg_timestamp: int = int(time.time() * 1e3)
        msg_product_code: int = msg_data[0].productPairCode
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=msg_product_code)
        order_book_message: OrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
            {"data": msg_data}, msg_timestamp, {"trading_pair": trading_pair}
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        payload = NdaxWebSocketAdaptor.payload_from_message(raw_message)
        msg_data: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry) for entry in payload]
        msg_timestamp: int = int(time.time() * 1e3)
        msg_product_code: int = msg_data[0].productPairCode
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=msg_product_code)
        order_book_message: OrderBookMessage = NdaxOrderBook.diff_message_from_exchange(
            {"data": msg_data}, msg_timestamp, {"trading_pair": trading_pair}
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        msg_event: str = NdaxWebSocketAdaptor.endpoint_from_message(event_message)
        if msg_event == CONSTANTS.WS_ORDER_BOOK_CHANNEL:
            return self._snapshot_messages_queue_key
        elif msg_event == CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT:
            return self._diff_messages_queue_key
