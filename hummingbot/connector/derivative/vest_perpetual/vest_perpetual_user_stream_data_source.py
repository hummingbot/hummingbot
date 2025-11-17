import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Dict, Optional

import hummingbot.connector.derivative.vest_perpetual.vest_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.vest_perpetual.vest_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_auth import VestPerpetualAuth
    from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_derivative import VestPerpetualDerivative


class VestPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: "VestPerpetualAuth",
        connector: "VestPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        use_testnet: bool = False,
    ):
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._api_factory = api_factory
        self._use_testnet = use_testnet
        self._listen_key: Optional[str] = None
        self._listen_key_initialized_event = asyncio.Event()
        self._manage_listen_key_task: Optional[asyncio.Task] = None

    @property
    def last_recv_time(self) -> float:
        return self._ws_assistant.last_recv_time if self._ws_assistant else 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """Create and connect a WebSocket assistant with listen key."""
        await self._get_listen_key()

        account_group = getattr(self._connector, "_account_group", 0)
        domain = getattr(self._connector, "domain", CONSTANTS.DEFAULT_DOMAIN)
        ws_url = web_utils.private_ws_url(
            listen_key=self._listen_key or "",
            domain=domain,
            account_group=account_group,
        )

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)

        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """Subscribe to user data channels."""
        try:
            subscribe_request = WSJSONRequest(
                payload={
                    "method": "SUBSCRIBE",
                    "params": [CONSTANTS.WS_ACCOUNT_PRIVATE_CHANNEL],
                    "id": 1,
                }
            )
            await ws.send(subscribe_request)
            self.logger().info("Subscribed to Vest user stream")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error subscribing to user stream")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """Process incoming user stream messages."""
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if "channel" in data and data["channel"] == CONSTANTS.WS_ACCOUNT_PRIVATE_CHANNEL:
                queue.put_nowait(data)

    async def _get_listen_key(self):
        """Obtain a listen key from the exchange."""
        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.rest_url(CONSTANTS.LISTEN_KEY_PATH_URL, self._use_testnet)

        response = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=CONSTANTS.LISTEN_KEY_PATH_URL,
            method=RESTMethod.POST,
            is_auth_required=True,
        )

        self._listen_key = response["listenKey"]
        self._listen_key_initialized_event.set()
        self.logger().info(f"Listen key obtained: {self._listen_key[:8]}...")

    async def _ping_listen_key(self):
        """Ping the listen key to keep it alive."""
        if self._listen_key is None:
            return

        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.rest_url(CONSTANTS.LISTEN_KEY_PATH_URL, self._use_testnet)

        try:
            await rest_assistant.execute_request(
                url=url,
                throttler_limit_id=CONSTANTS.LISTEN_KEY_PATH_URL,
                method=RESTMethod.PUT,
                is_auth_required=True,
            )
            self.logger().debug("Listen key pinged successfully")
        except Exception as e:
            self.logger().warning(f"Failed to ping listen key: {e}")

    async def _manage_listen_key_task_loop(self):
        """Manage listen key by pinging it periodically."""
        try:
            while True:
                await self._listen_key_initialized_event.wait()
                await asyncio.sleep(30 * 60)  # Ping every 30 minutes
                await self._ping_listen_key()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error in listen key management loop")
            raise

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """Listen for user stream messages and put them in the output queue."""
        self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
        try:
            await super().listen_for_user_stream(output)
        finally:
            if self._manage_listen_key_task is not None:
                self._manage_listen_key_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._manage_listen_key_task
                self._manage_listen_key_task = None
