import asyncio
import logging
import aiohttp
import time

from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS, \
    bybit_perpetual_utils
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_websocket_adaptor import \
    BybitPerpetualWebSocketAdaptor
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class BybitPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth_assistant: BybitPerpetualAuth,
                 session: Optional[aiohttp.ClientSession] = None,
                 domain: Optional[str] = None):
        super().__init__()
        self._auth_assistant: BybitPerpetualAuth = auth_assistant
        self._last_recv_time: float = 0
        self._domain = domain
        self._session = session

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _create_websocket_connection(self, url: str) -> BybitPerpetualWebSocketAdaptor:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()
            ws = await self._session.ws_connect(url)
            return BybitPerpetualWebSocketAdaptor(websocket=ws)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network(f"Unexpected error occurred during {CONSTANTS.EXCHANGE_NAME} WebSocket Connection"
                                  f" on {url} ({ex})")
            raise

    async def _authenticate(self, ws: BybitPerpetualWebSocketAdaptor):
        """
        Authenticates user to websocket
        """
        try:
            auth_payload: Dict[str, Any] = self._auth_assistant.get_ws_auth_payload()
            self.logger().info("Authenticating to User Stream...")
            await ws.authenticate(auth_payload)
            auth_resp = await ws.receive_json()

            if auth_resp["success"] is not True or not auth_resp["request"] or not auth_resp["request"]["op"] or \
                    auth_resp["request"]["op"] != "auth":
                self.logger().error(f"Response: {auth_resp}", exc_info=True)
                raise Exception("Could not authenticate websocket connection with Bybit Perpetual")
            else:
                self.logger().info("Successfully authenticated to User Stream.")

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().error(f"Error occurred when authenticating to user stream ({ex})",
                                exc_info=True)
            raise

    async def _subscribe_to_events(self, ws: BybitPerpetualWebSocketAdaptor):
        """
        Subscribes to User Account Events
        """
        try:
            await ws.subscribe_to_positions()
            await ws.subscribe_to_orders()
            await ws.subscribe_to_executions()
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().error(f"Error occurred subscribing to {CONSTANTS.EXCHANGE_NAME} private channels ({ex})",
                                exc_info=True)
            raise

    async def _listen_for_user_stream_on_url(self, url: str, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param url: the wss url to connect to
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                ws: BybitPerpetualWebSocketAdaptor = await self._create_websocket_connection(url)
                await self._authenticate(ws)
                await self._subscribe_to_events(ws)

                async for msg in ws.iter_messages():
                    self._last_recv_time = int(time.time())
                    # Handles ping and subscribe messages.
                    if "success" in msg:
                        if msg["success"] and msg["request"]["op"] == "ping":
                            continue
                        if msg["success"] and msg["request"]["op"] == "subscribe":
                            self.logger().info(
                                f"Successful subscription to the topic {msg['request']['args']} on {url}")
                        else:
                            self.logger().error(
                                "There was an error subscribing to the topic "
                                f"{msg['request']['args']} ({msg['ret_msg']}) on {url}")
                        continue
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(
                    f"Unexpected error with Bybit Perpetual WebSocket connection on {url}."
                    f" Retrying in 30 seconds. ({ex})",
                    exc_info=True
                )
                await ws.close()
                await asyncio.sleep(30.0)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Subscribe to all required events and start the listening cycle.
        """
        tasks_future = None
        try:
            tasks = []
            tasks.append(self._listen_for_user_stream_on_url(
                url=bybit_perpetual_utils.wss_linear_private_url(self._domain),
                output=output))
            tasks.append(self._listen_for_user_stream_on_url(
                url=bybit_perpetual_utils.wss_non_linear_private_url(self._domain),
                output=output))

            tasks_future = asyncio.gather(*tasks)
            await tasks_future

        except asyncio.CancelledError:
            tasks_future and tasks_future.cancel()
            raise
