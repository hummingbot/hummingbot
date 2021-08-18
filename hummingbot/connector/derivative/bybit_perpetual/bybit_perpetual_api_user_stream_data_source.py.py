import asyncio
import logging
import websockets

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


class BybitPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth_assistant: BybitPerpetualAuth, domain: Optional[str] = None):
        super().__init__()
        self._websocket_client: Optional[BybitPerpetualWebSocketAdaptor] = None
        self._auth_assistant: BybitPerpetualAuth = auth_assistant
        self._last_recv_time: float = 0
        self._domain = domain

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _init_websocket_connection(self) -> BybitPerpetualWebSocketAdaptor:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        self.logger().info("_init_websocket_connection")
        try:
            if self._websocket_client is None:
                ws = await websockets.connect(bybit_perpetual_utils.wss_url(self._domain))
                self._websocket_client = BybitPerpetualWebSocketAdaptor(websocket=ws)
            return self._websocket_client
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
        self.logger().info("_authenticate")
        try:
            auth_payload: Dict[str, Any] = self._auth_assistant.get_ws_auth_payload()
            await ws.send_request(CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME, auth_payload)
            auth_resp = await ws.recv()
            auth_payload: Dict[str, Any] = ws.payload_from_raw_message(auth_resp)

            if not auth_payload["request"] or not auth_payload["request"]["op"] or auth_payload["request"]["op"] != "auth":
                self.logger().error(f"Response: {auth_payload}",
                                    exc_info=True)
                raise Exception("Could not authenticate websocket connection with Bybit Perpetual")

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().error(f"Error occurred when authenticating to user stream ({ex})",
                                exc_info=True)
            raise
