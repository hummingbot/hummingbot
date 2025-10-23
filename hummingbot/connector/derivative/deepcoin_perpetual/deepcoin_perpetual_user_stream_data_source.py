import asyncio
import logging
from operator import truediv
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_web_utils import public_rest_url, wss_url
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSPlainTextRequest 
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_derivative import (
        DeepcoinPerpetualDerivative,
    )


class DeepcoinPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Deepcoin Perpetual API user stream data source
    """
    
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # 30 minutes - recommended to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0
    LISTEN_KEY_RETRY_INTERVAL = 5.0
    MAX_RETRIES = 3
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth,
        trading_pairs: List[str],
        connector: 'DeepcoinPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._current_listen_key = None
        self._last_listen_key_ping_ts = None
        self._manage_listen_key_task = None
        self._listen_key_initialized_event = asyncio.Event()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if not hasattr(cls, "_logger"):
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    async def _get_ws_assistant(self) -> WSAssistant:
        """
        Creates a new WSAssistant instance.
        """
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
                    url= public_rest_url(self._domain,CONSTANTS.USER_STREAM_ENDPOINT),
                    method=RESTMethod.GET,
                    throttler_limit_id=CONSTANTS.USER_STREAM_ENDPOINT,
                    headers=self._auth.get_auth_headers(method=RESTMethod.GET, request_path=CONSTANTS.USER_STREAM_ENDPOINT),
                    timeout=timeout,
                )
                if data.get("code") == "0":
                    return data["data"]["listenkey"]
                else:
                    raise Exception(f"Failed to get listen key: {data.get('msg', 'Unknown error')}")
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
            rest_assistant = await self._api_factory.get_rest_assistant()
            data = await rest_assistant.execute_request(
                url=wss_url(self._domain) + CONSTANTS.USER_STREAM_EXTEND_ENDPOINT,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.USER_STREAM_EXTEND_ENDPOINT,
                is_auth_required= True,
                headers=self._auth.get_auth_headers(method=RESTMethod.GET, request_path=CONSTANTS.USER_STREAM_EXTEND_ENDPOINT),
                params={"listenkey": self._current_listen_key},
                timeout=5.0,
            )
            if data.get("code") == "0":
                self.logger().debug(f"Successfully refreshed listen key {self._current_listen_key}")
                return True
            else:
                self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {data}")
                return False
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error refreshing listen key {self._current_listen_key}: {e}")
            return False

    async def _manage_listen_key_task_loop(self):
        """
        Background task that manages the listen key lifecycle.
        """
        while True:
            try:
                if self._current_listen_key is None:
                    await self._sleep(self.LISTEN_KEY_RETRY_INTERVAL)
                    continue

                success = await self._ping_listen_key()
                if success:
                    pass
                else:
                    # If ping fails, try to get a new listen key
                    self._current_listen_key = None
                    self._listen_key_initialized_event.clear()

                await self._sleep(self.LISTEN_KEY_KEEP_ALIVE_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in manage listen key task loop: {e}")
                await self._sleep(self.LISTEN_KEY_RETRY_INTERVAL)

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listens for user stream messages
        """
        while True:
            try:
                # Get or refresh listen key
                if self._current_listen_key is None:
                    self._current_listen_key = await self._get_listen_key()
                    self._listen_key_initialized_event.set()
                    
                    # Start the listen key management task
                    if self._manage_listen_key_task is None:
                        self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())

                # Connect to WebSocket
                base_url = CONSTANTS.WSS_USER_STREAM_URLS[self._domain]
                ws_url = f"{base_url}?listenKey={self._current_listen_key}"
                ws_assistant = await self._get_ws_assistant()
                
                await ws_assistant.connect(ws_url=ws_url,message_timeout=10)
                self.logger().info(f"Connected to Deepcoin user stream: {ws_url}")

                # Process messages
                await self._process_websocket_messages(websocket_assistant=ws_assistant, queue=output)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in user stream: {e}")
                if self._current_listen_key:
                    self._current_listen_key = None
                    self._listen_key_initialized_event.clear()
                await self._sleep(self.LISTEN_KEY_RETRY_INTERVAL)

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """
        Process incoming WebSocket messages
        """
        while True:
            try:
                message = await websocket_assistant.receive()
                if message:
                    await self._process_event_message(message, queue)
            except asyncio.TimeoutError:
                ping_request = WSPlainTextRequest(payload="ping")
                await websocket_assistant.send(ping_request)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error processing WebSocket message: {e}")
                raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        """
        Process individual event messages
        """
        try:
            if isinstance(event_message, dict):
                # Process different types of events
                if "event" in event_message:
                    event_type = event_message.get("action")
                    if event_type == "PushOrder":
                        await self._process_order_update(event_message, queue)
                    elif event_type == "PushPosition":
                        await self._process_position_update(event_message, queue)
                    elif event_type == "PushAccount":
                        await self._process_balance_update(event_message, queue)
                    elif event_type == "PushTrade":
                        await self._process_trades_update(event_message, queue)
                else:
                    # Generic message processing
                    # await queue.put(event_message)
                    pass
        except Exception as e:
            self.logger().error(f"Error processing event message: {e}")

    async def _process_order_update(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        """Process order update events"""
        await queue.put_nowait(event_message)

    async def _process_position_update(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        """Process position update events"""
        await queue.put_nowait(event_message)

    async def _process_balance_update(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        """Process balance update events"""
        await queue.put_nowait(event_message)
    async def _process_trades_update(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        """Process trades update events"""
        await queue.put_nowait(event_message)

    async def _sleep(self, delay: float):
        """Sleep for the specified delay"""
        await asyncio.sleep(delay)
