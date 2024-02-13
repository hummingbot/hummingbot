import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bitrue import bitrue_constants as CONSTANTS
from hummingbot.connector.exchange.bitrue.bitrue_auth import BitrueAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitrue.bitrue_exchange import BitrueExchange


class BitrueUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BitrueAuth,
        trading_pairs: List[str],
        connector: "BitrueExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth: BitrueAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory

        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0
        self._message_id_generator = NonceCreator.for_microseconds()
        self._last_connection_check_message_sent = -1

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
        await self._listen_key_initialized_event.wait()

        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{CONSTANTS.WSS_PRIVATE_URL.format(self._domain)}/stream?listenKey={self._current_listen_key}"
        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTIONS_RATE_LIMIT):
            await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            payload = {"event": "sub", "params": {"channel": "user_order_update"}}
            subscribe_request = WSJSONRequest(payload)
            await websocket_assistant.send(subscribe_request)

            payload = {"event": "sub", "params": {"channel": "user_balance_update"}}
            subscribe_request = WSJSONRequest(payload)
            await websocket_assistant.send(subscribe_request)

            self.logger().info("Subscribed to private channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Failed to subscribe to private channels...")
            raise

    async def _get_listen_key(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            resp = await rest_assistant.execute_request(
                url="https://open.bitrue.com" + CONSTANTS.BITRUE_USER_STREAM_PATH_URL,
                method=RESTMethod.POST,
                throttler_limit_id=CONSTANTS.BITRUE_USER_STREAM_PATH_URL,
                headers=self._auth.header_for_authentication(),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            raise IOError(f"Error fetching user stream listen key. Error: {exception}")

        return resp["data"]["listenKey"]

    async def _ping_listen_key(self) -> bool:
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            data = await rest_assistant.execute_request(
                url=CONSTANTS.REST_URL.replace("api/", "")
                + CONSTANTS.BITRUE_USER_STREAM_PATH_URL
                + f"/{self._current_listen_key}",
                method=RESTMethod.PUT,
                return_err=True,
                throttler_limit_id=CONSTANTS.BITRUE_USER_STREAM_PATH_URL,
                headers=self._auth.header_for_authentication(),
            )

            if "code" in data and data["code"] != 200:
                self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {data}")
                return False

        except asyncio.CancelledError:
            raise
        except Exception as exception:
            self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {exception}")
            return False

        return True

    async def _manage_listen_key_task_loop(self):
        try:
            while True:
                now = int(time.time())
                if self._current_listen_key is None:
                    self._current_listen_key = await self._get_listen_key()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")
                    self._listen_key_initialized_event.set()
                    self._last_listen_key_ping_ts = now

                if now - self._last_listen_key_ping_ts >= self.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                    success: bool = await self._ping_listen_key()
                    if not success:
                        self.logger().error("Error occurred renewing listen key ...")
                        break
                    else:
                        self.logger().info(f"Refreshed listen key {self._current_listen_key}.")
                        self._last_listen_key_ping_ts = int(time.time())
                else:
                    await self._sleep(self.LISTEN_KEY_KEEP_ALIVE_INTERVAL)
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        self._manage_listen_key_task and self._manage_listen_key_task.cancel()
        self._current_listen_key = None
        self._listen_key_initialized_event.clear()

    def _is_message_response_to_connection_check(self, event_message: Dict[str, Any]) -> bool:
        return False

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
        if event_message.get("event", "") == "ping":
            # For Bitrue we consider receiving the ping message as indication the websocket is still healthy
            pong_request = WSJSONRequest(payload={"pong": event_message["ts"]})
            await websocket_assistant.send(request=pong_request)
        elif event_message.get("event_rep", "") == "subed":
            if event_message.get("status") != "ok":
                raise ValueError(f"Error subscribing to topic: {event_message.get('channel')} ({event_message})")
        else:
            await super()._process_event_message(
                event_message=event_message, queue=queue
            )
