import asyncio
from typing import Any, Dict, Optional

from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_web_utils as web_utils,
)
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class KucoinAPIUserStreamDataSource(UserStreamTrackerDataSource):

    def __init__(self,
                 auth: KucoinAuth,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None, ):
        super().__init__()
        self._auth: KucoinAuth = auth
        self._time_synchronizer = time_synchronizer
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth,
        )
        self._last_ws_message_sent_timestamp = 0
        self._ping_interval = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        rest_assistant = await self._api_factory.get_rest_assistant()
        connection_info = await rest_assistant.execute_request(
            url=web_utils.rest_url(path_url=CONSTANTS.PRIVATE_WS_DATA_PATH_URL, domain=self._domain),
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.PRIVATE_WS_DATA_PATH_URL,
            is_auth_required=True,
        )

        ws_url = connection_info["data"]["instanceServers"][0]["endpoint"]
        self._ping_interval = int(int(connection_info["data"]["instanceServers"][0]["pingInterval"]) * 0.8 * 1e-3)
        token = connection_info["data"]["token"]

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=f"{ws_url}?token={token}", message_timeout=self._ping_interval)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            orders_change_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": "/spotMarket/tradeOrders",
                "privateChannel": True,
                "response": False,
            }
            subscribe_order_change_request: WSJSONRequest = WSJSONRequest(payload=orders_change_payload)

            balance_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": "/account/balance",
                "privateChannel": True,
                "response": False,
            }
            subscribe_balance_request: WSJSONRequest = WSJSONRequest(payload=balance_payload)

            await ws.send(subscribe_order_change_request)
            await ws.send(subscribe_balance_request)

            self._last_ws_message_sent_timestamp = self._time()
            self.logger().info("Subscribed to private order changes and balance updates channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                seconds_until_next_ping = self._ping_interval - (self._time() - self._last_ws_message_sent_timestamp)
                await asyncio.wait_for(
                    super()._process_websocket_messages(
                        websocket_assistant=websocket_assistant, queue=queue),
                    timeout=seconds_until_next_ping)
            except asyncio.TimeoutError:
                payload = {
                    "id": web_utils.next_message_id(),
                    "type": "ping",
                }
                ping_request = WSJSONRequest(payload=payload)
                self._last_ws_message_sent_timestamp = self._time()
                await websocket_assistant.send(request=ping_request)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if (len(event_message) > 0
                and event_message.get("type") == "message"
                and event_message.get("subject") in [CONSTANTS.ORDER_CHANGE_EVENT_TYPE, CONSTANTS.BALANCE_EVENT_TYPE]):
            queue.put_nowait(event_message)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
