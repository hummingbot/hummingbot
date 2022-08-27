import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.exchange.ftx import ftx_constants as CONSTANTS
from hummingbot.connector.exchange.ftx.ftx_auth import FtxAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ftx.ftx_exchange import FtxExchange


class FtxAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: FtxAuth,
            connector: 'FtxExchange',
            api_factory: WebAssistantsFactory):
        super().__init__()
        self._auth: FtxAuth = auth
        self._connector = connector
        self._api_factory = api_factory
        self._last_ws_message_sent_timestamp = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """

        ws: WSAssistant = await self._get_ws_assistant()
        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTION_LIMIT_ID):
            await ws.connect(ws_url=CONSTANTS.FTX_WS_URL)

        payload = {
            "op": "login",
            "args": self._auth.websocket_login_parameters()
        }

        login_request: WSJSONRequest = WSJSONRequest(payload=payload)

        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
            await ws.send(login_request)

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            payload = {
                "op": "subscribe",
                "channel": CONSTANTS.WS_PRIVATE_FILLS_CHANNEL,
            }
            subscribe_fills_request: WSJSONRequest = WSJSONRequest(payload=payload)

            payload = {
                "op": "subscribe",
                "channel": CONSTANTS.WS_PRIVATE_ORDERS_CHANNEL,
            }
            subscribe_orders_request: WSJSONRequest = WSJSONRequest(payload=payload)

            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                await websocket_assistant.send(subscribe_fills_request)
            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_REQUEST_LIMIT_ID):
                await websocket_assistant.send(subscribe_orders_request)

            self._last_ws_message_sent_timestamp = self._time()
            self.logger().info("Subscribed to private fills and orders channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                seconds_until_next_ping = (CONSTANTS.WS_PING_INTERVAL
                                           - (self._time() - self._last_ws_message_sent_timestamp))
                await asyncio.wait_for(super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue),
                    timeout=seconds_until_next_ping)
            except asyncio.TimeoutError:
                payload = {"op": "ping"}
                ping_request = WSJSONRequest(payload=payload)
                self._last_ws_message_sent_timestamp = self._time()
                await websocket_assistant.send(request=ping_request)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        event_type = event_message.get("type")
        error_code = event_message.get("code")
        error_message = event_message.get("msg")
        if (event_type == CONSTANTS.WS_EVENT_ERROR_TYPE
                and error_code == CONSTANTS.WS_EVENT_ERROR_CODE
                and error_message in [
                    CONSTANTS.WS_EVENT_INVALID_LOGIN_MESSAGE,
                    CONSTANTS.WS_EVENT_NOT_LOGGED_IN_MESSAGE]):
            raise IOError(f"Error authenticating the user stream websocket connection "
                          f"(code: {error_code}, message: {error_message})")
        elif (event_type == CONSTANTS.WS_EVENT_UPDATE_TYPE
              and event_message.get("channel") in [
                  CONSTANTS.WS_PRIVATE_ORDERS_CHANNEL,
                  CONSTANTS.WS_PRIVATE_FILLS_CHANNEL]):
            queue.put_nowait(event_message)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
