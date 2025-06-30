import asyncio
import time
from typing import TYPE_CHECKING, Optional

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import (
        BinancePerpetualDerivative,
    )


class BinancePerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0
    LISTEN_KEY_RETRY_INTERVAL = 5.0
    MAX_RETRIES = 3
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: BinancePerpetualAuth,
            connector: 'BinancePerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector
        self._current_listen_key = None
        self._last_listen_key_ping_ts = None
        self._manage_listen_key_task = None
        self._listen_key_initialized_event = asyncio.Event()

    async def _get_ws_assistant(self) -> WSAssistant:
        """
        Creates a new WSAssistant instance.
        """
        # Always create a new assistant to avoid connection issues
        return await self._api_factory.get_ws_assistant()

    async def _get_listen_key(self, max_retries: int = MAX_RETRIES) -> str:
        """
        Fetches a listen key from the exchange with retries and backoff.

        :param max_retries: Maximum number of retry attempts
        :return: Valid listen key string
        """
        retry_count = 0
        backoff_time = 1.0
        timeout = 5.0

        rest_assistant = await self._api_factory.get_rest_assistant()
        while True:
            try:
                data = await rest_assistant.execute_request(
                    url=web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self._domain),
                    method=RESTMethod.POST,
                    throttler_limit_id=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT,
                    headers=self._auth.header_for_authentication(),
                    timeout=timeout,
                )
                return data["listenKey"]
            except asyncio.CancelledError:
                raise
            except Exception as exception:
                retry_count += 1
                if retry_count > max_retries:
                    raise IOError(f"Error fetching user stream listen key after {max_retries} retries. Error: {exception}")

                self.logger().warning(f"Retry {retry_count}/{max_retries} fetching user stream listen key. Error: {repr(exception)}")
                await self._sleep(backoff_time)
                backoff_time *= 2

    async def _ping_listen_key(self) -> bool:
        """
        Sends a ping to keep the listen key alive.

        :return: True if successful, False otherwise
        """
        try:
            data = await self._connector._api_put(
                path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT,
                params={"listenKey": self._current_listen_key},
                is_auth_required=True,
                return_err=True)
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
        Background task that manages the listen key lifecycle:
        1. Obtains a new listen key if needed
        2. Periodically refreshes the listen key to keep it active
        3. Handles errors and resets state when necessary
        """
        self.logger().info("Starting listen key management task...")
        while True:
            try:
                now = int(time.time())

                # Initialize listen key if needed
                if self._current_listen_key is None:
                    self._current_listen_key = await self._get_listen_key()
                    self._last_listen_key_ping_ts = now
                    self._listen_key_initialized_event.set()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")

                # Refresh listen key periodically
                if now - self._last_listen_key_ping_ts >= self.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                    success = await self._ping_listen_key()
                    if success:
                        self.logger().info(f"Successfully refreshed listen key {self._current_listen_key}")
                        self._last_listen_key_ping_ts = now
                    else:
                        self.logger().error(
                            f"Failed to refresh listen key {self._current_listen_key}. Getting new key...")
                        raise
                        # Continue to next iteration which will get a new key
                await self._sleep(self.LISTEN_KEY_RETRY_INTERVAL)
            except asyncio.CancelledError:
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                raise
            except Exception as e:
                self.logger().error(f"Error occurred renewing listen key ... {e}")
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                await self._sleep(self.LISTEN_KEY_RETRY_INTERVAL)

    async def _ensure_listen_key_task_running(self):
        """
        Ensures the listen key management task is running.
        """
        # If task is already running, do nothing
        if self._manage_listen_key_task is not None and not self._manage_listen_key_task.done():
            return

        # Cancel old task if it exists and is done (failed)
        if self._manage_listen_key_task is not None:
            self._manage_listen_key_task.cancel()
            try:
                await self._manage_listen_key_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass  # Ignore any exception from the failed task

        # Create new task
        self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange.

        This method ensures the listen key is ready before connecting.
        """
        # Make sure the listen key management task is running
        await self._ensure_listen_key_task_running()

        # Wait for the listen key to be initialized
        await self._listen_key_initialized_event.wait()

        # Get a websocket assistant and connect it
        ws = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(CONSTANTS.PRIVATE_WS_ENDPOINT, self._domain)}/{self._current_listen_key}"

        self.logger().info(f"Connecting to user stream with listen key {self._current_listen_key}")
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        self.logger().info("Successfully connected to user stream")

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        Binance does not require any channel subscription.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        pass

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Handles websocket disconnection by cleaning up resources.

        :param websocket_assistant: The websocket assistant that was disconnected
        """
        self.logger().info("User stream interrupted. Cleaning up...")

        # Cancel listen key management task first
        if self._manage_listen_key_task and not self._manage_listen_key_task.done():
            self._manage_listen_key_task.cancel()
            try:
                await self._manage_listen_key_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass  # Ignore any exception from the task
            self._manage_listen_key_task = None

        # Disconnect the websocket if it exists
        websocket_assistant and await websocket_assistant.disconnect()
        self._current_listen_key = None
        self._listen_key_initialized_event.clear()
