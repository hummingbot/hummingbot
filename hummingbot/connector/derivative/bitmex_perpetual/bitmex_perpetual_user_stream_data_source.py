import asyncio
import logging
import time
from typing import Optional

import hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_auth import BitmexPerpetualAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BitmexPerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    _bpusds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpusds_logger is None:
            cls._bpusds_logger = logging.getLogger(__name__)
        return cls._bpusds_logger

    def __init__(
        self,
        auth: BitmexPerpetualAuth,
        domain: str = "bitmex_perpetual",
        throttler: Optional[AsyncThrottler] = None,
        api_factory: Optional[WebAssistantsFactory] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
    ):
        super().__init__()
        self._time_synchronizer = time_synchronizer
        self._domain = domain
        self._throttler = throttler
        self._api_factory: WebAssistantsFactory = api_factory or web_utils.build_api_factory(
            auth=auth
        )
        self._auth = auth
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

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                expires = int(time.time()) + 25
                url = web_utils.wss_url("", self._domain)
                # # establish initial connection to websocket
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=url)

                # # send auth request
                API_KEY = self._auth.api_key
                signature = await self._auth.generate_ws_signature(str(expires))
                auth_payload = {"op": "authKeyExpires", "args": [API_KEY, expires, signature]}

                auth_request: WSJSONRequest = WSJSONRequest(
                    payload=auth_payload,
                    is_auth_required=False
                )
                await ws.send(auth_request)
                # await ws.ping()  # to update last_recv_timestamp

                # # send subscribe
                # position - Updates on your positions
                # order - Live updates on your orders
                # margin - Updates on your current account balance and margin requirements
                # wallet - Bitcoin address balance data, including total deposits & withdrawals
                subscribe_payload = {"op": "subscribe", "args": ["position", "order", "margin", "wallet"]}
                subscribe_request: WSJSONRequest = WSJSONRequest(
                    payload=subscribe_payload,
                    is_auth_required=False
                )
                await ws.send(subscribe_request)

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
                await self._sleep(5)
