import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_web_utils as web_utils
from hummingbot.connector.exchange.ndax.ndax_order_book import NdaxOrderBook
from hummingbot.connector.exchange.ndax.ndax_order_book_message import NdaxOrderBookEntry
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
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
        self._shared_client = api_factory._connections_factory.get_rest_connection()
        self._throttler = api_factory.throttler
        self._domain: Optional[str] = domain

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
        # orderbook_entries: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry) for entry in response_ls]
        # return {"data": orderbook_entries,
        #         "timestamp": int(time.time() * 1e3)}
        return response_ls

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URLS.get(self._domain or "ndax_main"))
        return ws

    async def _order_book_snapshots(self, trading_pair: str) -> OrderBookMessage:
        """
        Periodically polls for orderbook snapshots using the REST API.
        """
        snapshot: Dict[str:Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_message: OrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
            msg=snapshot, timestamp=snapshot["timestamp"], metadata={"trading_pair": trading_pair}
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
                    "Symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                    "Depth": 200,
                }

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

    # async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
    #     """
    #     Listen for orderbook diffs using WebSocket API.
    #     """
    #     if not len(self._trading_pair_id_map) > 0:
    #         await self.init_trading_pair_ids(self._domain, self._throttler, self._shared_client)

    #     while True:
    #         try:
    #             ws_adaptor: NdaxWebSocketAdaptor = await self._create_websocket_connection()
    #             for trading_pair in self._trading_pairs:
    #                 payload = {
    #                     "OMSId": 1,
    #                     "Symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
    #                     "Depth": 200
    #                 }
    #                 async with self._throttler.execute_task(CONSTANTS.WS_ORDER_BOOK_CHANNEL):
    #                     await ws_adaptor.send_request(endpoint_name=CONSTANTS.WS_ORDER_BOOK_CHANNEL,
    #                                                   payload=payload)
    #             async for raw_msg in ws_adaptor.iter_messages():
    #                 payload = NdaxWebSocketAdaptor.payload_from_raw_message(raw_msg)
    #                 msg_event: str = NdaxWebSocketAdaptor.endpoint_from_raw_message(raw_msg)
    #                 if msg_event in [CONSTANTS.WS_ORDER_BOOK_CHANNEL, CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT]:
    #                     msg_data: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry)
    #                                                           for entry in payload]
    #                     msg_timestamp: int = int(time.time() * 1e3)
    #                     msg_product_code: int = msg_data[0].productPairCode

    #                     content = {"data": msg_data}
    #                     msg_trading_pair: Optional[str] = None

    #                     for trading_pair, instrument_id in self._trading_pair_id_map.items():
    #                         if msg_product_code == instrument_id:
    #                             msg_trading_pair = trading_pair
    #                             break

    #                     if msg_trading_pair:
    #                         metadata = {
    #                             "trading_pair": msg_trading_pair,
    #                             "instrument_id": msg_product_code,
    #                         }

    #                         order_book_message = None
    #                         if msg_event == CONSTANTS.WS_ORDER_BOOK_CHANNEL:
    #                             order_book_message: NdaxOrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
    #                                 msg=content,
    #                                 timestamp=msg_timestamp,
    #                                 metadata=metadata)
    #                         elif msg_event == CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT:
    #                             order_book_message: NdaxOrderBookMessage = NdaxOrderBook.diff_message_from_exchange(
    #                                 msg=content,
    #                                 timestamp=msg_timestamp,
    #                                 metadata=metadata)
    #                         self._last_traded_prices[
    #                             order_book_message.trading_pair] = order_book_message.last_traded_price
    #                         await output.put(order_book_message)

    #         except asyncio.CancelledError:
    #             raise
    #         except Exception:
    #             self.logger().network(
    #                 "Unexpected error with WebSocket connection.",
    #                 exc_info=True,
    #                 app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
    #                                 "Check network connection."
    #             )
    #             if ws_adaptor:
    #                 await ws_adaptor.close()
    #             await self._sleep(30.0)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        payload = NdaxWebSocketAdaptor.payload_from_raw_message(raw_message)
        msg_data: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry) for entry in payload]
        msg_timestamp: int = int(time.time() * 1e3)
        msg_product_code: int = msg_data[0].productPairCode
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=msg_product_code)
        order_book_message: OrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
            msg_data, msg_timestamp, {"trading_pair": trading_pair}
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        payload = NdaxWebSocketAdaptor.payload_from_raw_message(raw_message)
        msg_data: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry) for entry in payload]
        msg_timestamp: int = int(time.time() * 1e3)
        msg_product_code: int = msg_data[0].productPairCode
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=msg_product_code)
        order_book_message: OrderBookMessage = NdaxOrderBook.diff_message_from_exchange(
            msg_data, msg_timestamp, {"trading_pair": trading_pair}
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        msg_event: str = NdaxWebSocketAdaptor.endpoint_from_raw_message(event_message)
        if msg_event == CONSTANTS.WS_ORDER_BOOK_CHANNEL:
            return self._snapshot_messages_queue_key
        elif msg_event == CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT:
            return self._diff_messages_queue_key
