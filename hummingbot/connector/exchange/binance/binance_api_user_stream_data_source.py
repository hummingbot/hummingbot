import asyncio
import logging
import time
from typing import List, Optional

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
import hummingbot.connector.exchange.binance.binance_web_utils as web_utils
from hummingbot.connector.exchange.binance.binance_auth import BinanceAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BinanceAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _bausds_logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: BinanceAuth,
                 trading_pairs: List[str],
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__()
        self._auth: BinanceAuth = auth
        self._time_synchronizer = time_synchronizer
        self._current_listen_key = None
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None

        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message
        :return: the timestamp of the last received message in seconds
        """
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue

        :param output: the queue to use to store the received messages
        """
        ws = None
        while True:
            try:
                self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
                await self._listen_key_initialized_event.wait()

                ws: WSAssistant = await self._get_ws_assistant()
                url = f"{CONSTANTS.WSS_URL.format(self._domain)}/{self._current_listen_key}"
                await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                await ws.ping()  # to update last_recv_timestamp

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if len(data) > 0:
                        output.put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            finally:
                # Make sure no background task is leaked.
                ws and await ws.disconnect()
                self._manage_listen_key_task and self._manage_listen_key_task.cancel()
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                await self._sleep(5)

    async def _get_listen_key(self):
        try:
            data = await web_utils.api_request(
                path=CONSTANTS.BINANCE_USER_STREAM_PATH_URL,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
                domain=self._domain,
                method=RESTMethod.POST,
                headers=self._auth.header_for_authentication())
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            raise IOError(f"Error fetching user stream listen key. Error: {exception}")

        return data["listenKey"]

    async def _ping_listen_key(self) -> bool:
        try:
            data = await web_utils.api_request(
                path=CONSTANTS.BINANCE_USER_STREAM_PATH_URL,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
                domain=self._domain,
                params={"listenKey": self._current_listen_key},
                method=RESTMethod.PUT,
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
        try:
            while True:
                now = int(time.time())
                if self._current_listen_key is None:
                    self._current_listen_key = await self._get_listen_key()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")
                    self._listen_key_initialized_event.set()
                    self._last_listen_key_ping_ts = int(time.time())

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
