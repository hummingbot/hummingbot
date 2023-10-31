import asyncio
import logging
import time
from typing import Optional

import hummingbot.connector.exchange.bing_x.bing_x_constants as CONSTANTS
import hummingbot.connector.exchange.bing_x.bing_x_web_utils as web_utils
from hummingbot.connector.exchange.bing_x.bing_x_auth import BingXAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BingXAPIUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_TIME_INTERVAL = 30.0

    _bausds_logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: BingXAuth,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__()
        self._auth: BingXAuth = auth
        self._time_synchronizer = time_synchronizer
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)
        self._ws_assistant: Optional[WSAssistant] = None
        self._last_ws_message_sent_timestamp = 0

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
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.WSS_PRIVATE_URL[self._domain])
                await self._authenticate_connection(ws)
                self._last_ws_message_sent_timestamp = self._time()
                while True:
                    try:
                        seconds_until_next_ping = (CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL -
                                                   (self._time() - self._last_ws_message_sent_timestamp))
                        await asyncio.wait_for(
                            self._process_ws_messages(ws=ws, output=output), timeout=seconds_until_next_ping)
                    except asyncio.TimeoutError:
                        ping_time = self._time()
                        payload = {
                            "ping": int(ping_time * 1e3)
                        }
                        ping_request = WSJSONRequest(payload=payload)
                        await ws.send(request=ping_request)
                        self._last_ws_message_sent_timestamp = ping_time
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            finally:
                # Make sure no background task is leaked.
                ws and await ws.disconnect()
                await self._sleep(5)

    async def _authenticate_connection(self, ws: WSAssistant):
        """
        Sends the authentication message.
        :param ws: the websocket assistant used to connect to the exchange
        """
        auth_message: WSJSONRequest = WSJSONRequest(payload=self._auth.generate_ws_authentication_message())
        await ws.send(auth_message)

    async def _process_ws_messages(self, ws: WSAssistant, output: asyncio.Queue):
        async for ws_response in ws.iter_messages():
            data = ws_response.data
            if isinstance(data, list):
                for message in data:
                    if message["e"] in ["executionReport", "outboundAccountInfo"]:
                        output.put_nowait(message)
            elif data.get("auth") == "fail":
                raise IOError("Private channel authentication failed.")

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    def _time(self):
        return time.time()
