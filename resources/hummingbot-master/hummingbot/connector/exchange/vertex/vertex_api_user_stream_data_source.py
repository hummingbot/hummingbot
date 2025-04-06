import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.vertex import (
    vertex_constants as CONSTANTS,
    vertex_utils as utils,
    vertex_web_utils as web_utils,
)
from hummingbot.connector.exchange.vertex.vertex_auth import VertexAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.vertex.vertex_exchange import VertexExchange


class VertexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(
        self,
        auth: VertexAuth,
        trading_pairs: List[str],
        connector: "VertexExchange",
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        api_factory: Optional[WebAssistantsFactory] = None,
        throttler: Optional[AsyncThrottler] = None,
    ):
        super().__init__()
        self._connector = connector
        self._auth: VertexAuth = auth
        self._trading_pairs = trading_pairs
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)
        self._ping_interval = 0
        self._last_ws_message_sent_timestamp = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws_url = f"{CONSTANTS.WS_SUBSCRIBE_URLS[self._domain]}"
        self._ping_interval = CONSTANTS.HEARTBEAT_TIME_INTERVAL

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, message_timeout=self._ping_interval)
        return ws

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

                fill_payload = {
                    "method": CONSTANTS.WS_SUBSCRIBE_METHOD,
                    "stream": {
                        "type": CONSTANTS.FILL_EVENT_TYPE,
                        "product_id": product_id,
                        "subaccount": self._auth.sender_address,
                    },
                    "id": product_id,
                }
                position_change_payload = {
                    "method": CONSTANTS.WS_SUBSCRIBE_METHOD,
                    "stream": {
                        "type": CONSTANTS.POSITION_CHANGE_EVENT_TYPE,
                        "product_id": product_id,
                        "subaccount": self._auth.sender_address,
                    },
                    "id": product_id,
                }

                subscribe_fill_request: WSJSONRequest = WSJSONRequest(payload=fill_payload)
                subscribe_position_change_request: WSJSONRequest = WSJSONRequest(payload=position_change_payload)
                await websocket_assistant.send(subscribe_fill_request)
                await websocket_assistant.send(subscribe_position_change_request)

                self._last_ws_message_sent_timestamp = self._time()

                self.logger().info(f"Subscribed to subaccount fill and position change channels of {trading_pair}...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to trading and order book stream...", exc_info=True
            )
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                seconds_until_next_ping = self._ping_interval - (self._time() - self._last_ws_message_sent_timestamp)
                await asyncio.wait_for(
                    super()._process_websocket_messages(websocket_assistant=websocket_assistant, queue=queue),
                    timeout=seconds_until_next_ping,
                )
            except asyncio.TimeoutError:
                ping_time = self._time()
                await websocket_assistant.ping()
                self._last_ws_message_sent_timestamp = ping_time

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if (
            len(event_message) > 0
            and "type" in event_message
            and event_message.get("type") in [CONSTANTS.POSITION_CHANGE_EVENT_TYPE, CONSTANTS.FILL_EVENT_TYPE]
        ):
            queue.put_nowait(event_message)
