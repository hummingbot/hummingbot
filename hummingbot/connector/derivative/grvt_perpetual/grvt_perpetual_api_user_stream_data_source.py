import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GrvtPerpetualDerivative


class GrvtPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: AuthBase,
        trading_pairs: List[str],
        connector: "GrvtPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth: GrvtPerpetualAuth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_request_id = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.private_wss_url(domain=self._domain),
            ws_headers=await self._auth.get_ws_auth_headers(),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            selector = str(self._connector.trading_account_id)
            for stream in [
                CONSTANTS.PRIVATE_WS_CHANNEL_ORDER,
                CONSTANTS.PRIVATE_WS_CHANNEL_STATE,
                CONSTANTS.PRIVATE_WS_CHANNEL_POSITION,
                CONSTANTS.PRIVATE_WS_CHANNEL_FILL,
            ]:
                await websocket_assistant.send(self._subscription_request(stream=stream, selector=selector))
            self.logger().info("Subscribed to GRVT private order, fill, and position channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to GRVT user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("feed") is not None and event_message.get("stream") in {
            CONSTANTS.PRIVATE_WS_CHANNEL_ORDER,
            CONSTANTS.PRIVATE_WS_CHANNEL_STATE,
            CONSTANTS.PRIVATE_WS_CHANNEL_POSITION,
            CONSTANTS.PRIVATE_WS_CHANNEL_FILL,
        }:
            queue.put_nowait(event_message)

    def _subscription_request(self, stream: str, selector: str) -> WSJSONRequest:
        self._ws_request_id += 1
        return WSJSONRequest(
            payload={
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": {
                    "stream": stream,
                    "selectors": [selector],
                },
                "id": self._ws_request_id,
            }
        )
