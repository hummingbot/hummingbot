import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

import aiohttp

import hummingbot.connector.derivative.true_perpetual.true_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.true_perpetual.true_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.true_perpetual.true_perpetual_auth import TruePerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.true_perpetual.true_perpetual_derivative import TruePerpetualDerivative


class TruePerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Private account stream: GET /api/bot/v1/stream (server sent events, signed like any private read).

    Events: ready, account (the normalized snapshot whenever positions, open orders or equity change,
    checked every 2 s), warning, heartbeat (15 s), bye (the server closes after 30 minutes; reconnect).
    Fills and terminal order states are not on this stream, so the connector keeps polling
    GET /orders/{id} and GET /fills for in flight orders; the stream makes balances and positions
    move the moment the venue does.
    """

    _logger: Optional[HummingbotLogger] = None
    RECONNECT_DELAY = 5.0

    def __init__(
            self,
            auth: TruePerpetualAuth,
            connector: "TruePerpetualDerivative",
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._last_recv_time: float = 0.0
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                await self._consume_stream(output)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.logger().warning(f"TRUE account stream interrupted ({err}). Reconnecting in {self.RECONNECT_DELAY:.0f} s...")
                await self._sleep(self.RECONNECT_DELAY)

    async def _consume_stream(self, output: asyncio.Queue):
        url = web_utils.private_rest_url(CONSTANTS.STREAM_PATH_URL, domain=self._domain)
        timestamp = str(int(self._connector.time_synchronizer_time() * 1e3))
        headers = self._auth.sign_headers(
            timestamp=timestamp,
            method="GET",
            path_with_query=TruePerpetualAuth.path_with_query(url),
            raw_body="",
        )
        headers["Accept"] = "text/event-stream"
        headers["Cache-Control"] = "no-cache"
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=60)
        async with session.get(url, headers=headers, timeout=timeout) as response:
            if response.status >= 400:
                body = (await response.text())[:300]
                raise IOError(f"HTTP {response.status} opening the account stream: {body}")
            self._last_recv_time = time.time()
            event = "message"
            async for raw_line in response.content:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    continue
                if line.startswith("event:"):
                    event = line[6:].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                self._last_recv_time = time.time()
                payload = line[5:].strip()
                try:
                    data: Any = json.loads(payload) if payload else {}
                except ValueError:
                    continue
                if event == "bye":
                    self.logger().info("TRUE account stream reached its lifetime; reconnecting.")
                    return
                if event in ("heartbeat", "ready"):
                    event = "message"
                    continue
                await self._process_event_message(event_message={"event": event, "data": data}, queue=output)
                event = "message"
        raise ConnectionError("account stream closed by the server")

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message:
            queue.put_nowait(event_message)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _connected_websocket_assistant(self) -> WSAssistant:
        raise NotImplementedError("TRUE delivers the account stream over server sent events, not a websocket")

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass

    async def stop(self):
        await super().stop()
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
