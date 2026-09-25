import asyncio
from typing import Any, Dict
from urllib.parse import urlparse

import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_auth import KalshiPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class KalshiPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Kalshi has no listen key: private channels use the same signed websocket handshake as the public ones.
    Only fill and order events exist (no balance or position channel). They are queued raw, per contract, and the
    connector converts them to underlying units.
    """

    def __init__(
            self,
            auth: KalshiPerpetualAuth,
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._api_factory = api_factory
        self._domain = domain

    async def _get_ws_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.wss_url(self._domain)
        headers = self._auth.header_for_authentication(method="GET", path=urlparse(url).path)
        ws: WSAssistant = await self._get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL, ws_headers=headers)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            # Without market_tickers the private channels cover every market, so pairs added later need no update.
            payload = {
                "id": 1,
                "cmd": "subscribe",
                "params": {"channels": [CONSTANTS.WS_FILL_CHANNEL, CONSTANTS.WS_USER_ORDERS_CHANNEL]},
            }
            await websocket_assistant.send(WSJSONRequest(payload=payload))
            self.logger().info("Subscribed to private fill and user order channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to private channels...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if not event_message:
            return
        message_type = event_message.get("type")
        if message_type in (CONSTANTS.WS_FILL_MESSAGE, CONSTANTS.WS_USER_ORDER_MESSAGE):
            queue.put_nowait(event_message)
        elif message_type == CONSTANTS.WS_ERROR_MESSAGE:
            # A rejected subscription keeps the connection open without private events: raising reconnects after a
            # pause and subscribes again.
            raise IOError(f"Kalshi user stream error: {event_message.get('msg')}")
