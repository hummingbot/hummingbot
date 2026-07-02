from typing import TYPE_CHECKING, Optional

from hummingbot.connector.exchange.lambdaplex import (
    lambdaplex_constants as CONSTANTS,
    lambdaplex_web_utils as web_utils,
)
from hummingbot.connector.exchange.lambdaplex.lambdaplex_auth import LambdaplexAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lambdaplex.lambdaplex_exchange import LambdaplexExchange


class LambdaplexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: LambdaplexAuth,
        connector: 'LambdaplexExchange',
        api_factory: WebAssistantsFactory,
    ):
        super().__init__()
        self._auth = auth
        self._api_factory = api_factory
        self._connector = connector
        self._next_req_id = 1

    async def _connected_websocket_assistant(self) -> WSAssistant:
        websocket_assistant: WSAssistant = await self._api_factory.get_ws_assistant()

        await websocket_assistant.connect(ws_url=web_utils.ws_url())
        await self._authenticate(websocket_assistant)

        return websocket_assistant

    async def _authenticate(self, websocket_assistant: WSAssistant):
        request_id = self._generate_request_id()
        await websocket_assistant.send(
            WSJSONRequest(
                payload={
                    "id": request_id,
                    "method": CONSTANTS.WS_SESSION_LOGON_METHOD,
                },
                is_auth_required=True,
            )
        )
        response = await websocket_assistant.receive()
        message = response.data

        response_id = message.get("id")
        status_code = message.get("status")

        if response_id and int(response_id) == request_id and status_code and int(status_code) == 200:
            self.logger().info("Lambdaplex private WebSocket connection successfully authenticated.")
        else:
            error_message = f"Error authenticating the private websocket connection. Response message {message}"
            self.logger().error(error_message)
            raise ConnectionError(error_message)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        request_id = self._generate_request_id()
        await websocket_assistant.send(
            WSJSONRequest(
                payload={
                    "id": request_id,
                    "method": CONSTANTS.WS_SESSION_SUBSCRIBE_METHOD,
                },
            )
        )
        response = await websocket_assistant.receive()
        message = response.data

        response_id = message.get("id")
        status_code = message.get("status")

        if response_id and int(response_id) == request_id and status_code and int(status_code) == 200:
            self.logger().info("Lambdaplex private WebSocket stream successfully subscribed.")
        else:
            error_message = f"Error subscribing to the private websocket stream. Response message {message}"
            self.logger().error(error_message)
            raise ConnectionError(error_message)

    def _generate_request_id(self) -> int:
        request_id = self._next_req_id
        self._next_req_id += 1
        return request_id
