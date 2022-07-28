import aiohttp
import asyncio
import logging
import time
import ujson

from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_utils
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class NdaxAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, throttler: AsyncThrottler, auth_assistant: NdaxAuth, shared_client: Optional[aiohttp.ClientSession] = None, domain: Optional[str] = None):
        super().__init__()
        self._shared_client = shared_client or self._get_session_instance()
        self._ws_adaptor = None
        self._auth_assistant: NdaxAuth = auth_assistant
        self._last_recv_time: float = 0
        self._account_id: Optional[int] = None
        self._oms_id: Optional[int] = None
        self._domain = domain
        self._throttler = throttler

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    async def _init_websocket_connection(self) -> NdaxWebSocketAdaptor:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            if self._ws_adaptor is None:
                ws = await self._shared_client.ws_connect(ndax_utils.wss_url(self._domain))
                self._ws_adaptor = NdaxWebSocketAdaptor(throttler=self._throttler, websocket=ws)
            return self._ws_adaptor
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network(f"Unexpected error occurred during {CONSTANTS.EXCHANGE_NAME} WebSocket Connection "
                                  f"({ex})")
            raise

    async def _authenticate(self, ws: NdaxWebSocketAdaptor):
        """
        Authenticates user to websocket
        """
        try:
            auth_payload: Dict[str, Any] = self._auth_assistant.get_ws_auth_payload()
            async with self._throttler.execute_task(CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME):
                await ws.send_request(CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME, auth_payload)
            auth_resp = await ws.receive()
            auth_payload: Dict[str, Any] = ws.payload_from_raw_message(auth_resp.data)

            if not auth_payload["Authenticated"]:
                self.logger().error(f"Response: {auth_payload}",
                                    exc_info=True)
                raise Exception("Could not authenticate websocket connection with NDAX")

            auth_user = auth_payload.get("User")
            self._account_id = auth_user.get("AccountId")
            self._oms_id = auth_user.get("OMSId")

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().error(f"Error occurred when authenticating to user stream ({ex})",
                                exc_info=True)
            raise

    async def _subscribe_to_events(self, ws: NdaxWebSocketAdaptor):
        """
        Subscribes to User Account Events
        """
        payload = {"AccountId": self._account_id,
                   "OMSId": self._oms_id}
        try:
            async with self._throttler.execute_task(CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME):
                await ws.send_request(CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME, payload)

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
                ws: NdaxWebSocketAdaptor = await self._init_websocket_connection()
                self.logger().info("Authenticating to User Stream...")
                await self._authenticate(ws)
                self.logger().info("Successfully authenticated to User Stream.")
                await self._subscribe_to_events(ws)
                self.logger().info("Successfully subscribed to user events.")

                async for msg in ws.iter_messages():
                    self._last_recv_time = int(time.time())
                    output.put_nowait(ujson.loads(msg))
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(
                    f"Unexpected error with NDAX WebSocket connection. Retrying in 30 seconds. ({ex})",
                    exc_info=True
                )
                if self._ws_adaptor is not None:
                    await self._ws_adaptor.close()
                    self._ws_adaptor = None
                await asyncio.sleep(30.0)
