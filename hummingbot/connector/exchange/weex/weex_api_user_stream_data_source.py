import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, List, Optional

from hummingbot.connector.exchange.weex import weex_constants as CONSTANTS, weex_web_utils as web_utils
from hummingbot.connector.exchange.weex.weex_auth import WeexAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange


class WeexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    MAX_RETRIES = 3

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: WeexAuth,
        trading_pairs: List[str],
        connector: "WeexExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth: WeexAuth = auth
        self._domain = domain
        self._api_factory = api_factory
        self._connector = connector
        self._trading_pairs = trading_pairs

    async def _get_ws_assistant(self) -> WSAssistant:
        # Always create a new assistant to avoid connection issues
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to WEEX private WS.

        WEEX does NOT use listen keys. Authentication is done via WS handshake headers
        (provided by the WebAssistantsFactory + WeexAuth.ws_authenticate).
        """
        ws = await self._get_ws_assistant()
        url = web_utils.ws_private_url(domain=self._domain)

        self.logger().info("Connecting to WEEX private user stream: %s", url)
        await ws.connect(
            ws_url=url,
            ping_timeout=self.HEARTBEAT_TIME_INTERVAL,
            ws_headers=self._auth.build_ws_headers(),
        )
        self.logger().info("Connected to WEEX private user stream")
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribe to WEEX private channels after connecting.
        """
        # WEEX spot private channels commonly include: account, orders, fills
        subs = [
            {"event": "subscribe", "channel": "account"},
            {"event": "subscribe", "channel": "orders"},
            {"event": "subscribe", "channel": "fill"},
        ]

        for payload in subs:
            await websocket_assistant.send(WSJSONRequest(payload=payload))
        self.logger().info("Subscribed to WEEX private channels: account, orders, fills")

        # Set last_recv_time to indicate user stream is initialized
        # WEEX doesn't send unsolicited messages, so we mark it as active after subscription
        self._last_recv_time = self._time()

    async def _send_ping(self, websocket_assistant: WSAssistant):
        """Send periodic ping to keep connection alive"""
        while True:
            try:
                await asyncio.sleep(20)  # Ping every 20s (WEEX times out at ~30s)
                ping_payload = {"event": "ping", "time": int(time.time() * 1000)}
                await websocket_assistant.send(WSJSONRequest(payload=ping_payload))
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger().warning(f"Error sending ping: {e}")
                break

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """
        Read messages from WS, respond to ping, forward user events.
        """
        while True:
            msg = await websocket_assistant.receive()

            # Some WSAssistant implementations return objects with `.data`
            # Others return raw strings. Handle both.
            data: Any = getattr(msg, "data", msg)

            if data is None:
                continue

            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8")

            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    # Not JSON; ignore noisy frames
                    continue

            # WEEX ping/pong handling
            if isinstance(data, dict) and data.get("event") == "ping":
                pong = {"event": "pong", "time": data.get("time")}
                await websocket_assistant.send(WSJSONRequest(payload=pong))
                continue

            # Forward everything else to the user stream queue
            await queue.put(data)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Hummingbot calls this to start the user stream listener.
        """
        ws: Optional[WSAssistant] = None
        ping_task = None
        try:
            ws = await self._connected_websocket_assistant()
            await self._subscribe_channels(ws)

            # Start periodic ping to keep connection alive
            ping_task = asyncio.create_task(self._send_ping(ws))

            await self._process_websocket_messages(ws, output)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().exception("Unexpected error in WEEX user stream listener: %s", e)
            raise
        finally:
            if ping_task is not None:
                ping_task.cancel()
            if ws is not None:
                await ws.disconnect()

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        self.logger().info("User stream interrupted. Cleaning up...")
        websocket_assistant and await websocket_assistant.disconnect()
