from typing import TYPE_CHECKING, Optional

from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
        ArchitectPerpetualDerivative,
    )


class ArchitectPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(
        self,
        auth: ArchitectPerpetualAuth,
        connector: 'ArchitectPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistant: Optional[WSAssistant] = None
        self._connector = connector
        self._listen_for_user_stream_task = None

    async def _connected_websocket_assistant(self) -> WSAssistant:
        websocket_assistant: WSAssistant = await self._api_factory.get_ws_assistant()
        ws_url = web_utils.private_ws_url(domain=self._domain)
        await websocket_assistant.connect(
            ws_url=ws_url,
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE,
            ws_headers={"Authorization": f"Bearer {await self._api_factory.auth.get_token_for_ws_stream()}"}
        )
        self.logger().info(f"Subscribed to private order channels {ws_url}...")
        return websocket_assistant

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass  # no explicit subscription required
