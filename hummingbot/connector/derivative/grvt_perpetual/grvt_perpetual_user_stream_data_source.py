import asyncio
from typing import TYPE_CHECKING, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GrvtPerpetualDerivative


class GrvtPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: GrvtPerpetualAuth,
            connector: "GrvtPerpetualDerivative",
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector

    async def _get_ws_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to GRVT's authenticated trading websocket.
        Authentication is performed via session cookie injected into the connection headers.
        """
        ws = await self._get_ws_assistant()
        await self._auth.ensure_authenticated()
        url = web_utils.trade_wss_url(domain=self._domain)

        # Build auth headers with cookie and account-id
        ws_headers = self._auth.ws_headers_for_authentication()

        if ws_headers.get("Cookie"):
            account_id = ws_headers.get("X-Grvt-Account-Id", "")
            connect_url = f"{url}?x_grvt_account_id={account_id}"
            await ws.connect(
                ws_url=connect_url,
                ping_timeout=self.HEARTBEAT_TIME_INTERVAL,
                ws_headers=ws_headers,
            )
        else:
            await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)

        self.logger().info("Successfully connected to GRVT trading user stream")
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order updates, fill updates, and position updates via GRVT JSONRPC.
        """
        try:
            sub_account_id = self._auth.sub_account_id

            # Subscribe to order state updates
            order_payload = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": {
                    "stream": CONSTANTS.WS_ORDER_STREAM,
                    "selectors": [str(sub_account_id)],
                },
                "id": 1,
            }
            await websocket_assistant.send(WSJSONRequest(order_payload))

            # Subscribe to fill updates
            fill_payload = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": {
                    "stream": CONSTANTS.WS_FILL_STREAM,
                    "selectors": [str(sub_account_id)],
                },
                "id": 2,
            }
            await websocket_assistant.send(WSJSONRequest(fill_payload))

            # Subscribe to position updates
            position_payload = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": {
                    "stream": CONSTANTS.WS_POSITION_STREAM,
                    "selectors": [str(sub_account_id)],
                },
                "id": 3,
            }
            await websocket_assistant.send(WSJSONRequest(position_payload))

            self.logger().info("Subscribed to GRVT order, fill, and position user streams")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to GRVT user streams...")
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Handles websocket disconnection by cleaning up resources.
        """
        self.logger().info("GRVT user stream interrupted. Cleaning up...")
        if websocket_assistant is not None:
            await websocket_assistant.disconnect()
