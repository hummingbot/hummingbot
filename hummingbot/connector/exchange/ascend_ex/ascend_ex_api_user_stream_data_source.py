import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import AscendExExchange


class AscendExAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: AscendExAuth,
        trading_pairs: List[str],
        connector: "AscendExExchange",
        api_factory: WebAssistantsFactory,
    ):
        super().__init__()
        self._ascend_ex_auth: AscendExAuth = auth
        self._api_factory = api_factory
        self._trading_pairs = trading_pairs or []
        self._connector = connector
        self._last_ws_message_sent_timestamp = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        group_id = self._connector.ascend_ex_group_id
        headers = self._ascend_ex_auth.get_auth_headers(CONSTANTS.STREAM_PATH_URL)
        ws_url = f"{CONSTANTS.PRIVATE_WS_URL.format(group_id=group_id)}/{CONSTANTS.STREAM_PATH_URL}"

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ws_headers=headers)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            payload = {"op": CONSTANTS.SUB_ENDPOINT_NAME, "ch": "order:cash"}
            subscribe_request: WSJSONRequest = WSJSONRequest(payload)

            await websocket_assistant.send(subscribe_request)

            self._last_ws_message_sent_timestamp = self._time()
            self.logger().info("Subscribed to private order changes and balance updates channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if data is not None:  # data will be None when the websocket is disconnected
                await self._process_event_message(
                    event_message=data, queue=queue, websocket_assistant=websocket_assistant
                )

    async def _process_event_message(
        self, event_message: Dict[str, Any], queue: asyncio.Queue, websocket_assistant: WSAssistant
    ):
        if len(event_message) > 0:
            message_type = event_message.get("m")
            if message_type == "ping":
                pong_payloads = {"op": "pong"}
                pong_request = WSJSONRequest(payload=pong_payloads)
                await websocket_assistant.send(request=pong_request)
            elif message_type == CONSTANTS.ORDER_CHANGE_EVENT_TYPE and event_message.get("ac") == "CASH":
                queue.put_nowait(event_message)
