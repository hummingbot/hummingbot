import asyncio
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class ArchitectPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None
    HEARTBEAT_TIME_INTERVAL = 30.0

    def __init__(
        self,
        auth: ArchitectPerpetualAuth,
        trading_pairs: List[str],
        connector: "ArchitectPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_assistant: Optional[WSAssistant] = None
        self._last_ws_message_sent_timestamp = 0.0

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant is not None:
            return self._ws_assistant.last_recv_time
        return 0.0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        if self._ws_assistant is None or not self._ws_assistant.is_connected:
            ws_url = web_utils.wss_url(self._domain)
            self._ws_assistant = await self._api_factory.get_ws_assistant()
            await self._ws_assistant.connect(ws_url=ws_url)
            await self._authenticate(self._ws_assistant)
        return self._ws_assistant

    async def _authenticate(self, ws: WSAssistant) -> None:
        credentials = self._auth.get_credentials()
        auth_message = {"type": "auth", "api_key": credentials["api_key"], "api_secret": credentials["api_secret"]}
        await ws.send(WSJSONRequest(payload=auth_message))
        try:
            async for ws_response in ws.iter_messages():
                data = ws_response.data
                if isinstance(data, dict):
                    if data.get("type") == "auth" and data.get("status") == "success":
                        self.logger().info("WebSocket authentication successful")
                        break
                    elif data.get("type") == "error":
                        raise Exception(f"WebSocket auth failed: {data.get('message')}")
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket auth response timeout, continuing...")

    async def _subscribe_channels(self, ws: WSAssistant) -> None:
        try:
            await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": "orderflow"}))
            await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": "positions"}))
            await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": "account"}))
            self.logger().info("Subscribed to user stream channels")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error subscribing to user channels: {e}")
            raise

    async def _send_ping(self, ws: WSAssistant) -> None:
        await ws.send(WSJSONRequest(payload={"type": "ping"}))
        self._last_ws_message_sent_timestamp = asyncio.get_event_loop().time()

    async def listen_for_user_stream(self, output: asyncio.Queue) -> None:
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if isinstance(data, dict):
                        msg_type = data.get("type", data.get("channel", ""))
                        if msg_type == "pong":
                            continue
                        if msg_type in ["order", "orderflow", "fill", "position", "account", "balance"]:
                            await output.put(data)
                        elif msg_type == "error":
                            self.logger().error(f"User stream error: {data.get('message')}")
                        else:
                            await output.put(data)
                    current_time = asyncio.get_event_loop().time()
                    if current_time - self._last_ws_message_sent_timestamp > self.HEARTBEAT_TIME_INTERVAL:
                        await self._send_ping(ws)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream connection error: {e}. Reconnecting in 5 seconds...")
                await self._sleep(5.0)
            finally:
                if ws:
                    await ws.disconnect()
                    ws = None
                    self._ws_assistant = None
