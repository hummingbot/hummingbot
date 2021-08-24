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
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS, bybit_perpetual_utils
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_websocket_adaptor import BybitPerpetualWebSocketAdaptor
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class BybitPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth_assistant: BybitPerpetualAuth, session: Optional[aiohttp.ClientSession] = None, domain: Optional[str] = None):
        super().__init__()
        self._auth_assistant: BybitPerpetualAuth = auth_assistant
        self._last_recv_time: float = 0
        self._domain = domain
        self._session = session

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _create_websocket_connection(self) -> BybitPerpetualWebSocketAdaptor:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()
            ws = await self._session.ws_connect(bybit_perpetual_utils.wss_url(self._domain))
            return BybitPerpetualWebSocketAdaptor(websocket=ws)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network(f"Unexpected error occurred during {CONSTANTS.EXCHANGE_NAME} WebSocket Connection "
                                  f"({ex})")
            raise

    async def _authenticate(self, ws: BybitPerpetualWebSocketAdaptor):
        """
        Authenticates user to websocket
        """
        try:
            auth_payload: Dict[str, Any] = self._auth_assistant.get_ws_auth_payload()
            await ws.authenticate(auth_payload)
            auth_resp = await ws.receive_json()

            if auth_resp["success"] is not True or not auth_resp["request"] or not auth_resp["request"]["op"] or auth_resp["request"]["op"] != "auth":
                self.logger().error(f"Response: {auth_resp}", exc_info=True)
                raise Exception("Could not authenticate websocket connection with Bybit Perpetual")

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
            await ws.subscribe_to_stop_orders()
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().error(f"Error occurred subscribing to {CONSTANTS.EXCHANGE_NAME} private channels ({ex})",
                                exc_info=True)
            raise

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                ws: BybitPerpetualWebSocketAdaptor = await self._create_websocket_connection()
                self.logger().info("Authenticating to User Stream...")
                await self._authenticate(ws)
                self.logger().info("Successfully authenticated to User Stream.")
                await self._subscribe_to_events(ws)
                self.logger().info("Successfully subscribed to user events.")

                async for msg in ws.iter_messages():
                    self._last_recv_time = int(time.time())
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(
                    f"Unexpected error with Bybit Perpetual WebSocket connection. Retrying in 30 seconds. ({ex})",
                    exc_info=True
                )
                await ws.close()
                await asyncio.sleep(30.0)
