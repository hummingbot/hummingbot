import asyncio
import logging
from typing import Optional

import hummingbot.connector.exchange.tegro.tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS
from hummingbot.connector.exchange.tegro.tegro_auth import TegroAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

MESSAGE_TIMEOUT = 20.0
PING_TIMEOUT = 5.0


class TegroUserStreamDataSource(UserStreamTrackerDataSource):

    _bpusds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpusds_logger is None:
            cls._bpusds_logger = logging.getLogger(__name__)
        return cls._bpusds_logger

    def __init__(
        self,
        auth: TegroAuth,
        domain: str = CONSTANTS.DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
        api_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__()
        self._domain = domain
        self._throttler = throttler
        self._api_factory: WebAssistantsFactory = api_factory or web_utils.build_api_factory(
            auth=auth
        )
        self._auth: TegroAuth = auth
        self._ws_assistant: Optional[WSAssistant] = None

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _send_ping(self, websocket_assistant: WSAssistant):
        API_KEY = self._auth._api_key
        payload = {"action": "subscribe", "channelId": API_KEY}
        ping_request: WSJSONRequest = WSJSONRequest(payload=payload)
        await websocket_assistant.send(ping_request)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        ws = None
        while True:
            try:
                # # establish initial connection to websocket
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=web_utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain), ping_timeout=PING_TIMEOUT)

                # # send auth request
                API_KEY = self._auth._api_key
                subscribe_payload = {"action": "subscribe", "channelId": API_KEY}

                subscribe_request: WSJSONRequest = WSJSONRequest(
                    payload=subscribe_payload,
                    is_auth_required=False
                )
                await ws.send(subscribe_request)
                await self._send_ping(ws)
                async for msg in ws.iter_messages():
                    if msg.data is not None and len(msg.data) > 0:
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
                await self._sleep(5)
