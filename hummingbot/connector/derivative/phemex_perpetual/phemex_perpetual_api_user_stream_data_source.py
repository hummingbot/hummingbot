import asyncio
from typing import Any, Dict, Optional

from hummingbot.connector.derivative.phemex_perpetual import (
    phemex_perpetual_constants as CONSTANTS,
    phemex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_auth import PhemexPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class PhemexPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: PhemexPerpetualAuth,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._api_factory = api_factory
        self._domain = domain
        self.pong_received_event = asyncio.Event()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        url = web_utils.wss_url(CONSTANTS.PRIVATE_WS_ENDPOINT, self._domain)

        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WSS_CONNECTION_LIMIT_ID):
            await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT)  # protocol level ping used because it is not enforced at the application level

        await self._authenticate_ws(ws)

        return ws

    async def _authenticate_ws(self, ws: WSAssistant) -> WSAssistant:
        auth_request = self._auth.get_ws_auth_payload()
        login_request = WSJSONRequest(payload=auth_request)

        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WSS_MESSAGE_LIMIT_ID):
            await ws.send(login_request)

        response: WSResponse = await ws.receive()
        message = response.data
        if message["error"] is not None or message.get("result").get("status") != "success":
            self.logger().error("Error authenticating the private websocket connection")
            raise IOError(f"Private websocket connection authentication failed: {message}.")

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            payload = {
                "id": 0,
                "method": "aop_p.subscribe",
                "params": []
            }
            subscription_request = WSJSONRequest(payload)

            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WSS_MESSAGE_LIMIT_ID):
                await websocket_assistant.send(subscription_request)

            response: WSResponse = await websocket_assistant.receive()
            message = response.data
            if message["error"] is not None or message.get("result").get("status") != "success":
                raise IOError(f"Private account channel subscription failed: {message}.")

            self.logger().info("Subscribed to the private account channel...")
            safe_ensure_future(self.ping_loop(ws=websocket_assistant))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                "Unexpected error occurred subscribing to the private account channel..."
            )
            raise

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def ping_loop(self, ws: WSAssistant):
        count = 0
        while ws._connection.connected:
            ping_request: WSJSONRequest = WSJSONRequest({"id": 0, "method": "server.ping", "params": []})
            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WSS_MESSAGE_LIMIT_ID):
                await ws.send(ping_request)
            try:
                await asyncio.wait_for(self.pong_received_event.wait(), timeout=5)
                self.pong_received_event.clear()
                count = 0
                await self._sleep(5.0)
            except asyncio.TimeoutError:
                count += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                await ws._connection.disconnect()
            finally:
                if count == 3:
                    await ws._connection.disconnect()

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0:
            if event_message.get("result", "") == "pong":
                self.pong_received_event.set()
            else:
                queue.put_nowait(event_message)
