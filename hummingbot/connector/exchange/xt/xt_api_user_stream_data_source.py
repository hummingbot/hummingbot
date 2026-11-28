import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.xt import xt_constants as CONSTANTS, xt_web_utils as web_utils
from hummingbot.connector.exchange.xt.xt_auth import XtAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest, WSPlainTextRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xt.xt_exchange import XtExchange


class XtAPIUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 24 * 60 * 60

    USER_STREAM_TOPICS = {
        CONSTANTS.WS_PRIVATE_ORDER_TOPIC,
        CONSTANTS.WS_PRIVATE_TRADE_TOPIC,
        CONSTANTS.WS_PRIVATE_BALANCE_TOPIC,
    }

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: XtAuth,
        trading_pairs: List[str],
        connector: "XtExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory
        self._current_listen_key: Optional[str] = None
        self._listen_key_creation_time = 0.0
        self._next_request_id = 1

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_PRIVATE_URL,
            ping_timeout=CONSTANTS.WS_RESPONSE_TIMEOUT,
            message_timeout=CONSTANTS.WS_RESPONSE_TIMEOUT,
            ws_headers={"Sec-WebSocket-Extensions": "permessage-deflate"},
        )
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            listen_key = await self._get_listen_key()
            payload = {
                "method": "subscribe",
                "params": [
                    CONSTANTS.WS_PRIVATE_ORDER_TOPIC,
                    CONSTANTS.WS_PRIVATE_TRADE_TOPIC,
                    CONSTANTS.WS_PRIVATE_BALANCE_TOPIC,
                ],
                "listenKey": listen_key,
                "id": self._new_request_id(),
            }
            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIPTION_LIMIT_ID):
                await websocket_assistant.send(WSJSONRequest(payload=payload))
            self.logger().info("Subscribed to XT private order, trade, and balance channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to XT private streams.")
            raise

    async def _send_ping(self, websocket_assistant: WSAssistant):
        await websocket_assistant.send(WSPlainTextRequest(CONSTANTS.WS_PING_REQUEST))

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            # XT tokens expire after two days. Renew through the native reconnect path.
            if self._time() - self._listen_key_creation_time >= self.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                raise ConnectionError("XT listenKey renewal required.")
            try:
                await asyncio.wait_for(
                    super()._process_websocket_messages(websocket_assistant, queue),
                    timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
                )
                return
            except asyncio.TimeoutError:
                await self._send_ping(websocket_assistant)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        self._current_listen_key = None
        await super()._on_user_stream_interruption(websocket_assistant)

    async def _get_listen_key(self) -> str:
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.private_rest_url(path_url=CONSTANTS.WS_TOKEN_PATH_URL, domain=self._domain),
            method=RESTMethod.POST,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.WS_TOKEN_PATH_URL,
        )
        result = web_utils.result_from_response(response, "websocket token")
        listen_key = result["accessToken"]
        if not isinstance(listen_key, str) or not listen_key:
            raise IOError("XT websocket token response has no accessToken.")
        self._current_listen_key = listen_key
        self._listen_key_creation_time = self._time()
        return listen_key

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message == CONSTANTS.WS_PONG_RESPONSE:
            return
        if not event_message:
            return
        if not isinstance(event_message, dict):
            self.logger().debug(f"Received XT private websocket message in unknown format: {event_message}")
            return

        topic = event_message.get("topic")
        if topic in self.USER_STREAM_TOPICS and isinstance(event_message.get("data"), dict):
            queue.put_nowait(event_message)
            return

        if event_message.get("code") == 2:
            raise ConnectionError("XT listenKey is invalid; reconnecting with a fresh token.")
        if event_message.get("code") == 0:
            self.logger().info(f"XT private websocket subscription acknowledged: {event_message}")
        elif event_message.get("code") is not None:
            raise IOError(f"XT private websocket subscription failed: {event_message}")

    def _new_request_id(self) -> str:
        request_id = str(self._next_request_id)
        self._next_request_id += 1
        return request_id
