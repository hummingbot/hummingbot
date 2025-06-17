import asyncio
import time
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.mexc import mexc_constants as CONSTANTS, mexc_web_utils as web_utils
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.mexc.mexc_exchange import MexcExchange


class MexcAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Manages the user stream connection for MEXC exchange, handling listen key lifecycle
    and websocket connection management.
    """
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0
    LISTEN_KEY_RETRY_INTERVAL = 5.0  # Delay between listen key management iterations
    MAX_RETRIES = 3  # Maximum retries for obtaining a new listen key

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: MexcAuth,
                 trading_pairs: List[str],
                 connector: 'MexcExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: MexcAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory

        # Event to signal when listen key is ready for use
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        # Track last successful ping timestamp for refresh scheduling
        self._last_listen_key_ping_ts = None
        # Background task handle for listen key lifecycle management
        self._manage_listen_key_task = None

    async def _ensure_listen_key_task_running(self):
        """
        Ensures the listen key management task is running.

        Creates a new task if none exists or if the previous task has completed.
        This method is idempotent and safe to call multiple times.
        """
        if self._manage_listen_key_task is None or self._manage_listen_key_task.done():
            self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())

    async def _cancel_listen_key_task(self):
        """
        Safely cancels the listen key management task.

        Attempts graceful cancellation with a timeout to prevent hanging.
        Shields the task to allow cleanup operations to complete.
        """
        if self._manage_listen_key_task and not self._manage_listen_key_task.done():
            self.logger().info("Cancelling listen key management task")
            self._manage_listen_key_task.cancel()
            try:
                # Shield allows the task to complete cleanup operations
                await asyncio.wait_for(asyncio.shield(self._manage_listen_key_task), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                # Task didn't complete within timeout or was cancelled - acceptable
                pass

        self._manage_listen_key_task = None

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange.

        This method ensures the listen key is ready before connecting.
        The connection process follows these steps:
        1. Ensures the listen key management task is running
        2. Waits for a valid listen key to be obtained
        3. Establishes websocket connection with the listen key

        :return: Connected WSAssistant instance
        :raises: Connection errors if websocket fails to connect
        """
        # Make sure the listen key management task is running
        await self._ensure_listen_key_task_running()

        # Wait for the listen key to be initialized
        await self._listen_key_initialized_event.wait()

        # Get a websocket assistant and connect it
        ws = await self._get_ws_assistant()
        url = f"{CONSTANTS.WSS_URL.format(self._domain)}?listenKey={self._current_listen_key}"

        self.logger().info(f"Connecting to user stream with listen key {self._current_listen_key}")
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        self.logger().info("Successfully connected to user stream")

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:

            orders_change_payload = {
                "method": "SUBSCRIPTION",
                "params": [CONSTANTS.USER_ORDERS_ENDPOINT_NAME],
                "id": 1
            }
            subscribe_order_change_request: WSJSONRequest = WSJSONRequest(payload=orders_change_payload)

            trades_payload = {
                "method": "SUBSCRIPTION",
                "params": [CONSTANTS.USER_TRADES_ENDPOINT_NAME],
                "id": 2
            }
            subscribe_trades_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

            balance_payload = {
                "method": "SUBSCRIPTION",
                "params": [CONSTANTS.USER_BALANCE_ENDPOINT_NAME],
                "id": 3
            }
            subscribe_balance_request: WSJSONRequest = WSJSONRequest(payload=balance_payload)

            await websocket_assistant.send(subscribe_order_change_request)
            await websocket_assistant.send(subscribe_trades_request)
            await websocket_assistant.send(subscribe_balance_request)

            self.logger().info("Subscribed to private order changes and balance updates channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _get_listen_key(self, max_retries: int = MAX_RETRIES) -> str:
        """
        Fetches a listen key from the exchange with retries and exponential backoff.

        Implements a robust retry mechanism to handle temporary network issues
        or API errors. The backoff time doubles after each failed attempt.

        :param max_retries: Maximum number of retry attempts (default: MAX_RETRIES)
        :return: Valid listen key string
        :raises IOError: If all retry attempts fail
        """
        retry_count = 0
        backoff_time = 1.0  # Initial backoff: 1 second
        timeout = 5.0

        rest_assistant = await self._api_factory.get_rest_assistant()
        while True:
            try:
                data = await rest_assistant.execute_request(
                    url=web_utils.public_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self._domain),
                    method=RESTMethod.POST,
                    throttler_limit_id=CONSTANTS.MEXC_USER_STREAM_PATH_URL,
                    is_auth_required=True,
                    timeout=timeout,
                )
                return data["listenKey"]
            except asyncio.CancelledError:
                raise
            except Exception as exception:
                retry_count += 1
                if retry_count > max_retries:
                    raise IOError(f"Error fetching user stream listen key after {max_retries} retries. Error: {exception}")

                self.logger().warning(f"Retry {retry_count}/{max_retries} fetching user stream listen key. Error: {exception}")
                await self._sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff: 1s, 2s, 4s...

    async def _ping_listen_key(self) -> bool:
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            data = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self._domain),
                params={"listenKey": self._current_listen_key},
                method=RESTMethod.PUT,
                return_err=True,
                throttler_limit_id=CONSTANTS.MEXC_USER_STREAM_PATH_URL,
                is_auth_required=True
            )

            if "code" in data:
                self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {data}")
                return False

        except asyncio.CancelledError:
            raise
        except Exception as exception:
            self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {exception}")
            return False

        return True

    async def _manage_listen_key_task_loop(self):
        """
        Background task that manages the listen key lifecycle.

        This is the core method that ensures continuous connectivity by:
        1. Obtaining a new listen key if none exists or previous one failed
        2. Periodically refreshing the listen key before it expires (30-minute intervals)
        3. Handling errors gracefully and resetting state when necessary

        The task runs indefinitely until cancelled, automatically recovering from errors.
        State is properly cleaned up in the finally block to ensure consistency.
        """
        self.logger().info("Starting listen key management task...")
        try:
            while True:
                try:
                    now = int(time.time())

                    # Initialize listen key if needed (first run or after error)
                    if self._current_listen_key is None:
                        self._current_listen_key = await self._get_listen_key()
                        self._last_listen_key_ping_ts = now
                        self._listen_key_initialized_event.set()
                        self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")

                    # Refresh listen key periodically to prevent expiration
                    if now - self._last_listen_key_ping_ts >= self.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                        success = await self._ping_listen_key()
                        if success:
                            self.logger().info(f"Successfully refreshed listen key {self._current_listen_key}")
                            self._last_listen_key_ping_ts = now
                        else:
                            # Ping failed - force obtaining a new key in next iteration
                            self.logger().error(f"Failed to refresh listen key {self._current_listen_key}. Getting new key...")
                            raise Exception("Listen key refresh failed")

                    # Sleep before next check
                    await self._sleep(self.LISTEN_KEY_RETRY_INTERVAL)
                except asyncio.CancelledError:
                    self.logger().info("Listen key management task cancelled")
                    raise
                except Exception as e:
                    # Reset state on any error to force new key acquisition
                    self.logger().error(f"Error occurred renewing listen key ... {e}")
                    self._current_listen_key = None
                    self._listen_key_initialized_event.clear()
                    await self._sleep(self.LISTEN_KEY_RETRY_INTERVAL)
        finally:
            # Cleanup on task termination
            self.logger().info("Listen key management task stopped")
            await self._ws_assistant.disconnect()
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _send_ping(self, websocket_assistant: WSAssistant):
        payload = {
            "method": "PING",
        }
        ping_request: WSJSONRequest = WSJSONRequest(payload=payload)
        await websocket_assistant.send(ping_request)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Handles websocket disconnection by cleaning up resources.

        This method is called when the websocket connection is interrupted.
        It ensures proper cleanup by:
        1. Disconnecting the websocket assistant if it exists
        2. Clearing the current listen key to force renewal
        3. Resetting the initialization event to block new connections

        :param websocket_assistant: The websocket assistant that was disconnected
        """
        self.logger().info("User stream interrupted. Cleaning up...")

        # Disconnect the websocket if it exists
        websocket_assistant and await websocket_assistant.disconnect()
        # Force new listen key acquisition on reconnection
        self._current_listen_key = None
        self._listen_key_initialized_event.clear()

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await asyncio.wait_for(
                    super()._process_websocket_messages(websocket_assistant=websocket_assistant, queue=queue),
                    timeout=CONSTANTS.WS_CONNECTION_TIME_INTERVAL
                )
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"method": "PING"})
                await websocket_assistant.send(ping_request)
