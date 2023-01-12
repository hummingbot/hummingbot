import asyncio
import time
from typing import TYPE_CHECKING, List, Optional

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
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
        self._ws_assistants: List[WSAssistant] = []
        self._connector = connector
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
            data = await self._connector._api_post(
                path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT,
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

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
        await self._listen_key_initialized_event.wait()

        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(CONSTANTS.PRIVATE_WS_ENDPOINT, self._domain)}/{self._current_listen_key}"
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        Binance does not require any channel subscription.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        pass

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        websocket_assistant and await websocket_assistant.disconnect()
        self._manage_listen_key_task and self._manage_listen_key_task.cancel()
        self._current_listen_key = None
        self._listen_key_initialized_event.clear()
        await self._sleep(5)
