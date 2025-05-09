import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from hummingbot.connector.utilities.oms_connector import oms_connector_constants as CONSTANTS
from hummingbot.connector.utilities.oms_connector.oms_connector_auth import OMSConnectorAuth
from hummingbot.connector.utilities.oms_connector.oms_connector_web_utils import (
    OMSConnectorURLCreatorBase,
    OMSConnectorWebAssistantsFactory,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.utilities.oms_connector.oms_connector_exchange import OMSExchange


class OMSConnectorAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'OMSExchange',
        api_factory: OMSConnectorWebAssistantsFactory,
        url_provider: OMSConnectorURLCreatorBase,
        oms_id: int,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._auth: OMSConnectorAuth = api_factory.auth
        self._url_provider = url_provider
        self._oms_id = oms_id
        self._nonce_provider = NonceCreator.for_milliseconds()

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _parse_trade_message(self, raw_message: List[Dict[int, Union[int, float]]], message_queue: asyncio.Queue):
        raise NotImplementedError  # OMS connectors do not provide a public trades endpoint

    async def _parse_order_book_diff_message(
        self, raw_message: List[List[Union[int, float]]], message_queue: asyncio.Queue
    ):
        msg_data = raw_message[CONSTANTS.MSG_DATA_FIELD]
        first_row = msg_data[0]
        ts_ms = first_row[CONSTANTS.DIFF_UPDATE_TS_FIELD]
        update_id = self._nonce_provider.get_tracking_nonce(timestamp=ts_ms * 1e-3)
        instrument_id = first_row[CONSTANTS.DIFF_UPDATE_INSTRUMENT_ID_FIELD]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=str(instrument_id))
        bids, asks = self._get_bids_and_asks_from_snapshot(msg_data)

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        diff_message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.DIFF,
            order_book_message_content,
            ts_ms * 1e-3,
        )

        message_queue.put_nowait(diff_message)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        first_row = snapshot_response[0]
        ts_ms = first_row[CONSTANTS.DIFF_UPDATE_TS_FIELD]
        update_id = self._nonce_provider.get_tracking_nonce(timestamp=ts_ms * 1e-3)
        bids, asks = self._get_bids_and_asks_from_snapshot(snapshot_response)

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        snapshot_msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, order_book_message_content, ts_ms)
        return snapshot_msg

    @staticmethod
    def _get_bids_and_asks_from_snapshot(
        snapshot: List[List[Union[int, float]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """OMS connectors do not guarantee that the data is sorted in any way."""
        asks = []
        bids = []
        for row in snapshot:
            update = (row[CONSTANTS.DIFF_UPDATE_PRICE_FIELD], row[CONSTANTS.DIFF_UPDATE_AMOUNT_FIELD])
            if row[CONSTANTS.DIFF_UPDATE_SIDE_FIELD] == CONSTANTS.BUY_ACTION:
                bids.append(update)
            else:
                asks.append(update)
        return bids, asks

    async def _request_order_book_snapshot(self, trading_pair: str) -> List[List[Union[int, float]]]:
        instrument_id = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            CONSTANTS.OMS_ID_FIELD: self._oms_id,
            CONSTANTS.INSTRUMENT_ID_FIELD: int(instrument_id),
            CONSTANTS.DEPTH_FIELD: CONSTANTS.MAX_L2_SNAPSHOT_DEPTH,
        }
        rest_assistant = await self._get_rest_assistant()
        url = self._url_provider.get_rest_url(path_url=CONSTANTS.REST_GET_L2_SNAPSHOT_ENDPOINT)
        resp = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=CONSTANTS.REST_REQ_LIMIT_ID,
            params=params,
            method=RESTMethod.GET,
        )
        return resp

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._ensure_authenticated()
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        url = self._url_provider.get_ws_url()
        await ws.connect(ws_url=url, message_timeout=CONSTANTS.WS_MESSAGE_TIMEOUT)
        return ws

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ensure_authenticated()
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    def _ensure_authenticated(self):
        if not self._auth.initialized:
            raise RuntimeError("The authenticator is not initialized.")

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                instrument_id = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                req_params = {
                    CONSTANTS.OMS_ID_FIELD: self._oms_id,
                    CONSTANTS.INSTRUMENT_ID_FIELD: int(instrument_id),
                    CONSTANTS.DEPTH_FIELD: CONSTANTS.MAX_L2_SNAPSHOT_DEPTH,
                }
                payload = {
                    CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_L2_SUB_ENDPOINT,
                    CONSTANTS.MSG_DATA_FIELD: req_params,
                }
                subscribe_orderbook_request = WSJSONRequest(payload=payload)

                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQ_LIMIT_ID):
                    await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if event_message[CONSTANTS.MSG_TYPE_FIELD] != CONSTANTS.ERROR_MSG_TYPE:
            event_channel = event_message[CONSTANTS.MSG_ENDPOINT_FIELD]
            if event_channel == CONSTANTS.WS_L2_EVENT:
                channel = self._diff_messages_queue_key
        return channel

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        while True:
            try:
                async for ws_response in websocket_assistant.iter_messages():
                    data: Dict[str, Any] = ws_response.data
                    channel: str = self._channel_originating_message(event_message=data)
                    if channel in [self._diff_messages_queue_key, self._trade_messages_queue_key]:
                        self._message_queue[channel].put_nowait(data)
            except asyncio.TimeoutError:
                ping_payload = {
                    CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_PING_REQUEST,
                    CONSTANTS.MSG_DATA_FIELD: {},
                }
                ping_request = WSJSONRequest(payload=ping_payload)
                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_PING_REQUEST):
                    await websocket_assistant.send(request=ping_request)
