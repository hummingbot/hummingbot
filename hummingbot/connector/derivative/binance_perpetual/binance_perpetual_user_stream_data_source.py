import asyncio
import logging
import time
from typing import Optional

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BinancePerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _bpusds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpusds_logger is None:
            cls._bpusds_logger = logging.getLogger(__name__)
        return cls._bpusds_logger

    def __init__(
        self,
        auth: BinancePerpetualAuth,
        domain: str = "binance_perpetual",
        throttler: Optional[AsyncThrottler] = None,
        api_factory: Optional[WebAssistantsFactory] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
    ):
        super().__init__()
        self._time_synchronizer = time_synchronizer
        self._domain = domain
        self._throttler = throttler
        self._api_factory: WebAssistantsFactory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=auth,
        )
        self._ws_assistant: Optional[WSAssistant] = None
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_listen_key_ping_ts = None

        self._manage_listen_key_task = None
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def get_listen_key(self):
        data = None

        try:
            data = await web_utils.api_request(
                path=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
                domain=self._domain,
                method=RESTMethod.POST,
                is_auth_required=True)
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            raise IOError(
                f"Error fetching Binance Perpetual user stream listen key. "
                f"The response was {data}. Error: {exception}"
            )

        return data["listenKey"]

    async def ping_listen_key(self) -> bool:
        try:
            data = await web_utils.api_request(
                path=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
                domain=self._domain,
                params={"listenKey": self._current_listen_key},
                method=RESTMethod.PUT,
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
        try:
            while True:
                if self._current_listen_key is None:
                    self._current_listen_key = await self.get_listen_key()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")
                    self._listen_key_initialized_event.set()
                else:
                    success: bool = await self.ping_listen_key()
                    if not success:
                        self.logger().error("Error occurred renewing listen key... ")
                        break
                    else:
                        self.logger().info(f"Refreshed listen key {self._current_listen_key}.")
                        self._last_listen_key_ping_ts = int(time.time())
                await self._sleep(self.LISTEN_KEY_KEEP_ALIVE_INTERVAL)

        except Exception as e:
            self.logger().error(f"Unexpected error occurred with maintaining listen key. "
                                f"Error {e}")
            raise
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()

    async def listen_for_user_stream(self, output: asyncio.Queue):
        ws = None
        while True:
            try:
                self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
                await self._listen_key_initialized_event.wait()

                url = f"{web_utils.wss_url(CONSTANTS.PRIVATE_WS_ENDPOINT, self._domain)}/{self._current_listen_key}"
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
                await ws.ping()  # to update last_recv_timestamp

                async for msg in ws.iter_messages():
                    if len(msg.data) > 0:
                        output.put_nowait(msg.data)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error while listening to user stream. Retrying after 5 seconds... "
                    f"Error: {e}",
                    exc_info=True,
                )
            finally:
                # Make sure no background task is leaked.
                ws and await ws.disconnect()
                self._manage_listen_key_task and self._manage_listen_key_task.cancel()
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                await self._sleep(5)
